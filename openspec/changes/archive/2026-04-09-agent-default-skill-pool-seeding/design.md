## Context

当前 `POST /api/agents` 的请求模型里，`skill_names` 默认为 `None`。但路由在调用 `_initialize_agent_workspace()` 时，会把 `None` 直接归一成 `[]`，因此新建 agent 默认不会复制任何技能池内容。

这和当前系统的租户模型不一致：tenant bootstrap 已经把可用技能准备到租户本地 `skill_pool` 中，用户也会自然预期“新建 agent”默认继承这套可用技能，而不是再做一次手工选择。

现有工作区初始化辅助函数已经支持两类明确语义：
- `skill_names=[...]` 时复制指定技能
- `skill_names=None` 时跳过技能复制

这意味着本次变更的关键不在底层复制逻辑，而在 agent 创建路由如何把“未显式指定技能”解析成正确的默认值。

## Goals / Non-Goals

**Goals:**
- 让新建 agent 在未显式指定 `skill_names` 时，默认导入当前租户技能池中的全部技能。
- 保持显式 `skill_names` 的现有行为不变，包括显式子集和显式空列表。
- 继续通过 tenant-scoped skill pool 解析技能名，避免跨租户读取。
- 为默认值语义补足可回归测试。

**Non-Goals:**
- 不修改 QA agent 的初始化策略；QA agent 仍使用显式内置技能列表。
- 不改变租户 bootstrap、默认工作区 seeding 或 skill pool 管理 API 的行为。
- 不引入“自动同步”机制；本次仅影响 agent 创建时的一次性初始复制。

## Decisions

### Decision: 在 `create_agent` 路由层解析默认技能列表

当请求的 `skill_names is None` 时，路由从当前租户的 `skill_pool` manifest 读取全部技能名，并把结果传给 `_initialize_agent_workspace()`；当请求显式提供列表时，直接透传该列表。

Why:
- `_initialize_agent_workspace()` 已经承担“按给定名字复制技能”的职责，不需要再引入新的隐式默认分支。
- 只在 agent 创建入口修改默认值，能够避免影响 QA agent、迁移逻辑或其他可能直接调用初始化辅助函数的路径。
- 路由层已经掌握 tenant working dir，上下文最完整。

Alternatives considered:
- 修改 `_initialize_agent_workspace()`，让 `skill_names=None` 代表“复制全部技能”：拒绝，因为这会改变现有辅助函数语义，并可能影响其他调用方。
- 在请求模型里直接把默认值改成空列表或特殊标记：拒绝，因为 `None` 已经足够表达“调用方未指定”，无需额外协议。

### Decision: 默认全量技能名来自 tenant-scoped pool manifest

默认技能列表将通过 `read_skill_pool_manifest(working_dir=tenant_dir)` 读取，并以 manifest 中的技能名作为复制集合。

Why:
- manifest 已经是 skill pool 的标准元数据入口，能够避免直接扫描目录造成的脏状态或无效目录问题。
- 该路径已经支持 tenant `working_dir`，可复用现有租户隔离约束。
- reconcile 后的 manifest 能保证“默认全量导入”的来源与其他 pool 读路径一致。

Alternatives considered:
- 直接遍历 `skill_pool/*` 目录：拒绝，因为会绕过 manifest 的一致性与过滤规则。
- 从 builtin skills 列表推导默认集合：拒绝，因为租户技能池可能包含自定义技能，且未必需要导入所有 builtin。

### Decision: 显式空列表继续表示“创建无技能 agent”

如果调用方传入 `skill_names=[]`，系统仍然创建空技能工作区，不回退到默认全量导入。

Why:
- 空列表是一个明确的用户选择，与“未提供字段”语义不同。
- 这保留了前端或 API 调用方在需要极简 agent 时的控制能力。

Alternatives considered:
- 将空列表也视为默认全量导入：拒绝，因为会让调用方失去“明确不要技能”的表达方式，并破坏向后兼容。

## Risks / Trade-offs

- [技能池 manifest 缺失或为空时默认导入结果为空] → 这是可接受退化；agent 仍可成功创建，行为与“当前无可用技能”一致。
- [未来其他调用方错误复用路由语义假设] → 把默认解析明确限定在 `create_agent` 路由，并通过测试锁定 `_initialize_agent_workspace()` 的既有输入语义。
- [默认全量导入让新 agent 初始技能更多] → 这是本次需求目标；调用方仍可通过显式列表或空列表覆盖默认值。

## Migration Plan

1. 在 `create_agent` 中读取当前租户 skill pool manifest。
2. 当 `request.skill_names is None` 时，用 manifest 技能名作为初始化输入。
3. 保持显式 `request.skill_names` 原样透传。
4. 增加测试覆盖默认全量导入、显式子集导入、显式空列表三种场景。

回滚很直接：恢复路由把 `None` 归一成 `[]` 的旧逻辑即可。该变更不会引入新的持久化结构，只会改变新 agent 首次创建时的初始技能内容。

## Open Questions

- 无。当前需求边界明确，设计上也不需要新增协议字段或迁移步骤。
