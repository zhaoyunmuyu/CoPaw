## Context

招乎渠道的消息路由逻辑需要区分三种消息类型：
- **Case 1**: 任务进度查询（关键词匹配）
- **Case 2**: 任务分配（用户描述具体任务）
- **Case 3**: 闲聊（普通对话）

当前实现使用文本长度简单判断 Case 2 和 Case 3，无法准确识别用户意图。

## Goals / Non-Goals

**Goals:**
- 引入意图识别接口准确区分任务分配和闲聊
- 保持 Case 2 和 Case 3 使用相同的 sessionId（回调 session）
- Case 2 的唯一区别是发送卡片通知
- 接口失败时降级为闲聊处理

**Non-Goals:**
- 修改 Case 1（任务进度查询）的处理逻辑
- 修改定时任务的创建或执行逻辑

## Decisions

### Decision 1: 意图识别接口调用时机

**Choice:** 文本长度 > 5 时调用意图识别接口；<= 5 直接判定为闲聊。

**Rationale:**
- 过短的文本（<= 5 字符）通常不包含完整的任务描述
- 减少不必要的 API 调用
- 5 字符阈值足够过滤简单的问候语和确认词

**Alternatives considered:**
- 所有文本都调用接口：增加不必要的 API 负载
- 保持原有的 10 字符阈值：无法解决短任务识别问题

### Decision 2: 接口失败降级策略

**Choice:** 接口调用失败时默认为闲聊（Case 3）。

**Rationale:**
- 降级为闲聊更安全，不会发送错误的卡片通知
- 用户可以通过继续对话完成任务，体验不受影响
- 避免"假任务"卡片干扰用户

**Alternatives considered:**
- 失败时默认为任务：可能导致大量误发的卡片通知
- 失败时重试：增加延迟，影响用户体验

### Decision 3: Case 2 与 Case 3 的 sessionId 统一

**Choice:** Case 2 使用 `resolve_session_id(sap_id, meta)` 生成 sessionId，与 Case 3 相同。

**Rationale:**
- 保持对话上下文连续性
- 用户在同一 session 中可以继续讨论任务
- 减少独立的任务 session 数量

**Alternatives considered:**
- 保持原有独立的任务 session：增加 session 管理复杂度，对话上下文不连续

### Decision 4: 卡片通知仅在 Case 2 发送

**Choice:** Case 2 发送"任务已发起"卡片通知，Case 3 不发送。

**Rationale:**
- 卡片通知提醒用户任务正在处理
- 闲聊场景不需要卡片通知
- 保持最小化差异原则

## Implementation Details

### 意图识别接口规范

**请求格式：**
```bash
curl --location --request POST '${SWE_ZHAOHU_INTENT_URL}' \
--header 'API-Key: ${SWE_ZHAOHU_INTENT_API_KEY}' \
--header 'Content-Type: application/json' \
--data-raw '{
    "inputParams": {"question":"用户输入文本"},
    "openId": "${SWE_ZHAOHU_INTENT_OPEN_ID}"
}'
```

**响应格式：**
```json
{
    "returnCode": "SUC0000",
    "errorMsg": null,
    "body": {
        "output": {
            "result": "是"  // 或 "否"
        }
    }
}
```

### 配置新增

| 环境变量 | 配置字段 | 说明 |
|---------|---------|------|
| `SWE_ZHAOHU_INTENT_URL` | `intent_url` | 意图识别接口 URL |
| `SWE_ZHAOHU_INTENT_OPEN_ID` | `intent_open_id` | 意图识别接口 openId |
| `SWE_ZHAOHU_INTENT_API_KEY` | `intent_api_key` | 意图识别接口 API-Key |

**Note:** OAuth 配置项 `SWE_ZHAOHU_CLIENT_SECRET` 已更名为 `SWE_ZHAOHU_CLIENT_SECRET_POSEIDON`。

### 代码修改位置

| 文件 | 修改内容 |
|-----|---------|
| `channel.py` | 新增 `_check_intent` 方法 |
| `channel.py` | 修改 `_route_message` 判断逻辑 |
| `channel.py` | 修改 `_handle_task_assignment` 方法 |
| `config.py` | 新增 `ZhaohuConfig` 配置字段 |
| `prd.json` | 新增环境变量定义 |