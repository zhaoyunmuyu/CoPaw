# CoPaw Tracing 模块设计文档

## 1. 目标与范围

Tracing 模块为 CoPaw 提供完整的链路追踪和分析能力：

> 捕获 LLM 调用、工具执行、技能调用的完整生命周期，支持性能分析、成本统计和使用审计。

### 1.1 功能范围

**本期实现：**
- Trace（追踪）和 Span（跨度）数据模型
- 多种存储后端（JSON 文件 / MySQL/TDSQL 数据库）
- 批量写入与后台刷新
- 敏感数据脱敏
- 数据保留策略
- 统计分析 API

**本期不实现：**
- 分布式追踪（跨服务）
- 实时流式分析
- 自定义仪表盘配置

---

## 2. 核心概念

### 2.1 数据模型

```
┌─────────────────────────────────────────────────────────────┐
│                      Trace (追踪)                           │
│  - trace_id: 追踪标识                                       │
│  - user_id: 用户标识                                        │
│  - session_id: 会话标识                                     │
│  - channel: 渠道标识                                        │
│  - status: running / completed / error / cancelled         │
│  - 统计: tokens, duration, tools_used, skills_used         │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ 1:N
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Span (跨度)                            │
│  - span_id: 跨度标识                                        │
│  - trace_id: 所属追踪                                       │
│  - parent_span_id: 父跨度（嵌套操作）                        │
│  - event_type: 事件类型                                     │
│  - name: 操作名称                                           │
│  - 统计: duration_ms, tokens, tool_input/output             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 事件类型

| EventType | 说明 | 触发时机 |
|-----------|------|---------|
| `SESSION_START` | 会话开始 | 用户首次交互 |
| `SESSION_END` | 会话结束 | 会话关闭 |
| `LLM_INPUT` | LLM 输入 | 发送 prompt |
| `LLM_OUTPUT` | LLM 输出 | 接收 response |
| `TOOL_CALL_START` | 工具调用开始 | 工具执行前 |
| `TOOL_CALL_END` | 工具调用结束 | 工具执行后 |
| `SKILL_INVOCATION` | 技能调用 | 技能执行 |

### 2.3 追踪状态

| TraceStatus | 说明 |
|-------------|------|
| `running` | 正在执行 |
| `completed` | 成功完成 |
| `error` | 执行出错 |
| `cancelled` | 被取消 |

---

## 3. 架构设计

### 3.1 模块结构

```
src/copaw/tracing/
├── __init__.py        # 模块导出
├── config.py          # 配置定义
├── models.py          # 数据模型
├── database.py        # 数据库连接
├── store.py           # 存储层
├── manager.py         # 管理器
├── sanitizer.py       # 数据脱敏
└── model_wrapper.py   # 模型包装器（自动追踪）

src/copaw/app/routers/
└── tracing.py         # API 路由
```

### 3.2 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer                                │
│  - RESTful 端点                                             │
│  - 分页查询                                                  │
│  - 数据导出                                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Manager Layer                            │
│  - 生命周期管理                                              │
│  - 批量写入队列                                              │
│  - 后台刷新任务                                              │
│  - 数据清理任务                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Store Layer                              │
│  - Trace/Span CRUD                                          │
│  - 统计聚合                                                  │
│  - 历史数据加载                                              │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌───────────────────────────┐  ┌───────────────────────────┐
│     JSON File Storage     │  │   Database Storage        │
│  - 按日期分文件            │  │  - TDSQL/MySQL            │
│  - 内存缓存                │  │  - 连接池                 │
│  - 原子写入                │  │  - 事务支持               │
└───────────────────────────┘  └───────────────────────────┘
```

### 3.3 与 Agent 集成

Tracing 通过 `TracingModelWrapper` 自动包装 LLM 调用：

```python
# agents/hooks/tracing.py
class TracingHook:
    async def on_llm_start(self, trace_id, model_name, input_tokens):
        await trace_manager.emit_llm_input(trace_id, model_name, input_tokens)

    async def on_llm_end(self, trace_id, span_id, output_tokens):
        await trace_manager.emit_llm_output(trace_id, span_id, output_tokens)

    async def on_tool_start(self, trace_id, tool_name, tool_input):
        return await trace_manager.emit_tool_call_start(trace_id, tool_name, tool_input)

    async def on_tool_end(self, trace_id, span_id, tool_output, error):
        await trace_manager.emit_tool_call_end(trace_id, span_id, tool_output, error)
```

