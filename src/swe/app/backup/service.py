# -*- coding: utf-8 -*-
"""Backup service layer."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from swe.config.utils import list_all_tenant_ids
from swe.constant import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from swe.database import DatabaseConfig, DatabaseConnection
from .config import BackupConfig, load_backup_config
from .models import BackupTask, BackupTaskStatus, BackupTaskType
from .task_store import TaskStore
from .worker import BackupWorker

logger = logging.getLogger(__name__)

# Global task store instance
_task_store: TaskStore | None = None
_task_store_lock = asyncio.Lock()


async def get_task_store() -> TaskStore:
    """Get the global task store instance.

    Initializes the task store with database connection if available.
    """
    global _task_store

    if _task_store is not None:
        return _task_store

    async with _task_store_lock:
        if _task_store is not None:
            return _task_store

        # Create database connection if configured
        db: DatabaseConnection | None = None
        if DB_HOST:
            try:
                db_config = DatabaseConfig(
                    host=DB_HOST,
                    port=DB_PORT or 3306,
                    user=DB_USER or "root",
                    password=DB_PASSWORD or "",
                    database=DB_NAME or "copaw",
                )
                db = DatabaseConnection(db_config)
                await db.connect()
                logger.info(
                    "BackupTaskStore database connection established: %s",
                    DB_HOST,
                )
            except Exception as e:
                logger.warning(
                    "Failed to connect to database for backup tasks: %s",
                    e,
                )
                db = None

        _task_store = TaskStore(db)
        await _task_store.initialize()
        return _task_store


class BackupService:
    """Backup business logic service."""

    def __init__(self):
        self._worker: BackupWorker | None = None
        self._lock = asyncio.Lock()

    async def _get_task_store(self) -> TaskStore:
        """Get task store instance."""
        return await get_task_store()

    def _get_backup_config(self) -> BackupConfig:
        """Get backup config from file."""
        config = load_backup_config()
        if config is None:
            raise HTTPException(
                status_code=400,
                detail="Backup not configured",
            )
        return config

    def _get_worker(self, task_store: TaskStore) -> BackupWorker:
        """Get or create worker instance."""
        if self._worker is None:
            backup_config = self._get_backup_config()
            env_config = backup_config.get_active_config()
            if env_config is None:
                raise HTTPException(
                    status_code=400,
                    detail="Backup environment not configured",
                )
            self._worker = BackupWorker(task_store, env_config)
        return self._worker

    async def create_backup_task(
        self,
        tenant_ids: list[str] | None = None,
        instance_id: str | None = None,
        backup_date: str | None = None,
        backup_hour: int | None = None,
    ) -> BackupTask:
        """Create a new backup task.

        Args:
            tenant_ids: Specific tenants to backup, or None for all tenants
            instance_id: Instance identifier for multi-instance deployment
            backup_date: Backup date (YYYY-MM-DD), defaults to today
            backup_hour: Hour of day (0-23), defaults to current hour
        """
        task_store = await self._get_task_store()

        async with self._lock:
            if await task_store.has_running_task():
                raise HTTPException(
                    status_code=409,
                    detail="Another backup task is already running",
                )

        # Set backup date and hour (Beijing time)
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        if backup_date is None:
            backup_date = now.strftime("%Y-%m-%d")
        if backup_hour is None:
            backup_hour = now.hour

        task = BackupTask(
            task_id=str(uuid.uuid4()),
            task_type=BackupTaskType.BACKUP,
            status=BackupTaskStatus.PENDING,
            created_at=datetime.now(ZoneInfo("Asia/Shanghai")),
            target_tenant_ids=tenant_ids,
            instance_id=instance_id,
            backup_date=backup_date,
            backup_hour=backup_hour,
        )
        await task_store.save(task)

        # Start async execution
        worker = self._get_worker(task_store)
        asyncio.create_task(worker.run_backup_task(task))

        return task

    async def create_restore_task(
        self,
        date: str | None = None,
        hour: int | None = None,
        instance_id: str | None = None,
        tenant_ids: list[str] | None = None,
    ) -> BackupTask:
        """Create a new restore task.

        Args:
            date: Backup date (YYYY-MM-DD), defaults to today
            hour: Backup hour (0-23)
            instance_id: Instance identifier
            tenant_ids: Specific tenants to restore, or None for all
        """
        task_store = await self._get_task_store()

        async with self._lock:
            if await task_store.has_running_task():
                raise HTTPException(
                    status_code=409,
                    detail="Another backup task is already running",
                )

        # Set date if not provided
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        if date is None:
            date = now.strftime("%Y-%m-%d")

        task = BackupTask(
            task_id=str(uuid.uuid4()),
            task_type=BackupTaskType.RESTORE,
            status=BackupTaskStatus.PENDING,
            created_at=datetime.now(ZoneInfo("Asia/Shanghai")),
            backup_date=date,
            backup_hour=hour,
            instance_id=instance_id,
            target_tenant_ids=tenant_ids,
        )
        await task_store.save(task)

        # Start async execution
        worker = self._get_worker(task_store)
        asyncio.create_task(worker.run_restore_task(task))

        return task

    async def get_task(self, task_id: str) -> BackupTask | None:
        """Get task by ID."""
        task_store = await self._get_task_store()
        return await task_store.get(task_id)

    async def list_tasks(
        self,
        status: BackupTaskStatus | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[BackupTask]:
        """List tasks with filters."""
        task_store = await self._get_task_store()
        return await task_store.get_all(
            status=status,
            task_type=task_type,
            limit=limit,
        )

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        task_store = await self._get_task_store()
        return await task_store.delete(task_id)

    def list_available_backups(
        self,
        instance_id: str | None = None,
        date: str | None = None,
        hour: int | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        """List available backups from S3.

        Args:
            instance_id: Filter by instance ID
            date: Filter by date (YYYY-MM-DD)
            hour: Filter by hour (0-23)
            tenant_id: Filter by tenant ID
        """
        backup_config = self._get_backup_config()
        env_config = backup_config.get_active_config()
        if env_config is None:
            raise HTTPException(
                status_code=400,
                detail="Backup environment not configured",
            )

        from .s3_client import S3BackupClient

        s3_client = S3BackupClient(env_config)
        return s3_client.list_backups(
            instance_id=instance_id,
            date=date,
            hour=hour,
            tenant_id=tenant_id,
        )

    @staticmethod
    def list_all_tenant_ids() -> list[str]:
        """List all tenant IDs."""
        return list_all_tenant_ids()
