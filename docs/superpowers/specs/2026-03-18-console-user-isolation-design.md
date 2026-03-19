# Console Channel 用户隔离设计文档

**日期**: 2026-03-18
**主题**: Console Channel 定时器消息用户隔离

## 背景与问题

当前 CoPaw 的 console channel 使用内存存储 (`console_push_store.py`) 来暂存定时器发送的消息，前端通过 `/console/push-messages` API 轮询获取。但现有实现存在以下问题：

1. **无用户隔离**：消息只按 `session_id` 存储，同一 session 的不同用户会看到彼此的消息
2. **定时器场景**：定时器任务执行时带有 `target_user_id`，但发送到 console channel 时未利用该信息做隔离
3. **前端查询**：前端获取消息时没有验证用户身份，可能导致信息泄露

## 目标

1. 定时器执行后发送结果时，将 `target_user_id` 一并传递给 channel
2. Console channel 基于 `user_id` 存储消息，实现用户数据隔离
3. 前端 API 支持通过 `x-user-id` header 获取指定用户的消息

## 设计决策

### 方案选择

选择 **方案 C：按用户分区存储**，原因：
- 数据结构清晰，天然支持用户隔离
- 便于扩展（如后续支持获取用户所有消息）
- 符合 CoPaw 多用户架构的设计理念

### 核心变更

#### 1. 存储结构重构 (`console_push_store.py`)

```python
# 旧：扁平列表
_list: List[Dict[str, Any]] = []

# 新：按用户分区
_store: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> messages

# 消息结构（包含 user_id 字段用于调试和审计）
message = {
    "id": str(uuid.uuid4()),
    "text": text,
    "ts": time.time(),
    "session_id": session_id,
    "user_id": user_id,  # 新增：便于调试和问题排查
}
```

#### 2. API 签名变更

| 函数 | 旧签名 | 新签名 |
|------|--------|--------|
| `append` | `(session_id, text)` | `(user_id, session_id, text)` |
| `take` | `(session_id)` | `(user_id, session_id)` |
| `take_all` | `()` | `(user_id=None)` |
| `get_recent` | `(max_age_seconds=60)` | `(user_id=None, max_age_seconds=60)` |

#### 3. Console Channel 更新 (`console/channel.py`)

从 `meta` 参数中提取 `user_id` 传递给 `push_store_append`，需要更新两个方法：

**`send` 方法**：

```python
async def send(self, to_handle: str, text: str, meta: Optional[Dict] = None):
    # ... 打印逻辑 ...
    sid = (meta or {}).get("session_id")
    uid = (meta or {}).get("user_id")  # 新增
    if sid and text.strip():
        await push_store_append(uid, sid, text.strip())  # 传入 user_id
```

**`send_content_parts` 方法**：

```python
async def send_content_parts(
    self,
    to_handle: str,
    parts: List[OutgoingContentPart],
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    self._print_parts(parts)
    sid = (meta or {}).get("session_id")
    uid = (meta or {}).get("user_id")  # 新增
    if sid:
        body = self._parts_to_text(parts, meta)
        if body.strip():
            await push_store_append(uid, sid, body.strip())  # 传入 user_id
```

#### 4. API 路由更新 (`routers/console.py`)

从 header 读取 `x-user-id`，使用 `"default"` 作为默认值（与前端 `window.currentUserId` 默认值保持一致）：

```python
@router.get("/push-messages")
async def get_push_messages(
    session_id: str | None = Query(None),
    user_id: str = Header("default", alias="x-user-id"),  # 默认为 "default"
):
    if session_id and user_id:
        # 获取指定用户的指定会话消息
        messages = await take(user_id, session_id)
    elif user_id:
        # 获取指定用户的所有消息（ConsoleCronBubble 使用此场景）
        messages = await take_all(user_id)
    else:
        # 理论上不会执行（user_id 默认为 "default"）
        messages = []
    return {"messages": messages}
```

## 数据流

### 定时器消息发送流

```
CronExecutor.execute()
  ↓
ChannelManager.send_text(user_id, session_id, text)
  ↓  (meta 中包含 user_id 和 session_id)
ConsoleChannel.send_content_parts(to_handle, parts, meta)
  ↓
push_store_append(user_id, session_id, text)  ← 新增 user_id 参数
  ↓
存储: {user_id: [{id, text, ts, session_id, user_id}, ...]}
```

