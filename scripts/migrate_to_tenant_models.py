#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migration script for converting legacy providers.json to tenant model configuration.

This script migrates from the old providers.json format to the new tenant-based
model configuration format (TenantModelConfig).

Migration Logic:
1. Load legacy providers.json (if exists)
2. Convert legacy provider configs to TenantProviderConfig format
3. Convert legacy routing config to RoutingConfig format (if exists)
4. If no legacy config, create default empty configuration
5. Save to default tenant (tenants/default/tenant_models.json)
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

# Add parent directory to path for imports before importing copaw modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# pylint: disable=wrong-import-position
from copaw.constant import SECRET_DIR, WORKING_DIR
from copaw.tenant_models.manager import TenantModelManager
from copaw.tenant_models.models import (
    ModelSlot,
    RoutingConfig,
    TenantModelConfig,
    TenantProviderConfig,
)

# pylint: enable=wrong-import-position

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def determine_provider_type(
    provider_id: str,
    chat_model: Optional[str] = None,
) -> Literal["openai", "anthropic", "ollama"]:
    """Determine provider type from provider_id or chat_model.

    Args:
        provider_id: Provider identifier.
        chat_model: Chat model class name.

    Returns:
        Provider type: "openai", "anthropic", or "ollama".
    """
    if provider_id == "anthropic" or chat_model == "AnthropicChatModel":
        return "anthropic"
    if provider_id == "ollama":
        return "ollama"
    # Default to openai for most providers
    return "openai"


def extract_model_names(models_data: List[Dict[str, Any]]) -> List[str]:
    """Extract model IDs from model data.

    Args:
        models_data: List of model information dictionaries.

    Returns:
        List of model IDs.
    """
    return [model.get("id", model.get("name", "")) for model in models_data]


def convert_provider_config(
    provider_id: str,
    provider_data: Dict[str, Any],
    is_builtin: bool = False,
) -> TenantProviderConfig:
    """Convert legacy provider config to TenantProviderConfig.

    Args:
        provider_id: Provider identifier.
        provider_data: Legacy provider configuration data.
        is_builtin: Whether this is a built-in provider.

    Returns:
        TenantProviderConfig instance.
    """
    # Determine provider type
    chat_model = provider_data.get("chat_model")
    provider_type = determine_provider_type(provider_id, chat_model)

    # Extract API key
    api_key = provider_data.get("api_key")

    # Extract base URL
    base_url = provider_data.get("base_url")

    # Extract models (combine static models and extra_models)
    models = []
    if "models" in provider_data:
        models.extend(extract_model_names(provider_data["models"]))
    if "extra_models" in provider_data:
        models.extend(extract_model_names(provider_data["extra_models"]))

    # Extract extra configuration
    extra: Dict[str, Any] = {}
    if chat_model:
        extra["chat_model"] = chat_model
    if "generate_kwargs" in provider_data:
        extra["generate_kwargs"] = provider_data["generate_kwargs"]
    if "name" in provider_data:
        extra["name"] = provider_data["name"]
    if is_builtin:
        extra["is_builtin"] = True

    return TenantProviderConfig(
        id=provider_id,
        type=provider_type,
        api_key=api_key,
        base_url=base_url,
        models=models,
        enabled=True,
        extra=extra,
    )


def convert_active_llm_to_routing(
    active_llm: Optional[Dict[str, Any]],
) -> RoutingConfig:
    """Convert legacy active_llm config to RoutingConfig.

    Args:
        active_llm: Legacy active_llm configuration.

    Returns:
        RoutingConfig instance with default routing mode.
    """
    # Default routing mode
    mode: Literal["local_first", "cloud_first"] = "local_first"

    # Create slots dictionary
    slots: Dict[str, ModelSlot] = {}

    # If active_llm exists, use it as the cloud slot
    if (
        active_llm
        and active_llm.get("provider_id")
        and active_llm.get("model")
    ):
        slots["cloud"] = ModelSlot(
            provider_id=active_llm["provider_id"],
            model=active_llm["model"],
        )
        # Create a placeholder local slot
        slots["local"] = ModelSlot(
            provider_id="",
            model="",
        )
    else:
        # Create empty slots if no active_llm
        slots["local"] = ModelSlot(
            provider_id="",
            model="",
        )
        slots["cloud"] = ModelSlot(
            provider_id="",
            model="",
        )

    return RoutingConfig(mode=mode, slots=slots)


