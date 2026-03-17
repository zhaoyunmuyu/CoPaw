# 用户权限隔离实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现用户权限隔离，确保用户只能操作自己目录下的文件，Shell 命令在沙箱中执行。

**Architecture:** 通过 PathValidator 组件验证所有文件路径，使用 bubblewrap 沙箱隔离 Shell 命令执行。核心组件独立于工具层，便于测试和维护。

**Tech Stack:** Python 3.9+, Pydantic v2, asyncio, bubblewrap

**Spec:** [docs/superpowers/specs/2026-03-17-user-permission-isolation-design.md](../specs/2026-03-17-user-permission-isolation-design.md)

---

## File Structure

```
src/copaw/
├── agents/tools/
│   ├── path_validator.py    # NEW: 路径验证器
│   ├── sandbox.py           # NEW: Shell 沙箱执行器
│   ├── audit.py             # NEW: 审计日志工具
│   ├── file_io.py           # MODIFY: 添加路径验证
│   ├── file_search.py       # MODIFY: 添加路径验证
│   └── shell.py             # MODIFY: 使用沙箱执行
├── config/
│   └── config.py            # MODIFY: 添加 SandboxConfig
tests/
└── agents/tools/
    ├── test_path_validator.py  # NEW: PathValidator 测试
    ├── test_sandbox.py          # NEW: SandboxExecutor 测试
    └── test_audit.py            # NEW: 审计日志测试
```

---

## Task 1: 实现 PathValidator 组件

**Files:**
- Create: `src/copaw/agents/tools/path_validator.py`
- Test: `tests/agents/tools/test_path_validator.py`

### 1.1 编写 PathValidator 测试（RED）

- [ ] **Step 1: 创建测试文件**

```python
# tests/agents/tools/test_path_validator.py
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/agents/tools/test_path_validator.py -v`
Expected: FAIL (module not found)

### 1.2 实现 PathValidator（GREEN）

- [ ] **Step 3: 创建 PathValidator 实现**

```python
# src/copaw/agents/tools/path_validator.py
# -*- coding: utf-8 -*-
"""Path validator for user permission isolation.

This module provides path validation to ensure users can only access
files within their own directory.
"""

import logging
from pathlib import Path
from typing import Union

from ...constant import get_request_working_dir

logger = logging.getLogger(__name__)


class PathValidator:
    """路径验证器，确保用户只能访问自己的目录。"""

    @staticmethod
    def get_user_dir() -> Path:
        """获取当前请求用户的目录。

        Returns:
            Path: 用户工作目录的绝对路径
        """
        return get_request_working_dir()

    @staticmethod
    def validate_path(path: Union[str, Path]) -> tuple[bool, Path, str]:
        """验证路径是否在用户目录内。

        Args:
            path: 待验证的路径（绝对或相对）

        Returns:
            tuple[bool, Path, str]: (是否有效, 解析后的路径, 错误信息)
        """
        if not path:
            return False, Path(), "Invalid path: empty path"

        user_dir = PathValidator.get_user_dir()

        try:
            input_path = Path(path)

            # 解析路径：相对路径基于用户目录解析
            if input_path.is_absolute():
                resolved = input_path.resolve()
            else:
                resolved = (user_dir / input_path).resolve()

            # 检查是否在用户目录内
            if resolved.is_relative_to(user_dir):
                return True, resolved, ""
            else:
                logger.warning(
                    "Path validation failed: path outside user directory"
                )
                return (
                    False,
                    resolved,
                    "Permission denied: path is outside allowed directory",
                )

        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False, Path(), f"Invalid path: {e}"

    @staticmethod
    def resolve_and_validate(path: Union[str, Path]) -> Path:
        """解析并验证路径，失败时抛出 PermissionError。

        用于简化调用代码，当只需要成功情况时使用。

        Args:
            path: 待验证的路径

        Returns:
            Path: 解析后的绝对路径

        Raises:
            PermissionError: 当路径在用户目录外时
        """
        is_valid, resolved, error = PathValidator.validate_path(path)
        if not is_valid:
            raise PermissionError(error)
        return resolved
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/agents/tools/test_path_validator.py -v`
Expected: PASS

### 1.3 提交 PathValidator

