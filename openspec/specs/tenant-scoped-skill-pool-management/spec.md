# tenant-scoped-skill-pool-management Specification

## Purpose

This specification defines how tenant-scoped `/api/skills/pool*` operations must use the active tenant's local skill pool and never fall back to the global pool during tenant-scoped requests.

## Requirements

### Requirement: Tenant-scoped pool APIs use the current tenant skill pool
The backend SHALL serve tenant-scoped `/api/skills/pool*` operations from the
active tenant's local `WORKING_DIR/<tenant_id>/skill_pool` and MUST NOT fall
back to the global `WORKING_DIR/skill_pool` during tenant-scoped requests.

#### Scenario: Pool listing reads only the current tenant pool
- **GIVEN** tenant `tenant-a` has skill `alpha` in
  `WORKING_DIR/tenant-a/skill_pool`
- **AND** tenant `tenant-b` has skill `beta` in
  `WORKING_DIR/tenant-b/skill_pool`
- **WHEN** a tenant-scoped request for `tenant-a` calls `GET /api/skills/pool`
- **THEN** the response SHALL include `alpha`
- **AND** the response SHALL NOT include `beta`

#### Scenario: Pool mutation writes only the current tenant pool manifest
- **WHEN** a tenant-scoped request for `tenant-a` creates, edits, deletes, or
  updates config for a pool skill
- **THEN** the backend SHALL mutate only
  `WORKING_DIR/tenant-a/skill_pool` and its manifest state
- **AND** the backend SHALL NOT modify
  `WORKING_DIR/tenant-b/skill_pool` or the global `WORKING_DIR/skill_pool`

#### Scenario: Missing tenant context does not authorize global pool fallback
- **WHEN** a tenant-scoped pool helper or route executes without an active
  tenant context or explicit tenant working directory
- **THEN** the backend SHALL reject the request or fail closed
- **AND** the backend SHALL NOT substitute the global `WORKING_DIR/skill_pool`

### Requirement: Pool builtin operations are tenant-local
Builtin skill discovery, import, refresh, and update operations SHALL resolve
against the active tenant's local skill pool.

#### Scenario: Builtin source status is computed per tenant
- **GIVEN** tenant `tenant-a` has imported builtin skill `guidance`
- **AND** tenant `tenant-b` has not imported `guidance`
- **WHEN** each tenant requests builtin source or sync status for its pool
- **THEN** the backend SHALL report status from that tenant's own
  `skill_pool` state only

#### Scenario: Builtin import updates only the current tenant pool
- **WHEN** a tenant-scoped request for `tenant-a` imports or updates a builtin
  skill in the pool
- **THEN** the backend SHALL create or update the builtin under
  `WORKING_DIR/tenant-a/skill_pool`
- **AND** the backend SHALL NOT modify another tenant's pool state

### Requirement: Pool upload and download flows keep workspace and pool in the same tenant scope
Workspace-to-pool upload and pool-to-workspace download flows SHALL use the
current tenant's workspace set together with that same tenant's local
`skill_pool`.

#### Scenario: Workspace upload targets the current tenant pool
- **GIVEN** tenant `tenant-a` owns workspace `default`
- **WHEN** tenant `tenant-a` uploads a workspace skill to the pool
- **THEN** the backend SHALL write the uploaded skill into
  `WORKING_DIR/tenant-a/skill_pool`
- **AND** the backend SHALL NOT write into another tenant's pool

#### Scenario: Pool download reads from the current tenant pool
- **GIVEN** tenant `tenant-a` has skill `alpha` in its local pool
- **AND** tenant `tenant-b` has skill `beta` in its local pool
- **WHEN** tenant `tenant-a` downloads `alpha` into one of its workspaces
- **THEN** the backend SHALL copy from
  `WORKING_DIR/tenant-a/skill_pool/alpha`
- **AND** the backend SHALL NOT source content from
  `WORKING_DIR/tenant-b/skill_pool/beta`
