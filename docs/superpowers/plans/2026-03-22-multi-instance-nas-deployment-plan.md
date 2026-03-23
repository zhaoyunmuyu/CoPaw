# CoPaw 多实例容器化部署实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 CoPaw 改造为支持多实例容器化部署，使用 NAS 统一存储和 Redis 分布式锁

**Architecture:** 基于设计文档 `docs/superpowers/specs/2026-03-22-multi-instance-nas-deployment-design.md`，核心包括：1) Redis 分布式锁模块（含续期机制） 2) NAS 文件锁模块 3) Redis 存储临时数据（console_push, download_tasks） 4) CronManager 改造（锁、续期、状态持久化） 5) 健康检查端点 6) 部署配置

**Tech Stack:** Python, FastAPI, Redis, portalocker, asyncio, Docker Compose

---

## 文件结构

### 新增文件

| 文件 | 职责 |
|-----|------|
| `src/copaw/lock/__init__.py` | 锁模块导出 |
| `src/copaw/lock/redis_lock.py` | Redis 分布式锁实现，含 Lua 脚本、LockRenewalTask |
| `src/copaw/lock/file_lock.py` | NAS 文件锁实现，使用 portalocker |
| `src/copaw/store/redis_store.py` | Redis 版 console_push/download 存储 |
| `tests/lock/test_redis_lock.py` | Redis 锁单元测试 |
| `tests/lock/test_file_lock.py` | 文件锁单元测试 |
| `tests/store/test_redis_store.py` | Redis 存储单元测试 |

### 修改文件

| 文件 | 改造内容 |
|-----|---------|
| `pyproject.toml` | 添加 redis, portalocker 依赖 |
| `src/copaw/config/config.py` | 新增 RedisConfig、CronLockConfig、InstanceConfig |
| `src/copaw/constant.py` | 新增 Redis、锁相关常量，INSTANCE_ID |
| `src/copaw/app/crons/manager.py` | 添加锁获取、续期、状态持久化 |
| `src/copaw/app/crons/models.py` | 添加状态序列化方法 |
| `src/copaw/app/console_push_store.py` | 改用 Redis 存储 |
| `src/copaw/app/download_task_store.py` | 改用 Redis 存储 |
| `src/copaw/app/_app.py` | 添加 /health、/ready 端点 |
| `deploy/docker-compose.yml` | 添加 Redis，配置多实例 |
| `deploy/Dockerfile` | 添加依赖 |

---

## 前置依赖

确保以下服务可用：
- Python 3.10+
- Docker & Docker Compose
- 可访问的 NAS 挂载点
- 可访问的 Redis 服务（用于测试）

---

## Task 1: 添加依赖项

**Files:**
- Modify: `pyproject.toml`

### 背景
添加 Redis 客户端和文件锁库依赖。

### 步骤

- [ ] **Step 1: 添加依赖到 pyproject.toml**

在 `[project.dependencies]` 或 `[project.optional-dependencies]` 中添加：

```toml
[project.optional-dependencies]
multi-instance = [
    "redis>=5.0.0",
    "portalocker>=2.7.0",
]
```

或添加到主依赖：

```toml
dependencies = [
    # ... existing dependencies ...
    "redis>=5.0.0",
    "portalocker>=2.7.0",
]
```

- [ ] **Step 2: 验证依赖格式**

检查文件语法：`python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"`

Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add redis and portalocker for multi-instance support"
```

---

## Task 2: 配置模型更新

**Files:**
- Modify: `src/copaw/config/config.py`

### 背景
添加 Redis 连接、分布式锁、实例标识配置。

### 步骤

- [ ] **Step 1: 阅读现有 config.py 了解结构**

Run: `head -50 src/copaw/config/config.py`

Expected: 看到 BaseModel、ConfigDict 等 pydantic 模式

- [ ] **Step 2: 添加新配置类**

在文件末尾（ChannelConfigUnion 之前）添加：

```python
class RedisConfig(BaseModel):
    """Redis connection configuration."""
    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0)
    password: str = Field(default="")
    ssl: bool = Field(default=False)
    socket_connect_timeout: float = Field(default=5.0)
    socket_timeout: float = Field(default=5.0)


class CronLockConfig(BaseModel):
    """Distributed lock configuration for cron jobs."""
    enabled: bool = Field(default=True)
    ttl: int = Field(default=600, ge=60, description="Lock TTL in seconds")
    prefix: str = Field(default="copaw:cron:user:")
    jitter_ms: int = Field(default=2000, ge=0, description="Random delay before lock acquire")


class InstanceConfig(BaseModel):
    """Instance identification configuration."""
    id: str = Field(default="", description="Instance ID (auto-generated if empty)")
```

- [ ] **Step 3: 更新 Config 类**

找到 `class Config(BaseModel)`，添加新字段：

```python
class Config(BaseModel):
    """Root config (config.json)."""

    channels: ChannelConfig = ChannelConfig()
    mcp: MCPConfig = MCPConfig()
    last_api: LastApiConfig = LastApiConfig()
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    last_dispatch: Optional[LastDispatchConfig] = None
    show_tool_details: bool = True
    # 新增字段
    redis: RedisConfig = Field(default_factory=RedisConfig)
    cron_lock: CronLockConfig = Field(default_factory=CronLockConfig)
    instance: InstanceConfig = Field(default_factory=InstanceConfig)
```

- [ ] **Step 4: 验证配置加载**

创建测试脚本：

```python
# test_config.py
from copaw.config.config import Config, RedisConfig, CronLockConfig

config = Config()
assert config.redis.host == "localhost"
assert config.cron_lock.ttl == 600
assert config.cron_lock.jitter_ms == 2000
print("Config OK")
```

Run: `python test_config.py`

Expected: "Config OK"

- [ ] **Step 5: Cleanup 并 Commit**

```bash
rm -f test_config.py
git add src/copaw/config/config.py
git commit -m "config: add redis, cron_lock, instance configuration"
```

---

## Task 3: 常量定义更新

**Files:**
- Modify: `src/copaw/constant.py`

### 背景
添加 Redis 连接、锁、实例 ID 相关常量。

### 步骤

- [ ] **Step 1: 阅读现有 constant.py 了解结构**

Run: `head -100 src/copaw/constant.py`

Expected: 看到 DEFAULT_WORKING_DIR 等常量定义

- [ ] **Step 2: 添加 Redis 配置常量**

在文件末尾（get_customized_skills_dir 之后）添加：

```python
# ============================================================================
# Redis configuration
# ============================================================================

