# CoPaw Agents 模块分析文档

## 概述

`src/copaw/agents/` 模块是 CoPaw 的核心 Agent 实现，提供基于 ReAct 模式的 AI Agent，集成了工具管理、技能系统、内存管理和安全防护机制。

**位置**: `/home/yishixiang/git/CoPaw/src/copaw/agents/`

---

## 公共 API

模块通过 `__init__.py` 导出两个主要入口点（延迟加载）：

| 导出项 | 描述 |
|--------|------|
| `CoPawAgent` | 主 Agent 类，继承自 ReActAgent |
| `create_model_and_formatter` | 创建模型/格式化器对的工厂函数 |

**使用示例**:
```python
from copaw.agents import CoPawAgent, create_model_and_formatter

# 使用配置创建 Agent
agent = CoPawAgent(agent_config=agent_config)

# 或单独创建模型/格式化器
model, formatter = create_model_and_formatter(agent_id="my_agent")
```

---

## 核心类

### 1. CoPawAgent (`react_agent.py`)

**文件**: `src/copaw/agents/react_agent.py`

**继承关系**: `ToolGuardMixin` → `ReActAgent` (来自 agentscope)

**职责**:
- 主 Agent，编排 ReAct（推理 + 行动）循环
- 工具注册和管理（内置工具 + 技能 + MCP 工具）
- 内存管理与自动压缩
- 系统命令处理（`/compact`, `/new`, `/clear` 等）
- 非多模态模型的媒体块过滤
- 首次设置的引导机制
- MCP 客户端恢复与注册

**关键初始化参数**:

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `agent_config` | `AgentProfileConfig` | 完整的 Agent 配置 |
| `env_context` | `str | None` | 系统提示前缀的环境上下文 |
| `enable_memory_manager` | `bool` | 是否启用内存管理器（默认: True） |
| `mcp_clients` | `list[Any] | None` | MCP 工具集成客户端 |
| `memory_manager` | `BaseMemoryManager | None` | 自定义内存管理器实例 |
| `request_context` | `dict[str, str] | None` | 包含 session_id, user_id, channel, agent_id 的上下文 |
| `namesake_strategy` | `NamesakeStrategy` | 处理重名工具的策略（"override", "skip", "raise", "rename"） |
| `workspace_dir` | `Path | None` | 提示文件的工作目录 |

**关键方法**:

| 方法 | 用途 |
|--------|---------|
| `reply(msg)` | 处理用户消息的主入口 |
| `rebuild_sys_prompt()` | 从工作目录文件重建系统提示 |
| `register_mcp_clients()` | 异步注册 MCP 工具客户端 |
| `interrupt(msg)` | 取消当前的回复过程 |
| `_acting(tool_call)` | 带工具守卫拦截的重写 |
| `_reasoning(tool_choice)` | 带媒体过滤的重写 |

**设计模式**:
- **Mixin 模式**: `ToolGuardMixin` 通过 MRO 重写 `_acting` 和 `_reasoning`
- **工厂模式**: 使用 `create_model_and_formatter()` 创建模型
- **Hook 模式**: 预推理 Hook 用于引导和内存压缩
- **策略模式**: `namesake_strategy` 处理工具名冲突

---

### 2. ToolGuardMixin (`tool_guard_mixin.py`)

**文件**: `src/copaw/agents/tool_guard_mixin.py`

**职责**:
- 敏感工具调用的安全拦截
- 守卫工具的审批流程（拒绝/批准/等待）
- 对拒绝列表中工具的自动拒绝
- 基于会话的预审批消费
- 批准后的强制工具调用重放

**关键方法**:

| 方法 | 用途 |
|--------|---------|
| `_acting(tool_call)` | 执行前拦截工具调用 |
| `_reasoning(tool_choice)` | 等待审批时的短路处理 |
| `_decide_guard_action(tool_call)` | 决定守卫动作（在锁下运行） |
| `_execute_guard_action(action, tool_call)` | 执行决定的动作 |
| `_consume_preapproval(tool_name, tool_input)` | 检查并消费预审批令牌 |

