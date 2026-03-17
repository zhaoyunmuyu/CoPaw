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
│   ├── file_io.py           # MODIFY: 添加路径验证
│   ├── file_search.py       # MODIFY: 添加路径验证
│   └── shell.py             # MODIFY: 使用沙箱执行
├── config/
│   └── config.py            # MODIFY: 添加 SandboxConfig
tests/
└── agents/tools/
    ├── test_path_validator.py  # NEW: PathValidator 测试
    └── test_sandbox.py          # NEW: SandboxExecutor 测试
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
from unittest.mock import patch, MagicMock

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
                mock_proc.communicate = asyncio.coroutine(
                    lambda: (b"hello\n", b"")
                )
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
                # Simulate timeout
                mock_proc.communicate = asyncio.coroutine(
                    lambda: asyncio.sleep(10) or (b"", b"")
                )
                mock_proc.terminate = MagicMock()
                mock_proc.kill = MagicMock()
                mock_proc.wait = asyncio.coroutine(lambda: None)
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
                fallback_mode="deny",
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
                fallback_mode="warn",
            )

            # Mock subprocess for fallback execution
            with patch("asyncio.create_subprocess_shell") as mock_subprocess:
                mock_proc = MagicMock()
                mock_proc.communicate = asyncio.coroutine(
                    lambda: (b"output\n", b"")
                )
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
        fallback_mode: Literal["deny", "warn"] = "deny",
    ):
        """初始化沙箱执行器。

        Args:
            user_dir: 用户工作目录
            timeout: 命令超时时间（秒）
            allow_network: 是否允许网络访问
            readonly_system: 系统目录是否只读
            fallback_mode: bubblewrap 不可用时的处理策略
        """
        self.user_dir = Path(user_dir).resolve()
        self.timeout = timeout
        self.allow_network = allow_network
        self.readonly_system = readonly_system
        self.fallback_mode = fallback_mode

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
            RuntimeError: 当 bubblewrap 不可用且 fallback_mode="deny" 时
        """
        # 检查 bubblewrap 可用性
        if not self.is_available():
            if self.fallback_mode == "deny":
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

### 4.1 修改 _resolve_file_path 函数

- [ ] **Step 1: 替换 _resolve_file_path 函数**

找到现有的 `_resolve_file_path` 函数（约第 14-28 行），替换为：

```python
from .path_validator import PathValidator


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

- [ ] **Step 2: 在各函数中捕获 PermissionError**

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

### 4.2 运行测试验证

- [ ] **Step 3: 运行 file_io 相关测试**

Run: `pytest tests/agents/tools/test_file_io.py -v 2>/dev/null || pytest -k "file_io or read_file or write_file" -v`
Expected: PASS 或测试文件不存在时创建新测试

### 4.3 提交更改

- [ ] **Step 4: 提交代码**

```bash
git add src/copaw/agents/tools/file_io.py
git commit -m "feat: add path validation to file_io tools

- Replace _resolve_file_path with PathValidator integration
- Add PermissionError handling in all file operations
- Ensure users can only access files in their directory"
```

---

## Task 5: 改造 file_search.py

**Files:**
- Modify: `src/copaw/agents/tools/file_search.py`

### 5.1 修改 grep_search 和 glob_search

- [ ] **Step 1: 在 grep_search 中添加路径验证**

找到 `grep_search` 函数（约第 82 行），修改路径处理部分：

```python
from .path_validator import PathValidator


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

- [ ] **Step 2: 在 glob_search 中添加路径验证**

同样修改 `glob_search` 函数的路径处理部分。

### 5.2 运行测试验证

- [ ] **Step 3: 运行测试**

Run: `pytest tests/agents/tools/test_file_search.py -v 2>/dev/null || pytest -k "grep_search or glob_search" -v`
Expected: PASS

### 5.3 提交更改

- [ ] **Step 4: 提交代码**

```bash
git add src/copaw/agents/tools/file_search.py
git commit -m "feat: add path validation to file_search tools

- Validate search paths with PathValidator
- Ensure grep_search and glob_search are restricted to user directory"
```

---

## Task 6: 改造 shell.py

**Files:**
- Modify: `src/copaw/agents/tools/shell.py`

### 6.1 使用 SandboxExecutor 替换直接执行

- [ ] **Step 1: 导入 SandboxExecutor 和 PathValidator**

在文件顶部添加导入：

```python
from .path_validator import PathValidator
from .sandbox import SandboxExecutor
```

- [ ] **Step 2: 添加获取沙箱配置的辅助函数**

```python
def _get_sandbox_config():
    """获取沙箱配置。"""
    from ...config import load_config

    config = load_config()
    return config.sandbox
```

- [ ] **Step 3: 修改 execute_shell_command 函数**

替换 `execute_shell_command` 函数的主要逻辑：

```python
async def execute_shell_command(...):
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
        fallback_mode=sandbox_config.fallback,
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
    """直接执行命令（沙箱禁用时使用）。"""
    # 保持原有的直接执行逻辑
    # ... (复制原有的 subprocess 执行代码)
```

### 6.2 运行测试验证

- [ ] **Step 4: 运行测试**

Run: `pytest tests/agents/tools/test_shell.py -v 2>/dev/null || pytest -k "shell" -v`
Expected: PASS

### 6.3 提交更改

- [ ] **Step 5: 提交代码**

```bash
git add src/copaw/agents/tools/shell.py
git commit -m "feat: integrate SandboxExecutor into shell command execution

- Replace direct subprocess execution with sandboxed execution
- Add path validation for cwd parameter
- Support sandbox configuration (enabled, fallback, allow_network)"
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