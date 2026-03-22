# -*- coding: utf-8 -*-
"""Redis distributed lock with automatic renewal support."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Lua scripts for atomic operations
ACQUIRE_LOCK_SCRIPT = """
local key = KEYS[1]
local value = ARGV[1]
local ttl = tonumber(ARGV[2])

-- Try to set the lock if it doesn't exist or if we own it
local current = redis.call('GET', key)
if current == false then
    -- Key doesn't exist, acquire it
    redis.call('SET', key, value, 'PX', ttl)
    return 1
elseif current == value then
    -- We already own the lock, extend it
    redis.call('SET', key, value, 'PX', ttl)
    return 1
else
    -- Lock is held by someone else
    return 0
end
"""

RELEASE_LOCK_SCRIPT = """
local key = KEYS[1]
local value = ARGV[1]

-- Only release if we own the lock
local current = redis.call('GET', key)
if current == value then
    redis.call('DEL', key)
    return 1
else
    return 0
end
"""

EXTEND_LOCK_SCRIPT = """
local key = KEYS[1]
local value = ARGV[1]
local ttl = tonumber(ARGV[2])

-- Only extend if we own the lock
local current = redis.call('GET', key)
if current == value then
    redis.call('SET', key, value, 'PX', ttl)
    return 1
else
    return 0
end
"""


class LockRenewalTask:
    """Background task for automatic lock renewal."""

    def __init__(
        self,
        redis_client: redis.Redis,
        lock_key: str,
        lock_value: str,
        ttl: int,
        max_failed_renewals: int = 3,
    ):
        """
        Initialize lock renewal task.

        Args:
            redis_client: Redis client instance
            lock_key: Lock key to renew
            lock_value: Lock value (must match the lock owner)
            ttl: Lock TTL in milliseconds
            max_failed_renewals: Maximum consecutive failures before stopping
        """
        self.redis_client = redis_client
        self.lock_key = lock_key
        self.lock_value = lock_value
        self.ttl = ttl
        self.max_failed_renewals = max_failed_renewals

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._failed_renewals = 0
        self._renewal_count = 0
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the background renewal task."""
        if self._running:
            logger.warning(f"Lock renewal task already running for {self.lock_key}")
            return

        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._renew_loop())
        logger.debug(f"Started lock renewal task for {self.lock_key}")

    async def stop(self) -> None:
        """Stop the renewal task."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Lock renewal task did not stop gracefully for {self.lock_key}")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        logger.debug(
            f"Stopped lock renewal task for {self.lock_key} "
            f"(total renewals: {self._renewal_count})"
        )

    async def _renew_loop(self) -> None:
        """Main renewal loop."""
        renewal_interval = self.ttl / 2000.0  # Renew at half TTL

        while self._running and not self._stop_event.is_set():
            try:
                # Wait for renewal interval or stop signal
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=renewal_interval
                    )
                    # If we get here, stop was signaled
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, proceed with renewal
                    pass

                if not self._running:
                    break

                # Attempt renewal
                success = await self._extend()

                if success:
                    self._failed_renewals = 0
                    self._renewal_count += 1
                    logger.debug(
                        f"Renewed lock {self.lock_key} "
                        f"(renewal #{self._renewal_count})"
                    )
                else:
                    self._failed_renewals += 1
                    logger.warning(
                        f"Failed to renew lock {self.lock_key} "
                        f"(failure #{self._failed_renewals})"
                    )

                    if self._failed_renewals >= self.max_failed_renewals:
                        logger.error(
                            f"Lock renewal failed {self._failed_renewals} times, "
                            f"stopping renewal task for {self.lock_key}"
                        )
                        self._running = False
                        break

            except asyncio.CancelledError:
                logger.debug(f"Lock renewal task cancelled for {self.lock_key}")
                break
            except Exception as e:
                logger.error(
                    f"Unexpected error in lock renewal for {self.lock_key}: {e}",
                    exc_info=True
                )
                self._failed_renewals += 1

                if self._failed_renewals >= self.max_failed_renewals:
                    logger.error(
                        f"Too many failures, stopping renewal task for {self.lock_key}"
                    )
                    self._running = False
                    break

    async def _extend(self) -> bool:
        """
        Extend lock TTL using Lua script.

        Returns:
            True if extension succeeded, False otherwise
        """
        try:
            result = await self.redis_client.eval(
                EXTEND_LOCK_SCRIPT,
                1,
                self.lock_key,
                self.lock_value,
                self.ttl
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to extend lock {self.lock_key}: {e}")
            return False

    def is_healthy(self) -> bool:
        """
        Check if the renewal task is healthy.

        Returns:
            True if renewal is running and healthy, False otherwise
        """
        return (
            self._running and
            self._failed_renewals < self.max_failed_renewals and
            (self._task is not None and not self._task.done())
        )


class RedisLock:
    """Redis distributed lock with Lua script atomic operations."""

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize Redis lock.

        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client

    async def acquire(
        self,
        key: str,
        value: Optional[str] = None,
        ttl: int = 30000,
    ) -> bool:
        """
        Acquire a distributed lock.

        Args:
            key: Lock key
            value: Lock value (auto-generated if not provided)
            ttl: Lock TTL in milliseconds (default: 30 seconds)

        Returns:
            True if lock was acquired, False otherwise
        """
        if value is None:
            value = str(uuid.uuid4())

        try:
            result = await self.redis_client.eval(
                ACQUIRE_LOCK_SCRIPT,
                1,
                key,
                value,
                ttl
            )
            success = bool(result)

            if success:
                logger.debug(f"Acquired lock {key} with TTL {ttl}ms")
            else:
                logger.debug(f"Failed to acquire lock {key}")

            return success
        except Exception as e:
            logger.error(f"Error acquiring lock {key}: {e}")
            return False

    async def release(self, key: str, value: str) -> bool:
        """
        Release a distributed lock.

        Args:
            key: Lock key
            value: Lock value (must match the lock owner)

        Returns:
            True if lock was released, False otherwise
        """
        try:
            result = await self.redis_client.eval(
                RELEASE_LOCK_SCRIPT,
                1,
                key,
                value
            )
            success = bool(result)

            if success:
                logger.debug(f"Released lock {key}")
            else:
                logger.warning(
                    f"Failed to release lock {key} - "
                    f"lock not owned or already expired"
                )

            return success
        except Exception as e:
            logger.error(f"Error releasing lock {key}: {e}")
            return False

    async def is_locked(self, key: str) -> bool:
        """
        Check if a key is locked.

        Args:
            key: Lock key to check

        Returns:
            True if key is locked, False otherwise
        """
        try:
            result = await self.redis_client.get(key)
            return result is not None
        except Exception as e:
            logger.error(f"Error checking lock status for {key}: {e}")
            return False