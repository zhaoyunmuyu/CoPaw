# CoPaw Multi-Tenant Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement strict tenant isolation so every stateful request, background task, cron execution, memory operation, file write, and config lookup is bound to a tenant workspace and never falls back to global business storage.

**Architecture:** Introduce tenant identity and workspace binding as the top-level runtime boundary. HTTP and non-HTTP entrypoints resolve a tenant first, then bind execution to a tenant-scoped workspace directory; existing lower layers continue to rely primarily on `workspace_dir`, with tenant awareness added only where global state or config lookups currently break isolation.

**Tech Stack:** FastAPI, contextvars, existing Workspace/ServiceManager runtime, Pydantic config models, APScheduler cron runtime, ReMeLight memory manager, pytest

---

## File Structure / Responsibility Map

### New files
- `src/copaw/app/workspace/tenant_pool.py`
  - Tenant workspace registry/cache
  - Lazy creation, per-tenant locking, stop-all lifecycle
- `src/copaw/app/tenant_context.py`
  - Shared helpers/context manager for binding tenant/workspace context in HTTP, cron, and channel callbacks
- `src/copaw/app/middleware/tenant_identity.py`
  - Parse and validate `X-Tenant-Id` / `X-User-Id`
- `src/copaw/app/middleware/tenant_workspace.py`
  - Resolve `request.state.workspace` from tenant pool and bind workspace context
- `tests/unit/app/test_tenant_context.py`
  - Contextvar and context binding tests
- `tests/unit/app/test_tenant_pool.py`
  - Tenant workspace pool behavior tests
- `tests/unit/app/test_tenant_middleware.py`
  - HTTP middleware behavior tests

### Existing files to modify
- `src/copaw/config/context.py`
  - Add `current_tenant_id`, `current_user_id`, strict helpers
- `src/copaw/app/_app.py`
  - Register tenant middleware and initialize `TenantWorkspacePool`
- `src/copaw/app/agent_context.py`
  - Change resolution order to tenant-first, tenant-local agent lookup
- `src/copaw/app/routers/agent_scoped.py`
  - Reconcile agent-scoped routing with tenant-scoped routing
- `src/copaw/app/workspace/workspace.py`
  - Allow tenant-scoped config/runtime initialization, remove global assumptions, add `tenant_id` property
- `src/copaw/config/utils.py`
  - Add tenant path helpers; eliminate global business-path defaults; add `get_tenant_env()` helper
- `src/copaw/config/config.py`
  - Support tenant-scoped config/agent config resolution where needed
- `src/copaw/app/routers/console.py`
  - Bind chat/upload/push APIs to current tenant workspace only
- `src/copaw/app/console_push_store.py`
  - Remove global recent-message semantics; tenant+session-scoped store
- `src/copaw/app/routers/settings.py`
  - Persist settings to tenant config path
- `src/copaw/app/routers/envs.py`
  - Split system env management from tenant secret/config management
- `src/copaw/app/routers/agents.py`
  - Make agents tenant-local and active-agent selection tenant-local
- `src/copaw/app/routers/workspace.py`
  - Restrict download/upload/stats to current tenant workspace
- `src/copaw/app/crons/manager.py`
  - Tenant-local cron manager lifecycle and context restore
- `src/copaw/app/crons/executor.py`
  - Execute jobs inside tenant/workspace context
- `src/copaw/app/crons/models.py`
  - Add tenant metadata to persisted job specs
- `src/copaw/app/crons/repo/json_repo.py`
  - Verify tenant workspace-local jobs path behavior
- `src/copaw/app/crons/heartbeat.py`
  - Tenant-scoped heartbeat paths, runtime lookup, and context binding
- `src/copaw/app/crons/api.py`
  - Inject tenant_id from request context into created/updated jobs
- `src/copaw/agents/memory/reme_light_memory_manager.py`
  - Ensure tenant-scoped config lookups and context restoration assumptions hold
- `src/copaw/agents/memory/agent_md_manager.py`
  - Verify tenant workspace-local memory directory behavior
- `src/copaw/app/channels/base.py`
  - Add tenant context binding in `_consume_one_request()`
- `src/copaw/envs/store.py`
  - Restrict startup env loading to system-level bootstrap vars only
- `src/copaw/providers/provider_manager.py`
  - Separate global provider definitions from tenant-scoped credentials
