# 租户初始化 Source 隔离改造设计文档

## 1. 目标与范围

### 1.1 背景

当前所有新用户统一从 `default` 目录模板初始化，无法按来源（source）区分配置。前端已通过 `X-Source-Id` header 传递来源标识，但后端初始化流程未使用该信息。

### 1.2 目标

- 按 source 将 `default` 模板拆分为多份（如 `default_ruice`、`default_CMSJY`）
- 新用户从哪个 source 访问，就从对应的 `default_{source}` 初始化
- 维护映射表记录每个用户的 source 和初始化来源
- 支持固定 source 列表和动态新增 source

### 1.3 约束

- 用户 ID 即 tenant_id，一一对应
- 初始化时拷贝一份独立副本（非共享引用）
- 复用现有 `X-Source-Id` header 传递 source
- 映射表存储在 MySQL，历史用户数据由用户手动补充
- 同时拆分 `~/.swe/default` 和 `~/.swe.secret/default` 两套目录

---

## 2. 目录结构改造

### 2.1 改造前

```
~/.swe/
├── default/                        # 唯一默认模板
│   ├── config.json
│   └── workspaces/default/

~/.swe.secret/
├── default/
│   └── providers/
```

### 2.2 改造后

```
~/.swe/
├── default_ruice/                  # ruice source 模板
│   ├── config.json
│   └── workspaces/default/
├── default_CMSJY/                  # CMSJY source 模板
├── default_UPPCLAW/                # UPPCLAW source 模板
├── default/                        # 兜底模板（无 source 或未知 source）
└── {tenant_id}/                    # 用户实际目录（独立副本）

~/.swe.secret/
├── default_ruice/providers/        # ruice source 的 providers
├── default_CMSJY/providers/
├── default_UPPCLAW/providers/
├── default/providers/              # 兜底默认
└── {tenant_id}/providers/          # 用户实际 providers
```

### 2.3 命名规范

模板目录命名：`default_{source_id}`，其中 `source_id` 即前端 `X-Source-Id` 的值。

- source_id 为空或 "default" → 使用 `default/` 目录
- source_id 为 "ruice" → 使用 `default_ruice/` 目录
- source_id 对应的 `default_{source_id}` 不存在 → 回退到 `default/`

---

## 3. 数据库映射表设计

### 3.1 表结构

```sql
CREATE TABLE swe_tenant_init_source (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id VARCHAR(128) NOT NULL COMMENT '租户ID（即用户ID）',
    source_id VARCHAR(64) NOT NULL COMMENT '用户访问来源（X-Source-Id）',
    init_source VARCHAR(64) NOT NULL COMMENT '实际使用的模板目录名（如 default_ruice）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_tenant_id (tenant_id),
    INDEX idx_source_id (source_id),
    INDEX idx_init_source (init_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租户初始化来源映射表';
```

### 3.2 字段说明

| 字段 | 说明 |
|------|------|
| `tenant_id` | 用户唯一标识，与 `X-Tenant-Id` 一致，唯一键 |
| `source_id` | 用户首次访问时携带的 source 标识 |
| `init_source` | 实际用于初始化的模板目录名（如 `default_ruice`、`default`） |
| `created_at` | 记录创建时间 |
| `updated_at` | 记录更新时间 |

### 3.3 查询场景

| 场景 | 查询 |
|------|------|
| 新用户首次访问 | 先查映射表无记录 → 用 source_id 确定 init_source → 初始化并插入映射 |
| 已有用户访问 | 查映射表有记录 → 跳过初始化 |
| 管理端查询某用户来源 | `SELECT * FROM swe_tenant_init_source WHERE tenant_id = %s` |
| 统计各 source 用户数 | `SELECT source_id, COUNT(*) FROM swe_tenant_init_source GROUP BY source_id` |

---

## 4. 代码改造方案

### 4.1 改造总览

```
改造链路：

HTTP Request (X-Source-Id header)
  → TenantIdentityMiddleware (提取 source_id, 存入 request.state)
  → TenantWorkspaceMiddleware / Channel Router (传递 source_id)
  → TenantWorkspacePool.ensure_bootstrap(tenant_id, source_id=...)
  → TenantInitializer(base_working_dir, tenant_id, source_id=...)
      → _resolve_template_name() 确定使用哪个 default_xxx
      → seed_tenant_config_from_default()  从模板拷贝 config
      → seed_providers_from_default()      从模板拷贝 providers
      → seed_skill_pool_from_default()     从模板拷贝技能池
      → seed_default_workspace_skills_from_default() 从模板拷贝工作区技能
  → TenantInitSourceStore.get_or_create()  写入映射表
```

