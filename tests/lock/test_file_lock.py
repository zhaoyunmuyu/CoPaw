# -*- coding: utf-8 -*-
"""Tests for file lock functionality."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import portalocker
import pytest
from portalocker.exceptions import AlreadyLocked

from copaw.lock import file_lock, read_json_locked, write_json_locked


class TestExclusiveLock:
    """Tests for exclusive (write) locking behavior."""

    @pytest.mark.asyncio
    async def test_exclusive_lock_blocks_write(self) -> None:
        """Exclusive lock prevents other writers."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Acquire exclusive lock
            async with file_lock(tmp_path, mode="w"):
                # Try to acquire another exclusive lock - should fail
                with pytest.raises(AlreadyLocked):
                    async with file_lock(tmp_path, mode="w"):
                        pass

                # Try to acquire shared lock - should also fail
                with pytest.raises(AlreadyLocked):
                    async with file_lock(tmp_path, mode="r"):
                        pass
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_exclusive_lock_allows_write(self) -> None:
        """Exclusive lock allows writing to file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            async with file_lock(tmp_path, mode="w") as f:
                await asyncio.to_thread(f.write, "test content")

            # Verify content was written
            assert tmp_path.read_text() == "test content"
        finally:
            tmp_path.unlink(missing_ok=True)


class TestSharedLock:
    """Tests for shared (read) locking behavior."""

    @pytest.mark.asyncio
    async def test_shared_lock_allows_readers(self) -> None:
        """Shared lock allows multiple readers."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(b'{"key": "value"}')

        try:
            readers = []

            async def acquire_shared_lock(path: Path) -> bool:
                """Acquire shared lock and verify can read."""
                async with file_lock(path, mode="r") as f:
                    content = await asyncio.to_thread(f.read)
                    return content == '{"key": "value"}'

            # Acquire multiple shared locks concurrently
            async with file_lock(tmp_path, mode="r"):
                # Should be able to acquire another shared lock
                async with file_lock(tmp_path, mode="r"):
                    pass

                # Should also work concurrently
                results = await asyncio.gather(
                    acquire_shared_lock(tmp_path),
                    acquire_shared_lock(tmp_path),
                    acquire_shared_lock(tmp_path),
                )
                assert all(results)
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_shared_lock_blocks_writer(self) -> None:
        """Shared lock prevents exclusive lock acquisition."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            async with file_lock(tmp_path, mode="r"):
                # Try to acquire exclusive lock - should fail
                with pytest.raises(AlreadyLocked):
                    async with file_lock(tmp_path, mode="w"):
                        pass
        finally:
            tmp_path.unlink(missing_ok=True)


class TestJsonLocked:
    """Tests for JSON read/write with locking."""

    @pytest.mark.asyncio
    async def test_write_json_locked_atomic(self) -> None:
        """Write JSON atomically with exclusive lock."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "test.json"
            data = {"key": "value", "nested": {"inner": 123}}

            await write_json_locked(json_path, data)

            # Verify file exists and content is correct
            assert json_path.exists()
            content = json.loads(json_path.read_text())
            assert content == data

            # Verify no temp file left behind
            tmp_path = json_path.with_suffix(".tmp")
            assert not tmp_path.exists()

    @pytest.mark.asyncio
    async def test_write_json_locked_creates_parent_dirs(self) -> None:
        """Write JSON creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "subdir" / "nested" / "test.json"
            data = {"key": "value"}

            await write_json_locked(json_path, data)

            assert json_path.exists()
            content = json.loads(json_path.read_text())
            assert content == data

    @pytest.mark.asyncio
    async def test_read_json_locked(self) -> None:
        """Read JSON with shared lock."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "test.json"
            data = {"key": "value", "nested": {"inner": 123}}
            json_path.write_text(json.dumps(data))

            result = await read_json_locked(json_path)

            assert result == data

    @pytest.mark.asyncio
    async def test_read_json_locked_empty_file(self) -> None:
        """Read empty JSON file returns empty dict."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "empty.json"
            json_path.touch()

            result = await read_json_locked(json_path)

            assert result == {}

    @pytest.mark.asyncio
    async def test_read_json_locked_missing_file(self) -> None:
        """Read missing JSON file raises error."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "missing.json"

            with pytest.raises(FileNotFoundError):
                await read_json_locked(json_path)

    @pytest.mark.asyncio
    async def test_write_then_read_json(self) -> None:
        """Write and then read JSON preserves data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "test.json"
            data = {"name": "test", "count": 42, "items": [1, 2, 3]}

            await write_json_locked(json_path, data)
            result = await read_json_locked(json_path)

            assert result == data

    @pytest.mark.asyncio
    async def test_concurrent_reads_allowed(self) -> None:
        """Multiple concurrent reads are allowed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "test.json"
            data = {"counter": 0}
            json_path.write_text(json.dumps(data))

            async def read_data() -> dict:
                return await read_json_locked(json_path)

            # Multiple concurrent reads should succeed
            results = await asyncio.gather(
                read_data(),
                read_data(),
                read_data(),
                read_data(),
                read_data(),
            )

            assert all(r == data for r in results)

    @pytest.mark.asyncio
    async def test_write_blocks_while_locked(self) -> None:
        """Write is blocked while another write holds the lock."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "test.json"

            async with file_lock(json_path, mode="w"):
                # Try to write - should fail due to lock
                with pytest.raises(AlreadyLocked):
                    await write_json_locked(json_path, {"key": "blocked"})