- `src/copaw/app/auth.py`
  - Evaluate and document global vs tenant-scoped auth strategy
- `src/copaw/agents/skills_manager.py`
  - Replace direct `os.environ` writes with tenant-scoped env store
- `src/copaw/app/runner/runner.py`
  - Load `.env` from tenant workspace, not global `./`
- `src/copaw/constant.py`
  - Restrict module-level `.env` loading to system bootstrap vars
- `src/copaw/cli/cron_cmd.py`
  - Add `--tenant-id` parameter and `X-Tenant-Id` header support

### Existing tests to update or extend
- `tests/unit/routers/test_settings.py`
- New router tests under `tests/unit/routers/` for console, envs, workspace, agents
- New cron tests under `tests/unit/app/crons/`
- Workspace/runtime tests under `tests/unit/app/` or `tests/unit/workspace/`
- `tests/unit/app/channels/test_channel_tenant_binding.py`
- `tests/unit/app/test_tenant_secrets_isolation.py`
- `tests/unit/app/crons/test_cron_creation_tenant.py`

---

## Phase breakdown

1. Tenant runtime foundation
2. Tenant-scoped routing and console isolation
3. Tenant-scoped config, agents, workspace APIs, and secrets
4. Tenant-scoped cron/background execution
5. Channel layer tenant binding and full secrets isolation
6. Cron creation path hardening and MultiAgentManager deprecation
7. Memory/config dependency hardening, audit, and regression verification

---

### Task 1: Add tenant context primitives

**Files:**
- Create: `src/copaw/app/tenant_context.py`
- Modify: `src/copaw/config/context.py`
- Test: `tests/unit/app/test_tenant_context.py`

- [ ] Define `current_tenant_id` and `current_user_id` in `src/copaw/config/context.py` alongside `current_workspace_dir`.
- [ ] Add strict getter/setter helpers for tenant/workspace context, including a helper that raises when tenant-scoped workspace context is missing.
- [ ] Add a reusable tenant/workspace binding helper or context manager in `src/copaw/app/tenant_context.py` for non-HTTP code paths.
- [ ] Write unit tests covering set/get/reset behavior for tenant, user, and workspace contextvars.
- [ ] Write unit tests verifying the strict helper raises instead of falling back to global state.
- [ ] Run only the new tenant context tests.
- [ ] Commit foundation-only context changes.

### Task 2: Introduce TenantWorkspacePool

**Files:**
- Create: `src/copaw/app/workspace/tenant_pool.py`
- Modify: `src/copaw/app/workspace/workspace.py`
- Test: `tests/unit/app/test_tenant_pool.py`

- [ ] Implement a tenant workspace registry with `get_or_create`, `get`, `remove`, `mark_access`, and `stop_all`.
- [ ] Make workspace creation concurrency-safe per tenant so duplicate concurrent requests cannot create multiple tenant runtimes.
- [ ] Ensure failed initialization does not leave a cached half-started workspace.
- [ ] Decide and document the tenant workspace directory layout under `WORKING_DIR/<tenant_id>/...` in code-level helpers, not ad hoc router logic.
- [ ] Update workspace initialization assumptions so core services can be instantiated from a tenant workspace root instead of a global/agent-global root.
- [ ] Write unit tests for lazy creation, cache hits, concurrent creation safety, and stop-all cleanup.
- [ ] Run only the tenant pool tests.
- [ ] Commit the pool introduction before wiring it into HTTP.

### Task 3: Replace app-global runtime binding with tenant-aware app initialization

**Files:**
- Modify: `src/copaw/app/_app.py`
- Modify: `src/copaw/app/agent_context.py`
- Modify: `src/copaw/app/routers/agent_scoped.py`
- Test: `tests/unit/app/test_tenant_middleware.py`

- [ ] Initialize `app.state.tenant_workspace_pool` during FastAPI lifespan startup.
- [ ] Stop all tenant workspaces during shutdown.
- [ ] Rework the current app-global agent resolution flow so tenant is resolved before agent.
- [ ] Preserve any truly global services only where the spec allows shared state.
- [ ] Review `AgentContextMiddleware` and agent-scoped routes to ensure they no longer imply a cross-tenant global agent namespace.
- [ ] Add focused tests for tenant-first resolution order and app startup/shutdown lifecycle interactions.
- [ ] Run the app-level middleware/lifecycle tests.
- [ ] Commit app initialization refactor.

