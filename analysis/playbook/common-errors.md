# 常见报错

本文档只收录仓库中已经出现过、且有明确入口可追的高频报错。

## 长 MCP 调用期间 console SSE 被静默断开

### 症状

- MCP 工具调用耗时 10 秒以上时，前端 console 会话中断
- `streamable_http` MCP 本身还在执行，但 `/console/chat` 长时间没有任何 SSE 输出
- 日志可见运行被取消，例如：
  - `query_handler: <session_id> cancelled!`
  - `Runner finally block executing for session <session_id>`

### 典型原因

- 外层 `/console/chat` SSE 在长时间无事件期间没有发送心跳帧
- 代理、Ingress 或客户端对 10 到 15 秒静默连接执行 idle timeout
- 即使后端任务未失败，HTTP 流也会先被外层网络链路掐断
- `streamable_http` MCP 如果走到默认 `httpx` timeout，可能在读阶段约 5 秒无新字节时先超时或触发中断链路

### 第一落点

- [src/swe/app/routers/console.py](/Users/shixiangyi/code/Swe/src/swe/app/routers/console.py)
- 重点看 `post_console_chat()` 和 `_stream_with_keepalive()`
- [src/swe/app/runner/runner.py](/Users/shixiangyi/code/Swe/src/swe/app/runner/runner.py)
- 重点看 `_create_mcp_client_with_headers()` 是否给 `streamable_http` MCP 显式配置 `httpx.Timeout`

### 第一阶段处理

- 在 `/console/chat` 的 SSE 输出层补 comment 心跳，例如 `: keep-alive\n\n`
- 心跳周期要小于最短代理 idle timeout，当前实现默认 5 秒
- 响应头显式加 `X-Accel-Buffering: no`，避免代理缓冲导致心跳帧无法及时刷出

### 边界说明

- 这一阶段只解决“外层 SSE 静默断连”
- 不包含 MCP 内部执行进度透传；如果希望前端看到“工具执行中”，需要后续把 MCP progress/event 映射进 `TaskTracker` 或 SSE 事件流
