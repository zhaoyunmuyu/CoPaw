# -*- coding: utf-8 -*-
"""In-memory store for console channel push messages (e.g. cron text).

Bounded: at most _MAX_MESSAGES kept per user; messages older than _MAX_AGE_SECONDS
are dropped when reading. Frontend dedupes by id and caps its seen set.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List

# Per-user storage: {user_id: [messages]}
_store: Dict[str, List[Dict[str, Any]]] = {}
_lock = asyncio.Lock()
_MAX_AGE_SECONDS = 60
_MAX_MESSAGES = 500


async def append(user_id: str | None, session_id: str, text: str) -> None:
    """Append a message for a specific user (bounded per user)."""
    if not session_id or not text:
        return

    # Default to "default" for backward compatibility
    uid = user_id or "default"

    async with _lock:
        if uid not in _store:
            _store[uid] = []

        _store[uid].append(
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "ts": time.time(),
                "session_id": session_id,
                "user_id": uid,
            }
        )

        # Keep only _MAX_MESSAGES per user
        if len(_store[uid]) > _MAX_MESSAGES:
            _store[uid].sort(key=lambda m: m["ts"])
            _store[uid] = _store[uid][-_MAX_MESSAGES:]


async def take(user_id: str | None, session_id: str) -> List[Dict[str, Any]]:
    """Return and remove all messages for the user and session."""
    if not session_id:
        return []

    uid = user_id or "default"

    async with _lock:
        user_messages = _store.get(uid, [])
        out = [m for m in user_messages if m.get("session_id") == session_id]
        _store[uid] = [
            m for m in user_messages if m.get("session_id") != session_id
        ]
        return _strip_ts(out)


async def take_all(user_id: str | None = None) -> List[Dict[str, Any]]:
    """Return and remove all messages for the user."""
    uid = user_id or "default"

    async with _lock:
        out = _store.get(uid, [])
        _store[uid] = []
        return _strip_ts(out)


async def get_recent(
    user_id: str | None = None,
    max_age_seconds: int = _MAX_AGE_SECONDS,
) -> List[Dict[str, Any]]:
    """Return recent messages (not consumed) for the user."""
    uid = user_id or "default"
    now = time.time()
    cutoff = now - max_age_seconds

    async with _lock:
        # Clean up expired messages for this user
        user_messages = _store.get(uid, [])
        valid = [m for m in user_messages if m["ts"] >= cutoff]
        expired = [m for m in user_messages if m["ts"] < cutoff]

        if expired:
            _store[uid] = valid

        return _strip_ts(valid)


def _strip_ts(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"id": m["id"], "text": m["text"]} for m in msgs]
