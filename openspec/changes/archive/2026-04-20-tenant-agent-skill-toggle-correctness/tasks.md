## 1. Tenant-aware reload targeting

- [x] 1.1 Update `src/swe/app/utils.py` so scheduled agent reloads can carry
  the current `tenant_id` into `MultiAgentManager.reload_agent()`.
- [x] 1.2 Update single workspace skill enable/disable routes in
  `src/swe/app/routers/skills.py` to schedule reload for the same
  tenant-agent runtime that owns the mutated workspace.

## 2. Batch workspace skill convergence

- [x] 2.1 Update batch workspace skill enable/disable routes in
  `src/swe/app/routers/skills.py` to schedule one runtime reload after the
  batch when at least one mutation succeeds.
- [x] 2.2 Ensure failed or no-op workspace skill mutation batches do not
  schedule unnecessary reloads.

## 3. Regression coverage

- [x] 3.1 Add tenant-scoped router tests proving single-skill enable/disable
  reload the current tenant-agent runtime rather than a global or sibling
  runtime.
- [x] 3.2 Add tests proving batch enable/disable mutations trigger one reload
  for the current tenant-agent runtime when any item succeeds.
- [x] 3.3 Add tests proving workspace skill mutations do not reload other
  agents or other tenants.
