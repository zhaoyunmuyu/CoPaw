## Why

CoPaw backend cold start is slowed by eager initialization in `lifespan()`, including telemetry, migrations, QA agent setup, provider/local model managers, and agent prewarming. In a multi-tenant deployment this couples startup cost to tenant and agent footprint, delaying readiness and blurring runtime isolation boundaries.

## What Changes

- Reduce application startup to minimal control-plane assembly plus `ensure_default_agent_exists()`.
- Remove telemetry, legacy migrations, QA agent initialization, eager agent startup, provider/local model eager init, and default agent prewarm from the cold-start path.
- Split tenant initialization so request-time tenant access only performs minimal bootstrap and context binding.
- Rework tenant pool responsibilities so tenant-level access no longer starts a default workspace runtime.
- Make `MultiAgentManager.get_agent()` the single runtime startup entrypoint for tenant+agent lazy loading.
- Move skill pool, provider manager, local model manager, and QA agent initialization to on-demand feature entrypoints or explicit maintenance flows.
- Slim `Workspace.start()` so it only starts the current agent’s minimal runtime dependencies.

## Capabilities

### New Capabilities
- `backend-startup-lazy-loading`: Defines minimal startup, tenant bootstrap, and tenant+agent runtime lazy-loading behavior for the backend.

### Modified Capabilities
- None.

## Impact

- Affected code: `src/copaw/app/_app.py`, `src/copaw/app/multi_agent_manager.py`, `src/copaw/app/workspace/tenant_initializer.py`, `src/copaw/app/workspace/tenant_pool.py`, `src/copaw/app/workspace/workspace.py`, `src/copaw/app/middleware/tenant_workspace.py`, and related provider/skills initialization paths.
- Affected behavior: FastAPI readiness semantics, tenant bootstrap flow, agent runtime startup timing, provider/local model initialization timing, and maintenance/migration entrypoints.
- Operational impact: service becomes ready sooner, while first tenant/agent/provider/skills access may pay deferred initialization cost.
