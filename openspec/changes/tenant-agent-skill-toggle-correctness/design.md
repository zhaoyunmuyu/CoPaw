## Context

Workspace-local skill state is persisted under one agent workspace as
`<workspace>/skills/` plus `<workspace>/skill.json`. The request path already
resolves the target workspace through `get_agent_for_request()`, which binds the
current tenant and agent to a specific workspace directory.

The remaining gap is runtime convergence after manifest mutation:
- single-skill enable/disable routes mutate the correct workspace manifest, but
  call `schedule_agent_reload()` with only `agent_id`
- `MultiAgentManager` caches runtimes by `tenant_id + agent_id`, so reloading by
  bare `agent_id` can miss the loaded tenant-local runtime or target the wrong
  cache entry
- batch enable/disable routes mutate the workspace manifest but never trigger a
  runtime refresh, so the running agent can keep stale effective skills until a
  later manual reload

This change is small in code size but cross-cutting across router entrypoints,
reload plumbing, and tenant-aware runtime management, so a short design is
useful to make the boundary explicit.

## Goals / Non-Goals

**Goals:**
- Preserve workspace skill manifest writes on the current tenant-agent
  workspace only.
- Make runtime reload targeting explicit for the same tenant and agent that
  owns the mutated workspace.
- Ensure successful batch workspace skill mutations also converge runtime state.
- Add regression tests that prove no cross-tenant or cross-agent reload occurs.

**Non-Goals:**
- Changing skill pool behavior or tenant skill bootstrap behavior.
- Broadcasting workspace skill changes to every agent in the same tenant.
- Introducing distributed reload signaling across backend instances.
- Refactoring workspace skill storage away from `skill.json`.

## Decisions

### Decision: carry tenant scope through reload scheduling

`schedule_agent_reload()` will accept an optional `tenant_id` and pass it
through to `MultiAgentManager.reload_agent()`.

Why:
- The manager already treats `tenant_id + agent_id` as the runtime identity.
- Reload targeting should match the same identity used for workspace lookup and
  runtime caching.

Alternatives considered:
- Reconstruct tenant scope inside `schedule_agent_reload()` from ambient
  context only: rejected because explicit arguments are easier to audit and test.
- Reload by workspace path instead of tenant-agent identity: rejected because
  the runtime manager already keys on tenant-agent identity, not path lookup.

### Decision: batch workspace skill mutations reload once after any success

Batch enable/disable routes will perform all requested mutations first, then
schedule one reload for the current tenant-agent runtime if at least one skill
mutation succeeds.

Why:
- The runtime only needs to converge once to the new manifest state.
- A single post-batch reload avoids unnecessary duplicate reload tasks.

Alternatives considered:
- Reload after each successful item: rejected because it creates redundant work
  and racey intermediate convergence.
- Never auto-reload batch routes and rely on future requests: rejected because
  it leaves runtime state observably stale after a successful API response.

### Decision: failed mutations do not trigger runtime refresh

Routes will only schedule reload when the manifest changed successfully for at
least one target skill.

Why:
- Reload should represent convergence to a new durable workspace state.
- Avoiding no-op reloads keeps behavior easier to reason about and test.

Alternatives considered:
- Always reload after mutation attempts: rejected because failures would cause
  misleading runtime churn without a state change.

### Decision: unloaded runtimes remain lazy

If the current tenant-agent runtime is not loaded, the change will not force a
new runtime to start just to apply a skill mutation. The next normal runtime
load will read the updated manifest.

Why:
- This matches current lazy-loading semantics in `MultiAgentManager`.
- The main correctness issue is targeting the loaded runtime, not eager startup.

Alternatives considered:
- Force-load and reload an unloaded runtime: rejected because it changes runtime
  lifecycle behavior unrelated to the bug being fixed.

## Risks / Trade-offs

- [A route passes the wrong tenant identity into reload scheduling] →
  Centralize tenant-aware reload scheduling in one helper signature and cover it
  with router tests that use distinct tenant IDs.
- [Batch routes trigger reload even when every mutation failed] → Gate the
  reload call on at least one successful mutation result.
- [Future routes keep using the old helper signature] → Update the shared helper
  and all current workspace skill mutation call sites together.

## Migration Plan

1. Extend reload scheduling to accept `tenant_id`.
2. Update workspace skill mutation routes to pass the current workspace tenant
   and to reload after successful batch mutations.
3. Add regression tests for tenant-local reload targeting and batch convergence.
4. Verify OpenSpec and test coverage reflect the new contract.

Rollback is straightforward: revert the helper signature and router call sites.
Workspace skill manifests remain valid because this change does not alter the
on-disk schema.

## Open Questions

- None for this change. The current behavior gap and desired tenant-agent
  boundary are already clear from the existing runtime architecture.
