# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,protected-access
"""Unit tests for shell tenant path boundary enforcement.

Tests cover:
- Allowed tenant-local shell paths
- Denied cross-tenant cwd
- Denied relative traversal
- Denied absolute-path access
"""
from __future__ import annotations

from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from swe.config.context import tenant_context
from swe.agents.tools.shell import (
    _extract_path_tokens,
    _validate_shell_paths,
    _resolve_cwd,
)
from swe.security.tenant_path_boundary import (
    TenantPathBoundaryError,
    TenantContextMissingError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_tenant_dir(tmp_path: Path) -> Path:
    """Create a temporary directory structure mimicking ~/.swe/tenant_id."""
    tenant_dir = tmp_path / "test_tenant"
    tenant_dir.mkdir(parents=True)

    # Create subdirectories
    (tenant_dir / "subdir").mkdir()
    (tenant_dir / "subdir" / "nested").mkdir()

    # Create test files
    (tenant_dir / "file.txt").write_text("test content")
    (tenant_dir / "subdir" / "script.sh").write_text("#!/bin/bash\necho hello")

    return tenant_dir


@pytest.fixture
def other_tenant_dir(tmp_path: Path) -> Path:
    """Create another tenant directory to test isolation."""
    other_dir = tmp_path / "other_tenant"
    other_dir.mkdir(parents=True)
    (other_dir / "secret.txt").write_text("secret content")
    return other_dir


@pytest.fixture
def mock_working_dir(
    temp_tenant_dir: Path, other_tenant_dir: Path
) -> Generator[Path, None, None]:
    """Mock WORKING_DIR to use temporary directory."""
    parent_dir = temp_tenant_dir.parent
    with patch("swe.constant.WORKING_DIR", parent_dir):
        with patch("swe.security.tenant_path_boundary.WORKING_DIR", parent_dir):
            yield parent_dir


# =============================================================================
# Tests for _extract_path_tokens
# =============================================================================


class TestExtractPathTokens:
    """Tests for _extract_path_tokens function."""

    def test_extracts_absolute_paths(self):
        """Should extract absolute paths from commands."""
        cmd = "cat /etc/passwd && ls /var/log"
        tokens = _extract_path_tokens(cmd)
        assert "/etc/passwd" in tokens
        assert "/var/log" in tokens

    def test_extracts_relative_paths(self):
        """Should extract relative paths from commands."""
        cmd = "cat ./file.txt && ls ../parent"
        tokens = _extract_path_tokens(cmd)
        assert "./file.txt" in tokens
        assert "../parent" in tokens

    def test_extracts_paths_after_flags(self):
        """Should extract paths following common flags."""
        cmd = "cat -f /path/to/file --input ./input.txt -o /output.txt"
        tokens = _extract_path_tokens(cmd)
        assert "/path/to/file" in tokens
        assert "./input.txt" in tokens
        assert "/output.txt" in tokens

    def test_extracts_tilde_paths(self):
        """Should extract paths starting with tilde."""
        cmd = "cat ~/.bashrc && cp ~/file.txt /dest"
        tokens = _extract_path_tokens(cmd)
        assert "~/.bashrc" in tokens
        assert "~/file.txt" in tokens

    def test_no_false_positives(self):
        """Should not extract non-path tokens."""
        cmd = "echo hello world 123"
        tokens = _extract_path_tokens(cmd)
        assert "hello" not in tokens
        assert "world" not in tokens
        assert "123" not in tokens


# =============================================================================
# Tests for _validate_shell_paths
# =============================================================================


class TestValidateShellPaths:
    """Tests for _validate_shell_paths function."""

    def test_no_paths_returns_none(self, mock_working_dir: Path):
        """Should return None when no paths in command."""
        with tenant_context(tenant_id="test_tenant"):
            result = _validate_shell_paths("echo hello world")
            assert result is None

    def test_tenant_local_paths_allowed(self, mock_working_dir: Path):
        """Should allow paths within tenant workspace."""
        with tenant_context(tenant_id="test_tenant"):
            result = _validate_shell_paths("cat file.txt")
            assert result is None

    def test_absolute_path_outside_tenant_denied(self, mock_working_dir: Path):
        """Should reject absolute paths outside tenant."""
        with tenant_context(tenant_id="test_tenant"):
            other_path = mock_working_dir / "other_tenant/secret.txt"
            result = _validate_shell_paths(f"cat {other_path}")
            assert result is not None
            assert "outside the allowed workspace" in result

    def test_relative_traversal_denied(self, mock_working_dir: Path):
        """Should reject relative paths that traverse outside tenant."""
        with tenant_context(tenant_id="test_tenant"):
            result = _validate_shell_paths("cat ../other_tenant/secret.txt")
            assert result is not None
            assert "outside the allowed workspace" in result

    def test_tilde_path_denied(self, mock_working_dir: Path):
        """Should reject paths starting with tilde (expands to home)."""
        with tenant_context(tenant_id="test_tenant"):
            result = _validate_shell_paths("cat ~/.bashrc")
            assert result is not None
            assert "outside the allowed workspace" in result


# =============================================================================
# Tests for _resolve_cwd
# =============================================================================


class TestResolveCwd:
    """Tests for _resolve_cwd function."""

    def test_returns_tenant_root_when_cwd_none(self, mock_working_dir: Path):
        """Should return tenant root when cwd is None."""
        with tenant_context(tenant_id="test_tenant"):
            result = _resolve_cwd(None)
            expected = mock_working_dir / "test_tenant"
            assert result == expected

    def test_returns_resolved_cwd_when_within_tenant(self, mock_working_dir: Path):
        """Should return resolved cwd when within tenant."""
        tenant_dir = mock_working_dir / "test_tenant"
        subdir = tenant_dir / "subdir"

        with tenant_context(tenant_id="test_tenant"):
            result = _resolve_cwd(subdir)
            assert result == subdir.resolve()

    def test_raises_when_cwd_outside_tenant(self, mock_working_dir: Path):
        """Should raise TenantPathBoundaryError when cwd outside tenant."""
        other_dir = mock_working_dir / "other_tenant"

        with tenant_context(tenant_id="test_tenant"):
            with pytest.raises(TenantPathBoundaryError) as exc_info:
                _resolve_cwd(other_dir)

            assert "outside the tenant workspace" in str(exc_info.value)

    def test_raises_when_tenant_context_missing(self):
        """Should raise TenantContextMissingError when no tenant context."""
        with pytest.raises(TenantContextMissingError):
            _resolve_cwd(None)

    def test_rejects_traversal_cwd(self, mock_working_dir: Path):
        """Should reject cwd with path traversal."""
        tenant_dir = mock_working_dir / "test_tenant"
        traversal_path = tenant_dir / "../other_tenant"

        with tenant_context(tenant_id="test_tenant"):
            with pytest.raises(TenantPathBoundaryError):
                _resolve_cwd(traversal_path)


# =============================================================================
# Integration tests for execute_shell_command
# =============================================================================


class TestExecuteShellCommand:
    """Integration tests for execute_shell_command with tenant boundary."""

    @pytest.mark.asyncio
    async def test_executes_within_tenant(self, mock_working_dir: Path):
        """Should execute command within tenant workspace."""
        tenant_dir = mock_working_dir / "test_tenant"
        (tenant_dir / "test.txt").write_text("hello world")

        from swe.agents.tools.shell import execute_shell_command

        with tenant_context(tenant_id="test_tenant"):
            result = await execute_shell_command("cat test.txt")

            assert result.content[0]["text"] == "hello world"

    @pytest.mark.asyncio
    async def test_rejects_cross_tenant_cwd(self, mock_working_dir: Path):
        """Should reject command with cwd outside tenant."""
        from swe.agents.tools.shell import execute_shell_command

        other_dir = mock_working_dir / "other_tenant"

        with tenant_context(tenant_id="test_tenant"):
            result = await execute_shell_command("ls", cwd=other_dir)

            assert "outside the tenant workspace" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_rejects_cross_tenant_path_in_command(self, mock_working_dir: Path):
        """Should reject command referencing paths outside tenant."""
        from swe.agents.tools.shell import execute_shell_command

        with tenant_context(tenant_id="test_tenant"):
            other_path = mock_working_dir / "other_tenant/secret.txt"
            result = await execute_shell_command(f"cat {other_path}")

            assert "outside the allowed workspace" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_allows_valid_relative_paths(self, mock_working_dir: Path):
        """Should allow commands with valid relative paths."""
        tenant_dir = mock_working_dir / "test_tenant"
        (tenant_dir / "subdir" / "nested_file.txt").write_text("nested content")

        from swe.agents.tools.shell import execute_shell_command

        with tenant_context(tenant_id="test_tenant"):
            result = await execute_shell_command("cat subdir/nested_file.txt")

            assert "nested content" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_rejects_traversal_in_command(self, mock_working_dir: Path):
        """Should reject commands with path traversal."""
        from swe.agents.tools.shell import execute_shell_command

        with tenant_context(tenant_id="test_tenant"):
            result = await execute_shell_command("cat ../other_tenant/secret.txt")

            assert "outside the allowed workspace" in result.content[0]["text"]