### 前端消息获取流

```
GET /console/push-messages?session_id=xxx
Headers: x-user-id: <user_id>
  ↓
take(user_id, session_id)
  ↓
过滤: _store[user_id] 中 session_id 匹配的消息
  ↓
返回: [{id, text}, ...]
```

## 边界情况处理

| 场景 | 处理策略 |
|------|----------|
| 无 user_id（向后兼容） | 使用 `"default"` 作为默认键，与前端 `window.currentUserId` 默认值保持一致 |
| 前端未传 x-user-id | 使用 `"default"` 作为默认用户ID，确保现有前端行为不受影响 |
| user_id 不存在于 store | 返回空列表 |
| session_id 为 None | `take_all(user_id)` 返回该用户所有消息（消费并移除） |
| 消息过期清理 | 按用户分区分别清理过期消息 |

## 函数消费语义说明

| 函数 | 是否消费（移除）消息 | 说明 |
|------|---------------------|------|
| `take(user_id, session_id)` | 是 | 返回并移除指定用户的指定会话消息 |
| `take_all(user_id)` | 是 | 返回并移除指定用户的所有消息 |
| `get_recent(user_id, max_age)` | 否 | 返回但不移除近期消息，同时清理过期消息 |

## 文件变更清单

### 后端文件

| 文件路径 | 变更类型 | 变更内容 |
|----------|----------|----------|
| `src/copaw/app/console_push_store.py` | 重构 | 存储结构改为 Dict，所有函数增加 user_id 参数 |
| `src/copaw/app/channels/console/channel.py` | 修改 | `send` 和 `send_content_parts` 传入 user_id 到 push_store |
| `src/copaw/app/routers/console.py` | 修改 | 从 header 读取 x-user-id，使用 "default" 作为默认值 |

### 前端文件

| 文件路径 | 变更类型 | 变更内容 |
|----------|----------|----------|
| `console/src/api/modules/console.ts` | 修改 | `getPushMessages` 函数添加 `x-user-id` header，值为 `window.currentUserId \|\| "default"` |
| `console/src/components/ConsoleCronBubble/index.tsx` | 无需修改 | 保持现有调用方式，由 API 层处理 header |

## 前端 Session ID 说明

当前前端 `ConsoleCronBubble` 组件调用 `getPushMessages()` 时不传递 `session_id` 参数，这是预期行为：

- **使用场景**：定时器消息通常发送到特定用户的默认会话，前端只需要获取当前用户的所有定时器消息
- **API 设计**：`take_all(user_id)` 专门用于此场景，返回并消费该用户的所有消息
- **无需变更**：前端保持现状即可，由后端根据 `x-user-id` 返回对应用户的消息

## 测试要点

### 单元测试（`console_push_store.py`）

1. **多用户并发写入隔离**：
   - 用户 A 和用户 B 同时写入消息，验证各自只能读取自己的消息

2. **边界条件处理**：
   - `user_id` 为 `None` 时，使用 `"default"` 作为键
   - `user_id` 不存在于 store 时，返回空列表
   - `session_id` 为 `None` 时，`take_all` 返回该用户所有消息

3. **消息过期清理**：
   - 过期消息在分区存储下正确清理
   - 清理时不影响其他用户的消息

4. **消费语义验证**：
   - `take` 和 `take_all` 正确消费（移除）消息
   - `get_recent` 不移除消息

### 集成测试

1. **定时器消息隔离**：
   - 定时器任务以 user_id="alice" 执行，消息仅 alice 可见
   - 验证 bob 调用 API 获取不到 alice 的消息

2. **前后端兼容性**：
   - 前端不传 `x-user-id` 时，后端使用 `"default"` 作为默认值
   - 验证现有前端行为不受影响

### API 测试

1. **Header 传递验证**：
   - `x-user-id: alice` 请求只能获取 alice 的消息
   - `x-user-id: bob` 请求只能获取 bob 的消息
   - 无 `x-user-id` header 时，使用 `"default"`

## 安全考虑

1. **默认安全但兼容**：前端未传 `x-user-id` 时使用 `"default"` 作为默认值，与前端 `window.currentUserId` 默认值保持一致，既保证安全又不破坏现有功能
2. **数据隔离**：内存中的 `_store` 按用户分区，避免跨用户访问
3. **过期清理**：消息有过期时间（60秒），避免内存无限增长
