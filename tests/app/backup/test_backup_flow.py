# -*- coding: utf-8 -*-
"""Integration tests for backup feature."""

import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from copaw.app.backup.router import router as backup_router
from copaw.app.backup.task_store import TaskStore


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory(prefix="copaw_backup_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
async def client(temp_dir: Path) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with backup routes."""
    # Use temp directory for task storage
    original_init = TaskStore.__init__

    def patched_init(self, file_path=None):
        if file_path is None:
            file_path = temp_dir / "backup_tasks.json"
        original_init(self, file_path)

    TaskStore.__init__ = patched_init

    app = FastAPI()
    app.include_router(backup_router, prefix="/api")

    async with AsyncClient(
        transport=ASGITransport(app),
        base_url="http://test",
    ) as ac:
        yield ac

    TaskStore.__init__ = original_init


class TestBackupAPI:
    """Test backup API endpoints."""

    @pytest.mark.asyncio
    async def test_create_backup_without_config(self, client: AsyncClient):
        """Test backup creation fails without config."""
        response = await client.post("/api/backup/upload", json={})
        assert response.status_code == 400
        assert "Backup not configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_restore_without_config(self, client: AsyncClient):
        """Test restore creation fails without config."""
        response = await client.post(
            "/api/backup/download",
            json={"date": "2025-03-19"},
        )
        assert response.status_code == 400
        assert "Backup not configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client: AsyncClient):
        """Test listing tasks returns empty list."""
        response = await client.get("/api/backup/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, client: AsyncClient):
        """Test getting non-existent task returns 404."""
        response = await client.get("/api/backup/tasks/nonexistent-uuid")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_task(self, client: AsyncClient):
        """Test deleting non-existent task returns 400."""
        response = await client.delete("/api/backup/tasks/nonexistent-uuid")
        assert response.status_code == 400
        assert "Task not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_backups_without_config(self, client: AsyncClient):
        """Test listing backups fails without config."""
        response = await client.get("/api/backup/list")
        assert response.status_code == 400
        assert "Backup not configured" in response.json()["detail"]
