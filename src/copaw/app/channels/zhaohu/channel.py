# -*- coding: utf-8 -*-
"""Built-in Zhaohu channel.

Supports both outbound push and inbound message handling via callback.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Optional, Union

import httpx
from agentscope_runtime.engine.schemas.agent_schemas import (
    ContentType,
    TextContent,
)

from ....config.config import ZhaohuConfig as ZhaohuChannelConfig
from ..base import BaseChannel, OnReplySent, ProcessHandler

logger = logging.getLogger(__name__)

_TEXT_PART_LIMIT = 200
_SUMMARY_LIMIT = 50
_DEFAULT_CHANNEL = "ZH"
_DEFAULT_NET = "DMZ"
_DEFAULT_TIMEOUT = 15.0

# Message dedup: keep processed IDs for 5 minutes
_DEDUP_TTL_SECONDS = 300


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _normalize_text(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _chunk_text_values(text: str, limit: int = _TEXT_PART_LIMIT) -> list[str]:
    """Split text into text values under Zhaohu's 200-char limit."""
    normalized = _normalize_text(text)
    if not normalized:
        return [""]

    chunks: list[str] = []
    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        if line:
            chunks.append(line)

    return chunks or [_truncate(normalized, limit)]


def _clean_payload(obj: Any) -> Any:
    """Remove None and empty-string values from nested payloads."""
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            cleaned = _clean_payload(value)
            if cleaned is None or cleaned == "" or cleaned == [] or cleaned == {}:
                continue
            out[key] = cleaned
        return out
    if isinstance(obj, list):
        out = []
        for item in obj:
            cleaned = _clean_payload(item)
            if cleaned is None or cleaned == {}:
                continue
            out.append(cleaned)
        return out
    return obj


