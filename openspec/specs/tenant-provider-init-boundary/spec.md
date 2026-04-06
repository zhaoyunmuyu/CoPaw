## ADDED Requirements

### Requirement: Provider initialization occurs only at provider feature boundaries
The backend SHALL initialize tenant provider storage only when a request or runtime path actually uses provider-backed functionality. Generic tenant middleware MUST NOT materialize tenant provider storage as part of request entry.

#### Scenario: Non-provider tenant request does not initialize provider storage
- **WHEN** a tenant-scoped request enters the backend and does not access provider APIs, local model APIs, or runtime model creation
- **THEN** the backend SHALL process the request without creating or copying tenant provider storage

#### Scenario: Provider API first use initializes tenant provider storage
- **WHEN** a tenant first accesses a provider management API and tenant provider storage does not yet exist
- **THEN** the backend SHALL initialize tenant provider storage before serving the provider operation

#### Scenario: Runtime model creation initializes tenant provider storage
- **WHEN** a tenant first reaches a model creation path that requires provider-backed model resolution and tenant provider storage does not yet exist
- **THEN** the backend SHALL initialize tenant provider storage before constructing the model

### Requirement: Tenant workspace bootstrap remains workspace-scoped
The backend SHALL keep tenant workspace bootstrap focused on workspace concerns and MUST NOT treat workspace bootstrap as evidence that provider storage has already been initialized.

#### Scenario: Workspace bootstrap succeeds without provider readiness
- **WHEN** tenant workspace bootstrap completes for a tenant that has never used provider features
- **THEN** the tenant workspace SHALL be considered bootstrapped even if tenant provider storage does not exist yet

#### Scenario: Provider readiness is established independently from workspace bootstrap
- **WHEN** a tenant has already been workspace-bootstrapped but later accesses a provider feature for the first time
- **THEN** the backend SHALL initialize tenant provider storage at that provider feature boundary rather than requiring a new workspace bootstrap step
