# -*- coding: utf-8 -*-
"""Skill-Tool registry for tracking tool ownership declarations.

This module provides a registry service that maps skills to their declared
tools, enabling multi-skill attribution for tool calls during tracing.
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Any, Optional

import frontmatter

from .utils.file_handling import read_text_file_with_encoding_fallback

logger = logging.getLogger(__name__)


class SkillToolRegistry:
    """Registry maintaining skill -> tools mappings.

    This registry:
    1. Reads `uses_tools` declarations from SKILL.md frontmatter
    2. Builds forward mapping: skill_name -> [tool_names]
    3. Builds reverse mapping: tool_name -> [skill_names]
    4. Supports wildcard patterns (e.g., "browser_*")
    5. Calculates attribution weights for multi-skill scenarios

    Example:
        registry = SkillToolRegistry()
        registry.register_skill_tools("pdf", ["read_file", "execute_shell_command"])
        registry.register_skill_tools("docx", ["read_file", "write_file"])

        # Query which skills claim a tool
        skills = registry.get_skills_for_tool("read_file")
        # Returns: ["docx", "pdf"]

        # Calculate weights for multi-skill attribution
        weights = registry.calculate_weights(skills)
        # Returns: {"docx": 0.5, "pdf": 0.5}
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._skill_to_tools: dict[str, list[str]] = {}
        self._tool_to_skills: dict[str, list[str]] = {}
        self._tool_patterns: list[
            tuple[str, str]
        ] = []  # (pattern, skill_name)

    def register_skill_tools(
        self,
        skill_name: str,
        tools: list[str],
    ) -> None:
        """Register tools declared by a skill.

        Args:
            skill_name: Skill identifier
            tools: List of tool names or patterns (e.g., "browser_*")
        """
        if not tools:
            return

        self._skill_to_tools[skill_name] = list(tools)

        for tool in tools:
            if "*" in tool:
                # Wildcard pattern
                self._tool_patterns.append((tool, skill_name))
            else:
                # Exact match
                if tool not in self._tool_to_skills:
                    self._tool_to_skills[tool] = []
                if skill_name not in self._tool_to_skills[tool]:
                    self._tool_to_skills[tool].append(skill_name)

        logger.debug(
            "Registered %d tools for skill '%s': %s",
            len(tools),
            skill_name,
            tools,
        )

    def get_skills_for_tool(self, tool_name: str) -> list[str]:
        """Get all skills that declare using this tool.

        Args:
            tool_name: Tool name to look up

        Returns:
            Sorted list of skill names claiming ownership
        """
        skills: set[str] = set()

        # Exact matches
        if tool_name in self._tool_to_skills:
            skills.update(self._tool_to_skills[tool_name])

        # Pattern matches
        for pattern, skill_name in self._tool_patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                skills.add(skill_name)

        return sorted(skills)

    def calculate_weights(
        self,
        skill_names: list[str],
    ) -> dict[str, float]:
        """Calculate attribution weights for multiple skills.

        Strategy: Equal distribution (1/N each).
        When a tool is claimed by multiple skills, each gets equal weight.

        Args:
            skill_names: List of skills claiming the tool

        Returns:
            Dict mapping skill_name -> weight (sum = 1.0)
        """
        if not skill_names:
            return {}

        if len(skill_names) == 1:
            return {skill_names[0]: 1.0}

        weight = 1.0 / len(skill_names)
        return {name: weight for name in skill_names}

    def get_tools_for_skill(self, skill_name: str) -> list[str]:
        """Get tools declared by a specific skill.

        Args:
            skill_name: Skill identifier

        Returns:
            List of tool names declared by the skill
        """
        return list(self._skill_to_tools.get(skill_name, []))

    def clear(self) -> None:
        """Clear all registrations."""
        self._skill_to_tools.clear()
        self._tool_to_skills.clear()
        self._tool_patterns.clear()

    @property
    def skill_count(self) -> int:
        """Number of registered skills."""
        return len(self._skill_to_tools)

    @property
    def tool_count(self) -> int:
        """Number of unique tools with skill claims."""
        return len(self._tool_to_skills)


