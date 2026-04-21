## Why

Tenant first-access bootstrap now seeds `skill_pool` and default workspace
skills into tenant-local directories, but the `/api/skills/pool*` management
endpoints still mostly operate on the global `WORKING_DIR/skill_pool`.
That breaks tenant isolation after bootstrap: tenants can observe, mutate, or
sync against the wrong pool state.

## What Changes

- Make `/api/skills/pool*` routes resolve and operate on the current tenant's
  `WORKING_DIR/<tenant>/skill_pool`.
- Add tenant-aware `working_dir` plumbing to skill-pool services and helper
  functions that currently default to the global pool path.
- Keep workspace-side resolution tenant-aware for upload/download flows while
  switching their pool-side source and target to the same tenant scope.
- Update agent workspace initialization paths that seed skills by name from the
  pool so they read from the tenant-scoped pool instead of the global pool.
- Add regression tests proving pool listing, config updates, builtin sync,
  upload, and download do not cross tenant boundaries.

## Capabilities

### New Capabilities
- `tenant-scoped-skill-pool-management`: Skill-pool management APIs and helper
  paths operate on the active tenant's local `skill_pool` and must not fall
  back to a shared global pool during tenant-scoped requests.

### Modified Capabilities
- `tenant-skill-template-initialization`: Workspace initialization paths that
  copy named skills from a pool must use the tenant's own `skill_pool` after
  tenant bootstrap has materialized tenant-local skill state.

## Impact

- Affected code:
  - `src/swe/app/routers/skills.py`
  - `src/swe/agents/skills_manager.py`
  - `src/swe/agents/skills_hub.py`
  - `src/swe/app/routers/agents.py`
- Affected behavior:
  - `/api/skills/pool*` listing, refresh, create, save, delete, config, builtin
    import/update, zip import, hub import, upload, and download
  - agent workspace initialization when seeding by `skill_names`
- Unchanged behavior:
  - first-access tenant bootstrap still seeds tenant-local pool and workspace
    skills as before
  - workspace-local skill APIs remain scoped to the selected tenant workspace
- Testing impact:
  - tenant-scoped pool router coverage
  - tenant-scoped skill-pool service coverage
  - agent workspace initialization regression coverage
