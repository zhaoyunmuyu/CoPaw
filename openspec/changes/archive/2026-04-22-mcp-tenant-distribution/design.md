## Context

The current MCP management flow is agent-scoped. The console MCP page reads and
writes `mcp.clients` through the currently selected agent, and the backend MCP
router persists those changes into that agent workspace's `agent.json`.

This gives the feature a clear source of truth for distribution:
- source tenant: current request tenant
- source agent: current request selected agent
- source payload: original `MCPClientConfig` entries from the source agent's
  `agent.json`

The skill-pool broadcast flow already proves several useful cross-tenant
patterns:
- tenant selection can combine discovered tenant IDs with manual tenant entry
- target tenants may need runtime-safe seeded bootstrap before writes
- batch fan-out should isolate failures per target tenant
- the UI should report per-tenant results rather than treating the whole batch
  as transactional

MCP distribution differs from skill broadcast in one key way: there is no
tenant-level MCP pool or baseline today. MCP configuration lives only in
agent-scoped config. That means the requested first version should copy
selected clients directly from the current agent into each target tenant's
`default` agent instead of introducing a new shared MCP storage layer.

Another important constraint is secret handling. MCP list APIs intentionally
mask `env` and `headers` values for console display, so the distribution flow
cannot trust client payload echoed back from the browser. The backend must read
the original source-agent configuration and copy from there.

## Goals / Non-Goals

**Goals:**
- Distribute selected MCP clients from the current tenant's current agent to
  multiple target tenants in one request.
- Reuse the existing target-tenant discovery and manual-entry interaction
  pattern.
- Support target tenants that are not yet bootstrapped.
- Copy the full original MCP client config, including masked secret fields.
- Write distributed clients into each target tenant's `default` agent only.
- Use explicit overwrite semantics in v1.
- Return per-tenant results.

**Non-Goals:**
- Creating a tenant-level MCP pool or baseline.
- Distributing to arbitrary target agents or same-name agents.
- Merge, rename, or diff-preview conflict flows.
- Single-card quick distribution actions from each MCP client card.
- Replacing existing tenant discovery routing with a new shared registry.

## Decisions

### Decision 1: the distribution source is the current tenant's currently selected agent

**Choice:** The source MCP clients come from the current request's selected
agent, not from a tenant-global MCP catalog.

**Rationale:**
- This matches the current MCP page semantics exactly.
- It avoids inventing a new MCP scope in v1.
- It keeps the operator mental model simple: distribute what is currently shown
  on the MCP page.

**Alternatives considered:**
- Add a tenant-global MCP pool first: rejected because it significantly expands
  the feature and data model.
- Allow users to compose an ad hoc client payload in the modal: rejected
  because it duplicates MCP CRUD and increases validation complexity.

### Decision 2: the target is always the target tenant's `default` agent

**Choice:** Every successful distribution writes into
`WORKING_DIR/<tenant>/workspaces/default/agent.json`.

**Rationale:**
- This mirrors the first-version target chosen for skill broadcast.
- It avoids ambiguous behavior when the source agent is not `default`.
- Every bootstrapped tenant is guaranteed to have a `default` agent scaffold.

**Alternatives considered:**
- Write to same-name agent on the target tenant: rejected because the target
  tenant may not contain that agent and would require additional create/fallback
  semantics.
- Let the operator choose target agent IDs: rejected because it adds another
  selection surface and broader validation scope.

### Decision 3: the backend copies original MCP client config by `client_key`

**Choice:** The request body contains only `client_keys`; the backend resolves
and copies the original `MCPClientConfig` entries from the source agent.

**Rationale:**
- Console MCP read APIs mask `env` and `headers`, so browser-visible payloads
  are not safe copy sources.
- Copying by `client_key` preserves original secrets and avoids accidentally
  persisting masked values.
- The backend already has direct access to the authoritative agent config.

