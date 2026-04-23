## Tasks

### Task 1: 新增意图识别配置字段
- [x] 在 `ZhaohuConfig` 中新增 `intent_url`、`intent_open_id`、`intent_api_key` 字段
- [x] 在 `ZhaohuChannel.__init__` 中接收新参数并存储
- [x] 在 `from_env` 和 `from_config` 方法中读取新配置
- [x] 在 `prd.json` 中新增环境变量定义

### Task 2: 实现意图识别方法
- [x] 新增 `_check_intent` 方法
- [x] 构建请求 payload（inputParams、openId）
- [x] 设置 header（Content-Type、API-Key）
- [x] 解析响应判断是否为任务
- [x] 异常处理，失败时返回 False

### Task 3: 修改消息路由逻辑
- [x] 修改 `_route_message` 方法
- [x] 文本长度 <= 5 直接判定为 Case 3
- [x] 文本长度 > 5 调用 `_check_intent`
- [x] 根据意图识别结果路由到 Case 2 或 Case 3

### Task 4: 优化 Case 2 处理流程
- [x] 修改 `_handle_task_assignment` 方法
- [x] 使用 `resolve_session_id` 生成 sessionId（与 Case 3 相同）
- [x] 发送卡片通知
- [x] 使用 `get_llm_response` 处理 LLM 请求

## Verification

- [x] 语法检查通过（py_compile）
- [ ] 部署测试：配置环境变量后验证意图识别接口调用
- [ ] 功能测试：验证 Case 2 和 Case 3 的正确路由