# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

from .auth_state import resolve_auth_token_for_execution
from .models import CronJobSpec
from ..tenant_context import bind_tenant_context
from ..console_push_store import append as push_store_append

logger = logging.getLogger(__name__)

CONSOLE_CHANNEL = "console"


class CronExecutor:
    def __init__(self, *, runner: Any, channel_manager: Any):
        self._runner = runner
        self._channel_manager = channel_manager

    async def execute(self, job: CronJobSpec) -> None:
        """Execute one job once with tenant context.

        - task_type text: send fixed text to channel
        - task_type agent: ask agent with prompt, send reply to channel (
            stream_query + send_event)

        Job execution is wrapped in tenant context to ensure proper isolation.
        """
        target_user_id = job.dispatch.target.user_id
        target_session_id = job.dispatch.target.session_id
        dispatch_meta: Dict[str, Any] = dict(job.dispatch.meta or {})
        workspace_dir_value = dispatch_meta.get("workspace_dir")
        workspace_dir = None
        if workspace_dir_value:
            workspace_dir = Path(workspace_dir_value)

        # Extract tenant_id from job spec (added for tenant isolation)
        tenant_id = getattr(job, "tenant_id", None)
        if tenant_id:
            dispatch_meta["tenant_id"] = tenant_id

        logger.info(
            "cron execute: job_id=%s channel=%s task_type=%s "
            "target_user_id=%s target_session_id=%s tenant_id=%s",
            job.id,
            job.dispatch.channel,
            job.task_type,
            target_user_id[:40] if target_user_id else "",
            target_session_id[:40] if target_session_id else "",
            tenant_id or "default",
        )

        # Wrap execution in tenant context
        with bind_tenant_context(
            tenant_id=tenant_id,
            user_id=target_user_id,
            workspace_dir=workspace_dir,
        ):
            await self._execute_job(
                job,
                target_user_id,
                target_session_id,
                dispatch_meta,
            )

    async def _execute_job(
        self,
        job: CronJobSpec,
        target_user_id: str,
        target_session_id: str,
        dispatch_meta: Dict[str, Any],
    ) -> None:
        """Internal: execute job logic (called within tenant context)."""
        tenant_id = dispatch_meta.get("tenant_id") or "default"

        if job.task_type == "text" and job.text:
            logger.info(
                "cron send_text: job_id=%s channel=%s len=%s",
                job.id,
                job.dispatch.channel,
                len(job.text or ""),
            )
            await self._channel_manager.send_text(
                channel=job.dispatch.channel,
                user_id=target_user_id,
                session_id=target_session_id,
                text=job.text.strip(),
                meta=dispatch_meta,
            )
            # Always push to console regardless of configured channel
            if job.dispatch.channel != CONSOLE_CHANNEL:
                await self._push_to_console(
                    target_session_id,
                    job.text.strip(),
                    tenant_id,
                )
            return

        # agent: run request as the dispatch target user so context matches
        logger.info(
            "cron agent: job_id=%s channel=%s stream_query then send_event",
            job.id,
            job.dispatch.channel,
        )
        assert job.request is not None
        req: Dict[str, Any] = job.request.model_dump(mode="json")
        req["user_id"] = target_user_id or "cron"
        req["session_id"] = target_session_id or f"cron:{job.id}"
        req["skip_history"] = True  # 标记定时任务不加载历史会话

        # Collect text for console push
        console_text_parts: list[str] = []

        try:
            logger.info("开始执行定时任务")
            resolved = resolve_auth_token_for_execution(
                tenant_id=getattr(job, "tenant_id", None),
                workspace_dir=dispatch_meta.get("workspace_dir"),
            )
        except ValueError as exc:
            logger.warning(
                "cron agent aborted: job_id=%s auth_state_error=%s",
                job.id,
                repr(exc),
            )
            raise RuntimeError(
                "cron auth user_info is expired; "
                "please refresh cron auth configuration",
            ) from exc
        if resolved.token:
            req["auth_token"] = resolved.token
        if resolved.cookie_header:
            req["cookie"] = resolved.cookie_header

        async def _run_agent() -> None:
            async for event in self._runner.stream_query(req):
                await self._channel_manager.send_event(
                    channel=job.dispatch.channel,
                    user_id=target_user_id,
                    session_id=target_session_id,
                    event=event,
                    meta=dispatch_meta,
                )
                # Extract text from event for console push
                text = self._extract_text_from_event(event)
                if text:
                    console_text_parts.append(text)

        try:
            await asyncio.wait_for(
                _run_agent(),
                timeout=job.runtime.timeout_seconds,
            )
            # Push collected text to console after agent completes
            if job.dispatch.channel != CONSOLE_CHANNEL and console_text_parts:
                full_text = "\n".join(console_text_parts)
                await self._push_to_console(
                    target_session_id,
                    full_text,
                    tenant_id,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "cron execute: job_id=%s timed out after %ss",
                job.id,
                job.runtime.timeout_seconds,
            )
            raise
        except asyncio.CancelledError:
            logger.info("cron execute: job_id=%s cancelled", job.id)
            raise

    async def _push_to_console(
        self,
        session_id: str,
        text: str,
        tenant_id: str,
    ) -> None:
        """Push message to console channel for frontend notification."""
        if not session_id or not text:
            return
        logger.info(
            "cron push_to_console: session_id=%s text_len=%s tenant_id=%s",
            session_id[:40] if session_id else "",
            len(text),
            tenant_id,
        )
        await push_store_append(session_id, text.strip(), tenant_id=tenant_id)

    def _extract_text_from_event(self, event: Any) -> str:
        """Extract text content from a runner event.

        Args:
            event: Runner event (from stream_query)

        Returns:
            Extracted text string, empty if no text found
        """
        from agentscope_runtime.engine.schemas.agent_schemas import RunStatus

        obj = getattr(event, "object", None)
        status = getattr(event, "status", None)

        # Only extract from completed message events
        if obj != "message" or status != RunStatus.Completed:
            return ""

        # Extract text from message content
        content = getattr(event, "content", None) or []
        text_parts: list[str] = []
        for part in content:
            part_type = getattr(part, "type", None)
            if part_type == "text":
                text = getattr(part, "text", None)
                if text:
                    text_parts.append(text)
            elif part_type == "refusal":
                refusal = getattr(part, "refusal", None)
                if refusal:
                    text_parts.append(refusal)

        return "\n".join(text_parts) if text_parts else ""
