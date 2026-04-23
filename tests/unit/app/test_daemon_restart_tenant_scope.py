# -*- coding: utf-8 -*-
"""Regression tests for tenant-aware daemon restart reload."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentscope.message import Msg, TextBlock

from swe.app.runner import command_dispatch, daemon_commands


@pytest.mark.asyncio
async def test_run_daemon_restart_passes_tenant_id() -> None:
    reload_calls: list[tuple[str, str | None]] = []

    class FakeManager:
        async def reload_agent(
            self,
            agent_id: str,
            tenant_id: str | None = None,
        ) -> bool:
            reload_calls.append((agent_id, tenant_id))
            return True

    message = await daemon_commands.run_daemon_restart(
        daemon_commands.DaemonContext(
            manager=FakeManager(),
            agent_id="default",
            tenant_id="tenant-a",
        ),
    )

    assert "Restart completed" in message
    assert reload_calls == [("default", "tenant-a")]


@pytest.mark.asyncio
async def test_run_command_path_builds_tenant_aware_daemon_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, str | None] = {}

    async def fake_handle_daemon_command(self, query, context):
        del self
        observed["query"] = query
        observed["tenant_id"] = context.tenant_id
        return Msg(
            name="Friday",
            role="assistant",
            content=[TextBlock(type="text", text="ok")],
        )

    monkeypatch.setattr(
        command_dispatch.DaemonCommandHandlerMixin,
        "handle_daemon_command",
        fake_handle_daemon_command,
    )

    runner = SimpleNamespace(
        agent_id="default",
        memory_manager=None,
        _manager=SimpleNamespace(),
        _workspace=SimpleNamespace(tenant_id="tenant-a"),
    )
    request = SimpleNamespace(session_id="session-1", user_id="user-1")
    msgs = [SimpleNamespace(get_text_content=lambda: "/daemon restart")]

    results = []
    async for item in command_dispatch.run_command_path(
        request,
        msgs,
        runner,
    ):
        results.append(item)

    assert len(results) == 2
    assert observed == {
        "query": "/daemon restart",
        "tenant_id": "tenant-a",
    }
