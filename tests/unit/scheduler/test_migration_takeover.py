# -*- coding: utf-8 -*-
"""导入与 Scheduler 接管共库协作，原任务和会话标识不可改变。"""

import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from tests.unit.scheduler.test_managed_cron_executions import ExecutionDatabase
from tests.unit.scheduler.test_managed_cron_management import (
    create_payload,
    PlatformClient,
)


class MigrationDatabase(ExecutionDatabase):
    async def fetch_one(self, query, params=None):
        row = await super().fetch_one(query, params)
        if (
            row
            and "FROM swe_async_tasks" in query
            and isinstance(row.get("updated_at"), str)
        ):
            row["updated_at"] = datetime.fromisoformat(row["updated_at"])
        return row


def database():
    from swe.app.crons.migration_repository import (
        DEFINITION_FIELDS,
        STATE_FIELDS,
    )

    db = MigrationDatabase()
    for table, columns in {
        "swe_cron_jobs_v2": DEFINITION_FIELDS
        | {"imported_at", "source_observed_at", "migration_batch_id"},
        "swe_cron_job_states": STATE_FIELDS
        | {"state_observed_at", "runtime_updated_at"},
    }.items():
        existing = {
            row[1]
            for row in db.conn.execute("PRAGMA table_info(" + table + ")")
        }
        for column in columns - existing:
            kind = (
                "INTEGER DEFAULT 1" if column.endswith("version") else "TEXT"
            )
            db.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
    return db


def add_async_tables(db):
    db.conn.executescript(
        """CREATE TABLE swe_async_tasks(task_id TEXT PRIMARY KEY,task_type TEXT,service TEXT,status TEXT,title TEXT,target_count INTEGER,done_count INTEGER,failed_count INTEGER,result_json TEXT,error_message TEXT,created_at TEXT,updated_at TEXT,finished_at TEXT); CREATE TABLE swe_async_task_items(task_id TEXT,target_id TEXT,status TEXT,result_json TEXT,updated_at TEXT,PRIMARY KEY(task_id,target_id));""",
    )


def snapshot(mode="ordinary", *, job_id="original-job", parent=None):
    from swe.app.crons.migration_models import SnapshotCandidate
    from scheduler.app.services.cron.managed.definition import normalize_spec
    from scheduler.app.services.cron.managed.identity import CallerIdentity
    from scheduler.app.services.cron.managed.operations import ManagementStore

    caller = CallerIdentity("alice", "bank", "default", "alice")
    spec = normalize_spec(create_payload()["spec"], caller, job_id)
    spec["meta"].update(
        task_chat_id="original-chat",
        task_session_id="original-session",
    )
    spec["request"]["session_id"] = "original-session"
    spec["dispatch"]["target"]["session_id"] = "original-session"
    definition = {
        **ManagementStore.definition_values(spec),
        **dict(
            zip(
                ("tenant_id", "source_id", "agent_id", "job_id"),
                caller.job_key(job_id),
            ),
        ),
        "spec_json": spec,
        "management_owner": "legacy",
        "creator_user_id": "alice",
        "job_origin": "manual",
        "source_definition_version": 1,
    }
    if parent:
        definition.update(
            parent_tenant_id="alice",
            parent_source_id="bank",
            parent_agent_id="default",
            parent_job_id=parent,
        )
    return SnapshotCandidate(
        definition,
        {
            "task_chat_id": "original-chat",
            "task_session_id": "original-session",
            "ordinary_external_job_id": "old-ordinary",
            "batch_external_job_id": "old-batch",
            "dispatch_state": mode,
            "last_status": "success",
            "unread_execution_count": 7,
            "state_source": "file_meta",
        },
        datetime(2026, 10, 22),
        "tenant/workspaces/default/jobs.json",
        "original-fingerprint",
        1,
    )


@pytest.mark.asyncio
async def test_import_and_recovery_preserve_original_ids_without_preparation():
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db, candidate = database(), snapshot()
    repository = MigrationRepository(db, takeover=MigrationTakeover(db))
    outcome = await repository.import_snapshot(candidate)
    assert outcome.operation_id
    assert (
        await repository.inspect(candidate, "verify")
    ).status == "takeover_pending"
    row = await db.fetch_one("SELECT * FROM swe_cron_jobs_v2")
    assert row["job_id"] == "original-job"
    assert row["management_owner"] == "scheduler"
    resources = AsyncMock()
    resources.prepare.side_effect = AssertionError(
        "migration must not prepare new sessions",
    )
    platform = PlatformClient()
    worker = MigrationTakeoverWorker(db, resources, platform)
    assert await worker.tick() == 1
    state = await db.fetch_one("SELECT * FROM swe_cron_job_states")
    assert state["management_status"] == "ready"
    assert state["task_session_id"] == "original-session"
    assert state["task_chat_id"] == "original-chat"
    assert state["unread_execution_count"] == 7
    assert state["ordinary_external_job_id"] != "old-ordinary"
    resources.prepare.assert_not_awaited()
    assert (await repository.import_snapshot(candidate)).status == "unchanged"
    assert (await repository.inspect(candidate, "verify")).status == "matched"
    assert await worker.tick() == 0
    assert platform.calls.count("register") == 1
    db.conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["batch_enabled", "batch_paused"])
