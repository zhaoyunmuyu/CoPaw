#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for migration script to tenant model configuration."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import migration functions
from copaw.tenant_models.models import (
    ModelSlot,
    RoutingConfig,
    TenantModelConfig,
    TenantProviderConfig,
)


def test_determine_provider_type():
    """Test provider type determination."""
    from scripts.migrate_to_tenant_models import determine_provider_type

    # Test anthropic provider
    assert determine_provider_type("anthropic") == "anthropic"
    assert (
        determine_provider_type("claude", "AnthropicChatModel") == "anthropic"
    )

    # Test ollama provider
    assert determine_provider_type("ollama") == "ollama"

    # Test openai provider (default)
    assert determine_provider_type("openai") == "openai"
    assert determine_provider_type("aliyun-codingplan") == "openai"
    assert determine_provider_type("custom-provider") == "openai"


def test_extract_model_names():
    """Test model name extraction."""
    from scripts.migrate_to_tenant_models import extract_model_names

    models_data = [
        {"id": "model-1", "name": "Model One"},
        {"id": "model-2"},
        {"name": "Model Three"},
    ]

    result = extract_model_names(models_data)
    assert result == ["model-1", "model-2", "Model Three"]


def test_convert_provider_config():
    """Test provider config conversion."""
    from scripts.migrate_to_tenant_models import convert_provider_config

    legacy_config = {
        "api_key": "test-key",
        "base_url": "https://api.example.com/v1",
        "models": [{"id": "model-1"}, {"id": "model-2"}],
        "extra_models": [{"id": "model-3"}],
        "chat_model": "OpenAIChatModel",
        "generate_kwargs": {"max_tokens": 1000},
        "name": "Test Provider",
    }

    result = convert_provider_config(
        "test-provider",
        legacy_config,
        is_builtin=True,
    )

    assert isinstance(result, TenantProviderConfig)
    assert result.id == "test-provider"
    assert result.type == "openai"
    assert result.api_key == "test-key"
    assert result.base_url == "https://api.example.com/v1"
    assert len(result.models) == 3
    assert "model-1" in result.models
    assert "model-2" in result.models
    assert "model-3" in result.models
    assert result.enabled is True
    assert result.extra["chat_model"] == "OpenAIChatModel"
    assert result.extra["generate_kwargs"] == {"max_tokens": 1000}
    assert result.extra["name"] == "Test Provider"
    assert result.extra["is_builtin"] is True


def test_convert_active_llm_to_routing_with_data():
    """Test routing config conversion with active_llm data."""
    from scripts.migrate_to_tenant_models import convert_active_llm_to_routing

    active_llm = {
        "provider_id": "openai",
        "model": "gpt-4",
    }

    result = convert_active_llm_to_routing(active_llm)

    assert isinstance(result, RoutingConfig)
    assert result.mode == "local_first"
    assert "local" in result.slots
    assert "cloud" in result.slots
    assert result.slots["cloud"].provider_id == "openai"
    assert result.slots["cloud"].model == "gpt-4"
    assert result.slots["local"].provider_id == ""
    assert result.slots["local"].model == ""


def test_convert_active_llm_to_routing_empty():
    """Test routing config conversion without active_llm data."""
    from scripts.migrate_to_tenant_models import convert_active_llm_to_routing

    result = convert_active_llm_to_routing(None)

    assert isinstance(result, RoutingConfig)
    assert result.mode == "local_first"
    assert "local" in result.slots
    assert "cloud" in result.slots
    assert result.slots["cloud"].provider_id == ""
    assert result.slots["cloud"].model == ""


def test_migrate_legacy_to_tenant_config():
    """Test full legacy to tenant config migration."""
    from scripts.migrate_to_tenant_models import (
        migrate_legacy_to_tenant_config,
    )

    legacy_data = {
        "providers": {
            "openai": {
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "models": [{"id": "gpt-4"}, {"id": "gpt-3.5-turbo"}],
            },
            "anthropic": {
                "api_key": "ant-test",
                "models": [{"id": "claude-3-opus"}],
            },
        },
        "custom_providers": {
            "my-custom": {
                "name": "My Custom Provider",
                "base_url": "https://custom.api.com/v1",
                "api_key": "custom-key",
                "models": [{"id": "custom-model"}],
            },
        },
        "active_llm": {
            "provider_id": "openai",
            "model": "gpt-4",
        },
    }

    result = migrate_legacy_to_tenant_config(legacy_data)

    assert isinstance(result, TenantModelConfig)
    assert result.version == "1.0"
    assert len(result.providers) == 3

    # Check OpenAI provider
    openai_provider = next(p for p in result.providers if p.id == "openai")
    assert openai_provider.type == "openai"
    assert openai_provider.api_key == "sk-test"
    assert "gpt-4" in openai_provider.models
    assert openai_provider.extra.get("is_builtin") is True

    # Check Anthropic provider
    anthropic_provider = next(
        p for p in result.providers if p.id == "anthropic"
    )
    assert anthropic_provider.type == "anthropic"
    assert anthropic_provider.api_key == "ant-test"

    # Check custom provider
    custom_provider = next(p for p in result.providers if p.id == "my-custom")
    assert custom_provider.type == "openai"
    assert custom_provider.base_url == "https://custom.api.com/v1"
    # is_builtin may be absent or False for custom providers
    assert custom_provider.extra.get("is_builtin", False) is False
    assert custom_provider.extra.get("name") == "My Custom Provider"

    # Check routing
    assert result.routing.mode == "local_first"
    assert result.routing.slots["cloud"].provider_id == "openai"
    assert result.routing.slots["cloud"].model == "gpt-4"


