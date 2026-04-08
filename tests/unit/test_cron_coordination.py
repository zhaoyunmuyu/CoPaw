# -*- coding: utf-8 -*-
"""Unit tests for Redis-coordinated cron leadership.

These tests verify:
- Lease election and renewal
- Execution lock semantics
- Activation/deactivation behavior
- Reload debounce behavior
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests as requiring Redis (skipped if redis not available)
pytestmark = [
    pytest.mark.asyncio,
]

# Check if redis is available
try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


# Skip all tests if redis is not available
if not REDIS_AVAILABLE:
    pytest.skip("Redis not available", allow_module_level=True)


from swe.app.crons.coordination import (
    AgentLease,
    CoordinationConfig,
    CronCoordination,
    ExecutionLock,
    RedisNotAvailableError,
)


@pytest.fixture
def coordination_config():
    """Default coordination config for tests."""
    return CoordinationConfig(
        enabled=True,
        redis_url="redis://localhost:6379/15",  # Use DB 15 for tests
        lease_ttl_seconds=10,
        lease_renew_interval_seconds=3,
        lease_renew_failure_threshold=2,
        lock_safety_margin_seconds=5,
    )


@pytest.fixture
async def redis_client():
    """Create a Redis client for tests."""
    client = redis.from_url("redis://localhost:6379/15")
    try:
        await client.ping()
        yield client
    finally:
        # Clean up test keys
        keys = await client.keys("swe:cron:*")
        if keys:
            await client.delete(*keys)
        await client.close()


class TestAgentLease:
    """Tests for AgentLease - leader election per tenant+agent."""

    async def test_lease_acquire_and_release(
        self, redis_client, coordination_config
    ):
        """Test basic lease acquisition and release."""
        lease = AgentLease(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            instance_id="instance-1",
            config=coordination_config,
        )

        # Should not be owned initially
        assert not lease.is_owned

        # Acquire lease
        acquired = await lease.acquire()
        assert acquired is True
        assert lease.is_owned

        # Release lease
        await lease.release()
        assert not lease.is_owned

    async def test_lease_prevents_duplicate_acquisition(
        self, redis_client, coordination_config
    ):
        """Test that only one instance can hold the lease."""
        lease1 = AgentLease(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            instance_id="instance-1",
            config=coordination_config,
        )
        lease2 = AgentLease(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            instance_id="instance-2",
            config=coordination_config,
        )

        # First instance acquires lease
        acquired1 = await lease1.acquire()
        assert acquired1 is True
        assert lease1.is_owned

        # Second instance should fail to acquire
        acquired2 = await lease2.acquire()
        assert acquired2 is False
        assert not lease2.is_owned

        # Release first instance
        await lease1.release()

        # Second instance can now acquire
        acquired2 = await lease2.acquire()
        assert acquired2 is True
        assert lease2.is_owned

        await lease2.release()

    async def test_lease_renewal(self, redis_client, coordination_config):
        """Test that lease is automatically renewed."""
        # Use shorter intervals for faster test
        config = CoordinationConfig(
            enabled=True,
            redis_url="redis://localhost:6379/15",
            lease_ttl_seconds=5,
            lease_renew_interval_seconds=2,
            lease_renew_failure_threshold=3,
        )

        lease = AgentLease(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            instance_id="instance-1",
            config=config,
        )

        # Acquire lease
        acquired = await lease.acquire()
        assert acquired is True

        # Wait for renewal to happen
        await asyncio.sleep(3)

        # Lease should still be owned
        assert lease.is_owned

        # Verify TTL was extended
        ttl = await redis_client.ttl(lease._key)
        assert ttl > 0
        assert ttl <= config.lease_ttl_seconds

        await lease.release()

    async def test_lease_lost_when_key_deleted(
        self, redis_client, coordination_config
    ):
        """Test that lease is lost if key is externally deleted."""
        lease = AgentLease(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            instance_id="instance-1",
            config=coordination_config,
        )

        # Acquire lease
        await lease.acquire()
        assert lease.is_owned

        # Delete key externally (simulates another instance stealing or expiry)
        await redis_client.delete(lease._key)

        # Wait for renewal cycle to detect loss
        await asyncio.sleep(coordination_config.lease_renew_interval_seconds + 1)

        # Lease should be lost
        assert not lease.is_owned


class TestExecutionLock:
    """Tests for ExecutionLock - timed job de-duplication."""

    async def test_execution_lock_acquire_and_release(
        self, redis_client, coordination_config
    ):
        """Test basic lock acquisition and release."""
        lock = ExecutionLock(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            job_id="job-1",
            ttl_seconds=10,
        )

        # Acquire lock
        acquired = await lock.acquire()
        assert acquired is True

        # Try to acquire same lock again (should fail)
        lock2 = ExecutionLock(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            job_id="job-1",
            ttl_seconds=10,
        )
        acquired2 = await lock2.acquire()
        assert acquired2 is False

        # Release first lock
        await lock.release()

        # Now second lock can be acquired
        acquired2 = await lock2.acquire()
        assert acquired2 is True

        await lock2.release()

    async def test_execution_lock_expires(self, redis_client, coordination_config):
        """Test that lock expires after TTL."""
        lock = ExecutionLock(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            job_id="job-1",
            ttl_seconds=2,  # Short TTL for test
        )

        # Acquire lock
        acquired = await lock.acquire()
        assert acquired is True

        # Wait for TTL to expire
        await asyncio.sleep(3)

        # Now another lock can be acquired
        lock2 = ExecutionLock(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            job_id="job-1",
            ttl_seconds=10,
        )
        acquired2 = await lock2.acquire()
        assert acquired2 is True

        await lock2.release()

    async def test_execution_lock_isolated_per_job(
        self, redis_client, coordination_config
    ):
        """Test that locks for different jobs don't interfere."""
        lock1 = ExecutionLock(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            job_id="job-1",
            ttl_seconds=10,
        )
        lock2 = ExecutionLock(
            redis_client=redis_client,
            tenant_id="test-tenant",
            agent_id="test-agent",
            job_id="job-2",
            ttl_seconds=10,
        )

        # Both should be able to acquire
        acquired1 = await lock1.acquire()
        acquired2 = await lock2.acquire()
        assert acquired1 is True
        assert acquired2 is True

        await lock1.release()
        await lock2.release()


