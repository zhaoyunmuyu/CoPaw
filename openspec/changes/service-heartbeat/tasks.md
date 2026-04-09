## 1. 配置模型

- [x] 1.1 在 `src/swe/config/config.py` 添加 `ServiceHeartbeatConfig` 类
- [x] 1.2 在 `Config` 类中添加 `service_heartbeat` 字段
- [x] 1.3 添加配置验证（enabled=true 但 url 为空时警告）

## 2. 心跳模块核心

- [x] 2.1 创建 `src/swe/app/service_heartbeat.py`
- [x] 2.2 实现 `get_instance_ip()` 函数（从 /etc/hosts 读取）
- [x] 2.3 实现 `get_service_unit()` 函数（从环境变量读取）
- [x] 2.4 实现 `ServiceHeartbeatManager` 类
- [x] 2.5 实现心跳请求体构建 `_build_payload()`
- [x] 2.6 实现异步心跳发送 `_send_heartbeat()`
- [x] 2.7 实现心跳循环 `_heartbeat_loop()`

## 3. 生命周期管理

- [x] 3.1 实现 `start()` 方法启动心跳任务
- [x] 3.2 实现 `stop()` 方法停止心跳并发送关闭信号
- [x] 3.3 实现 `_async_stop()` 内部清理方法

## 4. 信号处理

- [x] 4.1 实现 SIGTERM/SIGINT 信号处理器
- [x] 4.2 信号处理器中发送同步关闭心跳
- [x] 4.3 设置 `_shutdown_requested` 全局标志
- [x] 4.4 实现 atexit 回调作为兜底
- [x] 4.5 处理 Windows 不支持信号的兼容性

## 5. 应用集成

- [x] 5.1 在 `_app.py` 导入心跳模块
- [x] 5.2 在 lifespan 启动时调用 `start_service_heartbeat()`
- [x] 5.3 在 lifespan finally 中调用 `stop_service_heartbeat()`

## 6. 验证与测试

- [ ] 6.1 编写心跳模块单元测试
- [ ] 6.2 测试正常心跳发送流程
- [ ] 6.3 测试 SIGTERM 信号处理
- [ ] 6.4 测试心跳失败不影响主服务
- [ ] 6.5 测试配置未启用时的行为

## 7. 文档更新

- [ ] 7.1 更新 CLAUDE.md 添加心跳功能说明
- [ ] 7.2 添加配置使用文档