# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request

from .manager import CronManager
from .models import CronJobListItem, CronJobSpec, CronJobView

router = APIRouter(prefix="/cron", tags=["cron"])


async def get_cron_manager(
    request: Request,
) -> CronManager:
    """Get cron manager for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.cron_manager is None:
        raise HTTPException(
            status_code=500,
            detail="CronManager not initialized",
        )
    return workspace.cron_manager


def _inject_request_tenant(spec: CronJobSpec, request: Request) -> CronJobSpec:
    """Force cron job tenant_id to follow request tenant context."""
    tenant_id = getattr(request.state, "tenant_id", None)
    return spec.model_copy(update={"tenant_id": tenant_id})


def _get_request_user_id(request: Request) -> str | None:
    state_user_id = getattr(request.state, "user_id", None)
    if state_user_id:
        return state_user_id
    return request.headers.get("X-User-Id")


def _inject_creator_user(
    spec: CronJobSpec,
    request: Request,
    existing: CronJobSpec | None = None,
) -> CronJobSpec:
    if spec.task_type != "agent":
        return spec
    meta = dict(spec.meta or {})
    existing_creator = (
        (existing.meta or {}).get("creator_user_id") if existing else None
    )
    creator_user_id = (
        existing_creator
        or meta.get("creator_user_id")
        or _get_request_user_id(request)
    )
    if creator_user_id:
        meta["creator_user_id"] = creator_user_id
    return spec.model_copy(update={"meta": meta})


def _serialize_state(state):
    if hasattr(state, "model_dump"):
        return state.model_dump(mode="json")
    return state


@router.get("/jobs", response_model=list[CronJobListItem])
async def list_jobs(
    request: Request,
    mgr: CronManager = Depends(get_cron_manager),
):
    user_id = _get_request_user_id(request)
    jobs = await mgr.list_jobs()
    return [
        CronJobListItem(
            **job.model_dump(mode="json"),
            state=_serialize_state(mgr.get_state(job.id)),
            task=mgr.build_task_view(job, user_id),
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}", response_model=CronJobView)
async def get_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return CronJobView(
        spec=job,
        state=_serialize_state(mgr.get_state(job_id)),
        task=mgr.build_task_view(job, _get_request_user_id(request)),
    )


@router.post("/jobs", response_model=CronJobSpec)
async def create_job(
    request: Request,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    # server generates id; ignore client-provided spec.id
    job_id = str(uuid.uuid4())
    created = spec.model_copy(update={"id": job_id})
    created = _inject_request_tenant(created, request)
    created = _inject_creator_user(created, request)
    await mgr.create_or_replace_job(created)
    saved = await mgr.get_job(job_id)
    return saved or created


@router.put("/jobs/{job_id}", response_model=CronJobSpec)
async def replace_job(
    request: Request,
    job_id: str,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    if spec.id != job_id:
        raise HTTPException(status_code=400, detail="job_id mismatch")
    existing = await mgr.get_job(job_id)
    spec = _inject_request_tenant(spec, request)
    spec = _inject_creator_user(spec, request, existing=existing)
    await mgr.create_or_replace_job(spec)
    saved = await mgr.get_job(job_id)
    return saved or spec


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    ok = await mgr.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"deleted": True}


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str, mgr: CronManager = Depends(get_cron_manager)):
    ok = await mgr.pause_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"paused": True}


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    ok = await mgr.resume_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"resumed": True}


@router.post("/jobs/{job_id}/run")
async def run_job(job_id: str, mgr: CronManager = Depends(get_cron_manager)):
    try:
        await mgr.run_job(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="job not found") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    # Note: run_job is a manual execution, not a schedule mutation
    # No reload signal needed
    return {"started": True}


@router.get("/jobs/{job_id}/state")
async def get_job_state(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return mgr.get_state(job_id).model_dump(mode="json")


@router.post("/jobs/{job_id}/task/mark-read")
async def mark_task_read(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    user_id = _get_request_user_id(request)
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id missing")
    ok = await mgr.mark_task_read(job_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task job not found")
    return {"marked_read": True}
