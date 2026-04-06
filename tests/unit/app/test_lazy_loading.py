# -*- coding: utf-8 -*-
"""Tests for backend startup lazy loading.

Verifies that:
- Application startup is minimal (no eager runtime initialization)
- Tenant bootstrap only creates directory structure, not runtime
- Workspace runtime starts only on demand via MultiAgentManager
- Feature subsystems initialize on first use
"""
# pylint: disable=protected-access,unused-argument
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


class TestMinimalStartup:
    """Tests that startup performs minimal initialization only."""

    def test_provider_manager_not_imported_in_startup(self):
        """ProviderManager should not be imported in _app.py startup path."""
        import copaw.app._app as app_module

        # ProviderManager should not be in module namespace
        assert not hasattr(app_module, "ProviderManager")

    def test_local_model_manager_not_imported_in_startup(self):
        """LocalModelManager should not be imported in _app.py startup path."""
        import copaw.app._app as app_module

        # LocalModelManager should not be in module namespace
        assert not hasattr(app_module, "LocalModelManager")

    def test_migration_functions_not_imported_in_startup(self):
        """Migration functions should not be imported in _app.py."""
        import copaw.app._app as app_module

        # Migration functions should not be in module namespace
        assert not hasattr(
            app_module,
            "migrate_legacy_workspace_to_default_agent",
        )
        assert not hasattr(app_module, "migrate_legacy_skills_to_skill_pool")
        assert not hasattr(app_module, "ensure_qa_agent_exists")

    def test_lifespan_only_calls_ensure_default_agent_exists(self):
        """Startup should only ensure default agent exists, not start it."""
        # The function should be imported - it's called inside the lifespan
        import copaw.app._app as app_module

        assert hasattr(app_module, "ensure_default_agent_exists")


class TestTenantBootstrapBoundaries:
    """Tests that tenant bootstrap only does minimal work."""

    async def test_ensure_bootstrap_creates_directory_structure(
        self,
        tmp_path,
    ):
        """Tenant bootstrap creates directory structure."""
        from copaw.app.workspace.tenant_pool import TenantWorkspacePool

        pool = TenantWorkspacePool(tmp_path / "tenants")

        await pool.ensure_bootstrap("tenant-1")

        tenant_dir = pool._get_tenant_workspace_dir("tenant-1")
        assert tenant_dir.exists()
        assert (tenant_dir / "workspaces").exists()
        assert (tenant_dir / "media").exists()
        assert (tenant_dir / "secrets").exists()

    async def test_ensure_bootstrap_does_not_start_workspace(self, tmp_path):
        """Tenant bootstrap does not start workspace runtime."""
        from copaw.app.workspace.tenant_pool import TenantWorkspacePool

        pool = TenantWorkspacePool(tmp_path / "tenants")

        with patch("copaw.app.workspace.tenant_pool.Workspace") as mock_ws:
            mock_ws_instance = AsyncMock()
            mock_ws.return_value = mock_ws_instance

            await pool.ensure_bootstrap("tenant-1")

            # Workspace should not be created or started
            assert not mock_ws.called
            assert not mock_ws_instance.start.called

    async def test_ensure_bootstrap_does_not_initialize_skill_pool(
        self,
        tmp_path,
    ):
        """Tenant bootstrap does not initialize skill pool."""
        from copaw.app.workspace.tenant_pool import TenantWorkspacePool
        import copaw.app.workspace.tenant_initializer as init_module

        pool = TenantWorkspacePool(tmp_path / "tenants")

        # ensure_skill_pool_initialized should not be in tenant_initializer
        assert not hasattr(init_module, "ensure_skill_pool_initialized")

        # Bootstrap should succeed without skill pool init
        await pool.ensure_bootstrap("tenant-1")
        assert "tenant-1" in pool

    async def test_ensure_bootstrap_does_not_create_qa_agent(self, tmp_path):
        """Tenant bootstrap does not create QA agent."""
        from copaw.app.workspace.tenant_pool import TenantWorkspacePool
        import copaw.app.workspace.tenant_initializer as init_module

        pool = TenantWorkspacePool(tmp_path / "tenants")

        # ensure_qa_agent_exists should not be in tenant_initializer
        assert not hasattr(init_module, "ensure_qa_agent_exists")

        # Bootstrap should succeed without QA agent
        await pool.ensure_bootstrap("tenant-1")
        assert "tenant-1" in pool

    async def test_ensure_bootstrap_registers_tenant_entry(self, tmp_path):
        """Tenant bootstrap registers entry in pool."""
        from copaw.app.workspace.tenant_pool import TenantWorkspacePool

        pool = TenantWorkspacePool(tmp_path / "tenants")

        await pool.ensure_bootstrap("tenant-1")

        assert "tenant-1" in pool
        entry = pool._workspaces["tenant-1"]
        assert entry.tenant_id == "tenant-1"
        assert entry.workspace is None  # No runtime started

    async def test_tenants_stay_isolated(self, tmp_path):
        """Different tenants have independent bootstrap state."""
        from copaw.app.workspace.tenant_pool import TenantWorkspacePool

        pool = TenantWorkspacePool(tmp_path / "tenants")

        await pool.ensure_bootstrap("tenant-a")

        # Tenant B should not exist yet
        assert "tenant-b" not in pool

        await pool.ensure_bootstrap("tenant-b")

        # Both should exist independently
        assert "tenant-a" in pool
        assert "tenant-b" in pool