### Task 4: Add tenant identity middleware

**Files:**
- Create: `src/copaw/app/middleware/tenant_identity.py`
- Modify: `src/copaw/app/_app.py`
- Test: `tests/unit/app/test_tenant_middleware.py`

- [ ] Implement middleware that reads `X-Tenant-Id` and `X-User-Id` from stateful requests.
- [ ] Enforce strong validation and reject missing/invalid tenant IDs with 4xx responses.
- [ ] Decide which routes are explicitly exempt because they are truly stateless or system-level, and encode that exclusion list in one place.
- [ ] Bind tenant/user contextvars during the request and reset them on exit.
- [ ] Add HTTP tests for valid tenant, missing tenant, invalid tenant, and exempt endpoints.
- [ ] Run only middleware tests.
- [ ] Commit tenant identity middleware.

### Task 5: Add tenant workspace middleware

**Files:**
- Create: `src/copaw/app/middleware/tenant_workspace.py`
- Modify: `src/copaw/app/_app.py`
- Test: `tests/unit/app/test_tenant_middleware.py`

- [ ] Implement middleware that loads the tenant workspace from `TenantWorkspacePool`.
- [ ] Store the tenant workspace in `request.state.workspace`.
- [ ] Bind `current_workspace_dir` from the tenant workspace for the duration of the request.
- [ ] Ensure middleware ordering is correct: auth/tenant identity/tenant workspace/agent-local routing.
- [ ] Add tests proving stateful handlers receive the tenant workspace and that context is reset after the response.
- [ ] Run the middleware tests again.
- [ ] Commit tenant workspace middleware.

### Task 6: Add tenant path helpers and remove global business-path defaults

**Files:**
- Modify: `src/copaw/config/utils.py`
- Modify: `src/copaw/config/config.py`
- Test: `tests/unit/config/test_tenant_paths.py`

- [ ] Add tenant-aware helpers for working dir, config path, jobs path, memory dir, media dir, secrets dir, and heartbeat path.
- [ ] Change config utility functions so tenant-scoped business data no longer defaults to global `WORKING_DIR` paths.
- [ ] Keep only explicitly system-level config helpers global.
- [ ] Audit all current helper functions that still read/write global `config.json`, `HEARTBEAT.md`, `jobs.json`, or related files.
- [ ] Add tests covering tenant path computation and strict failure when tenant/workspace context is absent.
- [ ] Run the tenant path tests.
- [ ] Commit config helper changes.

### Task 7: Make settings tenant-scoped

**Files:**
- Modify: `src/copaw/app/routers/settings.py`
- Test: `tests/unit/routers/test_settings.py`

- [ ] Replace the hard-coded global settings file path with tenant-scoped settings/config storage.
- [ ] Update the router to resolve the current tenant workspace instead of using a module-level `WORKING_DIR/settings.json` file.
- [ ] Preserve existing language validation behavior.
- [ ] Update existing tests to patch the tenant-scoped settings path instead of the global module constant.
- [ ] Add a test proving two different tenants see different settings values.
- [ ] Run the settings tests.
- [ ] Commit tenant-scoped settings.

### Task 8: Make console chat and upload tenant-scoped

**Files:**
- Modify: `src/copaw/app/routers/console.py`
- Modify: `src/copaw/app/agent_context.py`
- Possibly modify: `src/copaw/app/channels/console/channel.py`
- Test: `tests/unit/routers/test_console_tenant_isolation.py`

- [ ] Make console APIs use `request.state.workspace` as the primary source of runtime state.
- [ ] Ensure any remaining agent resolution occurs only inside the current tenant namespace.
- [ ] Update session ID generation so the tenant boundary is encoded in console sessions.
- [ ] Ensure upload writes always target the tenant workspace media directory.
- [ ] Add router tests showing tenant A cannot reconnect to, stop, or upload into tenant B resources.
- [ ] Run the console isolation tests.
- [ ] Commit console tenant isolation.

### Task 9: Replace global console push store semantics

**Files:**
- Modify: `src/copaw/app/console_push_store.py`
- Modify: `src/copaw/app/routers/console.py`
- Test: `tests/unit/app/test_console_push_store.py`
- Test: `tests/unit/routers/test_console_tenant_isolation.py`

