# -*- coding: utf-8 -*-
"""Greeting configuration store."""

import logging
from typing import Any, Optional

from .models import GreetingConfig

logger = logging.getLogger(__name__)


class GreetingStore:
    """Store for greeting configuration operations."""

    def __init__(self, db: Optional[Any] = None):
        """Initialize store.

        Args:
            db: Database connection (TDSQLConnection)
        """
        self.db = db
        self._use_db = db is not None and db.is_connected

    async def get_config(
        self,
        source_id: str,
        bbk_id: Optional[str] = None,
    ) -> Optional[GreetingConfig]:
        """Get greeting config by source_id and bbk_id.

        Exact match: source_id=X AND bbk_id=Y
        No fallback/inheritance.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Returns:
            GreetingConfig if found, None otherwise
        """
        if not self._use_db:
            return None

        # Use NULL-safe comparison (<=>) for bbk_id
        query = """
            SELECT * FROM swe_greeting_config
            WHERE source_id = %s AND bbk_id <=> %s AND is_active = 1
        """
        row = await self.db.fetch_one(query, (source_id, bbk_id))
        if row:
            return self._row_to_config(row)
        return None

    async def list_configs(
        self,
        source_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[GreetingConfig], int]:
        """List greeting configs with pagination.

        Args:
            source_id: Filter by source_id (optional)
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (configs list, total count)
        """
        if not self._use_db:
            return [], 0

        where_clauses = ["1=1"]
        params: list = []

        if source_id:
            where_clauses.append("source_id = %s")
            params.append(source_id)

        where_sql = " AND ".join(where_clauses)

        # Count query
        count_query = f"SELECT COUNT(*) as total FROM swe_greeting_config WHERE {where_sql}"
        count_row = await self.db.fetch_one(count_query, tuple(params))
        total = count_row["total"] if count_row else 0

        # Data query
        offset = (page - 1) * page_size
        query = f"""
            SELECT * FROM swe_greeting_config
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        rows = await self.db.fetch_all(query, tuple(params))

        configs = [self._row_to_config(row) for row in rows]
        return configs, total

    async def create_config(self, config: GreetingConfig) -> GreetingConfig:
        """Create greeting config.

        Args:
            config: GreetingConfig to create

        Returns:
            Created GreetingConfig
        """
        if self._use_db:
            query = """
                INSERT INTO swe_greeting_config
                    (source_id, bbk_id, greeting, subtitle, placeholder, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            await self.db.execute(
                query,
                (
                    config.source_id,
                    config.bbk_id,
                    config.greeting,
                    config.subtitle,
                    config.placeholder,
                    int(config.is_active),
                ),
            )
        return config

    async def update_config(
        self,
        config_id: int,
        greeting: Optional[str] = None,
        subtitle: Optional[str] = None,
        placeholder: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[GreetingConfig]:
        """Update greeting config.

        Args:
            config_id: Config ID to update
            greeting: New greeting text
            subtitle: New subtitle
            placeholder: New placeholder
            is_active: New active status

        Returns:
            Updated GreetingConfig or None if not found
        """
        if not self._use_db:
            return None

        updates = []
        params: list = []

        if greeting is not None:
            updates.append("greeting = %s")
            params.append(greeting)
        if subtitle is not None:
            updates.append("subtitle = %s")
            params.append(subtitle)
        if placeholder is not None:
            updates.append("placeholder = %s")
            params.append(placeholder)
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(int(is_active))

        if not updates:
            return None

        params.append(config_id)
        query = f"""
            UPDATE swe_greeting_config
            SET {', '.join(updates)}
            WHERE id = %s
        """
        await self.db.execute(query, tuple(params))

        # Fetch updated
        row = await self.db.fetch_one(
            "SELECT * FROM swe_greeting_config WHERE id = %s",
            (config_id,),
        )
        return self._row_to_config(row) if row else None

    async def delete_config(self, config_id: int) -> bool:
        """Delete greeting config.

        Args:
            config_id: Config ID to delete

        Returns:
            True if deleted, False otherwise
        """
        if self._use_db:
            query = "DELETE FROM swe_greeting_config WHERE id = %s"
            result = await self.db.execute(query, (config_id,))
            return result > 0
        return False

    async def check_exists(
        self,
        source_id: str,
        bbk_id: Optional[str] = None,
    ) -> bool:
        """Check if config exists for given source_id and bbk_id.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Returns:
            True if exists, False otherwise
        """
        if not self._use_db:
            return False

        query = """
            SELECT COUNT(*) as cnt FROM swe_greeting_config
            WHERE source_id = %s AND bbk_id <=> %s
        """
        row = await self.db.fetch_one(query, (source_id, bbk_id))
        return row["cnt"] > 0 if row else False

    def _row_to_config(self, row: dict) -> GreetingConfig:
        """Convert database row to GreetingConfig.

        Args:
            row: Database row dict

        Returns:
            GreetingConfig instance
        """
        return GreetingConfig(
            id=row["id"],
            source_id=row["source_id"],
            bbk_id=row["bbk_id"],
            greeting=row["greeting"],
            subtitle=row["subtitle"],
            placeholder=row["placeholder"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
