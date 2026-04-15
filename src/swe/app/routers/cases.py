# -*- coding: utf-8 -*-
"""Cases API - Dynamic case loading with user filtering.

Cases are stored in WORKING_DIR/cases.json (global definitions)
and WORKING_DIR/user_cases.json (user-case mappings).
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ...config.cases import Case, CasesConfig, UserCasesConfig
from ...constant import WORKING_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])

CASES_FILE = WORKING_DIR / "cases.json"
USER_CASES_FILE = WORKING_DIR / "user_cases.json"

# Default template files (bundled with the application)
DEFAULT_CASES_TEMPLATE = (
    Path(__file__).parent.parent / "workspace" / "default" / "cases.json"
)
DEFAULT_USER_CASES_TEMPLATE = (
    Path(__file__).parent.parent / "workspace" / "default" / "user_cases.json"
)


def _init_default_cases() -> None:
    """Initialize default cases from template if user's cases.json doesn't exist."""
    if not CASES_FILE.is_file() and DEFAULT_CASES_TEMPLATE.is_file():
        CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEFAULT_CASES_TEMPLATE, CASES_FILE)
        logger.info(f"Initialized default cases from template: {CASES_FILE}")


def _init_default_user_cases() -> None:
    """Initialize default user-case mapping from template if user's file doesn't exist."""
    if not USER_CASES_FILE.is_file() and DEFAULT_USER_CASES_TEMPLATE.is_file():
        USER_CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEFAULT_USER_CASES_TEMPLATE, USER_CASES_FILE)
        logger.info(
            f"Initialized default user_cases from template: {USER_CASES_FILE}",
        )


def _get_user_id(request: Request, user_id_query: str | None) -> str:
    """Get effective userId from request.

    Priority: X-User-Id header > query parameter > "default"

    Args:
        request: FastAPI request object
        user_id_query: Optional userId from query parameter

    Returns:
        Effective userId string
    """
    # Priority 1: X-User-Id header (iframe passing)
    user_id = request.headers.get("X-User-Id")
    if user_id:
        return user_id

    # Priority 2: Query parameter
    if user_id_query:
        return user_id_query

    # Priority 3: Default fallback
    return "default"


def _load_cases() -> CasesConfig:
    """Load cases from cases.json.

    Returns:
        CasesConfig object
    """
    # Initialize from template if not exists
    _init_default_cases()

    if not CASES_FILE.is_file():
        logger.info("cases.json not found, returning empty config")
        return CasesConfig()

    try:
        data = json.loads(CASES_FILE.read_text("utf-8"))
        return CasesConfig.model_validate(data)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load cases.json: {e}")
        return CasesConfig()


def _save_cases(config: CasesConfig) -> None:
    """Save cases to cases.json.

    Args:
        config: CasesConfig to save
    """
    CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CASES_FILE.write_text(
        json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
        "utf-8",
    )


def _load_user_cases() -> UserCasesConfig:
    """Load user-case mappings from user_cases.json.

    Returns:
        UserCasesConfig object with default mapping if file missing
    """
    # Initialize from template if not exists
    _init_default_user_cases()

    if not USER_CASES_FILE.is_file():
        logger.info("user_cases.json not found, returning default config")
        return UserCasesConfig()

    try:
        data = json.loads(USER_CASES_FILE.read_text("utf-8"))
        return UserCasesConfig.model_validate(data)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load user_cases.json: {e}")
        return UserCasesConfig()


def _save_user_cases(config: UserCasesConfig) -> None:
    """Save user-case mappings to user_cases.json.

    Args:
        config: UserCasesConfig to save
    """
    USER_CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_CASES_FILE.write_text(
        json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
        "utf-8",
    )


def _get_user_case_ids(user_id: str) -> list[str]:
    """Get case IDs visible to a specific user.

    Args:
        user_id: User identifier

    Returns:
        List of case IDs (uses "default" mapping if user not found)
    """
    user_cases = _load_user_cases()
    if user_id in user_cases.user_cases:
        return user_cases.user_cases[user_id]
    return user_cases.user_cases.get("default", [])


# --- Public endpoints (user-filtered) ---


@router.get(
    "",
    summary="Get case list for current user",
    description="Returns cases visible to the requesting user (filtered by userId)",
)
async def list_cases(
    request: Request,
    user_id: str
    | None = Query(
        None,
        description="User ID (optional, uses header if omitted)",
    ),
) -> list[dict]:
    """Get case list filtered by user.

    Args:
        request: FastAPI request object
        user_id: Optional user ID query parameter

    Returns:
        List of cases with {id, label, value, sort_order}
    """
    effective_user_id = _get_user_id(request, user_id)
    case_ids = _get_user_case_ids(effective_user_id)
    cases_config = _load_cases()

    result = []
    for c in cases_config.cases:
        if c.id in case_ids and c.is_active:
            result.append(
                {
                    "id": c.id,
                    "label": c.label,
                    "value": c.value,
                    "sort_order": c.sort_order,
                },
            )

    # Sort by sort_order
    result.sort(key=lambda x: cast(int, x["sort_order"]))
    return result


@router.get(
    "/{case_id}",
    summary="Get case detail",
    description="Returns full case detail including iframe_url and steps",
)
async def get_case_detail(case_id: str) -> dict:
    """Get case detail by ID.

    Args:
        case_id: Case identifier

    Returns:
        Full case data including detail

    Raises:
        HTTPException: 404 if case not found
    """
    config = _load_cases()
    for c in config.cases:
        if c.id == case_id:
            if not c.is_active:
                raise HTTPException(
                    status_code=404,
                    detail="Case not found (inactive)",
                )
            return c.model_dump()

    raise HTTPException(status_code=404, detail="Case not found")


# --- Admin endpoints (management) ---


@router.get(
    "/admin/all",
    summary="Get all cases (admin)",
    description="Returns all cases including inactive ones",
)
async def list_all_cases() -> list[dict]:
    """Get all cases for management.

    Returns:
        List of all cases
    """
    config = _load_cases()
    return [c.model_dump() for c in config.cases]


@router.get(
    "/admin/user-mapping",
    summary="Get user-case mapping (admin)",
    description="Returns userId -> case_ids mapping",
)
async def get_user_mapping() -> dict:
    """Get user-case mapping configuration.

    Returns:
        UserCasesConfig.user_cases dict
    """
    config = _load_user_cases()
    return {"user_cases": config.user_cases}


@router.put(
    "/admin/user-mapping",
    summary="Update user-case mapping (admin)",
    description="Updates userId -> case_ids mapping",
)
async def update_user_mapping(
    body: dict = Body(..., description="Mapping of userId to case IDs"),
) -> dict:
    """Update user-case mapping.

    Args:
        body: {"user_cases": {"default": ["case-1"], "userId": ["case-2"]}}

    Returns:
        Success response
    """
    mapping = body.get("user_cases", {})
    if not mapping:
        raise HTTPException(status_code=400, detail="Missing user_cases field")

    # Ensure default exists
    if "default" not in mapping:
        raise HTTPException(
            status_code=400,
            detail="default mapping is required",
        )

    config = UserCasesConfig(user_cases=mapping)
    _save_user_cases(config)
    return {"success": True}


@router.post(
    "",
    summary="Create case (admin)",
    description="Create a new case",
)
async def create_case(case: Case) -> dict:
    """Create a new case.

    Args:
        case: Case data

    Returns:
        Created case
    """
    config = _load_cases()

    # Check duplicate ID
    for existing in config.cases:
        if existing.id == case.id:
            raise HTTPException(
                status_code=400,
                detail=f"Case ID '{case.id}' already exists",
            )

    config.cases.append(case)
    _save_cases(config)
    logger.info(f"Created case: {case.id}")
    return case.model_dump()


@router.put(
    "/{case_id}",
    summary="Update case (admin)",
    description="Update an existing case",
)
async def update_case(case_id: str, case: Case) -> dict:
    """Update an existing case.

    Args:
        case_id: Case identifier
        case: Updated case data

    Returns:
        Updated case

    Raises:
        HTTPException: 404 if case not found
    """
    config = _load_cases()

    for i, existing in enumerate(config.cases):
        if existing.id == case_id:
            config.cases[i] = case
            _save_cases(config)
            logger.info(f"Updated case: {case_id}")
            return case.model_dump()

    raise HTTPException(status_code=404, detail="Case not found")


@router.delete(
    "/{case_id}",
    summary="Delete case (admin)",
    description="Delete a case",
)
async def delete_case(case_id: str) -> dict:
    """Delete a case.

    Args:
        case_id: Case identifier

    Returns:
        Deleted case ID

    Raises:
        HTTPException: 404 if case not found
    """
    config = _load_cases()

    for i, existing in enumerate(config.cases):
        if existing.id == case_id:
            config.cases.pop(i)
            _save_cases(config)
            logger.info(f"Deleted case: {case_id}")
            return {"deleted": case_id}

    raise HTTPException(status_code=404, detail="Case not found")
