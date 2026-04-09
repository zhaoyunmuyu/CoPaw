## Context

CoPaw 项目在 Kubernetes 容器多实例部署环境中运行，需要向远程注册中心发送心跳信号以实现：
- **服务注册**: 让注册中心感知到实例的存在
- **健康检查**: 定期心跳证明实例正常运行
- **负载均衡**: 注册中心根据心跳状态决定是否将流量路由到该实例
- **优雅关闭**: 进程退出时通知注册中心摘除该实例

### Kubernetes 容器关闭流程

```
Kubernetes 发送 SIGTERM 信号
    ↓
容器收到信号，开始优雅关闭（默认30秒宽限期）
    ↓
应用需要：
1. 停止接收新请求
2. 处理完正在进行请求
3. 发送关闭心跳（enabled=false）
    ↓
宽限期结束或应用主动退出
```

### 远程接口规范

接口为 POST 方法，入参如下：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| serviceName | String | 是 | 服务名称，固定为 "swe" |
| serviceUnit | String | 否 | 服务单元标识，从环境变量 `CMB_CAAS_SERVICEUNITID` 获取 |
| az | String | 否 | 可用区标识 |
| instanceIp | String | 是 | 实例IP，从 `/etc/hosts` 文件读取 |
| instancePort | Integer | 是 | 实例端口，默认 8088 |
| enabled | Boolean | 否 | 是否启用，正常心跳为 true，关闭时为 false |
| weight | Integer | 否 | 权重，默认 1 |

## Goals / Non-Goals

**Goals:**
- 实现定期心跳发送（默认30秒间隔，可配置）
- 进程退出时发送关闭信号（enabled=false）
- 心跳任务完全不影响用户正常使用
- 支持 Kubernetes 优雅关闭（捕获 SIGTERM 信号）
- 支持异常退出的兜底处理（atexit 回调）

**Non-Goals:**
- 不修改现有的 agent 心跳机制（那是 agent 级别的功能）
- 不引入新的依赖（使用现有的 httpx）
- 不支持心跳失败时的重试策略（失败只记录日志）
- 不支持复杂的服务发现协议

## Decisions

### 决策 1: 独立的 asyncio.Task 运行心跳

**选择**: 心跳循环在独立的 asyncio.Task 中运行

**理由**:
- 完全与主服务隔离，不影响用户请求处理
- 异步 HTTP 请求不阻塞主线程
- 任务失败不影响主服务运行

**实现要点**:
```python
self._task = asyncio.create_task(
    self._heartbeat_loop(),
    name="service-heartbeat",
)
```

### 决策 2: 三层退出信号捕获机制

**选择**: 使用信号处理器 + lifespan finally + atexit 三层保障

**理由**:
- 不同退出场景需要不同的捕获机制
- 信号处理器覆盖 Kubernetes SIGTERM 和用户 Ctrl+C
- lifespan finally 覆盖正常关闭流程
- atexit 作为最后的兜底

| 机制 | 触发场景 | 可靠性 |
|------|----------|--------|
| signal.SIGTERM/SIGINT | Kubernetes 关闭、Ctrl+C | 高 |
| lifespan finally | FastAPI 正常关闭 | 高 |
| atexit | sys.exit()、正常退出 | 中 |

**实现要点**:
```python
# 信号处理器：立即发送同步关闭心跳
for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, _signal_handler)

# atexit 回调：兜底方案
atexit.register(_atexit_handler)
```

### 册策 3: 实例IP从 /etc/hosts 读取

**选择**: 优先从 `/etc/hosts` 文件读取容器IP

**理由**:
- Kubernetes 容器的 `/etc/hosts` 包含容器IP和主机名映射
- 这是获取容器IP的可靠方式
- 失败时回退到 socket 方式获取本机IP

**实现要点**:
```python
with open("/etc/hosts", "r") as f:
    for line in f:
        parts = line.split()
        if len(parts) >= 2:
            ip = parts[0]
            if ip not in ("127.0.0.1", "::1"):
                return ip
```

### 决策 4: URL和间隔从环境变量读取

**选择**: 心跳URL和间隔时间从环境变量读取，而不是从 config.json

