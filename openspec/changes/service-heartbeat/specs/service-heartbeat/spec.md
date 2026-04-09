# Service Heartbeat Specification

## Overview

服务心跳功能提供向远程注册中心定期发送心跳信号的能力，用于服务注册、健康检查和负载均衡。关键特性：
- 心跳任务完全独立运行，不影响用户正常使用
- 支持 Kubernetes 优雅关闭（捕获 SIGTERM 信号）
- 多层退出信号捕获机制确保关闭心跳能发送出去

## Capabilities

### service-heartbeat

服务心跳能力，向远程接口定期发送心跳信号。

**提供能力:**
- 定期心跳发送（默认30秒间隔）
- 进程退出时发送关闭信号（enabled=false）
- 完全不影响主服务运行
- 支持 Kubernetes SIGTERM 优雅关闭
- 支持 Ctrl+C (SIGINT) 关闭
- atexit 回调兜底

## Configuration

### config.json

心跳功能通过 `config.json` 的 `service_heartbeat` 字段配置：

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `enabled` | bool | 否 | false | 是否启用服务心跳 |
| `service_name` | string | 否 | "swe" | 服务名称（固定为swe） |
| `instance_port` | int | 否 | 8088 | 实例端口（范围1-65535） |
| `weight` | int | 否 | 1 | 权重（范围1-100） |

### Environment Variables

心跳URL和间隔时间从环境变量读取，支持dev/prd环境区分：

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `SWE_SERVICE_HEARTBEAT_URL` | 是* | - | 心跳接口地址（POST请求） |
| `SWE_SERVICE_HEARTBEAT_INTERVAL` | 否 | 30 | 心跳间隔秒数（范围5-300） |
| `CMB_CAAS_SERVICEUNITID` | 否 | - | 服务单元标识 |

*当 `enabled=true` 时必需

### Configuration Example

**config.json**:
```json
{
  "service_heartbeat": {
    "enabled": true,
    "service_name": "swe",
    "instance_port": 8088,
    "weight": 1
  }
}
```

**dev.json** (开发环境):
```json
{
  "SWE_SERVICE_HEARTBEAT_URL": "https://dev-service.example.com/api/register",
  "SWE_SERVICE_HEARTBEAT_INTERVAL": "30"
}
```

**prd.json** (生产环境):
```json
{
  "SWE_SERVICE_HEARTBEAT_URL": "https://prd-service.example.com/api/register",
  "SWE_SERVICE_HEARTBEAT_INTERVAL": "30"
}
```

## Heartbeat Request

### Request Format

POST 请求，JSON 格式请求体：

```json
{
  "serviceName": "swe",
  "serviceUnit": "service-unit-001",
  "instanceIp": "10.0.0.1",
  "instancePort": 8088,
  "enabled": true,
  "weight": 1
}
```

### Field Description

| 字段 | 类型 | 必填 | 来源 |
|------|------|------|------|
| `serviceName` | String | 是 | 配置（固定 "swe"） |
| `serviceUnit` | String | 否 | 环境变量 `CMB_CAAS_SERVICEUNITID` |
| `az` | String | 否 | 不发送 |
| `instanceIp` | String | 是 | `/etc/hosts` 或本机IP |
| `instancePort` | Integer | 是 | 配置（默认 8088） |
| `enabled` | Boolean | 否 | 正常 true，关闭 false |
| `weight` | Integer | 否 | 配置（默认 1） |

### Shutdown Request

进程退出时发送的请求，`enabled=false`：

```json
{
  "serviceName": "swe",
  "instanceIp": "10.0.0.1",
  "instancePort": 8088,
  "enabled": false,
  "weight": 1
}
```

## Instance IP Resolution

### Resolution Order

1. **Primary**: 从 `/etc/hosts` 文件读取容器IP
2. **Fallback**: 通过 UDP socket 获取本机IP
3. **Last resort**: 返回 `127.0.0.1`

### /etc/hosts Parsing Logic

```python
with open("/etc/hosts", "r") as f:
    for line in f:
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            ip = parts[0]
            # Skip localhost
            if ip not in ("127.0.0.1", "::1", "localhost"):
                return ip
```

## Signal Handling

### Supported Signals

