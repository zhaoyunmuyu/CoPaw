# tenant-isolated-provider-storage Specification

## Purpose
TBD - created by archiving change tenant-isolated-provider-config. Update Purpose after archive.
## Requirements
### Requirement: Provider configuration stored per-tenant
The system SHALL store provider configurations in tenant-isolated directories, with each tenant having a separate `providers/` directory under their tenant secret directory.

#### Scenario: Default tenant uses global-like path
- **GIVEN** the system is configured with `SECRET_DIR = ~/.copaw.secret`
- **WHEN** the default tenant accesses provider configuration
- **THEN** the system SHALL use path `~/.copaw.secret/default/providers/`

#### Scenario: Named tenant has isolated storage
- **GIVEN** a tenant with ID "tenant-a" exists
- **WHEN** the tenant accesses provider configuration
- **THEN** the system SHALL use path `~/.copaw.secret/tenant-a/providers/`
- **AND** the path SHALL be inaccessible to other tenants

### Requirement: Tenant-specific API key isolation
The system SHALL ensure that API keys configured by one tenant are not accessible to other tenants.

#### Scenario: Tenant A configures API key
- **GIVEN** tenant "tenant-a" configures an API key for provider "openai"
- **WHEN** the configuration is saved
- **THEN** the API key SHALL be stored in `~/.copaw.secret/tenant-a/providers/builtin/openai.json`
- **AND** tenant "tenant-b" SHALL NOT be able to read this API key

#### Scenario: Different tenants have different API keys for same provider
- **GIVEN** tenant "tenant-a" has API key "sk-a" for provider "openai"
- **AND** tenant "tenant-b" has API key "sk-b" for provider "openai"
- **WHEN** each tenant uses the provider
- **THEN** tenant-a SHALL use API key "sk-a"
- **AND** tenant-b SHALL use API key "sk-b"

### Requirement: Per-tenant active model selection
The system SHALL maintain separate active model selections for each tenant.

#### Scenario: Tenant A changes active model
- **GIVEN** tenant "tenant-a" has active model "gpt-4o"
- **WHEN** tenant-a changes active model to "claude-opus"
- **THEN** the active model SHALL be stored in `~/.copaw.secret/tenant-a/providers/active_model.json`
- **AND** tenant "tenant-b" SHALL continue to use its previously configured active model

### Requirement: Automatic tenant configuration initialization
The system SHALL automatically initialize provider configuration for new tenants by copying from the default tenant.

#### Scenario: New tenant first access
- **GIVEN** a new tenant "new-tenant" makes its first request
- **AND** the default tenant has existing provider configuration
- **WHEN** the system processes the request
- **THEN** the system SHALL copy all provider configuration from `~/.copaw.secret/default/providers/` to `~/.copaw.secret/new-tenant/providers/`
- **AND** the new tenant SHALL be able to use providers immediately

#### Scenario: New tenant when default has no configuration
- **GIVEN** a new tenant "new-tenant" makes its first request
- **AND** the default tenant has no provider configuration
- **WHEN** the system processes the request
- **THEN** the system SHALL create empty directory structure at `~/.copaw.secret/new-tenant/providers/`
- **AND** the tenant SHALL receive appropriate "no provider configured" error

### Requirement: ProviderManager tenant-aware instance management
The system SHALL provide tenant-aware ProviderManager instances through an enhanced singleton pattern.

#### Scenario: Get instance for specific tenant
- **GIVEN** a tenant ID "tenant-a"
- **WHEN** code calls `ProviderManager.get_instance("tenant-a")`
- **THEN** the system SHALL return a ProviderManager instance configured for tenant-a
- **AND** subsequent calls with the same tenant ID SHALL return the same instance (cached)

#### Scenario: Backward compatibility for singleton access
- **GIVEN** existing code calls `ProviderManager.get_instance()` without arguments
- **WHEN** the code executes in non-tenant context
- **THEN** the system SHALL return the "default" tenant instance
- **AND** the code SHALL continue to work without modification

### Requirement: Middleware binds tenant provider context
The system SHALL bind tenant-specific provider configuration in the request context through middleware.

#### Scenario: Request with valid tenant ID
- **GIVEN** an HTTP request with header `X-Tenant-Id: tenant-a`
- **WHEN** the request passes through TenantWorkspaceMiddleware
- **THEN** the middleware SHALL ensure tenant-a's provider configuration exists
- **AND** the middleware SHALL bind the tenant-specific ProviderManager to the request context

#### Scenario: Request without tenant ID in exempt route
- **GIVEN** a request to an exempt route (e.g., `/health`)
- **AND** the request has no `X-Tenant-Id` header
- **WHEN** the request is processed
- **THEN** the system SHALL NOT require tenant provider configuration
- **AND** the request SHALL proceed normally

### Requirement: Migration from global to tenant-isolated storage
The system SHALL provide a migration mechanism to move existing global provider configuration to tenant-isolated storage.

#### Scenario: Migrate existing global configuration
- **GIVEN** existing global provider configuration at `~/.copaw.secret/providers/`
- **WHEN** the migration script runs
- **THEN** the system SHALL copy all configuration to `~/.copaw.secret/default/providers/`
- **AND** the system SHALL create a backup at `~/.copaw.secret/providers.backup.{timestamp}/`
- **AND** the system SHALL remove the old global directory after successful migration

#### Scenario: Idempotent migration
- **GIVEN** the migration has already been run
- **WHEN** the migration script runs again
- **THEN** the system SHALL detect the existing tenant-isolated configuration
- **AND** the system SHALL skip migration without error

