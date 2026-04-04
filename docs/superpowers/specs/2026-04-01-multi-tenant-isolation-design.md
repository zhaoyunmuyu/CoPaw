# CoPaw 多租户隔离整体设计方案

## 1. 目标与范围

本方案的目标不是简单地区分用户，而是建立一条严格、可验证的多租户隔离主线：

> 任意请求只要带上 `X-Tenant-Id`，后续所有配置、文件、会话、定时任务、记忆、工具输出、推送消息，都只能落到该租户自己的边界内。

本期实现范围：

- 租户级磁盘隔离
- 请求级上下文隔离
- Workspace 级运行时隔离
- Console 请求隔离
- Cron 隔离
- 配置 / 记忆 / 上传文件隔离
- 为 Workspace Pool 扩展能力预留接口和元数据

本期不实现：

- 空闲自动回收
- LRU 驱逐逻辑生效
- 复杂租户配额策略

但本方案会为后续回收、驱逐、资源治理保留演进位。

---

## 2. 核心原则

系统遵循一条不可绕开的主线：

`tenant_id -> TenantWorkspacePool -> tenant Workspace -> current_workspace_dir -> tenant-scoped storage/runtime`

落地原则如下：

- **入口层**负责识别租户身份
  - HTTP 请求：来自 `X-Tenant-Id`
  - 外部 channel 回调：来自该 channel 所属 workspace
  - Cron / heartbeat：来自 job 元数据或所属 workspace
- **绑定层**负责把当前执行流绑定到租户 workspace
- **业务层和工具层**默认不直接理解 tenant，而是依赖当前 `workspace` / `workspace_dir`
- **强隔离优先**：只要当前执行链需要租户上下文却未绑定成功，就立即报错
- **禁止静默回退**：多租户模式下，不允许回退到全局 `WORKING_DIR`

这保证隔离是结构性成立，而不是依赖每个模块显式传递 tenant 参数。

### 2.1 多租户模式判定

系统需要一个明确的机制来区分"多租户模式"和"单租户兼容模式"，以决定 fallback 行为：

- **多租户模式**：当 `TenantIdentityMiddleware` 配置为 `require_tenant=True` 且 `default_tenant_id=None` 时生效。此模式下：
  - 所有有状态请求必须携带 `X-Tenant-Id`，否则返回 4xx
  - `get_current_workspace_dir()` 返回 `None` 时必须报错，不允许 fallback 到 `WORKING_DIR`
  - 工具层的 `get_current_workspace_dir() or WORKING_DIR` 模式视为隔离漏洞
- **单租户兼容模式**：当 `default_tenant_id="default"` 时生效。此模式下：
  - 未携带 `X-Tenant-Id` 的请求自动绑定到 `default` 租户
  - 行为等价于多租户架构下的 `default` 租户，但不强制要求 header
  - 工具层的 fallback 到 `WORKING_DIR` 仍然安全，因为 `WORKING_DIR/default/` 就是唯一租户目录

判定方式建议：在 `app.state` 上暴露 `multi_tenant_strict: bool` 标志，由 middleware 初始化时设置，供需要区分行为的组件查询。

---

## 3. 隔离边界定义

### 3.1 全局共享对象

以下对象继续保持进程级共享：

- FastAPI app
- provider manager
- local model manager
- 内置 skills
- 应用代码与静态资源
- Python 依赖
- 系统级环境变量与服务运行参数

### 3.2 租户隔离对象

以下对象必须进入 `tenant Workspace`：

- runner
- chat manager
- cron manager
- task tracker
- memory manager
- channel manager
- agent state / active agent
- config / jobs / chats / uploads / screenshots / secrets

即：

> 租户边界定义在 Workspace 实例本身，而不是定义在 router 或某个路径函数里。

---

## 4. 磁盘隔离设计

### 4.1 目录结构

所有租户数据统一落在 `WORKING_DIR` 下的租户子目录中：

```text
WORKING_DIR/
├── default/
│   ├── config.json
│   ├── jobs.json
│   ├── chats.json
│   ├── memory/
│   ├── media/
│   ├── customized_skills/
│   ├── custom_channels/
│   ├── models/
│   ├── screenshots/
│   ├── files/
│   └── secrets/
├── tenant-acme/
│   └── ...
└── tenant-foo/
    └── ...
```

