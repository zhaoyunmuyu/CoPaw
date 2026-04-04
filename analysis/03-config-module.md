# CoPaw 配置模块分析文档

## 概述

`src/copaw/config/` 模块负责 CoPaw 的所有配置管理，使用 Pydantic 进行配置模型定义，支持热重载、多 Agent 配置隔离和跨平台时区检测。

---

## 模块结构

**位置**: `src/copaw/config/`

| 文件 | 用途 |
|------|---------|
| `__init__.py` | 公共 API 导出 |
| `config.py` | Pydantic 配置模型定义（1366 行） |
| `utils.py` | 配置加载、保存和工具函数 |
| `timezone.py` | 跨平台系统时区检测 |
| `context.py` | 多 Agent 工作区隔离的上下文变量 |

---

## 配置模型

### 根配置 (`Config`)

**文件**: `src/copaw/config/config.py`

`config.json` 的顶层模型：

```python
class Config(BaseModel):
    channels: ChannelConfig          # 所有通道配置
    mcp: MCPConfig                   # MCP 客户端配置
    tools: ToolsConfig               # 内置工具管理
    last_api: LastApiConfig          # 上次 API 主机/端口
    agents: AgentsConfig             # 多 Agent 配置
    last_dispatch: Optional[LastDispatchConfig]  # 上次分发目标
    security: SecurityConfig         # 安全设置
    show_tool_details: bool          # UI 工具输出开关
    user_timezone: str               # IANA 时区（自动检测）
```

---

### 通道配置模型

所有通道配置继承自 `BaseChannelConfig`：

| 字段 | 类型 | 默认值 | 描述 |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | 通道是否活动 |
| `bot_prefix` | `str` | `""` | Bot 命令前缀 |
| `filter_tool_messages` | `bool` | `False` | 过滤用户视图的工具输出 |
| `filter_thinking` | `bool` | `False` | 过滤思考块 |
| `dm_policy` | `Literal["open", "allowlist"]` | `"open"` | 私聊策略 |
| `group_policy` | `Literal["open", "allowlist"]` | `"open"` | 群聊策略 |
| `allow_from` | `List[str]` | `[]` | 白名单 |
| `deny_message` | `str` | `""` | 拒绝访问时的消息 |
| `require_mention` | `bool` | `False` | 群组中需要 @提及 |

**支持的通道类型**：

| 通道 | 模型类 | 关键字段 |
|---------|-------------|------------|
| iMessage | `IMessageChannelConfig` | `db_path`, `poll_sec`, `media_dir` |
| Discord | `DiscordConfig` | `bot_token`, `http_proxy` |
| DingTalk | `DingTalkConfig` | `client_id`, `client_secret`, `card_template_id` |
| Feishu | `FeishuConfig` | `app_id`, `app_secret`, `domain` |
| QQ | `QQConfig` | `app_id`, `client_secret` |
| Telegram | `TelegramConfig` | `bot_token`, `show_typing` |
| MQTT | `MQTTConfig` | `host`, `port`, `subscribe_topic` |
| Console | `ConsoleConfig` | `enabled=True` (默认) |
| Voice | `VoiceChannelConfig` | Twilio 凭证、TTS/STT 提供商 |

---

### 多 Agent 配置

**AgentProfileRef** - 存储在根 `config.json` 的 `agents.profiles`:

```python
class AgentProfileRef(BaseModel):
    id: str                  # 唯一 Agent ID
    workspace_dir: str       # Agent 工作区路径
    enabled: bool = True     # 控制实例加载
```

**AgentProfileConfig** - 存储在 `workspace/agent.json`:

```python
class AgentProfileConfig(BaseModel):
    id: str
    name: str
    description: str
    workspace_dir: str
    channels: Optional[ChannelConfig]
    mcp: Optional[MCPConfig]
    heartbeat: Optional[HeartbeatConfig]
    running: AgentsRunningConfig
    llm_routing: AgentsLLMRoutingConfig
    active_model: Optional[ModelSlotConfig]
    language: str = "zh"
    system_prompt_files: List[str]
    tools: Optional[ToolsConfig]
    security: Optional[SecurityConfig]
```

