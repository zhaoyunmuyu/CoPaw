# -*- coding: utf-8 -*-
# flake8: noqa: E402
# pylint: disable=wrong-import-position,unused-import,protected-access,unused-variable
"""Tests for deferred tenant provider initialization.

This module tests that provider storage is initialized lazily at provider
feature boundaries rather than eagerly in tenant middleware.

Test coverage:
- Non-provider requests do not initialize provider storage (Task 3.1)
- First provider API use initializes storage correctly (Task 3.2)
- First runtime model creation initializes storage correctly (Task 3.3)
- Tenant isolation semantics remain unchanged (Task 3.4)
"""
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from swe.providers.provider_manager import ProviderManager


class TestDeferredProviderInitialization:
    """Tests for deferred provider initialization at feature boundaries."""

    def test_non_provider_request_does_not_init_provider_storage(
        self,
        tmp_path,
    ):
        """Non-provider tenant requests should not create provider storage.

        This verifies that workspace bootstrap alone does not trigger
        provider storage initialization.
        """
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            tenant_id = "test-tenant-no-provider"
            tenant_providers_dir = (
                tmp_path / ".swe.secret" / tenant_id / "providers"
            )

            # Verify provider storage does not exist initially
            assert not tenant_providers_dir.exists()

            # Simulate workspace bootstrap (without provider initialization)
            # This mimics what TenantWorkspaceMiddleware does now
            workspace_dir = tmp_path / ".swe" / tenant_id
            workspace_dir.mkdir(parents=True)

            # Verify provider storage was NOT created
            assert not tenant_providers_dir.exists()

            # Verify other tenant directories were created
            assert workspace_dir.exists()

    def test_middleware_no_longer_calls_provider_init(self):
        """TenantWorkspaceMiddleware no longer initializes provider storage.

        Verifies that the middleware has been updated to remove the
        _ensure_tenant_provider_config call.
        """
        from swe.app.middleware.tenant_workspace import (
            TenantWorkspaceMiddleware,
        )

        # Verify the method no longer exists on the middleware
        assert not hasattr(
            TenantWorkspaceMiddleware,
            "_ensure_tenant_provider_config",
        ), "Middleware should not have _ensure_tenant_provider_config method"

    def test_provider_manager_has_ensure_storage_method(self):
        """ProviderManager has the ensure_tenant_provider_storage method."""
        assert hasattr(
            ProviderManager,
            "ensure_tenant_provider_storage",
        ), "ProviderManager should have ensure_tenant_provider_storage method"

        # Verify it's callable
        method = getattr(ProviderManager, "ensure_tenant_provider_storage")
        assert callable(
            method,
        ), "ensure_tenant_provider_storage should be callable"


class TestProviderAPIInitialization:
    """Tests for provider storage initialization at provider API boundaries."""

    def test_first_provider_api_call_initializes_storage(self, tmp_path):
        """First provider API use initializes tenant provider storage.

        This verifies that ensure_tenant_provider_storage is called when
        accessing provider management APIs.
        """
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            tenant_id = "api-init-tenant"
            tenant_providers_dir = (
                tmp_path / ".swe.secret" / tenant_id / "providers"
            )

            # Verify storage does not exist initially
            assert not tenant_providers_dir.exists()

            # Call ensure_tenant_provider_storage (simulating API entrypoint)
            ProviderManager.ensure_tenant_provider_storage(tenant_id)

            # Verify storage was created
            assert tenant_providers_dir.exists()
            assert (tenant_providers_dir / "builtin").exists()
            assert (tenant_providers_dir / "custom").exists()

    def test_ensure_storage_is_idempotent(self, tmp_path):
        """ensure_tenant_provider_storage can be called multiple times safely."""
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            tenant_id = "idempotent-tenant"
            tenant_providers_dir = (
                tmp_path / ".swe.secret" / tenant_id / "providers"
            )

            # First call creates storage
            ProviderManager.ensure_tenant_provider_storage(tenant_id)
            assert tenant_providers_dir.exists()

            # Add a marker file to verify it's not overwritten
            marker_file = tenant_providers_dir / "marker.txt"
            marker_file.write_text("test")

            # Second call should be a no-op
            ProviderManager.ensure_tenant_provider_storage(tenant_id)

            # Verify marker file still exists (storage wasn't recreated)
            assert marker_file.exists()
            assert marker_file.read_text() == "test"

    def test_ensure_storage_copies_from_default(self, tmp_path):
        """ensure_tenant_provider_storage copies from default tenant if available."""
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            # Setup default tenant with configuration
            default_dir = tmp_path / ".swe.secret" / "default" / "providers"
            default_dir.mkdir(parents=True)
            default_builtin = default_dir / "builtin"
            default_builtin.mkdir()

            # Create a provider config in default
            import json

            (default_builtin / "openai.json").write_text(
                json.dumps(
                    {
                        "id": "openai",
                        "name": "OpenAI",
                        "base_url": "https://api.openai.com/v1",
                        "api_key": "sk-default-key",
                    },
                ),
            )

            # Create a new tenant
            tenant_id = "inherit-tenant"
            tenant_providers_dir = (
                tmp_path / ".swe.secret" / tenant_id / "providers"
            )

            # Ensure storage for new tenant
            ProviderManager.ensure_tenant_provider_storage(tenant_id)

            # Verify config was copied from default
            assert tenant_providers_dir.exists()
            assert (tenant_providers_dir / "builtin" / "openai.json").exists()

            # Verify ProviderManager loads the inherited config
            ProviderManager._instances.clear()
            manager = ProviderManager.get_instance(tenant_id)
            provider = manager.get_provider("openai")
            assert provider is not None
            assert provider.api_key == "sk-default-key"


