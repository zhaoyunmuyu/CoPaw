## Summary

优化招乎渠道的消息路由逻辑，引入意图识别接口来区分任务分配和闲聊消息，而非仅依赖文本长度判断。

## Motivation

当前招乎渠道通过简单的文本长度判断（>10字符为任务，<=10字符为闲聊）来区分消息类型。这种方式存在以下问题：
1. 判断规则过于简单，无法准确识别用户意图
2. 短文本任务（如"帮我查报表"）可能被误判为闲聊
3. 长文本闲聊可能被误判为任务，导致不必要的卡片通知

## Proposal

引入外部意图识别接口，通过 AI 识别用户消息的真实意图：

1. **判断规则优化**：
   - 文本长度 <= 5 → 直接判定为闲聊（Case 3）
   - 文本长度 > 5 → 调用意图识别接口判断
     - 返回"是" → 任务分配（Case 2）
     - 返回"否"或接口失败 → 闲聊（Case 3）

2. **Case 2 处理优化**：
   - 使用与 Case 3 相同的 sessionId（回调 session）
   - 区别仅在于发送卡片通知
   - 不再新建独立的任务 session

## Impact

- **channel.py**: 新增 `_check_intent` 方法，修改 `_route_message` 和 `_handle_task_assignment`
- **config.py**: 新增 `intent_url`、`intent_open_id`、`intent_api_key` 配置字段
- **prd.json**: 新增 `SWE_ZHAOHU_INTENT_URL`、`SWE_ZHAOHU_INTENT_OPEN_ID`、`SWE_ZHAOHU_INTENT_API_KEY` 环境变量

## Tasks

- [x] 新增 `_check_intent` 方法调用意图识别接口
- [x] 修改 `_route_message` 判断逻辑
- [x] 修改 `_handle_task_assignment` 使用回调 session
- [x] 新增配置字段和环境变量