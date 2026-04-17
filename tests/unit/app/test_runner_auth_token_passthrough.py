# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from swe.app.runner.runner import AgentRunner


@pytest.mark.asyncio
async def test_query_handler_injects_auth_headers_into_mcp_headers_and_context(
    monkeypatch,
) -> None:
    runner = AgentRunner(agent_id="test-agent")
    runner.session = AsyncMock()
    runner.session.load_session_state = AsyncMock()
    runner.session.save_session_state = AsyncMock()
    runner._chat_manager = None

    captured: dict[str, object] = {}

    async def fake_build_clients(_mcp, passthrough_headers=None):
        captured["passthrough_headers"] = passthrough_headers
        return []

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["request_context"] = kwargs["request_context"]

        async def register_mcp_clients(self):
            return None

        def set_console_output_enabled(self, enabled=False):
            return None

        def rebuild_sys_prompt(self):
            return None

        async def __call__(self, _msgs):
            return None

    async def fake_stream_printing_messages(*, agents, coroutine_task):
        await coroutine_task
        if False:
            yield None

    monkeypatch.setattr(
        "swe.app.runner.runner.load_agent_config",
        lambda *args, **kwargs: SimpleNamespace(mcp=None),
    )
    monkeypatch.setattr(
        "swe.app.runner.runner._build_and_connect_mcp_clients",
        fake_build_clients,
    )
    monkeypatch.setattr("swe.app.runner.runner.SWEAgent", FakeAgent)
    monkeypatch.setattr(
        "swe.app.runner.runner.stream_printing_messages",
        fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.build_env_context",
        lambda **kwargs: kwargs,
    )
    monkeypatch.setattr(
        "swe.app.runner.runner._cleanup_mcp_clients",
        AsyncMock(),
    )

    request = SimpleNamespace(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        auth_token="token-123",
        cookie="foo=bar; com.cmb.dw.rtl.sso.token=auth-123",
    )
    msgs = [SimpleNamespace(get_text_content=lambda: "hello")]

    results = []
    async for item in runner.query_handler(msgs, request=request):
        results.append(item)

    assert results == []
    assert captured["passthrough_headers"] == {
        "Authorization": "Bearer token-123",
        "cookie": "foo=bar; com.cmb.dw.rtl.sso.token=auth-123",
    }
    assert captured["request_context"]["auth_token"] == "token-123"


@pytest.mark.asyncio
async def test_query_handler_keeps_existing_passthrough_headers(monkeypatch):
    runner = AgentRunner(agent_id="test-agent")
    runner.session = AsyncMock()
    runner.session.load_session_state = AsyncMock()
    runner.session.save_session_state = AsyncMock()
    runner._chat_manager = None

    captured: dict[str, object] = {}

    async def fake_build_clients(_mcp, passthrough_headers=None):
        captured["passthrough_headers"] = passthrough_headers
        return []

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["request_context"] = kwargs["request_context"]

        async def register_mcp_clients(self):
            return None

        def set_console_output_enabled(self, enabled=False):
            return None

        def rebuild_sys_prompt(self):
            return None

        async def __call__(self, _msgs):
            return None

    async def fake_stream_printing_messages(*, agents, coroutine_task):
        await coroutine_task
        if False:
            yield None

    monkeypatch.setattr(
        "swe.app.runner.runner.load_agent_config",
        lambda *args, **kwargs: SimpleNamespace(mcp=None),
    )
    monkeypatch.setattr(
        "swe.app.runner.runner._build_and_connect_mcp_clients",
        fake_build_clients,
    )
    monkeypatch.setattr("swe.app.runner.runner.SWEAgent", FakeAgent)
    monkeypatch.setattr(
        "swe.app.runner.runner.stream_printing_messages",
        fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.build_env_context",
        lambda **kwargs: kwargs,
    )
    monkeypatch.setattr(
        "swe.app.runner.runner._cleanup_mcp_clients",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "swe.app.runner.runner.get_current_passthrough_headers",
        lambda: {
            "authorization": "Bearer existing",
            "cookie": "foo=existing",
        },
    )

    request = SimpleNamespace(
        session_id="session-1",
        user_id="user-1",
        channel="console",
        auth_token="token-123",
        cookie="foo=bar; com.cmb.dw.rtl.sso.token=auth-123",
    )
    msgs = [SimpleNamespace(get_text_content=lambda: "hello")]

    results = []
    async for item in runner.query_handler(msgs, request=request):
        results.append(item)

    assert results == []
    assert captured["passthrough_headers"] == {
        "authorization": "Bearer existing",
        "cookie": "foo=existing",
    }
    assert captured["request_context"]["auth_token"] == "token-123"
