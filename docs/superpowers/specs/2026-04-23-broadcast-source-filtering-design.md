# Broadcast Tenant Source Filtering Design

**Date**: 2026-04-23
**Status**: Draft
**Author**: Claude

## Background

The broadcast functionality (skills, MCP, model configuration) currently returns all tenants from the file system scan without filtering by the current user's `source_id`. This allows users to see and potentially broadcast to tenants that belong to other sources, which violates source isolation requirements.

### Current State

- Skills broadcast: `GET /skills/pool/broadcast/tenants` → returns `list_logical_tenant_ids(source_id)` which only scans the file system
- Model broadcast: `GET /models/distribution/tenants` → same as above
- MCP broadcast: No dedicated tenant list endpoint
- `swe_tenant_init_source` table already stores the mapping of `tenant_id` → `source_id`
- `TenantInitSourceStore.get_by_source(source_id)` can query all tenants for a given source

## Goal

Add a filtering layer to the broadcast tenant list endpoints so that:
1. Only tenants belonging to the current user's `source_id` are returned
2. When database is unavailable, return an empty list (security-first)
3. When `source_id` is missing from the request, return an empty list
4. Add MCP broadcast tenant list endpoint for consistency

## Design

### 1. Extend `list_logical_tenant_ids` Function

**File**: `src/swe/config/utils.py`

Add an optional `source_filter` parameter. When enabled:
- Call `TenantInitSourceStore.get_by_source(source_id)` to get source-scoped tenants
- Return empty list if database unavailable or source_id is empty
- Convert the function to `async def` since the store method is async

```python
async def list_logical_tenant_ids(
    source_id: str | None = None,
    *,
    source_filter: bool = False,
) -> list[str]:
    """Return tenant IDs, optionally filtered by source_id.

    Args:
        source_id: Current request's source_id (from X-Source-Id header)
        source_filter: Enable source_id filtering. When enabled:
            - Database unavailable: return empty list
            - source_id empty: return empty list
            - Otherwise: return tenants from swe_tenant_init_source table

    Returns:
        List of tenant IDs
    """
    if source_filter:
        from ..app.workspace.tenant_init_source_store import (
            get_tenant_init_source_store,
        )
        store = get_tenant_init_source_store()
        if store is None or not source_id:
            return []
        rows = await store.get_by_source(source_id)
        return sorted({row["tenant_id"] for row in rows})

    # Existing logic unchanged
    tenant_ids = list_all_tenant_ids()
    if not source_id:
        return tenant_ids

    logical_tenant_ids: list[str] = []
    effective_default_tenant_id = resolve_effective_tenant_id(
        "default",
        source_id,
    )
    has_default_tenant = False

    for tenant_id in tenant_ids:
        if tenant_id in {"default", effective_default_tenant_id}:
            has_default_tenant = True
            continue
        logical_tenant_ids.append(tenant_id)

    if has_default_tenant:
        logical_tenant_ids.append("default")

    return sorted(set(logical_tenant_ids))
```

### 2. Modify Skills Broadcast Tenant List Endpoint

**File**: `src/swe/app/routers/skills.py`

Update the endpoint to use `source_filter=True`:

```python
@router.get(
    "/pool/broadcast/tenants",
    response_model=BroadcastTenantListResponse,
)
async def list_broadcast_tenants(
    request: Request,
) -> BroadcastTenantListResponse:
    return BroadcastTenantListResponse(
        tenant_ids=await list_logical_tenant_ids(
            _request_source_id(request),
            source_filter=True,
        ),
    )
```

### 3. Modify Model Broadcast Tenant List Endpoint

**File**: `src/swe/app/routers/providers.py`

Update the endpoint to use `source_filter=True`:

```python
@router.get(
    "/distribution/tenants",
    response_model=DistributionTenantListResponse,
)
async def list_active_model_distribution_tenants(
    request: Request,
) -> DistributionTenantListResponse:
    return DistributionTenantListResponse(
        tenant_ids=await list_logical_tenant_ids(
            _request_source_id(request),
            source_filter=True,
        ),
    )
```

### 4. Add MCP Distribution Tenant List Endpoint

**File**: `src/swe/app/routers/mcp.py`

Add new response model and endpoint:

```python
class MCPDistributionTenantListResponse(BaseModel):
    """Response for MCP distribution tenant list."""
    tenant_ids: List[str] = Field(default_factory=list)


@router.get(
    "/distribution/tenants",
    response_model=MCPDistributionTenantListResponse,
    summary="List tenants for MCP client distribution",
)
async def list_mcp_distribution_tenants(
    request: Request,
) -> MCPDistributionTenantListResponse:
    """Return all tenants belonging to the current source_id."""
    return MCPDistributionTenantListResponse(
        tenant_ids=await list_logical_tenant_ids(
            _request_source_id(request),
            source_filter=True,
        ),
    )
```

### 5. Frontend Updates

**Files**: `console/src/api/modules/skill.ts`, `console/src/api/modules/provider.ts`

Add MCP tenant list API:

```typescript
// In console/src/api/modules/mcp.ts (new or existing)
listMcpDistributionTenants: () =>
  request<MCPDistributionTenantListResponse>("/mcp/distribution/tenants"),
```

## Behavior Summary

| Condition | Response |
|-----------|----------|
| source_id present, database connected | Tenants from `swe_tenant_init_source` where `source_id = X` |
| source_id present, database unavailable | Empty list |
| source_id missing | Empty list |
| source_filter=False (default) | Existing file system scan behavior |

## Security Considerations

- **Fail-secure**: Database unavailability returns empty list instead of all tenants
- **Source isolation**: Users can only see and broadcast to tenants under their own source
- **No double validation**: Broadcast execution does not re-validate; tenant list filtering is trusted

## Testing

1. Unit test for `list_logical_tenant_ids` with `source_filter=True`
2. Unit test for each broadcast tenant list endpoint
3. Integration test for database unavailable scenario
4. Integration test for missing source_id scenario

## Implementation Order

1. Modify `list_logical_tenant_ids` to async with source_filter parameter
2. Update skills broadcast endpoint
3. Update model broadcast endpoint
4. Add MCP distribution tenant list endpoint
5. Update frontend API modules
6. Add tests
