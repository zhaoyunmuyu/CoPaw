# -*- coding: utf-8 -*-
"""Unit tests for tenant init source isolation.

Tests source-based template selection, mapping store, middleware source
extraction, and ProviderManager source-aware initialization.
"""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

# pylint: disable=wrong-import-position
import pytest  # noqa: E402
from swe.app.workspace.tenant_initializer import (  # noqa: E402
    TenantInitializer,
)
from swe.app.workspace.tenant_init_source_store import (  # noqa: E402
    TenantInitSourceStore,
    init_tenant_init_source_module,
    get_tenant_init_source_store,
)
from swe.config.context import (  # noqa: E402
    set_current_source_id,
    get_current_source_id,
    reset_current_source_id,
)
from swe.config.config import (  # noqa: E402
    Config,
    AgentsConfig,
    AgentProfileRef,
    SecurityConfig,
    ToolGuardConfig,
    ToolsConfig,
)
from swe.config.utils import save_config  # noqa: E402

# pylint: enable=wrong-import-position


# ==================== TenantInitializer source_id tests ====================


class TestTenantInitializerSourceId:
    """Tests for TenantInitializer source_id and template selection."""

    def test_non_default_without_source_uses_default_template(self, tmp_path):
        """Non-default tenant without source_id uses 'default' template."""
        initializer = TenantInitializer(tmp_path, "tenant-1")
        assert initializer.template_name == "default"
        assert initializer.source_id is None
        assert initializer.effective_tenant_id == "tenant-1"

    def test_default_without_source_raises_error(self, tmp_path):
        """Default tenant without source_id raises TenantContextError."""
        from swe.config.context import TenantContextError

        with pytest.raises(TenantContextError):
            TenantInitializer(tmp_path, "default", source_id=None)

    def test_source_id_selects_matching_template(self, tmp_path):
        """With source_id, template_name is 'default_{source_id}' if exists."""
        template_dir = tmp_path / "default_ruice"
        template_dir.mkdir()
        (template_dir / "config.json").write_text("{}", encoding="utf-8")

        initializer = TenantInitializer(
            tmp_path,
            "tenant-1",
            source_id="ruice",
        )
        assert initializer.template_name == "default_ruice"
        # Non-default tenant: effective_tenant_id is unchanged
        assert initializer.effective_tenant_id == "tenant-1"

    def test_default_user_with_source_uses_source_directory(self, tmp_path):
        """Default user with source_id accesses default_{source_id} directory."""
        default_dir = tmp_path / "default"
        default_dir.mkdir()
        (default_dir / "config.json").write_text(
            '{"agents": {}}',
            encoding="utf-8",
        )

        initializer = TenantInitializer(
            tmp_path,
            "default",
            source_id="ruice",
        )
        # Template is created from default
        assert initializer.template_name == "default_ruice"
        # Effective tenant ID is also default_ruice
        assert initializer.effective_tenant_id == "default_ruice"
        # Tenant dir points to source-specific directory
        assert initializer.tenant_dir == tmp_path / "default_ruice"

    def test_non_default_user_with_source_keeps_own_directory(self, tmp_path):
        """Non-default user with source_id still uses their own directory."""
        default_dir = tmp_path / "default"
        default_dir.mkdir()
        (default_dir / "config.json").write_text("{}", encoding="utf-8")

        initializer = TenantInitializer(
            tmp_path,
            "user-001",
            source_id="ruice",
        )
        # Template is created from default
        assert initializer.template_name == "default_ruice"
        # Effective tenant ID remains as user-001
        assert initializer.effective_tenant_id == "user-001"
        # Tenant dir points to user's own directory
        assert initializer.tenant_dir == tmp_path / "user-001"

    def test_source_id_creates_template_from_default_when_missing(
        self,
        tmp_path,
    ):
        """With source_id but no matching template dir, creates from default."""
        # Setup default template
        default_dir = tmp_path / "default"
        default_dir.mkdir()
        (default_dir / "config.json").write_text(
            '{"test": true}',
            encoding="utf-8",
        )

        initializer = TenantInitializer(
            tmp_path,
            "tenant-1",
            source_id="unknown",
        )
        # Should create default_unknown from default
        assert initializer.template_name == "default_unknown"
        assert (tmp_path / "default_unknown").exists()
        assert (tmp_path / "default_unknown" / "config.json").exists()

    def test_source_id_falls_back_to_default_when_no_default_exists(
        self,
        tmp_path,
    ):
        """With source_id and no default template, falls back to 'default'."""
        initializer = TenantInitializer(
            tmp_path,
            "tenant-1",
            source_id="unknown",
        )
        # No default to copy from, so fallback
        assert initializer.template_name == "default"

    def test_empty_source_id_uses_default(self, tmp_path):
        """Empty string source_id is treated as no source_id."""
        initializer = TenantInitializer(tmp_path, "tenant-1", source_id="")
        assert initializer.template_name == "default"

    def test_seeded_bootstrap_uses_source_template_config(self, tmp_path):
        """Config is seeded from the source-specific template directory."""
        # Setup default_ruice template
        ruice_dir = tmp_path / "default_ruice"
        ruice_workspace = ruice_dir / "workspaces" / "default"
        ruice_workspace.mkdir(parents=True)

        ruice_config = Config(
            agents=AgentsConfig(
                active_agent="default",
                profiles={
                    "default": AgentProfileRef(
                        id="default",
                        workspace_dir=str(ruice_workspace),
                    ),
                },
                language="zh",
            ),
            security=SecurityConfig(
                tool_guard=ToolGuardConfig(enabled=True),
            ),
        )
        save_config(ruice_config, ruice_dir / "config.json")

        agent_payload = {
            "id": "default",
            "name": "Ruice Agent",
            "description": "ruice template agent",
            "workspace_dir": str(ruice_workspace),
            "language": "zh",
        }
        (ruice_workspace / "agent.json").write_text(
            json.dumps(agent_payload),
            encoding="utf-8",
        )
        for filename in (
            "AGENTS.md",
            "HEARTBEAT.md",
            "MEMORY.md",
            "PROFILE.md",
            "SOUL.md",
        ):
            (ruice_workspace / filename).write_text(
                f"# {filename} ruice\n",
                encoding="utf-8",
            )

        # Initialize new tenant with source_id
        new_init = TenantInitializer(
            tmp_path,
            "tenant-ruice-user",
            source_id="ruice",
        )
        new_init.ensure_seeded_bootstrap()

        # Verify config was seeded from ruice template
        tenant_dir = tmp_path / "tenant-ruice-user"
        config_data = json.loads(
            (tenant_dir / "config.json").read_text(encoding="utf-8"),
        )
        assert config_data["security"]["tool_guard"]["enabled"] is True
        assert config_data["agents"]["language"] == "zh"

    def test_seeded_bootstrap_uses_source_template(self, tmp_path):
        """With source_id, config is seeded from source template for default tenant."""
        # Setup default template (as source template base)
        default_dir = tmp_path / "default"
        default_workspace = default_dir / "workspaces" / "default"
        default_workspace.mkdir(parents=True)

        default_config = Config(
            agents=AgentsConfig(
                active_agent="default",
                profiles={
                    "default": AgentProfileRef(
                        id="default",
                        workspace_dir=str(default_workspace),
                    ),
                },
                language="en",
            ),
            security=SecurityConfig(
                tool_guard=ToolGuardConfig(enabled=False),
            ),
        )
        save_config(default_config, default_dir / "config.json")

        (default_workspace / "agent.json").write_text(
            json.dumps(
                {
                    "id": "default",
                    "name": "Default Agent",
                    "workspace_dir": str(default_workspace),
                },
            ),
            encoding="utf-8",
        )
        for filename in (
            "AGENTS.md",
            "HEARTBEAT.md",
            "MEMORY.md",
            "PROFILE.md",
            "SOUL.md",
        ):
            (default_workspace / filename).write_text(
                f"# {filename}\n",
                encoding="utf-8",
            )

        # Initialize default tenant with source_id (creates default_ruice)
        new_init = TenantInitializer(tmp_path, "default", source_id="ruice")
        new_init.ensure_seeded_bootstrap()

        tenant_dir = tmp_path / "default_ruice"
        config_data = json.loads(
            (tenant_dir / "config.json").read_text(encoding="utf-8"),
        )
        assert config_data["security"]["tool_guard"]["enabled"] is False

    def test_config_workspace_dir_replacement_with_source_template(
        self,
        tmp_path,
    ):
        """Workspace paths in config are replaced from template to tenant."""
        ruice_dir = tmp_path / "default_ruice"
        ruice_workspace = ruice_dir / "workspaces" / "default"
        ruice_workspace.mkdir(parents=True)

        ruice_config = Config(
            agents=AgentsConfig(
                active_agent="default",
                profiles={
                    "default": AgentProfileRef(
                        id="default",
                        workspace_dir=str(ruice_workspace),
                    ),
                },
            ),
            tools=ToolsConfig(),
            security=SecurityConfig(
                tool_guard=ToolGuardConfig(enabled=False),
            ),
        )
        save_config(ruice_config, ruice_dir / "config.json")

        (ruice_workspace / "agent.json").write_text(
            json.dumps(
                {
                    "id": "default",
                    "name": "Ruice Agent",
                    "workspace_dir": str(ruice_workspace),
                },
            ),
            encoding="utf-8",
        )
        for filename in (
            "AGENTS.md",
            "HEARTBEAT.md",
            "MEMORY.md",
            "PROFILE.md",
            "SOUL.md",
        ):
            (ruice_workspace / filename).write_text(
                f"# {filename}\n",
                encoding="utf-8",
            )

        new_init = TenantInitializer(
            tmp_path,
            "user-001",
            source_id="ruice",
        )
        new_init.ensure_seeded_bootstrap()

        tenant_dir = tmp_path / "user-001"
        config_data = json.loads(
            (tenant_dir / "config.json").read_text(encoding="utf-8"),
        )
        actual_workspace = config_data["agents"]["profiles"]["default"][
            "workspace_dir"
        ]
        assert "default_ruice" not in actual_workspace
        assert "user-001" in actual_workspace