REDIS_HOST = os.environ.get("COPAW_REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("COPAW_REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("COPAW_REDIS_DB", "0"))
REDIS_PASSWORD = os.environ.get("COPAW_REDIS_PASSWORD", "")
REDIS_SSL = os.environ.get("COPAW_REDIS_SSL", "false").lower() in ("true", "1", "yes")

# ============================================================================
# Cron lock configuration
# ============================================================================

CRON_LOCK_ENABLED = os.environ.get("COPAW_CRON_LOCK_ENABLED", "true").lower() in ("true", "1", "yes")
CRON_LOCK_TTL = int(os.environ.get("COPAW_CRON_LOCK_TTL", "600"))
CRON_LOCK_PREFIX = os.environ.get("COPAW_CRON_LOCK_PREFIX", "copaw:cron:user:")
CRON_LOCK_JITTER_MS = int(os.environ.get("COPAW_CRON_LOCK_JITTER_MS", "2000"))

# ============================================================================
# Instance identification
# ============================================================================

import socket
import uuid as _uuid

INSTANCE_ID = os.environ.get("COPAW_INSTANCE_ID", "")
if not INSTANCE_ID:
    try:
        INSTANCE_ID = socket.gethostname()
    except Exception:
        INSTANCE_ID = str(_uuid.uuid4())[:8]
```

- [ ] **Step 3: 验证常量**

Run: `python -c "from copaw.constant import INSTANCE_ID, REDIS_HOST, CRON_LOCK_TTL; print(f'INSTANCE_ID={INSTANCE_ID}, REDIS_HOST={REDIS_HOST}, CRON_LOCK_TTL={CRON_LOCK_TTL}')"`

Expected: 看到正确的值

- [ ] **Step 4: Commit**

```bash
git add src/copaw/constant.py
git commit -m "constant: add redis, cron_lock, instance_id constants"
```

---

## Task 4: Redis 分布式锁模块

**Files:**
- Create: `src/copaw/lock/__init__.py`
- Create: `src/copaw/lock/redis_lock.py`

### 背景
实现基于 Redis 的分布式锁，含 Lua 脚本、锁续期。

### 步骤

- [ ] **Step 1: 创建锁模块目录**

Run: `mkdir -p src/copaw/lock`

- [ ] **Step 2: 创建 __init__.py**

```python
# -*- coding: utf-8 -*-
"""Lock module for multi-instance deployment."""
from __future__ import annotations

from .redis_lock import RedisLock, LockRenewalTask

__all__ = ["RedisLock", "LockRenewalTask"]
```

- [ ] **Step 3: 创建 redis_lock.py**

```python
# -*- coding: utf-8 -*-
"""Redis distributed lock implementation with renewal support."""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


# Lua scripts for atomic operations
ACQUIRE_LOCK_SCRIPT = """
if redis.call('exists', KEYS[1]) == 0 then
    redis.call('setex', KEYS[1], ARGV[2], ARGV[1])
    return 1
end
return 0
"""

RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

EXTEND_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


class LockRenewalTask:
    """Background task to renew lock TTL during long-running operations."""

    def __init__(
        self,
        redis_client: Redis,
        lock_key: str,
        lock_value: str,
        ttl: int,
        max_failed_renewals: int = 3,
    ):
        self.redis = redis_client
        self.key = lock_key
        self.value = lock_value
        self.ttl = ttl
        self.interval = ttl / 2  # Renew at half TTL
        self.max_failed_renewals = max_failed_renewals
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._failed_renewals = 0

    async def start(self) -> None:
        """Start the renewal background task."""
        self._task = asyncio.create_task(self._renew_loop())

    async def stop(self) -> None:
        """Stop the renewal background task."""
        self._stop_event.set()
        if self._task and not self._task.done():
            await self._task

    async def _renew_loop(self) -> None:
        """Main renewal loop."""
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval,
                )
                break  # Stop event received
            except asyncio.TimeoutError:
                success = await self._extend()
                if not success:
                    self._failed_renewals += 1
                    logger.warning(
                        "Lock renewal failed (%d/%d) for key=%s",
                        self._failed_renewals,
                        self.max_failed_renewals,
                        self.key,
                    )
                    if self._failed_renewals >= self.max_failed_renewals:
                        logger.error(
                            "Lock renewal failed too many times for key=%s, "
                            "lock may be lost",
                            self.key,
                        )
                        break
                else:
                    self._failed_renewals = 0

    async def _extend(self) -> bool:
        """Extend lock TTL. Returns True if successful."""
        try:
            result = await self.redis.eval(
                EXTEND_LOCK_SCRIPT,
                keys=[self.key],
                args=[self.value, self.ttl],
            )
            return result == 1
        except Exception as e:
            logger.exception("Lock renewal error: %s", e)
            return False

    def is_healthy(self) -> bool:
        """Check if renewal is healthy."""
        return self._failed_renewals < self.max_failed_renewals


class RedisLock:
    """Redis distributed lock manager."""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def acquire(
        self,
        key: str,
        value: str,
        ttl: int,
    ) -> bool:
        """Acquire a lock. Returns True if successful.

        Args:
            key: Lock key
            value: Lock value (instance identifier)
            ttl: Lock TTL in seconds
        """
        try:
            result = await self.redis.eval(
                ACQUIRE_LOCK_SCRIPT,
                keys=[key],
                args=[value, ttl],
            )
            return result == 1
        except Exception as e:
            logger.exception("Failed to acquire lock: %s", e)
            return False

    async def release(self, key: str, value: str) -> bool:
        """Release a lock. Returns True if successful.

        Args:
            key: Lock key
            value: Lock value (must match acquire value)
        """
        try:
            result = await self.redis.eval(
                RELEASE_LOCK_SCRIPT,
                keys=[key],
                args=[value],
            )
            return result == 1
        except Exception as e:
            logger.exception("Failed to release lock: %s", e)
            return False

    async def is_locked(self, key: str) -> bool:
        """Check if a key is locked."""
        try:
            exists = await self.redis.exists(key)
            return exists > 0
        except Exception as e:
            logger.exception("Failed to check lock status: %s", e)
            return False
```

- [ ] **Step 4: 验证模块可导入**

Run: `python -c "from copaw.lock import RedisLock, LockRenewalTask; print('Import OK')"`

Expected: "Import OK"（可能有依赖缺失警告，可忽略）

- [ ] **Step 5: Commit**

```bash
git add src/copaw/lock/
git commit -m "feat(lock): add redis distributed lock with renewal support"
```

---

## Task 5: NAS 文件锁模块

**Files:**
- Create: `src/copaw/lock/file_lock.py`

### 背景
实现基于 portalocker 的 NAS 文件锁，支持读写锁。

### 步骤

- [ ] **Step 1: 创建 file_lock.py**

```python
# -*- coding: utf-8 -*-
"""File lock implementation for NAS storage using portalocker."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import portalocker

logger = logging.getLogger(__name__)


def _ensure_file_exists(path: Path) -> None:
    """Ensure file exists, create if not."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


