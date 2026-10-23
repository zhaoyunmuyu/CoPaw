# -*- coding: utf-8 -*-
"""运行服务不借用旧管理器，也不把调度管理重新搬回 SWE。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from swe.config.context import encode_scope_id


class RuntimeWorkspace:
    def __init__(self, path):
        self.workspace_dir = path
        self.agent_id = "research"
        self.tenant_id = encode_scope_id("alice", "bank")
        self.runner = SimpleNamespace(workspace_dir=path)
        self.channel_manager = SimpleNamespace(send_text=AsyncMock())
        self._source_system_config_service = None
        self._continuous_governance_service = None

    @property
    def cron_manager(self):
        raise AssertionError("business execution must not access CronManager")


@pytest.mark.asyncio
async def test_independent_notification_preserves_channel_identity_and_link(
    tmp_path,
    monkeypatch,
):
    from swe.app.crons.notification_sender import CronNotificationSender
    from tests.unit.app.test_managed_cron_notifications import _spec

    workspace = RuntimeWorkspace(tmp_path)
    sender = CronNotificationSender.from_workspace(workspace)
    monkeypatch.setattr(
        sender,
        "_get_zhaohu_push_config",
        lambda: SimpleNamespace(
            session_end_push_link_prefix="https://example.test/chat",
            session_end_push_link_id_type="session_id",
        ),
    )
    await sender.send_task_success_notification("job-1", job=_spec())
    payload = workspace.channel_manager.send_text.await_args.kwargs
    assert payload["channel"] == "zhaohu"
    assert payload["user_id"] == "alice"
    assert payload["session_id"] == "cron-task:job-1"
    assert (
        payload["meta"]["link_url"]
        == "https://example.test/chat?sessionId=cron-task:job-1"
    )
    assert "执行时的名称" in payload["text"]
    assert not (tmp_path / "jobs.json").exists()


@pytest.mark.asyncio
async def test_system_actions_run_heartbeat_without_old_manager(
    tmp_path,
    monkeypatch,
):
    from swe.app.crons.system_actions import SystemBusinessActions
    from swe.app.crons import heartbeat

    workspace = RuntimeWorkspace(tmp_path)
    execute = AsyncMock()
    monkeypatch.setattr(heartbeat, "run_heartbeat_once", execute)
    manager = SimpleNamespace(get_agent=AsyncMock(return_value=workspace))
    action = await SystemBusinessActions(
        SimpleNamespace(state=SimpleNamespace(multi_agent_manager=manager)),
    ).prepare(
        {
            "scope_kind": "agent",
            "task_type": "heartbeat",
            "tenant_id": "alice",
            "source_id": "bank",
            "agent_id": "research",
        },
    )
    await action()
    payload = execute.await_args.kwargs
    assert payload["runner"] is workspace.runner
    assert payload["agent_id"] == "research"
    assert payload["managed_execution"] is True
    assert payload["tenant_id"] == encode_scope_id("alice", "bank")
    assert not (tmp_path / "jobs.json").exists()


@pytest.mark.asyncio
async def test_dream_runs_real_business_without_legacy_manager(tmp_path):
    from swe.app.crons.system_actions import SystemBusinessActions

    workspace = RuntimeWorkspace(tmp_path)
    dream = AsyncMock()
    workspace.runner.memory_manager = SimpleNamespace(dream_memory=dream)
    action = await SystemBusinessActions(
        SimpleNamespace(
            state=SimpleNamespace(
                multi_agent_manager=SimpleNamespace(
                    get_agent=AsyncMock(return_value=workspace),
                ),
            ),
        ),
    ).prepare(
        {
            "scope_kind": "agent",
            "task_type": "dream",
            "tenant_id": "alice",
            "source_id": "bank",
            "agent_id": "research",
        },
    )
    await action()
    dream.assert_awaited_once_with(
        tenant_id=encode_scope_id("alice", "bank"),
        trigger="cron",
    )
    assert not (tmp_path / "jobs.json").exists()


@pytest.mark.asyncio
async def test_legacy_cleanup_adapter_preserves_file_task_metadata(tmp_path):
    from swe.app.crons.legacy_session_cleanup import (
        cleanup_legacy_workspace_sessions,
    )
    from swe.app.crons.models import JobsFile
    from swe.app.crons.repo.json_repo import JsonJobRepository
    from tests.unit.app.test_cron_task_session_cleanup import (
        _Session,
        _SourceSystemConfigService,
        _job,
    )

    workspace = RuntimeWorkspace(tmp_path)
    workspace._source_system_config_service = _SourceSystemConfigService()
    session = _Session(
        {
            "task_messages": [
                {"timestamp": "2026-01-01T00:00:00Z", "content": "expired"},
            ],
        },
    )
    workspace.runner.session = session
    repo = JsonJobRepository(tmp_path / "jobs.json")
    await repo.save(
        JobsFile(
            jobs=[
                _job(
                    meta={
                        "task_session_id": "task-1",
                        "creator_user_id": "alice",
                        "task_unread_execution_count": 5,
                    },
                ),
            ],
        ),
    )
    result = await cleanup_legacy_workspace_sessions(
        workspace,
        now=datetime(2026, 10, 22, tzinfo=timezone.utc),
    )
    assert result["messages_removed"] == 1
    assert result["sessions_cleaned"] == 1
    saved = await repo.get_job("job-1")
    assert saved.meta["task_unread_execution_count"] == 0
    assert saved.meta["task_has_scheduled_result"] is False
    assert session.lock_keys == [("task-1", "alice", 5.0)]


def test_shared_pruning_preserves_unrelated_session_data():
    from swe.app.crons.session_cleanup import _prune_task_session_state

    state = {
        "custom": {"value": 1},
        "task_messages": [
            {"timestamp": "2026-01-01T00:00:00Z", "content": "old"},
        ],
    }
    snapshot = _prune_task_session_state(
        state,
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    assert snapshot.state["custom"] == {"value": 1}
    assert snapshot.state["task_messages"] == []
    assert len(state["task_messages"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["heartbeat", "dream"])
async def test_configuration_save_submits_refresh_without_old_manager(
    tmp_path,
    monkeypatch,
    kind,
):
    from swe.app.crons import system_bridge
    from swe.app.routers import config, agent
    from swe.config import AgentsRunningConfig
    from swe.app import agent_context
    import importlib

    workspace = RuntimeWorkspace(tmp_path)
    saved = []

    async def submit(*args):
        assert saved == [True]
        assert args == ("alice", "bank", "research", kind)
        return {"submission_status": "accepted"}

    monkeypatch.setattr(system_bridge, "submit_agent_refresh", submit)
    context_owner = agent_context if kind == "heartbeat" else agent
    save_owner = (
        importlib.import_module("swe.config.config")
        if kind == "heartbeat"
        else agent
    )
    monkeypatch.setattr(
        context_owner,
        "get_agent_and_config_for_request",
        AsyncMock(return_value=(workspace, SimpleNamespace())),
    )
    monkeypatch.setattr(
        save_owner,
        "save_agent_config",
        lambda *a, **k: saved.append(True),
    )
    if kind == "heartbeat":
        result = await config.put_heartbeat(
            SimpleNamespace(),
            config.HeartbeatBody(),
        )
        sync = result["scheduler_sync"]
    else:
        monkeypatch.setattr(
            agent,
            "schedule_agent_reload",
            lambda *a, **k: None,
        )
        result = await agent.put_agents_running_config(
            AgentsRunningConfig(),
            SimpleNamespace(),
        )
        sync = result.scheduler_sync
    assert sync["submission_status"] == "accepted"
