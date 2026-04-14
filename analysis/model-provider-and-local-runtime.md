# 模型、Provider 与本地运行时

本文档整理模型接入层，包括云 Provider、本地模型、MCP、数据库和运行时依赖。

## Provider 子系统

| 文件 | 说明 |
|------|------|
| `src/swe/providers/provider.py` | Provider 抽象基类 |
| `src/swe/providers/provider_manager.py` | Provider 装配与租户级实例管理 |
| `src/swe/providers/models.py` | Provider 相关数据模型 |
| `src/swe/providers/chat_model_registry.py` | 模型注册表 |
| `src/swe/providers/retry_chat_model.py` | 重试封装 |
| `src/swe/providers/rate_limiter.py` | 调用节流 |
| `src/swe/providers/capability_baseline.py` | 能力基线定义 |
| `src/swe/providers/openai_provider.py` | OpenAI Provider |
| `src/swe/providers/openai_chat_model_compat.py` | OpenAI 兼容层 |
| `src/swe/providers/anthropic_provider.py` | Anthropic Provider |
| `src/swe/providers/gemini_provider.py` | Gemini Provider |
| `src/swe/providers/ollama_provider.py` | Ollama Provider |
| `src/swe/providers/kimi_chat_model.py` | Kimi 相关适配 |
| `src/swe/providers/multimodal_prober.py` | 多模态能力探测 |

## 本地模型子系统

| 文件 | 说明 |
|------|------|
| `src/swe/local_models/manager.py` | 本地模型管理入口 |
| `src/swe/local_models/model_manager.py` | 模型元数据与生命周期 |
| `src/swe/local_models/download_manager.py` | 下载流程管理 |
| `src/swe/local_models/llamacpp.py` | llama.cpp 后端集成 |
| `src/swe/local_models/tag_parser.py` | 标签解析 |

## 外围运行依赖

| 区域 | 关键文件 | 说明 |
|------|----------|------|
| MCP | `src/swe/app/mcp/manager.py`, `src/swe/app/mcp/watcher.py` | MCP 客户端管理与配置监视 |
| 数据库 | `src/swe/database/config.py`, `src/swe/database/connection.py` | MySQL 连接配置与连接管理 |
| 路由入口 | `src/swe/app/routers/providers.py`, `src/swe/app/routers/local_models.py`, `src/swe/app/routers/mcp.py` | 对外暴露 Provider / Local Model / MCP API |

## 运行关系

```text
Agent / Runner
  -> model_factory.py
  -> provider_manager.py
  -> specific provider or local model backend
  -> token/tracing wrappers as needed
```

## 关联功能域

- Agent 执行内核: [agent-and-orchestration.md](agent-and-orchestration.md)
- 配置和租户隔离: [config-and-tenant-isolation.md](config-and-tenant-isolation.md)
