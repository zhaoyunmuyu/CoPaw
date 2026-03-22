# -*- coding: utf-8 -*-
"""Redis stores for console push and download tasks."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class ConsolePushStore:
    """Store for console push messages with TTL support.

    Each user's messages are stored in a Redis list with TTL.
    Messages can be consumed by session or all at once.
    """

    def __init__(self, redis_client: redis.Redis, ttl: int = 60):
        """Initialize ConsolePushStore.

        Args:
            redis_client: Redis client instance
            ttl: Default TTL for messages in seconds (default: 60)
        """
        self.redis_client = redis_client
        self.ttl = ttl

    def _key(self, user_id: str) -> str:
        """Generate Redis key for user's messages.

        Args:
            user_id: User identifier

        Returns:
            Redis key string
        """
        return f"copaw:push:{user_id}"

    async def append(
        self, user_id: str, session_id: str, text: str, ttl: Optional[int] = None
    ) -> None:
        """Append a message to user's queue with TTL.

        Args:
            user_id: User identifier
            session_id: Session identifier
            text: Message text
            ttl: Optional TTL override in seconds
        """
        key = self._key(user_id)
        message = {
            "session_id": session_id,
            "text": text,
            "timestamp": time.time(),
        }
        ttl_value = ttl if ttl is not None else self.ttl

        try:
            # Use pipeline for atomic operations
            async with self.redis_client.pipeline() as pipe:
                pipe.rpush(key, json.dumps(message))
                pipe.expire(key, ttl_value)
                await pipe.execute()
            logger.debug(f"Appended message to {key} for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to append message to {key}: {e}")
            raise

    async def take(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        """Get and remove all messages for a specific session.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            List of message dictionaries for the session
        """
        key = self._key(user_id)
        messages = []

        try:
            # Get all messages
            raw_messages = await self.redis_client.lrange(key, 0, -1)
            if not raw_messages:
                return messages

            # Parse and filter messages
            remaining = []
            for raw_msg in raw_messages:
                try:
                    msg = json.loads(raw_msg)
                    if msg.get("session_id") == session_id:
                        messages.append(msg)
                    else:
                        remaining.append(raw_msg)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in message: {raw_msg}")
                    continue

            # Rebuild list with remaining messages
            if remaining:
                await self.redis_client.delete(key)
                for msg in remaining:
                    await self.redis_client.rpush(key, msg)
                # Reset TTL
                await self.redis_client.expire(key, self.ttl)
            else:
                await self.redis_client.delete(key)

            logger.debug(
                f"Retrieved {len(messages)} messages for session {session_id} from {key}"
            )
            return messages
        except Exception as e:
            logger.error(f"Failed to take messages from {key}: {e}")
            raise

    async def take_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Get and remove ALL messages for a user.

        This is the primary method for consuming all pending messages.

        Args:
            user_id: User identifier

        Returns:
            List of all message dictionaries for the user
        """
        key = self._key(user_id)
        messages = []

        try:
            # Get all messages and delete atomically
            async with self.redis_client.pipeline() as pipe:
                pipe.lrange(key, 0, -1)
                pipe.delete(key)
                results = await pipe.execute()

            raw_messages = results[0]
            for raw_msg in raw_messages:
                try:
                    msg = json.loads(raw_msg)
                    messages.append(msg)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in message: {raw_msg}")
                    continue

            logger.debug(f"Retrieved {len(messages)} messages from {key}")
            return messages
        except Exception as e:
            logger.error(f"Failed to take all messages from {key}: {e}")
            raise

    async def get_recent(
        self, user_id: str, max_age_seconds: float
    ) -> List[Dict[str, Any]]:
        """Get recent messages without removing them (consume on read).

        Messages are consumed (removed) from the store after being read.
        Only messages within the max_age_seconds window are returned,
        but all messages are consumed.

        Args:
            user_id: User identifier
            max_age_seconds: Maximum age of messages to return

        Returns:
            List of recent message dictionaries
        """
        key = self._key(user_id)
        messages = []
        current_time = time.time()

        try:
            # Get all messages
            raw_messages = await self.redis_client.lrange(key, 0, -1)
            if not raw_messages:
                return messages

            # Parse and filter by age, consume all
            for raw_msg in raw_messages:
                try:
                    msg = json.loads(raw_msg)
                    msg_time = msg.get("timestamp", 0)
                    if current_time - msg_time <= max_age_seconds:
                        messages.append(msg)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in message: {raw_msg}")
                    continue

            # Consume (delete) all messages after reading
            await self.redis_client.delete(key)

            logger.debug(
                f"Retrieved {len(messages)} recent messages (consumed all) from {key}"
            )
            return messages
        except Exception as e:
            logger.error(f"Failed to get recent messages from {key}: {e}")
            raise


