## 1. Backend distribution API

- [x] 1.1 Add MCP distribution request/response models in `src/swe/app/routers/mcp.py`
- [x] 1.2 Add `POST /mcp/distribute/default-agents` with validation for non-empty `client_keys`, non-empty `target_tenant_ids`, and required `overwrite=true`
- [x] 1.3 Resolve the source tenant current agent and load original `MCPClientConfig` entries by `client_key`
- [x] 1.4 Add per-tenant distribution orchestration that validates tenant IDs, bootstraps target tenants, writes selected clients into each target tenant `default` agent, and returns per-tenant results
- [x] 1.5 Reload each successful target tenant runtime with explicit `reload_agent(\"default\", tenant_id=target_tenant_id)`

## 2. Frontend MCP page workflow

- [x] 2.1 Add multi-select state for MCP clients on `console/src/pages/Agent/MCP/index.tsx`
- [x] 2.2 Add a page-level “distribute to tenants” toolbar action that opens an MCP-specific distribution modal
- [x] 2.3 Add MCP API client and response types for distribution in `console/src/api/modules/mcp.ts` and `console/src/api/types/mcp.ts`
- [x] 2.4 Reuse the discovered-tenant API and wire the modal submission payload to send only `client_keys`, `target_tenant_ids`, and `overwrite`
- [x] 2.5 Show per-tenant success and failure feedback in the MCP page after submission

## 3. Shared tenant target selection

- [x] 3.1 Extract the discovered-tenant plus manual-entry selection behavior from the skill-pool broadcast flow into a reusable tenant target picker component or helper
- [x] 3.2 Reuse that picker in the MCP distribution modal without coupling the MCP page to skill-specific selection UI
- [x] 3.3 Make the MCP distribution UI explicitly state that writes go to each target tenant `default` agent and overwrite selected same-key clients

## 4. Verification

- [x] 4.1 Add backend tests for distributing to an already bootstrapped tenant
- [x] 4.2 Add backend tests for distributing to a not-yet-bootstrapped tenant
- [x] 4.3 Add backend tests that verify original `env` and `headers` values are copied rather than masked console values
- [x] 4.4 Add backend tests for overwrite semantics, unchanged unselected target clients, and per-tenant partial success behavior
- [x] 4.5 Add frontend contract or component coverage for batch selection, tenant target selection reuse, request payload shape, and result dialogs
