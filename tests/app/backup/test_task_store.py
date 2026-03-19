# -*- coding: utf-8 -*-
"""Tests for TaskStore."""

import tempfile
from datetime import datetime
from pathlib import Path

from copaw.app.backup.models import (
    BackupTask,
    BackupTaskStatus,
    BackupTaskType,
)
from copaw.app.backup.task_store import TaskStore


class TestTaskStore:
    """Test TaskStore functionality."""

    def test_save_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TaskStore(Path(tmpdir) / "tasks.json")
            task = BackupTask(
                task_id="test-123",
                task_type=BackupTaskType.BACKUP,
                status=BackupTaskStatus.PENDING,
                created_at=datetime.now(),
            )
            store.save(task)
            retrieved = store.get("test-123")
            assert retrieved is not None
            assert retrieved.task_id == "test-123"

    def test_has_running_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TaskStore(Path(tmpdir) / "tasks.json")
            assert not store.has_running_task()

            task = BackupTask(
                task_id="test-1",
                task_type=BackupTaskType.BACKUP,
                status=BackupTaskStatus.RUNNING,
                created_at=datetime.now(),
            )
            store.save(task)
            assert store.has_running_task()

    def test_delete_running_task_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TaskStore(Path(tmpdir) / "tasks.json")
            task = BackupTask(
                task_id="test-1",
                task_type=BackupTaskType.BACKUP,
                status=BackupTaskStatus.RUNNING,
                created_at=datetime.now(),
            )
            store.save(task)
            assert not store.delete("test-1")  # Cannot delete running task

    def test_delete_completed_task_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TaskStore(Path(tmpdir) / "tasks.json")
            task = BackupTask(
                task_id="test-1",
                task_type=BackupTaskType.BACKUP,
                status=BackupTaskStatus.COMPLETED,
                created_at=datetime.now(),
            )
            store.save(task)
            assert store.delete("test-1")
            assert store.get("test-1") is None
