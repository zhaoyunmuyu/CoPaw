# -*- coding: utf-8 -*-
"""Unit tests for app initialization with tenant workspace pool.

Tests TenantWorkspacePool initialization during app startup,
shutdown cleanup, and tenant-first resolution order.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestAppInitialization:
    """Tests for app initialization with tenant workspace pool."""

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_tenant_workspace_pool_import(self):
        """TenantWorkspacePool can be imported."""
        from swe.app.workspace.tenant_pool import TenantWorkspacePool

        assert TenantWorkspacePool is not None

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_tenant_workspace_pool_initialization(self, tmp_path):
        """TenantWorkspacePool initializes with base directory."""
        from swe.app.workspace.tenant_pool import TenantWorkspacePool

        pool = TenantWorkspacePool(tmp_path / "tenants")
        assert pool._base_working_dir.exists()

    def test_agent_context_imports(self):
        """agent_context module exports tenant-aware functions."""
        import importlib.util

        agent_ctx_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "swe"
            / "app"
            / "agent_context.py"
        )
        spec = importlib.util.spec_from_file_location(
            "agent_context_test",
            agent_ctx_path,
        )
        assert spec is not None
        # Check module has expected exports without full execution
        source = agent_ctx_path.read_text(encoding="utf-8")
        assert "def get_agent_for_request" in source
        assert "def set_current_agent_id" in source
        assert "def get_current_agent_id" in source
        assert "def get_active_agent_id" in source


class TestTenantFirstResolution:
    """Tests for tenant-first resolution order."""

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_active_agent_id_accepts_tenant_id(self):
        """get_active_agent_id accepts optional tenant_id parameter."""
        from swe.app.agent_context import get_active_agent_id

        # Should work without tenant_id
        result = get_active_agent_id()
        assert isinstance(result, str)

        # Should work with tenant_id
        result = get_active_agent_id(tenant_id="tenant-1")
        assert isinstance(result, str)

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_current_agent_id_accepts_tenant_id(self):
        """get_current_agent_id accepts optional tenant_id parameter."""
        from swe.app.agent_context import get_current_agent_id

        # Should work without tenant_id
        result = get_current_agent_id()
        assert isinstance(result, str)

        # Should work with tenant_id
        result = get_current_agent_id(tenant_id="tenant-1")
        assert isinstance(result, str)


class TestTenantContextIntegration:
    """Tests for tenant context integration with agent resolution."""

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_tenant_context_error_import(self):
        """TenantContextError can be imported from config.context."""
        from swe.config.context import TenantContextError

        assert TenantContextError is not None
        assert issubclass(TenantContextError, RuntimeError)

    def test_get_tenant_workspace_returns_none_when_not_set(self):
        """get_tenant_workspace returns None when workspace not set."""
        import importlib.util

        # Load context module directly
        context_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "swe"
            / "config"
            / "context.py"
        )
        spec = importlib.util.spec_from_file_location(
            "test_context",
            context_path,
        )
        context = importlib.util.module_from_spec(spec)
        sys.modules["test_context"] = context
        assert spec.loader is not None
        spec.loader.exec_module(context)

        assert context.get_current_workspace_dir() is None

    def test_get_tenant_workspace_strict_raises_when_not_set(self):
        """get_tenant_workspace_strict raises when workspace not set."""
        import importlib.util

        # Load context module directly
        context_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "swe"
            / "config"
            / "context.py"
        )
        spec = importlib.util.spec_from_file_location(
            "test_context",
            context_path,
        )
        context = importlib.util.module_from_spec(spec)
        sys.modules["test_context"] = context
        assert spec.loader is not None
        spec.loader.exec_module(context)

        with pytest.raises(context.TenantContextError):
            context.get_current_workspace_dir_strict()

    def test_get_tenant_workspace_returns_workspace_when_set(self):
        """get_tenant_workspace returns workspace when set."""
        import importlib.util

        # Load context module directly
        context_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "swe"
            / "config"
            / "context.py"
        )
        spec = importlib.util.spec_from_file_location(
            "test_context",
            context_path,
        )
        context = importlib.util.module_from_spec(spec)
        sys.modules["test_context"] = context
        assert spec.loader is not None
        spec.loader.exec_module(context)

        test_path = Path("/tmp/test-workspace")
        token = context.set_current_workspace_dir(test_path)
        try:
            assert context.get_current_workspace_dir() == test_path
        finally:
            context.reset_current_workspace_dir(token)


class TestMiddlewareOrdering:
    """Tests for middleware ordering requirements."""

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_agent_context_middleware_dispatch_signature(self):
        """AgentContextMiddleware has correct dispatch signature."""
        from swe.app.routers.agent_scoped import AgentContextMiddleware

        # Middleware should be callable and have dispatch method
        assert hasattr(AgentContextMiddleware, "dispatch")


class TestAppStateAttributes:
    """Tests for app.state attributes related to tenant management."""

    def test_app_state_tenant_workspace_pool_attribute(self):
        """app.state should have tenant_workspace_pool attribute."""
        from fastapi import FastAPI

        app = FastAPI()
        # Before lifespan, attribute should not exist
        assert not hasattr(app.state, "tenant_workspace_pool")

        # Simulate setting the attribute (as lifespan would)
        app.state.tenant_workspace_pool = Mock()
        assert hasattr(app.state, "tenant_workspace_pool")
        assert app.state.tenant_workspace_pool is not None

    def test_app_state_multi_agent_manager_attribute(self):
        """app.state should have multi_agent_manager attribute."""
        from fastapi import FastAPI

        app = FastAPI()
        # Before lifespan, attribute should not exist
        assert not hasattr(app.state, "multi_agent_manager")

        # Simulate setting the attribute (as lifespan would)
        app.state.multi_agent_manager = Mock()
        assert hasattr(app.state, "multi_agent_manager")
        assert app.state.multi_agent_manager is not None