- [ ] Redesign the in-memory store keying so messages are isolated by tenant and session.
- [ ] Remove or sharply constrain the current “recent messages across all sessions” behavior.
- [ ] Make the API read path require tenant-scoped access, ideally tenant plus session.
- [ ] Update cron/error-reporting call sites to pass tenant information when appending messages.
- [ ] Add unit tests proving messages do not leak across tenants or across sessions.
- [ ] Run push-store and console isolation tests.
- [ ] Commit push-store hardening.

### Task 10: Make workspace APIs tenant-scoped

**Files:**
- Modify: `src/copaw/app/routers/workspace.py`
- Test: `tests/unit/routers/test_workspace_tenant_scope.py`

- [ ] Replace agent-global workspace download/upload behavior with current-tenant workspace behavior.
- [ ] Ensure filenames, zip roots, merge targets, and stats all derive from the current tenant workspace.
- [ ] Verify no API path still exposes a global filesystem view.
- [ ] Add tests proving tenant A cannot download or overwrite tenant B’s workspace.
- [ ] Run workspace router tests.
- [ ] Commit workspace router isolation.

### Task 11: Make agents tenant-local

**Files:**
- Modify: `src/copaw/app/routers/agents.py`
- Modify: `src/copaw/app/agent_context.py`
- Modify: `src/copaw/config/utils.py`
- Modify: `src/copaw/config/config.py`
- Test: `tests/unit/routers/test_agents_tenant_scope.py`

- [ ] Redefine agent listing, creation, update, and active-agent selection as tenant-local operations.
- [ ] Ensure tenant-local config lookup and persistence paths are used for agent metadata and profiles.
- [ ] Remove assumptions that `config.agents.profiles` is app-global unless the remaining structure is explicitly a tenant-local copy.
- [ ] Ensure `X-Agent-Id` is resolved only inside the current tenant workspace namespace.
- [ ] Add tests for tenant-local list/get/update behavior and active-agent isolation.
- [ ] Run the agent router tests.
- [ ] Commit tenant-local agent behavior.

### Task 12: Split tenant secrets from system envs

**Files:**
- Modify: `src/copaw/app/routers/envs.py`
- Modify: `src/copaw/envs.py` or equivalent env persistence helpers
- Modify: `src/copaw/config/utils.py`
- Test: `tests/unit/routers/test_envs_tenant_scope.py`

- [ ] Identify which existing env endpoints are truly system-level and which keys are tenant business secrets.
- [ ] Add tenant-scoped secret storage under the tenant workspace instead of persisting tenant credentials as process-global env state.
- [ ] Keep system env behavior only for actual service/runtime configuration.
- [ ] Update API behavior so tenant secret reads/writes never mutate global `os.environ` as the source of truth.
- [ ] Add tests proving tenant A and tenant B cannot read or overwrite each other’s secrets.
- [ ] Run env/secret tests.
- [ ] Commit env/secret split.

### Task 13: Make cron persistence tenant-local

**Files:**
- Modify: `src/copaw/app/workspace/workspace.py`
- Modify: `src/copaw/app/crons/repo/json_repo.py`
- Modify: `src/copaw/app/crons/models.py`
- Test: `tests/unit/app/crons/test_tenant_cron_repo.py`

- [ ] Ensure each tenant workspace instantiates its own `CronManager` with a tenant-local `jobs.json` path.
- [ ] Extend cron job metadata to include tenant ID for diagnostics and context restore.
- [ ] Verify serialization/deserialization preserves the new tenant metadata.
- [ ] Add repository/model tests for tenant-local jobs path and metadata round-trip.
- [ ] Run cron repo/model tests.
- [ ] Commit cron persistence changes.

### Task 14: Execute cron jobs inside tenant context

**Files:**
- Modify: `src/copaw/app/crons/executor.py`
- Modify: `src/copaw/app/crons/manager.py`
- Modify: `src/copaw/app/tenant_context.py`
- Test: `tests/unit/app/crons/test_tenant_cron_execution.py`

- [ ] Wrap cron execution in the shared tenant/workspace context helper.
- [ ] Ensure both text jobs and agent jobs run with the correct tenant-scoped workspace context.
- [ ] Update error reporting and push-store append behavior to use tenant-scoped keys.
- [ ] Ensure timeout/cancellation paths still clear tenant context correctly.
- [ ] Add tests proving cron execution binds tenant context and does not leak events to other tenants.
- [ ] Run cron execution tests.
- [ ] Commit cron execution context restoration.

