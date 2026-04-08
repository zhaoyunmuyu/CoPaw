# -*- coding: utf-8 -*-
"""Cron executor tenant context regression tests."""
import asyncio
import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

SRC_ROOT = Path(__file__).parent.parent.parent.parent / "src"
_MODELS_FILE = SRC_ROOT / "swe" / "app" / "crons" / "models.py"
_EXECUTOR_FILE = SRC_ROOT / "swe" / "app" / "crons" / "executor.py"


if "swe.app" not in sys.modules:
    app_pkg = types.ModuleType("swe.app")
    app_pkg.__path__ = [str(SRC_ROOT / "swe" / "app")]
    sys.modules["swe.app"] = app_pkg

if "swe.app.crons" not in sys.modules:
    crons_pkg = types.ModuleType("swe.app.crons")
    crons_pkg.__path__ = [str(SRC_ROOT / "swe" / "app" / "crons")]
    sys.modules["swe.app.crons"] = crons_pkg

channels_schema = types.ModuleType("swe.app.channels.schema")
channels_schema.DEFAULT_CHANNEL = "console"
sys.modules["swe.app.channels.schema"] = channels_schema

context_module = importlib.import_module("swe.config.context")
importlib.import_module("swe.app.tenant_context")

models_spec = importlib.util.spec_from_file_location(
    "swe.app.crons.models",
    _MODELS_FILE,
)
models_module = importlib.util.module_from_spec(models_spec)
sys.modules["swe.app.crons.models"] = models_module
assert models_spec is not None and models_spec.loader is not None
models_spec.loader.exec_module(models_module)


executor_spec = importlib.util.spec_from_file_location(
    "swe.app.crons.executor",
    _EXECUTOR_FILE,
)
executor_module = importlib.util.module_from_spec(executor_spec)
sys.modules["swe.app.crons.executor"] = executor_module
assert executor_spec is not None and executor_spec.loader is not None
executor_spec.loader.exec_module(executor_module)


CronExecutor = executor_module.CronExecutor
CronJobRequest = models_module.CronJobRequest
CronJobSpec = models_module.CronJobSpec
DispatchSpec = models_module.DispatchSpec
DispatchTarget = models_module.DispatchTarget
JobRuntimeSpec = models_module.JobRuntimeSpec
ScheduleSpec = models_module.ScheduleSpec


def _get_current_workspace_dir():
    return context_module.get_current_workspace_dir()


class _Runner:
    async def stream_query(self, req):
        if False:
            yield None


class _ChannelManager:
    async def send_text(self, **kwargs):
        return None

    async def send_event(self, **kwargs):
        return None


def _build_text_job(workspace_dir: str) -> object:
    return CronJobSpec(
        id="job-text",
        name="text job",
        tenant_id="tenant-a",
        schedule=ScheduleSpec(cron="* * * * *"),
        task_type="text",
        text="hello",
        dispatch=DispatchSpec(
            channel="console",
            target=DispatchTarget(user_id="user-a", session_id="session-a"),
            meta={"workspace_dir": workspace_dir},
        ),
        runtime=JobRuntimeSpec(timeout_seconds=1),
    )


def _build_agent_job(workspace_dir: str, timeout_seconds: int = 1) -> object:
    return CronJobSpec(
        id="job-agent",
        name="agent job",
        tenant_id="tenant-a",
        schedule=ScheduleSpec(cron="* * * * *"),
        task_type="agent",
        request=CronJobRequest(input=[{"content": [{"text": "ping"}]}]),
        dispatch=DispatchSpec(
            channel="console",
            target=DispatchTarget(user_id="user-a", session_id="session-a"),
            meta={"workspace_dir": workspace_dir},
        ),
        runtime=JobRuntimeSpec(timeout_seconds=timeout_seconds),
    )


def test_execute_binds_workspace_dir_during_job_and_resets_afterward(monkeypatch):
    observed = {}
    executor = CronExecutor(runner=_Runner(), channel_manager=_ChannelManager())
    job = _build_text_job("/tmp/tenant-a/workspaces/alpha")

    async def fake_execute_job(self, job, target_user_id, target_session_id, dispatch_meta):
        observed["workspace_in_job"] = _get_current_workspace_dir()
        observed["meta_workspace"] = dispatch_meta.get("workspace_dir")

    monkeypatch.setattr(CronExecutor, "_execute_job", fake_execute_job)

    asyncio.run(executor.execute(job))

    assert observed["workspace_in_job"] == Path("/tmp/tenant-a/workspaces/alpha")
    assert _get_current_workspace_dir() is None


def test_execute_resets_workspace_dir_after_timeout(monkeypatch):
    observed = {}

    executor = CronExecutor(
        runner=_Runner(),
        channel_manager=_ChannelManager(),
    )
    job = _build_agent_job("/tmp/tenant-a/workspaces/beta")

    async def fake_execute_job(self, job, target_user_id, target_session_id, dispatch_meta):
        observed["workspace_in_job"] = _get_current_workspace_dir()
        raise asyncio.TimeoutError

    monkeypatch.setattr(CronExecutor, "_execute_job", fake_execute_job)

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(executor.execute(job))

    assert observed["workspace_in_job"] == Path("/tmp/tenant-a/workspaces/beta")
    assert _get_current_workspace_dir() is None
