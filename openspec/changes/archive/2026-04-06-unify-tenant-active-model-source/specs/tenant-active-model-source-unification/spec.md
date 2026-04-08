## ADDED Requirements

### Requirement: Runtime active model resolution uses provider-backed tenant state
The system SHALL resolve the current tenant's active model from `~/.swe.secret/{tenant}/providers/active_model.json` through tenant-aware `ProviderManager` APIs, and SHALL NOT require `tenant_models.json` on the runtime path.

#### Scenario: Runtime resolves active model for tenant
- **GIVEN** tenant `tenant-a` has `~/.swe.secret/tenant-a/providers/active_model.json`
- **WHEN** runtime code resolves the active model for chat execution
- **THEN** the system SHALL use `ProviderManager.get_instance("tenant-a")` to read the active model
- **AND** the resolved provider and model SHALL match the contents of that tenant's `active_model.json`

#### Scenario: Runtime ignores legacy tenant_models.json when new source exists
- **GIVEN** tenant `tenant-a` has both `tenant_models.json` and `providers/active_model.json`
- **WHEN** runtime code resolves the active model
- **THEN** the system SHALL treat `providers/active_model.json` as the source of truth
- **AND** the system SHALL NOT prefer `tenant_models.json`

### Requirement: Active model writes are single-source and tenant-scoped
The system SHALL persist tenant active model changes only to `~/.swe.secret/{tenant}/providers/active_model.json` and SHALL NOT perform long-term dual writes to `tenant_models.json`.

#### Scenario: Console changes active model
- **GIVEN** tenant `tenant-a` selects a new provider/model in the console
- **WHEN** the backend handles the active model update
- **THEN** the system SHALL write the selection to `~/.swe.secret/tenant-a/providers/active_model.json`
- **AND** the system SHALL NOT require writing `tenant_models.json` for the change to take effect

### Requirement: Legacy tenant configuration can be recovered during migration
The system SHALL provide a temporary migration-compatible read path for tenants that still have legacy `tenant_models.json` but do not yet have `providers/active_model.json`.

#### Scenario: Recover active model from legacy tenant config
- **GIVEN** tenant `tenant-a` has `tenant_models.json`
- **AND** tenant `tenant-a` does not yet have `providers/active_model.json`
- **WHEN** the system first resolves the tenant's active model
- **THEN** the system SHALL extract the legacy active slot from `tenant_models.json`
- **AND** the system SHALL persist the recovered provider/model to `~/.swe.secret/tenant-a/providers/active_model.json`

#### Scenario: No long-term fallback after recovery
- **GIVEN** the tenant's `providers/active_model.json` has been created from legacy state
- **WHEN** subsequent active model reads occur
- **THEN** the system SHALL use `providers/active_model.json`
- **AND** the system SHALL NOT continue to depend on `tenant_models.json` for normal operation

### Requirement: Provider APIs expose one active-model contract
The system SHALL use `/models` as the primary API contract for reading and setting tenant active model state.

#### Scenario: Read active model from /models/active
- **GIVEN** tenant `tenant-a` has an active model configured
- **WHEN** a client calls `GET /models/active`
- **THEN** the response SHALL reflect the active model stored in `~/.swe.secret/tenant-a/providers/active_model.json`

#### Scenario: Legacy /providers endpoint does not require tenant_models.json
- **GIVEN** the `/providers` endpoint remains available
- **WHEN** a client calls the endpoint for tenant `tenant-a`
- **THEN** the endpoint SHALL be backed by provider state rather than `tenant_models.json`
- **OR** the system SHALL explicitly deprecate the endpoint and direct clients to `/models`

### Requirement: Chat model selector uses tenant-level active model semantics
The system SHALL align frontend chat model switching with the backend's tenant-level active model contract.

#### Scenario: Chat model selector no longer sends unsupported agent scope
- **GIVEN** a user switches models in the Chat UI
- **WHEN** the frontend sends the active model update request
- **THEN** the request SHALL use the backend-supported tenant/global scope semantics
- **AND** the request SHALL NOT depend on agent-scoped active model storage

#### Scenario: Backend tolerates old agent scope during transition
- **GIVEN** an older frontend sends `scope=agent`
- **WHEN** the backend receives the request during the migration window
- **THEN** the backend SHALL normalize the request to the supported tenant-level active model behavior
- **OR** return a clear deprecation-compatible response path defined by the migration plan
