# CoPaw Shell 脚本备份接口设计文档

## 1. 目标与范围

本方案的目标是创建一个独立的 Shell 脚本备份接口，与原有的 Python zipfile 备份接口并存。

> 用户可通过 `/backup/shell/upload` 和 `/backup/shell/download` 接口使用 Shell 脚本进行备份和恢复，系统调用 Linux Shell 脚本打包用户文件，上传到 OSS 后自动清理本地临时文件。

### 1.1 功能范围

**本期实现：**
- 独立的 Shell 脚本备份接口 `/backup/shell/upload`
- 独立的 Shell 脚本恢复接口 `/backup/shell/download`
- 支持指定租户备份/恢复（通过 `tenant_ids` 参数）
- 支持设置实例标识（通过 `instance_id` 参数）
- 配置化的脚本路径和参数
- 自动清理本地压缩文件
- 回滚备份支持（恢复前创建备份）

**本期不实现：**
- 增量备份（仅全量备份）
- Windows 平台支持（仅 Linux/Unix）
- 与原有 Python 备份接口的合并

---

## 2. 接口设计

### 2.1 API 端点

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | `/api/backup/shell/upload` | 创建 Shell 备份任务 |
| POST | `/api/backup/shell/download` | 创建 Shell 恢复任务 |
| GET | `/api/backup/shell/tasks` | 查询任务列表 |
| GET | `/api/backup/shell/tasks/{task_id}` | 查询任务详情 |
| GET | `/api/backup/shell/list` | 列出可用备份 |

### 2.2 与原有接口对比

| 特性 | Python 备份 (`/backup/upload`) | Shell 备份 (`/backup/shell/upload`) |
|-----|-------------------------------|-----------------------------------|
| 压缩方式 | Python zipfile | Shell 脚本 + zip 命令 |
| 平台支持 | Windows/Linux | 仅 Linux |
| 执行效率 | 中等 | 高（批量处理） |
| 接口路径 | `/backup/upload` | `/backup/shell/upload` |

### 2.3 配置模型

```
┌─────────────────────────────────────────────────────────────┐
│                 ShellScriptConfig                           │
│  - compress_script_path: compress.sh 脚本路径               │
│  - decompress_script_path: decompress.sh 脚本路径           │
│  - timeout_seconds: 脚本执行超时                            │
│  - working_dir: 用户工作目录                                │
│  - secret_dir: 密钥目录                                     │
└─────────────────────────────────────────────────────────────┘

默认脚本路径：
/opt/deployments/app/src/scripts/backup/compress.sh
/opt/deployments/app/src/scripts/backup/decompress.sh
```

---

## 3. 模块结构

```
src/swe/app/backup/
├── config.py          # ShellScriptConfig 配置模型
├── router.py          # 原有 Python 备份路由（不变）
├── service.py         # 原有 Python 备份服务（不变）
├── worker.py          # 原有 Python 备份 worker（不变）
├── shell_router.py    # 新增：Shell 备份 API 路由
├── shell_service.py   # 新增：Shell 备份服务
├── shell_worker.py    # 新增：Shell 备份 worker
├── s3_client.py       # 复用：S3/OSS 客户端
├── models.py          # 复用：BackupTask 模型
└── task_store.py      # 复用：任务存储

scripts/backup/
├── compress.sh        # 压缩脚本
└── decompress.sh      # 解压脚本
```

---

## 4. Shell 脚本设计

### 4.1 compress.sh

默认路径：`/opt/deployments/app/src/scripts/backup/compress.sh`

支持参数：
- `--working-dir DIR`: 工作目录
- `--secret-dir DIR`: 密钥目录
- `--output-dir DIR`: 输出目录
- `--tenants LIST`: 指定租户（逗号分隔）
- `--date DATE`: 备份日期 YYYY-MM-DD
- `--hour HOUR`: 备份小时 0-23
- `--instance-id ID`: 实例标识

输出格式：
```
SUCCESS:tenant_id:/path/to/tenant_id.zip
OUTPUT_DIR:/tmp/backup_xxx
```

### 4.2 decompress.sh

默认路径：`/opt/deployments/app/src/scripts/backup/decompress.sh`