def load_legacy_config() -> Optional[Dict[str, Any]]:
    """Load legacy providers.json configuration.

    Returns:
        Legacy configuration data or None if file doesn't exist.
    """
    legacy_path = SECRET_DIR / "providers.json"
    if not legacy_path.exists():
        logger.info("No legacy providers.json found at %s", legacy_path)
        return None

    try:
        with open(legacy_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded legacy configuration from %s", legacy_path)
        return data
    except Exception as e:
        logger.error("Failed to load legacy configuration: %s", e)
        raise


def create_default_config() -> TenantModelConfig:
    """Create a default empty tenant model configuration.

    Returns:
        TenantModelConfig with empty providers and routing.
    """
    return TenantModelConfig(
        version="1.0",
        providers=[],
        routing=RoutingConfig(
            mode="local_first",
            slots={
                "local": ModelSlot(provider_id="", model=""),
                "cloud": ModelSlot(provider_id="", model=""),
            },
        ),
    )


def migrate_legacy_to_tenant_config(
    legacy_data: Dict[str, Any],
) -> TenantModelConfig:
    """Migrate legacy configuration to TenantModelConfig.

    Args:
        legacy_data: Legacy providers.json data.

    Returns:
        TenantModelConfig instance.
    """
    providers: List[TenantProviderConfig] = []

    # Migrate built-in providers
    builtin_providers = legacy_data.get("providers", {})
    for provider_id, config in builtin_providers.items():
        try:
            tenant_provider = convert_provider_config(
                provider_id,
                config,
                is_builtin=True,
            )
            providers.append(tenant_provider)
            logger.info("Migrated built-in provider: %s", provider_id)
        except Exception as e:
            logger.warning(
                "Failed to migrate built-in provider '%s': %s",
                provider_id,
                e,
            )

    # Migrate custom providers
    custom_providers = legacy_data.get("custom_providers", {})
    for provider_id, data in custom_providers.items():
        try:
            tenant_provider = convert_provider_config(
                provider_id,
                data,
                is_builtin=False,
            )
            providers.append(tenant_provider)
            logger.info("Migrated custom provider: %s", provider_id)
        except Exception as e:
            logger.warning(
                "Failed to migrate custom provider '%s': %s",
                provider_id,
                e,
            )

    # Migrate routing configuration
    active_llm = legacy_data.get("active_llm")
    routing = convert_active_llm_to_routing(active_llm)
    logger.info("Migrated routing configuration")

    return TenantModelConfig(
        version="1.0",
        providers=providers,
        routing=routing,
    )


def save_tenant_config(config: TenantModelConfig) -> None:
    """Save tenant model configuration to default tenant.

    Args:
        config: TenantModelConfig to save.
    """
    TenantModelManager.save("default", config)
    logger.info("Saved tenant configuration for default tenant")


def verify_migration(config_path: Path) -> None:
    """Verify the migrated configuration file.

    Args:
        config_path: Path to the migrated configuration file.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate using TenantModelConfig
        TenantModelConfig(**data)
        logger.info("Verification successful: configuration is valid")

        # Log summary
        logger.info("Configuration summary:")
        logger.info("  - Version: %s", data.get("version"))
        logger.info("  - Providers: %d", len(data.get("providers", [])))
        logger.info(
            "  - Routing mode: %s",
            data.get("routing", {}).get("mode"),
        )

        for provider in data.get("providers", []):
            logger.info(
                "  - Provider '%s': %d models",
                provider.get("id"),
                len(provider.get("models", [])),
            )
    except Exception as e:
        logger.error("Verification failed: %s", e)
        raise


def main() -> None:
    """Main migration function."""
    logger.info("Starting migration to tenant model configuration...")

    # Load legacy configuration
    legacy_data = load_legacy_config()

    # Create tenant configuration
    if legacy_data:
        logger.info("Migrating from legacy configuration...")
        tenant_config = migrate_legacy_to_tenant_config(legacy_data)
    else:
        logger.info("Creating default configuration...")
        tenant_config = create_default_config()

    # Save tenant configuration
    save_tenant_config(tenant_config)

    # Verify migration
    config_path = TenantModelManager.get_config_path("default")
    verify_migration(config_path)

    logger.info("Migration completed successfully!")

    # Print user guidance
    print("\nNext steps:")
    print(f"1. Review the migrated config at: {config_path}")
    print("2. Update API keys if needed")
    print("3. Restart the application")


if __name__ == "__main__":
    main()
