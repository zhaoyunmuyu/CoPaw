## Why

CoPaw 在 Kubernetes 容器多实例部署环境中，需要向远程注册中心发送心跳信号，以实现服务注册、健康检查和负载均衡。心跳服务需要：
- 服务启动时开启后台心跳任务，定期（默认30秒）发送正常心跳
- 进程结束前发送关闭信号（enabled=false），让注册中心及时摘除该实例
- 心跳任务完全不影响用户正常使用

## What Changes

- **新增** `src/swe/app/service_heartbeat.py` 模块，包含完整的心跳发送逻辑
- **新增** `ServiceHeartbeatConfig` 配置类，定义心跳相关配置项
- **新增** 信号处理器，捕获 SIGTERM/SIGINT 实现 Kubernetes 优雅关闭
- **新增** atexit 回调作为最后的兜底方案
- **修改** `src/swe/config/config.py`，添加 `service_heartbeat` 配置字段
- **修改** `src/swe/app/_app.py`，在 lifespan 中集成心跳启动和停止

## Capabilities

### New Capabilities

- `service-heartbeat`: 服务心跳能力，支持向远程接口定期发送心跳信号，进程退出时发送关闭信号

### Modified Capabilities

- （无现有 spec 需要修改）

## Impact

- **代码文件**:
  - `src/swe/app/service_heartbeat.py`: 新增心跳模块（约350行）
  - `src/swe/config/config.py`: 新增 `ServiceHeartbeatConfig` 类
  - `src/swe/app/_app.py`: 集成心跳启动和停止

- **配置变更**: `config.json` 新增 `service_heartbeat` 配置段

- **API 请求**: POST 请求发送心跳，请求体包含服务信息

- **环境变量**:
  - `SWE_SERVICE_HEARTBEAT_URL`: 心跳接口地址（从 dev.json/prd.json 加载）
  - `SWE_SERVICE_HEARTBEAT_INTERVAL`: 心跳间隔秒数（从 dev.json/prd.json 加载）
  - `CMB_CAAS_SERVICEUNITID`: 服务单元标识

- **向后兼容**: 完全向后兼容，心跳功能为可选功能，默认禁用