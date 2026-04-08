## Why

The backend startup lazy-loading work reduced cold start, but the first request for a tenant still performs provider-related initialization inside `TenantWorkspaceMiddleware`. That makes tenant entry pay for provider storage setup even when the request does not use provider or model features, which weakens the intended feature-level lazy-loading boundary.

## What Changes

- Move tenant provider storage initialization out of `TenantWorkspaceMiddleware`.
- Define provider and model feature entrypoints as the only places allowed to ensure tenant provider storage readiness.
- Keep tenant workspace bootstrap focused on workspace concerns only.
- Preserve the current per-tenant provider storage layout and default-template copy semantics in this iteration.
- Avoid frontend changes and avoid narrowing workspace bootstrap scope in this iteration.

## Capabilities

### New Capabilities
- `tenant-provider-init-boundary`: Enforce provider initialization at provider/model feature boundaries instead of generic tenant middleware.

### Modified Capabilities
- None.

## Impact

- Affected backend middleware: `src/swe/app/middleware/tenant_workspace.py`
- Affected provider/model initialization paths: `src/swe/app/routers/providers.py`, `src/swe/app/routers/local_models.py`, `src/swe/agents/model_factory.py`
- Affected provider subsystem ownership boundary: `src/swe/providers/provider_manager.py`
- No frontend/API contract changes are required for this iteration.
