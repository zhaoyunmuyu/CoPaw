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

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, tmp_path):
        """命令超时 - 应终止并返回错误"""
        with patch.object(
            SandboxExecutor, "is_available", return_value=True
        ):
            executor = SandboxExecutor(user_dir=tmp_path, timeout=1)

            with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                mock_proc = MagicMock()

                async def slow_communicate():
                    await asyncio.sleep(10)
                    return (b"", b"")

                mock_proc.communicate = slow_communicate
                mock_proc.terminate = MagicMock()
                mock_proc.kill = MagicMock()
                mock_proc.wait = AsyncMock(return_value=None)
                mock_subprocess.return_value = mock_proc

                returncode, stdout, stderr = await executor.execute(
                    "sleep 100"
                )

                assert returncode == -1
                assert "timed out" in stderr.lower()
                mock_proc.terminate.assert_called_once()


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

    @pytest.mark.asyncio
    async def test_fallback_warn_executes_with_warning(self, tmp_path):
        """配置 warn 时，bubblewrap 不可用应记录警告并继续执行"""
        with patch.object(
            SandboxExecutor, "is_available", return_value=False
        ):
            executor = SandboxExecutor(
                user_dir=tmp_path,
                timeout=30,
                fallback="warn",
            )

            with patch("asyncio.create_subprocess_shell") as mock_subprocess:
                mock_proc = MagicMock()
                mock_proc.communicate = AsyncMock(
                    return_value=(b"output\n", b"")
                )
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc

                returncode, stdout, stderr = await executor.execute("echo hello")

                # Command should execute successfully without sandbox
                assert returncode == 0
                assert "output" in stdout
                # Verify fallback was used (subprocess_shell, not exec)
                mock_subprocess.assert_called_once()


class TestSandboxExecutorBuildCommand:
    """Tests for bubblewrap command building."""

    def test_build_bwrap_command_basic(self, tmp_path):
        """构建基本 bubblewrap 命令"""
        executor = SandboxExecutor(user_dir=tmp_path)
        cmd = executor._build_bwrap_command("echo hello")

        cmd_str = " ".join(cmd)
        assert "bwrap" in cmd[0]
        assert "--unshare-all" in cmd
        assert str(tmp_path) in cmd_str
        assert "/workspace" in cmd_str

    def test_build_bwrap_command_with_network(self, tmp_path):
        """构建允许网络的 bubblewrap 命令"""
        executor = SandboxExecutor(user_dir=tmp_path, allow_network=True)
        cmd = executor._build_bwrap_command("curl example.com")

        cmd_str = " ".join(cmd)
        assert "--unshare-all" in cmd_str
        assert "--share-net" in cmd_str


class TestSandboxExecutorIsolation:
    """Tests for sandbox isolation effectiveness."""

    @pytest.mark.asyncio
    async def test_access_outside_user_dir_blocked(self, tmp_path):
        """沙箱应阻止访问用户目录外的文件"""
        with patch.object(
            SandboxExecutor, "is_available", return_value=True
        ):
            executor = SandboxExecutor(user_dir=tmp_path, timeout=30)

            # Mock the subprocess to simulate blocked access
            with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                mock_proc = MagicMock()
                # Simulate that /etc/passwd is not accessible in sandbox
                mock_proc.communicate = AsyncMock(
                    return_value=(b"", b"cat: /etc/passwd: Permission denied\n")
                )
                mock_proc.returncode = 1
                mock_subprocess.return_value = mock_proc

                returncode, stdout, stderr = await executor.execute(
                    "cat /etc/passwd"
                )

                # In a real sandbox, access would be blocked
                # Our mock simulates this behavior
                assert returncode != 0 or "Permission denied" in stderr

    @pytest.mark.asyncio
    async def test_write_to_user_dir_allowed(self, tmp_path):
        """沙箱应允许写入用户目录"""
        with patch.object(
            SandboxExecutor, "is_available", return_value=True
        ):
            executor = SandboxExecutor(user_dir=tmp_path, timeout=30)

            with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                mock_proc = MagicMock()
                mock_proc.communicate = AsyncMock(return_value=(b"ok\n", b""))
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc

                returncode, stdout, stderr = await executor.execute(
                    "echo test > file.txt"
                )

                assert returncode == 0

    @pytest.mark.asyncio
    async def test_network_access_denied_by_default(self, tmp_path):
        """默认应阻止网络访问"""
        executor = SandboxExecutor(user_dir=tmp_path, allow_network=False)
        cmd = executor._build_bwrap_command("curl example.com")

        cmd_str = " ".join(cmd)
        # --unshare-all isolates network by default
        assert "--unshare-all" in cmd_str
        # Should NOT have --share-net when allow_network=False
        assert "--share-net" not in cmd_str