## ADDED Requirements

### Requirement: Workspace skill mutations stay bound to the current tenant-agent workspace
The backend SHALL apply workspace skill enable and disable mutations only to the
workspace resolved for the current tenant-scoped agent request, and SHALL NOT
mutate skill state for another tenant or another agent workspace.

#### Scenario: Single-skill mutation updates only the current tenant-agent workspace
- **GIVEN** tenant `tenant-a` and tenant `tenant-b` each have an agent named
  `default`
- **AND** each workspace contains a skill entry named `docx`
- **WHEN** tenant `tenant-a` calls a workspace skill enable or disable API for
  agent `default`
- **THEN** the backend SHALL update only
  `WORKING_DIR/tenant-a/workspaces/default/skill.json`
- **AND** the backend SHALL NOT modify
  `WORKING_DIR/tenant-b/workspaces/default/skill.json`

#### Scenario: Batch workspace mutation stays within the selected agent workspace
- **GIVEN** tenant `tenant-a` has agents `default` and `qa`
- **AND** both workspaces contain one or more skill entries
- **WHEN** tenant `tenant-a` calls a batch workspace skill enable or disable API
  scoped to agent `default`
- **THEN** the backend SHALL update only
  `WORKING_DIR/tenant-a/workspaces/default/skill.json`
- **AND** the backend SHALL NOT modify
  `WORKING_DIR/tenant-a/workspaces/qa/skill.json`

### Requirement: Successful workspace skill mutations converge the same tenant-agent runtime
When a workspace skill mutation succeeds, the backend SHALL converge runtime
skill state for that same tenant-agent workspace and SHALL NOT reload a
different tenant or agent runtime.

#### Scenario: Single-skill mutation reloads the current tenant-agent runtime
- **GIVEN** tenant `tenant-a` has a loaded runtime for agent `default`
- **WHEN** tenant `tenant-a` successfully enables or disables a workspace skill
  for agent `default`
- **THEN** the backend SHALL schedule reload for runtime identity
  `tenant-a + default`
- **AND** the backend SHALL NOT schedule reload for a global `default` runtime
  or another tenant's `default` runtime

#### Scenario: Batch mutation reloads once after successful workspace changes
- **GIVEN** tenant `tenant-a` has a loaded runtime for agent `default`
- **WHEN** tenant `tenant-a` submits a batch workspace skill enable or disable
  request for agent `default`
- **AND** at least one requested skill mutation succeeds
- **THEN** the backend SHALL schedule exactly one reload for runtime identity
  `tenant-a + default`

#### Scenario: Failed batch mutation does not trigger reload
- **GIVEN** tenant `tenant-a` has a loaded runtime for agent `default`
- **WHEN** tenant `tenant-a` submits a batch workspace skill mutation request
  for agent `default`
- **AND** every requested mutation fails or leaves no workspace state change
- **THEN** the backend SHALL NOT schedule a runtime reload

#### Scenario: Unloaded runtime remains lazy after workspace mutation
- **GIVEN** tenant `tenant-a` does not currently have a loaded runtime for agent
  `default`
- **WHEN** tenant `tenant-a` successfully mutates workspace skill state for
  agent `default`
- **THEN** the backend SHALL persist the updated workspace manifest state
- **AND** the next normal runtime load for `tenant-a + default` SHALL read that
  updated manifest state
