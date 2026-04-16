## Why

SWE now enforces tenant path boundaries for builtin local tools, but tenant-scoped shell commands and stdio MCP servers can still start child processes without CPU or memory ceilings. In a multi-tenant deployment, one runaway script or MCP server can consume disproportionate host resources and degrade other tenants.

## What Changes

- Add a tenant-scoped process limit policy under the tenant root `config.json` to control per-process CPU time and memory ceilings for tenant-launched subprocesses.
- Apply the policy to builtin `execute_shell_command` launches without changing existing path-boundary or wall-clock timeout behavior.
- Apply the same policy to tenant-scoped MCP `stdio` server launches, including MCP client rebuild paths that reconnect servers from stored metadata.
- Introduce clear failure and logging behavior for invalid limit configuration, unsupported platforms, and resource-limit termination outcomes.
- Keep the scope limited to per-process ceilings for tenant-launched shell and MCP `stdio` subprocesses; do not introduce shared tenant quotas or change platform-managed subprocesses such as local model runtimes, Cloudflare tunnel helpers, or CLI maintenance processes.

## Capabilities

### New Capabilities
- `tenant-process-resource-limits`: Enforce tenant-scoped per-process CPU time and memory ceilings for builtin shell execution and MCP `stdio` subprocess launches.

### Modified Capabilities
- None.

## Impact

- Affected backend config and security plumbing:
  `src/swe/config/config.py`,
  `src/swe/config/context.py`,
  `src/swe/app/tenant_context.py`
- Affected subprocess launch paths:
  `src/swe/agents/tools/shell.py`,
  `src/swe/app/runner/runner.py`,
  `src/swe/agents/react_agent.py`
- Likely adds a shared process-limit helper and a tenant-aware stdio launcher module for MCP subprocesses
- Requires unit/integration coverage for tenant-scoped config resolution, shell enforcement, MCP stdio enforcement, and unsupported-platform behavior
