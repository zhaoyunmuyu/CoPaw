# -*- coding: utf-8 -*-
"""Skill feature extractor for parsing SKILL.md files.

This module extracts skill features from SKILL.md during skill loading,
supporting both explicit declarations and automatic inference.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import frontmatter

from .utils.file_handling import read_text_file_with_encoding_fallback

logger = logging.getLogger(__name__)


# 文件扩展名正则模式（支持完整文件名和裸扩展名）
_FILE_EXTENSION_PATTERN = re.compile(
    r"(?<!\w)(?:[a-zA-Z0-9_-]+)?\.([a-zA-Z0-9]{1,4})(?!\w)",
)

# MCP server 模式（常见格式）
_MCP_SERVER_PATTERN = re.compile(
    r"(?:mcp[_-]?server|MCP[_-]?Server|server[_-]?name|"
    r'mcpServer|server_name)[\s:=]+["\']?([a-zA-Z0-9_-]+)["\']?',
    re.IGNORECASE,
)

# 触发关键词段落标题模式
_TRIGGER_KEYWORDS_HEADER_PATTERN = re.compile(
    r"^##\s*触发关键词|^##\s*Trigger\s*Keywords|^##\s*Keywords|^##\s*关键词",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class ExtractedSkillFeatures:
    """Features extracted from a SKILL.md file.

    Attributes:
        trigger_keywords: Keywords from explicit '## 触发关键词' section
        description_keywords: Keywords auto-extracted from description
        file_extensions: File extensions found in content
        mcp_servers: MCP server names found in content
        uses_tools: Tools declared in metadata
        is_conversational: Whether this is a conversational Q&A skill
        source: Feature extraction source identifier
    """

    trigger_keywords: list[str] = field(default_factory=list)
    description_keywords: list[str] = field(default_factory=list)
    file_extensions: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    uses_tools: list[str] = field(default_factory=list)
    is_conversational: bool = False
    source: str = "extracted"


class SkillFeatureExtractor:
    """Extract skill features from SKILL.md content.

    Features are extracted once during skill loading and cached for
    runtime use. Supports both explicit declarations and automatic
    inference.

    Extraction sources:
    1. Frontmatter metadata (uses_tools, etc.)
    2. Description text (automatic keyword extraction)
    3. Body content sections (trigger_keywords, etc.)
    4. File path patterns in content

    Example:
        extractor = SkillFeatureExtractor()
        features = extractor.extract_from_content(skill_md_content)
        # features.trigger_keywords = ["黄金", "金价", ...]
        # features.file_extensions = [".xlsx", ".pdf"]
    """

    # 中文停用词
    _STOP_WORDS_CN = frozenset(
        {
            "的",
            "了",
            "是",
            "在",
            "和",
            "与",
            "或",
            "当",
            "等",
            "这",
            "那",
            "有",
            "也",
            "就",
            "都",
            "而",
            "及",
            "着",
            "如果",
            "但是",
            "可以",
            "这个",
            "那个",
            "什么",
            "怎么",
            "如何",
            "为什么",
            "因为",
            "所以",
            "然后",
            "或者",
            "以及",
            "不是",
            "没有",
            "一个",
            "一些",
            "这些",
            "那些",
            "其他",
            "另外",
            "对于",
            "关于",
            "通过",
            "使用",
            "进行",
            "实现",
            "需要",
            "应该",
            "可能",
            "能够",
            "已经",
        },
    )

    # 英文停用词
    _STOP_WORDS_EN = frozenset(
        {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "and",
            "but",
            "if",
            "or",
            "because",
            "until",
            "while",
            "although",
            "though",
            "this",
            "that",
            "these",
            "those",
            "use",
            "using",
            "used",
            "user",
            "users",
            "file",
            "files",
            "skill",
            "skills",
        },
    )

    def __init__(
        self,
        min_keyword_length: int = 2,
        max_keywords: int = 20,
    ) -> None:
        """Initialize the extractor.

        Args:
            min_keyword_length: Minimum length for extracted keywords
            max_keywords: Maximum number of keywords to keep per source
        """
        self._min_keyword_length = min_keyword_length
        self._max_keywords = max_keywords

    def extract_from_skill_md(
        self,
        skill_dir: Path,
        skill_name: str,
    ) -> ExtractedSkillFeatures:
        """Extract features from a skill directory's SKILL.md.

        Args:
            skill_dir: Path to the skill directory
            skill_name: Name of the skill for logging

        Returns:
            ExtractedSkillFeatures with all extracted features
        """
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            logger.debug("SKILL.md not found for skill '%s'", skill_name)
            return ExtractedSkillFeatures()

        try:
            content = read_text_file_with_encoding_fallback(skill_md_path)
            return self.extract_from_content(content, skill_name)
        except Exception as e:
            logger.warning(
                "Failed to extract features for skill '%s': %s",
                skill_name,
                e,
            )
            return ExtractedSkillFeatures()

    def extract_from_content(
        self,
        content: str,
        skill_name: str = "",
    ) -> ExtractedSkillFeatures:
        """Extract features from SKILL.md content.

        Args:
            content: SKILL.md file content
            skill_name: Optional skill name for logging

        Returns:
            ExtractedSkillFeatures with all extracted features
        """
        features = ExtractedSkillFeatures()

        # Parse frontmatter
        try:
            post = frontmatter.loads(content)
            description = str(post.get("description", "") or "")
            metadata = post.get("metadata") or {}

            # Extract uses_tools from metadata (existing logic)
            features.uses_tools = self._extract_uses_tools(metadata)

            # Extract description keywords
            features.description_keywords = self._extract_description_keywords(
                description,
            )

        except Exception as e:
            logger.debug(
                "Failed to parse frontmatter for '%s': %s",
                skill_name,
                e,
            )
            description = ""

        # Parse body content (after frontmatter)
        body_content = self._get_body_content(content)

        # Extract trigger keywords from explicit section
        features.trigger_keywords = self._extract_trigger_keywords_section(
            body_content,
        )

        # Extract file extensions from body
        features.file_extensions = self._extract_file_extensions(body_content)

        # Extract MCP server references
        features.mcp_servers = self._extract_mcp_servers(body_content)

        # Determine if conversational skill
        features.is_conversational = self._determine_conversational(features)

        logger.debug(
            "Extracted features for '%s': %d trigger_kw, %d desc_kw, "
            "%d ext, %d mcp, conversational=%s",
            skill_name,
            len(features.trigger_keywords),
            len(features.description_keywords),
            len(features.file_extensions),
            len(features.mcp_servers),
            features.is_conversational,
        )

        return features

    def _get_body_content(self, content: str) -> str:
        """Get body content after frontmatter.

        Args:
            content: Full SKILL.md content

        Returns:
            Body content without frontmatter
        """
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
        return content

    def _extract_uses_tools(self, metadata: dict[str, Any]) -> list[str]:
        """Extract uses_tools from metadata.

        Args:
            metadata: Parsed frontmatter metadata

        Returns:
            List of tool names
        """
        # Check swe namespace
        swe_meta = metadata.get("swe", {})
        if isinstance(swe_meta, dict):
            uses_tools = swe_meta.get("uses_tools", [])
            if isinstance(uses_tools, list):
                return [str(t) for t in uses_tools if t]

        # Fallback: check top-level metadata
        uses_tools = metadata.get("uses_tools", [])
        if isinstance(uses_tools, list):
            return [str(t) for t in uses_tools if t]

        return []

    def _extract_description_keywords(
        self,
        description: str,
    ) -> list[str]:
        """Extract keywords from description using simple tokenization.

        Supports both Chinese and English keywords.

        Args:
            description: Skill description text

        Returns:
            List of extracted keywords
        """
        if not description:
            return []

        keywords: set[str] = set()

        # Chinese word extraction
        # Simple approach: extract 2-4 character Chinese phrases
        cn_segments = re.findall(r"[\u4e00-\u9fff]+", description)
        for segment in cn_segments:
            for length in range(2, min(5, len(segment) + 1)):
                for i in range(len(segment) - length + 1):
                    phrase = segment[i : i + length]
                    if phrase not in self._STOP_WORDS_CN:
                        keywords.add(phrase)

        # English word extraction
        en_words = re.findall(r"\b[a-zA-Z]+\b", description)
        for word in en_words:
            word_lower = word.lower()
            if (
                word_lower not in self._STOP_WORDS_EN
                and len(word_lower) >= self._min_keyword_length
            ):
                keywords.add(word_lower)

        # Limit and sort (prefer longer keywords)
        sorted_keywords = sorted(
            keywords,
            key=lambda k: (-len(k), k),
        )
        return sorted_keywords[: self._max_keywords]

    def _extract_trigger_keywords_section(
        self,
        body_content: str,
    ) -> list[str]:
        """Extract keywords from explicit '## 触发关键词' section.

        Format:
            ## 触发关键词

            - 关键词1、关键词2、关键词3
            - 关键词4

        Args:
            body_content: Body content after frontmatter

        Returns:
            List of trigger keywords
        """
        keywords: list[str] = []

        # Find trigger keywords section
        match = _TRIGGER_KEYWORDS_HEADER_PATTERN.search(body_content)
        if not match:
            return keywords

        # Get content after header until next header or end
        start_pos = match.end()
        next_header = re.search(
            r"^##\s",
            body_content[start_pos:],
            re.MULTILINE,
        )
        if next_header:
            end_pos = start_pos + next_header.start()
        else:
            end_pos = len(body_content)

        section_content = body_content[start_pos:end_pos].strip()

        # Extract keywords from bullet points
        lines = section_content.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Handle bullet points
            if line.startswith("-") or line.startswith("*"):
                line = line.lstrip("-*").strip()

            # Split by common separators
            # Chinese comma, English comma, semicolon,顿号
            parts = re.split(r"[，,；;、]+", line)
            for part in parts:
                part = part.strip()
                if part and len(part) >= self._min_keyword_length:
                    keywords.append(part)

        return keywords

    def _extract_file_extensions(
        self,
        body_content: str,
    ) -> list[str]:
        """Extract file extensions from content patterns.

        Args:
            body_content: Body content after frontmatter

        Returns:
            List of file extensions (with dot)
        """
        extensions: set[str] = set()

        matches = _FILE_EXTENSION_PATTERN.findall(body_content)
        for ext_part in matches:
            # ext_part is the extension part without the dot
            ext = "." + ext_part.lower()
            # Filter valid extensions (typically 1-4 chars)
            if 1 <= len(ext) <= 5:
                extensions.add(ext)

        return sorted(extensions)

    def _extract_mcp_servers(
        self,
        body_content: str,
    ) -> list[str]:
        """Extract MCP server names from content.

        Looks for patterns like:
        - mcp_server: filesystem
        - server_name: "github"
        - MCPServer = 'slack'

        Args:
            body_content: Body content after frontmatter

        Returns:
            List of MCP server names
        """
        servers: set[str] = set()

        matches = _MCP_SERVER_PATTERN.findall(body_content)
        for server in matches:
            server = server.strip()
            if server:
                servers.add(server.lower())

        return sorted(servers)

    def _determine_conversational(
        self,
        features: ExtractedSkillFeatures,
    ) -> bool:
        """Determine if this is a conversational Q&A skill.

        A skill is considered conversational if:
        - Has trigger keywords (explicit)
        - Has description keywords
        - No file extensions (not a file processing skill)

        Args:
            features: Extracted features

        Returns:
            True if conversational skill
        """
        # Has explicit trigger keywords
        if features.trigger_keywords:
            return True

        # Has description keywords but no file extensions or MCP
        if (
            features.description_keywords
            and not features.file_extensions
            and not features.mcp_servers
            and not features.uses_tools
        ):
            return True

        return False

    def build_skill_feature(
        self,
        skill_name: str,
        extracted: ExtractedSkillFeatures,
        existing_feature: Optional[Any] = None,
    ) -> Any:
        """Build SkillFeature from extracted features.

        Merges extracted features with existing feature if provided.
        Explicit trigger_keywords override description_keywords.

        Args:
            skill_name: Skill name
            extracted: Extracted features
            existing_feature: Existing feature to merge (for builtins)

        Returns:
            Complete SkillFeature for registration
        """
        from .skill_feature_inferencer import SkillFeature

        # Use extracted trigger_keywords if available, else description_keywords
        keywords = extracted.trigger_keywords or extracted.description_keywords

        # If existing feature, merge with it
        if existing_feature is not None:
            merged_extensions = list(
                set(getattr(existing_feature, "file_extensions", []) or [])
                | set(extracted.file_extensions),
            )
            merged_keywords = list(
                set(getattr(existing_feature, "keywords", []) or [])
                | set(keywords),
            )
            merged_tools_hint = list(
                set(getattr(existing_feature, "tools_hint", []) or [])
                | set(extracted.uses_tools),
            )
            merged_mcp = list(
                set(
                    getattr(existing_feature, "mcp_servers", []) or [],
                )
                | set(extracted.mcp_servers),
            )

            return SkillFeature(
                skill_name=skill_name,
                file_extensions=merged_extensions,
                keywords=merged_keywords,
                tools_hint=merged_tools_hint,
                tool_patterns=getattr(existing_feature, "tool_patterns", [])
                or [],
                trigger_keywords=extracted.trigger_keywords,
                description_keywords=extracted.description_keywords,
                mcp_servers=merged_mcp,
                is_conversational=extracted.is_conversational,
            )

        return SkillFeature(
            skill_name=skill_name,
            file_extensions=extracted.file_extensions,
            keywords=keywords,
            tools_hint=extracted.uses_tools,
            tool_patterns=[],
            trigger_keywords=extracted.trigger_keywords,
            description_keywords=extracted.description_keywords,
            mcp_servers=extracted.mcp_servers,
            is_conversational=extracted.is_conversational,
        )


# Global extractor instance
_skill_feature_extractor: Optional[SkillFeatureExtractor] = None


def get_skill_feature_extractor() -> SkillFeatureExtractor:
    """Get the global skill feature extractor.

    Returns:
        SkillFeatureExtractor instance
    """
    global _skill_feature_extractor
    if _skill_feature_extractor is None:
        _skill_feature_extractor = SkillFeatureExtractor()
    return _skill_feature_extractor


def reset_skill_feature_extractor() -> None:
    """Reset the global extractor (for testing)."""
    global _skill_feature_extractor
    _skill_feature_extractor = None
