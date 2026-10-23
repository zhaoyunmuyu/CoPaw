# -*- coding: utf-8 -*-
"""业务只读客户端完整翻页、约束身份，不触碰旧管理器。"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_managed_reader_pages_and_preserves_bound_ids():
    from swe.app.crons.managed_query_client import ManagedCronQueryClient

    calls = []

    async def serve(request):
        calls.append(request)
        if request.url.params.get("cursor"):
            return httpx.Response(200, json={"items": [], "next_cursor": None})
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "original-id",
                        "name": "原任务",
                        "tenant_id": "alice",
                        "source_id": "bank",
                        "agent_id": "research",
                        "management_owner": "scheduler",
                        "meta": {
                            "task_session_id": "original-session",
                            "task_chat_id": "original-chat",
                        },
                    },
                ],
                "next_cursor": "page-2",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
        result = await ManagedCronQueryClient(
            "http://scheduler/api",
            http=http,
        ).list_jobs("alice", "bank", "research")
    assert len(calls) == 2
    assert all("/scheduler/cron/jobs" in request.url.path for request in calls)
    assert calls[0].headers["X-User-Id"] == "alice"
    assert result[0]["id"] == "original-id"
    assert result[0]["meta"]["task_session_id"] == "original-session"


@pytest.mark.asyncio
async def test_managed_reader_rejects_foreign_identity():
    from swe.app.crons.managed_query_client import ManagedCronQueryClient

    async def serve(request):
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "tenant_id": "bob",
                        "source_id": "bank",
                        "agent_id": "research",
                        "management_owner": "scheduler",
                    },
                ],
                "next_cursor": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
        with pytest.raises(ValueError, match="identity"):
            await ManagedCronQueryClient(
                "http://scheduler/api",
                http=http,
            ).list_jobs("alice", "bank", "research")


@pytest.mark.asyncio
async def test_progress_uses_database_execution_state_and_chat_binding():
    from datetime import datetime, timezone
    from swe.app.crons.managed_query_client import ManagedCronQueryClient

    async def serve(request):
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "original-id",
                        "name": "原任务",
                        "enabled": True,
                        "tenant_id": "alice",
                        "source_id": "bank",
                        "agent_id": "default",
                        "management_owner": "scheduler",
                        "task_type": "agent",
                        "request": {
                            "input": "报告",
                            "user_id": "alice",
                            "session_id": "original-session",
                        },
                        "schedule": {
                            "cron": "0 9 * * *",
                            "timezone": "Asia/Shanghai",
                        },
                        "dispatch": {
                            "channel": "console",
                            "target": {
                                "user_id": "alice",
                                "session_id": "original-session",
                            },
                        },
                        "state": {
                            "last_status": "success",
                            "last_run_at": "2020-01-01T01:00:01",
                        },
                        "task": {"chat_id": "original-chat"},
                    },
                ],
                "next_cursor": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
        tasks = await ManagedCronQueryClient(
            "http://scheduler/api",
            http=http,
        ).query_progress(
            "alice",
            "bank",
            "default",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    assert len(tasks) == 1
    assert tasks[0]["job_id"] == "original-id"
    assert tasks[0]["status"] == "completed"
    assert tasks[0]["meta"]["task_chat_id"] == "original-chat"
