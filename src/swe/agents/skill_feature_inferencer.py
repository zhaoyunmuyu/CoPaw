# -*- coding: utf-8 -*-
"""Skill feature inferencer for multi-layer attribution.

This module provides inference capabilities for skills that don't have
explicit `uses_tools` declarations. It uses file extensions, keywords,
and tool patterns to infer skill attribution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillFeature:
    """Skill feature definition for inference.

    Attributes:
        skill_name: Name of the skill
        file_extensions: Associated file extensions (e.g., [".xlsx", ".xls"])
        keywords: Trigger keywords in user messages or tool inputs
        tools_hint: Tools likely used by this skill
        tool_patterns: Patterns for matching tool sequences
    """

    skill_name: str
    file_extensions: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    tools_hint: list[str] = field(default_factory=list)
    tool_patterns: list[list[str]] = field(default_factory=list)


# Built-in skill features for legacy skill support
BUILTIN_SKILL_FEATURES: dict[str, SkillFeature] = {
    "xlsx": SkillFeature(
        skill_name="xlsx",
        file_extensions=[".xlsx", ".xls", ".csv", ".tsv"],
        keywords=["excel", "spreadsheet", "表格", "工作表", "xlsx", "xls"],
        tools_hint=["execute_shell_command", "read_file", "write_file"],
        tool_patterns=[
            ["read_file", "execute_shell_command"],
            ["execute_shell_command", "write_file"],
        ],
    ),
    "pdf": SkillFeature(
        skill_name="pdf",
        file_extensions=[".pdf"],
        keywords=["pdf", "PDF", "PDF文档", "pdf文件"],
        tools_hint=["execute_shell_command", "read_file"],
        tool_patterns=[
            ["read_file", "execute_shell_command"],
        ],
    ),
    "docx": SkillFeature(
        skill_name="docx",
        file_extensions=[".docx", ".doc"],
        keywords=["word", "document", "文档", "docx", "doc"],
        tools_hint=["execute_shell_command", "read_file", "write_file"],
        tool_patterns=[
            ["read_file", "execute_shell_command"],
        ],
    ),
    "pptx": SkillFeature(
        skill_name="pptx",
        file_extensions=[".pptx", ".ppt"],
        keywords=["powerpoint", "presentation", "演示", "PPT", "pptx"],
        tools_hint=["execute_shell_command", "read_file"],
        tool_patterns=[
            ["read_file", "execute_shell_command"],
        ],
    ),
    "cron": SkillFeature(
        skill_name="cron",
        file_extensions=[],
        keywords=["cron", "定时", "周期", "scheduled", "recurring"],
        tools_hint=["execute_shell_command"],
        tool_patterns=[],
    ),
}


class SkillFeatureInferencer:
    """Skill feature inferencer for multi-layer attribution.

    Provides inference when skills don't have explicit `uses_tools` declarations.
    Uses file extensions, keywords, and tool patterns to determine attribution.

    Attribution confidence levels:
    - 1.0: Explicit declaration (handled by registry)
    - 0.8: File extension match
    - 0.6-0.7: Keyword match
    - 0.5: Tool hint match
    - 0.4: Tool sequence pattern match

    Example:
        inferencer = SkillFeatureInferencer()
        skill, confidence = inferencer.infer_skill_from_tool_input(
            "execute_shell_command",
            {"command": "python process.xlsx"},
            ["xlsx", "pdf"]
        )
        # Returns: ("xlsx", 0.8) due to .xlsx in command
    """

    def __init__(
        self,
        builtin_features: Optional[dict[str, SkillFeature]] = None,
    ) -> None:
        """Initialize the inferencer.

        Args:
            builtin_features: Optional override for built-in features.
                Uses BUILTIN_SKILL_FEATURES by default.
        """
        self._features = builtin_features or BUILTIN_SKILL_FEATURES

    def infer_skill_from_tool_input(
        self,
        tool_name: str,
        tool_input: dict,
        enabled_skills: list[str],
    ) -> tuple[Optional[str], float]:
        """Infer skill attribution from tool input.

        Examines tool input parameters for skill-specific features
        like file extensions or keywords.

        Args:
            tool_name: Name of the tool being called
            tool_input: Tool input parameters
            enabled_skills: List of currently enabled skills

        Returns:
            Tuple of (skill_name, confidence) or (None, 0.0)
        """
        # Convert tool input to searchable string
        input_str = str(tool_input).lower()

        best_skill = None
        best_confidence = 0.0

        for skill_name in enabled_skills:
            feature = self._features.get(skill_name)
            if not feature:
                continue

            # Check file extensions (highest confidence for inference)
            for ext in feature.file_extensions:
                if ext.lower() in input_str:
                    return skill_name, 0.8

            # Check keywords
            keyword_matches = sum(
                1 for kw in feature.keywords if kw.lower() in input_str
            )
            if keyword_matches > 0:
                # Scale confidence based on number of matches
                confidence = min(0.7, 0.4 + keyword_matches * 0.15)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_skill = skill_name

            # Check if tool is in hint list
            if tool_name in feature.tools_hint:
                confidence = 0.5
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_skill = skill_name

        return best_skill, best_confidence

    def infer_skill_from_tool_sequence(
        self,
        recent_tools: list[str],
        enabled_skills: list[str],
    ) -> tuple[Optional[str], float]:
        """Infer skill from tool call sequence pattern.

        Compares recent tool calls against predefined patterns
        to identify skill execution.

        Args:
            recent_tools: List of recently called tools (in order)
            enabled_skills: List of currently enabled skills

        Returns:
            Tuple of (skill_name, confidence) or (None, 0.0)
        """
        for skill_name in enabled_skills:
            feature = self._features.get(skill_name)
            if not feature:
                continue

            for pattern in feature.tool_patterns:
                if self._match_sequence(recent_tools, pattern):
                    return skill_name, 0.6

        return None, 0.0

    def _match_sequence(
        self,
        recent: list[str],
        pattern: list[str],
    ) -> bool:
        """Check if recent tools match a pattern.

        Args:
            recent: Recent tool calls
            pattern: Expected pattern

        Returns:
            True if pattern matches end of recent tools
        """
        if len(recent) < len(pattern):
            return False

        # Check if the last N tools match the pattern
        recent_slice = recent[-len(pattern) :]
        return recent_slice == pattern

    def get_skills_for_tool(
        self,
        tool_name: str,
        enabled_skills: list[str],
    ) -> list[tuple[str, float]]:
        """Get skills that might use this tool.

        Returns skills where the tool is in their hint list,
        sorted by likelihood.

        Args:
            tool_name: Name of the tool
            enabled_skills: List of enabled skills

        Returns:
            List of (skill_name, confidence) tuples, sorted by confidence
        """
        results = []

        for skill_name in enabled_skills:
            feature = self._features.get(skill_name)
            if not feature:
                continue

            if tool_name in feature.tools_hint:
                results.append((skill_name, 0.4))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def register_feature(self, feature: SkillFeature) -> None:
        """Register a custom skill feature.

        Args:
            feature: Skill feature to register
        """
        self._features[feature.skill_name] = feature
        logger.debug(
            "Registered feature for skill '%s': %d extensions, %d keywords",
            feature.skill_name,
            len(feature.file_extensions),
            len(feature.keywords),
        )

    def get_feature(self, skill_name: str) -> Optional[SkillFeature]:
        """Get feature definition for a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            SkillFeature if exists, None otherwise
        """
        return self._features.get(skill_name)


# Global instance
_skill_feature_inferencer: Optional[SkillFeatureInferencer] = None


def get_skill_feature_inferencer() -> SkillFeatureInferencer:
    """Get the global skill feature inferencer.

    Returns:
        SkillFeatureInferencer instance
    """
    global _skill_feature_inferencer
    if _skill_feature_inferencer is None:
        _skill_feature_inferencer = SkillFeatureInferencer()
    return _skill_feature_inferencer


def reset_skill_feature_inferencer() -> None:
    """Reset the global inferencer (for testing)."""
    global _skill_feature_inferencer
    _skill_feature_inferencer = None
