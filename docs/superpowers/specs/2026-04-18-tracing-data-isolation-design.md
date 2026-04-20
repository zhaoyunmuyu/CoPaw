# Tracing 模块数据隔离设计文档

## 1. 概述

### 1.1 背景

CoPaw 支持多租户部署，不同租户的数据必须严格隔离。Tracing 模块作为观测能力的核心，记录了用户的会话、LLM 调用、工具执行、技能调用等敏感数据，必须确保：

1. 租户 A 无法查询到租户 B 的任何追踪数据
2. 所有 SQL 查询必须包含 `source_id` 过滤条件
3. 数据写入时必须正确携带 `source_id`

### 1.2 目标

- 设计基于 `source_id` 的数据隔离机制
- 定义 `source_id` 在全链路的传递方式
- 规范数据库层面的隔离约束
- 提供测试验证策略

### 1.3 范围

本设计仅覆盖 Tracing 模块的数据隔离，不包括：
- 其他模块的多租户隔离（见 `2026-04-01-multi-tenant-isolation-design.md`）
- Tracing 模块的其他功能设计（见 `2026-04-08-tracing-module-design.md`）

## 2. 核心概念

### 2.1 source_id 定义

`source_id` 是 Tracing 模块的租户标识符，用于隔离不同租户的追踪数据。

| 属性 | 说明 |
|------|------|
| 来源 | HTTP 请求头 `X-Source-Id` 或查询参数 `source_id` |
| 默认值 | `"default"`（单租户兼容模式） |
| 长度限制 | VARCHAR(64) |
| 存储位置 | `swe_tracing_traces.source_id`、`swe_tracing_spans.source_id` |

### 2.2 隔离边界

```
┌─────────────────────────────────────────────────────────────┐
│                      Tracing 数据隔离边界                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  source_id = "tenant-A"          source_id = "tenant-B"     │
│  ┌─────────────────────┐         ┌─────────────────────┐    │
│  │ Traces              │         │ Traces              │    │
│  │ ├─ trace-001        │         │ ├─ trace-101        │    │
│  │ ├─ trace-002        │         │ ├─ trace-102        │    │
│  │ └─ ...              │         │ └─ ...              │    │
│  │                     │         │                     │    │
│  │ Spans               │         │ Spans               │    │
│  │ ├─ span-001         │         │ ├─ span-101         │    │
│  │ ├─ span-002         │         │ ├─ span-102         │    │
│  │ └─ ...              │         │ └─ ...              │    │
│  └─────────────────────┘         └─────────────────────┘    │
│                                                             │
│  ❌ tenant-A 的查询无法看到 tenant-B 的数据                   │
│  ❌ tenant-B 的查询无法看到 tenant-A 的数据                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 3. 数据模型

### 3.1 Trace 模型

```python
class Trace(BaseModel):
    trace_id: str          # 唯一标识
    source_id: str         # 租户标识（必填）
    user_id: str           # 用户标识
    session_id: str        # 会话标识
    channel: str           # 通道来源
    start_time: datetime   # 开始时间
    end_time: Optional[datetime]    # 结束时间
    status: TraceStatus    # 状态
    user_message: Optional[str]     # 用户消息
    # ... 其他字段
```

### 3.2 Span 模型

```python
class Span(BaseModel):
    span_id: str           # 唯一标识
    trace_id: str          # 关联的 Trace
    source_id: str         # 租户标识（必填）
    parent_span_id: Optional[str]   # 父 Span
    name: str              # Span 名称
    event_type: EventType  # 事件类型
    start_time: datetime   # 开始时间
    end_time: Optional[datetime]    # 结束时间
    # ... 其他字段