@asynccontextmanager
async def file_lock(
    path: Path,
    mode: str = "r",
) -> AsyncGenerator:
    """File lock context manager (async wrapper).

    Args:
        path: File path to lock
        mode: 'r' for shared read lock, 'w' for exclusive write lock

    Example:
        async with file_lock(path, mode="w") as f:
            data = json.load(f)
            data["key"] = value
            f.seek(0)
            json.dump(data, f)
            f.truncate()
    """
    lock_mode = portalocker.LOCK_SH if mode == "r" else portalocker.LOCK_EX
    lock_mode |= portalocker.LOCK_NB  # Non-blocking

    # Ensure file exists for write mode
    if mode == "w":
        await asyncio.to_thread(_ensure_file_exists, path)

    fd = None
    try:
        fd = await asyncio.to_thread(open, path, "r+" if mode == "w" else "r")
        await asyncio.to_thread(portalocker.lock, fd, lock_mode)
        yield fd
    except portalocker.LockException:
        # Lock not acquired
        if fd:
            await asyncio.to_thread(fd.close)
        raise
    finally:
        if fd:
            await asyncio.to_thread(portalocker.unlock, fd)
            await asyncio.to_thread(fd.close)


async def read_json_locked(path: Path) -> dict:
    """Read JSON file with shared lock."""
    async with file_lock(path, mode="r") as f:
        import json
        content = await asyncio.to_thread(f.read)
        return json.loads(content) if content else {}


async def write_json_locked(path: Path, data: dict) -> None:
    """Write JSON file with exclusive lock (atomic)."""
    import json
    import tempfile

    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    # Write to temp file first, then atomic move
    async with file_lock(path, mode="w") as f:
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json_str, encoding="utf-8")
        tmp_path.replace(path)
```

- [ ] **Step 2: 更新 __init__.py**

编辑 `src/copaw/lock/__init__.py`：

```python
# -*- coding: utf-8 -*-
"""Lock module for multi-instance deployment."""
from __future__ import annotations

from .redis_lock import RedisLock, LockRenewalTask
from .file_lock import file_lock, read_json_locked, write_json_locked

__all__ = [
    "RedisLock",
    "LockRenewalTask",
    "file_lock",
    "read_json_locked",
    "write_json_locked",
]
```

- [ ] **Step 3: 验证模块可导入**

Run: `python -c "from copaw.lock import file_lock, read_json_locked; print('Import OK')"`

Expected: "Import OK"

- [ ] **Step 4: Commit**

```bash
git add src/copaw/lock/
git commit -m "feat(lock): add NAS file lock using portalocker"
```

---

## Task 6: Redis 存储模块（临时数据）

**Files:**
- Create: `src/copaw/store/__init__.py`
- Create: `src/copaw/store/redis_store.py`

### 背景
将 console_push_store 和 download_task_store 从内存改为 Redis 存储。

### 步骤

- [ ] **Step 1: 创建 store 目录**

Run: `mkdir -p src/copaw/store`

- [ ] **Step 2: 创建 __init__.py**

```python
# -*- coding: utf-8 -*-
"""Redis store module for temporary data."""
from __future__ import annotations

from .redis_store import ConsolePushStore, DownloadTaskStore

__all__ = ["ConsolePushStore", "DownloadTaskStore"]
```

- [ ] **Step 3: 创建 redis_store.py**

```python
# -*- coding: utf-8 -*-
"""Redis-based stores for temporary data with TTL."""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

DEFAULT_PUSH_TTL = 60  # 60 seconds for console push messages
DEFAULT_DOWNLOAD_TTL = 3600  # 1 hour for download tasks


