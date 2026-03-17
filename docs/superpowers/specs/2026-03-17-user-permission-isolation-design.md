# 用户权限隔离设计文档

**版本**: 1.1
**日期**: 2026-03-17
**状态**: 待审核

> **Python 版本要求**: 需要 Python 3.9+（使用 `Path.is_relative_to()`）

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
| 符号链接 | 通过 Path.resolve() 解析后验证（见 1.4 节） |
| 错误提示 | 简洁，不暴露系统路径 |

### 1.4 user_id 安全模型

**user_id 来源**：
- **Channel 消息**：来自各平台的 sender_id（如钉钉 userid、飞书 open_id）
- **Web Console**：来自 HTTP 请求头或 Session（需上层认证）

**安全假设**：
1. user_id 由可信的 Channel 或认证层提供，本模块不做额外验证
2. 若上层认证被绕过，攻击者可伪造 user_id 访问其他用户目录
3. 建议：生产环境应在 Channel 层或 API Gateway 层验证身份

**已知风险**：
- 如果 attacker 能控制 `request.user_id`，可访问任意用户目录
- 后续迭代应添加 JWT 验证或 API Token 认证

### 1.5 符号链接处理策略

使用 `Path.resolve()` 解析路径后验证，有以下行为：

| 场景 | 行为 | 是否允许 |
|------|------|----------|
| 普通文件/目录 | 直接验证 | ✅ |
| 用户目录内符号链接 → 用户目录内目标 | 解析后目标在用户目录内 | ✅ |
| 用户目录内符号链接 → 用户目录外目标 | 解析后目标在用户目录外 | ❌ 拒绝 |
| 用户目录外符号链接 | 不可能访问（已在验证前拒绝） | ❌ |

**结论**：`Path.resolve()` 提供**基础的符号链接保护**。若链接目标在用户目录外，会被拒绝。

**例外情况**（已知风险）：
- TOCTOU 竞争：验证和操作之间链接被替换
- 硬链接：无法通过 resolve() 检测

后续迭代可添加：
- 链接类型检测（`os.path.islink()`）
- 操作时锁定路径

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
  --setenv PATH /usr/bin:/bin:/sbin:/usr/sbin \  # 设置 PATH
  --setenv HOME /workspace \         # 设置 HOME
  --setenv USER sandbox \            # 设置 USER
  --setenv SHELL /bin/sh \           # 设置 SHELL
  --ro-bind /usr /usr \              # 只读挂载 /usr
  --ro-bind /bin /bin \              # 只读挂载 /bin
  --ro-bind /sbin /sbin \            # 只读挂载 /sbin（可选）
  --ro-bind /lib /lib \              # 只读挂载 /lib
  --ro-bind-try /lib64 /lib64 \      # 只读挂载 /lib64（x86_64，不存在则跳过）
  --ro-bind /etc /etc \              # 只读挂载 /etc（DNS、用户组查询等）
  --proc /proc \                     # 挂载 /proc
  --dev /dev \                       # 挂载 /dev
  --tmpfs /tmp \                     # 临时文件系统
  --bind {user_dir} /workspace \     # 读写挂载用户目录到 /workspace
  --chdir /workspace \               # 切换工作目录
  -- {shell} -c "{command}"          # 执行命令
```

**参数说明**：

| 参数 | 说明 | 备注 |
|------|------|------|
| `--ro-bind-try /lib64` | 条件挂载，目录不存在时跳过 | 兼容非 x86_64 架构 |
| `--ro-bind /etc` | 挂载配置目录 | 程序需要 DNS 解析、locale 等 |
| `--ro-bind /sbin` | 挂载系统管理命令 | `ip`, `ifconfig` 等需要 |
| `--setenv HOME/USER/SHELL` | 设置基本环境变量 | 部分程序依赖这些变量 |

### 4.3 资源限制

为防止资源耗尽攻击，添加以下限制：

```python
# SandboxExecutor 配置
class SandboxLimits:
    """沙箱资源限制"""
    max_memory_mb: int = 512        # 最大内存（MB）
    max_cpu_percent: int = 50       # 最大 CPU 使用率
    max_pids: int = 100             # 最大进程数
    max_file_size_mb: int = 100     # 单文件最大大小（MB）
    max_open_files: int = 1000      # 最大打开文件数
