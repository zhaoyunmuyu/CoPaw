# -*- coding: utf-8 -*-
"""Unit tests for secret directory handling in backup/restore."""

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from copaw.app.backup.worker import BackupWorker
from copaw.app.backup.config import BackupEnvironmentConfig
from copaw.app.backup.task_store import TaskStore


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory(
        prefix="copaw_test_user_",
    ) as user_dir, tempfile.TemporaryDirectory(
        prefix="copaw_test_secret_",
    ) as secret_dir, tempfile.TemporaryDirectory(
        prefix="copaw_test_zip_",
    ) as zip_dir:
        yield {
            "user_dir": Path(user_dir),
            "secret_dir": Path(secret_dir),
            "zip_dir": Path(zip_dir),
        }


@pytest.fixture
def worker():
    """Create a BackupWorker instance for testing."""
    config = BackupEnvironmentConfig(
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
        s3_bucket="test-bucket",
        s3_region="us-east-1",
    )
    task_store = TaskStore()
    return BackupWorker(task_store, config)


class TestCompressUser:
    """Tests for _compress_user method."""

    @pytest.mark.asyncio
    async def test_compress_user_without_secret_dir(
        self,
        worker: BackupWorker,
        temp_dirs: dict,
    ):
        """Test compressing user directory without secret directory."""
        user_dir = temp_dirs["user_dir"]
        zip_path = temp_dirs["zip_dir"] / "test.zip"

        # Create some test files in user directory
        (user_dir / "config.json").write_text('{"test": "data"}')
        (user_dir / "subdir").mkdir()
        (user_dir / "subdir" / "file.txt").write_text("test content")

        # Mock get_secret_dir to return non-existent directory
        with patch(
            "copaw.app.backup.worker.get_secret_dir",
        ) as mock_get_secret:
            mock_get_secret.return_value = Path("/nonexistent/secret")

            # Compress
            await worker._compress_user("test_user", user_dir, zip_path)

        # Verify zip contents
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "config.json" in names
            assert "subdir/file.txt" in names
            assert not any(name.startswith(".secret/") for name in names)

    @pytest.mark.asyncio
    async def test_compress_user_with_secret_dir(
        self,
        worker: BackupWorker,
        temp_dirs: dict,
    ):
        """Test compressing user directory with secret directory."""
        user_dir = temp_dirs["user_dir"]
        secret_dir = temp_dirs["secret_dir"]
        zip_path = temp_dirs["zip_dir"] / "test.zip"

        # Create test files in user directory
        (user_dir / "config.json").write_text('{"test": "data"}')

        # Create test files in secret directory
        (secret_dir / "providers.json").write_text('{"provider": "key"}')
        (secret_dir / "nested").mkdir()
        (secret_dir / "nested" / "secret.txt").write_text("secret data")

        # Mock get_secret_dir
        with patch(
            "copaw.app.backup.worker.get_secret_dir",
        ) as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            # Compress
            await worker._compress_user("test_user", user_dir, zip_path)

        # Verify zip contents
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "config.json" in names
            assert ".secret/providers.json" in names
            assert ".secret/nested/secret.txt" in names

            # Verify content
            assert zf.read("config.json") == b'{"test": "data"}'
            assert zf.read(".secret/providers.json") == b'{"provider": "key"}'
            assert zf.read(".secret/nested/secret.txt") == b"secret data"

    @pytest.mark.asyncio
    async def test_compress_user_empty_secret_dir(
        self,
        worker: BackupWorker,
        temp_dirs: dict,
    ):
        """Test compressing user directory with empty secret directory."""
        user_dir = temp_dirs["user_dir"]
        secret_dir = temp_dirs["secret_dir"]
        zip_path = temp_dirs["zip_dir"] / "test.zip"

        # Create test files in user directory
        (user_dir / "config.json").write_text('{"test": "data"}')

        # Leave secret directory empty (it exists but has no files)
        assert secret_dir.exists()

        # Mock get_secret_dir
        with patch(
            "copaw.app.backup.worker.get_secret_dir",
        ) as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            # Compress
            await worker._compress_user("test_user", user_dir, zip_path)

        # Verify zip contents
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "config.json" in names
            # Empty secret directory should not add any .secret/ entries
            assert not any(name.startswith(".secret/") for name in names)


class TestExtractZip:
    """Tests for _extract_zip method."""

    @pytest.mark.asyncio
    async def test_extract_zip_without_secret_folder(
        self,
        worker: BackupWorker,
        temp_dirs: dict,
    ):
        """Test extracting zip without .secret/ folder."""
        user_dir = temp_dirs["user_dir"]
        secret_dir = temp_dirs["secret_dir"]
        zip_path = temp_dirs["zip_dir"] / "test.zip"

        # Create a zip without .secret/ folder
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", '{"test": "data"}')
            zf.writestr("subdir/file.txt", "test content")

        # Mock get_secret_dir
        with patch(
            "copaw.app.backup.worker.get_secret_dir",
        ) as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            # Extract
            await worker._extract_zip(zip_path, user_dir, "test_user")

        # Verify extraction
        assert (user_dir / "config.json").exists()
        assert (user_dir / "subdir" / "file.txt").exists()
        assert (user_dir / "config.json").read_text() == '{"test": "data"}'
        assert (user_dir / "subdir" / "file.txt").read_text() == "test content"

        # Secret directory should remain empty
        assert not any(secret_dir.iterdir())

    @pytest.mark.asyncio
    async def test_extract_zip_with_secret_folder(
        self,
        worker: BackupWorker,
        temp_dirs: dict,
    ):
        """Test extracting zip with .secret/ folder."""
        user_dir = temp_dirs["user_dir"]
        secret_dir = temp_dirs["secret_dir"]
        zip_path = temp_dirs["zip_dir"] / "test.zip"

        # Create a zip with both regular files and .secret/ folder
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", '{"test": "data"}')
            zf.writestr(".secret/providers.json", '{"provider": "key"}')
            zf.writestr(".secret/nested/secret.txt", "secret data")

        # Mock get_secret_dir
        with patch(
            "copaw.app.backup.worker.get_secret_dir",
        ) as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            # Extract
            await worker._extract_zip(zip_path, user_dir, "test_user")

        # Verify regular files extracted to user_dir
        assert (user_dir / "config.json").exists()
        assert (user_dir / "config.json").read_text() == '{"test": "data"}'

        # Verify secret files extracted to secret_dir
        assert (secret_dir / "providers.json").exists()
        assert (secret_dir / "nested" / "secret.txt").exists()
        assert (
            secret_dir / "providers.json"
        ).read_text() == '{"provider": "key"}'
        assert (
            secret_dir / "nested" / "secret.txt"
        ).read_text() == "secret data"

        # Verify files are NOT in user_dir's .secret folder
        assert not (user_dir / ".secret").exists()

    @pytest.mark.asyncio
    async def test_extract_zip_path_traversal_protection(
        self,
        worker: BackupWorker,
        temp_dirs: dict,
    ):
        """Test that path traversal attempts are blocked."""
        user_dir = temp_dirs["user_dir"]
        secret_dir = temp_dirs["secret_dir"]
        zip_path = temp_dirs["zip_dir"] / "malicious.zip"

        # Create a zip with path traversal attempts
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", '{"test": "data"}')
            # Path traversal attempt
            zf.writestr("../../../etc/passwd", "malicious content")
            zf.writestr(".secret/../../../etc/shadow", "malicious secret")

        # Mock get_secret_dir
        with patch(
            "copaw.app.backup.worker.get_secret_dir",
        ) as mock_get_secret:
            mock_get_secret.return_value = secret_dir

            # Extract should raise ValueError
            with pytest.raises(ValueError) as exc_info:
                await worker._extract_zip(zip_path, user_dir, "test_user")

            assert "Path traversal detected" in str(exc_info.value)

        # Note: config.json was extracted before path traversal was encountered
        # This is expected - the implementation doesn't rollback on error
        assert (user_dir / "config.json").exists()

        # But verify malicious files were NOT extracted outside target dirs
        assert not (user_dir / ".." / ".." / ".." / "etc" / "passwd").exists()
        assert not (
            secret_dir / ".." / ".." / ".." / "etc" / "shadow"
        ).exists()
