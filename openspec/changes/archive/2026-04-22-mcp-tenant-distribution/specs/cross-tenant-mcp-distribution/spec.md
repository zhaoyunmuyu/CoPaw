## ADDED Requirements

### Requirement: The MCP page can distribute selected clients to multiple target tenants
The system SHALL let the active tenant select one or more MCP clients from the
currently selected agent and distribute them to multiple target tenant IDs from
the MCP page.

#### Scenario: Distribution accepts multiple target tenants
- **GIVEN** the current tenant selected agent contains MCP clients
  `filesystem` and `fetch`
- **WHEN** an operator submits a distribution request with target tenants
  `tenant-a` and `tenant-b`
- **THEN** the backend SHALL process both target tenants in the same request
- **AND** the backend SHALL evaluate the selected source MCP clients from the
  current tenant's current agent only

### Requirement: Distribution targets the target tenant default agent
For every successful target tenant, the system SHALL write distributed MCP
clients into the target tenant `default` agent configuration.

#### Scenario: Successful distribution writes to target default agent
- **GIVEN** target tenant `tenant-a` is selected for distribution
- **WHEN** selected MCP client `filesystem` is distributed successfully to
  `tenant-a`
- **THEN** `WORKING_DIR/tenant-a/workspaces/default/agent.json` SHALL contain
  the distributed `filesystem` client config under `mcp.clients`
- **AND** the system SHALL NOT require the target tenant to contain an agent
  with the same ID as the source agent

### Requirement: Distribution bootstraps target tenants before applying MCP writes
The system SHALL support target tenant IDs that do not yet have a runtime
scaffold by bootstrapping them before applying MCP configuration writes.

#### Scenario: Distribution to a not-yet-bootstrapped tenant
- **GIVEN** target tenant `tenant-new` does not yet have a complete
  `WORKING_DIR/tenant-new` scaffold
- **WHEN** the operator distributes selected MCP clients to `tenant-new`
- **THEN** the system SHALL run runtime-safe seeded bootstrap for `tenant-new`
- **AND** the system SHALL apply MCP writes only after bootstrap succeeds
- **AND** the system SHALL NOT require QA-agent creation or workspace runtime
  startup as part of the bootstrap step

### Requirement: Distribution copies the original full MCP client configuration
The distribution flow SHALL copy the original source MCP client configuration
for each selected `client_key`, including secret-bearing fields, instead of
using masked console response values.

#### Scenario: Distribution preserves original env and header values
- **GIVEN** source MCP client `fetch` contains original `headers` and `env`
  values in the source agent config
- **WHEN** `fetch` is distributed to a target tenant
- **THEN** the target tenant SHALL receive the original stored `headers` and
  `env` values
- **AND** the target tenant SHALL NOT receive masked placeholder values from
  the console read API

#### Scenario: Distribution preserves enabled state and transport settings
- **GIVEN** source MCP client `filesystem` is disabled and uses `stdio`
  transport
- **WHEN** `filesystem` is distributed to a target tenant
- **THEN** the target tenant copy of `filesystem` SHALL remain disabled
- **AND** the target tenant copy SHALL preserve the source transport, launch,
  and connection settings unchanged

### Requirement: Distribution uses additive overwrite semantics for selected client keys
The distribution flow SHALL overwrite same-key copies of selected MCP clients in
the target tenant while leaving unselected target MCP clients untouched.

#### Scenario: Selected same-key MCP client is overwritten
- **GIVEN** target tenant `tenant-a` already contains MCP client `fetch`
- **AND** the active tenant distributes selected client `fetch`
- **WHEN** the distribution succeeds for `tenant-a`
- **THEN** the target tenant `fetch` client config SHALL be replaced with the
  source tenant version

#### Scenario: Unselected target MCP clients remain untouched
- **GIVEN** target tenant `tenant-a` contains MCP clients `fetch` and
  `tenant-local-only`
- **WHEN** the operator distributes only selected client `fetch`
- **THEN** `fetch` SHALL be updated
- **AND** `tenant-local-only` SHALL remain present and unchanged

### Requirement: Distribution requires explicit overwrite in v1
The MCP distribution API SHALL require `overwrite=true` for the first version.

#### Scenario: Request without overwrite is rejected
- **WHEN** an operator submits an MCP distribution request without
  `overwrite=true`
- **THEN** the backend SHALL reject the request
- **AND** the backend SHALL NOT apply writes to any target tenant

### Requirement: Distribution results are reported per target tenant
The distribution flow SHALL isolate failures per target tenant and SHALL NOT
roll back already successful target tenants because another target failed.

#### Scenario: One target tenant fails while another succeeds
- **GIVEN** target tenants `tenant-a` and `tenant-b` are selected
- **AND** `tenant-a` can be updated successfully
- **AND** `tenant-b` encounters a validation, write, or reload failure
- **WHEN** the distribution request completes
- **THEN** the response SHALL report success for `tenant-a`
- **AND** the response SHALL report failure details for `tenant-b`
- **AND** the successful updates already written for `tenant-a` SHALL remain in
  place

### Requirement: The MCP page supports discovered tenant selection and manual tenant entry
The MCP distribution UI SHALL help operators choose discovered tenants while
also allowing explicit tenant IDs that are not yet bootstrapped.

#### Scenario: Discovered tenants are shown for selection
- **WHEN** the MCP page opens the distribution modal
- **THEN** the UI SHALL fetch and display the discovered tenant IDs available
  from the backend discovery route

#### Scenario: Operator enters a tenant ID that is not in the discovered list
- **GIVEN** tenant `tenant-new` is not yet present in the discovered tenant
  response
- **WHEN** the operator manually enters `tenant-new` as a distribution target
- **THEN** the UI SHALL include `tenant-new` in the submission
- **AND** the backend SHALL treat it as a valid target candidate subject to
  normal tenant ID validation and bootstrap/write success
