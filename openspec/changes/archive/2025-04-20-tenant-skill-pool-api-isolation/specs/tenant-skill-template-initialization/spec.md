## ADDED Requirements

### Requirement: Named pool skill seeding uses the tenant-local pool
After tenant bootstrap has materialized tenant-local skill state, any workspace
initialization path that seeds skills by explicit `skill_names` SHALL copy those
skills from the same tenant's local `WORKING_DIR/<tenant_id>/skill_pool`.

#### Scenario: Agent workspace initialization reads from the current tenant pool
- **GIVEN** tenant `tenant-a` has skill `guidance` in
  `WORKING_DIR/tenant-a/skill_pool`
- **AND** tenant `tenant-b` has a different skill directory with the same name
  in `WORKING_DIR/tenant-b/skill_pool`
- **WHEN** the backend initializes a workspace for tenant `tenant-a` with
  `skill_names=["guidance"]`
- **THEN** the backend SHALL copy `guidance` from
  `WORKING_DIR/tenant-a/skill_pool/guidance`
- **AND** the backend SHALL NOT copy from
  `WORKING_DIR/tenant-b/skill_pool/guidance`

#### Scenario: Tenant-scoped workspace initialization does not read the global pool
- **WHEN** a tenant-scoped workspace initialization path seeds skills by
  explicit `skill_names`
- **THEN** the backend SHALL use the tenant-local `skill_pool` as the source
- **AND** the backend SHALL NOT fall back to the global `WORKING_DIR/skill_pool`
