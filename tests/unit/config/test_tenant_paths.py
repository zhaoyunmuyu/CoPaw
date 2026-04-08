# -*- coding: utf-8 -*-
"""Unit tests for tenant path helpers.

Tests tenant-aware path computation and strict failure when
tenant/workspace context is absent.
"""
import importlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

config_stub = types.ModuleType("swe.config.config")
config_stub.Config = object
config_stub.HeartbeatConfig = object
config_stub.LastApiConfig = object
config_stub.LastDispatchConfig = object
config_stub.load_agent_config = lambda *args, **kwargs: None
config_stub.save_agent_config = lambda *args, **kwargs: None
sys.modules["swe.config.config"] = config_stub

context_module = importlib.import_module("swe.config.context")
utils_module = importlib.import_module("swe.config.utils")

TenantContextError = context_module.TenantContextError
get_tenant_working_dir_strict = utils_module.get_tenant_working_dir_strict
get_tenant_config_path_strict = utils_module.get_tenant_config_path_strict
WORKING_DIR = utils_module.WORKING_DIR


class TestTenantPathHelpers:
    """Tests for tenant-aware path helpers."""

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_working_dir_with_tenant_id(self):
        """get_tenant_working_dir returns tenant subdirectory."""
        from swe.config.utils import get_tenant_working_dir
        from swe.constant import WORKING_DIR

        path = get_tenant_working_dir("tenant-1")
        assert path == WORKING_DIR / "tenant-1"

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_working_dir_without_tenant_id(self):
        """get_tenant_working_dir uses context when no tenant_id provided."""
        from swe.config.utils import get_tenant_working_dir
        from swe.constant import WORKING_DIR

        # When no tenant in context, returns global WORKING_DIR
        path = get_tenant_working_dir()
        assert path == WORKING_DIR

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_config_path(self):
        """get_tenant_config_path returns tenant config.json path."""
        from swe.config.utils import get_tenant_config_path
        from swe.constant import WORKING_DIR

        path = get_tenant_config_path("tenant-1")
        assert path == WORKING_DIR / "tenant-1" / "config.json"

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_jobs_path(self):
        """get_tenant_jobs_path returns tenant jobs.json path."""
        from swe.config.utils import get_tenant_jobs_path
        from swe.constant import WORKING_DIR, JOBS_FILE

        path = get_tenant_jobs_path("tenant-1")
        assert path == WORKING_DIR / "tenant-1" / JOBS_FILE

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_chats_path(self):
        """get_tenant_chats_path returns tenant chats.json path."""
        from swe.config.utils import get_tenant_chats_path
        from swe.constant import WORKING_DIR, CHATS_FILE

        path = get_tenant_chats_path("tenant-1")
        assert path == WORKING_DIR / "tenant-1" / CHATS_FILE

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_memory_dir(self):
        """get_tenant_memory_dir returns tenant memory directory."""
        from swe.config.utils import get_tenant_memory_dir
        from swe.constant import WORKING_DIR

        path = get_tenant_memory_dir("tenant-1")
        assert path == WORKING_DIR / "tenant-1" / "memory"

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_media_dir(self):
        """get_tenant_media_dir returns tenant media directory."""
        from swe.config.utils import get_tenant_media_dir
        from swe.constant import WORKING_DIR

        path = get_tenant_media_dir("tenant-1")
        assert path == WORKING_DIR / "tenant-1" / "media"

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_secrets_dir(self):
        """get_tenant_secrets_dir returns tenant secrets directory."""
        from swe.config.utils import get_tenant_secrets_dir
        from swe.constant import WORKING_DIR

        path = get_tenant_secrets_dir("tenant-1")
        assert path == WORKING_DIR / "tenant-1" / ".secret"

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_heartbeat_path(self):
        """get_tenant_heartbeat_path returns tenant HEARTBEAT.md path."""
        from swe.config.utils import get_tenant_heartbeat_path
        from swe.constant import WORKING_DIR, HEARTBEAT_FILE

        path = get_tenant_heartbeat_path("tenant-1")
        assert path == WORKING_DIR / "tenant-1" / HEARTBEAT_FILE


class TestTenantPathStrictHelpers:
    """Tests for strict tenant path helpers."""

    def test_get_tenant_working_dir_strict_raises_without_tenant_context(self):
        with pytest.raises(TenantContextError):
            get_tenant_working_dir_strict()

    def test_get_tenant_config_path_strict_uses_explicit_tenant(self):
        path = get_tenant_config_path_strict("tenant-a")
        assert path == WORKING_DIR / "tenant-a" / "config.json"

    def test_tenant_sensitive_helper_call_does_not_fallback_to_global_path(self):
        with pytest.raises(TenantContextError):
            get_tenant_working_dir_strict(None)

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_working_dir_strict_with_tenant_id(self):
        """get_tenant_working_dir_strict works with explicit tenant_id."""
        from swe.config.utils import get_tenant_working_dir_strict
        from swe.constant import WORKING_DIR

        path = get_tenant_working_dir_strict("tenant-1")
        assert path == WORKING_DIR / "tenant-1"

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_get_tenant_config_path_strict_raises_without_context(self):
        """get_tenant_config_path_strict raises when no tenant context."""
        from swe.config.utils import get_tenant_config_path_strict
        from swe.config.context import TenantContextError

        with pytest.raises(TenantContextError):
            get_tenant_config_path_strict()


class TestTenantPathBackwardCompatibility:
    """Tests for backward compatibility with non-tenant code."""

    @pytest.mark.skip(reason="Requires full app dependencies")
    def test_global_helpers_still_work(self):
        """Global path helpers still work for system-level paths."""
        from swe.config.utils import get_config_path, get_jobs_path
        from swe.constant import WORKING_DIR, CONFIG_FILE, JOBS_FILE

        # Global helpers return paths under WORKING_DIR
        assert get_config_path() == WORKING_DIR / CONFIG_FILE
        assert get_jobs_path() == WORKING_DIR / JOBS_FILE