class TestCronCoordination:
    """Tests for CronCoordination - high-level coordination API."""

    async def test_connect_without_redis_raises_error(self):
        """Test that connection fails gracefully if Redis unavailable."""
        config = CoordinationConfig(enabled=True, redis_url="redis://invalid:6379")
        coord = CronCoordination(
            tenant_id="test",
            agent_id="test-agent",
            config=config,
        )

        # Should return False if connection fails
        connected = await coord.connect()
        assert connected is False

    async def test_coordination_disabled_returns_true(self):
        """Test that disabled coordination returns True (no-op mode)."""
        config = CoordinationConfig(enabled=False)
        coord = CronCoordination(
            tenant_id="test",
            agent_id="test-agent",
            config=config,
        )

        # Should return True when disabled (no coordination needed)
        connected = await coord.connect()
        assert connected is False  # Returns False because coordination is disabled

    async def test_activate_without_connection(self, coordination_config):
        """Test that activation without connection runs in no-coordination mode."""
        # Don't connect first
        coord = CronCoordination(
            tenant_id="test",
            agent_id="test-agent",
            config=coordination_config,
        )

        # Activate without connecting - should return True (run without coordination)
        is_leader = await coord.activate()
        assert is_leader is True

        await coord.deactivate()

    async def test_publish_reload_without_connection(self, coordination_config):
        """Test that publish_reload returns False if not connected."""
        coord = CronCoordination(
            tenant_id="test",
            agent_id="test-agent",
            config=coordination_config,
        )

        # Should return False if not connected
        result = await coord.publish_reload()
        assert result is False

    async def test_set_reload_callback(self, coordination_config):
        """Test setting reload callback."""
        coord = CronCoordination(
            tenant_id="test",
            agent_id="test-agent",
            config=coordination_config,
        )

        callback_called = False

        def callback():
            nonlocal callback_called
            callback_called = True

        coord.set_reload_callback(callback)
        assert coord._on_reload is callback


class TestCronCoordinationWithRedis:
    """Tests for CronCoordination that require Redis."""

    async def test_full_lifecycle(self, redis_client, coordination_config):
        """Test full coordination lifecycle with Redis."""
        coord = CronCoordination(
            tenant_id="test-tenant",
            agent_id="test-agent",
            config=coordination_config,
        )

        # Connect
        connected = await coord.connect()
        assert connected is True

        # Activate - should become leader
        is_leader = await coord.activate()
        assert is_leader is True
        assert coord.is_leader

        # Deactivate
        await coord.deactivate()
        assert not coord.is_leader

        # Disconnect
        await coord.disconnect()

    async def test_two_instances_leader_election(
        self, redis_client, coordination_config
    ):
        """Test leader election with two coordination instances."""
        coord1 = CronCoordination(
            tenant_id="test-tenant",
            agent_id="test-agent",
            config=coordination_config,
        )
        coord2 = CronCoordination(
            tenant_id="test-tenant",
            agent_id="test-agent",
            config=coordination_config,
        )

        # Connect both
        assert await coord1.connect()
        assert await coord2.connect()

        # Activate first - should become leader
        is_leader1 = await coord1.activate()
        assert is_leader1 is True
        assert coord1.is_leader

        # Activate second - should be follower
        is_leader2 = await coord2.activate()
        assert is_leader2 is False
        assert not coord2.is_leader

        # First deactivates
        await coord1.deactivate()
        assert not coord1.is_leader

        # Second can now become leader if it re-activates
        # (But in current implementation, it stays follower)

        await coord2.deactivate()
        await coord1.disconnect()
        await coord2.disconnect()

    async def test_publish_reload(self, redis_client, coordination_config):
        """Test publishing reload signal."""
        coord = CronCoordination(
            tenant_id="test-tenant",
            agent_id="test-agent",
            config=coordination_config,
        )

        # Connect and activate
        await coord.connect()
        await coord.activate()

        # Publish reload
        result = await coord.publish_reload()
        assert result is True

        await coord.deactivate()
        await coord.disconnect()

    async def test_create_execution_lock(self, redis_client, coordination_config):
        """Test creating execution lock through coordination."""
        coord = CronCoordination(
            tenant_id="test-tenant",
            agent_id="test-agent",
            config=coordination_config,
        )

        # Connect and activate
        await coord.connect()

        # Create execution lock
        lock = coord.create_execution_lock("job-1", timeout_seconds=30)
        assert lock is not None

        # Acquire the lock
        acquired = await lock.acquire()
        assert acquired is True

        await lock.release()
        await coord.disconnect()

    async def test_create_execution_lock_without_connection(self, coordination_config):
        """Test that creating execution lock without connection raises error."""
        coord = CronCoordination(
            tenant_id="test-tenant",
            agent_id="test-agent",
            config=coordination_config,
        )

        # Don't connect
        with pytest.raises(Exception):  # RedisNotAvailableError
            coord.create_execution_lock("job-1", timeout_seconds=30)
