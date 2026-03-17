# -*- coding: utf-8 -*-
"""Tests for shell sandbox integration."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from copaw.agents.tools.shell import execute_shell_command
from copaw.agents.tools.sandbox import SandboxExecutor


class TestShellSandboxIntegration:
    """Tests for shell sandbox integration."""

    @pytest.mark.asyncio
    async def test_shell_cwd_outside_user_dir_denied(self, tmp_path):
        """Specify external cwd - should deny."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await execute_shell_command(
                "echo hello",
                cwd=Path("/etc"),
            )
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_shell_with_sandbox(self, tmp_path):
        """Sandbox execution - should succeed."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            with patch.object(
                SandboxExecutor, "is_available", return_value=True
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
                        SandboxExecutor, "execute"
                    ) as mock_execute:
                        mock_execute.return_value = (0, "hello", "")

                        result = await execute_shell_command("echo hello")
                        assert "hello" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_shell_sandbox_unavailable_deny(self, tmp_path):
        """Sandbox unavailable with deny fallback."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            with patch.object(
                SandboxExecutor, "is_available", return_value=False
            ):
                with patch(
                    "copaw.agents.tools.shell._get_sandbox_config"
                ) as mock_config:
                    mock_config.return_value = MagicMock(
                        enabled=True,
                        allow_network=False,
                        fallback="deny",
                    )

                    result = await execute_shell_command("echo hello")
                    text = result.content[0].get("text", "")
                    assert "not available" in text

    @pytest.mark.asyncio
    async def test_shell_sandbox_disabled(self, tmp_path):
        """Sandbox disabled - should use direct execution."""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            with patch(
                "copaw.agents.tools.shell._get_sandbox_config"
            ) as mock_config:
                mock_config.return_value = MagicMock(
                    enabled=False,
                    allow_network=False,
                    fallback="deny",
                )

                with patch(
                    "copaw.agents.tools.shell._execute_subprocess_sync"
                ) as mock_exec:
                    mock_exec.return_value = (0, "hello", "")

                    result = await execute_shell_command("echo hello")
                    assert "hello" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_shell_cwd_inside_user_dir(self, tmp_path):
        """Cwd inside user dir - should allow."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            with patch(
                "copaw.agents.tools.shell._get_sandbox_config"
            ) as mock_config:
                mock_config.return_value = MagicMock(
                    enabled=False,
                    allow_network=False,
                    fallback="deny",
                )

                with patch(
                    "copaw.agents.tools.shell._execute_subprocess_sync"
                ) as mock_exec:
                    mock_exec.return_value = (0, "output", "")

                    result = await execute_shell_command(
                        "echo test", cwd=subdir
                    )
                    assert "output" in result.content[0].get("text", "")
                    # Verify correct working directory was passed
                    mock_exec.assert_called_once()
                    assert str(subdir) in mock_exec.call_args[0][1]