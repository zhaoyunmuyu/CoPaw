## 1. Channel Implementation

- [x] 1.1 zhaohu 渠道核心架构实现：入站回调处理、出站消息推送
- [x] 1.2 用户身份转换机制：openId → sapId → ystId
- [x] 1.3 OAuth Token 缓存和自动刷新机制
- [x] 1.4 消息去重机制：5分钟 TTL 内存缓存
- [x] 1.5 消息路由：三种 Case 判断和处理

## 2. Case 2 Non-Streaming Implementation

- [x] 2.1 新增 `_run_task_llm_and_notify` 方法，实现：发送卡片通知、运行LLM收集完整结果、发送最终结果
- [x] 2.2 修改 `_handle_task_assignment` 方法，移除 `_consume_with_tracker` 调用，改为调用 `_run_task_llm_and_notify`

## 3. Case 1 and Case 3 Implementation

- [x] 3.1 Case 1 任务进度查询：查询 CronManager，发送 Template 2 卡片
- [x] 3.2 Case 3 闲聊：使用 `_consume_with_tracker` 流式处理

## 4. Supporting Features

- [x] 4.1 自定义卡片模板：Template 1 任务发起通知、Template 2 任务进度查询
- [x] 4.2 Claw URL 构造：支持 session 和 task 跳转
- [x] 4.3 消息脱敏：姓名、身份证、银行卡、手机号、座机号

## 5. Testing

- [x] 5.1 单元测试：验证 `_run_task_llm_and_notify` 正确收集完整结果
- [x] 5.2 单元测试：验证错误处理时发送错误通知
- [x] 5.3 验证 Case 1 和 Case 3 流程不受影响