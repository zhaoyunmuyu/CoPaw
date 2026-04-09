# CoPaw 实例管理功能设计文档

## 1. 目标与范围

本方案的目标是为 CoPaw 提供多实例管理能力，支持：

> 用户可被分配到不同的服务实例，系统自动进行负载均衡，支持实例的创建、更新、删除和用户迁移。

### 1.1 功能范围

**本期实现：**
- 实例管理（CRUD）
- 用户分配（自动负载均衡 / 手动指定）
- 用户迁移（跨实例）
- 操作日志记录
- 使用率统计与告警

**本期不实现：**
- 实例健康检查
- 自动扩缩容
- 实例间数据同步
- 用户数据迁移

---

## 2. 核心概念

### 2.1 数据模型

```
┌─────────────────────────────────────────────────────────────┐
│                      Source (来源)                          │
│  - source_id: 来源标识                                       │
│  - source_name: 来源名称                                     │
│  - 统计: 实例数、用户数、活跃实例数                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ 1:N
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Instance (实例)                          │
│  - instance_id: 实例标识                                     │
│  - source_id: 所属来源                                       │
│  - instance_name: 实例名称                                   │
│  - instance_url: 实例访问地址                                │
│  - max_users: 最大用户数                                     │
│  - status: active / inactive                                │
│  - 使用率: current_users, usage_percent, warning_level      │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ 1:N
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 UserAllocation (用户分配)                    │
│  - user_id: 用户标识                                         │
│  - source_id: 来源标识                                       │
│  - instance_id: 分配的实例                                   │
│  - status: active / migrated                                │
│  - allocated_at: 分配时间                                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 状态枚举

| 枚举类型 | 值 | 说明 |
|---------|---|------|
| InstanceStatus | `active` | 实例正常运行，可接受新用户 |
| InstanceStatus | `inactive` | 实例已停用，不接受新用户 |
| UserAllocationStatus | `active` | 用户当前活跃分配 |
| UserAllocationStatus | `migrated` | 用户已迁移到其他实例 |

### 2.3 告警级别

使用率计算公式：`usage_percent = current_users / max_users * 100`

| 级别 | 条件 | 说明 |
|-----|------|------|
| `normal` | usage < 80% | 正常状态 |
| `warning` | 80% ≤ usage < 100% | 警告状态，建议扩容 |
| `critical` | usage ≥ 100% | 临界状态，已达上限 |

---

## 3. 架构设计

### 3.1 模块结构

```
src/copaw/app/instance/
├── __init__.py      # 模块导出
├── models.py        # 数据模型定义
├── store.py         # 数据库存储层
├── service.py       # 业务逻辑层
└── router.py        # API 路由层
```

### 3.2 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Router Layer                             │
│  - HTTP 端点定义                                            │
│  - 请求验证                                                 │
│  - 响应格式化                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                            │
│  - 业务逻辑封装                                             │
│  - 操作日志记录                                             │
│  - 负载均衡算法                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Store Layer                              │
│  - 数据库 CRUD                                              │
│  - SQL 查询封装                                             │
│  - 事务管理                                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database (MySQL/TDSQL)                   │
│  - swe_instance_info                                        │
│  - swe_instance_user                                        │
│  - swe_instance_log                                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 与现有系统集成

实例管理模块复用现有 Tracing 模块的数据库连接：

```python
# router.py
def init_instance_module(db=None):
    if db is None:
        from ...tracing import get_trace_manager
        trace_manager = get_trace_manager()
        if trace_manager._store and trace_manager._store._db:
            db = trace_manager._store._db
    _store = InstanceStore(db)
