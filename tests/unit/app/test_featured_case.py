# -*- coding: utf-8 -*-
"""Unit tests for featured case module."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from swe.app.featured_case.models import (
    CaseConfigCreate,
    CaseConfigItem,
    CaseStep,
    FeaturedCase,
    FeaturedCaseCreate,
    FeaturedCaseUpdate,
)
from swe.app.featured_case.service import FeaturedCaseService
from swe.app.featured_case.store import FeaturedCaseStore


class TestModels:
    """Tests for data models."""

    def test_case_step(self):
        """Test CaseStep model."""
        step = CaseStep(title="步骤1", content="内容1")
        assert step.title == "步骤1"
        assert step.content == "内容1"

    def test_featured_case_model(self):
        """Test FeaturedCase model creation."""
        case = FeaturedCase(
            id=1,
            case_id="case-001",
            label="存款案例",
            value="我要做存款经营",
            iframe_url="https://example.com",
            iframe_title="详情",
            is_active=True,
        )
        assert case.case_id == "case-001"
        assert case.label == "存款案例"
        assert case.is_active is True

    # pylint: disable=unsubscriptable-object
    def test_featured_case_with_steps(self):
        """Test FeaturedCase with steps."""
        steps = [
            CaseStep(title="步骤1", content="内容1"),
            CaseStep(title="步骤2", content="内容2"),
        ]
        case = FeaturedCase(
            case_id="case-001",
            label="案例",
            value="内容",
            steps=steps,
        )
        steps = case.steps
        assert steps is not None
        assert len(steps) == 2
        assert steps[0].title == "步骤1"

    def test_featured_case_create_validation(self):
        """Test FeaturedCaseCreate validation."""
        # Valid request
        request = FeaturedCaseCreate(
            case_id="case-001",
            label="案例",
            value="内容",
        )
        assert request.image_url is None
        assert request.steps is None

        # Empty case_id should fail
        with pytest.raises(ValueError):
            FeaturedCaseCreate(case_id="", label="test", value="test")

    def test_featured_case_update(self):
        """Test FeaturedCaseUpdate model."""
        request = FeaturedCaseUpdate(
            label="新标题",
            is_active=False,
        )
        assert request.label == "新标题"
        assert request.value is None

    def test_case_config_item(self):
        """Test CaseConfigItem model."""
        item = CaseConfigItem(case_id="case-001", sort_order=1)
        assert item.case_id == "case-001"
        assert item.sort_order == 1

    def test_case_config_create(self):
        """Test CaseConfigCreate model."""
        config = CaseConfigCreate(
            source_id="source1",
            bbk_id="bbk1",
            case_ids=[
                CaseConfigItem(case_id="case-001", sort_order=1),
                CaseConfigItem(case_id="case-002", sort_order=2),
            ],
        )
        assert config.source_id == "source1"
        assert len(config.case_ids) == 2

    def test_case_config_create_without_bbk_id(self):
        """Test CaseConfigCreate without bbk_id."""
        config = CaseConfigCreate(
            source_id="source1",
            case_ids=[],
        )
        assert config.bbk_id is None


class TestFeaturedCaseStore:
    """Tests for FeaturedCaseStore without database."""

    @pytest.fixture
    def store(self):
        """Create store without database."""
        return FeaturedCaseStore(db=None)

    def test_store_initialization(self, store):
        """Test store initializes correctly without database."""
        assert store.db is None
        # pylint: disable=protected-access
        assert store._use_db is False

    @pytest.mark.asyncio
    async def test_get_cases_for_dimension_no_db(self, store):
        """Test get_cases_for_dimension returns empty without database."""
        result = await store.get_cases_for_dimension("source1", "bbk1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_case_by_id_no_db(self, store):
        """Test get_case_by_id returns None without database."""
        result = await store.get_case_by_id("case-001")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_cases_no_db(self, store):
        """Test list_cases returns empty without database."""
        cases, total = await store.list_cases()
        assert cases == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_create_case_no_db(self, store):
        """Test create_case returns case without database."""
        case = FeaturedCase(
            case_id="case-001",
            label="案例",
            value="内容",
        )
        result = await store.create_case(case)
        assert result.case_id == "case-001"

    @pytest.mark.asyncio
    async def test_update_case_no_db(self, store):
        """Test update_case returns None without database."""
        result = await store.update_case("case-001", label="新")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_case_no_db(self, store):
        """Test delete_case returns False without database."""
        result = await store.delete_case("case-001")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_configs_no_db(self, store):
        """Test list_configs returns empty without database."""
        configs, total = await store.list_configs()
        assert configs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_upsert_config_no_db(self, store):
        """Test upsert_config returns False without database."""
        result = await store.upsert_config("source1", "bbk1", [])
        assert result is False


class TestFeaturedCaseStoreWithMockDb:
    """Tests for FeaturedCaseStore with mocked database."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database connection."""
        db = MagicMock()
        db.is_connected = True
        db.fetch_one = AsyncMock()
        db.fetch_all = AsyncMock()
        db.execute = AsyncMock(return_value=1)
        db.execute_many = AsyncMock(return_value=None)
        return db

    @pytest.fixture
    def store(self, mock_db):
        """Create store with mock database."""
        return FeaturedCaseStore(db=mock_db)

    @pytest.mark.asyncio
    async def test_get_cases_for_dimension(self, store, mock_db):
        """Test get_cases_for_dimension returns cases."""
        mock_db.fetch_all.return_value = [
            {
                "case_id": "case-001",
                "label": "存款案例",
                "value": "我要做存款",
                "image_url": None,
                "iframe_url": "https://example.com",
                "iframe_title": "详情",
                "steps": json.dumps([{"title": "步骤1", "content": "内容1"}]),
                "sort_order": 1,
            },
            {
                "case_id": "case-002",
                "label": "基金案例",
                "value": "我要买基金",
                "image_url": None,
                "iframe_url": None,
                "iframe_title": None,
                "steps": None,
                "sort_order": 2,
            },
        ]
        result = await store.get_cases_for_dimension("source1", "bbk1")
        assert len(result) == 2
        assert result[0]["id"] == "case-001"
        assert result[0]["detail"]["steps"][0]["title"] == "步骤1"
        assert result[1]["detail"] is None  # No iframe_url

    @pytest.mark.asyncio
    async def test_get_cases_for_dimension_with_null_bbk_id(
        self,
        store,
        mock_db,
    ):
        """Test get_cases_for_dimension with null bbk_id."""
        mock_db.fetch_all.return_value = []
        await store.get_cases_for_dimension("source1", None)
        # Verify query was called (NULL-safe comparison is in SQL)
        mock_db.fetch_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_case_by_id(self, store, mock_db):
        """Test get_case_by_id returns case."""
        mock_db.fetch_one.return_value = {
            "id": 1,
            "case_id": "case-001",
            "label": "案例",
            "value": "内容",
            "image_url": None,
            "iframe_url": "https://example.com",
            "iframe_title": "详情",
            "steps": json.dumps([{"title": "步骤1", "content": "内容1"}]),
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": None,
        }
        result = await store.get_case_by_id("case-001")
        assert result is not None
        assert result.case_id == "case-001"
        assert len(result.steps) == 1

    @pytest.mark.asyncio
    async def test_list_cases_with_pagination(self, store, mock_db):
        """Test list_cases with pagination."""
        mock_db.fetch_one.return_value = {"total": 10}
        mock_db.fetch_all.return_value = [
            {
                "id": 1,
                "case_id": "case-001",
                "label": "案例1",
                "value": "内容1",
                "image_url": None,
                "iframe_url": None,
                "iframe_title": None,
                "steps": None,
                "is_active": 1,
                "created_at": datetime.now(),
                "updated_at": None,
            },
        ]
        cases, total = await store.list_cases(page=1, page_size=10)
        assert total == 10
        assert len(cases) == 1

    @pytest.mark.asyncio
    async def test_create_case_with_db(self, store, mock_db):
        """Test create_case with database."""
        case = FeaturedCase(
            case_id="case-001",
            label="案例",
            value="内容",
            steps=[CaseStep(title="步骤1", content="内容1")],
            is_active=True,
        )
        result = await store.create_case(case)
        mock_db.execute.assert_called_once()
        assert result.case_id == "case-001"

    @pytest.mark.asyncio
    async def test_update_case_with_db(self, store, mock_db):
        """Test update_case with database."""
        mock_db.fetch_one.return_value = {
            "id": 1,
            "case_id": "case-001",
            "label": "新标题",
            "value": "新内容",
            "image_url": None,
            "iframe_url": None,
            "iframe_title": None,
            "steps": None,
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        result = await store.update_case("case-001", label="新标题")
        assert result is not None
        assert result.label == "新标题"

    @pytest.mark.asyncio
    async def test_delete_case_with_db(self, store, mock_db):
        """Test delete_case with database."""
        result = await store.delete_case("case-001")
        assert result is True
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_case_exists_true(self, store, mock_db):
        """Test check_case_exists returns True."""
        mock_db.fetch_one.return_value = {"cnt": 1}
        result = await store.check_case_exists("case-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_list_configs_with_db(self, store, mock_db):
        """Test list_configs with database."""
        mock_db.fetch_one.return_value = {"total": 5}
        mock_db.fetch_all.return_value = [
            {"source_id": "source1", "bbk_id": "bbk1", "case_count": 3},
            {"source_id": "source1", "bbk_id": None, "case_count": 2},
        ]
        configs, total = await store.list_configs()
        assert total == 5
        assert len(configs) == 2
        assert configs[0]["case_count"] == 3

    @pytest.mark.asyncio
    async def test_get_config_cases(self, store, mock_db):
        """Test get_config_cases returns case_ids."""
        mock_db.fetch_all.return_value = [
            {"case_id": "case-001"},
            {"case_id": "case-002"},
        ]
        result = await store.get_config_cases("source1", "bbk1")
        assert result == ["case-001", "case-002"]

    @pytest.mark.asyncio
    async def test_upsert_config_with_db(self, store, mock_db):
        """Test upsert_config with database."""
        case_ids = [
            {"case_id": "case-001", "sort_order": 1},
            {"case_id": "case-002", "sort_order": 2},
        ]
        result = await store.upsert_config("source1", "bbk1", case_ids)
        assert result is True
        mock_db.execute.assert_called_once()  # Delete
        mock_db.execute_many.assert_called_once()  # Insert

    @pytest.mark.asyncio
    async def test_upsert_config_empty_list(self, store, mock_db):
        """Test upsert_config with empty case_ids (deletes only)."""
        result = await store.upsert_config("source1", "bbk1", [])
        assert result is True
        mock_db.execute.assert_called_once()  # Delete only
        mock_db.execute_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_config_with_db(self, store, mock_db):
        """Test delete_config with database."""
        result = await store.delete_config("source1", "bbk1")
        assert result is True
        mock_db.execute.assert_called_once()


class TestFeaturedCaseService:
    """Tests for FeaturedCaseService."""

    @pytest.fixture
    def mock_store(self):
        """Create mock store."""
        store = MagicMock(spec=FeaturedCaseStore)
        store.get_cases_for_dimension = AsyncMock(return_value=[])
        store.get_case_by_id = AsyncMock()
        store.list_cases = AsyncMock(return_value=([], 0))
        store.create_case = AsyncMock()
        store.update_case = AsyncMock()
        store.delete_case = AsyncMock()
        store.check_case_exists = AsyncMock(return_value=False)
        store.list_configs = AsyncMock(return_value=([], 0))
        store.get_config_cases = AsyncMock(return_value=[])
        store.upsert_config = AsyncMock()
        store.delete_config = AsyncMock()
        return store

    @pytest.fixture
    def service(self, mock_store):
        """Create service with mock store."""
        return FeaturedCaseService(mock_store)

    @pytest.mark.asyncio
    async def test_get_cases_for_dimension(self, service, mock_store):
        """Test get_cases_for_dimension delegates to store."""
        expected = [{"id": "case-001", "label": "案例"}]
        mock_store.get_cases_for_dimension.return_value = expected
        result = await service.get_cases_for_dimension("source1", "bbk1")
        assert result == expected

    @pytest.mark.asyncio
    async def test_create_case_success(self, service, mock_store):
        """Test create_case succeeds when no duplicate."""
        request = FeaturedCaseCreate(
            case_id="case-001",
            label="案例",
            value="内容",
        )
        expected = FeaturedCase(
            case_id="case-001",
            label="案例",
            value="内容",
            is_active=True,
        )
        mock_store.create_case.return_value = expected
        result = await service.create_case(request)
        assert result.case_id == "case-001"
        mock_store.check_case_exists.assert_called_once_with("case-001")

    @pytest.mark.asyncio
    async def test_create_case_duplicate_raises(self, service, mock_store):
        """Test create_case raises when duplicate exists."""
        mock_store.check_case_exists.return_value = True
        request = FeaturedCaseCreate(
            case_id="case-001",
            label="案例",
            value="内容",
        )
        with pytest.raises(ValueError, match="已存在"):
            await service.create_case(request)

    @pytest.mark.asyncio
    async def test_update_case_success(self, service, mock_store):
        """Test update_case succeeds."""
        expected = FeaturedCase(
            case_id="case-001",
            label="新标题",
            value="新内容",
        )
        mock_store.update_case.return_value = expected
        request = FeaturedCaseUpdate(label="新标题")
        result = await service.update_case("case-001", request)
        assert result.label == "新标题"

    @pytest.mark.asyncio
    async def test_update_case_not_found_raises(self, service, mock_store):
        """Test update_case raises when not found."""
        mock_store.update_case.return_value = None
        request = FeaturedCaseUpdate(label="新")
        with pytest.raises(ValueError, match="不存在"):
            await service.update_case("case-001", request)

    @pytest.mark.asyncio
    async def test_delete_case_success(self, service, mock_store):
        """Test delete_case succeeds."""
        mock_store.delete_case.return_value = True
        await service.delete_case("case-001")
        mock_store.delete_case.assert_called_once_with("case-001")

    @pytest.mark.asyncio
    async def test_delete_case_not_found_raises(self, service, mock_store):
        """Test delete_case raises when not found."""
        mock_store.delete_case.return_value = False
        with pytest.raises(ValueError, match="不存在"):
            await service.delete_case("case-001")

    @pytest.mark.asyncio
    async def test_upsert_config_validates_case_ids(self, service, mock_store):
        """Test upsert_config validates case_ids exist."""
        mock_store.check_case_exists.side_effect = (
            lambda cid: cid == "case-001"
        )
        request = CaseConfigCreate(
            source_id="source1",
            case_ids=[
                CaseConfigItem(case_id="case-001", sort_order=1),
                CaseConfigItem(case_id="case-002", sort_order=2),  # Invalid
            ],
        )
        with pytest.raises(ValueError, match="无效的案例 ID"):
            await service.upsert_config(request)

    @pytest.mark.asyncio
    async def test_upsert_config_success(self, service, mock_store):
        """Test upsert_config succeeds when all case_ids valid."""
        mock_store.check_case_exists.return_value = True
        request = CaseConfigCreate(
            source_id="source1",
            bbk_id="bbk1",
            case_ids=[
                CaseConfigItem(case_id="case-001", sort_order=1),
            ],
        )
        await service.upsert_config(request)
        mock_store.upsert_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_config_success(self, service, mock_store):
        """Test delete_config succeeds."""
        mock_store.delete_config.return_value = True
        await service.delete_config("source1", "bbk1")
        mock_store.delete_config.assert_called_once_with("source1", "bbk1")

    @pytest.mark.asyncio
    async def test_delete_config_not_found_raises(self, service, mock_store):
        """Test delete_config raises when not found."""
        mock_store.delete_config.return_value = False
        with pytest.raises(ValueError, match="不存在"):
            await service.delete_config("source1", "bbk1")