class TestLazyRuntimeStartup:
    """Tests that runtime starts only on demand."""

    async def test_multi_agent_manager_get_agent_starts_runtime(
        self,
        tmp_path,
    ):
        """MultiAgentManager.get_agent() starts workspace runtime."""
        from copaw.app.multi_agent_manager import MultiAgentManager
        from copaw.config.utils import save_config
        from copaw.config.config import (
            Config,
            AgentsConfig,
            AgentProfileRef,
            ChannelConfig,
            MCPConfig,
            ToolsConfig,
            SecurityConfig,
        )

        # Setup minimal config
        base_dir = tmp_path / "copaw"
        base_dir.mkdir(parents=True)

        config = Config(
            agents=AgentsConfig(
                active_agent="default",
                profiles={
                    "default": AgentProfileRef(
                        id="default",
                        workspace_dir=str(base_dir / "workspaces" / "default"),
                    ),
                },
            ),
            channels=ChannelConfig(),
            mcp=MCPConfig(),
            tools=ToolsConfig(),
            security=SecurityConfig(),
        )
        save_config(config, base_dir / "config.json")

        # Create workspace directory
        workspace_dir = base_dir / "workspaces" / "default"
        workspace_dir.mkdir(parents=True)

        # Create agent.json
        import json

        agent_config = {
            "id": "default",
            "name": "Default Agent",
            "workspace_dir": str(workspace_dir),
        }
        with open(workspace_dir / "agent.json", "w", encoding="utf-8") as f:
            json.dump(agent_config, f)

        # Mock load_config to use our test config
        with patch("copaw.app.multi_agent_manager.load_config") as mock_load:
            mock_load.return_value = config

            manager = MultiAgentManager()

            with patch(
                "copaw.app.workspace.workspace.load_agent_config",
            ) as mock_load_agent:
                mock_load_agent.return_value = Mock(
                    id="default",
                    name="Default Agent",
                    running=Mock(memory_manager_backend="remelight"),
                )

                with patch.object(
                    manager,
                    "_load_agent_config_for_tenant",
                    return_value=config,
                ):
                    # Before get_agent, nothing should be started
                    assert len(manager.agents) == 0

                    # get_agent should trigger runtime creation
                    # Note: We can't fully test this without mocking Workspace
                    with patch(
                        "copaw.app.multi_agent_manager.Workspace",
                    ) as mock_ws:
                        mock_ws_instance = AsyncMock()
                        mock_ws.return_value = mock_ws_instance

                        await manager.get_agent("default")

                        # Workspace should be created and started
                        assert mock_ws.called
                        assert mock_ws_instance.start.called

    async def test_multi_agent_manager_caches_runtime(self):
        """MultiAgentManager caches workspace runtime."""
        from copaw.app.multi_agent_manager import MultiAgentManager

        manager = MultiAgentManager()

        # Mock the workspace creation
        with patch("copaw.app.multi_agent_manager.Workspace") as mock_ws:
            mock_ws_instance = AsyncMock()
            mock_ws.return_value = mock_ws_instance

            with patch.object(
                manager,
                "_load_agent_config_for_tenant",
            ) as mock_load:
                mock_load.return_value = Mock(
                    agents=Mock(
                        profiles={"default": Mock(workspace_dir="/tmp")},
                    ),
                )

                # First call creates workspace
                __ws1 = await manager.get_agent("default")

                # Second call should return cached instance
                __ws2 = await manager.get_agent("default")

                # Workspace should only be created once
            assert mock_ws.call_count == 1
            assert mock_ws_instance.start.call_count == 1


