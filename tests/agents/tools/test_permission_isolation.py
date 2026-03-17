# -*- coding: utf-8 -*-
"""Integration tests for user permission isolation."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from copaw.agents.tools.file_io import read_file, write_file
from copaw.agents.tools.file_search import grep_search
from copaw.agents.tools.shell import execute_shell_command
from copaw.agents.tools.sandbox import SandboxExecutor


class TestFileOperationIsolation:
    """Tests for file operation permission isolation."""

    @pytest.mark.asyncio
    async def test_read_file_inside_user_dir(self, tmp_path):
        """Reading files inside user directory should succeed."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await read_file("test.txt")
            assert "hello world" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_read_file_outside_user_dir(self, tmp_path):
        """Reading files outside user directory should be denied."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await read_file("/etc/passwd")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_write_file_outside_user_dir(self, tmp_path):
        """Writing files outside user directory should be denied."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await write_file("/etc/malicious.txt", "data")
            assert "Permission denied" in result.content[0].get("text", "")


class TestFileSearchIsolation:
    """Tests for file search permission isolation."""

    @pytest.mark.asyncio
    async def test_grep_search_outside_user_dir(self, tmp_path):
        """Searching outside user directory should be denied."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await grep_search("pattern", path="/etc")
            assert "Permission denied" in result.content[0].get("text", "")


class TestShellCommandIsolation:
    """Tests for shell command sandbox isolation."""

    @pytest.mark.asyncio
    async def test_shell_with_sandbox_unavailable_deny(self, tmp_path):
        """Shell command should fail when sandbox unavailable with deny."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            with patch(
                "copaw.agents.tools.shell._get_sandbox_config"
            ) as mock_config:
                mock_config.return_value = MagicMock(
                    enabled=True,
                    allow_network=False,
                    fallback="deny",
                )
                with patch.object(
                    SandboxExecutor, "is_available", return_value=False
                ):
                    result = await execute_shell_command("echo hello")
                    text = result.content[0].get("text", "")
                    assert (
                        "bubblewrap" in text.lower()
                        or "sandbox" in text.lower()
                    )