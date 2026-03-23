# CoPaw 多实例容器化部署设计文档 (修订版)

**日期**: 2026-03-22
**版本**: v1.1
**状态**: 评审中

---

## 1. 背景与目标

### 1.1 背景

CoPaw 当前支持单实例部署，所有数据存储在本地文件系统。随着用户规模增长，需要支持多实例水平扩展，并使用统一的 NAS 存储所有数据。

### 1.2 目标

- 支持 5-10 个 CoPaw 实例同时运行
- 使用统一 NAS 存储所有持久化数据
- 使用 Redis 实现分布式锁，解决定时任务并发执行问题
- 不使用 IM 通道（QQ/飞书/钉钉等），无需处理 WebSocket 长连接
- 负载均衡无需会话亲和性

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        负载均衡器 (任意策略)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
      ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
      │ 实例 1  │      │ 实例 2  │  ... │ 实例 N  │  (5-10 实例)
      │         │      │         │      │         │
      │ ┌─────┐ │      │ ┌─────┐ │      │ ┌─────┐ │
      │ │AP   │ │      │ │AP   │ │      │ │AP   │ │
      │ │调度 │ │      │ │调度 │ │      │ │调度 │ │
      │ │器   │ │      │ │器   │ │      │ │器   │ │
      │ └──┬──┘ │      │ └──┬──┘ │      │ └──┬──┘ │
      │    │    │      │    │    │      │    │    │
      │ 获取锁 │      │ 获取锁 │      │ 获取锁 │
      └────┼────┘      └────┼────┘      └────┼────┘
           │                │                │
           └────────────────┼────────────────┘
                            │
                    ┌───────┴───────┐
                    │    Redis      │  ← 分布式锁
                    │  (独立部署)    │
                    └───────────────┘
                            │
                    ┌───────┴───────┐
                    │     NAS       │  ← 任务配置、状态、会话
                    │  (统一存储)    │
                    └───────────────┘
