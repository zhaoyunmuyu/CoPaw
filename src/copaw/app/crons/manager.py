# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ...config import get_heartbeat_config

from ..console_push_store import append as push_store_append
from .executor import CronExecutor
from .heartbeat import parse_heartbeat_every, run_heartbeat_once
from .models import CronJobSpec, CronJobState
from .repo.json_repo import JsonJobRepository

HEARTBEAT_JOB_ID = "_heartbeat"

logger = logging.getLogger(__name__)


@dataclass
class _Runtime:
    sem: asyncio.Semaphore


class CronManager:
    def __init__(
        self,
        *,
        runner: Any,
        channel_manager: Any,
        timezone: str = "Asia/Shanghai",
    ):
        self._runner = runner
        self._channel_manager = channel_manager
        self._timezone = timezone
        self._scheduler = AsyncIOScheduler(timezone=timezone)
        self._executor = CronExecutor(
            runner=runner,
            channel_manager=channel_manager,
        )

        self._lock = asyncio.Lock()
        # Per-user state isolation: {user_id: {job_id: CronJobState}}
        self._states: Dict[str, Dict[str, CronJobState]] = {}
        # Per-user runtime: {user_id: {job_id: _Runtime}}
        self._rt: Dict[str, Dict[str, _Runtime]] = {}
        # Track started users: {user_id: Set[job_id]}
        self._user_jobs: Dict[str, Set[str]] = {}
        self._started = False
        # User scan interval (minutes), configurable via env var
        self._scan_interval_minutes = int(
            os.environ.get("COPAW_CRON_USER_SCAN_MINUTES", "5"),
        )
        self._scan_job_id = "_cron_user_scan"

    def _get_repo_for_user(self, user_id: str) -> JsonJobRepository:
        """Get repository for specific user.

        Args:
            user_id: User identifier

        Returns:
            JsonJobRepository for user's jobs.json
        """
        from ...config.utils import get_jobs_path

        return JsonJobRepository(get_jobs_path(user_id))

    async def start(self) -> None:
        """Start the scheduler (global, starts only once)."""
        async with self._lock:
            if self._started:
                return
            self._scheduler.start()
            self._started = True

        # Release lock before calling _scan_and_load_users to avoid deadlock
        # (start_user() also acquires the same lock)
        await self._scan_and_load_users()

        # Add periodic scan job
        if self._scan_interval_minutes > 0:
            async with self._lock:
                self._scheduler.add_job(
                    self._scan_and_load_users,
                    trigger=IntervalTrigger(
                        minutes=self._scan_interval_minutes,
                    ),
                    id=self._scan_job_id,
                    replace_existing=True,
                )
                logger.info(
                    "cron user scan scheduled: every %s minutes",
                    self._scan_interval_minutes,
                )

    async def stop(self) -> None:
        """Stop the scheduler."""
        async with self._lock:
            if not self._started:
                return
            # Remove scan job
            if self._scheduler.get_job(self._scan_job_id):
                self._scheduler.remove_job(self._scan_job_id)
            self._scheduler.shutdown(wait=False)
            self._started = False

    async def _scan_and_load_users(self) -> None:
        """Scan all user directories and load cron jobs for unloaded users.

        Iterates over ~/.copaw/*/ directories and calls start_user() for each
        user not yet loaded.
        """
        from ...constant import list_all_user_ids

        try:
            user_ids = list_all_user_ids()
            if not user_ids:
                logger.debug("cron scan: no users found")
                return

            loaded_count = 0
            for user_id in user_ids:
                if user_id not in self._user_jobs:
                    try:
                        await self.start_user(user_id)
                        loaded_count += 1
                        logger.info(
                            "cron scan: auto-loaded jobs for user=%s",
                            user_id,
                        )
                    except Exception as e:
                        logger.warning(
                            "cron scan: failed to load jobs for user=%s: %s",
                            user_id,
                            e,
                        )

            if loaded_count > 0:
                logger.info(
                    "cron scan: loaded jobs for %d new user(s) (total users: %d)",
                    loaded_count,
                    len(self._user_jobs),
                )
        except Exception:
            logger.exception("cron scan: failed to scan and load users")

    async def start_user(self, user_id: str) -> None:
        """Load and start jobs for a specific user.

        Args:
            user_id: User identifier
        """
        async with self._lock:
            if user_id in self._user_jobs:
                return  # Already started

            repo = self._get_repo_for_user(user_id)
            jobs_file = await repo.load()

            self._user_jobs[user_id] = set()
            self._states[user_id] = {}
            self._rt[user_id] = {}

            for job in jobs_file.jobs:
                await self._register_or_update(user_id, job)
                self._user_jobs[user_id].add(job.id)

            # Start per-user heartbeat
            await self._start_user_heartbeat(user_id)

    async def stop_user(self, user_id: str) -> None:
        """Stop all jobs for a specific user.

        Args:
            user_id: User identifier
        """
        async with self._lock:
            if user_id not in self._user_jobs:
                return

            # Remove all jobs for this user
            for job_id in list(self._user_jobs[user_id]):
                if self._scheduler.get_job(job_id):
                    self._scheduler.remove_job(job_id)

            # Remove user heartbeat
            heartbeat_job_id = f"_heartbeat:{user_id}"
            if self._scheduler.get_job(heartbeat_job_id):
                self._scheduler.remove_job(heartbeat_job_id)

            del self._user_jobs[user_id]
            del self._states[user_id]
            del self._rt[user_id]

    async def ensure_user_started(self, user_id: str) -> None:
        """Ensure user jobs are started (lazy loading).

        Args:
            user_id: User identifier
        """
        # start_user acquires the lock internally, so we don't need to acquire it here
        if user_id not in self._user_jobs:
            await self.start_user(user_id)

    # ----- read/state -----

    async def list_jobs(self, user_id: str) -> list[CronJobSpec]:
        """List all jobs for a user.

        Args:
            user_id: User identifier

        Returns:
            List of job specifications
        """
        repo = self._get_repo_for_user(user_id)
        return await repo.list_jobs()

    async def get_job(
        self,
        job_id: str,
        user_id: str,
    ) -> Optional[CronJobSpec]:
        """Get a specific job for a user.

        Args:
            job_id: Job identifier
            user_id: User identifier

        Returns:
            Job specification or None
        """
        repo = self._get_repo_for_user(user_id)
        return await repo.get_job(job_id)

    def get_state(self, job_id: str, user_id: str) -> CronJobState:
        """Get job state for a user.

        Args:
            job_id: Job identifier
            user_id: User identifier

        Returns:
            Job state
        """
        return self._states.get(user_id, {}).get(job_id, CronJobState())

    # ----- write/control -----

    async def create_or_replace_job(
        self,
        spec: CronJobSpec,
        user_id: str,
    ) -> None:
        """Create or replace a job for a user.

        Args:
            spec: Job specification
            user_id: User identifier
        """
        async with self._lock:
            repo = self._get_repo_for_user(user_id)
            await repo.upsert_job(spec)
            if self._started:
                await self._register_or_update(user_id, spec)
                if user_id in self._user_jobs:
                    self._user_jobs[user_id].add(spec.id)

    async def delete_job(self, job_id: str, user_id: str) -> bool:
        """Delete a job for a user.

        Args:
            job_id: Job identifier
            user_id: User identifier

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if self._started and self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

            # Clean up state
            if user_id in self._states:
                self._states[user_id].pop(job_id, None)
            if user_id in self._rt:
                self._rt[user_id].pop(job_id, None)
            if user_id in self._user_jobs:
                self._user_jobs[user_id].discard(job_id)

            repo = self._get_repo_for_user(user_id)
            return await repo.delete_job(job_id)

    async def pause_job(self, job_id: str, user_id: str) -> None:
        """Pause a job for a user.

        Args:
            job_id: Job identifier
            user_id: User identifier
        """
        async with self._lock:
            self._scheduler.pause_job(job_id)

    async def resume_job(self, job_id: str, user_id: str) -> None:
        """Resume a job for a user.

        Args:
            job_id: Job identifier
            user_id: User identifier
        """
        async with self._lock:
            self._scheduler.resume_job(job_id)

    async def reschedule_heartbeat(self, user_id: str) -> None:
        """Reload heartbeat config and update/remove heartbeat for a user.

        Args:
            user_id: User identifier
        """
        async with self._lock:
            if not self._started:
                return

            heartbeat_job_id = f"_heartbeat:{user_id}"
            if self._scheduler.get_job(heartbeat_job_id):
                self._scheduler.remove_job(heartbeat_job_id)

            # Use per-user heartbeat config
            from ...config.utils import load_config, get_config_path

            config = load_config(get_config_path(user_id))
            hb = config.agents.defaults.heartbeat
            if hb is None:
                hb = get_heartbeat_config()  # fallback

            if getattr(hb, "enabled", True):
                interval_seconds = parse_heartbeat_every(hb.every)
                self._scheduler.add_job(
                    self._heartbeat_callback_for_user,
                    trigger=IntervalTrigger(seconds=interval_seconds),
                    id=heartbeat_job_id,
                    replace_existing=True,
                    args=[user_id],
                )
                logger.info(
                    "heartbeat rescheduled for user=%s: every=%s (interval=%ss)",
                    user_id,
                    hb.every,
                    interval_seconds,
                )
            else:
                logger.info(
                    "heartbeat disabled for user=%s, job removed",
                    user_id,
                )

    async def run_job(self, job_id: str, user_id: str) -> None:
        """Trigger a job to run in the background.

        Args:
            job_id: Job identifier
            user_id: User identifier

        Raises:
            KeyError: If job not found
        """
        job = await self._get_repo_for_user(user_id).get_job(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        logger.info(
            "cron run_job (async): job_id=%s user_id=%s channel=%s task_type=%s "
            "target_user_id=%s target_session_id=%s",
            job_id,
            user_id,
            job.dispatch.channel,
            job.task_type,
            (job.dispatch.target.user_id or "")[:40],
            (job.dispatch.target.session_id or "")[:40],
        )
        task = asyncio.create_task(
            self._execute_once(user_id, job),
            name=f"cron-run-{job_id}",
        )
        task.add_done_callback(lambda t: self._task_done_cb(t, job))

    # ----- callbacks -----

    def _task_done_cb(self, task: asyncio.Task, job: CronJobSpec) -> None:
        """Suppress and log exceptions from fire-and-forget tasks."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "cron background task %s failed: %s",
                task.get_name(),
                repr(exc),
            )
            # Push error to the console for the frontend to display
            session_id = job.dispatch.target.session_id
            if session_id:
                error_text = f"❌ Cron job [{job.name}] failed: {exc}"
                asyncio.ensure_future(
                    push_store_append(
                        job.dispatch.target.user_id,  # Add user_id
                        session_id,
                        error_text,
                    ),
                )

    # ----- internal -----

    async def _register_or_update(
        self,
        user_id: str,
        spec: CronJobSpec,
    ) -> None:
        """Register or update a job in the scheduler.

        Args:
            user_id: User identifier
            spec: Job specification
        """
        # Per-job concurrency semaphore
        if user_id not in self._rt:
            self._rt[user_id] = {}
        self._rt[user_id][spec.id] = _Runtime(
            sem=asyncio.Semaphore(spec.runtime.max_concurrency),
        )

        trigger = self._build_trigger(spec)

        # Replace existing
        if self._scheduler.get_job(spec.id):
            self._scheduler.remove_job(spec.id)

        self._scheduler.add_job(
            self._scheduled_callback,
            trigger=trigger,
            id=spec.id,
            args=[user_id, spec.id],
            misfire_grace_time=spec.runtime.misfire_grace_seconds,
            replace_existing=True,
        )

        if not spec.enabled:
            self._scheduler.pause_job(spec.id)

        # Update next_run
        aps_job = self._scheduler.get_job(spec.id)
        if user_id not in self._states:
            self._states[user_id] = {}
        st = self._states[user_id].get(spec.id, CronJobState())
        st.next_run_at = aps_job.next_run_time if aps_job else None
        self._states[user_id][spec.id] = st

    def _build_trigger(self, spec: CronJobSpec) -> CronTrigger:
        """Build APScheduler trigger from spec."""
        # Enforce 5 fields (no seconds)
        parts = [p for p in spec.schedule.cron.split() if p]
        if len(parts) != 5:
            raise ValueError(
                f"cron must have 5 fields, got {len(parts)}:"
                f" {spec.schedule.cron}",
            )

        minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=spec.schedule.timezone,
        )

    async def _scheduled_callback(self, user_id: str, job_id: str) -> None:
        """Callback when a job is triggered by scheduler.

        Args:
            user_id: User identifier
            job_id: Job identifier
        """
        job = await self._get_repo_for_user(user_id).get_job(job_id)
        if not job:
            return

        # Set request context for user isolation during execution
        from ...constant import set_request_user_id, reset_request_user_id

        token = set_request_user_id(user_id)
        try:
            await self._execute_once(user_id, job)
        finally:
            reset_request_user_id(token)

        # Refresh next_run
        aps_job = self._scheduler.get_job(job_id)
        if user_id in self._states:
            st = self._states[user_id].get(job_id, CronJobState())
            st.next_run_at = aps_job.next_run_time if aps_job else None
            self._states[user_id][job_id] = st

    async def _start_user_heartbeat(self, user_id: str) -> None:
        """Start heartbeat for a specific user.

        Args:
            user_id: User identifier
        """
        from ...config.utils import load_config, get_config_path
        from ...constant import get_working_dir

        config = load_config(get_config_path(user_id))
        hb = config.agents.defaults.heartbeat
        if hb is None:
            hb = get_heartbeat_config()  # fallback to default

        if not getattr(hb, "enabled", True):
            return

        # Check if HEARTBEAT.md exists
        heartbeat_path = get_working_dir(user_id) / "HEARTBEAT.md"
        if not heartbeat_path.exists():
            return

        interval_seconds = parse_heartbeat_every(hb.every)
        heartbeat_job_id = f"_heartbeat:{user_id}"

        self._scheduler.add_job(
            self._heartbeat_callback_for_user,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=heartbeat_job_id,
            replace_existing=True,
            args=[user_id],
        )
        logger.info(
            "heartbeat started for user=%s: every=%s (interval=%ss)",
            user_id,
            hb.every,
            interval_seconds,
        )

    async def _heartbeat_callback_for_user(self, user_id: str) -> None:
        """Heartbeat callback for a specific user.

        Args:
            user_id: User identifier
        """
        try:
            # Set request context for user isolation
            from ...constant import set_request_user_id, reset_request_user_id

            token = set_request_user_id(user_id)
            try:
                await run_heartbeat_once(
                    runner=self._runner,
                    channel_manager=self._channel_manager,
                    user_id=user_id,
                )
            finally:
                reset_request_user_id(token)
        except Exception:  # pylint: disable=broad-except
            logger.exception("heartbeat run failed for user=%s", user_id)

    async def _execute_once(self, user_id: str, job: CronJobSpec) -> None:
        """Execute a job once.

        Args:
            user_id: User identifier
            job: Job specification
        """
        rt = self._rt.get(user_id, {}).get(job.id)
        if not rt:
            rt = _Runtime(sem=asyncio.Semaphore(job.runtime.max_concurrency))
            if user_id not in self._rt:
                self._rt[user_id] = {}
            self._rt[user_id][job.id] = rt

        async with rt.sem:
            if user_id not in self._states:
                self._states[user_id] = {}
            st = self._states[user_id].get(job.id, CronJobState())
            st.last_status = "running"
            self._states[user_id][job.id] = st

            try:
                await self._executor.execute(job)
                st.last_status = "success"
                st.last_error = None
                logger.info(
                    "cron _execute_once: job_id=%s user_id=%s status=success",
                    job.id,
                    user_id,
                )
            except Exception as e:  # pylint: disable=broad-except
                st.last_status = "error"
                st.last_error = repr(e)
                logger.warning(
                    "cron _execute_once: job_id=%s user_id=%s status=error error=%s",
                    job.id,
                    user_id,
                    repr(e),
                )
                raise
            finally:
                # Use scheduler's timezone for consistency with next_run_at
                st.last_run_at = datetime.now(self._scheduler.timezone)
                self._states[user_id][job.id] = st
