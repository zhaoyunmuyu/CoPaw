## Why

新建 agent 的当前默认行为会传入空的 `skill_names`，导致工作区初始化时不复制任何技能池内容。这样每次创建 agent 后都需要手动再选择或同步技能，和租户已经准备好的技能池基线不一致，也让“新 agent 可立即使用”这个预期落空。

## What Changes

- 调整新建 agent 的默认语义：当调用方未显式提供 `skill_names` 时，后端默认将当前租户技能池中的全部技能复制到新 agent 的工作区 `skills/` 中。
- 保留显式 `skill_names` 的优先级：如果请求提供了技能列表，仍然只导入请求指定的技能。
- 保留空列表的显式语义：如果调用方明确传入 `[]`，系统应创建不带任何技能的新 agent，而不是回退到“全量导入”。
- 为 agent 创建与工作区初始化增加回归测试，覆盖默认全量导入、显式子集导入、显式空列表不导入三类场景。

## Capabilities

### New Capabilities

### Modified Capabilities
- `tenant-skill-template-initialization`: agent 工作区初始化在未显式指定 `skill_names` 时，默认从当前租户 `skill_pool` 导入全部技能，并继续保持显式传参的覆盖语义。

## Impact

- Affected code:
  - `src/swe/app/routers/agents.py`
  - 可能涉及 `src/swe/agents/skills_manager.py` 中用于枚举池技能的辅助逻辑
- Affected behavior:
  - `POST /api/agents` 未传 `skill_names` 时的默认初始化结果
  - 新 agent 工作区 `skills/` 目录和工作区技能 manifest 的初始状态
- Unchanged behavior:
  - 租户技能池来源仍然是当前租户本地 `skill_pool`
  - 显式指定 `skill_names` 的 agent 创建流程
  - 其他租户初始化与 skill pool 管理接口
- Testing impact:
  - agent 创建路由默认值语义测试
  - 工作区初始化技能复制语义测试
