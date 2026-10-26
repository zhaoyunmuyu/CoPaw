# -*- coding: utf-8 -*-
"""验证接口异常可定位且不会将原始输入写入日志。"""

import logging

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from pymysql.err import OperationalError

from scheduler.app.api_logging import LoggedAPIRoute


def make_app():
    app = FastAPI()
    router = APIRouter(route_class=LoggedAPIRoute)

    @router.get("/jobs/{job_id}")
    async def database_failure(job_id: str):
        try:
            raise OperationalError(
                1205,
                "private-sql password=private-password",
            )
        except OperationalError as error:
            raise HTTPException(
                503,
                "cron_database_unavailable",
                headers={"Retry-After": "5"},
            ) from error

    def unavailable_service():
        raise RuntimeError("private-service-config")

    @router.post("/factory", dependencies=[Depends(unavailable_service)])
    async def factory_failure():
        return {"ok": True}

    @router.post("/operations")
    async def operation_failure():
        return JSONResponse(
            status_code=503,
            content={
                "operation": {
                    "operation_id": "operation-1",
                    "job_id": "job-1",
                    "status": "failed",
                    "stage": "prepare",
                    "error_code": "swe_prepare_failed",
                    "private": "private-response-body",
                },
            },
        )

    @router.get("/conflict")
    async def conflict():
        raise HTTPException(409, {"detail": "private-conflict"})

    class Input(BaseModel):
        count: int

    @router.post("/validate")
    async def validate(body: Input):
        return body

    @router.get("/ok")
    async def ok():
        return {"ok": True}

    @router.get("/stream")
    async def stream():
        async def content():
            yield b"private-stream-body"

        return StreamingResponse(content())

    app.include_router(router, prefix="/api")
    return app


def boundary_records(caplog):
    return [
        record
        for record in caplog.records
        if record.name == "scheduler.app.api_logging"
    ]


@pytest.mark.asyncio
async def test_http_error_preserves_response_and_logs_safe_cause(caplog):
    caplog.set_level(logging.WARNING)
    async with AsyncClient(
        transport=ASGITransport(app=make_app()),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/jobs/job-1?token=private-query",
            headers={
                "Cookie": "private-cookie",
                "Authorization": "Bearer private-token",
                "X-Request-ID": "request-1",
                "X-B3-TraceId": "abcdef0123456789",
            },
        )
    assert response.status_code == 503
    assert response.json() == {"detail": "cron_database_unavailable"}
    assert response.headers["Retry-After"] == "5"
    records = boundary_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    for expected in (
        "route=/api/jobs/{job_id}",
        "job_id=job-1",
        "request_id=request-1",
        "trace_id=abcdef0123456789",
        "http_status=503",
        "cron_database_unavailable",
        "OperationalError",
        "error_number=1205",
        "lock_wait_timeout",
        "database_failure",
    ):
        assert expected in records[0].getMessage()
    assert "private-" not in records[0].getMessage()