class ConsolePushStore:
    """Redis-based store for console push messages."""

    def __init__(self, redis_client: Redis, ttl: int = DEFAULT_PUSH_TTL):
        self.redis = redis_client
        self.ttl = ttl

    def _key(self, user_id: str) -> str:
        return f"copaw:push:{user_id}"

    async def append(
        self,
        user_id: Optional[str],
        session_id: str,
        text: str,
    ) -> None:
        """Append a message for a specific user."""
        if not session_id or not text:
            return

        uid = user_id or "default"
        key = self._key(uid)

        message = {
            "id": str(uuid.uuid4()),
            "text": text,
            "ts": time.time(),
            "session_id": session_id,
        }

        # Add to list and trim to max size
        await self.redis.lpush(key, json.dumps(message))
        await self.redis.ltrim(key, 0, 499)  # Keep max 500 messages
        await self.redis.expire(key, self.ttl)

    async def take(
        self,
        user_id: Optional[str],
        session_id: str,
    ) -> List[Dict[str, Any]]:
        """Return and remove all messages for the user and session."""
        if not session_id:
            return []

        uid = user_id or "default"
        key = self._key(uid)

        # Get all messages
        raw_messages = await self.redis.lrange(key, 0, -1)
        if not raw_messages:
            return []

        messages = [json.loads(m) for m in raw_messages]

        # Filter by session_id
        to_return = [m for m in messages if m.get("session_id") == session_id]
        to_keep = [m for m in messages if m.get("session_id") != session_id]

        # Update list (remove returned messages)
        if to_return:
            await self.redis.delete(key)
            if to_keep:
                await self.redis.lpush(key, *[json.dumps(m) for m in to_keep])
                await self.redis.expire(key, self.ttl)

        return [{"id": m["id"], "text": m["text"]} for m in to_return]

    async def take_all(
        self,
        user_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Return and remove all messages for the user."""
        uid = user_id or "default"
        key = self._key(uid)

        raw_messages = await self.redis.lrange(key, 0, -1)
        if raw_messages:
            await self.redis.delete(key)

        messages = [json.loads(m) for m in raw_messages]
        return [{"id": m["id"], "text": m["text"]} for m in messages]

    async def get_recent(
        self,
        user_id: Optional[str],
        max_age_seconds: int = DEFAULT_PUSH_TTL,
    ) -> List[Dict[str, Any]]:
        """Return and remove recent messages for the user."""
        uid = user_id or "default"
        key = self._key(uid)
        cutoff = time.time() - max_age_seconds

        raw_messages = await self.redis.lrange(key, 0, -1)
        if not raw_messages:
            return []

        messages = [json.loads(m) for m in raw_messages]

        # Filter by age (consume-once semantics)
        to_return = [m for m in messages if m["ts"] >= cutoff]

        # Remove all returned messages from store
        if to_return:
            await self.redis.delete(key)

        return [{"id": m["id"], "text": m["text"]} for m in to_return]


class DownloadTaskStore:
    """Redis-based store for download tasks."""

    def __init__(self, redis_client: Redis, ttl: int = DEFAULT_DOWNLOAD_TTL):
        self.redis = redis_client
        self.ttl = ttl

    def _key(self, task_id: str) -> str:
        return f"copaw:download:task:{task_id}"

    def _index_key(self, backend: Optional[str] = None) -> str:
        if backend:
            return f"copaw:download:index:{backend}"
        return "copaw:download:index:all"

    async def save(self, task: Dict[str, Any]) -> None:
        """Save or update a task."""
        task_id = task["task_id"]
        key = self._key(task_id)
        backend = task.get("backend")

        await self.redis.setex(key, self.ttl, json.dumps(task))

        # Add to index
        await self.redis.sadd(self._index_key(), task_id)
        if backend:
            await self.redis.sadd(self._index_key(backend), task_id)

    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        key = self._key(task_id)
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def get_all(
        self,
        backend: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get all tasks, optionally filtered by backend."""
        task_ids = await self.redis.smembers(self._index_key(backend))
        if not task_ids:
            return []

        tasks = []
        for tid in task_ids:
            task = await self.get(tid)
            if task:
                tasks.append(task)

        return tasks

    async def delete(self, task_id: str) -> bool:
        """Delete a task."""
        task = await self.get(task_id)
        if not task:
            return False

        key = self._key(task_id)
        backend = task.get("backend")

        await self.redis.delete(key)
        await self.redis.srem(self._index_key(), task_id)
        if backend:
            await self.redis.srem(self._index_key(backend), task_id)

        return True
```

- [ ] **Step 4: 验证模块可导入**

Run: `python -c "from copaw.store import ConsolePushStore, DownloadTaskStore; print('Import OK')"`

Expected: "Import OK"

- [ ] **Step 5: Commit**

```bash
git add src/copaw/store/
git commit -m "feat(store): add redis-based stores for temp data"
```

---

## Task 7: CronManager 改造 - Redis 集成

**Files:**
- Modify: `src/copaw/app/crons/manager.py`

### 背景
改造 CronManager 以支持：1) Redis 连接 2) 分布式锁 3) 锁续期 4) 防惊群 5) 状态持久化

### 步骤

- [ ] **Step 1: 阅读现有 manager.py 了解结构**

Run: `head -100 src/copaw/app/crons/manager.py`

Expected: 看到 CronManager 类、APScheduler 使用

- [ ] **Step 2: 添加导入**

在文件顶部添加：

```python
import random
from pathlib import Path

from redis.asyncio import from_url as redis_from_url

from ...lock import RedisLock, LockRenewalTask, read_json_locked, write_json_locked
from ...constant import (
    CRON_LOCK_ENABLED,
    CRON_LOCK_TTL,
    CRON_LOCK_PREFIX,
    CRON_LOCK_JITTER_MS,
    INSTANCE_ID,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_PASSWORD,
    REDIS_SSL,
)
```

- [ ] **Step 3: 更新 CronManager.__init__**

在 `__init__` 中添加 Redis 初始化：

```python
def __init__(self, *, runner: Any, channel_manager: Any, timezone: str = "Asia/Shanghai"):
    # ... existing code ...
    self._scheduler = AsyncIOScheduler(timezone=timezone)
    self._executor = CronExecutor(runner=runner, channel_manager=channel_manager)
    self._lock = asyncio.Lock()
    self._states: Dict[str, Dict[str, CronJobState]] = {}
    self._rt: Dict[str, Dict[str, _Runtime]] = {}
    self._user_jobs: Dict[str, Set[str]] = {}
    self._started = False
    self._scan_interval_minutes = int(os.environ.get("COPAW_CRON_USER_SCAN_MINUTES", "5"))
    self._scan_job_id = "_cron_user_scan"

    # 新增: Redis 客户端和锁
    self._redis: Optional[Redis] = None
    self._redis_lock: Optional[RedisLock] = None
    self._init_redis()

def _init_redis(self) -> None:
    """Initialize Redis connection and lock."""
    if not CRON_LOCK_ENABLED:
        logger.info("Cron lock is disabled")
        return

    try:
        redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        if REDIS_SSL:
            redis_url = redis_url.replace("redis://", "rediss://")

        self._redis = redis_from_url(
            redis_url,
            password=REDIS_PASSWORD or None,
            socket_connect_timeout=5.0,
            socket_timeout=5.0,
        )
        self._redis_lock = RedisLock(self._redis)
        logger.info("Redis initialized for cron locking")
    except Exception as e:
        logger.exception("Failed to initialize Redis: %s", e)
        self._redis = None
        self._redis_lock = None
```

- [ ] **Step 4: 添加状态文件路径方法**

```python
def _get_state_path(self, user_id: str) -> Path:
    """Get path to user's jobs_state.json."""
    from ...constant import get_working_dir
    return get_working_dir(user_id) / "jobs_state.json"

async def _load_user_states(self, user_id: str) -> Dict[str, CronJobState]:
    """Load user job states from NAS."""
    path = self._get_state_path(user_id)
    try:
        data = await read_json_locked(path)
        return {k: CronJobState(**v) for k, v in data.items()}
    except Exception as e:
        logger.warning("Failed to load states for user=%s: %s", user_id, e)
        return {}

async def _save_user_states(self, user_id: str) -> None:
    """Save user job states to NAS."""
    path = self._get_state_path(user_id)
    states = self._states.get(user_id, {})
    try:
        data = {k: v.model_dump() for k, v in states.items()}
        await write_json_locked(path, data)
    except Exception as e:
        logger.exception("Failed to save states for user=%s: %s", user_id, e)
```

- [ ] **Step 5: 改造 _scheduled_callback**

替换原有的 `_scheduled_callback`：

```python
async def _scheduled_callback(self, user_id: str, job_id: str) -> None:
    """Callback when a job is triggered by scheduler with distributed locking."""
    # 1. Random jitter to prevent thundering herd
    if CRON_LOCK_JITTER_MS > 0:
        jitter_ms = random.randint(0, CRON_LOCK_JITTER_MS)
        await asyncio.sleep(jitter_ms / 1000)

    # 2. Check Redis availability
    if CRON_LOCK_ENABLED:
        if not self._redis or not self._redis_lock:
            logger.error("Redis not available, skipping job for user=%s", user_id)
            return

        # 3. Acquire user-level lock
        lock_key = f"{CRON_LOCK_PREFIX}{user_id}"
        lock_value = f"{INSTANCE_ID}:{time.time()}"
        ttl = CRON_LOCK_TTL

        if not await self._redis_lock.acquire(lock_key, lock_value, ttl=ttl):
            logger.debug("Lock held by another instance for user=%s", user_id)
            return

        renewal: Optional[LockRenewalTask] = None
        try:
            # 4. Start lock renewal
            renewal = LockRenewalTask(self._redis, lock_key, lock_value, ttl)
            await renewal.start()

            # 5. Load states and execute
            await self._execute_with_lock(user_id)
        finally:
            # 6. Stop renewal and release lock
            if renewal:
                await renewal.stop()
            await self._redis_lock.release(lock_key, lock_value)
    else:
        # Lock disabled, execute directly
        await self._execute_with_lock(user_id)

async def _execute_with_lock(self, user_id: str) -> None:
    """Execute all pending jobs for a user (while holding lock)."""
    # Set request context
    from ...constant import set_request_user_id, reset_request_user_id

    token = set_request_user_id(user_id)
    try:
        # Load fresh states
        self._states[user_id] = await self._load_user_states(user_id)

        # Get user jobs
        if user_id not in self._user_jobs:
            await self.start_user(user_id)

        # Execute pending jobs
        for job_id in self._user_jobs.get(user_id, set()):
            job = await self._get_repo_for_user(user_id).get_job(job_id)
            if job:
                await self._execute_once(user_id, job)

        # Save states
        await self._save_user_states(user_id)
    finally:
        reset_request_user_id(token)
```

- [ ] **Step 6: 添加 stop 方法关闭 Redis**

在 `stop` 方法中添加：

```python
async def stop(self) -> None:
    """Stop the scheduler."""
    async with self._lock:
        if not self._started:
            return
        if self._scheduler.get_job(self._scan_job_id):
            self._scheduler.remove_job(self._scan_job_id)
        self._scheduler.shutdown(wait=False)
        self._started = False

        # Close Redis connection
        if self._redis:
            await self._redis.close()
            self._redis = None
```

- [ ] **Step 7: Commit**

```bash
git add src/copaw/app/crons/manager.py
git commit -m "feat(cron): add redis distributed locking with renewal and state persistence"
```

---

## Task 8: console_push_store 改用 Redis

**Files:**
- Modify: `src/copaw/app/console_push_store.py`

### 背景
将 console_push_store 从内存字典改为 Redis 存储。

### 步骤

- [ ] **Step 1: 备份原文件**

Run: `cp src/copaw/app/console_push_store.py src/copaw/app/console_push_store.py.bak`

- [ ] **Step 2: 重写文件**

```python
# -*- coding: utf-8 -*-
"""Redis-based store for console channel push messages.

Replaces in-memory storage with Redis for multi-instance support.
Messages have a 60-second TTL and are consumed on read.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis

from ..store.redis_store import ConsolePushStore as _ConsolePushStore
from ..constant import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_PASSWORD,
    REDIS_SSL,
)

logger = logging.getLogger(__name__)

# Global Redis client (initialized on first use)
_redis_client: Optional[Redis] = None
_store: Optional[_ConsolePushStore] = None
_MAX_AGE_SECONDS = 60


def _get_store() -> _ConsolePushStore:
    """Get or create the global store instance."""
    global _redis_client, _store

    if _store is None:
        redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        if REDIS_SSL:
            redis_url = redis_url.replace("redis://", "rediss://")

        _redis_client = Redis.from_url(
            redis_url,
            password=REDIS_PASSWORD or None,
            decode_responses=False,  # We'll handle JSON encoding
        )
        _store = _ConsolePushStore(_redis_client, ttl=_MAX_AGE_SECONDS)

    return _store


async def append(user_id: str | None, session_id: str, text: str) -> None:
    """Append a message for a specific user."""
    store = _get_store()
    await store.append(user_id, session_id, text)


async def take(user_id: str | None, session_id: str) -> List[Dict[str, Any]]:
    """Return and remove all messages for the user and session."""
    store = _get_store()
    return await store.take(user_id, session_id)


async def take_all(user_id: str | None = None) -> List[Dict[str, Any]]:
    """Return and remove all messages for the user."""
    store = _get_store()
    return await store.take_all(user_id)


async def get_recent(
    user_id: str | None = None,
    max_age_seconds: int = _MAX_AGE_SECONDS,
) -> List[Dict[str, Any]]:
    """Return and remove recent messages for the user."""
    store = _get_store()
    return await store.get_recent(user_id, max_age_seconds)


def _strip_ts(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Strip timestamp from messages for backward compatibility."""
    return [{"id": m["id"], "text": m["text"]} for m in msgs]
```

- [ ] **Step 3: Commit**

```bash
git add src/copaw/app/console_push_store.py
git commit -m "refactor(console): use redis storage for push messages"
```

---

## Task 9: download_task_store 改用 Redis

**Files:**
- Modify: `src/copaw/app/download_task_store.py`

### 背景
将 download_task_store 从内存字典改为 Redis 存储。

### 步骤

- [ ] **Step 1: 备份原文件**

Run: `cp src/copaw/app/download_task_store.py src/copaw/app/download_task_store.py.bak`

- [ ] **Step 2: 创建模型文件**

由于原文件有模型定义，需要首先创建模型文件：

Create: `src/copaw/app/download_task_store_models.py`

```python
# -*- coding: utf-8 -*-
"""Models for download task store."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DownloadTaskStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    filename: Optional[str] = None
    backend: str
    source: str
    status: DownloadTaskStatus = DownloadTaskStatus.PENDING
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
```

- [ ] **Step 3: 重写主文件**

备份并替换 `src/copaw/app/download_task_store.py`：
            decode_responses=False,
        )
        _store = _DownloadTaskStore(_redis_client)

    return _store


def _task_to_dict(task: DownloadTask) -> Dict[str, Any]:
    """Convert DownloadTask to dict."""
    return task.model_dump(mode="json")


def _dict_to_task(data: Dict[str, Any]) -> DownloadTask:
    """Convert dict to DownloadTask."""
    return DownloadTask(**data)


async def create_task(
    repo_id: str,
    filename: Optional[str],
    backend: str,
    source: str,
) -> DownloadTask:
    """Create a new pending download task."""
    store = _get_store()

    task = DownloadTask(
        repo_id=repo_id,
        filename=filename,
        backend=backend,
        source=source,
    )

    await store.save(_task_to_dict(task))
    return task


async def get_tasks(backend: Optional[str] = None) -> List[DownloadTask]:
    """Return all tasks, optionally filtered by backend."""
    store = _get_store()
    tasks = await store.get_all(backend)
    return [_dict_to_task(t) for t in tasks]


async def get_task(task_id: str) -> Optional[DownloadTask]:
    """Return a specific task by ID."""
    store = _get_store()
    task = await store.get(task_id)
    return _dict_to_task(task) if task else None


async def update_status(
    task_id: str,
    status: DownloadTaskStatus,
    *,
    error: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> None:
    """Update the status of a task."""
    store = _get_store()

    task = await store.get(task_id)
    if not task:
        return

    task["status"] = status
    task["updated_at"] = __import__("time").time()
    if error is not None:
        task["error"] = error
    if result is not None:
        task["result"] = result

    await store.save(task)


async def cancel_task(task_id: str) -> bool:
    """Cancel a pending or downloading task."""
    store = _get_store()

    task = await store.get(task_id)
    if not task:
        return False

    status = task.get("status")
    if status not in (DownloadTaskStatus.PENDING, DownloadTaskStatus.DOWNLOADING):
        return False

    task["status"] = DownloadTaskStatus.CANCELLED
    task["updated_at"] = __import__("time").time()
    await store.save(task)
    return True


async def clear_completed(backend: Optional[str] = None) -> None:
    """Remove tasks in a terminal state."""
    store = _get_store()

    tasks = await store.get_all(backend)
    terminal_statuses = {
        DownloadTaskStatus.COMPLETED,
        DownloadTaskStatus.FAILED,
        DownloadTaskStatus.CANCELLED,
    }

    for task in tasks:
        if task.get("status") in terminal_statuses:
            await store.delete(task["task_id"])
```

- [ ] **Step 4: Commit**

```bash
git add src/copaw/app/download_task_store.py
git add src/copaw/app/download_task_store_models.py
git commit -m "refactor(download): use redis storage for download tasks"
```

- [ ] **Step 5: 清理备份文件（可选）**

确认新实现正常工作后，删除备份：

```bash
rm src/copaw/app/download_task_store.py.bak
```

---

## Task 10: 添加健康检查端点

**Files:**
- Modify: `src/copaw/app/_app.py`

### 背景
添加 `/health` 和 `/ready` 端点供负载均衡器和 Kubernetes 使用。

### 步骤

- [ ] **Step 1: 阅读 _app.py 了解 FastAPI 应用结构**

Run: `grep -n "app = FastAPI\|@app.get" src/copaw/app/_app.py | head -20`

Expected: 看到 FastAPI 应用创建和路由注册

- [ ] **Step 2: 添加健康检查函数**

在文件末尾（或合适位置）添加：

```python
# ============================================================================
# Health check endpoints
# ============================================================================

async def check_redis() -> bool:
    """Check Redis connection health."""
    try:
        from redis.asyncio import from_url
        from copaw.constant import REDIS_HOST, REDIS_PORT, REDIS_DB

        redis = from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
        await redis.ping()
        await redis.close()
        return True
    except Exception:
        return False


def check_nas() -> bool:
    """Check NAS write access."""
    try:
        from copaw.constant import DEFAULT_WORKING_DIR

        test_file = DEFAULT_WORKING_DIR / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        return True
    except Exception:
        return False


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    from fastapi.responses import JSONResponse
    from copaw.constant import INSTANCE_ID

    redis_ok = await check_redis()
    nas_ok = check_nas()

    status = "healthy" if redis_ok and nas_ok else "unhealthy"
    code = 200 if status == "healthy" else 503

    return JSONResponse(
        status_code=code,
        content={
            "status": status,
            "redis": "connected" if redis_ok else "disconnected",
            "nas": "writable" if nas_ok else "not_writable",
            "instance_id": INSTANCE_ID,
        },
    )


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Kubernetes."""
    from fastapi.responses import JSONResponse

    redis_ok = await check_redis()
    nas_ok = check_nas()

    if not redis_ok:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "reason": "Redis not ready"},
        )
    if not nas_ok:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "reason": "NAS not ready"},
        )

    return JSONResponse(content={"ready": True})
