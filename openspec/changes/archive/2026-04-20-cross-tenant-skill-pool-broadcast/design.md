## Context

The current skill-pool page and `/api/skills/pool/download` flow are scoped to
the active tenant. They resolve one tenant's local `skill_pool`, enumerate that
same tenant's configured workspaces, and copy selected skills into selected
workspace skill directories.

That tenant-local model is not enough for the requested operator workflow. The
new workflow needs one source tenant to distribute selected pool skills across
multiple target tenants. For every selected target tenant, the selected skills
must become part of:
- the target tenant's `skill_pool` baseline, so future agents inherit them
- the target tenant's `workspaces/default/skills` state, so the default agent
  can use them immediately

The existing codebase already provides two important building blocks:
- tenant bootstrap can materialize a tenant's scaffold safely through
  `ensure_seeded_bootstrap()`
- skill-pool and workspace copy logic already know how to read/write skill
  directories and manifests

What is missing is an explicit cross-tenant orchestration layer that can:
- resolve selected target tenant IDs
- bootstrap missing target tenant scaffolds on demand
- write selected skills into the target tenant pool with overwrite semantics
- write the same skills into the target tenant `default` workspace
- isolate failures per target tenant

There is also no separate tenant registry in the current codebase. The existing
`list_all_tenant_ids()` helper only discovers tenants that already have a
materialized `config.json` under `WORKING_DIR/<tenant>`. That means the UI can
list discovered tenants, but still needs a manual tenant ID entry path for
targets that are known by operators before the runtime has bootstrapped them.

## Goals / Non-Goals

**Goals:**
- Broadcast selected pool skills from the active tenant to multiple target
  tenant IDs from the skill-pool page.
- For each target tenant, ensure the selected skills overwrite same-name copies
  in:
  - the target tenant `skill_pool`
  - the target tenant `default` agent workspace
- Preserve additive semantics:
  - selected same-name skills are overwritten
  - unselected target-tenant skills remain unchanged
- Allow target tenant IDs that are not bootstrapped yet by bootstrapping them
  just before broadcast.
- Return per-tenant results so one target failure does not roll back successful
  targets.

**Non-Goals:**
- Full mirror synchronization that deletes target-tenant skills not present in
  the selected source set.
- Rename or conflict-resolution dialogs for cross-tenant broadcast.
- A new tenant registry system or tenant identity source outside the current
  runtime filesystem model.
- A new authorization subsystem in this change.
  Inference: this change assumes the existing console/operator surface is the
  trust boundary for accessing the broadcast flow.
- Changing tenant-local pool CRUD or tenant-local workspace download behavior.

## Decisions

### Decision 1: add a dedicated cross-tenant broadcast API instead of reusing tenant-local download routes

**Choice:** Introduce a new broadcast route pair:
- one route to return discovered tenant IDs for the UI
- one route to perform cross-tenant broadcast to fixed `default` agents

**Rationale:**
- The current `/skills/pool/download` route is tenant-local on both its pool and
  workspace sides.
- Cross-tenant broadcast has extra orchestration concerns: target-tenant
  bootstrap, per-tenant partial success, fixed `default` workspace targeting,
  and skill-pool baseline writes.
- A dedicated API keeps this operator workflow explicit instead of hiding
  cross-tenant behavior inside a tenant-local route.

**Alternatives considered:**
- Loop in the frontend by changing `X-Tenant-Id` and calling existing routes:
  rejected because console auth/header behavior is tied to the active user
  tenant, and cache/request semantics are not built for client-side tenant
  hopping.
- Extend `/skills/pool/download` with cross-tenant fields: rejected because it
  would blur tenant-local download semantics with cross-tenant baseline sync.

### Decision 2: bootstrap each target tenant on demand using `ensure_seeded_bootstrap()`

**Choice:** Before applying any skill writes for a target tenant, call the
runtime-safe seeded bootstrap path for that tenant when needed.

**Rationale:**
- Broadcast must work even when the target tenant has not been bootstrapped.
- `ensure_seeded_bootstrap()` creates the required tenant scaffold, default
  agent, config, pool, and default workspace state without creating QA agents
  or starting workspace runtimes.
