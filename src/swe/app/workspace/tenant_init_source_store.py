# -*- coding: utf-8 -*-
"""Tenant init source mapping store.

Records which default_{source} template directory was used to initialize
each tenant, enabling source-based template isolation.
"""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Global store singleton
_store: Optional["TenantInitSourceStore"] = None


class TenantInitSourceStore:
    """Store for tenant initialization source mapping.

    Follows the same dependency-injection pattern as InstanceStore:
    - Receives an optional database connection via constructor
    - Graceful degradation when database is unavailable
    """

    def __init__(self, db: Optional[Any] = None):
        """Initialize store.

        Args:
            db: Database connection (DatabaseConnection)
        """
        self.db = db
        self._use_db = db is not None and getattr(db, "is_connected", False)

    async def initialize(self) -> None:
        """Initialize store, checking database availability."""
        if self.db is not None and getattr(self.db, "is_connected", False):
            self._use_db = True
            logger.info("TenantInitSourceStore initialized with database")
        else:
            self._use_db = False
            logger.info("TenantInitSourceStore initialized without database")

    async def get_init_source(self, tenant_id: str) -> Optional[str]:
        """Query the init_source (template directory name) for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The init_source value (e.g. "default_ruice"), or None if not found.
        """
        if not self._use_db:
            return None
        query = (
            "SELECT init_source FROM swe_tenant_init_source "
            "WHERE tenant_id = %s"
        )
        try:
            row = await self.db.fetch_one(query, (tenant_id,))
            return row["init_source"] if row else None
        except Exception as e:
            logger.warning(
                f"Failed to query init_source for tenant " f"{tenant_id}: {e}",
            )
            return None

    async def get_or_create(
        self,
        tenant_id: str,
        source_id: str,
        init_source: str,
    ) -> str:
        """Get existing or create a new mapping record.

        If the tenant already has a mapping record, returns the stored
        init_source. Otherwise, creates a new record and returns the
        provided init_source.

        Args:
            tenant_id: The tenant identifier.
            source_id: The source identifier from X-Source-Id header.
            init_source: The template directory name used for initialization.

        Returns:
            The init_source value for this tenant.
        """
        existing = await self.get_init_source(tenant_id)
        if existing:
            return existing

        if self._use_db:
            query = (
                "INSERT INTO swe_tenant_init_source "
                "(tenant_id, source_id, init_source) "
                "VALUES (%s, %s, %s)"
            )
            try:
                await self.db.execute(
                    query,
                    (tenant_id, source_id, init_source),
                )
                logger.info(
                    f"Created init_source mapping: tenant={tenant_id}, "
                    f"source={source_id}, init_source={init_source}",
                )
            except Exception as e:
                logger.warning(
                    f"Failed to insert init_source mapping for tenant "
                    f"{tenant_id}: {e}",
                )

        return init_source

    async def get_by_source(self, source_id: str) -> list[dict]:
        """Query all tenants initialized from a given source.

        Args:
            source_id: The source identifier to filter by.

        Returns:
            List of dicts with tenant_id, source_id, init_source, created_at.
        """
        if not self._use_db:
            return []
        query = (
            "SELECT tenant_id, source_id, init_source, created_at "
            "FROM swe_tenant_init_source WHERE source_id = %s "
            "ORDER BY created_at"
        )
        try:
            rows = await self.db.fetch_all(query, (source_id,))
            return list(rows)
        except Exception as e:
            logger.warning(
                f"Failed to query tenants by source_id={source_id}: {e}",
            )
            return []

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """Get all mapping records with pagination.

        Args:
            page: Page number (1-based).
            page_size: Records per page.

        Returns:
            Tuple of (records list, total count).
        """
        if not self._use_db:
            return [], 0

        try:
            count_query = (
                "SELECT COUNT(*) as total FROM swe_tenant_init_source"
            )
            count_row = await self.db.fetch_one(count_query)
            total = count_row["total"] if count_row else 0

            offset = (page - 1) * page_size
            query = (
                "SELECT tenant_id, source_id, init_source, created_at "
                "FROM swe_tenant_init_source "
                "ORDER BY created_at DESC LIMIT %s OFFSET %s"
            )
            rows = await self.db.fetch_all(query, (page_size, offset))
            return list(rows), total
        except Exception as e:
            logger.warning(f"Failed to query all init_source mappings: {e}")
            return [], 0


def init_tenant_init_source_module(db=None) -> None:
    """Initialize tenant init source module with database connection.

    Args:
        db: DatabaseConnection instance (optional, if None, module operates
            in stub mode without database persistence).
    """
    global _store

    if db is None or not getattr(db, "is_connected", False):
        _store = None
        logger.info(
            "TenantInitSourceStore initialized in stub mode (no database connection)",
        )
        return

    _store = TenantInitSourceStore(db)
    logger.info("TenantInitSourceStore initialized with database connection")


def get_tenant_init_source_store() -> Optional["TenantInitSourceStore"]:
    """Get the global TenantInitSourceStore instance.

    Returns:
        The store instance, or None if not initialized.
    """
    return _store
