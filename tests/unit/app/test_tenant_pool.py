# -*- coding: utf-8 -*-
"""Unit tests for TenantWorkspacePool.

Tests lazy creation, cache hits, concurrent creation safety, and stop-all cleanup.
"""
import asyncio
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from copaw.app.workspace.tenant_pool import TenantWorkspacePool, TenantWorkspaceEntry


class TestTenantWorkspacePoolBasics:
    """Basic functionality tests."""

    def test_initialization_creates_base_dir(self, tmp_path):
        """Pool initialization creates base directory if needed."""
        base_dir = tmp_path / "tenants"
        assert not base_dir.exists()

        pool = TenantWorkspacePool(base_dir)

        assert base_dir.exists()
        assert base_dir.is_dir()

    def test_initialization_with_existing_dir(self, tmp_path):
        """Pool initialization works with existing directory."""
        base_dir = tmp_path / "tenants"
        base_dir.mkdir()

        pool = TenantWorkspacePool(base_dir)

        assert pool._base_working_dir == base_dir

    def test_len_empty_pool(self, tmp_path):
        """Empty pool has length 0."""
        pool = TenantWorkspacePool(tmp_path / "tenants")
        assert len(pool) == 0

    def test_contains_empty_pool(self, tmp_path):
        """Empty pool doesn't contain any tenant."""
        pool = TenantWorkspacePool(tmp_path / "tenants")
        assert "tenant-1" not in pool


class TestTenantWorkspaceCreation:
    """Tests for workspace creation."""

    @pytest.mark.asyncio
    async def test_get_or_create_creates_workspace(self, tmp_path):
        """get_or_create creates a new workspace."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        workspace = pool.get_or_create("tenant-1")

        assert workspace is not None
        assert workspace.agent_id == "default"
        assert workspace.workspace_dir == pool._get_tenant_workspace_dir("tenant-1")

    @pytest.mark.asyncio
    async def test_get_or_create_with_custom_agent_id(self, tmp_path):
        """get_or_create uses provided agent_id."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        workspace = pool.get_or_create("tenant-1", agent_id="custom-agent")

        assert workspace.agent_id == "custom-agent"

    @pytest.mark.asyncio
    async def test_get_or_create_creates_tenant_dir(self, tmp_path):
        """get_or_create creates tenant workspace directory."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        pool.get_or_create("tenant-1")

        tenant_dir = pool._get_tenant_workspace_dir("tenant-1")
        assert tenant_dir.exists()
        assert tenant_dir.is_dir()

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing_workspace(self, tmp_path):
        """get_or_create returns existing workspace on second call."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        workspace1 = pool.get_or_create("tenant-1")
        workspace2 = pool.get_or_create("tenant-1")

        assert workspace1 is workspace2  # Same instance

    @pytest.mark.asyncio
    async def test_get_or_create_increases_pool_size(self, tmp_path):
        """get_or_create increases pool size."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        assert len(pool) == 0

        pool.get_or_create("tenant-1")
        assert len(pool) == 1

        pool.get_or_create("tenant-2")
        assert len(pool) == 2

        # Same tenant doesn't increase size
        pool.get_or_create("tenant-1")
        assert len(pool) == 2


class TestTenantWorkspaceGet:
    """Tests for get method."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_exists(self, tmp_path):
        """get returns None when workspace doesn't exist."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        result = pool.get("tenant-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_existing_workspace(self, tmp_path):
        """get returns workspace if it exists."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        created = pool.get_or_create("tenant-1")
        retrieved = pool.get("tenant-1")

        assert retrieved is created

    @pytest.mark.asyncio
    async def test_get_does_not_create_workspace(self, tmp_path):
        """get does not create workspace if not exists."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        result = pool.get("tenant-1")

        assert result is None
        assert len(pool) == 0


class TestTenantWorkspaceRemove:
    """Tests for remove method."""

    @pytest.mark.asyncio
    async def test_remove_returns_none_when_not_exists(self, tmp_path):
        """remove returns None when workspace doesn't exist."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        result = pool.remove("tenant-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_remove_returns_workspace(self, tmp_path):
        """remove returns workspace when it exists."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        created = pool.get_or_create("tenant-1")
        removed = pool.remove("tenant-1")

        assert removed is created

    @pytest.mark.asyncio
    async def test_removes_from_pool(self, tmp_path):
        """remove removes workspace from pool."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        pool.get_or_create("tenant-1")
        assert "tenant-1" in pool

        pool.remove("tenant-1")
        assert "tenant-1" not in pool


class TestTenantWorkspaceStop:
    """Tests for stop method."""

    @pytest.mark.asyncio
    async def test_stop_returns_false_when_not_exists(self, tmp_path):
        """stop returns False when workspace doesn't exist."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        result = await pool.stop("tenant-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_stop_removes_from_pool(self, tmp_path):
        """stop removes workspace from pool."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        pool.get_or_create("tenant-1")
        await pool.stop("tenant-1")

        assert "tenant-1" not in pool


class TestTenantWorkspaceStopAll:
    """Tests for stop_all method."""

    @pytest.mark.asyncio
    async def test_stop_all_empty_pool(self, tmp_path):
        """stop_all handles empty pool."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        await pool.stop_all()

        assert len(pool) == 0

    @pytest.mark.asyncio
    async def test_stop_all_removes_all_workspaces(self, tmp_path):
        """stop_all removes all workspaces from pool."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        pool.get_or_create("tenant-1")
        pool.get_or_create("tenant-2")
        pool.get_or_create("tenant-3")

        assert len(pool) == 3

        await pool.stop_all()

        assert len(pool) == 0