**Alternatives considered:**
- Submit full client JSON from the frontend: rejected because masked values
  would corrupt secrets.
- Re-fetch each client through existing read APIs: rejected because those APIs
  are display-oriented and still return masked values.

### Decision 4: overwrite is required and replaces the entire target client object

**Choice:** The v1 endpoint requires `overwrite=true` and replaces the target
`mcp.clients[client_key]` object in full.

**Rationale:**
- This keeps behavior unambiguous and matches the approved first-version scope.
- MCP clients are cohesive config objects; partial merges are more likely to
  leave stale or invalid combinations of transport, credentials, and launch
  metadata.
- Full replacement is easier to reason about and test.

**Alternatives considered:**
- Best-effort merge: rejected because field-level rules would be brittle.
- Skip-on-conflict: rejected because it does not satisfy the intended operator
  workflow.

### Decision 5: target tenants may be discovered or manually entered

**Choice:** The frontend reuses the discovered-tenant plus manual-entry
interaction pattern and continues to call the existing tenant discovery route in
v1.

**Rationale:**
- This behavior is already familiar in the console.
- Manual entry is necessary because a valid distribution target may not be
  bootstrapped yet.
- Reusing the discovery route avoids unnecessary API surface expansion.

**Alternatives considered:**
- Only allow discovered tenants: rejected because it blocks valid bootstrap-on-
  write targets.
- Add a new MCP-specific discovery route immediately: rejected because the
  existing route already satisfies v1 needs.

### Decision 6: per-tenant partial success, with ordered bootstrap -> write -> reload

**Choice:** The batch returns per-tenant results. For each target tenant, the
backend executes:
1. validate target tenant ID
2. ensure runtime-safe seeded bootstrap
3. load target tenant `default` agent config
4. overwrite selected `mcp.clients`
5. save target config
6. reload target tenant `default` runtime

If one tenant fails, other tenants still proceed.

**Rationale:**
- This matches the skill broadcast batch model already present in the product.
- Each tenant is an independent failure domain.
- Ordered per-tenant steps minimize half-written state before runtime reload.

**Alternatives considered:**
- Whole-batch rollback: rejected because unrelated target tenants should not be
  coupled.
- Save all tenants first and reload later in a second phase: rejected because
  it complicates failure accounting without improving operator value in v1.

## Risks / Trade-offs

- [Operators may assume the target agent matches the currently selected source
  agent] -> The MCP distribution UI and result copy should explicitly state
  that writes go to each target tenant's `default` agent.
- [Masked secrets could still leak into target config if the wrong source path
  is used] -> The endpoint must resolve source clients from the source agent's
  original config object, not from API response payloads.
- [Reloading the wrong runtime instance in a multi-tenant process could apply
  stale config] -> The backend must reload with explicit tenant scope:
  `reload_agent("default", tenant_id=target_tenant_id)`.
- [Target bootstrap may succeed but subsequent save or reload may fail] ->
  Return explicit per-tenant result details and avoid claiming transactional
  semantics.
- [Reusing the full skill broadcast modal would couple MCP to skill-specific
  UI terms] -> Extract only the tenant-target selection behavior into a shared
  component or helper, and build an MCP-specific modal around it.

## Migration Plan

1. Add the MCP distribution request/response models and backend endpoint.
2. Add the tenant-target picker reuse on the frontend and wire an MCP-specific
   distribution modal from the page-level toolbar.
3. Add backend tests for source-config resolution, target bootstrap, overwrite,
   and per-tenant partial failure.
4. Add console contract coverage for batch selection, tenant target submission,
   and result feedback.

Rollback:
- Remove the MCP page distribution entry point.
- Remove the MCP distribution endpoint.
- Existing tenant-local MCP CRUD remains unchanged, so rollback does not
  require data migration.

## Open Questions

- None for v1. The approved scope fixes the target to `default`, requires
  overwrite, and copies `enabled` state unchanged.