### 4.2 必须 tenant-scoped 的持久化数据

以下内容必须按租户隔离：

- 配置文件
- cron jobs
- chats / session 持久化
- memory 数据
- media 上传文件
- 工具输出文件（截图、浏览器快照、导出文件等）
- customized skills
- custom channels
- token usage 数据
- tool guard 的租户配置
- tenant 业务密钥 / secret
- heartbeat 相关文件

### 4.3 共享但不隔离的内容

以下内容继续共享：

- 应用代码 `src/copaw/...`
- 内置 skills
- 安全扫描规则
- 前端静态资源
- Python 依赖
- 系统级运行配置

### 4.4 路径访问规则

禁止业务代码直接使用全局路径：

```python
WORKING_DIR / "jobs.json"
WORKING_DIR / "memory"
WORKING_DIR / "media"
```

统一改为租户感知路径函数，例如：

```python
get_tenant_working_dir()
get_tenant_jobs_path()
get_tenant_memory_dir()
get_tenant_media_dir()
get_tenant_config_path()
```

同时，多租户模式下禁止如下静默 fallback：

```python
get_current_workspace_dir() or WORKING_DIR
```

缺少 `workspace` 上下文时应直接报错。

---

## 5. 请求级上下文隔离

### 5.1 contextvars

在 `src/copaw/config/context.py` 现有 `current_workspace_dir` 基础上新增：

- `current_tenant_id`
- `current_user_id`

保留：

- `current_workspace_dir`
- `current_recent_max_bytes`

如继续保留 agent 上下文，则同时保留 `current_agent_id`，但解析顺序改为：

`tenant -> workspace -> active agent`

即 agent 不再是全局命名空间，而是租户内命名空间。

### 5.2 HTTP 中间件链

建议拆分为两个职责清晰的 middleware。

#### TenantIdentityMiddleware

职责：

- 解析 `X-Tenant-Id`
- 解析 `X-User-Id`
- 校验 `tenant_id` 格式
- 设置 `current_tenant_id/current_user_id`

失败策略：

- 缺少 `X-Tenant-Id` 时返回 4xx
- `tenant_id` 非法时返回 4xx
- 不默认回退到 `default`

#### TenantWorkspaceMiddleware

职责：

- 从 `app.state.tenant_workspace_pool` 获取当前 tenant workspace
- 将 workspace 放入 `request.state.workspace`
- 设置 `current_workspace_dir = workspace.workspace_dir`
- 在请求结束时恢复 / 清理上下文

要求：

- 默认所有有状态 API 都必须经过该 middleware
- 未来若存在公开、无状态接口，可显式排除，但不能默许绕过

### 5.3 非 HTTP 执行链

cron、background task、外部 channel callback 不经过 HTTP middleware，因此必须提供统一的上下文恢复入口，例如一个 context manager 或 helper：

- 设置 `current_tenant_id`
- 设置 `current_workspace_dir`
- 必要时设置 `current_user_id/current_agent_id`
- 执行完成后恢复旧上下文

该机制需要在 cron executor、heartbeat、channel webhook 等路径中复用，避免各处重复实现。

---

## 6. Workspace 隔离设计

### 6.1 设计原则

一个租户对应一个独立 Workspace 实例：

> tenant -> workspace

这与当前 `Workspace` 已经封装 runner、memory manager、channel manager、cron manager、chat manager、task tracker 等运行时组件的事实相契合，是侵入最小且隔离最稳的方案。

### 6.2 TenantWorkspacePool

新增：

- `src/copaw/app/workspace/tenant_pool.py`

该组件本质上不是资源池，而是 **tenant -> Workspace 的并发安全注册表 / 缓存层**。

第一版职责：

- `get_or_create(tenant_id)`
- `get(tenant_id)`
- `remove(tenant_id)`
- `stop_all()`
- `mark_access(tenant_id)`

内部建议维护：

- `workspaces_by_tenant`
- `creation_locks_by_tenant`
- `last_access_by_tenant`

虽然当前不实现空闲回收，但 `last_access` 应先保留，避免后续接口再次变更。

