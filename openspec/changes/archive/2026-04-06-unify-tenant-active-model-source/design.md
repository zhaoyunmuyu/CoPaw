## Context

仓库已经完成 provider 配置目录的租户隔离，`ProviderManager` 也已经成为控制台 `/models` API 的主存储层；但 active model 的读取与运行时使用仍未完全收口。当前存在两条并行链路：

1. 运行时链路通过 `TenantModelManager` / `TenantModelContext` 读取 `tenant_models.json`，再由 `TenantModelConfig.get_active_slot()` 决定当前模型。
2. 控制台与 `/models` API 通过 tenant-aware `ProviderManager` 读写 `~/.copaw.secret/{tenant}/providers/active_model.json`。

这意味着“当前租户到底在用哪个模型”并没有唯一事实来源，带来三个直接问题：
- 聊天运行时可能读到旧的 `tenant_models.json`，而不是控制台刚设置的新 active model
- `/providers` 和 `/models` 暴露的模型配置语义不一致
- 前端 Chat `ModelSelector` 仍发送 `scope=agent`，与后端已经收口到租户级 active model 的实现相矛盾

本 change 的目标不是新增一套配置结构，而是删除重叠概念，明确 `providers/active_model.json` 是租户 active model 的唯一来源，并将运行时、API、前端与迁移行为全部对齐到这一来源。

## Goals / Non-Goals

**Goals:**
- 统一租户 active model 的唯一事实来源为 `~/.copaw.secret/{tenant}/providers/active_model.json`
- 让运行时模型解析、prompt 能力判断、agent 日志和 `/models/active` API 都从同一来源读取 active model
- 去除请求生命周期与运行时主路径对 `tenant_models.json` 的依赖
- 修复前端 Chat 模型切换仍发送 `scope=agent` 的历史遗留问题
- 为 legacy tenant 提供短期迁移/恢复路径，但避免长期双写
- 明确 `/providers` 的命运：淘汰，或重写为 provider-backed 只读兼容视图

**Non-Goals:**
- 不改变 provider 文件结构（`builtin/`, `custom/`, `active_model.json`）
- 不重新设计 provider CRUD API
- 不保留长期的 `tenant_models.json` 与 `active_model.json` 双写机制
- 不引入新的 active model 作用域（例如新的 per-agent 存储模型）

## Decisions

### 决策 1：`ProviderManager` 成为 active model 的唯一读取入口

**选择**：所有运行时和 API 的 active model 读取都通过 `ProviderManager.get_instance(tenant_id).get_active_model()` 完成。

**理由**：
- `ProviderManager` 已经是 `/models` API 的真实后端，复用现有能力改动最小
- `active_model.json` 已经位于租户隔离目录中，符合当前体系
- 可以彻底消除“tenant model config”和“provider active model”并存带来的漂移

**替代方案**：
- 继续保留 `TenantModelContext` 作为主来源，再同步回 `ProviderManager`：会继续维持双源状态
- 直接让运行时代码自己读文件：会把存储细节散落到多个模块中

### 决策 2：运行时移除对完整 `TenantModelConfig` 的主路径依赖

**选择**：`model_factory.py`、`prompt.py`、`react_agent.py` 不再以 `TenantModelContext.get_config().get_active_slot()` 为主逻辑，而是直接使用 tenant-aware `ProviderManager`。

**理由**：
- 这些模块真正需要的只是“当前 provider_id + model”，不需要完整 routing/config 结构
- 这样可以让 `tenant_models` 包退出运行时主链路，而不必一次性删除所有旧代码

**替代方案**：
- 保留 `TenantModelContext`，但改成只缓存 provider-backed 的轻量 active model 信息。这个方案也可行，但第一步并不必要；先直连 `ProviderManager` 更直接。

### 决策 3：`/models` 作为正式主接口，`/providers` 只允许兼容存在

**选择**：保留 `/models` 作为设置与读取 active model 的唯一主 API；`/providers` 若存在调用方，则重写为 provider-backed 兼容视图，否则淘汰。

