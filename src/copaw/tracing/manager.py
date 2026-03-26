# -*- coding: utf-8 -*-
"""Trace manager module.

Provides the TraceManager for event collection, batching, and storage.
"""
import asyncio
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Optional

from .config import TracingConfig
from .database import TDSQLConnection
from .models import EventType, Span, Trace, TraceStatus
from .store import TraceStore, sanitize_dict, sanitize_string

logger = logging.getLogger(__name__)

# Context variable for current trace
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar("current_trace", default=None)


class TraceContext:
    """Context for the current trace."""

    def __init__(
        self,
        trace_id: str,
        user_id: str,
        session_id: str,
        channel: str,
    ):
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.channel = channel
        self.start_time = datetime.now()
        self.trace: Optional[Trace] = None
        self._span_stack: list[str] = []

    def push_span(self, span_id: str) -> None:
        """Push a span ID onto the stack."""
        self._span_stack.append(span_id)

    def pop_span(self) -> Optional[str]:
        """Pop a span ID from the stack."""
        return self._span_stack.pop() if self._span_stack else None

    @property
    def current_span_id(self) -> Optional[str]:
        """Get current span ID."""
        return self._span_stack[-1] if self._span_stack else None


def get_current_trace() -> Optional[TraceContext]:
    """Get the current trace context."""
    return _current_trace.get()


def set_current_trace(ctx: Optional[TraceContext]) -> None:
    """Set the current trace context."""
    _current_trace.set(ctx)