| 信号 | 触发场景 | 处理方式 |
|------|----------|----------|
| SIGTERM | Kubernetes 优雅关闭 | 立即发送同步关闭心跳 |
| SIGINT | Ctrl+C | 立即发送同步关闭心跳 |

### Signal Handler Behavior

```python
def _signal_handler(signum, frame):
    # 1. Set shutdown flag
    _shutdown_requested = True

    # 2. Send synchronous shutdown heartbeat immediately
    send_sync_shutdown_heartbeat(url, payload)

    # 3. Try to schedule async cleanup if loop is running
    if loop and not loop.is_closed():
        loop.call_soon_threadsafe(lambda: asyncio.create_task(stop()))

    # 4. For SIGINT, exit process
    if signum == SIGINT:
        sys.exit(0)
```

### Platform Compatibility

- **Linux/Unix**: 支持 SIGTERM 和 SIGINT
- **Windows**: 可能不支持 SIGTERM，依赖 atexit 兜底

## Shutdown Guarantee

### Three-Layer Mechanism

| 层级 | 机制 | 触发场景 | 可靠性 |
|------|------|----------|--------|
| 1 | 信号处理器 | SIGTERM/SIGINT | 高 |
| 2 | lifespan finally | FastAPI 正常关闭 | 高 |
| 3 | atexit 回调 | sys.exit() | 中 |

### Shutdown Flow

```
关闭触发
    ↓
信号处理器收到信号？
    │
    ├── 是 → 立即发送同步关闭心跳（5秒超时）
    │
    └── 否（正常关闭）→
    ↓
FastAPI lifespan finally 块
    │
    ├── 未发送过 → 异步发送关闭心跳
    └── 清理 HTTP 客户端
    ↓
进程退出前
    │
    └── atexit 回调
        │
        ├── 已发送过 → 跳过
        └── 未发送过 → 发送同步关闭心跳
```

## Isolation Guarantee

### Heartbeat Task Isolation

心跳任务完全独立于主服务：

1. **独立 asyncio.Task**: 心跳循环在独立的 `asyncio.create_task()` 中运行
2. **异常不传播**: 所有异常在模块内部捕获，只记录日志
3. **独立超时**: HTTP 请求有独立的 10 秒超时，不阻塞主线程
4. **失败不影响主服务**: 心跳失败只记录 warning，不影响下一次心跳或主服务

### Exception Handling

```python
try:
    response = await client.post(url, json=payload)
except httpx.TimeoutException:
    logger.warning("心跳发送超时")
    return False  # 不影响循环继续
except httpx.RequestError as e:
    logger.warning("心跳发送网络错误: %s", e)
    return False
except Exception as e:
    logger.error("心跳发送异常: %s", repr(e))
    return False
```

## Dependencies

- `httpx`: HTTP 客户端（异步和同步）
- `signal`: 信号处理（标准库）
- `atexit`: 进程退出回调（标准库）
- `socket`: IP 地址获取（标准库）

## Logging

### Log Levels

| 场景 | 日志级别 | 示例 |
|------|----------|------|
| 心跳任务启动 | INFO | "服务心跳任务已启动" |
| 心跳发送成功 | INFO | "心跳发送成功: enabled=true, status=200" |
| 心跳发送失败 | WARNING | "心跳发送失败: status=500" |
| 心跳发送超时 | WARNING | "心跳发送超时: url=..." |
| 收到关闭信号 | INFO | "收到关闭信号: SIGTERM (15)" |
| 关闭心跳发送 | INFO | "发送服务关闭心跳信号..." |
| 配置未启用 | INFO | "服务心跳未启用，跳过启动" |

## Error Scenarios

| 错误场景 | 处理方式 |
|----------|----------|
| 配置 enabled=true 但 url 为空 | 跳过启动，记录 WARNING |
| 心跳 URL 不可达 | 记录 WARNING，继续下一次心跳 |
| 心跳响应非 2xx | 记录 WARNING，继续下一次心跳 |
| 实例 IP 获取失败 | 回退到 socket 方式，最终 127.0.0.1 |
| 信号处理器发送关闭心跳失败 | 记录 ERROR，进程继续退出 |
| Windows 不支持信号 | 忽略信号注册错误，依赖 atexit |