- [ ] **Step 5: 提交代码**

```bash
git add src/copaw/agents/tools/path_validator.py tests/agents/tools/test_path_validator.py
git commit -m "feat: add PathValidator for user permission isolation

- Add PathValidator class with path validation logic
- Validate paths are within user directory
- Handle symlink resolution with security checks
- Add comprehensive unit tests"
```

---

## Task 2: 实现 SandboxExecutor 组件

**Files:**
- Create: `src/copaw/agents/tools/sandbox.py`
- Test: `tests/agents/tools/test_sandbox.py`

### 2.1 编写 SandboxExecutor 测试（RED）

- [ ] **Step 1: 创建测试文件**

```python
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

            # Mock the subprocess execution
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
                # Simulate timeout using AsyncMock
                async def slow_communicate():
                    await asyncio.sleep(10)
                    return (b"", b"")

                mock_proc.communicate = slow_communicate
                mock_proc.terminate = MagicMock()
                mock_proc.kill = MagicMock()
                mock_proc.wait = AsyncMock(return_value=None)
                mock_subprocess.return_value = mock_proc

                with pytest.raises(asyncio.TimeoutError):
                    await executor.execute("sleep 100")


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
    async def test_fallback_warn_executes_with_warning(self, tmp_path, caplog):
        """配置 warn 时，bubblewrap 不可用应记录警告并继续执行"""
        import logging
        caplog.set_level(logging.WARNING)

        with patch.object(
            SandboxExecutor, "is_available", return_value=False
        ):
            executor = SandboxExecutor(
                user_dir=tmp_path,
                timeout=30,
                fallback="warn",
            )

            # Mock subprocess for fallback execution
            with patch("asyncio.create_subprocess_shell") as mock_subprocess:
                mock_proc = MagicMock()
                mock_proc.communicate = AsyncMock(return_value=(b"output\n", b""))
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc

                returncode, stdout, stderr = await executor.execute("echo hello")

                assert returncode == 0
                assert any(
                    "bubblewrap" in record.message.lower()
                    for record in caplog.records
                )


class TestSandboxExecutorBuildCommand:
    """Tests for bubblewrap command building."""

    def test_build_bwrap_command_basic(self, tmp_path):
        """构建基本 bubblewrap 命令"""
        executor = SandboxExecutor(user_dir=tmp_path)
        cmd = executor._build_bwrap_command("echo hello")

        assert "bwrap" in cmd[0] or "bwrap" in " ".join(cmd)
        assert "--unshare-all" in cmd
        assert str(tmp_path) in " ".join(cmd) or "/workspace" in " ".join(cmd)

    def test_build_bwrap_command_with_network(self, tmp_path):
        """构建允许网络的 bubblewrap 命令"""
        executor = SandboxExecutor(user_dir=tmp_path, allow_network=True)
        cmd = executor._build_bwrap_command("curl example.com")

        # Should NOT have --unshare-net when allow_network=True
        cmd_str = " ".join(cmd)
        assert "--unshare-all" in cmd_str  # Still unshare-all, but net will be shared
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/agents/tools/test_sandbox.py -v`
Expected: FAIL (module not found)

### 2.2 实现 SandboxExecutor（GREEN）

- [ ] **Step 3: 创建 SandboxExecutor 实现**

