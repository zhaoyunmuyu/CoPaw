# Backup Secret Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify backup worker to include secret directory content in backups and restore them correctly.

**Architecture:** Extend existing `_compress_user()`, `_extract_zip()`, and `_create_rollback_backup()` methods to handle `.secret/` folder within zip files. API remains unchanged; changes are internal to `BackupWorker`.

**Tech Stack:** Python, zipfile, FastAPI, pytest

**Reference:** `docs/superpowers/specs/2026-03-23-backup-secret-directory-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/copaw/app/backup/worker.py` | Core backup/restore logic with secret dir support |
| `tests/app/backup/test_secret_dir.py` | Unit tests for secret directory compression/extraction |
| `tests/app/backup/test_backup_flow.py` | Integration tests for full backup/restore with secrets |

---

## Task 1: Update Imports and Add get_secret_dir

**Files:**
- Modify: `src/copaw/app/backup/worker.py:14`

**Context:** The `get_secret_dir` function needs to be imported from `copaw.constant` to resolve secret directory paths per user.

- [ ] **Step 1: Update imports**

```python
# Line 14 - change from:
from ...constant import DEFAULT_WORKING_DIR

# To:
from ...constant import DEFAULT_WORKING_DIR, get_secret_dir
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from copaw.app.backup.worker import BackupWorker; print('Import OK')"`

Expected: `Import OK` (may show warnings about other deps, but no import errors)

- [ ] **Step 3: Commit**

```bash
git add src/copaw/app/backup/worker.py
git commit -m "chore(backup): import get_secret_dir from constant

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Modify _compress_user to Include Secret Directory

**Files:**
- Modify: `src/copaw/app/backup/worker.py:238-264`

**Context:** Current `_compress_user` only compresses `user_dir`. Need to also compress secret directory contents into `.secret/` folder within the zip.

- [ ] **Step 1: Read current implementation**

Read: `src/copaw/app/backup/worker.py` lines 238-264 to understand current `_compress_user` implementation.

- [ ] **Step 2: Modify _compress_user method**

Replace the entire `_compress_user` method (lines 238-264) with:

```python
    async def _compress_user(
        self,
        user_id: str,
        user_dir: Path,
        zip_path: Path,
    ) -> str:
        """Compress user directory and secret directory to zip."""

        def _do_compress():
            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as zf:
                # Compress user directory contents
                if user_dir.exists():
                    for file in user_dir.rglob("*"):
                        if file.is_file():
                            zf.write(file, file.relative_to(user_dir))
                        elif file.is_dir() and not any(file.iterdir()):
                            # Add empty directory
                            zf.writestr(
                                str(file.relative_to(user_dir)) + "/",
                                "",
                            )

                # Compress secret directory contents into .secret/ folder
                secret_dir = get_secret_dir(user_id)
                if secret_dir.exists():
                    for file in secret_dir.rglob("*"):
                        if file.is_file():
                            arcname = f".secret/{file.relative_to(secret_dir)}"
                            zf.write(file, arcname)
                        elif file.is_dir() and not any(file.iterdir()):
                            # Add empty directory
                            arcname = f".secret/{file.relative_to(secret_dir)}/"
                            zf.writestr(arcname, "")
            return str(zip_path)

        return await asyncio.to_thread(_do_compress)
```

- [ ] **Step 3: Verify syntax**

Run: `python -m py_compile src/copaw/app/backup/worker.py`

Expected: No output (no syntax errors)

- [ ] **Step 4: Commit**

```bash
git add src/copaw/app/backup/worker.py
git commit -m "feat(backup): include secret directory in backup compression

Compress secret directory contents into .secret/ folder within zip
for both regular backups and user data.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Modify _extract_zip to Handle .secret/ Folder

**Files:**
- Modify: `src/copaw/app/backup/worker.py:298-306`
- Modify: `src/copaw/app/backup/worker.py:204` (call site 1)
- Modify: `src/copaw/app/backup/worker.py:323` (call site 2)

**Context:** Current `_extract_zip` extracts everything to `target_dir`. Need to route `.secret/` entries to secret directory instead.

- [ ] **Step 1: Modify _extract_zip signature and implementation**

Replace the entire `_extract_zip` method (lines 298-306) with:

```python
    async def _extract_zip(
        self,
        zip_path: Path,
        target_dir: Path,
        user_id: str,
    ) -> None:
        """Extract zip to target directory, routing .secret/ to secret_dir."""

        def _do_extract():
            secret_dir = get_secret_dir(user_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            secret_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    # Route .secret/ entries to secret directory
                    if member.startswith(".secret/"):
                        # Remove .secret/ prefix
                        member_without_prefix = member[8:]  # len(".secret/") = 8
                        if not member_without_prefix:
                            continue  # Skip the .secret/ directory itself
                        dest_path = secret_dir / member_without_prefix
                    else:
                        dest_path = target_dir / member

                    # Security: Validate extracted path is under target directories
                    dest_path = dest_path.resolve()
                    if not (
                        str(dest_path).startswith(str(target_dir.resolve())) or
                        str(dest_path).startswith(str(secret_dir.resolve()))
                    ):
                        logger.warning(f"Skipping potentially malicious path: {member}")
                        continue

                    # Create parent directories and extract
                    if member.endswith("/"):
                        dest_path.mkdir(parents=True, exist_ok=True)
                    else:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(dest_path, "wb") as dst:
                            dst.write(src.read())

        await asyncio.to_thread(_do_extract)
```

- [ ] **Step 2: Update call site in run_restore_task (line ~204)**

Find line: `await self._extract_zip(zip_path, user_dir)`

Replace with: `await self._extract_zip(zip_path, user_dir, user_id)`

- [ ] **Step 3: Update call site in _rollback_all (line ~323)**

Find line: `await self._extract_zip(path, user_dir)`

Replace with: `await self._extract_zip(path, user_dir, user_id)`

- [ ] **Step 4: Verify syntax and imports**

Run: `python -m py_compile src/copaw/app/backup/worker.py`

Expected: No output

Run: `python -c "from copaw.app.backup.worker import BackupWorker; print('Import OK')"`

Expected: `Import OK`

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/backup/worker.py
git commit -m "feat(backup): route .secret/ entries to secret directory on restore

Update _extract_zip to accept user_id parameter and route entries
with .secret/ prefix to the user's secret directory.

Includes path traversal validation for security.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Modify _create_rollback_backup to Include Secret Directory

**Files:**
- Modify: `src/copaw/app/backup/worker.py:266-296`

**Context:** Rollback backup should also capture secret directory state for complete rollback capability.

- [ ] **Step 1: Modify _create_rollback_backup method**

Replace the entire `_create_rollback_backup` method (lines 266-296) with:

```python
    async def _create_rollback_backup(
        self,
        task_id: str,
        user_id: str,
        user_dir: Path,
    ) -> str:
        """Create a backup of current data (including secrets) before restore."""
        rollback_dir = DEFAULT_WORKING_DIR / ".rollback" / task_id
        rollback_dir.mkdir(parents=True, exist_ok=True)
        zip_path = rollback_dir / f"{user_id}.zip"

        def _do_compress():
            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as zf:
                # Compress user directory contents
                if user_dir.exists():
                    for file in user_dir.rglob("*"):
                        if file.is_file():
                            zf.write(file, file.relative_to(user_dir))
                        elif file.is_dir() and not any(file.iterdir()):
                            # Add empty directory
                            zf.writestr(
                                str(file.relative_to(user_dir)) + "/",
                                "",
                            )

                # Compress secret directory contents into .secret/ folder
                secret_dir = get_secret_dir(user_id)
                if secret_dir.exists():
                    for file in secret_dir.rglob("*"):
                        if file.is_file():
                            arcname = f".secret/{file.relative_to(secret_dir)}"
                            zf.write(file, arcname)
                        elif file.is_dir() and not any(file.iterdir()):
                            # Add empty directory
                            arcname = f".secret/{file.relative_to(secret_dir)}/"
                            zf.writestr(arcname, "")
            return str(zip_path)

        await asyncio.to_thread(_do_compress)
        return str(zip_path)
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile src/copaw/app/backup/worker.py`

Expected: No output

- [ ] **Step 3: Commit**

```bash
git add src/copaw/app/backup/worker.py
git commit -m "feat(backup): include secret directory in rollback backups

Ensure rollback backups capture secret directory state for
complete rollback capability during restore operations.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Write Unit Tests for Secret Directory Handling

**Files:**
- Create: `tests/app/backup/test_secret_dir.py`

**Context:** Need tests for `_compress_user` and `_extract_zip` secret directory handling.

- [ ] **Step 1: Create test file**

```python
# -*- coding: utf-8 -*-
"""Unit tests for secret directory backup/restore handling."""

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from copaw.app.backup.worker import BackupWorker
from copaw.app.backup.task_store import TaskStore
from copaw.app.backup.config import BackupEnvironmentConfig


