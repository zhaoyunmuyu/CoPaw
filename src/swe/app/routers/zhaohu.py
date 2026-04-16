# -*- coding: utf-8 -*-
"""Zhaohu channel callback router.

Exports ``zhaohu_router`` with Zhaohu callback endpoint:
``/api/zhaohu/callback`` - receives inbound messages from Zhaohu platform.
"""
from __future__ import annotations

import logging
import ssl
from typing import Any, Optional, Dict

import httpx

from fastapi import APIRouter, BackgroundTasks, Request, Response

from pydantic import BaseModel, Field

from ...constant import EnvVarLoader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Zhaohu callback router
# ---------------------------------------------------------------------------
zhaohu_router = APIRouter(tags=["zhaohu"])


class ZhaohuCallbackRequest(BaseModel):
    """Zhaohu message callback request body."""

    msg_id: str = Field(default="", alias="msgId")
    from_id: str = Field(default="", alias="fromId")
    to_id: str = Field(default="", alias="toId")
    group_id: Optional[int] = Field(default=None, alias="groupId")
    group_name: Optional[str] = Field(default=None, alias="groupName")
    msg_type: str = Field(default="", alias="msgType")
    msg_content: str = Field(default="", alias="msgContent")
    timestamp: int = Field(default=0)
    custom_info: Optional[Any] = Field(default=None, alias="customInfo")

    model_config = {"populate_by_name": True}


# Default timeout for user query requests
_DEFAULT_TIMEOUT = 30.0


async def _query_user_info(open_id: str) -> Optional[Dict[str, Any]]:
    """Query user info to convert openId to sapId.

    Returns user info dict with sapId, or None if query fails.
    This is a standalone method that reads config from environment variables.
    """
    user_query_url = EnvVarLoader.get_str(
        "SWE_ZHAOHU_USER_QUERY_URL",
        "",
    )

    if not user_query_url:
        logger.warning(
            "zhaohu user query skipped: user_query_url not configured",
        )
        return None

    if not open_id:
        return None

    query_payload = {
        "compareType": "EQ",
        "matchFields": ["openId"],
        "keyWord": open_id,
    }
    timeout = httpx.Timeout(_DEFAULT_TIMEOUT, connect=10.0)
    # 自定义SSL上下文
    context = ssl.create_default_context()
    context.options |= 0x4

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            verify=context,
        ) as client:
            response = await client.post(
                user_query_url,
                json=query_payload,
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != "200":
            logger.warning(
                "zhaohu user query failed: code=%s message=%s",
                data.get("code"),
                data.get("message"),
            )
            return None

        user_list = data.get("data") or []
        if not user_list or not isinstance(user_list, list):
            logger.warning(
                "zhaohu user query: no user found for openId=%s",
                open_id,
            )
            return None

        user_info = user_list[0]
        logger.info(
            "request zhaohu user query: openId=%s -> sapId=%s",
            open_id,
            user_info.get("sapId"),
        )
        return user_info

    except Exception:
        logger.exception("zhaohu user query failed for openId=%s", open_id)
        return None


async def _get_zhaohu_channel(request: Request):
    """Retrieve the ZhaohuChannel from workspace, or None."""
    from ..agent_context import get_agent_for_request

    try:
        workspace = await get_agent_for_request(request)
    except Exception:
        return None

    if not workspace or not workspace.channel_manager:
        return None

    for ch in workspace.channel_manager.channels:
        if ch.channel == "zhaohu":
            return ch
    return None


async def _process_callback_background(
    channel,
    body: ZhaohuCallbackRequest,
) -> None:
    """Background task to process callback message.

    This runs after the response is returned to the caller.
    The channel.process_callback_message() method will:
    1. Set user context via set_request_user_id()
    2. Query user info (openId -> sapId)
    3. Load session state from file (conversation history)
    4. Call LLM with conversation context
    5. Save session state
    6. Send response via push_url
    """
    try:
        await channel.process_callback_message(body)
    except Exception:
        logger.exception(
            "zhaohu background processing failed: msgId=%s",
            body.msg_id,
        )


@zhaohu_router.post("/zhaohu/callback")
async def zhaohu_callback(
    request: Request,
    body: ZhaohuCallbackRequest,
    background_tasks: BackgroundTasks,
) -> Response:
    """Zhaohu message callback: receive inbound messages.

    Returns immediately with 'received' status, then processes the message
    in the background (query user info, call LLM, send response via push_url).
    """
    user_info = await _query_user_info(body.from_id)
    sap_id = (user_info or {}).get("sapId") or ""

    # Set request state so get_agent_for_request can resolve tenant/user
    if sap_id:
        request.state.tenant_id = sap_id
        request.state.user_id = sap_id

    logger.info("zhaohu callback received: %s", user_info)
    zhaohu_ch = await _get_zhaohu_channel(request)
    if not zhaohu_ch:
        logger.warning("zhaohu callback received but channel not available")
        return Response(
            content='{"code": "error", "message": "channel not available"}',
            status_code=503,
            media_type="application/json",
        )

    if not zhaohu_ch.enabled:
        logger.debug("zhaohu callback received but channel disabled")
        return Response(
            content='{"code": "error", "message": "channel disabled"}',
            status_code=503,
            media_type="application/json",
        )

    # Log the incoming callback
    logger.info(
        "zhaohu callback: msgId=%s fromId=%s msgType=%s",
        body.msg_id,
        body.from_id,
        body.msg_type,
    )

    # Check for duplicate messages
    if not zhaohu_ch.try_accept_message(body.msg_id):
        logger.info(
            "zhaohu duplicate ignored: msgId=%s from=%s",
            body.msg_id,
            body.from_id,
        )
        return Response(
            content='{"code": "ok", "message": "duplicate ignored"}',
            media_type="application/json",
        )

    # Schedule background processing and return immediately
    # FastAPI will properly await the async function
    background_tasks.add_task(_process_callback_background, zhaohu_ch, body)

    return Response(
        content='{"code": "ok", "message": "received"}',
        media_type="application/json",
    )
