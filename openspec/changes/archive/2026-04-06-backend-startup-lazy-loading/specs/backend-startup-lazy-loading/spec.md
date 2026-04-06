## ADDED Requirements

### Requirement: Minimal application startup
The backend SHALL complete application startup after assembling routes, middleware, app state, lightweight manager containers, and ensuring default agent declaration. Startup MUST NOT eagerly initialize agent runtimes, telemetry, legacy migrations, QA agent setup, provider managers, local model managers, or default-agent prewarm.

#### Scenario: Service becomes ready without runtime prewarm
- **WHEN** the FastAPI lifespan startup completes
- **THEN** the service is ready to accept HTTP requests
- **THEN** no agent runtime has been started
- **THEN** telemetry and legacy migration flows have not been executed
- **THEN** provider and local model managers have not been instantiated eagerly

### Requirement: Tenant request performs only minimal bootstrap
The system SHALL limit first tenant access to minimal bootstrap work needed for tenant isolation, including directory skeleton creation, default agent declaration, provider config directory existence, and context binding. Tenant access MUST NOT start a workspace runtime, initialize skills, create QA agents, or start local models.

#### Scenario: First tenant request avoids runtime startup
- **WHEN** a request for a tenant without prior bootstrap arrives
- **THEN** the system creates or verifies the tenant directory skeleton
- **THEN** the system ensures the tenant default agent declaration exists
- **THEN** the system ensures tenant provider configuration directories exist
- **THEN** the system binds tenant workspace and model context for the request
- **THEN** the system does not start any agent runtime or initialize skill pools

### Requirement: Agent runtime starts only on tenant+agent demand
The system SHALL lazily start an agent runtime only when a request explicitly needs a specific `(tenant_id, agent_id)` runtime through `MultiAgentManager.get_agent()`. Runtime caching MUST be isolated by tenant and agent.

#### Scenario: First tenant+agent access starts one runtime
- **WHEN** the first request for `(tenant_id=A, agent_id=default)` reaches the runtime manager
- **THEN** the manager creates the workspace runtime for that tenant and agent
- **THEN** the manager starts that runtime exactly once for concurrent first access
- **THEN** subsequent requests for the same tenant and agent reuse the cached runtime

#### Scenario: Different tenants stay isolated
- **WHEN** tenant A starts agent `default` and tenant B has not accessed any agent
- **THEN** tenant B has no runtime started as a side effect
- **THEN** a later request for tenant B starts its own isolated runtime instance

### Requirement: Feature subsystems initialize on first feature use
The system SHALL initialize the skill pool, provider manager, local model manager, and QA agent only from explicit feature entrypoints or maintenance flows. These subsystems MUST NOT be initialized from app startup, tenant bootstrap, or generic workspace startup.

#### Scenario: Skills initialize from skills entrypoint
- **WHEN** a request first reaches a skills API or skill resolution path that requires the skill pool
- **THEN** the system initializes the skill pool on demand
- **THEN** app startup and tenant bootstrap remain free of skill initialization side effects

#### Scenario: Provider manager initializes from provider usage
- **WHEN** a request first reaches provider APIs or model factory logic that needs provider access for a tenant
- **THEN** the system initializes that tenant’s provider manager on demand
- **THEN** startup and tenant bootstrap do not instantiate the provider manager eagerly

#### Scenario: Local model manager initializes from local model usage
- **WHEN** a request first uses a local model management API or local-model-backed provider
- **THEN** the system initializes the local model manager on demand
- **THEN** startup does not resume or start local models eagerly

#### Scenario: QA agent initializes from explicit QA access
- **WHEN** a request explicitly targets the QA agent or an admin maintenance flow requests QA setup
- **THEN** the system creates or ensures the QA agent at that time
- **THEN** startup and tenant bootstrap do not create the QA agent implicitly

### Requirement: Workspace startup is limited to agent-local dependencies
`Workspace.start()` SHALL load agent configuration and start only the minimal runtime services directly required by that agent. It MUST NOT initialize tenant-wide or platform-wide resources such as skill pools or legacy skill migrations.

#### Scenario: Workspace startup avoids skill pool initialization
- **WHEN** a workspace runtime is started for an agent
- **THEN** the workspace loads the agent configuration and starts agent-local services
- **THEN** the workspace does not initialize the skill pool or run legacy skill migration as part of startup
