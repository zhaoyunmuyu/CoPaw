## Why

The skill-pool page can already broadcast pool skills into workspaces within the
current tenant, but it cannot distribute a selected skill baseline across
multiple tenant namespaces.

The requested workflow is different from tenant-local workspace broadcast:
- operators need to choose one or more tenant IDs from the skill-pool page
- the selected skills must become part of each target tenant's skill-pool
  baseline
- the same selected skills must also be equipped onto each target tenant's
  `default` agent immediately
- target tenants may not be bootstrapped yet
- failures must be isolated per tenant so one broken target does not block the
  others

Without an explicit cross-tenant broadcast flow, operators would have to switch
tenant context and repeat the same pool and workspace operations manually,
which is slow and error-prone.

## What Changes

- Add a cross-tenant skill-pool broadcast API that accepts selected skill names
  plus selected tenant IDs and applies the broadcast per target tenant.
- Add a tenant discovery API for the skill-pool page, while allowing manual
  tenant ID entry for targets that are known upstream but not bootstrapped yet.
- Make each target tenant broadcast perform runtime-safe seeded bootstrap before
  applying selected skills when the tenant scaffold is missing or incomplete.
- Update the skill-pool page broadcast modal from workspace selection to tenant
  selection, with the broadcast target fixed to each tenant's `default` agent.
- Use additive overwrite semantics:
  - selected same-name skills overwrite target pool and default-agent copies
  - unselected target-tenant skills remain untouched
  - rename flows are not part of this broadcast surface
- Return per-tenant success and failure results instead of making the whole
  batch transactional.

## Capabilities

### New Capabilities
- `cross-tenant-skill-pool-broadcast`: The system can broadcast selected pool
  skills from the current tenant into multiple target tenants by updating each
  target tenant's skill-pool baseline and `default` agent workspace with
  additive overwrite semantics.

### Modified Capabilities
- None.

## Impact

- Affected backend modules:
  - `src/swe/app/routers/skills.py`
  - `src/swe/agents/skills_manager.py`
  - `src/swe/app/workspace/tenant_initializer.py`
  - `src/swe/config/utils.py`
- Affected frontend modules:
  - `console/src/pages/Agent/SkillPool/index.tsx`
  - `console/src/pages/Agent/SkillPool/components/BroadcastModal.tsx`
  - `console/src/api/modules/skill.ts`
  - `console/src/api/types/skill.ts`
- Affected behavior:
  - skill-pool broadcast no longer targets arbitrary workspaces from the modal
  - skill-pool broadcast can target multiple tenant IDs and fixed `default`
    agents
- Unchanged behavior:
  - tenant-local skill-pool CRUD and tenant-local pool-to-workspace download
    semantics remain unchanged
  - broadcast does not delete unselected target skills
  - broadcast does not introduce rename or full-mirror synchronization
- Testing impact:
  - cross-tenant backend broadcast coverage
  - bootstrap-before-broadcast coverage
  - skill-pool page tenant selection coverage