```

---

## 4. 数据库设计

### 4.1 表结构

#### swe_instance_info (实例信息表)

```sql
CREATE TABLE swe_instance_info (
    instance_id VARCHAR(64) PRIMARY KEY,
    source_id VARCHAR(64) NOT NULL,
    bbk_id VARCHAR(64),
    instance_name VARCHAR(128) NOT NULL,
    instance_url VARCHAR(512) NOT NULL,
    max_users INT DEFAULT 100,
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_source_id (source_id),
    INDEX idx_status (status)
);
```

#### swe_instance_user (用户分配表)

```sql
CREATE TABLE swe_instance_user (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    instance_id VARCHAR(64) NOT NULL,
    allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('active', 'migrated') DEFAULT 'active',
    UNIQUE KEY uk_user_source (user_id, source_id),
    INDEX idx_instance_id (instance_id),
    INDEX idx_source_id (source_id),
    FOREIGN KEY (instance_id) REFERENCES swe_instance_info(instance_id)
);
```

#### swe_instance_log (操作日志表)

```sql
CREATE TABLE swe_instance_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    action VARCHAR(64) NOT NULL,
    target_type ENUM('source', 'instance', 'user') NOT NULL,
    target_id VARCHAR(128) NOT NULL,
    old_value JSON,
    new_value JSON,
    operator VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_action (action),
    INDEX idx_target (target_type, target_id),
    INDEX idx_created_at (created_at)
);
```

### 4.2 索引策略

| 表 | 索引 | 用途 |
|---|------|------|
| swe_instance_info | `idx_source_id` | 按来源查询实例 |
| swe_instance_info | `idx_status` | 查询活跃实例 |
| swe_instance_user | `uk_user_source` | 查询用户分配（主查询） |
| swe_instance_user | `idx_instance_id` | 统计实例用户数 |
| swe_instance_log | `idx_target` | 查询操作历史 |

---

## 5. API 设计

### 5.1 端点列表

| 方法 | 路径 | 说明 |
|-----|------|------|
| GET | `/api/instance/overview` | 获取统计概览 |
| GET | `/api/instance/sources` | 获取来源列表 |
| GET | `/api/instance/instances` | 获取实例列表 |
| GET | `/api/instance/instances/{id}` | 获取实例详情 |
| POST | `/api/instance/instances` | 创建实例 |
| PUT | `/api/instance/instances/{id}` | 更新实例 |
| DELETE | `/api/instance/instances/{id}` | 删除实例 |
| GET | `/api/instance/user-ids` | 获取用户 ID 列表 |
| GET | `/api/instance/allocations` | 获取分配列表 |
| GET | `/api/instance/allocations/url` | 获取用户实例 URL |
| POST | `/api/instance/allocations` | 分配用户 |
| POST | `/api/instance/allocations/migrate` | 迁移用户 |
| DELETE | `/api/instance/allocations` | 删除分配 |
| GET | `/api/instance/logs` | 获取操作日志 |

### 5.2 请求/响应示例

#### 创建实例

```http
POST /api/instance/instances
Content-Type: application/json

{
    "instance_id": "inst-001",
    "source_id": "source-001",
    "instance_name": "华东实例 1",
    "instance_url": "https://east-1.copaw.example.com",
    "max_users": 200
}
```

响应：
```json
{
    "success": true,
    "data": {
        "instance_id": "inst-001",
        "source_id": "source-001",
        "instance_name": "华东实例 1",
        "instance_url": "https://east-1.copaw.example.com",
        "max_users": 200,
        "status": "active",
        "created_at": "2026-04-08T08:00:00Z"
    }
}
```

#### 分配用户（自动负载均衡）

```http
POST /api/instance/allocations
Content-Type: application/json

{
    "user_id": "user-12345",
    "source_id": "source-001"
}
```

响应：
```json
{
    "success": true,
    "user_id": "user-12345",
    "source_id": "source-001",
    "instance_id": "inst-001",
    "instance_name": "华东实例 1",
    "instance_url": "https://east-1.copaw.example.com",
    "message": "分配成功"
}
```

#### 迁移用户

```http
POST /api/instance/allocations/migrate
Content-Type: application/json

{
    "user_id": "user-12345",
    "source_id": "source-001",
    "target_instance_id": "inst-002"
}
```

---

## 6. 负载均衡策略

### 6.1 自动分配算法

当用户请求分配但未指定实例时，系统自动选择最优实例：

```python
async def allocate_user(self, request):
    # 1. 获取该来源下所有活跃实例
    instances = await store.get_available_instances(source_id)

    # 2. 过滤掉已达阈值的实例
    available = [i for i in instances if i.current_users < i.max_users]

    # 3. 选择剩余容量最大的实例 (Best Fit)
    instance = max(available, key=lambda x: x.max_users - x.current_users)

    return instance
```

**算法选择理由：**
- 选择剩余容量最大的实例，可使各实例负载相对均匀
- 避免频繁触发实例阈值告警
- 为突发流量预留缓冲空间

### 6.2 手动分配

用户可指定目标实例 ID：

```python
# 验证实例存在且属于该来源
instance = await store.get_instance_with_usage(instance_id)
if instance.source_id != source_id:
    raise ValueError("实例不属于该来源")

# 检查是否已达阈值
if instance.current_users >= instance.max_users:
    return AllocateUserResponse(success=False, message="实例已达阈值")
```

---

## 7. 错误处理

### 7.1 错误码

| HTTP 状态码 | 错误场景 |
|------------|---------|
| 400 | 实例已存在 / 不存在 / 参数校验失败 |
| 400 | 用户已分配 / 未分配 / 实例不属于该来源 |
| 400 | 实例已达阈值 / 无可用实例 / 有用户无法删除 |
| 404 | 实例不存在 / 分配记录不存在 |

### 7.2 业务错误消息

```python
# 实例相关
"实例 {instance_id} 已存在"
"实例 {instance_id} 不存在"
"该实例下存在用户分配，无法删除"