```

### 3.3 数据库 Schema

#### swe_tracing_traces 表

```sql
CREATE TABLE swe_tracing_traces (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trace_id VARCHAR(36) NOT NULL,
    source_id VARCHAR(64) NOT NULL COMMENT '租户标识',
    user_id VARCHAR(128),
    session_id VARCHAR(36),
    channel VARCHAR(32),
    start_time DATETIME,
    end_time DATETIME,
    status VARCHAR(16) DEFAULT 'running',
    user_message TEXT,
    -- ... 其他字段
    UNIQUE KEY uk_trace_id (trace_id),
    INDEX idx_source_id (source_id),
    INDEX idx_source_start_time (source_id, start_time),
    INDEX idx_source_user (source_id, user_id),
    INDEX idx_source_session (source_id, session_id)
);
```

#### swe_tracing_spans 表

```sql
CREATE TABLE swe_tracing_spans (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    span_id VARCHAR(36) NOT NULL,
    trace_id VARCHAR(36) NOT NULL,
    source_id VARCHAR(64) NOT NULL COMMENT '租户标识',
    parent_span_id VARCHAR(36),
    name VARCHAR(128),
    event_type VARCHAR(32),
    start_time DATETIME,
    end_time DATETIME,
    -- ... 其他字段
    UNIQUE KEY uk_span_id (span_id),
    INDEX idx_source_id (source_id),
    INDEX idx_source_trace (source_id, trace_id),
    INDEX idx_source_skill (source_id, event_type, skill_name),
    INDEX idx_source_tool (source_id, event_type, tool_name)
);
```

### 3.4 索引设计说明

| 索引 | 用途 |
|------|------|
| `idx_source_id` | 基础租户过滤 |
| `idx_source_start_time` | 按时间范围查询（Overview、Traces 列表） |
| `idx_source_user` | 按用户查询（User Stats、User Messages） |
| `idx_source_session` | 按会话查询（Session Stats） |
| `idx_source_trace` | Span 按 Trace 查询 |
| `idx_source_skill` | 技能统计查询 |
| `idx_source_tool` | 工具统计查询 |

## 4. source_id 传递链路

### 4.1 完整传递流程

```
┌──────────────────────────────────────────────────────────────────────┐
│                           请求入口                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. 前端 iframe 上下文                                                │
│     └─ iframeStore.ts: source = iframeContext.source                 │
│                                                                      │
│  2. HTTP 请求头                                                       │
│     └─ authHeaders.ts: headers["X-Source-Id"] = source               │
│                                                                      │
│  3. Console 路由                                                      │
│     └─ console.py: source_id = request.headers.get("X-Source-Id")    │
│     └─ native_payload["meta"]["source_id"] = source_id               │
│                                                                      │
│  4. Runner 处理                                                       │
│     └─ runner.py: source_id = request.source_id                      │
│                 or request.channel_meta.get("source_id", "default")  │
│                                                                      │
│  5. TraceManager 初始化                                               │
│     └─ manager.py: start_trace(source_id=source_id)                  │
│                 └─ Trace(source_id=source_id)                        │
│                 └─ TraceContext(source_id=source_id)                 │
│                                                                      │
│  6. Agent Hooks                                                       │
│     └─ TracingHook(source_id=source_id)                              │
│     └─ SkillInvocationDetector(source_id=source_id)                  │
│                                                                      │
│  7. Span 写入                                                         │
│     └─ emit_span(source_id=source_id)                                │
│     └─ Span(source_id=source_id)                                     │
│                                                                      │
│  8. 数据库持久化                                                       │
│     └─ store.py: INSERT ... VALUES (..., source_id, ...)             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 查询链路

```
┌──────────────────────────────────────────────────────────────────────┐
│                           查询入口                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. API 请求                                                          │
│     └─ GET /tracing/overview?source_id=xxx                           │
│     └─ Header: X-Source-Id: tenant-A                                 │
│                                                                      │
│  2. Tracing 路由                                                      │
│     └─ _get_source_id(request, query_source_id)                      │
│        ├─ 优先级 1: request.headers["X-Source-Id"]                    │
│        ├─ 优先级 2: query_source_id                                   │
│        └─ 优先级 3: "default"                                         │
│                                                                      │
│  3. TraceStore 查询                                                   │
│     └─ WHERE source_id = %s                                          │
│                                                                      │
│  4. 返回结果                                                          │
│     └─ 仅包含当前 source_id 的数据                                     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 source_id 提取优先级

```python
def _get_source_id(
    request: Request,
    query_source_id: Optional[str] = None,
) -> str:
    """提取 source_id，优先级从高到低。"""
    # 1. HTTP Header（推荐方式）
    header_source_id = request.headers.get("X-Source-Id")
    if header_source_id:
        return header_source_id

    # 2. Query Parameter（兼容方式）
    if query_source_id:
        return query_source_id

    # 3. 默认值（单租户兼容）
    return "default"
