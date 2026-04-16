## ADDED Requirements

### Requirement: New agent creation defaults to all tenant pool skills
The system SHALL seed a new agent workspace with every skill currently
available in the active tenant's local `skill_pool` when the create-agent
request omits an explicit `skill_names` selection.

#### Scenario: Omitted skill selection copies all tenant pool skills
- **GIVEN** tenant `tenant-a` has skills `guidance` and `docx` in
  `WORKING_DIR/tenant-a/skill_pool`
- **WHEN** the backend creates a new agent for tenant `tenant-a` and the
  request omits `skill_names`
- **THEN** the backend SHALL copy both `guidance` and `docx` into the new
  workspace's `skills/` directory
- **AND** the workspace skill manifest SHALL contain entries for both copied
  skills

#### Scenario: Explicit skill selection still limits seeded skills
- **GIVEN** tenant `tenant-a` has skills `guidance` and `docx` in
  `WORKING_DIR/tenant-a/skill_pool`
- **WHEN** the backend creates a new agent for tenant `tenant-a` with
  `skill_names=["guidance"]`
- **THEN** the backend SHALL copy `guidance` into the new workspace's
  `skills/` directory
- **AND** the backend SHALL NOT copy `docx`

#### Scenario: Explicit empty skill selection creates an agent without skills
- **GIVEN** tenant `tenant-a` has one or more skills in
  `WORKING_DIR/tenant-a/skill_pool`
- **WHEN** the backend creates a new agent for tenant `tenant-a` with
  `skill_names=[]`
- **THEN** the backend SHALL NOT copy any pool skills into the new workspace
- **AND** the workspace skill manifest SHALL remain empty after initialization