# ==================== TenantInitSourceStore tests ====================


class TestTenantInitSourceStore:
    """Tests for the tenant init source mapping store."""

    # pylint: disable=protected-access

    def test_store_without_db(self):
        """Store operates in stub mode without database."""
        store = TenantInitSourceStore(db=None)
        assert store._use_db is False

    def test_store_with_disconnected_db(self):
        """Store detects disconnected database."""
        mock_db = MagicMock()
        mock_db.is_connected = False
        store = TenantInitSourceStore(db=mock_db)
        assert store._use_db is False

    def test_store_with_connected_db(self):
        """Store uses database when connected."""
        mock_db = MagicMock()
        mock_db.is_connected = True
        store = TenantInitSourceStore(db=mock_db)
        assert store._use_db is True

    @pytest.mark.asyncio
    async def test_get_init_source_returns_none_without_db(self):
        """get_init_source returns None when no database."""
        store = TenantInitSourceStore(db=None)
        result = await store.get_init_source("tenant-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_returns_init_source_without_db(self):
        """get_or_create returns init_source without persisting when no db."""
        store = TenantInitSourceStore(db=None)
        result = await store.get_or_create(
            tenant_id="tenant-1",
            source_id="ruice",
            init_source="default_ruice",
        )
        assert result == "default_ruice"

    @pytest.mark.asyncio
    async def test_get_or_create_inserts_new_record(self):
        """get_or_create inserts a new record when tenant has no mapping."""
        mock_db = MagicMock()
        mock_db.is_connected = True
        mock_db.fetch_one = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock()

        store = TenantInitSourceStore(db=mock_db)
        result = await store.get_or_create(
            tenant_id="tenant-1",
            source_id="ruice",
            init_source="default_ruice",
        )

        assert result == "default_ruice"
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing(self):
        """get_or_create returns existing init_source without inserting."""
        mock_db = MagicMock()
        mock_db.is_connected = True
        mock_db.fetch_one = AsyncMock(
            return_value={"init_source": "default_ruice"},
        )
        mock_db.execute = AsyncMock()

        store = TenantInitSourceStore(db=mock_db)
        result = await store.get_or_create(
            tenant_id="tenant-1",
            source_id="ruice",
            init_source="default_ruice",
        )

        assert result == "default_ruice"
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_source_returns_empty_without_db(self):
        """get_by_source returns empty list when no database."""
        store = TenantInitSourceStore(db=None)
        result = await store.get_by_source("ruice")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_returns_empty_without_db(self):
        """get_all returns empty when no database."""
        store = TenantInitSourceStore(db=None)
        records, total = await store.get_all()
        assert records == []
        assert total == 0


# ==================== Global store initialization tests ====================


class TestTenantInitSourceModuleInit:
    """Tests for module-level initialization functions."""

    # pylint: disable=protected-access

    def test_init_without_db_creates_no_store(self):
        """Initializing without db sets global store to None."""
        init_tenant_init_source_module(db=None)
        assert get_tenant_init_source_store() is None

    def test_init_with_connected_db_creates_store(self):
        """Initializing with connected db creates store instance."""
        mock_db = MagicMock()
        mock_db.is_connected = True
        init_tenant_init_source_module(db=mock_db)
        store = get_tenant_init_source_store()
        assert store is not None
        assert store._use_db is True

    def test_init_with_disconnected_db_creates_no_store(self):
        """Initializing with disconnected db sets global store to None."""
        mock_db = MagicMock()
        mock_db.is_connected = False
        init_tenant_init_source_module(db=mock_db)
        assert get_tenant_init_source_store() is None

    def test_cleanup(self):
        """Reset global store after tests."""
        init_tenant_init_source_module(db=None)


# ==================== Context variable tests ====================


class TestSourceIdContext:
    """Tests for source_id context variable."""

    def test_set_and_get_source_id(self):
        """set_current_source_id and get_current_source_id work correctly."""
        token = set_current_source_id("ruice")
        assert get_current_source_id() == "ruice"
        reset_current_source_id(token)
        assert get_current_source_id() is None

    def test_default_source_id_is_none(self):
        """Default source_id is None."""
        assert get_current_source_id() is None

    def test_set_source_id_to_none(self):
        """Setting source_id to None works."""
        token = set_current_source_id(None)
        assert get_current_source_id() is None
        reset_current_source_id(token)


# ==================== resolve_effective_tenant_id tests ====================


class TestResolveEffectiveTenantId:
    """Tests for resolve_effective_tenant_id utility."""

    def test_default_with_source_returns_source_tenant(self):
        """default + source_id → default_{source_id}."""
        from swe.config.context import resolve_effective_tenant_id

        assert (
            resolve_effective_tenant_id("default", "ruice") == "default_ruice"
        )

    def test_default_without_source_raises_error(self):
        """default + no source_id → TenantContextError."""
        from swe.config.context import (
            TenantContextError,
            resolve_effective_tenant_id,
        )

        with pytest.raises(TenantContextError):
            resolve_effective_tenant_id("default", None)

    def test_non_default_with_source_returns_original(self):
        """Non-default tenant with source_id → original tenant_id."""
        from swe.config.context import resolve_effective_tenant_id

        assert resolve_effective_tenant_id("user-001", "ruice") == "user-001"

    def test_non_default_without_source_returns_original(self):
        """Non-default tenant without source_id → original tenant_id."""
        from swe.config.context import resolve_effective_tenant_id

        assert resolve_effective_tenant_id("user-001", None) == "user-001"


# ==================== ProviderManager source-aware init tests ====================


class TestProviderManagerSourceInit:
    """Tests for ProviderManager source-aware initialization."""

    # pylint: disable=protected-access

    def test_source_template_providers_used_when_available(self, tmp_path):
        """ProviderManager uses source-specific template when available."""
        from swe.providers.provider_manager import ProviderManager

        with patch.object(ProviderManager, "__init__", lambda self: None):
            # Setup source-specific template
            source_providers = tmp_path / "default_ruice" / "providers"
            source_providers.mkdir(parents=True)
            (source_providers / "builtin").mkdir()
            (source_providers / "custom").mkdir()
            (source_providers / "active_model.json").write_text(
                '{"model": "ruice-model"}',
                encoding="utf-8",
            )

            target_dir = tmp_path / "tenant-1" / "providers"

            with (
                patch("swe.providers.provider_manager.SECRET_DIR", tmp_path),
                patch(
                    "swe.config.context.get_current_source_id",
                    return_value="ruice",
                ),
            ):
                ProviderManager._do_initialize_provider_storage(
                    "tenant-1",
                    target_dir,
                )

            assert target_dir.exists()
            assert (target_dir / "active_model.json").exists()

    def test_fallback_to_default_without_source_id(self, tmp_path):
        """ProviderManager falls back to default when no source_id."""
        from swe.providers.provider_manager import ProviderManager

        with patch.object(ProviderManager, "__init__", lambda self: None):
            default_providers = tmp_path / "default" / "providers"
            default_providers.mkdir(parents=True)
            (default_providers / "builtin").mkdir()
            (default_providers / "active_model.json").write_text(
                '{"model": "default-model"}',
                encoding="utf-8",
            )

            target_dir = tmp_path / "tenant-2" / "providers"

            with (
                patch("swe.providers.provider_manager.SECRET_DIR", tmp_path),
                patch(
                    "swe.config.context.get_current_source_id",
                    return_value=None,
                ),
            ):
                ProviderManager._do_initialize_provider_storage(
                    "tenant-2",
                    target_dir,
                )

            assert target_dir.exists()
            content = (target_dir / "active_model.json").read_text()
            assert "default-model" in content

    def test_empty_structure_when_no_template_exists(self, tmp_path):
        """ProviderManager creates empty structure when no template exists."""
        from swe.providers.provider_manager import ProviderManager

        with patch.object(ProviderManager, "__init__", lambda self: None):
            target_dir = tmp_path / "tenant-3" / "providers"

            with (
                patch("swe.providers.provider_manager.SECRET_DIR", tmp_path),
                patch(
                    "swe.config.context.get_current_source_id",
                    return_value=None,
                ),
            ):
                ProviderManager._do_initialize_provider_storage(
                    "tenant-3",
                    target_dir,
                )

            assert target_dir.exists()
            assert (target_dir / "builtin").exists()
            assert (target_dir / "custom").exists()

    def test_dynamic_source_template_creation_from_default(self, tmp_path):
        """ProviderManager creates source template from default when missing."""
        from swe.providers.provider_manager import ProviderManager

        with patch.object(ProviderManager, "__init__", lambda self: None):
            # Setup only default providers (no default_ruice)
            default_providers = tmp_path / "default" / "providers"
            default_providers.mkdir(parents=True)
            (default_providers / "builtin").mkdir()
            (default_providers / "custom").mkdir()
            (default_providers / "active_model.json").write_text(
                '{"model": "default-model"}',
                encoding="utf-8",
            )

            target_dir = tmp_path / "tenant-4" / "providers"

            with (
                patch("swe.providers.provider_manager.SECRET_DIR", tmp_path),
                patch(
                    "swe.config.context.get_current_source_id",
                    return_value="ruice",
                ),
            ):
                ProviderManager._do_initialize_provider_storage(
                    "tenant-4",
                    target_dir,
                )

            # Should have created default_ruice template
            assert (tmp_path / "default_ruice" / "providers").exists()
            # And copied to tenant
            assert target_dir.exists()
            assert (target_dir / "active_model.json").exists()
