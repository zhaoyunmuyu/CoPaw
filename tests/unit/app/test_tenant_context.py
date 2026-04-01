# -*- coding: utf-8 -*-
"""Unit tests for tenant context primitives.

Tests set/get/reset behavior for tenant, user, and workspace contextvars,
as well as the strict helpers that raise when context is missing.
"""
import sys
from pathlib import Path

# Add src to path for direct imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from copaw.config.context import (
    current_tenant_id,
    current_user_id,
    current_workspace_dir,
    get_current_tenant_id,
    get_current_user_id,
    get_current_workspace_dir,
    set_current_tenant_id,
    set_current_user_id,
    set_current_workspace_dir,
    reset_current_tenant_id,
    reset_current_user_id,
    reset_current_workspace_dir,
    get_current_tenant_id_strict,
    get_current_user_id_strict,
    get_current_workspace_dir_strict,
    tenant_context,
    TenantContextError,
)
from copaw.app.tenant_context import (
    bind_tenant_context,
    get_tenant_context,
    require_tenant_context,
    require_full_context,
    TenantContextError,
)


class TestTenantIdContext:
    """Tests for tenant_id context variable."""

    def test_get_returns_none_when_not_set(self):
        """get_current_tenant_id returns None when not set."""
        # Ensure clean state
        assert get_current_tenant_id() is None

    def test_set_and_get(self):
        """Setting tenant_id makes it retrievable."""
        token = set_current_tenant_id("tenant-123")
        try:
            assert get_current_tenant_id() == "tenant-123"
        finally:
            reset_current_tenant_id(token)

    def test_reset_restores_previous_value(self):
        """Resetting restores the previous context value."""
        # Set initial value
        token1 = set_current_tenant_id("tenant-1")
        try:
            assert get_current_tenant_id() == "tenant-1"

            # Set new value
            token2 = set_current_tenant_id("tenant-2")
            try:
                assert get_current_tenant_id() == "tenant-2"
            finally:
                reset_current_tenant_id(token2)

            # After reset, should be back to tenant-1
            assert get_current_tenant_id() == "tenant-1"
        finally:
            reset_current_tenant_id(token1)

    def test_reset_to_none(self):
        """Resetting when no prior value sets back to None."""
        token = set_current_tenant_id("tenant-123")
        reset_current_tenant_id(token)
        assert get_current_tenant_id() is None


class TestUserIdContext:
    """Tests for user_id context variable."""

    def test_get_returns_none_when_not_set(self):
        """get_current_user_id returns None when not set."""
        assert get_current_user_id() is None

    def test_set_and_get(self):
        """Setting user_id makes it retrievable."""
        token = set_current_user_id("user-456")
        try:
            assert get_current_user_id() == "user-456"
        finally:
            reset_current_user_id(token)

    def test_reset_restores_previous_value(self):
        """Resetting restores the previous context value."""
        token1 = set_current_user_id("user-1")
        try:
            assert get_current_user_id() == "user-1"

            token2 = set_current_user_id("user-2")
            try:
                assert get_current_user_id() == "user-2"
            finally:
                reset_current_user_id(token2)

            assert get_current_user_id() == "user-1"
        finally:
            reset_current_user_id(token1)


class TestWorkspaceDirContext:
    """Tests for workspace_dir context variable."""

    def test_get_returns_none_when_not_set(self):
        """get_current_workspace_dir returns None when not set."""
        assert get_current_workspace_dir() is None

    def test_set_and_get(self):
        """Setting workspace_dir makes it retrievable."""
        path = Path("/tmp/workspace")
        token = set_current_workspace_dir(path)
        try:
            assert get_current_workspace_dir() == path
        finally:
            reset_current_workspace_dir(token)

    def test_reset_restores_previous_value(self):
        """Resetting restores the previous context value."""
        path1 = Path("/tmp/workspace1")
        path2 = Path("/tmp/workspace2")

        token1 = set_current_workspace_dir(path1)
        try:
            assert get_current_workspace_dir() == path1

            token2 = set_current_workspace_dir(path2)
            try:
                assert get_current_workspace_dir() == path2
            finally:
                reset_current_workspace_dir(token2)

            assert get_current_workspace_dir() == path1
        finally:
            reset_current_workspace_dir(token1)