```python
# src/copaw/agents/tools/sandbox.py
# -*- coding: utf-8 -*-
"""Sandbox executor for shell command isolation using bubblewrap.

This module provides secure command execution within a sandboxed environment
to prevent users from accessing files outside their directory.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Literal, Optional

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
        """初始化沙箱执行器。

        Args:
            user_dir: 用户工作目录
            timeout: 命令超时时间（秒）
            allow_network: 是否允许网络访问
            readonly_system: 系统目录是否只读
            fallback: bubblewrap 不可用时的处理策略
        """
        self.user_dir = Path(user_dir).resolve()
        self.timeout = timeout
        self.allow_network = allow_network
        self.readonly_system = readonly_system
        self.fallback = fallback

    @staticmethod
    def is_available() -> bool:
        """检查 bubblewrap 是否可用。

        Returns:
            bool: True 如果 bubblewrap 已安装且可执行
        """
        return shutil.which("bwrap") is not None

    def _build_bwrap_command(self, command: str) -> list[str]:
        """构建 bubblewrap 命令参数列表。

        Args:
            command: 要执行的 shell 命令

        Returns:
            list[str]: bubblewrap 命令及参数
        """
        cmd = ["bwrap"]

        # 命名空间隔离
        cmd.append("--unshare-all")
        if self.allow_network:
            # 允许网络时，不隔离网络命名空间
            cmd.append("--share-net")

        # 进程管理
        cmd.extend(["--die-with-parent", "--new-session"])

        # 环境变量
        cmd.extend(["--clearenv"])
        cmd.extend(["--setenv", "PATH", "/usr/bin:/bin:/sbin:/usr/sbin"])
        cmd.extend(["--setenv", "HOME", "/workspace"])
        cmd.extend(["--setenv", "USER", "sandbox"])
        cmd.extend(["--setenv", "SHELL", "/bin/sh"])

        # 系统目录挂载（只读）
        if self.readonly_system:
            cmd.extend(["--ro-bind", "/usr", "/usr"])
            cmd.extend(["--ro-bind", "/bin", "/bin"])
            cmd.extend(["--ro-bind", "/sbin", "/sbin"])
            cmd.extend(["--ro-bind", "/lib", "/lib"])
            cmd.extend(["--ro-bind-try", "/lib64", "/lib64"])  # x86_64 only
            cmd.extend(["--ro-bind", "/etc", "/etc"])

        # proc 和 dev
        cmd.extend(["--proc", "/proc"])
        cmd.extend(["--dev", "/dev"])

        # 临时文件系统
        cmd.extend(["--tmpfs", "/tmp"])

        # 用户目录挂载（读写）
        cmd.extend(["--bind", str(self.user_dir), "/workspace"])

        # 工作目录
        cmd.extend(["--chdir", "/workspace"])

        # 执行命令
        cmd.extend(["--", "/bin/sh", "-c", command])

        return cmd

    async def execute(self, command: str) -> tuple[int, str, str]:
        """在沙箱中执行命令。

        Args:
            command: 要执行的 shell 命令

        Returns:
            tuple[int, str, str]: (返回码, 标准输出, 标准错误)

        Raises:
            RuntimeError: 当 bubblewrap 不可用且 fallback="deny" 时
        """
        # 检查 bubblewrap 可用性
        if not self.is_available():
            if self.fallback == "deny":
                raise RuntimeError(
                    "bubblewrap (bwrap) is not available. "
                    "Install it with: apt-get install bubblewrap"
                )
            else:
                logger.warning(
                    "bubblewrap not available, executing without sandbox. "
                    "This is less secure!"
                )
                return await self._execute_fallback(command)

        # 构建 bubblewrap 命令
        bwrap_cmd = self._build_bwrap_command(command)

        try:
            # 创建子进程
            proc = await asyncio.create_subprocess_exec(
                *bwrap_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # 带超时执行
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
                # 超时处理
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
            return -1, "", str(e)

    async def _execute_fallback(self, command: str) -> tuple[int, str, str]:
        """降级执行：无沙箱，直接在用户目录执行。

        Args:
            command: 要执行的命令

        Returns:
            tuple[int, str, str]: (返回码, 标准输出, 标准错误)
        """
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
            return -1, "", f"Command timed out after {self.timeout} seconds"
        except Exception as e:
            return -1, "", str(e)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/agents/tools/test_sandbox.py -v`
Expected: PASS

### 2.3 提交 SandboxExecutor

- [ ] **Step 5: 提交代码**

```bash
git add src/copaw/agents/tools/sandbox.py tests/agents/tools/test_sandbox.py
git commit -m "feat: add SandboxExecutor for shell command isolation

- Add SandboxExecutor using bubblewrap for system-level isolation
- Support network access toggle
- Implement fallback mode when bubblewrap unavailable
- Add comprehensive unit tests"
```

---

## Task 2.5: 实现审计日志模块

**Files:**
- Create: `src/copaw/agents/tools/audit.py`
- Test: `tests/agents/tools/test_audit.py`

### 2.5.1 编写审计日志测试（RED）

