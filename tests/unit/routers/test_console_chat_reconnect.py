# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.swe.app.routers import console as console_router


class _FakeConsoleChannel:
    def resolve_session_id(self, sender_id: str, channel_meta: dict) -> str:
        return channel_meta.get("session_id") or f"console:{sender_id}"

    async def stream_one(self, payload):
        yield payload


class _FakeChannelManager:
    async def get_channel(self, name: str):
        assert name == "console"
        return _FakeConsoleChannel()


class _FakeChatManager:
    def __init__(self) -> None:
        self.get_or_create_calls: list[tuple[str, str, str, str]] = []
        self.get_chat_id_by_session_calls: list[tuple[str, str]] = []

    async def get_chat(self, chat_id: str):
        if chat_id == "chat-existing":
            return SimpleNamespace(
                id="chat-existing",
                session_id="session-existing",
                user_id="user-1",
                channel="console",
                name="Existing Chat",
            )
        return None

    async def get_chat_id_by_session(self, session_id: str, channel: str):
        self.get_chat_id_by_session_calls.append((session_id, channel))
        if session_id == "session-existing" and channel == "console":
            return "chat-existing"
        return None

    async def get_or_create_chat(
        self,
        session_id: str,
        user_id: str,
        channel_id: str,
        name: str,
    ):
        self.get_or_create_calls.append(
            (session_id, user_id, channel_id, name),
        )
        return SimpleNamespace(
            id=f"chat:{session_id}",
            session_id=session_id,
            user_id=user_id,
            channel=channel_id,
            name=name,
        )


class _FakeTaskTracker:
    async def attach_or_start(self, run_key, payload, stream_fn):
        raise AssertionError("attach_or_start should not run during reconnect")

    async def attach(self, run_key):
        if run_key == "chat-existing":
            return object()
        return None

    async def stream_from_queue(self, _queue, _run_key):
        await asyncio.sleep(0)
        yield 'data: {"done": true}\n\n'


def test_console_chat_reconnect_accepts_chat_id_without_creating_new_chat(
    monkeypatch,
) -> None:
    app = FastAPI()
    app.include_router(console_router.router)

    chat_manager = _FakeChatManager()
    workspace = SimpleNamespace(
        channel_manager=_FakeChannelManager(),
        chat_manager=chat_manager,
        task_tracker=_FakeTaskTracker(),
    )

    async def _fake_get_agent_for_request(_request):
        return workspace

    monkeypatch.setattr(
        console_router,
        "get_agent_for_request",
        _fake_get_agent_for_request,
    )

    client = TestClient(app)

    with client.stream(
        "POST",
        "/console/chat",
        json={
            "reconnect": True,
            "session_id": "chat-existing",
            "user_id": "user-1",
            "channel": "console",
        },
    ) as response:
        assert response.status_code == 200
        assert list(response.iter_lines()) == ['data: {"done": true}', ""]

    assert not chat_manager.get_or_create_calls


def test_console_chat_reconnect_accepts_logical_session_id(
    monkeypatch,
) -> None:
    app = FastAPI()
    app.include_router(console_router.router)

    chat_manager = _FakeChatManager()
    workspace = SimpleNamespace(
        channel_manager=_FakeChannelManager(),
        chat_manager=chat_manager,
        task_tracker=_FakeTaskTracker(),
    )

    async def _fake_get_agent_for_request(_request):
        return workspace

    monkeypatch.setattr(
        console_router,
        "get_agent_for_request",
        _fake_get_agent_for_request,
    )

    client = TestClient(app)

    with client.stream(
        "POST",
        "/console/chat",
        json={
            "reconnect": True,
            "session_id": "session-existing",
            "user_id": "user-1",
            "channel": "console",
        },
    ) as response:
        assert response.status_code == 200
        assert list(response.iter_lines()) == ['data: {"done": true}', ""]

    assert chat_manager.get_chat_id_by_session_calls == [
        ("session-existing", "console"),
    ]
    assert not chat_manager.get_or_create_calls