class TestStrictHelpers:
    """Tests for strict helpers that raise when context is missing."""

    def test_get_current_tenant_id_strict_raises_when_not_set(self):
        """Strict helper raises TenantContextError when tenant_id not set."""
        with pytest.raises(TenantContextError) as exc_info:
            get_current_tenant_id_strict()
        assert "Tenant ID is not set" in str(exc_info.value)

    def test_get_current_tenant_id_strict_returns_value_when_set(self):
        """Strict helper returns value when tenant_id is set."""
        token = set_current_tenant_id("tenant-abc")
        try:
            assert get_current_tenant_id_strict() == "tenant-abc"
        finally:
            reset_current_tenant_id(token)

    def test_get_current_user_id_strict_raises_when_not_set(self):
        """Strict helper raises TenantContextError when user_id not set."""
        with pytest.raises(TenantContextError) as exc_info:
            get_current_user_id_strict()
        assert "User ID is not set" in str(exc_info.value)

    def test_get_current_user_id_strict_returns_value_when_set(self):
        """Strict helper returns value when user_id is set."""
        token = set_current_user_id("user-xyz")
        try:
            assert get_current_user_id_strict() == "user-xyz"
        finally:
            reset_current_user_id(token)

    def test_get_current_workspace_dir_strict_raises_when_not_set(self):
        """Strict helper raises TenantContextError when workspace_dir not set."""
        with pytest.raises(TenantContextError) as exc_info:
            get_current_workspace_dir_strict()
        assert "Workspace directory is not set" in str(exc_info.value)

    def test_get_current_workspace_dir_strict_returns_value_when_set(self):
        """Strict helper returns value when workspace_dir is set."""
        path = Path("/tmp/workspace")
        token = set_current_workspace_dir(path)
        try:
            assert get_current_workspace_dir_strict() == path
        finally:
            reset_current_workspace_dir(token)


class TestTenantContextManager:
    """Tests for tenant_context context manager."""

    def test_sets_all_context_values(self):
        """Context manager sets all provided values."""
        with tenant_context(
            tenant_id="tenant-1",
            user_id="user-1",
            workspace_dir=Path("/tmp/ws"),
        ):
            assert get_current_tenant_id() == "tenant-1"
            assert get_current_user_id() == "user-1"
            assert get_current_workspace_dir() == Path("/tmp/ws")

    def test_resets_context_on_exit(self):
        """Context manager resets values on exit."""
        with tenant_context(
            tenant_id="tenant-1",
            user_id="user-1",
            workspace_dir=Path("/tmp/ws"),
        ):
            pass  # Context set here

        # After exit, all should be None
        assert get_current_tenant_id() is None
        assert get_current_user_id() is None
        assert get_current_workspace_dir() is None

    def test_restores_previous_values(self):
        """Context manager restores previous values on exit."""
        # Set initial values
        t_token = set_current_tenant_id("original-tenant")
        u_token = set_current_user_id("original-user")
        w_token = set_current_workspace_dir(Path("/original"))

        try:
            with tenant_context(
                tenant_id="new-tenant",
                user_id="new-user",
                workspace_dir=Path("/new"),
            ):
                # Inside context, new values
                assert get_current_tenant_id() == "new-tenant"
                assert get_current_user_id() == "new-user"
                assert get_current_workspace_dir() == Path("/new")

            # After exit, original values restored
            assert get_current_tenant_id() == "original-tenant"
            assert get_current_user_id() == "original-user"
            assert get_current_workspace_dir() == Path("/original")
        finally:
            reset_current_tenant_id(t_token)
            reset_current_user_id(u_token)
            reset_current_workspace_dir(w_token)

    def test_handles_exception_and_resets(self):
        """Context manager resets even when exception occurs."""
        with pytest.raises(ValueError):
            with tenant_context(
                tenant_id="tenant-1",
                user_id="user-1",
                workspace_dir=Path("/tmp/ws"),
            ):
                assert get_current_tenant_id() == "tenant-1"
                raise ValueError("Test exception")

        # After exception, should be reset
        assert get_current_tenant_id() is None
        assert get_current_user_id() is None
        assert get_current_workspace_dir() is None

    def test_partial_context(self):
        """Context manager works with partial context."""
        with tenant_context(tenant_id="tenant-only"):
            assert get_current_tenant_id() == "tenant-only"
            assert get_current_user_id() is None
            assert get_current_workspace_dir() is None


