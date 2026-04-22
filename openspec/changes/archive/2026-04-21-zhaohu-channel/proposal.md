## Why

zhaohu 渠道是招商银行内部的即时通讯集成渠道，用于将 AI 助手接入招行员工日常工作场景。该渠道需要：
1. 接收来自招行员工的消息回调
2. 处理消息并通过招行推送系统回复
3. 支持自定义卡片通知，提供更好的用户体验
4. 实现敏感信息脱敏，符合金融合规要求

当前 zhaohu 渠道已实现三种消息场景的处理，本次优化 Case 2（任务分配）的处理流程，改为非流式输出模式。

## What Changes

**渠道整体设计（已完成）**：
- 入站回调处理：接收 Zhaohu 平台消息推送
- 出站消息推送：通过招行推送 URL 发送回复
- 用户身份转换：openId → sapId → ystId
- OAuth 认证：用于自定义卡片发送
- 消息脱敏：姓名、身份证、银行卡、手机号、座机号
- 消息去重：5分钟 TTL 防止重复处理

**Case 2 优化（本次变更）**：
- 移除流式处理：不再通过 `_consume_with_tracker` 广播流式事件
- 改为直接处理模式：使用 `_run_task_llm_and_notify` 收集完整结果后发送
- 发送完整结果：任务完成后一次性发送完整响应给用户

## Capabilities

### New Capabilities
- `zhaohu-channel-design`: zhaohu 渠道完整设计文档（包含架构、身份体系、三种 Case 处理流程）
- `zhaohu-task-complete-notification`: Case 2 非流式处理，完成后发送完整结果

### Modified Capabilities
<!-- 无现有specs需要修改 -->

## Impact

- **代码修改**：
  - `src/swe/app/channels/zhaohu/channel.py`：渠道核心实现
  - `src/swe/app/routers/zhaohu.py`：回调路由入口
  - `tests/unit/channels/test_zhaohu_channel.py`：单元测试
- **API影响**：`/api/zhaohu/callback` 回调接口
- **前端影响**：无（前端仍可通过卡片跳转查看完整 session 内容）
- **用户体验**：
  - Case 1：查询任务进度，收到卡片展示今日任务列表
  - Case 2：发送任务，先收到卡片通知，完成后收到完整结果
  - Case 3：闲聊对话，实时收到回复