- [ ] **Step 1: 创建测试文件**

```python
# tests/agents/tools/test_audit.py
# -*- coding: utf-8 -*-
"""Tests for audit logging module."""

import logging
import pytest
from unittest.mock import patch

from copaw.agents.tools.audit import AuditEvent, log_audit


class TestAuditEvent:
    """Tests for AuditEvent constants."""

    def test_audit_event_constants_exist(self):
        """审计事件常量应存在"""
        assert hasattr(AuditEvent, "PATH_VALIDATION_FAILED")
        assert hasattr(AuditEvent, "SANDBOX_EXECUTE")
        assert hasattr(AuditEvent, "SANDBOX_UNAVAILABLE")
        assert hasattr(AuditEvent, "PERMISSION_DENIED")


class TestLogAudit:
    """Tests for log_audit function."""

    def test_log_audit_path_validation_failed(self, caplog):
        """记录路径验证失败事件"""
        with caplog.at_level(logging.INFO, logger="copaw.audit"):
            log_audit(
                event=AuditEvent.PATH_VALIDATION_FAILED,
                user_id="test_user",
                details={"path_hint": "outside_user_dir"},
            )

        assert any(
            "test_user" in record.message or "test_user" in str(record.__dict__)
            for record in caplog.records
        )

    def test_log_audit_sandbox_execute(self, caplog):
        """记录沙箱执行事件"""
        with caplog.at_level(logging.INFO, logger="copaw.audit"):
            log_audit(
                event=AuditEvent.SANDBOX_EXECUTE,
                user_id="test_user",
                details={"command_hash": "abc123", "returncode": 0},
            )

        assert len(caplog.records) >= 1

    def test_log_audit_does_not_leak_full_paths(self, caplog):
        """审计日志不应泄露完整路径"""
        with caplog.at_level(logging.INFO, logger="copaw.audit"):
            log_audit(
                event=AuditEvent.PATH_VALIDATION_FAILED,
                user_id="test_user",
                details={"path": "/etc/passwd"},  # 不应该这样传递
            )

        # 验证日志中没有完整路径
        for record in caplog.records:
            msg = record.getMessage()
            assert "/etc/passwd" not in msg
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/agents/tools/test_audit.py -v`
Expected: FAIL (module not found)

### 2.5.2 实现审计日志模块（GREEN）

- [ ] **Step 3: 创建审计日志模块**

```python
# src/copaw/agents/tools/audit.py
# -*- coding: utf-8 -*-
"""Audit logging for security events.

This module provides audit logging for security-relevant events
like path validation failures and sandbox executions.
"""

import hashlib
import logging
from typing import Any

# 审计日志专用 logger
audit_logger = logging.getLogger("copaw.audit")


class AuditEvent:
    """审计事件类型常量。"""

    PATH_VALIDATION_FAILED = "path_validation_failed"
    SANDBOX_EXECUTE = "sandbox_execute"
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"
    PERMISSION_DENIED = "permission_denied"


def _sanitize_details(details: dict[str, Any]) -> dict[str, Any]:
    """清理详情字典，移除敏感信息。

    Args:
        details: 原始详情字典

    Returns:
        清理后的详情字典
    """
    sanitized = {}
    sensitive_keys = {"path", "file_path", "full_path", "absolute_path"}

    for key, value in details.items():
        if key.lower() in sensitive_keys:
            # 不记录完整路径，只记录提示
            sanitized[f"{key}_hint"] = "provided_but_redacted"
        elif isinstance(value, str) and len(value) > 100:
            # 截断过长的字符串
            sanitized[key] = value[:100] + "..."
        else:
            sanitized[key] = value

    return sanitized


def log_audit(event: str, user_id: str, details: dict[str, Any]) -> None:
    """记录审计日志。

    Args:
        event: 事件类型（使用 AuditEvent 常量）
        user_id: 用户标识
        details: 事件详情（会被清理以移除敏感信息）
    """
    sanitized_details = _sanitize_details(details)

    audit_logger.info(
        f"event={event} user={user_id} details={sanitized_details}"
    )


def hash_command(command: str) -> str:
    """计算命令的哈希值用于审计日志。

    Args:
        command: 要哈希的命令

    Returns:
        命令哈希的前 16 个字符
    """
    return hashlib.sha256(command.encode()).hexdigest()[:16]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/agents/tools/test_audit.py -v`
