## Why

Chat 当前在前端运行时混用了临时会话 ID、`chat.id`、逻辑 `session_id` 和全局请求状态，导致续聊、刷新恢复和会话切换存在竞态。该问题已经影响核心聊天连续性，表现为：

- 新建会话首轮请求后，前端将后端 `chat.id` 误写回后续请求使用的 `session_id`，导致下一轮续聊读取不到已有 memory，只按当次输入回复
- `onSessionIdResolved` 回调调用方错误消费参数，URL 可能停留在临时时间戳 ID，而不是后端真实 `chat.id`
- 页面刷新后，由于内存中的临时 ID → `chat.id` 映射已丢失，前端会把 URL 中的临时 ID 视为纯本地新会话，从而让已存在的回复看起来落入“新建会话”
- 旧 SSE 尾包出现在错误会话，以及完成态消息同步污染其他会话

因此需要尽快收敛为稳定的一致性模型。

## What Changes

- 明确区分 `chat.id` 与逻辑 `session_id` 的职责，禁止将 `chat.id` 回写为后续请求的 `session_id`
- 为 Chat 前端会话运行时增加稳定的会话映射，保证新建会话首轮完成后继续追问仍复用同一逻辑会话
- 修正新建会话首轮完成后的 URL 回填与刷新恢复逻辑，避免临时 ID 被当作真实会话恢复
- 为 submit / reconnect 请求增加 request 级隔离，防止旧 SSE 尾包更新当前会话视图
- 将完成态消息同步绑定到请求所属会话，而不是运行时“当前选中会话”
- 收敛 URL、session 选择态、reconnect、stop 和 polling 对会话标识的使用方式

## Capabilities

### New Capabilities
- `chat-session-identity-coordination`: 定义 Chat 前端在新建、续聊、切换、重连和流式更新时的会话身份约束与请求隔离规则

### Modified Capabilities
- `chat-followup-auto-interrupt`: 自动中断后续聊的行为需要补充“续聊不得切换到新的逻辑会话”和“自动提交必须绑定原会话”的要求

## Impact

- 前端 Chat 运行时与会话状态管理
- `/console/chat` 请求体中的 `session_id` 生成与复用逻辑
- Chat 页面 URL 同步、session list 选择、刷新恢复、auto reconnect、stop 与 suggestions/polling 相关流程
- 与 `chat.id` / `session_id` 映射相关的测试与调试路径
