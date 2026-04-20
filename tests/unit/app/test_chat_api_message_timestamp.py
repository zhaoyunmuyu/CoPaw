# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from agentscope.message import Msg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.swe.app.runner.api import (
    get_chat_manager,
    get_session,
    get_workspace,
    router,
)
from src.swe.app.runner.models import ChatSpec


class _FakeSession:
    async def get_session_state_dict(
        self,
        _session_id: str,
        _user_id: str,
    ) -> dict:
        return {"agent": {"memory": {"messages": []}}}


class _FakeMemory:
    def load_state_dict(
        self,
        state_dict: dict,
        _strict: bool = False,
    ) -> None:
        self.state_dict = state_dict

    async def get_memory(
        self,
        _prepend_summary: bool = False,
    ) -> list[Msg]:
        return [
            Msg(
                name="tester",
                role="user",
                content="hello",
                timestamp="2026-04-17T08:00:00Z",
            ),
        ]


class _FakeTaskTracker:
    async def get_status(self, _chat_id: str) -> str:
        return "idle"


class _FakeChatManager:
    async def get_chat(self, chat_id: str) -> ChatSpec:
        return ChatSpec(
            id=chat_id,
            name="Test Chat",
            session_id="default:user-1",
            user_id="user-1",
            channel="default",
        )


def test_get_chat_exposes_message_timestamp(
    monkeypatch,
) -> None:
    from src.swe.app.runner import api as chat_api_module

    monkeypatch.setattr(chat_api_module, "InMemoryMemory", _FakeMemory)

    workspace = SimpleNamespace(
        chat_manager=_FakeChatManager(),
        runner=SimpleNamespace(session=_FakeSession()),
        task_tracker=_FakeTaskTracker(),
    )

    app = FastAPI()
    app.include_router(router)

    async def _get_workspace():
        return workspace

    async def _get_chat_manager_override():
        return workspace.chat_manager

    async def _get_session_override():
        return workspace.runner.session

    app.dependency_overrides[get_workspace] = _get_workspace
    app.dependency_overrides[get_chat_manager] = _get_chat_manager_override
    app.dependency_overrides[get_session] = _get_session_override

    client = TestClient(app)

    response = client.get("/chats/chat-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["messages"][0]["timestamp"] == "2026-04-17T08:00:00Z"