### Task 15: Make heartbeat tenant-scoped

**Files:**
- Modify: `src/copaw/app/crons/heartbeat.py`
- Modify: `src/copaw/app/crons/manager.py`
- Modify: `src/copaw/config/utils.py`
- Test: `tests/unit/app/crons/test_tenant_heartbeat.py`

- [ ] Move heartbeat file/config lookup to tenant-scoped paths.
- [ ] Ensure enable/disable/reschedule logic operates per tenant workspace.
- [ ] Verify heartbeat dispatch target and execution context are tenant-bound.
- [ ] Add tests proving tenant A heartbeat configuration does not affect tenant B.
- [ ] Run heartbeat tests.
- [ ] Commit heartbeat isolation.

### Task 16: Harden memory dependencies for tenant-scoped behavior

**Files:**
- Modify: `src/copaw/agents/memory/reme_light_memory_manager.py`
- Possibly modify: `src/copaw/agents/memory/agent_md_manager.py`
- Modify: `src/copaw/config/utils.py`
- Modify: `src/copaw/config/config.py`
- Test: `tests/unit/agents/memory/test_tenant_memory_scope.py`

- [ ] Verify that memory storage remains derived from `working_dir` and therefore tenant-scoped when the workspace root is tenant-scoped.
- [ ] Remove any remaining global config/agent-config assumptions used by memory summary, compaction, and index rebuild flows.
- [ ] Ensure memory-generated file operations restore the tenant workspace context before invoking file tools.
- [ ] Add tests proving memory artifacts and markdown memory files resolve inside the tenant workspace and do not cross tenants.
- [ ] Run tenant memory tests.
- [ ] Commit memory hardening.

### Task 17: Add tenant context binding to channel layer

**Files:**
- Modify: `src/copaw/app/channels/base.py`
- Modify: `src/copaw/app/workspace/workspace.py`
- Test: `tests/unit/app/channels/test_channel_tenant_binding.py`

- [ ] Add `tenant_id` property to `Workspace` class so channels can access the tenant identity of their owning workspace.
- [ ] In `BaseChannel._consume_one_request()`, wrap the entire processing path in `bind_tenant_context()` using the workspace's tenant_id, sender_id, and workspace_dir.
- [ ] Ensure the binding happens before `_payload_to_request()`, `_before_consume_process()`, and `_process()` calls.
- [ ] Verify that `_consume_with_tracker()` path also runs inside tenant context.
- [ ] Add unit tests proving channel message processing binds tenant context correctly.
- [ ] Add a test proving file writes during channel processing resolve to the tenant workspace directory.
- [ ] Add a test proving two channels belonging to different tenant workspaces do not share mutable state.
- [ ] Run channel tenant binding tests.
- [ ] Commit channel tenant binding.

### Task 18: Full secrets and env isolation

**Files:**
- Modify: `src/copaw/envs/store.py`
- Modify: `src/copaw/providers/provider_manager.py`
- Modify: `src/copaw/app/auth.py`
- Modify: `src/copaw/agents/skills_manager.py`
- Modify: `src/copaw/app/runner/runner.py`
- Modify: `src/copaw/constant.py`
- Modify: `src/copaw/config/utils.py`
- Test: `tests/unit/app/test_tenant_secrets_isolation.py`

- [ ] Refactor `load_envs_into_environ()` to only load system-level bootstrap variables (e.g. `COPAW_WORKING_DIR`, `COPAW_SECRET_DIR`) into `os.environ`. Remove tenant secret loading from startup path.
- [ ] Introduce `get_tenant_env(key, tenant_id=None)` helper that reads from tenant-scoped `envs.json` without polluting `os.environ`.
- [ ] Refactor `ProviderManager` to separate provider capability definitions (global) from provider credentials (tenant-scoped). Credentials should be loaded from `get_tenant_secrets_dir(tenant_id) / "providers"` at request time.
- [ ] Evaluate `auth.py` — if authentication is a system-level gateway concern, document it as intentionally global. If per-tenant auth is needed, migrate `AUTH_FILE` to tenant secret store.
- [ ] Refactor `skills_manager.py` to write skill env vars to tenant-scoped env store instead of `os.environ`.
- [ ] Refactor `runner.py` `.env` loading to load from tenant workspace directory, not `./`.
- [ ] Audit `constant.py` module-level `.env` loading — restrict to system-level bootstrap variables only.
- [ ] Add tests proving tenant A cannot read tenant B's API keys via `get_tenant_env()`.
- [ ] Add tests proving `os.environ` is not polluted with tenant-specific secrets after request processing.
- [ ] Add tests proving provider credentials are loaded from tenant-scoped paths.
- [ ] Run secrets isolation tests.
- [ ] Commit secrets isolation.

