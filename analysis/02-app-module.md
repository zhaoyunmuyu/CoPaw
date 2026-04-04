# CoPaw App 模块分析文档

## 概述

`src/copaw/app/` 模块是 CoPaw 的核心应用层，基于 FastAPI 实现多 Agent AI 助手系统。提供可插拔的通道系统支持多种消息平台、MCP 工具集成、定时任务执行，以及带有热重载能力的多 Agent 管理系统。

---

## 架构图

```
FastAPI Application (_app.py)
├── Lifespan Management
│   ├── MultiAgentManager (multi_agent_manager.py)
│   │   └── Workspace instances (workspace/workspace.py)
│   │       ├── AgentRunner (runner/runner.py)
│   │       ├── ChannelManager (channels/manager.py)
│   │       │   └── BaseChannel implementations
│   │       ├── MCPClientManager (mcp/manager.py)
│   │       ├── CronManager (crons/manager.py)
│   │       └── ChatManager (runner/manager.py)
│   ├── ProviderManager
│   └── LocalModelManager
├── Routers (routers/)
│   └── Agent-scoped and global API endpoints
├── AuthMiddleware (auth.py)
└── Static file serving (SPA)
```

---

## 核心组件

### 1. FastAPI 应用 (`_app.py`)

**文件**: `src/copaw/app/_app.py`

**职责**:
- FastAPI 应用工厂，带生命周期管理
- 中间件配置（CORS、认证、Agent 上下文）
- Web Console SPA 的静态文件服务
- API 端点的路由注册

**关键类**:

| 类 | 描述 |
|-------|-------------|
| `DynamicMultiAgentRunner` | 根据 `X-Agent-Id` 头或活动 Agent 配置将请求路由到正确的工作区运行器 |

**关键函数**:

| 函数 | 用途 |
|----------|---------|
| `lifespan(app)` | 异步上下文管理器，处理启动/关闭：迁移、MultiAgentManager 初始化、提供商设置 |
| `read_root()` | 提供 SPA index.html |
| `get_version()` | 返回 CoPaw 版本 |

**API 路由挂载**:
- `/api/*` - 主 API 路由器
- `/api/agents/{agentId}/*` - Agent 范围路由器
- `/api/agent/*` - AgentApp 路由器（AgentScope 集成）
- `/voice/*` - 语音通道端点（Twilio）

---

### 2. 多 Agent 管理

#### `MultiAgentManager` (`multi_agent_manager.py`)

**文件**: `src/copaw/app/multi_agent_manager.py`

**职责**:
- 多个 Agent 工作区的集中管理
- 工作区实例的延迟加载
- 零停机热重载，支持优雅任务完成
- 生命周期管理（启动、停止、重载）

**关键方法**:

| 方法 | 描述 |
|--------|-------------|
| `get_agent(agent_id)` | 带延迟加载获取工作区 |
| `reload_agent(agent_id)` | 零停机重载：创建新实例，原子交换，优雅停止旧实例 |
| `start_all_configured_agents()` | 启动时并发启动所有启用的 Agent |
| `stop_all()` | 关闭时停止所有 Agent |

**设计模式**: 零停机重载模式确保:
1. 新实例在锁外创建并启动
2. 在锁内原子交换（最小阻塞）
3. 旧实例优雅停止（等待任务完成）

#### `Workspace` (`workspace/workspace.py`)

**文件**: `src/copaw/app/workspace/workspace.py`

**职责**:
- 封装完整的独立 Agent 运行时
- 通过 ServiceManager 管理服务生命周期
- 提供属性访问所有服务

**关键属性**:
- `runner` - 处理请求的 AgentRunner
- `memory_manager` - 会话内存
- `mcp_manager` - MCP 客户端管理器
- `chat_manager` - 聊天历史管理
- `channel_manager` - 通信通道
- `cron_manager` - 定时任务
- `task_tracker` - 后台任务跟踪

**生命周期**:
- `start()` - 加载配置，通过 ServiceManager 启动所有服务
- `stop(final)` - 停止服务（如 `final=False` 用于重载则跳过可复用服务）

---

### 3. 通道系统

#### `BaseChannel` (`channels/base.py`)

**文件**: `src/copaw/app/channels/base.py`

