# 招乎渠道消息实时传递设计文档

**日期**: 2026-03-22
**主题**: 招乎渠道入站消息处理与会话隔离

## 1. 背景与问题

招乎(zhaohu)是中石化内部通讯平台。当前 CoPaw 的招乎渠道仅支持出站推送(outbound push)，即 CoPaw 可以主动向招乎用户发送消息，但无法接收用户的回复消息。

### 业务需求

1. **接收用户消息**: 用户在招乎中发送消息给机器人，CoPaw 需要能够接收
2. **智能回复**: 接收消息后调用大模型生成回复，并发送给用户
3. **会话隔离**: 不同用户的会话独立，同一用户的消息保持上下文连续性
4. **技能共享**: 招乎用户与前端用户共用技能配置

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   招乎平台      │ ──── │  CoPaw Server   │ ──── │   大模型服务    │
│                 │      │                 │      │                 │
│  用户发送消息   │ ───▶ │  回调接口       │      │                 │
│                 │      │  (立即响应)     │ ───▶ │  生成回复       │
│  接收回复消息   │ ◀─── │  后台处理       │ ◀─── │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

### 2.2 消息处理流程

```
招乎回调请求
     │
     ▼
┌─────────────────┐
│  POST /api/     │
│  zhaohu/callback│
└────────┬────────┘
         │
         ▼
┌─────────────────┐     立即返回
│  参数校验       │ ──────────────▶ {"code":"ok","message":"received"}
│  消息去重       │
│  后台任务调度   │
└────────┬────────┘
         │
         ▼ (后台异步)
┌─────────────────┐
│  查询用户信息   │ ◀── openId → sapId
│  (user_query_url)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  构建请求       │
│  session_id =   │
│  zhaohu:callback│
│  :{sapId}       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  调用大模型     │
│  (process)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  发送回复       │
│  (push_url)     │ ──────────────▶ 招乎用户收到回复
└─────────────────┘
```

## 3. 接口设计

### 3.1 回调接口

**端点**: `POST /api/zhaohu/callback`

**请求体**:

```json
{
  "msgId": "XXXXXXXXXXXXXXXXXXX",
  "fromId": "XXXXXXXXXXXXXXXXXXXXXXXX",
  "toId": "XXXXXXXXXXXXXXXXXXXXXX",
  "groupId": 920000306024,
  "groupName": "某某某创建的群组",
  "msgType": "at",
  "msgContent": "xxxxxxx",
  "timestamp": 1234567890123,
  "customInfo": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| msgId | string | 是 | 消息唯一标识，用于去重 |
| fromId | string | 是 | 发送者 openId |
| toId | string | 是 | 接收者（机器人）ID |
| groupId | int | 否 | 群组ID，私聊为 null |
| groupName | string | 否 | 群组名称 |
| msgType | string | 是 | 消息类型：text/at/image等 |
| msgContent | string | 是 | 消息内容 |
| timestamp | int | 是 | 消息时间戳（毫秒） |
| customInfo | any | 否 | 自定义信息 |

**响应**:

```json
{
  "code": "ok",
  "message": "received"
}
```

| 状态码 | 说明 |
|--------|------|
| 200 | 成功接收 |
| 503 | 渠道未启用或不可用 |

### 3.2 用户信息查询接口

**端点**: `{user_query_url}` (配置项)

**请求**:

```json
{
  "compareType": "EQ",
  "matchFields": ["openId"],
  "keyWord": "{openId}"
}
```

**响应**:

```json
{
  "code": "200",
  "message": "OK",
  "result": true,
  "data": [
    {
      "sapId": "SAP001",
      "openId": "openId_xxx",
      "userName": "张三"
    }
  ]
}
```

### 3.3 消息推送接口

**端点**: `{push_url}` (配置项)

**请求体结构**:

```json
{
  "baseInfo": {
    "sysId": "系统ID",
    "channel": "ZH",
    "robotOpenId": "机器人ID",
    "sendAddrs": [
      {
        "sendAddr": "接收者sapId",
        "sendPk": "发送主键"
      }
    ],
    "net": "DMZ"
  },
  "msgContent": {
    "summary": "消息摘要",
    "pushContent": "推送内容",
    "message": [
      {
        "type": "txt",
        "value": [{"text": "消息文本"}]
      }
    ]
  }
}
```

## 4. 会话隔离设计

### 4.1 Session ID 设计

```
session_id = "zhaohu:callback:{sapId}"
```

**设计说明**:

| 组成部分 | 说明 |
|----------|------|
| `zhaohu` | 渠道标识 |
| `callback` | 标识来自回调接口，与前端创建的会话区分 |
| `{sapId}` | 用户唯一标识，同一用户的所有消息使用相同 session_id |

### 4.2 会话隔离效果

```
用户A (sapId=SAP001):
  - session_id: "zhaohu:callback:SAP001"
  - 用户目录: {working_dir}/SAP001/
  - 会话文件: {working_dir}/SAP001/sessions/SAP001_zhaohu--callback--SAP001.json

