# -*- coding: utf-8 -*-
"""Backup service layer."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from fastapi import HTTPException

from .config import BackupConfig, load_backup_config
from .models import BackupTask, BackupTaskStatus, BackupTaskType
from .task_store import TaskStore
from .worker import BackupWorker


class BackupService:
    """Backup business logic service."""

    def __init__(self):
        self.task_store = TaskStore()
        self._worker: BackupWorker | None = None
        self._lock = asyncio.Lock()

    def _get_backup_config(self) -> BackupConfig:
        """Get backup config from file."""
        config = load_backup_config()
        if config is None:
            raise HTTPException(
                status_code=400,
                detail="Backup not configured",
            )
        return config

    def _get_worker(self) -> BackupWorker:
        """Get or create worker instance."""
        if self._worker is None:
            backup_config = self._get_backup_config()
            env_config = backup_config.get_active_config()
            if env_config is None:
                raise HTTPException(
                    status_code=400,
                    detail="Backup environment not configured",
                )
            self._worker = BackupWorker(self.task_store, env_config)
        return self._worker

    async def create_backup_task(
        self,
        target_user_id: str | None = None,
    ) -> BackupTask:
        """Create a new backup task."""
        async with self._lock:
            if self.task_store.has_running_task():
                raise HTTPException(
                    status_code=409,
                    detail="Another backup task is already running",
                )

        task = BackupTask(
            task_id=str(uuid.uuid4()),
            task_type=BackupTaskType.BACKUP,
            status=BackupTaskStatus.PENDING,
            created_at=datetime.now(),
            target_user_id=target_user_id,
        )
        self.task_store.save(task)

        # Start async execution
        asyncio.create_task(self._get_worker().run_backup_task(task))

        return task

    async def create_restore_task(
        self,
        date: str,
        user_ids: list[str] | None = None,
    ) -> BackupTask:
        """Create a new restore task."""
        async with self._lock:
            if self.task_store.has_running_task():
                raise HTTPException(
                    status_code=409,
                    detail="Another backup task is already running",
                )

        task = BackupTask(
            task_id=str(uuid.uuid4()),
            task_type=BackupTaskType.RESTORE,
            status=BackupTaskStatus.PENDING,
            created_at=datetime.now(),
            backup_date=date,
            target_user_ids=user_ids,
        )
        self.task_store.save(task)

        # Start async execution
        asyncio.create_task(self._get_worker().run_restore_task(task))

        return task

    def get_task(self, task_id: str) -> BackupTask | None:
        """Get task by ID."""
        return self.task_store.get(task_id)

    def list_tasks(
        self,
        status: BackupTaskStatus | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[BackupTask]:
        """List tasks with filters."""
        return self.task_store.get_all(
            status=status,
            task_type=task_type,
            limit=limit,
        )

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        return self.task_store.delete(task_id)

    def list_available_backups(
        self,
        user_id: str | None = None,
        date: str | None = None,
    ) -> dict:
        """List available backups from S3."""
        backup_config = self._get_backup_config()
        env_config = backup_config.get_active_config()
        if env_config is None:
            raise HTTPException(
                status_code=400,
                detail="Backup environment not configured",
            )

        from .s3_client import S3BackupClient

        s3_client = S3BackupClient(env_config)
        return s3_client.list_backups(user_id=user_id, date=date)
