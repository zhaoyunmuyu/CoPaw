# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
"""The shell command tool."""

import asyncio
import locale
import logging
import subprocess
from pathlib import Path
from typing import Optional

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

from .path_validator import PathValidator
from .sandbox import SandboxExecutor


def _get_sandbox_config():
    """Get sandbox configuration."""
    from ...config import load_config

    config = load_config()
    return config.sandbox


def _execute_subprocess_sync(
    cmd: str,
    cwd: str,
    timeout: int,
) -> tuple[int, str, str]:
    """Execute subprocess synchronously in a thread.

    This function runs in a separate thread to avoid Windows asyncio
    subprocess limitations.

    Args:
        cmd (`str`):
            The shell command to execute.
        cwd (`str`):
            The working directory for the command execution.
        timeout (`int`):
            The maximum time (in seconds) allowed for the command to run.

    Returns:
        `tuple[int, str, str]`:
            A tuple containing the return code, standard output, and
            standard error of the executed command. If timeout occurs, the
            return code will be -1 and stderr will contain timeout information.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            encoding=locale.getpreferredencoding(False) or "utf-8",
            errors="replace",
        )
        return (
            result.returncode,
            result.stdout.strip("\n"),
            result.stderr.strip("\n"),
        )
    except subprocess.TimeoutExpired:
        return (
            -1,
            "",
            f"Command execution exceeded the timeout of {timeout} seconds.",
        )
    except Exception as e:
        return -1, "", str(e)


# pylint: disable=too-many-branches, too-many-statements
async def execute_shell_command(
    command: str,
    timeout: int = 60,
    cwd: Optional[Path] = None,
) -> ToolResponse:
    """Execute given command in sandbox and return the result.

    Args:
        command: The shell command to execute.
        timeout: Maximum time (in seconds) for command execution.
        cwd: Working directory. If None, defaults to user directory.

    Returns:
        ToolResponse with returncode, stdout, and stderr.
    """
    cmd = (command or "").strip()

    # Get user directory and validate cwd
    user_dir = PathValidator.get_user_dir()

    if cwd is not None:
        is_valid, resolved, error = PathValidator.validate_path(cwd)
        if not is_valid:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=error,
                    ),
                ],
            )
        working_dir = Path(resolved)
    else:
        working_dir = user_dir

    # Get sandbox config
    sandbox_config = _get_sandbox_config()

    if sandbox_config.enabled and SandboxExecutor.is_available():
        # Execute in sandbox
        executor = SandboxExecutor(
            user_dir=working_dir,
            timeout=timeout,
            allow_network=sandbox_config.allow_network,
            fallback=sandbox_config.fallback,
        )
        try:
            returncode, stdout, stderr = await executor.execute(cmd)
        except RuntimeError as e:
            # Sandbox unavailable with deny fallback
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=str(e),
                    ),
                ],
            )
    else:
        # Fallback: direct execution (when sandbox disabled)
        if sandbox_config.enabled:
            # Sandbox enabled but unavailable
            if sandbox_config.fallback == "deny":
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text="Sandbox is not available. "
                            "Install bubblewrap: apt-get install bubblewrap",
                        ),
                    ],
                )
            # fallback == "warn": log warning and continue
            logging.getLogger(__name__).warning(
                "Sandbox unavailable, executing without isolation"
            )

        # Direct execution
        returncode, stdout, stderr = _execute_subprocess_sync(
            cmd,
            str(working_dir),
            timeout,
        )

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=(
                    f"<returncode>{returncode}</returncode>\n"
                    f"<stdout>\n{stdout}\n</stdout>\n"
                    f"<stderr>\n{stderr}\n</stderr>"
                ),
            ),
        ],
    )