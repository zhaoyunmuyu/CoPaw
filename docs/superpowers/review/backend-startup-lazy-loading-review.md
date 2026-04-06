# 应用启动冷加载代码检视报告

- 检视范围：2026-04-05 ~ 2026-04-06 与 backend startup lazy loading 相关提交
- 重点提交：`71c5d6f feat(startup): implement lazy loading for backend startup`
- 参考设计：`openspec/changes/archive/2026-04-06-backend-startup-lazy-loading/design.md`
- 检视目标：确认实现是否符合“最小启动、按需初始化、租户隔离、职责拆分”的设计目标，并识别高置信问题与整改路径

---

## 一、总体结论

这次“应用启动冷加载”实现总体方向与设计文档一致，主要体现在：

- 启动阶段收缩为最小初始化，仅保留 `ensure_default_agent_exists()`
- `TenantWorkspacePool` 从“运行时池”收缩为“tenant bootstrap / registry”
- `Workspace.start()` 去掉 skill pool 初始化
- agent runtime 改为经 `MultiAgentManager.get_agent()` 按需启动

但当前实现里仍有 **2 个已确认缺陷**，以及 **2 个高风险兼容性问题** 需要尽快收口，否则会出现冷启动后功能直接报错、旧上下文契约失效、兼容接口语义漂移等问题。

---

## 二、设计符合点

对照设计文档，本次实现已经落实了以下关键点：

### 1. Service ready != all agents ready
已实现：应用启动时不再 `start_all_configured_agents()`。

- 位置：`src/copaw/app/_app.py:175-177`
- 影响：服务 readiness 不再依赖所有 agent runtime 启动完成，符合设计预期。

### 2. Default agent “exists” vs “is running”
已实现：启动时仅执行 `ensure_default_agent_exists()`，不再预热 default agent runtime。

- 位置：`src/copaw/app/_app.py:166-168`

### 3. Tenant bootstrap != agent runtime startup
已实现：`TenantWorkspaceMiddleware` 中只做 tenant bootstrap，不再直接启动 workspace runtime。

- 位置：`src/copaw/app/middleware/tenant_workspace.py:194-202`
- 位置：`src/copaw/app/workspace/tenant_pool.py:104-163`

### 4. Workspace.start() 失去 skill pool 初始化职责
已实现：移除了 `ensure_skill_pool_initialized()`。

- 位置：`src/copaw/app/workspace/workspace.py`（提交 diff 已删除对应逻辑）

这些都说明主设计方向是对的，问题主要集中在**旧契约收口不完整**和**入口层未同步迁移**。

---

## 三、问题清单

## P1. `/local-models` 路由已被当前改动直接打断

### 现象
启动流程里已经删除：

- `app.state.provider_manager`
- `app.state.local_model_manager`

见：

- `src/copaw/app/_app.py:166-198`

但本地模型路由仍然直接依赖这两个 state：

- `src/copaw/app/routers/local_models.py:17-24`

```python
def get_local_model_manager(request: Request) -> LocalModelManager:
    return request.app.state.local_model_manager

def get_provider_manager(request: Request) -> ProviderManager:
    return request.app.state.provider_manager
```

### 影响
以下接口在冷启动后首次访问时会直接因为 `AttributeError` 报错，而不是按需初始化：

- `/local-models/server`
- `/local-models/server/download`
- `/local-models/models`
- `/local-models/server` 的 start/stop
- 其他依赖 `Depends(get_local_model_manager)` / `Depends(get_provider_manager)` 的接口

### 根因
设计要求是“feature-level lazy initialization”，但 `local_models` 路由仍保留旧的“启动期注入 app.state”契约，没有迁移到按需获取。

### 证据
- 启动阶段不再设置 manager：`src/copaw/app/_app.py:166-198`
- 路由仍强依赖 app.state：`src/copaw/app/routers/local_models.py:17-24`
- 路由大量使用该依赖：`src/copaw/app/routers/local_models.py:107`, `175`, `194`, `206`, `223-224`, `262-263`, `292`, `310`, `335`, `347`

### 定性
**已确认缺陷，优先级最高。**

---

## P1. `TenantWorkspaceMiddleware` 去掉 workspace 绑定后，旧 request-scoped workspace 契约被破坏

### 现象
中间件现在只做：

- `await pool.ensure_bootstrap(tenant_id)`
- 然后直接 `return None`

见：

- `src/copaw/app/middleware/tenant_workspace.py:194-202`

因此以下逻辑不再执行：

- `request.state.workspace = workspace`
- `request.state.tenant_workspace = workspace`
- `set_current_workspace_dir(workspace.workspace_dir)`

