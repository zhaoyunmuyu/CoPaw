## Why

当前聊天首页使用通用的 WelcomePrompts 组件，呈现为简单的文字列表样式，无法承载精选案例展示、知识库切换、任务管理等业务场景。需要根据 Pixso 设计稿对聊天首页进行全面 UI 改版，使其符合产品定位（"专属小龙虾助手"），同时新增侧栏任务列表、精选案例卡片等交互模块。

## What Changes

- 重构欢迎区域布局：欢迎语样式调整（字号 16→22），居中展示
- 输入框从底部移至页面中央，改为白底圆角 12 的卡片式设计（800px 宽），含描述占位文字、附件按钮、发送按钮
- 新增知识库 Tab 切换组件：胶囊标签样式（圆角 20，紫色 #8482E7），"原保险经验库" / "分行经验库"，仅 UI 占位，保留后续功能接入
- 重构提示词区域为精选案例卡片：5 个横向滚动卡片（176x168px），白底圆角，含图片缩略图 + 文字描述
- 新增案例卡悬浮交互层：半透明黑色遮罩 + 「看案例」（展开详情）+ 「做同款」（将内容填入输入框）
- 新增侧栏「我的任务」列表：显示定时任务标题、更新摘要、红点 badge；点击直接触发已有定时任务
- 侧栏「历史记录」样式改版：加分组标题、时间戳格式化显示
- 「新建聊天」按钮改为蓝色胶囊样式（圆角 100）
- 新增侧栏底部工具栏：「skill 市场」/「操作指南」入口

## Capabilities

### New Capabilities
- `featured-case-cards`: 精选案例卡片展示与交互，包括横向滚动卡片列表、悬浮遮罩层（看案例/做同款）
- `knowledge-base-tabs`: 知识库 Tab 切换组件，胶囊标签 UI 占位
- `sidebar-task-list`: 侧栏任务列表，展示定时任务并支持点击触发执行
- `chat-welcome-layout`: 聊天首页欢迎区域整体布局重构（输入框居中、欢迎语、整体排版）

### Modified Capabilities
（无既有 spec 需要修改）

## Impact

- **前端组件**:
  - `components/agentscope-chat/WelcomePrompts/` — 重构为新的欢迎页布局
  - `components/agentscope-chat/Sender/` — 输入框样式与位置调整
  - `components/agentscope-chat/Welcome/` — 欢迎页入口逻辑
  - 页面级 `pages/Chat/` — 侧栏 + 主区域布局
  - 新增组件: `FeaturedCases/`, `KnowledgeTabs/`, `TaskList/`, `SidebarFooter/`
- **API 调用**:
  - 定时任务列表获取（复用现有 cronjob API）
  - 定时任务触发执行（复用现有 cronjob API）
- **样式**: 新增主题色 #3769FC（主蓝）、#8482E7（标签紫）、#FE2842（红点）等设计 token
- **无后端改动**: 本次仅前端 UI 层变更，不涉及后端 API 新增或修改