Expected: PASS

### 2.5.3 提交审计日志模块

- [ ] **Step 5: 提交代码**

```bash
git add src/copaw/agents/tools/audit.py tests/agents/tools/test_audit.py
git commit -m "feat: add audit logging for security events

- Add AuditEvent constants for event types
- Add log_audit function with sensitive data sanitization
- Add hash_command utility for command hashing
- Add comprehensive unit tests"
```

---

## Task 3: 添加沙箱配置到 config.py

**Files:**
- Modify: `src/copaw/config/config.py`

### 3.1 添加配置类

- [ ] **Step 1: 添加 SandboxLimitsConfig 和 SandboxConfig 类**

在 `src/copaw/config/config.py` 文件末尾（`Config` 类之前）添加：

```python
class SandboxLimitsConfig(BaseModel):
    """沙箱资源限制配置。"""

    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    max_pids: int = 100
    max_file_size_mb: int = 100
    max_open_files: int = 1000


class SandboxConfig(BaseModel):
    """沙箱配置。"""

    enabled: bool = True
    backend: Literal["bubblewrap"] = "bubblewrap"
    fallback: Literal["deny", "warn"] = "deny"
    allow_network: bool = False
    timeout: int = 60
    limits: SandboxLimitsConfig = SandboxLimitsConfig()
```

- [ ] **Step 2: 在 Config 类中添加 sandbox 字段**

在 `Config` 类中添加 `sandbox` 字段：

```python
class Config(BaseModel):
    # ... 现有字段 ...
    sandbox: SandboxConfig = SandboxConfig()
```

- [ ] **Step 3: 运行测试验证配置加载**

Run: `pytest tests/test_config.py -v -k sandbox 2>/dev/null || python -c "from copaw.config.config import SandboxConfig; c = SandboxConfig(); print(f'SandboxConfig: enabled={c.enabled}, fallback={c.fallback}')"`
Expected: 配置类可正常导入和实例化

### 3.2 提交配置更改

- [ ] **Step 4: 提交代码**

```bash
git add src/copaw/config/config.py
git commit -m "feat: add SandboxConfig to configuration

- Add SandboxLimitsConfig for resource limits
- Add SandboxConfig for sandbox settings
- Integrate into main Config model"
```

---

## Task 4: 改造 file_io.py

**Files:**
- Modify: `src/copaw/agents/tools/file_io.py`
- Test: `tests/agents/tools/test_file_io.py` (新增权限测试)

### 4.1 编写权限隔离测试（RED）

- [ ] **Step 1: 创建 file_io 权限测试**

在 `tests/agents/tools/test_file_io.py` 中添加：

```python
# tests/agents/tools/test_file_io.py
# -*- coding: utf-8 -*-
"""Tests for file_io permission isolation."""

import pytest
from pathlib import Path
from unittest.mock import patch

from copaw.agents.tools.file_io import read_file, write_file


class TestFileIOPermissionIsolation:
    """Tests for file_io permission isolation."""

    @pytest.mark.asyncio
    async def test_read_file_outside_user_dir_denied(self, tmp_path):
        """读取用户目录外文件 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await read_file("/etc/passwd")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_write_file_outside_user_dir_denied(self, tmp_path):
        """写入用户目录外 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await write_file("/etc/malicious.txt", "data")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_read_file_inside_user_dir_allowed(self, tmp_path):
        """读取用户目录内文件 - 应成功"""
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
        """路径遍历攻击 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await read_file("../../../etc/passwd")
            assert "Permission denied" in result.content[0].get("text", "")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/agents/tools/test_file_io.py -v`
Expected: FAIL (路径遍历未被阻止)

### 4.2 修改 _resolve_file_path 函数（GREEN）

- [ ] **Step 3: 在文件顶部添加导入**

在 `src/copaw/agents/tools/file_io.py` 的导入部分（约第 11 行后）添加：

```python
from .path_validator import PathValidator
```

- [ ] **Step 4: 替换 _resolve_file_path 函数**