见：

- `src/copaw/app/middleware/tenant_workspace.py:89-127`

### 影响
凡是仍依赖 `request.state.workspace` 的调用链，都会失去上下文。

已找到的直接证据：

1. `src/copaw/app/tenant_context.py:145-169`
   - `bind_request_context()` 明确从 `request.state.workspace` 取 workspace

2. `src/copaw/app/middleware/tenant_workspace.py:368-385`
   - `get_workspace_from_request_strict()` 仍会在没有 workspace 时抛 503

### 根因
这次改动把“tenant bootstrap”和“workspace runtime startup”拆开了，但同时把“request-scoped workspace context”也移除了；后者其实是一个**独立契约**，不能默认跟 runtime 一起消失。

### 证据
- 中间件不再绑定 workspace：`src/copaw/app/middleware/tenant_workspace.py:194-202`
- 旧 helper 仍存在：`src/copaw/app/middleware/tenant_workspace.py:356-385`
- 仍有 request-scoped 读取：`src/copaw/app/tenant_context.py:145-169`

### 定性
**已确认缺陷/兼容性回归。**

---

## P2. `TenantWorkspacePool.get_or_create()` 声称兼容旧接口，但行为已不再兼容

### 现象
现在的 `get_or_create()` 里每次都现建一个新的 `MultiAgentManager()`：

- `src/copaw/app/workspace/tenant_pool.py:185-196`

```python
from ..multi_agent_manager import MultiAgentManager
multi_agent_manager = MultiAgentManager()
return await multi_agent_manager.get_agent(agent_id, tenant_id=tenant_id)
```

同时 docstring 写的是：

- “kept for backward compatibility”

### 风险
这意味着：

- `TenantWorkspacePool` 不再缓存 runtime
- 多次 `get_or_create()` 不保证返回同一 runtime
- `stop_all()` 也无法覆盖这些通过临时 `MultiAgentManager()` 创建的 workspace

这和旧接口语义明显不一致。

### 进一步证据
仓库内仍有大量测试把 `get_or_create()` 当作“缓存/同实例/可 stop”的接口在验证：

- `tests/unit/app/test_tenant_pool.py:73`
- `tests/unit/app/test_tenant_pool.py:103-106`
- `tests/unit/app/test_tenant_pool.py:140-142`
- `tests/unit/app/test_tenant_pool.py:201-224`
- `tests/unit/app/test_tenant_pool.py:260-264`
- `tests/unit/app/test_tenant_pool.py:307`
- `tests/unit/app/test_tenant_pool.py:323`

如果这批测试未同步修订，则说明接口语义和测试预期已经出现分叉。

### 定性
**高风险兼容性问题。**

---

## P3. `tenant_context.bind_request_context()` 里使用 `workspace.path` 很可疑

### 现象
见：

- `src/copaw/app/tenant_context.py:160-168`

```python
workspace = getattr(request.state, "workspace", None)
workspace_dir = workspace.path if workspace else None
```

而 `Workspace` 类的可见属性是：

- `workspace.workspace_dir`

见：

- `src/copaw/app/workspace/workspace.py:73-76`

### 风险
如果未来某处重新恢复/继续依赖 `request.state.workspace`，这里可能还会额外触发属性错误，或者说明这里原本就是旧代码遗留。

### 定性
**中风险遗留问题，建议顺手修掉。**

---

## 四、整改详细方案

## 整改项 1：把 `/local-models` 完整改成“功能入口懒初始化”

### 目标
让 `local_models` 路由不依赖 `_app.py` 启动时注入的 app.state，而是在请求进入时自己拿到可用实例。

### 建议改法

#### 方案 A：直接在依赖函数里按需获取
修改：

- `src/copaw/app/routers/local_models.py:17-24`

建议改成类似：

```python
def get_local_model_manager(request: Request) -> LocalModelManager:
    manager = getattr(request.app.state, "local_model_manager", None)
    if manager is None:
        manager = LocalModelManager.get_instance()
        request.app.state.local_model_manager = manager
    return manager


def get_provider_manager(request: Request) -> ProviderManager:
    tenant_id: str | None = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        tenant_id = "default"
    return ProviderManager.get_instance(tenant_id)
```

### 为什么推荐这样改
- 对现有路由改动最小
- 保持“首次访问才初始化”
- 和 `src/copaw/app/routers/providers.py:45-66` 的 tenant-aware provider manager 获取方式一致

### 注意事项
1. `ProviderManager` 应优先 tenant-aware
   - 不建议继续使用全局默认实例，否则会破坏多租户语义
