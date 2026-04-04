# CLI Init 多租户支持设计方案

## 1. 目标

修改 `copaw init` 命令，新增 `--tenant-id` 参数，使其能够为指定租户创建隔离的目录结构和配置。同时抽象出 `TenantInitializer` 类，供 CLI 和 runtime 共享初始化逻辑。

## 2. 范围

本次改动：

- `copaw init` 命令新增 `--tenant-id` 参数（默认 `"default"`）
- 新增 `TenantInitializer` 类，封装租户初始化逻辑
- migration 函数新增 `working_dir` 可选参数
- `TenantWorkspacePool.get_or_create()` 集成 `TenantInitializer`

不在本次范围：

- `copaw app` 命令不改动
- 不迁移现有用户数据
- 不改动 middleware / context / router

## 3. 向后兼容

- 不传 `--tenant-id` 时默认为 `"default"`，等价于 `copaw init --tenant-id default`
- 产物落在 `~/.copaw/default/` 下
- 现有用户的 `~/.copaw/` 根目录数据保持不动，新旧并存
- 现有不传 `working_dir` 参数的 migration 函数调用点保持兼容（fallback 到 `WORKING_DIR`）

## 4. 目录结构

```text
WORKING_DIR/                    # ~/.copaw/
├── (现有根目录数据保持不动)
├── default/                    # copaw init（不传 --tenant-id）
│   ├── config.json
│   ├── HEARTBEAT.md
│   ├── workspaces/
│   │   └── default/
│   │       ├── agent.json
│   │       ├── chats.json
│   │       ├── jobs.json
│   │       ├── sessions/
│   │       ├── memory/
│   │       ├── active_skills/
│   │       └── customized_skills/
│   ├── media/
│   ├── secrets/
│   └── skill_pool/
├── tenant-acme/                # copaw init --tenant-id tenant-acme
│   └── (同上结构)
└── tenant-foo/
    └── (同上结构)
```

## 5. TenantInitializer

新增文件：`src/copaw/app/workspace/tenant_initializer.py`

```python
class TenantInitializer:
    """为指定 tenant 创建完整的目录结构和初始配置。

    所有操作幂等：已存在的目录和文件不会被覆盖。
    两个调用方：
    - CLI init_cmd.py：交互式初始化
    - TenantWorkspacePool.get_or_create()：runtime 懒创建
    """

    def __init__(self, base_working_dir: Path, tenant_id: str):
        self.base_working_dir = base_working_dir
        self.tenant_id = tenant_id
        self.tenant_dir = base_working_dir / tenant_id

    def ensure_directory_structure(self) -> None:
        """创建租户目录骨架。

        创建以下目录（如不存在）：
        - tenant_dir/
        - tenant_dir/workspaces/
        - tenant_dir/media/
        - tenant_dir/secrets/
        """

    def ensure_default_agent(self) -> None:
        """在 tenant_dir 下创建 default agent workspace。

        调用 ensure_default_agent_exists(working_dir=self.tenant_dir)。
        """

    def ensure_qa_agent(self) -> None:
        """在 tenant_dir 下创建 QA agent workspace。

        调用 ensure_qa_agent_exists(working_dir=self.tenant_dir)。
        """

    def ensure_skill_pool(self) -> None:
        """初始化 tenant 的 skill pool。

        调用 ensure_skill_pool_initialized(working_dir=self.tenant_dir)。
        """

    def initialize(self) -> None:
        """完整初始化流程（幂等）。

        依次调用：
        1. ensure_directory_structure()
        2. ensure_default_agent()
        3. ensure_qa_agent()
        4. ensure_skill_pool()
        """
```

幂等性要求：
- 目录已存在 → 跳过
- config.json 已存在 → 跳过
- agent workspace 已存在 → 跳过

## 6. init_cmd.py 改造

### 6.1 新增参数

```python
@click.option(
    "--tenant-id",
    default="default",
    show_default=True,
    help="Tenant ID for multi-tenant isolation.",
)
def init_cmd(force, use_defaults, accept_security, tenant_id):
```

### 6.2 路径基点变更

所有路径从 `WORKING_DIR` 改为 `tenant_dir`：

```python
tenant_dir = WORKING_DIR / tenant_id
config_path = tenant_dir / "config.json"
heartbeat_path = tenant_dir / "HEARTBEAT.md"
default_workspace = tenant_dir / "workspaces" / "default"
```