---

## 4. 配置设计

### 4.1 TracingConfig

```python
class TracingConfig(BaseModel):
    enabled: bool = False              # 是否启用追踪
    batch_size: int = 100              # 批量写入大小
    flush_interval: int = 5            # 刷新间隔（秒）
    retention_days: int = 30           # 数据保留天数
    sanitize_output: bool = True       # 是否脱敏
    max_output_length: int = 500       # 输出截断长度
    max_memory_traces: int = 10000     # 内存最大追踪数
    storage_path: Optional[str] = None # 自定义存储路径
    database: Optional[TDSQLConfig]    # 数据库配置
```

### 4.2 TDSQLConfig

```python
class TDSQLConfig(BaseModel):
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "copaw_tracing"
    min_connections: int = 2
    max_connections: int = 10
    charset: str = "utf8mb4"
```

### 4.3 环境变量

```bash
TRACING_DB_HOST=localhost
TRACING_DB_PORT=3306
TRACING_DB_USER=copaw
TRACING_DB_PASSWORD=secret
TRACING_DB_NAME=copaw
TRACING_DB_MIN_CONN=2
TRACING_DB_MAX_CONN=10
```

---

## 5. 存储设计

### 5.1 JSON 文件存储

当数据库不可用时，使用 JSON 文件作为后备存储：

```
WORKING_DIR/tracing/
├── traces_2026-04-01.json
├── traces_2026-04-02.json
├── traces_2026-04-03.json
└── ...
```

**文件结构：**
```json
{
    "traces": [
        {
            "trace_id": "xxx",
            "user_id": "user1",
            "session_id": "session1",
            "channel": "console",
            "start_time": "2026-04-08T08:00:00Z",
            "status": "completed",
            ...
        }
    ],
    "spans": [
        {
            "span_id": "span1",
            "trace_id": "xxx",
            "event_type": "llm_input",
            ...
        }
    ]
}
```

### 5.2 数据库存储（可选）

当配置了数据库时，使用 MySQL/TDSQL 存储：

```sql
CREATE TABLE tracing_trace (
    trace_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(128),
    session_id VARCHAR(128),
    channel VARCHAR(32),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_ms INT,
    status VARCHAR(16),
    model_name VARCHAR(128),
    total_input_tokens INT,
    total_output_tokens INT,
    tools_used JSON,
    skills_used JSON,
    error TEXT,
    user_message TEXT,
    INDEX idx_user_id (user_id),
    INDEX idx_session_id (session_id),
    INDEX idx_start_time (start_time)
);

CREATE TABLE tracing_span (
    span_id VARCHAR(64) PRIMARY KEY,
    trace_id VARCHAR(64),
    parent_span_id VARCHAR(64),
    event_type VARCHAR(32),
    name VARCHAR(256),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_ms INT,
    model_name VARCHAR(128),
    input_tokens INT,
    output_tokens INT,
    tool_name VARCHAR(128),
    skill_name VARCHAR(128),
    mcp_server VARCHAR(128),
    tool_input JSON,
    tool_output TEXT,
    error TEXT,
    metadata JSON,
    INDEX idx_trace_id (trace_id),
    FOREIGN KEY (trace_id) REFERENCES tracing_trace(trace_id)
);
```

---

## 6. 数据脱敏

### 6.1 敏感键列表

```python
SENSITIVE_KEYS = frozenset([
    "api_key", "apikey", "password", "passwd", "secret",
    "token", "authorization", "credential", "private_key",
    "access_token", "refresh_token", "session_id", "auth",
    "private-key", "privatekey", "secret_key", "secretkey",
    "api_secret", "apisecret",
])
```

### 6.2 脱敏规则

```python
def sanitize_dict(data: dict, max_length: int = 500) -> dict:
    """脱敏字典数据"""
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        # 检查是否包含敏感关键词
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > max_length:
            result[key] = value[:max_length] + "..."
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, max_length)
        else:
            result[key] = value
    return result
```

---

## 7. API 设计

