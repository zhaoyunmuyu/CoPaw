## 1. Consistency Tests

- [x] 1.1 Add regression tests for tenant-scoped `schedule_agent_reload()` and direct `reload_agent()` call sites so missing `tenant_id` is detectable
- [x] 1.2 Add API-level tests for `GET /api/mcp` proving reads use the resolved tenant and agent's authoritative `agent.json`
- [x] 1.3 Add read-after-write regression tests covering MCP create, update, toggle, and delete flows for the same tenant and agent
- [x] 1.4 Add isolation tests proving two tenants with the same agent id do not observe each other's updated config

## 2. Tenant-Aware Reload Contract

- [x] 2.1 Audit and update all `schedule_agent_reload(...)` call sites under `src/swe/app/routers/` to pass the correct tenant scope
- [x] 2.2 Audit and update all direct `MultiAgentManager.reload_agent(...)` call sites to pass tenant scope where required
- [x] 2.3 Extend daemon restart context and reload flow so `/daemon restart` reloads the correct tenant-scoped runtime

## 3. Authoritative Control Read Path

- [x] 3.1 Identify agent-scoped control read endpoints that currently return `Workspace.config` snapshots instead of authoritative `agent.json`
- [x] 3.2 Refactor MCP control reads to resolve the target agent and load tenant-scoped `agent.json` as the response source
- [x] 3.3 Refactor other affected control reads such as tools and running-config to use the same authoritative tenant-scoped agent config path
- [x] 3.4 Introduce a shared helper or pattern for tenant-scoped agent config reads so route handlers stop re-implementing inconsistent load behavior

## 4. Verification and Rollout Readiness

- [x] 4.1 Verify single-instance behavior for repeated `GET /api/mcp` before and after config mutation
- [x] 4.2 Verify multi-instance or simulated multi-cache behavior no longer oscillates between old and new MCP snapshots
- [x] 4.3 Document the backend consistency boundary and the non-goal relationship to `complete-console-agent-switching`