### 6.3 创建语义

`get_or_create(tenant_id)` 应执行：

1. 计算 tenant working dir
2. 基于该目录构建 tenant-scoped Workspace
3. 启动 workspace 内部组件并缓存

关键要求：

- 同一 tenant 并发请求只能创建一次
- 创建失败时不得缓存半初始化对象
- workspace 的启动与停止必须完整对称

### 6.4 与现有 MultiAgentManager 的关系

现有 app 初始化主链以 `MultiAgentManager` 为中心，按 `agent_id` 获取 workspace。多租户后需要改为：

- **租户是第一层命名空间**
- **agent 是租户内第二层命名空间**

推荐方案：

- `TenantWorkspacePool` 持有 tenant runtime
- tenant runtime 内部管理该租户自己的 agent list / active agent 状态

不建议继续保留”app 全局一个 MultiAgentManager，所有 agent 跨 tenant 共享命名空间”的结构，因为这会直接破坏隔离边界。

#### 6.4.1 MultiAgentManager 退场路径

当前实现中 `MultiAgentManager` 和 `TenantWorkspacePool` 同时存在于 `_app.py`。虽然 `MultiAgentManager` 内部已通过 `_cache_key(agent_id, tenant_id)` 做了租户隔离，但两套并行的 workspace 管理机制增加了理解和维护成本，且容易引入”该走哪条路径”的歧义。

建议退场步骤：

1. **过渡期**（当前）：`MultiAgentManager` 保留，但所有新代码路径统一走 `TenantWorkspacePool`
2. **收敛期**：将 `MultiAgentManager` 的剩余调用方逐一迁移到 `TenantWorkspacePool`
3. **移除期**：确认无引用后删除 `MultiAgentManager`

退场完成标志：`_app.py` 中只存在 `TenantWorkspacePool` 一个 workspace 生命周期管理入口。

### 6.5 app 初始化原则

`src/copaw/app/_app.py` 目前在应用启动时统一启动全部 agent。多租户后建议改为：

- app 启动时仅初始化：
  - `TenantWorkspacePool`
  - provider / local model 等真正全局共享组件
- tenant workspace 按需懒创建
- app shutdown 时统一执行 `tenant_workspace_pool.stop_all()`

这样更符合多租户模型，也避免启动阶段预热不存在的 tenant。

---

## 7. Router 与接口隔离设计

总原则：

- router 不直接拼 tenant 路径
- router 不直接读取全局 `WORKING_DIR`
- router 统一从 `request.state.workspace` 获取运行时对象
- 所有有状态接口都必须先绑定 tenant workspace，再做业务处理

### 7.1 Console Chat

当前 `src/copaw/app/routers/console.py` 已通过 `get_agent_for_request(request)` 取 workspace，但需要改为 tenant 优先语义。

设计要求：

- `request.state.workspace` 成为唯一来源
- 如保留 agent 选择，则只在当前 tenant workspace 内解析 agent
- `session_id` 必须带租户边界，最少为：

```text
console:<tenant_id>:<user_id>
```

- `chat_manager` 必须是 tenant workspace 内实例
- reconnect / stop 只能作用于当前 tenant 的 `workspace.task_tracker`

效果：

- tenant A 无法 attach tenant B 的 chat
- tenant A 无法 stop tenant B 的任务
- chats.json 自然落在各自 tenant 目录

### 7.2 Console Upload

`ConsoleChannel` 初始化时绑定 tenant workspace_dir，采用：

- `media_dir = tenant_workspace_dir / "media"`

这样上传链路天然隔离，无需 router 自己再理解 tenant。

### 7.3 Push Messages

当前 `console_push_store` 是进程级全局列表，且 `GET /console/push-messages` 在未提供 `session_id` 时会返回所有 recent messages。这是明确的跨租户泄露风险。

设计要求：

- push message 主键至少包含：
  - `tenant_id`
  - `session_id`
- 读取时只允许返回“当前 tenant + 当前 session”的消息
- 禁止暴露全局 `get_recent()` 语义
- 若前端确实需要 recent，也必须是 tenant-scoped recent

更稳妥的接口收敛方式：

- `session_id` 必填
- 接口仅返回当前 tenant 下该 session 的消息