**职责**:
- 定义通道接口的抽象基类
- 带防抖和批处理的消息处理
- 策略执行（白名单、提及要求）
- 与 TaskTracker 集成支持取消

**关键抽象方法**:
```python
@classmethod
def from_env(cls, process, on_reply_sent) -> "BaseChannel":
    """从环境变量创建通道"""

@classmethod
def from_config(cls, process, config, ...) -> "BaseChannel":
    """从配置对象创建通道"""

def build_agent_request_from_native(self, native_payload) -> AgentRequest:
    """将通道原生负载转换为 AgentRequest"""
```

**关键方法**:

| 方法 | 描述 |
|--------|-------------|
| `consume_one(payload)` | 带时间防抖处理一个负载 |
| `resolve_session_id(sender_id, meta)` | 将发送者映射到会话 ID |
| `send_content_parts(to_handle, parts, meta)` | 向用户发送内容部分 |
| `send_event(user_id, session_id, event, meta)` | 向通道发送事件 |
| `merge_native_items(items)` | 合并批量消息 |
| `_check_allowlist(sender_id, is_group)` | 执行访问策略 |

**配置属性**:
- `dm_policy` / `group_policy` - 访问控制（"open" 或 "allowlist"）
- `allow_from` - 允许的用户 ID 列表
- `require_mention` - 群组中需要提及 Bot
- `show_tool_details` / `filter_tool_messages` / `filter_thinking` - 输出过滤

#### `ChannelManager` (`channels/manager.py`)

**文件**: `src/copaw/app/channels/manager.py`

**职责**:
- 拥有所有通道的统一队列系统
- 管理通道生命周期（启动/停止）
- 通过优先级队列路由消息
- 处理热重载期间的通道替换

**关键方法**:

| 方法 | 描述 |
|--------|-------------|
| `from_config(process, config, ...)` | 从配置创建通道的工厂 |
| `enqueue(channel_id, payload)` | 线程安全入队（从同步上下文调用） |
| `start_all()` | 启动所有通道和队列管理器 |
| `replace_channel(new_channel)` | 热重载单个通道 |
| `send_text(channel, user_id, session_id, text)` | 向特定通道发送文本 |
| `send_event(channel, user_id, session_id, event)` | 向通道发送事件 |

#### 通道注册表 (`channels/registry.py`)

**文件**: `src/copaw/app/channels/registry.py`

**内置通道**:

| 通道 | 类 | 描述 |
|---------|-------|-------------|
| `console` | `ConsoleChannel` | 终端输出（必需） |
| `telegram` | `TelegramChannel` | Telegram Bot API |
| `dingtalk` | `DingTalkChannel` | 钉钉 Stream API |
| `feishu` | `FeishuChannel` | 飞书/Lark |
| `discord` | `DiscordChannel` | Discord Bot |
| `qq` | `QQChannel` | QQ Bot |
| `mqtt` | `MQTTChannel` | MQTT 协议 |
| `imessage` | `IMessageChannel` | iMessage |
| `matrix` | `MatrixChannel` | Matrix 协议 |
| `voice` | `VoiceChannel` | Twilio Voice |
| `wecom` | `WecomChannel` | 企业微信 |
| `xiaoyi` | `XiaoYiChannel` | 小意 |
| `weixin` | `WeixinChannel` | 微信 |

**自定义通道支持**:
- 将 Python 模块放在 `CUSTOM_CHANNELS_DIR`
- 模块必须定义继承 `BaseChannel` 的类
- 类必须有 `channel` 属性作为唯一标识符

---

### 4. 通道实现

#### `ConsoleChannel` (`channels/console/channel.py`)

**文件**: `src/copaw/app/channels/console/channel.py`

- 终端输出的轻量级通道
- 使用 ANSI 颜色漂亮打印 Agent 响应
- 通过 `console_push_store` 向前端推送消息
- 使用 `stream_one()` 进行 SSE 格式的事件流

#### `TelegramChannel` (`channels/telegram/channel.py`)

**文件**: `src/copaw/app/channels/telegram/channel.py`

- 通过轮询的 Telegram Bot API
- 支持文本、图像、视频、音频、文档
- 带可配置超时的打字指示器
- 群组提及支持，可选 `require_mention`
- HTML 格式化，回退到纯文本
- 带指数退避的自动重连