用户B (sapId=SAP002):
  - session_id: "zhaohu:callback:SAP002"
  - 用户目录: {working_dir}/SAP002/
  - 会话文件: {working_dir}/SAP002/sessions/SAP002_zhaohu--callback--SAP002.json

前端会话 (UUID格式):
  - session_id: "550e8400-e29b-41d4-a716-446655440000"
  - 完全独立，不会与招乎会话冲突
```

### 4.3 技能共享机制

```
用户A的目录结构:
{working_dir}/SAP001/
├── AGENTS.md          # Agent配置
├── SOUL.md            # 人格配置
├── PROFILE.md         # 用户画像
├── skills/            # 技能目录 (与前端共用)
│   ├── skill1/
│   └── skill2/
└── sessions/
    ├── SAP001_zhaohu--callback--SAP001.json  # 招乎会话
    └── xxx-xxx-xxx.json                       # 前端会话
```

**共享机制**:
- 招乎会话和前端会话共享同一用户的 `skills/` 目录
- `user_id = sapId`，确保用户身份一致
- 会话文件按 `session_id` 隔离，互不影响

## 5. 消息去重机制

### 5.1 去重策略

```python
# 内存缓存，5分钟TTL
_processed_message_ids: Dict[str, float] = {}
_DEDUP_TTL_SECONDS = 300

def try_accept_message(self, msg_id: str) -> bool:
    # 1. 清理过期条目
    # 2. 检查是否已处理
    # 3. 记录新消息ID
```

### 5.2 去重流程

```
收到消息 msgId="abc123"
     │
     ▼
检查 _processed_message_ids
     │
     ├── 存在且未过期 → 返回 False (重复消息，忽略)
     │
     └── 不存在或已过期 → 记录时间戳，返回 True (新消息)
```

### 5.3 为什么需要去重

| 场景 | 说明 |
|------|------|
| 网络重试 | 招乎平台可能因网络问题重复推送 |
| 服务重启 | 消息队列中的消息可能被重新投递 |
| 集群部署 | 多实例可能同时收到同一条消息 |

## 6. 配置说明

### 6.1 配置项

```json
{
  "channels": {
    "zhaohu": {
      "enabled": true,
      "push_url": "https://zhaohu.example.com/api/push",
      "sys_id": "copaw",
      "robot_open_id": "robot_001",
      "channel": "ZH",
      "net": "DMZ",
      "request_timeout": 15.0,
      "user_query_url": "https://zhaohu.example.com/api/user/query",
      "dm_policy": "open",
      "group_policy": "open",
      "allow_from": [],
      "deny_message": ""
    }
  }
}
```

### 6.2 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| enabled | bool | 是 | 是否启用招乎渠道 |
| push_url | string | 是 | 消息推送接口地址 |
| sys_id | string | 是 | 系统ID |
| robot_open_id | string | 是 | 机器人OpenID |
| channel | string | 否 | 渠道代码，默认"ZH" |
| net | string | 否 | 网络类型，默认"DMZ" |
| request_timeout | float | 否 | 请求超时时间（秒），默认15 |
| user_query_url | string | 是 | 用户信息查询接口地址 |
| dm_policy | string | 否 | 私聊策略：open/restricted |
| group_policy | string | 否 | 群聊策略：open/restricted |
| allow_from | list | 否 | 允许的用户/群组ID列表 |
| deny_message | string | 否 | 拒绝访问时的提示消息 |

### 6.3 环境变量配置

```bash
# 启用招乎渠道
export ZHAOHU_CHANNEL_ENABLED=1

