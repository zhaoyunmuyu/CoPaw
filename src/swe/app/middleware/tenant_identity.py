# -*- coding: utf-8 -*-
"""Tenant identity middleware for multi-tenant isolation.

Parses and validates X-Tenant-Id and X-User-Id headers, enforces
tenant identity requirements on stateful routes, and binds tenant/user
context for the duration of the request.
"""
import logging
from typing import Callable, Awaitable

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from swe.config.context import (
    resolve_runtime_tenant_id,
    set_current_tenant_id,
    set_current_user_id,
    set_current_source_id,
    reset_current_tenant_id,
    reset_current_user_id,
    reset_current_source_id,
)

logger = logging.getLogger(__name__)

# Routes that are explicitly exempt from tenant identity requirements
# These are either truly stateless or system-level endpoints
TENANT_EXEMPT_ROUTES = frozenset(
    [
        # Health check endpoints
        "/health",
        "/healthz",
        "/api/health/health",
        "/ready",
        "/readyz",
        "/alive",
        # Version endpoint
        "/api/version",
        # OpenAPI docs (if enabled)
        "/docs",
        "/redoc",
        "/openapi.json",
        # Auth endpoints
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/api/auth/logout",
        "/api/zhaohu/callback",
        # Static assets
        "/assets",
        "/logo.png",
        "/dark-logo.png",
        "/swe-symbol.svg",
        "/swe-dark.png",
        # Console SPA routes (static files)
        "/console",
        "/console/",
    ],
)


def is_tenant_exempt(path: str) -> bool:
    """Check if a route is exempt from tenant identity requirements.

    Args:
        path: The request path to check.

    Returns:
        True if the route is exempt, False otherwise.
    """
    # Exact match
    if path in TENANT_EXEMPT_ROUTES:
        return True

    # Prefix match for certain routes
    exempt_prefixes = (
        "/assets/",
        "/static/",
        "/console/",
    )
    if any(path.startswith(prefix) for prefix in exempt_prefixes):
        return True

    return False


class TenantIdentityMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate tenant identity from headers.

        Reads X-Tenant-Id and X-User-Id headers, validates them, and binds
    the tenant/user context for the duration of the request. Stateful
        routes require a valid tenant ID; exempt routes skip validation.

        Middleware ordering: Should be placed early in the middleware stack,
        before TenantWorkspaceMiddleware and AgentContextMiddleware.
    """

    def __init__(
        self,
        app: ASGIApp,
        require_tenant: bool = True,
        default_tenant_id: str | None = None,
    ):
        """Initialize tenant identity middleware.

        Args:
            app: The ASGI application.
            require_tenant: If True, require tenant ID on non-exempt routes.
            default_tenant_id: Default tenant ID to use if not provided
                and require_tenant is False. Set to None to enforce strict
                tenant isolation with no fallback.
        """
        super().__init__(app)
        self._require_tenant = require_tenant
        self._default_tenant_id = default_tenant_id

    def _resolve_request_identity(
        self,
        request: Request,
    ) -> tuple[str | None, str | None, str | None, bool]:
        """Resolve tenant, user, and source IDs from request headers."""
        path = request.url.path
        is_exempt = request.method == "OPTIONS" or is_tenant_exempt(path)
        tenant_id = request.headers.get("X-Tenant-Id")
        user_id = request.headers.get("X-User-Id")
        source_id = request.headers.get("X-Source-Id")

        if not is_exempt:
            tenant_id = self._validate_tenant_id(path, tenant_id)

        return tenant_id, user_id, source_id, is_exempt

    def _validate_tenant_id(
        self,
        path: str,
        tenant_id: str | None,
    ) -> str | None:
        """Validate tenant ID for non-exempt routes."""
        if not tenant_id:
            if self._require_tenant:
                logger.warning(
                    f"Missing X-Tenant-Id header for {path}",
                )
                raise HTTPException(
                    status_code=400,
                    detail="X-Tenant-Id header is required",
                )
            return self._default_tenant_id

        if not self._is_valid_tenant_id(tenant_id):
            logger.warning(f"Invalid tenant ID format: {tenant_id}")
            raise HTTPException(
                status_code=400,
                detail="Invalid X-Tenant-Id format",
            )
        return tenant_id

    def _store_request_state(
        self,
        request: Request,
        tenant_id: str | None,
        user_id: str | None,
        source_id: str | None,
    ) -> None:
        """Store identity in request state for downstream use."""
        effective_tenant_id = resolve_runtime_tenant_id(tenant_id, source_id)
        if tenant_id:
            request.state.tenant_id = tenant_id
        if effective_tenant_id:
            request.state.effective_tenant_id = effective_tenant_id
        if user_id:
            request.state.user_id = user_id
        if source_id:
            request.state.source_id = source_id

    def _bind_context(
        self,
        tenant_id: str | None,
        user_id: str | None,
        source_id: str | None,
    ) -> list[tuple[str, object]]:
        """Bind identity to context variables, return tokens for reset."""
        tokens = []
        if tenant_id:
            tokens.append(("tenant", set_current_tenant_id(tenant_id)))
        if user_id:
            tokens.append(("user", set_current_user_id(user_id)))
        if source_id:
            tokens.append(("source", set_current_source_id(source_id)))
        return tokens

    def _reset_context(self, tokens: list[tuple[str, object]]) -> None:
        """Reset context variables using tokens."""
        reset_map = {
            "tenant": reset_current_tenant_id,
            "user": reset_current_user_id,
            "source": reset_current_source_id,
        }
        for name, token in reversed(tokens):
            if name in reset_map:
                reset_map[name](token)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Extract tenant identity and bind context.

        Args:
            request: The incoming request.
            call_next: The next middleware/endpoint to call.

        Returns:
            The response from the next handler.

        Raises:
            HTTPException: If tenant ID is required but missing/invalid.
        """
        tokens = []

        try:
            (
                tenant_id,
                user_id,
                source_id,
                is_exempt,
            ) = self._resolve_request_identity(request)

            self._store_request_state(request, tenant_id, user_id, source_id)
            tokens = self._bind_context(tenant_id, user_id, source_id)

            logger.debug(
                f"TenantIdentityMiddleware: tenant_id={tenant_id}, "
                f"user_id={user_id}, path={request.url.path}, exempt={is_exempt}",
            )

            response = await call_next(request)

            if tenant_id:
                response.headers["X-Tenant-Id-Resolved"] = tenant_id

            return response
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )
        finally:
            self._reset_context(tokens)

    def _is_valid_tenant_id(self, tenant_id: str) -> bool:
        """Validate tenant ID format.

        Args:
            tenant_id: The tenant ID to validate.

        Returns:
            True if valid, False otherwise.
        """
        if not tenant_id:
            return False

        # Basic validation: not empty, reasonable length, no path traversal
        if len(tenant_id) < 1 or len(tenant_id) > 256:
            return False

        # Disallow path traversal characters
        if ".." in tenant_id or "/" in tenant_id or "\\" in tenant_id:
            return False

        # Disallow control characters
        if any(ord(c) < 32 for c in tenant_id):
            return False

        return True


def get_tenant_id_from_request(request: Request) -> str | None:
    """Get tenant ID from request state.

    Args:
        request: The FastAPI request object.

    Returns:
        The tenant ID if set, None otherwise.
    """
    return getattr(request.state, "tenant_id", None)


def get_user_id_from_request(request: Request) -> str | None:
    """Get user ID from request state.

    Args:
        request: The FastAPI request object.

    Returns:
        The user ID if set, None otherwise.
    """
    return getattr(request.state, "user_id", None)


def require_tenant_id(request: Request) -> str:
    """Require tenant ID from request, raising if not set.

    Args:
        request: The FastAPI request object.

    Returns:
        The tenant ID.

    Raises:
        HTTPException: If tenant ID is not set in request state.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail="Tenant context not available",
        )
    return tenant_id


def require_user_id(request: Request) -> str:
    """Require user ID from request, raising if not set.

    Args:
        request: The FastAPI request object.

    Returns:
        The user ID.

    Raises:
        HTTPException: If user ID is not set in request state.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(
            status_code=400,
            detail="User context not available",
        )
    return user_id


def get_source_id_from_request(request: Request) -> str | None:
    """Get source ID from request state.

    Args:
        request: The FastAPI request object.

    Returns:
        The source ID if set, None otherwise.
    """
    return getattr(request.state, "source_id", None)


__all__ = [
    "TenantIdentityMiddleware",
    "is_tenant_exempt",
    "TENANT_EXEMPT_ROUTES",
    "get_tenant_id_from_request",
    "get_user_id_from_request",
    "require_tenant_id",
    "require_user_id",
    "get_source_id_from_request",
]