### 4.2 Step 1：TenantIdentityMiddleware 提取 source_id

**文件**: `src/swe/app/middleware/tenant_identity.py`

**改动**:

1. 在 `_resolve_request_identity()` 中新增 `source_id` 提取
2. 将 `source_id` 存入 `request.state`
3. 设置 context variable 供下游使用

```python
# _resolve_request_identity 方法新增：
source_id = request.headers.get("X-Source-Id")

# dispatch 方法新增：
if source_id:
    request.state.source_id = source_id
```

### 4.3 Step 2：配置 context variable 支持 source_id

**文件**: `src/swe/config/context.py`

**改动**:

1. 新增 `current_source_id` ContextVar
2. 新增 `set_current_source_id()` / `get_current_source_id()` / `reset_current_source_id()`

```python
current_source_id: ContextVar[str | None] = ContextVar(
    "current_source_id", default=None
)

def set_current_source_id(source_id: str | None) -> Token:
    return current_source_id.set(source_id)

def get_current_source_id() -> str | None:
    return current_source_id.get()

def reset_current_source_id(token: Token) -> None:
    current_source_id.reset(token)
```

3. 在 `TenantIdentityMiddleware.dispatch()` 中绑定 source_id context

### 4.4 Step 3：TenantInitializer 支持多 source 模板

**文件**: `src/swe/app/workspace/tenant_initializer.py`

**改动**:

1. `__init__` 新增 `source_id` 参数
2. 新增 `_resolve_template_name()` 方法确定模板目录
3. 改造所有 `seed_*` 方法，将硬编码的 `"default"` 替换为 `self.template_name`

核心逻辑：

```python
class TenantInitializer:
    def __init__(
        self,
        base_working_dir: Path,
        tenant_id: str,
        source_id: str | None = None,
    ):
        self.base_working_dir = Path(base_working_dir).expanduser().resolve()
        self.tenant_id = tenant_id
        self.tenant_dir = self.base_working_dir / tenant_id
        self.source_id = source_id
        self.template_name = self._resolve_template_name()

    def _resolve_template_name(self) -> str:
        """确定使用哪个 default_xxx 模板目录。"""
        if not self.source_id:
            return "default"
        template_name = f"default_{self.source_id}"
        template_dir = self.base_working_dir / template_name
        if template_dir.exists():
            return template_name
        logger.info(
            f"Template dir {template_name} not found, "
            f"falling back to default for tenant {self.tenant_id}"
        )
        return "default"
```

**需要改造的方法**（将 `"default"` 替换为 `self.template_name`）：

| 方法 | 原代码 | 改造后 |
|------|--------|--------|
| `seed_tenant_config_from_default` | `self.base_working_dir / "default" / "config.json"` | `self.base_working_dir / self.template_name / "config.json"` |
| `seed_providers_from_default` | `SECRET_DIR / "default" / "providers"` | `SECRET_DIR / self.template_name / "providers"` |
| `seed_skill_pool_from_default` | `self.base_working_dir / "default"` (default_working_dir) | `self.base_working_dir / self.template_name` |
| `seed_default_workspace_skills_from_default` | `self.base_working_dir / "default" / "workspaces" / "default"` | `self.base_working_dir / self.template_name / "workspaces" / "default"` |
| `ensure_default_workspace_scaffold` | `self.base_working_dir / "default" / "workspaces" / "default"` | `self.base_working_dir / self.template_name / "workspaces" / "default"` |

**路径替换逻辑调整**:

`seed_tenant_config_from_default` 中路径替换前缀也需要动态化：

```python
# 原：固定 default
default_workspace_prefix = str(self.base_working_dir / "default" / "workspaces")
# 改：使用 template_name
template_workspace_prefix = str(
    self.base_working_dir / self.template_name / "workspaces"
)
```

### 4.5 Step 4：TenantWorkspacePool 传递 source_id

**文件**: `src/swe/app/workspace/tenant_pool.py`

**改动**:

1. `ensure_bootstrap()` 方法新增 `source_id` 参数
2. 将 `source_id` 传递给 `TenantInitializer` 构造函数

```python
async def ensure_bootstrap(
    self,
    tenant_id: str,
    source_id: str | None = None,  # 新增
) -> None:
    # ...
    initializer = TenantInitializer(
        self._base_working_dir,
        tenant_id,
        source_id=source_id,  # 新增
    )
```

### 4.6 Step 5：新增映射表管理模块

**文件**: `src/swe/app/workspace/tenant_init_source_store.py`（新建）

遵循现有 `InstanceStore` 的模式：依赖注入 `db`，无数据库时 graceful degradation。

