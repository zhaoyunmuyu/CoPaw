## ADDED Requirements

### Requirement: Channel Architecture
zhaohu 渠道 SHALL 支持双向通信：
- 入站：接收 Zhaohu 平台的回调消息
- 出站：通过招行推送 URL 发送回复消息

#### Scenario: Receive callback message
- **WHEN** Zhaohu 平台推送消息到 `/api/zhaohu/callback`
- **THEN** 系统接收消息并返回 `{"code": "ok", "message": "received"}`
- **AND** 系统在后台异步处理消息

#### Scenario: Send reply message
- **WHEN** 系统需要向用户发送回复
- **THEN** 系统通过 `push_url` 发送消息
- **AND** 消息内容包含系统标识、机器人标识、目标地址

### Requirement: User Identity Mapping
系统 SHALL 支持用户身份转换：openId → sapId → ystId

#### Scenario: Convert openId to sapId
- **WHEN** 收到回调消息包含 `fromId`（openId）
- **THEN** 系统通过 `user_query_url` 查询用户信息
- **AND** 获取用户的 `sapId` 用于租户上下文

#### Scenario: Get ystId for message sending
- **WHEN** 需要向用户发送消息
- **THEN** 系统从用户信息获取 `ystId` 作为发送目标地址
- **AND** 如果 `ystId` 缺失，使用 `sapId` 作为 fallback

### Requirement: OAuth Token Management
系统 SHALL 支持 OAuth Token 缓存和自动刷新

#### Scenario: Cache OAuth token
- **WHEN** 获取到 OAuth Token
- **THEN** 系统将 Token 缓存到内存
- **AND** Token 有效期为 90 分钟

#### Scenario: Refresh expired token
- **WHEN** 缓存的 Token 超过 90 分钟有效期
- **THEN** 系统自动请求新的 Token
- **AND** 使用新 Token 替换缓存的旧 Token

### Requirement: Message Deduplication
系统 SHALL 对回调消息进行去重处理

#### Scenario: Accept new message
- **WHEN** 收到新消息（msgId 未在缓存中）
- **THEN** 系统处理该消息
- **AND** 将 msgId 加入缓存

#### Scenario: Reject duplicate message
- **WHEN** 收到重复消息（msgId 在缓存中且未过期）
- **THEN** 系统返回 `{"code": "ok", "message": "duplicate ignored"}`
- **AND** NOT 处理该消息

#### Scenario: Expire old message IDs
- **WHEN** 缓存中的消息 ID 超过 5 分钟 TTL
- **THEN** 系统自动清理过期记录
- **AND** 后续相同 msgId 可被重新处理

### Requirement: Message Routing by Case
系统 SHALL 根据消息内容路由到不同处理流程

#### Scenario: Case 1 - Task progress query
- **WHEN** 消息内容为任务进度关键词（`我的任务进度`、`任务进度`、`查看任务进度`）
- **THEN** 系统查询 CronManager 获取用户今日任务列表
- **AND** 发送任务进度卡片（Template 2）

#### Scenario: Case 2 - Task assignment
- **WHEN** 消息内容长度大于 10 字符
- **THEN** 系统判定为任务分配场景
- **AND** 使用非流式处理模式

#### Scenario: Case 3 - Casual chat
- **WHEN** 消息内容长度小于等于 10 字符且非任务进度关键词
- **THEN** 系统判定为闲聊场景
- **AND** 使用流式处理模式

### Requirement: Case 2 Non-Streaming Processing
Case 2 任务分配 SHALL 使用非流式处理模式

#### Scenario: Send task initiated card
- **WHEN** Case 2 任务分配场景触发
- **THEN** 系统立即发送"任务已发起"卡片通知
- **AND** 卡片包含 Claw URL 可跳转查看进度

#### Scenario: Process task in background
- **WHEN** 任务分配开始处理
- **THEN** 系统在后台异步运行 LLM
- **AND** NOT 发送流式事件给前端

#### Scenario: Send complete result
- **WHEN** 任务处理完成
- **THEN** 系统发送完整的处理结果给用户
- **AND** 用户收到的是一条完整消息而非多条流式碎片

#### Scenario: Handle processing error
- **WHEN** 任务处理过程中发生异常
- **THEN** 系统发送错误通知给用户
- **AND** 错误通知内容为"抱歉，处理您的任务时发生错误，请稍后重试。"

### Requirement: Case 3 Streaming Processing
Case 3 闲聊 SHALL 使用流式处理模式

#### Scenario: Use consume with tracker
- **WHEN** Case 3 闲聊场景触发
- **THEN** 系统使用 `_consume_with_tracker` 流式处理
- **AND** 通过 `on_event_message_completed` 发送消息给用户

#### Scenario: Broadcast to frontend
- **WHEN** workspace 可用
- **THEN** 系统通过 TaskTracker 广播事件给 Console 前端
- **AND** 前端可实时展示处理进度

### Requirement: Message Content Masking
系统 SHALL 对响应内容进行敏感信息脱敏

#### Scenario: Mask names
- **WHEN** 响应包含姓名信息
- **THEN** 系统调用 `extract_url` 服务识别姓名
- **AND** 将姓名脱敏为 `首字符 + *号`

#### Scenario: Mask ID card numbers
- **WHEN** 响应包含 18 位身份证号
- **THEN** 系统将身份证号脱敏为 `前3位 + 11个* + 后4位`

#### Scenario: Mask bank card numbers
- **WHEN** 响应包含银行卡号
- **THEN** 系统将银行卡号脱敏为 `前4位 + 中间* + 后4位`

#### Scenario: Mask phone numbers
- **WHEN** 响应包含手机号
- **THEN** 系统将手机号脱敏为 `前3位 + 4个* + 后4位`

### Requirement: Custom Card Templates
系统 SHALL 支持自定义卡片消息发送

#### Scenario: Template 1 - Task initiated card
- **WHEN** 发送任务发起通知
- **THEN** 卡片内容包含任务描述和跳转链接
- **AND** 使用 OAuth Token 认证

#### Scenario: Template 2 - Task progress card
- **WHEN** 发送任务进度查询结果
- **THEN** 卡片内容包含今日任务列表
- **AND** 每个任务显示状态（已完成/进行中/待开始）

#### Scenario: Card send with OAuth
- **WHEN** 发送自定义卡片
- **THEN** 系统使用 OAuth Token 进行认证
- **AND** Token 通过 `bearer` 方式放在 Authorization header

### Requirement: Claw URL Generation
系统 SHALL 支持 Claw URL 构造用于卡片跳转

#### Scenario: Build claw URL for session
- **WHEN** 需要 Card 跳转到 session 页面
- **THEN** 系统构造 URL 包含 sessionId 参数
- **AND** URL 格式为 `CMBMobileOA:///?pcSysId={sys_id}&pcParams={encoded}`

#### Scenario: Build claw URL for task
- **WHEN** 需要 Card 跳转到任务结果页面
- **THEN** 系统构造 URL 包含 taskId 参数
- **AND** 使用 `cron_task_menu_id` 作为跳转目标