class TraceManager:
    """Manager for trace lifecycle and event collection.

    Handles:
    - Trace creation and completion
    - Span creation and updates
    - Batch writing for performance
    - Data sanitization
    """

    def __init__(
        self,
        config: TracingConfig,
        store: Optional[TraceStore] = None,
    ):
        """Initialize trace manager.

        Args:
            config: Tracing configuration
            store: Optional trace store (created if not provided)
        """
        self.config = config
        self._store = store
        self._db: Optional[TDSQLConnection] = None

        # Batch queue for spans
        self._span_queue: list[Span] = []
        self._span_queue_lock = asyncio.Lock()

        # Pending spans cache (for update before flush)
        self._pending_spans: dict[str, Span] = {}

        # Background flush task
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

        # Active traces
        self._active_traces: dict[str, Trace] = {}

    @property
    def store(self) -> TraceStore:
        """Get trace store."""
        if self._store is None:
            raise RuntimeError("TraceManager not initialized")
        return self._store

    @property
    def enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self.config.enabled

    async def initialize(self) -> None:
        """Initialize the trace manager."""
        if not self.config.enabled:
            logger.info("Tracing is disabled")
            return

        # Create database connection if configured
        if self.config.database:
            self._db = TDSQLConnection(self.config.database)
            try:
                await self._db.connect()
            except Exception as e:
                logger.warning("Failed to connect to database: %s, using in-memory storage", e)
                self._db = None

        # Create store
        self._store = TraceStore(self.config, self._db)
        await self._store.initialize()

        # Start flush task
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())

        logger.info("TraceManager initialized")

    async def close(self) -> None:
        """Close the trace manager."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Final flush
        await self._flush_spans()

        if self._store:
            await self._store.close()

        if self._db:
            await self._db.close()

        logger.info("TraceManager closed")

    # Trace lifecycle

    async def start_trace(
        self,
        user_id: str,
        session_id: str,
        channel: str,
        trace_id: Optional[str] = None,
    ) -> str:
        """Start a new trace.

        Args:
            user_id: User identifier
            session_id: Session identifier
            channel: Channel identifier
            trace_id: Optional trace ID (generated if not provided)

        Returns:
            Trace ID
        """
        if not self.enabled:
            return trace_id or str(uuid.uuid4())

        trace_id = trace_id or str(uuid.uuid4())

        trace = Trace(
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            channel=channel,
            start_time=datetime.now(),
            status=TraceStatus.RUNNING,
        )

        await self.store.create_trace(trace)
        self._active_traces[trace_id] = trace

        # Create context
        ctx = TraceContext(trace_id, user_id, session_id, channel)
        ctx.trace = trace
        set_current_trace(ctx)

        return trace_id

    async def end_trace(
        self,
        trace_id: str,
        status: TraceStatus = TraceStatus.COMPLETED,
        error: Optional[str] = None,
    ) -> None:
        """End a trace.

        Args:
            trace_id: Trace identifier
            status: Final status
            error: Optional error message
        """
        if not self.enabled:
            return

        # Flush pending spans before ending trace
        await self._flush_spans()

        trace = self._active_traces.pop(trace_id, None) or await self.store.get_trace(trace_id)
        if trace is None:
            logger.warning("Trace not found: %s", trace_id)
            return

        trace.end_time = datetime.now()
        trace.duration_ms = int((trace.end_time - trace.start_time).total_seconds() * 1000)
        trace.status = status
        trace.error = error

        await self.store.update_trace(trace)

        # Clear context
        ctx = get_current_trace()
        if ctx and ctx.trace_id == trace_id:
            set_current_trace(None)

    # Span operations

    async def emit_span(
        self,
        trace_id: str,
        event_type: EventType,
        name: str,
        user_id: str,
        session_id: str,
        channel: str,
        parent_span_id: Optional[str] = None,
        model_name: Optional[str] = None,
        input_tokens: Optional[int] = None,
        tool_name: Optional[str] = None,
        skill_name: Optional[str] = None,
        tool_input: Optional[dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
    ) -> str:
        """Emit a new span event.

        Args:
            trace_id: Trace identifier
            event_type: Event type
            name: Span name
            user_id: User identifier
            session_id: Session identifier
            channel: Channel identifier
            parent_span_id: Optional parent span ID
            model_name: Optional model name
            input_tokens: Optional input token count
            tool_name: Optional tool name
            skill_name: Optional skill name
            tool_input: Optional tool input (will be sanitized)
            start_time: Optional start time

        Returns:
            Span ID
        """
        if not self.enabled:
            return str(uuid.uuid4())

        span_id = str(uuid.uuid4())

        # Get parent from context if not provided
        if parent_span_id is None:
            ctx = get_current_trace()
            if ctx and ctx.trace_id == trace_id:
                parent_span_id = ctx.current_span_id

        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            event_type=event_type,
            start_time=start_time or datetime.now(),
            user_id=user_id,
            session_id=session_id,
            channel=channel,
            model_name=model_name,
            input_tokens=input_tokens,
            tool_name=tool_name,
            skill_name=skill_name,
            tool_input=sanitize_dict(tool_input) if self.config.sanitize_output else tool_input,
        )

        # Add to pending cache and queue atomically
        async with self._span_queue_lock:
            self._pending_spans[span_id] = span
            self._span_queue.append(span)

        return span_id

    async def update_span(
        self,
        span_id: str,
        trace_id: str,
        output_tokens: Optional[int] = None,
        input_tokens: Optional[int] = None,
        tool_output: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> None:
        """Update an existing span.

        Args:
            span_id: Span identifier
            trace_id: Trace identifier
            output_tokens: Optional output token count
            input_tokens: Optional input token count (updates span if provided)
            tool_output: Optional tool output (will be sanitized)
            error: Optional error message
            metadata: Optional metadata
            span: Optional span object (to avoid re-fetching)
        """
        if not self.enabled:
            return

        # Use provided span or find it
        if span is None:
            # First, check pending cache (spans not yet flushed)
            span = self._pending_spans.get(span_id)

            # If not in cache, check store
            if span is None:
                spans = await self.store.get_spans(trace_id)
                for s in spans:
                    if s.span_id == span_id:
                        span = s
                        break

        if span is None:
            logger.warning("Span not found for update: %s", span_id)
            return

        # Update span
        span.end_time = datetime.now()
        span.duration_ms = int((span.end_time - span.start_time).total_seconds() * 1000)
        span.output_tokens = output_tokens
        # Update input_tokens if provided (for LLM calls where we only know after the fact)
        if input_tokens is not None and input_tokens > 0:
            span.input_tokens = input_tokens
        span.tool_output = (
            sanitize_string(tool_output, self.config.max_output_length)
            if self.config.sanitize_output else tool_output
        )
        span.error = error
        span.metadata = metadata

        # Update trace totals
        trace = self._active_traces.get(trace_id)
        if trace:
            if output_tokens:
                trace.total_output_tokens += output_tokens
            if span.input_tokens:
                trace.total_input_tokens += span.input_tokens
            if span.model_name:
                trace.model_name = span.model_name
            if span.tool_name and span.tool_name not in trace.tools_used:
                trace.tools_used.append(span.tool_name)
            if span.skill_name and span.skill_name not in trace.skills_used:
                trace.skills_used.append(span.skill_name)

        # Only update store if span is not in pending cache (already flushed)
        if span_id not in self._pending_spans:
            await self.store.update_span(span)

    async def emit_llm_input(
        self,
        trace_id: str,
        model_name: str,
        input_tokens: int,
        user_id: str,
        session_id: str,
        channel: str,
    ) -> str:
        """Emit LLM input event.

        Args:
            trace_id: Trace identifier
            model_name: Model name
            input_tokens: Input token count
            user_id: User identifier
            session_id: Session identifier
            channel: Channel identifier

        Returns:
            Span ID
        """
        return await self.emit_span(
            trace_id=trace_id,
            event_type=EventType.LLM_INPUT,
            name=f"llm_call_{model_name}",
            user_id=user_id,
            session_id=session_id,
            channel=channel,
            model_name=model_name,
            input_tokens=input_tokens,
        )

    async def emit_llm_output(
        self,
        trace_id: str,
        span_id: str,
        output_tokens: int,
        input_tokens: int = 0,
    ) -> None:
        """Emit LLM output event (updates the span).

        Args:
            trace_id: Trace identifier
            span_id: Span identifier from LLM input
            output_tokens: Output token count
            input_tokens: Input token count (updates span if provided)
        """
        await self.update_span(
            span_id=span_id,
            trace_id=trace_id,
            output_tokens=output_tokens,
            input_tokens=input_tokens if input_tokens > 0 else None,
        )

    async def emit_tool_call_start(
        self,
        trace_id: str,
        tool_name: str,
        tool_input: Optional[dict[str, Any]],
        user_id: str,
        session_id: str,
        channel: str,
    ) -> str:
        """Emit tool call start event.

        Args:
            trace_id: Trace identifier
            tool_name: Tool name
            tool_input: Tool input
            user_id: User identifier
            session_id: Session identifier
            channel: Channel identifier

        Returns:
            Span ID
        """
        return await self.emit_span(
            trace_id=trace_id,
            event_type=EventType.TOOL_CALL_START,
            name=f"tool_{tool_name}",
            user_id=user_id,
            session_id=session_id,
            channel=channel,
            tool_name=tool_name,
            tool_input=tool_input,
        )

    async def emit_tool_call_end(
        self,
        trace_id: str,
        span_id: str,
        tool_output: Optional[str],
        error: Optional[str] = None,
    ) -> None:
        """Emit tool call end event.

        Args:
            trace_id: Trace identifier
            span_id: Span identifier from tool call start
            tool_output: Tool output
            error: Optional error message
        """
        # First, find the span (in pending cache or store)
        span = self._pending_spans.get(span_id)
        if span is None:
            spans = await self.store.get_spans(trace_id)
            for s in spans:
                if s.span_id == span_id:
                    span = s
                    break

        if span is None:
            logger.warning("Span not found for tool_call_end: %s", span_id)
            return

        # Update event_type to TOOL_CALL_END for proper statistics
        span.event_type = EventType.TOOL_CALL_END

        # Update other fields, passing the span object to avoid re-fetching
        await self.update_span(
            span_id=span_id,
            trace_id=trace_id,
            tool_output=tool_output,
            error=error,
            span=span,
        )

    async def emit_skill_invocation(
        self,
        trace_id: str,
        skill_name: str,
        user_id: str,
        session_id: str,
        channel: str,
    ) -> str:
        """Emit skill invocation event.

        Args:
            trace_id: Trace identifier
            skill_name: Skill name
            user_id: User identifier
            session_id: Session identifier
            channel: Channel identifier

        Returns:
            Span ID
        """
        return await self.emit_span(
            trace_id=trace_id,
            event_type=EventType.SKILL_INVOCATION,
            name=f"skill_{skill_name}",
            user_id=user_id,
            session_id=session_id,
            channel=channel,
            skill_name=skill_name,
        )

    # Session events

    async def emit_session_start(
        self,
        trace_id: str,
        user_id: str,
        session_id: str,
        channel: str,
    ) -> str:
        """Emit session start event.

        Args:
            trace_id: Trace identifier
            user_id: User identifier
            session_id: Session identifier
            channel: Channel identifier

        Returns:
            Span ID
        """
        return await self.emit_span(
            trace_id=trace_id,
            event_type=EventType.SESSION_START,
            name="session_start",
            user_id=user_id,
            session_id=session_id,
            channel=channel,
        )

    async def emit_session_end(
        self,
        trace_id: str,
    ) -> None:
        """Emit session end event.

        Args:
            trace_id: Trace identifier
        """
        ctx = get_current_trace()
        if ctx and ctx.trace_id == trace_id:
            # Find session start span and create end
            pass  # Session end is implicit in trace end

    # Background flush

    async def _flush_loop(self) -> None:
        """Background loop for flushing queued spans."""
        while self._running:
            try:
                await asyncio.sleep(self.config.flush_interval)
                await self._flush_spans()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in flush loop: %s", e)

    async def _flush_spans(self) -> None:
        """Flush queued spans to storage."""
        async with self._span_queue_lock:
            if not self._span_queue:
                return
            spans = self._span_queue.copy()
            self._span_queue.clear()
            # Clear pending cache atomically with queue clear
            for span in spans:
                self._pending_spans.pop(span.span_id, None)

        if spans:
            try:
                await self.store.batch_create_spans(spans)
            except Exception as e:
                logger.error("Failed to flush spans: %s", e)

    # Query methods (delegate to store)

    async def get_overview_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Get overview statistics."""
        return await self.store.get_overview_stats(start_date, end_date)

    async def get_users(self, page: int = 1, page_size: int = 20, user_id: Optional[str] = None):
        """Get users list."""
        return await self.store.get_users(page, page_size, user_id)

    async def get_user_stats(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Get user statistics."""
        return await self.store.get_user_stats(user_id, start_date, end_date)

    async def get_traces(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Get traces list."""
        return await self.store.get_traces(
            page, page_size, user_id, session_id, status, start_date, end_date
        )

    async def get_trace_detail(self, trace_id: str):
        """Get trace detail."""
        return await self.store.get_trace_detail(trace_id)


# Global trace manager instance
_trace_manager: Optional[TraceManager] = None


def get_trace_manager() -> TraceManager:
    """Get the global trace manager.

    Raises:
        RuntimeError: If trace manager not initialized

    Returns:
        TraceManager instance
    """
    if _trace_manager is None:
        raise RuntimeError("TraceManager not initialized. Call init_trace_manager() first.")
    return _trace_manager


async def init_trace_manager(config: Optional[TracingConfig] = None) -> TraceManager:
    """Initialize the global trace manager.

    Args:
        config: Optional tracing configuration (uses defaults if not provided)

    Returns:
        TraceManager instance
    """
    global _trace_manager

    if _trace_manager is not None:
        return _trace_manager

    config = config or TracingConfig()
    _trace_manager = TraceManager(config)
    await _trace_manager.initialize()

    return _trace_manager


async def close_trace_manager() -> None:
    """Close the global trace manager."""
    global _trace_manager

    if _trace_manager is not None:
        await _trace_manager.close()
        _trace_manager = None
