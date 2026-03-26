# -*- coding: utf-8 -*-
"""Tracing API router.

Provides REST API endpoints for tracing analytics.
"""
from datetime import datetime, timedelta
from typing import Optional
import logging

from fastapi import APIRouter, Query, HTTPException

from ...tracing import get_trace_manager, TracingConfig
from ...tracing.models import (
    OverviewStats,
    UserStats,
    UserListItem,
    TraceListItem,
    TraceDetail,
)

router = APIRouter(prefix="/tracing", tags=["tracing"])
logger = logging.getLogger(__name__)


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> OverviewStats:
    """Get overview statistics for the dashboard.

    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        Overview statistics including user counts, token usage, model distribution
    """
    try:
        manager = get_trace_manager()
    except RuntimeError:
        # Tracing not initialized, return empty stats
        return OverviewStats()

    start = None
    end = None

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            end = end + timedelta(days=1)  # Include the end date
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    return await manager.get_overview_stats(start, end)


@router.get("/users", response_model=dict)
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    user_id: Optional[str] = Query(None, description="Filter by user ID (partial match)"),
) -> dict:
    """Get list of users with their statistics.

    Args:
        page: Page number
        page_size: Page size
        user_id: Filter by user ID

    Returns:
        Paginated list of users with stats
    """
    try:
        manager = get_trace_manager()
    except RuntimeError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    users, total = await manager.get_users(page, page_size, user_id)
    return {
        "items": [u.model_dump() for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/users/{user_id}", response_model=UserStats)
async def get_user_stats(
    user_id: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> UserStats:
    """Get statistics for a specific user.

    Args:
        user_id: User identifier
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        User statistics
    """
    try:
        manager = get_trace_manager()
    except RuntimeError:
        return UserStats(user_id=user_id)

    start = None
    end = None

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            end = end + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    return await manager.get_user_stats(user_id, start, end)


@router.get("/traces", response_model=dict)
async def get_traces(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """Get list of traces.

    Args:
        page: Page number
        page_size: Page size
        user_id: Filter by user ID
        session_id: Filter by session ID
        status: Filter by status (running, completed, error, cancelled)
        start_date: Start date filter
        end_date: End date filter

    Returns:
        Paginated list of traces
    """
    try:
        manager = get_trace_manager()
    except RuntimeError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    start = None
    end = None

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            end = end + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    traces, total = await manager.get_traces(
        page=page,
        page_size=page_size,
        user_id=user_id,
        session_id=session_id,
        status=status,
        start_date=start,
        end_date=end,
    )
    return {
        "items": [t.model_dump() for t in traces],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/traces/{trace_id}", response_model=TraceDetail)
async def get_trace_detail(trace_id: str) -> TraceDetail:
    """Get detailed trace with spans.

    Args:
        trace_id: Trace identifier

    Returns:
        Trace detail with all spans

    Raises:
        HTTPException: If trace not found
    """
    try:
        manager = get_trace_manager()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Tracing not available")

    detail = await manager.get_trace_detail(trace_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    return detail


@router.get("/models", response_model=dict)
async def get_model_usage(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """Get model usage statistics.

    Args:
        start_date: Start date filter
        end_date: End date filter

    Returns:
        Model usage statistics
    """
    try:
        manager = get_trace_manager()
    except RuntimeError:
        return {"models": []}

    stats = await manager.get_overview_stats(
        start=datetime.strptime(start_date, "%Y-%m-%d") if start_date else None,
        end=datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) if end_date else None,
    )

    return {"models": [m.model_dump() for m in stats.model_distribution]}


@router.get("/tools", response_model=dict)
async def get_tool_usage(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> dict:
    """Get tool usage statistics.

    Args:
        start_date: Start date filter
        end_date: End date filter

    Returns:
        Tool usage statistics
    """
    try:
        manager = get_trace_manager()
    except RuntimeError:
        return {"tools": []}

    stats = await manager.get_overview_stats(
        start=datetime.strptime(start_date, "%Y-%m-%d") if start_date else None,
        end=datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) if end_date else None,
    )

    return {"tools": [t.model_dump() for t in stats.top_tools]}
