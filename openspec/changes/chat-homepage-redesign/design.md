## Context

当前聊天首页由 `AgentScopeRuntimeWebUI` 组件驱动，内部结构为：

```
ChatPage (pages/Chat/index.tsx)
  └─ AgentScopeRuntimeWebUI
       ├─ Layout (core/Layout)
       │    ├─ Header (rightHeader: ModelSelector + ChatActionGroup)
       │    ├─ Sessions (hideBuiltInSessionList=true, 由 ChatSessionDrawer 管理)
       │    └─ Chat (core/Chat)
       │         ├─ MessageList (消息列表)
       │         └─ Input (底部输入区)
       │              ├─ Welcome (欢迎页, 无消息时显示)
       │              │    └─ WelcomePrompts (greeting + prompts 列表)
       │              └─ Sender (输入框 + 附件 + 发送)
       └─ ComposedProvider (多个 Context)
```

关键约束：
- `Welcome` 组件仅在无消息时渲染（欢迎态），有消息后切换为 `MessageList + Sender`
- 侧栏会话列表由 `ChatSessionDrawer` 独立管理，不在 `AgentScopeRuntimeWebUI` 内部
- 所有配置通过 `IAgentScopeRuntimeWebUIOptions` 传入，支持 `welcome.render` 自定义渲染

## Goals / Non-Goals

**Goals:**
- 欢迎态布局重构：输入框居中 + 欢迎语 + 知识库 Tab + 精选案例卡片
- 新增精选案例卡片组件（含悬浮交互：看案例/做同款）
- 新增侧栏任务列表（对接现有 cronjob API，点击触发定时任务）
- 新增侧栏底部工具栏（skill 市场 / 操作指南）
- 新建聊天按钮样式改为蓝色胶囊

**Non-Goals:**
- 不修改顶部导航栏
- 不修改消息列表（MessageList）和消息气泡（Bubble）的展示
- 不实现知识库 Tab 的实际切换逻辑（仅 UI 占位）
- 不实现「看案例」的详情展示内容（仅展开交互占位）
- 不修改 Sender 输入框的发送逻辑和 API 调用

## Decisions

### 1. 欢迎页渲染策略：使用 `welcome.render` 自定义渲染

**决策**: 通过 `IAgentScopeRuntimeWebUIOptions.welcome.render` 提供自定义渲染函数，替代默认的 `WelcomePrompts` 组件。

**原因**:
- 现有架构支持 `render` 回调，无需修改 `AgentScopeRuntimeWebUI` 内部逻辑
- 新布局结构（输入框居中 + 精选案例）与默认 WelcomePrompts 差异过大，直接修改默认组件不现实
- 保持 `welcome` 选项的 `onSubmit`、`greeting`、`prompts` 等接口不变，仅替换渲染层

**替代方案**: 直接修改 `WelcomePrompts` 组件 → 会导致默认样式和新样式耦合，且影响其他使用 WelcomePrompts 的地方。

### 2. 输入框位置策略：在 Welcome 自定义渲染中嵌入 Sender

**决策**: 在 `welcome.render` 的自定义渲染函数中，嵌入一个独立的 `Sender` 组件实例，替代默认底部 Sender。

**原因**:
- 设计稿要求输入框在欢迎页中央，而不是页面底部
- 当用户发送消息后，Welcome 消失，MessageList + 底部 Sender 恢复正常布局
- 需要将 `Sender` 的 `onSubmit` 与 Chat 的 `handleSubmit` 连接

**实现方式**:
- 通过 `ChatAnywhereInputContext` 获取 `onSubmit` 和 `loading` 状态
- 使用 Event Emitter (`handleSubmit` 事件) 触发提交，无需直接持有 controller 引用
- 输入框值通过本地 state 管理，发送时通过 event 触发

### 3. 精选案例卡片：新建独立组件 `FeaturedCases`

**决策**: 新建 `components/agentscope-chat/FeaturedCases/` 组件，不修改现有 WelcomePrompts。

**原因**:
- 卡片布局（横向滚动、图片缩略图、悬浮遮罩）与现有文字列表 prompt 完全不同
- 独立组件便于后续扩展（数据源可从 API 获取或配置注入）
- 与 WelcomePrompts 解耦，互不影响

**数据来源**: 初期从 `welcome.prompts` 配置中读取（复用现有 prompts 数据结构），后续可切换为 API 获取。

### 4. 侧栏任务列表：新建独立组件，对接 cronjob API

**决策**: 新建 `pages/Chat/components/ChatTaskList/` 组件，嵌入现有 `ChatSessionDrawer` 侧栏。

**原因**:
- 侧栏由 `ChatSessionDrawer` 管理（非 `AgentScopeRuntimeWebUI` 的 Sessions）
- 任务列表数据来自 cronjob API，与聊天会话列表数据源不同
- 保持侧栏的扩展性，任务列表和会话列表可独立更新

**API 对接**:
- `cronjobApi.listCronJobs()` — 获取任务列表
- `cronjobApi.triggerCronJob(id)` — 触发任务执行
- 红点 badge 来自任务的 `unread_count` 或类似字段

### 5. 样式方案：CSS Modules + antd-style 混用

**决策**: 新组件使用 `antd-style`（与项目现有模式一致），不引入新样式方案。

**设计 Token**:
```
--color-primary: #3769FC
--color-tag-purple: #8482E7
--color-badge-red: #FE2842
--color-bg-page: #F1F2F7
--color-text-primary: #11142D
--color-text-secondary: #4F5060 / #808191
--radius-card: 12px
--radius-tab: 20px
--radius-button-pill: 100px
```

## Risks / Trade-offs

- [风险] Welcome 自定义渲染中嵌入 Sender 可能导致双实例冲突 → 缓解：隐藏默认 Sender，只在 Welcome 中显示
- [风险] 精选案例数据初期依赖 prompts 配置，格式可能不匹配卡片所需字段 → 缓解：扩展 prompts 类型，支持 `icon`/`image` 字段
- [风险] 侧栏任务列表的 API 字段可能与设计稿不完全匹配 → 缓解：先适配现有字段，缺失字段用 placeholder
- [取舍] 知识库 Tab 暂无功能，仅为 UI 占位，后续需要接入实际逻辑
