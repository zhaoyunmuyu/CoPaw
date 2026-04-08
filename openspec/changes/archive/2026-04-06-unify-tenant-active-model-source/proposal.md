## Why

当前仓库已经将 provider 配置主体迁移到租户隔离的 `~/.swe.secret/{tenant}/providers/` 目录，但 active model 的运行时读取链路仍然同时依赖 `tenant_models.json` 和 `providers/active_model.json` 两套来源。这导致运行时选模、控制台切模、以及旧 `/providers` 接口之间存在语义分裂和状态漂移风险，需要将 active model 的唯一来源统一到 tenant-scoped `providers/active_model.json`。

## What Changes

- **BREAKING**: 停止将 `tenant_models.json` 作为租户 active model 的运行时来源，active model 统一从 `~/.swe.secret/{tenant}/providers/active_model.json` 读取
- 修改运行时模型解析链路，使 `model_factory`、prompt 相关能力、以及 agent 日志统一通过 tenant-aware `ProviderManager` 解析当前 active model
- 修改请求生命周期中的租户模型加载逻辑，去除或替换 `TenantModelManager` / `TenantModelContext` 对完整 `TenantModelConfig` 的依赖
- 调整 provider 相关 API，保留 `/models` 作为主接口，弱化、重写或淘汰依赖 `tenant_models.json` 的 `/providers` 旧接口
- 修复前端 Chat `ModelSelector` 仍发送 `scope=agent` 的问题，使其与后端当前租户级 active model 语义保持一致
- 增加旧租户迁移兼容逻辑：仅在过渡期允许从旧配置恢复 active model，不引入长期双写
- 清理与 `tenant_models.json` 运行时使用相关的测试、脚本与文档，确保系统只维护一套 active model 来源

## Capabilities

### New Capabilities
- `tenant-active-model-source-unification`: 统一租户 active model 的读取、设置与 API 语义，使 `providers/active_model.json` 成为唯一事实来源

### Modified Capabilities
- （无现有 spec 需要修改）

## Impact

- **代码文件**:
  - `src/swe/providers/provider_manager.py`: 作为租户 active model 的唯一入口与存储层
  - `src/swe/agents/model_factory.py`: 移除 `tenant_models.json` 主路径读取
  - `src/swe/agents/prompt.py`: active model 信息来源统一
  - `src/swe/agents/react_agent.py`: active model 日志来源统一
  - `src/swe/app/middleware/tenant_workspace.py`: 去除旧 tenant model config 注入
  - `src/swe/app/routers/providers.py`: 清理 `/providers` 旧逻辑并统一 `/models/active` 语义
  - `console/src/pages/Chat/ModelSelector/index.tsx`: 修复 `scope=agent`
  - `console/src/api/modules/provider.ts`: 对齐 active model scope 语义

- **数据/迁移**:
  - 旧租户若仍只配置了 `tenant_models.json`，需要一次性迁移或过渡恢复到 `providers/active_model.json`

- **API 影响**:
  - `/models/active` 成为租户 active model 的主 API
  - `/providers` 若保留，需改为 provider-backed 视图；若无调用方，可淘汰

- **验证影响**:
  - 需要回归验证租户隔离、active model 切换、控制台模型选择、以及 legacy tenant 迁移行为
