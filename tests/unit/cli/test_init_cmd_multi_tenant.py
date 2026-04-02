# -*- coding: utf-8 -*-
"""Unit tests for tenant-aware CLI init command.

Tests that `copaw init --tenant-id <id>` writes config to the correct
tenant directory structure, and that backward compatibility is preserved.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest
from click.testing import CliRunner
from copaw.cli.init_cmd import init_cmd


def test_init_cmd_writes_to_tenant_directory(tmp_path, monkeypatch):
    """Test that --tenant-id writes config to tenant-specific directory."""
    # Patch WORKING_DIR to use tmp_path
    monkeypatch.setattr("copaw.cli.init_cmd.WORKING_DIR", tmp_path)
    monkeypatch.setattr("copaw.constant.WORKING_DIR", tmp_path)

    # Mock ProviderManager to avoid side effects
    class MockProviderManager:
        _instance = None

        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def get_instance(cls):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

        def get_active_provider(self):
            return None

        def get_active_model(self):
            return None

    monkeypatch.setattr(
        "copaw.cli.init_cmd.ProviderManager",
        MockProviderManager,
    )

    runner = CliRunner()

    result = runner.invoke(
        init_cmd,
        ["--defaults", "--accept-security", "--tenant-id", "tenant-acme"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "tenant-acme" / "config.json").exists()
    assert (tmp_path / "tenant-acme" / "HEARTBEAT.md").exists()
    assert (tmp_path / "tenant-acme" / "workspaces" / "default").is_dir()


def test_init_cmd_defaults_tenant_id_to_default(tmp_path, monkeypatch):
    """Test that init without --tenant-id defaults to 'default' tenant."""
    # Patch WORKING_DIR to use tmp_path
    monkeypatch.setattr("copaw.cli.init_cmd.WORKING_DIR", tmp_path)
    monkeypatch.setattr("copaw.constant.WORKING_DIR", tmp_path)

    # Mock ProviderManager to avoid side effects
    class MockProviderManager:
        _instance = None

        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def get_instance(cls):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

        def get_active_provider(self):
            return None

        def get_active_model(self):
            return None

    monkeypatch.setattr(
        "copaw.cli.init_cmd.ProviderManager",
        MockProviderManager,
    )

    runner = CliRunner()

    result = runner.invoke(init_cmd, ["--defaults", "--accept-security"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "default" / "config.json").exists()
    # Ensure old flat structure is NOT created
    assert not (tmp_path / "config.json").exists()
