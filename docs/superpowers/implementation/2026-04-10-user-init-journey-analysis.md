# 用户初始化旅程分析

Date: 2026-04-10

Related artifacts:
- `docs/superpowers/specs/2026-04-02-cli-init-multi-tenant-design.md`
- `docs/superpowers/specs/2026-04-03-model-config-multi-tenant-design.md`
- `docs/superpowers/review/tenant-isolated-provider-config-review.md`

---

## 1. 目标

本文分析当前代码中的两条“用户初始化”路径：

1. 显式执行 `swe init` 的命令行初始化路径
2. 首次接口访问时，经中间件拦截触发的被动初始化路径

本文重点回答四个问题：

1. 用户的完整初始化旅程是什么
2. 每个阶段最终会产出哪些目录和文件
3. `swe init` 与接口拦截初始化的最终产物差异是什么
4. 当前实现与设计意图之间有哪些偏差

本文描述的是“当前代码真实行为”，不是仅复述设计方案。

---

## 2. 总体结论

当前代码中，初始化存在两条主路径：

1. `swe init` 走的是主动全量初始化。它先复用 `TenantInitializer.initialize_full()` 完成租户脚手架，再继续执行 CLI 专属的 heartbeat、provider、skills、环境变量等配置流程。
2. 接口拦截走的是被动懒初始化。它只会执行 `TenantInitializer.ensure_seeded_bootstrap()` 级别的租户脚手架初始化，不会创建 QA agent，不会立即初始化 provider 存储，也不会启动 workspace runtime。

两条路径共享的核心能力是：

- 创建 tenant 目录骨架
- 确保 `default` agent 的 tenant-scoped workspace 存在
- 确保 default workspace 的 Markdown scaffold、`jobs.json`、`chats.json`、`token_usage.json` 存在
- 初始化 tenant 级 skill pool
- 在有 `default` tenant 模板时，从 `default` tenant 继承 config 和 skill 状态

两条路径最大的产物差异是：

- `swe init` 理论上会额外产出 tenant 根目录 `HEARTBEAT.md`、QA agent workspace、provider 配置和 active model 配置
- 被动初始化只会产出 tenant 脚手架；provider 配置和 runtime 会继续按需懒加载

但当前实现里存在几个重要偏差：

1. `swe init` 复制初始化模板 `config.json` / `providers.json` 的逻辑当前基本无效，因为模板文件不存在
2. `swe init` 的 provider 配置步骤没有透传 `tenant_id`，实际落到 `default` tenant provider 存储
3. `swe init --defaults` 下载和启用技能时使用了全局 skill pool service，而不是 tenant-scoped skill pool
4. CLI 会打印“Builtin QA agent workspace ensured”，但 QA agent 实际可能因为依赖缺失而创建失败

---

## 3. 代码入口

### 3.1 命令行初始化入口

- `src/swe/cli/init_cmd.py`
- 核心函数：`init_cmd()`

入口特征：

- 显式接收 `--tenant-id`
- 直接构造 `tenant_dir = WORKING_DIR / tenant_id`
- 调用 `TenantInitializer.initialize_full()`

关键代码：

- `src/swe/cli/init_cmd.py:142`
- `src/swe/cli/init_cmd.py:151`
- `src/swe/cli/init_cmd.py:224`

### 3.2 接口拦截初始化入口

- `src/swe/app/_app.py`
- `src/swe/app/middleware/tenant_identity.py`
- `src/swe/app/middleware/tenant_workspace.py`
- `src/swe/app/workspace/tenant_pool.py`

入口特征：

- 请求先经过 `TenantIdentityMiddleware`
- 再由 `TenantWorkspaceMiddleware` 调用 `TenantWorkspacePool.ensure_bootstrap()`
- `ensure_bootstrap()` 内部执行 `TenantInitializer.ensure_seeded_bootstrap()`

关键代码：

- `src/swe/app/_app.py:363`
- `src/swe/app/_app.py:369`
- `src/swe/app/middleware/tenant_workspace.py:185`
- `src/swe/app/workspace/tenant_pool.py:118`

---

## 4. 共享初始化内核：TenantInitializer

`TenantInitializer` 是 CLI 初始化和 runtime 懒初始化的共享底座。

文件：

- `src/swe/app/workspace/tenant_initializer.py`

### 4.1 minimal bootstrap

`initialize_minimal()` 只做两件事：

1. 创建 tenant 目录骨架
2. 确保 default agent 存在

关键代码：

