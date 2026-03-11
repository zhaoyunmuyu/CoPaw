# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

# Default working directory (used when no user_id is specified)
DEFAULT_WORKING_DIR = (
    Path(os.environ.get("COPAW_WORKING_DIR", "~/.copaw"))
    .expanduser()
    .resolve()
)

# Default secret directory (used when no user_id is specified)
DEFAULT_SECRET_DIR = (
    Path(os.environ.get("COPAW_SECRET_DIR", f"{DEFAULT_WORKING_DIR}.secret"))
    .expanduser()
    .resolve()
)

# Runtime state for user-specific directory
_current_user_id: str | None = None
_runtime_working_dir: Path = DEFAULT_WORKING_DIR
_runtime_secret_dir: Path = DEFAULT_SECRET_DIR


def get_working_dir(user_id: str | None = None) -> Path:
    """获取工作目录，支持用户隔离。

    Args:
        user_id: 用户标识，None 表示使用当前运行时设置

    Returns:
        工作目录路径
    """
    if user_id is None:
        return _runtime_working_dir
    return DEFAULT_WORKING_DIR / user_id


def get_secret_dir(user_id: str | None = None) -> Path:
    """获取敏感信息目录，支持用户隔离。

    Args:
        user_id: 用户标识，None 表示使用当前运行时设置

    Returns:
        敏感信息目录路径
    """
    if user_id is None:
        return _runtime_secret_dir
    return DEFAULT_SECRET_DIR / user_id


def set_current_user(user_id: str | None) -> None:
    """设置当前用户标识。

    Args:
        user_id: 用户标识，None 表示使用默认目录
    """
    global _current_user_id, _runtime_working_dir, _runtime_secret_dir
    _current_user_id = user_id
    if user_id:
        _runtime_working_dir = DEFAULT_WORKING_DIR / user_id
        _runtime_secret_dir = DEFAULT_SECRET_DIR / user_id
    else:
        _runtime_working_dir = DEFAULT_WORKING_DIR
        _runtime_secret_dir = DEFAULT_SECRET_DIR


def get_runtime_working_dir() -> Path:
    """获取运行时工作目录（考虑 set_current_user 后的值）。"""
    return _runtime_working_dir


def get_runtime_secret_dir() -> Path:
    """获取运行时敏感目录（考虑 set_current_user 后的值）。"""
    return _runtime_secret_dir


def get_current_user_id() -> str | None:
    """获取当前用户标识。"""
    return _current_user_id


# Backward compatibility aliases - these now point to runtime values
WORKING_DIR = DEFAULT_WORKING_DIR
SECRET_DIR = DEFAULT_SECRET_DIR

JOBS_FILE = os.environ.get("COPAW_JOBS_FILE", "jobs.json")

CHATS_FILE = os.environ.get("COPAW_CHATS_FILE", "chats.json")

CONFIG_FILE = os.environ.get("COPAW_CONFIG_FILE", "config.json")

HEARTBEAT_FILE = os.environ.get("COPAW_HEARTBEAT_FILE", "HEARTBEAT.md")
HEARTBEAT_DEFAULT_EVERY = "6h"
HEARTBEAT_DEFAULT_TARGET = "main"
HEARTBEAT_TARGET_LAST = "last"

# Env key for app log level (used by CLI and app load for reload child).
LOG_LEVEL_ENV = "COPAW_LOG_LEVEL"

# Env to indicate running inside a container (e.g. Docker). Set to 1/true/yes.
RUNNING_IN_CONTAINER = os.environ.get("COPAW_RUNNING_IN_CONTAINER", "false")

# Timeout in seconds for checking if a provider is reachable.
# TODO: add a module to parse and validate env vars
try:
    MODEL_PROVIDER_CHECK_TIMEOUT = float(
        os.environ.get("COPAW_MODEL_PROVIDER_CHECK_TIMEOUT", "5.0"),
    )
except (TypeError, ValueError):
    MODEL_PROVIDER_CHECK_TIMEOUT = 5.0

# Playwright: use system Chromium when set (e.g. in Docker).
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH_ENV = "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"

# When True, expose /docs, /redoc, /openapi.json
# (dev only; keep False in prod).
DOCS_ENABLED = os.environ.get("COPAW_OPENAPI_DOCS", "false").lower() in (
    "true",
    "1",
    "yes",
)

# Skills directories
# Active skills directory (activated skills that agents use)
ACTIVE_SKILLS_DIR = get_runtime_working_dir() / "active_skills"
# Customized skills directory (user-created skills)
CUSTOMIZED_SKILLS_DIR = get_runtime_working_dir() / "customized_skills"

# Memory directory
MEMORY_DIR = get_runtime_working_dir() / "memory"

# Custom channel modules (installed via `copaw channels install`); manager
# loads BaseChannel subclasses from here.
CUSTOM_CHANNELS_DIR = get_runtime_working_dir() / "custom_channels"

# Local models directory
MODELS_DIR = get_runtime_working_dir() / "models"

# Memory compaction configuration
MEMORY_COMPACT_KEEP_RECENT = int(
    os.environ.get("COPAW_MEMORY_COMPACT_KEEP_RECENT", "3"),
)

MEMORY_COMPACT_RATIO = float(
    os.environ.get("COPAW_MEMORY_COMPACT_RATIO", "0.7"),
)

DASHSCOPE_BASE_URL = os.environ.get(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# CORS configuration — comma-separated list of allowed origins for dev mode.
# Example: COPAW_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
# When unset, CORS middleware is not applied.
CORS_ORIGINS = os.environ.get("COPAW_CORS_ORIGINS", "").strip()
