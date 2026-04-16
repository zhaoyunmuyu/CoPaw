# -*- coding: utf-8 -*-
"""Helpers for normalizing stream boundary events."""

from __future__ import annotations

import copy
import logging
from typing import AsyncGenerator, AsyncIterator, Iterable

from agentscope_runtime.engine.schemas.agent_schemas import (
    ContentType,
    Event,
    Message,
    MessageType,
    RunStatus,
)

from ...agents.utils.tool_summary import (
    async_generate_tool_call_summary,
    async_generate_tool_output_summary,
    generate_tool_call_summary,
    generate_tool_output_summary,
)


logger = logging.getLogger(__name__)


def _is_empty_reasoning_boundary_message(event: Event) -> bool:
    """Return True when *event* is the empty assistant-message boundary."""
    if not isinstance(event, Message):
        return False
    if event.object != "message" or event.type != MessageType.MESSAGE:
        return False
    if event.status != RunStatus.InProgress:
        return False
    return not event.content


def _normalize_reasoning_boundary_events(
    events: Iterable[Event],
):
    """Replace empty assistant boundaries with reasoning completed events."""
    current_reasoning: Message | None = None

    for event in events:
        if isinstance(event, Message):
            if (
                event.object == "message"
                and event.type == MessageType.REASONING
                and event.status == RunStatus.InProgress
            ):
                current_reasoning = event
                yield event
                continue

            if (
                current_reasoning is not None
                and event.object == "message"
                and event.type == MessageType.REASONING
                and event.id == current_reasoning.id
                and event.status != RunStatus.InProgress
            ):
                current_reasoning = None
                yield event
                continue

            if (
                current_reasoning is not None
                and _is_empty_reasoning_boundary_message(event)
            ):
                completed_reasoning = copy.deepcopy(current_reasoning)
                completed_reasoning.completed()
                current_reasoning = None
                yield completed_reasoning
                yield event
                continue

        yield event


async def _enrich_tool_message(event: Message) -> None:
    """Attach summaries to tool events."""
    contents = event.content or []

    if event.type in (
        MessageType.FUNCTION_CALL,
        MessageType.PLUGIN_CALL,
        MessageType.MCP_TOOL_CALL,
    ):
        for content in contents:
            if getattr(content, "type", None) != ContentType.DATA:
                continue
            data = getattr(content, "data", None) or {}
            tool_name = data.get("name", "")
            arguments = data.get("arguments", "{}")
            server_label = data.get("server_label")
            try:
                data["summary"] = await async_generate_tool_call_summary(
                    tool_name=tool_name,
                    arguments=arguments,
                    server_label=server_label,
                )
            except Exception as exc:
                logger.debug(
                    "Failed to generate async tool call summary: %s",
                    exc,
                )
                try:
                    data["summary"] = generate_tool_call_summary(
                        tool_name=tool_name,
                        arguments=arguments,
                        server_label=server_label,
                    )
                except Exception as sync_exc:
                    logger.debug(
                        "Failed to generate tool call summary: %s",
                        sync_exc,
                    )

    elif event.type in (
        MessageType.FUNCTION_CALL_OUTPUT,
        MessageType.PLUGIN_CALL_OUTPUT,
        MessageType.MCP_TOOL_CALL_OUTPUT,
    ):
        for content in contents:
            if getattr(content, "type", None) != ContentType.DATA:
                continue
            data = getattr(content, "data", None) or {}
            tool_name = data.get("name", "")
            output = data.get("output", "")
            arguments = data.get("arguments")
            try:
                data["output_summary"] = await async_generate_tool_output_summary(
                    tool_name=tool_name,
                    output=output,
                    arguments=arguments,
                )
            except Exception as exc:
                logger.debug(
                    "Failed to generate async tool output summary: %s",
                    exc,
                )
                try:
                    data["output_summary"] = generate_tool_output_summary(
                        tool_name=tool_name,
                        output=output,
                    )
                except Exception as sync_exc:
                    logger.debug(
                        "Failed to generate tool output summary: %s",
                        sync_exc,
                    )


async def normalize_reasoning_boundary_stream(
    source_stream: AsyncIterator[Event],
) -> AsyncGenerator[Event, None]:
    """Async wrapper for reasoning boundary normalization."""
    current_reasoning: Message | None = None

    async for event in source_stream:
        if isinstance(event, Message):
            if (
                event.object == "message"
                and event.type == MessageType.REASONING
                and event.status == RunStatus.InProgress
            ):
                current_reasoning = event
                yield event
                continue

            if (
                current_reasoning is not None
                and event.object == "message"
                and event.type == MessageType.REASONING
                and event.id == current_reasoning.id
                and event.status != RunStatus.InProgress
            ):
                current_reasoning = None
                yield event
                continue

            if (
                current_reasoning is not None
                and _is_empty_reasoning_boundary_message(event)
            ):
                completed_reasoning = copy.deepcopy(current_reasoning)
                completed_reasoning.completed()
                current_reasoning = None
                yield completed_reasoning
                yield event
                continue

        if isinstance(event, Message):
            await _enrich_tool_message(event)

        yield event
