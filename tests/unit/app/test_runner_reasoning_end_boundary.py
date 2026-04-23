# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

import pytest
from agentscope_runtime.engine.schemas.agent_schemas import (
    DataContent,
    Message,
    MessageType,
    Role,
    RunStatus,
    TextContent,
)

from swe.app.runner.stream_boundary import (
    _normalize_reasoning_boundary_events,
    normalize_reasoning_boundary_stream,
)


def _message(
    *,
    msg_id: str,
    msg_type: str,
    status: str,
    text: str | None = None,
) -> Message:
    content = None
    if text is not None:
        content = [TextContent(text=text, delta=False, index=0)]
    return Message(
        id=msg_id,
        type=msg_type,
        role=Role.ASSISTANT,
        status=status,
        content=content,
    )


def test_reasoning_empty_boundary_becomes_completed_reasoning_event() -> None:
    reasoning = _message(
        msg_id="reason-1",
        msg_type=MessageType.REASONING,
        status=RunStatus.InProgress,
        text="thinking",
    )
    boundary = _message(
        msg_id="boundary-1",
        msg_type=MessageType.MESSAGE,
        status=RunStatus.InProgress,
    )

    events = list(_normalize_reasoning_boundary_events([reasoning, boundary]))

    assert events[0] is reasoning
    assert events[1].id == "reason-1"
    assert events[1].type == MessageType.REASONING
    assert events[1].status == RunStatus.Completed


def test_non_reasoning_message_boundary_is_preserved() -> None:
    message = _message(
        msg_id="msg-1",
        msg_type=MessageType.MESSAGE,
        status=RunStatus.InProgress,
        text="hello",
    )
    next_message = _message(
        msg_id="msg-2",
        msg_type=MessageType.MESSAGE,
        status=RunStatus.InProgress,
    )

    events = list(
        _normalize_reasoning_boundary_events([message, next_message]),
    )

    assert events == [message, next_message]


def test_reasoning_boundary_keeps_following_assistant_message_start() -> None:
    reasoning = _message(
        msg_id="reason-1",
        msg_type=MessageType.REASONING,
        status=RunStatus.InProgress,
        text="thinking",
    )
    answer_start = _message(
        msg_id="answer-1",
        msg_type=MessageType.MESSAGE,
        status=RunStatus.InProgress,
    )

    events = list(
        _normalize_reasoning_boundary_events([reasoning, answer_start]),
    )

    assert len(events) == 3
    assert events[0] is reasoning
    assert events[1].id == "reason-1"
    assert events[1].type == MessageType.REASONING
    assert events[1].status == RunStatus.Completed
    assert events[2] is answer_start


@pytest.mark.asyncio
async def test_stream_tool_call_uses_async_summary(monkeypatch) -> None:
    event = Message(
        id="tool-1",
        type=MessageType.FUNCTION_CALL,
        role=Role.ASSISTANT,
        status=RunStatus.InProgress,
        content=[
            DataContent(
                data={
                    "name": "grep_search",
                    "arguments": '{"pattern": "tenant"}',
                },
                delta=False,
                index=0,
            ),
        ],
    )

    async def source():
        yield event

    async def fake_summary(**_kwargs):
        return "搜索 tenant 相关代码"

    monkeypatch.setattr(
        "swe.app.runner.stream_boundary.async_generate_tool_call_summary",
        fake_summary,
    )

    events = [
        item async for item in normalize_reasoning_boundary_stream(source())
    ]

    assert events[0].content[0].data["summary"] == "搜索 tenant 相关代码"


@pytest.mark.asyncio
async def test_stream_tool_output_falls_back_to_rule_summary(
    monkeypatch,
) -> None:
    event = Message(
        id="tool-2",
        type=MessageType.FUNCTION_CALL_OUTPUT,
        role=Role.ASSISTANT,
        status=RunStatus.InProgress,
        content=[
            DataContent(
                data={
                    "name": "grep_search",
                    "output": '["a.py:1", "b.py:2"]',
                },
                delta=False,
                index=0,
            ),
        ],
    )

    async def source():
        yield event

    async def boom(**_kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(
        "swe.app.runner.stream_boundary.async_generate_tool_output_summary",
        boom,
    )

    events = [
        item async for item in normalize_reasoning_boundary_stream(source())
    ]

    assert events[0].content[0].data["output_summary"] == "共找到 2 项内容"


@pytest.mark.asyncio
async def test_stream_tool_output_summary_timeout_does_not_block_stream(
    monkeypatch,
) -> None:
    event = Message(
        id="tool-3",
        type=MessageType.FUNCTION_CALL_OUTPUT,
        role=Role.ASSISTANT,
        status=RunStatus.InProgress,
        content=[
            DataContent(
                data={
                    "name": "grep_search",
                    "output": '["a.py:1", "b.py:2"]',
                },
                delta=False,
                index=0,
            ),
        ],
    )

    async def source():
        yield event

    started = asyncio.Event()
    release = asyncio.Event()

    async def hang_forever(**_kwargs):
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()

    monkeypatch.setattr(
        "swe.app.runner.stream_boundary.async_generate_tool_output_summary",
        hang_forever,
    )

    events = await asyncio.wait_for(
        asyncio.create_task(
            _collect_events(normalize_reasoning_boundary_stream(source())),
        ),
        timeout=0.2,
    )

    assert started.is_set()
    assert events[0].content[0].data["output_summary"] == "共找到 2 项内容"

    release.set()


async def _collect_events(stream) -> list[Message]:
    return [item async for item in stream]
