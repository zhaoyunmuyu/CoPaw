## Why

当前 `ProviderManager` 将提供商配置（API 密钥、base URL、活跃模型选择等）存储在全局共享目录 `~/.copaw.secret/providers/` 中，所有租户共享同一套配置。这违反了多租户隔离原则，导致租户 A 可以访问租户 B 的 API 密钥和模型配置。需要将 `ProviderManager` 改造为按租户隔离存储，每个租户拥有独立的配置目录。

## What Changes

- **BREAKING**: 修改 `ProviderManager` 存储路径，从全局 `~/.copaw.secret/providers/` 改为租户隔离的 `~/.copaw.secret/{tenant_id}/providers/`
- **BREAKING**: `ProviderManager` 不再作为全局单例直接使用，需要通过租户上下文获取租户特定的实例
- 新增 `TenantProviderManager` 包装类，根据当前租户 ID 动态路由到正确的配置目录
- 修改 `TenantWorkspaceMiddleware`，在请求上下文中绑定租户特定的 `ProviderManager`
- 修改 `create_model_and_formatter`，从租户上下文中获取 provider 配置而非全局单例
- 新增迁移脚本，将现有的全局 provider 配置迁移到 default 租户目录
- 新增自动初始化逻辑：当租户首次访问且配置不存在时，从 default 租户配置复制或创建默认配置

## Capabilities

### New Capabilities
- `tenant-isolated-provider-storage`: 租户隔离的 Provider 配置存储机制，支持按租户读写 provider 配置、API 密钥、活跃模型选择

### Modified Capabilities
- （无现有 spec 需要修改）

## Impact

- **代码文件**:
  - `src/copaw/providers/provider_manager.py`: 修改存储路径逻辑，支持租户隔离
  - `src/copaw/app/middleware/tenant_workspace.py`: 在请求上下文中加载租户 provider 配置
  - `src/copaw/agents/model_factory.py`: 从租户上下文获取 provider 配置
  - `src/copaw/cli/providers_cmd.py`: 支持按租户管理 provider
  - `src/copaw/app/routers/providers.py`: API 端点需要租户上下文

- **数据迁移**: 现有的 `~/.copaw.secret/providers/` 需要迁移到 `~/.copaw.secret/default/providers/`

- **API 变更**: Provider 管理 API 需要 `X-Tenant-Id` header，返回租户特定的配置

- **CLI 变更**: `copaw models` 命令需要支持 `--tenant-id` 参数

- **向后兼容**: 单租户部署使用 "default" 租户，现有配置自动迁移