支持参数：
- `--zip-dir DIR`: zip 文件目录
- `--working-dir DIR`: 目标工作目录
- `--secret-dir DIR`: 目标密钥目录
- `--tenants LIST`: 指定租户
- `--rollback-dir DIR`: 回滚备份目录
- `--task-id ID`: 任务 ID

输出格式：
```
ROLLBACK:tenant_id:/path/to/rollback/tenant_id.zip
SUCCESS:tenant_id
```

---

## 5. API 请求/响应示例

### 5.1 创建备份

```http
POST /api/backup/shell/upload
Content-Type: application/json

{
    "tenant_ids": ["alice", "bob"],
    "instance_id": "inst-001"
}
```

响应：
```json
{
    "task_id": "abc123",
    "status": "pending",
    "task_type": "backup",
    "message": "Shell backup task created successfully",
    "target_tenants": ["alice", "bob"],
    "created_at": "2026-04-22T10:00:00Z",
    "instance_id": "inst-001"
}
```

### 5.2 创建恢复

```http
POST /api/backup/shell/download
Content-Type: application/json

{
    "date": "2026-04-22",
    "hour": 10,
    "instance_id": "inst-001",
    "tenant_ids": ["alice"]
}
```

---

## 6. 环境变量配置

| 变量 | 说明 | 默认值 |
|-----|------|--------|
| `SWE_BACKUP_COMPRESS_SCRIPT` | compress.sh 路径 | `/opt/deployments/app/src/scripts/backup/compress.sh` |
| `SWE_BACKUP_DECOMPRESS_SCRIPT` | decompress.sh 路径 | `/opt/deployments/app/src/scripts/backup/decompress.sh` |
| `SWE_BACKUP_SCRIPT_TIMEOUT` | 脚本超时（秒） | `600` |
| `SWE_BACKUP_SCRIPT_WORKING_DIR` | 工作目录 | 使用 WORKING_DIR 常量 |
| `SWE_BACKUP_SCRIPT_SECRET_DIR` | 密钥目录 | 使用 SECRET_DIR 常量 |

OSS 配置复用原有备份模块的环境变量：
- `SWE_BACKUP_AWS_ACCESS_KEY_ID`
- `SWE_BACKUP_AWS_SECRET_ACCESS_KEY`
- `SWE_BACKUP_S3_BUCKET`
- `SWE_BACKUP_ENDPOINT_URL`

---

## 7. 部署注意事项

### 7.1 脚本安装

```bash
# 脚本默认路径
mkdir -p /opt/deployments/app/src/scripts/backup

# 复制脚本
cp scripts/backup/compress.sh /opt/deployments/app/src/scripts/backup/
cp scripts/backup/decompress.sh /opt/deployments/app/src/scripts/backup/

# 设置执行权限
chmod +x /opt/deployments/app/src/scripts/backup/*.sh
```

### 7.2 平台限制

- Shell 备份接口仅支持 Linux/Unix 平台
- Windows 平台调用会返回 400 错误
- 原有 Python 备份接口仍可用于 Windows

---

## 8. 测试验证

### 8.1 手动测试步骤

1. 确保脚本已安装并具有执行权限
2. 设置 OSS 环境变量
3. 调用 `POST /api/backup/shell/upload`
4. 查看日志确认脚本执行
5. 检查 OSS 存储确认上传
6. 调用 `POST /api/backup/shell/download`
7. 验证文件恢复正确

### 8.2 API 测试

```bash
# 创建备份
curl -X POST http://localhost:8088/api/backup/shell/upload \
  -H "Content-Type: application/json" \
  -d '{"tenant_ids": ["test_user"]}'

# 查看任务
curl http://localhost:8088/api/backup/shell/tasks/{task_id}
```

---

## 9. 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/swe/app/backup/config.py` | 修改 | 新增 ShellScriptConfig |
| `src/swe/app/backup/shell_router.py` | 新增 | Shell 备份 API 路由 |
| `src/swe/app/backup/shell_service.py` | 新增 | Shell 备份服务 |
| `src/swe/app/backup/shell_worker.py` | 新增 | Shell 备份 worker |
| `src/swe/app/routers/__init__.py` | 修改 | 注册 shell_router |
| `scripts/backup/compress.sh` | 新增 | 压缩脚本 |
| `scripts/backup/decompress.sh` | 新增 | 解压脚本 |

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| 1.0.0 | 2026-04-22 | 初始版本，独立 Shell 备份接口 |