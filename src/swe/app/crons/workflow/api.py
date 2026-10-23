# -*- coding: utf-8 -*-
"""独立 Workflow 配置接口，原 URL 和权限不变。"""

from typing import Any
from fastapi import APIRouter, HTTPException, Request
from ..models import CronJobSpec
from .config_store import WorkflowConfigStore
from .models import WorkflowConfig

router = APIRouter(prefix="/cron", tags=["workflow-configuration"])


def _workflow_store(request: Request) -> WorkflowConfigStore:
    store = getattr(request.app.state, "workflow_config_store", None)
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="workflow configuration storage unavailable",
        )
    return store


async def _bind_workflow_config(
    spec: CronJobSpec,
    store: WorkflowConfigStore,
) -> CronJobSpec:
    if spec.task_type != "workflow":
        return spec
    config = await store.resolve_first_skill(
        spec.source_id or "",
        spec.skill_ids,
    )
    if (
        spec.workflow_binding_id
        and spec.workflow_binding_id != config.binding_id
    ):
        raise ValueError("workflow_binding_id does not match first skill")
    return spec.model_copy(
        update={"workflow_binding_id": config.binding_id},
    )


@router.get(
    "/workflow-bindings/{skill_id}",
    response_model=WorkflowConfig,
)
async def get_workflow_binding(
    skill_id: str,
    request: Request,
) -> WorkflowConfig:
    from ...source_system_config.router import _require_manager

    _require_manager(request)
    source_id = getattr(request.state, "source_id", None)
    if not source_id:
        raise HTTPException(status_code=400, detail="source_id is required")
    try:
        return await _workflow_store(request).resolve_first_skill(
            source_id,
            skill_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put(
    "/workflow-bindings/{skill_id}",
    response_model=WorkflowConfig,
)
async def publish_workflow_binding(
    skill_id: str,
    definition: dict[str, Any],
    request: Request,
) -> WorkflowConfig:
    from pydantic import ValidationError

    from ...source_system_config.router import _require_manager

    _require_manager(request)
    source_id = getattr(request.state, "source_id", None)
    if not source_id:
        raise HTTPException(status_code=400, detail="source_id is required")
    try:
        return await _workflow_store(request).publish(
            source_id=source_id,
            skill_id=skill_id,
            definition=definition,
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
