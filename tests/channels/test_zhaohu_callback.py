# -*- coding: utf-8 -*-
"""Tests for Zhaohu channel callback functionality.

Test cases:
1. Configuration tests
2. Session isolation tests
3. Message deduplication tests
4. Callback API tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncGenerator

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from copaw.config.config import ZhaohuConfig, ChannelConfig
from copaw.app.routers.zhaohu import (
    ZhaohuCallbackRequest,
    zhaohu_router,
    _get_zhaohu_channel,
    _process_callback_background,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def zhaohu_config() -> ZhaohuConfig:
    """Create a test ZhaohuConfig instance."""
    return ZhaohuConfig(
        enabled=True,
        push_url="https://test.example.com/push",
        sys_id="test_sys",
        robot_open_id="test_robot",
        user_query_url="https://test.example.com/user/query",
    )


@pytest.fixture
def mock_channel(zhaohu_config: ZhaohuConfig):
    """Create a mock ZhaohuChannel for testing."""
    from copaw.app.channels.zhaohu.channel import ZhaohuChannel

    channel = MagicMock(spec=ZhaohuChannel)
    channel.channel = "zhaohu"
    channel.enabled = True
    channel.try_accept_message = MagicMock(return_value=True)
    channel.process_callback_message = AsyncMock()
    channel.user_query_url = zhaohu_config.user_query_url
    channel.push_url = zhaohu_config.push_url

    return channel


@pytest.fixture
async def client(mock_channel) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with zhaohu routes."""
    app = FastAPI()
    app.include_router(zhaohu_router)

    # Mock channel manager
    mock_channel_manager = MagicMock()
    mock_channel_manager.channels = [mock_channel]
    app.state.channel_manager = mock_channel_manager

    async with AsyncClient(
        transport=ASGITransport(app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def callback_request() -> dict:
    """Create a sample callback request body."""
    return {
        "msgId": "test_msg_001",
        "fromId": "test_open_id_001",
        "toId": "test_bot_id",
        "groupId": None,
        "groupName": None,
        "msgType": "text",
        "msgContent": "你好，请介绍一下自己",
        "timestamp": 1711094400000,
    }


# ============================================================================
# Configuration Tests
# ============================================================================

class TestZhaohuConfig:
    """Test ZhaohuConfig configuration class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ZhaohuConfig()
        assert config.enabled is False
        assert config.push_url == ""
        assert config.sys_id == ""
        assert config.robot_open_id == ""
        assert config.channel == "ZH"
        assert config.net == "DMZ"
        assert config.request_timeout == 15.0
        assert config.user_query_url == ""

    def test_custom_values(self, zhaohu_config: ZhaohuConfig):
        """Test custom configuration values."""
        assert zhaohu_config.enabled is True
        assert zhaohu_config.push_url == "https://test.example.com/push"
        assert zhaohu_config.sys_id == "test_sys"
        assert zhaohu_config.robot_open_id == "test_robot"
        assert zhaohu_config.user_query_url == "https://test.example.com/user/query"

    def test_channel_config_includes_zhaohu(self):
        """Test that ChannelConfig includes zhaohu."""
        ch = ChannelConfig()
        assert hasattr(ch, "zhaohu")
        assert isinstance(ch.zhaohu, ZhaohuConfig)

    def test_channel_config_from_dict(self):
        """Test creating ChannelConfig from dictionary."""
        data = {
            "zhaohu": {
                "enabled": True,
                "push_url": "https://api.zhaohu.example/push",
                "sys_id": "copaw",
                "robot_open_id": "robot-1",
                "user_query_url": "https://api.zhaohu.example/user/query",
            },
        }
        ch = ChannelConfig(**data)
        assert ch.zhaohu.enabled is True
        assert ch.zhaohu.push_url == "https://api.zhaohu.example/push"
        assert ch.zhaohu.user_query_url == "https://api.zhaohu.example/user/query"


# ============================================================================
# Session Isolation Tests
# ============================================================================

class TestSessionIsolation:
    """Test session isolation for Zhaohu channel."""

    def test_resolve_session_id_format(self):
        """Test session_id format: zhaohu:callback:{sapId}."""
        from copaw.app.channels.zhaohu.channel import ZhaohuChannel

        # Create channel with minimal config
        channel = ZhaohuChannel(
            process=lambda x: None,
            enabled=True,
            push_url="",
            sys_id="",
            robot_open_id="",
            channel_code="ZH",
            net="DMZ",
            request_timeout=15.0,
            bot_prefix="",
        )

        session_id = channel.resolve_session_id("SAP001")
        assert session_id == "zhaohu:callback:SAP001"

    def test_same_user_same_session(self):
        """Test that same user gets same session_id."""
        from copaw.app.channels.zhaohu.channel import ZhaohuChannel

        channel = ZhaohuChannel(
            process=lambda x: None,
            enabled=True,
            push_url="",
            sys_id="",
            robot_open_id="",
            channel_code="ZH",
            net="DMZ",
            request_timeout=15.0,
            bot_prefix="",
        )

        session1 = channel.resolve_session_id("SAP001")
        session2 = channel.resolve_session_id("SAP001")
        assert session1 == session2

    def test_different_users_different_sessions(self):
        """Test that different users get different session_ids."""
        from copaw.app.channels.zhaohu.channel import ZhaohuChannel

        channel = ZhaohuChannel(
            process=lambda x: None,
            enabled=True,
            push_url="",
            sys_id="",
            robot_open_id="",
            channel_code="ZH",
            net="DMZ",
            request_timeout=15.0,
            bot_prefix="",
        )

        session1 = channel.resolve_session_id("SAP001")
        session2 = channel.resolve_session_id("SAP002")
        assert session1 != session2

    def test_session_id_not_uuid_format(self):
        """Test that session_id is NOT in UUID format (frontend sessions use UUID)."""
        from copaw.app.channels.zhaohu.channel import ZhaohuChannel
        import re

        channel = ZhaohuChannel(
            process=lambda x: None,
            enabled=True,
            push_url="",
            sys_id="",
            robot_open_id="",
            channel_code="ZH",
            net="DMZ",
            request_timeout=15.0,
            bot_prefix="",
        )

        session_id = channel.resolve_session_id("SAP001")

        # Should not match UUID pattern
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        assert not uuid_pattern.match(session_id)


# ============================================================================
# Message Deduplication Tests
# ============================================================================

class TestMessageDeduplication:
    """Test message deduplication mechanism."""

    def test_accept_new_message(self):
        """Test that new message is accepted."""
        from copaw.app.channels.zhaohu.channel import ZhaohuChannel

        channel = ZhaohuChannel(
            process=lambda x: None,
            enabled=True,
            push_url="",
            sys_id="",
            robot_open_id="",
            channel_code="ZH",
            net="DMZ",
            request_timeout=15.0,
            bot_prefix="",
        )

        result = channel.try_accept_message("msg_001")
        assert result is True

    def test_reject_duplicate_message(self):
        """Test that duplicate message is rejected."""
        from copaw.app.channels.zhaohu.channel import ZhaohuChannel

        channel = ZhaohuChannel(
            process=lambda x: None,
            enabled=True,
            push_url="",
            sys_id="",
            robot_open_id="",
            channel_code="ZH",
            net="DMZ",
            request_timeout=15.0,
            bot_prefix="",
        )

        # First message should be accepted
        result1 = channel.try_accept_message("msg_001")
        assert result1 is True

        # Duplicate should be rejected
        result2 = channel.try_accept_message("msg_001")
        assert result2 is False

    def test_different_messages_accepted(self):
        """Test that different messages are all accepted."""
        from copaw.app.channels.zhaohu.channel import ZhaohuChannel

        channel = ZhaohuChannel(
            process=lambda x: None,
            enabled=True,
            push_url="",
            sys_id="",
            robot_open_id="",
            channel_code="ZH",
            net="DMZ",
            request_timeout=15.0,
            bot_prefix="",
        )

        result1 = channel.try_accept_message("msg_001")
        result2 = channel.try_accept_message("msg_002")
        result3 = channel.try_accept_message("msg_003")

        assert result1 is True
        assert result2 is True
        assert result3 is True

    def test_empty_msg_id_accepted(self):
        """Test that empty msg_id is accepted (no dedup for empty ID)."""
        from copaw.app.channels.zhaohu.channel import ZhaohuChannel

        channel = ZhaohuChannel(
            process=lambda x: None,
            enabled=True,
            push_url="",
            sys_id="",
            robot_open_id="",
            channel_code="ZH",
            net="DMZ",
            request_timeout=15.0,
            bot_prefix="",
        )

        result = channel.try_accept_message("")
        assert result is True


# ============================================================================
# Callback Request Model Tests
# ============================================================================

class TestZhaohuCallbackRequest:
    """Test ZhaohuCallbackRequest model."""

    def test_parse_camel_case_fields(self):
        """Test parsing fields with camelCase aliases."""
        body = {
            "msgId": "test_001",
            "fromId": "open_001",
            "toId": "bot_001",
            "groupId": 12345,
            "groupName": "Test Group",
            "msgType": "text",
            "msgContent": "Hello",
            "timestamp": 1711094400000,
        }

        request = ZhaohuCallbackRequest(**body)

        assert request.msg_id == "test_001"
        assert request.from_id == "open_001"
        assert request.to_id == "bot_001"
        assert request.group_id == 12345
        assert request.group_name == "Test Group"
        assert request.msg_type == "text"
        assert request.msg_content == "Hello"
        assert request.timestamp == 1711094400000

    def test_parse_snake_case_fields(self):
        """Test parsing fields with snake_case."""
        body = {
            "msg_id": "test_001",
            "from_id": "open_001",
            "to_id": "bot_001",
            "msg_type": "text",
            "msg_content": "Hello",
            "timestamp": 1711094400000,
        }

        request = ZhaohuCallbackRequest(**body)

        assert request.msg_id == "test_001"
        assert request.from_id == "open_001"

    def test_default_values(self):
        """Test default values for optional fields."""
        request = ZhaohuCallbackRequest()

        assert request.msg_id == ""
        assert request.from_id == ""
        assert request.to_id == ""
        assert request.group_id is None
        assert request.group_name is None
        assert request.msg_type == ""
        assert request.msg_content == ""
        assert request.timestamp == 0
        assert request.custom_info is None


# ============================================================================
# Callback API Tests
# ============================================================================

class TestZhaohuCallbackAPI:
    """Test Zhaohu callback API endpoints."""

    @pytest.mark.asyncio
    async def test_callback_success(
        self,
        client: AsyncClient,
        callback_request: dict,
        mock_channel
    ):
        """Test successful callback."""
        response = await client.post(
            "/api/zhaohu/callback",
            json=callback_request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "ok"
        assert data["message"] == "received"

        # Verify dedup was called
        mock_channel.try_accept_message.assert_called_once_with("test_msg_001")

    @pytest.mark.asyncio
    async def test_callback_duplicate_message(
        self,
        client: AsyncClient,
        callback_request: dict,
        mock_channel
    ):
        """Test duplicate message handling."""
        # First call accepts
        mock_channel.try_accept_message.return_value = True
        response1 = await client.post(
            "/api/zhaohu/callback",
            json=callback_request,
        )
        assert response1.json()["message"] == "received"

        # Second call rejects as duplicate
        mock_channel.try_accept_message.return_value = False
        response2 = await client.post(
            "/api/zhaohu/callback",
            json=callback_request,
        )
        assert response2.json()["message"] == "duplicate ignored"

    @pytest.mark.asyncio
    async def test_callback_channel_disabled(
        self,
        callback_request: dict,
        mock_channel
    ):
        """Test callback when channel is disabled."""
        mock_channel.enabled = False

        app = FastAPI()
        app.include_router(zhaohu_router)
        mock_channel_manager = MagicMock()
        mock_channel_manager.channels = [mock_channel]
        app.state.channel_manager = mock_channel_manager

        async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/zhaohu/callback",
                json=callback_request,
            )

        assert response.status_code == 503
        assert "disabled" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_callback_channel_not_available(
        self,
        callback_request: dict
    ):
        """Test callback when channel is not available."""
        app = FastAPI()
        app.include_router(zhaohu_router)
        # No channel manager
        app.state.channel_manager = None

        async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/zhaohu/callback",
                json=callback_request,
            )

        assert response.status_code == 503
        assert "not available" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_callback_private_chat(
        self,
        client: AsyncClient,
        mock_channel
    ):
        """Test private chat (no groupId)."""
        private_request = {
            "msgId": "private_001",
            "fromId": "user_open_id",
            "toId": "bot_id",
            "groupId": None,  # Private chat
            "groupName": None,
            "msgType": "text",
            "msgContent": "私聊消息",
            "timestamp": 1711094400000,
        }

        response = await client.post(
            "/api/zhaohu/callback",
            json=private_request,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_callback_group_chat(
        self,
        client: AsyncClient,
        mock_channel
    ):
        """Test group chat (with groupId)."""
        group_request = {
            "msgId": "group_001",
            "fromId": "user_open_id",
            "toId": "bot_id",
            "groupId": 920000306024,  # Group chat
            "groupName": "测试群组",
            "msgType": "at",
            "msgContent": "@bot 群聊消息",
            "timestamp": 1711094400000,
        }

        response = await client.post(
            "/api/zhaohu/callback",
            json=group_request,
        )

        assert response.status_code == 200


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    def test_get_zhaohu_channel_found(self, mock_channel):
        """Test finding zhaohu channel in app state."""
        request = MagicMock()
        request.app.state.channel_manager.channels = [mock_channel]

        result = _get_zhaohu_channel(request)
        assert result == mock_channel

    def test_get_zhaohu_channel_not_found(self):
        """Test when zhaohu channel is not found."""
        request = MagicMock()
        request.app.state.channel_manager.channels = []

        result = _get_zhaohu_channel(request)
        assert result is None

    def test_get_zhaohu_channel_no_app(self):
        """Test when request has no app."""
        request = MagicMock(spec=['app'])
        request.app = None

        result = _get_zhaohu_channel(request)
        assert result is None


# ============================================================================
# Integration Tests (marked for manual execution)
# ============================================================================

@pytest.mark.integration
class TestZhaohuIntegration:
    """Integration tests for Zhaohu channel (requires running service)."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires running service and real endpoints")
    async def test_full_message_flow(self):
        """
        Test full message flow:
        1. Receive callback
        2. Query user info
        3. Call LLM
        4. Send response via push_url

        This test should be run manually with:
        - Running CoPaw service
        - Configured user_query_url
        - Configured push_url
        - Valid LLM API keys
        """
        pass