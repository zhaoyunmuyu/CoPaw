# 用户权限隔离设计文档

**版本**: 1.0
**日期**: 2026-03-17
**状态**: 待审核

---

## 1. 概述

### 1.1 背景

CoPaw 项目提供文件操作和 Shell 命令执行功能，当前存在安全风险：
- 文件操作允许访问任意绝对路径
- Shell 命令无任何限制，可执行任意命令

### 1.2 目标

实现用户权限隔离，确保：
- 用户只能操作自己目录下的内容
- Shell 命令在沙箱环境中执行，无法访问其他用户数据

### 1.3 范围

| 项目 | 选择 |
|------|------|
| 运行环境 | 混合模式（Channel + Web Console） |
| Shell 限制 | 系统级沙箱隔离 |
| 认证机制 | 信任现有 user_id 标识 |
| 符号链接 | 暂不处理（已知风险） |
| 错误提示 | 简洁，不暴露系统路径 |

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Request                            │
│                   (user_id in context)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   PathValidator                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ validate_path(path, user_id) → bool                  │    │
│  │ - 解析相对路径                                        │    │
│  │ - 检查是否在用户目录内                                │    │
│  │ - 返回简洁错误信息                                    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   file_io.py    │  │  file_search.py │  │    shell.py     │
│                 │  │                 │  │                 │
│ read_file()     │  │ grep_search()   │  │ execute_shell() │
│ write_file()    │  │ glob_search()   │  │                 │
│ edit_file()     │  │                 │  │ ┌─────────────┐ │
│ append_file()   │  │ 调用            │  │ │ SandboxExec │ │
│                 │  │ PathValidator   │  │ │ (bubblewrap)│ │
│ 调用            │  │                 │  │ └─────────────┘ │
│ PathValidator   │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 2.2 组件说明

| 组件 | 职责 | 文件位置 |
|------|------|----------|
| PathValidator | 路径验证，确保在用户目录内 | `src/copaw/agents/tools/path_validator.py` |
| SandboxExecutor | Shell 命令沙箱执行 | `src/copaw/agents/tools/sandbox.py` |
| file_io.py | 文件读写操作（改造） | `src/copaw/agents/tools/file_io.py` |
| file_search.py | 文件搜索操作（改造） | `src/copaw/agents/tools/file_search.py` |
| shell.py | Shell 命令执行（改造） | `src/copaw/agents/tools/shell.py` |

---

## 3. PathValidator 组件

### 3.1 接口设计

```python
class PathValidator:
    """路径验证器，确保用户只能访问自己的目录。"""

    @staticmethod
    def get_user_dir() -> Path:
        """获取当前请求用户的目录。"""

    @staticmethod
    def validate_path(path: str | Path) -> tuple[bool, Path, str]:
        """
        验证路径是否在用户目录内。

        Args:
            path: 待验证的路径（绝对或相对）

        Returns:
            tuple[bool, Path, str]: (是否有效, 解析后的路径, 错误信息)
        """

    @staticmethod
    def resolve_and_validate(path: str | Path) -> Path:
        """
        解析并验证路径，失败时抛出 PermissionError。
        用于简化调用代码。
        """
```

### 3.2 验证流程

```
输入路径
    │
    ▼
┌─────────────────────────────────────┐
│ 1. 获取用户目录                       │
│    user_dir = get_request_working_dir() │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 2. 解析路径                          │
│    - 绝对路径：直接使用               │
│    - 相对路径：基于用户目录解析        │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 3. 规范化路径                        │
│    resolved = Path(path).resolve()   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 4. 检查是否在用户目录内               │
│    is_inside = resolved.is_relative_to(user_dir) │
└─────────────────────────────────────┘
    │
    ├── True ──► 返回 (True, resolved, "")
    └── False ─► 返回 (False, resolved, "Permission denied: path is outside allowed directory")
```

### 3.3 错误消息

| 场景 | 返回消息 |
|------|----------|
| 路径在用户目录外 | `Permission denied: path is outside allowed directory` |
| 路径不存在（读操作） | `File not found: {filename}` |
| 路径格式错误 | `Invalid path format` |

**安全原则**：不返回完整的系统路径，只返回文件名或相对路径部分。

---

## 4. SandboxExecutor 组件

### 4.1 接口设计

```python
class SandboxExecutor:
    """Shell 命令沙箱执行器，使用 bubblewrap 实现系统级隔离。"""

    def __init__(
        self,
        user_dir: Path,
        timeout: int = 60,
        allow_network: bool = False,
        readonly_system: bool = True,
    ):
        """
        初始化沙箱执行器。

        Args:
            user_dir: 用户工作目录
            timeout: 命令超时时间（秒）
            allow_network: 是否允许网络访问
            readonly_system: 系统目录是否只读
        """

    async def execute(self, command: str) -> tuple[int, str, str]:
        """
        在沙箱中执行命令。

        Returns:
            tuple[int, str, str]: (返回码, 标准输出, 标准错误)
        """

    @staticmethod
    def is_available() -> bool:
        """检查 bubblewrap 是否可用。"""
```