- This stays aligned with existing runtime-safe tenant initialization
  boundaries.

**Alternatives considered:**
- Require targets to already exist on disk: rejected because it would fail the
  requested workflow.
- Run full tenant initialization: rejected because it would do unrelated work,
  especially QA-agent creation, beyond what broadcast needs.

### Decision 3: broadcast writes both target tenant pool and target tenant default workspace

**Choice:** For each selected skill and each target tenant:
1. write the selected skill into the target tenant `skill_pool`
2. write the same selected skill into the target tenant
   `workspaces/default/skills`

**Rationale:**
- Updating only the default workspace would make the default agent usable now,
  but future agents would not inherit the new baseline.
- Updating only the pool would change future inheritance, but the current
  default agent would not receive the skill immediately.
- Writing both surfaces matches the stated product intent.

**Alternatives considered:**
- Pool-only sync: rejected because it delays usability until later agent
  creation.
- Default-workspace-only sync: rejected because it creates baseline drift inside
  the target tenant.

### Decision 4: use additive overwrite semantics, not full mirror semantics

**Choice:** The broadcast only touches the selected skills. If a selected skill
 already exists in the target tenant pool or default workspace, it is
 overwritten. Skills that are not selected are left unchanged.

**Rationale:**
- This is the explicit user-approved product behavior.
- It reduces blast radius versus a full mirror sync.
- It fits the current skill model, where operators may have tenant-local skills
  that should remain intact even when new baseline skills are broadcast.

**Alternatives considered:**
- Full mirror sync that removes unselected target skills: rejected because the
  user explicitly chose additive semantics.
- Rename-on-conflict: rejected because cross-tenant baseline broadcast is meant
  to keep canonical skill names aligned across tenants.

### Decision 5: fix the broadcast target to `default` instead of letting users choose agent IDs

**Choice:** The modal selects tenant IDs only. The target agent inside each
 tenant is always `default`.

**Rationale:**
- The requested workflow is about broadcasting to all target tenants' default
  agents.
- The system already treats `default` as the reserved tenant baseline agent.
- Removing per-agent choice keeps the UX and backend contract simpler.

**Alternatives considered:**
- Let the user choose arbitrary target agents in each tenant: rejected because
  it expands the operator surface beyond the approved requirement.

### Decision 6: discovered tenant listing plus manual tenant ID input

**Choice:** The UI gets a discovered tenant list from the backend, but also
 supports manual tenant ID entry.

**Rationale:**
- The current runtime only discovers bootstrapped tenants through filesystem
  state.
- Broadcast must also support target IDs that are not bootstrapped yet.
- Combining discovery with manual entry keeps the current system usable without
  introducing a new tenant registry in this change.

**Alternatives considered:**
- Discovered tenants only: rejected because it would exclude valid not-yet-
  bootstrapped targets.
- Manual entry only: rejected because operators still benefit from a safe
  pick-list of known tenants.

### Decision 7: per-tenant atomicity with partial batch success

**Choice:** Each target tenant is processed independently. A failure in one
 target tenant reports an error for that tenant only and does not roll back
 already successful targets.

**Rationale:**
- This matches the approved transaction model.
- It is operationally better for a broadcast batch where tenant readiness may
  vary.
- It avoids coupling unrelated target tenants into one failure domain.

**Alternatives considered:**
- Whole-batch rollback: rejected because the user explicitly chose partial
  success semantics.
- Best-effort writes with no per-tenant atomicity: rejected because each target
  tenant should still avoid ending in a half-updated pool/workspace state.

## API Sketch

### `GET /api/skills/pool/broadcast/tenants`

Returns the discovered tenant IDs currently visible from filesystem state.

Example response:

```json
{
  "tenant_ids": ["default", "tenant-a", "tenant-b"]
}
```

Notes:
- This list is discovery-only, not an exclusive allowlist.
- The frontend may still submit manually entered tenant IDs that are not in the
  response.

### `POST /api/skills/pool/broadcast/default-agents`

Example request:

```json
{
  "skill_names": ["guidance", "playbook"],
  "target_tenant_ids": ["tenant-a", "tenant-b", "tenant-new"],
  "overwrite": true
}
```