### 7.4 Settings

`src/copaw/app/routers/settings.py` 的读取与保存必须只作用于当前 tenant config。

要求：

- tenant A 的模型配置、渠道配置、UI 设置，对 tenant B 完全不可见

### 7.5 Agents

`src/copaw/app/routers/agents.py` 需改为 **tenant 内 agent 命名空间**。

要求：

- agent list 是 tenant 内的
- active_agent 是 tenant 内的
- `X-Agent-Id` 只在当前 tenant 下解析
- agent config 路径基于 tenant config path

解析顺序应为：

`current_tenant -> tenant config -> tenant agents -> active/current agent`

### 7.6 Workspace / Files / Status

`src/copaw/app/routers/workspace.py` 以及任何返回文件列表、运行状态、存储占用的接口，都只能返回当前 tenant workspace 视图。

禁止：

- 全局工作目录浏览
- 全局文件统计
- 跨 tenant 的存储占用聚合

若未来需要管理员视角，应设计成完全独立的管理员接口和权限模型。

---

## 8. Cron 与异步执行链

### 8.1 租户内独立 CronManager

`src/copaw/app/crons/manager.py` 当前是 agent 维度。多租户后必须改为 tenant workspace 内独立 `CronManager`，并在初始化时绑定：

- tenant workspace_dir
- tenant channel_manager
- tenant runner / active agent resolver

### 8.2 jobs.json 与 job 元数据

要求：

- `jobs.json` 位于 `tenant_workspace_dir / "jobs.json"`
- `CronJobSpec.meta["tenant_id"] = tenant_id`

虽然 tenant 理论上可从 workspace 推导，但冗余记录能提高调试、导出、恢复上下文时的可靠性。

#### 8.2.1 Job 创建路径的 tenant_id 注入

所有 job 创建入口都必须在持久化前注入 `tenant_id`，不能依赖客户端传入：

| 创建入口 | tenant_id 来源 | 要求 |
|---------|---------------|------|
| `POST /cron/jobs` API | `request.state.tenant_id`（由 middleware 设置） | 服务端强制注入，忽略客户端传入的 tenant_id |
| `PUT /cron/jobs/{job_id}` API | 同上 | 同上 |
| CLI `copaw cron create` | `--tenant-id` 参数或 HTTP header `X-Tenant-Id` | CLI 必须传递 tenant 标识 |
| Heartbeat 自动创建 | 所属 workspace 的 tenant_id | 由 CronManager 初始化时绑定 |

禁止出现 `tenant_id=None` 的持久化 job（单租户模式下应为 `"default"`）。

### 8.3 执行前恢复上下文

cron 不经过 HTTP middleware，因此在 `executor.py` 真正执行任务前，必须显式恢复：

- `current_tenant_id`
- `current_workspace_dir`
- 必要时 `current_agent_id`

否则 file tool、shell、memory、config 等能力可能误落到共享目录。

### 8.4 Heartbeat

heartbeat 也必须 tenant-scoped：

- 每个 tenant workspace 自己决定是否启用 heartbeat
- heartbeat 文件写到 tenant working dir
- dispatch target、配置读取、执行上下文都绑定 tenant

不能再有全局 heartbeat 文件或全局 heartbeat 运行语义。

### 8.5 Background Task / Reconnect / Stop

`task_tracker` 必须始终作为 `workspace.task_tracker` 使用，不能再有全局共享 tracker。

这样才能保证：

- tenant A 的 attach / reconnect / stop 只作用于 tenant A
- tenant B 无法影响 tenant A 的后台执行链

---

## 9. 配置、Secrets、Memory、工具输出隔离

### 9.1 Config 分层

`src/copaw/config/utils.py` 当前仍围绕全局 `WORKING_DIR` 展开。多租户后应拆分为两层：

#### 系统级配置

只保留真正系统级内容：

- 服务监听参数
- 日志级别
- 运行模式
- 全局 provider 能力开关

#### 租户级配置

全部迁移到 tenant working dir，包括：

- config.json
- chats.json
- jobs.json
- agent config
- heartbeat / last_api / last_dispatch
- token usage
- tool guard tenant config

因此，`get_config_path()` 一类的全局默认入口不能再作为业务路径默认值。

