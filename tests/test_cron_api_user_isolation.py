# -*- coding: utf-8 -*-
"""Integration tests for Cron API user isolation.

Tests the HTTP API endpoints with X-User-ID header.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from copaw.app.crons.api import router as cron_router
from copaw.app.crons.manager import CronManager


@pytest.fixture
def temp_base_dir() -> Path:
    """Create a temporary base directory for tests."""
    with tempfile.TemporaryDirectory(prefix="copaw_cron_api_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_runner() -> Any:
    """Mock runner for testing."""

    class MockRunner:
        async def stream_query(self, req: dict) -> Any:
            yield {"type": "text", "content": "test response"}

    return MockRunner()


@pytest.fixture
def mock_channel_manager() -> Any:
    """Mock channel manager for testing."""

    class MockChannelManager:
        async def send_text(self, **kwargs) -> None:
            pass

        async def send_event(self, **kwargs) -> None:
            pass

    return MockChannelManager()


@pytest.fixture
async def client(
    temp_base_dir: Path,
    mock_runner: Any,
    mock_channel_manager: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with cron routes."""
    from copaw.config import utils as config_utils

    # Patch get_jobs_path
    original_get_jobs_path = config_utils.get_jobs_path

    def mock_get_jobs_path(user_id: str | None = None) -> Path:
        if user_id is not None:
            return temp_base_dir / user_id / "jobs.json"
        return temp_base_dir / "jobs.json"

    config_utils.get_jobs_path = mock_get_jobs_path

    # Create cron manager
    cron_manager = CronManager(
        runner=mock_runner,
        channel_manager=mock_channel_manager,
        timezone="UTC",
    )

    await cron_manager.start()

    application = FastAPI()
    application.state.cron_manager = cron_manager
    application.include_router(cron_router, prefix="/api")

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as ac:
        yield ac

    await cron_manager.stop()
    config_utils.get_jobs_path = original_get_jobs_path


@pytest.mark.asyncio
async def test_list_jobs_with_user_id(client: AsyncClient) -> None:
    """Test listing jobs with X-User-ID header."""
    # Create job for user_a
    job_spec = {
        "name": "user-a-job",
        "enabled": True,
        "schedule": {
            "type": "cron",
            "cron": "0 9 * * *",
            "timezone": "UTC",
        },
        "task_type": "text",
        "text": "Test message",
        "dispatch": {
            "type": "channel",
            "channel": "console",
            "target": {"user_id": "test", "session_id": "test"},
        },
        "runtime": {
            "max_concurrency": 1,
            "timeout_seconds": 120,
            "misfire_grace_seconds": 60,
        },
    }

    response = await client.post(
        "/api/cron/jobs",
        json=job_spec,
        headers={"X-User-ID": "user_a"},
    )
    assert response.status_code == 200
    job_a_id = response.json()["id"]

    # Create job for user_b
    response = await client.post(
        "/api/cron/jobs",
        json={**job_spec, "name": "user-b-job"},
        headers={"X-User-ID": "user_b"},
    )
    assert response.status_code == 200
    job_b_id = response.json()["id"]

    # List jobs for user_a - should only see user_a's job
    response = await client.get(
        "/api/cron/jobs", headers={"X-User-ID": "user_a"}
    )
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["name"] == "user-a-job"
    assert jobs[0]["id"] == job_a_id

    # List jobs for user_b - should only see user_b's job
    response = await client.get(
        "/api/cron/jobs", headers={"X-User-ID": "user_b"}
    )
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["name"] == "user-b-job"
    assert jobs[0]["id"] == job_b_id

    # Default user (no header) should have no jobs
    response = await client.get("/api/cron/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 0


@pytest.mark.asyncio
async def test_get_job_with_user_id(client: AsyncClient) -> None:
    """Test getting a specific job with X-User-ID header."""
    # Create job
    job_spec = {
        "name": "test-job",
        "enabled": True,
        "schedule": {
            "type": "cron",
            "cron": "0 9 * * *",
            "timezone": "UTC",
        },
        "task_type": "text",
        "text": "Test message",
        "dispatch": {
            "type": "channel",
            "channel": "console",
            "target": {"user_id": "test", "session_id": "test"},
        },
        "runtime": {
            "max_concurrency": 1,
            "timeout_seconds": 120,
            "misfire_grace_seconds": 60,
        },
    }

    response = await client.post(
        "/api/cron/jobs",
        json=job_spec,
        headers={"X-User-ID": "user_a"},
    )
    assert response.status_code == 200
    job_id = response.json()["id"]

    # Get job with correct user
    response = await client.get(
        f"/api/cron/jobs/{job_id}",
        headers={"X-User-ID": "user_a"},
    )
    assert response.status_code == 200
    assert response.json()["spec"]["name"] == "test-job"

    # Get job with wrong user - should 404
    response = await client.get(
        f"/api/cron/jobs/{job_id}",
        headers={"X-User-ID": "user_b"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_job_with_user_id(client: AsyncClient) -> None:
    """Test deleting a job with X-User-ID header."""
    job_spec = {
        "name": "delete-test-job",
        "enabled": True,
        "schedule": {
            "type": "cron",
            "cron": "0 9 * * *",
            "timezone": "UTC",
        },
        "task_type": "text",
        "text": "Test message",
        "dispatch": {
            "type": "channel",
            "channel": "console",
            "target": {"user_id": "test", "session_id": "test"},
        },
        "runtime": {
            "max_concurrency": 1,
            "timeout_seconds": 120,
            "misfire_grace_seconds": 60,
        },
    }

    # Create job for user_a
    response = await client.post(
        "/api/cron/jobs",
        json=job_spec,
        headers={"X-User-ID": "user_a"},
    )
    assert response.status_code == 200
    job_id = response.json()["id"]

    # Delete with wrong user - should 404
    response = await client.delete(
        f"/api/cron/jobs/{job_id}",
        headers={"X-User-ID": "user_b"},
    )
    assert response.status_code == 404

    # Job should still exist for user_a
    response = await client.get(
        f"/api/cron/jobs/{job_id}",
        headers={"X-User-ID": "user_a"},
    )
    assert response.status_code == 200

    # Delete with correct user - should succeed
    response = await client.delete(
        f"/api/cron/jobs/{job_id}",
        headers={"X-User-ID": "user_a"},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    # Job should no longer exist
    response = await client.get(
        f"/api/cron/jobs/{job_id}",
        headers={"X-User-ID": "user_a"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_default_user_header(client: AsyncClient) -> None:
    """Test that missing X-User-ID header defaults to 'default' user."""
    job_spec = {
        "name": "default-user-job",
        "enabled": True,
        "schedule": {
            "type": "cron",
            "cron": "0 9 * * *",
            "timezone": "UTC",
        },
        "task_type": "text",
        "text": "Test message",
        "dispatch": {
            "type": "channel",
            "channel": "console",
            "target": {"user_id": "test", "session_id": "test"},
        },
        "runtime": {
            "max_concurrency": 1,
            "timeout_seconds": 120,
            "misfire_grace_seconds": 60,
        },
    }

    # Create job without header
    response = await client.post("/api/cron/jobs", json=job_spec)
    assert response.status_code == 200
    job_id = response.json()["id"]

    # Get job without header (should use default)
    response = await client.get(f"/api/cron/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["spec"]["name"] == "default-user-job"

    # List jobs without header
    response = await client.get("/api/cron/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["name"] == "default-user-job"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
