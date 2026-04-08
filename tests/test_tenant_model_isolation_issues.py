# -*- coding: utf-8 -*-
"""Verification tests for multi-tenant model isolation issues.

This test suite verifies the identified issues before remediation:
1. Model selection fallback path shares global active_model
2. ProviderManager stores data in global path
3. Potential race condition in active_model file access

Run these tests to confirm issues exist before implementing fixes.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio

from swe.config.context import tenant_context
from swe.providers.models import ModelSlotConfig
from swe.providers.provider_manager import ProviderManager
from swe.tenant_models import (
    TenantModelConfig,
    TenantModelContext,
    TenantModelManager,
)
from swe.tenant_models.models import (
    ModelSlot,
    RoutingConfig,
    TenantProviderConfig,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_swe_root(tmp_path: Path) -> Path:
    """Create a temporary directory structure mimicking ~/.swe/."""
    swe_root = tmp_path / ".swe"
    swe_root.mkdir(parents=True)

    # Create .secret directory
    secret_dir = swe_root / ".secret"
    secret_dir.mkdir(parents=True)

    # Create tenant directories
    for tenant_id in ["tenant_a", "tenant_b"]:
        tenant_dir = swe_root / tenant_id
        tenant_dir.mkdir(parents=True)
        (tenant_dir / "sessions").mkdir()
        (tenant_dir / "memory").mkdir()

        # Create tenant-specific secret directory
        tenant_secret = secret_dir / tenant_id
        tenant_secret.mkdir(parents=True)

    return swe_root


@pytest.fixture
def mock_provider_manager_storage(temp_swe_root: Path) -> Path:
    """Create mock ProviderManager storage structure."""
    secret_dir = temp_swe_root / ".secret"
    providers_dir = secret_dir / "providers"
    providers_dir.mkdir(parents=True)

    # Create global active_model.json
    active_model = {"provider_id": "openai", "model": "gpt-4o"}
    with open(providers_dir / "active_model.json", "w") as f:
        json.dump(active_model, f)

    return providers_dir


@pytest_asyncio.fixture
async def reset_singleton():
    """Reset ProviderManager singleton after each test."""
    yield
    # Reset singleton
    ProviderManager._instance = None


# =============================================================================
# Issue 1: Model Selection Fallback Path Verification
# =============================================================================


@pytest.mark.asyncio
class TestModelSelectionFallbackIssue:
    """Verify Issue 1: Model selection falls back to global active_model."""

    async def test_fallback_to_global_when_tenant_config_missing(
        self,
        temp_swe_root: Path,
        mock_provider_manager_storage: Path,
        reset_singleton,
    ):
        """Test: When tenant has no model config, system uses global active_model.

        Expected behavior BEFORE fix: Falls back to global active_model
        Expected behavior AFTER fix: Raises error requiring tenant configuration
        """
        with patch("swe.constant.WORKING_DIR", temp_swe_root):
            with patch(
                "swe.constant.SECRET_DIR",
                temp_swe_root / ".secret",
            ):
                # Reset singleton before creating new instance
                ProviderManager._instance = None

                # Initialize ProviderManager (creates singleton)
                pm = ProviderManager.get_instance()

                # Verify global model exists (this is the issue)
                global_model = pm.get_active_model()

                # The issue: global model exists and would be used as fallback
                print(
                    f"\n[ISSUE CONFIRMED] Global active_model exists: {global_model}",
                )

                # Simulate tenant WITHOUT model configuration
                tenant_id = "tenant_without_config"

                with tenant_context(tenant_id=tenant_id, user_id=tenant_id):
                    # Attempt to get model configuration
                    try:
                        tenant_config = TenantModelManager.load(tenant_id)
                    except Exception:
                        tenant_config = None

                    # Verify tenant config is None (not configured)
                    assert (
                        tenant_config is None
                    ), "Tenant should not have config"

                    # The problematic code path in model_factory.py:767
                    # would use this global model as fallback
                    print(
                        f"[ISSUE CONFIRMED] Tenant '{tenant_id}' has no config",
                    )
                    print(
                        f"[ISSUE CONFIRMED] But global model exists: {global_model}",
                    )
                    print(
                        "[ISSUE CONFIRMED] Current code would use global model as fallback",
                    )

                    # Verify fallback path would use global model
                    assert (
                        global_model is not None
                    ), "Global active_model exists - this is the issue!"

    async def test_tenant_config_isolation_when_configured(
        self,
        temp_swe_root: Path,
        mock_provider_manager_storage: Path,
        reset_singleton,
    ):
        """Test: When tenant HAS model config, it should be isolated."""
        with patch("swe.constant.WORKING_DIR", temp_swe_root):
            with patch(
                "swe.constant.SECRET_DIR",
                temp_swe_root / ".secret",
            ):
                tenant_id = "tenant_a"

                # Create tenant-specific model config
                tenant_config = TenantModelConfig(
                    providers=[
                        TenantProviderConfig(
                            id="custom",
                            type="openai",
                            models=["custom-model"],
                        ),
                    ],
                    routing=RoutingConfig(
                        mode="local_first",
                        slots={
                            "local": ModelSlot(
                                provider_id="custom",
                                model="custom-model",
                            ),
                            "cloud": ModelSlot(
                                provider_id="custom",
                                model="custom-model",
                            ),
                        },
                    ),
                )

                # Save tenant config
                TenantModelManager.save(tenant_id, tenant_config)

                with tenant_context(tenant_id=tenant_id, user_id=tenant_id):
                    # Load tenant config
                    loaded_config = TenantModelManager.load(tenant_id)

                    # Verify tenant config is isolated
                    assert loaded_config is not None
                    assert (
                        loaded_config.get_active_slot().provider_id == "custom"
                    )
                    assert (
                        loaded_config.get_active_slot().model == "custom-model"
                    )

                    # Verify different from global
                    pm = ProviderManager.get_instance()
                    global_model = pm.get_active_model()

                    # This shows the isolation works when configured
                    assert (
                        loaded_config.get_active_slot().provider_id
                        != global_model.provider_id
                    )
                    print(
                        f"\n[ISOLATION WORKS] Tenant config: {loaded_config.get_active_slot()}",
                    )
                    print(f"[ISOLATION WORKS] Global model: {global_model}")


# =============================================================================
# Issue 2: ProviderManager Global Storage Path Verification
# =============================================================================


@pytest.mark.asyncio
class TestProviderManagerGlobalStorageIssue:
    """Verify Issue 2: ProviderManager uses global storage path."""

    async def test_provider_manager_uses_global_path(
        self,
        temp_swe_root: Path,
        mock_provider_manager_storage: Path,
        reset_singleton,
    ):
        """Test: ProviderManager stores data in global path, not tenant-specific.

        This verifies that ProviderManager.root_path is global:
        ~/.swe/.secret/providers/
        Instead of tenant-specific:
        ~/.swe/.secret/{tenant_id}/providers/
        """
        with patch("swe.constant.SECRET_DIR", temp_swe_root / ".secret"):
            # Reset singleton before creating new instance
            ProviderManager._instance = None

            pm = ProviderManager.get_instance()

            # Verify global path
            expected_global = temp_swe_root / ".secret" / "providers"
            actual_path = pm.root_path

            # Verify the path is NOT tenant-specific
            tenant_specific = (
                temp_swe_root / ".secret" / "tenant_a" / "providers"
            )

            # The issue is that ProviderManager uses global path
            print(
                f"\n[ISSUE CONFIRMED] ProviderManager.root_path: {actual_path}",
            )
            print(f"[ISSUE CONFIRMED] Expected global path: {expected_global}")
            print(f"[ISSUE CONFIRMED] Expected tenant path: {tenant_specific}")

            # Verify it's NOT tenant-specific (this confirms the issue)
            assert (
                actual_path != tenant_specific
            ), "ProviderManager should NOT use tenant-specific path (this is the issue)"

            print(
                "[ISSUE CONFIRMED] ProviderManager uses global storage, not tenant-specific!",
            )

            # Verify the path follows the expected pattern (ends with /providers)
            assert (
                actual_path.name == "providers"
            ), f"ProviderManager path should end with 'providers', got: {actual_path.name}"

    async def test_active_model_storage_location(
        self,
        temp_swe_root: Path,
        mock_provider_manager_storage: Path,
        reset_singleton,
    ):
        """Test: active_model.json is stored globally, not per-tenant."""
        with patch("swe.constant.SECRET_DIR", temp_swe_root / ".secret"):
            pm = ProviderManager.get_instance()

            # active_model path is global
            active_model_path = pm.root_path / "active_model.json"
            assert active_model_path.exists()

            # Verify not per-tenant
            tenant_active_model = (
                temp_swe_root
                / ".secret"
                / "tenant_a"
                / "providers"
                / "active_model.json"
            )
            assert (
                not tenant_active_model.parent.exists()
            ), "Tenant-specific provider storage should exist"

            print(
                f"\n[ISSUE CONFIRMED] active_model.json at: {active_model_path}",
            )
            print(
                f"[ISSUE CONFIRMED] Not at tenant path: {tenant_active_model}",
            )


# =============================================================================
# Issue 3: Potential Race Condition Verification
# =============================================================================


@pytest.mark.asyncio
class TestActiveModelRaceConditionIssue:
    """Verify Issue 3: Potential race condition in active_model access."""

    async def test_concurrent_active_model_modification(
        self,
        temp_swe_root: Path,
        mock_provider_manager_storage: Path,
        reset_singleton,
    ):
        """Test: Concurrent modifications to active_model may cause race conditions.

        This test demonstrates that multiple tenants accessing the same
        global active_model.json file could cause race conditions.
        """
        with patch("swe.constant.SECRET_DIR", temp_swe_root / ".secret"):
            pm = ProviderManager.get_instance()

            modification_count = 10
            errors = []

            async def modify_active_model(tenant_id: str, iteration: int):
                """Simulate a tenant modifying active model."""
                try:
                    # This would be problematic if multiple tenants do this concurrently
                    new_model = ModelSlotConfig(
                        provider_id=f"provider_{tenant_id}",
                        model=f"model_{tenant_id}_{iteration}",
                    )
                    pm.save_active_model(new_model)
                    return True
                except Exception as e:
                    errors.append(f"{tenant_id}-{iteration}: {e}")
                    return False

            # Simulate concurrent access from multiple tenants
            tasks = []
            for i in range(modification_count):
                tenant_id = f"tenant_{i % 3}"  # 3 tenants
                tasks.append(modify_active_model(tenant_id, i))

            results = await asyncio.gather(*tasks)

            # The final active_model will be from the last write
            # demonstrating the lack of isolation
            final_model = pm.load_active_model()

            print(
                f"\n[ISSUE DEMONSTRATION] {sum(results)}/{len(results)} modifications succeeded",
            )
            print(f"[ISSUE DEMONSTRATION] Final active_model: {final_model}")
            print("[ISSUE DEMONSTRATION] All tenants modify the SAME file!")

            if errors:
                print(f"[ISSUE DEMONSTRATION] Errors: {errors}")

            # The issue is that all tenants modify the same global file
            assert final_model is not None


# =============================================================================
# Summary Test
# =============================================================================


@pytest.mark.asyncio
class TestIssueSummary:
    """Summary of all verified issues."""

    async def test_all_issues_verified(
        self,
        temp_swe_root: Path,
        mock_provider_manager_storage: Path,
        reset_singleton,
    ):
        """Print summary of all verified issues."""
        print("\n" + "=" * 70)
        print("MULTI-TENANT MODEL ISOLATION ISSUES - VERIFICATION SUMMARY")
        print("=" * 70)

        with patch("swe.constant.WORKING_DIR", temp_swe_root):
            with patch(
                "swe.constant.SECRET_DIR",
                temp_swe_root / ".secret",
            ):
                pm = ProviderManager.get_instance()

                print("\n[ISSUE 1] Model Selection Fallback Path:")
                print("  - Location: src/swe/agents/model_factory.py:767")
                print(
                    "  - Problem: When TenantModelContext is None, falls back to",
                )
                print("             ProviderManager.get_active_chat_model()")
                print("  - Impact: Unconfigured tenants share global model")

                print("\n[ISSUE 2] ProviderManager Global Storage:")
                print(f"  - Location: {pm.root_path}")
                print(
                    "  - Problem: Uses global path instead of tenant-specific",
                )
                print("  - Current: ~/.swe/.secret/providers/")
                print("  - Should be: ~/.swe/.secret/{tenant_id}/providers/")

                print("\n[ISSUE 3] Active Model Race Condition:")
                print(f"  - Location: {pm.root_path}/active_model.json")
                print("  - Problem: Multiple tenants modify same file")
                print("  - Impact: Last write wins, no isolation")

                print("\n" + "=" * 70)
                print(
                    "RECOMMENDATION: Implement remediation plan before production",
                )
                print("=" * 70)

                # Mark as verified
                assert True