找到现有的 `_resolve_file_path` 函数（搜索 `def _resolve_file_path`），替换为：

```python
def _resolve_file_path(file_path: str) -> str:
    """解析并验证路径，失败时抛出 PermissionError。

    Args:
        file_path: 输入文件路径（绝对或相对）

    Returns:
        str: 解析后的绝对路径

    Raises:
        PermissionError: 当路径在用户目录外时
    """
    return str(PathValidator.resolve_and_validate(file_path))
```

- [ ] **Step 5: 在各函数中捕获 PermissionError**

在 `read_file`、`write_file`、`edit_file`、`append_file` 函数开头添加 try-except：

```python
async def read_file(...):
    try:
        file_path = _resolve_file_path(file_path)
    except PermissionError as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=str(e),
                ),
            ],
        )
    # ... 原有逻辑 ...
```

- [ ] **Step 6: 运行测试验证通过**

Run: `pytest tests/agents/tools/test_file_io.py -v`
Expected: PASS

### 4.3 提交更改

- [ ] **Step 7: 提交代码**

```bash
git add src/copaw/agents/tools/file_io.py tests/agents/tools/test_file_io.py
git commit -m "feat: add path validation to file_io tools

- Replace _resolve_file_path with PathValidator integration
- Add PermissionError handling in all file operations
- Ensure users can only access files in their directory
- Add permission isolation tests"
```

---

## Task 5: 改造 file_search.py

**Files:**
- Modify: `src/copaw/agents/tools/file_search.py`
- Test: `tests/agents/tools/test_file_search.py` (新增权限测试)

### 5.1 编写权限隔离测试（RED）

- [ ] **Step 1: 创建 file_search 权限测试**

在 `tests/agents/tools/test_file_search.py` 中添加：

```python
# tests/agents/tools/test_file_search.py
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
        """搜索用户目录外 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await grep_search("pattern", path="/etc")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_glob_search_outside_user_dir_denied(self, tmp_path):
        """glob 搜索用户目录外 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await glob_search("*.txt", path="/etc")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_grep_search_inside_user_dir_allowed(self, tmp_path):
        """搜索用户目录内 - 应成功"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await grep_search("hello")
            assert "hello" in result.content[0].get("text", "")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/agents/tools/test_file_search.py -v`
Expected: FAIL (路径验证未生效)

### 5.2 修改 grep_search 和 glob_search（GREEN）

- [ ] **Step 3: 在文件顶部添加导入**

在 `src/copaw/agents/tools/file_search.py` 的导入部分添加：

```python
from .path_validator import PathValidator
```

- [ ] **Step 4: 修改 grep_search 函数**

找到 `grep_search` 函数（搜索 `async def grep_search`），修改路径处理部分：

```python
async def grep_search(...):
    # ... 现有参数检查 ...

    # 使用 PathValidator 验证路径
    user_dir = PathValidator.get_user_dir()

    if path:
        is_valid, search_root, error = PathValidator.validate_path(path)
        if not is_valid:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=error,
                    ),
                ],
            )
        search_root = Path(search_root)
    else:
        search_root = user_dir

    # ... 后续逻辑不变 ...
```

- [ ] **Step 5: 修改 glob_search 函数**

同样修改 `glob_search` 函数的路径处理部分。

- [ ] **Step 6: 运行测试验证通过**

Run: `pytest tests/agents/tools/test_file_search.py -v`
Expected: PASS

### 5.3 提交更改

- [ ] **Step 7: 提交代码**

```bash
git add src/copaw/agents/tools/file_search.py tests/agents/tools/test_file_search.py
git commit -m "feat: add path validation to file_search tools

- Validate search paths with PathValidator
- Ensure grep_search and glob_search are restricted to user directory
- Add permission isolation tests"
```

---

## Task 6: 改造 shell.py

**Files:**
- Modify: `src/copaw/agents/tools/shell.py`
- Test: `tests/agents/tools/test_shell.py` (新增沙箱测试)

### 6.1 编写沙箱集成测试（RED）

- [ ] **Step 1: 创建 shell 沙箱测试**

在 `tests/agents/tools/test_shell.py` 中添加：

