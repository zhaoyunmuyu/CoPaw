# Console Channel 用户隔离实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Console Channel 定时器消息的用户隔离，确保每个用户只能看到自己的消息。

**Architecture:** 将 `console_push_store` 的存储结构从扁平列表改为按用户分区的字典，所有 API 增加 `user_id` 参数。前端通过 `x-user-id` header 传递用户身份，后端使用 `"default"` 作为默认值保证向后兼容。

**Tech Stack:** Python, FastAPI, TypeScript, React

---

## 文件变更清单

### 后端文件

| 文件 | 责任 |
|------|------|
| `src/copaw/app/console_push_store.py` | 消息存储，按用户分区 |
| `src/copaw/app/channels/console/channel.py` | Console Channel，从 meta 提取 user_id |
| `src/copaw/app/routers/console.py` | API 路由，从 header 读取 user_id |
| `src/copaw/app/crons/manager.py` | 定时器错误推送，更新 append 调用 |
| `src/copaw/app/routers/local_models.py` | 模型下载通知，更新 append 调用 |

### 前端文件

| 文件 | 责任 |
|------|------|
| `console/src/api/modules/console.ts` | API 客户端，添加 x-user-id header |

---

## Task 1: 重构 console_push_store.py 存储结构

**Files:**
- Modify: `src/copaw/app/console_push_store.py`
- Test: `tests/test_console_push_store.py` (新建)

- [ ] **Step 1: 编写失败测试 - 验证按用户分区存储**

```python
import pytest
import asyncio
from copaw.app.console_push_store import append, take, take_all, get_recent


@pytest.fixture(autouse=True)
async def cleanup_store():
    """Clean up store after each test."""
    from copaw.app.console_push_store import _store, _lock
    async with _lock:
        _store.clear()
    yield
    async with _lock:
        _store.clear()


@pytest.mark.asyncio
async def test_append_with_user_id():
    """测试带 user_id 的消息存储"""
    await append("alice", "session_1", "Hello from Alice")
    messages = await take("alice", "session_1")
    assert len(messages) == 1
    assert messages[0]["text"] == "Hello from Alice"


@pytest.mark.asyncio
async def test_user_isolation():
    """测试用户隔离 - alice 看不到 bob 的消息"""
    await append("alice", "session_1", "Alice's message")
    await append("bob", "session_1", "Bob's message")

    alice_messages = await take("alice", "session_1")
    bob_messages = await take("bob", "session_1")

    assert len(alice_messages) == 1
    assert alice_messages[0]["text"] == "Alice's message"
    assert len(bob_messages) == 1
    assert bob_messages[0]["text"] == "Bob's message"


@pytest.mark.asyncio
async def test_take_all_for_user():
    """测试 take_all 返回用户所有消息"""
    await append("alice", "session_1", "Message 1")
    await append("alice", "session_2", "Message 2")
    await append("bob", "session_1", "Bob's message")

    alice_all = await take_all("alice")
    assert len(alice_all) == 2
    texts = [m["text"] for m in alice_all]
    assert "Message 1" in texts
    assert "Message 2" in texts


@pytest.mark.asyncio
async def test_get_recent_non_consuming():
    """测试 get_recent 不消费消息"""
    await append("alice", "session_1", "Recent message")

    # First call - should return message but not consume
    messages1 = await get_recent("alice", max_age_seconds=60)
    assert len(messages1) == 1

    # Second call - should still return the same message
    messages2 = await get_recent("alice", max_age_seconds=60)
    assert len(messages2) == 1


@pytest.mark.asyncio
async def test_get_recent_expires_old_messages():
    """测试 get_recent 清理过期消息"""
    import time
    from unittest.mock import patch

    now = time.time()
    with patch('time.time', return_value=now):
        await append("alice", "session_1", "Old message")

    # Simulate time passing (70 seconds later)
    with patch('time.time', return_value=now + 70):
        messages = await get_recent("alice", max_age_seconds=60)
        assert len(messages) == 0  # Message expired
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_console_push_store.py -v`
Expected: FAIL - 函数签名不匹配或函数不存在

- [ ] **Step 3: 实现按用户分区的存储结构**

修改 `src/copaw/app/console_push_store.py`：