### 7.1 端点列表

| 方法 | 路径 | 说明 |
|-----|------|------|
| GET | `/api/tracing/overview` | 概览统计 |
| GET | `/api/tracing/users` | 用户列表 |
| GET | `/api/tracing/users/{user_id}` | 用户统计 |
| GET | `/api/tracing/traces` | 追踪列表 |
| GET | `/api/tracing/traces/{trace_id}` | 追踪详情 |
| GET | `/api/tracing/sessions` | 会话列表 |
| GET | `/api/tracing/sessions/{session_id}` | 会话统计 |
| GET | `/api/tracing/models` | 模型使用统计 |
| GET | `/api/tracing/tools` | 工具使用统计 |
| GET | `/api/tracing/skills` | 技能使用统计 |
| GET | `/api/tracing/mcp` | MCP 工具统计 |
| GET | `/api/tracing/user-messages` | 用户消息列表 |
| GET | `/api/tracing/user-messages/export` | 导出用户消息 |

### 7.2 查询参数

所有列表端点支持分页：

```
?page=1&page_size=20
```

时间范围过滤：

```
?start_date=2026-04-01&end_date=2026-04-08
```

### 7.3 响应示例

#### 概览统计

```json
{
    "online_users": 5,
    "total_users": 100,
    "total_tokens": 500000,
    "input_tokens": 300000,
    "output_tokens": 200000,
    "total_sessions": 500,
    "total_conversations": 300,
    "avg_duration_ms": 2500,
    "model_distribution": [
        {
            "model_name": "gpt-4",
            "count": 200,
            "total_tokens": 300000,
            "input_tokens": 200000,
            "output_tokens": 100000
        }
    ],
    "top_tools": [
        {
            "tool_name": "browser_control",
            "count": 50,
            "avg_duration_ms": 1500,
            "error_count": 2
        }
    ],
    "top_skills": [
        {
            "skill_name": "pdf",
            "count": 30,
            "avg_duration_ms": 800
        }
    ],
    "top_mcp_tools": [],
    "mcp_servers": [],
    "daily_trend": []
}
```

#### 追踪详情

```json
{
    "trace": {
        "trace_id": "xxx",
        "user_id": "user1",
        "session_id": "session1",
        "status": "completed",
        ...
    },
    "spans": [
        {
            "span_id": "span1",
            "event_type": "llm_input",
            "name": "llm_call_gpt-4",
            "duration_ms": 1500,
            ...
        }
    ],
    "llm_duration_ms": 3000,
    "tool_duration_ms": 1500,
    "tools_called": [
        {
            "tool_name": "browser_control",
            "duration_ms": 800,
            "error": null
        }
    ]
}
```

---

## 8. 批量写入机制

### 8.1 写入队列

```python
class TraceManager:
    def __init__(self):
        self._span_queue: list[Span] = []
        self._span_queue_lock = asyncio.Lock()
        self._pending_spans: dict[str, Span] = {}

    async def emit_span(self, span: Span):
        async with self._span_queue_lock:
            self._pending_spans[span.span_id] = span
            self._span_queue.append(span)

            # 达到批量大小时触发刷新
            if len(self._span_queue) >= self.config.batch_size:
                asyncio.create_task(self._flush_spans())
```

### 8.2 后台刷新

```python
async def _flush_loop(self):
    """后台刷新循环"""
    while self._running:
        await asyncio.sleep(self.config.flush_interval)
        await self._flush_spans()

async def _flush_spans(self):
    """刷新队列到存储"""
    async with self._span_queue_lock:
        spans = self._span_queue.copy()
        self._span_queue.clear()

    if spans:
        await self.store.batch_create_spans(spans)
        await self.store.flush()
```

---

## 9. 数据清理

### 9.1 清理策略

```python
async def _cleanup_loop(self):
    """后台清理循环"""
    while self._running:
        await asyncio.sleep(24 * 60 * 60)  # 每天执行一次
        await self._cleanup_old_data()

async def _cleanup_old_data(self):
    """清理过期数据"""
    cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)

    # 清理 JSON 文件
    for file_path in self.storage_path.glob("traces_*.json"):
        date_str = file_path.stem.replace("traces_", "")
        file_date = datetime.strptime(date_str, "%Y-%m-%d")
        if file_date < cutoff_date:
            file_path.unlink()

    # 清理内存数据
    await self.store.cleanup_old_data(cutoff_date)
```

