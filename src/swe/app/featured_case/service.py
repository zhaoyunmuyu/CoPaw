# -*- coding: utf-8 -*-
"""Featured case service."""

import logging
from typing import Optional

from .models import (
    CaseConfigCreate,
    FeaturedCase,
    FeaturedCaseCreate,
    FeaturedCaseUpdate,
)
from .store import FeaturedCaseStore

logger = logging.getLogger(__name__)


class FeaturedCaseService:
    """Service for featured case operations."""

    def __init__(self, store: FeaturedCaseStore):
        """Initialize service.

        Args:
            store: FeaturedCaseStore instance
        """
        self.store = store

    # ==================== Case display ====================

    async def get_cases_for_dimension(
        self,
        source_id: str,
        bbk_id: Optional[str] = None,
    ) -> list[dict]:
        """Get cases for a specific dimension.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Returns:
            List of case dicts for display
        """
        return await self.store.get_cases_for_dimension(source_id, bbk_id)

    async def get_case_by_id(self, case_id: str) -> Optional[FeaturedCase]:
        """Get case by case_id.

        Args:
            case_id: Case identifier

        Returns:
            FeaturedCase if found, None otherwise
        """
        return await self.store.get_case_by_id(case_id)

    # ==================== Case CRUD ====================

    async def list_cases(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FeaturedCase], int]:
        """List all cases with pagination.

        Args:
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (cases list, total count)
        """
        return await self.store.list_cases(page=page, page_size=page_size)

    async def create_case(self, request: FeaturedCaseCreate) -> FeaturedCase:
        """Create case.

        Args:
            request: Create request

        Returns:
            Created FeaturedCase

        Raises:
            ValueError: If case already exists
        """
        exists = await self.store.check_case_exists(request.case_id)
        if exists:
            raise ValueError(f"案例 {request.case_id} 已存在")

        case = FeaturedCase(
            case_id=request.case_id,
            label=request.label,
            value=request.value,
            image_url=request.image_url,
            iframe_url=request.iframe_url,
            iframe_title=request.iframe_title,
            steps=request.steps,
            is_active=True,
        )
        return await self.store.create_case(case)

    async def update_case(
        self,
        case_id: str,
        request: FeaturedCaseUpdate,
    ) -> FeaturedCase:
        """Update case.

        Args:
            case_id: Case identifier
            request: Update request

        Returns:
            Updated FeaturedCase

        Raises:
            ValueError: If case not found
        """
        updated = await self.store.update_case(
            case_id=case_id,
            label=request.label,
            value=request.value,
            image_url=request.image_url,
            iframe_url=request.iframe_url,
            iframe_title=request.iframe_title,
            steps=request.steps,
            is_active=request.is_active,
        )
        if not updated:
            raise ValueError("案例不存在")
        return updated

    async def delete_case(self, case_id: str) -> None:
        """Delete case.

        Args:
            case_id: Case identifier

        Raises:
            ValueError: If case not found
        """
        deleted = await self.store.delete_case(case_id)
        if not deleted:
            raise ValueError("案例不存在")

    # ==================== Case-Config operations ====================

    async def list_configs(
        self,
        source_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """List all configs with pagination.

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

    async def get_config_cases(
        self,
        source_id: str,
        bbk_id: Optional[str] = None,
    ) -> list[str]:
        """Get case_ids for a dimension config.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Returns:
            List of case_ids
        """
        return await self.store.get_config_cases(source_id, bbk_id)

    async def upsert_config(self, request: CaseConfigCreate) -> None:
        """Upsert case config for dimension.

        Args:
            request: Create request

        Raises:
            ValueError: If invalid case_id provided
        """
        # Validate all case_ids exist
        for item in request.case_ids:
            if not await self.store.check_case_exists(item.case_id):
                raise ValueError(f"无效的案例 ID: {item.case_id}")

        case_ids = [item.model_dump() for item in request.case_ids]
        await self.store.upsert_config(
            source_id=request.source_id,
            bbk_id=request.bbk_id,
            case_ids=case_ids,
        )

    async def delete_config(
        self,
        source_id: str,
        bbk_id: Optional[str] = None,
    ) -> None:
        """Delete case config for dimension.

        Args:
            source_id: Source identifier
            bbk_id: BBK identifier (optional)

        Raises:
            ValueError: If config not found
        """
        deleted = await self.store.delete_config(source_id, bbk_id)
        if not deleted:
            raise ValueError("配置不存在")
