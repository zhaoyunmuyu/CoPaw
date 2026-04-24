## Zhaohu Intent Recognition

### Feature: Intent-based Message Routing

**Description:**
使用外部意图识别接口区分任务分配和闲聊消息，替代原有的文本长度判断逻辑。

**Configuration:**

| 环境变量 | 必填 | 默认值 | 说明 |
|---------|-----|-------|------|
| `SWE_ZHAOHU_INTENT_URL` | 是 | - | 意图识别接口 URL |
| `SWE_ZHAOHU_INTENT_OPEN_ID` | 是 | - | 意图识别接口 openId |
| `SWE_ZHAOHU_INTENT_API_KEY` | 是 | - | 意图识别接口 API-Key |

**Note:** OAuth 配置项 `SWE_ZHAOHU_CLIENT_SECRET` 已更名为 `SWE_ZHAOHU_CLIENT_SECRET_POSEIDON`。

**Routing Logic:**

```
if text in TASK_PROGRESS_KEYWORDS:
    → Case 1: Task Progress Query
elif len(text) <= 5:
    → Case 3: Casual Chat
elif intent_api returns "是":
    → Case 2: Task Assignment
else:
    → Case 3: Casual Chat
```

**Case 2 Behavior:**
- Session ID: `resolve_session_id(sap_id, meta)` (same as Case 3)
- Sends card notification before LLM processing
- Uses standard LLM flow (`get_llm_response`)

**API Specification:**

```http
POST ${SWE_ZHAOHU_INTENT_URL}
Headers:
  Content-Type: application/json
  API-Key: ${SWE_ZHAOHU_INTENT_API_KEY}

Body:
{
  "inputParams": {
    "question": "用户输入文本"
  },
  "openId": "${SWE_ZHAOHU_INTENT_OPEN_ID}"
}

Response:
{
  "returnCode": "SUC0000",
  "errorMsg": null,
  "body": {
    "output": {
      "result": "是" | "否"
    }
  }
}
```

**Error Handling:**
- API call failure → default to Case 3 (Casual Chat)
- Missing configuration → log warning, default to Case 3
- Non-success returnCode → log warning, default to Case 3