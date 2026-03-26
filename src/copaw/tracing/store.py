# -*- coding: utf-8 -*-
"""Trace store module.

Provides storage operations for traces and spans with fallback to in-memory storage.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from .config import TracingConfig
from .database import TDSQLConnection
from .models import (
    DailyStats,
    EventType,
    ModelUsage,
    OverviewStats,
    Span,
    Trace,
    TraceDetail,
    TraceListItem,
    TraceStatus,
    ToolUsage,
    SkillUsage,
    UserListItem,
    UserStats,
)

logger = logging.getLogger(__name__)

# Sensitive keys to redact from tool input/output
SENSITIVE_KEYS = frozenset([
    "api_key", "apikey", "password", "passwd", "secret", "token",
    "authorization", "credential", "private_key", "access_token",
    "refresh_token", "session_id", "auth",
])


def sanitize_dict(data: Optional[dict[str, Any]], max_length: int = 500) -> Optional[dict]:
    """Sanitize dictionary by redacting sensitive keys.

    Args:
        data: Dictionary to sanitize
        max_length: Maximum string length

    Returns:
        Sanitized dictionary
    """
    if data is None:
        return None

    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > max_length:
            result[key] = value[:max_length] + "..."
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, max_length)
        else:
            result[key] = value
    return result


def sanitize_string(text: Optional[str], max_length: int = 500) -> Optional[str]:
    """Sanitize string by truncating and removing media references.

    Args:
        text: String to sanitize
        max_length: Maximum length

    Returns:
        Sanitized string
    """
    if text is None:
        return None
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


class TraceStore:
    """Store for traces and spans with database and in-memory fallback."""

    def __init__(
        self,
        config: TracingConfig,
        db: Optional[TDSQLConnection] = None,
    ):
        """Initialize trace store.

        Args:
            config: Tracing configuration
            db: Optional database connection
        """
        self.config = config
        self.db = db
        self._use_db = False

        # In-memory fallback storage
        self._traces: dict[str, Trace] = {}
        self._spans: dict[str, list[Span]] = {}
        self._user_stats: dict[str, dict] = {}
        self._global_stats: dict[str, dict] = {}

    async def initialize(self) -> None:
        """Initialize store. Database tables must be created manually."""
        if self.db is not None and self.db.is_connected:
            self._use_db = True
            logger.info("TraceStore initialized with database")
        else:
            logger.info("TraceStore initialized with in-memory storage")

    async def close(self) -> None:
        """Close store and database connection."""
        if self.db is not None:
            await self.db.close()

    # Trace operations

    async def create_trace(self, trace: Trace) -> None:
        """Create a new trace.

        Args:
            trace: Trace to create
        """
        if self._use_db:
            await self._db_create_trace(trace)
        else:
            self._traces[trace.trace_id] = trace
            self._spans[trace.trace_id] = []

    async def update_trace(self, trace: Trace) -> None:
        """Update an existing trace.

        Args:
            trace: Trace to update
        """
        if self._use_db:
            await self._db_update_trace(trace)
        else:
            self._traces[trace.trace_id] = trace

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID.

        Args:
            trace_id: Trace identifier

        Returns:
            Trace or None
        """
        if self._use_db:
            return await self._db_get_trace(trace_id)
        return self._traces.get(trace_id)

    # Span operations

    async def create_span(self, span: Span) -> None:
        """Create a new span.

        Args:
            span: Span to create
        """
        if self._use_db:
            await self._db_create_span(span)
        else:
            if span.trace_id not in self._spans:
                self._spans[span.trace_id] = []
            self._spans[span.trace_id].append(span)

    async def update_span(self, span: Span) -> None:
        """Update an existing span.

        Args:
            span: Span to update
        """
        if self._use_db:
            await self._db_update_span(span)
        else:
            spans = self._spans.get(span.trace_id, [])
            for i, s in enumerate(spans):
                if s.span_id == span.span_id:
                    spans[i] = span
                    break

    async def get_spans(self, trace_id: str) -> list[Span]:
        """Get all spans for a trace.

        Args:
            trace_id: Trace identifier

        Returns:
            List of spans
        """
        if self._use_db:
            return await self._db_get_spans(trace_id)
        return self._spans.get(trace_id, [])

    # Batch operations

    async def batch_create_spans(self, spans: list[Span]) -> None:
        """Batch create spans.

        Args:
            spans: List of spans to create
        """
        if not spans:
            return
        if self._use_db:
            await self._db_batch_create_spans(spans)
        else:
            for span in spans:
                if span.trace_id not in self._spans:
                    self._spans[span.trace_id] = []
                self._spans[span.trace_id].append(span)

    # Query operations

    async def get_overview_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> OverviewStats:
        """Get overview statistics.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Overview statistics
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.now()

        if self._use_db:
            return await self._db_get_overview_stats(start_date, end_date)
        return self._memory_get_overview_stats(start_date, end_date)

    async def get_users(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
    ) -> tuple[list[UserListItem], int]:
        """Get list of users with stats.

        Args:
            page: Page number
            page_size: Page size
            user_id: Filter by user ID

        Returns:
            Tuple of (users list, total count)
        """
        if self._use_db:
            return await self._db_get_users(page, page_size, user_id)
        return self._memory_get_users(page, page_size, user_id)

    async def get_user_stats(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> UserStats:
        """Get statistics for a specific user.

        Args:
            user_id: User identifier
            start_date: Start date filter
            end_date: End date filter

        Returns:
            User statistics
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        if self._use_db:
            return await self._db_get_user_stats(user_id, start_date, end_date)
        return self._memory_get_user_stats(user_id, start_date, end_date)

    async def get_traces(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[TraceListItem], int]:
        """Get list of traces.

        Args:
            page: Page number
            page_size: Page size
            user_id: Filter by user ID
            session_id: Filter by session ID
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Tuple of (traces list, total count)
        """
        if self._use_db:
            return await self._db_get_traces(
                page, page_size, user_id, session_id, status, start_date, end_date
            )
        return self._memory_get_traces(
            page, page_size, user_id, session_id, status, start_date, end_date
        )

    async def get_trace_detail(self, trace_id: str) -> Optional[TraceDetail]:
        """Get detailed trace with spans.

        Args:
            trace_id: Trace identifier

        Returns:
            Trace detail or None
        """
        trace = await self.get_trace(trace_id)
        if trace is None:
            return None

        spans = await self.get_spans(trace_id)

        # Calculate durations by type
        llm_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type in (EventType.LLM_INPUT, EventType.LLM_OUTPUT)
        )
        tool_duration = sum(
            s.duration_ms or 0
            for s in spans
            if s.event_type in (EventType.TOOL_CALL_START, EventType.TOOL_CALL_END)
        )

        # Extract tool calls
        tools_called = []
        tool_spans = [s for s in spans if s.event_type == EventType.TOOL_CALL_END]
        for span in tool_spans:
            tools_called.append({
                "tool_name": span.tool_name or span.name,
                "tool_input": span.tool_input,
                "tool_output": span.tool_output,
                "duration_ms": span.duration_ms,
                "error": span.error,
            })

        return TraceDetail(
            trace=trace,
            spans=spans,
            llm_duration_ms=llm_duration,
            tool_duration_ms=tool_duration,
            tools_called=tools_called,
        )

    # Database implementations

    async def _db_create_trace(self, trace: Trace) -> None:
        """Create trace in database."""
        query = """
            INSERT INTO swe_tracing_traces (
                trace_id, user_id, session_id, channel, start_time,
                end_time, duration_ms, model_name, total_input_tokens,
                total_output_tokens, total_tokens, tools_used, skills_used,
                status, error
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            trace.trace_id,
            trace.user_id,
            trace.session_id,
            trace.channel,
            trace.start_time,
            trace.end_time,
            trace.duration_ms,
            trace.model_name,
            trace.total_input_tokens,
            trace.total_output_tokens,
            trace.total_input_tokens + trace.total_output_tokens,
            json.dumps(trace.tools_used),
            json.dumps(trace.skills_used),
            trace.status.value if isinstance(trace.status, TraceStatus) else trace.status,
            trace.error,
        )
        await self.db.execute(query, params)

    async def _db_update_trace(self, trace: Trace) -> None:
        """Update trace in database."""
        query = """
            UPDATE swe_tracing_traces SET
                end_time = %s,
                duration_ms = %s,
                model_name = %s,
                total_input_tokens = %s,
                total_output_tokens = %s,
                total_tokens = %s,
                tools_used = %s,
                skills_used = %s,
                status = %s,
                error = %s
            WHERE trace_id = %s
        """
        params = (
            trace.end_time,
            trace.duration_ms,
            trace.model_name,
            trace.total_input_tokens,
            trace.total_output_tokens,
            trace.total_input_tokens + trace.total_output_tokens,
            json.dumps(trace.tools_used),
            json.dumps(trace.skills_used),
            trace.status.value if isinstance(trace.status, TraceStatus) else trace.status,
            trace.error,
            trace.trace_id,
        )
        await self.db.execute(query, params)

    async def _db_get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get trace from database."""
        query = "SELECT * FROM swe_tracing_traces WHERE trace_id = %s"
        row = await self.db.fetch_one(query, (trace_id,))
        if row is None:
            return None
        return self._row_to_trace(row)

    async def _db_create_span(self, span: Span) -> None:
        """Create span in database."""
        query = """
            INSERT INTO swe_tracing_spans (
                span_id, trace_id, parent_span_id, name, event_type,
                start_time, end_time, duration_ms, user_id, session_id, channel,
                model_name, input_tokens, output_tokens, tool_name, skill_name,
                tool_input, tool_output, error, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            span.span_id,
            span.trace_id,
            span.parent_span_id,
            span.name,
            span.event_type.value if isinstance(span.event_type, EventType) else span.event_type,
            span.start_time,
            span.end_time,
            span.duration_ms,
            span.user_id,
            span.session_id,
            span.channel,
            span.model_name,
            span.input_tokens,
            span.output_tokens,
            span.tool_name,
            span.skill_name,
            json.dumps(span.tool_input) if span.tool_input else None,
            span.tool_output,
            span.error,
            json.dumps(span.metadata) if span.metadata else None,
        )
        await self.db.execute(query, params)

    async def _db_update_span(self, span: Span) -> None:
        """Update span in database."""
        query = """
            UPDATE swe_tracing_spans SET
                end_time = %s,
                duration_ms = %s,
                output_tokens = %s,
                tool_output = %s,
                error = %s,
                metadata = %s,
                event_type = %s
            WHERE span_id = %s
        """
        params = (
            span.end_time,
            span.duration_ms,
            span.output_tokens,
            span.tool_output,
            span.error,
            json.dumps(span.metadata) if span.metadata else None,
            span.event_type.value if hasattr(span.event_type, 'value') else span.event_type,
            span.span_id,
        )
        await self.db.execute(query, params)

    async def _db_get_spans(self, trace_id: str) -> list[Span]:
        """Get spans from database."""
        query = "SELECT * FROM swe_tracing_spans WHERE trace_id = %s ORDER BY start_time"
        rows = await self.db.fetch_all(query, (trace_id,))
        return [self._row_to_span(row) for row in rows]

    async def _db_batch_create_spans(self, spans: list[Span]) -> None:
        """Batch create spans in database."""
        query = """
            INSERT INTO swe_tracing_spans (
                span_id, trace_id, parent_span_id, name, event_type,
                start_time, end_time, duration_ms, user_id, session_id, channel,
                model_name, input_tokens, output_tokens, tool_name, skill_name,
                tool_input, tool_output, error, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params_list = []
        for span in spans:
            params_list.append((
                span.span_id,
                span.trace_id,
                span.parent_span_id,
                span.name,
                span.event_type.value if isinstance(span.event_type, EventType) else span.event_type,
                span.start_time,
                span.end_time,
                span.duration_ms,
                span.user_id,
                span.session_id,
                span.channel,
                span.model_name,
                span.input_tokens,
                span.output_tokens,
                span.tool_name,
                span.skill_name,
                json.dumps(span.tool_input) if span.tool_input else None,
                span.tool_output,
                span.error,
                json.dumps(span.metadata) if span.metadata else None,
            ))
        await self.db.execute_many(query, params_list)

    async def _db_get_overview_stats(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> OverviewStats:
        """Get overview stats from database."""
        # Get total users and active users
        users_query = """
            SELECT COUNT(DISTINCT user_id) as total_users
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time <= %s
        """
        users_row = await self.db.fetch_one(users_query, (start_date, end_date))
        total_users = users_row["total_users"] if users_row else 0

        # Get online users (active in last 5 minutes, based on spans)
        online_query = """
            SELECT COUNT(DISTINCT user_id) as online_users
            FROM swe_tracing_spans
            WHERE start_time >= %s
        """
        online_threshold = datetime.now() - timedelta(minutes=5)
        online_row = await self.db.fetch_one(online_query, (online_threshold,))
        online_users = online_row["online_users"] if online_row else 0

        # Get token stats
        token_query = """
            SELECT
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens,
                COUNT(*) as total_sessions,
                AVG(duration_ms) as avg_duration
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time <= %s
        """
        token_row = await self.db.fetch_one(token_query, (start_date, end_date))

        # Get model distribution
        model_query = """
            SELECT model_name, COUNT(*) as count,
                   SUM(total_input_tokens) as input_tokens,
                   SUM(total_output_tokens) as output_tokens,
                   SUM(total_tokens) as total_tokens
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time <= %s AND model_name IS NOT NULL
            GROUP BY model_name
            ORDER BY count DESC
            LIMIT 10
        """
        model_rows = await self.db.fetch_all(model_query, (start_date, end_date))
        model_distribution = [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"] or 0,
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in model_rows
        ]

        # Get top tools (by event_type = tool_call_end)
        tool_query = """
            SELECT tool_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND tool_name IS NOT NULL
            GROUP BY tool_name
            ORDER BY count DESC
            LIMIT 10
        """
        tool_rows = await self.db.fetch_all(tool_query, (start_date, end_date))
        top_tools = [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in tool_rows
        ]

        # Get top skills (by event_type = skill_invocation)
        skill_query = """
            SELECT skill_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration
            FROM swe_tracing_spans
            WHERE start_time >= %s AND start_time <= %s
              AND event_type = 'skill_invocation'
              AND skill_name IS NOT NULL
            GROUP BY skill_name
            ORDER BY count DESC
            LIMIT 10
        """
        skill_rows = await self.db.fetch_all(skill_query, (start_date, end_date))
        top_skills = [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in skill_rows
        ]

        return OverviewStats(
            online_users=online_users or 0,
            total_users=total_users or 0,
            model_distribution=model_distribution,
            total_tokens=token_row["total_tokens"] or 0 if token_row else 0,
            input_tokens=token_row["input_tokens"] or 0 if token_row else 0,
            output_tokens=token_row["output_tokens"] or 0 if token_row else 0,
            total_sessions=token_row["total_sessions"] or 0 if token_row else 0,
            total_conversations=token_row["total_sessions"] or 0 if token_row else 0,
            avg_duration_ms=int(token_row["avg_duration"] or 0) if token_row and token_row["avg_duration"] else 0,
            top_tools=top_tools,
            top_skills=top_skills,
            daily_trend=[],
        )

    async def _db_get_users(
        self,
        page: int,
        page_size: int,
        user_id: Optional[str],
    ) -> tuple[list[UserListItem], int]:
        """Get users from database."""
        where_clauses = []
        params = []
        if user_id:
            where_clauses.append("user_id LIKE %s")
            params.append(f"%{user_id}%")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        count_query = f"SELECT COUNT(DISTINCT user_id) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self.db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        # Get users with skill counts from spans
        offset = (page - 1) * page_size
        query = f"""
            SELECT t.user_id,
                   COUNT(*) as total_sessions,
                   COUNT(DISTINCT t.session_id) as total_conversations,
                   SUM(t.total_tokens) as total_tokens,
                   MAX(t.start_time) as last_active,
                   (SELECT COUNT(*) FROM swe_tracing_spans s
                    WHERE s.trace_id IN (SELECT trace_id FROM swe_tracing_traces WHERE user_id = t.user_id)
                    AND s.event_type = 'skill_invocation') as total_skills
            FROM swe_tracing_traces t
            WHERE {where_sql}
            GROUP BY t.user_id
            ORDER BY last_active DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        rows = await self.db.fetch_all(query, tuple(params))
        users = [
            UserListItem(
                user_id=row["user_id"],
                total_sessions=row["total_sessions"] or 0,
                total_conversations=row["total_conversations"] or 0,
                total_tokens=row["total_tokens"] or 0,
                total_skills=row["total_skills"] or 0,
                last_active=row["last_active"],
            )
            for row in rows
        ]
        return users, total

    async def _db_get_user_stats(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> UserStats:
        """Get user stats from database."""
        # Get basic stats
        stats_query = """
            SELECT
                COUNT(*) as total_sessions,
                COUNT(DISTINCT session_id) as total_conversations,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(duration_ms) as avg_duration
            FROM swe_tracing_traces
            WHERE user_id = %s AND start_time >= %s AND start_time <= %s
        """
        stats_row = await self.db.fetch_one(stats_query, (user_id, start_date, end_date))

        # Get model usage
        model_query = """
            SELECT model_name, COUNT(*) as count,
                   SUM(total_input_tokens) as input_tokens,
                   SUM(total_output_tokens) as output_tokens,
                   SUM(total_tokens) as total_tokens
            FROM swe_tracing_traces
            WHERE user_id = %s AND start_time >= %s AND start_time <= %s AND model_name IS NOT NULL
            GROUP BY model_name
            ORDER BY count DESC
        """
        model_rows = await self.db.fetch_all(model_query, (user_id, start_date, end_date))
        model_usage = [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"],
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in model_rows
        ]

        # Get tool usage (by event_type = tool_call_end)
        tool_query = """
            SELECT tool_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE user_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND tool_name IS NOT NULL
            GROUP BY tool_name
            ORDER BY count DESC
        """
        tool_rows = await self.db.fetch_all(tool_query, (user_id, start_date, end_date))
        tools_used = [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in tool_rows
        ]

        # Get skill usage (by event_type = skill_invocation)
        skill_query = """
            SELECT skill_name, COUNT(*) as count
            FROM swe_tracing_spans
            WHERE user_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'skill_invocation'
              AND skill_name IS NOT NULL
            GROUP BY skill_name
            ORDER BY count DESC
        """
        skill_rows = await self.db.fetch_all(skill_query, (user_id, start_date, end_date))
        skills_used = [
            SkillUsage(skill_name=row["skill_name"], count=row["count"])
            for row in skill_rows
        ]

        return UserStats(
            user_id=user_id,
            model_usage=model_usage,
            total_tokens=stats_row["total_tokens"] if stats_row else 0,
            input_tokens=stats_row["input_tokens"] if stats_row else 0,
            output_tokens=stats_row["output_tokens"] if stats_row else 0,
            total_sessions=stats_row["total_sessions"] if stats_row else 0,
            total_conversations=stats_row["total_conversations"] if stats_row else 0,
            avg_duration_ms=int(stats_row["avg_duration"] or 0) if stats_row else 0,
            tools_used=tools_used,
            skills_used=skills_used,
        )

    async def _db_get_traces(
        self,
        page: int,
        page_size: int,
        user_id: Optional[str],
        session_id: Optional[str],
        status: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> tuple[list[TraceListItem], int]:
        """Get traces from database."""
        where_clauses = []
        params = []

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id = %s")
            params.append(session_id)
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self.db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        # Get traces
        offset = (page - 1) * page_size
        query = f"""
            SELECT trace_id, user_id, session_id, channel, start_time,
                   duration_ms, total_tokens, model_name, status,
                   JSON_LENGTH(tools_used) as tools_count
            FROM swe_tracing_traces
            WHERE {where_sql}
            ORDER BY start_time DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        rows = await self.db.fetch_all(query, tuple(params))
        traces = [
            TraceListItem(
                trace_id=row["trace_id"],
                user_id=row["user_id"],
                session_id=row["session_id"],
                channel=row["channel"],
                start_time=row["start_time"],
                duration_ms=row["duration_ms"],
                total_tokens=row["total_tokens"] or 0,
                model_name=row["model_name"],
                status=row["status"],
                tools_count=row["tools_count"] or 0,
            )
            for row in rows
        ]
        return traces, total

    # In-memory implementations

    def _memory_get_overview_stats(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> OverviewStats:
        """Get overview stats from memory."""
        traces = [
            t for t in self._traces.values()
            if start_date <= t.start_time <= end_date
        ]

        # Don't return early - we still need to check spans for tools/skills

        # Count unique users
        users = set(t.user_id for t in traces)

        # Count online users based on recent span activity (last 5 minutes)
        online_threshold = datetime.now() - timedelta(minutes=5)
        online_users = set()
        for trace_id, spans in self._spans.items():
            for s in spans:
                if s.start_time >= online_threshold and s.user_id:
                    online_users.add(s.user_id)
        online_users = len(online_users)

        # Token stats
        total_input = sum(t.total_input_tokens for t in traces)
        total_output = sum(t.total_output_tokens for t in traces)
        avg_duration = sum(t.duration_ms or 0 for t in traces) // max(len(traces), 1)

        # Model distribution
        model_counts: dict[str, dict] = {}
        for t in traces:
            if t.model_name:
                if t.model_name not in model_counts:
                    model_counts[t.model_name] = {"count": 0, "tokens": 0}
                model_counts[t.model_name]["count"] += 1
                model_counts[t.model_name]["tokens"] += t.total_input_tokens + t.total_output_tokens

        model_distribution = [
            ModelUsage(model_name=name, count=data["count"], total_tokens=data["tokens"])
            for name, data in sorted(model_counts.items(), key=lambda x: -x[1]["count"])
        ]

        # Tool usage and skill usage (separate by event_type)
        tool_counts: dict[str, dict] = {}
        skill_counts: dict[str, dict] = {}

        for trace_id, spans in self._spans.items():
            for s in spans:
                if not (start_date <= s.start_time <= end_date):
                    continue
                # Check event_type to distinguish tool vs skill
                event_type_str = s.event_type.value if hasattr(s.event_type, 'value') else str(s.event_type)

                if event_type_str == EventType.SKILL_INVOCATION.value and s.skill_name:
                    # Skill invocation
                    if s.skill_name not in skill_counts:
                        skill_counts[s.skill_name] = {"count": 0, "duration": 0, "errors": 0}
                    skill_counts[s.skill_name]["count"] += 1
                    skill_counts[s.skill_name]["duration"] += s.duration_ms or 0
                    if s.error:
                        skill_counts[s.skill_name]["errors"] += 1
                elif event_type_str == EventType.TOOL_CALL_END.value and s.tool_name:
                    # Tool call (only count TOOL_CALL_END)
                    if s.tool_name not in tool_counts:
                        tool_counts[s.tool_name] = {"count": 0, "duration": 0, "errors": 0}
                    tool_counts[s.tool_name]["count"] += 1
                    tool_counts[s.tool_name]["duration"] += s.duration_ms or 0
                    if s.error:
                        tool_counts[s.tool_name]["errors"] += 1

        top_tools = [
            ToolUsage(
                tool_name=name,
                count=data["count"],
                avg_duration_ms=data["duration"] // max(data["count"], 1),
                error_count=data["errors"],
            )
            for name, data in sorted(tool_counts.items(), key=lambda x: -x[1]["count"])[:10]
        ]

        top_skills = [
            SkillUsage(
                skill_name=name,
                count=data["count"],
                avg_duration_ms=data["duration"] // max(data["count"], 1),
            )
            for name, data in sorted(skill_counts.items(), key=lambda x: -x[1]["count"])[:10]
        ]

        return OverviewStats(
            online_users=online_users,
            total_users=len(users),
            model_distribution=model_distribution,
            total_tokens=total_input + total_output,
            input_tokens=total_input,
            output_tokens=total_output,
            total_sessions=len(traces),
            total_conversations=len(set(t.session_id for t in traces)),
            avg_duration_ms=avg_duration,
            top_tools=top_tools,
            top_skills=top_skills,
            daily_trend=[],
        )

    def _memory_get_users(
        self,
        page: int,
        page_size: int,
        user_id: Optional[str],
    ) -> tuple[list[UserListItem], int]:
        """Get users from memory."""
        # Aggregate by user
        user_data: dict[str, dict] = {}
        for t in self._traces.values():
            uid = t.user_id
            if user_id and user_id not in uid:
                continue
            if uid not in user_data:
                user_data[uid] = {
                    "sessions": 0,
                    "conversations": set(),
                    "tokens": 0,
                    "skills": 0,
                    "last_active": t.start_time,
                }
            user_data[uid]["sessions"] += 1
            user_data[uid]["conversations"].add(t.session_id)
            user_data[uid]["tokens"] += t.total_input_tokens + t.total_output_tokens
            if t.start_time > user_data[uid]["last_active"]:
                user_data[uid]["last_active"] = t.start_time

        # Count skills per user from spans
        for trace_id, spans in self._spans.items():
            trace = self._traces.get(trace_id)
            if trace and trace.user_id in user_data:
                for s in spans:
                    event_type_str = s.event_type.value if hasattr(s.event_type, 'value') else str(s.event_type)
                    if event_type_str == EventType.SKILL_INVOCATION.value:
                        user_data[trace.user_id]["skills"] += 1

        # Sort and paginate
        sorted_users = sorted(
            user_data.items(),
            key=lambda x: x[1]["last_active"],
            reverse=True,
        )
        total = len(sorted_users)
        offset = (page - 1) * page_size
        items = [
            UserListItem(
                user_id=uid,
                total_sessions=data["sessions"],
                total_conversations=len(data["conversations"]),
                total_tokens=data["tokens"],
                total_skills=data["skills"],
                last_active=data["last_active"],
            )
            for uid, data in sorted_users[offset:offset + page_size]
        ]
        return items, total

    def _memory_get_user_stats(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> UserStats:
        """Get user stats from memory."""
        traces = [
            t for t in self._traces.values()
            if t.user_id == user_id and start_date <= t.start_time <= end_date
        ]

        if not traces:
            return UserStats(user_id=user_id)

        total_input = sum(t.total_input_tokens for t in traces)
        total_output = sum(t.total_output_tokens for t in traces)
        avg_duration = sum(t.duration_ms or 0 for t in traces) // max(len(traces), 1)

        # Model usage
        model_counts: dict[str, dict] = {}
        for t in traces:
            if t.model_name:
                if t.model_name not in model_counts:
                    model_counts[t.model_name] = {"count": 0, "tokens": 0}
                model_counts[t.model_name]["count"] += 1
                model_counts[t.model_name]["tokens"] += t.total_input_tokens + t.total_output_tokens

        model_usage = [
            ModelUsage(model_name=name, count=data["count"], total_tokens=data["tokens"])
            for name, data in sorted(model_counts.items(), key=lambda x: -x[1]["count"])
        ]

        # Tool and skill usage (separate by event_type)
        tool_counts: dict[str, dict] = {}
        skill_counts: dict[str, dict] = {}
        for trace_id, spans in self._spans.items():
            trace = self._traces.get(trace_id)
            if trace and trace.user_id == user_id:
                for s in spans:
                    if not (start_date <= s.start_time <= end_date):
                        continue
                    event_type_str = s.event_type.value if hasattr(s.event_type, 'value') else str(s.event_type)

                    if event_type_str == EventType.SKILL_INVOCATION.value and s.skill_name:
                        # Skill invocation
                        if s.skill_name not in skill_counts:
                            skill_counts[s.skill_name] = {"count": 0, "duration": 0, "errors": 0}
                        skill_counts[s.skill_name]["count"] += 1
                        skill_counts[s.skill_name]["duration"] += s.duration_ms or 0
                        if s.error:
                            skill_counts[s.skill_name]["errors"] += 1
                    elif event_type_str == EventType.TOOL_CALL_END.value and s.tool_name:
                        # Tool call (count once, use TOOL_CALL_END)
                        if s.tool_name not in tool_counts:
                            tool_counts[s.tool_name] = {"count": 0, "duration": 0, "errors": 0}
                        tool_counts[s.tool_name]["count"] += 1
                        tool_counts[s.tool_name]["duration"] += s.duration_ms or 0
                        if s.error:
                            tool_counts[s.tool_name]["errors"] += 1

        tools_used = [
            ToolUsage(
                tool_name=name,
                count=data["count"],
                avg_duration_ms=data["duration"] // max(data["count"], 1),
                error_count=data["errors"],
            )
            for name, data in sorted(tool_counts.items(), key=lambda x: -x[1]["count"])
        ]

        skills_used = [
            SkillUsage(
                skill_name=name,
                count=data["count"],
            )
            for name, data in sorted(skill_counts.items(), key=lambda x: -x[1]["count"])
        ]

        return UserStats(
            user_id=user_id,
            model_usage=model_usage,
            total_tokens=total_input + total_output,
            input_tokens=total_input,
            output_tokens=total_output,
            total_sessions=len(traces),
            total_conversations=len(set(t.session_id for t in traces)),
            avg_duration_ms=avg_duration,
            tools_used=tools_used,
            skills_used=skills_used,
        )

    def _memory_get_traces(
        self,
        page: int,
        page_size: int,
        user_id: Optional[str],
        session_id: Optional[str],
        status: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> tuple[list[TraceListItem], int]:
        """Get traces from memory."""
        traces = list(self._traces.values())

        # Apply filters
        if user_id:
            traces = [t for t in traces if t.user_id == user_id]
        if session_id:
            traces = [t for t in traces if t.session_id == session_id]
        if status:
            traces = [t for t in traces if t.status == status]
        if start_date:
            traces = [t for t in traces if t.start_time >= start_date]
        if end_date:
            traces = [t for t in traces if t.start_time <= end_date]

        # Sort by start time descending
        traces.sort(key=lambda t: t.start_time, reverse=True)

        total = len(traces)
        offset = (page - 1) * page_size
        items = [
            TraceListItem(
                trace_id=t.trace_id,
                user_id=t.user_id,
                session_id=t.session_id,
                channel=t.channel,
                start_time=t.start_time,
                duration_ms=t.duration_ms,
                total_tokens=t.total_input_tokens + t.total_output_tokens,
                model_name=t.model_name,
                status=t.status.value if isinstance(t.status, TraceStatus) else t.status,
                tools_count=len(t.tools_used),
            )
            for t in traces[offset:offset + page_size]
        ]
        return items, total

    # Helper methods

    def _row_to_trace(self, row: dict) -> Trace:
        """Convert database row to Trace model."""
        return Trace(
            trace_id=row["trace_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            channel=row["channel"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_ms=row["duration_ms"],
            model_name=row["model_name"],
            total_input_tokens=row["total_input_tokens"] or 0,
            total_output_tokens=row["total_output_tokens"] or 0,
            tools_used=json.loads(row["tools_used"]) if row["tools_used"] else [],
            skills_used=json.loads(row["skills_used"]) if row["skills_used"] else [],
            status=TraceStatus(row["status"]) if row["status"] else TraceStatus.RUNNING,
            error=row["error"],
        )

    def _row_to_span(self, row: dict) -> Span:
        """Convert database row to Span model."""
        return Span(
            span_id=row["span_id"],
            trace_id=row["trace_id"],
            parent_span_id=row["parent_span_id"],
            name=row["name"],
            event_type=EventType(row["event_type"]),
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_ms=row["duration_ms"],
            user_id=row.get("user_id") or "",
            session_id=row.get("session_id") or "",
            channel=row.get("channel") or "",
            model_name=row["model_name"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            tool_name=row["tool_name"],
            skill_name=row["skill_name"],
            tool_input=json.loads(row["tool_input"]) if row["tool_input"] else None,
            tool_output=row["tool_output"],
            error=row["error"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )
