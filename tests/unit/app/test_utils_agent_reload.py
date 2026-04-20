# -*- coding: utf-8 -*-
"""Tests for tenant-aware agent reload scheduling."""

import asyncio
from types import SimpleNamespace
from typing import Any, Coroutine
from unittest.mock import AsyncMock

from swe.app import utils as app_utils


def test_schedule_agent_reload_passes_tenant_id(monkeypatch) -> None:
    manager = SimpleNamespace(reload_agent=AsyncMock(return_value=True))
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(multi_agent_manager=manager),
        ),
    )
    scheduled: list[Coroutine[Any, Any, Any]] = []

    def fake_create_task(coro):
        scheduled.append(coro)
        return SimpleNamespace()

    monkeypatch.setattr(app_utils.asyncio, "create_task", fake_create_task)

    app_utils.schedule_agent_reload(
        request,
        "default",
        tenant_id="tenant-a",
    )

    assert len(scheduled) == 1
    asyncio.run(scheduled[0])
    manager.reload_agent.assert_awaited_once_with(
        "default",
        tenant_id="tenant-a",
    )