class DownloadTaskStore:
    """Store for download task metadata with TTL support."""

    def __init__(self, redis_client: redis.Redis, ttl: int = 3600):
        """Initialize DownloadTaskStore.

        Args:
            redis_client: Redis client instance
            ttl: Default TTL for tasks in seconds (default: 3600 = 1 hour)
        """
        self.redis_client = redis_client
        self.ttl = ttl

    def _key(self, task_id: str) -> str:
        """Generate Redis key for task.

        Args:
            task_id: Task identifier

        Returns:
            Redis key string
        """
        return f"copaw:download:task:{task_id}"

    def _index_key(self, backend: Optional[str] = None) -> str:
        """Generate index key for task tracking.

        Args:
            backend: Optional backend filter

        Returns:
            Index key string
        """
        if backend:
            return f"copaw:download:index:{backend}"
        return "copaw:download:index:all"

    async def save(
        self, task: Dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """Save a download task with TTL.

        Args:
            task: Task dictionary containing task metadata
            ttl: Optional TTL override in seconds
        """
        task_id = task.get("task_id")
        if not task_id:
            raise ValueError("Task must have a 'task_id' field")

        key = self._key(task_id)
        ttl_value = ttl if ttl is not None else self.ttl
        backend = task.get("backend")

        try:
            async with self.redis_client.pipeline() as pipe:
                # Save task data
                pipe.set(key, json.dumps(task), ex=ttl_value)
                # Add to index (with same TTL as task)
                index_key = self._index_key(backend)
                pipe.sadd(index_key, task_id)
                pipe.expire(index_key, ttl_value)
                # Also add to global index
                global_index_key = self._index_key()
                pipe.sadd(global_index_key, task_id)
                pipe.expire(global_index_key, ttl_value)
                await pipe.execute()

            logger.debug(f"Saved task {task_id} to {key}")
        except Exception as e:
            logger.error(f"Failed to save task {task_id}: {e}")
            raise

    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task dictionary or None if not found
        """
        key = self._key(task_id)

        try:
            raw_task = await self.redis_client.get(key)
            if raw_task is None:
                return None

            task = json.loads(raw_task)
            return task
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON for task {task_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            raise

    async def get_all(self, backend: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tasks, optionally filtered by backend.

        Args:
            backend: Optional backend filter

        Returns:
            List of task dictionaries
        """
        index_key = self._index_key(backend)
        tasks = []

        try:
            # Get all task IDs from index
            task_ids = await self.redis_client.smembers(index_key)
            if not task_ids:
                return tasks

            # Fetch each task
            for task_id_bytes in task_ids:
                task_id = task_id_bytes.decode("utf-8")
                task = await self.get(task_id)
                if task:
                    tasks.append(task)

            return tasks
        except Exception as e:
            logger.error(f"Failed to get all tasks: {e}")
            raise

    async def delete(self, task_id: str) -> bool:
        """Delete a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            True if task was deleted, False if not found
        """
        # First get the task to find its backend
        task = await self.get(task_id)
        if not task:
            return False

        key = self._key(task_id)
        backend = task.get("backend")

        try:
            async with self.redis_client.pipeline() as pipe:
                # Delete task data
                pipe.delete(key)
                # Remove from backend-specific index
                if backend:
                    index_key = self._index_key(backend)
                    pipe.srem(index_key, task_id)
                # Remove from global index
                global_index_key = self._index_key()
                pipe.srem(global_index_key, task_id)
                results = await pipe.execute()

            deleted = bool(results[0])
            if deleted:
                logger.debug(f"Deleted task {task_id}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            raise