```python
# -*- coding: utf-8 -*-
"""In-memory store for console channel push messages (e.g. cron text).

Bounded: at most _MAX_MESSAGES kept per user; messages older than _MAX_AGE_SECONDS
are dropped when reading. Frontend dedupes by id and caps its seen set.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List

# Per-user storage: {user_id: [messages]}
_store: Dict[str, List[Dict[str, Any]]] = {}
_lock = asyncio.Lock()
_MAX_AGE_SECONDS = 60
_MAX_MESSAGES = 500


async def append(user_id: str | None, session_id: str, text: str) -> None:
    """Append a message for a specific user (bounded per user)."""
    if not session_id or not text:
        return

    # Default to "default" for backward compatibility
    uid = user_id or "default"

    async with _lock:
        if uid not in _store:
            _store[uid] = []

        _store[uid].append({
            "id": str(uuid.uuid4()),
            "text": text,
            "ts": time.time(),
            "session_id": session_id,
            "user_id": uid,
        })

        # Keep only _MAX_MESSAGES per user
        if len(_store[uid]) > _MAX_MESSAGES:
            _store[uid].sort(key=lambda m: m["ts"])
            _store[uid] = _store[uid][-_MAX_MESSAGES:]


async def take(user_id: str | None, session_id: str) -> List[Dict[str, Any]]:
    """Return and remove all messages for the user and session."""
    if not session_id:
        return []

    uid = user_id or "default"

    async with _lock:
        user_messages = _store.get(uid, [])
        out = [m for m in user_messages if m.get("session_id") == session_id]
        _store[uid] = [m for m in user_messages if m.get("session_id") != session_id]
        return _strip_ts(out)


async def take_all(user_id: str | None = None) -> List[Dict[str, Any]]:
    """Return and remove all messages for the user."""
    uid = user_id or "default"

    async with _lock:
        out = _store.get(uid, [])
        _store[uid] = []
        return _strip_ts(out)


async def get_recent(
    user_id: str | None = None,
    max_age_seconds: int = _MAX_AGE_SECONDS,
) -> List[Dict[str, Any]]:
    """Return recent messages (not consumed) for the user."""
    uid = user_id or "default"
    now = time.time()
    cutoff = now - max_age_seconds

    async with _lock:
        # Clean up expired messages for this user
        user_messages = _store.get(uid, [])
        valid = [m for m in user_messages if m["ts"] >= cutoff]
        expired = [m for m in user_messages if m["ts"] < cutoff]

        if expired:
            _store[uid] = valid

        return _strip_ts(valid)


def _strip_ts(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"id": m["id"], "text": m["text"]} for m in msgs]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_console_push_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_console_push_store.py src/copaw/app/console_push_store.py
git commit -m "feat: refactor console_push_store with user isolation

- Change storage from flat list to per-user dict
- Add user_id parameter to all functions
- Default to 'default' for backward compatibility
- Maintain message bounds per user"
```

---

## Task 2: 更新 Console Channel 传递 user_id

**Files:**
- Modify: `src/copaw/app/channels/console/channel.py`

- [ ] **Step 1: 修改 send 方法**

修改 `src/copaw/app/channels/console/channel.py` 中的 `send` 方法（约第309-326行）：

```python
async def send(
    self,
    to_handle: str,
    text: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Send a text message — prints to stdout and pushes to frontend."""
    if not self.enabled:
        return
    ts = _ts()
    prefix = (meta or {}).get("bot_prefix", self.bot_prefix) or ""
    print(
        f"\n{_GREEN}{_BOLD}🤖 [{ts}] Bot → {to_handle}{_RESET}\n"
        f"{prefix}{text}\n",
    )
    sid = (meta or {}).get("session_id")
    uid = (meta or {}).get("user_id")  # Extract user_id from meta
    if sid and text.strip():
        await push_store_append(uid, sid, text.strip())  # Pass user_id
```

- [ ] **Step 2: 修改 send_content_parts 方法**

修改 `src/copaw/app/channels/console/channel.py` 中的 `send_content_parts` 方法（约第328-342行）：