Example response:

```json
{
  "results": [
    {
      "tenant_id": "tenant-a",
      "success": true,
      "bootstrapped": false,
      "pool_updated": ["guidance", "playbook"],
      "default_agent_updated": ["guidance", "playbook"]
    },
    {
      "tenant_id": "tenant-new",
      "success": false,
      "bootstrapped": true,
      "error": "..."
    }
  ]
}
```

Notes:
- `overwrite` is required to be `true` for this flow in the first version.
- Results are returned per tenant.
- The route is responsible for validating the source skills exist in the active
  tenant pool before fan-out begins.

## Backend Flow

For each target tenant:

```text
validate target tenant id
  -> ensure seeded bootstrap
  -> for each selected skill:
       read source skill from active tenant pool
       overwrite target tenant pool copy
       overwrite target tenant default workspace copy
  -> collect tenant result
```

Implementation shape:
- source side stays bound to the active tenant from the request context
- target side resolves a tenant working dir explicitly per target tenant
- the cross-tenant route coordinates the fan-out
- lower-level skill helpers remain responsible for manifest-safe writes and
  skill scanning

To support overwrite into the target tenant pool, the backend will likely need a
 dedicated service/helper path for explicit replacement of a pool skill entry.
 This avoids reusing user-facing pool upload/import protections that treat some
 existing pool states, especially builtin entries, as non-overwritable in normal
 CRUD flows.

Inference: the dedicated replacement path should still preserve skill scanning
 and manifest metadata generation, but it should not reuse rename-oriented
 conflict semantics.

## Frontend Flow

The skill-pool page broadcast modal changes from:
- select skills
- select workspaces

to:
- select skills
- select tenant IDs
  - discovered list
  - manual tenant ID entry

The modal no longer exposes workspace or agent choice. The confirmation action
calls the new cross-tenant broadcast API and presents per-tenant success/failure
 results.

The existing localized copy for "broadcast to agents" can remain conceptually,
 but the modal content and helper text need to explain that the target is each
 selected tenant's `default` agent and skill-pool baseline.

## Risks / Trade-offs

- [Discovered tenant list is incomplete for not-yet-bootstrapped tenants]
  → Manual tenant ID entry is required in the first version.
- [Target tenant bootstrap seeds default template state before broadcast]
  → Broadcast overwrite runs after bootstrap, so selected skills still become
  the final state for the selected skill names.
- [Pool overwrite logic accidentally reuses restrictive CRUD conflict behavior]
  → Introduce an explicit broadcast replacement helper instead of piggybacking
  on rename/conflict workflows.
- [Per-tenant failures leave one target tenant partially updated]
  → Keep per-tenant execution atomic around pool + default workspace writes for
  the selected skill set, even though the overall batch is partially successful.
- [Authorization expectations are broader than current console trust boundary]
  → Document that this change does not introduce a new auth model; a future
  change can add stronger admin enforcement if needed.

## Migration Plan

1. Add backend request/response models and routes for discovered tenant listing
   and cross-tenant default-agent broadcast.
2. Add backend orchestration that:
   - validates source skills
   - bootstraps target tenants on demand
   - overwrites selected skills into target tenant pools
   - overwrites selected skills into target tenant default workspaces
   - returns per-tenant results
3. Update the skill-pool page modal to select tenants instead of workspaces,
   including manual tenant ID entry.
4. Add tests for:
   - broadcast to bootstrapped and non-bootstrapped targets
   - additive overwrite semantics
   - partial success results
   - future-agent inheritance from the updated target tenant pool baseline

Rollback is straightforward:
- remove the cross-tenant routes and UI path
- keep tenant-local skill-pool behavior unchanged
- target tenant changes already written by a broadcast remain on disk unless
  manually reverted by operators

## Open Questions

- Should the first version process target tenants sequentially for simpler
  isolation, or with bounded concurrency for faster large batches?
  Recommended answer: start sequentially unless performance proves inadequate.
- Should the tenant discovery API include only discovered IDs, or also a
  display model with bootstrapped status?
  Recommended answer: include bootstrapped status if convenient, but tenant ID
  list alone is sufficient for the first version.
