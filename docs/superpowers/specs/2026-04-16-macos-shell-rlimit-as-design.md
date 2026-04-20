# macOS Shell `RLIMIT_AS` Compatibility Fix

## Context

`execute_shell_command` currently resolves tenant-scoped process limits and passes a Unix `preexec_fn` into `asyncio.create_subprocess_shell(...)`.

On macOS, shell process limits can be enabled with both CPU and memory settings. The current implementation treats any non-Windows Unix-like platform as supporting both `RLIMIT_CPU` and `RLIMIT_AS`. In practice, setting `RLIMIT_AS` in the shell `preexec_fn` on the current macOS environment raises inside the child process before `exec`, which surfaces to callers as:

`Exception occurred in preexec_fn.`

This breaks otherwise valid shell commands whenever shell process limits are enabled with `memory_max_mb`.

## Goal

Prevent `execute_shell_command` from forcing shell `RLIMIT_AS` on macOS, while preserving existing shell CPU-limit behavior and leaving `mcp_stdio` unchanged.

## Non-Goals

- Do not change `mcp_stdio` launch behavior.
- Do not redesign the overall process-limit config model.
- Do not introduce a new platform-specific memory limit mechanism for macOS.

## Options Considered

### Option 1: Skip shell `RLIMIT_AS` on macOS, keep shell `RLIMIT_CPU`

Recommended.

This keeps the current shell protection model as intact as possible on macOS while removing the proven failure path. CPU time limits continue to work, and only the unsupported memory-limit enforcement path is skipped.

### Option 2: Disable all shell process limits on macOS

This is safer in the narrow sense but throws away working CPU-limit enforcement. The rollback is broader than necessary.

### Option 3: Continue attempting `RLIMIT_AS` and swallow failures

This hides a platform mismatch and leaves enforcement status ambiguous. It would also keep the error-prone logic inside `preexec_fn`, where diagnostics are weak.

## Design

### Policy Resolution

Refine shell process-limit capability checks so they are not derived from a single coarse “Unix supports both” predicate.

For shell scope:

- `RLIMIT_CPU` remains enforceable on Unix platforms where `resource.setrlimit` and `resource.RLIMIT_CPU` are available.
- `RLIMIT_AS` is not enforceable on macOS (`sys.platform == "darwin"`).

This means a shell policy on macOS may still be enforceable even when `memory_max_mb` is configured, but only for CPU limits.

### `preexec_fn` Construction

The generated shell `preexec_fn` should only call `setrlimit` for limits that are actually enforceable on the current platform.

On macOS:

- If `cpu_time_limit_seconds` is configured, apply `RLIMIT_CPU`.
- If `memory_max_mb` is configured, do not apply `RLIMIT_AS`.

### Diagnostics

When shell memory limits are configured but skipped on macOS, the resolved policy should carry an explicit diagnostic stating that shell memory enforcement is not applied on this platform. The shell tool already appends policy diagnostics to tool output, so callers get a concrete explanation rather than a generic subprocess failure.

### Scope Boundary

This compatibility adjustment is limited to the shell builtin tool path:

- `src/swe/agents/tools/shell.py`
- `src/swe/security/process_limits.py`

`src/swe/app/mcp/stdio_launcher.py` remains unchanged in this fix.

## Testing Strategy

Add regression coverage for shell process-limit resolution/building:

1. macOS shell policy with both CPU and memory configured should build a `preexec_fn` that applies CPU only.
2. Existing non-macOS behavior should continue to apply both CPU and memory limits when supported.
3. Shell integration tests should continue to confirm that enabled shell process limits still inject a `preexec_fn`.

## Risks

- macOS shell commands lose memory-limit enforcement. This is intentional because the current behavior is broken and prevents command execution entirely.
- Diagnostics may appear in successful command output when memory enforcement is skipped. This is acceptable because the user-visible behavior should be explicit.

## Success Criteria

- On macOS, `execute_shell_command` no longer fails with `Exception occurred in preexec_fn.` solely because shell `memory_max_mb` is configured.
- Shell CPU limit behavior remains available.
- Existing Linux/Unix shell limit behavior outside macOS does not regress.
