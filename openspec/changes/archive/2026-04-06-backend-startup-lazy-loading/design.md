## Context

Current CoPaw backend cold start is slowed by excessive synchronous initialization inside `lifespan()`. The current startup flow includes telemetry, legacy workspace migration, legacy skills migration, QA agent initialization, starting all configured agents, eager initialization of `ProviderManager` and `LocalModelManager`, and prewarming the default agent. This delays service readiness and couples startup cost to tenant/agent footprint in multi-tenant deployments.

Existing lazy-loading structures include `MultiAgentManager.get_agent()` and `TenantWorkspacePool.get_or_create()`, but they still trigger too much work: tenant bootstrap, workspace startup, skill pool initialization, and legacy migrations are still mixed into the request path.

## Goals / Non-Goals

**Goals:**
- Reduce cold start to minimal control-plane initialization plus `ensure_default_agent_exists()`.
- Remove telemetry and migrations from the startup path.
- Defer agent runtime, provider manager, local model manager, and skill pool initialization to on-demand triggers.
- Separate tenant bootstrap (directory + minimal metadata) from agent runtime startup.
- Ensure tenant-level isolation: one tenant’s runtime initialization must not affect others.
- Slim `Workspace.start()` to only start agent-level dependencies, not tenant-level or platform-level resources.

**Non-Goals:**
- Changing agent business logic or conversation behavior.
- Changing provider protocols or model selection semantics.
- Introducing new multi-tenant data structures.
- Moving all initialization to background async prewarm.
- Guaranteeing low latency on first agent request (trade-off accepted).

## Decisions

1. **Service ready != all agents ready**
   - Rationale: FastAPI ready only requires routes, middleware, and app state. Agent runtimes are demand-started by `MultiAgentManager.get_agent()`.
2. **Default agent “exists” vs “is running”**
   - Rationale: Startup ensures directory, agent.json, and minimal metadata exist. Runtime starts only when first request arrives.
3. **Tenant bootstrap != agent runtime startup**
   - Rationale: Tenant middleware and `TenantWorkspacePool` only ensure directory skeleton and context binding. Workspace runtime is started by `MultiAgentManager.get_agent()`.
4. **Feature-level lazy initialization**
   - Rationale: Skills, provider manager, and local model manager are initialized on first use of their respective APIs, not at startup or tenant bootstrap.
5. **Migrations move to explicit maintenance paths**
   - Rationale: Legacy migrations are data maintenance, not prerequisites for service readiness.
6. **Workspace.start() loses skill pool initialization**
   - Rationale: Skill pool initialization is a feature-level concern triggered by skill APIs, not a per-agent startup requirement.

## Risks / Trade-offs

- **First agent request latency** → Acceptable trade-off for faster cold start; observability should surface per-tenant/agent init times.
- **Health check semantics change** → Ready means HTTP up; it no longer implies default agent prewarmed. Deployment automation must adjust expectations if it relied on implicit prewarm.
- **Implicit dependency exposure** → Past startup/tenant paths may have hidden side effects (e.g., skill pool init). Regression tests must verify explicit initialization on first use.

## Migration Plan

1. Deploy changes that remove eager initializations (maintain backward-compatible APIs).
2. Monitor cold start duration and first-request latency per tenant/agent.
3. If needed, add optional background prewarm without blocking readiness.
4. Provide explicit CLI or admin endpoints for legacy migrations and QA agent creation.

## Open Questions

- Should we provide an opt-in eager prewarm after startup for specific high-priority tenants/agents?
- Should telemetry move to a background job or be removed entirely?