```python
# tests/agents/tools/test_shell.py (追加内容)
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
        """指定外部 cwd - 应拒绝"""
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
    async def test_shell_with_sandbox_disabled(self, tmp_path):
        """沙箱禁用 - 直接执行"""
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
                result = await execute_shell_command("echo hello")
                # 应该执行成功（无沙箱）
                assert "hello" in result.content[0].get("text", "") or "success" in result.content[0].get("text", "").lower()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/agents/tools/test_shell.py -v`
Expected: FAIL (沙箱集成未实现)

### 6.2 实现 SandboxExecutor 集成（GREEN）

- [ ] **Step 3: 在文件顶部添加导入**

在 `src/copaw/agents/tools/shell.py` 的现有导入后添加：

```python
from .path_validator import PathValidator
from .sandbox import SandboxExecutor
```

- [ ] **Step 4: 添加获取沙箱配置的辅助函数**

在文件中添加辅助函数（可放在 `_execute_subprocess_sync` 函数之前）：

```python
def _get_sandbox_config():
    """获取沙箱配置。"""
    from ...config import load_config

    config = load_config()
    return config.sandbox
```

- [ ] **Step 5: 修改 execute_shell_command 函数**

替换 `execute_shell_command` 函数的主要逻辑。找到函数定义（搜索 `async def execute_shell_command`），替换为：

```python
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

    # 获取用户目录并验证 cwd
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
        working_dir = resolved
    else:
        working_dir = user_dir

    # 获取沙箱配置
    sandbox_config = _get_sandbox_config()

    if not sandbox_config.enabled:
        # 沙箱禁用，使用原有逻辑直接执行
        return await _execute_directly(cmd, working_dir, timeout)

    # 使用 SandboxExecutor
    executor = SandboxExecutor(
        user_dir=working_dir,
        timeout=timeout,
        allow_network=sandbox_config.allow_network,
        fallback=sandbox_config.fallback,
    )

    try:
        returncode, stdout, stderr = await executor.execute(cmd)
    except RuntimeError as e:
        # bubblewrap 不可用且 fallback=deny
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: {e}",
                ),
            ],
        )

    # 格式化响应
    if returncode == 0:
        response_text = stdout if stdout else "Command executed successfully."
    else:
        response_parts = [f"Command failed with exit code {returncode}."]
        if stdout:
            response_parts.append(f"\n[stdout]\n{stdout}")
        if stderr:
            response_parts.append(f"\n[stderr]\n{stderr}")
        response_text = "".join(response_parts)

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=response_text,
            ),
        ],
    )


async def _execute_directly(cmd: str, working_dir: Path, timeout: int):
    """直接执行命令（沙箱禁用时使用）。

    保持原有的 subprocess 执行逻辑。
    """
    import sys
    import locale

    try:
        if sys.platform == "win32":
            returncode, stdout_str, stderr_str = await asyncio.to_thread(
                _execute_subprocess_sync,
                cmd,
                str(working_dir),
                timeout,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                bufsize=0,
                cwd=str(working_dir),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
                encoding = locale.getpreferredencoding(False) or "utf-8"
                stdout_str = stdout.decode(encoding, errors="replace").strip("\n")
                stderr_str = stderr.decode(encoding, errors="replace").strip("\n")
                returncode = proc.returncode

            except asyncio.TimeoutError:
                stderr_suffix = (
                    f"TimeoutError: Command exceeded {timeout} seconds."
                )
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                returncode = -1
                stdout_str = ""
                stderr_str = stderr_suffix

        # 格式化响应
        if returncode == 0:
            response_text = stdout_str if stdout_str else "Command executed successfully."
        else:
            response_parts = [f"Command failed with exit code {returncode}."]
            if stdout_str:
                response_parts.append(f"\n[stdout]\n{stdout_str}")
            if stderr_str:
                response_parts.append(f"\n[stderr]\n{stderr_str}")
            response_text = "".join(response_parts)

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=response_text,
                ),
            ],
        )

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Shell command execution failed due to\n{e}",
                ),
            ],
        )
```

- [ ] **Step 6: 运行测试验证通过**

Run: `pytest tests/agents/tools/test_shell.py -v`
Expected: PASS

### 6.3 提交更改

- [ ] **Step 7: 提交代码**