- `src/swe/app/workspace/tenant_initializer.py:84`
- `src/swe/app/workspace/tenant_initializer.py:43`
- `src/swe/app/workspace/tenant_initializer.py:53`

目录骨架包括：

- `<tenant>/`
- `<tenant>/workspaces/`
- `<tenant>/media/`
- `<tenant>/secrets/`

### 4.2 runtime-safe seeded bootstrap

`ensure_seeded_bootstrap()` 在 minimal bootstrap 基础上继续做四步：

1. 必要时从 `default` tenant 继承 `config.json`
2. 初始化 tenant `skill_pool`
3. 初始化 default workspace 的 skills
4. 补齐 default workspace scaffold

关键代码：

- `src/swe/app/workspace/tenant_initializer.py:96`
- `src/swe/app/workspace/tenant_initializer.py:131`
- `src/swe/app/workspace/tenant_initializer.py:137`
- `src/swe/app/workspace/tenant_initializer.py:141`
- `src/swe/app/workspace/tenant_initializer.py:144`

### 4.3 full bootstrap

`initialize_full()` 先调用 `ensure_seeded_bootstrap()`，再额外调用 `ensure_qa_agent()`。

关键代码：

- `src/swe/app/workspace/tenant_initializer.py:789`
- `src/swe/app/workspace/tenant_initializer.py:803`
- `src/swe/app/workspace/tenant_initializer.py:807`

这就是 CLI 初始化和接口被动初始化的第一层分界线：

- 接口被动初始化停在 `ensure_seeded_bootstrap()`
- CLI 初始化继续走到 `initialize_full()`

---

## 5. 被动初始化旅程

### 5.1 请求进入中间件

应用中间件顺序保证 tenant identity 先于 tenant workspace 解析：

- `TenantIdentityMiddleware`
- `TenantWorkspaceMiddleware`

关键代码：

- `src/swe/app/_app.py:345`
- `src/swe/app/_app.py:365`
- `src/swe/app/_app.py:369`

### 5.2 TenantIdentityMiddleware 绑定 tenant

`TenantIdentityMiddleware` 读取：

- `X-Tenant-Id`
- `X-User-Id`

并把 tenant/user 绑定到 request state 和 contextvars。

关键代码：

- `src/swe/app/middleware/tenant_identity.py`

### 5.3 TenantWorkspaceMiddleware 触发 bootstrap

`TenantWorkspaceMiddleware._get_workspace()` 中，第一次访问 tenant 时会调用：

```python
await pool.ensure_bootstrap(tenant_id)
```

关键代码：

- `src/swe/app/middleware/tenant_workspace.py:163`
- `src/swe/app/middleware/tenant_workspace.py:187`

### 5.4 TenantWorkspacePool.ensure_bootstrap()

`ensure_bootstrap()` 的语义是：

- 检查 tenant 是否已经具备 seeded bootstrap
- 如果没有，则加 tenant 级锁后执行 bootstrap
- bootstrap 完成后，只在 pool 中登记 tenant，不创建 runtime

关键代码：

- `src/swe/app/workspace/tenant_pool.py:118`
- `src/swe/app/workspace/tenant_pool.py:167`
- `src/swe/app/workspace/tenant_pool.py:185`

这里的注释也明确说明：

- bootstrap 不创建 QA agent
- bootstrap 不启动 workspace runtime

### 5.5 被动初始化结束后的系统状态

完成 `ensure_bootstrap()` 后：

1. tenant 目录已经存在
2. default workspace 已经存在
3. tenant skill pool 已经存在
4. request.state 中保存的是一个轻量 `TenantWorkspaceContext`
5. 真正的 `Workspace` runtime 还没有启动

`TenantWorkspaceMiddleware` 自己的注释也写得很明确：

- 返回的是 lightweight context
- full workspace runtime 由 `MultiAgentManager.get_agent()` 按需创建

关键代码：

- `src/swe/app/middleware/tenant_workspace.py:175`
- `src/swe/app/middleware/tenant_workspace.py:189`
- `src/swe/app/multi_agent_manager.py:49`

### 5.6 provider 配置不会在这一步初始化

被动初始化完成时，provider 存储通常还不存在。

provider 存储的懒初始化边界在：

- provider API
- local model API
- model factory 创建模型

例如模型工厂里会先调用：

```python
ProviderManager.ensure_tenant_provider_storage(tenant_id)
```

关键代码：

- `src/swe/providers/provider_manager.py:702`
- `src/swe/agents/model_factory.py:825`

因此：

