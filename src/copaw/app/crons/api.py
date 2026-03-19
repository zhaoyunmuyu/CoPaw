# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Header

from .manager import CronManager
from .models import CronJobSpec, CronJobView

router = APIRouter(prefix="/cron", tags=["cron"])


def get_cron_manager(request: Request) -> CronManager:
    mgr = getattr(request.app.state, "cron_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="cron manager not initialized",
        )
    return mgr


def _get_user_id(x_user_id: str | None) -> str:
    """Get user_id from header or default to 'default'."""
    return x_user_id or "default"


@router.get("/jobs", response_model=list[CronJobSpec])
async def list_jobs(
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """List all cron jobs for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    return await mgr.list_jobs(user_id)


@router.get("/jobs/{job_id}", response_model=CronJobView)
async def get_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """Get a specific cron job for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    job = await mgr.get_job(job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return CronJobView(spec=job, state=mgr.get_state(job_id, user_id))


@router.post("/jobs", response_model=CronJobSpec)
async def create_job(
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """Create a new cron job for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    # Server generates id; ignore client-provided spec.id
    job_id = str(uuid.uuid4())
    created = spec.model_copy(update={"id": job_id})
    await mgr.create_or_replace_job(created, user_id)
    return created


@router.put("/jobs/{job_id}", response_model=CronJobSpec)
async def replace_job(
    job_id: str,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """Replace a cron job for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    if spec.id != job_id:
        raise HTTPException(status_code=400, detail="job_id mismatch")
    await mgr.create_or_replace_job(spec, user_id)
    return spec


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """Delete a cron job for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    ok = await mgr.delete_job(job_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"deleted": True}


@router.post("/jobs/{job_id}/pause")
async def pause_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """Pause a cron job for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    try:
        await mgr.pause_job(job_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"paused": True}


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """Resume a paused cron job for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    try:
        await mgr.resume_job(job_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"resumed": True}


@router.post("/jobs/{job_id}/run")
async def run_job(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """Trigger a job to run immediately for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    try:
        await mgr.run_job(job_id, user_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="job not found") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"started": True}


@router.get("/jobs/{job_id}/state")
async def get_job_state(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
):
    """Get the state of a cron job for the user."""
    user_id = _get_user_id(x_user_id)
    await mgr.ensure_user_started(user_id)
    job = await mgr.get_job(job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return mgr.get_state(job_id, user_id).model_dump(mode="json")