```

- [ ] **Step 3: 验证端点可访问**

由于需要运行应用才能测试，先检查语法：

Run: `python -m py_compile src/copaw/app/_app.py`

Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add src/copaw/app/_app.py
git commit -m "feat(app): add /health and /ready endpoints"
```

---

## Task 11: Dockerfile 更新

**Files:**
- Modify: `deploy/Dockerfile`

### 背景
添加依赖和实例 ID 环境变量支持。

### 步骤

- [ ] **Step 1: 检查当前 Dockerfile**

Run: `head -30 deploy/Dockerfile`

- [ ] **Step 2: 修改安装依赖步骤**

找到 pip install 步骤，确保安装新依赖。可能需要修改：

```dockerfile
# 在 pip install . 之前，确保依赖已安装
# 如果 pyproject.toml 已更新，这会自动处理
RUN pip install --no-cache-dir .
```

如果依赖在 optional-dependencies 中，改为：

```dockerfile
RUN pip install --no-cache-dir ".[multi-instance]"
```

- [ ] **Step 3: 添加健康检查**

在 Dockerfile 末尾添加：

```dockerfile
# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8088/health || exit 1
```

确保安装 curl：

```dockerfile
# 在 apt-get install 中添加 curl
RUN apt-get update && apt-get install -y --fix-missing \
    curl \
    # ... other packages ...
```

