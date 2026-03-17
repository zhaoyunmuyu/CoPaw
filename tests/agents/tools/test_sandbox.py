# tests/agents/tools/test_sandbox.py
# -*- coding: utf-8 -*-
"""Tests for SandboxExecutor component."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from copaw.agents.tools.sandbox import SandboxExecutor


class TestSandboxExecutorAvailability:
    """Tests for bubblewrap availability check."""

    def test_is_available_returns_true_when_bwrap_exists(self):
        """bwrap 存在时返回 True"""
        with patch("shutil.which", return_value="/usr/bin/bwrap"):
            assert SandboxExecutor.is_available() is True

    def test_is_available_returns_false_when_bwrap_missing(self):
        """bwrap 不存在时返回 False"""
        with patch("shutil.which", return_value=None):
            assert SandboxExecutor.is_available() is False


class TestSandboxExecutorExecute:
    """Tests for execute method."""

    @pytest.mark.asyncio
    async def test_execute_simple_command(self, tmp_path):
        """执行简单命令 - 应成功"""
        with patch.object(
            SandboxExecutor, "is_available", return_value=True
        ):
            executor = SandboxExecutor(user_dir=tmp_path, timeout=30)

            with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                mock_proc = MagicMock()
                mock_proc.communicate = AsyncMock(return_value=(b"hello\n", b""))
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc

                returncode, stdout, stderr = await executor.execute("echo hello")

                assert returncode == 0
                assert "hello" in stdout


class TestSandboxExecutorFallback:
    """Tests for fallback behavior when bubblewrap unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_deny_raises_error(self, tmp_path):
        """配置 deny 时，bubblewrap 不可用应抛出错误"""
        with patch.object(
            SandboxExecutor, "is_available", return_value=False
        ):
            executor = SandboxExecutor(
                user_dir=tmp_path,
                timeout=30,
                fallback="deny",
            )

            with pytest.raises(RuntimeError) as exc_info:
                await executor.execute("echo hello")

            assert "bubblewrap" in str(exc_info.value).lower()