### Task 19: Fix cron job creation paths to inject tenant_id

**Files:**
- Modify: `src/copaw/app/crons/api.py`
- Modify: `src/copaw/app/crons/heartbeat.py`
- Modify: `src/copaw/app/crons/manager.py`
- Modify: `src/copaw/cli/cron_cmd.py`
- Test: `tests/unit/app/crons/test_cron_creation_tenant.py`

- [ ] In `POST /cron/jobs`, inject `tenant_id` from `request.state.tenant_id` into the created `CronJobSpec`, overriding any client-provided value.
- [ ] In `PUT /cron/jobs/{job_id}`, inject `tenant_id` from `request.state.tenant_id` into the updated spec.
- [ ] Add validation: reject job creation if `tenant_id` would be `None` in multi-tenant strict mode.
- [ ] Update CLI `copaw cron create` to accept `--tenant-id` parameter and send `X-Tenant-Id` header in HTTP requests.
- [ ] Wrap heartbeat callback execution in `bind_tenant_context()` with the owning workspace's tenant_id.
- [ ] Replace hardcoded `user_id="main"` in `run_heartbeat_once()` with tenant-aware user_id.
- [ ] Add tests proving API-created jobs always have tenant_id set from request context.
- [ ] Add tests proving heartbeat execution runs inside tenant context.
- [ ] Add a test proving no job can be persisted with `tenant_id=None` in strict mode.
- [ ] Run cron creation tests.
- [ ] Commit cron creation tenant_id injection.

### Task 20: Plan MultiAgentManager deprecation

**Files:**
- Modify: `src/copaw/app/_app.py`
- Modify: `src/copaw/app/agent_context.py`
- Modify: any remaining `MultiAgentManager` callers
- Test: existing workspace/agent tests

- [ ] Audit all remaining call sites of `MultiAgentManager` — list each caller and whether it can be migrated to `TenantWorkspacePool`.
- [ ] For each call site that can be migrated, route through `TenantWorkspacePool` instead.
- [ ] If any call site genuinely requires the old interface, add a deprecation comment with migration path.
- [ ] Remove `MultiAgentManager` from `_app.py` lifespan if all callers have been migrated; otherwise mark it as deprecated with a TODO.
- [ ] Ensure app startup/shutdown only manages `TenantWorkspacePool` as the primary workspace lifecycle owner.
- [ ] Run existing workspace and agent tests to verify no regressions.
- [ ] Commit MultiAgentManager deprecation progress.

### Task 21: Audit remaining global fallbacks and shared-state leaks

**Files:**
- Modify: `src/copaw/config/utils.py`
- Modify: `src/copaw/app/agent_context.py`
- Modify: `src/copaw/app/_app.py`
- Modify any remaining files found during grep/audit
- Test: targeted regression tests

- [ ] Search for remaining uses of global business storage fallbacks such as `WORKING_DIR / "jobs.json"`, `WORKING_DIR / "memory"`, `get_current_workspace_dir() or WORKING_DIR`, and similar patterns.
- [ ] Search for module-level global state that remains tenant-unsafe.
- [ ] Fix each finding by routing through tenant path helpers or tenant-local runtime state.
- [ ] Add small regression tests for each previously unsafe fallback that is removed.
- [ ] Run the targeted regression tests.
- [ ] Commit fallback cleanup.