**理由**:
- 测试环境和生产环境的地址不同
- 与项目现有的环境变量管理模式一致（dev.json/prd.json）
- 敏感的服务地址不需要放在 config.json 中
- 支持运维人员在不同环境配置不同的值

**环境变量**:
```
SWE_SERVICE_HEARTBEAT_URL      # 心跳接口地址
SWE_SERVICE_HEARTBEAT_INTERVAL # 心跳间隔秒数（默认30，范围5-300）
```

**config.json 配置结构**:
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

**dev.json/prd.json 配置**:
```json
{
  "SWE_SERVICE_HEARTBEAT_URL": "https://dev.example.com/register",
  "SWE_SERVICE_HEARTBEAT_INTERVAL": "30"
}
```

### 册策 5: 关闭心跳使用同步HTTP客户端

**选择**: 信号处理器中使用同步 HTTP 客户端发送关闭心跳

**理由**:
- 信号处理器中异步操作可能无法完成（事件循环可能已停止）
- 同步请求确保关闭心跳一定能发送出去
- 使用独立的 5 秒超时，避免长时间阻塞

**实现要点**:
```python
def _signal_handler(signum, frame):
    # 立即发送同步关闭心跳
    with httpx.Client(timeout=5.0) as client:
        client.post(url, json=payload)
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| [风险] 心跳URL配置错误 | 配置验证，enabled=true但url为空时跳过启动 |
| [风险] 心跳发送失败 | 失败只记录日志，不影响主服务和下一次心跳 |
| [风险] 网络延迟阻塞心跳 | HTTP 请求独立 10 秒超时 |
| [风险] 信号处理器未执行 | atexit 回调作为兜底 |
| [风险] Windows 不支持 SIGTERM | 信号注册失败时忽略，依赖 atexit |
| [风险] 多实例IP获取失败 | 回退到 socket 获取本机IP，最终回退到 127.0.0.1 |

## Design Details

### 心跳循环流程

```
启动心跳任务
    ↓
加载配置，获取实例IP和服务单元标识
    ↓
进入心跳循环
    │
    ├── 发送心跳（enabled=true）
    │       ↓
    │   成功 → 记录日志
    │   失败 → 记录警告，继续循环
    │
    ├── 等待 interval_seconds
    │
    └── 循环继续...
    ↓
收到关闭信号或调用 stop()
    ↓
发送关闭心跳（enabled=false）
    ↓
清理资源
```

### 关闭流程

```
收到 SIGTERM/SIGINT 信号
    ↓
信号处理器触发
    │
    ├── 设置 _shutdown_requested = True
    ├── 立即发送同步关闭心跳
    └── 尝试安排异步清理（如果事件循环还在）
    ↓
FastAPI lifespan finally 块
    │
    ├── 如果未发送过关闭心跳，异步发送
    └── 清理 HTTP 客户端
    ↓
进程退出
```

### 异常处理边界

所有心跳相关的异常都在模块内部捕获：

```python
try:
    response = await self._client.post(url, json=payload)
except httpx.TimeoutException:
    logger.warning("心跳发送超时")
except httpx.RequestError as e:
    logger.warning("心跳发送网络错误")
except Exception as e:
    logger.error("心跳发送异常")
# 异常不会传播到外部
```

## File Structure

```
src/swe/
├── app/
│   ├── service_heartbeat.py    # 新增：心跳模块
│   └── _app.py                 # 修改：集成心跳
└── config/
    └── config.py               # 修改：新增 ServiceHeartbeatConfig
```

## Migration Plan

### 部署前准备

1. 在 `config.json` 中添加 `service_heartbeat` 配置（enabled 和基本参数）
2. 在 `dev.json` 或 `prd.json` 中配置 `SWE_SERVICE_HEARTBEAT_URL`
3. 配置 `CMB_CAAS_SERVICEUNITID` 环境变量（可选）

### 配置示例

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

**dev.json / prd.json**:
```json
{
  "SWE_SERVICE_HEARTBEAT_URL": "https://your-service.example.com/api/register",
  "SWE_SERVICE_HEARTBEAT_INTERVAL": "30"
}
```

### 验证步骤

1. 启动服务，检查日志确认心跳任务启动
2. 观察日志确认心跳发送成功
3. 使用 Ctrl+C 或 kill SIGTERM 测试关闭心跳发送