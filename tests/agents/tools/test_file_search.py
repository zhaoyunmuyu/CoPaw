# -*- coding: utf-8 -*-
"""Tests for file_search permission isolation."""

import pytest
from pathlib import Path
from unittest.mock import patch

from copaw.agents.tools.file_search import grep_search, glob_search


class TestFileSearchPermissionIsolation:
    """Tests for file_search permission isolation."""

    @pytest.mark.asyncio
    async def test_grep_search_outside_user_dir_denied(self, tmp_path):
        """Search outside user directory - should deny"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await grep_search("pattern", path="/etc")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_glob_search_outside_user_dir_denied(self, tmp_path):
        """glob search outside user directory - should deny"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await glob_search("*.txt", path="/etc")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_grep_search_inside_user_dir_allowed(self, tmp_path):
        """Search inside user directory - should succeed"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await grep_search("hello")
            assert "hello" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_glob_search_inside_user_dir_allowed(self, tmp_path):
        """glob search inside user directory - should succeed"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await glob_search("*.txt")
            assert "test.txt" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_grep_search_relative_path_traversal_denied(self, tmp_path):
        """Relative path traversal attack - should deny"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await grep_search("pattern", path="../../../etc")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_glob_search_relative_path_traversal_denied(self, tmp_path):
        """Relative path traversal attack for glob - should deny"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await glob_search("*.txt", path="../../../etc")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_grep_search_empty_pattern(self, tmp_path):
        """Empty pattern - should return error"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await grep_search("")
            assert "Error" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_glob_search_empty_pattern(self, tmp_path):
        """Empty pattern for glob - should return error"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await glob_search("")
            assert "Error" in result.content[0].get("text", "")