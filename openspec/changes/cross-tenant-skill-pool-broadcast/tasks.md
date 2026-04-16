## 1. Backend API surface

- [x] 1.1 Add request/response models for discovered tenant listing and cross-tenant default-agent broadcast in `src/swe/app/routers/skills.py`
- [x] 1.2 Add `GET /api/skills/pool/broadcast/tenants` to return discovered tenant IDs
- [x] 1.3 Add `POST /api/skills/pool/broadcast/default-agents` to accept `skill_names`, `target_tenant_ids`, and `overwrite`

## 2. Backend orchestration

- [x] 2.1 Validate that every requested source skill exists in the active tenant's pool before target fan-out begins
- [x] 2.2 Add target-tenant bootstrap orchestration using `ensure_seeded_bootstrap()` before applying writes
- [x] 2.3 Implement explicit overwrite-to-pool helper logic for selected skills in target tenant `skill_pool`
- [x] 2.4 Implement explicit overwrite-to-default-workspace helper logic for selected skills in target tenant `workspaces/default/skills`
- [x] 2.5 Keep broadcast semantics additive: selected skills overwrite, unselected skills remain untouched
- [x] 2.6 Return per-tenant success/failure results without whole-batch rollback

## 3. Frontend skill-pool page

- [x] 3.1 Update `console/src/api/modules/skill.ts` with tenant discovery and cross-tenant broadcast API calls
- [x] 3.2 Update `console/src/api/types/skill.ts` with broadcast tenant/result response types
- [x] 3.3 Replace workspace selection in `console/src/pages/Agent/SkillPool/components/BroadcastModal.tsx` with tenant selection UI
- [x] 3.4 Add manual tenant ID entry in the broadcast modal for not-yet-bootstrapped targets
- [x] 3.5 Update `console/src/pages/Agent/SkillPool/index.tsx` to call the new cross-tenant broadcast API and present per-tenant results
- [x] 3.6 Update relevant i18n copy to explain that broadcast targets each selected tenant's skill-pool baseline and `default` agent

## 4. Verification

- [x] 4.1 Add backend tests for broadcasting to an already bootstrapped tenant
- [x] 4.2 Add backend tests for broadcasting to a tenant that is not bootstrapped yet
- [x] 4.3 Add backend tests for additive overwrite semantics that preserve unselected target skills
- [x] 4.4 Add backend tests for per-tenant partial success behavior
- [x] 4.5 Add backend tests that new agents created after broadcast inherit the updated target tenant pool baseline
- [x] 4.6 Add frontend or integration coverage for tenant selection, manual tenant entry, and broadcast result display
