# -*- coding: utf-8 -*-
"""User management API – initialize user directories."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...agents.utils.setup_utils import initialize_user_directory
from ...constant import get_working_dir

router = APIRouter(prefix="/users", tags=["users"])


class InitUserRequest(BaseModel):
    """Request body for POST /users/init."""

    user_id: str
    language: str = "en"


class InitUserResponse(BaseModel):
    """Response body for POST /users/init."""

    success: bool
    initialized: bool
    user_id: str
    working_dir: str


class UserStatusResponse(BaseModel):
    """Response body for GET /users/{user_id}/status."""

    user_id: str
    initialized: bool
    working_dir: str
    config_exists: bool
    providers_exists: bool
    active_skills_exists: bool


@router.post(
    "/init",
    response_model=InitUserResponse,
    summary="Initialize user directory",
    description=(
        "Initialize a user directory with default configuration files. "
        "Creates config.json, providers.json, active_skills/, and MD files. "
        "Returns initialized=false if the user directory already exists."
    ),
)
async def init_user(request: InitUserRequest) -> InitUserResponse:
    """Initialize user directory with minimal required files.

    Args:
        request: InitUserRequest with user_id and optional language

    Returns:
        InitUserResponse with initialization status

    Raises:
        HTTPException: If initialization fails
    """
    try:
        initialized = initialize_user_directory(
            user_id=request.user_id,
            language=request.language,
        )

        working_dir = get_working_dir(request.user_id)

        return InitUserResponse(
            success=True,
            initialized=initialized,
            user_id=request.user_id,
            working_dir=str(working_dir),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize user directory: {e}",
        ) from e


@router.get(
    "/{user_id}/status",
    response_model=UserStatusResponse,
    summary="Get user directory status",
    description="Check if a user directory is initialized and what files exist.",
)
async def get_user_status(user_id: str) -> UserStatusResponse:
    """Get initialization status for a user directory.

    Args:
        user_id: User identifier

    Returns:
        UserStatusResponse with initialization status
    """
    working_dir = get_working_dir(user_id)

    config_exists = (working_dir / "config.json").exists()
    providers_exists = (working_dir / "providers.json").exists()
    active_skills_exists = (working_dir / "active_skills").is_dir()

    initialized = config_exists and active_skills_exists

    return UserStatusResponse(
        user_id=user_id,
        initialized=initialized,
        working_dir=str(working_dir),
        config_exists=config_exists,
        providers_exists=providers_exists,
        active_skills_exists=active_skills_exists,
    )
