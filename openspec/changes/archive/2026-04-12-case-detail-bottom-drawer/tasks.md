## 1. 创建 CaseDetailDrawer 组件

- [x] 1.1 创建 `console/src/components/agentscope-chat/CaseDetailDrawer/index.tsx`：底部弹窗组件，使用 Ant Design Drawer（placement="bottom"），接收 `visible`、`onClose`、`caseData`、`onMakeSimilar` props
- [x] 1.2 创建 `console/src/components/agentscope-chat/CaseDetailDrawer/style.ts`：弹窗样式（标题栏 48px、左右分栏、底部操作栏 60px），按 Pixso 设计稿还原

## 2. 弹窗内容实现

- [x] 2.1 实现标题栏：左侧"案例详情"文字（16px #333），右侧关闭图标（#999），底部分割线（#ddd）
- [x] 2.2 实现左侧数据表格面板：白色背景、圆角 8px、padding 20px/16px，包含标题行和表格内容（按设计稿硬编码示例数据）
- [x] 2.3 实现右侧步骤说明面板：白色背景、圆角 8px、padding 20px/16px，分步骤展示说明文字
- [x] 2.4 实现底部操作栏：「订阅为定时任务」（白底蓝字胶囊，圆角 24px）和「做同款」（蓝底白字胶囊）按钮

## 3. 集成到聊天页面

- [x] 3.1 在 `Chat/index.tsx` 中添加弹窗状态管理（visible、selectedCase），引入 CaseDetailDrawer 组件
- [x] 3.2 修改 FeaturedCases 组件：添加 `onViewCase` 回调 prop，点击「看案例」按钮时触发
- [x] 3.3 实现「做同款」回调：关闭弹窗后通过 `chatRef.current.input.submit` 或直接设置输入框内容