### 9.2 Secrets / Envs

必须区分两类配置：

#### 系统 env

继续来自真实环境变量，用于服务进程本身运行。

#### tenant secrets

必须存入 tenant secret store，例如：

- tenant secret file
- 或 tenant config 下的专门 secrets 区域

使用规则：

- router / API 读写的是 tenant secret store
- provider / channel 初始化时从 tenant workspace 加载
- 不写回全局 `os.environ`

这样才能保证 tenant A 与 tenant B 的 API key、token、provider 配置互不可见。

#### 9.2.1 需要改造的全局 secret 访问点

以下组件当前直接使用全局 `SECRET_DIR`，必须迁移到租户隔离路径：

| 组件 | 当前行为 | 目标行为 |
|------|---------|---------|
| `envs/store.py` `load_envs_into_environ()` | 启动时将全局 `envs.json` 加载到 `os.environ` | 仅加载系统级 bootstrap 变量；租户 secret 按需从 tenant secret store 读取，不污染 `os.environ` |
| `providers/provider_manager.py` | `root_path = SECRET_DIR / "providers"` 全局共享 | 区分系统级 provider（全局共享）和租户级 provider credential（tenant secret store） |
| `app/auth.py` | `AUTH_FILE = SECRET_DIR / "auth.json"` 单一全局 | 若需要租户级认证，迁移到 tenant secret store；若认证是系统级网关行为，保持全局但明确标注 |
| `agents/skills_manager.py` | 直接写 `os.environ[key] = value` | 改为写入 tenant-scoped env store，不污染进程全局环境 |
| `app/runner/runner.py` | 从 `./` 加载 `.env` 到全局 `os.environ` | 从 tenant workspace 加载 `.env`，不污染全局 |
| `constant.py` | 模块导入时加载项目根 `.env` | 仅保留系统级 bootstrap 变量 |

#### 9.2.2 租户 secret 读取模式

推荐引入 `get_tenant_env(key, tenant_id=None)` 辅助函数：

- 从 tenant secret store（`get_tenant_secrets_dir() / "envs.json"`）读取
- 不经过 `os.environ`
- agent / skill / provider 代码中所有 `os.getenv()` 调用逐步替换为该函数
- 子进程启动时显式构造 env dict，而非继承全局 `os.environ`

#### 9.2.3 Provider Manager 隔离策略

Provider Manager 当前是全局共享对象（见 3.1 节）。多租户下需要区分：

- **provider 能力定义**（支持哪些 provider、模型列表）：继续全局共享
- **provider credential**（API key、base URL、自定义端点）：必须租户隔离

实现方式：Provider Manager 在执行请求时，从当前 tenant workspace 加载 credential，而非从全局 `SECRET_DIR` 读取。

### 9.3 Memory

Memory 必须 tenant-scoped，但隔离应主要在 workspace 层完成，而不是在 memory 层显式引入 tenant 语义。

设计原则：

- memory manager 继续只理解 `working_dir`
- `working_dir` 必须是 tenant workspace_dir
- memory 相关文件、索引、摘要产物都从 tenant workspace_dir 派生
- memory 依赖的 config / agent config 读取接口也必须先 tenant-scoped

这意味着：

- `memory/` 目录天然位于 `tenant_workspace_dir / "memory"`
- ReMeLight 的底层 file store / index / watcher 也应随 tenant working_dir 隔离
- memory summary 中触发的文件工具必须运行在当前 tenant workspace context 下

特别要求：

- 不要求 memory 模块到处显式传递 `tenant_id`
- 但必须保证创建 `MemoryManager` 时传入的是 tenant workspace_dir
- `load_agent_config()` 一类依赖接口不能再按全局 agent 命名空间解析，否则会导致 memory 读取错误配置或把异常产物写到错误目录
- 若 `load_config()` 中存在租户级设置（例如 user timezone），则该读取也必须改为 tenant-scoped；若属于系统级设置，则可继续全局共享

因此，本方案对 memory 的改造重点不是重写 memory 模块，而是保证：

1. memory manager 绑定到正确的 tenant workspace_dir
2. memory 运行时恢复了正确的 workspace context
3. memory 依赖的 agent/config 读取链路已经 tenant-scoped