不再调用 `get_config_path()` / `get_heartbeat_query_path()` 这类全局函数。

### 6.3 初始化流程

用 `TenantInitializer` 替代直接调用 migration 函数：

```python
initializer = TenantInitializer(WORKING_DIR, tenant_id)
initializer.ensure_directory_structure()
initializer.ensure_default_agent()
initializer.ensure_qa_agent()
initializer.ensure_skill_pool()
```

### 6.4 后续交互式流程

provider、channel、skill、env、heartbeat 的交互式配置保持不变，只是路径改为 tenant-scoped：

- `configure_providers_interactive`：**保持全局**。当前通过 `ProviderManager.get_instance()` 单例写入全局 `SECRET_DIR / "providers"`（默认 `~/.copaw.secret/providers/`）。本次迭代不改动 provider 存储位置，多租户共享同一套 provider 配置
- `SkillService` / `SkillPoolService`：workspace 路径改为 `default_workspace`（基于 tenant_dir）
- `configure_env_interactive()`：**保持全局**。当前写入全局 `SECRET_DIR / "envs.json"`（默认 `~/.copaw.secret/envs.json`）。本次迭代不改动 env 存储位置，多租户共享同一套环境变量
- `configure_channels_interactive`：config 已经通过 `config_path` 参数隔离，无需额外改动

**注意**：Provider 和 env secret 存储在本次迭代中保持全局（`SECRET_DIR` 级别）。本次改动仅使 config.json、workspace、heartbeat、skill pool 实现租户隔离。未来如需租户级 provider/env 隔离，需单独设计。

### 6.5 telemetry

telemetry 保持全局（`WORKING_DIR` 级别），不按 tenant 隔离。这是匿名系统级数据。

## 7. migration 函数改造

给以下函数新增可选 `working_dir` 参数：

### ensure_default_agent_exists

```python
def ensure_default_agent_exists(working_dir: Path | None = None) -> None:
    wd = working_dir or WORKING_DIR
    # 内部所有路径基于 wd
```

### ensure_qa_agent_exists

```python
def ensure_qa_agent_exists(working_dir: Path | None = None) -> None:
    wd = working_dir or WORKING_DIR
    # 内部所有路径基于 wd
```

### migrate_legacy_skills_to_skill_pool

```python
def migrate_legacy_skills_to_skill_pool(working_dir: Path | None = None) -> None:
    wd = working_dir or WORKING_DIR
    # 内部所有路径基于 wd
```

### ensure_skill_pool_initialized

```python
def ensure_skill_pool_initialized(working_dir: Path | None = None) -> bool:
    wd = working_dir or WORKING_DIR
    # skill pool 目录基于 wd
```

现有不传参的调用点保持兼容。

## 8. TenantWorkspacePool 集成

`TenantWorkspacePool.get_or_create()` 在创建 workspace 前调用 `TenantInitializer`：

```python
async def get_or_create(self, tenant_id: str, agent_id: str = "default") -> Workspace:
    # ... 现有锁逻辑 ...

    # 确保 tenant 目录结构就绪（幂等）
    initializer = TenantInitializer(self._base_working_dir, tenant_id)
    initializer.initialize()

    # 创建 Workspace 实例
    tenant_dir = self._base_working_dir / tenant_id
    workspace = Workspace(workspace_dir=tenant_dir, ...)
    # ...
```

## 9. 改动文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/copaw/app/workspace/tenant_initializer.py` | 新增 | TenantInitializer 类 |
| `src/copaw/cli/init_cmd.py` | 修改 | 新增 --tenant-id，路径改为 tenant-scoped |
| `src/copaw/app/migration.py` | 修改 | 三个函数新增 working_dir 参数 |
| `src/copaw/app/workspace/tenant_pool.py` | 修改 | get_or_create 集成 TenantInitializer |

## 10. 验收标准

1. `copaw init` 不传 --tenant-id → 产物落在 `~/.copaw/default/`，行为与改造前等价
2. `copaw init --tenant-id acme` → 产物落在 `~/.copaw/acme/`，结构完整
3. 重复执行 `copaw init --tenant-id acme` → 幂等，不覆盖已有配置
4. 现有 `~/.copaw/` 根目录数据不受影响
5. `TenantWorkspacePool.get_or_create("new-tenant")` → 自动创建完整目录结构
6. migration 函数不传 working_dir 时行为不变
