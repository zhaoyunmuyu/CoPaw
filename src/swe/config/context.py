# -*- coding: utf-8 -*-
"""Context variables for tenant isolation and workspace directory.

This module provides context variables to pass tenant identity, user identity,
and workspace directory to tool functions, enabling strict tenant isolation
in a multi-tenant environment.
"""
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Generator
from contextlib import contextmanager

# Context variable to store the current tenant ID
current_tenant_id: ContextVar[str | None] = ContextVar(
    "current_tenant_id",
    default=None,
)

# Context variable to store the current user ID
current_user_id: ContextVar[str | None] = ContextVar(
    "current_user_id",
    default=None,
)

# Context variable to store the current agent's workspace directory
current_workspace_dir: ContextVar[Path | None] = ContextVar(
    "current_workspace_dir",
    default=None,
)

# Context variable to store the current source ID (from X-Source-Id header)
current_source_id: ContextVar[str | None] = ContextVar(
    "current_source_id",
    default=None,
)


def get_current_tenant_id() -> str | None:
    """Get the current tenant ID from context.

    Returns:
        The current tenant ID, or None if not set.
    """
    return current_tenant_id.get()


def set_current_tenant_id(tenant_id: str | None) -> Token:
    """Set the current tenant ID in context.

    Args:
        tenant_id: The tenant ID to set.

    Returns:
        Token for resetting the context variable.
    """
    return current_tenant_id.set(tenant_id)


def reset_current_tenant_id(token: Token) -> None:
    """Reset the current tenant ID using a token.

    Args:
        token: The token returned by set_current_tenant_id.
    """
    current_tenant_id.reset(token)


def get_current_user_id() -> str | None:
    """Get the current user ID from context.

    Returns:
        The current user ID, or None if not set.
    """
    return current_user_id.get()


def set_current_user_id(user_id: str | None) -> Token:
    """Set the current user ID in context.

    Args:
        user_id: The user ID to set.

    Returns:
        Token for resetting the context variable.
    """
    return current_user_id.set(user_id)


def reset_current_user_id(token: Token) -> None:
    """Reset the current user ID using a token.

    Args:
        token: The token returned by set_current_user_id.
    """
    current_user_id.reset(token)


def get_current_source_id() -> str | None:
    """Get the current source ID from context.

    Returns:
        The current source ID, or None if not set.
    """
    return current_source_id.get()


def resolve_runtime_tenant_id(
    tenant_id: str | None,
    source_id: str | None,
) -> str | None:
    """Resolve the tenant ID used by runtime-scoped storage and workspaces.

    Unlike :func:`resolve_effective_tenant_id`, this helper is tolerant of
    missing ``source_id`` and simply returns the original ``tenant_id`` in that
    case. This makes it safe for generic runtime code paths that may run in
    both source-scoped and non-source-scoped contexts.
    """
    if tenant_id is None:
        return None
    if tenant_id != "default" or not source_id:
        return tenant_id
    return resolve_effective_tenant_id(tenant_id, source_id)


def set_current_source_id(source_id: str | None) -> Token:
    """Set the current source ID in context.

    Args:
        source_id: The source ID to set.

    Returns:
        Token for resetting the context variable.
    """
    return current_source_id.set(source_id)


def reset_current_source_id(token: Token) -> None:
    """Reset the current source ID using a token.

    Args:
        token: The token returned by set_current_source_id.
    """
    current_source_id.reset(token)


def get_current_workspace_dir() -> Path | None:
    """Get the current agent's workspace directory from context.

    Returns:
        Path to the current agent's workspace directory, or None if not set.
    """
    return current_workspace_dir.get()


def get_current_effective_tenant_id() -> str | None:
    """Get the current runtime tenant ID with default+source isolation."""
    return resolve_runtime_tenant_id(
        get_current_tenant_id(),
        get_current_source_id(),
    )


def set_current_workspace_dir(workspace_dir: Path | None) -> Token:
    """Set the current agent's workspace directory in context.

    Args:
        workspace_dir: Path to the agent's workspace directory.

    Returns:
        Token for resetting the context variable.
    """
    return current_workspace_dir.set(workspace_dir)


def reset_current_workspace_dir(token: Token) -> None:
    """Reset the current workspace directory using a token.

    Args:
        token: The token returned by set_current_workspace_dir.
    """
    current_workspace_dir.reset(token)


class TenantContextError(RuntimeError):
    """Raised when tenant context is required but not available."""


def get_current_tenant_id_strict() -> str:
    """Get the current tenant ID, raising if not set.

    Returns:
        The current tenant ID.

    Raises:
        TenantContextError: If tenant ID is not set in context.
    """
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        raise TenantContextError(
            "Tenant ID is not set in context. "
            "Ensure this code runs within a tenant-scoped request or context.",
        )
    return tenant_id


