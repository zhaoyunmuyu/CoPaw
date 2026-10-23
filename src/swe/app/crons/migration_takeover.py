# -*- coding: utf-8 -*-
"""在快照事务中登记 Scheduler 接管；不创建任务、会话或外部定时器。"""

import hashlib
import json
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from ...config.context import is_valid_identity_value

from .migration_repository import (
    MigrationOutcome,
    IDENTITY_FIELDS,
    IDENTITY_WHERE,
)
from .migration_source import PROVENANCE_KEY

JOURNAL = "swe_cron_registration_journal"


class MigrationTakeoverConflict(ValueError):
    pass


def encoded(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def provenance(definition):
    spec = definition.get("spec_json") or {}
    if isinstance(spec, (str, bytes)):
        spec = json.loads(spec)
    return (
        spec.get(PROVENANCE_KEY)
        or (spec.get("meta") or {}).get(PROVENANCE_KEY)
        or {}
    )


class MigrationTakeover:
    def __init__(self, db):
        self.db = db
        self.run_id = None

    async def check_schema(self):
        await self.db.execute(
            f"SELECT operation_id,active_key,tenant_id,source_id,agent_id,job_id,actor_id,action,request_id,request_hash,expected_version,payload_json,progress_json,status,stage,error_code,lease_owner,lease_until,version,created_at,updated_at FROM {JOURNAL} WHERE 1=0",
        )

    def operation_id(self, candidate):
        return str(
            uuid5(
                NAMESPACE_URL,
                "cron-snapshot-takeover:"
                + encoded(
                    [
                        *candidate.identity,
                        candidate.source_key,
                        candidate.fingerprint,
                    ],
                ),
            ),
        )

    async def existing(self, candidate, definition, state):
        if not definition or definition.get("management_owner") != "scheduler":
            return None
        meta = provenance(definition)
        if (
            not definition.get("imported_at")
            or meta.get("source_key") != candidate.source_key
            or meta.get("fingerprint") != candidate.fingerprint
        ):
            return None
        row = await self.db.fetch_one(
            f"SELECT * FROM {JOURNAL} WHERE operation_id=%s",
            (self.operation_id(candidate),),
        )
        if row is None:
            return None
        if state is None:
            raise MigrationTakeoverConflict("migration_state_missing")
        self._check_binding(
            json.loads(row["progress_json"])["prepared"]["spec"],
            state,
        )
        await self._observe(row["operation_id"])
        return MigrationOutcome(
            "unchanged",
            "already_scheduler_managed",
            operation_id=row["operation_id"],
            takeover_status=row["status"],
        )

    @staticmethod
    def _check_binding(spec, state):
        meta = spec.get("meta") or {}
        for field in ("task_chat_id", "task_session_id"):
            value = meta.get(field)
            if value is not None and value != state.get(field):
                raise MigrationTakeoverConflict(
                    "migration_session_binding_conflict",
                )
        session = state.get("task_session_id")
        if session:
            values = [
                (spec.get("request") or {}).get("session_id"),
                ((spec.get("dispatch") or {}).get("target") or {}).get(
                    "session_id",
                ),
            ]
            if any(value and value != session for value in values):
                raise MigrationTakeoverConflict(
                    "migration_session_binding_conflict",
                )

    async def enqueue(self, candidate, outcome):
        definition = await self.db.fetch_one(
            f"SELECT * FROM swe_cron_jobs_v2 WHERE {IDENTITY_WHERE} FOR UPDATE",
            candidate.identity,
        )
        state = await self.db.fetch_one(
            f"SELECT * FROM swe_cron_job_states WHERE {IDENTITY_WHERE} FOR UPDATE",
            candidate.identity,
        )
        if state.get("last_status") == "running":
            raise MigrationTakeoverConflict("migration_job_still_running")
        spec = (
            json.loads(definition["spec_json"])
            if isinstance(definition["spec_json"], str)
            else dict(definition["spec_json"])
        )
        self._check_binding(spec, state)
        if spec.get("id") != definition["job_id"]:
            raise MigrationTakeoverConflict("migration_job_identity_conflict")
        meta = dict(spec.get("meta") or {})
        audit = spec.pop(PROVENANCE_KEY, {})
        meta[PROVENANCE_KEY] = audit
        for field in ("external_job_id", "batch_dispatch_external_job_id"):
            meta.pop(field, None)
        for field in ("task_chat_id", "task_session_id"):
            if state.get(field) is not None:
                meta[field] = state[field]
        actor = (
            definition.get("creator_user_id")
            or meta.get("creator_user_id")
            or (spec.get("request") or {}).get("user_id")
            or definition["tenant_id"]
        )
        if not isinstance(actor, str) or not is_valid_identity_value(actor):
            raise MigrationTakeoverConflict("migration_actor_identity_invalid")
        meta["creator_user_id"] = actor
        spec["meta"] = meta
        op_id = self.operation_id(candidate)
        payload = {
            "spec": spec,
            "dispatch_state": state["dispatch_state"],
            "actor_is_manager": False,
            "migration_takeover": True,
            "migration_run_id": self.run_id,
            "original_binding": {
                "job_id": definition["job_id"],
                "task_chat_id": state.get("task_chat_id"),
                "task_session_id": state.get("task_session_id"),
            },
        }
        prepared = {
            "spec": spec,
            "chat_id": state.get("task_chat_id"),
            "session_id": state.get("task_session_id"),
        }
        progress = {
            "prepared": prepared,
            "prior_external_ids": {
                key: state.get(key)
                for key in (
                    "ordinary_external_job_id",
                    "batch_external_job_id",
                )
            },
        }
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        row = {
            "operation_id": op_id,
            "active_key": hashlib.sha256(
                encoded(list(candidate.identity)).encode(),
            ).hexdigest(),
            **dict(zip(IDENTITY_FIELDS, candidate.identity)),
            "actor_id": actor,
            "action": "update",
            "request_id": "migration-" + op_id,
            "request_hash": hashlib.sha256(
                encoded(payload).encode(),
            ).hexdigest(),
            "expected_version": definition["definition_version"],
            "payload_json": encoded(payload),
            "progress_json": encoded(progress),
            "status": "pending",
            "stage": "prepare",
            "error_code": None,
            "lease_owner": "",
            "lease_until": None,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        await self.db.execute(
            f"INSERT INTO {JOURNAL} ("
            + ",".join(row)
            + ") VALUES ("
            + ",".join("%s" for _ in row)
            + ")",
            tuple(row.values()),
        )
        await self.db.execute(
            f"UPDATE swe_cron_jobs_v2 SET management_owner=%s,creator_user_id=%s,migration_batch_id=%s WHERE {IDENTITY_WHERE}",
            ("scheduler", actor, candidate.fingerprint, *candidate.identity),
        )
        await self.db.execute(
            f"UPDATE swe_cron_job_states SET ordinary_external_job_id=NULL,batch_external_job_id=NULL,management_status=%s,management_version=management_version+1,management_updated_at=%s WHERE {IDENTITY_WHERE}",
            ("updating", now, *candidate.identity),
        )
        await self._observe(op_id)
        outcome.operation_id, outcome.takeover_status = op_id, "pending"
        return outcome

    async def _observe(self, operation_id):
        if not self.run_id:
            return
        target = "takeover:" + operation_id
        existing = await self.db.fetch_one(
            "SELECT target_id FROM swe_async_task_items WHERE task_id=%s AND target_id=%s",
            (self.run_id, target),
        )
        if existing is None:
            await self.db.execute(
                "INSERT INTO swe_async_task_items (task_id,target_id,status,result_json,updated_at) VALUES (%s,%s,%s,%s,%s)",
                (
                    self.run_id,
                    target,
                    "pending",
                    encoded({"operation_id": operation_id}),
                    datetime.now(timezone.utc).replace(tzinfo=None),
                ),
            )

    async def summary(self):
        rows = await self.db.fetch_all(
            f"SELECT j.status,COUNT(*) AS count FROM swe_async_task_items i JOIN {JOURNAL} j ON j.operation_id=JSON_UNQUOTE(JSON_EXTRACT(i.result_json,'$.operation_id')) WHERE i.task_id=%s AND i.target_id LIKE 'takeover:%%' GROUP BY j.status",
            (self.run_id,),
        )
        counts = {row["status"]: int(row["count"]) for row in rows}
        total = sum(counts.values())
        completed = counts.get("completed", 0)
        failed = counts.get("failed", 0) + counts.get("superseded", 0)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": total - completed - failed,
        }