---

### 运行配置 (`AgentsRunningConfig`)

控制 Agent 执行行为：

| 字段 | 类型 | 默认值 | 描述 |
|-------|------|---------|-------------|
| `max_iters` | `int` | `100` | 最大 ReAct 迭代次数 |
| `llm_retry_enabled` | `bool` | `True` | 自动重试瞬时 LLM 错误 |
| `llm_max_retries` | `int` | `3` | 最大重试次数 |
| `llm_backoff_base` | `float` | `1.0` | 指数退避基数（秒） |
| `llm_backoff_cap` | `float` | `10.0` | 最大退避延迟 |
| `llm_max_concurrent` | `int` | `10` | 并发 LLM 调用限制 |
| `llm_max_qpm` | `int` | `600` | 每分钟查询限制 |
| `max_input_length` | `int` | `131072` | 上下文窗口大小（128K 令牌） |
| `history_max_length` | `int` | `10000` | 最大 /history 输出 |

**嵌套配置**:
- `context_compact` - 令牌计数和压缩阈值
- `tool_result_compact` - 工具输出截断
- `memory_summary` - 内存搜索和索引
- `embedding_config` - 嵌入后端设置

---

### 心跳配置 (`HeartbeatConfig`)

```python
class HeartbeatConfig(BaseModel):
    enabled: bool = False          # 心跳是否活动
    every: str = "6h"              # 间隔（如 "6h", "30m"）
    target: str = "main"           # 目标通道（"main" 或 "last"）
    active_hours: Optional[ActiveHoursConfig]  # 时间窗口限制
```

---

### MCP 配置 (`MCPConfig`)

```python
class MCPClientConfig(BaseModel):
    name: str                      # 客户端名称
    description: str               # 描述
    enabled: bool = True           # 是否活动
    transport: Literal["stdio", "streamable_http", "sse"]
    url: str                       # HTTP/SSE 端点
    headers: Dict[str, str]        # 自定义头
    command: str                   # stdio 命令
    args: List[str]                # 命令参数
    env: Dict[str, str]            # 环境变量
```

---

### 安全配置 (`SecurityConfig`)

```python
class SecurityConfig(BaseModel):
    tool_guard: ToolGuardConfig     # 工具执行守卫
    file_guard: FileGuardConfig     # 文件访问守卫
    skill_scanner: SkillScannerConfig  # 技能安全扫描
```

**工具守卫**:

```python
class ToolGuardConfig(BaseModel):
    enabled: bool = True
    guarded_tools: Optional[List[str]]  # None = 内置默认
    denied_tools: List[str]              # 阻止的工具
    custom_rules: List[ToolGuardRuleConfig]
```

---

## 配置加载与验证

### 主加载函数 (`load_config`)

```python
def load_config(config_path: Optional[Path] = None) -> Config:
    """从文件加载配置。文件缺失时返回默认 Config"""
```

**加载流程**:

1. **文件读取** (`_read_config_data`)
   - 从 `WORKING_DIR/config.json` 读取
   - 使用 `json_repair` 处理常见语法问题
   - 文件不可恢复时创建备份并返回 `None`

2. **路径规范化** (`_normalize_working_dir_bound_paths`)
   - 将旧版 `~/.copaw` 路径重写为当前 `WORKING_DIR`
   - 处理 `workspace_dir` 和 `media_dir` 字段

3. **向后兼容**
   - 迁移 `last_api_host`/`last_api_port` 到 `last_api` 对象
   - 支持降级场景

4. **验证错误恢复**
   - `ValidationError` 时尝试移除问题字段
   - 恢复失败时回退到默认 `Config()`

---

### Agent 配置加载

```python
def load_agent_config(agent_id: str) -> AgentProfileConfig:
    """从 workspace/agent.json 加载 Agent 完整配置"""
```