class TestCompressUser:
    """Test _compress_user method with secret directory."""

    @pytest.fixture
    def mock_config(self):
        """Create mock backup config."""
        config = MagicMock(spec=BackupEnvironmentConfig)
        config.s3_bucket = "test-bucket"
        config.s3_prefix = "test"
        config.s3_region = "us-east-1"
        config.aws_access_key_id = "test-key"
        config.aws_secret_access_key = "test-secret"
        config.endpoint_url = None
        return config

    @pytest.fixture
    def worker(self, mock_config, tmp_path):
        """Create BackupWorker with mocked dependencies."""
        task_store = MagicMock(spec=TaskStore)
        worker = BackupWorker(task_store, mock_config)
        # Mock S3 client to avoid actual S3 calls
        worker.s3_client = MagicMock()
        return worker

    @pytest.mark.asyncio
    async def test_compress_user_without_secret_dir(self, worker, tmp_path):
        """Test compression when secret directory doesn't exist."""
        user_id = "testuser"
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        (user_dir / "config.json").write_text('{"test": true}')
        zip_path = tmp_path / "backup.zip"

        with patch("copaw.app.backup.worker.get_secret_dir") as mock_get_secret:
            secret_dir = tmp_path / "nonexistent"
            mock_get_secret.return_value = secret_dir

            result = await worker._compress_user(user_id, user_dir, zip_path)

        assert result == str(zip_path)
        assert zip_path.exists()

        # Verify zip contents - no .secret/ folder
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "config.json" in names
            assert not any(n.startswith(".secret/") for n in names)

    @pytest.mark.asyncio
    async def test_compress_user_with_secret_dir(self, worker, tmp_path):
        """Test compression includes secret directory contents."""
        user_id = "testuser"
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        (user_dir / "config.json").write_text('{"test": true}')

        secret_dir = tmp_path / "secret"
        secret_dir.mkdir()
        (secret_dir / "envs.json").write_text('{"API_KEY": "secret"}')

        zip_path = tmp_path / "backup.zip"

        with patch("copaw.app.backup.worker.get_secret_dir") as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            result = await worker._compress_user(user_id, user_dir, zip_path)

        assert result == str(zip_path)
        assert zip_path.exists()

        # Verify zip contents - includes .secret/ folder
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "config.json" in names
            assert ".secret/envs.json" in names

    @pytest.mark.asyncio
    async def test_compress_user_empty_secret_dir(self, worker, tmp_path):
        """Test compression with empty secret directory."""
        user_id = "testuser"
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        (user_dir / "config.json").write_text('{"test": true}')

        secret_dir = tmp_path / "secret"
        secret_dir.mkdir()  # Empty directory

        zip_path = tmp_path / "backup.zip"

        with patch("copaw.app.backup.worker.get_secret_dir") as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            result = await worker._compress_user(user_id, user_dir, zip_path)

        # Should still create valid zip
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "config.json" in names


class TestExtractZip:
    """Test _extract_zip method with .secret/ folder handling."""

    @pytest.fixture
    def mock_config(self):
        """Create mock backup config."""
        config = MagicMock(spec=BackupEnvironmentConfig)
        config.s3_bucket = "test-bucket"
        config.s3_prefix = "test"
        config.s3_region = "us-east-1"
        config.aws_access_key_id = "test-key"
        config.aws_secret_access_key = "test-secret"
        config.endpoint_url = None
        return config

    @pytest.fixture
    def worker(self, mock_config):
        """Create BackupWorker with mocked dependencies."""
        task_store = MagicMock(spec=TaskStore)
        return BackupWorker(task_store, mock_config)

    @pytest.mark.asyncio
    async def test_extract_zip_without_secret_folder(self, worker, tmp_path):
        """Test extraction when zip has no .secret/ folder (backward compat)."""
        user_id = "testuser"
        target_dir = tmp_path / "target"
        secret_dir = tmp_path / "secret"
        zip_path = tmp_path / "backup.zip"

        # Create zip without .secret/ folder
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", '{"test": true}')
            zf.writestr("sessions/test.json", "{}")

        with patch("copaw.app.backup.worker.get_secret_dir") as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            await worker._extract_zip(zip_path, target_dir, user_id)

        # Verify target dir has contents
        assert (target_dir / "config.json").exists()
        assert (target_dir / "sessions/test.json").exists()

        # Secret dir should exist but be empty
        assert secret_dir.exists()
        assert not any(secret_dir.iterdir())

    @pytest.mark.asyncio
    async def test_extract_zip_with_secret_folder(self, worker, tmp_path):
        """Test extraction routes .secret/ entries to secret directory."""
        user_id = "testuser"
        target_dir = tmp_path / "target"
        secret_dir = tmp_path / "secret"
        zip_path = tmp_path / "backup.zip"

        # Create zip with .secret/ folder
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", '{"test": true}')
            zf.writestr(".secret/envs.json", '{"API_KEY": "secret"}')
            zf.writestr(".secret/providers.json", '{"provider": "test"}')

        with patch("copaw.app.backup.worker.get_secret_dir") as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            await worker._extract_zip(zip_path, target_dir, user_id)

        # Verify target dir has non-secret contents
        assert (target_dir / "config.json").exists()
        assert not (target_dir / ".secret").exists()

        # Verify secret dir has .secret/ contents
        assert (secret_dir / "envs.json").exists()
        assert (secret_dir / "envs.json").read_text() == '{"API_KEY": "secret"}'
        assert (secret_dir / "providers.json").exists()

    @pytest.mark.asyncio
    async def test_extract_zip_path_traversal_protection(self, worker, tmp_path):
        """Test path traversal attempts are blocked."""
        user_id = "testuser"
        target_dir = tmp_path / "target"
        secret_dir = tmp_path / "secret"
        zip_path = tmp_path / "backup.zip"

        # Create zip with malicious path
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", '{"test": true}')
            zf.writestr("../../../etc/passwd", "malicious")  # Path traversal attempt

        with patch("copaw.app.backup.worker.get_secret_dir") as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            # Should complete without error (malicious entry is skipped)
            await worker._extract_zip(zip_path, target_dir, user_id)

        # Verify target dir only has safe contents
        assert (target_dir / "config.json").exists()
        assert not (tmp_path / "etc").exists()  # Path traversal was blocked
