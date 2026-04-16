# -*- coding: utf-8 -*-
"""Compatibility shell for removed local model management APIs."""

from __future__ import annotations

from enum import Enum
from typing import List, NoReturn, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/local-models", tags=["local-models"])

UNSUPPORTED_DETAIL = (
    "Local model management has been removed from the backend."
)
UNSUPPORTED_MESSAGE = "Local models are no longer supported."


class DownloadSource(str, Enum):
    HUGGINGFACE = "huggingface"
    MODELSCOPE = "modelscope"
    AUTO = "auto"


class LocalModelInfo(BaseModel):
    id: str = Field(..., description="Local model identifier")
    name: str = Field(..., description="Human-readable local model name")
    size_bytes: int = Field(..., description="Downloaded size in bytes")
    downloaded: bool = Field(..., description="Whether the model is local")
    source: DownloadSource = Field(..., description="Download source")


class ServerStatus(BaseModel):
    available: bool = Field(
        ...,
        description="Whether a local model server is available",
    )
    installable: bool = Field(
        ...,
        description="Whether local model installation is supported",
    )
    installed: bool = Field(
        ...,
        description="Whether a local runtime is installed",
    )
    port: Optional[int] = Field(
        default=None,
        description="Active local server port",
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Active local model name",
    )
    message: Optional[str] = Field(
        default=None,
        description="Additional compatibility status",
    )


class DownloadProgressResponse(BaseModel):
    status: str
    model_name: Optional[str] = None
    downloaded_bytes: int
    total_bytes: Optional[int] = None
    speed_bytes_per_sec: float
    source: Optional[str] = None
    error: Optional[str] = None
    local_path: Optional[str] = None


class StartServerRequest(BaseModel):
    model_id: str = Field(
        ...,
        description="Previously requested local model id",
    )


class StartServerResponse(BaseModel):
    port: int = Field(..., description="Deprecated local server port")
    model_name: str = Field(..., description="Deprecated local model name")


class StartModelDownloadRequest(BaseModel):
    model_name: str = Field(
        ...,
        description="Previously requested local model name",
    )
    source: DownloadSource = Field(
        default=DownloadSource.AUTO,
        description="Deprecated local model source",
    )


class ActionResponse(BaseModel):
    status: str = Field(..., description="Operation result status")
    message: str = Field(..., description="Human-readable operation result")


def _unsupported_progress() -> DownloadProgressResponse:
    return DownloadProgressResponse(
        status="idle",
        model_name=None,
        downloaded_bytes=0,
        total_bytes=None,
        speed_bytes_per_sec=0.0,
        source=None,
        error=None,
        local_path=None,
    )


def _raise_removed() -> NoReturn:
    raise HTTPException(status_code=410, detail=UNSUPPORTED_DETAIL)


@router.get(
    "/server",
    response_model=ServerStatus,
    summary="Check local model server compatibility status",
)
async def server_available() -> ServerStatus:
    """Return a stable compatibility response for removed local runtimes."""
    return ServerStatus(
        available=False,
        installable=False,
        installed=False,
        port=None,
        model_name=None,
        message=UNSUPPORTED_MESSAGE,
    )


@router.post(
    "/server/download",
    response_model=ActionResponse,
    summary="Start local runtime download",
)
async def start_llamacpp_download() -> ActionResponse:
    """Reject removed local runtime management operations."""
    _raise_removed()


@router.get(
    "/server/download",
    response_model=DownloadProgressResponse,
    summary="Get local runtime download progress",
)
async def get_llamacpp_download_progress() -> DownloadProgressResponse:
    """Return an idle shell progress response."""
    return _unsupported_progress()


@router.delete(
    "/server/download",
    response_model=ActionResponse,
    summary="Cancel local runtime download",
)
async def cancel_llamacpp_download() -> ActionResponse:
    """Reject removed local runtime management operations."""
    _raise_removed()


@router.post(
    "/server",
    response_model=StartServerResponse,
    summary="Start local runtime server",
)
async def start_llamacpp_server(
    payload: StartServerRequest,
) -> StartServerResponse:
    """Reject removed local runtime management operations."""
    del payload
    _raise_removed()


@router.delete(
    "/server",
    response_model=ActionResponse,
    summary="Stop local runtime server",
)
async def stop_llamacpp_server() -> ActionResponse:
    """Reject removed local runtime management operations."""
    _raise_removed()


@router.get(
    "/models",
    response_model=List[LocalModelInfo],
    summary="List local model compatibility shell",
)
async def list_local() -> List[LocalModelInfo]:
    """Return no local models because backend support was removed."""
    return []


@router.post(
    "/models/download",
    response_model=ActionResponse,
    summary="Start local model download",
)
async def start_local_model_download(
    payload: StartModelDownloadRequest,
) -> ActionResponse:
    """Reject removed local runtime management operations."""
    del payload
    _raise_removed()


@router.get(
    "/models/download",
    response_model=DownloadProgressResponse,
    summary="Get local model download progress",
)
async def get_local_model_download_progress() -> DownloadProgressResponse:
    """Return an idle shell progress response."""
    return _unsupported_progress()


@router.delete(
    "/models/download",
    response_model=ActionResponse,
    summary="Cancel local model download",
)
async def cancel_local_model_download() -> ActionResponse:
    """Reject removed local runtime management operations."""
    _raise_removed()
