# Redis-Coordinated Cron Leadership - Configuration Examples

## Configuration Sources

Cron coordination is configured **exclusively through environment-derived values**:

1. **Process environment variables** (highest priority)
2. **User's `envs.json`** (persisted secrets at `~/.swe.secret/envs.json`)
3. **Packaged environment presets**: `src/swe/config/envs/{dev|prd}.json`
4. **`.env` file** in the working directory
5. **Hardcoded defaults** (lowest priority)

**Note**: `config.json` is **not** a supported source for cron coordination settings. Legacy `cron_coordination` sections in `config.json` are ignored.

**Important**: `.env` file has lower priority than packaged presets (`dev.json`/`prd.json`).
If you need to override preset values, use process environment variables or `envs.json`.

## Environment Variable Configuration

### Standalone Redis Mode

In `.env` file or as process environment variables:

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

## Environment Preset Files

For deployment-wide configuration, use the packaged environment presets:

**Development** (`src/swe/config/envs/dev.json`):
```json
{
  "SWE_CRON_COORDINATION_ENABLED": "true",
  "SWE_CRON_CLUSTER_MODE": "false",
  "SWE_CRON_REDIS_URL": "redis://localhost:6379/0",
  "SWE_CRON_LEASE_TTL_SECONDS": "30",
  "SWE_CRON_LEASE_RENEW_INTERVAL_SECONDS": "10"
}
```

**Production** (`src/swe/config/envs/prd.json`):
```json
{
  "SWE_CRON_COORDINATION_ENABLED": "true",
  "SWE_CRON_CLUSTER_MODE": "true",
  "SWE_CRON_CLUSTER_NODES": "redis-1:6379,redis-2:6379,redis-3:6379",
  "SWE_CRON_LEASE_TTL_SECONDS": "30",
  "SWE_CRON_LEASE_RENEW_INTERVAL_SECONDS": "10"
}
```

## Configuration Parameters

### Common Parameters

| Parameter | Environment Variable | Type | Default | Description |
|-----------|---------------------|------|---------|-------------|
| `enabled` | `SWE_CRON_COORDINATION_ENABLED` | bool | `false` | Enable Redis coordination |
| `cluster_mode` | `SWE_CRON_CLUSTER_MODE` | bool | `false` | Use Cluster mode |
| `lease_ttl_seconds` | `SWE_CRON_LEASE_TTL_SECONDS` | int | `30` | Leader lease TTL |
| `lease_renew_interval_seconds` | `SWE_CRON_LEASE_RENEW_INTERVAL_SECONDS` | int | `10` | Lease renew interval |
| `lease_renew_failure_threshold` | `SWE_CRON_LEASE_RENEW_FAILURE_THRESHOLD` | int | `3` | Failure threshold |
| `lock_safety_margin_seconds` | `SWE_CRON_LOCK_SAFETY_MARGIN_SECONDS` | int | `30` | Lock safety margin |
| `reload_channel_prefix` | - | str | `"swe:cron:reload"` | Reload channel prefix (code default) |

### Standalone Mode Parameters

| Parameter | Environment Variable | Type | Default | Description |
|-----------|---------------------|------|---------|-------------|
| `redis_url` | `SWE_CRON_REDIS_URL` | str | `"redis://localhost:6379/0"` | Redis URL |

### Cluster Mode Parameters

| Parameter | Environment Variable | Type | Default | Description |
|-----------|---------------------|------|---------|-------------|
| `cluster_nodes` | `SWE_CRON_CLUSTER_NODES` | str | `""` | Node list (host:port,host:port) |
| `cluster_max_connections` | - | int | `50` | Max connections (code default) |

## Disabling Coordination (Default)

```bash
SWE_CRON_COORDINATION_ENABLED=false
```

When disabled, the system runs in single-instance mode without Redis dependency.
