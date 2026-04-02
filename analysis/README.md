# CoPaw 后端代码分析文档索引

本文件夹包含 CoPaw 项目 `src/copaw/` 后端代码的详细分析文档。

## 文档列表

| 文档 | 模块 | 描述 |
|------|------|------|
| [01-agents-module.md](01-agents-module.md) | `agents/` | Agent 核心实现：ReAct 模式、工具管理、技能系统、内存管理、安全守卫 |
| [02-app-module.md](02-app-module.md) | `app/` | FastAPI 应用层：多 Agent 管理、通道系统、MCP 集成、定时任务 |
| [03-config-module.md](03-config-module.md) | `config/` | 配置管理：Pydantic 模型、热重载、多 Agent 配置隔离 |
| [04-cli-module.md](04-cli-module.md) | `cli/` | 命令行接口：延迟加载命令、交互式提示 |
| [05-other-modules.md](05-other-modules.md) | 其他模块 | 环境存储、本地模型、提供商、安全、令牌跟踪、分词器、隧道、工具 |

---

## 项目架构概览

```
src/copaw/
├── agents/           # 核心 Agent 实现
│   ├── react_agent.py      # CoPawAgent (ReActAgent 子类)
│   ├── tool_guard_mixin.py # 工具调用安全拦截
│   ├── command_handler.py  # 系统命令处理
│   ├── model_factory.py    # LLM 模型工厂
│   ├── prompt.py           # 系统提示构建
│   ├── skills_manager.py   # 技能加载管理
│   ├── tools/              # 内置工具集
│   ├── memory/             # 内存管理器
│   └── hooks/              # 预推理 Hooks
│
├── app/              # FastAPI 应用层
│   ├── _app.py             # FastAPI 应用工厂
│   ├── multi_agent_manager.py  # 多 Agent 管理
│   ├── workspace/          # 工作区封装
│   ├── channels/           # 通道系统
│   │   ├── base.py         # BaseChannel 抽象类
│   │   ├── manager.py      # ChannelManager
│   │   ├── unified_queue_manager.py  # 统一队列
│   │   └── [各通道实现]
│   ├── mcp/                # MCP 客户端管理
│   ├── crons/              # 定时任务
│   ├── runner/             # AgentRunner
│   ├── routers/            # API 路由
│   └── auth.py             # 认证中间件
│
├── config/           # 配置管理
│   ├── config.py           # Pydantic 配置模型
│   ├── utils.py            # 配置加载/保存
│   ├── context.py          # 上下文变量
│   └── timezone.py         # 时区检测
│
├── cli/              # 命令行接口
│   ├── main.py             # LazyGroup CLI
│   ├── utils.py            # 交互式提示
│   └── [各命令模块]
│
├── envs/             # 环境变量存储
├── local_models/     # 本地模型管理
├── providers/        # LLM 提供商管理
├── security/         # 安全子系统
├── token_usage/      # 令牌使用跟踪
├── tokenizer/        # 分词工具
├── tunnel/           # Cloudflare 隧道
├── utils/            # 通用工具函数
└── constant.py       # 常量定义
```

---

## 核心设计模式

| 模式 | 应用场景 |
|------|----------|
| **Mixin** | `ToolGuardMixin` 重写 Agent 方法 |
| **抽象工厂** | `BaseChannel.from_config()` |
| **策略** | 通道实现、提供商实现 |
| **观察者** | 配置变更文件监视器 |
| **单例** | `ProviderManager`, `TokenUsageManager` |
| **外观** | `LocalModelManager` |
| **Hook** | `BootstrapHook`, `MemoryCompactionHook` |
| **零停机重载** | 多 Agent 工作区交换 |
| **优先级队列** | `UnifiedQueueManager` |

---

## 关键数据流

### 用户消息处理流程

```
用户消息 → 通道接收 → ChannelManager.enqueue()
    → UnifiedQueueManager → 消费者循环
    → BaseChannel.consume_one() → AgentRequest
    → AgentRunner.stream_query() → CoPawAgent.reply()
    → ReAct 循环 → 工具执行 → 响应流式返回
```

### 工具安全检查流程

```
工具调用 → ToolGuardMixin._acting()
    → _decide_guard_action()
        → 检查拒绝列表
        → 检查预审批
        → 运行守卫
    → 执行动作 (拒绝/审批/执行)
```

---

## 扩展指南

### 添加自定义通道

1. 在 `CUSTOM_CHANNELS_DIR` 创建 Python 模块
2. 定义继承 `BaseChannel` 的类
3. 实现 `from_config()`, `build_agent_request_from_native()` 等方法
4. 设置 `channel` 属性为唯一标识符

### 添加自定义工具

1. 在 `src/copaw/agents/tools/` 添加工具函数
2. 使用 `@tool` 装饰器注册
3. 在 `ToolsConfig` 中添加默认配置

### 添加自定义提供商

1. 在 `src/copaw/providers/` 创建提供商类
2. 继承 `Provider` 抽象基类
3. 实现必要方法
4. 在 `ProviderManager` 中注册