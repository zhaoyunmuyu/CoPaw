# -*- coding: utf-8 -*-
# pylint: disable=unused-variable,unused-argument,unused-import
"""Tests for provider config migration script."""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest


class TestMigrationCheck:
    """Tests for migration needed check."""

    def test_migration_needed_when_old_exists_and_new_doesnt(self, tmp_path):
        """Migration needed when old providers dir exists and new doesn't."""
        from scripts.migrate_provider_config import check_migration_needed

        # Create old global providers dir
        old_dir = tmp_path / "providers"
        old_dir.mkdir()
        (old_dir / "test.json").write_text("{}")

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            needs, old, new = check_migration_needed()

        assert needs is True
        assert old == tmp_path / "providers"
        assert new == tmp_path / "default" / "providers"

    def test_migration_not_needed_when_new_exists(self, tmp_path):
        """Migration not needed when new tenant-isolated dir exists."""
        from scripts.migrate_provider_config import check_migration_needed

        # Create new tenant-isolated dir
        new_dir = tmp_path / "default" / "providers"
        new_dir.mkdir(parents=True)

        # Also create old (should be ignored)
        old_dir = tmp_path / "providers"
        old_dir.mkdir()

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            needs, old, new = check_migration_needed()

        assert needs is False

    def test_migration_not_needed_when_old_doesnt_exist(self, tmp_path):
        """Migration not needed when old global dir doesn't exist."""
        from scripts.migrate_provider_config import check_migration_needed

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            needs, old, new = check_migration_needed()

        assert needs is False


class TestBackupCreation:
    """Tests for backup creation."""

    def test_backup_created_with_timestamp(self, tmp_path):
        """Backup is created with timestamp in name."""
        from scripts.migrate_provider_config import create_backup

        source = tmp_path / "providers"
        source.mkdir()
        (source / "config.json").write_text("{}")

        backup = create_backup(source)

        assert backup.exists()
        assert "backup" in backup.name
        assert (backup / "config.json").exists()


class TestMigrationPerform:
    """Tests for migration execution."""

    def test_migration_copies_all_files(self, tmp_path):
        """Migration copies all config files."""
        from scripts.migrate_provider_config import perform_migration

        # Create old structure
        old_dir = tmp_path / "providers"
        old_dir.mkdir()
        builtin_dir = old_dir / "builtin"
        builtin_dir.mkdir()
        custom_dir = old_dir / "custom"
        custom_dir.mkdir()

        (builtin_dir / "openai.json").write_text(json.dumps({"id": "openai"}))
        (custom_dir / "custom.json").write_text(json.dumps({"id": "custom"}))
        (old_dir / "active_model.json").write_text(
            json.dumps({"model": "gpt-4"}),
        )

        new_dir = tmp_path / "default" / "providers"

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            result = perform_migration(old_dir, new_dir, dry_run=False)

        assert result is True
        assert new_dir.exists()
        assert (new_dir / "builtin" / "openai.json").exists()
        assert (new_dir / "custom" / "custom.json").exists()
        assert (new_dir / "active_model.json").exists()

    def test_migration_removes_old_directory(self, tmp_path):
        """Old directory is removed after migration."""
        from scripts.migrate_provider_config import perform_migration

        old_dir = tmp_path / "providers"
        old_dir.mkdir()
        (old_dir / "file.json").write_text("{}")

        new_dir = tmp_path / "default" / "providers"

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            result = perform_migration(old_dir, new_dir, dry_run=False)

        assert result is True
        assert not old_dir.exists()

    def test_dry_run_does_not_modify(self, tmp_path):
        """Dry run doesn't make changes."""
        from scripts.migrate_provider_config import perform_migration

        old_dir = tmp_path / "providers"
        old_dir.mkdir()
        (old_dir / "file.json").write_text("{}")

        new_dir = tmp_path / "default" / "providers"

        result = perform_migration(old_dir, new_dir, dry_run=True)

        assert result is True
        assert old_dir.exists()  # Not removed
        assert not new_dir.exists()  # Not created

    def test_migration_verifies_content(self, tmp_path):
        """Migration verifies content was copied correctly."""
        from scripts.migrate_provider_config import perform_migration

        old_dir = tmp_path / "providers"
        old_dir.mkdir()
        (old_dir / "config.json").write_text('{"key": "value"}')

        new_dir = tmp_path / "default" / "providers"

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            result = perform_migration(old_dir, new_dir, dry_run=False)

        assert result is True
        content = (new_dir / "config.json").read_text()
        assert json.loads(content) == {"key": "value"}


class TestRollback:
    """Tests for rollback functionality."""

    def test_rollback_restores_from_backup(self, tmp_path):
        """Rollback restores original from backup."""
        from scripts.migrate_provider_config import rollback_migration

        # Create backup
        backup = tmp_path / "providers.backup.20240101_120000"
        backup.mkdir()
        (backup / "config.json").write_text('{"original": true}')

        # Create new (simulating partial migration)
        new_dir = tmp_path / "default" / "providers"
        new_dir.mkdir(parents=True)
        (new_dir / "new.json").write_text("{}")

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            result = rollback_migration(backup, new_dir)

        assert result is True
        assert not new_dir.exists()
        restored = tmp_path / "providers"
        assert restored.exists()
        assert (restored / "config.json").exists()


class TestMainFunction:
    """Tests for main entry point."""

    def test_main_returns_0_when_no_migration_needed(self, tmp_path, caplog):
        """Exit code 0 when no migration needed."""
        from scripts.migrate_provider_config import main

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            with patch("sys.argv", ["migrate_provider_config.py"]):
                result = main()

        assert result == 0

    def test_main_returns_1_on_failure(self, tmp_path):
        """Exit code 1 when migration fails."""
        from scripts.migrate_provider_config import main

        # Create old dir
        old_dir = tmp_path / "providers"
        old_dir.mkdir()

        # Make new dir read-only to cause failure
        new_parent = tmp_path / "default"
        new_parent.mkdir()
        new_parent.chmod(0o555)

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            with patch("sys.argv", ["migrate_provider_config.py"]):
                result = main()

        # Restore permissions for cleanup
        new_parent.chmod(0o755)
        assert result == 1

    def test_main_dry_run_reports_success(self, tmp_path, caplog):
        """Dry run reports success without changes."""
        from scripts.migrate_provider_config import main

        # Create old dir
        old_dir = tmp_path / "providers"
        old_dir.mkdir()
        (old_dir / "config.json").write_text("{}")

        with patch("scripts.migrate_provider_config.SECRET_DIR", tmp_path):
            with patch(
                "sys.argv",
                ["migrate_provider_config.py", "--dry-run"],
            ):
                result = main()

        assert result == 0
        assert old_dir.exists()  # Still exists