- [ ] **Step 4: Commit**

```bash
git add deploy/Dockerfile
git commit -m "build(docker): add curl and healthcheck, support multi-instance deps"
```

---

## Task 12: Docker Compose 配置

**Files:**
- Create: `deploy/docker-compose.multi.yml`

### 背景
创建多实例部署配置，包含 Redis 和多个 CoPaw 实例。

### 步骤

- [ ] **Step 1: 创建 docker-compose.multi.yml**

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    networks:
      - copaw-net

  copaw:
    image: copaw:latest
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    restart: unless-stopped
    deploy:
      replicas: 5
      update_config:
        parallelism: 1
        delay: 10s
    environment:
      - COPAW_WORKING_DIR=/nas/copaw
      - COPAW_SECRET_DIR=/nas/copaw/.secret
      - COPAW_REDIS_HOST=redis
      - COPAW_REDIS_PORT=6379
      - COPAW_REDIS_DB=0
      - COPAW_CRON_LOCK_ENABLED=true
      - COPAW_CRON_LOCK_TTL=600
      - COPAW_CRON_LOCK_JITTER_MS=2000
      # INSTANCE_ID auto-generated from hostname
    volumes:
      - /mnt/nas/copaw:/nas/copaw:rw
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - copaw-net
    # Port not exposed directly, use load balancer

  # Optional: Nginx load balancer
  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "8088:8088"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - copaw
    networks:
      - copaw-net

