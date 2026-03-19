# -*- coding: utf-8 -*-
"""文件上传 API - 支持上传文件到用户目录."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from ...constant import get_request_working_dir

router = APIRouter(prefix="/files", tags=["files"])


class FileUploadResponse(BaseModel):
    """文件上传响应."""

    success: bool
    filename: str
    path: str
    size: int


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    summary="上传文件",
    description="上传文件到用户目录下的 uploads/ 文件夹",
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
) -> FileUploadResponse:
    """上传文件到用户目录."""
    working_dir = get_request_working_dir()
    uploads_dir = working_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # 安全检查：防止路径遍历
    filename = Path(file.filename or "unnamed").name
    target_path = uploads_dir / filename
    resolved_path = target_path.resolve()
    if not str(resolved_path).startswith(str(uploads_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # 写入文件
    content = await file.read()
    target_path.write_bytes(content)

    return FileUploadResponse(
        success=True,
        filename=filename,
        path=str(target_path.relative_to(working_dir)),
        size=len(content),
    )