### Task 22: End-to-end verification and documentation sync

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-multi-tenant-isolation-design.md` only if implementation-driven clarifications are required
- Test: relevant pytest suites

- [ ] Run all new tenant isolation unit tests.
- [ ] Run the existing router/settings/workspace/cron tests affected by these changes.
- [ ] Run a focused regression sweep for single-tenant mode using `tenant_id=default`.
- [ ] Verify the acceptance criteria from the spec one by one: request isolation, disk isolation, runtime isolation, context correctness, single-tenant compatibility.
- [ ] If implementation revealed a spec ambiguity, update the spec minimally to reflect the final intended behavior.
- [ ] Create the final implementation commit set or hand off to execution workflow.

---

## High-risk areas to watch during execution

### 1. Middleware ordering
If tenant identity, tenant workspace, auth, and agent-scoped middleware are applied in the wrong order, request context will be inconsistent or silently wrong.

### 2. Global config fallbacks
`load_config()`, `load_agent_config()`, heartbeat helpers, and legacy config writers currently assume global state in multiple places. These are the most likely sources of accidental cross-tenant reads and writes.

### 3. Console push leakage
The current push store is process-global and can return recent messages without a session filter. This is a direct data leak and must be fixed before considering the feature usable.

### 4. Agent namespace collisions
Current agent APIs and runtime resolution are app-global. Tenant-first lookup must be complete before claiming isolation.

### 5. Cron/background context loss
Cron and background flows do not pass through HTTP middleware. Any missed context restore here will reintroduce global fallbacks.

### 6. Memory indirect config reads
Memory storage itself is mostly safe once `working_dir` is tenant-scoped, but helper calls that load config or agent config can still escape the tenant boundary.

### 7. Secrets semantics
If tenant secrets are still mirrored into global environment variables as the source of truth, isolation is not real. Key offenders: `load_envs_into_environ()`, `skills_manager.py` direct `os.environ` writes, `runner.py` `.env` loading.

### 8. Channel layer tenant context gap
All 14 channel implementations process messages without tenant context binding. This is the largest isolation gap — every IM message runs in an unscoped context. Fix must be in `BaseChannel._consume_one_request()` to avoid per-channel duplication.

### 9. Cron job creation without tenant_id
API endpoints `POST/PUT /cron/jobs` and CLI `copaw cron create` do not inject tenant_id into new jobs. Jobs created without tenant_id will execute in wrong/missing tenant context.

### 10. MultiAgentManager / TenantWorkspacePool dual ownership
Two parallel workspace lifecycle managers create ambiguity about which path to use. Must converge to single owner before claiming isolation is complete.

---

## Verification checklist

### Request isolation
- Missing `X-Tenant-Id` on stateful routes returns 4xx.
- Tenant A cannot read or mutate tenant B chat, settings, agent, cron, file, or push-store data.

### Disk isolation
- Tenant-specific directories contain separate `config.json`, `jobs.json`, `chats.json`, `memory/`, `media/`, and secret storage.
- No new business data files are written directly under the global root except explicitly system-level state.

### Runtime isolation
- `task_tracker`, `chat_manager`, `cron_manager`, and active agent state are tenant-local.
- Console reconnect/stop and cron push events cannot cross tenant boundaries.

### Context correctness
- File and shell tools invoked during HTTP requests resolve relative paths against the current tenant workspace.
- Cron and heartbeat execution do the same without HTTP middleware.
- Channel message processing runs inside tenant context with correct workspace_dir.
- Missing workspace context raises instead of falling back (in multi-tenant strict mode).

### Secrets isolation
- Tenant A cannot read tenant B's API keys, provider credentials, or env secrets.
- `os.environ` does not contain any tenant-specific secrets after startup.
- Provider credentials are loaded from tenant-scoped paths at request time.
- Skill env vars do not leak across tenants via `os.environ`.

### Cron job integrity
- All persisted cron jobs have a non-null `tenant_id`.
- Jobs created via API, CLI, and heartbeat all carry correct tenant_id.
- Job execution restores full tenant context before running.

### Single-tenant compatibility
- Using `tenant_id=default` preserves existing user-visible behavior while still running through the new tenant architecture.

### Workspace lifecycle
- Only one workspace lifecycle manager (`TenantWorkspacePool`) owns workspace creation/destruction.
- `MultiAgentManager` is either removed or clearly marked as deprecated with no new callers.

---

## Recommended execution order

1. Tasks 1-5 (runtime foundation)
2. Tasks 6-12 (router/config/secrets surface area)
3. Tasks 13-15 (cron/heartbeat persistence and execution)
4. Task 16 (memory hardening)
5. Task 17 (channel layer tenant binding)
6. Task 18 (full secrets/env isolation)
7. Task 19 (cron creation path tenant_id injection)
8. Task 20 (MultiAgentManager deprecation)
9. Tasks 21-22 (audit and verification)

---

Plan complete and saved to `docs/superpowers/plans/2026-04-01-multi-tenant-isolation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
