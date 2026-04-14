# 通道接入、API 与访问界面

本文档整理请求如何进入系统，包括消息通道、HTTP 路由、中间件，以及前端界面目录。

## 后端接入面

| 区域 | 关键路径 | 说明 |
|------|----------|------|
| 通道抽象 | `src/swe/app/channels/base.py`, `src/swe/app/channels/schema.py` | 定义通道模型和基础协议 |
| 通道管理 | `src/swe/app/channels/manager.py`, `src/swe/app/channels/registry.py` | 通道注册与生命周期管理 |
| 队列与渲染 | `src/swe/app/channels/unified_queue_manager.py`, `src/swe/app/channels/renderer.py` | 统一队列与输出格式 |
| 命令注册 | `src/swe/app/channels/command_registry.py` | 通道命令映射 |
| 具体通道 | `src/swe/app/channels/console/channel.py`, `src/swe/app/channels/zhaohu/channel.py` | Console / 招呼等通道实现 |
| 路由层 | `src/swe/app/routers/*.py` | Agent、配置、Provider、文件、消息、技能、Tracing 等 API |
| 中间件 | `src/swe/app/middleware/*.py` | Header 透传、租户身份、租户工作区注入 |
| 认证与审批 | `src/swe/app/auth.py`, `src/swe/app/approvals/service.py` | 身份校验与审批服务 |

## 主要路由文件

- `src/swe/app/routers/agent.py`
- `src/swe/app/routers/agent_scoped.py`
- `src/swe/app/routers/agents.py`
- `src/swe/app/routers/config.py`
- `src/swe/app/routers/envs.py`
- `src/swe/app/routers/files.py`
- `src/swe/app/routers/local_models.py`
- `src/swe/app/routers/mcp.py`
- `src/swe/app/routers/messages.py`
- `src/swe/app/routers/providers.py`
- `src/swe/app/routers/settings.py`
- `src/swe/app/routers/skills.py`
- `src/swe/app/routers/skills_stream.py`
- `src/swe/app/routers/token_usage.py`
- `src/swe/app/routers/tools.py`
- `src/swe/app/routers/tracing.py`
- `src/swe/app/routers/voice.py`
- `src/swe/app/routers/workspace.py`
- `src/swe/app/routers/zhaohu.py`

## 前端目录

| 目录 | 说明 |
|------|------|
| `console/src/api/` | 控制台 API 调用封装 |
| `console/src/pages/` | 页面入口 |
| `console/src/components/` | 通用 UI 组件 |
| `console/src/stores/` | 状态管理 |
| `console/src/contexts/`, `console/src/hooks/` | 运行时上下文与钩子 |

## 请求进入系统的常见路径

```text
Console/HTTP Client
  -> app/routers/*
  -> middleware/*
  -> workspace/service_manager.py
  -> runner/runner.py

Message Channel
  -> app/channels/*/channel.py
  -> unified_queue_manager.py
  -> runner/runner.py
```

## 关联功能域

- Agent 执行内核: [agent-and-orchestration.md](agent-and-orchestration.md)
- 安全与审批链路: [security-and-governance.md](security-and-governance.md)