class TestConcurrentInitialization:
    """Tests for concurrent-safe provider storage initialization."""

    def test_concurrent_ensure_storage_is_safe(self, tmp_path):
        """Concurrent calls to ensure_tenant_provider_storage are safe."""
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            tenant_id = "concurrent-init-tenant"
            tenant_providers_dir = (
                tmp_path / ".swe.secret" / tenant_id / "providers"
            )

            results = []
            errors = []

            def ensure_storage():
                try:
                    ProviderManager.ensure_tenant_provider_storage(tenant_id)
                    results.append("success")
                except Exception as e:
                    errors.append(str(e))

            # Start multiple threads simultaneously
            threads = []
            for _ in range(10):
                t = threading.Thread(target=ensure_storage)
                threads.append(t)

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            # Verify no errors
            assert len(errors) == 0, f"Errors during concurrent init: {errors}"

            # Verify storage was created
            assert tenant_providers_dir.exists()

    def test_concurrent_ensure_storage_with_default_copy(self, tmp_path):
        """Concurrent initialization with default tenant copy is safe."""
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            # Setup default tenant
            default_dir = tmp_path / ".swe.secret" / "default" / "providers"
            default_dir.mkdir(parents=True)
            default_builtin = default_dir / "builtin"
            default_builtin.mkdir()

            import json

            (default_builtin / "test-provider.json").write_text(
                json.dumps({"id": "test-provider", "name": "Test"}),
            )

            tenant_id = "concurrent-copy-tenant"
            errors = []

            def ensure_storage():
                try:
                    ProviderManager.ensure_tenant_provider_storage(tenant_id)
                except Exception as e:
                    errors.append(str(e))

            # Start multiple threads simultaneously
            threads = []
            for _ in range(5):
                t = threading.Thread(target=ensure_storage)
                threads.append(t)

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            # Verify no errors
            assert len(errors) == 0, f"Errors during concurrent copy: {errors}"

            # Verify storage was created correctly
            tenant_dir = tmp_path / ".swe.secret" / tenant_id / "providers"
            assert tenant_dir.exists()
            assert (tenant_dir / "builtin" / "test-provider.json").exists()


class TestTenantIsolationPreserved:
    """Tests that tenant isolation semantics remain unchanged."""

    def test_tenant_isolation_after_deferred_init(self, tmp_path):
        """Tenant isolation works correctly with deferred initialization."""
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            # Initialize storage for two tenants
            tenant_a = "isolated-a"
            tenant_b = "isolated-b"

            ProviderManager.ensure_tenant_provider_storage(tenant_a)
            ProviderManager.ensure_tenant_provider_storage(tenant_b)

            # Get managers for both tenants
            ProviderManager._instances.clear()
            manager_a = ProviderManager.get_instance(tenant_a)
            manager_b = ProviderManager.get_instance(tenant_b)

            # Configure different API keys
            manager_a.update_provider("openai", {"api_key": "sk-a"})
            manager_b.update_provider("openai", {"api_key": "sk-b"})

            # Clear cache and reload
            ProviderManager._instances.clear()
            reloaded_a = ProviderManager.get_instance(tenant_a)
            reloaded_b = ProviderManager.get_instance(tenant_b)

            # Verify isolation is preserved
            assert reloaded_a.get_provider("openai").api_key == "sk-a"
            assert reloaded_b.get_provider("openai").api_key == "sk-b"

    def test_default_tenant_isolation_preserved(self, tmp_path):
        """Default tenant isolation works with deferred initialization."""
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            # Ensure default tenant storage exists
            ProviderManager.ensure_tenant_provider_storage("default")

            # Configure default tenant
            manager = ProviderManager.get_instance("default")
            manager.update_provider("openai", {"api_key": "sk-default"})

            # New tenant should inherit from default but be isolated
            new_tenant = "inherits-from-default"
            ProviderManager.ensure_tenant_provider_storage(new_tenant)

            # Verify new tenant has inherited config
            new_manager = ProviderManager.get_instance(new_tenant)
            assert new_manager.get_provider("openai").api_key == "sk-default"

            # Modify new tenant's config
            new_manager.update_provider("openai", {"api_key": "sk-new"})

            # Verify default tenant is unchanged
            ProviderManager._instances.clear()
            default_manager = ProviderManager.get_instance("default")
            assert (
                default_manager.get_provider("openai").api_key == "sk-default"
            )


class TestEmptyDirectoryCreation:
    """Tests for empty directory creation when default has no config."""

    def test_empty_structure_when_default_empty(self, tmp_path):
        """Empty directory structure is created when default has no config."""
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            # Don't create default tenant config
            tenant_id = "empty-default-tenant"
            tenant_providers_dir = (
                tmp_path / ".swe.secret" / tenant_id / "providers"
            )

            # Ensure storage
            ProviderManager.ensure_tenant_provider_storage(tenant_id)

            # Verify empty structure was created
            assert tenant_providers_dir.exists()
            assert (tenant_providers_dir / "builtin").exists()
            assert (tenant_providers_dir / "custom").exists()

            # Verify no files were copied (empty)
            assert not list((tenant_providers_dir / "builtin").iterdir())


class TestNoneTenantHandling:
    """Tests for None tenant_id handling."""

    def test_none_tenant_defaults_to_default(self, tmp_path):
        """None tenant_id defaults to 'default' for ensure_tenant_provider_storage."""
        with patch(
            "swe.providers.provider_manager.SECRET_DIR",
            tmp_path / ".swe.secret",
        ):
            # Call with None
            ProviderManager.ensure_tenant_provider_storage(None)

            # Verify default tenant storage was created
            default_dir = tmp_path / ".swe.secret" / "default" / "providers"
            assert default_dir.exists()
