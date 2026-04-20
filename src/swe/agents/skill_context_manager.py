# -*- coding: utf-8 -*-
"""Skill context manager for request-level skill execution isolation.

This module provides context management for skill execution using ContextVar
for request-scoped isolation. It tracks the active skill stack and records
tool calls within skill contexts.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SkillExecutionContext:
    """Skill execution context.

    Tracks the execution state of a skill invocation including timing,
    tool calls, and attribution confidence.

    Attributes:
        skill_name: Name of the skill being executed
        start_time: When the skill execution started
        trigger_reason: How the skill was detected (declared/inferred/keyword)
        tools_called: List of built-in tools called during execution
        mcp_tools_called: List of MCP tools called during execution
        confidence: Attribution confidence level (0.0-1.0)
        span_id: Span ID for tracing (used to update duration on end)
    """

    skill_name: str
    start_time: datetime
    trigger_reason: str = "inferred"
    tools_called: list[str] = field(default_factory=list)
    mcp_tools_called: list[str] = field(default_factory=list)
    confidence: float = 1.0
    span_id: Optional[str] = None


class SkillContextManager:
    """Skill context manager using ContextVar for request isolation.

    Manages a stack of active skill contexts for proper attribution of
    tool calls. Each request/session has its own isolated context stack.

    Example:
        manager = SkillContextManager()
        manager.push_skill("xlsx", trigger_reason="declared")
        manager.record_tool_call("execute_shell_command")
        manager.record_tool_call("read_file", mcp_server="filesystem")
        context = manager.pop_skill()
        # context.tools_called = ["execute_shell_command"]
        # context.mcp_tools_called = ["filesystem:read_file"]
    """

    _current_context: ContextVar[Optional[SkillExecutionContext]] = ContextVar(
        "skill_context",
        default=None,
    )
    _context_stack: ContextVar[list[SkillExecutionContext]] = ContextVar(
        "skill_context_stack",
    )

    def __init__(self) -> None:
        """Initialize the context manager."""
        # Initialize empty stack
        self._context_stack.set([])

    def push_skill(
        self,
        skill_name: str,
        trigger_reason: str = "inferred",
        confidence: float = 1.0,
        span_id: Optional[str] = None,
    ) -> None:
        """Start a new skill execution context.

        Adds a new skill context to the stack and sets it as current.
        Supports nested skill invocations.

        Args:
            skill_name: Name of the skill to activate
            trigger_reason: How the skill was detected
                - "declared": Explicitly declared in uses_tools
                - "inferred": Detected through inference
                - "keyword": Detected through trigger keywords
            confidence: Attribution confidence (0.0-1.0)
            span_id: Span ID for tracing (used to update duration on end)
        """
        context = SkillExecutionContext(
            skill_name=skill_name,
            start_time=datetime.now(),
            trigger_reason=trigger_reason,
            confidence=confidence,
            span_id=span_id,
        )

        # Get current stack and append (ContextVar requires re-assignment)
        stack = self._context_stack.get()
        stack = stack + [context]
        self._context_stack.set(stack)
        self._current_context.set(context)

    def pop_skill(self) -> Optional[SkillExecutionContext]:
        """End the current skill execution context.

        Removes the top skill from the stack and returns its context.
        Sets the next skill in stack as current (if any).

        Returns:
            The ended skill context, or None if stack is empty
        """
        stack = self._context_stack.get()
        if not stack:
            return None

        context = stack[-1]
        stack = stack[:-1]
        self._context_stack.set(stack)
        self._current_context.set(stack[-1] if stack else None)

        return context

    @property
    def current_skill(self) -> Optional[str]:
        """Get the name of the currently active skill.

        Returns:
            Skill name if a skill is active, None otherwise
        """
        context = self._current_context.get()
        return context.skill_name if context else None

    @property
    def current_context(self) -> Optional[SkillExecutionContext]:
        """Get the current skill execution context.

        Returns:
            Current context if active, None otherwise
        """
        return self._current_context.get()

    @property
    def active_skills(self) -> list[str]:
        """Get all active skills in the stack (from bottom to top).

        Returns:
            List of skill names in execution order
        """
        stack = self._context_stack.get()
        return [ctx.skill_name for ctx in stack]

    @property
    def skill_depth(self) -> int:
        """Get the depth of the skill stack.

        Returns:
            Number of nested skills currently active
        """
        return len(self._context_stack.get())

    def record_tool_call(
        self,
        tool_name: str,
        mcp_server: Optional[str] = None,
    ) -> None:
        """Record a tool call in the current skill context.

        Args:
            tool_name: Name of the tool called
            mcp_server: MCP server name if this is an MCP tool
        """
        context = self._current_context.get()
        if not context:
            return

        if mcp_server:
            full_tool_name = f"{mcp_server}:{tool_name}"
            if full_tool_name not in context.mcp_tools_called:
                context.mcp_tools_called.append(full_tool_name)
        else:
            if tool_name not in context.tools_called:
                context.tools_called.append(tool_name)

    def clear(self) -> None:
        """Clear all skill contexts.

        Resets the context stack and current context to empty.
        Use this at the end of a request/session to clean up.
        """
        self._current_context.set(None)
        self._context_stack.set([])

    def get_all_contexts(self) -> list[SkillExecutionContext]:
        """Get all skill execution contexts in the stack.

        Returns:
            List of all contexts from bottom to top
        """
        return list(self._context_stack.get())


# Global instance for convenience
_skill_context_manager: Optional[SkillContextManager] = None


def get_skill_context_manager() -> SkillContextManager:
    """Get the global skill context manager.

    Returns:
        SkillContextManager instance (creates new if not exists)
    """
    global _skill_context_manager
    if _skill_context_manager is None:
        _skill_context_manager = SkillContextManager()
    return _skill_context_manager


def reset_skill_context_manager() -> None:
    """Reset the global context manager (for testing)."""
    global _skill_context_manager
    if _skill_context_manager is not None:
        _skill_context_manager.clear()
    _skill_context_manager = None
