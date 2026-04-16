## Why

父应用通过 iframe 嵌入 CoPaw 时，URL 可包含 `sessionId` 或 `taskId` 参数，期望子应用能自动跳转到对应的聊天会话或任务关联的聊天页面。当前 iframe 参数处理仅支持 `origin=Y` + Cookie 用户信息初始化，不支持会话/任务导航参数，导致用户需要手动查找目标会话。

## What Changes

- 扩展 iframe URL 参数处理，新增 `sessionId` 和 `taskId` 参数读取
- `sessionId` 参数：直接导航到 `/chat/:sessionId`
- `taskId` 参数：查询任务关联的 `chat_id` 后导航到 `/chat/:chatId`
- iframeStore 新增 `sessionId` 和 `taskId` 状态字段及清除方法
- Chat 页面首次加载时检查 iframeStore 并执行导航

## Capabilities

### New Capabilities
- `iframe-url-session-navigation`: iframe URL 参数驱动的会话/任务导航能力

### Modified Capabilities
- `iframe-context`: 扩展 iframeStore 状态，新增 `sessionId`、`taskId` 字段

## Impact

- **前端组件**:
  - `stores/iframeStore.ts` — 新增 sessionId/taskId 状态字段
  - `types/iframe.ts` — 新增类型定义
  - `utils/iframeMessage.ts` — 扩展 handleUrlOriginParam() 读取新参数
  - `pages/Chat/index.tsx` — 新增导航 effect
- **API 调用**:
  - taskId 导航需要任务列表加载完成后查询 chat_id（复用现有 cronjob API）
- **无后端改动**: 本次仅前端参数处理与导航逻辑变更