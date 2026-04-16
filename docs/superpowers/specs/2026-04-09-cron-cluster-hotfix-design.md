# Cron Cluster Hotfix Design

## Goal

Provide the smallest safe follow-up to commit `dbe8a52304b5efa25dbdd891556f69cb3af38fc5` so the cron coordination changes are mergeable.

This design only covers fixes for the regressions found in review:

1. Cluster mode fails on multi-node `redis_url` parsing.
2. Cluster mode reload publish still uses `RedisCluster`, which lacks pub/sub APIs.
3. Failover takeover can leave an instance holding leadership without a started scheduler if startup fails.

## Scope

In scope:

- Fix cluster connection parameter parsing for multi-node Redis URLs
- Fix reload publish path in cluster mode
- Fix failover takeover error handling
- Add focused regression tests for these paths

Out of scope:

- Refactoring cron coordination architecture
- Changing cluster pub/sub node selection strategy
- Adding full Redis Cluster integration tests
- Adding retry/backoff policy for scheduler startup

## Design

### 1. Cluster URL Parsing

`CronCoordination._build_cluster_startup_nodes()` remains the source of truth for parsing host/port pairs from cluster configuration.

`CronCoordination._parse_redis_url()` will be narrowed to parsing only shared connection attributes:

- `username`
- `password`
- `ssl`
- optional `db` if already trivially available

The method must not read `parsed.port` for cluster-style multi-node URLs such as:

- `redis://host1:6379,host2:6380`
- `redis://user:pass@host1:6379,host2:6380`

This avoids `urllib.parse` raising `ValueError` on the combined port segment.

### 2. Cluster Reload Publish

`CronCoordination.publish_reload()` will publish through `_pubsub_client` instead of `_redis`.

Expected behavior:

- standalone mode: `_pubsub_client is _redis`, so behavior is unchanged
- cluster mode: `_pubsub_client` is the standalone Redis client already introduced for subscription support

This keeps publish and subscribe on the same API-compatible client type and avoids runtime `AttributeError` from `RedisCluster.publish()`.

### 3. Failover Takeover Startup Safety

`CronManager._on_become_leader()` will continue scheduling asynchronous startup, but the startup path must be wrapped in a controlled coroutine.

Required behavior:

- call `_do_start()`
- if startup succeeds, keep the acquired lease
- if startup fails, log the error at error level
- then call `deactivate()` to release leadership and stop coordination state

This is the minimum safe behavior because it prevents a stuck leader that cannot schedule jobs while still blocking followers from taking over.

No retry loop will be added in this change.

## Test Plan

Add focused unit tests covering:

1. Cluster auth parsing with multi-node `redis_url`
   - confirms parsing does not raise on multi-node URL
   - confirms username/password/ssl extraction still works

2. Cluster reload publish path
   - verifies `publish_reload()` uses `_pubsub_client`
   - verifies the publish call is made on the standalone client, not `RedisCluster`

3. Failover startup failure handling
   - simulates `_do_start()` failure after leadership callback
   - verifies cleanup/deactivation is triggered

Existing cron coordination tests remain the main regression suite:

```bash
venv/bin/python -m pytest tests/unit/test_cron_coordination.py tests/unit/test_cron_manager_coordination.py -q
```

## Risks

- Publishing reload via the standalone client still depends on the chosen node being reachable.
- Releasing leadership after startup failure may briefly leave the system without a leader until another candidate retries.

Both are acceptable for this hotfix because they preserve correctness and availability better than the current failure modes.

## Acceptance Criteria

This hotfix is ready when all of the following are true:

- Cluster mode no longer fails because multi-node `redis_url` parsing touches `.port`
- Cluster mode cron mutations can publish reload signals without using `RedisCluster.publish()`
- Failover startup failure does not leave a zombie leader
- Added tests cover all three regressions
- Target cron unit tests pass
