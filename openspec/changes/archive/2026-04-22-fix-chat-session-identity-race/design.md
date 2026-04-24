## Context

Chat 运行时当前同时维护 UI 会话 ID、临时会话 ID、后端 `chat.id`、逻辑 `session_id` 和单例流式请求状态。后端单次请求内部会固定使用 `request.session_id` 执行、持久化和回放历史，因此“会话漂移”主要不是后端内部问题，而是前端在会话解析、URL 同步、follow-up 自动提交、reconnect 和 SSE 消费时混用了不同身份字段。

本次变更跨越 Chat 页面、session API、流式请求控制和 follow-up 自动中断流程，属于前端运行时的一致性修复。它需要在不重构后端存储模型的前提下，重新定义 `chat.id` 与 `session_id` 的职责边界，并为每次流式请求引入稳定的归属校验。

## Goals / Non-Goals

**Goals:**
- 保证逻辑 `session_id` 在同一会话生命周期内稳定，不被 `chat.id` 覆盖
- 保证首轮回复完成后的 follow-up 继续复用原有逻辑会话
- 保证 submit / reconnect 产生的流式更新只能落到其所属会话
- 保证完成态同步、stop、reconnect、polling 和 URL 导航使用正确的身份字段

**Non-Goals:**
- 不修改后端 `ChatSpec` / session state 的存储结构
- 不重做整套 Chat UI 组件或消息卡片渲染模型
- 不在本次范围内处理与会话身份无关的样式、文案或历史分组问题

## Observed Failure Chain

当前代码里已经可以串出一条完整的故障链：

1. 新建会话时，前端用临时时间戳作为 UI 会话 ID，同时也把它作为首轮请求的逻辑 `session_id`
2. 后端按该 `session_id` 加载和保存 session state，因此首轮 memory 被持久化在这个临时逻辑 ID 下
3. 首轮结束后，前端在 pending session 解析流程里把 `window.currentSessionId` 写成后端 `chat.id`，破坏了“后续请求继续使用逻辑 `session_id`”这一前提
4. 第二轮继续追问时，请求体从 `window.currentSessionId` 取值，于是把 `chat.id` 发给 `/console/chat`
5. 后端收到新的 `request.session_id` 后，会按这个新键加载 session state，自然读不到首轮 memory，于是表现成“只看本轮输入”
6. 同一时期，`onSessionIdResolved` 的调用约定是 `(tempId, realId)`，但页面侧把第一个参数当成真实 ID 使用，导致 URL 可能停留在临时 ID
7. 页面刷新后，内存中的临时 ID → `chat.id` 映射消失；前端再按 URL 中的临时 ID 取会话时，只能回退到纯本地空会话分支，于是已存在的回复看起来像进入了“新建会话”

这说明当前问题不是单点缺陷，而是“身份字段漂移 + URL 回填错误 + 刷新后缺少兜底映射”共同造成的。

## Decisions

### 1. 区分 `chat.id` 与逻辑 `session_id`

前端需要明确两类身份：

- 逻辑 `session_id`
  - 决定是否续聊
  - 作为 `/console/chat` 请求中的上下文身份
  - 对应后端 memory / session state
- `chat.id`
  - 仅用于 URL、chat detail 查询、stop、reconnect attach、status 与 polling

之所以采用这一区分，是因为后端 `ChatManager` 按 `session_id` 复用/新建 chat；只要前端把 `chat.id` 回写成下一轮请求的 `session_id`，后端就会把续聊误判为新会话。

备选方案是继续使用单一 `window.currentSessionId` 同时表示两者，但这会延续当前混乱语义，不足以避免竞态。

### 2. 为每个前端会话维护显式映射

前端会话运行时应显式维护：

- `uiSessionId -> logical session_id`
- `uiSessionId -> chat.id`

而不是依赖单个全局变量在不同阶段保存不同含义。首轮请求完成后，可以补齐 `chat.id` 映射和 URL，但不得回写或替换逻辑 `session_id`。

之所以使用映射，是为了兼容“新建会话先有临时 UI ID，后有真实 `chat.id`”这一流程，同时保持后续追问的会话身份稳定。

这里还需要补充一个刷新约束：

- 刷新后如果 URL 已经是 `chat.id`，前端应通过 chat detail/list 恢复 `chat.id -> logical session_id`
- 刷新后如果 URL 仍是临时 UI ID，前端不得把它静默恢复为一个新的空逻辑会话；应优先尝试基于持久化列表或待解析映射恢复真实 `chat.id`，恢复失败时再明确退回空态

这样才能避免“URL 保留临时 ID，刷新后掉进本地空会话”的现象。

### 3. 为 submit / reconnect 引入 request 级归属校验

每次 submit 或 reconnect 都应生成独立 request token，并绑定：

- 所属 UI 会话
- 所属逻辑 `session_id`
- 关联 `chat.id`
- 响应目标

SSE chunk、完成事件和取消事件到达时，前端必须先校验该事件是否仍属于当前活动请求；不属于时直接丢弃，不更新全局消息数组，也不触发完成态同步。

之所以采用 request token，而不是仅在切会话时调用 `abort()`，是因为旧 SSE 尾包可能在 `abort()` 之后仍到达；只有在消费阶段再做归属校验，才能阻止尾包串到新会话。

### 4. 完成态同步绑定到请求发起时的会话

`finishResponse()` 与 `syncSessionMessages()` 不能再依赖运行时“当前选中会话”，必须使用请求创建时记录的会话身份写回。这样即使用户在响应未完全收尾时切换会话，也不会把旧请求的消息写入新会话。

备选方案是将消息状态完全改为按 session 分片存储。这会更彻底，但改动面较大，不适合作为本次 bugfix 的最小实现路径。

### 5. 修正 URL 同步回调签名与使用方式

`onSessionIdResolved` 需要统一为明确的 `(tempId, realId)` 语义，调用方必须按该签名消费。URL 只应反映 `chat.id`，不得反向影响逻辑 `session_id`。这样可以避免页面导航和后续请求身份互相污染。

这里的具体修复目标包括：

- 禁止在 pending session 解析后把 `window.currentSessionId` 改写为 `chat.id`
- 明确 `window.currentSessionId` 若继续保留，只能表示逻辑 `session_id`
- URL 回填仅使用 `realId`
- 初始 session 选择和刷新恢复逻辑不得把“不存在于 sessionList 的临时 URL ID”直接当成可继续请求的真实会话

## Risks / Trade-offs

- [风险] 前端仍存在历史逻辑依赖 `window.currentSessionId` 的隐式约定 → [缓解] 逐一梳理发送、重连、停止、轮询路径，统一改为显式读取映射
- [风险] request guard 引入后，某些原本可见的尾包会被丢弃，造成“回复突然结束”的感知变化 → [缓解] 仅丢弃已失去归属的旧请求事件，保持当前请求正常展示
- [风险] 只修复身份与请求归属，不重构全局消息存储，后续仍可能存在其他共享状态问题 → [缓解] 将本次设计限定为一致性修复，并在验证阶段覆盖切换、刷新、重连等关键路径