2. `LocalModelManager` 如果本身是进程级单例，可以继续挂到 `app.state` 做缓存
3. `_app.py` 的 shutdown 中保留：
   - `local_model_mgr = getattr(app.state, "local_model_manager", None)`
   - 这与按需初始化并不冲突

### 回归测试
新增/调整测试：

1. 冷启动后访问 `/local-models/server` 不报 500
2. 冷启动后首次访问 `/local-models/models` 可正常返回
3. 首次访问 `/local-models/server` 时会触发按需创建 manager
4. provider manager 获取遵循 tenant_id，而不是固定 default/global

---

## 整改项 2：把“request-scoped workspace context”从“runtime 是否启动”中解耦

### 目标
明确并恢复 request 级上下文契约，避免旧 helper 在冷加载后集体失效。

### 关键判断
你现在拆分的是：

- tenant bootstrap
- workspace runtime startup

这是对的。

但不应该顺手把下面这个契约一起删除：

- request 上是否存在可用于 tenant/workspace 语义解析的上下文对象

### 推荐方案

#### 方案 A：引入“轻量 workspace context”对象
在 `TenantWorkspaceMiddleware` 完成 `ensure_bootstrap(tenant_id)` 后，不要求启动 runtime，但可以在 `request.state` 里放一个轻量对象，例如：

```python
class TenantWorkspaceContext:
    def __init__(self, tenant_id: str, workspace_dir: Path):
        self.tenant_id = tenant_id
        self.workspace_dir = workspace_dir
```

然后：

```python
request.state.workspace = TenantWorkspaceContext(...)
request.state.tenant_workspace = request.state.workspace
workspace_token = set_current_workspace_dir(context.workspace_dir)
```

### 好处
- 不触发 runtime 启动
- 保留 request-scoped workspace 语义
- 兼容多数旧 helper
- 与设计目标不冲突

#### 方案 B：彻底废弃 `request.state.workspace` 契约
如果你希望完全去掉这个契约，那必须同步完成以下工作：

1. 废弃/删除
   - `get_workspace_from_request()`
   - `get_workspace_from_request_strict()`
   - `bind_request_context()` 中对 `request.state.workspace` 的读取

2. 全量替换调用方
   - 改为从 tenant_id / agent_id / MultiAgentManager 获取 runtime

3. 明确文档和测试都切换到新模式

### 建议选择
**建议优先选方案 A。**

原因：
- 改动最小
- 不影响 lazy-loading 主目标
- 可以先恢复兼容性，再逐步清理旧契约

### 回归测试
新增/调整测试：

1. tenant middleware 经过后，即使 runtime 未启动，也存在 request-scoped workspace context
2. `set_current_workspace_dir()` 仍能得到 tenant 对应目录
3. `get_workspace_from_request_strict()` 要么能工作，要么明确废弃并移除相关调用
4. 涉及 tenant context 绑定的请求链在冷启动下不报 503

---

## 整改项 3：修正 `TenantWorkspacePool.get_or_create()` 的兼容语义

### 目标
避免留下“名字像旧接口、行为却完全不同”的兼容陷阱。

### 推荐改法

#### 方案 A：显式废弃，不再伪装兼容
如果生产代码已经不再依赖它，建议直接：

1. 在 docstring 中明确写清楚：
   - 不保证缓存一致性
   - 仅为临时过渡入口
2. 在方法内部加 warning log
3. 调整/删除旧测试，避免错误背书

例如：

```python
logger.warning(
    "TenantWorkspacePool.get_or_create() is deprecated; use "
    "ensure_bootstrap() + app.state.multi_agent_manager.get_agent() instead"
)
```

#### 方案 B：真正恢复兼容语义
如果你必须保留它作为兼容接口，则不应在方法里 `MultiAgentManager()` 现建实例，而应使用应用级 manager：

- 由外部注入 `multi_agent_manager`
- 或 `TenantWorkspacePool` 在构造时持有 manager 引用

例如：

```python
class TenantWorkspacePool:
    def __init__(self, base_working_dir: Path, manager: MultiAgentManager | None = None):
        self._manager = manager
```

然后：

```python
return await self._manager.get_agent(agent_id, tenant_id=tenant_id)
```

### 建议选择
如果当前生产路径已经不走它，**优先方案 A：真废弃，不伪兼容。**

否则会出现：
- stop/reload 生命周期不统一
- 同 tenant agent 多实例漂移
- cache 语义和历史预期冲突

