## 1. Agent creation default skill resolution

- [x] 1.1 Update `src/swe/app/routers/agents.py` so `create_agent` resolves
  omitted `skill_names` to the full set of skills from the current tenant's
  `skill_pool` manifest.
- [x] 1.2 Preserve explicit request semantics in `create_agent`: non-empty
  `skill_names` stays a selective import, and explicit `[]` stays an empty
  workspace skill set.

## 2. Workspace initialization behavior checks

- [x] 2.1 Confirm `_initialize_agent_workspace` continues to copy only the
  names it is given and does not change QA agent initialization behavior.
- [x] 2.2 Ensure new agent workspace skill manifests are reconciled correctly
  for both default full import and explicit empty import cases.

## 3. Regression coverage

- [x] 3.1 Add tests for `POST /api/agents` proving omitted `skill_names`
  imports all tenant-local pool skills into the new agent workspace.
- [x] 3.2 Add tests proving explicit `skill_names=["..."]` still imports only
  the requested subset from the current tenant pool.
- [x] 3.3 Add tests proving explicit `skill_names=[]` creates an agent without
  copied pool skills.
