## Why

The MCP page currently manages client configuration only for the current
tenant and the currently selected agent. Operators who need the same MCP
servers in multiple tenants must recreate those client definitions tenant by
tenant, which is slow and error-prone.

The console already has a proven cross-tenant target-picker pattern in the
skill-pool broadcast flow, including discovered tenants, manual tenant entry,
bootstrap-on-write, and per-tenant result reporting. MCP needs an equivalent
distribution workflow, but without introducing a new tenant-level MCP pool.

## What Changes

- Add a cross-tenant MCP distribution API in the MCP domain.
- Let the MCP page batch-select one or more MCP clients from the current
  tenant's currently selected agent and distribute them to multiple target
  tenants in one request.
- Fix the first version target to each target tenant's `default` agent.
- Copy the full original MCP client configuration for each selected client:
  `enabled`, `transport`, `url`, `headers`, `command`, `args`, `env`, and
  `cwd`.
- Require `overwrite=true` for the first version instead of adding merge,
  rename, or skip-on-conflict branches.
- Support target tenant IDs that are not yet bootstrapped by running the
  runtime-safe tenant bootstrap flow before writing MCP configuration.
- Return per-tenant success and failure results instead of making the whole
  batch transactional.
- Reuse the existing tenant discovery and target-selection interaction pattern
  from the skill-pool broadcast flow, but surface it through an MCP-specific
  modal instead of reusing the skill modal directly.

## Capabilities

### New Capabilities
- `cross-tenant-mcp-distribution`: The system can distribute selected MCP
  clients from the current tenant's current agent to multiple target tenants'
  `default` agents with explicit overwrite semantics and per-tenant results.

### Modified Capabilities
- None.

## Impact

- Affected backend modules:
  - `src/swe/app/routers/mcp.py`
  - `src/swe/app/multi_agent_manager.py`
  - `src/swe/app/workspace/tenant_initializer.py`
  - `src/swe/config/config.py`
- Affected frontend modules:
  - `console/src/pages/Agent/MCP/index.tsx`
  - `console/src/pages/Agent/MCP/useMCP.ts`
  - `console/src/api/modules/mcp.ts`
  - `console/src/api/types/mcp.ts`
  - shared tenant-target picker extraction from the current skill-pool
    broadcast UI
- Affected behavior:
  - operators can batch distribute selected MCP clients to multiple target
    tenants from the MCP page
  - distribution writes into each target tenant's `default` agent only
  - target tenants can be discovered or entered manually even if not yet
    bootstrapped
- Unchanged behavior:
  - MCP configuration remains agent-scoped, not tenant-baseline scoped
  - regular tenant-local MCP CRUD behavior remains unchanged
  - the skill-pool broadcast workflow remains a separate feature
- Testing impact:
  - cross-tenant MCP distribution backend coverage
  - bootstrap/write/reload coverage for target tenant `default` agents
  - frontend tenant picker reuse, batch selection, and result display coverage