# 推送配置
export ZHAOHU_PUSH_URL="https://zhaohu.example.com/api/push"
export ZHAOHU_SYS_ID="copaw"
export ZHAOHU_ROBOT_OPEN_ID="robot_001"

# 用户查询配置
export ZHAOHU_USER_QUERY_URL="https://zhaohu.example.com/api/user/query"

# 访问控制
export ZHAOHU_DM_POLICY="open"
export ZHAOHU_GROUP_POLICY="open"
export ZHAOHU_ALLOW_FROM="SAP001,SAP002"
```

## 7. 代码结构

### 7.1 文件清单

| 文件 | 说明 |
|------|------|
| `src/copaw/config/config.py` | ZhaohuConfig 配置类 |
| `src/copaw/app/routers/zhaohu.py` | 回调路由 |
| `src/copaw/app/channels/zhaohu/channel.py` | 招乎渠道实现 |
| `src/copaw/app/routers/__init__.py` | 路由注册 |

### 7.2 核心类与方法

```
ZhaohuChannel (BaseChannel)
├── __init__()                    # 初始化配置
├── from_env()                    # 从环境变量创建
├── from_config()                 # 从配置创建
├── resolve_session_id()          # 生成会话ID
├── try_accept_message()          # 消息去重
├── _query_user_info()            # 查询用户信息
├── process_callback_message()    # 处理回调消息
├── send()                        # 发送消息
└── _build_push_payload()         # 构建推送载荷

zhaohu_router (APIRouter)
├── ZhaohuCallbackRequest         # 请求模型
├── _get_zhaohu_channel()         # 获取渠道实例
├── _process_callback_background()# 后台处理任务
└── zhaohu_callback()             # 回调处理函数
```

## 8. 测试案例

### 8.1 单元测试

```python
class TestZhaohuConfig:
    def test_defaults(self):
        """测试默认配置"""
        config = ZhaohuConfig()
        assert config.enabled is False
        assert config.push_url == ""
        assert config.user_query_url == ""

    def test_custom_config(self):
        """测试自定义配置"""
        config = ZhaohuConfig(
            enabled=True,
            push_url="https://example.com/push",
            user_query_url="https://example.com/query"
        )
        assert config.enabled is True
        assert config.push_url == "https://example.com/push"


class TestZhaohuChannel:
    def test_resolve_session_id(self):
        """测试会话ID生成"""
        channel = ZhaohuChannel(...)
        session_id = channel.resolve_session_id("SAP001")
        assert session_id == "zhaohu:callback:SAP001"

    def test_try_accept_message_new(self):
        """测试新消息被接受"""
        channel = ZhaohuChannel(...)
        assert channel.try_accept_message("msg001") is True

    def test_try_accept_message_duplicate(self):
        """测试重复消息被拒绝"""
        channel = ZhaohuChannel(...)
        channel.try_accept_message("msg001")  # 第一次
        assert channel.try_accept_message("msg001") is False  # 重复