```python
async def send_content_parts(
    self,
    to_handle: str,
    parts: List[OutgoingContentPart],
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Send content parts — prints to stdout and pushes to frontend store."""
    self._print_parts(parts)
    sid = (meta or {}).get("session_id")
    uid = (meta or {}).get("user_id")  # Extract user_id from meta
    if sid:
        body = self._parts_to_text(parts, meta)
        if body.strip():
            await push_store_append(uid, sid, body.strip())  # Pass user_id
```

- [ ] **Step 3: Commit**

```bash
git add src/copaw/app/channels/console/channel.py
git commit -m "feat: pass user_id from meta to push_store in console channel

- Extract user_id from meta in send() method
- Extract user_id from meta in send_content_parts() method
- Pass user_id to push_store_append()"
```

---

## Task 3: 更新其他调用点

**Files:**
- Modify: `src/copaw/app/crons/manager.py`
- Modify: `src/copaw/app/routers/local_models.py`

- [ ] **Step 1: 更新 crons/manager.py**

修改 `src/copaw/app/crons/manager.py` 第413行：

```python
# 原代码:
# asyncio.ensure_future(
#     push_store_append(session_id, error_text),
# )

# 新代码:
asyncio.ensure_future(
    push_store_append(
        job.dispatch.target.user_id,  # Add user_id
        session_id,
        error_text,
    ),
)
```

- [ ] **Step 2: 更新 local_models.py**

修改 `src/copaw/app/routers/local_models.py` 两处调用：

```python
# 第213-216行:
await push_store_append(
    None,  # Use default user
    "console",
    f"Model downloaded: {info.display_name}",
)

# 第224-227行:
await push_store_append(
    None,  # Use default user
    "console",
    f"Model download failed: {body.repo_id} — {exc}",
)
```

- [ ] **Step 3: Commit**

```bash
git add src/copaw/app/crons/manager.py src/copaw/app/routers/local_models.py
git commit -m "fix: update push_store_append calls with user_id parameter

- crons/manager.py: pass job.dispatch.target.user_id
- local_models.py: pass None for default user"
```

---

## Task 4: 更新 API 路由支持 x-user-id Header

**Files:**
- Modify: `src/copaw/app/routers/console.py`

**API 行为说明**：
- 无 `session_id` 时从 `get_recent()` 改为 `take_all()`，这是**预期行为变更**
- 原因：`ConsoleCronBubble` 使用消费性语义（消息被取走即移除），避免重复显示
- 新 API 使用 `Header(default="default", alias="x-user-id")` 支持前端传递用户ID

- [ ] **Step 1: 修改 API 路由**

修改 `src/copaw/app/routers/console.py`：

```python
# -*- coding: utf-8 -*-
"""Console API: push messages for cron text bubbles on the frontend."""

from fastapi import APIRouter, Query, Header


router = APIRouter(prefix="/console", tags=["console"])


@router.get("/push-messages")
async def get_push_messages(
    session_id: str | None = Query(None, description="Optional session id"),
    user_id: str = Header(default="default", alias="x-user-id"),
):
    """
    Return pending push messages. With user_id only: returns all messages
    for that user (consumed). With user_id and session_id: returns messages
    for that user's session (consumed).
    """
    from ..console_push_store import take, take_all

    if session_id:
        messages = await take(user_id, session_id)
    else:
        messages = await take_all(user_id)
    return {"messages": messages}
```

- [ ] **Step 2: Commit**

```bash
git add src/copaw/app/routers/console.py
git commit -m "feat: add x-user-id header support to console push-messages API

- Read user_id from x-user-id header with 'default' as default
- Use take() when session_id provided
- Use take_all() when only user_id provided
- Changed from get_recent() to take_all() for consuming semantics"
```

---

## Task 5: 更新前端 API 客户端

**Files:**
- Modify: `console/src/api/modules/console.ts`

- [ ] **Step 1: 修改 console.ts 添加 header**

修改 `console/src/api/modules/console.ts`：

```typescript
import { request } from "../request";

export interface PushMessage {
  id: string;
  text: string;
}

export const consoleApi = {
  getPushMessages: () =>
    request<{ messages: PushMessage[] }>("/console/push-messages", {
      headers: {
        "x-user-id": (window as any).currentUserId || "default",
      },
    }),
};
```

- [ ] **Step 2: Commit**

