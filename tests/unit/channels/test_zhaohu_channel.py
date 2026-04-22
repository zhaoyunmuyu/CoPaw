# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Unit tests for Zhaohu channel case2 non-streaming handling."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    ContentType,
    Message,
    Role,
    RunStatus,
    TextContent,
)

from swe.app.channels.zhaohu.channel import ZhaohuChannel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_channel(**overrides: Any) -> ZhaohuChannel:
    """Create a ZhaohuChannel with dummy process handler."""

    async def _noop_process(_request):
        yield  # pragma: no cover

    defaults = {
        "process": _noop_process,
        "enabled": True,
        "push_url": "https://test.push.url",
        "sys_id": "test_sys_id",
        "robot_open_id": "test_robot_open_id",
        "channel_code": "ZH",
        "net": "DMZ",
        "request_timeout": 15.0,
        "bot_prefix": "",
        "custom_card_url": "https://test.card.url",
        "oauth_url": "https://test.oauth.url",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
    }
    defaults.update(overrides)
    ch = ZhaohuChannel(**defaults)
    ch._http = MagicMock()
    return ch


def _make_request(
    session_id: str = "test_session",
    user_id: str = "test_user",
    text: str = "test content",
) -> AgentRequest:
    """Create a minimal AgentRequest for testing."""
    msg = Message(
        type="message",
        role=Role.USER,
        content=[TextContent(type=ContentType.TEXT, text=text)],
    )
    return AgentRequest(
        session_id=session_id,
        user_id=user_id,
        input=[msg],
        channel="zhaohu",
    )


def _make_completed_event(text: str) -> MagicMock:
    """Create a mock completed message event."""
    event = MagicMock()
    event.object = "message"
    event.status = RunStatus.Completed
    # Mock _message_to_content_parts behavior
    event.content = [TextContent(type=ContentType.TEXT, text=text)]
    return event


# ---------------------------------------------------------------------------
# Tests for _run_task_llm_and_notify
# ---------------------------------------------------------------------------


class TestRunTaskLlmAndNotify:
    """Tests for _run_task_llm_and_notify method."""

    @pytest.mark.asyncio
    async def test_collects_complete_result(self):
        """验证 _run_task_llm_and_notify 正确收集完整结果."""
        ch = _make_channel()

        # Mock process to yield completed events
        async def _mock_process(_request):
            # Yield a completed message event
            event = _make_completed_event("Final result text here")
            yield event

        ch._process = _mock_process

        # Mock send_custom_card
        ch.send_custom_card = AsyncMock(return_value=(0, "msg123"))

        # Mock send
        ch.send = AsyncMock()

        request = _make_request()
        meta = {"send_addr": "yst_id_123"}

        await ch._run_task_llm_and_notify(
            request=request,
            session_id="test_session",
            task_content="Do something",
            from_id="open_id_123",
            meta=meta,
            user_id="sap_id_123",
        )

        # Verify card was sent
        ch.send_custom_card.assert_called_once()

        # Verify final result was sent via push_url
        ch.send.assert_called_once()
        call_args = ch.send.call_args
        assert call_args[0][0] == "yst_id_123"
        assert "Final result text here" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_card_sent_immediately(self):
        """验证卡片通知立即发送."""
        ch = _make_channel()

        async def _mock_process(_request):
            yield _make_completed_event("Result")

        ch._process = _mock_process
        ch.send_custom_card = AsyncMock(return_value=(0, "msg123"))
        ch.send = AsyncMock()

        request = _make_request()
        meta = {"send_addr": "yst_id_123"}

        await ch._run_task_llm_and_notify(
            request=request,
            session_id="test_session",
            task_content="Do something",
            from_id="open_id_123",
            meta=meta,
            user_id="sap_id_123",
        )

        # Card should be called first (before send)
        ch.send_custom_card.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_result_no_send(self):
        """验证无结果时不发送消息."""
        ch = _make_channel()

        async def _mock_process(_request):
            # Yield nothing (no completed message)
            yield MagicMock(object="other", status=None)

        ch._process = _mock_process
        ch.send_custom_card = AsyncMock(return_value=(0, "msg123"))
        ch.send = AsyncMock()

        request = _make_request()
        meta = {"send_addr": "yst_id_123"}

        await ch._run_task_llm_and_notify(
            request=request,
            session_id="test_session",
            task_content="Do something",
            from_id="open_id_123",
            meta=meta,
            user_id="sap_id_123",
        )

        # Card should still be sent
        ch.send_custom_card.assert_called_once()
        # But no result send
        ch.send.assert_not_called()


