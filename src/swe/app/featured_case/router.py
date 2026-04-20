# -*- coding: utf-8 -*-
"""Featured case API router."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from .models import (
    CaseConfigCreate,
    CaseConfigDetail,
    CaseConfigListResponse,
    CaseConfigListItem,
    FeaturedCaseCreate,
    FeaturedCaseListResponse,
    FeaturedCaseUpdate,
)
from .service import FeaturedCaseService
from .store import FeaturedCaseStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/featured-cases", tags=["featured-cases"])

# Global instances
_store: Optional[FeaturedCaseStore] = None
_service: Optional[FeaturedCaseService] = None


def init_featured_case_module(db=None) -> None:
    """Initialize featured case module.

    Args:
        db: Database connection (TDSQLConnection)

    Raises:
        RuntimeError: If database is not connected
    """
    global _store, _service

    if db is None or not getattr(db, "is_connected", False):
        raise RuntimeError(
            "Featured case module requires a connected database.",
        )

    _store = FeaturedCaseStore(db)
    _service = FeaturedCaseService(_store)
    logger.info("Featured case module initialized")


def get_service() -> FeaturedCaseService:
    """Get featured case service.

    Returns:
        FeaturedCaseService instance

    Raises:
        RuntimeError: If module not initialized
    """
    global _service
    if _service is None:
        raise RuntimeError("Featured case module not initialized")
    return _service


# ==================== Client endpoints (for frontend display) ====================


@router.get(
    "",
    summary="Get cases for current context",
    description="Returns cases matched by X-Source-Id and X-Bbk-Id headers",
)
async def list_cases_for_display(request: Request) -> list[dict]:
    """Get cases for display.

    Headers:
        X-Source-Id: Source ID (required)
        X-Bbk-Id: BBK ID (optional)
    """
    source_id = request.headers.get("X-Source-Id")
    bbk_id = request.headers.get("X-Bbk-Id")

    if not source_id:
        return []

    service = get_service()
    return await service.get_cases_for_dimension(source_id, bbk_id)


@router.get(
    "/{case_id}",
    summary="Get case detail",
)
async def get_case_detail(case_id: str) -> dict:
    """Get case detail by ID."""
    service = get_service()
    case = await service.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.model_dump()


# ==================== Admin endpoints - Case definitions ====================


@router.get(
    "/admin/cases",
    response_model=FeaturedCaseListResponse,
    summary="List all cases (admin)",
)
async def list_all_cases(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> FeaturedCaseListResponse:
    """List all case definitions."""
    service = get_service()
    cases, total = await service.list_cases(page=page, page_size=page_size)
    return FeaturedCaseListResponse(cases=cases, total=total)


@router.post(
    "/admin/cases",
    summary="Create case (admin)",
)
async def create_case(case: FeaturedCaseCreate) -> dict:
    """Create case definition."""
    service = get_service()
    try:
        created = await service.create_case(case)
        return {"success": True, "data": created.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put(
    "/admin/cases/{case_id}",
    summary="Update case (admin)",
)
async def update_case(case_id: str, updates: FeaturedCaseUpdate) -> dict:
    """Update case definition."""
    service = get_service()
    try:
        updated = await service.update_case(case_id, updates)
        return {"success": True, "data": updated.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete(
    "/admin/cases/{case_id}",
    summary="Delete case (admin)",
)
async def delete_case(case_id: str) -> dict:
    """Delete case definition."""
    service = get_service()
    try:
        await service.delete_case(case_id)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ==================== Admin endpoints - Case configs ====================


@router.get(
    "/admin/configs",
    response_model=CaseConfigListResponse,
    summary="List case configs (admin)",
)
async def list_configs(
    source_id: Optional[str] = Query(None, description="Filter by source_id"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> CaseConfigListResponse:
    """List case configs with pagination."""
    service = get_service()
    configs, total = await service.list_configs(
        source_id=source_id,
        page=page,
        page_size=page_size,
    )
    config_items = [
        CaseConfigListItem(
            source_id=c["source_id"],
            bbk_id=c["bbk_id"],
            case_count=c["case_count"],
        )
        for c in configs
    ]
    return CaseConfigListResponse(configs=config_items, total=total)


@router.get(
    "/admin/configs/detail",
    summary="Get config detail (admin)",
)
async def get_config_detail(
    source_id: str = Query(..., description="Source ID"),
    bbk_id: Optional[str] = Query(None, description="BBK ID"),
) -> CaseConfigDetail:
    """Get config detail with case_ids."""
    service = get_service()
    case_ids = await service.get_config_cases(source_id, bbk_id)
    if not case_ids:
        raise HTTPException(status_code=404, detail="Config not found")
    return CaseConfigDetail(
        source_id=source_id,
        bbk_id=bbk_id,
        case_ids=case_ids,
    )


@router.put(
    "/admin/configs",
    summary="Upsert case config (admin)",
)
async def upsert_config(config: CaseConfigCreate) -> dict:
    """Upsert case config for dimension."""
    service = get_service()
    try:
        await service.upsert_config(config)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete(
    "/admin/configs",
    summary="Delete case config (admin)",
)
async def delete_config(
    source_id: str = Query(..., description="Source ID"),
    bbk_id: Optional[str] = Query(None, description="BBK ID"),
) -> dict:
    """Delete case config for dimension."""
    service = get_service()
    try:
        await service.delete_config(source_id, bbk_id)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
