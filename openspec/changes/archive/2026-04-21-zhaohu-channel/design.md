## Context

zhaohu 渠道是招商银行内部的即时通讯集成渠道，核心文件位于 `src/swe/app/channels/zhaohu/channel.py`。

### 渠道架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Zhaohu 平台   │────▶│  Callback API   │────▶│  ZhaohuChannel  │
│  (用户消息推送)  │     │ /zhaohu/callback│     │   (消息处理)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Zhaohu 平台   │◀────│   Push URL      │◀────│    LLM/Agent    │
│  (消息接收展示)  │     │  (消息推送)     │     │   (响应生成)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 用户身份体系

zhaohu 渠道涉及三种用户标识：

| 标识 | 来源 | 用途 |
|------|------|------|
| `openId` | Zhaohu 平台 | 回调消息中的发送者标识 |
| `sapId` | 企业 HR 系统 | 员工编号，用于租户隔离和用户上下文 |
| `ystId` | YST 系统 | 消息推送的目标地址 |

转换流程：
```
回调消息 openId → user_query_url 查询 → 获取 sapId + ystId
                                        ↓
                                   sapId 用于租户上下文
                                   ystId 用于消息推送
```

### 配置项

| 配置项 | 环境变量 | 说明 |
|--------|----------|------|
| `push_url` | `ZHAOHU_PUSH_URL` | 消息推送 URL |
| `user_query_url` | `ZHAOHU_USER_QUERY_URL` | 用户身份查询 URL |
| `oauth_url` | `ZHAOHU_OAUTH_URL` | OAuth 认证 URL |
| `custom_card_url` | `ZHAOHU_CUSTOM_CARD_URL` | 自定义卡片发送 URL |
| `sys_id` | `ZHAOHU_SYS_ID` | 系统标识 |
| `robot_open_id` | `ZHAOHU_ROBOT_OPEN_ID` | 机器人 OpenId |
| `cron_task_menu_id` | `ZHAOHU_CRON_TASK_MENU_ID` | Claw 跳转菜单 ID |
| `extract_url` | `ZHAOHU_EXTRACT_URL` | 姓名提取服务 URL |

## Goals / Non-Goals

**Goals:**
- 完整记录 zhaohu 渠道架构设计
- 三种 Case 处理流程清晰定义
- Case 2 优化为非流式处理，完成后发送完整结果
- OAuth 认证机制、消息脱敏机制设计文档

**Non-Goals:**
- 不修改其他渠道的实现
- 不修改 Console 前端的 session 加载逻辑
- 不添加实时推送通知机制（用户需点击卡片跳转查看）

## Decisions

### Decision 1: 三种 Case 路由策略

根据消息内容长度和关键词进行路由：

| Case | 判断条件 | 处理方式 |
|------|----------|----------|
| Case 1 | 消息 == 任务进度关键词 | 直接查询 CronManager，发送卡片 |
| Case 2 | 消息长度 > 10 字符 | 发送卡片 + 后台处理 + 完成后发送结果 |
| Case 3 | 消息长度 <= 10 字符 | 流式处理，实时回复 |

关键词列表：`我的任务进度`、`任务进度`、`查看任务进度`

### Decision 2: Case 2 非流式处理

**选择**: 使用 `_run_task_llm_and_notify` 直接处理，不使用 `_consume_with_tracker`

**理由**:
- 任务场景用户期望收到完整结果，而非流式碎片
- 减少 TaskTracker 介入，简化处理流程
- 卡片通知让用户知道任务已受理，避免长时间无反馈

**处理流程**:
```
收到长文本消息
    ↓
生成任务 session_id: zhaohu:task:{sapId}:{uuid}
    ↓
立即发送"任务已发起"卡片（Template 1）
    ↓
后台异步运行 LLM
    ↓
完成后发送完整结果
```

### Decision 3: Case 3 流式处理

**选择**: 使用 `_consume_with_tracker` 流式处理

**理由**:
- 闲聊场景需要实时反馈，用户体验更好
- 流式处理支持 Console 前端同步展示
- 符合对话交互的自然体验

### Decision 4: OAuth Token 缓存

**选择**: 内存缓存 OAuth Token，90 分钟有效期

**理由**:
- 减少认证请求次数，提高响应速度
- 90 分钟足够覆盖大部分工作场景
- Token 失效时自动刷新

### Decision 5: 消息脱敏

**选择**: 发送前对响应文本进行敏感信息脱敏

**脱敏规则**:
| 类型 | 规则 |
|------|------|
| 姓名 | `张三` → `张**`（通过 extract_url 服务识别） |
| 身份证 | 前3位 + 11个* + 后4位 |
| 银行卡 | 前4位 + 中间* + 后4位 |
| 手机号 | 前3位 + 4个* + 后4位 |
| 座机号 | 区号 + 中间* + 后4位 |

### Decision 6: 卡片模板

**Template 1 - 任务发起通知**:
```json
[
  {"type": "content", "list": [{"content": "任务【{task}】已发起...", "style": 5}]},
  {"type": "content", "list": [{"type": [3], "content": "点击跳转...", "link": {"pcUrl": claw_url}}]}
]
```

**Template 2 - 任务进度查询**:
```json
[
  {"type": "title", "content": "今日任务进度(N)"},
  {"type": "container", "list": [任务1状态, 任务2状态, ...]}
]
```

**Claw URL 构造**:
```
CMBMobileOA:///?pcSysId={sys_id}&pcParams={base64(base64(json({to, queryParam})))}
```

### Decision 7: 消息去重

**选择**: 内存缓存已处理消息 ID，5 分钟 TTL

**理由**:
- 防止网络重试导致的重复处理
- 5 分钟足够覆盖回调重试周期
- 内存缓存简单高效

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Case 2 处理时间较长时用户无反馈 | 卡片通知告知任务已发起，用户可点击跳转查看 |
| Case 2 处理失败时用户无感知 | `_run_task_llm_and_notify` 捕获异常并发送错误通知 |
| OAuth Token 失效导致卡片发送失败 | 自动刷新机制，失败时记录日志 |
| 用户身份查询失败 | 使用 openId 作为 fallback，记录警告日志 |
| 消息推送失败 | 记录日志，不阻塞处理流程 |
| 消息脱敏遗漏敏感信息 | 多层脱敏规则，覆盖常见敏感信息类型 |

## Session ID 格式

| 场景 | Session ID 格式 | 说明 |
|------|-----------------|------|
| Case 1/3 | `zhaohu:callback:{sapId}` | 同一用户共享 session，保持对话上下文 |
| Case 2 | `zhaohu:task:{sapId}:{uuid}` | 每个任务独立 session，避免干扰对话历史 |

## API 接口

### Callback 接口

```
POST /api/zhaohu/callback

Request Body:
{
  "msgId": "消息唯一标识",
  "fromId": "发送者 openId",
  "toId": "接收者 openId（机器人）",
  "groupId": "群组 ID（可选）",
  "groupName": "群组名称（可选）",
  "msgType": "消息类型",
  "msgContent": "消息内容",
  "timestamp": 1234567890
}

Response:
{"code": "ok", "message": "received"}
```

### 消息推送

```
POST {push_url}

Request Body:
{
  "baseInfo": {
    "sysId": "系统标识",
    "channel": "ZH",
    "robotOpenId": "机器人 openId",
    "sendAddrs": [{"sendAddr": "ystId", "sendPk": "发送主键"}],
    "net": "DMZ"
  },
  "msgContent": {
    "summary": "消息摘要",
    "pushContent": "推送内容",
    "message": [{"type": "txt", "value": [{"type": "txt", "text": "消息内容"}]}]
  }
}
```