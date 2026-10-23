# -*- coding: utf-8 -*-
"""恢复共库中的迁移接管意图，不重建原任务或会话。"""

import json
import logging

from .identity import CallerIdentity
from .management import ManagementService
from .operations import JOURNAL, utc_now

logger = logging.getLogger(__name__)
KEYS = ("tenant_id", "source_id", "agent_id", "job_id")
WHERE = " AND ".join(f"{key}=%s" for key in KEYS)


class MigrationTakeoverWorker:
    def __init__(self, db, resources, platform, *, limit=32):
        self.db = db
        self.service = ManagementService(db, resources, platform)
        self.limit = limit
        self.after = ""

    async def tick(self):
        rows = await self._rows(self.after)
        if not rows and self.after:
            rows = await self._rows("")
        if rows:
            self.after = rows[-1]["operation_id"]
        count = 0
        for row in rows:
            try:
                count += await self._process(row)
            except Exception as error:
                logger.warning(
                    "迁移接管本轮未完成 operation_id=%s error_type=%s",
                    row["operation_id"],
                    type(error).__name__,
                )
        return count

    async def _rows(self, after):
        return await self.db.fetch_all(
            f"SELECT * FROM {JOURNAL} WHERE operation_id>%s AND action='update' AND status IN ('pending','running') AND JSON_EXTRACT(payload_json,'$.migration_takeover')=true AND (lease_until IS NULL OR lease_until<=%s) ORDER BY operation_id LIMIT %s",
            (after, utc_now(), self.limit),
        )

    async def _process(self, row):
        payload = json.loads(row["payload_json"])
        caller = CallerIdentity(
            row["tenant_id"],
            row["source_id"],
            row["agent_id"],
            row["actor_id"],
        )
        parent = await self._parent(row, payload)
        if parent == "waiting":
            return False
        if parent:
            operation = await self.service.store.claim(
                caller,
                row["job_id"],
                row["operation_id"],
            )
            if operation is not None:
                await self.service.store.checkpoint(
                    operation,
                    "migration_parent",
                    json.loads(operation["progress_json"]),
                    status="failed",
                    error=parent,
                )
            return True
        await self.service.retry(caller, row["job_id"], row["operation_id"])
        return True

    async def _parent(self, row, payload):
        if payload["dispatch_state"] == "ordinary":
            return None
        definition = await self.db.fetch_one(
            f"SELECT * FROM swe_cron_jobs_v2 WHERE {WHERE}",
            tuple(row[key] for key in KEYS),
        )
        if not definition.get("parent_job_id"):
            meta = payload["spec"].get("meta") or {}
            return (
                "migration_parent_identity_missing"
                if meta.get("broadcast_source_job_id")
                else None
            )
        key = tuple(definition.get("parent_" + name) for name in KEYS)
        if not all(key) or key == tuple(row[name] for name in KEYS):
            return "migration_parent_identity_invalid"
        state = await self.db.fetch_one(
            f"SELECT management_status FROM swe_cron_job_states WHERE {WHERE}",
            key,
        )
        if state and state["management_status"] == "ready":
            return None
        if state and str(state["management_status"]).endswith("failed"):
            return "migration_parent_failed"
        if await self._scan_complete(payload):
            if state is None:
                return "migration_parent_missing"
            if state["management_status"] in {None, "imported", "deleted"}:
                return "migration_parent_not_managed"
        return "waiting"

    async def _scan_complete(self, payload):
        run_id = payload.get("migration_run_id")
        if run_id is None:
            return True
        task = await self.db.fetch_one(
            "SELECT status,result_json FROM swe_async_tasks WHERE task_id=%s",
            (run_id,),
        )
        return (
            task is None
            or task["status"] not in {"queued", "running"}
            or bool(json.loads(task["result_json"]).get("scan_complete"))
        )
