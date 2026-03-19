# -*- coding: utf-8 -*-
"""Backup API router."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .models import BackupTaskStatus
from .service import BackupService

router = APIRouter(prefix="/backup", tags=["backup"])


class CreateBackupRequest(BaseModel):
    target_user_id: Optional[str] = None


class CreateBackupResponse(BaseModel):
    task_id: str
    status: str
    task_type: str
    message: str
    created_at: str


class CreateRestoreRequest(BaseModel):
    date: str
    user_ids: Optional[list[str]] = None


class CreateRestoreResponse(BaseModel):
    task_id: str
    status: str
    task_type: str
    message: str
    target_users: list[str]
    created_at: str


class TaskListResponse(BaseModel):
    tasks: list[dict]
    total: int


class TaskDetailResponse(BaseModel):
    task: dict


class DeleteTaskResponse(BaseModel):
    success: bool
    message: str


class ListBackupsResponse(BaseModel):
    dates: list[str]
    backups: dict


def get_backup_service() -> BackupService:
    """Get backup service instance."""
    return BackupService()


@router.post(
    "/upload",
    response_model=CreateBackupResponse,
    summary="创建备份任务",
    description="创建备份任务，上传用户数据到 S3。如果不指定 user_id，则备份所有用户。",
)
async def create_backup(request: CreateBackupRequest) -> CreateBackupResponse:
    service = get_backup_service()
    task = await service.create_backup_task(
        target_user_id=request.target_user_id,
    )
    return CreateBackupResponse(
        task_id=task.task_id,
        status=task.status.value,
        task_type=task.task_type.value,
        message="Backup task created successfully",
        created_at=task.created_at.isoformat(),
    )


@router.post(
    "/download",
    response_model=CreateRestoreResponse,
    summary="创建恢复任务",
    description="从 S3 下载备份并恢复到用户目录。支持按日期和用户列表筛选。",
)
async def create_restore(
    request: CreateRestoreRequest,
) -> CreateRestoreResponse:
    service = get_backup_service()

    # Preview target users
    backups = service.list_available_backups(date=request.date)
    available_users = list(backups["backups"].get(request.date, {}).keys())

    if request.user_ids:
        target_users = [u for u in request.user_ids if u in available_users]
    else:
        target_users = available_users

    task = await service.create_restore_task(
        date=request.date,
        user_ids=target_users if request.user_ids else None,
    )
    return CreateRestoreResponse(
        task_id=task.task_id,
        status=task.status.value,
        task_type=task.task_type.value,
        message=f"Restore task created for {request.date}",
        target_users=target_users,
        created_at=task.created_at.isoformat(),
    )


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="查询任务列表",
    description="查询备份任务列表，支持按状态和类型筛选。",
)
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Maximum number of tasks",
    ),
) -> TaskListResponse:
    service = get_backup_service()
    tasks = service.list_tasks(
        status=BackupTaskStatus(status) if status else None,
        task_type=task_type,
        limit=limit,
    )
    return TaskListResponse(
        tasks=[t.model_dump(mode="json") for t in tasks],
        total=len(tasks),
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskDetailResponse,
    summary="查询任务详情",
    description="获取指定任务的详细信息。",
)
async def get_task(task_id: str) -> TaskDetailResponse:
    service = get_backup_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskDetailResponse(task=task.model_dump(mode="json"))


@router.delete(
    "/tasks/{task_id}",
    response_model=DeleteTaskResponse,
    summary="删除任务",
    description="删除已完成的任务。无法删除运行中的任务。",
)
async def delete_task(task_id: str) -> DeleteTaskResponse:
    service = get_backup_service()
    success = service.delete_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Task not found or cannot delete running task",
        )
    return DeleteTaskResponse(success=True, message="Task deleted")


@router.get(
    "/list",
    response_model=ListBackupsResponse,
    summary="列出可用备份",
    description="列出 S3 上可用的备份列表，支持按用户和日期筛选。",
)
async def list_backups(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    date: Optional[str] = Query(
        None,
        description="Filter by date (YYYY-MM-DD)",
    ),
) -> ListBackupsResponse:
    service = get_backup_service()
    result = service.list_available_backups(user_id=user_id, date=date)
    return ListBackupsResponse(**result)
