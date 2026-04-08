## 1. Runtime active model source unification

- [x] 1.1 Audit and update `src/swe/providers/provider_manager.py` so tenant-aware active model reads and writes are the single supported path
- [x] 1.2 Refactor `src/swe/agents/model_factory.py` to resolve active model from tenant-aware `ProviderManager` instead of `TenantModelContext` / `tenant_models.json`
- [x] 1.3 Refactor `src/swe/agents/prompt.py` so active model info and multimodal capability checks use provider-backed active model state
- [x] 1.4 Refactor `src/swe/agents/react_agent.py` logging to use the provider-backed active model source

## 2. Request context and API consolidation

- [x] 2.1 Remove or replace `TenantWorkspaceMiddleware` runtime loading of full `TenantModelConfig`
- [x] 2.2 Update `src/swe/app/routers/providers.py` so `/models/active` is the canonical tenant active-model API backed by `ProviderManager`
- [x] 2.3 Decide the fate of `GET /providers` and either deprecate it or reimplement it as a provider-backed compatibility view without `tenant_models.json`
- [x] 2.4 Add short-term backend compatibility for legacy `scope=agent` requests while preserving tenant-level active-model semantics

## 3. Migration compatibility and legacy cleanup

- [x] 3.1 Implement one-time recovery/migration from legacy `tenant_models.json` when `providers/active_model.json` is missing
- [x] 3.2 Remove active model write paths that persist or depend on `tenant_models.json`
- [x] 3.3 Reduce `src/swe/tenant_models/` runtime responsibility so it is no longer on the main active-model path

## 4. Frontend alignment

- [x] 4.1 Update `console/src/pages/Chat/ModelSelector/index.tsx` to stop sending unsupported `scope=agent`
- [x] 4.2 Align `console/src/api/modules/provider.ts` active model request semantics with the tenant-level backend contract
- [x] 4.3 Verify Chat and Settings model selection flows still display and switch the tenant active model correctly

## 5. Verification and cleanup

- [x] 5.1 Update or add backend tests covering tenant-scoped active model resolution, writes, and legacy recovery behavior
- [x] 5.2 Update frontend checks/tests for the chat model selector scope change (N/A - no frontend test infrastructure)
- [x] 5.3 Search for remaining runtime references to `tenant_models.json` and remove or quarantine obsolete uses
- [x] 5.4 Update migration scripts and design/docs that still describe `tenant_models.json` as an active runtime source