**守卫动作**:

| 动作 | 描述 |
|--------|-------------|
| `auto_denied` | 工具在拒绝列表中，直接阻止 |
| `preapproved` | 预审批令牌已消费，立即执行 |
| `needs_approval` | 检测到风险，进入审批流程 |

---

### 3. CommandHandler (`command_handler.py`)

**文件**: `src/copaw/agents/command_handler.py`

**职责**:
- 处理会话管理的系统命令
- 内存压缩、清除和历史操作

**支持的命令**:

| 命令 | 描述 |
|---------|-------------|
| `/compact` | 将当前消息压缩为摘要 |
| `/new` | 启动新会话并后台生成摘要 |
| `/clear` | 清除所有历史和摘要 |
| `/history` | 显示格式化的会话历史 |
| `/compact_str` | 显示当前压缩摘要 |
| `/await_summary` | 等待所有后台摘要任务 |
| `/message <index>` | 查看指定索引的消息 |
| `/dump_history` | 保存消息到 JSONL 文件 |
| `/load_history` | 从 JSONL 文件加载消息 |
| `/long_term_memory` | 显示长期记忆内容 |

---

### 4. RoutingChatModel (`routing_chat_model.py`)

**文件**: `src/copaw/agents/routing_chat_model.py`

**职责**:
- 在本地和云端模型端点之间路由 LLM 调用
- 基于策略的路由决策

**关键类**:

| 类 | 用途 |
|-------|---------|
| `RoutingChatModel` | 在端点间路由的 ChatModelBase |
| `RoutingPolicy` | 决定使用哪个端点 |
| `RoutingDecision` | 包含路由选择和原因 |
| `RoutingEndpoint` | 包含 provider/model/formatter 的冻结数据类 |

---

## 内存管理 (`memory/`)

### BaseMemoryManager (`base_memory_manager.py`)

**文件**: `src/copaw/agents/memory/base_memory_manager.py`

**所有内存管理器后端的抽象接口**:

| 抽象方法 | 用途 |
|------------------|---------|
| `start()` | 启动内存管理器生命周期 |
| `close()` | 关闭并清理 |
| `compact_tool_result(**kwargs)` | 截断大型工具输出 |
| `check_context(**kwargs)` | 检查是否需要压缩 |
| `compact_memory(messages, previous_summary)` | 将消息压缩为摘要 |
| `summary_memory(messages)` | 生成综合摘要 |
| `memory_search(query, max_results, min_score)` | 在记忆中进行语义搜索 |
| `get_in_memory_memory()` | 获取内存中的记忆对象 |

**具体方法**:

| 方法 | 用途 |
|--------|---------|
| `add_async_summary_task(messages)` | 添加后台摘要任务 |
| `await_summary_tasks()` | 等待所有摘要任务 |

---

### ReMeLightMemoryManager (`reme_light_memory_manager.py`)

**文件**: `src/copaw/agents/memory/reme_light_memory_manager.py`

**包装 ReMeLight 库的实现**:

- 嵌入配置优先级: config > 环境变量
- 后端选择: `MEMORY_STORE_BACKEND` 环境变量（auto/local/chroma）
- Windows 默认使用 `local` 后端（SQLite 兼容性）
- 通过嵌入进行向量搜索，可选全文搜索

---

### AgentMdManager (`agent_md_manager.py`)

**文件**: `src/copaw/agents/memory/agent_md_manager.py`

**职责**:
- 在工作目录和内存目录中读写 Markdown 文件
- 列出 Markdown 文件及其元数据（大小、时间戳）

---

## Hooks (`hooks/`)

### BootstrapHook (`bootstrap.py`)

**文件**: `src/copaw/agents/hooks/bootstrap.py`

**用途**: 当 `BOOTSTRAP.md` 存在时提供首次设置引导

**行为**:
- 在首次用户交互时检查 `BOOTSTRAP.md`
- 在第一条用户消息前添加语言特定的引导
- 创建 `.bootstrap_completed` 标志防止再次触发

---

### MemoryCompactionHook (`memory_compaction.py`)

