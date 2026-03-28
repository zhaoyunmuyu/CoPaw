# -*- coding: utf-8 -*-
"""OpenAI chat model compatibility wrappers."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Type

from agentscope.model import OpenAIChatModel
from agentscope.model._model_response import ChatResponse
from agentscope.message import TextBlock, ThinkingBlock
from pydantic import BaseModel

from ..local_models.tag_parser import (
    StreamingThinkParser,
    extract_thinking_from_text,
    text_contains_think_tag,
)


def _clone_with_overrides(obj: Any, **overrides: Any) -> Any:
    """Clone a stream object into a mutable namespace with overrides."""
    data = dict(getattr(obj, "__dict__", {}))
    data.update(overrides)
    return SimpleNamespace(**data)


def _sanitize_tool_call(tool_call: Any) -> Any | None:
    """Normalize a tool call for parser safety, or drop it if unusable."""
    if not hasattr(tool_call, "index"):
        return None

    function = getattr(tool_call, "function", None)
    if function is None:
        return None

    has_name = hasattr(function, "name")
    has_arguments = hasattr(function, "arguments")

    raw_name = getattr(function, "name", "")
    if isinstance(raw_name, str):
        safe_name = raw_name
    elif raw_name is None:
        safe_name = ""
    else:
        safe_name = str(raw_name)

    raw_arguments = getattr(function, "arguments", "")
    if isinstance(raw_arguments, str):
        safe_arguments = raw_arguments
    elif raw_arguments is None:
        safe_arguments = ""
    else:
        try:
            safe_arguments = json.dumps(raw_arguments, ensure_ascii=False)
        except (TypeError, ValueError):
            safe_arguments = str(raw_arguments)

    if (
        has_name
        and has_arguments
        and isinstance(raw_name, str)
        and isinstance(
            raw_arguments,
            str,
        )
    ):
        return tool_call

    safe_function = SimpleNamespace(
        name=safe_name,
        arguments=safe_arguments,
    )
    return _clone_with_overrides(tool_call, function=safe_function)


def _sanitize_chunk(chunk: Any) -> Any:
    """Drop/normalize malformed tool-calls in a streaming chunk."""
    choices = getattr(chunk, "choices", None)
    if not choices:
        return chunk

    sanitized_choices: list[Any] = []
    changed = False

    for choice in choices:
        delta = getattr(choice, "delta", None)
        if delta is None:
            sanitized_choices.append(choice)
            continue

        raw_tool_calls = getattr(delta, "tool_calls", None)
        if not raw_tool_calls:
            sanitized_choices.append(choice)
            continue

        choice_changed = False
        sanitized_tool_calls: list[Any] = []
        for tool_call in raw_tool_calls:
            sanitized = _sanitize_tool_call(tool_call)
            if sanitized is not tool_call:
                choice_changed = True
            if sanitized is not None:
                sanitized_tool_calls.append(sanitized)

        if choice_changed:
            changed = True
            sanitized_delta = _clone_with_overrides(
                delta,
                tool_calls=sanitized_tool_calls,
            )
            sanitized_choice = _clone_with_overrides(
                choice,
                delta=sanitized_delta,
            )
            sanitized_choices.append(sanitized_choice)
            continue

        sanitized_choices.append(choice)

    if not changed:
        return chunk
    return _clone_with_overrides(chunk, choices=sanitized_choices)


def _sanitize_stream_item(item: Any) -> Any:
    """Sanitize either plain stream chunks or structured stream items."""
    if hasattr(item, "chunk"):
        chunk = item.chunk
        sanitized_chunk = _sanitize_chunk(chunk)
        if sanitized_chunk is chunk:
            return item
        return _clone_with_overrides(item, chunk=sanitized_chunk)

    return _sanitize_chunk(item)


def _clone_choice_with_delta(choice: Any, delta: Any) -> Any:
    """Clone a choice object while replacing its delta."""
    return _clone_with_overrides(choice, delta=delta)


def _clone_chunk_with_choices(chunk: Any, choices: list[Any]) -> Any:
    """Clone a chunk object while replacing its choices."""
    return _clone_with_overrides(chunk, choices=choices)


def _split_thinking_blocks(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw ``<think>...</think>`` text into dedicated thinking blocks.

    Some OpenAI-compatible backends place reasoning inside plain text instead
    of the structured ``reasoning_content`` field. This post-processes parsed
    content so downstream runtime/UI receives a normal ``thinking`` block.
    """
    has_structured_thinking = any(
        block.get("type") == "thinking" for block in content
    )

    normalized: list[dict[str, Any]] = []
    for block in content:
        if block.get("type") != "text":
            normalized.append(block)
            continue

        text = block.get("text", "")
        if not text or not text_contains_think_tag(text):
            normalized.append(block)
            continue

        parsed = extract_thinking_from_text(text)
        if parsed.thinking and not has_structured_thinking:
            normalized.append(
                ThinkingBlock(type="thinking", thinking=parsed.thinking),
            )
        if parsed.remaining_text:
            normalized.append(
                TextBlock(type="text", text=parsed.remaining_text),
            )

    return normalized