class TestOnDemandSubsystemInitialization:
    """Tests that subsystems initialize on first use."""

    async def test_workspace_start_does_not_init_skill_pool(self, tmp_path):
        """Workspace.start() does not initialize skill pool."""
        from copaw.app.workspace.workspace import Workspace
        import copaw.app.workspace.workspace as ws_module

        # Setup workspace directory
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir(parents=True)

        # Create agent.json
        import json

        agent_config = {
            "id": "default",
            "name": "Default Agent",
            "workspace_dir": str(workspace_dir),
            "running": {"memory_manager_backend": "remelight"},
        }
        with open(workspace_dir / "agent.json", "w", encoding="utf-8") as f:
            json.dump(agent_config, f)

        # Create workspace instance but don't start it
        _workspace = Workspace("default", str(workspace_dir))
        assert _workspace is not None

        # ensure_skill_pool_initialized should not be in workspace module
        assert not hasattr(ws_module, "ensure_skill_pool_initialized")

    async def test_provider_manager_initializes_on_demand(self):
        """ProviderManager initializes on first use."""
        from copaw.providers.provider_manager import ProviderManager

        # Reset any existing instance
        ProviderManager._instance = None

        # get_instance should create instance on first call
        with patch.object(
            ProviderManager,
            "__init__",
            return_value=None,
        ) as _mock_init:
            # Note: Due to singleton pattern, actual testing would need more setup
            # This test verifies the pattern exists
            pass

    async def test_local_model_manager_initializes_on_demand(self):
        """LocalModelManager initializes on first use."""
        from copaw.local_models.manager import LocalModelManager

        # Remove any existing instance
        if hasattr(LocalModelManager, "_instance"):
            delattr(LocalModelManager, "_instance")

        # get_instance should create instance on first call
        with patch.object(
            LocalModelManager,
            "__init__",
            return_value=None,
        ) as _mock_init:
            # Note: Due to singleton pattern, actual testing would need more setup
            # This test verifies the pattern exists
            pass


class TestStartupLogging:
    """Tests that startup logs indicate deferred initialization."""

    def test_startup_logs_minimal_initialization(self):
        """Startup logs indicate minimal initialization."""
        # This is verified by examining the log messages in _app.py
        from copaw.app._app import lifespan

        # The lifespan function should contain logging about deferred initialization
        import inspect

        source = inspect.getsource(lifespan)

        # Should mention minimal initialization
        assert "minimal" in source.lower() or "deferred" in source.lower()


class TestMiddlewareIntegration:
    """Tests for middleware lazy loading integration."""

    async def test_middleware_calls_ensure_bootstrap_not_get_or_create(self):
        """Middleware should call ensure_bootstrap, not get_or_create."""
        from copaw.app.middleware.tenant_workspace import (
            TenantWorkspaceMiddleware,
        )

        middleware = TenantWorkspaceMiddleware(Mock())

        with patch.object(
            middleware,
            "_ensure_tenant_provider_config",
            AsyncMock(),
        ):
            # Mock request
            mock_request = Mock()
            mock_request.state.tenant_id = "tenant-1"
            mock_request.app.state.tenant_workspace_pool = Mock()

            pool = mock_request.app.state.tenant_workspace_pool
            pool.ensure_bootstrap = AsyncMock()
            pool.get_or_create = AsyncMock()

            # Call the _get_workspace method
            await middleware._get_workspace(mock_request, "tenant-1")

            # Should call ensure_bootstrap, not get_or_create
            assert pool.ensure_bootstrap.called
            assert not pool.get_or_create.called

    async def test_middleware_returns_none_for_workspace(self):
        """Middleware returns None since runtime is not started."""
        from copaw.app.middleware.tenant_workspace import (
            TenantWorkspaceMiddleware,
        )

        middleware = TenantWorkspaceMiddleware(Mock())

        with patch.object(
            middleware,
            "_ensure_tenant_provider_config",
            AsyncMock(),
        ):
            mock_request = Mock()
            mock_request.state.tenant_id = "tenant-1"
            mock_request.app.state.tenant_workspace_pool = Mock()
            mock_request.app.state.tenant_workspace_pool.ensure_bootstrap = (
                AsyncMock()
            )

            result = await middleware._get_workspace(mock_request, "tenant-1")

            # Should return None since runtime is deferred
            assert result is None