class TestErrorHandling:
    """Tests for error handling in _run_task_llm_and_notify."""

    @pytest.mark.asyncio
    async def test_error_notification_sent(self):
        """验证处理失败时发送错误通知."""
        ch = _make_channel()

        async def _mock_process(_request):
            raise RuntimeError("Processing failed")

        ch._process = _mock_process
        ch.send_custom_card = AsyncMock(return_value=(0, "msg123"))
        ch.send = AsyncMock()

        request = _make_request()
        meta = {"send_addr": "yst_id_123"}

        await ch._run_task_llm_and_notify(
            request=request,
            session_id="test_session",
            task_content="Do something",
            from_id="open_id_123",
            meta=meta,
            user_id="sap_id_123",
        )

        # Card should still be sent
        ch.send_custom_card.assert_called_once()

        # Error notification should be sent
        ch.send.assert_called_once()
        call_args = ch.send.call_args
        assert call_args[0][0] == "yst_id_123"
        assert "错误" in call_args[0][1] or "error" in call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_no_send_addr_no_error_send(self):
        """验证无 send_addr 时不发送错误通知."""
        ch = _make_channel()

        async def _mock_process(_request):
            raise RuntimeError("Processing failed")

        ch._process = _mock_process
        ch.send_custom_card = AsyncMock(return_value=(0, "msg123"))
        ch.send = AsyncMock()

        request = _make_request()
        meta = {}  # No send_addr

        await ch._run_task_llm_and_notify(
            request=request,
            session_id="test_session",
            task_content="Do something",
            from_id="open_id_123",
            meta=meta,
            user_id="sap_id_123",
        )

        # Card should still be sent
        ch.send_custom_card.assert_called_once()
        # No error send since no send_addr
        ch.send.assert_not_called()


class TestHandleTaskAssignment:
    """Tests for _handle_task_assignment using non-streaming flow."""

    @pytest.mark.asyncio
    async def test_calls_run_task_llm_and_notify(self):
        """验证 _handle_task_assignment 调用 _run_task_llm_and_notify."""
        ch = _make_channel()

        # Mock _run_task_llm_and_notify
        ch._run_task_llm_and_notify = AsyncMock()

        await ch._handle_task_assignment(
            sap_id="sap123",
            from_id="open123",
            task_content="This is a long task description",
            meta={"send_addr": "yst123"},
        )

        # Should call _run_task_llm_and_notify
        ch._run_task_llm_and_notify.assert_called_once()
        call_args = ch._run_task_llm_and_notify.call_args[0]
        # Arguments: request, session_id, task_content, from_id, meta
        assert call_args[1].startswith("zhaohu:task:")
        assert call_args[3] == "open123"

    @pytest.mark.asyncio
    async def test_no_consume_with_tracker_call(self):
        """验证不调用 _consume_with_tracker."""
        ch = _make_channel()

        # Mock both methods to track which is called
        ch._run_task_llm_and_notify = AsyncMock()
        ch._consume_with_tracker = AsyncMock()

        await ch._handle_task_assignment(
            sap_id="sap123",
            from_id="open123",
            task_content="This is a long task description",
            meta={"send_addr": "yst123"},
        )

        # Should NOT call _consume_with_tracker
        ch._consume_with_tracker.assert_not_called()


class TestCase1AndCase3Unaffected:
    """Tests for Case 1 and Case 3 flow not affected."""

    @pytest.mark.asyncio
    async def test_case1_task_progress_query_unchanged(self):
        """验证 Case 1（任务进度查询）流程不变."""
        ch = _make_channel()

        # Mock _query_task_progress
        ch._query_task_progress = AsyncMock(return_value=True)

        # Case 1: message is exactly one of the keywords
        await ch._route_message(
            msg_id="msg123",
            from_id="open123",
            sap_id="sap123",
            yst_id="yst123",
            msg_content="我的任务进度",
            meta={"send_addr": "yst123"},
        )

        # Should call _query_task_progress
        ch._query_task_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_case3_casual_chat_unchanged(self):
        """验证 Case 3（闲聊）流程不变."""
        ch = _make_channel()

        # Mock _handle_casual_chat
        ch._handle_casual_chat = AsyncMock()

        # Case 3: short message (< 10 chars)
        await ch._route_message(
            msg_id="msg123",
            from_id="open123",
            sap_id="sap123",
            yst_id="yst123",
            msg_content="你好",  # Short message
            meta={"send_addr": "yst123"},
        )

        # Should call _handle_casual_chat
        ch._handle_casual_chat.assert_called_once()