@pytest.mark.asyncio
async def test_unhandled_dependency_failure_is_not_rewritten(caplog):
    caplog.set_level(logging.WARNING)
    async with AsyncClient(
        transport=ASGITransport(app=make_app(), raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/factory")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert len(boundary_records(caplog)) == 1
    assert "RuntimeError" in caplog.text
    assert "unavailable_service" in caplog.text
    assert "private-service-config" not in caplog.text


@pytest.mark.asyncio
async def test_failed_operation_response_logs_receipt_not_body(caplog):
    caplog.set_level(logging.WARNING)
    async with AsyncClient(
        transport=ASGITransport(app=make_app()),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/operations")
    assert response.status_code == 503
    assert response.json()["operation"]["private"] == "private-response-body"
    assert len(boundary_records(caplog)) == 1
    for expected in (
        "operation_id=operation-1",
        "job_id=job-1",
        "stage=prepare",
        "error_code=swe_prepare_failed",
    ):
        assert expected in caplog.text
    assert "private-response-body" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path, status",
    [("/conflict", 409), ("/validate", 422)],
)
async def test_client_errors_are_warning_without_input(caplog, path, status):
    caplog.set_level(logging.WARNING)
    async with AsyncClient(
        transport=ASGITransport(app=make_app()),
        base_url="http://test",
    ) as client:
        response = (
            await client.get("/api/conflict")
            if path == "/conflict"
            else await client.post(
                "/api/validate",
                json={"count": "private-input"},
            )
        )
    assert response.status_code == status
    records = boundary_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert "private-" not in records[0].getMessage()


@pytest.mark.asyncio
async def test_success_and_stream_are_unchanged_without_error_log(caplog):
    caplog.set_level(logging.WARNING)
    async with AsyncClient(
        transport=ASGITransport(app=make_app()),
        base_url="http://test",
    ) as client:
        assert (await client.get("/api/ok")).json() == {"ok": True}
        assert (await client.get("/api/stream")).text == "private-stream-body"
    assert not boundary_records(caplog)


def test_all_new_routers_install_boundary_without_touching_legacy():
    from scheduler.app.routers import api_router

    for route in api_router.routes:
        if "managed" in " ".join(route.tags) or any(
            tag in route.tags
            for tag in (
                "external-cron",
                "cron-calendar",
                "system-cron",
                "system-cron-execution",
                "system-cron-internal",
            )
        ):
            assert isinstance(route, LoggedAPIRoute), route.path
        else:
            assert not isinstance(route, LoggedAPIRoute), route.path


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["query", "callback", "management_factory"],
)
async def test_real_router_faults_no_longer_silently_return_503(
    caplog,
    monkeypatch,
    failure,
):
    from scheduler.app.routers import (
        managed_callbacks,
        managed_cron,
        managed_cron_management,
    )
    from scheduler.app.services.cron.managed.repository import (
        ManagedCronRepository,
    )

    class BrokenDatabase:
        async def fetch_all(self, *_args, **_kwargs):
            raise OperationalError(1205, "private-sql")

    class BrokenCallback:
        async def accept(self, *_args):
            raise RuntimeError("private-callback-error")

    def broken_factory():
        raise RuntimeError("private-connection-string")

    app = FastAPI()
    for router in (
        managed_cron.router,
        managed_callbacks.router,
        managed_cron_management.router,
    ):
        app.include_router(router, prefix="/api")
    app.dependency_overrides[managed_cron.get_managed_repository] = (
        lambda: ManagedCronRepository(BrokenDatabase())
    )
    app.dependency_overrides[managed_callbacks.scheduling_service] = (
        BrokenCallback
    )
    monkeypatch.setattr(
        managed_cron_management,
        "get_db_connection",
        broken_factory,
    )
    caplog.set_level(logging.WARNING)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-User-Id": "alice", "X-Source-Id": "bank"},
    ) as client:
        if failure == "query":
            response = await client.get("/api/scheduler/cron/jobs")
            expected = "cron_database_unavailable"
        elif failure == "callback":
            response = await client.post(
                "/api/scheduler/cron/ordinary/callback",
                json={"job_id": "job-1"},
            )
            expected = "cron_callback_storage_unavailable"
        else:
            response = await client.post(
                "/api/scheduler/cron/jobs",
                json={"request_id": "create-1", "spec": {}},
            )
            expected = "cron_management_service_unavailable"
    assert response.status_code == 503
    assert response.json() == {"detail": expected}
    assert len(boundary_records(caplog)) == 1
    assert expected in caplog.text
    assert "private-" not in caplog.text


@pytest.mark.asyncio
async def test_logger_failure_cannot_replace_original_response(monkeypatch):
    from scheduler.app import api_logging

    def fail_log(*_args, **_kwargs):
        raise RuntimeError("logging unavailable")

    monkeypatch.setattr(api_logging.logger, "log", fail_log)
    async with AsyncClient(
        transport=ASGITransport(app=make_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/jobs/job-1")
        receipt = await client.post("/api/operations")
    assert response.status_code == 503
    assert response.json() == {"detail": "cron_database_unavailable"}
    assert receipt.status_code == 503
    assert receipt.json()["operation"]["operation_id"] == "operation-1"


@pytest.mark.asyncio
async def test_log_fields_reject_newlines_and_do_not_dump_raw_path(caplog):
    caplog.set_level(logging.WARNING)
    async with AsyncClient(
        transport=ASGITransport(app=make_app()),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/jobs/private-path%0Ainjected",
            headers={"X-Request-ID": "private-request\ninjected"},
        )
    assert response.status_code == 503
    assert len(boundary_records(caplog)) == 1
    assert "private-" not in caplog.text
    assert "job_id=-" in caplog.text
    assert "request_id=-" in caplog.text
