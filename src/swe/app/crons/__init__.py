# -*- coding: utf-8 -*-
"""Lazy exports for the crons package."""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "CoordinationConfig": (".coordination", "CoordinationConfig"),
    "CronCoordination": (".coordination", "CronCoordination"),
    "AgentLease": (".coordination", "AgentLease"),
    "ExecutionLock": (".coordination", "ExecutionLock"),
    "ReloadPublisher": (".coordination", "ReloadPublisher"),
    "ReloadSubscriber": (".coordination", "ReloadSubscriber"),
    "CronCoordinationError": (".coordination", "CronCoordinationError"),
    "DefinitionLockTimeoutError": (
        ".coordination",
        "DefinitionLockTimeoutError",
    ),
    "LeaseLostError": (".coordination", "LeaseLostError"),
    "RedisNotAvailableError": (".coordination", "RedisNotAvailableError"),
    "REDIS_AVAILABLE": (".coordination", "REDIS_AVAILABLE"),
    "CronManager": (".manager", "CronManager"),
    "CronJobSpec": (".models", "CronJobSpec"),
    "CronJobState": (".models", "CronJobState"),
    "CronJobView": (".models", "CronJobView"),
    "JobsFile": (".models", "JobsFile"),
    "ScheduleSpec": (".models", "ScheduleSpec"),
    "DispatchSpec": (".models", "DispatchSpec"),
    "DispatchTarget": (".models", "DispatchTarget"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
