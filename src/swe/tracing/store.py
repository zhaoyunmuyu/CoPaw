# -*- coding: utf-8 -*-
"""Trace store module.

Provides database storage operations for traces and spans.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from .config import TracingConfig
from ..database import DatabaseConnection
from .models import (
    EventType,
    MCPToolUsage,
    MCPServerUsage,
    ModelUsage,
    OverviewStats,
    SessionListItem,
    SessionStats,
    Span,
    Trace,
    TraceDetail,
    TraceListItem,
    TraceStatus,
    ToolUsage,
    SkillUsage,
    UserListItem,
    UserMessageItem,
    UserStats,
)

logger = logging.getLogger(__name__)


def _matches_trace_filters(
    trace: Trace,
    user_id: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> bool:
    """Return whether a trace matches the requested user/date filters."""
    uid = trace.user_id
    if not uid:
        return False
    if user_id and user_id not in uid:
        return False
    if start_date and trace.start_time < start_date:
        return False
    if end_date and trace.start_time > end_date:
        return False
    return True


def _create_user_summary(trace: Trace) -> dict[str, Any]:
    """Create an in-memory aggregation bucket for a user."""
    return {
        "sessions": 0,
        "conversations": set(),
        "tokens": 0,
        "skills": 0,
        "last_active": trace.start_time,
    }


class TraceStore:
    """Store for traces and spans using database storage only."""

    def __init__(
        self,
        config: TracingConfig,
        db: DatabaseConnection,
        owns_db: bool = False,
    ):
        """Initialize trace store.

        Args:
            config: Tracing configuration
            db: Database connection for persistent storage
            owns_db: Whether this store owns the database connection.
                If True, close() will close the database connection.
                If False (default), the connection is shared and should not be closed here.
        """
        self.config = config
        self.db = db
        self._owns_db = owns_db

    async def initialize(self) -> None:
        """Initialize store. Database tables must be created manually."""
        if self.db is None:
            raise RuntimeError(
                "Database connection is required for TraceStore. "
                "Please configure database in tracing config.",
            )
        if not self.db.is_connected:
            raise RuntimeError(
                "Database is not connected. Please check database configuration.",
            )
        logger.info(
            "TraceStore initialized with database (host=%s, database=%s)",
            self.db.config.host,
            self.db.config.database,
        )

    async def close(self) -> None:
        """Close store. Only closes database connection if this store owns it."""
        if self._owns_db and self.db is not None:
            await self.db.close()

    # Trace operations

    async def create_trace(self, trace: Trace) -> None:
        """Create a new trace.

        Args:
            trace: Trace to create
        """
        query = """
            INSERT INTO swe_tracing_traces (
                trace_id, user_id, session_id, channel, start_time,
                end_time, duration_ms, model_name, total_input_tokens,
                total_output_tokens, total_tokens, tools_used, skills_used,
                status, error, user_message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            trace.status.value
            if isinstance(trace.status, TraceStatus)
            else trace.status,
            trace.error,
            trace.user_message,
        )
        await self.db.execute(query, params)

    async def update_trace(self, trace: Trace) -> None:
        """Update an existing trace.

        Args:
            trace: Trace to update
        """
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
            trace.status.value
            if isinstance(trace.status, TraceStatus)
            else trace.status,
            trace.error,
            trace.trace_id,
        )
        await self.db.execute(query, params)

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID.

        Args:
            trace_id: Trace identifier

        Returns:
            Trace or None
        """
        query = "SELECT * FROM swe_tracing_traces WHERE trace_id = %s"
        row = await self.db.fetch_one(query, (trace_id,))
        if row is None:
            return None
        return self._row_to_trace(row)

    # Span operations

    async def create_span(self, span: Span) -> None:
        """Create a new span.

        Args:
            span: Span to create
        """
        query = """
            INSERT INTO swe_tracing_spans (
                span_id, trace_id, parent_span_id, name, event_type,
                start_time, end_time, duration_ms, user_id, session_id, channel,
                model_name, input_tokens, output_tokens, tool_name, skill_name, mcp_server,
                tool_input, tool_output, error, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            span.span_id,
            span.trace_id,
            span.parent_span_id,
            span.name,
            span.event_type.value
            if isinstance(span.event_type, EventType)
            else span.event_type,
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
            span.mcp_server,
            json.dumps(span.tool_input) if span.tool_input else None,
            span.tool_output,
            span.error,
            json.dumps(span.metadata) if span.metadata else None,
        )
        await self.db.execute(query, params)

    async def update_span(self, span: Span) -> None:
        """Update an existing span.

        Args:
            span: Span to update
        """
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
            span.event_type.value
            if hasattr(span.event_type, "value")
            else span.event_type,
            span.span_id,
        )
        await self.db.execute(query, params)

    async def get_spans(self, trace_id: str) -> list[Span]:
        """Get all spans for a trace.

        Args:
            trace_id: Trace identifier

        Returns:
            List of spans
        """
        query = "SELECT * FROM swe_tracing_spans WHERE trace_id = %s ORDER BY start_time"
        rows = await self.db.fetch_all(query, (trace_id,))
        return [self._row_to_span(row) for row in rows]

    # Batch operations

    async def batch_create_spans(self, spans: list[Span]) -> None:
        """Batch create spans.

        Args:
            spans: List of spans to create
        """
        if not spans:
            return
        query = """
            INSERT INTO swe_tracing_spans (
                span_id, trace_id, parent_span_id, name, event_type,
                start_time, end_time, duration_ms, user_id, session_id, channel,
                model_name, input_tokens, output_tokens, tool_name, skill_name, mcp_server,
                tool_input, tool_output, error, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params_list = []
        for span in spans:
            params_list.append(
                (
                    span.span_id,
                    span.trace_id,
                    span.parent_span_id,
                    span.name,
                    span.event_type.value
                    if isinstance(span.event_type, EventType)
                    else span.event_type,
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
                    span.mcp_server,
                    json.dumps(span.tool_input) if span.tool_input else None,
                    span.tool_output,
                    span.error,
                    json.dumps(span.metadata) if span.metadata else None,
                ),
            )
        await self.db.execute_many(query, params_list)

    # Query operations

    def _build_overview_stats(
        self,
        total_users: int,
        online_users: int,
        token_row: Optional[dict],
        model_distribution: list,
        top_tools: list,
        top_skills: list,
        top_mcp_tools: list,
        mcp_servers: list,
    ) -> OverviewStats:
        """Build OverviewStats from collected data."""
        return OverviewStats(
            online_users=online_users,
            total_users=total_users,
            model_distribution=model_distribution,
            total_tokens=token_row["total_tokens"] or 0 if token_row else 0,
            input_tokens=token_row["input_tokens"] or 0 if token_row else 0,
            output_tokens=token_row["output_tokens"] or 0 if token_row else 0,
            total_sessions=token_row["total_sessions"] or 0
            if token_row
            else 0,
            total_conversations=token_row["total_sessions"] or 0
            if token_row
            else 0,
            avg_duration_ms=(
                int(token_row["avg_duration"] or 0)
                if token_row and token_row["avg_duration"]
                else 0
            ),
            top_tools=top_tools,
            top_skills=top_skills,
            top_mcp_tools=top_mcp_tools,
            mcp_servers=mcp_servers,
            daily_trend=[],
        )

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
        # Verify database connection
        if self.db is None or not self.db.is_connected:
            logger.error("Database not connected in get_overview_stats")
            return OverviewStats()

        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=1)  # Include today

        logger.debug(
            "get_overview_stats: start_date=%s, end_date=%s",
            start_date,
            end_date,
        )

        # Basic stats
        total_users = await self._db_get_total_users(start_date, end_date)
        online_users = await self._db_get_online_users()
        token_row = await self._db_get_token_stats(start_date, end_date)

        # Distribution stats
        model_distribution = await self._db_get_model_distribution(
            start_date,
            end_date,
        )
        top_tools = await self._db_get_top_tools(start_date, end_date)
        top_skills = await self._db_get_top_skills(start_date, end_date)
        top_mcp_tools, mcp_servers = await self._db_get_mcp_stats(
            start_date,
            end_date,
        )

        return self._build_overview_stats(
            total_users,
            online_users,
            token_row,
            model_distribution,
            top_tools,
            top_skills,
            top_mcp_tools,
            mcp_servers,
        )

    async def get_users(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[UserListItem], int]:
        """Get list of users with stats.

        Args:
            page: Page number
            page_size: Page size
            user_id: Filter by user ID
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Tuple of (users list, total count)
        """
        where_clauses: list[str] = []
        params: list[Any] = []
        if user_id:
            where_clauses.append("user_id LIKE %s")
            params.append(f"%{user_id}%")
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        count_query = f"""
            SELECT COUNT(DISTINCT user_id) as total
            FROM swe_tracing_traces
            WHERE {where_sql}
        """
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
                    WHERE s.trace_id IN (
                        SELECT trace_id FROM swe_tracing_traces WHERE user_id = t.user_id
                    )
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

    async def _get_user_model_usage(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ModelUsage]:
        """Get model usage for a user."""
        model_query = """
            SELECT model_name, COUNT(*) as count,
                   SUM(total_input_tokens) as input_tokens,
                   SUM(total_output_tokens) as output_tokens,
                   SUM(total_tokens) as total_tokens
            FROM swe_tracing_traces
            WHERE user_id = %s AND start_time >= %s AND start_time <= %s
                  AND model_name IS NOT NULL
            GROUP BY model_name
            ORDER BY count DESC
        """
        model_rows = await self.db.fetch_all(
            model_query,
            (user_id, start_date, end_date),
        )
        return [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"],
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in model_rows
        ]

    async def _get_user_tool_usage(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ToolUsage]:
        """Get tool usage for a user."""
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
        tool_rows = await self.db.fetch_all(
            tool_query,
            (user_id, start_date, end_date),
        )
        return [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in tool_rows
        ]

    async def _get_user_skill_usage(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[SkillUsage]:
        """Get skill usage for a user."""
        skill_query = """
            SELECT skill_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration
            FROM swe_tracing_spans
            WHERE user_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'skill_invocation'
              AND skill_name IS NOT NULL
            GROUP BY skill_name
            ORDER BY count DESC
        """
        skill_rows = await self.db.fetch_all(
            skill_query,
            (user_id, start_date, end_date),
        )
        return [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in skill_rows
        ]

    def _build_user_stats(
        self,
        user_id: str,
        stats_row: Optional[dict],
        model_usage: list[ModelUsage],
        tools_used: list[ToolUsage],
        skills_used: list[SkillUsage],
    ) -> UserStats:
        """Build UserStats from collected data."""
        return UserStats(
            user_id=user_id,
            model_usage=model_usage,
            total_tokens=stats_row["total_tokens"] if stats_row else 0,
            input_tokens=stats_row["input_tokens"] if stats_row else 0,
            output_tokens=stats_row["output_tokens"] if stats_row else 0,
            total_sessions=stats_row["total_sessions"] if stats_row else 0,
            total_conversations=stats_row["total_conversations"]
            if stats_row
            else 0,
            avg_duration_ms=int(stats_row["avg_duration"] or 0)
            if stats_row
            else 0,
            tools_used=tools_used,
            skills_used=skills_used,
        )

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
        stats_row = await self.db.fetch_one(
            stats_query,
            (user_id, start_date, end_date),
        )

        # Get usage data in parallel
        model_usage = await self._get_user_model_usage(
            user_id,
            start_date,
            end_date,
        )
        tools_used = await self._get_user_tool_usage(
            user_id,
            start_date,
            end_date,
        )
        skills_used = await self._get_user_skill_usage(
            user_id,
            start_date,
            end_date,
        )

        return self._build_user_stats(
            user_id,
            stats_row,
            model_usage,
            tools_used,
            skills_used,
        )

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
        where_clauses: list[str] = []
        params: list[Any] = []

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
                   JSON_LENGTH(skills_used) as skills_count
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
                skills_count=row["skills_count"] or 0,
            )
            for row in rows
        ]
        return traces, total

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
            if s.event_type
            in (EventType.TOOL_CALL_START, EventType.TOOL_CALL_END)
        )

        # Extract tool calls
        tools_called = []
        tool_spans = [
            s for s in spans if s.event_type == EventType.TOOL_CALL_END
        ]
        for span in tool_spans:
            tools_called.append(
                {
                    "tool_name": span.tool_name or span.name,
                    "tool_input": span.tool_input,
                    "tool_output": span.tool_output,
                    "duration_ms": span.duration_ms,
                    "error": span.error,
                },
            )

        return TraceDetail(
            trace=trace,
            spans=spans,
            llm_duration_ms=llm_duration,
            tool_duration_ms=tool_duration,
            tools_called=tools_called,
        )

    async def get_sessions(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[SessionListItem], int]:
        """Get list of sessions with stats.

        Args:
            page: Page number
            page_size: Page size
            user_id: Filter by user ID
            session_id: Filter by session ID (partial match)
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Tuple of (sessions list, total count)
        """
        where_clauses: list[str] = []
        params: list[Any] = []

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id LIKE %s")
            params.append(f"%{session_id}%")
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count of unique sessions
        count_query = f"""
            SELECT COUNT(DISTINCT session_id) as total
            FROM swe_tracing_traces
            WHERE {where_sql}
        """
        count_row = await self.db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        # Get sessions with skill counts from spans
        offset = (page - 1) * page_size
        query = f"""
            SELECT t.session_id,
                   t.user_id,
                   t.channel,
                   COUNT(*) as total_traces,
                   SUM(t.total_tokens) as total_tokens,
                   MIN(t.start_time) as first_active,
                   MAX(t.start_time) as last_active,
                   (SELECT COUNT(*) FROM swe_tracing_spans s
                    WHERE s.session_id = t.session_id
                    AND s.event_type = 'skill_invocation') as total_skills
            FROM swe_tracing_traces t
            WHERE {where_sql}
            GROUP BY t.session_id, t.user_id, t.channel
            ORDER BY last_active DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        rows = await self.db.fetch_all(query, tuple(params))
        sessions = [
            SessionListItem(
                session_id=row["session_id"],
                user_id=row["user_id"],
                channel=row["channel"],
                total_traces=row["total_traces"] or 0,
                total_tokens=row["total_tokens"] or 0,
                total_skills=row["total_skills"] or 0,
                first_active=row["first_active"],
                last_active=row["last_active"],
            )
            for row in rows
        ]
        return sessions, total

    async def get_session_stats(
        self,
        session_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> SessionStats:
        """Get statistics for a specific session.

        Args:
            session_id: Session identifier
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Session statistics
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        stats_row = await self._db_get_session_basic_stats(
            session_id,
            start_date,
            end_date,
        )

        if not stats_row or not stats_row.get("user_id"):
            return SessionStats(session_id=session_id, user_id="", channel="")

        user_id = stats_row["user_id"]
        channel = stats_row["channel"] or ""

        # Get distribution stats
        model_usage = await self._db_get_session_model_usage(
            session_id,
            start_date,
            end_date,
        )
        tools_used = await self._db_get_session_tools(
            session_id,
            start_date,
            end_date,
        )
        skills_used = await self._db_get_session_skills(
            session_id,
            start_date,
            end_date,
        )
        mcp_tools_used = await self._db_get_session_mcp_tools(
            session_id,
            start_date,
            end_date,
        )

        return SessionStats(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            model_usage=model_usage,
            total_tokens=stats_row["total_tokens"] or 0,
            input_tokens=stats_row["input_tokens"] or 0,
            output_tokens=stats_row["output_tokens"] or 0,
            total_traces=stats_row["total_traces"] or 0,
            avg_duration_ms=int(stats_row["avg_duration"] or 0)
            if stats_row and stats_row["avg_duration"]
            else 0,
            tools_used=tools_used,
            skills_used=skills_used,
            mcp_tools_used=mcp_tools_used,
            first_active=stats_row["first_active"],
            last_active=stats_row["last_active"],
        )

    async def get_user_messages(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query: Optional[str] = None,
        export: bool = False,
    ) -> tuple[list[UserMessageItem], int]:
        """Get user messages with token info for cost analysis.

        Args:
            page: Page number
            page_size: Page size
            user_id: Filter by user ID
            session_id: Filter by session ID
            start_date: Filter by start date
            end_date: Filter by end date
            query: Search in user message content (partial match)
            export: If True, return all results (ignore pagination)

        Returns:
            Tuple of (messages list, total count)
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.now()

        where_clauses = ["start_time >= %s", "start_time <= %s"]
        params: list[Any] = [start_date, end_date]

        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)
        if session_id:
            where_clauses.append("session_id = %s")
            params.append(session_id)
        if query:
            where_clauses.append("user_message LIKE %s")
            params.append(f"%{query}%")

        where_sql = " AND ".join(where_clauses)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM swe_tracing_traces WHERE {where_sql}"
        count_row = await self.db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        # Get messages
        if export:
            sql_query = f"""
                SELECT trace_id, user_id, session_id, channel, user_message,
                       total_input_tokens, total_output_tokens, model_name,
                       start_time, duration_ms
                FROM swe_tracing_traces
                WHERE {where_sql}
                ORDER BY start_time DESC
            """
            rows = await self.db.fetch_all(sql_query, tuple(params))
        else:
            offset = (page - 1) * page_size
            sql_query = f"""
                SELECT trace_id, user_id, session_id, channel, user_message,
                       total_input_tokens, total_output_tokens, model_name,
                       start_time, duration_ms
                FROM swe_tracing_traces
                WHERE {where_sql}
                ORDER BY start_time DESC
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])
            rows = await self.db.fetch_all(sql_query, tuple(params))

        messages = [
            UserMessageItem(
                trace_id=row["trace_id"],
                user_id=row["user_id"],
                session_id=row["session_id"],
                channel=row["channel"],
                user_message=row["user_message"],
                input_tokens=row["total_input_tokens"] or 0,
                output_tokens=row["total_output_tokens"] or 0,
                model_name=row["model_name"],
                start_time=row["start_time"],
                duration_ms=row["duration_ms"],
            )
            for row in rows
        ]
        return messages, total

    # Flush operation (no-op for database storage)

    async def flush(self) -> None:
        """Flush current data - no-op for database storage."""

    # Cleanup operation

    async def cleanup_old_data(self, cutoff_date: datetime) -> None:
        """Clean up data older than the cutoff date.

        Args:
            cutoff_date: Remove data older than this date
        """
        # Delete old spans
        span_query = """
            DELETE FROM swe_tracing_spans
            WHERE trace_id IN (
                SELECT trace_id FROM swe_tracing_traces
                WHERE start_time < %s
            )
        """
        await self.db.execute(span_query, (cutoff_date,))

        # Delete old traces
        trace_query = "DELETE FROM swe_tracing_traces WHERE start_time < %s"
        result = await self.db.execute(trace_query, (cutoff_date,))
        logger.info(
            "Cleaned up %d old traces (older than %s)",
            result,
            cutoff_date.strftime("%Y-%m-%d"),
        )

    # Database helper methods

    async def _db_get_total_users(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """Get total users count."""
        query = """
            SELECT COUNT(DISTINCT user_id) as total_users
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time <= %s
        """
        row = await self.db.fetch_one(query, (start_date, end_date))
        result = row["total_users"] if row else 0
        logger.debug(
            "_db_get_total_users: start=%s, end=%s, result=%s",
            start_date,
            end_date,
            result,
        )
        return result

    async def _db_get_online_users(self) -> int:
        """Get online users count (active in last 5 minutes)."""
        query = """
            SELECT COUNT(DISTINCT user_id) as online_users
            FROM swe_tracing_spans
            WHERE start_time >= %s
        """
        online_threshold = datetime.now() - timedelta(minutes=5)
        row = await self.db.fetch_one(query, (online_threshold,))
        return row["online_users"] if row else 0

    async def _db_get_token_stats(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[dict]:
        """Get token statistics."""
        query = """
            SELECT
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens,
                COUNT(*) as total_sessions,
                AVG(duration_ms) as avg_duration
            FROM swe_tracing_traces
            WHERE start_time >= %s AND start_time <= %s
        """
        return await self.db.fetch_one(query, (start_date, end_date))

    async def _db_get_model_distribution(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ModelUsage]:
        """Get model distribution."""
        query = """
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
        rows = await self.db.fetch_all(query, (start_date, end_date))
        return [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"] or 0,
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in rows
        ]

    async def _db_get_top_tools(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ToolUsage]:
        """Get top tools (non-MCP)."""
        query = """
            SELECT tool_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND tool_name IS NOT NULL
              AND mcp_server IS NULL
            GROUP BY tool_name
            ORDER BY count DESC
            LIMIT 10
        """
        rows = await self.db.fetch_all(query, (start_date, end_date))
        return [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in rows
        ]

    async def _db_get_top_skills(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[SkillUsage]:
        """Get top skills."""
        query = """
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
        rows = await self.db.fetch_all(query, (start_date, end_date))
        return [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in rows
        ]

    async def _db_get_mcp_stats(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[list[MCPToolUsage], list[MCPServerUsage]]:
        """Get MCP tools and server statistics."""
        # Get top MCP tools
        mcp_tool_query = """
            SELECT tool_name, mcp_server, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND mcp_server IS NOT NULL
            GROUP BY tool_name, mcp_server
            ORDER BY count DESC
            LIMIT 10
        """
        mcp_tool_rows = await self.db.fetch_all(
            mcp_tool_query,
            (start_date, end_date),
        )
        top_mcp_tools = [
            MCPToolUsage(
                tool_name=row["tool_name"],
                mcp_server=row["mcp_server"],
                count=row["count"] or 0,
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in mcp_tool_rows
        ]

        # Get MCP server statistics
        mcp_servers = await self._db_get_mcp_servers(start_date, end_date)

        return top_mcp_tools, mcp_servers

    async def _db_get_mcp_servers(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MCPServerUsage]:
        """Get MCP server statistics with tools."""
        query = """
            SELECT mcp_server,
                   COUNT(DISTINCT tool_name) as tool_count,
                   COUNT(*) as total_calls,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND mcp_server IS NOT NULL
            GROUP BY mcp_server
            ORDER BY total_calls DESC
        """
        server_rows = await self.db.fetch_all(query, (start_date, end_date))

        mcp_servers = []
        for server_row in server_rows:
            server_name = server_row["mcp_server"]
            tools = await self._db_get_server_tools(
                start_date,
                end_date,
                server_name,
            )
            mcp_servers.append(
                MCPServerUsage(
                    server_name=server_name,
                    tool_count=server_row["tool_count"] or 0,
                    total_calls=server_row["total_calls"] or 0,
                    avg_duration_ms=int(server_row["avg_duration"] or 0),
                    error_count=server_row["error_count"] or 0,
                    tools=tools,
                ),
            )

        return mcp_servers

    async def _db_get_server_tools(
        self,
        start_date: datetime,
        end_date: datetime,
        server_name: str,
    ) -> list[MCPToolUsage]:
        """Get tools for a specific MCP server."""
        query = """
            SELECT tool_name, mcp_server, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND mcp_server = %s
            GROUP BY tool_name, mcp_server
            ORDER BY count DESC
        """
        rows = await self.db.fetch_all(
            query,
            (start_date, end_date, server_name),
        )
        return [
            MCPToolUsage(
                tool_name=r["tool_name"],
                mcp_server=r["mcp_server"],
                count=r["count"] or 0,
                avg_duration_ms=int(r["avg_duration"] or 0),
                error_count=r["error_count"] or 0,
            )
            for r in rows
        ]

    async def _db_get_session_basic_stats(
        self,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[dict]:
        """Get basic session stats."""
        query = """
            SELECT
                user_id,
                channel,
                COUNT(*) as total_traces,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(duration_ms) as avg_duration,
                MIN(start_time) as first_active,
                MAX(start_time) as last_active
            FROM swe_tracing_traces
            WHERE session_id = %s AND start_time >= %s AND start_time <= %s
            GROUP BY user_id, channel
        """
        return await self.db.fetch_one(
            query,
            (session_id, start_date, end_date),
        )

    async def _db_get_session_model_usage(
        self,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ModelUsage]:
        """Get model usage for session."""
        query = """
            SELECT model_name, COUNT(*) as count,
                   SUM(total_input_tokens) as input_tokens,
                   SUM(total_output_tokens) as output_tokens,
                   SUM(total_tokens) as total_tokens
            FROM swe_tracing_traces
            WHERE session_id = %s AND start_time >= %s AND start_time <= %s
                  AND model_name IS NOT NULL
            GROUP BY model_name
            ORDER BY count DESC
        """
        rows = await self.db.fetch_all(
            query,
            (session_id, start_date, end_date),
        )
        return [
            ModelUsage(
                model_name=row["model_name"],
                count=row["count"],
                total_tokens=row["total_tokens"] or 0,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
            )
            for row in rows
        ]

    async def _db_get_session_tools(
        self,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ToolUsage]:
        """Get tool usage for session (non-MCP)."""
        query = """
            SELECT tool_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND tool_name IS NOT NULL
              AND mcp_server IS NULL
            GROUP BY tool_name
            ORDER BY count DESC
        """
        rows = await self.db.fetch_all(
            query,
            (session_id, start_date, end_date),
        )
        return [
            ToolUsage(
                tool_name=row["tool_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in rows
        ]

    async def _db_get_session_mcp_tools(
        self,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MCPToolUsage]:
        """Get MCP tool usage for session."""
        query = """
            SELECT tool_name, mcp_server, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM swe_tracing_spans
            WHERE session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'tool_call_end'
              AND mcp_server IS NOT NULL
            GROUP BY tool_name, mcp_server
            ORDER BY count DESC
        """
        rows = await self.db.fetch_all(
            query,
            (session_id, start_date, end_date),
        )
        return [
            MCPToolUsage(
                tool_name=row["tool_name"],
                mcp_server=row["mcp_server"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
                error_count=row["error_count"] or 0,
            )
            for row in rows
        ]

    async def _db_get_session_skills(
        self,
        session_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[SkillUsage]:
        """Get skill usage for session."""
        query = """
            SELECT skill_name, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration
            FROM swe_tracing_spans
            WHERE session_id = %s AND start_time >= %s AND start_time <= %s
              AND event_type = 'skill_invocation'
              AND skill_name IS NOT NULL
            GROUP BY skill_name
            ORDER BY count DESC
        """
        rows = await self.db.fetch_all(
            query,
            (session_id, start_date, end_date),
        )
        return [
            SkillUsage(
                skill_name=row["skill_name"],
                count=row["count"],
                avg_duration_ms=int(row["avg_duration"] or 0),
            )
            for row in rows
        ]

    # Row conversion helpers

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
            tools_used=json.loads(row["tools_used"])
            if row["tools_used"]
            else [],
            skills_used=json.loads(row["skills_used"])
            if row["skills_used"]
            else [],
            status=TraceStatus(row["status"])
            if row["status"]
            else TraceStatus.RUNNING,
            error=row["error"],
            user_message=row.get("user_message"),
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
            mcp_server=row.get("mcp_server"),
            tool_input=json.loads(row["tool_input"])
            if row["tool_input"]
            else None,
            tool_output=row["tool_output"],
            error=row["error"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )
