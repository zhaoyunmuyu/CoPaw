# -*- coding: utf-8 -*-
"""Tests for file_io permission isolation."""

import pytest
from pathlib import Path
from unittest.mock import patch

from copaw.agents.tools.file_io import (
    read_file,
    write_file,
    edit_file,
    append_file,
)


class TestFileIOPermissionIsolation:
    """Tests for file_io permission isolation."""

    @pytest.mark.asyncio
    async def test_read_file_outside_user_dir_denied(self, tmp_path):
        """Reading files outside user directory should be denied."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await read_file("/etc/passwd")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_write_file_outside_user_dir_denied(self, tmp_path):
        """Writing files outside user directory should be denied."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await write_file("/etc/malicious.txt", "data")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_read_file_inside_user_dir_allowed(self, tmp_path):
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
    async def test_read_file_traversal_attack_denied(self, tmp_path):
        """Path traversal attacks should be denied."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await read_file("../../../etc/passwd")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_edit_file_outside_user_dir_denied(self, tmp_path):
        """Editing files outside user directory should be denied."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await edit_file("/etc/malicious.txt", "old", "new")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_append_file_outside_user_dir_denied(self, tmp_path):
        """Appending to files outside user directory should be denied."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await append_file("/etc/malicious.txt", "data")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_edit_file_inside_user_dir_allowed(self, tmp_path):
        """Editing files inside user directory should succeed."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await edit_file("test.txt", "world", "universe")
            assert "Successfully replaced" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_append_file_inside_user_dir_allowed(self, tmp_path):
        """Appending to files inside user directory should succeed."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await append_file("test.txt", " world")
            assert "Appended" in result.content[0].get("text", "")