- 第一次普通请求触发 tenant bootstrap，不等于 provider 配置也已经就绪
- 第一次真正访问 provider 或创建模型时，`~/.swe.secret/<tenant>/providers/` 才会出现

---

## 6. 被动初始化的最终产物

### 6.1 首次接口拦截完成后，已存在的产物

按当前代码，首次接口拦截后，tenant 至少会有以下产物：

```text
~/.swe/<tenant>/
├── config.json
├── media/
├── secrets/
├── skill_pool/
│   ├── skill.json
│   └── <builtin or inherited skills>/
└── workspaces/
    └── default/
        ├── agent.json
        ├── AGENTS.md
        ├── BOOTSTRAP.md
        ├── HEARTBEAT.md
        ├── MEMORY.md
        ├── PROFILE.md
        ├── SOUL.md
        ├── chats.json
        ├── jobs.json
        ├── token_usage.json
        ├── sessions/
        ├── memory/
        └── skills/
```

产物来源：

- `ensure_default_agent_exists()` 负责 default workspace、`chats.json`、`jobs.json`
- `ensure_default_workspace_scaffold()` 负责 `agent.json`、Markdown scaffold、`token_usage.json`
- `seed_skill_pool_from_default()` 负责 tenant `skill_pool`
- `seed_default_workspace_skills_from_default()` 负责 default workspace skill state

关键代码：

- `src/swe/app/migration.py:642`
- `src/swe/app/workspace/tenant_initializer.py:313`
- `src/swe/app/workspace/tenant_initializer.py:430`
- `src/swe/app/workspace/tenant_initializer.py:593`

### 6.2 首次接口拦截完成后，不存在的产物

按当前代码，以下内容通常还不存在：

- `~/.swe/<tenant>/HEARTBEAT.md`
- `~/.swe/<tenant>/workspaces/<BUILTIN_QA_AGENT_ID>/...`
- `~/.swe.secret/<tenant>/providers/...`
- `~/.swe.secret/<tenant>/providers/active_model.json`

其中 QA agent 不存在是设计边界，不是 bug。

对应测试：

- `tests/unit/workspace/test_tenant_initializer.py:190`

### 6.3 进一步触发 provider 功能后新增的产物

当 tenant 首次真正访问 provider/model 功能后，会继续补出：

```text
~/.swe.secret/<tenant>/
├── .provider_init.lock
└── providers/
    ├── builtin/
    └── custom/
```

如果 `default` tenant 已经存在 provider 配置，则 `providers/` 会从 default tenant 整体拷贝而来。

关键代码：

- `src/swe/providers/provider_manager.py:674`
- `src/swe/providers/provider_manager.py:684`

---

## 7. `swe init` 旅程

### 7.1 命令入口

`swe init` 入口为：

- `src/swe/cli/init_cmd.py:142`

它显式接收：

- `--tenant-id`
- `--defaults`
- `--force`
- `--accept-security`

### 7.2 命令执行阶段

当前代码中的主要阶段如下。

#### 阶段 1：解析 tenant 路径

```python
tenant_dir = WORKING_DIR / tenant_id
config_path = tenant_dir / "config.json"
heartbeat_path = tenant_dir / "HEARTBEAT.md"
default_workspace = tenant_dir / "workspaces" / "default"
```

关键代码：

- `src/swe/cli/init_cmd.py:151`

#### 阶段 2：安全确认和 telemetry

CLI 会先展示安全提示，然后在全局 `WORKING_DIR` 级别处理 telemetry。

关键代码：

- `src/swe/cli/init_cmd.py:159`
- `src/swe/cli/init_cmd.py:177`

#### 阶段 3：尝试复制初始化模板

CLI 会调用 `copy_init_config_files()`，理论上想复制：

- `config.json`
- `providers.json`

到 tenant working dir 和 tenant secret dir。

关键代码：

- `src/swe/cli/init_cmd.py:200`
- `src/swe/agents/utils/setup_utils.py:280`

#### 阶段 4：调用 `TenantInitializer.initialize_full()`

这一步执行共享 bootstrap，并额外尝试创建 QA agent。

关键代码：

- `src/swe/cli/init_cmd.py:222`
- `src/swe/app/workspace/tenant_initializer.py:789`

#### 阶段 5：写 tenant 根 `config.json`

CLI 会继续把 heartbeat/show_tool_details/language/audio_mode/transcription/channels 写入 tenant 根配置。

关键代码：

- `src/swe/cli/init_cmd.py:244`
- `src/swe/cli/init_cmd.py:361`

