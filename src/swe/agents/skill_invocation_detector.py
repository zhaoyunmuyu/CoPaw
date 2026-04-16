# -*- coding: utf-8 -*-
"""Skill invocation detector for detecting skill boundaries.

This module provides the SkillInvocationDetector which detects when tool
calls belong to skill execution flows, manages skill execution boundaries,
and resolves multi-skill attribution conflicts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from .skill_context_manager import (
    SkillContextManager,
    get_skill_context_manager,
)
from .skill_feature_inferencer import (
    SkillFeatureInferencer,
    get_skill_feature_inferencer,
)
from .skill_tool_registry import SkillToolRegistry, get_skill_tool_registry

if TYPE_CHECKING:
    from ..tracing.manager import TraceManager

logger = logging.getLogger(__name__)


class SkillInvocationDetector:
    """Skill invocation detector.

    Responsible for:
    1. Detecting tool calls that belong to skill execution flows
    2. Managing skill execution start/end boundaries
    3. Resolving multi-skill attribution conflicts
    4. Tracking skill state and activity

    The detector uses multiple layers for attribution:
    - Layer 1: Explicit declaration (uses_tools in SKILL.md)
    - Layer 2: Feature matching (file extensions, keywords)
    - Layer 3: Tool sequence patterns
    - Layer 4: Skill-tool association hints

    Example:
        detector = SkillInvocationDetector(
            registry=get_skill_tool_registry(),
            context_manager=get_skill_context_manager(),
        )
        detector.set_enabled_skills(["xlsx", "pdf"])

        # On tool call
        primary_skill, weights = await detector.on_tool_call(
            "execute_shell_command",
            {"command": "python process.py data.xlsx"},
        )
        # Returns: ("xlsx", {"xlsx": 0.8, "pdf": 0.2})
    """

    def __init__(
        self,
        registry: Optional[SkillToolRegistry] = None,
        context_manager: Optional[SkillContextManager] = None,
        inferencer: Optional[SkillFeatureInferencer] = None,
        trace_manager: Optional["TraceManager"] = None,
        trace_id: Optional[str] = None,
        user_id: str = "",
        session_id: str = "",
        channel: str = "",
        idle_threshold: int = 3,
    ) -> None:
        """Initialize the detector.

        Args:
            registry: Skill-tool registry for explicit declarations
            context_manager: Skill context manager for execution tracking
            inferencer: Feature inferencer for legacy skill support
            trace_manager: Optional trace manager for emitting events
            trace_id: Current trace ID
            user_id: User identifier
            session_id: Session identifier
            channel: Channel identifier
            idle_threshold: Number of non-skill tool calls before ending skill
        """
        self._registry = registry or get_skill_tool_registry()
        self._context_manager = context_manager or get_skill_context_manager()
        self._inferencer = inferencer or get_skill_feature_inferencer()
        self._trace_manager = trace_manager
        self._trace_id = trace_id
        self._user_id = user_id
        self._session_id = session_id
        self._channel = channel

        # Configuration
        self._idle_threshold = idle_threshold

        # State tracking
        self._enabled_skills: set[str] = set()
        self._skill_activation_time: dict[str, datetime] = {}
        self._skill_call_history: dict[str, int] = {}
        self._idle_counters: dict[str, int] = {}
        self._recent_tools: list[str] = []

        # Layer 0: User message detection cache
        self._message_detected_skill: Optional[str] = None
        self._message_detected_confidence: float = 0.0

    def set_enabled_skills(self, skills: list[str]) -> None:
        """Set the list of enabled skills.

        Args:
            skills: List of skill names that are currently enabled
        """
        self._enabled_skills = set(skills)
        logger.debug("Enabled skills set: %s", skills)

    def detect_from_user_message(
        self,
        user_message: str,
    ) -> tuple[Optional[str], float]:
        """Layer 0: Detect skill from user message content.

        This method should be called at the start of a trace, before any
        tool calls are made. The result is cached for use during tool
        call detection.

        Args:
            user_message: User's message text

        Returns:
            Tuple of (skill_name, confidence) or (None, 0.0)
        """
        enabled_skills = list(self._enabled_skills)

        skill, confidence = self._inferencer.infer_skill_from_user_message(
            user_message,
            enabled_skills,
        )

        if skill:
            self._message_detected_skill = skill
            self._message_detected_confidence = confidence
            logger.debug(
                "Layer 0 detected skill '%s' from user message (confidence: %.2f)",
                skill,
                confidence,
            )

        return skill, confidence

    def set_tracing_context(
        self,
        trace_manager: "TraceManager",
        trace_id: str,
        user_id: str,
        session_id: str,
        channel: str,
    ) -> None:
        """Set tracing context for emitting events.

        Args:
            trace_manager: Trace manager instance
            trace_id: Current trace ID
            user_id: User identifier
            session_id: Session identifier
            channel: Channel identifier
        """
        self._trace_manager = trace_manager
        self._trace_id = trace_id
        self._user_id = user_id
        self._session_id = session_id
        self._channel = channel

    async def on_tool_call(
        self,
        tool_name: str,
        tool_input: Optional[dict[str, Any]] = None,
        mcp_server: Optional[str] = None,
    ) -> tuple[Optional[str], dict[str, float]]:
        """Process a tool call and determine skill attribution.

        This is the main entry point for skill detection. It:
        1. Queries the registry for explicit declarations
        2. Falls back to feature inference if needed
        3. Manages skill activation/deactivation
        4. Returns attribution with weights

        Args:
            tool_name: Name of the tool being called
            tool_input: Tool input parameters (for inference)
            mcp_server: MCP server name if this is an MCP tool

        Returns:
            Tuple of (primary_skill, weights_dict)
            - primary_skill: The main skill to attribute this call to
            - weights: Dict mapping skill_name -> weight (sum = 1.0)
        """
        tool_input = tool_input or {}

        # Track recent tools for sequence matching
        self._recent_tools.append(tool_name)
        if len(self._recent_tools) > 10:
            self._recent_tools.pop(0)

        # Step 1: Check for explicit declaration
        declared_skills = self._registry.get_skills_for_tool(tool_name)

        # Filter to enabled skills only
        declared_skills = [
            s for s in declared_skills if s in self._enabled_skills
        ]

        if declared_skills:
            return await self._handle_declared_skills(
                declared_skills,
                tool_name,
                tool_input,
            )

        # Step 2-4: Fallback to inference for legacy skills
        return await self._infer_skill_attribution(
            tool_name,
            tool_input,
            mcp_server,
        )

    async def _handle_declared_skills(
        self,
        skills: list[str],
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> tuple[Optional[str], dict[str, float]]:
        """Handle tool call with explicit skill declarations.

        Args:
            skills: Skills that declare using this tool
            tool_name: Tool name
            tool_input: Tool input

        Returns:
            Tuple of (primary_skill, weights)
        """
        current = self._context_manager.current_skill

        # Check if current active skill is in the list
        if current and current in skills:
            # Continue current skill
            self._update_skill_state(current)
            self._context_manager.record_tool_call(tool_name)
            return current, {current: 1.0}

        # Check if current skill should end (idle threshold)
        if current:
            self._idle_counters[current] = (
                self._idle_counters.get(current, 0) + 1
            )
            if self._idle_counters[current] >= self._idle_threshold:
                await self._end_skill(current)
                current = None

        # Calculate weights for multi-skill attribution
        weights = self._calculate_weights(skills, tool_name, tool_input)

        # Select primary skill (highest weight)
        primary_skill = (
            max(weights, key=lambda k: weights[k]) if weights else None
        )

        # Start new skill if none active
        if not current and primary_skill:
            await self._start_skill(
                primary_skill,
                trigger_tool=tool_name,
                trigger_reason="declared",
                confidence=weights[primary_skill],
            )
            self._context_manager.record_tool_call(tool_name)

        return primary_skill, weights

    async def _infer_skill_attribution(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        mcp_server: Optional[str] = None,
    ) -> tuple[Optional[str], dict[str, float]]:
        """Infer skill attribution for tools without explicit declarations.

        Uses multiple layers:
        0. Cached user message detection (if available)
        1. MCP server matching
        2. Feature matching (file extensions, keywords)
        3. Tool sequence patterns
        4. Tool-skill hints

        Args:
            tool_name: Tool name
            tool_input: Tool input
            mcp_server: MCP server if applicable

        Returns:
            Tuple of (primary_skill, weights)
        """
        enabled_skills = list(self._enabled_skills)

        # Layer 0: Check cached user message detection
        if (
            self._message_detected_skill
            and self._message_detected_confidence >= 0.7
        ):
            skill = self._message_detected_skill
            confidence = self._message_detected_confidence
            await self._ensure_skill_active(skill, confidence, tool_name)
            self._context_manager.record_tool_call(tool_name, mcp_server)
            return skill, {skill: confidence}

        # Layer 1: MCP server matching
        if mcp_server:
            skill, confidence = self._inferencer.infer_skill_from_mcp_server(
                mcp_server,
                enabled_skills,
            )
            if skill and confidence >= 0.8:
                await self._ensure_skill_active(skill, confidence, tool_name)
                self._context_manager.record_tool_call(tool_name, mcp_server)
                return skill, {skill: confidence}

        # Layer 2: Feature matching
        skill, confidence = self._inferencer.infer_skill_from_tool_input(
            tool_name,
            tool_input,
            enabled_skills,
        )
        if skill and confidence >= 0.6:
            await self._ensure_skill_active(skill, confidence, tool_name)
            self._context_manager.record_tool_call(tool_name, mcp_server)
            return skill, {skill: confidence}

        # Layer 3: Tool sequence patterns
        skill, confidence = self._inferencer.infer_skill_from_tool_sequence(
            self._recent_tools,
            enabled_skills,
        )
        if skill and confidence >= 0.5:
            await self._ensure_skill_active(skill, confidence, tool_name)
            self._context_manager.record_tool_call(tool_name, mcp_server)
            return skill, {skill: confidence}

        # Layer 4: Tool hints
        inferred = self._inferencer.get_skills_for_tool(
            tool_name,
            enabled_skills,
        )
        if inferred:
            primary_skill = inferred[0][0]
            weights = dict(inferred)
            await self._ensure_skill_active(
                primary_skill,
                weights.get(primary_skill, 0.4),
                tool_name,
            )
            self._context_manager.record_tool_call(tool_name, mcp_server)
            return primary_skill, weights

        # No attribution possible
        return None, {}

    async def _ensure_skill_active(
        self,
        skill_name: str,
        confidence: float,
        trigger_tool: str,
    ) -> None:
        """Ensure a skill is active, starting it if needed.

        Args:
            skill_name: Skill to ensure active
            confidence: Attribution confidence
            trigger_tool: Tool that triggered this skill
        """
        current = self._context_manager.current_skill

        if current == skill_name:
            # Already active, just update state
            self._update_skill_state(skill_name)
            return

        if current:
            # Different skill active, end it first
            await self._end_skill(current)

        # Start the new skill
        await self._start_skill(
            skill_name,
            trigger_tool=trigger_tool,
            trigger_reason="inferred",
            confidence=confidence,
        )

    def _calculate_weights(
        self,
        skills: list[str],
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, float]:
        """Calculate attribution weights for multi-skill scenarios.

        Uses multiple factors:
        - Recency of activation (0-0.4)
        - Input feature matching (0-0.3)
        - Call frequency (0-0.2)
        - Enabled status (0-0.1)

        Args:
            skills: Skills claiming this tool
            tool_name: Tool name
            tool_input: Tool input

        Returns:
            Dict mapping skill_name -> weight (sum = 1.0)
        """
        if len(skills) == 1:
            return {skills[0]: 1.0}

        scores: dict[str, float] = {}

        for skill in skills:
            score = 0.0

            # Factor 1: Recent activation (decays over 5 minutes)
            if skill in self._skill_activation_time:
                elapsed = (
                    datetime.now() - self._skill_activation_time[skill]
                ).seconds
                recency = max(0, 0.4 * (1 - elapsed / 300))
                score += recency

            # Factor 2: Input feature matching
            input_score = self._match_tool_input(skill, tool_name, tool_input)
            score += input_score * 0.3

            # Factor 3: Call frequency
            calls = self._skill_call_history.get(skill, 0)
            frequency = min(0.2, calls * 0.02)
            score += frequency

            # Factor 4: Enabled status
            if skill in self._enabled_skills:
                score += 0.1

            scores[skill] = score

        # Normalize to sum = 1.0
        total = sum(scores.values())
        if total > 0:
            return {k: v / total for k, v in scores.items()}
        else:
            # Equal distribution if no factors apply
            n = len(skills)
            return {s: 1.0 / n for s in skills}

    def _match_tool_input(
        self,
        skill: str,
        _tool_name: str,
        tool_input: dict[str, Any],
    ) -> float:
        """Match tool input against skill features.

        Args:
            skill: Skill name
            tool_name: Tool name
            tool_input: Tool input parameters

        Returns:
            Match score (0.0-1.0)
        """
        feature = self._inferencer.get_feature(skill)
        if not feature:
            return 0.5  # No feature info, neutral score

        input_str = str(tool_input).lower()
        matches = sum(
            1 for f in feature.file_extensions if f.lower() in input_str
        )
        matches += sum(1 for kw in feature.keywords if kw.lower() in input_str)

        if not feature.file_extensions and not feature.keywords:
            return 0.5

        total_features = len(feature.file_extensions) + len(feature.keywords)
        if total_features == 0:
            return 0.5

        return matches / total_features

    def _update_skill_state(self, skill: str) -> None:
        """Update skill state after a tool call.

        Args:
            skill: Skill name to update
        """
        self._skill_activation_time[skill] = datetime.now()
        self._skill_call_history[skill] = (
            self._skill_call_history.get(skill, 0) + 1
        )
        if skill in self._idle_counters:
            self._idle_counters[skill] = 0

    async def _start_skill(
        self,
        skill_name: str,
        trigger_tool: str,
        trigger_reason: str = "inferred",
        confidence: float = 1.0,
    ) -> None:
        """Start a new skill invocation.

        Args:
            skill_name: Skill to start
            trigger_tool: Tool that triggered this skill
            trigger_reason: How the skill was detected
            confidence: Attribution confidence
        """
        # Push to context manager
        self._context_manager.push_skill(
            skill_name,
            trigger_reason=trigger_reason,
            confidence=confidence,
        )

        # Update state
        self._update_skill_state(skill_name)

        # Emit tracing event
        if self._trace_manager and self._trace_id:
            try:
                await self._trace_manager.emit_skill_invocation(
                    trace_id=self._trace_id,
                    skill_name=skill_name,
                    user_id=self._user_id,
                    session_id=self._session_id,
                    channel=self._channel,
                    skill_input={
                        "trigger_tool": trigger_tool,
                        "trigger_reason": trigger_reason,
                        "confidence": confidence,
                    },
                )
            except Exception as e:
                logger.debug("Failed to emit skill start event: %s", e)

        logger.debug(
            "Started skill '%s' (reason: %s, confidence: %.2f)",
            skill_name,
            trigger_reason,
            confidence,
        )

    async def _end_skill(self, skill_name: str) -> None:
        """End a skill invocation.

        Args:
            skill_name: Skill to end
        """
        # Pop from context manager
        context = self._context_manager.pop_skill()

        if context is None:
            return

        # Emit tracing event
        if self._trace_manager and self._trace_id:
            try:
                # Find the span_id for this skill invocation
                # The span would have been created on start
                await self._trace_manager.end_skill_invocation(
                    trace_id=self._trace_id,
                    span_id="",  # Will be handled by context
                    skill_output=json.dumps(
                        {
                            "tools_called": context.tools_called,
                            "mcp_tools_called": context.mcp_tools_called,
                            "total_tools": len(context.tools_called)
                            + len(context.mcp_tools_called),
                        },
                    ),
                )
            except Exception as e:
                logger.debug("Failed to emit skill end event: %s", e)

        logger.debug(
            "Ended skill '%s' (tools: %d, mcp: %d)",
            skill_name,
            len(context.tools_called),
            len(context.mcp_tools_called),
        )

    async def on_reasoning_end(self) -> None:
        """Handle end of LLM reasoning.

        Ends all active skills when reasoning completes.
        """
        # End all skills in the stack (from top to bottom)
        while self._context_manager.skill_depth > 0:
            current = self._context_manager.current_skill
            if current:
                await self._end_skill(current)
            else:
                break

        # Clear any remaining state
        self._context_manager.clear()

    def reset(self) -> None:
        """Reset detector state for a new request."""
        self._skill_activation_time.clear()
        self._skill_call_history.clear()
        self._idle_counters.clear()
        self._recent_tools.clear()
        self._context_manager.clear()
        # Clear Layer 0 cache
        self._message_detected_skill = None
        self._message_detected_confidence = 0.0


# Global detector instance (per-request, should be reset)
_skill_invocation_detector: Optional[SkillInvocationDetector] = None


def get_skill_invocation_detector() -> SkillInvocationDetector:
    """Get the global skill invocation detector.

    Returns:
        SkillInvocationDetector instance
    """
    global _skill_invocation_detector
    if _skill_invocation_detector is None:
        _skill_invocation_detector = SkillInvocationDetector()
    return _skill_invocation_detector


def reset_skill_invocation_detector() -> None:
    """Reset the global detector (for testing or new request)."""
    global _skill_invocation_detector
    if _skill_invocation_detector is not None:
        _skill_invocation_detector.reset()
    _skill_invocation_detector = None