```python
class TenantInitSourceStore:
    """租户初始化来源映射存储层。"""

    def __init__(self, db=None):
        self.db = db
        self._use_db = db is not None and db.is_connected

    async def initialize(self) -> None:
        if self.db is not None and db.is_connected:
            self._use_db = True
        else:
            self._use_db = False

    async def get_init_source(self, tenant_id: str) -> str | None:
        """查询租户的初始化来源。"""
        if not self._use_db:
            return None
        query = (
            "SELECT init_source FROM swe_tenant_init_source "
            "WHERE tenant_id = %s"
        )
        row = await self.db.fetch_one(query, (tenant_id,))
        return row["init_source"] if row else None

    async def get_or_create(
        self,
        tenant_id: str,
        source_id: str,
        init_source: str,
    ) -> str:
        """获取或创建映射记录，返回 init_source。"""
        existing = await self.get_init_source(tenant_id)
        if existing:
            return existing
        if self._use_db:
            query = (
                "INSERT INTO swe_tenant_init_source "
                "(tenant_id, source_id, init_source) "
                "VALUES (%s, %s, %s)"
            )
            await self.db.execute(query, (tenant_id, source_id, init_source))
        return init_source

    async def get_by_source(self, source_id: str) -> list[dict]:
        """查询某 source 下的所有租户。"""
        if not self._use_db:
            return []
        query = (
            "SELECT tenant_id, source_id, init_source, created_at "
            "FROM swe_tenant_init_source WHERE source_id = %s"
        )
        rows = await self.db.fetch_all(query, (source_id,))
        return list(rows)
```

### 4.7 Step 6：串联调用链 - Workspace Middleware 传递 source_id

**文件**: `src/swe/app/middleware/` (或 `tenant_pool.py` 的调用方)

需要在调用 `ensure_bootstrap` 时传入 `source_id`。查找所有调用 `ensure_bootstrap` 的位置：

```python
# 调用方（如 TenantWorkspaceMiddleware 或 multi_agent_manager）：
source_id = getattr(request.state, "source_id", None)
await tenant_pool.ensure_bootstrap(tenant_id, source_id=source_id)
```

### 4.8 Step 7：ProviderManager 适配

**文件**: `src/swe/providers/provider_manager.py`

`ProviderManager._do_initialize_provider_storage` 当前从固定的 `default` 拷贝。需支持从 `default_{source_id}` 拷贝：

```python
@staticmethod
def _do_initialize_provider_storage(
    tenant_id: str,
    tenant_providers_dir: Path,
    source_id: str | None = None,  # 新增
) -> None:
    # 优先从 default_{source_id} 拷贝
    template_name = "default"
    if source_id:
        candidate = SECRET_DIR / f"default_{source_id}" / "providers"
        if candidate.exists() and any(candidate.iterdir()):
            template_name = f"default_{source_id}"

    source_dir = SECRET_DIR / template_name / "providers"
    if source_dir.exists() and any(source_dir.iterdir()):
        shutil.copytree(source_dir, tenant_providers_dir)
```

---

## 5. 初始化流程（改造后）

```
1. 用户访问 → 前端携带 X-Source-Id: ruice
2. TenantIdentityMiddleware 提取 source_id="ruice"，存入 request.state
3. 调用 ensure_bootstrap(tenant_id, source_id="ruice")
4. 查询映射表 → 无记录（新用户）
5. TenantInitializer._resolve_template_name():
   - 检查 ~/.swe/default_ruice/ 是否存在 → 存在 → template_name="default_ruice"
6. 从 ~/.swe/default_ruice/ 拷贝 config/skills → ~/.swe/{tenant_id}/
7. 从 ~/.swe.secret/default_ruice/providers/ 拷贝 → ~/.swe.secret/{tenant_id}/providers/
8. 写入映射表: (tenant_id, "ruice", "default_ruice")
9. 后续该用户再次访问 → 映射表已有记录 → 跳过初始化
```

---

## 6. 历史数据迁移

### 6.1 映射表数据补充

用户手动补充历史用户映射记录：

```sql
-- 示例：为已存在的租户补充映射记录
-- 假设历史用户全部使用 default 初始化
INSERT INTO swe_tenant_init_source (tenant_id, source_id, init_source)
SELECT tenant_id, 'default', 'default'
FROM swe_instance_user
WHERE status = 'active';

-- 或按实际来源补充
INSERT INTO swe_tenant_init_source (tenant_id, source_id, init_source)
VALUES
    ('user_001', 'ruice', 'default_ruice'),
    ('user_002', 'CMSJY', 'default_CMSJY');
```