```

## 5. API 设计

### 5.1 查询接口隔离要求

所有查询接口必须：
1. 接受 `source_id` 参数（Query 或 Header）
2. 在 SQL 查询中强制包含 `WHERE source_id = %s`
3. 不允许绕过 `source_id` 过滤

### 5.2 接口列表

| 接口 | source_id 来源 | SQL 过滤 |
|------|---------------|----------|
| `GET /tracing/overview` | Header / Query | ✅ |
| `GET /tracing/users` | Header / Query | ✅ |
| `GET /tracing/users/{user_id}` | Header / Query | ✅ |
| `GET /tracing/traces` | Header / Query | ✅ |
| `GET /tracing/traces/{trace_id}` | 无（按 ID 查询） | ⚠️ 见 5.3 |
| `GET /tracing/traces/{trace_id}/timeline` | 无（按 ID 查询） | ⚠️ 见 5.3 |
| `GET /tracing/models` | Header / Query | ✅ |
| `GET /tracing/tools` | Header / Query | ✅ |
| `GET /tracing/skills` | Header / Query | ✅ |
| `GET /tracing/mcp` | Header / Query | ✅ |
| `GET /tracing/sessions` | Header / Query | ✅ |
| `GET /tracing/sessions/{session_id}` | Header / Query | ✅ |
| `GET /tracing/user-messages` | Header / Query | ✅ |
| `GET /tracing/user-messages/export` | Header / Query | ✅ |

### 5.3 按 ID 查询的安全考量

`GET /tracing/traces/{trace_id}` 和 `GET /tracing/traces/{trace_id}/timeline` 按 `trace_id` 直接查询，未强制校验 `source_id`。

**风险评估：**
- `trace_id` 使用 UUID v4，猜测难度高
- 数据本身不涉及敏感信息（仅为调用链）

**缓解措施（可选）：**
- 增加 `source_id` 参数，查询时验证 `trace_id` 归属
- 或在返回前检查 `trace.source_id == request.source_id`

## 6. 存储层设计

### 6.1 写入隔离

```python
async def create_trace(self, trace: Trace) -> None:
    """创建 Trace，必须携带 source_id。"""
    query = """
        INSERT INTO swe_tracing_traces
        (trace_id, source_id, user_id, session_id, channel, ...)
        VALUES (%s, %s, %s, %s, %s, ...)
    """
    params = (
        trace.trace_id,
        trace.source_id,  # 必填，NOT NULL 约束
        trace.user_id,
        trace.session_id,
        trace.channel,
        # ...
    )
    await self._db.execute(query, params)
```

### 6.2 查询隔离

```python
async def get_traces(
    self,
    source_id: str,  # 必填参数
    page: int = 1,
    page_size: int = 20,
    user_id: Optional[str] = None,
    # ...
) -> tuple[list[TraceListItem], int]:
    """查询 Traces，强制按 source_id 过滤。"""
    where_clauses = ["source_id = %s"]  # 强制条件
    params = [source_id]

    if user_id:
        where_clauses.append("user_id = %s")
        params.append(user_id)

    # ...

    count_query = f"SELECT COUNT(*) FROM swe_tracing_traces WHERE {' AND '.join(where_clauses)}"
    total = await self._db.fetch_one(count_query, params)

    list_query = f"""
        SELECT * FROM swe_tracing_traces
        WHERE {' AND '.join(where_clauses)}
        ORDER BY start_time DESC
        LIMIT %s OFFSET %s
    """
    params.extend([page_size, (page - 1) * page_size])
    rows = await self._db.fetch_all(list_query, params)

    return [TraceListItem(**row) for row in rows], total["COUNT(*)"]
```

### 6.3 辅助查询函数

所有辅助查询函数必须接受 `source_id` 作为第一个参数：

```python
async def _db_get_total_users(self, source_id: str, ...) -> int:
    query = "SELECT COUNT(DISTINCT user_id) FROM swe_tracing_traces WHERE source_id = %s"
    ...

async def _db_get_token_stats(self, source_id: str, ...) -> dict:
    query = "SELECT SUM(input_tokens), SUM(output_tokens) FROM swe_tracing_spans WHERE source_id = %s"
    ...

async def _db_get_top_tools(self, source_id: str, ...) -> list:
    query = "SELECT tool_name, COUNT(*) FROM swe_tracing_spans WHERE source_id = %s AND event_type = %s GROUP BY tool_name"
    ...
