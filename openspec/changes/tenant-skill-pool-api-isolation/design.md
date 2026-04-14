## Context

Tenant first-access bootstrap now creates tenant-local skill state under
`WORKING_DIR/<tenant>/skill_pool` and
`WORKING_DIR/<tenant>/workspaces/default/skills`. That means skill state is
already modeled as tenant-local on disk.

However, the skill-pool management layer still has a split boundary:
- tenant bootstrap paths explicitly pass `working_dir=self.tenant_dir`
- many pool management routes and helpers call
  `get_skill_pool_dir()`, `get_pool_skill_manifest_path()`,
  `read_skill_pool_manifest()`, or `reconcile_pool_manifest()` without a tenant
  `working_dir`
- `SkillPoolService` itself is constructed without tenant scope and therefore
  defaults to the global `WORKING_DIR/skill_pool`

As a result, tenant-scoped requests can resolve tenant-local workspaces while
still reading or mutating a shared global pool. Upload/download flows are the
clearest example: the workspace side is tenant-aware through `list_workspaces()`
while the pool side remains global.

This change is cross-cutting because it touches router entrypoints, shared pool
helpers, skill hub import helpers, and agent workspace initialization.

## Goals / Non-Goals

**Goals:**
- Make pool management operations resolve against the current tenant's
  `WORKING_DIR/<tenant>/skill_pool`.
- Keep workspace-side routing tenant-aware and align pool-side routing to the
  same tenant.
- Remove implicit fallback to global pool state during tenant-scoped requests.
- Preserve current pool semantics within a tenant:
  - builtin import and update behavior
  - conflict detection
  - workspace upload/download behavior
- Add regression coverage for cross-tenant isolation.

**Non-Goals:**
- Changing first-access tenant bootstrap seeding behavior.
- Changing workspace-local skill APIs outside the pool integration points.
- Introducing cross-tenant skill sharing or a new global/shared pool concept.
- Refactoring unrelated tenant bootstrap or provider-isolation logic.

## Decisions

### Decision: make `SkillPoolService` explicitly tenant-aware

`SkillPoolService` will accept `working_dir: Path | None` and use that stored
value for every pool read/write operation.

Why:
- The service is the main abstraction used by pool routes and helper paths.
- Centralizing tenant scope there removes repeated ad hoc path resolution in
  higher layers.

Alternatives considered:
- Keep `SkillPoolService` global and patch every route separately: rejected
  because helper paths such as hub import and builtin update would still have
  bypasses.
- Infer tenant from ambient context inside the service: rejected because
  explicit `working_dir` is easier to audit and test.

### Decision: thread tenant `working_dir` through pool helper functions

Helper functions that inspect or mutate pool state will gain an explicit
`working_dir` parameter where missing, including:
- builtin source listing
- builtin sync status
- builtin update
- pool spec building
- hub import entrypoints that create pool skills

Why:
- Several router and service paths do not go through the same service methods.
- Helper-level explicit scope avoids hidden fallbacks to the global pool.

Alternatives considered:
- Leave helpers global and only use service wrappers: rejected because current
  router code and utility code already call helpers directly.

### Decision: route layer resolves tenant working dir once per request

Pool routes will resolve the active tenant directory from request context and
pass it downward explicitly.

Why:
- Request handlers already define the multi-tenant request boundary.
- It keeps tenant scoping obvious in API code and avoids accidental global
  behavior when later routes are added.

Alternatives considered:
- Rely on ambient context inside helpers only: rejected because many helpers
  currently default to global `WORKING_DIR`, and explicit request-time binding
  is easier to verify.

### Decision: upload/download remain tenant-local on both sides

For `/skills/pool/upload` and `/skills/pool/download`, the workspace target list
will continue to come from the current tenant's workspace config, and the pool
source/target will be switched to that same tenant's local pool.

Why:
- Current behavior is mixed-scope and therefore unsafe.
- Matching workspace scope and pool scope keeps the user mental model simple:
  each tenant manages its own pool and its own workspaces.

Alternatives considered:
- Preserve a global pool for upload/download only: rejected because it keeps
  cross-tenant mutation paths open and contradicts tenant-local bootstrap.

### Decision: agent workspace initialization must also use tenant-local pool

The helper path that seeds workspace skills by `skill_names` during agent
workspace initialization will accept tenant `working_dir` and read from the
tenant-local pool.

Why:
- Otherwise pool API isolation can be bypassed through agent initialization.
- It keeps all named pool-to-workspace copy paths aligned.

Alternatives considered:
- Leave agent initialization global and treat it as legacy behavior: rejected
  because it would reintroduce cross-tenant pool reads.

## Risks / Trade-offs

- [Missed helper path still falls back to global pool] → Audit every use of
  `get_skill_pool_dir()`, `read_skill_pool_manifest()`,
  `get_pool_skill_manifest_path()`, and `reconcile_pool_manifest()` in
  tenant-facing code and cover the key routes with tenant-isolation tests.
- [Backward compatibility assumptions around a shared pool] → Keep the change
  scoped to tenant-aware request paths and document that tenant pool management
  is local to the active tenant.
- [Signature churn across multiple helpers and services] → Introduce a single
  optional `working_dir` parameter pattern and update call sites consistently.
- [Tests may still pass through ambient default tenant behavior] → Use fixtures
  with two named tenants and assert on concrete per-tenant filesystem paths.

## Migration Plan

1. Update `SkillPoolService` and pool helper functions to accept explicit
   tenant `working_dir`.
2. Update `/skills/pool*` routes and hub import helpers to pass the current
   tenant directory explicitly.
3. Update agent workspace initialization paths that seed from the pool.
4. Add or update tests for two-tenant isolation on pool list, create, config,
   builtin update/import, upload, and download flows.
5. Verify no tenant-scoped request path writes to `WORKING_DIR/skill_pool`.

Rollback is straightforward: restore the previous no-argument helper/service
calls. Tenant-local pools created during the change remain valid on disk, but
tenant-scoped API behavior would revert to global-pool semantics.

## Open Questions

- Should there remain any explicitly supported admin-only global pool workflow,
  or should all request-path pool management be tenant-local?
  Recommended answer: tenant-scoped request paths should be tenant-local only;
  any future global workflow should use a separate explicit admin surface.