### 6.2 模板目录准备

部署时需要手动创建 `default_{source}` 目录：

```bash
# 从现有 default 复制出各 source 的模板
cp -r ~/.swe/default ~/.swe/default_ruice
cp -r ~/.swe/default ~/.swe/default_CMSJY
cp -r ~/.swe/default ~/.swe/default_UPPCLAW

cp -r ~/.swe.secret/default ~/.swe.secret/default_ruice
cp -r ~/.swe.secret/default ~/.swe.secret/default_CMSJY
cp -r ~/.swe.secret/default ~/.swe.secret/default_UPPCLAW

# 然后根据各 source 的实际需求修改各模板目录中的配置
```

---

## 7. 实施步骤

### Phase 1：基础设施（映射表 + Context）

| # | 任务 | 文件 |
|---|------|------|
| 1.1 | 创建数据库迁移脚本 | `scripts/sql/tenant_init_source_table.sql` |
| 1.2 | 新增 source_id context variable | `src/swe/config/context.py` |
| 1.3 | 新增映射表 Store | `src/swe/app/workspace/tenant_init_source_store.py` |

### Phase 2：中间件改造（提取 source_id）

| # | 任务 | 文件 |
|---|------|------|
| 2.1 | TenantIdentityMiddleware 提取 X-Source-Id | `src/swe/app/middleware/tenant_identity.py` |

### Phase 3：核心初始化逻辑改造

| # | 任务 | 文件 |
|---|------|------|
| 3.1 | TenantInitializer 支持 source_id + _resolve_template_name | `src/swe/app/workspace/tenant_initializer.py` |
| 3.2 | 改造 seed_tenant_config_from_default 使用动态模板 | `src/swe/app/workspace/tenant_initializer.py` |
| 3.3 | 改造 seed_providers_from_default 使用动态模板 | `src/swe/app/workspace/tenant_initializer.py` |
| 3.4 | 改造 seed_skill_pool_from_default 使用动态模板 | `src/swe/app/workspace/tenant_initializer.py` |
| 3.5 | 改造 seed_default_workspace_skills_from_default 使用动态模板 | `src/swe/app/workspace/tenant_initializer.py` |
| 3.6 | 改造 ensure_default_workspace_scaffold 使用动态模板 | `src/swe/app/workspace/tenant_initializer.py` |

### Phase 4：调用链串联

| # | 任务 | 文件 |
|---|------|------|
| 4.1 | TenantWorkspacePool.ensure_bootstrap 传递 source_id | `src/swe/app/workspace/tenant_pool.py` |
| 4.2 | 查找并改造所有 ensure_bootstrap 调用方传递 source_id | 多文件 |
| 4.3 | ProviderManager._do_initialize_provider_storage 适配 source_id | `src/swe/providers/provider_manager.py` |
| 4.4 | 初始化完成后写入映射表 | `src/swe/app/workspace/tenant_pool.py` |

### Phase 5：测试

| # | 任务 | 文件 |
|---|------|------|
| 5.1 | TenantInitSourceStore 单元测试 | `tests/unit/workspace/test_tenant_init_source_store.py` |
| 5.2 | TenantInitializer source_id 测试 | `tests/unit/workspace/test_tenant_initializer_source.py` |
| 5.3 | TenantIdentityMiddleware source_id 提取测试 | `tests/unit/middleware/test_tenant_identity_source.py` |
| 5.4 | 端到端集成测试 | `tests/integrated/test_source_init.py` |

---

## 8. 兼容性与回退

| 场景 | 行为 |
|------|------|
| 无 `X-Source-Id` header | `source_id=None` → 使用 `default/` 模板（完全向后兼容） |
| `X-Source-Id` 为 "default" | 使用 `default/` 模板 |
| `default_{source_id}` 目录不存在 | 回退到 `default/` 模板，日志记录 |
| 数据库不可用 | 映射表写入失败不影响初始化流程，仅日志告警 |
| 历史用户已初始化 | `has_seeded_bootstrap()` 返回 True → 跳过初始化 |

---

## 9. 风险点

| 风险 | 缓解措施 |
|------|----------|
| `source_id` 包含特殊字符导致目录名不安全 | `_resolve_template_name()` 中校验 source_id 格式，拒绝 `..`、`/`、`\` 等 |
| 大量 source 导致模板目录碎片化 | 文档约束 source 数量；模板目录结构统一由运维管理 |
| 映射表与实际初始化不一致 | `has_seeded_bootstrap()` 仍作为初始化的实际判断依据，映射表仅做记录 |

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| 1.0.0 | 2026-04-20 | 初始版本 |
