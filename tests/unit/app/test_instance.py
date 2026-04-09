# -*- coding: utf-8 -*-
"""Unit tests for instance management module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copaw.app.instance.models import (
    CreateInstanceRequest,
    DeleteAllocationRequest,
    Instance,
    InstanceStatus,
    InstanceWithUsage,
    MigrateUserRequest,
    Source,
    SourceWithStats,
    UpdateInstanceRequest,
    UserAllocation,
    UserAllocationStatus,
)
from copaw.app.instance.service import InstanceService
from copaw.app.instance.store import InstanceStore, calculate_warning_level


class TestCalculateWarningLevel:
    """Tests for warning level calculation."""

    def test_normal_level(self):
        """Test normal warning level."""
        assert calculate_warning_level(50, 100) == "normal"
        assert calculate_warning_level(79, 100) == "normal"

    def test_warning_level(self):
        """Test warning level (80-99%)."""
        assert calculate_warning_level(80, 100) == "warning"
        assert calculate_warning_level(90, 100) == "warning"

    def test_critical_level(self):
        """Test critical level (>=100%)."""
        assert calculate_warning_level(100, 100) == "critical"
        assert calculate_warning_level(150, 100) == "critical"

    def test_zero_max_users(self):
        """Test critical when max_users is zero."""
        assert calculate_warning_level(0, 0) == "critical"
        assert calculate_warning_level(5, 0) == "critical"


class TestModels:
    """Tests for data models."""

    def test_source_model(self):
        """Test Source model creation."""
        source = Source(
            source_id="source1",
            source_name="Source One",
            created_at=datetime.now(),
        )
        assert source.source_id == "source1"
        assert source.source_name == "Source One"

    def test_source_with_stats(self):
        """Test SourceWithStats model."""
        source = SourceWithStats(
            source_id="source1",
            source_name="Source One",
            total_instances=5,
            total_users=100,
            active_instances=4,
        )
        assert source.total_instances == 5
        assert source.total_users == 100
        assert source.active_instances == 4

    def test_instance_model(self):
        """Test Instance model."""
        instance = Instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
            max_users=100,
            status=InstanceStatus.ACTIVE,
        )
        assert instance.instance_id == "inst1"
        assert instance.status == InstanceStatus.ACTIVE

    def test_instance_with_usage(self):
        """Test InstanceWithUsage model."""
        instance = InstanceWithUsage(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
            max_users=100,
            status=InstanceStatus.ACTIVE,
            current_users=50,
            usage_percent=50.0,
            warning_level="normal",
        )
        assert instance.current_users == 50
        assert instance.usage_percent == 50.0
        assert instance.warning_level == "normal"

    def test_user_allocation_model(self):
        """Test UserAllocation model."""
        allocation = UserAllocation(
            id=1,
            user_id="user1",
            source_id="source1",
            instance_id="inst1",
            status=UserAllocationStatus.ACTIVE,
        )
        assert allocation.user_id == "user1"
        assert allocation.instance_id == "inst1"

    def test_create_instance_request_validation(self):
        """Test CreateInstanceRequest validation."""
        # Valid request
        request = CreateInstanceRequest(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        assert request.max_users == 100  # default value

        # Invalid max_users
        with pytest.raises(ValueError):
            CreateInstanceRequest(
                instance_id="inst1",
                source_id="source1",
                instance_name="Instance 1",
                instance_url="http://localhost:8001",
                max_users=0,  # below minimum
            )

    def test_update_instance_request(self):
        """Test UpdateInstanceRequest model."""
        request = UpdateInstanceRequest(
            instance_name="New Name",
            max_users=200,
        )
        assert request.instance_name == "New Name"
        assert request.max_users == 200
        assert request.instance_url is None


class TestInstanceStore:
    """Tests for InstanceStore without database."""

    @pytest.fixture
    def store(self):
        """Create store without database."""
        return InstanceStore(db=None)

    def test_store_initialization(self, store):
        """Test store initializes correctly without database."""
        assert store.db is None
        # pylint: disable=protected-access
        assert store._use_db is False

    @pytest.mark.asyncio
    async def test_get_source_no_db(self, store):
        """Test get_source returns None without database."""
        result = await store.get_source("source1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_sources_no_db(self, store):
        """Test get_sources returns empty list without database."""
        result = await store.get_sources()
        assert result == []

    @pytest.mark.asyncio
    async def test_create_instance_no_db(self, store):
        """Test create_instance returns instance without database."""
        result = await store.create_instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        assert result.instance_id == "inst1"
        assert result.source_id == "source1"

    @pytest.mark.asyncio
    async def test_get_instance_no_db(self, store):
        """Test get_instance returns None without database."""
        result = await store.get_instance("inst1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_instances_no_db(self, store):
        """Test get_instances returns empty list without database."""
        result = await store.get_instances()
        assert result == []

    @pytest.mark.asyncio
    async def test_create_allocation_no_db(self, store):
        """Test create_allocation returns allocation without database."""
        result = await store.create_allocation(
            user_id="user1",
            source_id="source1",
            instance_id="inst1",
        )
        assert result.user_id == "user1"
        assert result.instance_id == "inst1"

    @pytest.mark.asyncio
    async def test_get_allocation_no_db(self, store):
        """Test get_allocation returns None without database."""
        result = await store.get_allocation("user1", "source1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_allocations_no_db(self, store):
        """Test get_allocations returns empty list without database."""
        result, total = await store.get_allocations()
        assert result == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_overview_stats_no_db(self, store):
        """Test get_overview_stats returns defaults without database."""
        result = await store.get_overview_stats()
        assert result["total_instances"] == 0
        assert result["total_users"] == 0
        assert result["active_instances"] == 0


class TestInstanceStoreWithMockDb:
    """Tests for InstanceStore with mocked database."""

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
        return InstanceStore(db=mock_db)

    @pytest.mark.asyncio
    async def test_get_source_with_db(self, store, mock_db):
        """Test get_source with database."""
        mock_db.fetch_one.return_value = {
            "source_id": "source1",
            "created_at": datetime.now(),
        }
        result = await store.get_source("source1")
        assert result is not None
        assert result.source_id == "source1"
        mock_db.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_instance_with_db(self, store, mock_db):
        """Test get_instance with database."""
        mock_db.fetch_one.return_value = {
            "instance_id": "inst1",
            "source_id": "source1",
            "bbk_id": None,
            "instance_name": "Instance 1",
            "instance_url": "http://localhost:8001",
            "max_users": 100,
            "status": "active",
            "created_at": datetime.now(),
        }
        result = await store.get_instance("inst1")
        assert result is not None
        assert result.instance_id == "inst1"
        assert result.status == InstanceStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_instance_with_usage(self, store, mock_db):
        """Test get_instance_with_usage with database."""
        mock_db.fetch_one.return_value = {
            "instance_id": "inst1",
            "source_id": "source1",
            "bbk_id": None,
            "instance_name": "Instance 1",
            "instance_url": "http://localhost:8001",
            "max_users": 100,
            "status": "active",
            "created_at": datetime.now(),
            "current_users": 50,
            "bbk_name": None,
        }
        result = await store.get_instance_with_usage("inst1")
        assert result is not None
        assert result.current_users == 50
        assert result.usage_percent == 50.0
        assert result.warning_level == "normal"

    @pytest.mark.asyncio
    async def test_create_instance_with_db(self, store, mock_db):
        """Test create_instance with database."""
        result = await store.create_instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
            max_users=100,
        )
        mock_db.execute.assert_called_once()
        assert result.instance_id == "inst1"

    @pytest.mark.asyncio
    async def test_delete_instance_with_users_fails(self, store, mock_db):
        """Test delete_instance fails when instance has users."""
        mock_db.fetch_one.return_value = {"cnt": 5}
        result = await store.delete_instance("inst1")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_instance_without_users(self, store, mock_db):
        """Test delete_instance succeeds when instance has no users."""
        mock_db.fetch_one.return_value = {"cnt": 0}
        result = await store.delete_instance("inst1")
        assert result is True
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_allocations_with_pagination(self, store, mock_db):
        """Test get_allocations with pagination."""
        mock_db.fetch_one.return_value = {"total": 25}
        mock_db.fetch_all.return_value = [
            {
                "id": 1,
                "user_id": "user1",
                "source_id": "source1",
                "instance_id": "inst1",
                "allocated_at": datetime.now(),
                "status": "active",
                "instance_name": "Instance 1",
                "instance_url": "http://localhost:8001",
            },
        ]
        allocations, total = await store.get_allocations(page=1, page_size=10)
        assert total == 25
        assert len(allocations) == 1
        assert allocations[0].user_id == "user1"


class TestInstanceService:
    """Tests for InstanceService."""

    @pytest.fixture
    def mock_store(self):
        """Create mock store."""
        store = MagicMock(spec=InstanceStore)
        store.get_instance = AsyncMock(return_value=None)
        store.create_instance = AsyncMock()
        store.update_instance = AsyncMock(return_value=True)
        store.delete_instance = AsyncMock(return_value=True)
        store.get_instance_with_usage = AsyncMock()
        store.get_allocation = AsyncMock(return_value=None)
        store.create_allocation = AsyncMock()
        store.get_available_instances = AsyncMock(return_value=[])
        store.create_log = AsyncMock()
        store.get_source = AsyncMock()
        return store

    @pytest.fixture
    def service(self, mock_store):
        """Create service with mock store."""
        return InstanceService(mock_store)

    @pytest.mark.asyncio
    async def test_create_instance_success(self, service, mock_store):
        """Test successful instance creation."""
        mock_store.create_instance.return_value = Instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        request = CreateInstanceRequest(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        result = await service.create_instance(request)
        assert result.instance_id == "inst1"
        mock_store.create_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_instance_already_exists(self, service, mock_store):
        """Test instance creation fails when instance already exists."""
        mock_store.get_instance.return_value = Instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="Existing Instance",
            instance_url="http://localhost:8001",
        )
        request = CreateInstanceRequest(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        with pytest.raises(ValueError, match="已存在"):
            await service.create_instance(request)

    @pytest.mark.asyncio
    async def test_update_instance_success(self, service, mock_store):
        """Test successful instance update."""
        mock_store.get_instance.return_value = Instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="Old Name",
            instance_url="http://localhost:8001",
        )
        mock_store.get_instance.return_value = Instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="New Name",
            instance_url="http://localhost:8001",
        )
        request = UpdateInstanceRequest(instance_name="New Name")
        # Reset the mock for the second call
        mock_store.get_instance = AsyncMock(
            side_effect=[
                Instance(
                    instance_id="inst1",
                    source_id="source1",
                    instance_name="Old Name",
                    instance_url="http://localhost:8001",
                ),
                Instance(
                    instance_id="inst1",
                    source_id="source1",
                    instance_name="New Name",
                    instance_url="http://localhost:8001",
                ),
            ],
        )
        await service.update_instance("inst1", request)
        mock_store.update_instance.assert_called_once()
        mock_store.create_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_instance_not_found(self, service, mock_store):
        """Test instance update fails when instance not found."""
        mock_store.get_instance.return_value = None
        request = UpdateInstanceRequest(instance_name="New Name")
        with pytest.raises(ValueError, match="不存在"):
            await service.update_instance("inst1", request)

    @pytest.mark.asyncio
    async def test_delete_instance_success(self, service, mock_store):
        """Test successful instance deletion."""
        mock_store.get_instance.return_value = Instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        result = await service.delete_instance("inst1")
        assert result is True
        mock_store.delete_instance.assert_called_once()
        mock_store.create_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_instance_not_found(self, service, mock_store):
        """Test instance deletion fails when instance not found."""
        mock_store.get_instance.return_value = None
        with pytest.raises(ValueError, match="不存在"):
            await service.delete_instance("inst1")

    @pytest.mark.asyncio
    async def test_allocate_user_success(self, service, mock_store):
        """Test successful user allocation."""
        mock_store.get_available_instances.return_value = [
            InstanceWithUsage(
                instance_id="inst1",
                source_id="source1",
                instance_name="Instance 1",
                instance_url="http://localhost:8001",
                max_users=100,
                status=InstanceStatus.ACTIVE,
                current_users=50,
                usage_percent=50.0,
                warning_level="normal",
            ),
        ]
        mock_store.get_instance_with_usage.return_value = InstanceWithUsage(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
            max_users=100,
            status=InstanceStatus.ACTIVE,
            current_users=51,
            usage_percent=51.0,
            warning_level="normal",
        )
        request = {
            "user_id": "user1",
            "source_id": "source1",
        }
        result = await service.allocate_user(request)
        assert result.success is True
        assert result.instance_id == "inst1"
        mock_store.create_allocation.assert_called_once()

    @pytest.mark.asyncio
    async def test_allocate_user_already_allocated(self, service, mock_store):
        """Test user allocation fails when already allocated."""
        mock_store.get_allocation.return_value = UserAllocation(
            user_id="user1",
            source_id="source1",
            instance_id="inst1",
        )
        request = {
            "user_id": "user1",
            "source_id": "source1",
        }
        result = await service.allocate_user(request)
        assert result.success is False
        assert "已分配" in result.message

    @pytest.mark.asyncio
    async def test_allocate_user_no_instances(self, service, mock_store):
        """Test user allocation fails when no instances available."""
        mock_store.get_available_instances.return_value = []
        request = {
            "user_id": "user1",
            "source_id": "source1",
        }
        result = await service.allocate_user(request)
        assert result.success is False
        assert "无可用实例" in result.message

    @pytest.mark.asyncio
    async def test_migrate_user_success(self, service, mock_store):
        """Test successful user migration."""
        mock_store.get_allocation.return_value = UserAllocation(
            user_id="user1",
            source_id="source1",
            instance_id="inst1",
        )
        mock_store.get_instance_with_usage.return_value = InstanceWithUsage(
            instance_id="inst2",
            source_id="source1",
            instance_name="Instance 2",
            instance_url="http://localhost:8002",
            max_users=100,
            status=InstanceStatus.ACTIVE,
            current_users=30,
            usage_percent=30.0,
            warning_level="normal",
        )
        request = MigrateUserRequest(
            user_id="user1",
            source_id="source1",
            target_instance_id="inst2",
        )
        result = await service.migrate_user(request)
        assert result.success is True
        assert result.instance_id == "inst2"
        mock_store.update_allocation_instance.assert_called_once()

    @pytest.mark.asyncio
    async def test_migrate_user_not_allocated(self, service, mock_store):
        """Test user migration fails when user not allocated."""
        mock_store.get_allocation.return_value = None
        request = MigrateUserRequest(
            user_id="user1",
            source_id="source1",
            target_instance_id="inst2",
        )
        with pytest.raises(ValueError, match="未分配实例"):
            await service.migrate_user(request)

    @pytest.mark.asyncio
    async def test_migrate_user_target_not_found(self, service, mock_store):
        """Test user migration fails when target instance not found."""
        mock_store.get_allocation.return_value = UserAllocation(
            user_id="user1",
            source_id="source1",
            instance_id="inst1",
        )
        mock_store.get_instance_with_usage.return_value = None
        request = MigrateUserRequest(
            user_id="user1",
            source_id="source1",
            target_instance_id="inst2",
        )
        with pytest.raises(ValueError, match="不存在"):
            await service.migrate_user(request)

    @pytest.mark.asyncio
    async def test_delete_allocation_success(self, service, mock_store):
        """Test successful allocation deletion."""
        mock_store.get_allocation.return_value = UserAllocation(
            user_id="user1",
            source_id="source1",
            instance_id="inst1",
        )
        mock_store.delete_allocation.return_value = True
        request = DeleteAllocationRequest(
            user_id="user1",
            source_id="source1",
        )
        result = await service.delete_allocation(request)
        assert result is True
        mock_store.delete_allocation.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_instance_url_success(self, service, mock_store):
        """Test successful user instance URL query."""
        mock_store.get_allocation.return_value = UserAllocation(
            user_id="user1",
            source_id="source1",
            instance_id="inst1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        mock_store.get_source.return_value = Source(
            source_id="source1",
            source_name="Source One",
        )
        result = await service.get_user_instance_url("user1", "source1")
        assert result.success is True
        assert result.instance_url == "http://localhost:8001"

    @pytest.mark.asyncio
    async def test_get_user_instance_url_not_allocated(
        self,
        service,
        mock_store,
    ):
        """Test user instance URL query when not allocated."""
        mock_store.get_allocation.return_value = None
        result = await service.get_user_instance_url("user1", "source1")
        assert result.success is False
        assert "未分配实例" in result.message


class TestRouter:
    """Tests for API router."""

    @pytest.fixture
    def mock_service(self):
        """Create mock service for router tests."""
        service = MagicMock(spec=InstanceService)
        service.store = MagicMock(spec=InstanceStore)
        service.store.get_overview_stats = AsyncMock(
            return_value={
                "total_instances": 10,
                "total_users": 500,
                "active_instances": 8,
                "warning_instances": 1,
                "critical_instances": 1,
            },
        )
        service.store.get_sources_with_stats = AsyncMock(return_value=[])
        service.store.get_instances = AsyncMock(return_value=[])
        service.store.get_instance_with_usage = AsyncMock(return_value=None)
        service.create_instance = AsyncMock()
        service.update_instance = AsyncMock()
        service.delete_instance = AsyncMock()
        service.store.get_user_ids = AsyncMock(return_value=[])
        service.store.get_allocations = AsyncMock(return_value=([], 0))
        service.get_user_instance_url = AsyncMock()
        service.allocate_user = AsyncMock()
        service.migrate_user = AsyncMock()
        service.delete_allocation = AsyncMock()
        service.store.get_logs = AsyncMock(return_value=([], 0))
        return service

    @pytest.mark.asyncio
    async def test_get_overview(self, mock_service):
        """Test GET /instance/overview endpoint."""
        from copaw.app.instance.router import get_overview

        with patch(
            "copaw.app.instance.router.get_service",
            return_value=mock_service,
        ):
            result = await get_overview()
            assert result.total_instances == 10
            assert result.total_users == 500

    @pytest.mark.asyncio
    async def test_list_sources(self, mock_service):
        """Test GET /instance/sources endpoint."""
        from copaw.app.instance.router import list_sources

        with patch(
            "copaw.app.instance.router.get_service",
            return_value=mock_service,
        ):
            result = await list_sources()
            assert result.sources == []
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_instances(self, mock_service):
        """Test GET /instance/instances endpoint."""
        from copaw.app.instance.router import list_instances

        with patch(
            "copaw.app.instance.router.get_service",
            return_value=mock_service,
        ):
            result = await list_instances()
            assert result.instances == []
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_get_instance_not_found(self, mock_service):
        """Test GET /instance/instances/{instance_id} returns 404."""
        from copaw.app.instance.router import get_instance
        from fastapi import HTTPException

        with patch(
            "copaw.app.instance.router.get_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_instance("nonexistent")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_instance_success(self, mock_service):
        """Test POST /instance/instances endpoint."""
        from copaw.app.instance.router import create_instance

        mock_service.create_instance.return_value = Instance(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        request = CreateInstanceRequest(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        with patch(
            "copaw.app.instance.router.get_service",
            return_value=mock_service,
        ):
            result = await create_instance(request)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_instance_validation_error(self, mock_service):
        """Test POST /instance/instances with validation error."""
        from copaw.app.instance.router import create_instance
        from fastapi import HTTPException

        mock_service.create_instance.side_effect = ValueError("实例已存在")
        request = CreateInstanceRequest(
            instance_id="inst1",
            source_id="source1",
            instance_name="Instance 1",
            instance_url="http://localhost:8001",
        )
        with patch(
            "copaw.app.instance.router.get_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await create_instance(request)
            assert exc_info.value.status_code == 400
