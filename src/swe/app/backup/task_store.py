# -*- coding: utf-8 -*-
"""Task state persistence using database storage."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from swe.database import DatabaseConnection
from .models import BackupTask, BackupTaskStatus, BackupTaskType

logger = logging.getLogger(__name__)


def _normalize_datetime(dt: datetime) -> datetime:
    """Normalize datetime to UTC for comparison.

    Handles both offset-naive and offset-aware datetimes.
    """
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TaskStore:
    """Database-based task storage."""

    def __init__(self, db: Optional[DatabaseConnection] = None):
        """Initialize task store.

        Args:
            db: Database connection (DatabaseConnection)
        """
        self.db = db
        self._use_db = db is not None and db.is_connected

    async def initialize(self) -> None:
        """Initialize store and ensure table exists."""
        if self.db is not None and self.db.is_connected:
            self._use_db = True
            await self._ensure_table()
            logger.info("TaskStore initialized with database storage")
        else:
            self._use_db = False
            logger.warning(
                "TaskStore initialized without database - using fallback",
            )

    async def _ensure_table(self) -> None:
        """Ensure backup task table exists."""
        if not self._use_db:
            return

        create_table_sql = """
            CREATE TABLE IF NOT EXISTS `swe_backup_task` (
                `task_id` VARCHAR(64) NOT NULL,
                `task_type` ENUM('backup', 'restore') NOT NULL,
                `tenant_id` VARCHAR(64) DEFAULT NULL,
                `status` ENUM('pending', 'running', 'completed', 'failed', 'rolling_back', 'rolled_back') NOT NULL DEFAULT 'pending',
                `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `started_at` TIMESTAMP NULL DEFAULT NULL,
                `completed_at` TIMESTAMP NULL DEFAULT NULL,
                `target_tenant_ids` JSON DEFAULT NULL,
                `backup_date` VARCHAR(10) DEFAULT NULL,
                `backup_hour` INT DEFAULT NULL,
                `instance_id` VARCHAR(64) DEFAULT NULL,
                `current_step` VARCHAR(256) DEFAULT '',
                `progress_percent` INT NOT NULL DEFAULT 0,
                `processed_tenants` INT NOT NULL DEFAULT 0,
                `total_tenants` INT NOT NULL DEFAULT 0,
                `s3_keys` JSON DEFAULT NULL,
                `local_zip_paths` JSON DEFAULT NULL,
                `error_message` TEXT DEFAULT NULL,
                `rollback_data_paths` JSON DEFAULT NULL,
                `restored_tenants` JSON DEFAULT NULL,
                PRIMARY KEY (`task_id`),
                INDEX `idx_task_type` (`task_type`),
                INDEX `idx_status` (`status`),
                INDEX `idx_created_at` (`created_at`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        try:
            await self.db.execute(create_table_sql)
            logger.debug("Backup task table ensured")
        except Exception as e:
            logger.warning("Failed to ensure backup task table: %s", e)

    def _row_to_task(self, row: dict) -> BackupTask:
        """Convert database row to BackupTask."""
        return BackupTask(
            task_id=row["task_id"],
            task_type=BackupTaskType(row["task_type"]),
            tenant_id=row.get("tenant_id"),
            status=BackupTaskStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            target_tenant_ids=json.loads(row["target_tenant_ids"] or "null"),
            backup_date=row.get("backup_date"),
            backup_hour=row.get("backup_hour"),
            instance_id=row.get("instance_id"),
            current_step=row.get("current_step") or "",
            progress_percent=row.get("progress_percent") or 0,
            processed_tenants=row.get("processed_tenants") or 0,
            total_tenants=row.get("total_tenants") or 0,
            s3_keys=json.loads(row["s3_keys"] or "null") or [],
            local_zip_paths=json.loads(row["local_zip_paths"] or "null") or [],
            error_message=row.get("error_message"),
            rollback_data_paths=json.loads(
                row["rollback_data_paths"] or "null",
            )
            or [],
            restored_tenants=json.loads(row["restored_tenants"] or "null")
            or [],
        )

    async def save(self, task: BackupTask) -> None:
        """Save or update a task."""
        if not self._use_db:
            logger.warning(
                "Database not available, task not saved: %s",
                task.task_id,
            )
            return

        # Check if task exists
        existing = await self.get(task.task_id)

        if existing:
            # Update existing task
            update_sql = """
                UPDATE swe_backup_task SET
                    task_type = %s,
                    tenant_id = %s,
                    status = %s,
                    started_at = %s,
                    completed_at = %s,
                    target_tenant_ids = %s,
                    backup_date = %s,
                    backup_hour = %s,
                    instance_id = %s,
                    current_step = %s,
                    progress_percent = %s,
                    processed_tenants = %s,
                    total_tenants = %s,
                    s3_keys = %s,
                    local_zip_paths = %s,
                    error_message = %s,
                    rollback_data_paths = %s,
                    restored_tenants = %s
                WHERE task_id = %s
            """
            params = (
                task.task_type.value,
                task.tenant_id,
                task.status.value,
                task.started_at,
                task.completed_at,
                json.dumps(task.target_tenant_ids)
                if task.target_tenant_ids
                else None,
                task.backup_date,
                task.backup_hour,
                task.instance_id,
                task.current_step,
                task.progress_percent,
                task.processed_tenants,
                task.total_tenants,
                json.dumps(task.s3_keys) if task.s3_keys else None,
                json.dumps(task.local_zip_paths)
                if task.local_zip_paths
                else None,
                task.error_message,
                json.dumps(task.rollback_data_paths)
                if task.rollback_data_paths
                else None,
                json.dumps(task.restored_tenants)
                if task.restored_tenants
                else None,
                task.task_id,
            )
            await self.db.execute(update_sql, params)
        else:
            # Insert new task
            insert_sql = """
                INSERT INTO swe_backup_task (
                    task_id, task_type, tenant_id, status, created_at,
                    started_at, completed_at, target_tenant_ids,
                    backup_date, backup_hour, instance_id,
                    current_step, progress_percent, processed_tenants, total_tenants,
                    s3_keys, local_zip_paths, error_message,
                    rollback_data_paths, restored_tenants
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
            """
            params = (
                task.task_id,
                task.task_type.value,
                task.tenant_id,
                task.status.value,
                task.created_at,
                task.started_at,
                task.completed_at,
                json.dumps(task.target_tenant_ids)
                if task.target_tenant_ids
                else None,
                task.backup_date,
                task.backup_hour,
                task.instance_id,
                task.current_step,
                task.progress_percent,
                task.processed_tenants,
                task.total_tenants,
                json.dumps(task.s3_keys) if task.s3_keys else None,
                json.dumps(task.local_zip_paths)
                if task.local_zip_paths
                else None,
                task.error_message,
                json.dumps(task.rollback_data_paths)
                if task.rollback_data_paths
                else None,
                json.dumps(task.restored_tenants)
                if task.restored_tenants
                else None,
            )
            await self.db.execute(insert_sql, params)

    async def get(self, task_id: str) -> Optional[BackupTask]:
        """Get task by ID."""
        if not self._use_db:
            return None

        query = "SELECT * FROM swe_backup_task WHERE task_id = %s"
        row = await self.db.fetch_one(query, (task_id,))
        if row:
            return self._row_to_task(row)
        return None

    async def get_all(
        self,
        status: BackupTaskStatus | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[BackupTask]:
        """Get tasks with optional filters."""
        if not self._use_db:
            return []

        where_clauses = []
        params: list = []

        if status:
            where_clauses.append("status = %s")
            params.append(status.value)
        if task_type:
            where_clauses.append("task_type = %s")
            params.append(task_type)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT * FROM swe_backup_task
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %s
        """
        params.append(limit)

        rows = await self.db.fetch_all(query, tuple(params))
        return [self._row_to_task(row) for row in rows]

    async def has_running_task(self) -> bool:
        """Check if any task is currently running."""
        if not self._use_db:
            return False

        query = "SELECT COUNT(*) as cnt FROM swe_backup_task WHERE status = 'running'"
        row = await self.db.fetch_one(query)
        return row and row.get("cnt", 0) > 0

    async def delete(self, task_id: str) -> bool:
        """Delete a task. Returns False if task not found or is running."""
        if not self._use_db:
            return False

        # Check if task exists and is not running
        task = await self.get(task_id)
        if task is None:
            return False
        if task.status == BackupTaskStatus.RUNNING:
            return False

        query = "DELETE FROM swe_backup_task WHERE task_id = %s"
        result = await self.db.execute(query, (task_id,))
        return result > 0
