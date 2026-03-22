# -*- coding: utf-8 -*-
"""File lock implementation for NAS storage using portalocker."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import portalocker
from portalocker.exceptions import AlreadyLocked

logger = logging.getLogger(__name__)


def _ensure_file_exists(path: Path) -> None:
    """Ensure file exists, create if not."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


@asynccontextmanager
async def file_lock(path: Path, mode: str = "r") -> AsyncGenerator:
    """File lock context manager (async wrapper).

    Args:
        path: File path to lock
        mode: 'r' for shared read lock, 'w' for exclusive write lock
    """
    lock_mode = portalocker.LOCK_SH if mode == "r" else portalocker.LOCK_EX
    lock_mode |= portalocker.LOCK_NB  # Non-blocking

    if mode == "w":
        await asyncio.to_thread(_ensure_file_exists, path)

    fd = None
    locked = False
    try:
        fd = await asyncio.to_thread(open, path, "r+" if mode == "w" else "r")
        await asyncio.to_thread(portalocker.lock, fd, lock_mode)
        locked = True
        yield fd
    except AlreadyLocked:
        if fd:
            await asyncio.to_thread(fd.close)
        raise
    finally:
        if fd and locked:
            await asyncio.to_thread(portalocker.unlock, fd)
            await asyncio.to_thread(fd.close)


async def read_json_locked(path: Path) -> dict:
    """Read JSON file with shared lock."""
    async with file_lock(path, mode="r") as f:
        import json

        content = await asyncio.to_thread(f.read)
        return json.loads(content) if content else {}


async def write_json_locked(path: Path, data: dict) -> None:
    """Write JSON file with exclusive lock (atomic)."""
    import json

    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    async with file_lock(path, mode="w") as f:
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json_str, encoding="utf-8")
        tmp_path.replace(path)
