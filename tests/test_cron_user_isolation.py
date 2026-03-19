# -*- coding: utf-8 -*-
"""Tests for Cron user isolation feature.

This test module verifies that:
1. Each user has isolated cron jobs (user A cannot see user B's jobs)
2. Cron jobs are stored in user-specific directories
3. Default user ("default") works for backward compatibility
4. Cron manager correctly handles per-user state
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

import pytest

from copaw.app.crons.manager import CronManager
from copaw.app.crons.models import (
    CronJobSpec,
    ScheduleSpec,
    DispatchSpec,
    DispatchTarget,
    JobRuntimeSpec,
)
from copaw.app.crons.repo.json_repo import JsonJobRepository


@pytest.fixture
def temp_base_dir() -> Path:
    """Create a temporary base directory for tests."""
    with tempfile.TemporaryDirectory(prefix="copaw_cron_test_") as tmpdir:
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
async def cron_manager(
    mock_runner: Any,
    mock_channel_manager: Any,
) -> AsyncGenerator[CronManager, None]:
    """Create a CronManager instance for testing."""
    manager = CronManager(
        runner=mock_runner,
        channel_manager=mock_channel_manager,
        timezone="UTC",
    )
    await manager.start()
    yield manager
    await manager.stop()


def create_test_job(name: str = "test-job") -> CronJobSpec:
    """Create a test cron job spec."""
    target = DispatchTarget(user_id="test_user", session_id="test_session")
    return CronJobSpec(
        id=str(uuid.uuid4()),
        name=name,
        enabled=True,
        schedule=ScheduleSpec(
            type="cron",
            cron="0 9 * * *",
            timezone="UTC",
        ),
        task_type="text",
        text="Test message",
        dispatch=DispatchSpec(
            type="channel",
            channel="console",
            target=target,
        ),
        runtime=JobRuntimeSpec(),
    )


@pytest.mark.asyncio
async def test_user_isolated_jobs(
    temp_base_dir: Path,
    cron_manager: CronManager,
) -> None:
    """Test that users have isolated cron jobs."""
    # Override the working dir by patching get_jobs_path
    from copaw.config import utils as config_utils

    original_get_jobs_path = config_utils.get_jobs_path

    def mock_get_jobs_path(user_id: str | None = None) -> Path:
        if user_id is not None:
            return temp_base_dir / user_id / "jobs.json"
        return temp_base_dir / "jobs.json"

    config_utils.get_jobs_path = mock_get_jobs_path

    try:
        # Create jobs for user_a
        job_a1 = create_test_job("user-a-job-1")
        job_a2 = create_test_job("user-a-job-2")

        # Create job for user_b
        job_b1 = create_test_job("user-b-job-1")

        # Create jobs
        await cron_manager.create_or_replace_job(job_a1, "user_a")
        await cron_manager.create_or_replace_job(job_a2, "user_a")
        await cron_manager.create_or_replace_job(job_b1, "user_b")

        # Verify user_a can only see their own jobs
        user_a_jobs = await cron_manager.list_jobs("user_a")
        assert len(user_a_jobs) == 2
        user_a_job_names = {j.name for j in user_a_jobs}
        assert "user-a-job-1" in user_a_job_names
        assert "user-a-job-2" in user_a_job_names
        assert "user-b-job-1" not in user_a_job_names

        # Verify user_b can only see their own jobs
        user_b_jobs = await cron_manager.list_jobs("user_b")
        assert len(user_b_jobs) == 1
        assert user_b_jobs[0].name == "user-b-job-1"

        # Verify job files are stored in separate directories
        user_a_jobs_path = temp_base_dir / "user_a" / "jobs.json"
        user_b_jobs_path = temp_base_dir / "user_b" / "jobs.json"

        assert user_a_jobs_path.exists()
        assert user_b_jobs_path.exists()

        # Verify file contents are isolated
        user_a_data = json.loads(user_a_jobs_path.read_text())
        user_b_data = json.loads(user_b_jobs_path.read_text())

        assert len(user_a_data["jobs"]) == 2
        assert len(user_b_data["jobs"]) == 1
    finally:
        config_utils.get_jobs_path = original_get_jobs_path


@pytest.mark.asyncio
async def test_delete_job_isolation(
    temp_base_dir: Path,
    cron_manager: CronManager,
) -> None:
    """Test that deleting a job only affects the user's own jobs."""
    from copaw.config import utils as config_utils

    original_get_jobs_path = config_utils.get_jobs_path

    def mock_get_jobs_path(user_id: str | None = None) -> Path:
        if user_id is not None:
            return temp_base_dir / user_id / "jobs.json"
        return temp_base_dir / "jobs.json"

    config_utils.get_jobs_path = mock_get_jobs_path

    try:
        # Create same-named job for two users
        job_a = create_test_job("shared-name")
        job_b = create_test_job("shared-name")

        await cron_manager.create_or_replace_job(job_a, "user_a")
        await cron_manager.create_or_replace_job(job_b, "user_b")

        # Delete job for user_a
        deleted = await cron_manager.delete_job(job_a.id, "user_a")
        assert deleted is True

        # Verify user_a's job is deleted
        user_a_jobs = await cron_manager.list_jobs("user_a")
        assert len(user_a_jobs) == 0

        # Verify user_b's job still exists
        user_b_jobs = await cron_manager.list_jobs("user_b")
        assert len(user_b_jobs) == 1
        assert user_b_jobs[0].id == job_b.id
    finally:
        config_utils.get_jobs_path = original_get_jobs_path