#### 阶段 6：配置 provider 和 active model

CLI 进入 provider 配置流程，理论上应该把 tenant 的 active model 配好。

关键代码：

- `src/swe/cli/init_cmd.py:364`

#### 阶段 7：下载和启用默认技能

在 `--defaults` 模式下，CLI 会尝试把 skill pool 下载到 default workspace 并启用。

关键代码：

- `src/swe/cli/init_cmd.py:390`

#### 阶段 8：写 tenant 根 `HEARTBEAT.md`

CLI 最后会把租户根目录下的 `HEARTBEAT.md` 写出来。

关键代码：

- `src/swe/cli/init_cmd.py:520`

---

## 8. `swe init` 理论上的最终产物

在共享 bootstrap 产物之外，`swe init` 理论上还应该额外产出：

```text
~/.swe/<tenant>/
├── HEARTBEAT.md
└── workspaces/
    ├── default/
    └── <BUILTIN_QA_AGENT_ID>/

~/.swe.secret/<tenant>/
└── providers/
    ├── builtin/
    ├── custom/
    └── active_model.json
```

此外还应该体现为：

- tenant 根 `config.json` 比 runtime bootstrap 更完整
- default workspace `skills/` 中应有从 pool 下载下来的技能

但这里说的是“理论上应该”。当前实现的真实行为并不完全满足这一点。

---

## 9. 两种初始化方式的最终产物对比

## 9.1 共享产物

两种方式都会产出：

- `~/.swe/<tenant>/config.json`
- `~/.swe/<tenant>/media/`
- `~/.swe/<tenant>/secrets/`
- `~/.swe/<tenant>/skill_pool/`
- `~/.swe/<tenant>/workspaces/default/`
- `~/.swe/<tenant>/workspaces/default/agent.json`
- `~/.swe/<tenant>/workspaces/default/chats.json`
- `~/.swe/<tenant>/workspaces/default/jobs.json`
- `~/.swe/<tenant>/workspaces/default/token_usage.json`
- `~/.swe/<tenant>/workspaces/default/AGENTS.md`
- `~/.swe/<tenant>/workspaces/default/BOOTSTRAP.md`
- `~/.swe/<tenant>/workspaces/default/HEARTBEAT.md`
- `~/.swe/<tenant>/workspaces/default/MEMORY.md`
- `~/.swe/<tenant>/workspaces/default/PROFILE.md`
- `~/.swe/<tenant>/workspaces/default/SOUL.md`
- `~/.swe/<tenant>/workspaces/default/sessions/`
- `~/.swe/<tenant>/workspaces/default/memory/`
- `~/.swe/<tenant>/workspaces/default/skills/`

## 9.2 差异对比表

| 维度 | `swe init` | 接口拦截被动初始化 |
|---|---|---|
| 触发方式 | 用户显式执行命令 | 第一次带 tenant 的请求自动触发 |
| bootstrap 级别 | `initialize_full()` | `ensure_seeded_bootstrap()` |
| default workspace | 有 | 有 |
| tenant 根 `HEARTBEAT.md` | 有 | 没有 |
| QA agent workspace | 理论上有 | 没有 |
| provider 存储 | 理论上会初始化 | 不会，直到首次 provider/model 访问 |
| active model | 理论上会配置 | 不会自动配置 |
| runtime 创建 | 不启动 | bootstrap 时也不启动，之后按需启动 |
| 面向目标 | 初始化完成后尽量可直接用 | 先把 tenant 骨架补齐 |

## 9.3 更准确的现实描述

如果只看“当前代码真实行为”而不是设计意图：

1. 被动初始化更接近“骨架创建器”
2. `swe init` 在骨架之上又额外尝试执行 provider、skills、QA agent、root heartbeat 等配置
3. 但其中至少 provider、skills、QA agent 这三项，当前实现都存在与目标 tenant 不完全一致的行为

---

## 10. 当前实现偏差

这一节是本文最重要的部分。这里不讨论设计意图，只讨论当前代码真实行为与“看起来想做的事”之间的差异。

### 10.1 初始化模板复制当前基本无效

`copy_init_config_files()` 会尝试从：

- `src/swe/agents/md_files/config.json`
- `src/swe/agents/md_files/providers.json`

复制初始化模板。

关键代码：

- `src/swe/agents/utils/setup_utils.py:303`
- `src/swe/agents/utils/setup_utils.py:318`
- `src/swe/agents/utils/setup_utils.py:327`