async def test_migrated_batch_parent_registers_new_timer_with_original_mode(
    mode,
):
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db = database()
    await MigrationRepository(
        db,
        takeover=MigrationTakeover(db),
    ).import_snapshot(snapshot(mode))
    platform = PlatformClient()
    await MigrationTakeoverWorker(db, AsyncMock(), platform).tick()
    state = await db.fetch_one("SELECT * FROM swe_cron_job_states")
    assert state["dispatch_state"] == mode
    assert state["batch_external_job_id"] != "old-batch"
    assert platform.calls[-1] == (
        "enable" if mode == "batch_enabled" else "pause"
    )
    db.conn.close()


@pytest.mark.asyncio
async def test_binding_conflict_rolls_back_without_claiming_ownership():
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover

    db, candidate = database(), snapshot()
    candidate.definition["spec_json"]["meta"][
        "task_session_id"
    ] = "different-session"
    with pytest.raises(ValueError, match="binding"):
        await MigrationRepository(
            db,
            takeover=MigrationTakeover(db),
        ).import_snapshot(candidate)
    assert await db.fetch_one("SELECT * FROM swe_cron_jobs_v2") is None
    db.conn.close()


@pytest.mark.asyncio
async def test_platform_failure_keeps_original_ids_and_is_reported_by_verify():
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db, candidate = database(), snapshot()
    repository = MigrationRepository(db, takeover=MigrationTakeover(db))
    await repository.import_snapshot(candidate)
    resources, platform = AsyncMock(), PlatformClient()
    platform.lose_register_response = True
    await MigrationTakeoverWorker(db, resources, platform).tick()
    state = await db.fetch_one("SELECT * FROM swe_cron_job_states")
    assert state["task_chat_id"] == "original-chat"
    assert state["task_session_id"] == "original-session"
    assert (await repository.inspect(candidate, "verify")).status == "failed"
    assert platform.calls == ["register"]
    resources.prepare.assert_not_awaited()
    db.conn.close()


@pytest.mark.asyncio
async def test_two_recovery_workers_register_once():
    import asyncio
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db = database()
    await MigrationRepository(
        db,
        takeover=MigrationTakeover(db),
    ).import_snapshot(snapshot())
    platform = PlatformClient()
    await asyncio.gather(
        MigrationTakeoverWorker(db, AsyncMock(), platform).tick(),
        MigrationTakeoverWorker(db, AsyncMock(), platform).tick(),
    )
    assert platform.calls.count("register") == 1
    db.conn.close()


@pytest.mark.asyncio
async def test_batch_child_uses_parent_timer_without_own_registration():
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db = database()
    repository = MigrationRepository(db, takeover=MigrationTakeover(db))
    await repository.import_snapshot(
        snapshot("batch_enabled", job_id="parent"),
    )
    await repository.import_snapshot(
        snapshot("batch_enabled", job_id="child", parent="parent"),
    )
    platform = PlatformClient()
    worker = MigrationTakeoverWorker(db, AsyncMock(), platform)
    await worker.tick()
    await worker.tick()
    assert platform.calls.count("register") == 1
    states = await db.fetch_all(
        "SELECT management_status FROM swe_cron_job_states",
    )
    assert all(state["management_status"] == "ready" for state in states)
    db.conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("corrupt", ["state_binding", "prepared"])
async def test_recovery_never_replaces_changed_or_missing_original_bindings(
    corrupt,
):
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db = database()
    await MigrationRepository(
        db,
        takeover=MigrationTakeover(db),
    ).import_snapshot(snapshot())
    if corrupt == "state_binding":
        await db.execute(
            "UPDATE swe_cron_job_states SET task_session_id='changed'",
        )
    else:
        await db.execute(
            "UPDATE swe_cron_registration_journal SET progress_json='{}'",
        )
    resources, platform = AsyncMock(), PlatformClient()
    await MigrationTakeoverWorker(db, resources, platform).tick()
    assert platform.calls == []
    resources.prepare.assert_not_awaited()
    assert (
        await db.fetch_one("SELECT status FROM swe_cron_registration_journal")
    )["status"] == "failed"
    db.conn.close()


