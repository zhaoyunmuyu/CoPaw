# -*- coding: utf-8 -*-
"""Cron management module.

Provides scheduled task execution with Redis-coordinated leadership
for multi-instance deployments.
"""
from __future__ import annotations

from .coordination import (
    CoordinationConfig,
    CronCoordination,
    AgentLease,
    ExecutionLock,
    ReloadPublisher,
    ReloadSubscriber,
    CronCoordinationError,
    DefinitionLockTimeoutError,
    LeaseLostError,
    RedisNotAvailableError,
    REDIS_AVAILABLE,
)
from .manager import CronManager
from .models import (
    CronJobSpec,
    CronJobState,
    CronJobView,
    JobsFile,
    ScheduleSpec,
    DispatchSpec,
    DispatchTarget,
)

__all__ = [
    # Coordination
    "CoordinationConfig",
    "CronCoordination",
    "AgentLease",
    "ExecutionLock",
    "ReloadPublisher",
    "ReloadSubscriber",
    "CronCoordinationError",
    "DefinitionLockTimeoutError",
    "LeaseLostError",
    "RedisNotAvailableError",
    "REDIS_AVAILABLE",
    # Manager
    "CronManager",
    # Models
    "CronJobSpec",
    "CronJobState",
    "CronJobView",
    "JobsFile",
    "ScheduleSpec",
    "DispatchSpec",
    "DispatchTarget",
]