volumes:
  redis_data:

networks:
  copaw-net:
    driver: bridge
```

- [ ] **Step 2: 创建 Nginx 配置**

Create: `deploy/nginx.conf`

```nginx
events {
    worker_connections 1024;
}

http {
    upstream copaw {
        least_conn;  # Load balance to least connections
        server copaw:8088;
    }

    server {
        listen 8088;

        location / {
            proxy_pass http://copaw;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /health {
            proxy_pass http://copaw/health;
            # Health check endpoint for load balancer
        }
    }
}
```

- [ ] **Step 3: 创建环境变量模板**

Create: `deploy/.env.multi.example`

```bash
# CoPaw Multi-Instance Configuration

# NAS Configuration
COPAW_WORKING_DIR=/nas/copaw
COPAW_SECRET_DIR=/nas/copaw/.secret
NAS_MOUNT_POINT=/mnt/nas/copaw

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Cron Lock Configuration
COPAW_CRON_LOCK_ENABLED=true
COPAW_CRON_LOCK_TTL=600
COPAW_CRON_LOCK_JITTER_MS=2000

# Number of instances
COPAW_REPLICAS=5
```

- [ ] **Step 4: Commit**

```bash
git add deploy/docker-compose.multi.yml deploy/nginx.conf deploy/.env.multi.example
git commit -m "deploy: add multi-instance docker compose configuration"
```

---

## Task 12a: Redis 锁单元测试

**Files:**
- Create: `tests/lock/test_redis_lock.py`

### 步骤

- [ ] **Step 1: 创建测试目录和文件**

```bash
mkdir -p tests/lock
touch tests/lock/__init__.py
```

- [ ] **Step 2: 编写 Redis 锁测试**

```python
# -*- coding: utf-8 -*-
"""Tests for Redis distributed lock."""
import asyncio
import pytest
from redis.asyncio import from_url

from copaw.lock import RedisLock, LockRenewalTask


@pytest.fixture
async def redis_client():
    """Create Redis client for tests."""
    from copaw.constant import REDIS_HOST, REDIS_PORT, REDIS_DB

    client = from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    yield client
    await client.close()


@pytest.fixture
async def lock_manager(redis_client):
    """Create lock manager."""
    return RedisLock(redis_client)


class TestRedisLock:
    """Test Redis distributed lock."""

    async def test_acquire_release(self, lock_manager, redis_client):
        """Test basic acquire and release."""
        key = "test:lock:1"
        value = "instance-1"

        # Acquire
        acquired = await lock_manager.acquire(key, value, ttl=60)
        assert acquired is True

        # Verify lock exists
        exists = await redis_client.exists(key)
        assert exists == 1

        # Release
        released = await lock_manager.release(key, value)
        assert released is True

        # Verify lock gone
        exists = await redis_client.exists(key)
        assert exists == 0

    async def test_acquire_already_locked(self, lock_manager):
        """Test acquire when already locked."""
        key = "test:lock:2"

        # First acquire
        acquired = await lock_manager.acquire(key, "instance-1", ttl=60)
        assert acquired is True

        # Second acquire should fail
        acquired = await lock_manager.acquire(key, "instance-2", ttl=60)
        assert acquired is False

    async def test_release_wrong_value(self, lock_manager):
        """Test release with wrong value fails."""
        key = "test:lock:3"

        await lock_manager.acquire(key, "instance-1", ttl=60)

        # Release with wrong value
        released = await lock_manager.release(key, "instance-2")
        assert released is False


class TestLockRenewal:
    """Test lock renewal task."""

    async def test_renewal_extends_ttl(self, redis_client):
        """Test that renewal extends lock TTL."""
        key = "test:renew:1"
        value = "instance-1"

        # Create lock
        await redis_client.setex(key, 10, value)

        # Start renewal
        renewal = LockRenewalTask(redis_client, key, value, ttl=10)
        await renewal.start()

        # Wait a bit
        await asyncio.sleep(3)

        # Check TTL is still high (renewed)
        ttl = await redis_client.ttl(key)
        assert ttl > 5  # Should be renewed back to near 10

        # Stop renewal
        await renewal.stop()

        # Clean up
        await redis_client.delete(key)

    async def test_renewal_detects_lock_loss(self, redis_client):
        """Test renewal detects when lock is lost."""
        key = "test:renew:2"
        value = "instance-1"

        # Create lock
        await redis_client.setex(key, 60, value)

        # Start renewal with very short TTL for testing
        renewal = LockRenewalTask(
            redis_client, key, value, ttl=5, max_failed_renewals=1
        )
        await renewal.start()

        # Delete the lock externally (simulating loss)
        await redis_client.delete(key)

        # Wait for renewal to fail
        await asyncio.sleep(3)

        # Check not healthy
        assert not renewal.is_healthy()

        # Stop
        await renewal.stop()
```

- [ ] **Step 3: Commit**

```bash
git add tests/lock/
git commit -m "test(lock): add redis lock and renewal tests"
```

---

## Task 12b: 文件锁单元测试

**Files:**
- Create: `tests/lock/test_file_lock.py`

### 步骤

- [ ] **Step 1: 编写文件锁测试**

```python
# -*- coding: utf-8 -*-
"""Tests for NAS file lock."""
import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from copaw.lock import file_lock, read_json_locked, write_json_locked


class TestFileLock:
    """Test NAS file locking."""

    async def test_exclusive_lock_blocks_write(self):
        """Test exclusive lock blocks other writers."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("{}")
            path = Path(f.name)

        try:
            # First lock acquired
            async with file_lock(path, mode="w"):
                # Try to acquire another lock (should fail or block)
                with pytest.raises(Exception):  # portalocker.LockException
                    async with file_lock(path, mode="w"):
                        pass
        finally:
            path.unlink(missing_ok=True)

    async def test_shared_lock_allows_readers(self):
        """Test shared lock allows multiple readers."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("{}")
            path = Path(f.name)

        try:
            # Multiple shared locks should work
            async with file_lock(path, mode="r") as f1:
                content1 = await asyncio.to_thread(f1.read)

            async with file_lock(path, mode="r") as f2:
                content2 = await asyncio.to_thread(f2.read)

            assert content1 == content2
        finally:
            path.unlink(missing_ok=True)

    async def test_write_json_locked_atomic(self):
        """Test JSON write is atomic."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"

            data = {"key": "value", "number": 42}
            await write_json_locked(path, data)

            # Verify file exists and is valid JSON
            assert path.exists()
            content = json.loads(path.read_text())
            assert content == data

    async def test_read_json_locked(self):
        """Test JSON read with lock."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            path.write_text(json.dumps({"test": "data"}))

            data = await read_json_locked(path)
            assert data == {"test": "data"}
