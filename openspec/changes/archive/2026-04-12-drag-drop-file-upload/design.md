## Context

聊天页面已有完整的文件上传流程（`handleFileUpload` → `chatApi.uploadFile`），通过点击附件按钮触发。`Attachments/DropArea.tsx` 组件已实现全局拖拽覆盖层机制（监听 dragenter/dragover/dragleave/drop 事件，用 portal 渲染覆盖层）。欢迎页的附件按钮目前没有连接任何上传逻辑。

## Goals / Non-Goals

**Goals:**
- 在聊天消息区域（包括欢迎页和活跃聊天页）添加拖拽文件上传支持
- 拖入文件时显示上传提示卡片，按 Pixso 设计稿还原（800x329，圆角12，浅蓝背景 #F1F6FF，上传图标 + 提示文字 + 格式说明 + 关闭按钮）
- 拖拽释放后调走现有的 `handleFileUpload` 流程
- 欢迎页附件按钮可点击触发文件选择

**Non-Goals:**
- 不修改后端上传 API
- 不修改活跃聊天页已有的附件按钮行为（保持点击上传功能不变）

## Decisions

1. **在 Chat/index.tsx 层实现拖拽监听**：在消息区域容器上监听 dragenter/drop 事件，因为这里能访问到 `chatRef` 和 `handleFileUpload`
2. **拖拽提示卡片作为独立组件**：创建 `DragUploadOverlay` 组件，仅在拖拽状态激活时渲染，使用 React Portal 挂载到聊天区域
3. **复用 handleFileUpload**：拖拽释放和欢迎页附件按钮都复用 Chat 页面已有的上传逻辑
4. **使用 HTML5 原生拖拽 API**：dragenter/dragover/dragleave/drop 事件，不引入额外依赖

## Risks / Trade-offs

- 拖拽事件冒泡可能影响输入框内的拖拽行为（如文本选择拖放），需要通过文件类型判断过滤
- 大文件拖拽的性能影响较小，因为只是传递 File 引用，不读取内容
