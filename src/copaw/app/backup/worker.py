# -*- coding: utf-8 -*-
"""Async worker for executing backup/restore tasks."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from ...constant import DEFAULT_WORKING_DIR
from .config import BackupEnvironmentConfig
from .models import BackupTask, BackupTaskStatus
from .s3_client import S3BackupClient
from .task_store import TaskStore

logger = logging.getLogger(__name__)


class BackupWorker:
    """Async worker for backup and restore operations."""

    def __init__(self, task_store: TaskStore, config: BackupEnvironmentConfig):
        self.task_store = task_store
        self.config = config
        self.s3_client = S3BackupClient(config)

    # pylint: disable=too-many-statements
    async def run_backup_task(
        self,
        task: BackupTask,
    ) -> None:
        """Execute a backup task."""
        task.status = BackupTaskStatus.RUNNING
        task.started_at = datetime.now()
        self.task_store.save(task)

        try:
            if task.target_user_id:
                user_ids = [task.target_user_id]
            else:
                user_ids = self._get_all_user_ids()

            # Check for empty user list to avoid division by zero
            if not user_ids:
                task.status = BackupTaskStatus.COMPLETED
                task.current_step = "completed"
                task.progress_percent = 100
                task.completed_at = datetime.now()
                self.task_store.save(task)
                return

            task.total_users = len(user_ids)
            task.current_step = "compressing"
            self.task_store.save(task)

            s3_keys = []
            local_paths = []
            date_str = datetime.now().strftime("%Y-%m-%d")

            for i, user_id in enumerate(user_ids):
                # Update progress (1-indexed)
                task.processed_users = i + 1
                task.progress_percent = int(((i + 1) / len(user_ids)) * 50)
                self.task_store.save(task)

                # Compress user directory
                user_dir = DEFAULT_WORKING_DIR / user_id
                if not user_dir.exists():
                    continue

                zip_path = (
                    Path(tempfile.gettempdir()) / f"backup_{user_id}.zip"
                )
                await self._compress_user(user_id, user_dir, zip_path)
                local_paths.append(str(zip_path))

            # Upload to S3
            task.current_step = "uploading"
            self.task_store.save(task)

            # Check for empty local_paths to avoid division by zero
            if not local_paths:
                task.status = BackupTaskStatus.COMPLETED
                task.current_step = "completed"
                task.progress_percent = 100
                task.completed_at = datetime.now()
                self.task_store.save(task)
                return

            for i, zip_path_str in enumerate(local_paths):
                zip_path = Path(zip_path_str)
                user_id = zip_path.stem.replace("backup_", "")
                s3_key = await asyncio.to_thread(
                    self.s3_client.upload,
                    zip_path,
                    date_str,
                    user_id,
                )
                s3_keys.append(s3_key)

                # Update progress (1-indexed)
                task.processed_users = i + 1
                task.progress_percent = 50 + int(
                    ((i + 1) / len(local_paths)) * 50,
                )
                self.task_store.save(task)

            task.s3_keys = s3_keys
            task.local_zip_paths = local_paths
            task.status = BackupTaskStatus.COMPLETED
            task.current_step = "completed"
            task.progress_percent = 100

        except Exception as e:
            task.status = BackupTaskStatus.FAILED
            task.error_message = str(e)
            task.current_step = "failed"
        finally:
            task.completed_at = datetime.now()
            self.task_store.save(task)
            # Cleanup temp files
            for path in task.local_zip_paths:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {path}: {e}")

    # pylint: disable=too-many-statements
    async def run_restore_task(
        self,
        task: BackupTask,
    ) -> None:
        """Execute a restore task."""
        task.status = BackupTaskStatus.RUNNING
        task.started_at = datetime.now()
        self.task_store.save(task)

        rollback_paths = []

        try:
            # Get target users
            if task.target_user_ids:
                user_ids = task.target_user_ids
            else:
                # List all backups for the date
                backups = self.s3_client.list_backups(date=task.backup_date)
                user_ids = list(
                    backups["backups"].get(task.backup_date, {}).keys(),
                )

            # Check for empty user list to avoid division by zero
            if not user_ids:
                task.status = BackupTaskStatus.COMPLETED
                task.current_step = "completed"
                task.progress_percent = 100
                task.completed_at = datetime.now()
                self.task_store.save(task)
                return

            task.total_users = len(user_ids)
            task.current_step = "backing_up_current"
            self.task_store.save(task)

            # Backup current data for rollback
            for i, user_id in enumerate(user_ids):
                user_dir = DEFAULT_WORKING_DIR / user_id
                if user_dir.exists():
                    rollback_path = await self._create_rollback_backup(
                        task.task_id,
                        user_id,
                        user_dir,
                    )
                    rollback_paths.append(rollback_path)

            task.rollback_data_paths = rollback_paths
            task.current_step = "downloading"
            self.task_store.save(task)

            # Download and restore
            for i, user_id in enumerate(user_ids):
                task.processed_users = i + 1
                task.progress_percent = int(((i + 1) / len(user_ids)) * 50)
                self.task_store.save(task)

                s3_key = self.s3_client.get_backup_key(
                    task.backup_date,
                    user_id,
                )
                zip_path = (
                    Path(tempfile.gettempdir()) / f"restore_{user_id}.zip"
                )

                await asyncio.to_thread(
                    self.s3_client.download,
                    s3_key,
                    zip_path,
                )

                user_dir = DEFAULT_WORKING_DIR / user_id
                await self._extract_zip(zip_path, user_dir)

            # Clean up rollback data after successful restore
            rollback_dir = DEFAULT_WORKING_DIR / ".rollback" / task.task_id
            if rollback_dir.exists():
                try:
                    shutil.rmtree(rollback_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup rollback dir: {e}")

            task.current_step = "completed"
            task.status = BackupTaskStatus.COMPLETED
            task.progress_percent = 100

        except Exception as e:
            task.error_message = str(e)
            task.current_step = "rolling_back"
            task.status = BackupTaskStatus.ROLLING_BACK
            self.task_store.save(task)

            # Rollback all users
            await self._rollback_all(rollback_paths)

            task.status = BackupTaskStatus.ROLLED_BACK
        finally:
            task.completed_at = datetime.now()
            self.task_store.save(task)

    def _get_all_user_ids(self) -> list[str]:
        """Get all user IDs from working directory."""
        from ...constant import list_all_user_ids

        return list_all_user_ids()

    async def _compress_user(
        self,
        user_id: str,  # pylint: disable=unused-argument
        user_dir: Path,
        zip_path: Path,
    ) -> str:
        """Compress user directory to zip."""

        def _do_compress():
            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as zf:
                for file in user_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(user_dir))
                    elif file.is_dir() and not any(file.iterdir()):
                        # 添加空文件夹
                        zf.writestr(
                            str(file.relative_to(user_dir)) + "/",
                            "",
                        )
            return str(zip_path)

        return await asyncio.to_thread(_do_compress)

    async def _create_rollback_backup(
        self,
        task_id: str,
        user_id: str,
        user_dir: Path,
    ) -> str:
        """Create a backup of current data before restore."""
        rollback_dir = DEFAULT_WORKING_DIR / ".rollback" / task_id
        rollback_dir.mkdir(parents=True, exist_ok=True)
        zip_path = rollback_dir / f"{user_id}.zip"

        def _do_compress():
            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as zf:
                for file in user_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(user_dir))
                    elif file.is_dir() and not any(file.iterdir()):
                        # 添加空文件夹
                        zf.writestr(
                            str(file.relative_to(user_dir)) + "/",
                            "",
                        )
            return str(zip_path)

        await asyncio.to_thread(_do_compress)
        return str(zip_path)

    async def _extract_zip(self, zip_path: Path, target_dir: Path) -> None:
        """Extract zip to target directory."""

        def _do_extract():
            target_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_dir)

        await asyncio.to_thread(_do_extract)

    async def _rollback_all(self, rollback_paths: list[str]) -> None:
        """Rollback all users to pre-restore state."""
        for rollback_path in rollback_paths:
            try:
                path = Path(rollback_path)
                if not path.exists():
                    continue
                user_id = path.stem
                user_dir = DEFAULT_WORKING_DIR / user_id

                # Remove current data
                if user_dir.exists():
                    shutil.rmtree(user_dir)

                # Restore from rollback
                await self._extract_zip(path, user_dir)
            except Exception as e:
                # Continue rollback for other users
                logger.error(f"Failed to rollback {rollback_path}: {e}")