class ZhaohuChannel(BaseChannel):
    """Official built-in Zhaohu channel (outbound push + inbound callback)."""

    channel = "zhaohu"
    display_name = "Zhaohu"

    def __init__(
        self,
        process: ProcessHandler,
        enabled: bool,
        push_url: str,
        sys_id: str,
        robot_open_id: str,
        channel_code: str,
        net: str,
        request_timeout: float,
        bot_prefix: str,
        user_query_url: str = "",
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
        filter_thinking: bool = False,
        dm_policy: str = "open",
        group_policy: str = "open",
        allow_from: Optional[list] = None,
        deny_message: str = "",
    ):
        super().__init__(
            process,
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
            filter_thinking=filter_thinking,
            dm_policy=dm_policy,
            group_policy=group_policy,
            allow_from=allow_from,
            deny_message=deny_message,
        )
        self.enabled = enabled
        self.push_url = push_url or ""
        self.sys_id = sys_id or ""
        self.robot_open_id = robot_open_id or ""
        self.channel_code = channel_code or _DEFAULT_CHANNEL
        self.net = net or _DEFAULT_NET
        self.request_timeout = max(float(request_timeout or 0), 1.0)
        self.bot_prefix = bot_prefix or ""
        self.user_query_url = user_query_url or ""

        # Message dedup: set of processed message IDs with timestamp
        self._processed_message_ids: Dict[str, float] = {}
        self._dedup_lock = threading.Lock()

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "ZhaohuChannel":
        allow_from_env = os.getenv("ZHAOHU_ALLOW_FROM", "")
        allow_from = (
            [s.strip() for s in allow_from_env.split(",") if s.strip()]
            if allow_from_env
            else []
        )
        return cls(
            process=process,
            enabled=os.getenv("ZHAOHU_CHANNEL_ENABLED", "0") == "1",
            push_url=os.getenv("ZHAOHU_PUSH_URL", ""),
            sys_id=os.getenv("ZHAOHU_SYS_ID", ""),
            robot_open_id=os.getenv("ZHAOHU_ROBOT_OPEN_ID", ""),
            channel_code=os.getenv("ZHAOHU_CHANNEL", _DEFAULT_CHANNEL),
            net=os.getenv("ZHAOHU_NET", _DEFAULT_NET),
            request_timeout=float(
                os.getenv("ZHAOHU_REQUEST_TIMEOUT", str(_DEFAULT_TIMEOUT)),
            ),
            bot_prefix=os.getenv("ZHAOHU_BOT_PREFIX", ""),
            user_query_url=os.getenv("ZHAOHU_USER_QUERY_URL", ""),
            on_reply_sent=on_reply_sent,
            dm_policy=os.getenv("ZHAOHU_DM_POLICY", "open"),
            group_policy=os.getenv("ZHAOHU_GROUP_POLICY", "open"),
            allow_from=allow_from,
            deny_message=os.getenv("ZHAOHU_DENY_MESSAGE", ""),
        )

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: Union[ZhaohuChannelConfig, dict],
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
        filter_thinking: bool = False,
    ) -> "ZhaohuChannel":
        c = config if isinstance(config, dict) else config.model_dump()

        def _get_str(key: str) -> str:
            return (c.get(key) or "").strip()

        return cls(
            process=process,
            enabled=bool(c.get("enabled", False)),
            push_url=_get_str("push_url"),
            sys_id=_get_str("sys_id"),
            robot_open_id=_get_str("robot_open_id"),
            channel_code=_get_str("channel") or _DEFAULT_CHANNEL,
            net=_get_str("net") or _DEFAULT_NET,
            request_timeout=float(
                c.get("request_timeout") or _DEFAULT_TIMEOUT,
            ),
            bot_prefix=_get_str("bot_prefix"),
            user_query_url=_get_str("user_query_url"),
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
            filter_thinking=filter_thinking,
            dm_policy=c.get("dm_policy") or "open",
            group_policy=c.get("group_policy") or "open",
            allow_from=c.get("allow_from") or [],
            deny_message=c.get("deny_message") or "",
        )

    def resolve_session_id(
        self,
        sender_id: str,
        channel_meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate session_id for zhaohu callback messages.

        Session ID format: `zhaohu:callback:{sapId}`

        This ensures:
        - Same user (same sapId) has the same session for conversation continuity
        - Different from frontend sessions (which use UUID)
        - Isolated from outbound push sessions

        Args:
            sender_id: User's sapId from user query
            channel_meta: Optional channel metadata

        Returns:
            Session ID string
        """
        return f"zhaohu:callback:{sender_id}"

    def build_agent_request_from_native(self, native_payload: Any) -> Any:
        """Convert native callback payload to AgentRequest."""
        payload = native_payload if isinstance(native_payload, dict) else {}
        channel_id = payload.get("channel_id") or self.channel
        sender_id = payload.get("sender_id") or ""
        meta = payload.get("meta") or {}
        session_id = self.resolve_session_id(sender_id, meta)
        content_parts = payload.get("content_parts") or []

        if not content_parts:
            content_parts = [
                TextContent(
                    type=ContentType.TEXT,
                    text=payload.get("text", ""),
                ),
            ]

        request = self.build_agent_request_from_user_content(
            channel_id=channel_id,
            sender_id=sender_id,
            session_id=session_id,
            content_parts=content_parts,
            channel_meta=meta,
        )
        request.channel_meta = meta
        return request

    def try_accept_message(self, msg_id: str) -> bool:
        """Check if message ID is new; return True if accepted (not duplicate).

        Maintains a time-based dedup cache that prunes entries older than TTL.
        """
        if not msg_id:
            return True

        now = time.time()
        with self._dedup_lock:
            # Prune old entries
            expired = [
                mid
                for mid, ts in self._processed_message_ids.items()
                if now - ts > _DEDUP_TTL_SECONDS
            ]
            for mid in expired:
                del self._processed_message_ids[mid]

            if msg_id in self._processed_message_ids:
                return False

            self._processed_message_ids[msg_id] = now
            return True

    async def _query_user_info(self, open_id: str) -> Optional[Dict[str, Any]]:
        """Query user info to convert openId to sapId.

        Returns user info dict with sapId, or None if query fails.
        """
        if not self.user_query_url:
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
        timeout = httpx.Timeout(self.request_timeout, connect=10.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.user_query_url,
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
                "zhaohu user query: openId=%s -> sapId=%s",
                open_id,
                user_info.get("sapId"),
            )
            return user_info

        except Exception:
            logger.exception("zhaohu user query failed for openId=%s", open_id)
            return None

    async def enqueue_callback_message(self, callback_body: Any) -> None:
        """Process callback message and enqueue for agent processing.

        Called by the router when a message is received from Zhaohu.
        """
        if not self._enqueue:
            logger.warning(
                "zhaohu callback: enqueue not set, message dropped",
            )
            return

        msg_id = getattr(callback_body, "msg_id", "") or ""
        from_id = getattr(callback_body, "from_id", "") or ""
        to_id = getattr(callback_body, "to_id", "") or ""
        group_id = getattr(callback_body, "group_id", None)
        group_name = getattr(callback_body, "group_name", None)
        msg_type = getattr(callback_body, "msg_type", "") or ""
        msg_content = getattr(callback_body, "msg_content", "") or ""
        timestamp = getattr(callback_body, "timestamp", 0)

        # Query user info to get sapId from openId
        user_info = await self._query_user_info(from_id)
        sap_id = (user_info or {}).get("sapId") or from_id
        user_name = (user_info or {}).get("userName") or ""

        is_group = group_id is not None

        # Build meta for send path
        meta: Dict[str, Any] = {
            "send_addr": sap_id,
            "open_id": from_id,
            "to_id": to_id,
            "group_id": group_id,
            "group_name": group_name,
            "msg_type": msg_type,
            "timestamp": timestamp,
            "is_group": is_group,
        }
        if user_name:
            meta["user_name"] = user_name

        # Build content parts
        content_parts = [
            TextContent(type=ContentType.TEXT, text=msg_content),
        ]

        # Build native payload for queue
        native = {
            "channel_id": self.channel,
            "sender_id": sap_id,
            "content_parts": content_parts,
            "meta": meta,
            "message_id": msg_id,
        }

        logger.info(
            "zhaohu enqueue: msgId=%s fromId=%s sapId=%s text=%s",
            msg_id,
            from_id,
            sap_id,
            msg_content[:100] if msg_content else "",
        )

        self._enqueue(native)

    async def process_callback_message(self, callback_body: Any) -> None:
        """Process callback message: query user, call LLM, send response.

        This method is called in the background after the callback response
        is returned to the caller. It handles the complete flow:
        1. Query user info (openId → sapId)
        2. Build AgentRequest and call LLM
        3. Send response via push_url
        """
        from agentscope_runtime.engine.schemas.agent_schemas import RunStatus

        msg_id = getattr(callback_body, "msg_id", "") or ""
        from_id = getattr(callback_body, "from_id", "") or ""
        to_id = getattr(callback_body, "to_id", "") or ""
        group_id = getattr(callback_body, "group_id", None)
        group_name = getattr(callback_body, "group_name", None)
        msg_type = getattr(callback_body, "msg_type", "") or ""
        msg_content = getattr(callback_body, "msg_content", "") or ""
        timestamp = getattr(callback_body, "timestamp", 0)

        logger.info(
            "zhaohu processing: msgId=%s fromId=%s text=%s",
            msg_id,
            from_id,
            msg_content[:50] if msg_content else "",
        )

        # Query user info to get sapId from openId
        user_info = await self._query_user_info(from_id)
        sap_id = (user_info or {}).get("sapId") or from_id
        user_name = (user_info or {}).get("userName") or ""

        is_group = group_id is not None

        # Build meta for send path
        meta: Dict[str, Any] = {
            "send_addr": sap_id,
            "open_id": from_id,
            "to_id": to_id,
            "group_id": group_id,
            "group_name": group_name,
            "msg_type": msg_type,
            "timestamp": timestamp,
            "is_group": is_group,
        }
        if user_name:
            meta["user_name"] = user_name

        # Build content parts
        content_parts = [
            TextContent(type=ContentType.TEXT, text=msg_content),
        ]

        # Build session_id for conversation continuity
        session_id = self.resolve_session_id(sap_id, meta)

        # Build AgentRequest
        request = self.build_agent_request_from_user_content(
            channel_id=self.channel,
            sender_id=sap_id,
            session_id=session_id,
            content_parts=content_parts,
            channel_meta=meta,
        )
        request.channel_meta = meta

        # Process through LLM and collect response
        try:
            response_text = ""
            async for event in self._process(request):
                obj = getattr(event, "object", None)
                status = getattr(event, "status", None)
                if obj == "message" and status == RunStatus.Completed:
                    # Extract text from the completed message
                    parts = self._message_to_content_parts(event)
                    for part in parts:
                        if hasattr(part, "text") and part.text:
                            response_text += part.text
                        elif hasattr(part, "refusal") and part.refusal:
                            response_text += part.refusal

            if response_text:
                logger.info(
                    "zhaohu response: msgId=%s to=%s text=%s",
                    msg_id,
                    sap_id,
                    response_text[:50] if response_text else "",
                )
                # Send response via push_url
                await self.send(sap_id, response_text, meta)
            else:
                logger.warning(
                    "zhaohu no response text: msgId=%s",
                    msg_id,
                )

        except Exception:
            logger.exception(
                "zhaohu LLM processing failed: msgId=%s",
                msg_id,
            )
            # Send error message
            await self.send(
                sap_id,
                "抱歉，处理您的消息时发生错误，请稍后重试。",
                meta,
            )

    async def start(self) -> None:
        if not self.enabled:
            logger.debug("zhaohu channel disabled")
            return
        logger.info(
            "zhaohu channel started (outbound push + inbound callback)",
        )

    async def stop(self) -> None:
        if not self.enabled:
            return
        logger.info("zhaohu channel stopped")

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[dict] = None,
    ) -> None:
        """POST a Zhaohu push payload to the configured endpoint."""
        if not self.enabled:
            return
        if not self.push_url:
            logger.warning(
                "zhaohu send skipped: push_url not configured for %s",
                to_handle,
            )
            return
        if not self.sys_id or not self.robot_open_id:
            logger.warning(
                "zhaohu send skipped: sys_id or robot_open_id missing",
            )
            return

        payload = self._build_push_payload(to_handle, text, meta or {})
        timeout = httpx.Timeout(self.request_timeout, connect=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self.push_url, json=payload)
            response.raise_for_status()
            try:
                data = response.json() if response.content else {}
            except ValueError:
                data = {}

        body = data.get("body") or []
        exp_msg_ids = [
            str(item.get("expMsgId"))
            for item in body
            if isinstance(item, dict) and item.get("expMsgId")
        ]
        logger.info(
            "zhaohu push ok: to=%s returnCode=%s expMsgIds=%s",
            to_handle,
            str(data.get("returnCode") or "(empty)"),
            exp_msg_ids,
        )

    def _build_push_payload(
        self,
        to_handle: str,
        text: str,
        meta: dict,
    ) -> dict:
        send_addr = str(meta.get("send_addr") or to_handle or "").strip()
        session_id = str(meta.get("session_id") or "").strip()
        send_pk = str(
            meta.get("send_pk")
            or f"{session_id}_{send_addr}".strip("_")
            or send_addr
        ).strip()

        normalized_text = _normalize_text(text)
        summary_line = (
            normalized_text.split("\n", 1)[0] if normalized_text else ""
        )
        summary = _truncate(summary_line or normalized_text, _SUMMARY_LIMIT)
        text_values = [{"text": chunk} for chunk in _chunk_text_values(text)]

        payload = {
            "baseInfo": {
                "sysId": self.sys_id,
                "ssnId": meta.get("ssn_id") or session_id,
                "ssnNo": meta.get("ssn_no"),
                "msgBigCls": meta.get("msg_big_cls"),
                "msgSmlCls": meta.get("msg_sml_cls"),
                "channel": self.channel_code,
                "robotOpenId": self.robot_open_id,
                "sendAddrs": [
                    {
                        "sendAddr": send_addr,
                        "sendPk": send_pk,
                    },
                ],
                "net": self.net,
            },
            "msgCtlInfo": {
                "configId": meta.get("config_id"),
                "batchId": meta.get("batch_id"),
            },
            "msgContent": {
                "summary": summary,
                "pushContent": summary,
                "message": [
                    {
                        "type": "txt",
                        "value": text_values,
                    },
                ],
            },
        }
        return _clean_payload(payload)
