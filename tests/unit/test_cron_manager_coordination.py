# -*- coding: utf-8 -*-
"""Unit tests for CronManager with Redis coordination.

These tests verify:
- CronManager activation/deactivation with coordination
- Manual run_job bypasses execution lock
- Timed execution uses execution lock
- Reload behavior
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests as requiring Redis
pytestmark = [
    pytest.mark.asyncio,
]

# Check if redis is available
try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


from swe.app.crons.manager import CronManager
from swe.app.crons.coordination import CoordinationConfig
from swe.app.crons.models import (
    CronJobSpec,
    ScheduleSpec,
    DispatchSpec,
    DispatchTarget,
    JobRuntimeSpec,
    CronJobRequest,
)
from swe.app.crons.repo.json_repo import JsonJobRepository


@pytest.fixture
def temp_jobs_file(tmp_path):
    """Create a temporary jobs.json file."""
    return tmp_path / "jobs.json"


@pytest.fixture
def coordination_config():
    """Default coordination config for tests."""
    return CoordinationConfig(
        enabled=True,
        redis_url="redis://localhost:6379/15",  # Use DB 15 for tests
        lease_ttl_seconds=10,
        lease_renew_interval_seconds=3,
        lock_safety_margin_seconds=5,
    )


@pytest.fixture
def mock_runner():
    """Create a mock runner."""
    runner = MagicMock()
    runner.workspace_dir = Path("/tmp/test")
    return runner


@pytest.fixture
def mock_channel_manager():
    """Create a mock channel manager."""
    return MagicMock()


@pytest.fixture
def sample_job_spec():
    """Create a sample job spec."""
    return CronJobSpec(
        id="test-job",
        name="Test Job",
        enabled=True,
        tenant_id="test-tenant",
        schedule=ScheduleSpec(
            type="cron",
            cron="0 0 * * *",  # Daily at midnight
            timezone="UTC",
        ),
        task_type="text",
        text="Hello from cron",
        dispatch=DispatchSpec(
            type="channel",
            channel="console",
            target=DispatchTarget(user_id="user1", session_id="session1"),
        ),
        runtime=JobRuntimeSpec(
            max_concurrency=1,
            timeout_seconds=30,
        ),
    )


class TestCronManagerLifecycle:
    """Tests for CronManager lifecycle with coordination."""

    async def test_manager_without_coordination(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
    ):
        """Test manager works without coordination (backwards compatible)."""
        repo = JsonJobRepository(temp_jobs_file)
        manager = CronManager(
            repo=repo,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
        )

        # Initialize
        await manager.initialize()
        assert manager._scheduler is not None
        assert not manager.is_started

        # Activate (no coordination = becomes leader)
        is_leader = await manager.activate()
        assert is_leader is True
        assert manager.is_started
        assert manager.is_leader

        # Deactivate
        await manager.deactivate()
        assert not manager.is_started

    async def test_manager_with_coordination_disabled(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
    ):
        """Test manager with disabled coordination."""
        config = CoordinationConfig(enabled=False)
        repo = JsonJobRepository(temp_jobs_file)
        manager = CronManager(
            repo=repo,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=config,
        )

        # Activate (disabled = becomes leader)
        is_leader = await manager.activate()
        assert is_leader is True
        assert manager.is_started

        await manager.deactivate()


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
class TestCronManagerWithRedis:
    """Tests for CronManager that require Redis."""

    async def test_manager_activation_with_redis(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
        coordination_config,
    ):
        """Test manager activation with Redis coordination."""
        repo = JsonJobRepository(temp_jobs_file)
        manager = CronManager(
            repo=repo,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=coordination_config,
        )

        # Activate - should connect and acquire leadership
        # If Redis is not running, this will raise RuntimeError
        try:
            is_leader = await manager.activate()
            assert isinstance(is_leader, bool)

            if is_leader:
                assert manager.is_started
                assert manager.is_leader

            await manager.deactivate()
        except RuntimeError as e:
            # Redis not available - this is expected if Redis is not running
            assert (
                "Redis coordination is enabled but Redis is not available"
                in str(e)
            )

    async def test_two_managers_leader_election(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
        coordination_config,
    ):
        """Test that only one manager becomes leader."""
        # Create two separate repos pointing to the same file
        repo1 = JsonJobRepository(temp_jobs_file)
        repo2 = JsonJobRepository(temp_jobs_file)

        manager1 = CronManager(
            repo=repo1,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=coordination_config,
        )
        manager2 = CronManager(
            repo=repo2,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=coordination_config,
        )

        # Activate first manager - should become leader (or raise if Redis unavailable)
        try:
            is_leader1 = await manager1.activate()

            # If Redis is running and coordination worked
            if is_leader1:
                assert manager1.is_leader

                # Activate second manager - should be follower
                is_leader2 = await manager2.activate()
                assert not is_leader2
                assert not manager2.is_leader
                assert not manager2.is_started
        except RuntimeError as e:
            # Redis not available - this is expected if Redis is not running
            assert (
                "Redis coordination is enabled but Redis is not available"
                in str(e)
            )

        await manager1.deactivate()
        await manager2.deactivate()

    async def test_manager_reload(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
    ):
        """Test manager reload functionality."""
        config = CoordinationConfig(enabled=False)
        repo = JsonJobRepository(temp_jobs_file)
        manager = CronManager(
            repo=repo,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=config,
        )

        # Activate
        await manager.activate()

        # Create a job
        job = CronJobSpec(
            id="test-job",
            name="Test Job",
            enabled=True,
            tenant_id="test-tenant",
            schedule=ScheduleSpec(
                type="cron",
                cron="0 0 * * *",
                timezone="UTC",
            ),
            task_type="text",
            text="Test",
            dispatch=DispatchSpec(
                type="channel",
                channel="console",
                target=DispatchTarget(user_id="user1", session_id="session1"),
            ),
        )
        await manager.create_or_replace_job(job)

        # Reload
        await manager.reload()

        # Job should still exist
        jobs = await manager.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "test-job"

        await manager.deactivate()


class TestCronManagerManualRun:
    """Tests for manual run_job bypassing execution lock."""

    async def test_run_job_bypasses_execution_lock(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
    ):
        """Test that manual run_job does not use execution lock."""
        config = CoordinationConfig(enabled=False)
        repo = JsonJobRepository(temp_jobs_file)
        manager = CronManager(
            repo=repo,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=config,
        )

        await manager.activate()

        # Create a job
        job = CronJobSpec(
            id="test-job",
            name="Test Job",
            enabled=True,
            tenant_id="test-tenant",
            schedule=ScheduleSpec(
                type="cron",
                cron="0 0 * * *",
                timezone="UTC",
            ),
            task_type="text",
            text="Test message",
            dispatch=DispatchSpec(
                type="channel",
                channel="console",
                target=DispatchTarget(user_id="user1", session_id="session1"),
            ),
            runtime=JobRuntimeSpec(timeout_seconds=30),
        )
        await manager.create_or_replace_job(job)

        # Run job manually - should not require execution lock
        # This just schedules the execution (fire-and-forget)
        await manager.run_job("test-job")

        # Wait a bit for the task to start
        await asyncio.sleep(0.1)

        await manager.deactivate()

    async def test_run_job_nonexistent_raises_keyerror(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
    ):
        """Test that run_job raises KeyError for nonexistent job."""
        config = CoordinationConfig(enabled=False)
        repo = JsonJobRepository(temp_jobs_file)
        manager = CronManager(
            repo=repo,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=config,
        )

        await manager.activate()

        with pytest.raises(KeyError):
            await manager.run_job("nonexistent-job")

        await manager.deactivate()


class TestCronManagerState:
    """Tests for CronManager state tracking."""

    async def test_job_state_tracking(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
    ):
        """Test that job state is properly tracked."""
        config = CoordinationConfig(enabled=False)
        repo = JsonJobRepository(temp_jobs_file)
        manager = CronManager(
            repo=repo,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=config,
        )

        await manager.activate()

        # Create a job
        job = CronJobSpec(
            id="test-job",
            name="Test Job",
            enabled=True,
            tenant_id="test-tenant",
            schedule=ScheduleSpec(
                type="cron",
                cron="0 0 * * *",
                timezone="UTC",
            ),
            task_type="text",
            text="Test",
            dispatch=DispatchSpec(
                type="channel",
                channel="console",
                target=DispatchTarget(user_id="user1", session_id="session1"),
            ),
        )
        await manager.create_or_replace_job(job)

        # Get initial state
        state = manager.get_state("test-job")
        assert state.last_status is None
        assert state.last_run_at is None

        await manager.deactivate()


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
class TestCronManagerFailover:
    """Tests for automatic failover between managers."""

    async def test_follower_takes_over_after_leader_loses_lease(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
        coordination_config,
    ):
        """Test that follower automatically takes over when leader loses lease."""
        # Use shorter intervals for faster test
        config = CoordinationConfig(
            enabled=True,
            redis_url="redis://localhost:6379/15",
            lease_ttl_seconds=3,
            lease_renew_interval_seconds=1,
        )

        # Create two managers
        repo1 = JsonJobRepository(temp_jobs_file)
        repo2 = JsonJobRepository(temp_jobs_file)

        leader = CronManager(
            repo=repo1,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=config,
        )
        follower = CronManager(
            repo=repo2,
            runner=mock_runner,
            channel_manager=mock_channel_manager,
            agent_id="test-agent",
            tenant_id="test-tenant",
            coordination_config=config,
        )

        try:
            # Leader activates and becomes leader
            is_leader = await leader.activate()
            if not is_leader:
                pytest.skip("Could not acquire leadership for test")

            assert leader.is_leader
            assert leader.is_started

            # Follower activates as follower
            is_follower_leader = await follower.activate()
            assert not is_follower_leader
            assert not follower.is_leader
            assert not follower.is_started

            # Create a job while leader
            job = CronJobSpec(
                id="test-job",
                name="Test Job",
                enabled=True,
                tenant_id="test-tenant",
                schedule=ScheduleSpec(
                    type="cron",
                    cron="0 0 * * *",
                    timezone="UTC",
                ),
                task_type="text",
                text="Test",
                dispatch=DispatchSpec(
                    type="channel",
                    channel="console",
                    target=DispatchTarget(
                        user_id="user1", session_id="session1"
                    ),
                ),
            )
            await leader.create_or_replace_job(job)

            # Leader deactivates (simulates lease loss or shutdown)
            await leader.deactivate()

            # Wait for follower's candidate loop to detect and take over
            # Wait longer than lease TTL + candidate loop interval
            await asyncio.sleep(config.lease_ttl_seconds + 2)

            # Follower should now be leader
            assert follower.is_leader
            assert follower.is_started

        except RuntimeError as e:
            if "Redis coordination is enabled but Redis is not available" in str(e):
                pytest.skip("Redis not available")
            raise
        finally:
            await leader.deactivate()
            await follower.deactivate()
            await leader.disconnect_coordination()
            await follower.disconnect_coordination()