```

## 7. 前端集成

### 7.1 iframe 上下文获取

```typescript
// console/src/stores/iframeStore.ts
interface IframeContext {
  initialized: boolean;
  userId: string | null;
  source: string | null;  // source_id 来源
  // ...
}

// 父窗口通过 postMessage 设置
window.addEventListener('message', (event) => {
  if (event.data.type === 'SET_CONTEXT') {
    iframeContext.source = event.data.source;
  }
});
```

### 7.2 请求头注入

```typescript
// console/src/api/authHeaders.ts
export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};

  // ... 其他 headers

  // Source ID（数据隔离）
  const iframeContext = useIframeStore.getState();
  if (iframeContext.source) {
    headers["X-Source-Id"] = iframeContext.source;
  }

  return headers;
}
```

## 8. 数据库迁移

### 8.1 迁移脚本

```sql
-- scripts/sql/tracing_source_migration.sql

-- 1. Traces 表添加 source_id
ALTER TABLE swe_tracing_traces
ADD COLUMN IF NOT EXISTS source_id VARCHAR(64) NOT NULL DEFAULT 'default'
COMMENT 'Source identifier for data isolation'
AFTER trace_id;

-- 2. 为现有数据设置默认值（如需要）
-- UPDATE swe_tracing_traces SET source_id = 'default' WHERE source_id IS NULL;

-- 3. 添加索引
ALTER TABLE swe_tracing_traces ADD INDEX IF NOT EXISTS idx_source_id (source_id);
ALTER TABLE swe_tracing_traces ADD INDEX IF NOT EXISTS idx_source_start_time (source_id, start_time);
ALTER TABLE swe_tracing_traces ADD INDEX IF NOT EXISTS idx_source_user (source_id, user_id);
ALTER TABLE swe_tracing_traces ADD INDEX IF NOT EXISTS idx_source_session (source_id, session_id);

-- 4. Spans 表添加 source_id
ALTER TABLE swe_tracing_spans
ADD COLUMN IF NOT EXISTS source_id VARCHAR(64) NOT NULL DEFAULT 'default'
COMMENT 'Source identifier for data isolation'
AFTER span_id;

-- 5. 添加索引
ALTER TABLE swe_tracing_spans ADD INDEX IF NOT EXISTS idx_source_id (source_id);
ALTER TABLE swe_tracing_spans ADD INDEX IF NOT EXISTS idx_source_trace (source_id, trace_id);
ALTER TABLE swe_tracing_spans ADD INDEX IF NOT EXISTS idx_source_skill (source_id, event_type, skill_name);
ALTER TABLE swe_tracing_spans ADD INDEX IF NOT EXISTS idx_source_tool (source_id, event_type, tool_name);
```

### 8.2 迁移注意事项

1. **NOT NULL 约束**：添加列时使用 `DEFAULT 'default'` 避免现有数据报错
2. **索引创建**：大表添加索引可能耗时，建议低峰期执行
3. **回滚方案**：保留 `ALTER TABLE ... DROP COLUMN` 脚本

## 9. 测试策略

### 9.1 测试分类

```
tests/unit/tracing/test_data_isolation.py
├── TestMatchesTraceFilters       # 过滤逻辑单元测试
├── TestStoreSourceIdIsolation    # 存储层隔离测试
├── TestManagerSourceIdPropagation # 管理器传递测试
└── TestCrossTenantIsolation      # 跨租户隔离测试
```

### 9.2 测试用例清单

#### 存储层隔离测试

| 测试用例 | 验证点 |
|----------|--------|
| `test_create_trace_carries_source_id` | INSERT 参数包含 source_id |
| `test_create_span_carries_source_id` | INSERT 参数包含 source_id |
| `test_batch_create_spans_carries_source_id` | 批量写入包含 source_id |
| `test_get_overview_stats_filters_by_source_id` | 统计查询强制过滤 |
| `test_get_users_filters_by_source_id` | 用户列表过滤 |
| `test_get_traces_filters_by_source_id` | Trace 列表过滤 |
| `test_get_sessions_filters_by_source_id` | Session 列表过滤 |
| `test_get_user_stats_filters_by_source_id` | 用户统计过滤 |
| `test_get_user_messages_filters_by_source_id` | 消息列表过滤 |
| `test_get_session_stats_filters_by_source_id` | Session 统计过滤 |
| `test_mcp_stats_filters_by_source_id` | MCP 统计过滤 |
| `test_source_id_in_where_clause_sql` | SQL 包含 WHERE source_id = %s |

#### 跨租户隔离测试

| 测试用例 | 验证点 |
|----------|--------|
| `test_two_tenants_data_does_not_mix` | 租户 A 查询看不到租户 B 数据 |
| `test_overview_stats_isolated_per_tenant` | 统计数据按租户隔离 |
| `test_user_stats_isolated_per_tenant` | 用户统计按租户隔离 |
| `test_spans_written_with_correct_source_id` | Span 写入正确的 source_id |
| `test_session_stats_isolated_per_tenant` | Session 统计按租户隔离 |

### 9.3 测试示例

```python
@pytest.mark.asyncio
async def test_two_tenants_data_does_not_mix(self, config, mock_db):
    """验证两个租户的数据完全隔离。"""
    store = TraceStore(config, mock_db)
    await store.initialize()

    # 写入租户 A 的数据
    trace_a = _make_trace("tenant-A", trace_id="trace-a")
    await store.create_trace(trace_a)

    # 写入租户 B 的数据
    trace_b = _make_trace("tenant-B", trace_id="trace-b")
    await store.create_trace(trace_b)

    # 查询租户 A
    mock_db.fetch_one.return_value = {"total": 0}
    mock_db.fetch_all.return_value = []
    await store.get_traces(source_id="tenant-A")

    # 验证所有查询都使用 tenant-A 作为参数
    for call in mock_db.fetch_one.call_args_list:
        assert call[0][1][0] == "tenant-A"
    for call in mock_db.fetch_all.call_args_list:
        assert call[0][1][0] == "tenant-A"