**理由**：
- console 当前已经主要依赖 `/models`
- `/providers` 的返回结构来自 `tenant_models.json`，如果继续保留旧数据源，会再次形成双轨体系
- 从维护成本上看，保留一条主链路比维护两套模型接口更稳定

**替代方案**：
- 继续并存 `/providers` 与 `/models` 两套接口：会不断放大语义分裂问题
- 立即删除 `/providers`：如果存在外部调用方，会引入不必要的兼容风险

### 决策 4：前端停止发送 `scope=agent`，后端短期归一化兼容

**选择**：前端 Chat `ModelSelector` 改为发送租户级 scope；后端短期接受 `agent` 并归一化到当前唯一支持的租户级 active model 语义。

**理由**：
- 当前前端行为与后端能力已经脱节
- 先后端兼容、再前端修正，可以减少中间版本出错窗口

**替代方案**：
- 只改前端，不做后端兼容：旧前端版本会直接失败
- 重新引入真正的 agent 级 active model：与当前配置收敛目标相反

### 决策 5：迁移采用“短期读兼容、立即写收口”

**选择**：
- 所有 active model 写入只写 `providers/active_model.json`
- 若 legacy tenant 缺少该文件但存在 `tenant_models.json`，允许一次性恢复/迁移 active slot 到新文件
- 不保留长期双写

**理由**：
- 双写最容易制造隐蔽不一致
- 读兼容能覆盖存量租户，写收口能快速建立新事实来源

**替代方案**：
- 长期双写：高概率导致状态漂移
- 完全不兼容旧租户：会让存量环境升级风险过高

## Risks / Trade-offs

- [风险] 仍有隐藏代码路径依赖 `tenant_models.json` → **缓解**：在实现前后都执行全局搜索，并补充运行时/接口回归测试。
- [风险] `/providers` 存在未知外部调用方 → **缓解**：先保留接口壳，内部重定向到 provider-backed 视图，待确认无人使用后再删除。
- [风险] legacy tenant 只有旧配置，没有 `providers/active_model.json` → **缓解**：在首次读取 active model 时提供一次性恢复/迁移逻辑，并记录日志。
- [风险] 前后端过渡期间 scope 语义不一致 → **缓解**：后端先兼容 `agent`，前端再切换到租户级 scope。
- [风险] `tenant_models` 包仍被测试、脚本、文档引用 → **缓解**：将运行时清理与测试/脚本/文档同步纳入本 change 的任务列表，不只改代码主链路。

## Migration Plan

1. 先统一运行时与 `/models/active` 的读写路径，确保 active model 只从 tenant-aware `ProviderManager` 获取与保存。
2. 在读取链路中加入短期 legacy 恢复逻辑：当新文件不存在但旧 `tenant_models.json` 存在时，提取旧 active slot 并写入 `providers/active_model.json`。
3. 修复前端 `ModelSelector` 的 scope 参数，同时在后端保留短期兼容，避免中间版本报错。
4. 将 `/providers` 改为 provider-backed 兼容视图或标记弃用；验证无依赖后再删除。
5. 清理运行时代码中对 `TenantModelManager` / `TenantModelContext` 的主路径依赖。
6. 最后更新测试、脚本与文档，并移除不再需要的旧逻辑。

**回滚策略：**
- 代码回滚后仍可继续读取旧 `tenant_models.json`（如果兼容逻辑尚未删除）
- 如果迁移已写入 `providers/active_model.json`，回滚不会破坏 provider 目录结构，只需恢复旧代码路径
- 不采用 destructive 数据迁移，不删除 legacy 文件，直到验证完成

## Open Questions

1. `/providers` 是否仍有控制台之外的真实调用方？如果没有，应在本 change 内直接弃用还是仅标记废弃？
2. legacy 恢复逻辑应在运行时首次读取时触发，还是在中间件/启动阶段显式执行一次？
3. `TenantModelContext` 是否保留为轻量上下文层，还是在这次 change 中完全退出运行时？