#### `DingTalkChannel` (`channels/dingtalk/channel.py`)

**文件**: `src/copaw/app/channels/dingtalk/channel.py`

- 企业消息的钉钉 Stream API
- AI 卡片支持流式响应
- 会话 webhook 存储，用于主动消息
- Markdown 和卡片模板支持
- 通过 message_id 跟踪的消息去重

---

### 5. 队列管理

#### `UnifiedQueueManager` (`channels/unified_queue_manager.py`)

**文件**: `src/copaw/app/channels/unified_queue_manager.py`

**职责**:
- 每会话、每优先级的队列隔离
- 按需消费者创建（无固定工作池）
- 自动空闲队列清理
- 监控的指标收集

**QueueKey 结构**:
```python
QueueKey = Tuple[channel_id, session_id, priority_level]
```

**优先级级别**:

| 级别 | 名称 | 用途 |
|-------|------|----------|
| 0 | critical | 控制命令（`/stop`） |
| 10 | high | 状态命令（`/status`, `/daemon`） |
| 20 | normal | 常规消息（默认） |
| 30 | low | 批量任务 |

#### `CommandRegistry` (`channels/command_registry.py`)

**文件**: `src/copaw/app/channels/command_registry.py`

**职责**:
- 将命令前缀映射到优先级级别
- 检测控制命令以立即处理
- 可扩展自定义优先级级别

---

### 6. Runner 系统

#### `AgentRunner` (`runner/runner.py`)

**文件**: `src/copaw/app/runner/runner.py`

**职责**:
- 通过 AgentScope 集成处理 Agent 请求
- 带持久化的会话状态管理
- 工具守卫审批处理
- 控制命令的命令分发
- 聊天自动注册

**关键方法**:

| 方法 | 描述 |
|--------|-------------|
| `query_handler(msgs, request)` | 主查询处理 - 生成 `(Msg, is_last)` 元组 |
| `init_handler()` | 加载环境，初始化会话 |
| `_resolve_pending_approval(session_id, query)` | 处理待决的工具守卫审批 |

#### `ChatManager` (`runner/manager.py`)

**文件**: `src/copaw/app/runner/manager.py`

**职责**:
- 聊天历史持久化（JSON 仓库）
- 从消息自动注册聊天
- 聊天元数据更新

---

### 7. MCP 集成

#### `MCPClientManager` (`mcp/manager.py`)

**文件**: `src/copaw/app/mcp/manager.py`

**职责**:
- MCP 工具客户端的生命周期管理
- 客户端配置的热重载支持
- 支持 StdIO 和 HTTP 传输

**关键方法**:

| 方法 | 描述 |
|--------|-------------|
| `init_from_config(config)` | 从 MCP 配置初始化客户端 |
| `get_clients()` | 返回已连接客户端列表 |
| `replace_client(key, config)` | 热重载客户端 |
| `close_all()` | 优雅关闭 |

#### `MCPConfigWatcher` (`mcp/watcher.py`)

- MCP 配置变更的文件系统监视器
- 文件修改时触发客户端重载

---

### 8. Cron 系统

#### `CronManager` (`crons/manager.py`)

**文件**: `src/copaw/app/crons/manager.py`

**职责**:
- 使用 APScheduler 的定时作业管理
- 支持 cron 表达式和间隔
- 作业状态跟踪（上次运行、状态、错误）
- 心跳调度

**关键方法**:

| 方法 | 描述 |
|--------|-------------|
| `start()` | 启动调度器并从仓库加载作业 |
| `create_or_replace_job(spec)` | 创建或更新作业 |
| `run_job(job_id)` | 触发立即作业执行 |
| `reschedule_heartbeat()` | 从配置更新心跳调度 |

#### `CronExecutor` (`crons/executor.py`)

**文件**: `src/copaw/app/crons/executor.py`

**任务类型**:
- `text` - 发送固定文本消息
- `agent` - 运行 Agent 查询并发送响应

---

### 9. 认证

#### `AuthMiddleware` (`auth.py`)

**文件**: `src/copaw/app/auth.py`

**特性**:
- 单用户设计，带密码哈希（加盐 SHA-256）
- HMAC 签名令牌（无外部 JWT 依赖）
- 令牌有效期: 7 天
- 从环境变量自动注册，用于部署
- 本地主机绕过，用于 CLI 访问