但当前仓库的 `src/swe/agents/md_files/` 下只有语言 Markdown 和 QA Markdown，没有这两个 JSON 模板。

因此当前真实行为是：

- 这一步只会 warning
- tenant root `config.json` 最终仍然主要来自 `ensure_default_agent_exists()` 创建的空/默认配置，再由 CLI 继续增量写入
- tenant secret 下也不会因为这一步生成 `providers.json`

### 10.2 `swe init` 的 provider 配置没有透传 tenant_id

CLI 在进入 provider 配置时使用的是：

```python
provider_manager = ProviderManager.get_instance()
```

关键代码：

- `src/swe/cli/init_cmd.py:365`

而 `ProviderManager.get_instance()` 在 `tenant_id is None` 时会落到 `"default"`。

关键代码：

- `src/swe/providers/provider_manager.py:702`

CLI provider 交互工具本身是支持 tenant 参数的：

- `src/swe/cli/providers_cmd.py:74`
- `src/swe/cli/providers_cmd.py:361`
- `src/swe/cli/providers_cmd.py:452`

但 `init_cmd` 没有把当前 `tenant_id` 传进去。

这意味着当前真实行为是：

1. 用户执行 `swe init --tenant-id tenant-a`
2. tenant `tenant-a` 的 workspace 和 config 会创建在 `~/.swe/tenant-a/`
3. 但 provider 配置步骤实际会操作 `default` tenant 的 provider 存储
4. 所以真正写出的 provider 产物会更接近：

```text
~/.swe.secret/default/providers/...
```

而不是：

```text
~/.swe.secret/tenant-a/providers/...
```

这是当前 `swe init` 和被动初始化最关键的实现偏差之一。

### 10.3 `swe init --defaults` 下载技能时使用了全局 skill pool service

在 `--defaults` 路径中，CLI 使用：

```python
pool = SkillPoolService()
service = SkillService(default_workspace)
```

关键代码：

- `src/swe/cli/init_cmd.py:398`

而 `SkillPoolService()` 默认会使用全局 `WORKING_DIR/skill_pool`，除非显式传入 `working_dir`。

关键代码：

- `src/swe/agents/skills_manager.py:2170`

这会导致当前真实行为变成：

1. tenant bootstrap 时已经正确创建了 `~/.swe/<tenant>/skill_pool/`
2. 但 CLI 的后续“下载并启用全部技能”操作，很可能改用全局 `~/.swe/skill_pool/`
3. 结果就是 default workspace 未必真的从 tenant skill pool 下载到技能

我在临时目录的实际执行里看到的现象是：

- tenant 级 `skill_pool/` 存在
- 额外生成了根级 `wd/skill_pool/`
- default workspace 的 `skills/` 目录仍为空

因此当前代码中，“CLI 会把所有 pool skills 下载并启用到 tenant default workspace”这个说法并不成立。

### 10.4 QA agent 的成功提示不可靠

`initialize_full()` 内部会记录 QA agent 是否创建成功：

- 成功则 `result["qa_agent"] = True`
- 失败则 `result["qa_agent"] = False`

关键代码：

- `src/swe/app/workspace/tenant_initializer.py:805`

但 `init_cmd` 完全没有检查这个返回值，只是无条件打印：

```python
click.echo("✓ Builtin QA agent workspace ensured")
```

关键代码：

- `src/swe/cli/init_cmd.py:242`

因此当前真实行为可能是：

1. QA agent 实际创建失败
2. CLI 仍然打印成功文案

在本地临时执行中，QA agent 创建就因为导入 backup 路径而缺少 `boto3` 失败，但 CLI 仍然输出了“ensured”。

### 10.5 被动初始化对“脚手架完整性”的定义更严格

`has_seeded_bootstrap()` 判断 tenant 是否完成 bootstrap 时，要求：

- tenant root `config.json`
- default workspace 的 `agent.json`
- `chats.json`
- `jobs.json`
- `token_usage.json`
- `sessions/`
- `memory/`
- 以及除 `BOOTSTRAP.md` 外的 Markdown scaffold
- 同时 skill pool 也必须有状态

关键代码：

- `src/swe/app/workspace/tenant_initializer.py:61`

这意味着被动初始化不是“只建几个空目录”这么简单，而是会自愈到一个比较完整的 default workspace scaffold。

这一点和很多人直觉中的“runtime bootstrap 很轻量”不同，实际它已经相当完整，只是没有走 CLI 专属的交互配置。

---

## 11. 基于实际执行的目录树摘要

