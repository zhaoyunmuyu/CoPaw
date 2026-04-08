#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-position,f-string-without-interpolation,too-many-branches,too-many-statements
"""Migration script for provider configuration from global to tenant-isolated storage.

This script migrates existing global provider configuration from:
    ~/.swe.secret/providers/

To the new tenant-isolated structure:
    ~/.swe.secret/default/providers/

Usage:
    python scripts/migrate_provider_config.py [--dry-run]

Options:
    --dry-run  Show what would be done without making changes
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from swe.constant import SECRET_DIR


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def check_migration_needed() -> tuple[bool, Path, Path]:
    """Check if migration is needed.

    Returns:
        Tuple of (needs_migration, old_providers_dir, new_providers_dir)
    """
    old_providers_dir = SECRET_DIR / "providers"
    default_tenant_dir = SECRET_DIR / "default"
    new_providers_dir = default_tenant_dir / "providers"

    # Check if old global directory exists and has content
    old_exists = old_providers_dir.exists() and old_providers_dir.is_dir()

    # Check if new tenant-isolated directory already exists
    new_exists = new_providers_dir.exists()

    # Migration is needed if:
    # 1. Old directory exists AND
    # 2. New directory does not exist (or is empty)
    needs_migration = old_exists and not new_exists

    return needs_migration, old_providers_dir, new_providers_dir


def create_backup(source_dir: Path) -> Path:
    """Create a timestamped backup of the source directory.

    Args:
        source_dir: Directory to backup

    Returns:
        Path to the backup directory
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = source_dir.parent / f"{source_dir.name}.backup.{timestamp}"

    logger.info(f"Creating backup at: {backup_dir}")
    shutil.copytree(source_dir, backup_dir)
    logger.info(f"Backup created successfully")

    return backup_dir


def perform_migration(
    old_dir: Path,
    new_dir: Path,
    dry_run: bool = False,
) -> bool:
    """Perform the migration from global to tenant-isolated storage.

    Args:
        old_dir: Global providers directory
        new_dir: Tenant-isolated providers directory
        dry_run: If True, only show what would be done

    Returns:
        True if migration succeeded, False otherwise
    """
    try:
        # Step 1: Create backup
        if not dry_run:
            backup_dir = create_backup(old_dir)
            logger.info(f"Backup location: {backup_dir}")
        else:
            logger.info("[DRY RUN] Would create backup")

        # Step 2: Create new directory structure
        logger.info(f"Creating new directory: {new_dir}")
        if not dry_run:
            new_dir.mkdir(parents=True, exist_ok=True)

        # Step 3: Copy all configuration files
        logger.info(f"Copying configuration from {old_dir} to {new_dir}")
        for item in old_dir.iterdir():
            target = new_dir / item.name
            if dry_run:
                logger.info(f"[DRY RUN] Would copy: {item.name}")
            else:
                if item.is_file():
                    shutil.copy2(item, target)
                    logger.debug(f"Copied file: {item.name}")
                elif item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                    logger.debug(f"Copied directory: {item.name}")

        # Step 4: Verify migration
        if not dry_run:
            logger.info("Verifying migration...")
            if not new_dir.exists():
                logger.error(
                    "Migration verification failed: new directory does not exist",
                )
                return False

            # Check that expected files exist
            old_files = set(f.name for f in old_dir.rglob("*") if f.is_file())
            new_files = set(f.name for f in new_dir.rglob("*") if f.is_file())

            if old_files != new_files:
                missing = old_files - new_files
                logger.error(
                    f"Migration verification failed: missing files: {missing}",
                )
                return False

            logger.info("Migration verification passed")

        # Step 5: Remove old directory (only after successful verification)
        if not dry_run:
            logger.info(f"Removing old directory: {old_dir}")
            shutil.rmtree(old_dir)
            logger.info("Old directory removed successfully")
        else:
            logger.info(f"[DRY RUN] Would remove old directory: {old_dir}")

        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False


def rollback_migration(backup_dir: Path, new_dir: Path) -> bool:
    """Rollback migration by restoring from backup.

    Args:
        backup_dir: Backup directory to restore from
        new_dir: New directory to remove

    Returns:
        True if rollback succeeded, False otherwise
    """
    try:
        logger.warning("Starting rollback...")

        # Remove new directory if it exists
        if new_dir.exists():
            logger.info(f"Removing incomplete new directory: {new_dir}")
            shutil.rmtree(new_dir)

        # Restore from backup
        old_dir = backup_dir.parent / "providers"
        logger.info(f"Restoring from backup: {backup_dir} -> {old_dir}")
        shutil.copytree(backup_dir, old_dir)

        logger.info("Rollback completed successfully")
        return True

    except Exception as e:
        logger.error(f"Rollback failed: {e}", exc_info=True)
        return False


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Migrate provider configuration from global to tenant-isolated storage",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--rollback",
        metavar="BACKUP_DIR",
        help="Rollback migration from backup directory",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    logger.info("=" * 60)
    logger.info("Provider Configuration Migration Tool")
    logger.info("=" * 60)

    # Handle rollback
    if args.rollback:
        backup_path = Path(args.rollback)
        if not backup_path.exists():
            logger.error(f"Backup directory not found: {backup_path}")
            return 1

        new_dir = SECRET_DIR / "default" / "providers"
        if rollback_migration(backup_path, new_dir):
            logger.info("Rollback completed successfully")
            return 0
        else:
            logger.error("Rollback failed")
            return 1

    # Check if migration is needed
    needs_migration, old_dir, new_dir = check_migration_needed()

    if not needs_migration:
        logger.info("No migration needed.")

        # Provide helpful information
        if old_dir.exists():
            logger.info(f"Old global directory exists: {old_dir}")
        if new_dir.exists():
            logger.info(
                f"New tenant-isolated directory already exists: {new_dir}",
            )
            logger.info("Migration appears to have already been completed.")

        return 0

    logger.info(f"Migration needed:")
    logger.info(f"  From: {old_dir}")
    logger.info(f"  To: {new_dir}")

    if args.dry_run:
        logger.info("[DRY RUN MODE - No changes will be made]")

    # Perform migration
    if perform_migration(old_dir, new_dir, dry_run=args.dry_run):
        if args.dry_run:
            logger.info("[DRY RUN] Migration would succeed")
        else:
            logger.info("=" * 60)
            logger.info("Migration completed successfully!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Your provider configuration has been migrated to:")
            logger.info(f"  {new_dir}")
            logger.info("")
            logger.info("A backup was created at:")
            logger.info(f"  {old_dir}.backup.<timestamp>/")
            logger.info("")
            logger.info("To rollback if needed, run:")
            logger.info(
                f"  python scripts/migrate_provider_config.py --rollback <backup_dir>",
            )
        return 0
    else:
        logger.error("=" * 60)
        logger.error("Migration failed!")
        logger.error("=" * 60)
        logger.error("")
        logger.error("Your original configuration should be intact.")
        logger.error("Check the logs above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
