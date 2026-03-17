# src/copaw/agents/tools/sandbox.py
# -*- coding: utf-8 -*-
"""Sandbox executor for shell command isolation using bubblewrap."""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


class SandboxExecutor:
    """Shell 命令沙箱执行器，使用 bubblewrap 实现系统级隔离。"""

    def __init__(
        self,
        user_dir: Path,
        timeout: int = 60,
        allow_network: bool = False,
        readonly_system: bool = True,
        fallback: Literal["deny", "warn"] = "deny",
    ):
        self.user_dir = Path(user_dir).resolve()
        self.timeout = timeout
        self.allow_network = allow_network
        self.readonly_system = readonly_system
        self.fallback = fallback

    @staticmethod
    def is_available() -> bool:
        """检查 bubblewrap 是否可用。"""
        return shutil.which("bwrap") is not None

    def _build_bwrap_command(self, command: str) -> list[str]:
        """构建 bubblewrap 命令参数列表。"""
        cmd = ["bwrap"]
        cmd.append("--unshare-all")
        if self.allow_network:
            cmd.append("--share-net")
        cmd.extend(["--die-with-parent", "--new-session"])
        cmd.extend(["--clearenv"])
        cmd.extend(["--setenv", "PATH", "/usr/bin:/bin:/sbin:/usr/sbin"])
        cmd.extend(["--setenv", "HOME", "/workspace"])
        cmd.extend(["--setenv", "USER", "sandbox"])
        cmd.extend(["--setenv", "SHELL", "/bin/sh"])
        if self.readonly_system:
            cmd.extend(["--ro-bind", "/usr", "/usr"])
            cmd.extend(["--ro-bind", "/bin", "/bin"])
            cmd.extend(["--ro-bind", "/sbin", "/sbin"])
            cmd.extend(["--ro-bind", "/lib", "/lib"])
            cmd.extend(["--ro-bind-try", "/lib64", "/lib64"])
            cmd.extend(["--ro-bind", "/etc", "/etc"])
        cmd.extend(["--proc", "/proc"])
        cmd.extend(["--dev", "/dev"])
        cmd.extend(["--tmpfs", "/tmp"])
        cmd.extend(["--bind", str(self.user_dir), "/workspace"])
        cmd.extend(["--chdir", "/workspace"])
        cmd.extend(["--", "/bin/sh", "-c", command])
        return cmd

    async def execute(self, command: str) -> tuple[int, str, str]:
        """在沙箱中执行命令。"""
        if not self.is_available():
            if self.fallback == "deny":
                raise RuntimeError(
                    "bubblewrap (bwrap) is not available. "
                    "Install it with: apt-get install bubblewrap"
                )
            else:
                logger.warning(
                    "bubblewrap not available, executing without sandbox."
                )
                return await self._execute_fallback(command)

        bwrap_cmd = self._build_bwrap_command(command)

        try:
            proc = await asyncio.create_subprocess_exec(
                *bwrap_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout,
                )
                return (
                    proc.returncode or 0,
                    stdout.decode("utf-8", errors="replace"),
                    stderr.decode("utf-8", errors="replace"),
                )

            except asyncio.TimeoutError:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                return (
                    -1,
                    "",
                    f"Command timed out after {self.timeout} seconds",
                )

        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return (-1, "", str(e))

    async def _execute_fallback(self, command: str) -> tuple[int, str, str]:
        """降级执行：无沙箱。"""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.user_dir),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )
            return (
                proc.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        except asyncio.TimeoutError:
            proc.terminate()
            await proc.wait()
            return (
                    -1,
                    "",
                    f"Command timed out after {self.timeout} seconds",
                )
        except Exception as e:
            return (-1, "", str(e))