# Global registry instance
_skill_tool_registry: Optional[SkillToolRegistry] = None


def get_skill_tool_registry() -> SkillToolRegistry:
    """Get the global skill-tool registry.

    Returns:
        SkillToolRegistry instance (creates new if not exists)
    """
    global _skill_tool_registry
    if _skill_tool_registry is None:
        _skill_tool_registry = SkillToolRegistry()
    return _skill_tool_registry


def reset_skill_tool_registry() -> None:
    """Reset the global registry (for testing)."""
    global _skill_tool_registry
    if _skill_tool_registry is not None:
        _skill_tool_registry.clear()
    _skill_tool_registry = None


def build_skill_tool_registry(
    workspace_dir: Path,
    enabled_skills: list[str],
) -> SkillToolRegistry:
    """Build skill-tool registry from enabled workspace skills.

    This function reads SKILL.md files for each enabled skill and extracts:
    1. The `uses_tools` declaration from the frontmatter metadata
    2. Skill features (trigger keywords, file extensions, MCP servers, etc.)

    Args:
        workspace_dir: Workspace directory containing skills
        enabled_skills: List of enabled skill names

    Returns:
        Populated SkillToolRegistry
    """
    from .skill_feature_extractor import get_skill_feature_extractor
    from .skill_feature_inferencer import get_skill_feature_inferencer
    from .skills_manager import get_workspace_skills_dir

    registry = get_skill_tool_registry()
    registry.clear()

    skills_dir = get_workspace_skills_dir(workspace_dir)
    extractor = get_skill_feature_extractor()
    inferencer = get_skill_feature_inferencer()

    processed_skills = 0
    for skill_name in enabled_skills:
        skill_dir = skills_dir / skill_name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            content = read_text_file_with_encoding_fallback(skill_md)
            post = frontmatter.loads(content)

            # Extract uses_tools from metadata
            uses_tools = _extract_uses_tools(post)

            if uses_tools:
                registry.register_skill_tools(skill_name, uses_tools)
                logger.debug(
                    "Skill '%s' declares %d tools: %s",
                    skill_name,
                    len(uses_tools),
                    uses_tools,
                )

            # Extract skill features for inference
            features = extractor.extract_from_content(content, skill_name)

            # Build and register SkillFeature
            existing_feature = inferencer.get_feature(skill_name)
            skill_feature = extractor.build_skill_feature(
                skill_name,
                features,
                existing_feature,
            )
            inferencer.register_feature(skill_feature)

            logger.debug(
                "Registered feature for skill '%s': %d keywords, %d extensions, "
                "%d mcp_servers, conversational=%s",
                skill_name,
                len(skill_feature.keywords),
                len(skill_feature.file_extensions),
                len(skill_feature.mcp_servers),
                skill_feature.is_conversational,
            )
            processed_skills += 1

        except Exception as e:
            logger.debug(
                "Failed to parse skill '%s': %s",
                skill_name,
                e,
            )

    logger.info(
        "Built skill-tool registry: %d/%d skills processed, %d with explicit tool declarations",
        processed_skills,
        len(enabled_skills),
        registry.skill_count,
    )

    return registry


def _extract_uses_tools(post: Any) -> list[str]:
    """Extract uses_tools declaration from frontmatter.

    Args:
        post: Parsed frontmatter object

    Returns:
        List of tool names
    """
    metadata = post.get("metadata") or {}

    # Check swe namespace
    swe_meta = metadata.get("swe", {})
    if isinstance(swe_meta, dict):
        uses_tools = swe_meta.get("uses_tools", [])
        if isinstance(uses_tools, list) and uses_tools:
            # Validate all items are strings
            return [str(t) for t in uses_tools if t]

    # Fallback: check top-level metadata
    uses_tools = metadata.get("uses_tools", [])
    if isinstance(uses_tools, list):
        return [str(t) for t in uses_tools if t]

    return []
