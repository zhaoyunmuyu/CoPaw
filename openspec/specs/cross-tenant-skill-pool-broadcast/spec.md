## ADDED Requirements

### Requirement: The skill-pool page can broadcast selected pool skills to multiple target tenants
The system SHALL let the active tenant select one or more pool skills and
broadcast them to multiple target tenant IDs from the skill-pool page.

#### Scenario: Broadcast accepts multiple target tenants
- **GIVEN** the active tenant pool contains skills `guidance` and `playbook`
- **WHEN** an operator submits a broadcast request with target tenants
  `tenant-a` and `tenant-b`
- **THEN** the backend SHALL process both target tenants in the same request
- **AND** the backend SHALL evaluate the selected source skills from the active
  tenant's local pool only

### Requirement: Broadcast bootstraps target tenants before applying selected skills
The system SHALL support target tenant IDs that do not yet have a runtime
scaffold by bootstrapping them before applying broadcast writes.

#### Scenario: Broadcast to a not-yet-bootstrapped tenant
- **GIVEN** target tenant `tenant-new` does not yet have a complete
  `WORKING_DIR/tenant-new` scaffold
- **WHEN** the operator broadcasts selected skills to `tenant-new`
- **THEN** the system SHALL run runtime-safe seeded bootstrap for `tenant-new`
- **AND** the system SHALL apply the selected skill writes only after bootstrap
  succeeds
- **AND** the system SHALL NOT require QA-agent creation or workspace runtime
  startup as part of the broadcast

### Requirement: Broadcast updates both target tenant skill-pool baseline and target tenant default agent
For every successful target tenant, the system SHALL apply the selected skills
to both the target tenant `skill_pool` and the target tenant `default` agent
workspace.

#### Scenario: Successful broadcast updates both storage surfaces
- **GIVEN** target tenant `tenant-a` is selected for broadcast
- **WHEN** selected skill `guidance` is broadcast successfully to `tenant-a`
- **THEN** `WORKING_DIR/tenant-a/skill_pool/guidance` SHALL contain the
  broadcast skill content
- **AND** `WORKING_DIR/tenant-a/workspaces/default/skills/guidance` SHALL
  contain the same broadcast skill content

#### Scenario: Future agent creation inherits the updated target baseline
- **GIVEN** target tenant `tenant-a` received broadcast skill `guidance`
- **WHEN** a new agent is later created in `tenant-a` without an explicit
  `skill_names` override
- **THEN** the new agent initialization SHALL inherit `guidance` from
  `tenant-a`'s updated local `skill_pool`

### Requirement: Broadcast uses additive overwrite semantics for selected skills
The broadcast flow SHALL overwrite same-name copies of selected skills in the
target tenant while leaving unselected target-tenant skills untouched.

#### Scenario: Selected same-name skill is overwritten
- **GIVEN** target tenant `tenant-a` already has skill `guidance`
- **AND** the active tenant broadcasts selected skill `guidance`
- **WHEN** the broadcast succeeds for `tenant-a`
- **THEN** the target tenant pool copy of `guidance` SHALL be replaced with the
  source tenant version
- **AND** the target tenant default workspace copy of `guidance` SHALL be
  replaced with the source tenant version

#### Scenario: Unselected target skills remain untouched
- **GIVEN** target tenant `tenant-a` contains local skills `guidance` and
  `tenant-local-only`
- **WHEN** the operator broadcasts only selected skill `guidance`
- **THEN** `guidance` SHALL be updated
- **AND** `tenant-local-only` SHALL remain present and unchanged

### Requirement: Broadcast results are reported per target tenant
The broadcast flow SHALL isolate failures per target tenant and SHALL NOT roll
back already successful target tenants because another target failed.

#### Scenario: One target tenant fails while another succeeds
- **GIVEN** target tenants `tenant-a` and `tenant-b` are selected
- **AND** `tenant-a` can be updated successfully
- **AND** `tenant-b` encounters a validation or write failure
- **WHEN** the broadcast request completes
- **THEN** the response SHALL report success for `tenant-a`
- **AND** the response SHALL report failure details for `tenant-b`
- **AND** the successful updates already written for `tenant-a` SHALL remain in
  place

### Requirement: The skill-pool page supports discovered tenant selection and manual tenant entry
The broadcast UI SHALL help operators choose discovered tenants while also
allowing explicit tenant IDs that are not yet bootstrapped.

#### Scenario: Discovered tenants are shown for selection
- **WHEN** the skill-pool page opens the broadcast modal
- **THEN** the UI SHALL fetch and display the discovered tenant IDs available
  from the backend discovery route

#### Scenario: Operator enters a tenant ID that is not in the discovered list
- **GIVEN** tenant `tenant-new` is not yet present in the discovered tenant
  response
- **WHEN** the operator manually enters `tenant-new` as a broadcast target
- **THEN** the UI SHALL include `tenant-new` in the broadcast submission
- **AND** the backend SHALL treat it as a valid target candidate subject to
  normal tenant ID validation and bootstrap/write success
