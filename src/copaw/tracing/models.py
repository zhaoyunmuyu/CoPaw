# -*- coding: utf-8 -*-
"""Tracing data models.

Defines Trace, Span, and EventType for tracing events.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types for tracing."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    LLM_INPUT = "llm_input"
    LLM_OUTPUT = "llm_output"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    SKILL_INVOCATION = "skill_invocation"


class TraceStatus(str, Enum):
    """Trace status."""

    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class Span(BaseModel):
    """Span represents a single operation within a trace.

    A span can be an LLM call, tool execution, or other operation.
    """

    span_id: str = Field(description="Unique span identifier")
    trace_id: str = Field(description="Parent trace identifier")
    parent_span_id: Optional[str] = Field(
        default=None,
        description="Parent span identifier for nested operations",
    )
    name: str = Field(description="Span name/operation name")
    event_type: EventType = Field(description="Type of event")
    start_time: datetime = Field(description="Start timestamp")
    end_time: Optional[datetime] = Field(default=None, description="End timestamp")
    duration_ms: Optional[int] = Field(default=None, description="Duration in milliseconds")
    user_id: str = Field(description="User identifier")
    session_id: str = Field(description="Session identifier")
    channel: str = Field(description="Channel identifier")
    model_name: Optional[str] = Field(default=None, description="Model name for LLM events")
    input_tokens: Optional[int] = Field(default=None, description="Input token count")
    output_tokens: Optional[int] = Field(default=None, description="Output token count")
    tool_name: Optional[str] = Field(default=None, description="Tool name for tool events")
    skill_name: Optional[str] = Field(default=None, description="Skill name for skill events")
    tool_input: Optional[dict[str, Any]] = Field(
        default=None,
        description="Tool input (sanitized)",
    )
    tool_output: Optional[str] = Field(
        default=None,
        description="Tool output (truncated)",
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata",
    )

    class Config:
        use_enum_values = True


class Trace(BaseModel):
    """Trace represents a complete request/session trace.

    A trace contains multiple spans and represents the full lifecycle
    of a user request.
    """

    trace_id: str = Field(description="Unique trace identifier")
    user_id: str = Field(description="User identifier")
    session_id: str = Field(description="Session identifier")
    channel: str = Field(description="Channel identifier")
    start_time: datetime = Field(description="Trace start timestamp")
    end_time: Optional[datetime] = Field(default=None, description="Trace end timestamp")
    duration_ms: Optional[int] = Field(default=None, description="Total duration in milliseconds")
    model_name: Optional[str] = Field(default=None, description="Primary model used")
    total_input_tokens: int = Field(default=0, description="Total input tokens")
    total_output_tokens: int = Field(default=0, description="Total output tokens")
    tools_used: list[str] = Field(default_factory=list, description="Tools used in trace")
    skills_used: list[str] = Field(default_factory=list, description="Skills used in trace")
    status: TraceStatus = Field(default=TraceStatus.RUNNING, description="Trace status")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    class Config:
        use_enum_values = True


class SpanCreate(BaseModel):
    """Payload for creating a new span."""

    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    event_type: EventType
    user_id: str
    session_id: str
    channel: str
    model_name: Optional[str] = None
    input_tokens: Optional[int] = None
    tool_name: Optional[str] = None
    skill_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None


class SpanUpdate(BaseModel):
    """Payload for updating an existing span."""

    span_id: str
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    output_tokens: Optional[int] = None
    tool_output: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


# API Response Models

class ModelUsage(BaseModel):
    """Model usage statistics."""

    model_name: str
    count: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class ToolUsage(BaseModel):
    """Tool usage statistics."""

    tool_name: str
    count: int = 0
    avg_duration_ms: int = 0
    error_count: int = 0


class SkillUsage(BaseModel):
    """Skill usage statistics."""

    skill_name: str
    count: int = 0
    avg_duration_ms: int = 0


class DailyStats(BaseModel):
    """Daily statistics."""

    date: str
    total_users: int = 0
    active_users: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    session_count: int = 0
    conversation_count: int = 0
    avg_duration_ms: int = 0


class OverviewStats(BaseModel):
    """Overview dashboard statistics."""

    online_users: int = 0
    total_users: int = 0
    model_distribution: list[ModelUsage] = Field(default_factory=list)
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_sessions: int = 0
    total_conversations: int = 0
    avg_duration_ms: int = 0
    top_tools: list[ToolUsage] = Field(default_factory=list)
    top_skills: list[SkillUsage] = Field(default_factory=list)
    daily_trend: list[DailyStats] = Field(default_factory=list)


class UserStats(BaseModel):
    """User-specific statistics."""

    user_id: str
    model_usage: list[ModelUsage] = Field(default_factory=list)
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_sessions: int = 0
    total_conversations: int = 0
    avg_duration_ms: int = 0
    tools_used: list[ToolUsage] = Field(default_factory=list)
    skills_used: list[SkillUsage] = Field(default_factory=list)


class ToolCall(BaseModel):
    """Tool call details in a trace."""

    tool_name: str
    tool_input: Optional[dict[str, Any]] = None
    tool_output: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


class TraceDetail(BaseModel):
    """Detailed trace with spans."""

    trace: Trace
    spans: list[Span] = Field(default_factory=list)
    llm_duration_ms: int = 0
    tool_duration_ms: int = 0
    tools_called: list[ToolCall] = Field(default_factory=list)


class UserListItem(BaseModel):
    """User list item with stats."""

    user_id: str
    total_sessions: int = 0
    total_conversations: int = 0
    total_tokens: int = 0
    total_skills: int = 0
    last_active: Optional[datetime] = None


class TraceListItem(BaseModel):
    """Trace list item."""

    trace_id: str
    user_id: str
    session_id: str
    channel: str
    start_time: datetime
    duration_ms: Optional[int] = None
    total_tokens: int = 0
    model_name: Optional[str] = None
    status: str
    tools_count: int = 0