```

**bubblewrap 资源限制参数**（需要 systemd 或 cgroups）：
```bash
# 使用 --limits 参数（需要 bubblewrap 支持）
bwrap --limits memory=512M --limits pids=100 ...
```

**替代方案**：使用 Python 的 `resource` 模块在进程内限制：
```python
import resource
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_NPROC, (100, 100))
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

**改动**：替换 `_resolve_file_path` 函数，添加异常处理

```python
from .path_validator import PathValidator

def _resolve_file_path(file_path: str) -> str:
    """解析并验证路径，失败时抛出 PermissionError。"""
    try:
        return str(PathValidator.resolve_and_validate(file_path))
    except PermissionError as e:
        # 转换为 ToolResponse 格式的错误消息
        raise PermissionError(_sanitize_error_message(str(e))) from e


def _sanitize_error_message(msg: str) -> str:
    """清理错误消息，移除敏感路径信息。"""
    # 不返回完整系统路径，只保留文件名
    if "outside allowed directory" in msg:
        return "Permission denied: path is outside allowed directory"
    return msg


# 各函数需要捕获 PermissionError 并返回 ToolResponse
async def read_file(file_path: str, ...):
    try:
        resolved_path = _resolve_file_path(file_path)
    except PermissionError as e:
        return ToolResponse(content=[TextBlock(type="text", text=str(e))])
    # ... 后续逻辑使用 resolved_path
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

class SandboxLimitsConfig(BaseModel):
    """沙箱资源限制配置"""
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    max_pids: int = 100
    max_file_size_mb: int = 100
    max_open_files: int = 1000


class SandboxConfig(BaseModel):
    """沙箱配置"""
    enabled: bool = True
    backend: Literal["bubblewrap"] = "bubblewrap"
    fallback: Literal["deny", "warn"] = "deny"
    allow_network: bool = False
    timeout: int = 60
    limits: SandboxLimitsConfig = SandboxLimitsConfig()
```

**config.json 示例**：
```json
{
  "sandbox": {
    "enabled": true,
    "backend": "bubblewrap",
    "fallback": "deny",
    "allow_network": false,
    "timeout": 60,
    "limits": {
      "max_memory_mb": 512,
      "max_pids": 100
    }
  }
}
```

### 5.5 审计日志

所有安全相关事件应记录审计日志：

```python
import logging

audit_logger = logging.getLogger("copaw.audit")

# 日志事件类型
class AuditEvent:
    PATH_VALIDATION_FAILED = "path_validation_failed"
    SANDBOX_EXECUTE = "sandbox_execute"
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"
    PERMISSION_DENIED = "permission_denied"


def log_audit(event: str, user_id: str, details: dict):
    """记录审计日志。"""
    audit_logger.info(
        "audit_event",
        extra={
            "event": event,
            "user_id": user_id,
            "details": details,
        }
    )


# 使用示例
log_audit(
    event=AuditEvent.PATH_VALIDATION_FAILED,
    user_id=user_id,
    details={"path_hint": "outside_user_dir"}  # 不记录完整路径
)

log_audit(
    event=AuditEvent.SANDBOX_EXECUTE,
    user_id=user_id,
    details={"command_hash": hashlib.sha256(cmd).hexdigest()[:16]}
)
```

