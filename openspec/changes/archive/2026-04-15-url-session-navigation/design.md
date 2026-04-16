## Overview

父应用通过 URL 参数向 iframe 子应用传递导航目标，子应用在初始化时自动跳转到对应的聊天会话。

## URL 参数

| 参数名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `origin` | string | 固定值 `Y`，标识从父应用嵌入 | `origin=Y` |
| `sessionId` | string | 聊天会话 ID（ChatSpec.id），直接导航 | `sessionId=abc-123` |
| `taskId` | string | 任务 ID（CronJobSpecOutput.id），需查询 chat_id | `taskId=task-456` |

**参数优先级**：`sessionId` > `taskId`（同时存在时优先处理 sessionId）

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    sessionId 导航流程                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  URL: ?origin=Y&sessionId=xxx                                   │
│                                                                 │
│  main.tsx                                                       │
│  └─ initIframeMessageListener()                                 │
│     └─ handleUrlOriginParam()                                   │
│        └─ iframeStore.setContext({                              │
│             sessionId: "xxx",                                   │
│             taskId: null                                        │
│           })                                                    │
│                                                                 │
│  React 渲染                                                      │
│  └─ Chat/index.tsx                                              │
│     └─ useEffect(() => {                                        │
│          const { sessionId } = iframeStore.getState()           │
│          if (sessionId) {                                       │
│            navigate(`/chat/${sessionId}`, { replace: true })   │
│            iframeStore.clearNavigationParams()                  │
│          }                                                      │
│        }, [])                                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    taskId 导航流程                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  URL: ?origin=Y&taskId=yyy                                      │
│                                                                 │
│  main.tsx                                                       │
│  └─ iframeStore.setContext({ sessionId: null, taskId: "yyy" })  │
│                                                                 │
│  Chat/index.tsx                                                 │
│  └─ useEffect(() => {                                           │
│       const { taskId } = iframeStore.getState()                 │
│       if (taskId && jobs.length > 0) {                          │
│         const task = jobs.find(j => j.id === taskId)            │
│         const chatId = task?.task?.chat_id                      │
│         if (chatId) {                                           │
│           navigate(`/chat/${chatId}`, { replace: true })        │
│           iframeStore.clearNavigationParams()                   │
│         } else {                                                │
│           console.warn("taskId not found or no chat_id")        │
│         }                                                       │
│       }                                                         │
│     }, [jobs])                                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. iframeStore 扩展

```typescript
// stores/iframeStore.ts
interface IframeStore extends IframeContext {
  sessionId: string | null;
  taskId: string | null;

  setNavigationParams: (sessionId: string | null, taskId: string | null) => void;
  clearNavigationParams: () => void;
}
```

### 2. iframeMessage.ts 扩展

```typescript
// utils/iframeMessage.ts - handleUrlOriginParam()
const sessionId = urlParams.get("sessionId");
const taskId = urlParams.get("taskId");

if (sessionId || taskId) {
  store.setNavigationParams(sessionId, taskId);
}
```

### 3. Chat/index.tsx 导航 Effect

```typescript
// pages/Chat/index.tsx
useEffect(() => {
  const { sessionId, taskId } = useIframeStore.getState();

  // sessionId 直接导航
  if (sessionId) {
    navigate(`/chat/${sessionId}`, { replace: true });
    useIframeStore.getState().clearNavigationParams();
    return;
  }

  // taskId 需等待任务列表
  if (taskId && jobs.length > 0) {
    const task = jobs.find(j => j.id === taskId);
    if (task?.task?.chat_id) {
      navigate(`/chat/${task.task.chat_id}`, { replace: true });
      useIframeStore.getState().clearNavigationParams();
    }
  }
}, [jobs, navigate]);
```

## Edge Cases

| 场景 | 处理方式 |
|------|----------|
| sessionId 和 taskId 同时存在 | 优先 sessionId，忽略 taskId |
| taskId 不存在于任务列表 | console.warn，不导航 |
| taskId 存在但 task.chat_id 为空 | console.warn，不导航 |
| 无 sessionId/taskId | 不执行任何导航 |

## Files Modified

| 文件 | 变更 |
|------|------|
| `types/iframe.ts` | 新增 `sessionId`, `taskId` 字段 |
| `stores/iframeStore.ts` | 新增状态字段 + setNavigationParams/clearNavigationParams 方法 |
| `utils/iframeMessage.ts` | handleUrlOriginParam() 读取 sessionId/taskId 参数 |
| `pages/Chat/index.tsx` | 新增导航 useEffect |