本文除了读源码，也在临时目录里实际执行了两条路径做交叉验证。

### 11.1 被动初始化后的目录摘要

在只执行 `TenantWorkspacePool.ensure_bootstrap("tenant-passive")` 之后，目录摘要为：

```text
wd/
├── tenant-passive/
│   ├── config.json
│   ├── media/
│   ├── secrets/
│   ├── skill_pool/
│   └── workspaces/default/
│       ├── agent.json
│       ├── AGENTS.md
│       ├── BOOTSTRAP.md
│       ├── HEARTBEAT.md
│       ├── MEMORY.md
│       ├── PROFILE.md
│       ├── SOUL.md
│       ├── chats.json
│       ├── jobs.json
│       ├── token_usage.json
│       ├── sessions/
│       ├── memory/
│       └── skills/
└── skill_pool/
```

此时没有：

- tenant 根 `HEARTBEAT.md`
- QA agent workspace
- `secret/tenant-passive/providers/`

### 11.2 被动初始化后，再首次触发 provider 存储

如果在 bootstrap 之后继续调用：

- `ProviderManager.ensure_tenant_provider_storage("tenant-passive")`

则会新增：

```text
secret/
└── tenant-passive/
    ├── .provider_init.lock
    └── providers/
        ├── builtin/
        └── custom/
```

### 11.3 `swe init --defaults` 的实际目录摘要

在临时目录实际执行 `swe init --defaults --tenant-id tenant-cli` 后，看到的关键现象是：

```text
wd/
├── .telemetry_collected
├── skill_pool/
├── tenant-cli/
│   ├── HEARTBEAT.md
│   ├── config.json
│   ├── media/
│   ├── secrets/
│   ├── skill_pool/
│   └── workspaces/default/
│       ├── agent.json
│       ├── AGENTS.md
│       ├── BOOTSTRAP.md
│       ├── HEARTBEAT.md
│       ├── MEMORY.md
│       ├── PROFILE.md
│       ├── SOUL.md
│       ├── chats.json
│       ├── jobs.json
│       ├── token_usage.json
│       ├── sessions/
│       ├── memory/
│       ├── skill.json
│       └── skills/
└── ...

secret/
├── default/
│   └── providers/
│       ├── builtin/
│       └── custom/
└── tenant-cli/
```

这个结果恰好反映了前面提到的三个偏差：

1. `tenant-cli` 确实拿到了 tenant-scoped workspace 产物
2. provider 实际写到了 `secret/default/providers/`
3. 根级 `wd/skill_pool/` 被创建出来了

---

## 12. 最终结论

如果把“初始化”定义为“租户第一次能在系统里被正确识别、拥有自己的工作区和默认 agent scaffold”，那么：

- 接口拦截的被动初始化已经足够完成这个目标
- 它做的事情并不只是建空目录，而是会把 tenant 的 default workspace 脚手架补齐到可运行前状态

如果把“初始化”定义为“用户第一次初始化后就尽量可以直接使用完整功能”，那么：

- `swe init` 才是面向这个目标设计的路径
- 它比被动初始化多做了 root heartbeat、provider、skills、QA agent 等后续步骤

但就当前代码真实行为而言，`swe init` 仍然不是一个完全 tenant-correct 的全量初始化器，因为：

1. provider 配置落点仍然偏向 `default` tenant
2. 技能下载使用了全局 skill pool service
3. QA agent 成功提示和实际结果可能不一致
4. 初始化模板 JSON 复制步骤当前没有实际产物

因此，更准确的结论是：

- 被动初始化是“tenant 脚手架正确初始化”
- `swe init` 是“在 tenant 脚手架之上再尝试做用户级配置”
- 但当前 `swe init` 的后半段还有若干跨 tenant 或提示不准确的问题，不能简单视为“被动初始化的严格超集”

---

## 13. 建议的后续修正

如果要让两条路径在语义上真正清晰、在产物上真正 tenant-correct，建议优先修正：

1. `init_cmd` 中所有 provider 相关调用都显式传入 `tenant_id`
2. `init_cmd --defaults` 中 `SkillPoolService` 显式传入 tenant working dir
3. `init_cmd` 按 `init_result["qa_agent"]` 的真实值打印成功或失败信息
4. 修复或移除当前失效的 `copy_init_config_files()` JSON 模板复制逻辑

做到这四点之后，才能把两条路径更稳定地描述为：

- 被动初始化负责“骨架”
- CLI 初始化负责“骨架 + 可用化”
