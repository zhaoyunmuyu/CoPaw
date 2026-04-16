## Tasks

### 1. 扩展 iframeStore 状态
- **File**: `console/src/stores/iframeStore.ts`
- **Changes**:
  - 新增 `sessionId: string | null` 状态字段
  - 新增 `taskId: string | null` 状态字段
  - 新增 `setNavigationParams(sessionId, taskId)` 方法
  - 新增 `clearNavigationParams()` 方法
  - 更新 `initialState` 和 `partialize` 配置

### 2. 扩展 iframe 类型定义
- **File**: `console/src/types/iframe.ts`
- **Changes**:
  - `IframeContext` 接口新增 `sessionId` 和 `taskId` 字段

### 3. 扩展 URL 参数处理
- **File**: `console/src/utils/iframeMessage.ts`
- **Changes**:
  - `handleUrlOriginParam()` 函数内读取 `sessionId` 和 `taskId` URL 参数
  - 调用 `store.setNavigationParams(sessionId, taskId)` 存储参数

### 4. Chat 页面导航逻辑
- **File**: `console/src/pages/Chat/index.tsx`
- **Changes**:
  - 新增 useEffect 监听 iframeStore 的 sessionId/taskId
  - sessionId 存在时直接 navigate(`/chat/${sessionId}`)
  - taskId 存在时等待 jobs 加载，查找 task.chat_id 后导航
  - 导航后调用 `clearNavigationParams()` 防止重复

### 5. 测试验证
- 手动测试 URL 参数：
  - `?origin=Y&sessionId=xxx` → 导航到 `/chat/xxx`
  - `?origin=Y&taskId=yyy` → 导航到任务的 chat_id
  - 同时传递时优先 sessionId