def test_create_default_config():
    """Test default config creation."""
    from scripts.migrate_to_tenant_models import create_default_config

    result = create_default_config()

    assert isinstance(result, TenantModelConfig)
    assert result.version == "1.0"
    assert len(result.providers) == 0
    assert result.routing.mode == "local_first"
    assert "local" in result.routing.slots
    assert "cloud" in result.routing.slots


def test_save_and_verify_tenant_config():
    """Test saving and verifying tenant config."""
    from scripts.migrate_to_tenant_models import (
        save_tenant_config,
        verify_migration,
    )

    config = TenantModelConfig(
        version="1.0",
        providers=[
            TenantProviderConfig(
                id="test-provider",
                type="openai",
                api_key="test-key",
                models=["model-1", "model-2"],
                enabled=True,
                extra={},
            ),
        ],
        routing=RoutingConfig(
            mode="local_first",
            slots={
                "local": ModelSlot(provider_id="", model=""),
                "cloud": ModelSlot(
                    provider_id="test-provider",
                    model="model-1",
                ),
            },
        ),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        # Patch WORKING_DIR in migration script and SECRET_DIR in manager
        with patch(
            "scripts.migrate_to_tenant_models.WORKING_DIR",
            working_dir,
        ):
            with patch("copaw.tenant_models.manager.SECRET_DIR", working_dir):
                # Clear cache to ensure fresh load
                from copaw.tenant_models.manager import TenantModelManager

                TenantModelManager._cache.clear()

                # Save config
                save_tenant_config(config)

                # Verify file was created
                config_path = working_dir / "default" / "tenant_models.json"
                assert config_path.exists()

                # Verify content
                with open(config_path, "r") as f:
                    data = json.load(f)

                assert data["version"] == "1.0"
                assert len(data["providers"]) == 1
                assert data["providers"][0]["id"] == "test-provider"

                # Run verification
                verify_migration(config_path)


def test_full_migration_workflow_without_legacy():
    """Test full migration workflow when no legacy config exists."""
    from scripts.migrate_to_tenant_models import (
        create_default_config,
        save_tenant_config,
        verify_migration,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        with patch(
            "scripts.migrate_to_tenant_models.WORKING_DIR",
            working_dir,
        ):
            with patch("copaw.tenant_models.manager.SECRET_DIR", working_dir):
                # Clear cache
                from copaw.tenant_models.manager import TenantModelManager

                TenantModelManager._cache.clear()

                # Create default config
                config = create_default_config()

                # Save it
                save_tenant_config(config)

                # Verify
                config_path = working_dir / "default" / "tenant_models.json"
                verify_migration(config_path)

                assert config_path.exists()


def test_full_migration_workflow_with_legacy():
    """Test full migration workflow with legacy config."""
    from scripts.migrate_to_tenant_models import (
        migrate_legacy_to_tenant_config,
        save_tenant_config,
        verify_migration,
    )

    legacy_data = {
        "providers": {
            "openai": {
                "api_key": "sk-test",
                "models": [{"id": "gpt-4"}],
            },
        },
        "active_llm": {
            "provider_id": "openai",
            "model": "gpt-4",
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        with patch(
            "scripts.migrate_to_tenant_models.WORKING_DIR",
            working_dir,
        ):
            with patch("copaw.tenant_models.manager.SECRET_DIR", working_dir):
                # Clear cache
                from copaw.tenant_models.manager import TenantModelManager

                TenantModelManager._cache.clear()

                # Migrate
                config = migrate_legacy_to_tenant_config(legacy_data)

                # Save it
                save_tenant_config(config)

                # Verify
                config_path = working_dir / "default" / "tenant_models.json"
                verify_migration(config_path)

                assert config_path.exists()

                # Verify content
                with open(config_path, "r") as f:
                    data = json.load(f)

                assert len(data["providers"]) == 1
                assert data["providers"][0]["id"] == "openai"
                assert (
                    data["routing"]["slots"]["cloud"]["provider_id"]
                    == "openai"
                )
