#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Execute featured case table migration."""

import asyncio
import os
import sys

from swe.database.config import get_database_config
from swe.database.connection import DatabaseConnection

# Add project path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


async def _safe_execute_with_duplicate_check(
    db: DatabaseConnection,
    sql: str,
    action_name: str,
    duplicate_keyword: str = "Duplicate",
) -> bool:
    """Execute SQL and handle duplicate errors gracefully."""
    try:
        await db.execute(sql)
        print(f"{action_name} completed")
        return True
    except Exception as e:
        error_str = str(e)
        if duplicate_keyword in error_str:
            print(f"{action_name} already exists, skipping")
            return False
        print(f"Error: {action_name} - {e}")
        return False


async def _add_columns(db: DatabaseConnection) -> None:
    """Step 1: Add new columns to swe_featured_case table."""
    print("\n=== Step 1: Adding new columns ===")

    await _safe_execute_with_duplicate_check(
        db,
        """
        ALTER TABLE `swe_featured_case`
        ADD COLUMN `source_id` VARCHAR(64) NOT NULL DEFAULT 'default' COMMENT '来源ID' AFTER `id`
        """,
        "Added source_id column",
        "Duplicate column",
    )

    await _safe_execute_with_duplicate_check(
        db,
        """
        ALTER TABLE `swe_featured_case`
        ADD COLUMN `bbk_id` VARCHAR(64) DEFAULT NULL COMMENT 'BBK ID' AFTER `source_id`
        """,
        "Added bbk_id column",
        "Duplicate column",
    )

    await _safe_execute_with_duplicate_check(
        db,
        """
        ALTER TABLE `swe_featured_case`
        ADD COLUMN `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序序号' AFTER `steps`
        """,
        "Added sort_order column",
        "Duplicate column",
    )


async def _migrate_config_data(db: DatabaseConnection) -> None:
    """Step 2: Migrate data from config table."""
    print("\n=== Step 2: Migrating data from config table ===")
    try:
        result = await db.execute(
            """
            UPDATE `swe_featured_case` c
            JOIN `swe_featured_case_config` cc ON c.case_id = cc.case_id
            SET c.source_id = cc.source_id,
                c.bbk_id = cc.bbk_id,
                c.sort_order = cc.sort_order
            WHERE cc.is_active = 1
            """,
        )
        print(f"Migrated {result} rows from config table")
    except Exception as e:
        print(f"Config table migration skipped: {e}")


async def _update_indexes(db: DatabaseConnection) -> None:
    """Step 3: Update indexes on swe_featured_case table."""
    print("\n=== Step 3: Updating indexes ===")

    # Drop old unique key
    try:
        await db.execute(
            "ALTER TABLE `swe_featured_case` DROP INDEX `uk_case_id`",
        )
        print("Dropped old unique key uk_case_id")
    except Exception as e:
        error_str = str(e)
        if (
            "check that column/key exists" in error_str
            or "Unknown index" in error_str
        ):
            print("uk_case_id index not found, skipping")
        else:
            print(f"Error dropping uk_case_id: {e}")

    # Add new unique key
    await _safe_execute_with_duplicate_check(
        db,
        """
        ALTER TABLE `swe_featured_case`
        ADD UNIQUE KEY `uk_source_bbk_case` (`source_id`, `bbk_id`, `case_id`)
        """,
        "Added new unique key uk_source_bbk_case",
        "Duplicate key name",
    )

    # Add index
    await _safe_execute_with_duplicate_check(
        db,
        "ALTER TABLE `swe_featured_case` ADD INDEX `idx_source_bbk` (`source_id`, `bbk_id`)",
        "Added index idx_source_bbk",
        "Duplicate key name",
    )


async def _verify_table_structure(db: DatabaseConnection) -> None:
    """Verify final table structure after migration."""
    print("\n=== Verification ===")
    try:
        rows = await db.fetch_all("DESCRIBE `swe_featured_case`")
        print("Table structure after migration:")
        for row in rows:
            print(
                f"  {row['Field']}: {row['Type']} ({row['Null']}, {row['Key']})",
            )
    except Exception as e:
        print(f"Error describing table: {e}")


async def run_migration():
    """Execute migration SQL statements."""
    config = get_database_config()
    print(
        f"Connecting to database: {config.host}:{config.port}/{config.database}",
    )

    db = DatabaseConnection(config)
    await db.connect()
    print("Connected successfully")

    await _add_columns(db)
    await _migrate_config_data(db)
    await _update_indexes(db)
    await _verify_table_structure(db)

    await db.close()
    print("\nMigration completed!")


if __name__ == "__main__":
    asyncio.run(run_migration())