@pytest.mark.asyncio
async def test_get_job_isolation(
    temp_base_dir: Path,
    cron_manager: CronManager,
) -> None:
    """Test that getting a job returns None for other users' jobs."""
    from copaw.config import utils as config_utils

    original_get_jobs_path = config_utils.get_jobs_path

    def mock_get_jobs_path(user_id: str | None = None) -> Path:
        if user_id is not None:
            return temp_base_dir / user_id / "jobs.json"
        return temp_base_dir / "jobs.json"

    config_utils.get_jobs_path = mock_get_jobs_path

    try:
        job_a = create_test_job()
        await cron_manager.create_or_replace_job(job_a, "user_a")

        # User_a can get their own job
        found = await cron_manager.get_job(job_a.id, "user_a")
        assert found is not None
        assert found.id == job_a.id

        # User_b cannot see user_a's job
        not_found = await cron_manager.get_job(job_a.id, "user_b")
        assert not_found is None
    finally:
        config_utils.get_jobs_path = original_get_jobs_path


@pytest.mark.asyncio
async def test_default_user_backward_compat(
    temp_base_dir: Path,
    cron_manager: CronManager,
) -> None:
    """Test that default user works for backward compatibility."""
    from copaw.config import utils as config_utils

    original_get_jobs_path = config_utils.get_jobs_path

    def mock_get_jobs_path(user_id: str | None = None) -> Path:
        if user_id is not None:
            return temp_base_dir / user_id / "jobs.json"
        return temp_base_dir / "jobs.json"

    config_utils.get_jobs_path = mock_get_jobs_path

    try:
        job = create_test_job("default-user-job")

        # Create job for default user
        await cron_manager.create_or_replace_job(job, "default")

        # Verify job exists
        jobs = await cron_manager.list_jobs("default")
        assert len(jobs) == 1
        assert jobs[0].name == "default-user-job"

        # Verify file is in default directory
        default_jobs_path = temp_base_dir / "default" / "jobs.json"
        assert default_jobs_path.exists()
    finally:
        config_utils.get_jobs_path = original_get_jobs_path


@pytest.mark.asyncio
async def test_state_isolation(
    temp_base_dir: Path,
    cron_manager: CronManager,
) -> None:
    """Test that job states are isolated per user."""
    from copaw.config import utils as config_utils

    original_get_jobs_path = config_utils.get_jobs_path

    def mock_get_jobs_path(user_id: str | None = None) -> Path:
        if user_id is not None:
            return temp_base_dir / user_id / "jobs.json"
        return temp_base_dir / "jobs.json"

    config_utils.get_jobs_path = mock_get_jobs_path

    try:
        job_a = create_test_job("job-a")
        job_b = create_test_job("job-b")

        # Create jobs for different users
        await cron_manager.create_or_replace_job(job_a, "user_a")
        await cron_manager.create_or_replace_job(job_b, "user_b")

        # Get states
        state_a = cron_manager.get_state(job_a.id, "user_a")
        state_b = cron_manager.get_state(job_b.id, "user_b")

        # States should be separate instances
        assert state_a is not state_b

        # Modify state_a and verify state_b is unaffected
        state_a.last_status = "running"
        assert state_b.last_status is None
    finally:
        config_utils.get_jobs_path = original_get_jobs_path


@pytest.mark.asyncio
async def test_repo_for_user(temp_base_dir: Path) -> None:
    """Test that _get_repo_for_user returns correct repos."""
    from copaw.config import utils as config_utils

    original_get_jobs_path = config_utils.get_jobs_path

    def mock_get_jobs_path(user_id: str | None = None) -> Path:
        if user_id is not None:
            return temp_base_dir / user_id / "jobs.json"
        return temp_base_dir / "jobs.json"

    config_utils.get_jobs_path = mock_get_jobs_path

    try:
        manager = CronManager(runner=None, channel_manager=None)  # type: ignore

        repo_a = manager._get_repo_for_user("user_a")
        repo_b = manager._get_repo_for_user("user_b")

        # Should return different repos
        assert repo_a is not repo_b

        # Should point to correct paths
        assert repo_a.path == temp_base_dir / "user_a" / "jobs.json"
        assert repo_b.path == temp_base_dir / "user_b" / "jobs.json"
    finally:
        config_utils.get_jobs_path = original_get_jobs_path


@pytest.mark.asyncio
async def test_job_update_isolation(
    temp_base_dir: Path,
    cron_manager: CronManager,
) -> None:
    """Test that updating a job doesn't affect other users."""
    from copaw.config import utils as config_utils

    original_get_jobs_path = config_utils.get_jobs_path

    def mock_get_jobs_path(user_id: str | None = None) -> Path:
        if user_id is not None:
            return temp_base_dir / user_id / "jobs.json"
        return temp_base_dir / "jobs.json"

    config_utils.get_jobs_path = mock_get_jobs_path

    try:
        job_a = create_test_job("original-name")
        await cron_manager.create_or_replace_job(job_a, "user_a")

        job_b = create_test_job("original-name")
        await cron_manager.create_or_replace_job(job_b, "user_b")

        # Update user_a's job
        updated_job = job_a.model_copy(update={"name": "updated-name"})
        await cron_manager.create_or_replace_job(updated_job, "user_a")

        # Verify user_a's job is updated
        user_a_job = await cron_manager.get_job(job_a.id, "user_a")
        assert user_a_job is not None
        assert user_a_job.name == "updated-name"

        # Verify user_b's job is NOT updated
        user_b_job = await cron_manager.get_job(job_b.id, "user_b")
        assert user_b_job is not None
        assert user_b_job.name == "original-name"
    finally:
        config_utils.get_jobs_path = original_get_jobs_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