**文件**: `src/copaw/agents/hooks/memory_compaction.py`

**用途**: 当接近上下文限制时自动压缩

**行为**:
- 在推理前监控令牌计数
- 保留系统提示和最近消息
- 超过阈值时触发压缩
- 启动后台摘要任务
- 向用户打印状态消息

---

## 技能管理

### SkillsManager (`skills_manager.py`)

**文件**: `src/copaw/agents/skills_manager.py`

**关键函数**:

| 函数 | 用途 |
|----------|---------|
| `get_builtin_skills_dir()` | 打包的内置技能路径 |
| `get_skill_pool_dir()` | 本地共享技能池目录 |
| `get_workspace_skills_dir(workspace_dir)` | 工作区技能源目录 |
| `resolve_effective_skills(workspace_dir, channel)` | 确定通道的有效技能 |
| `ensure_skills_initialized(workspace_dir)` | 初始化技能注册表 |
| `reconcile_pool_manifest()` | 同步池注册表与文件系统 |
| `reconcile_workspace_manifest(workspace_dir)` | 同步工作区注册表 |
| `import_builtin_skills(skill_names)` | 将内置技能导入池 |
| `apply_skill_config_env_overrides(workspace_dir, channel)` | 技能配置环境变量的上下文管理器 |

**关键类**:

| 类 | 用途 |
|-------|---------|
| `SkillInfo` | 技能详情（名称、描述、版本、内容、来源） |
| `SkillRequirements` | 系统管理的要求（bins, envs） |
| `SkillConflictError` | 导入/保存冲突时抛出 |
| `SkillService` | 工作区技能 CRUD 操作 |
| `SkillPoolService` | 池技能 CRUD 操作 |

---

### SkillsHub (`skills_hub.py`)

**文件**: `src/copaw/agents/skills_hub.py`

**用途**: 远程技能中心（ClawHub）集成的客户端

**关键类**:

| 类 | 用途 |
|-------|---------|
| `HubSkillResult` | 中心的技能搜索结果 |
| `HubInstallResult` | 安装结果 |
| `SkillImportCancelled` | 用户取消导入的异常 |

---

## 工具 (`tools/`)

### 内置工具 (`__init__.py`)

**文件**: `src/copaw/agents/tools/__init__.py`

| 工具 | 描述 |
|------|-------------|
| `execute_shell_command` | 执行 Shell 命令（带超时） |
| `read_file` | 读取文件（支持行范围） |
| `write_file` | 创建/覆盖文件 |
| `edit_file` | 文件内查找替换 |
| `append_file` | 追加到文件 |
| `grep_search` | 文件内正则搜索 |
| `glob_search` | Glob 模式文件搜索 |
| `send_file_to_user` | 向用户界面发送文件 |
| `desktop_screenshot` | 捕获桌面截图 |
| `view_image` | 查看图像文件（多模态） |
| `view_video` | 查看视频文件（多模态） |
| `browser_use` | 浏览器自动化 |
| `create_memory_search_tool` | 创建内存搜索工具 |
| `get_current_time` | 获取当前时间戳 |
| `set_user_timezone` | 设置用户时区 |
| `get_token_usage` | 获取令牌使用统计 |

---

## 模型工厂 (`model_factory.py`)

**文件**: `src/copaw/agents/model_factory.py`

**用途**: 创建聊天模型和格式化器的统一工厂

**关键函数**:

| 函数 | 用途 |
|----------|---------|
| `create_model_and_formatter(agent_id)` | 创建模型/格式化器对 |
| `_create_formatter_instance(chat_model_class)` | 创建增强格式化器 |
| `_create_file_block_support_formatter(base_formatter_class)` | 文件块支持格式化器工厂 |

**格式化器增强**:
- 工具结果中的文件块支持
- 不同提供商的视频块处理
- Anthropic 媒体块格式化
- 思考块保留（reasoning_content）

---

## 提示构建 (`prompt.py`)

**文件**: `src/copaw/agents/prompt.py`

**关键函数**:

