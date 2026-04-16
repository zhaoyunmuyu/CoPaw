## ADDED Requirements

### Requirement: Tenant root config SHALL define process launch policy for in-scope subprocesses
The system SHALL resolve per-process launch limits from the current tenant's root `config.json` under `security.process_limits` and SHALL apply that policy only to in-scope tenant-scoped subprocess launch paths.

#### Scenario: Tenant-scoped request uses tenant root process-limit policy
- **GIVEN** tenant `tenant-a` has `security.process_limits.enabled=true`
- **AND** tenant `tenant-a` config enables shell enforcement with `cpu_time_limit_seconds` and `memory_max_mb`
- **WHEN** a tenant-scoped shell or MCP `stdio` launch occurs for `tenant-a`
- **THEN** the system SHALL resolve process-limit settings from `tenant-a`'s root config
- **AND** the system SHALL NOT read process-limit settings from another tenant's config

#### Scenario: Disabled process-limit policy preserves current launch behavior
- **WHEN** a tenant-scoped shell or MCP `stdio` launch occurs and `security.process_limits.enabled=false`
- **THEN** the system SHALL launch the subprocess without applying process ceilings
- **AND** the subprocess SHALL remain subject to existing validation and timeout behavior

### Requirement: Shell subprocesses SHALL honor configured per-process ceilings
The system SHALL apply configured per-process CPU time and memory ceilings to tenant-scoped builtin shell subprocess launches on supported Unix platforms.

#### Scenario: Shell launch applies configured CPU time and memory ceilings
- **GIVEN** tenant process limits are enabled for shell launches
- **WHEN** the system starts a tenant-scoped builtin shell command on a supported Unix platform
- **THEN** the child process SHALL start with the configured CPU time ceiling
- **AND** the child process SHALL start with the configured memory ceiling

#### Scenario: Shell subprocess exceeding CPU time ceiling is terminated
- **GIVEN** tenant process limits are enabled for shell launches with a low CPU time ceiling
- **WHEN** a tenant-scoped builtin shell command consumes more CPU time than the configured limit
- **THEN** the operating system SHALL terminate the subprocess
- **AND** the builtin shell tool SHALL return a failure result indicating the command exceeded process limits

#### Scenario: Shell subprocess exceeding memory ceiling is terminated
- **GIVEN** tenant process limits are enabled for shell launches with a low memory ceiling
- **WHEN** a tenant-scoped builtin shell command exceeds the configured memory ceiling
- **THEN** the operating system SHALL terminate or fail the subprocess
- **AND** the builtin shell tool SHALL return a failure result indicating the command exceeded process limits

### Requirement: MCP `stdio` subprocesses SHALL honor the same configured ceilings
The system SHALL apply the same tenant-scoped per-process CPU time and memory ceilings to tenant-scoped MCP `stdio` server subprocess launches, including rebuild paths that reconnect a stdio client from stored metadata.

#### Scenario: Initial MCP `stdio` launch uses tenant process limits
- **GIVEN** tenant process limits are enabled for MCP `stdio` launches
- **WHEN** the system creates a tenant-scoped MCP `stdio` client from tenant config
- **THEN** the launched MCP server subprocess SHALL inherit the configured CPU time ceiling
- **AND** the launched MCP server subprocess SHALL inherit the configured memory ceiling

#### Scenario: Rebuilt MCP `stdio` launch preserves tenant process limits
- **GIVEN** a tenant-scoped MCP `stdio` client stores rebuild metadata
- **AND** tenant process limits are enabled for MCP `stdio` launches
- **WHEN** the system rebuilds that MCP client from stored metadata
- **THEN** the rebuilt MCP server subprocess SHALL launch with the same tenant-scoped process-limit policy

### Requirement: Process-limit enforcement SHALL preserve current scope boundaries
The system SHALL apply tenant process limits only to tenant-scoped builtin shell launches and tenant-scoped MCP `stdio` launches in this capability.

#### Scenario: Out-of-scope platform-managed subprocess is not covered by tenant process-limit policy
- **WHEN** the system starts an out-of-scope platform-managed subprocess such as a local model runtime, tunnel helper, or CLI maintenance worker
- **THEN** this capability SHALL NOT require tenant process limits to be applied to that subprocess

#### Scenario: Existing shell wall-clock timeout behavior remains in effect
- **WHEN** a tenant-scoped builtin shell command runs with process limits enabled
- **THEN** the system SHALL continue enforcing the existing wall-clock timeout behavior independently from CPU time limits

### Requirement: Unsupported platforms SHALL not silently claim enforcement
The system SHALL avoid silently claiming process-limit enforcement on unsupported platforms.

#### Scenario: Unsupported platform leaves launch behavior unchanged with diagnostics
- **GIVEN** tenant process limits are enabled
- **WHEN** an in-scope subprocess launch occurs on a platform where this capability does not enforce process limits
- **THEN** the system SHALL leave subprocess launch behavior unchanged
- **AND** the system SHALL emit diagnostics indicating that process limits were not enforced on that platform
