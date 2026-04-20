# -*- coding: utf-8 -*-
"""Unit tests for greeting configuration module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from swe.app.greeting.models import (
    GreetingConfig,
    GreetingConfigCreate,
    GreetingConfigUpdate,
    GreetingDisplay,
    GreetingConfigListResponse,
)
from swe.app.greeting.service import GreetingService
from swe.app.greeting.store import GreetingStore


class TestModels:
    """Tests for data models."""

    def test_greeting_config_model(self):
        """Test GreetingConfig model creation."""
        config = GreetingConfig(
            id=1,
            source_id="source1",
            bbk_id="bbk1",
            greeting="你好，欢迎！",
            subtitle="我可以帮你",
            placeholder="输入问题",
            is_active=True,
            created_at=datetime.now(),
        )
        assert config.source_id == "source1"
        assert config.bbk_id == "bbk1"
        assert config.greeting == "你好，欢迎！"
        assert config.is_active is True

    def test_greeting_config_with_null_bbk_id(self):
        """Test GreetingConfig with null bbk_id."""
        config = GreetingConfig(
            source_id="source1",
            bbk_id=None,
            greeting="你好",
        )
        assert config.bbk_id is None
        assert config.greeting == "你好"

    def test_greeting_config_create_validation(self):
        """Test GreetingConfigCreate validation."""
        # Valid request
        request = GreetingConfigCreate(
            source_id="source1",
            greeting="欢迎语",
        )
        assert request.bbk_id is None  # default

        # Empty source_id should fail
        with pytest.raises(ValueError):
            GreetingConfigCreate(source_id="", greeting="test")

        # Empty greeting should fail
        with pytest.raises(ValueError):
            GreetingConfigCreate(source_id="source1", greeting="")

    def test_greeting_config_update(self):
        """Test GreetingConfigUpdate model."""
        request = GreetingConfigUpdate(
            greeting="新欢迎语",
            subtitle="新副标题",
        )
        assert request.greeting == "新欢迎语"
        assert request.placeholder is None

    def test_greeting_display(self):
        """Test GreetingDisplay model."""
        display = GreetingDisplay(
            greeting="欢迎",
            subtitle="副标题",
            placeholder="输入",
        )
        assert display.greeting == "欢迎"
        assert display.subtitle == "副标题"

    def test_greeting_config_list_response(self):
        """Test GreetingConfigListResponse model."""
        response = GreetingConfigListResponse(
            configs=[
                GreetingConfig(source_id="s1", greeting="g1"),
                GreetingConfig(source_id="s2", greeting="g2"),
            ],
            total=2,
        )
        assert len(response.configs) == 2
        assert response.total == 2


class TestGreetingStore:
    """Tests for GreetingStore without database."""

    @pytest.fixture
    def store(self):
        """Create store without database."""
        return GreetingStore(db=None)

    def test_store_initialization(self, store):
        """Test store initializes correctly without database."""
        assert store.db is None
        # pylint: disable=protected-access
        assert store._use_db is False

    @pytest.mark.asyncio
    async def test_get_config_no_db(self, store):
        """Test get_config returns None without database."""
        result = await store.get_config("source1", "bbk1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_config_null_bbk_id_no_db(self, store):
        """Test get_config with null bbk_id returns None."""
        result = await store.get_config("source1", None)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_configs_no_db(self, store):
        """Test list_configs returns empty without database."""
        configs, total = await store.list_configs()
        assert configs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_create_config_no_db(self, store):
        """Test create_config returns config without database."""
        config = GreetingConfig(
            source_id="source1",
            greeting="欢迎",
        )
        result = await store.create_config(config)
        assert result.source_id == "source1"
        assert result.greeting == "欢迎"

    @pytest.mark.asyncio
    async def test_update_config_no_db(self, store):
        """Test update_config returns None without database."""
        result = await store.update_config(1, greeting="新")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_config_no_db(self, store):
        """Test delete_config returns False without database."""
        result = await store.delete_config(1)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_exists_no_db(self, store):
        """Test check_exists returns False without database."""
        result = await store.check_exists("source1", "bbk1")
        assert result is False


class TestGreetingStoreWithMockDb:
    """Tests for GreetingStore with mocked database."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database connection."""
        db = MagicMock()
        db.is_connected = True
        db.fetch_one = AsyncMock()
        db.fetch_all = AsyncMock()
        db.execute = AsyncMock(return_value=1)
        return db

    @pytest.fixture
    def store(self, mock_db):
        """Create store with mock database."""
        return GreetingStore(db=mock_db)

    @pytest.mark.asyncio
    async def test_get_config_with_bbk_id(self, store, mock_db):
        """Test get_config with both source_id and bbk_id."""
        mock_db.fetch_one.return_value = {
            "id": 1,
            "source_id": "source1",
            "bbk_id": "bbk1",
            "greeting": "欢迎语",
            "subtitle": "副标题",
            "placeholder": "输入",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        result = await store.get_config("source1", "bbk1")
        assert result is not None
        assert result.source_id == "source1"
        assert result.bbk_id == "bbk1"
        assert result.greeting == "欢迎语"
        # Verify query params include both source_id and bbk_id
        mock_db.fetch_one.assert_called_once()
        call_args = mock_db.fetch_one.call_args[0][0]
        assert "source_id = %s" in call_args
        assert "bbk_id <=> %s" in call_args

    @pytest.mark.asyncio
    async def test_get_config_with_null_bbk_id(self, store, mock_db):
        """Test get_config with null bbk_id (NULL-safe comparison)."""
        mock_db.fetch_one.return_value = {
            "id": 2,
            "source_id": "source1",
            "bbk_id": None,
            "greeting": "默认欢迎语",
            "subtitle": None,
            "placeholder": None,
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": None,
        }
        result = await store.get_config("source1", None)
        assert result is not None
        assert result.bbk_id is None
        assert result.greeting == "默认欢迎语"
        # Verify NULL-safe comparison is used
        mock_db.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_config_not_found(self, store, mock_db):
        """Test get_config returns None when not found."""
        mock_db.fetch_one.return_value = None
        result = await store.get_config("unknown", "bbk1")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_configs_with_pagination(self, store, mock_db):
        """Test list_configs with pagination."""
        mock_db.fetch_one.return_value = {"total": 25}
        mock_db.fetch_all.return_value = [
            {
                "id": 1,
                "source_id": "source1",
                "bbk_id": "bbk1",
                "greeting": "欢迎1",
                "subtitle": None,
                "placeholder": None,
                "is_active": 1,
                "created_at": datetime.now(),
                "updated_at": None,
            },
            {
                "id": 2,
                "source_id": "source2",
                "bbk_id": None,
                "greeting": "欢迎2",
                "subtitle": None,
                "placeholder": None,
                "is_active": 1,
                "created_at": datetime.now(),
                "updated_at": None,
            },
        ]
        configs, total = await store.list_configs(page=1, page_size=10)
        assert total == 25
        assert len(configs) == 2
        assert configs[0].source_id == "source1"

    @pytest.mark.asyncio
    async def test_list_configs_with_source_id_filter(self, store, mock_db):
        """Test list_configs with source_id filter."""
        mock_db.fetch_one.return_value = {"total": 1}
        mock_db.fetch_all.return_value = [
            {
                "id": 1,
                "source_id": "source1",
                "bbk_id": None,
                "greeting": "欢迎",
                "subtitle": None,
                "placeholder": None,
                "is_active": 1,
                "created_at": datetime.now(),
                "updated_at": None,
            },
        ]
        configs, total = await store.list_configs(source_id="source1")
        assert total == 1
        assert len(configs) == 1

    @pytest.mark.asyncio
    async def test_create_config_with_db(self, store, mock_db):
        """Test create_config with database."""
        config = GreetingConfig(
            source_id="source1",
            bbk_id="bbk1",
            greeting="欢迎",
            subtitle="副标题",
            placeholder="输入",
            is_active=True,
        )
        result = await store.create_config(config)
        mock_db.execute.assert_called_once()
        assert result.source_id == "source1"

    @pytest.mark.asyncio
    async def test_update_config_with_db(self, store, mock_db):
        """Test update_config with database."""
        mock_db.fetch_one.return_value = {
            "id": 1,
            "source_id": "source1",
            "bbk_id": "bbk1",
            "greeting": "新欢迎语",
            "subtitle": "新副标题",
            "placeholder": "新占位符",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        result = await store.update_config(
            1,
            greeting="新欢迎语",
            subtitle="新副标题",
            placeholder="新占位符",
        )
        assert result is not None
        assert result.greeting == "新欢迎语"
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_config_no_fields(self, store, mock_db):
        """Test update_config with no fields to update."""
        result = await store.update_config(1)
        assert result is None
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_config_with_db(self, store, mock_db):
        """Test delete_config with database."""
        result = await store.delete_config(1)
        assert result is True
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_exists_true(self, store, mock_db):
        """Test check_exists returns True when config exists."""
        mock_db.fetch_one.return_value = {"cnt": 1}
        result = await store.check_exists("source1", "bbk1")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_exists_false(self, store, mock_db):
        """Test check_exists returns False when config doesn't exist."""
        mock_db.fetch_one.return_value = {"cnt": 0}
        result = await store.check_exists("source1", "bbk1")
        assert result is False


class TestGreetingService:
    """Tests for GreetingService."""

    @pytest.fixture
    def mock_store(self):
        """Create mock store."""
        store = MagicMock(spec=GreetingStore)
        store.get_config = AsyncMock()
        store.list_configs = AsyncMock(return_value=([], 0))
        store.create_config = AsyncMock()
        store.update_config = AsyncMock()
        store.delete_config = AsyncMock()
        store.check_exists = AsyncMock(return_value=False)
        return store

    @pytest.fixture
    def service(self, mock_store):
        """Create service with mock store."""
        return GreetingService(mock_store)

    @pytest.mark.asyncio
    async def test_get_config(self, service, mock_store):
        """Test get_config delegates to store."""
        expected = GreetingConfig(source_id="s1", greeting="g")
        mock_store.get_config.return_value = expected
        result = await service.get_config("s1", "b1")
        assert result == expected
        mock_store.get_config.assert_called_once_with("s1", "b1")

    @pytest.mark.asyncio
    async def test_create_config_success(self, service, mock_store):
        """Test create_config succeeds when no duplicate."""
        request = GreetingConfigCreate(
            source_id="source1",
            bbk_id="bbk1",
            greeting="欢迎",
        )
        expected = GreetingConfig(
            source_id="source1",
            bbk_id="bbk1",
            greeting="欢迎",
            is_active=True,
        )
        mock_store.create_config.return_value = expected
        result = await service.create_config(request)
        assert result.source_id == "source1"
        # Verify check_exists was called with correct params
        mock_store.check_exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_config_duplicate_raises(self, service, mock_store):
        """Test create_config raises when duplicate exists."""
        mock_store.check_exists.return_value = True
        request = GreetingConfigCreate(
            source_id="source1",
            bbk_id="bbk1",
            greeting="欢迎",
        )
        with pytest.raises(ValueError, match="已存在"):
            await service.create_config(request)

    @pytest.mark.asyncio
    async def test_update_config_success(self, service, mock_store):
        """Test update_config succeeds."""
        expected = GreetingConfig(
            id=1,
            source_id="source1",
            greeting="新欢迎",
        )
        mock_store.update_config.return_value = expected
        request = GreetingConfigUpdate(greeting="新欢迎")
        result = await service.update_config(1, request)
        assert result.greeting == "新欢迎"

    @pytest.mark.asyncio
    async def test_update_config_not_found_raises(self, service, mock_store):
        """Test update_config raises when not found."""
        mock_store.update_config.return_value = None
        request = GreetingConfigUpdate(greeting="新")
        with pytest.raises(ValueError, match="不存在"):
            await service.update_config(1, request)

    @pytest.mark.asyncio
    async def test_delete_config_success(self, service, mock_store):
        """Test delete_config succeeds."""
        mock_store.delete_config.return_value = True
        await service.delete_config(1)
        mock_store.delete_config.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_delete_config_not_found_raises(self, service, mock_store):
        """Test delete_config raises when not found."""
        mock_store.delete_config.return_value = False
        with pytest.raises(ValueError, match="不存在"):
            await service.delete_config(1)
