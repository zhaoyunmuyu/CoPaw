# -*- coding: utf-8 -*-
"""Tests for PathValidator component."""

import pytest
from pathlib import Path
from unittest.mock import patch

from copaw.agents.tools.path_validator import PathValidator


class TestPathValidatorGetUserDir:
    """Tests for get_user_dir method."""

    def test_get_user_dir_returns_path(self, tmp_path):
        """Should return a Path object."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = PathValidator.get_user_dir()
            assert isinstance(result, Path)
            assert result == tmp_path


class TestPathValidatorValidatePath:
    """Tests for validate_path method."""

    def test_relative_path_inside_user_dir(self, tmp_path):
        """相对路径在用户目录内 - 应通过"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            # 创建测试文件
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello")

            is_valid, resolved, error = PathValidator.validate_path("test.txt")

            assert is_valid is True
            assert resolved == test_file.resolve()
            assert error == ""

    def test_absolute_path_inside_user_dir(self, tmp_path):
        """绝对路径在用户目录内 - 应通过"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello")

            is_valid, resolved, error = PathValidator.validate_path(
                str(test_file)
            )

            assert is_valid is True
            assert resolved == test_file.resolve()
            assert error == ""

    def test_relative_path_outside_user_dir(self, tmp_path):
        """相对路径跳出用户目录 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            is_valid, resolved, error = PathValidator.validate_path(
                "../../../etc/passwd"
            )

            assert is_valid is False
            assert "Permission denied" in error

    def test_absolute_path_outside_user_dir(self, tmp_path):
        """绝对路径指向外部 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            is_valid, resolved, error = PathValidator.validate_path("/etc/passwd")

            assert is_valid is False
            assert "Permission denied" in error

    def test_path_with_traversal_attempts(self, tmp_path):
        """路径遍历攻击尝试 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            # 创建子目录
            subdir = tmp_path / "subdir"
            subdir.mkdir()

            is_valid, resolved, error = PathValidator.validate_path(
                "subdir/../../etc/passwd"
            )

            assert is_valid is False

    def test_empty_path(self, tmp_path):
        """空路径 - 应返回无效路径错误"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            is_valid, resolved, error = PathValidator.validate_path("")

            assert is_valid is False
            assert "Invalid path" in error or "empty" in error.lower()


class TestPathValidatorResolveAndValidate:
    """Tests for resolve_and_validate method."""

    def test_valid_path_returns_resolved(self, tmp_path):
        """有效路径返回解析后的路径"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello")

            result = PathValidator.resolve_and_validate("test.txt")

            assert result == test_file.resolve()

    def test_invalid_path_raises_permission_error(self, tmp_path):
        """无效路径抛出 PermissionError"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            with pytest.raises(PermissionError) as exc_info:
                PathValidator.resolve_and_validate("/etc/passwd")

            assert "Permission denied" in str(exc_info.value)


class TestPathValidatorSymlinkHandling:
    """Tests for symlink handling."""

    def test_symlink_inside_user_dir_to_inside(self, tmp_path):
        """用户目录内符号链接指向用户目录内 - 应通过"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            target = tmp_path / "target.txt"
            target.write_text("content")
            link = tmp_path / "link.txt"
            link.symlink_to(target)

            is_valid, resolved, error = PathValidator.validate_path("link.txt")

            assert is_valid is True
            assert resolved == target.resolve()

    def test_symlink_inside_user_dir_to_outside(self, tmp_path):
        """用户目录内符号链接指向用户目录外 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            # 创建外部文件（模拟 /etc/passwd）
            external_dir = tmp_path.parent / "external"
            external_dir.mkdir(exist_ok=True)
            external_file = external_dir / "secret.txt"
            external_file.write_text("secret")

            # 在用户目录内创建指向外部的符号链接
            link = tmp_path / "external_link"
            link.symlink_to(external_file)

            is_valid, resolved, error = PathValidator.validate_path("external_link")

            assert is_valid is False
            assert "Permission denied" in error