**日志格式**：
```
2026-03-17 10:30:15 [INFO] copaw.audit: path_validation_failed user=alice details={"path_hint": "outside_user_dir"}
2026-03-17 10:30:20 [INFO] copaw.audit: sandbox_execute user=alice details={"command_hash": "a1b2c3d4", "returncode": 0}
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
  - 符号链接绕过（解析后应被拒绝）
  - 硬链接绕过（已知风险）

□ Shell 命令隔离测试
  - 访问 /etc/passwd
  - 访问其他用户目录
  - 网络访问
  - 进程列表获取
  - 环境变量读取

□ 边界条件测试
  - 空路径
  - 特殊字符路径
  - 超长路径（> 4096 字符）
  - Unicode 路径
  - 路径包含空字节
  - 路径包含换行符
  - Windows 风格路径（在 Linux 环境）

□ 资源限制测试
  - 内存耗尽攻击
  - fork 炸弹
  - 无限文件创建
  - CPU 占满

□ 降级模式测试
  - bubblewrap 不存在
  - bubblewrap 权限不足
  - 容器内运行（缺少 sys_admin）
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

6. 验证沙箱隔离
   └─► 执行测试命令验证隔离效果

7. 检查审计日志
   └─► 确认安全事件正常记录
```

### 7.4 部署验证

安装后执行以下验证步骤：

```bash
# 1. 验证 bubblewrap 基本功能
bwrap --version
# 输出: bubblewrap x.x.x

# 2. 验证沙箱隔离效果
# 创建测试目录
mkdir -p /tmp/sandbox-test
echo "secret" > /tmp/sandbox-test/secret.txt

# 在沙箱中尝试访问外部文件（应失败）
bwrap --unshare-all \
  --ro-bind /usr /usr \
  --ro-bind /bin /bin \
  --bind /tmp/sandbox-test /workspace \
  --chdir /workspace \
  -- cat /etc/passwd
# 预期: Permission denied 或无输出

# 3. 验证用户目录可访问
bwrap --unshare-all \
  --ro-bind /usr /usr \
  --ro-bind /bin /bin \
  --bind /tmp/sandbox-test /workspace \
  --chdir /workspace \
  -- cat secret.txt
# 预期: 输出 "secret"

# 清理
rm -rf /tmp/sandbox-test
```

### 7.5 容器环境部署

在 Docker 容器中运行 bubblewrap 需要额外配置：

**检测容器环境**：
```python
def is_running_in_container() -> bool:
    """检测是否在容器内运行。"""
    # 检查 /.dockerenv
    if Path("/.dockerenv").exists():
        return True
    # 检查 cgroup
    try:
        cgroup = Path("/proc/1/cgroup").read_text()
        return "docker" in cgroup or "kubepods" in cgroup
    except Exception:
        return False
```

**Docker 配置**：
```yaml
# docker-compose.yml
services:
  copaw:
    image: copaw:latest
    # 需要以下权限之一：
    # 方式 1: 特权模式（不推荐）
    # privileged: true

    # 方式 2: 添加 capabilities（推荐）
    cap_add:
      - SYS_ADMIN
      - NET_ADMIN
    security_opt:
      - seccomp:unconfined
    # 挂载用户目录
    volumes:
      - ./data:/root/.copaw
```

**Kubernetes 配置**：
```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: copaw
    securityContext:
      capabilities:
        add: ["SYS_ADMIN", "NET_ADMIN"]
```

### 7.6 已知限制

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

1. **硬链接**：用户可通过硬链接访问外部文件（无法通过 resolve() 检测）
2. **TOCTOU 竞争**：验证和操作之间路径可能被修改
3. **容器环境**：bubblewrap 在容器内运行需要特权
4. **user_id 伪造**：若上层认证被绕过，攻击者可访问任意用户目录

### 9.2 后续迭代

1. 添加硬链接检测（`os.stat().st_nlink`）
2. 支持更多沙箱后端（Docker, gVisor）
3. 添加 JWT/API Token 认证层
4. macOS 平台支持（使用 Seatbelt 或其他隔离方案）
5. TOCTOU 防护（文件描述符锁定）