# -*- coding: utf-8 -*-
"""Agent context utilities for multi-agent and multi-tenant support.

Provides utilities to get the correct agent instance for each request,
with tenant-first resolution order.
"""
from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING
from fastapi import Request

from ..config.utils import load_config, get_tenant_config_path
from ..config.context import (
    get_current_tenant_id,
    get_current_user_id,
    TenantContextError,
)

if TYPE_CHECKING:
    from .workspace import Workspace

# Context variable to store current agent ID across async calls
_current_agent_id: ContextVar[Optional[str]] = ContextVar(
    "current_agent_id",
    default=None,
)


def _get_tenant_aware_config(tenant_id: Optional[str] = None):
    """Get config with tenant awareness.

    When tenant_id is provided, loads config from tenant workspace.
    Otherwise falls back to global config.

    Args:
        tenant_id: Optional tenant ID for tenant-scoped config.

    Returns:
        Configuration object.
    """
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return load_config()
    return load_config(get_tenant_config_path(tenant_id))


async def get_agent_for_request(
    request: Request,
    agent_id: Optional[str] = None,
) -> "Workspace":
    """Get agent workspace for current request with tenant-first resolution.

    Resolution order (tenant-first):
    1. Resolve tenant from X-Tenant-Id header or context
    2. Resolve user from X-User-Id header or context
    3. Resolve agent from context, header, or tenant-local config

    Args:
        request: FastAPI request object
        agent_id: Agent ID override (highest priority)

    Returns:
        Workspace for the specified or active agent

    Raises:
        HTTPException: If agent not found or tenant context missing
    """
    from fastapi import HTTPException

    # Step 1: Resolve tenant context
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        # Try to get from request state (set by tenant middleware)
        tenant_id = getattr(request.state, "tenant_id", None)

    # Step 1b: Prefer tenant workspace already bound by middleware when it
    # matches the resolved target agent.
    workspace = getattr(request.state, "workspace", None)

    # Step 2: Resolve user context
    user_id = get_current_user_id()
    if user_id is None:
        user_id = getattr(request.state, "user_id", None)

    # Step 3: Determine which agent to use
    target_agent_id = agent_id
    explicit_agent_requested = target_agent_id is not None

    # Check request.state.agent_id (from agent-scoped router)
    if not target_agent_id and hasattr(request.state, "agent_id"):
        target_agent_id = request.state.agent_id
        explicit_agent_requested = target_agent_id is not None

    # Check X-Agent-Id header
    if not target_agent_id:
        target_agent_id = request.headers.get("X-Agent-Id")
        explicit_agent_requested = target_agent_id is not None

    # Load tenant-aware config for fallback and validation
    config = None
    if workspace is not None and not explicit_agent_requested:
        return workspace
    if not target_agent_id:
        # Fallback to active agent from config
        config = _get_tenant_aware_config(tenant_id)
        target_agent_id = target_agent_id or config.agents.active_agent or "default"

    if workspace is not None and getattr(workspace, "agent_id", None) == target_agent_id:
        return workspace

    # Check if agent exists and is enabled (using tenant-aware config)
    if config is None:
        config = _get_tenant_aware_config(tenant_id)

    if target_agent_id not in config.agents.profiles:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{target_agent_id}' not found",
        )

    agent_ref = config.agents.profiles[target_agent_id]
    if not getattr(agent_ref, "enabled", True):
        raise HTTPException(
            status_code=403,
            detail=f"Agent '{target_agent_id}' is disabled",
        )

    # Get MultiAgentManager (tenant-aware resolution)
    if not hasattr(request.app.state, "multi_agent_manager"):
        raise HTTPException(
            status_code=500,
            detail="MultiAgentManager not initialized",
        )

    # Store tenant/user context in request state for downstream use
    if tenant_id:
        request.state.tenant_id = tenant_id
    if user_id:
        request.state.user_id = user_id

    manager = request.app.state.multi_agent_manager

    try:
        workspace = await manager.get_agent(target_agent_id, tenant_id=tenant_id)
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{target_agent_id}' not found",
            )
        return workspace
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent: {str(e)}",
        ) from e


def get_active_agent_id(tenant_id: Optional[str] = None) -> str:
    """Get current active agent ID from config.

    Args:
        tenant_id: Optional tenant ID for tenant-scoped lookup.

    Returns:
        Active agent ID, defaults to "default"
    """
    try:
        config = _get_tenant_aware_config(tenant_id)
        return config.agents.active_agent or "default"
    except Exception:
        return "default"


def set_current_agent_id(agent_id: str) -> None:
    """Set current agent ID in context.

    Args:
        agent_id: Agent ID to set
    """
    _current_agent_id.set(agent_id)


def get_current_agent_id(tenant_id: Optional[str] = None) -> str:
    """Get current agent ID from context or config fallback.

    Args:
        tenant_id: Optional tenant ID for tenant-scoped lookup.

    Returns:
        Current agent ID, defaults to active agent or "default"
    """
    agent_id = _current_agent_id.get()
    if agent_id:
        return agent_id
    return get_active_agent_id(tenant_id)


def get_tenant_workspace(request: Request) -> Optional["Workspace"]:
    """Get tenant workspace from request state.

    Args:
        request: FastAPI request object

    Returns:
        Workspace if tenant workspace is bound, None otherwise
    """
    return getattr(request.state, "workspace", None)


def get_tenant_workspace_strict(request: Request) -> "Workspace":
    """Get tenant workspace from request state, raising if not set.

    Args:
        request: FastAPI request object

    Returns:
        Workspace for the current tenant

    Raises:
        TenantContextError: If workspace is not set in request state
    """
    workspace = getattr(request.state, "workspace", None)
    if workspace is None:
        raise TenantContextError(
            "Tenant workspace not bound to request. "
            "Ensure tenant workspace middleware is installed."
        )
    return workspace


__all__ = [
    "get_agent_for_request",
    "get_active_agent_id",
    "set_current_agent_id",
    "get_current_agent_id",
    "get_tenant_workspace",
    "get_tenant_workspace_strict",
]
