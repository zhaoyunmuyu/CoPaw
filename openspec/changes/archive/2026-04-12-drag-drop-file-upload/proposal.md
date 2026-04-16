## Why

当前聊天首页的输入区域和欢迎页输入框没有拖拽上传功能，用户只能通过点击上传按钮选择文件。需要支持拖拽文件到聊天区域实现上传，提升交互体验。

## What Changes

- 在聊天消息区域添加全局拖拽监听，拖入文件时显示设计稿中的上传提示卡片（800px 宽、浅蓝背景、圆角 12、上传图标 + "点击或拖放文件到该区域" + 格式说明 + 关闭按钮）
- 拖拽释放后触发现有的 `handleFileUpload` 上传流程
- 欢迎页输入框的附件按钮（`SparkAttachmentLine`）也需要连接到上传逻辑
- 复用已有的 `Attachments/DropArea.tsx` 拖拽覆盖层机制

## Capabilities

### New Capabilities
- `chat-drag-drop-upload`: 聊天区域全局拖拽文件上传，包含拖入时的 UI 提示卡片和释放后的文件处理

### Modified Capabilities

## Impact

- 修改 `console/src/pages/Chat/index.tsx` — 添加拖拽监听和上传提示 UI
- 修改 `console/src/components/agentscope-chat/WelcomeCenterLayout/index.tsx` — 附件按钮连接上传逻辑
- 复用 `console/src/components/agentscope-chat/Attachments/DropArea.tsx`