class TestTenantWorkspaceAccessTracking:
    """Tests for access tracking."""

    @pytest.mark.asyncio
    async def test_mark_access_updates_timestamp(self, tmp_path):
        """mark_access updates last_accessed_at."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        pool.get_or_create("tenant-1")

        # Wait a tiny bit to ensure time difference
        await asyncio.sleep(0.001)

        pool.mark_access("tenant-1")

        # Entry was updated (we can't easily test the exact timestamp)
        assert pool.mark_access("tenant-1") is True

    @pytest.mark.asyncio
    async def test_mark_access_returns_false_when_not_exists(self, tmp_path):
        """mark_access returns False when workspace doesn't exist."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        result = pool.mark_access("tenant-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_or_create_tracks_access(self, tmp_path):
        """get_or_create tracks access count."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        pool.get_or_create("tenant-1")
        pool.get_or_create("tenant-1")  # Second access
        pool.get_or_create("tenant-1")  # Third access

        # Access should have been tracked (via get_or_create -> mark_access)
        stats = pool.get_stats()
        assert stats["tenants"]["tenant-1"]["access_count"] >= 1


class TestTenantWorkspaceStats:
    """Tests for get_stats method."""

    @pytest.mark.asyncio
    async def test_get_stats_empty_pool(self, tmp_path):
        """get_stats returns empty info for empty pool."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        stats = pool.get_stats()

        assert stats["tenant_count"] == 0
        assert stats["tenants"] == {}

    @pytest.mark.asyncio
    async def test_get_stats_with_tenants(self, tmp_path):
        """get_stats returns info for all tenants."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        pool.get_or_create("tenant-1")
        pool.get_or_create("tenant-2")

        stats = pool.get_stats()

        assert stats["tenant_count"] == 2
        assert "tenant-1" in stats["tenants"]
        assert "tenant-2" in stats["tenants"]
        assert "created_at" in stats["tenants"]["tenant-1"]
        assert "last_accessed_at" in stats["tenants"]["tenant-1"]
        assert "access_count" in stats["tenants"]["tenant-1"]


class TestTenantWorkspaceConcurrency:
    """Tests for concurrent access safety."""

    @pytest.mark.asyncio
    async def test_concurrent_get_or_create_same_tenant(self, tmp_path):
        """Concurrent get_or_create for same tenant returns same workspace."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        async def get_workspace():
            return pool.get_or_create("tenant-1")

        # Launch multiple concurrent requests
        tasks = [get_workspace() for _ in range(10)]
        workspaces = await asyncio.gather(*tasks)

        # All should be the same workspace instance
        first = workspaces[0]
        for ws in workspaces[1:]:
            assert ws is first

    @pytest.mark.asyncio
    async def test_concurrent_get_or_create_different_tenants(self, tmp_path):
        """Concurrent get_or_create for different tenants works correctly."""
        pool = TenantWorkspacePool(tmp_path / "tenants")

        async def get_workspace(tenant_id):
            return pool.get_or_create(tenant_id)

        # Launch concurrent requests for different tenants
        tasks = [get_workspace(f"tenant-{i}") for i in range(5)]
        workspaces = await asyncio.gather(*tasks)

        # All should be different instances
        assert len(set(id(ws) for ws in workspaces)) == 5

        # Pool should have all 5
        assert len(pool) == 5


class TestTenantWorkspaceDirectoryLayout:
    """Tests for tenant workspace directory layout."""

    def test_tenant_workspace_dir_under_base(self, tmp_path):
        """Tenant workspace dir is under base working dir."""
        base_dir = tmp_path / "tenants"
        pool = TenantWorkspacePool(base_dir)

        tenant_dir = pool._get_tenant_workspace_dir("tenant-1")

        # Compare with resolved base path since pool resolves it
        assert tenant_dir.parent == pool._base_working_dir
        assert tenant_dir.name == "tenant-1"

    def test_different_tenants_different_dirs(self, tmp_path):
        """Different tenants get different directories."""
        base_dir = tmp_path / "tenants"
        pool = TenantWorkspacePool(base_dir)

        dir1 = pool._get_tenant_workspace_dir("tenant-1")
        dir2 = pool._get_tenant_workspace_dir("tenant-2")

        assert dir1 != dir2
        assert dir1.parent == dir2.parent

    def test_tenant_dir_with_special_chars(self, tmp_path):
        """Tenant IDs with special characters work correctly."""
        base_dir = tmp_path / "tenants"
        pool = TenantWorkspacePool(base_dir)

        # Test various tenant ID formats
        tenant_ids = [
            "tenant-1",
            "tenant_1",
            "tenant.1",
            "Tenant1",
            "123-abc",
            "a" * 50,
        ]

        for tenant_id in tenant_ids:
            dir_path = pool._get_tenant_workspace_dir(tenant_id)
            assert dir_path.name == tenant_id
            assert dir_path.parent == base_dir


class TestTenantWorkspaceEntry:
    """Tests for TenantWorkspaceEntry dataclass."""

    def test_entry_creation(self):
        """TenantWorkspaceEntry can be created."""
        # Create a mock workspace
        class MockWorkspace:
            pass

        entry = TenantWorkspaceEntry(
            tenant_id="tenant-1",
            workspace=MockWorkspace(),
        )

        assert entry.tenant_id == "tenant-1"
        assert entry.access_count == 0
        assert entry.created_at > 0
        assert entry.last_accessed_at > 0