@pytest.mark.asyncio
async def test_async_migration_waits_for_platform_takeover_completion():
    import asyncio
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from swe.app.crons.migration_models import MigrationTaskRequest
    from swe.app.crons.migration_tasks import (
        MigrationTaskStore,
        MigrationTaskRunner,
    )
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db = database()
    add_async_tables(db)
    store = MigrationTaskStore(db)
    task_id = await store.create(MigrationTaskRequest(), "test")
    takeover = MigrationTakeover(db)
    takeover.run_id = task_id
    await MigrationRepository(db, takeover=takeover).import_snapshot(
        snapshot(),
    )
    progress = json.loads((await store.row(task_id))["result_json"])
    progress["scan_complete"] = True
    wait = asyncio.create_task(
        MigrationTaskRunner(store)._wait_takeover(task_id, takeover, progress),
    )
    await asyncio.sleep(0)
    assert not wait.done()
    await MigrationTakeoverWorker(db, AsyncMock(), PlatformClient()).tick()
    assert await asyncio.wait_for(wait, timeout=3) == "succeeded"
    assert (await takeover.summary())["completed"] == 1
    db.conn.close()


@pytest.mark.asyncio
async def test_unbound_job_remains_unbound_and_original_cron_is_preserved():
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db, candidate = database(), snapshot()
    spec = candidate.definition["spec_json"]
    for field in ("task_chat_id", "task_session_id"):
        spec["meta"].pop(field)
        candidate.state_patch[field] = None
    spec["request"]["session_id"] = None
    spec["dispatch"]["target"]["session_id"] = None
    candidate.definition["original_cron_expr"] = "0 12 * * *"
    await MigrationRepository(
        db,
        takeover=MigrationTakeover(db),
    ).import_snapshot(candidate)
    resources = AsyncMock()
    await MigrationTakeoverWorker(db, resources, PlatformClient()).tick()
    state = await db.fetch_one("SELECT * FROM swe_cron_job_states")
    definition = await db.fetch_one("SELECT * FROM swe_cron_jobs_v2")
    assert state["management_status"] == "ready"
    assert state["task_session_id"] is None
    assert state["task_chat_id"] is None
    assert definition["original_cron_expr"] == "0 12 * * *"
    resources.prepare.assert_not_awaited()
    db.conn.close()


@pytest.mark.asyncio
async def test_missing_batch_parent_fails_instead_of_registering_child_timer():
    from swe.app.crons.migration_repository import MigrationRepository
    from swe.app.crons.migration_takeover import MigrationTakeover
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )

    db = database()
    await MigrationRepository(
        db,
        takeover=MigrationTakeover(db),
    ).import_snapshot(
        snapshot("batch_enabled", job_id="child", parent="missing"),
    )
    platform, resources = PlatformClient(), AsyncMock()
    await MigrationTakeoverWorker(db, resources, platform).tick()
    operation = await db.fetch_one(
        "SELECT status,error_code FROM swe_cron_registration_journal",
    )
    assert operation["status"] == "failed"
    assert operation["error_code"] == "migration_parent_missing"
    assert platform.calls == []
    resources.prepare.assert_not_awaited()
    db.conn.close()


@pytest.mark.asyncio
async def test_real_migration_api_waits_for_scheduler_and_preserves_file_bindings(
    tmp_path,
    monkeypatch,
):
    import asyncio
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from swe.app.crons import migration_api
    from swe.app.routers import internal
    from scheduler.app.services.cron.managed.migration_takeover import (
        MigrationTakeoverWorker,
    )
    from tests.unit.app.test_cron_migration_source import job, write_jobs

    db = database()
    add_async_tables(db)
    original = job(
        id="stable-job",
        meta={
            "task_session_id": "stable-session",
            "task_chat_id": "stable-chat",
        },
        dispatch={
            "channel": "console",
            "target": {"user_id": "tenant-a", "session_id": "stable-session"},
        },
    )
    path = write_jobs(tmp_path, [original])
    before = path.read_bytes()
    app = FastAPI()
    app.include_router(migration_api.router, prefix="/api")
    app.state.db_connection = db
    monkeypatch.setattr(migration_api, "working_root", lambda: tmp_path)
    monkeypatch.setattr(internal, "_INTERNAL_TOKEN", "")
    resources, platform = AsyncMock(), PlatformClient()
    worker = MigrationTakeoverWorker(db, resources, platform)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        result = await client.post(
            "/api/internal/cron/migration/tasks",
            json={"operation": "import"},
        )
        assert result.status_code == 202, result.text
        task_id = result.json()["task_id"]

        async def finish():
            while not (
                await db.fetch_one(
                    "SELECT status FROM swe_cron_registration_journal",
                )
            ):
                await asyncio.sleep(0.01)
            await worker.tick()
            await app.state.cron_migration_tasks.wait()

        await asyncio.wait_for(finish(), timeout=5)
        response = await client.get(
            f"/api/internal/cron/migration/tasks/{task_id}",
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "succeeded", result
        assert result["progress"]["takeover"] == {
            "total": 1,
            "completed": 1,
            "failed": 0,
            "pending": 0,
        }
    state = await db.fetch_one("SELECT * FROM swe_cron_job_states")
    assert state["job_id"] == "stable-job"
    assert state["task_chat_id"] == "stable-chat"
    assert state["task_session_id"] == "stable-session"
    assert path.read_bytes() == before
    assert platform.calls.count("register") == 1
    resources.prepare.assert_not_awaited()
    db.conn.close()
