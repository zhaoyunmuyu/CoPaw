## 1. Config And Shared Policy

- [x] 1.1 Add `security.process_limits` schema and validation to tenant root config models with fields for enablement, shell/MCP scope, CPU time, and memory ceilings.
- [x] 1.2 Implement a shared tenant process-limit helper that resolves the current tenant policy and constructs Unix enforcement behavior plus unsupported-platform diagnostics.

## 2. Shell Enforcement

- [x] 2.1 Apply the shared process-limit helper to tenant-scoped builtin shell launches without changing existing path-boundary or wall-clock timeout behavior.
- [x] 2.2 Add shell-focused tests covering disabled policy, tenant-scoped config lookup, CPU time enforcement, memory enforcement, and unsupported-platform behavior.

## 3. MCP StdIO Enforcement

- [x] 3.1 Add a SWE-owned tenant-aware stdio launcher that applies configured process limits and then `exec`s the configured MCP server command.
- [x] 3.2 Route tenant-scoped MCP `stdio` client creation and rebuild paths through the launcher while preserving rebuild metadata and original command intent.
- [x] 3.3 Add MCP `stdio` tests covering launcher wiring, tenant policy propagation, and rebuild-path enforcement.

## 4. Verification And Operational Notes

- [x] 4.1 Add focused verification for cron-initiated tenant-scoped launches to confirm they inherit the same process-limit policy through tenant context.
- [x] 4.2 Update relevant analysis or operator-facing documentation to explain scope, Linux/Unix-first support, and the difference between CPU time limits and existing wall-clock timeouts.