class TestBindTenantContext:
    """Tests for bind_tenant_context (app-level)."""

    def test_sets_all_context_values(self):
        """bind_tenant_context sets all provided values."""
        with bind_tenant_context(
            tenant_id="tenant-1",
            user_id="user-1",
            workspace_dir=Path("/tmp/ws"),
        ):
            assert get_current_tenant_id() == "tenant-1"
            assert get_current_user_id() == "user-1"
            assert get_current_workspace_dir() == Path("/tmp/ws")

    def test_resets_context_on_exit(self):
        """bind_tenant_context resets values on exit."""
        with bind_tenant_context(
            tenant_id="tenant-1",
            user_id="user-1",
            workspace_dir=Path("/tmp/ws"),
        ):
            pass

        assert get_current_tenant_id() is None
        assert get_current_user_id() is None
        assert get_current_workspace_dir() is None


class TestGetTenantContext:
    """Tests for get_tenant_context helper."""

    def test_returns_all_none_when_not_set(self):
        """Returns all None when no context is set."""
        ctx = get_tenant_context()
        assert ctx["tenant_id"] is None
        assert ctx["user_id"] is None
        assert ctx["workspace_dir"] is None

    def test_returns_set_values(self):
        """Returns all set values."""
        with tenant_context(
            tenant_id="tenant-1",
            user_id="user-1",
            workspace_dir=Path("/tmp/ws"),
        ):
            ctx = get_tenant_context()
            assert ctx["tenant_id"] == "tenant-1"
            assert ctx["user_id"] == "user-1"
            assert ctx["workspace_dir"] == Path("/tmp/ws")


class TestRequireTenantContext:
    """Tests for require_tenant_context helper."""

    def test_raises_when_tenant_id_not_set(self):
        """Raises when tenant_id is not set."""
        with pytest.raises(TenantContextError):
            require_tenant_context()

    def test_raises_when_workspace_not_set(self):
        """Raises when workspace_dir is not set."""
        with tenant_context(tenant_id="tenant-1"):
            with pytest.raises(TenantContextError):
                require_tenant_context()

    def test_returns_values_when_set(self):
        """Returns tuple when both are set."""
        with tenant_context(
            tenant_id="tenant-1",
            workspace_dir=Path("/tmp/ws"),
        ):
            tenant_id, workspace_dir = require_tenant_context()
            assert tenant_id == "tenant-1"
            assert workspace_dir == Path("/tmp/ws")


class TestRequireFullContext:
    """Tests for require_full_context helper."""

    def test_raises_when_any_missing(self):
        """Raises when any context is missing."""
        with tenant_context(tenant_id="tenant-1"):
            with pytest.raises(TenantContextError):
                require_full_context()

    def test_returns_values_when_all_set(self):
        """Returns tuple when all are set."""
        with tenant_context(
            tenant_id="tenant-1",
            user_id="user-1",
            workspace_dir=Path("/tmp/ws"),
        ):
            tenant_id, user_id, workspace_dir = require_full_context()
            assert tenant_id == "tenant-1"
            assert user_id == "user-1"
            assert workspace_dir == Path("/tmp/ws")
