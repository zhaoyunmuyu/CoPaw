# Agent Init API Design

## Summary

Add a new HTTP endpoint `POST /api/agent/init` that appends text to the end of a top-level Markdown file in the workspace of a specific agent under the current tenant. The request body contains `filename`, `text`, and `agentId`. Tenant resolution remains header-based through `X-Tenant-Id`; `tenantId` is not accepted in the request body.

This endpoint is intentionally narrow. It is not a general file-write API. It only targets top-level workspace Markdown files, does not allow path traversal or nested paths, and does not operate on the `memory/` directory.

## Goals

- Provide a dedicated API for appending bootstrap or initialization text into an agent workspace file.
- Reuse the existing tenant middleware and agent workspace resolution flow.
- Reuse the existing Markdown file manager behavior for `.md` normalization and append semantics.
- Keep the change localized to the existing agent router and matching unit tests.

## Non-Goals

- Supporting arbitrary relative paths or non-Markdown files.
- Supporting writes into `memory/` files.
- Changing the existing `/api/agent/files/*` read/write contract.
- Introducing a new service layer for this one endpoint.

## Recommended Approach

Implement a dedicated endpoint in the existing agent router:

- Route: `POST /api/agent/init`
- Location: `src/swe/app/routers/agent.py`
- Tenant resolution: existing `X-Tenant-Id` middleware
- Agent resolution: explicit `agentId` from request body via `get_agent_for_request(request, agent_id=...)`
- File operation: `AgentMdManager.append_working_md(filename, text)`

This matches the requested API shape while staying aligned with current backend patterns. It avoids coupling append behavior into the existing overwrite-based file APIs and avoids introducing a second agent-scoped route shape for the same action.

## Alternatives Considered

### 1. Agent-scoped route

Use `POST /api/agents/{agentId}/agent/init`.

Pros:
- Fits the existing agent-scoped router layout.
- Removes `agentId` from the request body.

Cons:
- Does not match the requested endpoint shape.
- Adds a second way to address the same behavior.

### 2. Extend existing file write APIs

Add an append mode to `/api/agent/files/{md_name}`.

Pros:
- No new endpoint.

Cons:
- Blurs overwrite and append semantics.
- Makes a simple business action harder to reason about.
- Moves the contract farther from the user’s explicit request.

## API Contract

### Endpoint

`POST /api/agent/init`

### Headers

- `X-Tenant-Id`: required by existing tenant middleware

### Request Body

```json
{
  "filename": "PROFILE",
  "text": "\nNew initialization block",
  "agentId": "default"
}
```

### Request Validation

- `filename` is required and must not be blank.
- `filename` must refer to a top-level Markdown file name only.
- `filename` must not contain `/`, `\\`, or `..`.
- `filename` may omit the `.md` suffix; existing manager behavior will normalize it.
- `text` is required but may be an empty string.
- `agentId` is required and must not be blank.

### Success Response

HTTP `200 OK`

```json
{
  "appended": true,
  "filename": "PROFILE.md",
  "agent_id": "default"
}
```

The response returns the resolved Markdown filename and target agent ID. It does not return the absolute workspace path.

## Execution Flow

1. FastAPI receives `POST /api/agent/init`.
2. Existing tenant middleware validates and binds `X-Tenant-Id`.
3. The route validates the request body fields.
4. The route resolves the target workspace with `get_agent_for_request(request, agent_id=body.agentId)`.
5. The route constructs `AgentMdManager(str(workspace.workspace_dir))`.
6. The route appends `text` into the target working Markdown file with `append_working_md`.
7. If the file does not exist, the existing append behavior creates it and writes the provided content.
8. The route returns a compact success payload.

## Validation and Safety Rules

The endpoint must reject any filename that could escape the top-level workspace Markdown contract.

Rejected examples:

- `memory/PROFILE.md`
- `../PROFILE.md`
- `nested/PROFILE.md`
- `a\\b.md`

Accepted examples:

- `PROFILE`
- `PROFILE.md`
- `custom-notes`
- `custom-notes.md`

The route should perform explicit validation before calling `AgentMdManager` so the endpoint contract is unambiguous and does not accidentally become a path-based write surface.

## Error Handling

- Missing or invalid `X-Tenant-Id`: existing middleware returns `400`.
- Unknown agent within the tenant: return `404`.
- Disabled agent: return `403`.
- Invalid request body or filename: return `400`.
- Unexpected file system or runtime failures: return `500`.

The route should preserve the current router style in `agent.py`, which maps expected exceptions to `HTTPException` and falls back to `500` for unexpected failures.

## Implementation Notes

- Add a dedicated request model such as `AgentInitRequest` in `src/swe/app/routers/agent.py`.
- Keep the implementation in the router module to match existing patterns in `agent.py`.
- Reuse `get_agent_for_request` instead of manually loading tenant config or walking workspace directories.
- Reuse `AgentMdManager.append_working_md` instead of adding a new file helper.
- Do not expose internal workspace paths in the API response.

## Testing Plan

Add unit tests under `tests/unit/app/` covering:

1. Successful append into an existing top-level Markdown file for a specified tenant and agent.
2. Auto-create behavior when the target file does not yet exist.
3. Filename normalization when `.md` is omitted.
4. Rejection of invalid filenames containing path separators or traversal markers.
5. Agent isolation within the same tenant: writing to one `agentId` must not affect another agent workspace.
6. Tenant isolation: the same `agentId` under two tenants must resolve to separate workspaces.
7. Missing tenant header: request is rejected by middleware with `400`.

## Impact

The change is low-risk and localized:

- One new endpoint in the agent router
- One request model
- Targeted unit tests

No data model, provider, runner, or console protocol changes are required for this design.
