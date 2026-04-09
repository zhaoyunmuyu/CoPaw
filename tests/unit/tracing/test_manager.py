# -*- coding: utf-8 -*-
"""Tests for TraceManager and TraceContext."""
# pylint: disable=protected-access,redefined-outer-name,unused-import

import pytest

from copaw.tracing.config import TracingConfig
from copaw.tracing.manager import (
    TraceContext,
    TraceManager,
    get_current_trace,
    set_current_trace,
    get_trace_manager,
    init_trace_manager,
    close_trace_manager,
    has_trace_manager,
)
from copaw.tracing.models import EventType, TraceStatus


@pytest.fixture(autouse=True)
def reset_global_manager():
    """Reset global trace manager before and after each test."""
    # Import the module to access the global variable
    import copaw.tracing.manager as manager_module

    manager_module._trace_manager = None  # pylint: disable=protected-access
    yield
    manager_module._trace_manager = None  # pylint: disable=protected-access


@pytest.fixture
def enabled_config():
    """Create enabled tracing config."""
    return TracingConfig(enabled=True, batch_size=10, flush_interval=1)


@pytest.fixture
def disabled_config():
    """Create disabled tracing config."""
    return TracingConfig(enabled=False)


class TestTraceContext:
    """Tests for TraceContext class."""

    def test_creation(self):
        """Test creating TraceContext."""
        ctx = TraceContext(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        assert ctx.trace_id == "trace-1"
        assert ctx.user_id == "user-1"
        assert ctx.session_id == "session-1"
        assert ctx.channel == "console"
        assert ctx.trace is None

    def test_span_stack(self):
        """Test span stack operations."""
        ctx = TraceContext(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        # Initially empty
        assert ctx.current_span_id is None

        # Push spans
        ctx.push_span("span-1")
        assert ctx.current_span_id == "span-1"

        ctx.push_span("span-2")
        assert ctx.current_span_id == "span-2"

        # Pop spans
        assert ctx.pop_span() == "span-2"
        assert ctx.current_span_id == "span-1"

        assert ctx.pop_span() == "span-1"
        assert ctx.current_span_id is None

    def test_pop_empty_stack(self):
        """Test popping from empty stack returns None."""
        ctx = TraceContext(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        assert ctx.pop_span() is None


class TestCurrentTraceContext:
    """Tests for get_current_trace and set_current_trace."""

    def test_get_default_none(self):
        """Test get_current_trace returns None by default."""
        assert get_current_trace() is None

    def test_set_and_get(self):
        """Test set_current_trace and get_current_trace."""
        ctx = TraceContext(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        set_current_trace(ctx)
        assert get_current_trace() is ctx

        set_current_trace(None)
        assert get_current_trace() is None


class TestTraceManager:
    """Tests for TraceManager class."""

    def test_creation_disabled(self, disabled_config):
        """Test TraceManager creation with disabled config."""
        manager = TraceManager(disabled_config)

        assert manager.enabled is False
        assert manager.config == disabled_config

    def test_creation_enabled(self, enabled_config):
        """Test TraceManager creation with enabled config."""
        manager = TraceManager(enabled_config)

        assert manager.enabled is True

    @pytest.mark.asyncio
    async def test_initialize_disabled(self, disabled_config, tmp_path):
        """Test initializing disabled manager."""
        manager = TraceManager(disabled_config)
        await manager.initialize(tmp_path)

        # Should not create store when disabled
        assert manager._store is None  # pylint: disable=protected-access

    @pytest.mark.asyncio
    async def test_initialize_enabled(self, enabled_config, tmp_path):
        """Test initializing enabled manager."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        assert manager._store is not None  # pylint: disable=protected-access
        assert manager._running is True  # pylint: disable=protected-access

        await manager.close()

    @pytest.mark.asyncio
    async def test_close(self, enabled_config, tmp_path):
        """Test closing manager."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)
        await manager.close()

        assert manager._running is False  # pylint: disable=protected-access
        assert manager._flush_task is None  # pylint: disable=protected-access

    @pytest.mark.asyncio
    async def test_start_trace_disabled(self, disabled_config):
        """Test start_trace when disabled returns a UUID."""
        manager = TraceManager(disabled_config)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        assert trace_id is not None
        # Should not create active trace
        assert (
            trace_id not in manager._active_traces
        )  # pylint: disable=protected-access

    @pytest.mark.asyncio
    async def test_start_trace_enabled(self, enabled_config, tmp_path):
        """Test start_trace when enabled."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
            user_message="Hello",
        )

        assert trace_id is not None
        assert (
            trace_id in manager._active_traces
        )  # pylint: disable=protected-access
        assert get_current_trace() is not None

        await manager.close()

    @pytest.mark.asyncio
    async def test_end_trace(self, enabled_config, tmp_path):
        """Test end_trace updates trace status."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        await manager.end_trace(trace_id, TraceStatus.COMPLETED)

        assert (
            trace_id not in manager._active_traces
        )  # pylint: disable=protected-access
        trace = await manager.store.get_trace(trace_id)
        assert trace.status == TraceStatus.COMPLETED
        assert trace.end_time is not None
        assert trace.duration_ms is not None

        await manager.close()

    @pytest.mark.asyncio
    async def test_end_trace_with_error(self, enabled_config, tmp_path):
        """Test end_trace with error status."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        await manager.end_trace(
            trace_id,
            TraceStatus.ERROR,
            "Something went wrong",
        )

        trace = await manager.store.get_trace(trace_id)
        assert trace.status == TraceStatus.ERROR
        assert trace.error == "Something went wrong"

        await manager.close()

    @pytest.mark.asyncio
    async def test_emit_span_disabled(self, disabled_config):
        """Test emit_span when disabled returns a UUID."""
        manager = TraceManager(disabled_config)

        span_id = await manager.emit_span(
            trace_id="trace-1",
            event_type=EventType.LLM_INPUT,
            name="test_span",
        )

        assert span_id is not None

    @pytest.mark.asyncio
    async def test_emit_span_enabled(self, enabled_config, tmp_path):
        """Test emit_span when enabled."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        span_id = await manager.emit_span(
            trace_id=trace_id,
            event_type=EventType.LLM_INPUT,
            name="llm_call_gpt-4",
            model_name="gpt-4",
            input_tokens=100,
        )

        assert span_id is not None

        # Check span is in queue
        assert (
            span_id in manager._pending_spans
        )  # pylint: disable=protected-access

        await manager.close()

    @pytest.mark.asyncio
    async def test_emit_llm_input(self, enabled_config, tmp_path):
        """Test emit_llm_input convenience method."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        span_id = await manager.emit_llm_input(
            trace_id=trace_id,
            model_name="gpt-4",
            input_tokens=100,
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        assert span_id is not None
        span = manager._pending_spans[
            span_id
        ]  # pylint: disable=protected-access
        assert span.event_type == EventType.LLM_INPUT
        assert span.model_name == "gpt-4"
        assert span.input_tokens == 100

        await manager.close()

    @pytest.mark.asyncio
    async def test_emit_llm_output(self, enabled_config, tmp_path):
        """Test emit_llm_output updates span."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        span_id = await manager.emit_llm_input(
            trace_id=trace_id,
            model_name="gpt-4",
            input_tokens=100,
        )

        await manager.emit_llm_output(
            trace_id=trace_id,
            span_id=span_id,
            output_tokens=200,
        )

        span = manager._pending_spans[
            span_id
        ]  # pylint: disable=protected-access
        assert span.output_tokens == 200
        assert span.duration_ms is not None

        await manager.close()

    @pytest.mark.asyncio
    async def test_emit_tool_call(self, enabled_config, tmp_path):
        """Test tool call start and end."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        span_id = await manager.emit_tool_call_start(
            trace_id=trace_id,
            tool_name="browser_control",
            tool_input={"url": "https://example.com"},
        )

        assert span_id is not None
        span = manager._pending_spans[
            span_id
        ]  # pylint: disable=protected-access
        assert span.event_type == EventType.TOOL_CALL_START
        assert span.tool_name == "browser_control"

        await manager.emit_tool_call_end(
            trace_id=trace_id,
            span_id=span_id,
            tool_output="success",
        )

        span = manager._pending_spans[
            span_id
        ]  # pylint: disable=protected-access
        assert span.event_type == EventType.TOOL_CALL_END
        assert span.tool_output == "success"

        await manager.close()

    @pytest.mark.asyncio
    async def test_emit_tool_call_with_error(self, enabled_config, tmp_path):
        """Test tool call end with error."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        span_id = await manager.emit_tool_call_start(
            trace_id=trace_id,
            tool_name="browser_control",
            tool_input={"url": "https://example.com"},
        )

        await manager.emit_tool_call_end(
            trace_id=trace_id,
            span_id=span_id,
            tool_output=None,
            error="Connection failed",
        )

        span = manager._pending_spans[
            span_id
        ]  # pylint: disable=protected-access
        assert span.error == "Connection failed"

        await manager.close()

    @pytest.mark.asyncio
    async def test_emit_skill_invocation(self, enabled_config, tmp_path):
        """Test skill invocation."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        span_id = await manager.emit_skill_invocation(
            trace_id=trace_id,
            skill_name="pdf",
        )

        assert span_id is not None
        span = manager._pending_spans[
            span_id
        ]  # pylint: disable=protected-access
        assert span.event_type == EventType.SKILL_INVOCATION
        assert span.skill_name == "pdf"

        await manager.close()

    @pytest.mark.asyncio
    async def test_emit_mcp_tool(self, enabled_config, tmp_path):
        """Test MCP tool call."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        span_id = await manager.emit_tool_call_start(
            trace_id=trace_id,
            tool_name="get_weather",
            tool_input={"city": "Beijing"},
            mcp_server="weather-server",
        )

        span = manager._pending_spans[
            span_id
        ]  # pylint: disable=protected-access
        assert span.mcp_server == "weather-server"

        await manager.close()

    @pytest.mark.asyncio
    async def test_user_message_sanitization(self, tmp_path):
        """Test that user message is sanitized."""
        config = TracingConfig(enabled=True, sanitize_output=True)
        manager = TraceManager(config)
        await manager.initialize(tmp_path)

        long_message = "x" * 1000
        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
            user_message=long_message,
        )

        trace = await manager.store.get_trace(trace_id)
        assert len(trace.user_message) < len(long_message)
        assert trace.user_message.endswith("...")

        await manager.close()

    @pytest.mark.asyncio
    async def test_tool_input_sanitization(self, tmp_path):
        """Test that tool input is sanitized."""
        config = TracingConfig(enabled=True, sanitize_output=True)
        manager = TraceManager(config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        await manager.emit_tool_call_start(
            trace_id=trace_id,
            tool_name="test_tool",
            tool_input={"api_key": "secret123", "data": "normal"},
        )

        span = list(manager._pending_spans.values())[
            0
        ]  # pylint: disable=protected-access
        assert span.tool_input["api_key"] == "[REDACTED]"
        assert span.tool_input["data"] == "normal"

        await manager.close()

    @pytest.mark.asyncio
    async def test_trace_totals_updated(self, enabled_config, tmp_path):
        """Test that trace totals are updated from spans."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        # Emit LLM call
        span_id = await manager.emit_llm_input(
            trace_id=trace_id,
            model_name="gpt-4",
            input_tokens=100,
        )
        await manager.emit_llm_output(trace_id, span_id, output_tokens=200)

        # Check trace totals
        trace = manager._active_traces[
            trace_id
        ]  # pylint: disable=protected-access
        assert trace.total_input_tokens == 100
        assert trace.total_output_tokens == 200
        assert trace.model_name == "gpt-4"

        await manager.close()


class TestGlobalManager:
    """Tests for global manager functions."""

    def test_has_trace_manager_false_initially(self):
        """Test has_trace_manager returns False initially."""
        assert has_trace_manager() is False

    def test_get_trace_manager_raises_when_not_initialized(self):
        """Test get_trace_manager raises when not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_trace_manager()

    @pytest.mark.asyncio
    async def test_init_trace_manager(self, tmp_path):
        """Test init_trace_manager creates manager."""
        config = TracingConfig(enabled=True)
        manager = await init_trace_manager(config, tmp_path)

        assert manager is not None
        assert has_trace_manager() is True
        assert get_trace_manager() is manager

        await close_trace_manager()

    @pytest.mark.asyncio
    async def test_close_trace_manager(self, tmp_path):
        """Test close_trace_manager closes and clears manager."""
        config = TracingConfig(enabled=True)
        await init_trace_manager(config, tmp_path)

        assert has_trace_manager() is True

        await close_trace_manager()

        assert has_trace_manager() is False

    @pytest.mark.asyncio
    async def test_init_trace_manager_idempotent(self, tmp_path):
        """Test init_trace_manager returns existing manager if initialized."""
        config = TracingConfig(enabled=True)
        manager1 = await init_trace_manager(config, tmp_path)
        manager2 = await init_trace_manager(config, tmp_path)

        assert manager1 is manager2

        await close_trace_manager()


class TestBatchFlush:
    """Tests for batch flushing behavior."""

    @pytest.mark.asyncio
    async def test_flush_on_batch_size(self, tmp_path):
        """Test that flush happens when batch size is reached."""
        config = TracingConfig(enabled=True, batch_size=3, flush_interval=60)
        manager = TraceManager(config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        # Emit spans up to batch size
        for i in range(3):
            await manager.emit_span(
                trace_id=trace_id,
                event_type=EventType.LLM_INPUT,
                name=f"span_{i}",
            )

        # Wait a bit for async flush
        import asyncio

        await asyncio.sleep(0.1)

        # Queue should be cleared after flush
        assert (
            len(manager._span_queue) == 0
        )  # pylint: disable=protected-access

        await manager.close()

    @pytest.mark.asyncio
    async def test_manual_flush(self, enabled_config, tmp_path):
        """Test manual flush via close."""
        manager = TraceManager(enabled_config)
        await manager.initialize(tmp_path)

        trace_id = await manager.start_trace(
            user_id="user-1",
            session_id="session-1",
            channel="console",
        )

        # Emit a span
        await manager.emit_span(
            trace_id=trace_id,
            event_type=EventType.LLM_INPUT,
            name="test_span",
        )

        # Close should flush remaining spans
        await manager.close()

        # Verify data was persisted
        store = manager._store  # pylint: disable=protected-access
        traces = store._traces  # pylint: disable=protected-access
        assert trace_id in traces
