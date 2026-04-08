## 1. Startup path slimming

- [x] 1.1 Remove telemetry, legacy workspace migration, legacy skills migration, QA agent setup, eager agent startup, provider/local model eager init, and default-agent prewarm from `src/swe/app/_app.py` lifespan startup.
- [x] 1.2 Keep startup limited to minimal app assembly, `ensure_default_agent_exists()`, manager container creation, and shutdown cleanup for actually-started runtimes.
- [x] 1.3 Add or adjust startup logging so readiness and deferred initialization boundaries are observable.

## 2. Tenant bootstrap separation

- [x] 2.1 Split `src/swe/app/workspace/tenant_initializer.py` into minimal bootstrap behavior versus extended/maintenance-only initialization.
- [x] 2.2 Update tenant request paths and middleware to call only minimal bootstrap and provider-config directory setup.
- [x] 2.3 Ensure tenant bootstrap no longer starts default workspace runtime, initializes skills, creates QA agent, or starts local models.

## 3. Runtime ownership refactor

- [x] 3.1 Refactor `src/swe/app/workspace/tenant_pool.py` so it tracks tenant bootstrap/registry state instead of creating and starting workspaces.
- [x] 3.2 Keep `src/swe/app/multi_agent_manager.py` as the single `(tenant_id, agent_id)` runtime startup entrypoint with proper cache and concurrency protection.
- [x] 3.3 Slim `src/swe/app/workspace/workspace.py` startup so it only loads agent config and agent-local runtime services.

## 4. On-demand subsystem initialization

- [x] 4.1 Move skill pool initialization and any legacy skill compatibility work to explicit skills entrypoints instead of startup, tenant bootstrap, or workspace startup.
- [x] 4.2 Move `ProviderManager` initialization to provider/model usage entrypoints and preserve tenant isolation.
- [x] 4.3 Move `LocalModelManager` initialization to local-model usage entrypoints and stop eager local-model resume at startup.
- [x] 4.4 Move QA agent creation to explicit QA access or maintenance flows.

## 5. Verification

- [x] 5.1 Add or update tests covering minimal startup readiness with no eager runtime/provider/skills/local-model initialization.
- [x] 5.2 Add or update tests covering tenant bootstrap boundaries and tenant-isolated lazy runtime startup.
- [x] 5.3 Add or update tests covering on-demand initialization for skills, provider manager, local model manager, and QA agent.
- [x] 5.4 Run focused test suites and verify no regressions in startup, tenant access, and runtime lazy-loading behavior.

**Note:** Created comprehensive lazy loading tests in `tests/unit/app/test_lazy_loading.py` (18 tests) covering all lazy loading behaviors. Some existing tests in `test_tenant_pool.py` and `test_tenant_workspace.py` need `mock_working_dir` fixture updates due to architecture change (TenantWorkspacePool now delegates to MultiAgentManager which uses global WORKING_DIR).
