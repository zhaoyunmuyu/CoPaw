# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ...config import get_heartbeat_config

from ..tenant_context import bind_tenant_context
from ..console_push_store import append as push_store_append
from .coordination import (
    CoordinationConfig,
    CronCoordination,
)
from .executor import CronExecutor
from .heartbeat import (
    is_cron_expression,
    parse_heartbeat_cron,
    parse_heartbeat_every,
    run_heartbeat_once,
)
from .models import CronJobSpec, CronJobState, JobsFile
from .repo.base import BaseJobRepository

HEARTBEAT_JOB_ID = "_heartbeat"

logger = logging.getLogger(__name__)
_T = TypeVar("_T")


@dataclass
class _Runtime:
    sem: asyncio.Semaphore


class CronManager:
    """Manages scheduled cron jobs and heartbeat.

    This class has been refactored to support Redis-coordinated leadership:
    - Passive initialization: The manager is created but scheduler not started
    - Explicit activation: When leadership is acquired, start() is called
    - Explicit deactivation: When leadership is lost, stop() is called
    - Reload from repo: When configuration changes, reload() rebuilds schedule
    """

    def __init__(
        self,
        *,
        repo: BaseJobRepository,
        runner: Any,
        channel_manager: Any,
        timezone: str = "UTC",  # pylint: disable=redefined-outer-name
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        coordination_config: Optional[CoordinationConfig] = None,
    ):
        self._repo = repo
        self._runner = runner
        self._channel_manager = channel_manager
        self._agent_id = agent_id
        self._tenant_id = tenant_id
        self._timezone = timezone
        self._coordination_config = coordination_config

        # Scheduler is created but NOT started in __init__
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._executor = CronExecutor(
            runner=runner,
            channel_manager=channel_manager,
        )

        self._lock = asyncio.Lock()
        self._states: Dict[str, CronJobState] = {}
        self._rt: Dict[str, _Runtime] = {}
        self._started = False
        self._definition_version = 0
        self._definition_reconcile_task: Optional[asyncio.Task] = None
        self._stop_definition_reconcile = asyncio.Event()

        # Coordination for multi-instance leadership
        self._coordination: Optional[CronCoordination] = None
        if coordination_config is not None and coordination_config.enabled:
            self._coordination = CronCoordination(
                tenant_id=tenant_id,
                agent_id=agent_id or "default",
                config=coordination_config,
            )
            # Set callbacks
            self._coordination.set_reload_callback(self._on_reload_signal)
            self._coordination.set_lease_lost_callback(self._on_lease_lost)
            self._coordination.set_become_leader_callback(self._on_become_leader)

        self._active_jobs: set[str] = set()  # Track which jobs are scheduled

    @property
    def is_started(self) -> bool:
        """Check if the scheduler is currently started."""
        return self._started

    @property
    def is_leader(self) -> bool:
        """Check if this instance is the current leader (if coordination enabled)."""
        if self._coordination is None:
            return True  # No coordination = always leader
        return self._coordination.is_leader

    async def initialize(self) -> None:
        """Passive initialization - prepare resources but don't start scheduler.

        This is called during workspace setup. The scheduler is NOT started
        here - that happens in activate() when leadership is confirmed.
        """
        async with self._lock:
            if self._scheduler is not None:
                return

            self._scheduler = AsyncIOScheduler(timezone=self._timezone)
            logger.debug(
                "CronManager initialized (passive): agent=%s",
                self._agent_id,
            )

    async def connect_coordination(self) -> bool:
        """Connect to Redis coordination.

        Returns True if connected/coordination enabled, False otherwise.
        """
        if self._coordination is None:
            return True  # No coordination needed

        return await self._coordination.connect()

    async def disconnect_coordination(self) -> None:
        """Disconnect from Redis coordination."""
        if self._coordination is not None:
            await self._coordination.disconnect()

    async def activate(self) -> bool:
        """Activate scheduling - acquire leadership and start scheduler.

        Returns True if this instance became the active leader,
        False if this is a follower.

        Raises:
            RedisNotAvailableError: If coordination is enabled but Redis is not available.
        """
        await self.initialize()

        # Connect coordination first
        connected = await self.connect_coordination()

        if self._coordination is not None:
            # Coordination is enabled - we must connect to Redis
            if not connected:
                logger.error(
                    "CronManager failed to activate: Redis coordination enabled "
                    "but Redis is not available (agent=%s)",
                    self._agent_id,
                )
                raise RuntimeError(
                    "Redis coordination is enabled but Redis is not available. "
                    "Please check Redis connection or disable coordination.",
                )

            # Try to acquire leadership
            is_leader = await self._coordination.activate()
            if not is_leader:
                logger.info(
                    "CronManager activated as follower: agent=%s",
                    self._agent_id,
                )
                # Start candidate loop for automatic failover
                await self._coordination.start_candidate_loop()
                return False
            logger.info(
                "CronManager activated as leader: agent=%s instance=%s",
                self._agent_id,
                self._coordination.instance_id,
            )
        else:
            logger.info(
                "CronManager activated (no coordination): agent=%s",
                self._agent_id,
            )

        # Start the scheduler
        try:
            await self._do_start()
        except Exception:
            logger.exception(
                "Failed to start scheduler during activate: agent=%s",
                self._agent_id,
            )
            await self._cleanup_failed_leader_startup()
            raise
        return True

    async def deactivate(self) -> None:
        """Deactivate scheduling - stop scheduler and release leadership."""
        await self._do_stop()

        if self._coordination is not None:
            await self._coordination.deactivate()
            logger.info(
                "CronManager deactivated: agent=%s",
                self._agent_id,
            )

    async def reload(self) -> None:
        """Reload jobs from repository and rebuild schedule.

        This is called when:
        - A reload signal is received from another instance
        - Local cron mutations are made
        """
        async with self._lock:
            if not self._started or self._scheduler is None:
                logger.debug(
                    "Cannot reload: scheduler not started (agent=%s)",
                    self._agent_id,
                )
                return

            logger.info(
                "Reloading cron schedule from repository: agent=%s",
                self._agent_id,
            )

            # Clear existing jobs (except heartbeat)
            jobs_to_remove = [
                job_id
                for job_id in self._active_jobs
                if job_id != HEARTBEAT_JOB_ID
            ]
            for job_id in jobs_to_remove:
                if self._scheduler.get_job(job_id):
                    self._scheduler.remove_job(job_id)
                self._active_jobs.discard(job_id)

            # Load jobs from repo
            invalid_enabled_jobs: set[str] = set()
            jobs_file: Optional[JobsFile] = None
            try:
                jobs_file = await self._repo.load()
                for job in jobs_file.jobs:
                    try:
                        await self._register_or_update(job)
                    except Exception as e:  # pylint: disable=broad-except
                        logger.warning(
                            "Skipping invalid cron job during reload: "
                            "job_id=%s name=%s error=%s",
                            job.id,
                            job.name,
                            repr(e),
                        )
                        if job.enabled:
                            invalid_enabled_jobs.add(job.id)
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Failed to reload jobs from repository: %s", e)

            if invalid_enabled_jobs:
                await self._auto_disable_invalid_jobs_locked(
                    invalid_enabled_jobs,
                )

            # Reload heartbeat
            await self._update_heartbeat()
            await self._refresh_definition_version_locked(jobs_file=jobs_file)

            logger.info(
                "Cron schedule reloaded: agent=%s jobs=%d",
                self._agent_id,
                len(self._active_jobs),
            )

    async def _do_start(self) -> None:
        """Internal: Start the scheduler and load initial jobs."""
        async with self._lock:
            if self._started:
                return

            if self._scheduler is None:
                raise RuntimeError("CronManager not initialized")

            jobs_file = await self._repo.load()
            invalid_enabled_jobs: set[str] = set()

            self._scheduler.start()
            for job in jobs_file.jobs:
                try:
                    await self._register_or_update(job)
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(
                        "Skipping invalid cron job during startup: "
                        "job_id=%s name=%s cron=%s error=%s",
                        job.id,
                        job.name,
                        job.schedule.cron,
                        repr(e),
                    )
                    if job.enabled:
                        invalid_enabled_jobs.add(job.id)

            if invalid_enabled_jobs:
                await self._auto_disable_invalid_jobs_locked(
                    invalid_enabled_jobs,
                )

            # Heartbeat: scheduled job when enabled in config
            await self._update_heartbeat()
            await self._refresh_definition_version_locked(jobs_file=jobs_file)

            self._started = True
            self._start_definition_reconcile_loop()
            logger.info(
                "CronManager started: agent=%s jobs=%d",
                self._agent_id,
                len(self._active_jobs),
            )

    async def _do_stop(self) -> None:
        """Internal: Stop the scheduler."""
        async with self._lock:
            if not self._started:
                return
            if self._scheduler is not None:
                self._scheduler.shutdown(wait=False)
            self._started = False
            self._active_jobs.clear()
            await self._stop_definition_reconcile_loop()
            logger.info("CronManager stopped: agent=%s", self._agent_id)

    def _on_reload_signal(self) -> None:
        """Callback invoked when a reload signal is received."""
        logger.info(
            "Received reload signal, scheduling reload: agent=%s",
            self._agent_id,
        )
        # Schedule reload in the event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.reload())
        except RuntimeError:
            # No event loop running - this shouldn't happen in normal operation
            logger.warning(
                "Cannot schedule reload: no event loop (agent=%s)",
                self._agent_id,
            )

    def _on_lease_lost(self) -> None:
        """Callback invoked when the leadership lease is lost.

        This stops the scheduler to prevent duplicate executions.
        """
        logger.warning(
            "Lease lost callback invoked, deactivating scheduler: agent=%s",
            self._agent_id,
        )
        # Schedule deactivate in the event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.deactivate())
        except RuntimeError:
            # No event loop running - this shouldn't happen in normal operation
            logger.warning(
                "Cannot schedule deactivate: no event loop (agent=%s)",
                self._agent_id,
            )

    def _on_become_leader(self) -> None:
        """Callback invoked when this instance becomes leader via candidate loop.

        This starts the scheduler to begin cron execution.
        If startup fails, releases the lease to allow another instance to take over.
        """
        logger.info(
            "Become leader callback invoked, starting scheduler: agent=%s",
            self._agent_id,
        )
        # Schedule start in the event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._become_leader_and_start())
        except RuntimeError:
            # No event loop running - this shouldn't happen in normal operation
            logger.warning(
                "Cannot schedule start: no event loop (agent=%s)",
                self._agent_id,
            )

    async def _become_leader_and_start(self) -> None:
        """Internal: Start scheduler after becoming leader via candidate loop.

        This wrapper handles startup failures by releasing the lease,
        allowing another instance to take over.
        """
        try:
            await self._do_start()
            logger.info(
                "Successfully started scheduler after becoming leader: agent=%s",
                self._agent_id,
            )
        except Exception:
            logger.exception(
                "Failed to start scheduler after becoming leader: agent=%s",
                self._agent_id,
            )
            try:
                await self._cleanup_failed_leader_startup()
            except Exception:
                logger.exception(
                    "Unexpected error during startup failure cleanup: "
                    "agent=%s",
                    self._agent_id,
                )
            return

    async def _cleanup_failed_leader_startup(self) -> None:
        """Rollback partial startup and release leadership on startup failure.

        Never raises: best-effort cleanup for callback/background safety.
        """
        # _do_start() can fail after starting APScheduler but before _started=True.
        # Roll back scheduler runtime state before manager-level cleanup.
        had_running_scheduler = self._scheduler is not None and getattr(
            self._scheduler, "running", False,
        )
        safe_to_release = True
        if had_running_scheduler:
            safe_to_release = self._rollback_partially_started_scheduler()

        if had_running_scheduler and not safe_to_release:
            # Scheduler may still run jobs: keep coordination ownership to
            # avoid split-brain duplicate execution.
            self._started = True
            logger.error(
                "Emergency path: scheduler not safely stopped during startup "
                "rollback, keeping leadership: agent=%s",
                self._agent_id,
            )
            return

        self._started = False
        self._active_jobs.clear()
        self._rt.clear()

        if self._coordination is not None:
            logger.warning(
                "Releasing lease due to startup failure: agent=%s",
                self._agent_id,
            )
        try:
            await self.deactivate()
        except Exception:
            logger.exception(
                "Failed to deactivate during startup failure cleanup: "
                "agent=%s",
                self._agent_id,
            )
            return

    def _rollback_partially_started_scheduler(self) -> bool:
        """Try to stop/disable a running scheduler after startup failure."""
        if self._scheduler is None:
            return True

        try:
            self._scheduler.shutdown(wait=False)
        except Exception:
            logger.exception(
                "Failed to shutdown scheduler during rollback: agent=%s",
                self._agent_id,
            )
            return self._best_effort_disable_scheduler()

        # AsyncIOScheduler is not restartable after shutdown.
        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        return True

    def _best_effort_disable_scheduler(self) -> bool:
        """Best-effort disable path when scheduler.shutdown() fails."""
        if self._scheduler is None:
            return True

        paused = False
        removed = False

        try:
            self._scheduler.pause()
            paused = True
        except Exception:
            logger.exception(
                "Failed to pause scheduler during rollback: agent=%s",
                self._agent_id,
            )

        try:
            self._scheduler.remove_all_jobs()
            removed = True
            self._active_jobs.clear()
        except Exception:
            logger.exception(
                "Failed to remove scheduler jobs during rollback: agent=%s",
                self._agent_id,
            )

        if paused or removed:
            logger.warning(
                "Scheduler shutdown failed, used disable fallback: "
                "agent=%s paused=%s removed=%s",
                self._agent_id,
                paused,
                removed,
            )
            return True
        return False

    async def _update_heartbeat(self) -> None:
        """Update heartbeat job based on current config."""
        if self._scheduler is None:
            return

        # Remove existing heartbeat job if present
        if self._scheduler.get_job(HEARTBEAT_JOB_ID):
            self._scheduler.remove_job(HEARTBEAT_JOB_ID)
            self._active_jobs.discard(HEARTBEAT_JOB_ID)

        hb = get_heartbeat_config(self._agent_id)
        if getattr(hb, "enabled", False):
            trigger = self._build_heartbeat_trigger(hb.every)
            self._scheduler.add_job(
                self._heartbeat_callback,
                trigger=trigger,
                id=HEARTBEAT_JOB_ID,
                replace_existing=True,
            )
            self._active_jobs.add(HEARTBEAT_JOB_ID)
            logger.info(
                "Heartbeat job scheduled for agent %s: every=%s",
                self._agent_id,
                hb.every,
            )

    # ----- read/state -----

    async def list_jobs(self) -> list[CronJobSpec]:
        return await self._repo.list_jobs()

    async def get_job(self, job_id: str) -> Optional[CronJobSpec]:
        return await self._repo.get_job(job_id)

    def get_state(self, job_id: str) -> CronJobState:
        return self._states.get(job_id, CronJobState())

    # ----- write/control -----

    async def create_or_replace_job(self, spec: CronJobSpec) -> None:
        async with self._lock:
            changed, _, _ = await self._mutate_jobs_file_locked(
                lambda jobs_file: self._upsert_job_in_jobs_file(
                    jobs_file,
                    spec,
                ),
            )
            if self._started and self._scheduler is not None:
                if changed or self._scheduler.get_job(spec.id) is None:
                    await self._register_or_update(spec)

    async def delete_job(self, job_id: str) -> bool:
        async with self._lock:
            changed, found, _ = await self._mutate_jobs_file_locked(
                lambda jobs_file: self._delete_job_in_jobs_file(
                    jobs_file,
                    job_id,
                ),
            )
            if not found:
                return False

            if self._started and self._scheduler is not None:
                if self._scheduler.get_job(job_id):
                    self._scheduler.remove_job(job_id)
                self._active_jobs.discard(job_id)
            self._states.pop(job_id, None)
            self._rt.pop(job_id, None)
            return found if changed else found

    async def pause_job(self, job_id: str) -> bool:
        """Pause a job - disables execution and persists to repository.

        Args:
            job_id: The job ID to pause.

        Returns:
            True if job was found and paused, False otherwise.
        """
        async with self._lock:
            changed, job, _ = await self._mutate_jobs_file_locked(
                lambda jobs_file: self._set_job_enabled_in_jobs_file(
                    jobs_file,
                    job_id,
                    enabled=False,
                ),
            )
            if job is None:
                return False

            # Pause in scheduler if started
            if self._started and self._scheduler is not None:
                if self._scheduler.get_job(job_id):
                    self._scheduler.pause_job(job_id)

            return True

    async def resume_job(self, job_id: str) -> bool:
        """Resume a paused job - enables execution and persists to repository.

        Args:
            job_id: The job ID to resume.

        Returns:
            True if job was found and resumed, False otherwise.
        """
        async with self._lock:
            changed, job, _ = await self._mutate_jobs_file_locked(
                lambda jobs_file: self._set_job_enabled_in_jobs_file(
                    jobs_file,
                    job_id,
                    enabled=True,
                ),
            )
            if job is None:
                return False

            # Resume in scheduler if started
            if self._started and self._scheduler is not None:
                if self._scheduler.get_job(job_id):
                    self._scheduler.resume_job(job_id)

            return True

    async def reschedule_heartbeat(self) -> None:
        """Reload heartbeat config and update or remove the heartbeat job.

        Note: This should be called after activate() when the manager is leader.
        Heartbeat config lives in agent config rather than jobs.json, so these
        changes converge through the config watcher + reschedule flow, not
        through the cron definition version/reconcile path.
        """
        async with self._lock:
            if not self._started:
                logger.warning(
                    f"CronManager not started for agent {self._agent_id}, "
                    f"cannot reschedule heartbeat. This should not happen.",
                )
                return

            await self._update_heartbeat()

    async def run_job(self, job_id: str) -> None:
        """Trigger a job to run in the background (fire-and-forget).

        This is a MANUAL execution outside scheduler ownership semantics.
        It does not use scheduler-originated lease preflight.

        Raises KeyError if the job does not exist.
        The actual execution happens asynchronously; errors are logged
        and reflected in the job state but NOT propagated to the caller.
        """
        job = await self._repo.get_job(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        logger.info(
            "cron run_job (manual, outside scheduler ownership semantics): "
            "job_id=%s channel=%s task_type=%s "
            "target_user_id=%s target_session_id=%s",
            job_id,
            job.dispatch.channel,
            job.task_type,
            (job.dispatch.target.user_id or "")[:40],
            (job.dispatch.target.session_id or "")[:40],
        )
        task = asyncio.create_task(
            self._execute_once(job),
            name=f"c ron-run-{job_id}",
        )
        task.add_done_callback(lambda t: self._task_done_cb(t, job))

    # ----- callbacks -----

    def _task_done_cb(self, task: asyncio.Task, job: CronJobSpec) -> None:
        """Suppress and log exceptions from fire-and-forget tasks.

        On failure, push an error message to the console push store so
        the frontend can display it.
        """
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

                async def _push_error() -> None:
                    await push_store_append(
                        session_id,
                        error_text,
                        tenant_id=job.tenant_id,
                    )

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(_push_error())
                else:
                    loop.create_task(_push_error())

    # ----- internal -----

    async def _mutate_jobs_file_locked(
        self,
        mutator: Callable[[JobsFile], tuple[bool, _T]],
    ) -> tuple[bool, _T, int]:
        definition_lock = None
        changed = False
        should_publish = False
        save_succeeded = False
        result: _T
        version = self._definition_version

        if self._coordination is not None:
            definition_lock = await self._coordination.acquire_definition_lock()

        try:
            jobs_file = await self._repo.load()
            version = max(
                version,
                self._get_jobs_file_definition_version(jobs_file),
            )
            if self._coordination is not None:
                version = max(
                    version,
                    await self._coordination.get_definition_version(),
                )
            changed, result = mutator(jobs_file)
            if not changed:
                return False, result, version

            version += 1
            jobs_file.definition_version = version
            await self._repo.save(jobs_file)
            save_succeeded = True
            if self._coordination is not None:
                version = await self._coordination.ensure_definition_version(version)
            self._definition_version = version
            should_publish = True
            return True, result, version
        except Exception:
            if save_succeeded and not should_publish:
                logger.warning(
                    "Cron definition mutation saved jobs.json but failed to sync "
                    "definition version: "
                    "agent=%s version=%s",
                    self._agent_id,
                    version,
                    exc_info=True,
                )
            raise
        finally:
            if definition_lock is not None:
                await definition_lock.release()
                if should_publish:
                    await self._coordination.publish_reload(version=version)

    async def _auto_disable_invalid_jobs_locked(
        self,
        job_ids: set[str],
    ) -> None:
        changed, disabled_ids, _ = await self._mutate_jobs_file_locked(
            lambda jobs_file: self._disable_invalid_jobs_in_jobs_file(
                jobs_file,
                job_ids,
            ),
        )
        if changed:
            for job_id in disabled_ids:
                logger.warning("Auto-disabled invalid cron job: job_id=%s", job_id)

    @staticmethod
    def _get_jobs_file_definition_version(jobs_file: JobsFile) -> int:
        return max(int(getattr(jobs_file, "definition_version", 0) or 0), 0)

    async def _refresh_definition_version_locked(
        self,
        *,
        jobs_file: Optional[JobsFile] = None,
    ) -> None:
        file_version = (
            self._get_jobs_file_definition_version(jobs_file)
            if jobs_file is not None
            else None
        )
        remote_version: Optional[int] = None

        if self._coordination is not None:
            try:
                remote_version = await self._coordination.get_definition_version()
                if (
                    file_version is not None
                    and remote_version is not None
                    and file_version > remote_version
                ):
                    remote_version = await self._coordination.ensure_definition_version(
                        file_version,
                    )
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "Failed to refresh cron definition version: agent=%s",
                    self._agent_id,
                    exc_info=True,
                )

        versions = [self._definition_version]
        if file_version is not None:
            versions.append(file_version)
        if remote_version is not None:
            versions.append(remote_version)
        self._definition_version = max(versions)

    def _start_definition_reconcile_loop(self) -> None:
        if self._coordination is None or self._definition_reconcile_task is not None:
            return
        self._stop_definition_reconcile.clear()
        self._definition_reconcile_task = asyncio.create_task(
            self._definition_reconcile_loop(),
            name=f"cron-def-reconcile-{self._tenant_id or 'default'}-{self._agent_id}",
        )

    async def _stop_definition_reconcile_loop(self) -> None:
        if self._definition_reconcile_task is None:
            return
        self._stop_definition_reconcile.set()
        try:
            await asyncio.wait_for(self._definition_reconcile_task, timeout=5.0)
        except asyncio.TimeoutError:
            self._definition_reconcile_task.cancel()
            try:
                await self._definition_reconcile_task
            except asyncio.CancelledError:
                pass
        self._definition_reconcile_task = None

    async def _definition_reconcile_loop(self) -> None:
        interval = 10
        if self._coordination_config is not None:
            interval = self._coordination_config.lease_renew_interval_seconds

        while not self._stop_definition_reconcile.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_definition_reconcile.wait(),
                    timeout=interval,
                )
                return
            except asyncio.TimeoutError:
                pass

            try:
                await self._reconcile_definition_version_once()
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "Cron definition reconcile failed: agent=%s",
                    self._agent_id,
                    exc_info=True,
                )

    async def _reconcile_definition_version_once(self) -> None:
        if self._coordination is None or not self._started or not self.is_leader:
            return

        jobs_file = await self._repo.load()
        file_version = self._get_jobs_file_definition_version(jobs_file)

        remote_version = self._definition_version
        try:
            remote_version = await self._coordination.get_definition_version()
            if file_version > remote_version:
                remote_version = await self._coordination.ensure_definition_version(
                    file_version,
                )
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "Failed to read or repair cron definition version during "
                "reconcile: agent=%s",
                self._agent_id,
                exc_info=True,
            )

        observed_version = max(file_version, remote_version)
        if observed_version > self._definition_version:
            logger.info(
                "Reconciling cron definitions after missed reload: "
                "agent=%s local_version=%s file_version=%s remote_version=%s",
                self._agent_id,
                self._definition_version,
                file_version,
                remote_version,
            )
            await self.reload()

    def _upsert_job_in_jobs_file(
        self,
        jobs_file: JobsFile,
        spec: CronJobSpec,
    ) -> tuple[bool, CronJobSpec]:
        for index, job in enumerate(jobs_file.jobs):
            if job.id == spec.id:
                if job == spec:
                    return False, spec
                jobs_file.jobs[index] = spec
                return True, spec
        jobs_file.jobs.append(spec)
        return True, spec

    def _delete_job_in_jobs_file(
        self,
        jobs_file: JobsFile,
        job_id: str,
    ) -> tuple[bool, bool]:
        before = len(jobs_file.jobs)
        jobs_file.jobs = [job for job in jobs_file.jobs if job.id != job_id]
        return before != len(jobs_file.jobs), before != len(jobs_file.jobs)

    def _set_job_enabled_in_jobs_file(
        self,
        jobs_file: JobsFile,
        job_id: str,
        *,
        enabled: bool,
    ) -> tuple[bool, Optional[CronJobSpec]]:
        for index, job in enumerate(jobs_file.jobs):
            if job.id != job_id:
                continue
            if job.enabled == enabled:
                return False, job
            updated = job.model_copy(update={"enabled": enabled})
            jobs_file.jobs[index] = updated
            return True, updated
        return False, None

    def _disable_invalid_jobs_in_jobs_file(
        self,
        jobs_file: JobsFile,
        job_ids: set[str],
    ) -> tuple[bool, list[str]]:
        changed = False
        disabled_ids: list[str] = []
        for index, job in enumerate(jobs_file.jobs):
            if job.id not in job_ids or not job.enabled:
                continue
            jobs_file.jobs[index] = job.model_copy(update={"enabled": False})
            disabled_ids.append(job.id)
            changed = True
        return changed, disabled_ids

    async def _register_or_update(self, spec: CronJobSpec) -> None:
        if self._scheduler is None:
            return

        # Validate and build trigger first. If cron is invalid, fail fast
        # without mutating scheduler/runtime state.
        trigger = self._build_trigger(spec)

        # per-job concurrency semaphore
        self._rt[spec.id] = _Runtime(
            sem=asyncio.Semaphore(spec.runtime.max_concurrency),
        )

        # replace existing
        if self._scheduler.get_job(spec.id):
            self._scheduler.remove_job(spec.id)

        self._scheduler.add_job(
            self._scheduled_callback,
            trigger=trigger,
            id=spec.id,
            args=[spec.id],
            misfire_grace_time=spec.runtime.misfire_grace_seconds,
            replace_existing=True,
        )
        self._active_jobs.add(spec.id)

        if not spec.enabled:
            self._scheduler.pause_job(spec.id)

        # update next_run
        aps_job = self._scheduler.get_job(spec.id)
        st = self._states.get(spec.id, CronJobState())
        st.next_run_at = aps_job.next_run_time if aps_job else None
        self._states[spec.id] = st

    def _build_trigger(self, spec: CronJobSpec) -> CronTrigger:
        # enforce 5 fields (no seconds)
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

    def _build_heartbeat_trigger(
        self,
        every: str,
    ) -> Union[CronTrigger, IntervalTrigger]:
        """Build a trigger from the heartbeat *every* value.

        Returns CronTrigger for cron expressions,
        IntervalTrigger for interval strings.
        """
        if is_cron_expression(every):
            minute, hour, day, month, day_of_week = parse_heartbeat_cron(every)
            return CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            )
        interval_seconds = parse_heartbeat_every(every)
        return IntervalTrigger(seconds=interval_seconds)

    async def _scheduled_callback(self, job_id: str) -> None:
        """Callback invoked by APScheduler for timed execution.

        Scheduler-originated cron runs use lease preflight immediately before
        work starts. This reduces stale-leader execution, but failover remains
        at-least-once and handlers must therefore be idempotent.
        """
        # Check if we're still the leader
        if self._coordination is not None and not self._coordination.is_leader:
            logger.debug(
                "Skipping scheduled job: not leader (agent=%s, job=%s)",
                self._agent_id,
                job_id,
            )
            return

        job = await self._repo.get_job(job_id)
        if not job:
            return

        if self._coordination is not None:
            still_owner = await self._coordination.preflight_scheduler_execution(
                job_id=job_id,
                schedule_type="cron",
            )
            if not still_owner:
                logger.info(
                    "Skipping scheduled cron after lease preflight: "
                    "agent=%s job_id=%s",
                    self._agent_id,
                    job_id,
                )
                st = self._states.get(job_id, CronJobState())
                st.last_status = "skipped"
                st.last_error = "stale leader preflight rejected execution"
                st.last_run_at = datetime.now(timezone.utc)
                self._states[job_id] = st
                return

            await self._execute_once(job)
        else:
            # No coordination - execute directly
            await self._execute_once(job)

        # refresh next_run
        if self._scheduler is not None:
            aps_job = self._scheduler.get_job(job_id)
            st = self._states.get(job_id, CronJobState())
            st.next_run_at = aps_job.next_run_time if aps_job else None
            self._states[job_id] = st

    async def _heartbeat_callback(self) -> None:
        """Run one heartbeat under the same preflight as ordinary cron jobs."""
        # Check if we're still the leader
        if self._coordination is not None and not self._coordination.is_leader:
            logger.debug(
                "Skipping heartbeat: not leader (agent=%s)",
                self._agent_id,
            )
            return

        if self._coordination is not None:
            still_owner = await self._coordination.preflight_scheduler_execution(
                job_id=HEARTBEAT_JOB_ID,
                schedule_type="heartbeat",
            )
            if not still_owner:
                logger.info(
                    "Skipping heartbeat after lease preflight: agent=%s",
                    self._agent_id,
                )
                st = self._states.get(HEARTBEAT_JOB_ID, CronJobState())
                st.last_status = "skipped"
                st.last_error = "stale leader preflight rejected execution"
                st.last_run_at = datetime.now(timezone.utc)
                self._states[HEARTBEAT_JOB_ID] = st
                return

        try:
            # Get workspace_dir from runner if available
            workspace_dir = None
            if hasattr(self._runner, "workspace_dir"):
                workspace_dir = self._runner.workspace_dir

            tenant_id = None
            if (
                hasattr(self._runner, "_workspace")
                and self._runner._workspace is not None
            ):
                tenant_id = getattr(self._runner._workspace, "tenant_id", None)

            with bind_tenant_context(
                tenant_id=tenant_id,
                workspace_dir=workspace_dir,
            ):
                await self._run_heartbeat_once(workspace_dir)
        except asyncio.CancelledError:
            logger.info("heartbeat cancelled")
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception("heartbeat run failed")

    async def _run_heartbeat_once(self, workspace_dir: Any) -> None:
        await run_heartbeat_once(
            runner=self._runner,
            channel_manager=self._channel_manager,
            agent_id=self._agent_id,
            workspace_dir=workspace_dir,
        )

    async def _execute_once(self, job: CronJobSpec) -> None:
        rt = self._rt.get(job.id)
        if not rt:
            rt = _Runtime(sem=asyncio.Semaphore(job.runtime.max_concurrency))
            self._rt[job.id] = rt

        async with rt.sem:
            st = self._states.get(job.id, CronJobState())
            st.last_status = "running"
            self._states[job.id] = st

            try:
                await self._executor.execute(job)
                st.last_status = "success"
                st.last_error = None
                logger.info(
                    "cron _execute_once: job_id=%s status=success",
                    job.id,
                )
            except asyncio.CancelledError:
                st.last_status = "cancelled"
                st.last_error = "Job was cancelled"
                logger.info(
                    "cron _execute_once: job_id=%s status=cancelled",
                    job.id,
                )
                raise
            except Exception as e:  # pylint: disable=broad-except
                st.last_status = "error"
                st.last_error = repr(e)
                logger.warning(
                    "cron _execute_once: job_id=%s status=error error=%s",
                    job.id,
                    repr(e),
                )
                raise
            finally:
                st.last_run_at = datetime.now(timezone.utc)
                self._states[job.id] = st

    # ----- Legacy API compatibility -----

    async def start(self) -> None:
        """Legacy start method - calls activate().

        DEPRECATED: Use activate() instead for proper coordination support.
        """
        await self.activate()

    async def stop(self) -> None:
        """Legacy stop method - calls deactivate().

        DEPRECATED: Use deactivate() instead for proper coordination support.
        """
        await self.deactivate()
