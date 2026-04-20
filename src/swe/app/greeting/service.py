# -*- coding: utf-8 -*-
"""Greeting configuration service."""

import logging
from typing import Optional

from .models import GreetingConfig, GreetingConfigCreate, GreetingConfigUpdate
from .store import GreetingStore

logger = logging.getLogger(__name__)


class GreetingService:
    """Service for greeting configuration operations."""

    def __init__(self, store: GreetingStore):
        """Initialize service.

        Args:
            store: GreetingStore instance
        """
        self.store = store

    async def get_config(
        self,
        source_id: str,
        bbk_id: Optional[str] = None,
    ) -> Optional[GreetingConfig]:
        """Get greeting config by source_id and bbk_id.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Returns:
            GreetingConfig if found, None otherwise
        """
        return await self.store.get_config(source_id, bbk_id)

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
        return await self.store.list_configs(
            source_id=source_id,
            page=page,
            page_size=page_size,
        )

    async def create_config(
        self,
        request: GreetingConfigCreate,
    ) -> GreetingConfig:
        """Create greeting config.

        Args:
            request: Create request

        Returns:
            Created GreetingConfig

        Raises:
            ValueError: If config already exists
        """
        # Check for duplicates
        exists = await self.store.check_exists(
            source_id=request.source_id,
            bbk_id=request.bbk_id,
        )
        if exists:
            bbk_str = request.bbk_id or "NULL"
            raise ValueError(
                f"配置 (source_id={request.source_id}, bbk_id={bbk_str}) 已存在",
            )

        config = GreetingConfig(
            source_id=request.source_id,
            bbk_id=request.bbk_id,
            greeting=request.greeting,
            subtitle=request.subtitle,
            placeholder=request.placeholder,
            is_active=True,
        )
        return await self.store.create_config(config)

    async def update_config(
        self,
        config_id: int,
        request: GreetingConfigUpdate,
    ) -> GreetingConfig:
        """Update greeting config.

        Args:
            config_id: Config ID to update
            request: Update request

        Returns:
            Updated GreetingConfig

        Raises:
            ValueError: If config not found or no fields to update
        """
        updated = await self.store.update_config(
            config_id=config_id,
            greeting=request.greeting,
            subtitle=request.subtitle,
            placeholder=request.placeholder,
            is_active=request.is_active,
        )
        if not updated:
            raise ValueError("配置不存在")
        return updated

    async def delete_config(self, config_id: int) -> None:
        """Delete greeting config.

        Args:
            config_id: Config ID to delete

        Raises:
            ValueError: If config not found
        """
        deleted = await self.store.delete_config(config_id)
        if not deleted:
            raise ValueError("配置不存在")