```bash
git add src/copaw/agents/tools/shell.py tests/agents/tools/test_shell.py
git commit -m "feat: integrate SandboxExecutor into shell command execution

- Replace direct subprocess execution with sandboxed execution
- Add path validation for cwd parameter
- Support sandbox configuration (enabled, fallback, allow_network)
- Add _execute_directly for fallback when sandbox disabled
- Add sandbox integration tests"
```

---

## Task 7: 更新工具模块导出

**Files:**
- Modify: `src/copaw/agents/tools/__init__.py`

### 7.1 导出新组件

- [ ] **Step 1: 添加导出语句**

```python
from .path_validator import PathValidator
from .sandbox import SandboxExecutor
```

- [ ] **Step 2: 提交更改**

```bash
git add src/copaw/agents/tools/__init__.py
git commit -m "chore: export PathValidator and SandboxExecutor from tools module"
```

---

## Task 8: 集成测试

**Files:**
- Create: `tests/agents/tools/test_permission_isolation.py`

### 8.1 编写集成测试

- [ ] **Step 1: 创建集成测试文件**

```python
# tests/agents/tools/test_permission_isolation.py
# -*- coding: utf-8 -*-
"""Integration tests for user permission isolation."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from copaw.agents.tools.file_io import read_file, write_file
from copaw.agents.tools.file_search import grep_search
from copaw.agents.tools.shell import execute_shell_command


class TestFileOperationIsolation:
    """Tests for file operation permission isolation."""

    @pytest.mark.asyncio
    async def test_read_file_inside_user_dir(self, tmp_path):
        """读取用户目录内文件 - 应成功"""
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
        """读取用户目录外文件 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await read_file("/etc/passwd")
            assert "Permission denied" in result.content[0].get("text", "")

    @pytest.mark.asyncio
    async def test_write_file_outside_user_dir(self, tmp_path):
        """写入用户目录外 - 应拒绝"""
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
        """搜索用户目录外 - 应拒绝"""
        with patch(
            "copaw.agents.tools.path_validator.get_request_working_dir",
            return_value=tmp_path,
        ):
            result = await grep_search("pattern", path="/etc")
            assert "Permission denied" in result.content[0].get("text", "")


class TestShellCommandIsolation:
    """Tests for shell command sandbox isolation."""

    @pytest.mark.asyncio
    async def test_shell_with_sandbox(self, tmp_path):
        """Shell 命令在沙箱中执行"""
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
                    # Should fail because sandbox unavailable and fallback=deny
                    assert "bubblewrap" in result.content[0].get("text", "").lower()
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/agents/tools/test_permission_isolation.py -v`
Expected: PASS

### 8.2 提交集成测试

- [ ] **Step 3: 提交代码**

```bash
git add tests/agents/tools/test_permission_isolation.py
git commit -m "test: add integration tests for permission isolation

- Test file operations are restricted to user directory
- Test file search is restricted to user directory
- Test shell command sandbox integration"
```

---

## Task 9: 运行完整测试套件

### 9.1 运行所有测试

- [ ] **Step 1: 运行完整测试**

Run: `pytest tests/ -v --cov=src/copaw/agents/tools --cov-report=term-missing`
Expected: 所有测试通过，覆盖率达标

- [ ] **Step 2: 检查代码风格**

Run: `flake8 src/copaw/agents/tools/path_validator.py src/copaw/agents/tools/sandbox.py --max-line-length=79`
Expected: 无错误

### 9.2 最终提交

- [ ] **Step 3: 合并提交（可选）**

```bash
git log --oneline -10
# 如果需要合并多个提交为一个：
# git rebase -i HEAD~N
```

---

## Verification Checklist

完成所有任务后，验证以下内容：

- [ ] PathValidator 单元测试全部通过
- [ ] SandboxExecutor 单元测试全部通过
- [ ] file_io.py 改造后功能正常
- [ ] file_search.py 改造后功能正常
- [ ] shell.py 使用沙箱执行命令
- [ ] 集成测试通过
- [ ] 代码覆盖率达标（PathValidator 95%+, SandboxExecutor 90%+）
- [ ] 无 flake8 错误
- [ ] 所有提交信息符合规范