| 函数 | 用途 |
|----------|---------|
| `build_system_prompt_from_working_dir(...)` | 从 Markdown 文件构建系统提示 |
| `build_bootstrap_guidance(language)` | 生成引导文本 |
| `build_multimodal_hint()` | 添加多模态能力提示 |
| `get_active_model_supports_multimodal()` | 检查模型多模态支持 |

**PromptBuilder 类**:
- 加载 AGENTS.md, SOUL.md, PROFILE.md（可配置）
- 根据配置过滤心跳部分
- 从文件中剥离 YAML frontmatter

---

## 数据流

### Agent 回复流程

```
用户消息
    │
    ▼
CoPawAgent.reply()
    │
    ├── 处理文件/媒体块
    │
    ├── 检查系统命令（/compact, /new 等）
    │   └── CommandHandler.handle_command()
    │
    ├── 应用技能配置环境覆盖
    │
    ▼
ReActAgent.reply() (父类)
    │
    ├── 预推理 Hooks
    │   ├── BootstrapHook（首次交互）
    │   └── MemoryCompactionHook（上下文满）
    │
    ├── _reasoning() [ToolGuardMixin 重写]
    │   ├── 检查强制工具调用（审批重放）
    │   ├── 检查等待审批
    │   └── 调用模型
    │
    ├── _acting() [ToolGuardMixin 重写]
    │   ├── 检查拒绝工具
    │   ├── 检查预审批
    │   ├── 运行守卫
    │   ├── 如需要进入审批流程
    │   └── 执行工具
    │
    ▼
响应消息
```

### 工具守卫流程

```
工具调用
    │
    ▼
ToolGuardMixin._acting()
    │
    ├── 获取锁
    │
    ├── _decide_guard_action()
    │   ├── 检查是否拒绝 → auto_denied
    │   ├── 检查预审批 → preapproved
    │   ├── 运行守卫 → needs_approval（如有发现）
    │   └── 无发现 → None（透传）
    │
    ├── 释放锁
    │
    ▼
_execute_guard_action()
    │
    ├── auto_denied: 返回阻止消息
    ├── preapproved: 立即执行工具
    ├── needs_approval: 创建待审批，返回等待消息
    └── None: 调用 super()._acting()
```

---

## 设计模式总结

| 模式 | 实现 |
|---------|---------------|
| **Mixin** | `ToolGuardMixin` 通过 MRO 重写 `_acting`/`_reasoning` |
| **工厂** | `create_model_and_formatter()`, `_create_file_block_support_formatter()` |
| **策略** | `namesake_strategy` 处理工具名冲突，路由策略用于模型选择 |
| **Hook** | `BootstrapHook`, `MemoryCompactionHook` 作为预推理回调 |
| **抽象基类** | `BaseMemoryManager` 定义内存后端接口 |
| **组合** | `ReMeLightMemoryManager` 包装 ReMeLight 实例 |
| **上下文管理器** | `apply_skill_config_env_overrides()` 用于技能配置注入 |
| **延迟加载** | `__init__.py` 使用 `__getattr__` 进行延迟导入 |

---

## 关键文件位置

| 组件 | 文件路径 |
|-----------|-----------|
| 主 Agent | `src/copaw/agents/react_agent.py` |
| 工具守卫 | `src/copaw/agents/tool_guard_mixin.py` |
| 命令处理器 | `src/copaw/agents/command_handler.py` |
| 模型工厂 | `src/copaw/agents/model_factory.py` |
| 提示构建器 | `src/copaw/agents/prompt.py` |
| 技能管理器 | `src/copaw/agents/skills_manager.py` |
| 技能中心 | `src/copaw/agents/skills_hub.py` |
| 内存基类 | `src/copaw/agents/memory/base_memory_manager.py` |
| ReMeLight 内存 | `src/copaw/agents/memory/reme_light_memory_manager.py` |
| Bootstrap Hook | `src/copaw/agents/hooks/bootstrap.py` |
| 压缩 Hook | `src/copaw/agents/hooks/memory_compaction.py` |
| 工具包 | `src/copaw/agents/tools/__init__.py` |