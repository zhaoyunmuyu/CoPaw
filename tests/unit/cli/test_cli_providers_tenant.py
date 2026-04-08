# -*- coding: utf-8 -*-
# flake8: noqa: E402
# pylint: disable=wrong-import-position,unused-variable
"""Tests for CLI providers tenant support."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from swe.cli.providers_cmd import models_group


class TestCLITenantIdOption:
    """Tests for --tenant-id option support."""

    def test_tenant_id_option_is_recognized(self):
        """--tenant-id option is recognized by CLI."""
        runner = CliRunner()

        # Test with list command - should not error on unknown option
        with patch(
            "swe.cli.providers_cmd._all_provider_objects",
            return_value=[],
        ):
            with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm:
                mock_manager = MagicMock()
                mock_manager.get_active_model.return_value = None
                mock_pm.get_instance.return_value = mock_manager

                result = runner.invoke(
                    models_group,
                    ["--tenant-id", "tenant-a", "list"],
                )

        # Should not fail due to unknown option
        assert "no such option" not in result.output.lower()

    def test_tenant_id_short_form_is_recognized(self):
        """-t short form is recognized."""
        runner = CliRunner()

        with patch(
            "swe.cli.providers_cmd._all_provider_objects",
            return_value=[],
        ):
            with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm:
                mock_manager = MagicMock()
                mock_manager.get_active_model.return_value = None
                mock_pm.get_instance.return_value = mock_manager

                result = runner.invoke(
                    models_group,
                    ["-t", "tenant-a", "list"],
                )

        assert "no such option" not in result.output.lower()


class TestCLITenantProviderManager:
    """Tests for tenant-specific ProviderManager usage."""

    def test_list_uses_tenant_specific_manager(self):
        """list command uses tenant-specific ProviderManager."""
        runner = CliRunner()

        with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.get_active_model.return_value = None
            mock_pm_class.get_instance.return_value = mock_manager

            with patch(
                "swe.cli.providers_cmd._all_provider_objects",
                return_value=[],
            ):
                result = runner.invoke(
                    models_group,
                    ["--tenant-id", "tenant-a", "list"],
                )

            # Verify get_instance was called with tenant-a
            mock_pm_class.get_instance.assert_called_with("tenant-a")

    def test_list_uses_default_when_no_tenant(self):
        """list command uses default tenant when no --tenant-id."""
        runner = CliRunner()

        with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.get_active_model.return_value = None
            mock_pm_class.get_instance.return_value = mock_manager

            with patch(
                "swe.cli.providers_cmd._all_provider_objects",
                return_value=[],
            ):
                result = runner.invoke(models_group, ["list"])

            # Verify get_instance was called with None (which uses default)
            mock_pm_class.get_instance.assert_called_with(None)

    def test_add_provider_uses_tenant_specific_manager(self):
        """add-provider command uses tenant-specific ProviderManager."""
        runner = CliRunner()

        with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.add_custom_provider = AsyncMock(
                return_value=MagicMock(id="test-provider"),
            )
            mock_pm_class.get_instance.return_value = mock_manager

            result = runner.invoke(
                models_group,
                [
                    "--tenant-id",
                    "tenant-b",
                    "add-provider",
                    "test-provider",
                    "--name",
                    "Test Provider",
                    "--base-url",
                    "https://test.example/v1",
                ],
            )

            # Verify get_instance was called with tenant-b
            mock_pm_class.get_instance.assert_called_with("tenant-b")

    def test_remove_provider_uses_tenant_specific_manager(self):
        """remove-provider command uses tenant-specific ProviderManager."""
        runner = CliRunner()

        with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.builtin_providers = {"openai", "anthropic"}
            mock_manager.remove_custom_provider.return_value = True
            mock_pm_class.get_instance.return_value = mock_manager

            result = runner.invoke(
                models_group,
                [
                    "--tenant-id",
                    "tenant-c",
                    "remove-provider",
                    "custom-provider",
                    "--yes",
                ],
            )

            # Verify get_instance was called with tenant-c
            mock_pm_class.get_instance.assert_called_with("tenant-c")

    def test_add_model_uses_tenant_specific_manager(self):
        """add-model command uses tenant-specific ProviderManager."""
        runner = CliRunner()

        with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm_class:
            mock_manager = MagicMock()
            mock_provider = MagicMock()
            mock_provider.add_model = AsyncMock(return_value=(True, ""))
            mock_manager.get_provider.return_value = mock_provider
            mock_pm_class.get_instance.return_value = mock_manager

            result = runner.invoke(
                models_group,
                [
                    "--tenant-id",
                    "tenant-d",
                    "add-model",
                    "openai",
                    "--model-id",
                    "gpt-4",
                    "--model-name",
                    "GPT-4",
                ],
            )

            # Verify get_instance was called with tenant-d
            mock_pm_class.get_instance.assert_called_with("tenant-d")

    def test_remove_model_uses_tenant_specific_manager(self):
        """remove-model command uses tenant-specific ProviderManager."""
        runner = CliRunner()

        with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm_class:
            mock_manager = MagicMock()
            mock_provider = MagicMock()
            mock_provider.delete_model = AsyncMock(return_value=(True, ""))
            mock_manager.get_provider.return_value = mock_provider
            mock_pm_class.get_instance.return_value = mock_manager

            result = runner.invoke(
                models_group,
                [
                    "--tenant-id",
                    "tenant-e",
                    "remove-model",
                    "openai",
                    "--model-id",
                    "gpt-4",
                ],
            )

            # Verify get_instance was called with tenant-e
            mock_pm_class.get_instance.assert_called_with("tenant-e")


class TestCLITenantIsolation:
    """Tests for tenant isolation in CLI commands."""

    def test_different_tenants_get_different_managers(self):
        """Different tenants get different ProviderManager instances."""
        runner = CliRunner()

        with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm_class:
            mock_manager_a = MagicMock()
            mock_manager_a.get_active_model.return_value = None
            mock_manager_b = MagicMock()
            mock_manager_b.get_active_model.return_value = None

            # Return different managers for different tenants
            def get_instance(tenant_id):
                if tenant_id == "tenant-a":
                    return mock_manager_a
                return mock_manager_b

            mock_pm_class.get_instance.side_effect = get_instance

            with patch(
                "swe.cli.providers_cmd._all_provider_objects",
                return_value=[],
            ):
                # Call for tenant-a
                runner.invoke(
                    models_group,
                    ["--tenant-id", "tenant-a", "list"],
                )
                # Call for tenant-b
                runner.invoke(
                    models_group,
                    ["--tenant-id", "tenant-b", "list"],
                )

            # Verify get_instance was called with different tenants
            assert mock_pm_class.get_instance.call_count == 2
            calls = [
                call.args[0]
                for call in mock_pm_class.get_instance.call_args_list
            ]
            assert "tenant-a" in calls
            assert "tenant-b" in calls


class TestCLIBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_commands_work_without_tenant_id(self):
        """Commands work without --tenant-id for backward compatibility."""
        runner = CliRunner()

        with patch("swe.cli.providers_cmd.ProviderManager") as mock_pm_class:
            mock_manager = MagicMock()
            mock_manager.get_active_model.return_value = None
            mock_pm_class.get_instance.return_value = mock_manager

            with patch(
                "swe.cli.providers_cmd._all_provider_objects",
                return_value=[],
            ):
                result = runner.invoke(models_group, ["list"])

            # Should succeed without --tenant-id
            assert result.exit_code == 0
            # Should use default tenant (None passed to get_instance)
            mock_pm_class.get_instance.assert_called_with(None)


class TestCLIHelpDocumentation:
    """Tests for CLI help documentation."""

    def test_tenant_id_in_help(self):
        """--tenant-id is documented in help."""
        runner = CliRunner()
        result = runner.invoke(models_group, ["--help"])

        assert result.exit_code == 0
        assert "--tenant-id" in result.output or "-t" in result.output
        assert (
            "Tenant ID" in result.output or "tenant" in result.output.lower()
        )