### 4.2 bubblewrap 执行参数

```bash
bwrap \
  --unshare-all \                    # 隔离所有命名空间
  --die-with-parent \                # 父进程退出时终止沙箱
  --new-session \                    # 新建 session
  --clearenv \                       # 清空环境变量
  --setenv PATH /usr/bin:/bin \      # 设置 PATH
  --ro-bind /usr /usr \              # 只读挂载 /usr
  --ro-bind /bin /bin \              # 只读挂载 /bin
  --ro-bind /lib /lib \              # 只读挂载 /lib
  --ro-bind /lib64 /lib64 \          # 只读挂载 /lib64 (x86_64)
  --proc /proc \                     # 挂载 /proc
  --dev /dev \                       # 挂载 /dev
  --tmpfs /tmp \                     # 临时文件系统
  --bind {user_dir} /workspace \     # 读写挂载用户目录到 /workspace
  --chdir /workspace \               # 切换工作目录
  -- {shell} -c "{command}"          # 执行命令
```

### 4.3 隔离效果

| 隔离项 | 效果 |
|--------|------|
| 文件系统 | 只能访问 `/workspace`（用户目录）和只读系统目录 |
| 网络 | 默认禁止，可通过 `allow_network=True` 开启 |
| 用户命名空间 | 隔离，无法看到其他用户信息 |
| 进程命名空间 | 隔离，无法看到其他进程 |
| IPC 命名空间 | 隔离，无法访问共享内存等 |

### 4.4 降级策略

```
执行命令时检查 bubblewrap 是否可用
    │
    ├── 可用 ──► 使用沙箱执行
    │
    └── 不可用 ──► 检查配置
                    │
                    ├── 配置 fallback=deny ──► 抛出错误，拒绝执行
                    │
                    └── 配置 fallback=warn ──► 记录警告日志
                                                │
                                                └── 使用基础路径过滤执行
```

### 4.5 路径映射

| 用户视角 | 实际路径 |
|----------|----------|
| `/workspace` | `~/.copaw/{user_id}` |
| `/workspace/file.txt` | `~/.copaw/{user_id}/file.txt` |
| `/tmp` | 沙箱内的临时文件系统 |

---

## 5. 工具改造

### 5.1 file_io.py

**改动**：替换 `_resolve_file_path` 函数

```python
# 改造前
def _resolve_file_path(file_path: str) -> str:
    path = Path(file_path)
    if path.is_absolute():
        return str(path)
    else:
        return str(get_request_working_dir() / file_path)

# 改造后
from .path_validator import PathValidator

def _resolve_file_path(file_path: str) -> str:
    """解析并验证路径，失败时抛出 PermissionError。"""
    return str(PathValidator.resolve_and_validate(file_path))
```

**影响函数**：`read_file`, `write_file`, `edit_file`, `append_file`

### 5.2 file_search.py

**改动**：添加路径验证，限制搜索范围

```python
from .path_validator import PathValidator

async def grep_search(pattern: str, path: Optional[str] = None, ...):
    user_dir = PathValidator.get_user_dir()

    if path:
        is_valid, resolved, error = PathValidator.validate_path(path)
        if not is_valid:
            return ToolResponse(content=[TextBlock(type="text", text=error)])
        search_root = resolved
    else:
        search_root = user_dir
    # ... 后续逻辑
```

**影响函数**：`grep_search`, `glob_search`

### 5.3 shell.py

**改动**：引入 SandboxExecutor

```python
from .path_validator import PathValidator
from .sandbox import SandboxExecutor

async def execute_shell_command(command: str, timeout: int = 60, cwd: Optional[Path] = None):
    user_dir = PathValidator.get_user_dir()

    if cwd is not None:
        is_valid, resolved, error = PathValidator.validate_path(cwd)
        if not is_valid:
            return ToolResponse(content=[TextBlock(type="text", text=error)])
        working_dir = resolved
    else:
        working_dir = user_dir

    sandbox = SandboxExecutor(
        user_dir=working_dir,
        timeout=timeout,
        allow_network=_get_sandbox_config().allow_network,
    )

    returncode, stdout, stderr = await sandbox.execute(command)
    # ... 格式化响应
```

### 5.4 配置新增

```python
# src/copaw/config/config.py

class SandboxConfig(BaseModel):
    """沙箱配置"""
    enabled: bool = True
    backend: Literal["bubblewrap"] = "bubblewrap"
    fallback: Literal["deny", "warn"] = "deny"
    allow_network: bool = False
    timeout: int = 60
```

**config.json 示例**：
```json
{
  "sandbox": {
    "enabled": true,
    "backend": "bubblewrap",
    "fallback": "deny",
    "allow_network": false,
    "timeout": 60
  }
}
```

