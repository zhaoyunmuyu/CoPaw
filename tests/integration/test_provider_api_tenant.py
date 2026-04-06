# -*- coding: utf-8 -*-
# flake8: noqa: E402
# pylint: disable=wrong-import-position,redefined-outer-name,unused-variable
"""Integration tests for provider API tenant routing."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from copaw.app.routers.providers import router as providers_router
from copaw.providers.provider import ProviderInfo


@pytest.fixture
def client():
    """Create a test client with providers router."""
    app = FastAPI()

    # Add middleware to set tenant_id in request state
    @app.middleware("http")
    async def add_tenant_id(request: Request, call_next):
        request.state.tenant_id = request.headers.get("X-Tenant-Id", "default")
        response = await call_next(request)
        return response

    # Don't add prefix - the router already has /models prefix
    app.include_router(providers_router)
    return TestClient(app)


class TestProviderAPIGetProviders:
    """Tests for GET /models endpoint."""

    def test_get_providers_uses_tenant_from_header(self, client):
        """GET /models uses tenant ID from header."""
        with patch(
            "copaw.app.routers.providers.ProviderManager",
        ) as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.list_provider_info = AsyncMock(
                return_value=[
                    ProviderInfo(
                        id="openai",
                        name="OpenAI",
                        base_url="https://api.openai.com/v1",
                        is_custom=False,
                    ),
                ],
            )
            mock_manager.get_active_model.return_value = None
            mock_pm_class.get_instance.return_value = mock_manager

            response = client.get(
                "/models/",
                headers={"X-Tenant-Id": "tenant-a"},
            )

            assert response.status_code == 200
            # Verify get_instance was called with tenant-a
            mock_pm_class.get_instance.assert_called_with("tenant-a")

    def test_get_providers_uses_default_without_header(self, client):
        """GET /models uses default tenant without header."""
        with patch(
            "copaw.app.routers.providers.ProviderManager",
        ) as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.list_provider_info = AsyncMock(return_value=[])
            mock_manager.get_active_model.return_value = None
            mock_pm_class.get_instance.return_value = mock_manager

            response = client.get("/models/")

            assert response.status_code == 200
            # Verify get_instance was called with default
            mock_pm_class.get_instance.assert_called_with("default")


class TestProviderAPICreateProvider:
    """Tests for POST /models/custom-providers endpoint."""

    def test_create_provider_uses_tenant_from_header(self, client):
        """POST /models/custom-providers uses tenant ID from header."""
        with patch(
            "copaw.app.routers.providers.ProviderManager",
        ) as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.add_custom_provider = AsyncMock(
                return_value=ProviderInfo(
                    id="custom",
                    name="Custom",
                    base_url="https://custom.example/v1",
                    is_custom=True,
                ),
            )
            mock_pm_class.get_instance.return_value = mock_manager

            response = client.post(
                "/models/custom-providers",
                headers={"X-Tenant-Id": "tenant-b"},
                json={
                    "id": "custom",
                    "name": "Custom",
                    "base_url": "https://custom.example/v1",
                    "api_key_prefix": "",
                    "chat_model": "OpenAIChatModel",
                    "models": [],
                },
            )

            # Verify get_instance was called with tenant-b
            mock_pm_class.get_instance.assert_called_with("tenant-b")


class TestProviderAPIUpdateProvider:
    """Tests for PUT /models/{provider_id}/config endpoint."""

    def test_update_provider_uses_tenant_from_header(self, client):
        """PUT /models/{id}/config uses tenant ID from header."""
        with patch(
            "copaw.app.routers.providers.ProviderManager",
        ) as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.update_provider.return_value = True
            mock_manager.get_provider_info = AsyncMock(
                return_value=ProviderInfo(
                    id="openai",
                    name="OpenAI",
                    base_url="https://api.openai.com/v1",
                    is_custom=False,
                ),
            )
            mock_pm_class.get_instance.return_value = mock_manager

            response = client.put(
                "/models/openai/config",
                headers={"X-Tenant-Id": "tenant-c"},
                json={"api_key": "sk-test"},
            )

            # Verify get_instance was called with tenant-c
            mock_pm_class.get_instance.assert_called_with("tenant-c")


class TestProviderAPIDeleteProvider:
    """Tests for DELETE /models/custom-providers/{provider_id} endpoint."""

    def test_delete_provider_uses_tenant_from_header(self, client):
        """DELETE /models/custom-providers/{id} uses tenant ID from header."""
        with patch(
            "copaw.app.routers.providers.ProviderManager",
        ) as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.remove_custom_provider.return_value = True
            mock_manager.list_provider_info = AsyncMock(return_value=[])
            mock_manager.builtin_providers = {"openai"}
            mock_pm_class.get_instance.return_value = mock_manager

            response = client.delete(
                "/models/custom-providers/custom",
                headers={"X-Tenant-Id": "tenant-d"},
            )

            # Verify get_instance was called with tenant-d
            mock_pm_class.get_instance.assert_called_with("tenant-d")


class TestProviderAPISetActiveModel:
    """Tests for PUT /models/active endpoint."""

    def test_set_active_model_uses_tenant_from_header(self, client):
        """PUT /models/active uses tenant ID from header."""
        with patch(
            "copaw.app.routers.providers.ProviderManager",
        ) as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.activate_model = AsyncMock(return_value=None)
            mock_manager.get_active_model.return_value = None
            mock_pm_class.get_instance.return_value = mock_manager

            response = client.put(
                "/models/active",
                headers={"X-Tenant-Id": "tenant-e"},
                json={
                    "provider_id": "openai",
                    "model": "gpt-4",
                    "scope": "global",
                },
            )

            # Verify get_instance was called with tenant-e
            mock_pm_class.get_instance.assert_called_with("tenant-e")


class TestProviderAPITenantIsolation:
    """Tests for tenant isolation in provider API."""

    def test_different_tenants_see_different_providers(self, client):
        """Different tenants see different provider configurations."""
        with patch(
            "copaw.app.routers.providers.ProviderManager",
        ) as mock_pm_class:
            # Create separate managers for each tenant
            manager_a = MagicMock()
            manager_a.list_provider_info = AsyncMock(
                return_value=[
                    ProviderInfo(
                        id="openai",
                        name="OpenAI",
                        base_url="https://api.openai.com/v1",
                        is_custom=False,
                    ),
                ],
            )
            manager_a.get_active_model.return_value = None

            manager_b = MagicMock()
            manager_b.list_provider_info = AsyncMock(
                return_value=[
                    ProviderInfo(
                        id="anthropic",
                        name="Anthropic",
                        base_url="https://api.anthropic.com/v1",
                        is_custom=False,
                    ),
                ],
            )
            manager_b.get_active_model.return_value = None

            def get_instance(tenant_id):
                return manager_a if tenant_id == "tenant-a" else manager_b

            mock_pm_class.get_instance.side_effect = get_instance

            # Get providers for tenant-a
            response_a = client.get(
                "/models/",
                headers={"X-Tenant-Id": "tenant-a"},
            )
            data_a = response_a.json()

            # Get providers for tenant-b
            response_b = client.get(
                "/models/",
                headers={"X-Tenant-Id": "tenant-b"},
            )
            data_b = response_b.json()

            # Verify different providers
            assert data_a[0]["id"] == "openai"
            assert data_b[0]["id"] == "anthropic"

    def test_provider_config_isolated_by_tenant(self, client):
        """Provider configurations are isolated by tenant."""
        with patch(
            "copaw.app.routers.providers.ProviderManager",
        ) as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.update_provider.return_value = True
            mock_manager.get_provider_info = AsyncMock(
                return_value=ProviderInfo(
                    id="openai",
                    name="OpenAI",
                    base_url="https://api.openai.com/v1",
                    is_custom=False,
                ),
            )
            mock_pm_class.get_instance.return_value = mock_manager

            # Update for tenant-x
            client.put(
                "/models/openai/config",
                headers={"X-Tenant-Id": "tenant-x"},
                json={"api_key": "sk-tenant-x"},
            )

            # Update for tenant-y
            client.put(
                "/models/openai/config",
                headers={"X-Tenant-Id": "tenant-y"},
                json={"api_key": "sk-tenant-y"},
            )

            # Verify different tenants were used
            assert mock_pm_class.get_instance.call_count == 2
            calls = [
                call.args[0]
                for call in mock_pm_class.get_instance.call_args_list
            ]
            assert "tenant-x" in calls
            assert "tenant-y" in calls