```bash
git add console/src/api/modules/console.ts
git commit -m "feat: add x-user-id header to console push-messages API call

- Use window.currentUserId as header value
- Fallback to 'default' for backward compatibility"
```

---

## Task 6: 集成测试

**Files:**
- Test: `tests/test_console_user_isolation_integration.py` (新建)

- [ ] **Step 1: 编写集成测试**

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
async def cleanup_store():
    """Clean up store after each test."""
    from copaw.app.console_push_store import _store, _lock
    async with _lock:
        _store.clear()
    yield
    async with _lock:
        _store.clear()


@pytest.mark.asyncio
async def test_cron_message_user_isolation():
    """测试定时器消息的用户隔离完整流程"""
    from copaw.app.console_push_store import append, take_all

    # 模拟定时器发送消息给 alice
    await append("alice", "session_1", "Hello Alice from cron")

    # 模拟定时器发送消息给 bob
    await append("bob", "session_1", "Hello Bob from cron")

    # Alice 只能看到自己的消息
    alice_messages = await take_all("alice")
    assert len(alice_messages) == 1
    assert alice_messages[0]["text"] == "Hello Alice from cron"

    # Bob 只能看到自己的消息
    bob_messages = await take_all("bob")
    assert len(bob_messages) == 1
    assert bob_messages[0]["text"] == "Hello Bob from cron"


@pytest.mark.asyncio
async def test_default_user_backward_compatibility():
    """测试默认用户的向后兼容性"""
    from copaw.app.console_push_store import append, take_all

    # 不指定 user_id（模拟旧代码）
    await append(None, "session_1", "Default user message")

    # 使用 "default" 获取
    messages = await take_all("default")
    assert len(messages) == 1
    assert messages[0]["text"] == "Default user message"


@pytest.mark.asyncio
async def test_console_channel_send_with_user_id():
    """测试 ConsoleChannel 正确传递 user_id"""
    from copaw.app.channels.console.channel import ConsoleChannel
    from copaw.app.console_push_store import take_all

    # Mock process handler
    mock_process = AsyncMock()

    # Create channel
    channel = ConsoleChannel(
        process=mock_process,
        enabled=True,
        bot_prefix="[BOT] ",
    )

    # Send with user_id in meta
    await channel.send(
        to_handle="user123",
        text="Test message",
        meta={"session_id": "sess_1", "user_id": "alice"},
    )

    # Verify message stored with correct user_id
    messages = await take_all("alice")
    assert len(messages) == 1
    assert messages[0]["text"] == "Test message"

    # Verify bob cannot see alice's message
    bob_messages = await take_all("bob")
    assert len(bob_messages) == 0
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/test_console_user_isolation_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_console_user_isolation_integration.py
git commit -m "test: add integration tests for console user isolation

- Test cron message isolation between users
- Test backward compatibility with default user
- Test ConsoleChannel.send() passes user_id correctly"
```

---

## Task 7: 端到端验证

- [ ] **Step 1: 启动后端服务**

```bash
cd /Users/shixiangyi/code/CoPaw
pip install -e ".[dev]"
copaw app
```

- [ ] **Step 2: 启动前端开发服务器**

```bash
cd /Users/shixiangyi/code/CoPaw/console
npm run dev
```

- [ ] **Step 3: 手动测试**

1. 创建两个用户（alice 和 bob）的定时器任务
2. 等待定时器执行
3. 验证：
   - alice 的浏览器只显示 alice 的定时器消息
   - bob 的浏览器只显示 bob 的定时器消息

- [ ] **Step 4: Commit** (如测试通过)

```bash
git commit --allow-empty -m "chore: e2e verification passed for console user isolation"
```

---

## 验证清单

- [ ] `console_push_store.py` 所有函数支持 user_id 参数
- [ ] 存储结构改为按用户分区
- [ ] `console/channel.py` 从 meta 提取并传递 user_id
- [ ] `crons/manager.py` 更新调用传递 user_id
- [ ] `local_models.py` 更新调用传递 user_id
- [ ] `routers/console.py` 从 header 读取 user_id
- [ ] 前端 API 添加 x-user-id header
- [ ] 单元测试通过 (`test_console_push_store.py`)
- [ ] 集成测试通过 (`test_console_user_isolation_integration.py`)
- [ ] 手动端到端测试通过
