## 1. Tenant-aware pool primitives

- [x] 1.1 Update `SkillPoolService` in `src/swe/agents/skills_manager.py` to
  accept tenant `working_dir` and use it for all pool reads and writes.
- [x] 1.2 Add explicit `working_dir` plumbing to pool helper functions that
  still default to the global pool, including builtin candidate listing, pool
  sync status, builtin update, and related manifest/path helpers.
- [x] 1.3 Update hub-import helpers in `src/swe/agents/skills_hub.py` to pass
  the tenant-scoped pool working directory into pool service operations.

## 2. Tenant-scoped pool API routing

- [x] 2.1 Update `src/swe/app/routers/skills.py` pool list, refresh, builtin,
  config, create/save/delete, zip import, and batch delete endpoints to resolve
  the current tenant working directory and pass it explicitly.
- [x] 2.2 Update pool upload/download flows in
  `src/swe/app/routers/skills.py` so both workspace resolution and pool
  resolution stay within the current tenant scope.
- [x] 2.3 Verify tenant-scoped pool requests fail closed instead of falling back
  to the global `WORKING_DIR/skill_pool`.

## 3. Workspace initialization alignment

- [x] 3.1 Update agent workspace initialization in
  `src/swe/app/routers/agents.py` so `skill_names` seeding reads from the
  tenant-local pool rather than the global pool.
- [x] 3.2 Audit other tenant-facing pool-to-workspace copy paths and remove any
  remaining global-pool bypasses.

## 4. Verification and regression coverage

- [x] 4.1 Add router or service tests proving `GET /api/skills/pool` and pool
  config operations return different results for different tenants.
- [x] 4.2 Add tests proving pool create/save/delete/import-builtin/update-builtin
  mutate only the current tenant's `skill_pool`.
- [x] 4.3 Add tests proving pool upload/download flows do not cross tenant
  boundaries.
- [x] 4.4 Add tests proving agent workspace initialization seeded by
  `skill_names` reads from the tenant-local pool only.