# 分配相关
"用户已分配到实例 {instance_id}"
"用户未分配实例"
"实例不属于该来源"
"实例已达阈值，请选择其他实例或扩容"
"该来源无可用实例，请先添加实例"
"所有实例已达阈值，请扩容"

# 迁移相关
"目标实例 {instance_id} 不存在"
"目标实例不可用"
"目标实例不属于该来源"
"目标实例已达阈值"
```

---

## 8. 操作日志

### 8.1 日志类型

| Action | Target Type | 说明 |
|--------|------------|------|
| `create_instance` | instance | 创建实例 |
| `update_instance` | instance | 更新实例 |
| `delete_instance` | instance | 删除实例 |
| `allocate` | user | 分配用户 |
| `migrate` | user | 迁移用户 |
| `delete_allocation` | user | 删除分配 |

### 8.2 日志记录格式

```python
await store.create_log(
    action="allocate",
    target_type="user",
    target_id="user-12345",
    old_value=None,
    new_value={
        "source_id": "source-001",
        "instance_id": "inst-001",
    },
    operator="admin",
)
```

---

## 9. 前端集成

### 9.1 API 模块

前端 API 封装位于 `console/src/api/modules/instance.ts`：

```typescript
export const instanceApi = {
  // 概览
  getOverview: () => request<OverviewStats>("/instance/overview"),

  // 实例管理
  getInstances: (filters) => request("/instance/instances", { params: filters }),
  createInstance: (data) => request("/instance/instances", { method: "POST", body: data }),

  // 用户分配
  allocateUser: (data) => request("/instance/allocations", { method: "POST", body: data }),
  migrateUser: (data) => request("/instance/allocations/migrate", { method: "POST", body: data }),
};
```

### 9.2 使用示例

```typescript
// 自动分配用户
const result = await instanceApi.allocateUser({
  user_id: "user-12345",
  source_id: "source-001",
});

if (result.success) {
  console.log(`用户已分配到: ${result.instance_url}`);
}
```

---

## 10. 测试覆盖

### 10.1 单元测试

测试文件：`tests/unit/app/test_instance.py`

| 测试类 | 覆盖内容 | 测试数 |
|-------|---------|-------|
| TestCalculateWarningLevel | 告警级别计算 | 4 |
| TestModels | 数据模型验证 | 7 |
| TestInstanceStore | 存储层（无数据库） | 9 |
| TestInstanceStoreWithMockDb | 存储层（模拟数据库） | 7 |
| TestInstanceService | 业务逻辑层 | 14 |
| TestRouter | API 路由层 | 8 |

### 10.2 运行测试

```bash
python -m pytest tests/unit/app/test_instance.py -v
```

---

## 11. 扩展预留

### 11.1 未来功能

以下功能在当前版本未实现，但架构已预留扩展点：

1. **实例健康检查**
   - 定时探测实例可用性
   - 自动摘除故障实例
   - 路由流量切换

2. **自动扩缩容**
   - 基于使用率自动创建实例
   - 低负载实例自动合并
   - 成本优化策略

3. **用户数据迁移**
   - 迁移用户时同步历史数据
   - 会话、配置、记忆迁移
   - 迁移进度跟踪

4. **多区域部署**
   - 跨地域实例管理
   - 就近访问策略
   - 灾备切换

### 11.2 扩展接口

```python
# 预留的健康检查接口
class InstanceHealthChecker:
    async def check_health(self, instance_id: str) -> HealthStatus:
        pass

# 预留的扩缩容接口
class InstanceScaler:
    async def scale_up(self, source_id: str) -> Instance:
        pass

    async def scale_down(self, instance_id: str) -> bool:
        pass
```

---

## 12. 部署注意事项

### 12.1 数据库初始化

在部署前需创建相关数据库表：

```bash
# 执行建表 SQL
mysql -u root -p copaw < scripts/sql/instance_tables.sql
```

### 12.2 环境变量

实例管理模块依赖 Tracing 模块的数据库配置：

```bash
TRACING_DB_HOST=localhost
TRACING_DB_PORT=3306
TRACING_DB_USER=copaw
TRACING_DB_PASSWORD=secret
TRACING_DB_NAME=copaw
```

### 12.3 无数据库运行

当数据库不可用时，实例管理模块可正常运行，但所有操作返回空数据：

```python
# store.py
async def get_instances(self, ...):
    if not self._use_db:
        return []  # 无数据库时返回空列表
```

---

## 13. 版本历史

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| 1.0.0 | 2026-04-08 | 初始版本，支持实例管理、用户分配、迁移功能 |
