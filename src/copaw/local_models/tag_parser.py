# -*- coding: utf-8 -*-
"""Parse special tags from model-generated text.

Handles ``<think>...</think>`` (reasoning) and
``<tool_call>...</tool_call>`` (function calling) tags that local models
like Qwen3-Instruct embed in their raw text output.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

THINK_START = "<think>"
THINK_END = "</think>"

# Alternative control characters used by some Qwen models
# \x1b = ESC (U+001B), \x07 = BEL (U+0007)
CTRL_THINK_START = "\x1b"
CTRL_THINK_END = "\x07"

TOOL_CALL_START = "<tool_call>"
TOOL_CALL_END = "</tool_call>"

# Regex to find a complete <think>...</think> block (non-greedy).
_THINK_RE = re.compile(
    r"<think>(.*?)</think>",
    re.DOTALL,
)

# Regex for control character thinking tags (Qwen models)
_CTRL_THINK_RE = re.compile(
    r"\x1b(.*?)\x07",
    re.DOTALL,
)

# Regex to find complete <tool_call>...</tool_call> blocks (non-greedy).
_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>",
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TextWithThinking:
    """Result of extracting ``<think>`` tags from text."""

    # The thinking/reasoning content (between the tags).
    thinking: str = ""
    # The remaining text after removing the ``<think>...</think>`` block.
    remaining_text: str = ""
    # True when ``<think>`` has been opened but ``</think>`` not yet seen
    # (streaming scenario).
    has_open_tag: bool = False


@dataclass
class ParsedToolCall:
    """A single parsed tool call extracted from text."""

    id: str
    name: str
    arguments: dict
    raw_arguments: str


@dataclass
class TextWithToolCalls:
    """Result of parsing text that may contain tool-call tags."""

    # Text content before the first <tool_call> tag.
    text_before: str = ""
    # Text content after the last </tool_call> tag.
    text_after: str = ""
    # Successfully parsed tool calls.
    tool_calls: list[ParsedToolCall] = field(default_factory=list)
    # True when an opening <tool_call> has no matching </tool_call> yet
    # (streaming scenario).
    has_open_tag: bool = False
    # Raw text accumulated after the unclosed <tool_call> tag.
    partial_tool_text: str = ""


@dataclass
class StreamingTextSegment:
    """A single text segment emitted by incremental think-tag parsing."""

    kind: str
    text: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


def _parse_single_tool_call(raw_text: str) -> ParsedToolCall | None:
    """
    Parse the JSON content between a ``<tool_call>`` / ``</tool_call>`` pair.

    Expected format::

        {"name": "func_name", "arguments": {"key": "value"}}
    """
    try:
        data = json.loads(raw_text.strip())
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse tool call JSON: %s", raw_text[:200])
        return None

    name = data.get("name", "")
    if not name:
        logger.warning("Tool call missing 'name' field: %s", raw_text[:200])
        return None

    arguments = data.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            arguments = {}

    return ParsedToolCall(
        id=_generate_call_id(),
        name=name,
        arguments=arguments,
        raw_arguments=json.dumps(arguments, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def text_contains_think_tag(text: str) -> bool:
    """Fast substring check for a ``<think>`` tag or control character tag."""
    return THINK_START in text or CTRL_THINK_START in text


def extract_thinking_from_text(text: str) -> TextWithThinking:
    """Extract `` хро... хро`` or ``\\x1b...\\x07`` content from *text*.

    Returns a :class:`TextWithThinking` with:

    * ``thinking``       – the reasoning content (empty if none found)
    * ``remaining_text`` – everything outside the think tags
    * ``has_open_tag``   – ``True`` if the tag opened but not closed yet
    """
    # First try XML-style tags ( хро... хро)
    match = _THINK_RE.search(text)
    if match:
        thinking = match.group(1).strip()
        remaining = (text[: match.start()] + text[match.end() :]).strip()
        return TextWithThinking(
            thinking=thinking,
            remaining_text=remaining,
        )

    # Try control character tags (ESC...BEL, used by Qwen models)
    ctrl_match = _CTRL_THINK_RE.search(text)
    if ctrl_match:
        thinking = ctrl_match.group(1).strip()
        remaining = (text[: ctrl_match.start()] + text[ctrl_match.end() :]).strip()
        return TextWithThinking(
            thinking=thinking,
            remaining_text=remaining,
        )

    # No complete block — check for an unclosed tag
    # Check XML-style first
    open_idx = text.find(THINK_START)
    if open_idx != -1:
        remaining = text[:open_idx].strip()
        partial = text[open_idx + len(THINK_START) :]
        return TextWithThinking(
            thinking=partial.strip(),
            remaining_text=remaining,
            has_open_tag=True,
        )

    # Check control character style
    ctrl_open_idx = text.find(CTRL_THINK_START)
    if ctrl_open_idx != -1:
        remaining = text[:ctrl_open_idx].strip()
        partial = text[ctrl_open_idx + len(CTRL_THINK_START) :]
        return TextWithThinking(
            thinking=partial.strip(),
            remaining_text=remaining,
            has_open_tag=True,
        )

    # Some backends emit only a closing tag. Treat everything before the
    # first ``</think>`` as implicit thinking content.
    end_idx = text.find(THINK_END)
    if end_idx != -1:
        thinking = text[:end_idx].strip()
        remaining = text[end_idx + len(THINK_END) :].strip()
        return TextWithThinking(
            thinking=thinking,
            remaining_text=remaining,
        )

    return TextWithThinking(remaining_text=text)


def text_contains_tool_call_tag(text: str) -> bool:
    """Fast substring check for a ``<tool_call>`` tag."""
    return TOOL_CALL_START in text


class StreamingThinkParser:
    """Incrementally split raw text into ``text`` and ``thinking`` segments.

    Assumes ``<think>`` and ``</think>`` markers always arrive complete within
    a single chunk. The parser only tracks whether the current stream position
    is inside a thinking region and splits the current chunk accordingly.
    """

    def __init__(self) -> None:
        self._in_thinking = False
        self._trim_next_thinking_leading_newline = False
        self._is_first_chunk = True

    def feed(self, text: str) -> list[StreamingTextSegment]:
        """Consume a raw chunk and emit newly available segments."""
        if not text:
            return []
        if self._is_first_chunk:
            self._is_first_chunk = False
            if THINK_START not in text:
                text = THINK_START + text
        emitted: list[StreamingTextSegment] = []
        remaining = text

        while remaining:
            if not self._in_thinking:
                start_idx = remaining.find(THINK_START)
                end_idx = remaining.find(THINK_END)
                if end_idx != -1 and (start_idx == -1 or end_idx < start_idx):
                    thinking_text = remaining[:end_idx]
                    if self._trim_next_thinking_leading_newline:
                        thinking_text = thinking_text.lstrip("\n")
                        self._trim_next_thinking_leading_newline = False
                    if thinking_text:
                        emitted.append(
                            StreamingTextSegment(
                                kind="thinking",
                                text=thinking_text,
                            ),
                        )
                    remaining = remaining[end_idx + len(THINK_END) :]
                    continue

            marker = THINK_END if self._in_thinking else THINK_START
            idx = remaining.find(marker)

            if idx == -1:
                final_text = remaining
                if self._in_thinking and self._trim_next_thinking_leading_newline:
                    final_text = final_text.lstrip("\n")
                    self._trim_next_thinking_leading_newline = False
                if not final_text:
                    break
                emitted.append(
                    StreamingTextSegment(
                        kind="thinking" if self._in_thinking else "text",
                        text=final_text,
                    ),
                )
                break

            prefix = remaining[:idx]
            if prefix:
                if self._in_thinking and self._trim_next_thinking_leading_newline:
                    prefix = prefix.lstrip("\n")
                    self._trim_next_thinking_leading_newline = False
                if prefix:
                    emitted.append(
                        StreamingTextSegment(
                            kind="thinking" if self._in_thinking else "text",
                            text=prefix,
                        ),
                    )

            remaining = remaining[idx + len(marker) :]
            self._in_thinking = not self._in_thinking
            if self._in_thinking:
                self._trim_next_thinking_leading_newline = True

        if (
            emitted
            and emitted[-1].kind == "thinking"
            and self._trim_next_thinking_leading_newline
        ):
            emitted[-1].text = emitted[-1].text.lstrip("\n")
            self._trim_next_thinking_leading_newline = False
            if not emitted[-1].text:
                emitted.pop()

        return emitted

    def flush(self) -> list[StreamingTextSegment]:
        """Flush remaining buffered text at end-of-stream."""
        return []


def parse_tool_calls_from_text(text: str) -> TextWithToolCalls:
    """Extract all ``<tool_call>...</tool_call>`` blocks from *text*.

    Returns a :class:`TextWithToolCalls` with:

    * ``text_before`` – all text before the first ``<tool_call>`` tag
    * ``text_after``  – all text after the last ``</tool_call>`` tag
    * ``tool_calls``  – successfully parsed tool calls
    * ``has_open_tag`` – whether there is an unclosed ``<tool_call>``
        (streaming)
    * ``partial_tool_text`` – content after the unclosed tag
    """
    matches = list(_TOOL_CALL_RE.finditer(text))

    if not matches:
        # No complete blocks.  Check for an unclosed opening tag.
        open_idx = text.rfind(TOOL_CALL_START)
        if open_idx != -1:
            return TextWithToolCalls(
                text_before=text[:open_idx].rstrip(),
                has_open_tag=True,
                partial_tool_text=text[open_idx + len(TOOL_CALL_START) :],
            )
        return TextWithToolCalls(text_before=text)

    # --- Text before the first match ---
    text_before = text[: matches[0].start()].rstrip()

    # --- Text after the last match ---
    remaining = text[matches[-1].end() :]
    open_idx = remaining.find(TOOL_CALL_START)
    if open_idx != -1:
        text_after = remaining[:open_idx].strip()
        has_open_tag = True
        partial_tool_text = remaining[open_idx + len(TOOL_CALL_START) :]
    else:
        text_after = remaining.strip()
        has_open_tag = False
        partial_tool_text = ""

    # --- Parse each complete block ---
    tool_calls: list[ParsedToolCall] = []
    for match in matches:
        parsed = _parse_single_tool_call(match.group(1))
        if parsed is not None:
            tool_calls.append(parsed)

    return TextWithToolCalls(
        text_before=text_before,
        text_after=text_after,
        tool_calls=tool_calls,
        has_open_tag=has_open_tag,
        partial_tool_text=partial_tool_text,
    )