只要这三条成立，memory 基本可以在低侵入前提下完成可靠隔离。

### 9.4 工具输出目录

截图、浏览器快照、导出文件、临时附件等都必须统一从 tenant workspace_dir 派生，例如：

- `screenshots/`
- `files/`
- `browser-artifacts/`
- `exports/`

关键约束：

- 所有工具输出都必须从当前 workspace_dir 推导
- 不得 fallback 到全局 `WORKING_DIR`

---

## 10. 非 HTTP 入口隔离

外部 IM / channel webhook 不一定带 `X-Tenant-Id`，因此租户来源必须改为：

- 根据该 channel 配置属于哪个 tenant workspace
- 事件进入后先绑定对应 tenant workspace
- 再进入 runner / task / memory / file 相关逻辑

即：

- HTTP 入口按 header 定 tenant
- 外部 channel 入口按 workspace 归属定 tenant
- 最终都在”绑定当前 workspace 上下文”这一层汇合

### 10.1 Channel 层租户绑定实施要求

当前所有 channel 实现（DingTalk、Feishu、Telegram、Discord、QQ、Weixin、WeCom、iMessage、XiaoYi、Mattermost、Matrix、MQTT、Voice、Console）的消息处理路径 `_consume_one_request()` 均未绑定租户上下文。这是多租户隔离的关键缺口，必须在第三阶段完成修复。

#### 绑定位置

在 `BaseChannel._consume_one_request()` 入口处统一绑定，而非在每个子类中重复实现：

```python
async def _consume_one_request(self, payload: Any) -> None:
    tenant_id = self._resolve_tenant()
    with bind_tenant_context(
        tenant_id=tenant_id,
        user_id=self._extract_sender_id(payload),
        workspace_dir=self._workspace.workspace_dir,
    ):
        # 原有处理逻辑
```

#### 租户来源

Channel 实例在创建时已绑定到特定 tenant workspace（由 `TenantWorkspacePool` 管理），因此：

- `tenant_id` 来自 channel 所属 workspace 的 tenant 元数据
- 不需要从消息 payload 中解析 tenant
- `Workspace` 类需要暴露 `tenant_id` 属性供 channel 使用

#### 验收条件

- 所有 channel 消息处理必须在 `bind_tenant_context()` 内执行
- channel 内的文件写入、memory 操作、config 读取都解析到正确的 tenant workspace
- 不同 tenant 的 channel 实例之间无共享可变状态

---

## 11. 实施顺序

建议按 4 个阶段实施，每个阶段都能独立验证隔离是否成立。

### 第一阶段：建立租户主链路

改动范围：

- `config/context.py`
- tenant middleware
- `TenantWorkspacePool`
- app 初始化入口
- `request.state.workspace` 打通

阶段目标：

- 有状态 HTTP 请求必须带合法 `X-Tenant-Id`
- 当前请求能够稳定获得 tenant workspace
- `current_workspace_dir` 来自 tenant workspace，而不是全局目录

### 第二阶段：打通核心交互接口

优先顺序：

1. `routers/console.py`
2. `console_push_store.py`
3. `routers/settings.py`
4. `routers/agents.py`
5. `routers/workspace.py`

目的：先封住最容易直接串租户的用户可见入口。

### 第三阶段：打通异步链路

范围：

- `app/crons/*`
- heartbeat
- background task / reconnect / stop
- 外部 channel callback 的 tenant 绑定逻辑

目的：封住“不走 HTTP 但仍会落盘 / 发消息”的路径。

### 第四阶段：收紧配置与文件边界

范围：

- `config/utils.py`
- tenant path helpers
- secret / envs 存储
- uploads / screenshots / browser artifacts / exports
- customized_skills / custom_channels
- token usage / tool guard tenant config

目的：彻底清理所有仍可能偷偷走全局路径的能力。

---

## 12. 风险清单

以下问题必须专项检查：

### 12.1 全局内存态泄露

重点检查：

- `console_push_store`
- 全局缓存
- 全局 tracker / manager 单例
- 任何 module-level dict / list

判断标准：

- key 是否显式带 tenant
- 或该状态是否已被收进 tenant workspace