```

- [ ] **Step 2: Run tests to verify they work**

Run: `pytest tests/app/backup/test_secret_dir.py -v`

Expected: All tests PASS (8 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/app/backup/test_secret_dir.py
git commit -m "test(backup): add unit tests for secret directory handling

Add tests for _compress_user and _extract_zip with secret directory
support including backward compatibility and path traversal protection.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Update Integration Tests

**Files:**
- Modify: `tests/app/backup/test_backup_flow.py`

**Context:** Existing integration tests should continue to pass, but we may need to update mocks to handle secret directory.

- [ ] **Step 1: Check existing tests still pass**

Run: `pytest tests/app/backup/test_backup_flow.py -v`

Expected: All tests PASS (6 tests)

If tests fail due to missing `get_secret_dir` mock, update the test fixtures.

- [ ] **Step 2: If needed, patch get_secret_dir in fixtures**

Add to `test_backup_flow.py` fixture if tests fail:

```python
@pytest.fixture(autouse=True)
def mock_secret_dir(tmp_path):
    """Mock secret directory to avoid filesystem issues."""
    with patch("copaw.app.backup.worker.get_secret_dir") as mock:
        mock.return_value = tmp_path / "secret"
        yield
```

- [ ] **Step 3: Run tests again to confirm**

Run: `pytest tests/app/backup/test_backup_flow.py tests/app/backup/test_secret_dir.py -v`

Expected: All tests PASS

- [ ] **Step 4: Commit if changes made**

```bash
git add tests/app/backup/test_backup_flow.py
git commit -m "test(backup): update integration tests for secret directory

Ensure existing tests pass with secret directory handling.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Run Full Test Suite and Pre-commit

**Files:**
- All modified files

**Context:** Ensure no regressions and code quality passes.

- [ ] **Step 1: Run all backup tests**

Run: `pytest tests/app/backup/ -v`

Expected: All tests PASS

- [ ] **Step 2: Run pre-commit checks**

Run: `pre-commit run --all-files`

Expected: All checks pass (or only warnings unrelated to our changes)

- [ ] **Step 3: Final verification**

Run: `pytest tests/ -k backup -v`

Expected: All backup-related tests PASS

- [ ] **Step 4: Commit if any fixes needed**

```bash
git add -A
git commit -m "chore(backup): final fixes for secret directory feature

Address any linting issues and ensure all tests pass.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Summary

This plan modifies the backup system to include secret directory contents in backups while maintaining backward compatibility:

1. **Import update** - Add `get_secret_dir` import
2. **Compress** - Include secret directory in zip as `.secret/` folder
3. **Extract** - Route `.secret/` entries to secret directory during restore
4. **Rollback** - Include secrets in rollback backups
5. **Tests** - Unit tests for new functionality
6. **Integration** - Ensure existing tests pass
7. **Verification** - Full test suite and pre-commit

API endpoints remain unchanged - this is purely an internal enhancement to the `BackupWorker` class.
