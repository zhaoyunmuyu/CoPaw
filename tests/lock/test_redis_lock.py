# -*- coding: utf-8 -*-
"""Tests for Redis distributed lock with automatic renewal support."""
import asyncio

import pytest
import redis.asyncio as redis

from copaw.lock import RedisLock, LockRenewalTask


@pytest.fixture
async def redis_client():
    """Create a Redis client for testing."""
    client = redis.Redis(
        host="localhost", port=6379, db=15, decode_responses=True
    )
    yield client
    # Cleanup: flush test database
    await client.flushdb()
    await client.aclose()


@pytest.fixture
async def redis_lock(redis_client):
    """Create a RedisLock instance."""
    return RedisLock(redis_client)


class TestRedisLock:
    """Tests for RedisLock class."""

    @pytest.mark.asyncio
    async def test_acquire_release(self, redis_lock, redis_client):
        """Test basic lock acquire and release."""
        key = "test:lock:acquire_release"
        value = "owner-1"

        # Acquire lock
        acquired = await redis_lock.acquire(key, value=value, ttl=5000)
        assert acquired is True

        # Verify lock is held
        stored_value = await redis_client.get(key)
        assert stored_value == value

        # Release lock
        released = await redis_lock.release(key, value)
        assert released is True

        # Verify lock is released
        stored_value = await redis_client.get(key)
        assert stored_value is None

    @pytest.mark.asyncio
    async def test_acquire_already_locked(self, redis_lock):
        """Test that acquiring a lock already held by another fails."""
        key = "test:lock:already_locked"
        owner1 = "owner-1"
        owner2 = "owner-2"

        # Owner 1 acquires lock
        acquired = await redis_lock.acquire(key, value=owner1, ttl=5000)
        assert acquired is True

        # Owner 2 tries to acquire the same lock
        acquired = await redis_lock.acquire(key, value=owner2, ttl=5000)
        assert acquired is False

        # Verify lock is still held by owner 1
        is_locked = await redis_lock.is_locked(key)
        assert is_locked is True

    @pytest.mark.asyncio
    async def test_release_wrong_value(self, redis_lock, redis_client):
        """Test that releasing with wrong value fails."""
        key = "test:lock:wrong_value"
        owner = "owner-1"
        wrong_owner = "owner-2"

        # Acquire lock
        await redis_lock.acquire(key, value=owner, ttl=5000)

        # Try to release with wrong value
        released = await redis_lock.release(key, wrong_owner)
        assert released is False

        # Verify lock is still held
        stored_value = await redis_client.get(key)
        assert stored_value == owner

    @pytest.mark.asyncio
    async def test_renewal_extends_ttl(self, redis_client):
        """Test that lock renewal extends TTL."""
        key = "test:lock:renewal_ttl"
        value = "owner-1"
        ttl = 500  # 500ms TTL

        # Acquire lock
        lock = RedisLock(redis_client)
        acquired = await lock.acquire(key, value=value, ttl=ttl)
        assert acquired is True

        # Create and start renewal task
        renewal = LockRenewalTask(
            redis_client=redis_client,
            lock_key=key,
            lock_value=value,
            ttl=ttl,
        )
        await renewal.start()

        # Wait for at least one renewal cycle
        await asyncio.sleep(0.4)  # Renewal interval is TTL/2 = 250ms

        # Stop renewal task
        await renewal.stop()

        # Verify lock is still held
        stored_value = await redis_client.get(key)
        assert stored_value == value

        # Clean up
        await lock.release(key, value)

    @pytest.mark.asyncio
    async def test_renewal_detects_lock_loss(self, redis_client):
        """Test that renewal detects when lock is lost."""
        key = "test:lock:renewal_loss"
        value = "owner-1"
        ttl = 500  # 500ms TTL

        # Acquire lock
        lock = RedisLock(redis_client)
        acquired = await lock.acquire(key, value=value, ttl=ttl)
        assert acquired is True

        # Create renewal task
        renewal = LockRenewalTask(
            redis_client=redis_client,
            lock_key=key,
            lock_value=value,
            ttl=ttl,
            max_failed_renewals=1,  # Stop after 1 failure
        )
        await renewal.start()

        # Simulate lock being taken by another owner
        await redis_client.set(key, "other-owner", px=5000)

        # Wait for renewal to detect failure
        await asyncio.sleep(0.4)

        # Verify renewal task stopped due to failure
        assert renewal.is_healthy() is False

        # Clean up
        await renewal.stop()
