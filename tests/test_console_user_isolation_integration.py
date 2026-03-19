# -*- coding: utf-8 -*-
"""Integration tests for console user isolation."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock


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
async def test_cron_message_user_isolation():
    """测试定时器消息的用户隔离完整流程"""
    from copaw.app.console_push_store import append, take_all

    # 模拟定时器发送消息给 alice
    await append("alice", "session_1", "Hello Alice from cron")

    # 模拟定时器发送消息给 bob
    await append("bob", "session_1", "Hello Bob from cron")

    # Alice 只能看到自己的消息
    alice_messages = await take_all("alice")
    assert len(alice_messages) == 1
    assert alice_messages[0]["text"] == "Hello Alice from cron"

    # Bob 只能看到自己的消息
    bob_messages = await take_all("bob")
    assert len(bob_messages) == 1
    assert bob_messages[0]["text"] == "Hello Bob from cron"


@pytest.mark.asyncio
async def test_default_user_backward_compatibility():
    """测试默认用户的向后兼容性"""
    from copaw.app.console_push_store import append, take_all

    # 不指定 user_id（模拟旧代码）
    await append(None, "session_1", "Default user message")

    # 使用 "default" 获取
    messages = await take_all("default")
    assert len(messages) == 1
    assert messages[0]["text"] == "Default user message"


@pytest.mark.asyncio
async def test_console_channel_send_with_user_id():
    """测试 ConsoleChannel 正确传递 user_id"""
    from copaw.app.channels.console.channel import ConsoleChannel
    from copaw.app.console_push_store import take_all

    # Mock process handler
    mock_process = AsyncMock()

    # Create channel
    channel = ConsoleChannel(
        process=mock_process,
        enabled=True,
        bot_prefix="[BOT] ",
    )

    # Send with user_id in meta
    await channel.send(
        to_handle="user123",
        text="Test message",
        meta={"session_id": "sess_1", "user_id": "alice"},
    )

    # Verify message stored with correct user_id
    messages = await take_all("alice")
    assert len(messages) == 1
    assert messages[0]["text"] == "Test message"

    # Verify bob cannot see alice's message
    bob_messages = await take_all("bob")
    assert len(bob_messages) == 0


@pytest.mark.asyncio
async def test_console_channel_send_content_parts_with_user_id():
    """测试 ConsoleChannel send_content_parts 正确传递 user_id"""
    from copaw.app.channels.console.channel import ConsoleChannel
    from copaw.app.console_push_store import take_all
    from copaw.app.channels.base import ContentType

    # Mock process handler
    mock_process = AsyncMock()

    # Create channel
    channel = ConsoleChannel(
        process=mock_process,
        enabled=True,
        bot_prefix="[BOT] ",
    )

    # Create a text content part
    content_part = MagicMock()
    content_part.type = ContentType.TEXT
    content_part.text = "Content parts message"

    # Send with user_id in meta
    await channel.send_content_parts(
        to_handle="user123",
        parts=[content_part],
        meta={"session_id": "sess_1", "user_id": "alice"},
    )

    # Verify message stored with correct user_id
    messages = await take_all("alice")
    assert len(messages) == 1
    assert messages[0]["text"] == "[BOT] Content parts message"

    # Verify bob cannot see alice's message
    bob_messages = await take_all("bob")
    assert len(bob_messages) == 0


@pytest.mark.asyncio
async def test_api_router_with_user_id_header():
    """测试 API 路由正确处理 x-user-id header"""
    from copaw.app.console_push_store import append, get_recent

    # Add messages for different users
    await append("alice", "session_1", "Alice's message")
    await append("bob", "session_1", "Bob's message")

    # Simulate API call with alice's user_id
    alice_messages = await get_recent("alice")
    assert len(alice_messages) == 1
    assert alice_messages[0]["text"] == "Alice's message"

    # Simulate API call with bob's user_id
    bob_messages = await get_recent("bob")
    assert len(bob_messages) == 1
    assert bob_messages[0]["text"] == "Bob's message"

    # Simulate API call with default user_id
    default_messages = await get_recent("default")
    assert len(default_messages) == 0  # No messages for default user


@pytest.mark.asyncio
async def test_api_router_with_session_id():
    """测试 API 路由正确处理 session_id 参数"""
    from copaw.app.console_push_store import append, take

    # Add messages for different sessions
    await append("alice", "session_1", "Message 1")
    await append("alice", "session_2", "Message 2")

    # Take messages for session_1 only
    session_1_messages = await take("alice", "session_1")
    assert len(session_1_messages) == 1
    assert session_1_messages[0]["text"] == "Message 1"

    # session_2 message should still be there
    session_2_messages = await take("alice", "session_2")
    assert len(session_2_messages) == 1
    assert session_2_messages[0]["text"] == "Message 2"
