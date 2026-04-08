# Redis-Coordinated Cron Leadership - Configuration Examples

## Configuration Sources (优先级从高到低)

1. **环境变量** (`.env` 文件或系统环境变量)
2. **`config.json` 中的 `cron_coordination` 配置**

## 使用环境变量配置 (推荐)

在 `.env` 文件中添加：

### Standalone Redis Mode

```bash
# Enable cron coordination
SWE_CRON_COORDINATION_ENABLED=true

# Standalone mode (default)
SWE_CRON_CLUSTER_MODE=false
SWE_CRON_REDIS_URL=redis://localhost:6379/0

# Optional: lease configuration
SWE_CRON_LEASE_TTL_SECONDS=30
SWE_CRON_LEASE_RENEW_INTERVAL_SECONDS=10
SWE_CRON_LEASE_RENEW_FAILURE_THRESHOLD=3
SWE_CRON_LOCK_SAFETY_MARGIN_SECONDS=30
```

### Redis Cluster Mode

```bash
# Enable cron coordination
SWE_CRON_COORDINATION_ENABLED=true

# Enable cluster mode
SWE_CRON_CLUSTER_MODE=true

# Cluster nodes (comma-separated host:port pairs)
SWE_CRON_CLUSTER_NODES=redis-node-1:6379,redis-node-2:6379,redis-node-3:6379

# Optional: cluster-specific settings
SWE_CRON_LEASE_TTL_SECONDS=30
SWE_CRON_LEASE_RENEW_INTERVAL_SECONDS=10
SWE_CRON_LEASE_RENEW_FAILURE_THRESHOLD=3
SWE_CRON_LOCK_SAFETY_MARGIN_SECONDS=30
```

## 使用 config.json 配置

### Standalone Redis Mode

```json
{
  "cron_coordination": {
    "enabled": true,
    "cluster_mode": false,
    "redis_url": "redis://localhost:6379/0",
    "lease_ttl_seconds": 30,
    "lease_renew_interval_seconds": 10,
    "lease_renew_failure_threshold": 3,
    "lock_safety_margin_seconds": 30,
    "reload_channel_prefix": "swe:cron:reload"
  }
}
```

### Redis Cluster Mode

```json
{
  "cron_coordination": {
    "enabled": true,
    "cluster_mode": true,
    "cluster_nodes": [
      {"host": "redis-node-1", "port": 6379},
      {"host": "redis-node-2", "port": 6379},
      {"host": "redis-node-3", "port": 6379}
    ],
    "cluster_max_connections": 50,
    "lease_ttl_seconds": 30,
    "lease_renew_interval_seconds": 10,
    "lease_renew_failure_threshold": 3,
    "lock_safety_margin_seconds": 30,
    "reload_channel_prefix": "swe:cron:reload"
  }
}
```

### 混合配置 (环境变量 + config.json)

环境变量：
```bash
SWE_CRON_COORDINATION_ENABLED=true
SWE_CRON_CLUSTER_MODE=true
SWE_CRON_CLUSTER_NODES=redis-1:6379,redis-2:6379
```

config.json (仅覆盖部分设置)：
```json
{
  "cron_coordination": {
    "enabled": true,
    "lease_ttl_seconds": 60
  }
}
```

## 环境变量文件

项目提供了预设的环境变量文件：

- `src/swe/config/envs/dev.json` - 开发环境配置
- `src/swe/config/envs/prd.json` - 生产环境配置

可以在这些文件中添加 Redis 配置：

```json
{
  "SWE_CRON_COORDINATION_ENABLED": "true",
  "SWE_CRON_CLUSTER_MODE": "true",
  "SWE_CRON_CLUSTER_NODES": "redis-1:6379,redis-2:6379,redis-3:6379",
  "SWE_CRON_LEASE_TTL_SECONDS": "30",
  "SWE_CRON_LEASE_RENEW_INTERVAL_SECONDS": "10"
}
```

## 配置参数说明

### 通用参数

| 参数 | 环境变量 | 类型 | 默认值 | 说明 |
|------|----------|------|--------|------|
| `enabled` | `SWE_CRON_COORDINATION_ENABLED` | bool | `false` | 启用 Redis 协调 |
| `cluster_mode` | `SWE_CRON_CLUSTER_MODE` | bool | `false` | 使用 Cluster 模式 |
| `lease_ttl_seconds` | `SWE_CRON_LEASE_TTL_SECONDS` | int | `30` | Leader 租约 TTL |
| `lease_renew_interval_seconds` | `SWE_CRON_LEASE_RENEW_INTERVAL_SECONDS` | int | `10` | 租约续期间隔 |
| `lease_renew_failure_threshold` | `SWE_CRON_LEASE_RENEW_FAILURE_THRESHOLD` | int | `3` | 失败阈值 |
| `lock_safety_margin_seconds` | `SWE_CRON_LOCK_SAFETY_MARGIN_SECONDS` | int | `30` | 执行锁安全边距 |
| `reload_channel_prefix` | - | str | `"swe:cron:reload"` | reload 频道前缀 |

### Standalone 模式参数

| 参数 | 环境变量 | 类型 | 默认值 | 说明 |
|------|----------|------|--------|------|
| `redis_url` | `SWE_CRON_REDIS_URL` | str | `"redis://localhost:6379/0"` | Redis URL |

### Cluster 模式参数

| 参数 | 环境变量 | 类型 | 默认值 | 说明 |
|------|----------|------|--------|------|
| `cluster_nodes` | `SWE_CRON_CLUSTER_NODES` | str | `""` | 节点列表 (host:port,host:port) |
| `cluster_max_connections` | - | int | `50` | 最大连接数 |

## 禁用协调 (默认)

```bash
SWE_CRON_COORDINATION_ENABLED=false
```

或 config.json:

```json
{
  "cron_coordination": {
    "enabled": false
  }
}
```

当禁用时，系统保持单实例模式运行，不依赖 Redis。