### 回归测试
1. 若保留兼容：重复 `get_or_create()` 返回同一 runtime
2. 若废弃：旧测试改写为 `ensure_bootstrap() + MultiAgentManager.get_agent()`
3. `stop_all()` 与实际创建路径保持一致，不再给人错误预期

---

## 整改项 4：修复 `tenant_context.bind_request_context()` 中的属性访问

### 目标
去掉潜在的隐藏错误点。

### 建议修改
文件：
- `src/copaw/app/tenant_context.py:160-168`

建议把：

```python
workspace_dir = workspace.path if workspace else None
```

改为更稳妥的形式：

```python
workspace_dir = None
if workspace is not None:
    workspace_dir = getattr(workspace, "workspace_dir", None)
    if workspace_dir is None:
        workspace_dir = getattr(workspace, "path", None)
```

如果你决定统一新契约，也可以直接只认 `workspace_dir`。

### 建议
如果要做体系收口，建议最终统一为 `workspace_dir`，不要再保留 `path` 这种不一致命名。

---

## 五、建议的整改顺序

### 第一阶段：先止血
1. 修 `src/copaw/app/routers/local_models.py`
2. 恢复 request-scoped workspace context，或临时兼容旧 helper
3. 补冷启动访问回归测试

### 第二阶段：收口旧契约
4. 明确 `TenantWorkspacePool.get_or_create()` 是真兼容还是废弃
5. 修正 `tenant_context.py` 的 `workspace.path` 问题
6. 清理依赖 `request.state.workspace` 的旧调用链

### 第三阶段：补文档与测试
7. 补“lazy loading architecture”开发说明
8. 更新旧测试，避免用过期语义验证新架构
9. 增加多租户 + 冷启动 + 首次访问场景测试

---

## 六、建议新增的测试清单

### 启动与入口层
1. 应用冷启动后访问 `/local-models/server` 返回非 500
2. 应用冷启动后首次访问 `/local-models/models` 能按需初始化 manager
3. provider manager 按 tenant 获取，不串租户

### 租户上下文
4. tenant middleware 在 runtime 未启动时仍能绑定 tenant 级 workspace context
5. `set_current_workspace_dir()` 在 tenant 请求中指向正确目录
6. 旧 helper 若保留，则在冷加载下仍可工作

### runtime 懒加载
7. `MultiAgentManager.get_agent()` 首次访问启动 runtime
8. 重复访问同 tenant + agent 命中缓存
9. 不同 tenant 访问彼此隔离

### 兼容接口
10. `TenantWorkspacePool.get_or_create()` 若保留，明确验证其语义
11. 若废弃，则测试 warning 和替代路径

---

## 七、最终结论

这次改动在**架构方向**上是正确的，真正的问题不在 lazy-loading 思路本身，而在于：

1. **入口层没有同步切换到懒初始化契约**
   - 典型代表：`/local-models`

2. **旧 request-scoped workspace 契约被一并拿掉，但调用方未收口**
   - 典型代表：`tenant_context.py`、`get_workspace_from_request_strict()`

3. **兼容接口表面保留，实际语义已变化**
   - 典型代表：`TenantWorkspacePool.get_or_create()`

如果只修一个点，优先修 `/local-models`；
如果要把这次 lazy-loading 真正落稳，建议至少完成：

- `local_models` 按需初始化修复
- request-scoped workspace context 收口
- `get_or_create()` 兼容语义澄清

---

## 八、附：关键代码位置索引

- 启动最小化：`src/copaw/app/_app.py:166-204`
- shutdown 中 local model 清理：`src/copaw/app/_app.py:209-220`
- tenant middleware 主流程：`src/copaw/app/middleware/tenant_workspace.py:83-172`
- tenant middleware bootstrap：`src/copaw/app/middleware/tenant_workspace.py:194-202`
- request workspace helper：`src/copaw/app/middleware/tenant_workspace.py:356-385`
- tenant context 绑定：`src/copaw/app/tenant_context.py:140-169`
- local models 依赖入口：`src/copaw/app/routers/local_models.py:17-24`
- providers 路由的正确 tenant-aware 获取方式：`src/copaw/app/routers/providers.py:45-66`
- tenant pool bootstrap 逻辑：`src/copaw/app/workspace/tenant_pool.py:104-196`
- workspace 属性定义：`src/copaw/app/workspace/workspace.py:73-76`

---

如需下一步落地，建议直接按下面顺序改代码：

1. `src/copaw/app/routers/local_models.py`
2. `src/copaw/app/middleware/tenant_workspace.py`
3. `src/copaw/app/tenant_context.py`
4. `src/copaw/app/workspace/tenant_pool.py`
5. 对应单元测试与冷启动回归测试
