## 1. 创建拖拽上传覆盖层组件

- [x] 1.1 创建 `console/src/components/agentscope-chat/DragUploadOverlay/index.tsx`：拖拽提示卡片组件，按设计稿实现（800x329，圆角12，浅蓝背景，上传图标+文字+关闭按钮）
- [x] 1.2 创建 `console/src/components/agentscope-chat/DragUploadOverlay/style.ts`：覆盖层样式

## 2. Chat 页面集成拖拽监听

- [x] 2.1 在 `Chat/index.tsx` 添加拖拽状态管理（isDragging），在消息区域容器上监听 dragenter/dragover/dragleave/drop 事件
- [x] 2.2 拖入时渲染 DragUploadOverlay，释放时调用 handleFileUpload 上传文件
- [x] 2.3 处理拖拽事件过滤：仅对包含文件的拖拽显示覆盖层，忽略文本拖拽等

## 3. 欢迎页附件按钮连接上传

- [x] 3.1 修改 `WelcomeCenterLayout/index.tsx`：附件按钮点击触发文件选择，通过新增 prop `onFileUpload` 将文件传递给父组件
- [x] 3.2 在 `Chat/index.tsx` 中为 WelcomeCenterLayout 传入 `onFileUpload` 回调，复用 handleFileUpload