```

- [ ] **Step 2: Commit**

```bash
git add tests/lock/test_file_lock.py
git commit -m "test(lock): add nas file lock tests"
```

---

## Task 12c: Redis 存储单元测试

**Files:**
- Create: `tests/store/test_redis_store.py`

### 步骤

- [ ] **Step 1: 创建测试目录和文件**

```bash
mkdir -p tests/store
touch tests/store/__init__.py
```

- [ ] **Step 2: 编写存储测试**

```python
# -*- coding: utf-8 -*-
"""Tests for Redis-based stores."""
import asyncio
import pytest
from redis.asyncio import from_url

from copaw.store.redis_store import ConsolePushStore, DownloadTaskStore


@pytest.fixture
async def redis_client():
    """Create Redis client for tests."""
    from copaw.constant import REDIS_HOST, REDIS_PORT, REDIS_DB

    client = from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    # Clean up test keys
    keys = await client.keys("test:*")
    if keys:
        await client.delete(*keys)
    yield client
    # Clean up
    keys = await client.keys("test:*")
    if keys:
        await client.delete(*keys)
    await client.close()


class TestConsolePushStore:
    """Test console push store."""

    async def test_append_and_take(self, redis_client):
        """Test append and take."""
        store = ConsolePushStore(redis_client, ttl=60)

        # Append messages
        await store.append("user1", "session1", "Hello")
        await store.append("user1", "session1", "World")
        await store.append("user1", "session2", "Other")

        # Take session1 messages
        msgs = await store.take("user1", "session1")
        assert len(msgs) == 2
        assert msgs[0]["text"] == "World"  # LIFO order
        assert msgs[1]["text"] == "Hello"

        # Take again - should be empty (consumed)
        msgs = await store.take("user1", "session1")
        assert len(msgs) == 0

        # Session2 still has message
        msgs = await store.take("user1", "session2")
        assert len(msgs) == 1
        assert msgs[0]["text"] == "Other"

    async def test_take_all_consumes_all(self, redis_client):
        """Test take_all consumes all messages."""
        store = ConsolePushStore(redis_client, ttl=60)

        await store.append("user1", "session1", "Msg1")
        await store.append("user1", "session2", "Msg2")

        # Take all
        msgs = await store.take_all("user1")
        assert len(msgs) == 2

        # Take again - should be empty
        msgs = await store.take_all("user1")
        assert len(msgs) == 0

    async def test_ttl_expires(self, redis_client):
        """Test messages expire after TTL."""
        store = ConsolePushStore(redis_client, ttl=1)  # 1 second TTL

        await store.append("user1", "session1", "Msg1")

        # Should exist immediately
        msgs = await store.get_recent("user1")
        assert len(msgs) == 1

        # Wait for TTL
        await asyncio.sleep(2)

        # Should be expired
        msgs = await store.get_recent("user1")
        assert len(msgs) == 0


class TestDownloadTaskStore:
    """Test download task store."""

    async def test_save_and_get(self, redis_client):
        """Test save and get task."""
        store = DownloadTaskStore(redis_client, ttl=60)

        task = {
            "task_id": "task-1",
            "repo_id": "repo/a",
            "filename": "model.bin",
            "backend": "ollama",
            "source": "huggingface",
            "status": "pending",
        }

        await store.save(task)

        retrieved = await store.get("task-1")
        assert retrieved is not None
        assert retrieved["repo_id"] == "repo/a"

    async def test_get_all_with_backend_filter(self, redis_client):
        """Test get all with backend filter."""
        store = DownloadTaskStore(redis_client, ttl=60)

        # Save tasks for different backends
        await store.save({
            "task_id": "task-1", "backend": "ollama", "repo_id": "r1"
        })
        await store.save({
            "task_id": "task-2", "backend": "ollama", "repo_id": "r2"
        })
        await store.save({
            "task_id": "task-3", "backend": "lmstudio", "repo_id": "r3"
        })

        all_tasks = await store.get_all()
        assert len(all_tasks) == 3

        ollama_tasks = await store.get_all(backend="ollama")
        assert len(ollama_tasks) == 2

    async def test_delete_task(self, redis_client):
        """Test delete task."""
        store = DownloadTaskStore(redis_client, ttl=60)

        await store.save({"task_id": "task-1", "backend": "ollama"})

        deleted = await store.delete("task-1")
        assert deleted is True

        # Verify gone
        task = await store.get("task-1")
        assert task is None
```

- [ ] **Step 3: Commit**

```bash
git add tests/store/
git commit -m "test(store): add redis store tests"
```

---

## Task 13: 最终验证和清理

**Files:**
- Run tests, cleanup backup files

### 步骤

- [ ] **Step 1: 安装依赖**

```bash
pip install -e ".[dev,multi-instance]"
```

- [ ] **Step 2: 运行单元测试**

```bash
# Test imports
python -c "from copaw.lock import RedisLock, file_lock; from copaw.store import ConsolePushStore; print('All imports OK')"

# Test config loading
python -c "from copaw.config.config import Config, RedisConfig; c = Config(); print(f'Redis host: {c.redis.host}')"
```

Expected: 无错误

- [ ] **Step 3: 检查代码风格**

```bash
pre-commit run --all-files
```

Expected: 通过或只有不相关的问题

- [ ] **Step 4: Commit 最终版本**

```bash
git commit -m "chore: final multi-instance deployment setup" || echo "Nothing to commit"
```

- [ ] **Step 5: 清理备份文件**

确认所有新实现正常工作后，删除备份文件：

```bash
rm -f src/copaw/app/console_push_store.py.bak
rm -f src/copaw/app/download_task_store.py.bak
```

---

## 实施完成

所有任务已完成，CoPaw 现在支持：

1. ✅ Redis 分布式锁（含续期机制）
2. ✅ NAS 文件锁（使用 portalocker）
3. ✅ Redis 存储临时数据
4. ✅ CronManager 锁、续期、状态持久化
5. ✅ 健康检查端点
6. ✅ 多实例 Docker Compose 配置

### 部署步骤

```bash
# 1. Build image
docker-compose -f deploy/docker-compose.multi.yml build

# 2. Start services
docker-compose -f deploy/docker-compose.multi.yml up -d

# 3. Verify
curl http://localhost:8088/health
```

### 回滚

如需回滚到单实例：

```bash
docker-compose -f deploy/docker-compose.multi.yml down
docker-compose up -d  # 使用单实例配置
```