**公开路径**:
- `/api/auth/login`, `/api/auth/status`, `/api/auth/register`
- `/api/version`, `/api/settings/language`
- 静态资源（`/assets/*`, `/logo.png` 等）

---

### 10. 服务管理

#### `ServiceManager` (`workspace/service_manager.py`)

**文件**: `src/copaw/app/workspace/service_manager.py`

**职责**:
- 通过 `ServiceDescriptor` 的声明式服务注册
- 优先级驱动的启动顺序
- 可能的并发初始化
- 热重载期间的服务复用
- 反向优先级关闭

**ServiceDescriptor 属性**:

| 属性 | 描述 |
|-----------|-------------|
| `name` | 唯一服务标识符 |
| `service_class` | 要实例化的类 |
| `init_args` | 返回初始化 kwargs 的可调用对象 |
| `post_init` | 创建后的设置 Hook |
| `start_method` / `stop_method` | 生命周期方法名 |
| `reusable` | 重载期间可复用 |
| `priority` | 启动顺序（越小越早） |
| `concurrent_init` | 可并行初始化 |

---

### 11. API 路由器

**文件**: `src/copaw/app/routers/__init__.py`

**可用路由器**:

| 路由器 | 前缀 | 用途 |
|--------|--------|---------|
| `agents_router` | `/api/agents` | 多 Agent 管理 |
| `agent_router` | `/api/agent` | 单 Agent 操作 |
| `config_router` | `/api/config` | 配置管理 |
| `console_router` | `/api/console` | Console 通道 API |
| `cron_router` | `/api/cron` | 定时作业 |
| `local_models_router` | `/api/local-models` | 本地模型管理 |
| `mcp_router` | `/api/mcp` | MCP 客户端管理 |
| `messages_router` | `/api/messages` | 消息历史 |
| `providers_router` | `/api/providers` | LLM 提供商 |
| `runner_router` | `/api/runner` | Runner 操作 |
| `skills_router` | `/api/skills` | 技能管理 |
| `tools_router` | `/api/tools` | 工具管理 |
| `workspace_router` | `/api/workspace` | 工作区操作 |
| `envs_router` | `/api/envs` | 环境变量 |
| `token_usage_router` | `/api/token-usage` | 令牌使用统计 |
| `auth_router` | `/api/auth` | 认证 |
| `files_router` | `/api/files` | 文件操作 |
| `settings_router` | `/api/settings` | 设置管理 |

**Agent 范围路由器**:
- 在 `/api/agents/{agentId}/` 下挂载现有路由器
- 使用 `AgentContextMiddleware` 设置当前 Agent
- 在多 Agent 设置中启用每 Agent 隔离

---

### 12. 消息渲染

#### `MessageRenderer` (`channels/renderer.py`)

**文件**: `src/copaw/app/channels/renderer.py`

**职责**:
- 将 `Message` 对象转换为可发送的内容部分
- 应用通道特定的样式（Markdown、Emoji、代码围栏）
- 过滤工具消息和思考块

**RenderStyle 选项**:
```python
@dataclass
class RenderStyle:
    show_tool_details: bool = True
    supports_markdown: bool = True
    supports_code_fence: bool = True
    use_emoji: bool = True
    filter_tool_messages: bool = False
    filter_thinking: bool = False
    internal_tools: frozenset = frozenset()
```

---

### 13. 支撑模块

#### `agent_context.py`

**文件**: `src/copaw/app/agent_context.py`

**职责**:
- 当前 Agent ID 的上下文变量管理
- 从请求头/状态解析 Agent

**关键函数**:
- `get_agent_for_request(request, agent_id)` - 为请求解析工作区
- `get_current_agent_id()` - 从上下文获取 Agent ID
- `set_current_agent_id(agent_id)` - 设置上下文变量

#### `agent_config_watcher.py`

**文件**: `src/copaw/app/agent_config_watcher.py`

- Agent 配置变更的文件监视器
- 配置修改时触发工作区重载

#### `migration.py`

**文件**: `src/copaw/app/migration.py`

- 旧版工作区迁移到多 Agent 结构
- 默认 Agent 创建
- QA Agent 初始化

