## Why

用户点击精选案例卡片的「看案例」按钮后，需要一个底部弹窗来展示案例的完整详情内容（包含数据表格和步骤说明），帮助用户在聊天页面内直接了解案例流程，无需跳转。

## What Changes

- 新增案例详情底部弹窗组件（CaseDetailDrawer），从页面底部滑入
- 弹窗顶部有标题栏（"案例详情" + 关闭按钮）
- 弹窗内容区域分左右两栏：左侧为数据表格，右侧为步骤说明
- 底部有操作按钮：「订阅为定时任务」和「做同款」
- 精选案例卡片的「看案例」按钮点击后打开此弹窗
- 「做同款」按钮点击后关闭弹窗并将案例内容填入聊天输入框

## Capabilities

### New Capabilities
- `case-detail-drawer`: 案例详情底部弹窗组件，包含标题栏、左右分栏内容区、底部操作按钮

### Modified Capabilities
<!-- 无需修改现有能力的需求 -->

## Impact

- 新增组件：`console/src/components/agentscope-chat/CaseDetailDrawer/`
- 修改组件：`console/src/components/agentscope-chat/FeaturedCases/` — 添加「看案例」回调
- 修改页面：`console/src/pages/Chat/index.tsx` — 集成弹窗状态管理