def get_current_user_id_strict() -> str:
    """Get the current user ID, raising if not set.

    Returns:
        The current user ID.

    Raises:
        TenantContextError: If user ID is not set in context.
    """
    user_id = current_user_id.get()
    if user_id is None:
        raise TenantContextError(
            "User ID is not set in context. "
            "Ensure this code runs within a tenant-scoped request or context.",
        )
    return user_id


def get_current_workspace_dir_strict() -> Path:
    """Get the current workspace directory, raising if not set.

    Returns:
        Path to the current workspace directory.

    Raises:
        TenantContextError: If workspace directory is not set in context.
    """
    workspace_dir = current_workspace_dir.get()
    if workspace_dir is None:
        raise TenantContextError(
            "Workspace directory is not set in context. "
            "Ensure this code runs within a tenant-scoped request or context.",
        )
    return workspace_dir


@contextmanager
def tenant_context(
    tenant_id: str | None = None,
    user_id: str | None = None,
    workspace_dir: Path | None = None,
    source_id: str | None = None,
) -> Generator[None, None, None]:
    """Context manager for binding tenant context.

    Temporarily sets tenant_id, user_id, workspace_dir, and source_id
    in context, restoring previous values on exit.

    Args:
        tenant_id: The tenant ID to set.
        user_id: The user ID to set.
        workspace_dir: The workspace directory to set.
        source_id: The source ID to set.

    Yields:
        None

    Example:
        with tenant_context(tenant_id="acme", user_id="alice"):
            # Code here has access to tenant context
            process_request()
        # Context restored after exit
    """
    tokens: list[tuple[str, Token[Any]]] = []
    try:
        if tenant_id is not None:
            tokens.append(("tenant", current_tenant_id.set(tenant_id)))
        if user_id is not None:
            tokens.append(("user", current_user_id.set(user_id)))
        if workspace_dir is not None:
            tokens.append(
                ("workspace", current_workspace_dir.set(workspace_dir)),
            )
        if source_id is not None:
            tokens.append(("source", current_source_id.set(source_id)))
        yield
    finally:
        for name, token in reversed(tokens):
            if name == "tenant":
                current_tenant_id.reset(token)
            elif name == "user":
                current_user_id.reset(token)
            elif name == "workspace":
                current_workspace_dir.reset(token)
            elif name == "source":
                current_source_id.reset(token)


# Context variable to store the recent_max_bytes limit
current_recent_max_bytes: ContextVar[int | None] = ContextVar(
    "current_recent_max_bytes",
    default=None,
)


def get_current_recent_max_bytes() -> int | None:
    """Get the current agent's recent_max_bytes limit from context.

    Returns:
        Byte limit for recent tool output truncation, or None if not set.
    """
    return current_recent_max_bytes.get()


def set_current_recent_max_bytes(max_bytes: int | None) -> None:
    """Set the current agent's recent_max_bytes limit in context.

    Args:
        max_bytes: Byte limit for recent tool output truncation.
    """
    current_recent_max_bytes.set(max_bytes)


# Context variable to store request-level passthrough headers for MCP
current_passthrough_headers: ContextVar[dict[str, str] | None] = ContextVar(
    "current_passthrough_headers",
    default=None,
)


def get_current_passthrough_headers() -> dict[str, str] | None:
    """Get current passthrough headers from context.

    These headers are extracted from x-header-* HTTP headers and
    will be merged into MCP client HTTP requests.

    Returns:
        Dictionary of headers to passthrough, or None if not set.
    """
    return current_passthrough_headers.get()


def set_current_passthrough_headers(headers: dict[str, str] | None) -> Token:
    """Set current passthrough headers in context.

    Args:
        headers: Dictionary of headers to passthrough to MCP servers.

    Returns:
        Token for resetting the context variable.
    """
    return current_passthrough_headers.set(headers)


def reset_current_passthrough_headers(token: Token) -> None:
    """Reset passthrough headers using token.

    Args:
        token: The token returned by set_current_passthrough_headers.
    """
    current_passthrough_headers.reset(token)


def resolve_effective_tenant_id(
    tenant_id: str,
    source_id: str | None,
) -> str:
    """Resolve the effective tenant ID considering source isolation.

    - Default tenant with source_id: effective = ``default_{source_id}``
    - Default tenant without source_id: effective = ``default``
    - Non-default tenant: effective = tenant_id (unchanged)

    Args:
        tenant_id: The original tenant ID from X-Tenant-Id header.
        source_id: The source ID from X-Source-Id header.

    Returns:
        The effective tenant ID to use for directory resolution.
    """
    if tenant_id == "default":
        if source_id:
            return f"default_{source_id}"
        return "default"
    return tenant_id
