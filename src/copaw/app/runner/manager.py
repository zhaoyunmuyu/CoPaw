# -*- coding: utf-8 -*-
"""Chat manager for managing chat specifications."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .models import ChatSpec
from .repo.json_repo import JsonChatRepository
from ..channels.schema import DEFAULT_CHANNEL

logger = logging.getLogger(__name__)


class ChatManager:
    """Manages chat specifications in repository.

    Only handles ChatSpec CRUD operations.
    Does NOT manage Redis session state - that's handled by runner's session.

    Similar to CronManager's role in crons module.
    """

    def __init__(self):
        """Initialize chat manager without fixed repo.

        Repository is created per-request for user isolation.
        """
        self._lock = asyncio.Lock()

    def _get_repo_for_user(self, user_id: str) -> JsonChatRepository:
        """Get repository for specific user.

        Args:
            user_id: User identifier

        Returns:
            JsonChatRepository for user's chats.json
        """
        from ...config.utils import get_chats_path

        return JsonChatRepository(get_chats_path(user_id))

    # ----- Read Operations -----

    async def list_chats(
        self,
        user_id: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> list[ChatSpec]:
        """List chat specs with optional filters.

        Args:
            user_id: Optional user ID filter (required for repo lookup)
            channel: Optional channel filter

        Returns:
            List of chat specifications
        """
        if user_id is None:
            return []
        repo = self._get_repo_for_user(user_id)
        async with self._lock:
            return await repo.filter_chats(
                user_id=user_id,
                channel=channel,
            )

    async def get_chat(
        self, chat_id: str, user_id: Optional[str] = None
    ) -> Optional[ChatSpec]:
        """Get chat spec by chat_id (UUID).

        Args:
            chat_id: Chat UUID
            user_id: Optional user ID for repo lookup (required for user isolation)

        Returns:
            Chat spec or None if not found
        """
        if user_id is None:
            return None
        repo = self._get_repo_for_user(user_id)
        async with self._lock:
            return await repo.get_chat(chat_id)

    async def get_or_create_chat(
        self,
        session_id: str,
        user_id: str,
        channel: str = DEFAULT_CHANNEL,
        name: str = "New Chat",
    ) -> ChatSpec:
        """Get existing chat or create new one.

        Useful for auto-registration when chats come from channels.

        Args:
            session_id: Session identifier (channel:user_id)
            user_id: User identifier
            channel: Channel name
            name: Chat name

        Returns:
            Chat specification (existing or newly created)
        """
        repo = self._get_repo_for_user(user_id)
        async with self._lock:
            # Try to find existing by session_id
            existing = await repo.get_chat_by_id(
                session_id,
                user_id,
                channel,
            )
            if existing:
                return existing

            # Create new
            spec = ChatSpec(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                name=name,
            )
            # Call internal create without lock (already locked)
            await repo.upsert_chat(spec)
            logger.debug(
                f"Auto-registered new chat: {spec.id} -> {session_id}",
            )
            return spec

    async def create_chat(self, spec: ChatSpec, user_id: str) -> ChatSpec:
        """Create a new chat.

        Args:
            spec: Chat specification (chat_id will be generated if not set)
            user_id: User identifier for repo lookup

        Returns:
            Chat spec
        """
        repo = self._get_repo_for_user(user_id)
        async with self._lock:
            await repo.upsert_chat(spec)
            return spec

    async def update_chat(self, spec: ChatSpec, user_id: str) -> ChatSpec:
        """Update an existing chat spec.

        Args:
            spec: Updated chat specification
            user_id: User identifier for repo lookup

        Returns:
            Updated chat spec
        """
        repo = self._get_repo_for_user(user_id)
        async with self._lock:
            spec.updated_at = datetime.now(timezone.utc)
            await repo.upsert_chat(spec)
            return spec

    async def delete_chats(
        self,
        chat_ids: list[str],
        user_id: Optional[str] = None,
    ) -> bool:
        """Delete a chat spec.

        Note: This only deletes the spec. Redis session state is NOT deleted.

        Args:
            chat_ids: List of chat IDs
            user_id: User identifier for repo lookup

        Returns:
            True if deleted, False if not found
        """
        if user_id is None:
            return False
        repo = self._get_repo_for_user(user_id)
        async with self._lock:
            deleted = await repo.delete_chats(chat_ids)

            if deleted:
                logger.debug(f"Deleted chats: {chat_ids}")

            return deleted

    async def count_chats(
        self,
        user_id: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> int:
        """Count chats matching filters.

        Args:
            user_id: Optional user ID filter
            channel: Optional channel filter

        Returns:
            Number of matching chats
        """
        if user_id is None:
            return 0
        repo = self._get_repo_for_user(user_id)
        async with self._lock:
            chats = await repo.filter_chats(
                user_id=user_id,
                channel=channel,
            )
            return len(chats)