### 12.2 静默 fallback

重点检查：

- `get_current_workspace_dir() or WORKING_DIR`
- `load_config()` 默认全局路径
- agent / config / job / chat 的默认读取路径

在强隔离模式下，这些都应视为漏洞入口。

### 12.3 agent 与 tenant 命名空间混用

重点检查：

- active_agent 是否全局共享
- `X-Agent-Id` 是否跨 tenant 可见
- agent config 是否仍写到全局位置

### 12.4 异步上下文丢失

重点检查：

- cron callback
- background task
- stream reconnect
- webhook handler
- heartbeat task

只要执行流可能脱离原始请求，就必须显式恢复 tenant / workspace context。

### 12.5 磁盘目录遗漏

重点检查：

- `jobs.json`
- `chats.json`
- `memory/`
- `media/`
- `customized_skills/`
- `custom_channels/`
- `screenshots/`
- `files/`
- heartbeat 相关文件
- token usage
- tenant secrets

只要其中任意一项仍落在全局目录，多租户隔离就没有闭环。

### 12.6 Channel 层租户上下文缺失

重点检查：

- `BaseChannel._consume_one_request()` 是否在处理前绑定了 tenant context
- 所有 14 个 channel 实现是否都通过基类统一绑定
- channel 内的文件写入、memory 操作是否解析到正确的 tenant workspace

当前状态：所有 channel 实现均未绑定租户上下文，是最大的隔离缺口。

### 12.7 os.environ 全局污染

重点检查：

- `load_envs_into_environ()` 是否仍在启动时将租户 secret 加载到全局 `os.environ`
- `skills_manager.py` 是否仍直接写 `os.environ[key] = value`
- `runner.py` 是否仍从 `./` 加载 `.env` 到全局环境
- 子进程是否继承了包含其他租户 secret 的全局环境

`os.environ` 是进程级共享状态，任何租户 secret 写入 `os.environ` 都等同于跨租户泄露。

### 12.8 Cron Job 创建路径 tenant_id 缺失

重点检查：

- `POST /cron/jobs` 和 `PUT /cron/jobs/{job_id}` 是否从 request context 注入 tenant_id
- CLI `copaw cron create` 是否传递 tenant 标识
- Heartbeat 自动创建的 job 是否携带 tenant_id
- 是否存在 `tenant_id=None` 的持久化 job

---

## 13. 验收标准

验收标准应写成可验证断言，而不是泛泛描述。

### 13.1 请求隔离

- 不带 `X-Tenant-Id` 的有状态请求返回 4xx
- tenant A 请求不能读取 tenant B 的聊天、配置、任务、文件
- 同一用户在不同 tenant 下的 session_id 不冲突

### 13.2 磁盘隔离

- tenant A / B 分别产生独立的 `config.json`、`jobs.json`、`chats.json`
- 上传、截图、导出文件落在各自 tenant 目录
- 不再出现新的共享全局业务数据文件

### 13.3 运行时隔离

- tenant A 的 `task_tracker` 无法 stop / attach tenant B 的任务
- tenant A 的 cron 不会向 tenant B 的 console / session 推消息
- tenant A 切换 active agent 不影响 tenant B

### 13.4 上下文正确性

- HTTP 请求中工具相对路径解析到当前 tenant workspace
- cron / heartbeat / webhook 中工具相对路径同样解析到正确 tenant workspace
- 缺失 workspace context 时直接报错，而不是回退到全局目录

### 13.5 单租户回归兼容

单租户场景下，统一以 `tenant_id=default` 运行：

- 原有能力仍可正常工作
- 但底层不保留旧的“全局业务目录”语义
- 单租户只是多租户架构下的 `default tenant`

---

## 14. 最终结论

本方案的最终架构结论是：

> 把 tenant 作为顶层运行时边界，把 Workspace 作为唯一隔离容器，把 workspace_dir 作为所有持久化与工具执行的唯一落点。

该方案的优势：

- 架构主线清晰
- 与现有 Workspace 模型高度契合
- 对 memory / file tool / shell 等底层能力侵入最小
- 能建立“强隔离默认正确”的结构约束
- 为未来 idle cleanup、tenant quota、workspace eviction 保留扩展位
