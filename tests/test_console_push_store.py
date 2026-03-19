# -*- coding: utf-8 -*-
"""Tests for console_push_store with user isolation."""
import pytest
import asyncio
import time
from unittest.mock import patch


@pytest.fixture(autouse=True)
async def cleanup_store():
    """Clean up store after each test."""
    from copaw.app.console_push_store import _store, _lock

    async with _lock:
        _store.clear()
    yield
    async with _lock:
        _store.clear()


@pytest.mark.asyncio
async def test_append_with_user_id():
    """测试带 user_id 的消息存储"""
    from copaw.app.console_push_store import append, take

    await append("alice", "session_1", "Hello from Alice")
    messages = await take("alice", "session_1")
    assert len(messages) == 1
    assert messages[0]["text"] == "Hello from Alice"


@pytest.mark.asyncio
async def test_user_isolation():
    """测试用户隔离 - alice 看不到 bob 的消息"""
    from copaw.app.console_push_store import append, take

    await append("alice", "session_1", "Alice's message")
    await append("bob", "session_1", "Bob's message")

    alice_messages = await take("alice", "session_1")
    bob_messages = await take("bob", "session_1")

    assert len(alice_messages) == 1
    assert alice_messages[0]["text"] == "Alice's message"
    assert len(bob_messages) == 1
    assert bob_messages[0]["text"] == "Bob's message"


@pytest.mark.asyncio
async def test_take_all_for_user():
    """测试 take_all 返回用户所有消息"""
    from copaw.app.console_push_store import append, take_all

    await append("alice", "session_1", "Message 1")
    await append("alice", "session_2", "Message 2")
    await append("bob", "session_1", "Bob's message")

    alice_all = await take_all("alice")
    assert len(alice_all) == 2
    texts = [m["text"] for m in alice_all]
    assert "Message 1" in texts
    assert "Message 2" in texts


@pytest.mark.asyncio
async def test_get_recent_non_consuming():
    """测试 get_recent 不消费消息"""
    from copaw.app.console_push_store import append, get_recent

    await append("alice", "session_1", "Recent message")

    # First call - should return message but not consume
    messages1 = await get_recent("alice", max_age_seconds=60)
    assert len(messages1) == 1

    # Second call - should still return the same message
    messages2 = await get_recent("alice", max_age_seconds=60)
    assert len(messages2) == 1


@pytest.mark.asyncio
async def test_get_recent_expires_old_messages():
    """测试 get_recent 清理过期消息"""
    from copaw.app.console_push_store import append, get_recent

    now = time.time()
    with patch("time.time", return_value=now):
        await append("alice", "session_1", "Old message")

    # Simulate time passing (70 seconds later)
    with patch("time.time", return_value=now + 70):
        messages = await get_recent("alice", max_age_seconds=60)
        assert len(messages) == 0  # Message expired