def _expand_text_delta_segments(
    *,
    item: Any,
    parser: StreamingThinkParser,
) -> list[Any]:
    """Rewrite mixed ``delta.content`` chunks into separate text/reasoning chunks."""
    chunk = getattr(item, "chunk", item)
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return [item]

    choice = choices[0]
    delta = getattr(choice, "delta", None)
    if delta is None:
        return [item]

    content_piece = getattr(delta, "content", None) or ""
    reasoning_piece = getattr(delta, "reasoning_content", None) or ""

    if not content_piece:
        return [item]

    segments = parser.feed(content_piece)
    emitted_items: list[Any] = []

    if reasoning_piece:
        reasoning_delta = _clone_with_overrides(
            delta,
            content="",
            reasoning_content=reasoning_piece,
        )
        reasoning_choice = _clone_choice_with_delta(choice, reasoning_delta)
        reasoning_chunk = _clone_chunk_with_choices(chunk, [reasoning_choice])
        emitted_items.append(
            _clone_with_overrides(item, chunk=reasoning_chunk)
            if hasattr(item, "chunk")
            else reasoning_chunk,
        )

    if not segments:
        return emitted_items

    for segment in segments:
        if not segment.text:
            continue
        segment_delta = _clone_with_overrides(
            delta,
            content=segment.text if segment.kind == "text" else "",
            reasoning_content=(
                segment.text if segment.kind == "thinking" else ""
            ),
        )
        segment_choice = _clone_choice_with_delta(choice, segment_delta)
        segment_chunk = _clone_chunk_with_choices(chunk, [segment_choice])
        emitted_items.append(
            _clone_with_overrides(item, chunk=segment_chunk)
            if hasattr(item, "chunk")
            else segment_chunk,
        )

    return emitted_items or [item]


class _SanitizedStream:
    """Proxy OpenAI async stream that sanitizes each emitted item and
    captures ``extra_content`` from tool-call chunks (used by Gemini
    thinking models to carry ``thought_signature``)."""

    def __init__(self, stream: Any):
        self._stream = stream
        self._ctx_stream: Any | None = None
        self.extra_contents: dict[str, Any] = {}
        self._think_parser = StreamingThinkParser()
        self._pending_items: list[Any] = []

    async def __aenter__(self) -> "_SanitizedStream":
        self._ctx_stream = await self._stream.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc: Any,
        tb: Any,
    ) -> bool | None:
        return await self._stream.__aexit__(exc_type, exc, tb)

    def __aiter__(self) -> "_SanitizedStream":
        return self

    async def __anext__(self) -> Any:
        while True:
            if self._pending_items:
                return self._pending_items.pop(0)

            if self._ctx_stream is None:
                raise StopAsyncIteration
            item = await self._ctx_stream.__anext__()
            sanitized_item = _sanitize_stream_item(item)
            self._capture_extra_content(sanitized_item)

            expanded_items = _expand_text_delta_segments(
                item=sanitized_item,
                parser=self._think_parser,
            )
            if not expanded_items:
                continue
            if len(expanded_items) > 1:
                self._pending_items.extend(expanded_items[1:])
            return expanded_items[0]

    def _capture_extra_content(self, item: Any) -> None:
        """Store ``extra_content`` keyed by tool-call id."""
        chunk = getattr(item, "chunk", item)
        for choice in getattr(chunk, "choices", []):
            delta = getattr(choice, "delta", None)
            if not delta:
                continue
            for tc in getattr(delta, "tool_calls", None) or []:
                tc_id = getattr(tc, "id", None)
                if not tc_id:
                    continue
                extra = getattr(tc, "extra_content", None)
                if extra is None:
                    model_extra = getattr(tc, "model_extra", None)
                    if isinstance(model_extra, dict):
                        extra = model_extra.get("extra_content")
                if extra:
                    self.extra_contents[tc_id] = extra


class OpenAIChatModelCompat(OpenAIChatModel):
    """OpenAIChatModel with robust parsing for malformed tool-call chunks
    and transparent ``extra_content`` (Gemini thought_signature) relay."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_usage = None  # Store last response usage for tracing

    def _parse_openai_completion_response(
        self,
        start_datetime: datetime,
        response: Any,
        structured_model: Type[BaseModel] | None = None,
    ) -> ChatResponse:
        """Parse non-streaming response and store usage for tracing."""
        parsed = super()._parse_openai_completion_response(
            start_datetime=start_datetime,
            response=response,
            structured_model=structured_model,
        )
        # Store usage for tracing
        if parsed.usage:
            self._last_usage = parsed.usage
        return parsed

    async def _parse_openai_stream_response(
        self,
        start_datetime: datetime,
        response: Any,
        structured_model: Type[BaseModel] | None = None,
    ) -> AsyncGenerator[ChatResponse, None]:
        sanitized_response = _SanitizedStream(response)
        async for parsed in super()._parse_openai_stream_response(
            start_datetime=start_datetime,
            response=sanitized_response,
            structured_model=structured_model,
        ):
            # Store usage from the last chunk for tracing
            if parsed.usage:
                self._last_usage = parsed.usage
            parsed.content = _split_thinking_blocks(parsed.content)
            if sanitized_response.extra_contents:
                for block in parsed.content:
                    if block.get("type") != "tool_use":
                        continue
                    tool_id = block.get("id")
                    if not isinstance(tool_id, str):
                        continue
                    ec = sanitized_response.extra_contents.get(tool_id)
                    if ec:
                        block["extra_content"] = ec
            yield parsed
