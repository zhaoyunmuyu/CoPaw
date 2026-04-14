# 安全、审批与治理边界

本文档整理与执行安全、审批流程、认证和路径边界相关的模块。

## 工具治理主链路

| 区域 | 关键文件 | 说明 |
|------|----------|------|
| Agent 接入层 | `src/swe/agents/tool_guard_mixin.py` | 在 Agent 工具调用前插入治理逻辑 |
| 审批模型 | `src/swe/security/tool_guard/models.py` | 审批与守卫相关结构 |
| 审批入口 | `src/swe/security/tool_guard/approval.py` | 审批流程入口 |
| 守卫引擎 | `src/swe/security/tool_guard/engine.py` | 规则执行与决策 |
| Guardian | `src/swe/security/tool_guard/guardians/file_guardian.py`, `src/swe/security/tool_guard/guardians/rule_guardian.py` | 文件边界和规则守卫 |
| 规则集 | `src/swe/security/tool_guard/rules/dangerous_shell_commands.yaml` | 危险命令规则 |
| 工具函数 | `src/swe/security/tool_guard/utils.py` | 守卫辅助逻辑 |

## 其他安全边界

| 文件 | 说明 |
|------|------|
| `src/swe/security/tenant_path_boundary.py` | 租户路径越界防护 |
| `src/swe/security/skill_scanner/scanner.py` | 技能扫描器 |
| `src/swe/security/skill_scanner/scan_policy.py` | 技能扫描策略 |
| `src/swe/security/skill_scanner/models.py` | 技能扫描结果模型 |
| `src/swe/app/auth.py` | 应用认证中间件/逻辑 |
| `src/swe/app/routers/auth.py` | 认证路由 |
| `src/swe/app/approvals/service.py` | 审批服务 |

## 治理范围

- Shell、文件读写、浏览器等高风险工具需进入 Tool Guard 决策
- 技能文件进入系统前可经过扫描策略校验
- 租户目录与密钥目录必须受请求上下文和路径边界共同限制
- API 请求受认证与租户中间件约束

## 关联功能域

- Agent 工具调用链: [agent-and-orchestration.md](agent-and-orchestration.md)
- 通道/API 接入面: [channels-and-access.md](channels-and-access.md)
