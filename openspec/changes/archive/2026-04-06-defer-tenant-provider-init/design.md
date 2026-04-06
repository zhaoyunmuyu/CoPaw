## Context

The backend startup lazy-loading work has already reduced `lifespan()` to minimal service initialization, but tenant-scoped requests still do more synchronous work than intended. The main remaining issue is that `TenantWorkspaceMiddleware` currently mixes workspace binding with provider-related initialization.

Today, the first request for a tenant can still trigger multiple concerns in one path:
- tenant workspace bootstrap
- tenant provider storage initialization
- tenant model configuration binding

This weakens the design goal of feature-level lazy initialization. Provider storage setup is not required for every tenant request, yet it is still performed in generic tenant middleware before the request reaches a provider or model feature.

The existing multi-tenant provider isolation design intentionally introduced per-tenant provider storage and `ProviderManager.get_instance(tenant_id)`, but it placed first-time provider storage materialization in `TenantWorkspaceMiddleware`. That choice simplified rollout, but it keeps provider initialization on the tenant request path rather than the provider feature path.

## Goals / Non-Goals

**Goals:**
- Remove tenant provider storage initialization from `TenantWorkspaceMiddleware`.
- Keep tenant workspace bootstrap minimal and workspace-focused.
- Trigger tenant provider storage readiness only on provider/model first use.
- Preserve existing tenant-isolated provider storage semantics in this iteration.
- Reduce first-tenant-entry latency without changing frontend behavior.

**Non-Goals:**
- Changing frontend routes, bundling, or console behavior.
- Redesigning provider storage format or inheritance semantics.
- Introducing a read-through fallback model for provider config in this iteration.
- Narrowing workspace bootstrap to only a subset of tenant routes in this iteration.
- Changing tenant model selection semantics.

## Decisions

### 决策 1：Provider 初始化从 TenantWorkspaceMiddleware 移出

**选择**：`TenantWorkspaceMiddleware` no longer ensures tenant provider storage exists.

**理由**：
- Provider storage initialization is a provider concern, not a workspace concern.
- Middleware should bind request context, not trigger unrelated feature initialization.
- This aligns the code with the backend lazy-loading design: feature-level initialization happens on first use.

**替代方案**：
- 保留在 middleware：实现简单，但继续让所有 tenant 首次请求承担 provider 初始化成本。
- 将 provider 初始化并回 `lifespan()`：会重新扩大 cold start，违背现有 lazy-loading 目标。

### 决策 2：Provider storage readiness 属于 provider 子系统职责

**选择**：The provider subsystem owns tenant provider storage materialization, including default-template copy and concurrency protection.

**理由**：
- 现在这部分职责分散在 middleware 和 `ProviderManager` 之间，边界不清晰。
- Provider feature entrypoints 天然存在：provider APIs、local model APIs、runtime model creation paths。
- 将副作用集中在 provider first use 路径，便于测试和推理。

**替代方案**：
- 新增独立初始化 API：会引入额外使用步骤，且不能自动覆盖运行时模型创建路径。
- 保持分散职责：短期无改动，但长期会继续放大 request-path 隐式依赖。

### 决策 3：Tenant bootstrap 继续保持最小化，但不再暗示 provider readiness

**选择**：`TenantWorkspacePool.ensure_bootstrap()` 继续只负责 tenant 目录骨架、default agent declaration 和 workspace context 可用性。

**理由**：
- Tenant existence、workspace readiness、provider readiness、runtime readiness 是不同状态。
- 将这些状态分离，才能避免未来继续把更多 feature 初始化塞进 tenant request path。
- 当前 `ensure_bootstrap()` 已经相对轻量，不是本轮最主要的职责错位点。

**替代方案**：
- 本轮同时收缩 workspace bootstrap 触发范围：理论上更干净，但变更面更大，风险更高。
- 在 bootstrap 中继续处理 provider：会重新耦合 workspace 与 provider 生命周期。

### 决策 4：本轮只调整初始化时机，不改变 provider 存储语义

**选择**：保留当前 tenant-isolated provider storage 结构和 default tenant 模板复制语义，仅调整触发时机。

**理由**：
- 风险更低，便于在现有多租户 provider 隔离基础上增量优化。
- 可以立即减少 tenant entry 延迟，而不必同时重做 provider 配置继承模型。
- 与现有测试和运维心智保持兼容。

**替代方案**：
- 改成 read-through default / write-on-first-mutation：长期可能更优，但会显著扩大设计与实现范围。

## Risks / Trade-offs

- [风险] 首次 provider/model 使用延迟上升 → 将成本从 tenant entry 转移到 provider/model first use，符合 lazy-loading 设计目标。
- [风险] 某些路径隐式依赖 middleware 已完成 provider 初始化 → 在 provider APIs、local model APIs、model factory 等入口显式兜底并补充回归测试。
- [风险] 并发首次 provider 初始化产生竞争 → 保留幂等初始化与锁保护，将其收口到 provider 子系统内部。
- [风险] workspace bootstrap 仍对部分轻量请求偏早 → 本轮接受该限制，后续再评估 identity-only 与 workspace-bound 路由拆分。

## Migration Plan

1. Remove provider storage initialization from `TenantWorkspaceMiddleware`.
2. Introduce explicit provider storage readiness checks at provider feature entrypoints.
3. Validate that a tenant can complete provider API flows and runtime model creation without prior middleware materialization.
4. Verify that a non-provider tenant request no longer creates tenant provider storage.
5. If regressions appear, roll back by restoring middleware-based initialization while retaining the new tests.

## Open Questions

- Should `TenantModelContext` remain request-scoped in `TenantWorkspaceMiddleware`, or eventually move closer to model runtime resolution?
- After provider initialization is moved out, which tenant routes truly need workspace bootstrap and which only need tenant identity?
- If first-use provider copy is still noticeable, should a later change adopt read-through default semantics?