**流程**:
1. 验证 Agent ID 存在于根 `config.agents.profiles`
2. 从 `workspace_dir/agent.json` 加载
3. `agent.json` 缺失时回退到根配置字段
4. 规范化旧版路径

---

## 热重载机制

### AgentConfigWatcher

轮询 `agent.json` 的修改时间并自动重载变更的配置。

| 组件 | 描述 |
|-----------|-------------|
| 轮询循环 | 每 2 秒检查文件 `mtime` |
| 快照 | 存储 channels 和 heartbeat 配置的哈希 |
| 变更检测 | 比较当前哈希与快照 |
| 重载 | 更新通道管理器并重调度心跳 |

**关键方法**:

| 方法 | 用途 |
|--------|---------|
| `start()` | 初始化快照并开始轮询任务 |
| `stop()` | 取消轮询任务 |
| `_check()` | 比较 mtime，如变更则重载 |
| `_apply_channel_changes()` | 差异并重载修改的通道 |

---

### MCPConfigWatcher

MCP 配置的文件系统监视器，变更时热重载客户端。

---

## 上下文变量（多 Agent 隔离）

```python
# 工作区目录上下文
current_workspace_dir: ContextVar[Path | None]

def get_current_workspace_dir() -> Path | None
def set_current_workspace_dir(workspace_dir: Path | None) -> None

# 工具输出截断上下文
current_recent_max_bytes: ContextVar[int | None]
```

这些上下文变量允许工具函数在多 Agent 环境中正确解析相对路径。

---

## 时区检测

```python
def detect_system_timezone() -> str:
    """返回主机的 IANA 时区名称。回退到 UTC"""
```

**检测方法（按平台）**:

| 平台 | 检测方法 |
|----------|---------------|
| 所有 | Python 运行时, `$TZ` 环境变量 |
| Windows | 注册表: `HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation` |
| macOS | `/etc/localtime` 符号链接, `timedatectl` |
| Linux | `/etc/timezone`, `/etc/localtime` 符号链接, `timedatectl` |

---

## 工具函数

| 函数 | 用途 |
|----------|---------|
| `get_config_path()` | 返回 `WORKING_DIR/config.json` 路径 |
| `save_config(config)` | 写入配置到 JSON 文件 |
| `get_available_channels()` | 返回启用的通道 |
| `is_running_in_container()` | 检测 Docker/Kubernetes 环境 |
| `get_system_default_browser()` | 检测 OS 默认浏览器 |
| `get_heartbeat_config(agent_id)` | 返回有效的心跳配置 |
| `update_last_dispatch(...)` | 持久化上次用户-回复目标 |

---

## 环境变量

| 变量 | 用途 |
|----------|---------|
| `COPAW_WORKING_DIR` | 覆盖工作目录（默认: `~/.copaw`） |
| `COPAW_ENABLED_CHANNELS` | 白名单活动通道 |
| `COPAW_DISABLED_CHANNELS` | 黑名单通道 |
| `COPAW_RUNNING_IN_CONTAINER` | 强制容器检测 |
| `COPAW_LLM_MAX_RETRIES` | LLM 重试次数 |
| `COPAW_LLM_MAX_CONCURRENT` | 并发 LLM 调用 |
| `COPAW_LLM_MAX_QPM` | 每分钟查询限制 |
| `TAVILY_API_KEY` | 自动启用 tavily MCP 客户端 |

---

## 文件位置

| 文件 | 位置 | 内容 |
|------|----------|---------|
| `config.json` | `WORKING_DIR/config.json` | 根配置 |
| `agent.json` | `WORKING_DIR/workspaces/{agent_id}/agent.json` | Agent 特定配置 |
| `HEARTBEAT.md` | `WORKING_DIR/HEARTBEAT.md` | 心跳查询文件 |
| `jobs.json` | `WORKING_DIR/jobs.json` | Cron 作业 |
| `chats.json` | `WORKING_DIR/chats.json` | 聊天历史 |