```

### 8.2 集成测试

```python
class TestZhaohuCallbackAPI:
    @pytest.mark.asyncio
    async def test_callback_success(self, client: AsyncClient):
        """测试回调成功"""
        response = await client.post(
            "/api/zhaohu/callback",
            json={
                "msgId": "test001",
                "fromId": "openId001",
                "toId": "bot001",
                "msgType": "text",
                "msgContent": "你好",
                "timestamp": 1234567890123
            }
        )
        assert response.status_code == 200
        assert response.json()["code"] == "ok"

    @pytest.mark.asyncio
    async def test_callback_duplicate(self, client: AsyncClient):
        """测试重复消息"""
        body = {
            "msgId": "test002",
            "fromId": "openId001",
            "toId": "bot001",
            "msgType": "text",
            "msgContent": "你好",
            "timestamp": 1234567890123
        }
        # 第一次
        response1 = await client.post("/api/zhaohu/callback", json=body)
        assert response1.json()["message"] == "received"

        # 重复
        response2 = await client.post("/api/zhaohu/callback", json=body)
        assert response2.json()["message"] == "duplicate ignored"

    @pytest.mark.asyncio
    async def test_callback_channel_disabled(self, client: AsyncClient):
        """测试渠道禁用"""
        # Mock channel disabled
        response = await client.post(
            "/api/zhaohu/callback",
            json={"msgId": "test003", ...}
        )
        assert response.status_code == 503
```

### 8.3 手动测试

```bash
# 1. 启动服务
uvicorn copaw.main:app --reload

# 2. 发送测试回调
curl -X POST http://localhost:8000/api/zhaohu/callback \
  -H "Content-Type: application/json" \
  -d '{
    "msgId": "test-'$(date +%s)'",
    "fromId": "testOpenId",
    "toId": "botId",
    "groupId": null,
    "groupName": null,
    "msgType": "text",
    "msgContent": "你好，请介绍一下自己",
    "timestamp": '$(date +%s000)'
  }'

# 3. 检查响应
# 预期: {"code": "ok", "message": "received"}

# 4. 查看日志确认处理流程
# 预期看到:
# - zhaohu callback: msgId=xxx fromId=xxx msgType=text
# - zhaohu processing: msgId=xxx fromId=xxx text=你好...
# - zhaohu user query: openId=xxx -> sapId=xxx
# - zhaohu response: msgId=xxx to=xxx text=...
# - zhaohu push ok: to=xxx returnCode=...
```

## 9. 错误处理

### 9.1 错误场景

| 场景 | 处理方式 |
|------|----------|
| 渠道未启用 | 返回 503，message="channel disabled" |
| 渠道不可用 | 返回 503，message="channel not available" |
| 重复消息 | 返回 200，message="duplicate ignored" |
| 用户查询失败 | 使用 openId 作为 sapId 继续处理 |
| 大模型调用失败 | 发送错误提示消息给用户 |
| 推送失败 | 记录错误日志，不重试 |

### 9.2 错误响应消息

当处理失败时，系统会发送友好的错误提示：

```python
await self.send(
    sap_id,
    "抱歉，处理您的消息时发生错误，请稍后重试。",
    meta
)
```

## 10. 安全考虑

### 10.1 访问控制

- `dm_policy`: 控制私聊访问权限
- `group_policy`: 控制群聊访问权限
- `allow_from`: 白名单用户/群组列表

### 10.2 数据隔离

- 不同用户的会话文件完全隔离
- 技能目录按用户隔离
- 敏感配置（API密钥等）不记录在日志中

### 10.3 日志规范

- 不记录完整的消息内容（截断至100字符）
- 不记录用户敏感信息
- 记录必要的调试信息（msgId, fromId, sapId）

## 11. 性能优化

### 11.1 立即响应

回调接口立即返回，后台异步处理，避免招乎平台超时。

### 11.2 消息去重缓存

- 使用内存缓存，避免数据库查询
- 定期清理过期条目，防止内存泄漏
- TTL设置为5分钟，平衡性能与可靠性

### 11.3 会话复用

- 同一用户的会话状态持久化
- 支持多轮对话上下文
- 避免每次都重新初始化

## 12. 未来扩展

### 12.1 支持的消息类型

当前仅支持文本消息，未来可扩展：

- 图片消息
- 文件消息
- 卡片消息

### 12.2 群聊支持

当前群聊与私聊处理逻辑相同，未来可扩展：

- 群成员权限控制
- 群消息过滤
- 群聊专属功能

### 12.3 消息追踪

- 消息处理状态追踪
- 消息送达确认
- 处理耗时统计