```

## 10. 安全考量

### 10.1 威胁模型

| 威胁 | 风险等级 | 缓解措施 |
|------|----------|----------|
| 租户 A 伪造 source_id 查询租户 B 数据 | 高 | API Gateway 层校验 source_id 归属 |
| SQL 注入绕过 source_id 过滤 | 高 | 参数化查询（已实现） |
| 内部接口泄露跨租户数据 | 中 | 内部接口也需校验 source_id |
| trace_id 猜测攻击 | 低 | UUID v4 不可预测 |

### 10.2 建议加固

1. **API Gateway 层校验**：在网关层验证 `X-Source-Id` 与用户身份的绑定关系
2. **审计日志**：记录跨租户访问尝试
3. **按 ID 查询加固**：`GET /traces/{trace_id}` 增加 source_id 校验

## 11. 性能考量

### 11.1 索引覆盖

所有查询的 WHERE 条件均被索引覆盖：

- `WHERE source_id = ?` → `idx_source_id`
- `WHERE source_id = ? AND start_time BETWEEN ?` → `idx_source_start_time`
- `WHERE source_id = ? AND user_id = ?` → `idx_source_user`
- `WHERE source_id = ? AND session_id = ?` → `idx_source_session`

### 11.2 查询优化建议

1. 避免在 `source_id` 上使用函数（如 `LOWER(source_id)`），会导致索引失效
2. 复合查询使用复合索引（如 `source_id + start_time`）

## 12. 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-04-18 | 初始版本，定义 Tracing 模块 source_id 数据隔离设计 |

## 附录

### A. 相关设计文档

- `2026-04-01-multi-tenant-isolation-design.md` - 系统级多租户隔离设计
- `2026-04-08-tracing-module-design.md` - Tracing 模块完整设计
- `2026-04-10-skill-invocation-tracing-design.md` - 技能调用追踪设计

### B. 关键文件索引

| 文件 | 职责 |
|------|------|
| `src/swe/tracing/models.py` | 数据模型定义 |
| `src/swe/tracing/store.py` | 数据库操作与隔离过滤 |
| `src/swe/tracing/manager.py` | 追踪生命周期管理 |
| `src/swe/app/routers/tracing.py` | API 路由与 source_id 提取 |
| `src/swe/app/runner/runner.py` | 请求处理与 source_id 传递 |
| `src/swe/agents/hooks/tracing.py` | Agent 钩子与 source_id 传播 |
| `console/src/api/authHeaders.ts` | 前端请求头注入 |
| `scripts/sql/tracing_source_migration.sql` | 数据库迁移脚本 |
| `tests/unit/tracing/test_data_isolation.py` | 隔离测试用例 |
