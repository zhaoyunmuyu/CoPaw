## Why

Workspace skill enable/disable APIs already resolve the current workspace from
the active tenant and agent request context, but runtime convergence is not
correct: single-skill mutations schedule reload by `agent_id` only and can lose
tenant scope, while batch enable/disable mutations do not reload the runtime at
all. That can leave the wrong runtime refreshed or the current runtime stale
after a successful workspace skill change.

## What Changes

- Make workspace skill enable/disable reload targeting explicit at the
  `tenant + agent` boundary instead of reloading by `agent_id` alone.
- Require successful batch workspace skill enable/disable operations to trigger
  runtime convergence for the same tenant-agent workspace.
- Keep workspace skill manifest writes scoped to the current tenant-agent
  workspace and ensure runtime refresh does not spill into sibling tenants or
  other agents.
- Add regression tests covering single-skill and batch-skill mutations for
  tenant-local reload targeting and no-cross-agent behavior.

## Capabilities

### New Capabilities
- `workspace-skill-runtime-management`: Workspace skill mutations operate on the
  current tenant-agent workspace state and converge the runtime for that same
  tenant-agent workspace only.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `src/swe/app/routers/skills.py`
  - `src/swe/app/utils.py`
  - `src/swe/app/multi_agent_manager.py`
- Affected behavior:
  - single-skill `POST /api/skills/{skill_name}/enable`
  - single-skill `POST /api/skills/{skill_name}/disable`
  - batch `POST /api/skills/batch-enable`
  - batch `POST /api/skills/batch-disable`
- Testing impact:
  - tenant-scoped router tests for workspace skill mutations
  - reload-targeting tests for current tenant-agent runtime convergence
