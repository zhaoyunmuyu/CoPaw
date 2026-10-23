# -*- coding: utf-8 -*-
"""SWE 业务入口只读 Scheduler；不读取旧文件任务或管理器。"""

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx

from ...config.context import is_valid_identity_value
from .models import CronJobSpec, CronJobState
from .monitor_sync_client import get_scheduler_api_url
from .task_progress import TaskProgressView


class ManagedCronQueryClient:
    def __init__(self, base_url=None, *, http=None, headers=None):
        self.base_url = (base_url or get_scheduler_api_url()).rstrip("/")
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("cron_scheduler_url_invalid")
        self.http = http
        self.headers = {
            name: value
            for name, value in (headers or {}).items()
            if name.lower()
            in {
                "authorization",
                "x-header-cookie",
                "b3",
                "x-b3-traceid",
                "x-b3-spanid",
            }
        }

    @asynccontextmanager
    async def _client(self):
        if self.http is not None:
            yield self.http
        else:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=False,
            ) as client:
                yield client

    async def list_jobs(self, tenant, source, agent="default"):
        identity = (tenant, source, agent)
        if any(not is_valid_identity_value(value) for value in identity):
            raise ValueError("cron_query_identity_invalid")
        headers = {
            **self.headers,
            "X-User-Id": tenant,
            "X-Tenant-Id": tenant,
            "X-Source-Id": source,
            "X-Agent-Id": agent,
        }
        result, cursors, identifiers = [], set(), set()
        cursor = None
        async with self._client() as client:
            while True:
                params = {"limit": 200, "include_deleted": "false"}
                if cursor:
                    params["cursor"] = cursor
                response = await client.get(
                    self.base_url + "/scheduler/cron/jobs",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("items"),
                    list,
                ):
                    raise ValueError("cron_query_response_invalid")
                for job in payload["items"]:
                    self._validate(job, identity, identifiers)
                    result.append(job)
                cursor = payload.get("next_cursor")
                if cursor is None:
                    return result
                if (
                    not isinstance(cursor, str)
                    or not cursor
                    or cursor in cursors
                ):
                    raise ValueError("cron_query_cursor_invalid")
                cursors.add(cursor)

    @staticmethod
    def _validate(job, identity, identifiers):
        if (
            not isinstance(job, dict)
            or job.get("management_owner") != "scheduler"
            or tuple(
                job.get(key) for key in ("tenant_id", "source_id", "agent_id")
            )
            != identity
        ):
            raise ValueError("cron_query_identity_conflict")
        identifier = job.get("id")
        if not isinstance(identifier, str) or identifier in identifiers:
            raise ValueError("cron_query_identity_conflict")
        identifiers.add(identifier)

    async def query_progress(self, user_id, source_id, agent_id, date):
        jobs = await self.list_jobs(user_id, source_id, agent_id)
        view, tasks = TaskProgressView(), []
        for row in jobs:
            spec = CronJobSpec.model_validate(row)
            if not spec.enabled or spec.task_type not in {"agent", "workflow"}:
                continue
            state = CronJobState.model_validate(row.get("state") or {})
            for scheduled in view._calculate_run_times_on_date(spec, date):
                status = view._determine_task_status(scheduled, state, date)
                text, info = view._build_task_status_display(
                    status,
                    scheduled,
                    state.last_run_at,
                )
                task = row.get("task") or {}
                tasks.append(
                    {
                        "job_id": spec.id,
                        "task_name": spec.name,
                        "status": status,
                        "status_text": text,
                        "time_info": info,
                        "scheduled_time": scheduled,
                        "meta": {
                            **spec.meta,
                            "task_chat_id": task.get("chat_id")
                            or spec.meta.get("task_chat_id", ""),
                        },
                    },
                )
        return sorted(tasks, key=lambda task: task["scheduled_time"])