---

## 数据流

### 消息处理流程

```
1. 用户通过通道发送消息（Telegram, 钉钉等）
2. 通道接收原生负载并转换为 dict:
   {
     "channel_id": "telegram",
     "sender_id": "user123",
     "content_parts": [TextContent(...), ImageContent(...)],
     "meta": {"chat_id": "456", "is_group": false}
   }
3. 通道调用 self._enqueue(native_dict)
4. ChannelManager.enqueue() 路由到 UnifiedQueueManager
5. UnifiedQueueManager 按（通道, 会话, 优先级）创建/获取队列
6. 消费者循环处理队列:
   a. 从队列抽取批量
   b. 如需要合并负载
   c. 调用 channel._consume_one_request(merged)
7. 通道转换为 AgentRequest
8. 通过 AgentRunner.stream_query() 处理
9. 通过 TaskTracker 流式返回事件
10. 通道通过 send_content_parts() 发送响应
```

### 热重载流程

```
1. 检测到配置文件变更
2. 调用 MultiAgentManager.reload_agent(agent_id)
3. 用新配置创建新 Workspace
4. 可复用服务转移（memory_manager, chat_manager）
5. 新工作区完全启动
6. 原子交换: self.agents[agent_id] = new_instance
7. 旧工作区优雅停止:
   - 活动任务允许完成（最多 60 秒）
   - 然后强制停止
```

---

## 设计模式

1. **抽象工厂模式** - `BaseChannel.from_config()` / `from_env()`
2. **策略模式** - 不同通道实现，统一接口
3. **观察者模式** - 配置变更的文件监视器
4. **优先级队列模式** - `UnifiedQueueManager` 带优先级级别
5. **服务定位器模式** - `ServiceManager` 用于依赖解析
6. **上下文管理器模式** - 生命周期管理、会话处理
7. **防抖模式** - `BaseChannel` 中的消息批处理
8. **零停机重载** - 带优雅关闭的原子交换
9. **协议模式** - `ChannelMessageConverter` 用于类型检查

---

## 公共 API 契约

### 通道接口（用于实现自定义通道）

```python
class BaseChannel(ABC):
    channel: str  # 唯一通道标识符

    @classmethod
    def from_config(cls, process, config, ...) -> "BaseChannel":
        """从配置的工厂方法"""

    def build_agent_request_from_native(self, payload) -> AgentRequest:
        """将原生负载转换为 AgentRequest"""

    async def send(self, to_handle: str, text: str, meta: dict) -> None:
        """发送文本消息"""

    async def send_content_parts(self, to_handle, parts, meta) -> None:
        """发送内容部分（文本、图像等）"""

    async def start(self) -> None:
        """启动通道（由管理器调用）"""

    async def stop(self) -> None:
        """停止通道（由管理器调用）"""
```

### 自定义通道注册

```python
# 在 custom_channels/my_channel.py
from copaw.app.channels.base import BaseChannel

class MyChannel(BaseChannel):
    channel = "my_channel"

    @classmethod
    def from_config(cls, process, config, **kwargs):
        return cls(process=process, enabled=config.enabled, ...)

    # 实现必需方法...

# 可选: 注册额外的 HTTP 路由
def register_app_routes(app):
    @app.get("/api/my-channel/webhook")
    async def webhook_handler():
        ...
```

---

## 关键文件位置

| 组件 | 文件路径 |
|-----------|-----------|
| FastAPI App | `src/copaw/app/_app.py` |
| 多 Agent 管理器 | `src/copaw/app/multi_agent_manager.py` |
| Workspace | `src/copaw/app/workspace/workspace.py` |
| 基通道 | `src/copaw/app/channels/base.py` |
| 通道管理器 | `src/copaw/app/channels/manager.py` |
| 通道注册表 | `src/copaw/app/channels/registry.py` |
| 队列管理器 | `src/copaw/app/channels/unified_queue_manager.py` |
| Agent Runner | `src/copaw/app/runner/runner.py` |
| MCP 管理器 | `src/copaw/app/mcp/manager.py` |
| Cron 管理器 | `src/copaw/app/crons/manager.py` |
| 认证中间件 | `src/copaw/app/auth.py` |
| 服务管理器 | `src/copaw/app/workspace/service_manager.py` |