---

## 6. 测试策略

### 6.1 单元测试

**测试文件**：`tests/agents/tools/`

#### PathValidator 测试

```python
class TestPathValidator:
    def test_relative_path_inside_user_dir(self):
        """相对路径在用户目录内 - 应通过"""

    def test_absolute_path_inside_user_dir(self):
        """绝对路径在用户目录内 - 应通过"""

    def test_relative_path_outside_user_dir(self):
        """相对路径跳出用户目录 - 应拒绝"""

    def test_absolute_path_outside_user_dir(self):
        """绝对路径指向外部 - 应拒绝"""

    def test_path_with_traversal_attempts(self):
        """路径遍历攻击尝试 - 应拒绝"""

    def test_path_not_exists(self):
        """路径不存在 - 返回文件不存在错误"""

    def test_empty_path(self):
        """空路径 - 返回无效路径错误"""
```

#### SandboxExecutor 测试

```python
class TestSandboxExecutor:
    def test_bubblewrap_available(self):
        """检查 bubblewrap 可用性"""

    async def test_execute_simple_command(self):
        """执行简单命令 - 应成功"""

    async def test_access_outside_user_dir(self):
        """尝试访问用户目录外 - 应失败"""

    async def test_write_to_user_dir(self):
        """写入用户目录 - 应成功"""

    async def test_network_access_denied(self):
        """网络访问 - 应失败（默认禁止）"""

    async def test_command_timeout(self):
        """命令超时 - 应终止并返回错误"""

    async def test_fallback_when_bubblewrap_unavailable(self):
        """bubblewrap 不可用时的降级处理"""
```

### 6.2 覆盖率目标

| 组件 | 目标覆盖率 |
|------|------------|
| PathValidator | 95% |
| SandboxExecutor | 90% |
| file_io.py (改动部分) | 90% |
| file_search.py (改动部分) | 90% |
| shell.py (改动部分) | 90% |

### 6.3 安全测试清单

```
□ 路径遍历攻击测试
  - ../ 跳出用户目录
  - 绝对路径访问外部
  - 符号链接绕过（已知风险，暂不处理）

□ Shell 命令隔离测试
  - 访问 /etc/passwd
  - 访问其他用户目录
  - 网络访问
  - 进程列表获取
  - 环境变量读取

□ 边界条件测试
  - 空路径
  - 特殊字符路径
  - 超长路径
  - Unicode 路径
```

---

## 7. 部署指南

### 7.1 系统要求

```bash
# Ubuntu/Debian
sudo apt-get install bubblewrap

# CentOS/RHEL
sudo yum install bubblewrap

# Arch Linux
sudo pacman -S bubblewrap
```

### 7.2 内核要求

- Linux 内核 3.8+
- 支持命名空间：user, pid, network, mount

**检查内核支持**：
```bash
cat /proc/sys/kernel/unprivileged_userns_clone
# 应返回 1

# 如果返回 0，需要启用
echo 1 | sudo tee /proc/sys/kernel/unprivileged_userns_clone
```

### 7.3 升级步骤

```
1. 安装 bubblewrap
   └─► sudo apt-get install bubblewrap

2. 验证 bubblewrap 可用
   └─► bwrap --version

3. 更新代码
   └─► git pull / pip install

4. 更新配置文件
   └─► 添加 sandbox 配置项到 config.json

5. 重启服务
   └─► copaw app --reload

6. 验证功能
   └─► 测试文件操作和 Shell 执行
```

### 7.4 已知限制

| 限制 | 说明 | 缓解措施 |
|------|------|----------|
| 符号链接 | 暂不处理，可能被利用访问外部 | 后续迭代添加检测 |
| 容器内运行 | 需要特权或 sys_admin capability | 使用 `--privileged` 或配置 capability |
| macOS 不支持 | bubblewrap 仅支持 Linux | macOS 环境降级为基础过滤 |

---

## 8. 改动汇总

| 文件 | 改动类型 | 预估改动量 |
|------|----------|------------|
| `path_validator.py` | 新增 | ~80 行 |
| `sandbox.py` | 新增 | ~150 行 |
| `file_io.py` | 修改 | ~10 行 |
| `file_search.py` | 修改 | ~20 行 |
| `shell.py` | 修改 | ~40 行 |
| `config/config.py` | 修改 | ~15 行 |
| `__init__.py` | 修改 | ~2 行 |
| 测试文件 | 新增 | ~300 行 |

---

## 9. 风险与后续迭代

### 9.1 当前风险

1. **符号链接**：用户可通过符号链接访问外部文件
2. **硬链接**：同样存在风险
3. **容器环境**：bubblewrap 在容器内运行需要特权

### 9.2 后续迭代

1. 添加符号链接检测和警告
2. 支持更多沙箱后端（Docker, gVisor）
3. 添加审计日志和访问记录
4. macOS 平台支持（使用其他隔离方案）