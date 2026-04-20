# -*- coding: utf-8 -*-
"""Greeting configuration API router."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from .models import (
    GreetingConfigCreate,
    GreetingConfigListResponse,
    GreetingConfigUpdate,
)
from .service import GreetingService
from .store import GreetingStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/greeting", tags=["greeting"])

# Global instances
_store: Optional[GreetingStore] = None
_service: Optional[GreetingService] = None


def init_greeting_module(db=None) -> None:
    """Initialize greeting module.

    Args:
        db: Database connection (TDSQLConnection)

    Raises:
        RuntimeError: If database is not connected
    """
    global _store, _service

    if db is None or not getattr(db, "is_connected", False):
        raise RuntimeError("Greeting module requires a connected database.")

    _store = GreetingStore(db)
    _service = GreetingService(_store)
    logger.info("Greeting module initialized")


def get_service() -> GreetingService:
    """Get greeting service.

    Returns:
        GreetingService instance

    Raises:
        RuntimeError: If module not initialized
    """
    global _service
    if _service is None:
        raise RuntimeError("Greeting module not initialized")
    return _service


# ==================== Client endpoint (for frontend display) ====================


@router.get(
    "/display",
    summary="Get greeting for current context",
    description="Returns greeting config matched by X-Source-Id and X-Bbk-Id headers",
)
async def get_display_greeting(request: Request) -> Optional[dict]:
    """Get greeting config for display.

    Headers:
        X-Source-Id: Source ID (required)
        X-Bbk-Id: BBK ID (optional)
    """
    source_id = request.headers.get("X-Source-Id")
    bbk_id = request.headers.get("X-Bbk-Id")

    if not source_id:
        return None

    service = get_service()
    config = await service.get_config(source_id, bbk_id)

    if not config:
        return None

    return {
        "greeting": config.greeting,
        "subtitle": config.subtitle,
        "placeholder": config.placeholder,
    }


# ==================== Admin endpoints (management) ====================


@router.get(
    "/admin/list",
    response_model=GreetingConfigListResponse,
    summary="List all greeting configs (admin)",
)
async def list_greeting_configs(
    source_id: Optional[str] = Query(None, description="Filter by source_id"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> GreetingConfigListResponse:
    """List greeting configs with pagination."""
    service = get_service()
    configs, total = await service.list_configs(
        source_id=source_id,
        page=page,
        page_size=page_size,
    )
    return GreetingConfigListResponse(configs=configs, total=total)


@router.post(
    "/admin",
    summary="Create greeting config (admin)",
)
async def create_greeting_config(config: GreetingConfigCreate) -> dict:
    """Create greeting config."""
    service = get_service()
    try:
        created = await service.create_config(config)
        return {"success": True, "data": created.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put(
    "/admin/{config_id}",
    summary="Update greeting config (admin)",
)
async def update_greeting_config(
    config_id: int,
    updates: GreetingConfigUpdate,
) -> dict:
    """Update greeting config."""
    service = get_service()
    try:
        updated = await service.update_config(config_id, updates)
        return {"success": True, "data": updated.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete(
    "/admin/{config_id}",
    summary="Delete greeting config (admin)",
)
async def delete_greeting_config(config_id: int) -> dict:
    """Delete greeting config."""
    service = get_service()
    try:
        await service.delete_config(config_id)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
