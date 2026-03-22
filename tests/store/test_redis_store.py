# -*- coding: utf-8 -*-
"""Tests for Redis stores (ConsolePushStore and DownloadTaskStore)."""
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copaw.store.redis_store import ConsolePushStore, DownloadTaskStore


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with async support."""
    redis_client = MagicMock()
    redis_client.pipeline = MagicMock()
    redis_client.lrange = AsyncMock()
    redis_client.rpush = AsyncMock()
    redis_client.delete = AsyncMock()
    redis_client.expire = AsyncMock()
    redis_client.get = AsyncMock()
    redis_client.set = AsyncMock()
    redis_client.sadd = AsyncMock()
    redis_client.srem = AsyncMock()
    redis_client.smembers = AsyncMock()
    return redis_client


class TestConsolePushStore:
    """Tests for ConsolePushStore."""

    @pytest.mark.asyncio
    async def test_append_and_take(self, mock_redis):
        """Test append and consume messages."""
        store = ConsolePushStore(mock_redis, ttl=60)

        # Mock pipeline for append
        mock_pipe = AsyncMock()
        mock_pipe.rpush = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[1, True])
        mock_redis.pipeline.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipe
        )
        mock_redis.pipeline.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        # Append a message
        with patch("time.time", return_value=1000.0):
            await store.append("user1", "session1", "Hello World")

        # Verify append was called with correct key
        mock_pipe.rpush.assert_called_once()
        call_args = mock_pipe.rpush.call_args
        assert call_args[0][0] == "copaw:push:user1"
        message = json.loads(call_args[0][1])
        assert message["session_id"] == "session1"
        assert message["text"] == "Hello World"
        assert message["timestamp"] == 1000.0

        # Mock lrange to return the message for take
        stored_message = json.dumps(
            {
                "session_id": "session1",
                "text": "Hello World",
                "timestamp": 1000.0,
            },
        )
        mock_redis.lrange = AsyncMock(return_value=[stored_message.encode()])

        # Take messages for session
        messages = await store.take("user1", "session1")

        assert len(messages) == 1
        assert messages[0]["session_id"] == "session1"
        assert messages[0]["text"] == "Hello World"
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_take_all_consumes_all(self, mock_redis):
        """Test take_all removes all messages."""
        store = ConsolePushStore(mock_redis, ttl=60)

        # Mock pipeline for take_all
        stored_messages = [
            json.dumps(
                {"session_id": "s1", "text": "Message 1", "timestamp": 1000.0},
            ).encode(),
            json.dumps(
                {"session_id": "s2", "text": "Message 2", "timestamp": 1001.0},
            ).encode(),
        ]

        mock_pipe = AsyncMock()
        mock_pipe.lrange = MagicMock(return_value=mock_pipe)
        mock_pipe.delete = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[stored_messages, 1])
        mock_redis.pipeline.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipe
        )
        mock_redis.pipeline.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        messages = await store.take_all("user1")

        assert len(messages) == 2
        texts = [m["text"] for m in messages]
        assert "Message 1" in texts
        assert "Message 2" in texts

    @pytest.mark.asyncio
    async def test_ttl_expires(self, mock_redis):
        """Test messages expire after TTL."""
        store = ConsolePushStore(mock_redis, ttl=60)

        # Mock pipeline for append
        mock_pipe = AsyncMock()
        mock_pipe.rpush = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[1, True])
        mock_redis.pipeline.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipe
        )
        mock_redis.pipeline.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        # Append with custom TTL
        await store.append("user1", "session1", "Test message", ttl=120)

        # Verify TTL was set correctly
        mock_pipe.expire.assert_called_once_with("copaw:push:user1", 120)

    @pytest.mark.asyncio
    async def test_get_recent_consumes_messages(self, mock_redis):
        """Test get_recent consumes messages on read."""
        store = ConsolePushStore(mock_redis, ttl=60)

        current_time = 1000.0
        stored_messages = [
            json.dumps(
                {"session_id": "s1", "text": "Recent", "timestamp": 990.0},
            ).encode(),  # 10 seconds old
            json.dumps(
                {"session_id": "s2", "text": "Old", "timestamp": 900.0},
            ).encode(),  # 100 seconds old
        ]

        mock_redis.lrange = AsyncMock(return_value=stored_messages)
        mock_redis.delete = AsyncMock()

        with patch("time.time", return_value=current_time):
            messages = await store.get_recent("user1", max_age_seconds=60)

        # Only recent message should be returned
        assert len(messages) == 1
        assert messages[0]["text"] == "Recent"

        # But all messages should be consumed
        mock_redis.delete.assert_called_once()


class TestDownloadTaskStore:
    """Tests for DownloadTaskStore."""

    @pytest.mark.asyncio
    async def test_save_and_get(self, mock_redis):
        """Test save and retrieve task."""
        store = DownloadTaskStore(mock_redis, ttl=3600)

        task = {
            "task_id": "task123",
            "backend": "nas",
            "status": "pending",
            "url": "https://example.com/file.zip",
        }

        # Mock pipeline for save
        mock_pipe = AsyncMock()
        mock_pipe.set = MagicMock(return_value=mock_pipe)
        mock_pipe.sadd = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[True, 1, True, 1, True])
        mock_redis.pipeline.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipe
        )
        mock_redis.pipeline.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        await store.save(task)

        # Verify set was called
        mock_pipe.set.assert_called_once()
        call_args = mock_pipe.set.call_args
        assert call_args[0][0] == "copaw:download:task:task123"
        assert json.loads(call_args[0][1]) == task

        # Mock get for retrieval
        mock_redis.get = AsyncMock(return_value=json.dumps(task).encode())

        retrieved = await store.get("task123")

        assert retrieved is not None
        assert retrieved["task_id"] == "task123"
        assert retrieved["backend"] == "nas"

    @pytest.mark.asyncio
    async def test_get_all_with_backend_filter(self, mock_redis):
        """Test get_all filters by backend."""
        store = DownloadTaskStore(mock_redis, ttl=3600)

        # Mock smembers to return task IDs
        mock_redis.smembers = AsyncMock(
            return_value={b"task1", b"task2", b"task3"},
        )

        # Mock get to return different tasks
        tasks = {
            "task1": {"task_id": "task1", "backend": "nas"},
            "task2": {"task_id": "task2", "backend": "s3"},
            "task3": {"task_id": "task3", "backend": "nas"},
        }

        async def mock_get(task_id):
            task = tasks.get(task_id)
            if task:
                return task
            return None

        # Patch store.get to use our mock
        with patch.object(store, "get", side_effect=mock_get):
            # Get all NAS backend tasks
            mock_redis.smembers = AsyncMock(return_value={b"task1", b"task3"})
            nas_tasks = await store.get_all(backend="nas")

            assert len(nas_tasks) == 2
            task_ids = {t["task_id"] for t in nas_tasks}
            assert task_ids == {"task1", "task3"}

    @pytest.mark.asyncio
    async def test_delete_task(self, mock_redis):
        """Test delete task removes from all indexes."""
        store = DownloadTaskStore(mock_redis, ttl=3600)

        task = {
            "task_id": "task123",
            "backend": "nas",
            "status": "completed",
        }

        # Mock get to return the task
        with patch.object(store, "get", return_value=task):
            # Mock pipeline for delete
            mock_pipe = AsyncMock()
            mock_pipe.delete = MagicMock(return_value=mock_pipe)
            mock_pipe.srem = MagicMock(return_value=mock_pipe)
            mock_pipe.execute = AsyncMock(return_value=[1, 1, 1])
            mock_redis.pipeline.return_value.__aenter__ = AsyncMock(
                return_value=mock_pipe,
            )
            mock_redis.pipeline.return_value.__aexit__ = AsyncMock(
                return_value=None
            )

            result = await store.delete("task123")

            assert result is True
            mock_pipe.delete.assert_called_once_with(
                "copaw:download:task:task123"
            )
            mock_pipe.srem.assert_any_call(
                "copaw:download:index:nas", "task123"
            )
            mock_pipe.srem.assert_any_call(
                "copaw:download:index:all", "task123"
            )

    @pytest.mark.asyncio
    async def test_delete_nonexistent_task(self, mock_redis):
        """Test delete returns False for non-existent task."""
        store = DownloadTaskStore(mock_redis, ttl=3600)

        # Mock get to return None
        with patch.object(store, "get", return_value=None):
            result = await store.delete("nonexistent")

            assert result is False

    @pytest.mark.asyncio
    async def test_save_without_task_id_raises(self, mock_redis):
        """Test save raises ValueError when task_id is missing."""
        store = DownloadTaskStore(mock_redis, ttl=3600)

        task = {"backend": "nas", "status": "pending"}

        with pytest.raises(ValueError, match="task_id"):
            await store.save(task)

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, mock_redis):
        """Test get returns None for non-existent task."""
        store = DownloadTaskStore(mock_redis, ttl=3600)

        mock_redis.get = AsyncMock(return_value=None)

        result = await store.get("nonexistent")

        assert result is None
