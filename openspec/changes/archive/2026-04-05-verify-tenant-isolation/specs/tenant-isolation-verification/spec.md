## ADDED Requirements

### Requirement: Context-scoped user isolation
The system SHALL maintain separate request contexts for each concurrent tenant such that `get_request_user_id()` returns the correct user ID for the current request scope.

#### Scenario: Concurrent requests from different tenants
- **WHEN** two requests from user "alice" and user "bob" are processed concurrently
- **THEN** each request sees only its own user ID via `get_request_user_id()`

#### Scenario: Nested async operations maintain isolation
- **WHEN** a request handler calls multiple async functions
- **THEN** the user context remains consistent throughout the call chain

### Requirement: Directory isolation per tenant
The system SHALL ensure that `get_request_working_dir()`, `get_request_secret_dir()`, `get_active_skills_dir()`, `get_memory_dir()`, and `get_models_dir()` return paths specific to the current request's user ID.

#### Scenario: Directory paths contain user ID
- **WHEN** user "alice" calls `get_request_working_dir()`
- **THEN** the returned path ends with `.swe/alice/`

#### Scenario: Different users get different directories
- **WHEN** user "alice" and user "bob" both call `get_request_working_dir()`
- **THEN** the returned paths are different and user-specific

### Requirement: Data leakage prevention between tenants
The system SHALL prevent any tenant from accessing another tenant's data through the directory getters or file operations.

#### Scenario: Tenant cannot access other's config
- **WHEN** user "alice" attempts to read user "bob"'s config.json
- **THEN** the operation fails or returns unauthorized

#### Scenario: Tenant cannot access other's memory
- **WHEN** user "alice" attempts to read user "bob"'s memory files
- **THEN** the operation fails or returns unauthorized

#### Scenario: Tenant cannot access other's sessions
- **WHEN** user "alice" attempts to read user "bob"'s session files
- **THEN** the operation fails or returns unauthorized

### Requirement: AgentRunner sets context correctly
The system SHALL ensure that `AgentRunner.query_handler()` correctly sets up the request context with the proper user ID before processing queries.

#### Scenario: Query handler sets user context
- **WHEN** a message from user "alice" is processed by `query_handler()`
- **THEN** `get_request_user_id()` returns "alice" during query processing

#### Scenario: Query handler clears context after completion
- **WHEN** a query completes processing
- **THEN** the request context is properly cleaned up