```

### 2.2 组件职责

| 组件 | 职责 |
|-----|------|
| 负载均衡器 | HTTP 请求分发，无需会话保持 |
| CoPaw 实例 | 处理 API 请求，执行定时任务（抢锁执行） |
| Redis | 提供分布式锁服务 |
| NAS | 统一存储所有持久化数据 |

---

## 3. 存储设计

### 3.1 存储分层

| 数据类型 | 存储位置 | 说明 |
|---------|---------|-----|
| **分布式锁** | Redis | 用户级锁，防止同一用户任务重复执行 |
| **临时数据** | Redis | `console_push`, `download_tasks` 使用 Redis 带 TTL |
| **任务配置** | NAS `{user_dir}/jobs.json` | 现有实现，无需修改 |
| **任务状态** | NAS `{user_dir}/jobs_state.json` | 持久化任务状态 |
| **会话数据** | NAS `{user_dir}/sessions/*.json` | 现有实现 |
| **配置数据** | NAS `{user_dir}/config.json` | 现有实现 |
| **记忆数据** | NAS `{user_dir}/memory/` | 现有实现 |
| **备份任务** | NAS `{user_dir}/backup_tasks.json` | 现有实现 |

### 3.2 临时数据改用 Redis（关键变更）

**原因**: `console_push_store` 和 `download_task_store` 具有以下特点：
- 生命周期短（console_push 仅60秒有效期）
- 读写频繁
- consume-once 语义要求高
- 无需持久化

**方案**: 改用 Redis Hash + TTL，避免 NAS 文件锁竞争。

```python
# console_push_store 使用 Redis
KEY = f"copaw:push:{user_id}"
TTL = 60  # 60秒过期

# download_task_store 使用 Redis
KEY = f"copaw:download:{task_id}"
TTL = 3600  # 1小时过期
```

### 3.3 NAS 路径结构

```
/nas/copaw/
├── {user_id}/
│   ├── config.json              # 用户配置
│   ├── jobs.json                # 定时任务配置
│   ├── jobs_state.json          # 定时任务状态
│   ├── HEARTBEAT.md             # 心跳查询文件
│   ├── backup_tasks.json        # 备份任务状态
│   ├── envs.json                # 环境变量
│   ├── sessions/                # 会话目录
│   │   └── {session_id}.json
│   ├── memory/                  # 记忆数据
│   ├── active_skills/           # 激活的技能
│   ├── customized_skills/       # 自定义技能
│   └── models/                  # 本地模型
```

---

## 4. 分布式锁设计

### 4.1 锁粒度

**用户级锁**：同一用户的任务串行执行，不同用户的任务并行执行。

```python
# 锁 Key 格式
KEY = f"copaw:cron:user:{user_id}"

# 示例
"copaw:cron:user:alice"  # alice 的所有任务竞争这把锁
"copaw:cron:user:bob"    # bob 的所有任务竞争这把锁
```

### 4.2 锁参数

| 参数 | 默认值 | 说明 | 可配置 |
|-----|-------|-----|-------|
| `CRON_LOCK_TTL` | 600 (秒) | 锁超时时间 | 是 |
| `CRON_LOCK_PREFIX` | `copaw:cron:user:` | 锁 Key 前缀 | 是 |
| `CRON_LOCK_RENEW_INTERVAL` | 300 (秒) | 锁续期间隔（TTL/2） | 否，固定 TTL/2 |
| `CRON_LOCK_JITTER` | 2000 (毫秒) | 抢锁随机延迟 | 是 |

### 4.3 Lua 脚本

```lua
-- acquire_lock.lua
-- 获取锁，仅在 Key 不存在时设置
if redis.call('exists', KEYS[1]) == 0 then
    redis.call('setex', KEYS[1], ARGV[2], ARGV[1])
    return 1
end
return 0

-- release_lock.lua
-- 释放锁，仅当持有者匹配时才删除
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0

-- extend_lock.lua
-- 续期锁，仅当持有者匹配时才续期
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
```

### 4.4 锁续期机制（关键变更）

**问题**: 用户有多个长耗时任务时，锁可能在执行期间过期。

**解决**: 后台任务定期续期锁。

```python
class LockRenewalTask:
    """后台锁续期任务"""

    EXTEND_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('expire', KEYS[1], ARGV[2])
    end
    return 0
    """

    def __init__(self, redis_client, lock_key, lock_value, ttl):
        self.redis = redis_client
        self.key = lock_key
        self.value = lock_value
        self.ttl = ttl
        self.interval = ttl / 2  # TTL/2 时续期
        self._stop_event = asyncio.Event()
        self._task = None
        self._failed_renewals = 0
        self._max_failed_renewals = 3  # 连续失败3次后放弃

    async def start(self):
        self._task = asyncio.create_task(self._renew_loop())

    async def stop(self):
        self._stop_event.set()
        if self._task:
            await self._task

    async def _renew_loop(self):
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval
                )
                break  # 收到停止信号
            except asyncio.TimeoutError:
                # 续期锁
                success = await self._extend()
                if not success:
                    self._failed_renewals += 1
                    logger.warning(
                        f"Lock renewal failed ({self._failed_renewals}/{self._max_failed_renewals}) "
                        f"for key={self.key}"
                    )
                    if self._failed_renewals >= self._max_failed_renewals:
                        logger.error(f"Lock renewal failed too many times, lock may be lost")
                        break  # 退出续期循环，让主任务决定如何处理
                else:
                    self._failed_renewals = 0  # 重置失败计数

    async def _extend(self) -> bool:
        """续期锁，返回是否成功"""
        try:
            result = await self.redis.eval(
                self.EXTEND_SCRIPT,
                keys=[self.key],
                args=[self.value, self.ttl]
            )
            return result == 1
        except Exception as e:
            logger.exception(f"Lock renewal error: {e}")
            return False

    def is_healthy(self) -> bool:
        """检查续期任务是否健康"""
        return self._failed_renewals < self._max_failed_renewals
```

### 4.5 锁使用流程（含续期和防惊群）

```python
async def _scheduled_callback(self, user_id: str, job_id: str):
    # 1. 随机延迟防止惊群效应
    jitter_ms = random.randint(0, CRON_LOCK_JITTER)
    await asyncio.sleep(jitter_ms / 1000)

    # 2. 尝试获取用户级锁
    lock_key = f"copaw:cron:user:{user_id}"
    lock_value = f"{INSTANCE_ID}:{time.time()}"
    ttl = CRON_LOCK_TTL

    if not await redis_lock.acquire(lock_key, lock_value, ttl=ttl):
        logger.debug(f"Lock held by another instance for user={user_id}")
        return  # 其他实例正在处理该用户的任务

    # 3. 获取锁成功，启动续期任务
    renewal = LockRenewalTask(redis, lock_key, lock_value, ttl)
    await renewal.start()

    try:
        # 4. 加载用户任务状态
        states = await self._load_user_states(user_id)
        self._states[user_id] = states

        # 5. 执行该用户的所有待运行任务
        await self._execute_user_pending_jobs(user_id)

        # 6. 持久化任务状态到 NAS
        await self._save_user_states(user_id)
    finally:
        # 7. 停止续期任务
        await renewal.stop()
        # 8. 释放锁
        await redis_lock.release(lock_key, lock_value)
```

---

## 5. NAS 文件锁设计

### 5.1 文件锁使用场景

虽然临时数据移到了 Redis，但 NAS 上的文件仍需要文件锁保护：

| 文件 | 锁类型 | 说明 |
|-----|-------|-----|
| `jobs.json` | 写锁 | 修改任务配置时 |
| `jobs_state.json` | 读写锁 | 读取和更新任务状态时 |
| `config.json` | 写锁 | 保存配置时 |
| `sessions/*.json` | 无锁 | 单会话只被一个实例处理 |

### 5.2 文件锁实现

使用 `portalocker` 库实现跨平台文件锁。

```python
import portalocker
from contextlib import asynccontextmanager

@asynccontextmanager
async def file_lock(path: Path, mode: str = "r"):
    """文件锁上下文管理器（异步包装）

    Args:
        path: 文件路径
        mode: 'r' 读锁(共享), 'w' 写锁(独占)
    """
    lock_mode = portalocker.LOCK_SH if mode == "r" else portalocker.LOCK_EX
    lock_mode |= portalocker.LOCK_NB  # 非阻塞

    # 写模式下确保文件存在
    if mode == "w":
        await asyncio.to_thread(_ensure_file_exists, path)

    fd = None
    try:
        fd = await asyncio.to_thread(open, path, "r+" if mode == "w" else "r")
        await asyncio.to_thread(portalocker.lock, fd, lock_mode)
        yield fd
    finally:
        if fd:
            await asyncio.to_thread(portalocker.unlock, fd)
            await asyncio.to_thread(fd.close)


def _ensure_file_exists(path: Path) -> None:
    """确保文件存在（同步方法，在线程中执行）"""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
```

### 5.3 任务状态读写流程

```python
async def _load_user_states(self, user_id: str) -> Dict[str, CronJobState]:
    """加载用户任务状态（带文件锁）"""
    state_path = get_user_state_path(user_id)

    if not state_path.exists():
        return {}

    async with file_lock(state_path, mode="r"):
        data = json.loads(state_path.read_text())
        return {k: CronJobState(**v) for k, v in data.items()}

async def _save_user_states(self, user_id: str) -> None:
    """保存用户任务状态（带文件锁）"""
    state_path = get_user_state_path(user_id)
    states = self._states.get(user_id, {})

    async with file_lock(state_path, mode="w"):
        # 原子写入
        tmp_path = state_path.with_suffix(".tmp")
        data = {k: v.model_dump() for k, v in states.items()}
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.replace(state_path)
```

---

## 6. Redis 故障处理

### 6.1 故障检测

```python
async def check_redis() -> bool:
    """检查 Redis 连接状态"""
    try:
        await redis.ping()
        return True
    except Exception:
        return False
```

### 6.2 故障模式

**采用 Fail-Fast 策略**：Redis 不可用时，所有实例跳过任务执行。

```python
async def _scheduled_callback(self, user_id: str, job_id: str):
    # 检查 Redis 连接
    if not await check_redis():
        logger.error(f"Redis unavailable, skipping job for user={user_id}")
        return  # 不执行，等待 Redis 恢复

    # 正常流程...
```

**原因**:
1. Redis 是轻量级服务，可用性高
2. Fail-Fast 避免复杂的降级逻辑
3. 任务可配置 misfire_grace_time，错过的任务会在 Redis 恢复后补执行

### 6.3 健康检查

```python
@app.get("/health")
async def health_check():
    """健康检查端点"""
    redis_ok = await check_redis()
    nas_ok = check_nas_writable()

    status = "healthy" if redis_ok and nas_ok else "unhealthy"
    code = 200 if status == "healthy" else 503

    return JSONResponse(
        status_code=code,
        content={
            "status": status,
            "redis": "connected" if redis_ok else "disconnected",
            "nas": "writable" if nas_ok else "not_writable",
            "instance_id": INSTANCE_ID,
        }
    )

@app.get("/ready")
async def readiness_check():
    """就绪检查端点（用于 Kubernetes）"""
    # 检查关键依赖
    if not await check_redis():
        raise HTTPException(status_code=503, detail="Redis not ready")
    if not check_nas_writable():
        raise HTTPException(status_code=503, detail="NAS not ready")
    return {"ready": True}
```

---

## 7. 实例标识

### 7.1 实例 ID 生成

```python
import socket
import uuid

# 优先级: 环境变量 > 主机名 > UUID
INSTANCE_ID = (
    os.environ.get("COPAW_INSTANCE_ID") or
    socket.gethostname() or
    str(uuid.uuid4())[:8]
)
```

### 7.2 环境变量配置

```bash
# Docker Compose（独立模式）
# 注意：在独立 Docker Compose 中，所有容器共享相同 hostname
# 建议留空让应用自动生成 UUID，或使用容器名称
  - COPAW_INSTANCE_ID=  # 留空，自动生成

# Docker Swarm 模式（推荐用于生产）
  - COPAW_INSTANCE_ID={{.Task.Name}}  # 使用 Swarm 任务名称

# Kubernetes
  - COPAW_INSTANCE_ID=$(POD_NAME)  # 使用 Pod 名称
```

# Kubernetes
env:
  - name: COPAW_INSTANCE_ID
    valueFrom:
      fieldRef:
        fieldPath: metadata.name  # Pod 名称
```

---

## 8. 改造清单

### 8.1 新增文件

| 文件 | 说明 |
|-----|------|
| `src/copaw/lock/redis_lock.py` | Redis 分布式锁实现 |
| `src/copaw/lock/file_lock.py` | NAS 文件锁实现（封装 portalocker） |
| `src/copaw/lock/__init__.py` | 锁模块导出 |
| `src/copaw/store/redis_store.py` | Redis 版 console_push/download 存储 |

### 8.2 修改文件

| 文件 | 改造内容 |
|-----|---------|
| `src/copaw/app/crons/manager.py` | 1. 添加锁续期机制<br>2. 添加随机延迟防惊群<br>3. 状态持久化到 NAS<br>4. Redis 故障检测 |
| `src/copaw/app/console_push_store.py` | 改用 Redis 存储（带 TTL） |
| `src/copaw/app/download_task_store.py` | 改用 Redis 存储（带 TTL） |
| `src/copaw/config/config.py` | 新增 Redis 配置、锁配置、实例 ID 配置 |
| `src/copaw/constant.py` | 新增 Redis 相关常量 |
| `src/copaw/app/_app.py` | 添加 `/health` 和 `/ready` 端点 |
| `deploy/docker-compose.yml` | 添加 Redis 服务，配置多实例部署 |
| `deploy/Dockerfile` | 添加 redis、portalocker 依赖 |
| `pyproject.toml` | 添加依赖 |

### 8.3 配置变更

#### 环境变量

```bash
# Redis 配置
COPAW_REDIS_HOST=redis
COPAW_REDIS_PORT=6379
COPAW_REDIS_DB=0
COPAW_REDIS_PASSWORD=
COPAW_REDIS_SSL=false

# 分布式锁配置
COPAW_CRON_LOCK_TTL=600          # 锁超时时间（秒）
COPAW_CRON_LOCK_JITTER=2000      # 抢锁随机延迟（毫秒）

# 实例标识
COPAW_INSTANCE_ID=               # 自动生成（主机名或UUID）

# 工作目录（指向 NAS）
COPAW_WORKING_DIR=/nas/copaw
COPAW_SECRET_DIR=/nas/copaw/.secret
```

---

## 9. 部署方案

### 9.1 Docker Compose

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  copaw:
    image: copaw:latest
    restart: unless-stopped
    deploy:
      replicas: 5
    environment:
      - COPAW_WORKING_DIR=/nas/copaw
      - COPAW_SECRET_DIR=/nas/copaw/.secret
      - COPAW_REDIS_HOST=redis
      - COPAW_REDIS_PORT=6379
      - COPAW_CRON_LOCK_TTL=600
      - COPAW_CRON_LOCK_JITTER=2000
      - COPAW_INSTANCE_ID={{.Task.Name}}  # Docker Swarm
    volumes:
      - /mnt/nas/copaw:/nas/copaw:rw
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8088/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  redis_data:
```

### 9.2 NAS 挂载选项

```yaml
# Docker Compose 高级挂载选项
volumes:
  - type: bind
    source: /mnt/nas/copaw
    target: /nas/copaw
    bind:
      propagation: rshared
    # 或 NFS 直接挂载
  - type: nfs
    source: nas-server:/copaw
    target: /nas/copaw
```

**推荐挂载参数**（NFSv4）:
```bash
mount -t nfs4 -o
  vers=4.0,
  hard,
  intr,
  timeo=600,
  retrans=3,
  nolock,  # 禁用 NFS 客户端锁，使用应用层锁
  nas-server:/copaw /mnt/nas/copaw
```

---

## 10. 迁移方案

### 10.1 从单实例迁移到多实例

**步骤**:

1. **停止单实例**
   ```bash
   docker-compose down
   # 或 systemctl stop copaw
   ```

2. **迁移数据到 NAS**
   ```bash
   # 假设原数据在 ~/.copaw
   rsync -av ~/.copaw/ /mnt/nas/copaw/
   ```

3. **更新配置**
   - 设置 `COPAW_WORKING_DIR=/nas/copaw`
   - 配置 Redis 连接

4. **启动多实例**
   ```bash
   docker-compose -f docker-compose.multi.yml up -d
   ```

5. **验证**
   - 检查所有实例健康状态
   - 测试定时任务正常触发

### 10.2 数据兼容性

| 数据 | 迁移影响 | 处理 |
|-----|---------|------|
| `config.json` | 无影响 | 直接使用 |
| `jobs.json` | 无影响 | 直接使用 |
| `sessions/` | 无影响 | 直接使用 |
| `memory/` | 无影响 | 直接使用 |
| `console_push` | 丢失 | 内存数据，重启后重建 |
| `download_tasks` | 丢失 | 内存数据，重启后重建 |
| `jobs_state` | 重置 | 重新加载后重建 |

---

## 11. 容错设计

### 11.1 故障场景处理

| 场景 | 处理方案 |
|-----|---------|
| 实例宕机时持有锁 | 锁 TTL 过期后自动释放（默认10分钟） |
| 任务执行超时 | 锁自动过期，其他实例可接管 |
| Redis 宕机 | Fail-Fast，所有实例跳过任务执行，等待恢复 |
| NAS 不可写 | 任务执行失败，健康检查失败 |
| 锁续期失败 | 立即停止任务执行，释放资源 |
| 惊群效应 | 随机延迟 0-2 秒避免 |

### 11.2 监控指标

| 指标 | 类型 | 说明 |
|-----|------|------|
| `cron_lock_acquire_total` | Counter | 锁获取尝试次数 |
| `cron_lock_acquire_failed` | Counter | 锁获取失败次数 |
| `cron_lock_renewal_total` | Counter | 锁续期次数 |
| `cron_lock_renewal_failed` | Counter | 锁续期失败次数 |
| `cron_job_execution_time` | Histogram | 任务执行耗时 |
| `cron_job_execution_status` | Counter | 任务执行成功/失败数 |
| `redis_connection_status` | Gauge | Redis 连接状态 |
| `nas_write_latency` | Histogram | NAS 写入延迟 |

---

## 12. 测试计划

### 12.1 功能测试

- [ ] 多实例下定时任务正常触发
- [ ] 同一用户任务不会重复执行
- [ ] 不同用户任务并行执行
- [ ] Console Push 消息正常收发
- [ ] 下载任务状态同步正常
- [ ] 会话数据读写正常
- [ ] 锁续期机制正常工作

### 12.2 容错测试

- [ ] 实例宕机后锁自动释放
- [ ] Redis 宕机后 Fail-Fast
- [ ] NAS 断开后恢复自动重连
- [ ] 长时间任务锁续期正常

### 12.3 性能测试

- [ ] 10 个实例并发运行稳定
- [ ] 100 个用户定时任务正常调度
- [ ] 锁获取延迟 < 10ms
- [ ] 惊群效应下无重复执行

---

## 13. 附录

### 13.1 依赖项

```toml
# pyproject.toml 新增依赖
[project.optional-dependencies]
redis = [
    "redis>=5.0.0",
    "portalocker>=2.7.0",
]
```

### 13.2 术语表

| 术语 | 说明 |
|-----|------|
| NAS | Network Attached Storage，网络附加存储 |
| TTL | Time To Live，生存时间 |
| Lua | 轻量级脚本语言，Redis 支持原子操作 |
| APScheduler | Python 定时任务调度库 |
| 惊群效应 | 多个实例同时竞争资源导致性能下降 |

### 13.3 参考文档

- [Redis 分布式锁](https://redis.io/docs/manual/patterns/distributed-locks/)
- [Portalocker 文档](https://github.com/WoLpH/portalocker)
- [APScheduler 文档](https://apscheduler.readthedocs.io/)
- [CoPaw CLAUDE.md](../../CLAUDE.md)

---

## 14. 变更记录

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| v1.0 | 2026-03-22 | 初始版本 |
| v1.1 | 2026-03-22 | 修订版：添加锁续期、文件锁、Redis 存储临时数据、防惊群、健康检查、实例 ID 生成 |

---

**文档状态**: 评审中
**最后更新**: 2026-03-22
