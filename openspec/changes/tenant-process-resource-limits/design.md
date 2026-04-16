## Context

SWE already carries tenant identity and workspace context through HTTP requests, cron jobs, and channel callbacks. Builtin shell execution uses that tenant context at launch time, and tenant-scoped MCP `stdio` clients are created from tenant root config plus request context. That means the architecture already has authoritative launch points for user-driven subprocesses, but those launch points currently enforce only path and timeout constraints, not resource ceilings.

The requested scope is intentionally narrow:
- limits are per launched process, not shared across all processes owned by a tenant
- the first implementation should use CPU time, not CPU quota or cpu-share throttling
- shell and MCP `stdio` are in scope because they are the main tenant-driven subprocess entry points
- platform-managed subprocesses such as local model servers, tunnel helpers, desktop bootstrapping, and update workers remain out of scope

Two codebase constraints shape the design:
- builtin shell execution on Unix already uses `asyncio.create_subprocess_shell(...)`, which can accept subprocess keyword arguments such as `preexec_fn`
- `agentscope.mcp.StdIOStatefulClient` only accepts `command`, `args`, `env`, and `cwd`, so MCP `stdio` launch cannot directly inject `preexec_fn` or other subprocess kwargs

## Goals / Non-Goals

**Goals:**
- Add a tenant-scoped process limit policy to tenant root config rather than per-agent config.
- Enforce per-process CPU time and memory ceilings for tenant-scoped shell subprocesses on supported Unix platforms.
- Enforce the same ceilings for tenant-scoped MCP `stdio` subprocesses, including reconnect and rebuild flows.
- Keep process-limit logic centralized so shell and MCP `stdio` use one policy model and one enforcement contract.
- Preserve existing shell timeout, path-boundary, and approval behavior.

**Non-Goals:**
- Implementing tenant-wide shared CPU or memory quotas across multiple concurrent processes.
- Implementing CPU throttling by percent, cores, cgroup quotas, or scheduler shares.
- Enforcing process ceilings for platform-managed subprocesses such as local model runtimes, tunnel helpers, or CLI maintenance commands.
- Requiring Windows parity in the first iteration.
- Replacing existing wall-clock timeout semantics with CPU time limits.

## Decisions

### Decision 1: Store process limits under tenant root `security` config

**Choice:** Add a new `security.process_limits` section to the tenant root `config.json`.

**Rationale:**
- The limit is tenant-scoped infrastructure policy, not agent personality or workspace behavior.
- Tenant root config already owns adjacent cross-cutting settings such as `mcp`, `tools`, and `security`.
- Cron, channel, and request paths can all resolve the same tenant policy without depending on a specific agent profile file.

**Alternatives considered:**
- Agent-level config: rejected because it would let one tenant bypass policy by using a different agent profile.
- Environment-only config: rejected because the user wants per-tenant control instead of process-global defaults.

### Decision 2: Model the first release as per-process CPU time and memory ceilings

**Choice:** Support `cpu_time_limit_seconds` and `memory_max_mb`, plus booleans for whether the policy applies to shell and MCP `stdio`.

**Rationale:**
- The user explicitly chose CPU time rather than CPU throttling.
- CPU time and memory ceilings map directly to Unix `resource.setrlimit(...)`.
- This keeps the first release aligned with existing subprocess launch points without introducing cgroup coordination or shared accounting.

**Alternatives considered:**
- CPU quota percent / cores: rejected for the first release because it needs cgroup-style throttling instead of simple launch-time limits.
- Shared tenant quotas: rejected because the user explicitly chose per-process ceilings first.

### Decision 3: Shell launches use a shared Unix `preexec_fn` limit applicator

**Choice:** Add a shared process-limit helper that converts tenant policy into subprocess launch behavior for Unix shell execution by applying `RLIMIT_CPU` and `RLIMIT_AS` in `preexec_fn`.

**Rationale:**
- Shell already has the direct launch control needed to set rlimits before `exec`.
- A shared helper keeps the policy-to-launch translation out of `shell.py`.
- Existing timeout and process-group cleanup logic can remain unchanged.

**Alternatives considered:**
- In-line `setrlimit` logic in `shell.py`: rejected because the same policy needs to be reused elsewhere.
- A wrapper process for shell as well: rejected because shell already has a simpler direct hook on Unix.

### Decision 4: MCP `stdio` launches use a tenant-aware launcher wrapper

**Choice:** Start tenant-scoped MCP `stdio` servers through a small SWE-owned launcher entry point that applies rlimits and then `exec`s the configured command.

**Rationale:**
- `StdIOStatefulClient` does not expose subprocess kwargs such as `preexec_fn`.
- A launcher wrapper gives SWE full control over resource application without modifying third-party code.
- The same wrapper can be reused for both initial MCP client creation and rebuild paths from stored `_swe_rebuild_info`.

**Alternatives considered:**
- Patching or subclassing `StdIOStatefulClient`: rejected for the first release because it couples SWE to third-party internals.
- Leaving MCP `stdio` out of scope: rejected because it would leave a tenant-controlled subprocess bypass next to shell enforcement.

### Decision 5: Unsupported platforms fail open with explicit diagnostics, not silent enforcement claims

**Choice:** When process limits are enabled on unsupported platforms, SWE should not pretend enforcement succeeded; it should leave launch behavior unchanged and emit clear logs or user-visible error context where appropriate.

**Rationale:**
- Silent no-op behavior would make operators believe tenants are protected when they are not.
- The deployed environment is Linux, so first-release value is preserved even if local development platforms differ.
- This is safer than partially emulating Windows process limits with unrelated APIs.

**Alternatives considered:**
- Best-effort Windows implementation in the same change: rejected to keep the security contract precise.
- Hard failure on every unsupported platform launch: rejected because it would unnecessarily block development workflows outside the target deployment environment.

## Risks / Trade-offs

- [CPU time is not wall-clock time] -> Keep existing `timeout` behavior unchanged and document that `sleep`-heavy commands are still governed by wall-clock timeout rather than `RLIMIT_CPU`.
- [Address-space limits can be stricter than expected for Python or Node runtimes] -> Start with configurable tenant values, default conservatively, and keep the policy optional per tenant.
- [MCP wrapper changes the exact command chain seen by operators] -> Preserve the original command in rebuild metadata and logs so troubleshooting still points at the tenant-configured MCP server.
- [Shell and MCP may surface different termination messages from the OS] -> Normalize common limit-exceeded outcomes into consistent SWE error text while keeping stderr detail when available.
- [Unsupported platforms may drift from production behavior] -> Log explicit “limits not enforced on this platform” diagnostics and keep the first-release contract Linux/Unix-focused.

## Migration Plan

1. Add the new `security.process_limits` schema with defaults disabled so existing tenants keep current behavior.
2. Implement the shared policy helper and shell launch integration on Unix.
3. Add the tenant-aware MCP `stdio` launcher and route both initial and rebuilt stdio clients through it.
4. Add focused tests for config validation, shell enforcement, MCP stdio enforcement, and unsupported-platform behavior.
5. Roll out by enabling the policy per tenant with conservative values; rollback is immediate by disabling `security.process_limits.enabled`.

## Open Questions

- Should SWE expose `security.process_limits` through an admin API in the same change, or is tenant root config support sufficient for the first release?
- Should limit-exceeded events produce dedicated structured audit records beyond normal logs?
- Do we want the MCP launcher to propagate tenant identity explicitly in argv, environment, or both for debugging purposes?
