---
name: cron
description: 通过 copaw 命令管理定时任务 - 创建、查询、暂停、恢复、删除、立即执行任务
metadata: { "copaw": { "emoji": "⏰" } }
---

# 定时任务管理

使用 `copaw cron` 命令管理定时任务。任务会在后台按 cron 表达式定时执行，支持发送文本消息或向 Agent 提问。

## 命令概览

| 命令 | 说明 |
|------|------|
| `copaw cron list` | 列出所有定时任务 |
| `copaw cron get <job_id>` | 查看任务详情 |
| `copaw cron state <job_id>` | 查看任务运行状态 |
| `copaw cron create [选项]` | 创建新任务 |
| `copaw cron delete <job_id>` | 删除任务 |
| `copaw cron pause <job_id>` | 暂停任务 |
| `copaw cron resume <job_id>` | 恢复任务 |
| `copaw cron run <job_id>` | 立即执行一次 |

## 全局选项

所有命令都支持以下选项：

- `--user-id <id>`: 指定用户 ID（多用户隔离，默认 `default`）
- `--base-url <url>`: 指定 API 地址（默认使用全局 `--host`/`--port`）

## 创建任务

### 任务类型

- **text**: 定时向频道发送固定文本消息
- **agent**: 定时向 Agent 提问，并将回复发送到频道

### 基本用法

```bash
copaw cron create [选项]
```

### 必填参数

| 参数 | 说明 |
|------|------|
| `--type <text\|agent>` | 任务类型 |
| `--name <名称>` | 任务显示名称 |
| `--cron <表达式>` | cron 表达式（5字段：分 时 日 月 周） |
| `--channel <频道>` | 目标频道：`imessage`/`discord`/`dingtalk`/`qq`/`console` |
| `--target-user <用户>` | 目标用户标识 |
| `--target-session <会话>` | 目标会话标识 |
| `--text <内容>` | 消息内容（text类型）或问题（agent类型） |

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--timezone <时区>` | `Asia/Shanghai` | 时区，如 `UTC`、`America/New_York` |
| `--enabled` / `--no-enabled` | `--enabled` | 是否启用任务 |
| `--mode <stream\|final>` | `final` | `stream`实时发送/`final`只发最终结果 |

### 创建示例

**每天 9:00 发送早安消息：**

```bash
copaw cron create \
  --type text \
  --name "每日早安" \
  --cron "0 9 * * *" \
  --timezone Asia/Shanghai \
  --channel imessage \
  --target-user "user123" \
  --target-session "session456" \
  --text "早上好！今天又是充满活力的一天！"
```

**每 2 小时检查待办事项：**

```bash
copaw cron create \
  --type agent \
  --name "检查待办" \
  --cron "0 */2 * * *" \
  --channel dingtalk \
  --target-user "user123" \
  --target-session "session456" \
  --text "我目前有哪些待办事项？"
```

**创建工作日晚间提醒（禁用状态）：**

```bash
copaw cron create \
  --type text \
  --name "下班提醒" \
  --cron "0 18 * * 1-5" \
  --channel console \
  --target-user "user123" \
  --target-session "session456" \
  --text "该下班了！记得保存工作进度。" \
  --no-enabled
```

### 从 JSON 文件创建

对于复杂配置，先创建 JSON 文件：

```bash
copaw cron create -f job_spec.json
```

**JSON 示例：**

```json
{
  "name": "复杂任务示例",
  "enabled": true,
  "schedule": {
    "type": "cron",
    "cron": "0 9 * * *",
    "timezone": "Asia/Shanghai"
  },
  "task_type": "agent",
  "request": {
    "input": [
      {
        "role": "user",
        "type": "message",
        "content": [{"type": "text", "text": "总结今日新闻"}]
      }
    ],
    "session_id": "session456",
    "user_id": "cron"
  },
  "dispatch": {
    "type": "channel",
    "channel": "console",
    "target": {"user_id": "user123", "session_id": "session456"},
    "mode": "final",
    "meta": {}
  },
  "runtime": {
    "max_concurrency": 1,
    "timeout_seconds": 120,
    "misfire_grace_seconds": 60
  },
  "meta": {}
}
```

## Cron 表达式参考

格式：`分 时 日 月 周`（5个字段）

| 表达式 | 含义 |
|--------|------|
| `0 9 * * *` | 每天 9:00 |
| `30 8 * * 1-5` | 工作日 8:30 |
| `0 */2 * * *` | 每 2 小时 |
| `*/15 * * * *` | 每 15 分钟 |
| `0 0 * * 0` | 每周日零点 |
| `0 12 1 * *` | 每月 1 号 12:00 |

## 任务管理

### 查看任务列表

```bash
copaw cron list
```

多用户环境下指定用户：

```bash
copaw cron list --user-id alice
```

### 查看任务详情

```bash
copaw cron get <job_id>
```

### 查看任务状态

```bash
copaw cron state <job_id>
```

输出示例：

```json
{
  "enabled": true,
  "last_status": "success",
  "last_run_at": "2026-03-18T09:00:00",
  "next_run_at": "2026-03-19T09:00:00",
  "run_count": 5,
  "error_count": 0
}
```

### 暂停与恢复

```bash
# 暂停任务（不再按 schedule 执行）
copaw cron pause <job_id>

# 恢复任务
copaw cron resume <job_id>
```

### 立即执行

忽略 schedule，立即运行一次任务：

```bash
copaw cron run <job_id>
```

### 删除任务

```bash
copaw cron delete <job_id>
```

## 使用建议

1. **创建前确认参数**：如果用户缺少必要参数，询问补充后再创建
2. **查找 job_id**：暂停/删除/恢复前，先用 `copaw cron list` 获取 job_id
3. **排查问题**：用 `copaw cron state <job_id>` 查看任务状态和下次执行时间
4. **时区设置**：建议明确指定 `--timezone`，避免 UTC 转换错误
5. **给用户的命令要完整**：确保用户可以直接复制执行