---

## 10. 上下文管理

### 10.1 TraceContext

```python
class TraceContext:
    """追踪上下文"""
    def __init__(self, trace_id, user_id, session_id, channel):
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.channel = channel
        self.start_time = datetime.now()
        self._span_stack: list[str] = []

    def push_span(self, span_id: str):
        """压入跨度栈"""
        self._span_stack.append(span_id)

    def pop_span(self) -> Optional[str]:
        """弹出跨度栈"""
        return self._span_stack.pop() if self._span_stack else None

    @property
    def current_span_id(self) -> Optional[str]:
        """获取当前跨度 ID"""
        return self._span_stack[-1] if self._span_stack else None
```

### 10.2 ContextVar

```python
_current_trace: ContextVar[Optional[TraceContext]] = ContextVar(
    "current_trace", default=None
)

def get_current_trace() -> Optional[TraceContext]:
    return _current_trace.get()

def set_current_trace(ctx: Optional[TraceContext]):
    _current_trace.set(ctx)
```

---

## 11. 统计模型

### 11.1 使用统计

| 模型 | 说明 |
|------|------|
| `ModelUsage` | 模型使用统计 |
| `ToolUsage` | 工具使用统计 |
| `SkillUsage` | 技能使用统计 |
| `MCPToolUsage` | MCP 工具使用统计 |
| `MCPServerUsage` | MCP 服务器统计 |
| `DailyStats` | 每日统计 |

### 11.2 列表项

| 模型 | 说明 |
|------|------|
| `UserListItem` | 用户列表项 |
| `TraceListItem` | 追踪列表项 |
| `SessionListItem` | 会话列表项 |
| `UserMessageItem` | 用户消息项 |

---

## 12. 导出功能

### 12.1 导出格式

支持三种导出格式：

| 格式 | 说明 |
|------|------|
| `csv` | CSV 文件，通用格式 |
| `json` | JSON 文件，结构化数据 |
| `xlsx` | Excel 文件，带格式 |

### 12.2 导出示例

```
GET /api/tracing/user-messages/export?format=csv&start_date=2026-04-01
```

响应：
```http
Content-Type: text/csv
Content-Disposition: attachment; filename=user_messages_20260408_080000.csv

trace_id,user_id,session_id,channel,user_message,input_tokens,output_tokens,model_name,start_time,duration_ms
xxx,user1,session1,console,你好,100,200,gpt-4,2026-04-08T08:00:00Z,1500
```

---

## 13. 部署注意事项

### 13.1 无数据库运行

当数据库不可用时，Tracing 模块可正常运行：

```python
if not AIOMYSQL_AVAILABLE:
    logger.debug("aiomysql not installed, tracing will use JSON file storage")
```

### 13.2 性能考虑

- 批量写入减少 I/O 开销
- 后台刷新避免阻塞主流程
- 内存缓存提升查询性能
- 历史数据按需加载

### 13.3 存储估算

每条 Trace 约 1KB，每条 Span 约 0.5KB：
- 1000 次/天 × 30 天 = 30MB
- 10000 次/天 × 30 天 = 300MB

---

## 14. 扩展预留

### 14.1 未来功能

1. **实时流式分析**
   - WebSocket 推送实时统计
   - 在线用户实时监控

2. **自定义仪表盘**
   - 可配置统计维度
   - 可视化图表

3. **告警规则**
   - Token 使用阈值告警
   - 错误率监控

4. **分布式追踪**
   - OpenTelemetry 集成
   - 跨服务追踪

### 14.2 扩展接口

```python
# 预留的实时统计接口
class RealTimeStats:
    async def get_online_users(self) -> int:
        pass

    async def get_active_sessions(self) -> list[str]:
        pass

# 预留的告警接口
class AlertManager:
    async def check_token_threshold(self, threshold: int) -> bool:
        pass

    async def check_error_rate(self, threshold: float) -> bool:
        pass
```

---

## 15. 版本历史

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| 1.0.0 | 2026-04-08 | 初始版本，支持 Trace/Span 追踪、统计分析、数据导出 |
