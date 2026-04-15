## Why

当前"案例详情"功能存在以下问题：

1. **数据硬编码** - 案例列表和详情内容在前端代码中硬编码，修改需要重新部署
2. **无用户区分** - 所有用户看到相同的案例列表，无法根据用户身份定制内容
3. **iframe 嵌入缺失** - "他行存款到期潜力客户名单"等外部网页无法在详情中展示

这些问题导致：
- 运营人员无法灵活调整案例内容
- 不同角色/分行的用户无法获得针对性案例
- 外部业务系统页面无法与案例详情联动展示

## What Changes

### 新增功能

- **案例数据 API** - 新增 `/cases` 系列接口，从配置文件读取案例数据
- **用户维度案例** - 根据 `userId` 过滤案例列表，支持不同用户看到不同案例
- **iframe 自动嵌入** - 案例详情右侧自动嵌入 `iframe_url` 指定的外部网页
- **后台管理页面** - 新增案例管理页面，支持创建/编辑案例和用户分配

### 修改内容

- **FeaturedCases 组件** - 从 API 动态加载案例列表（替代硬编码）
- **CaseDetailDrawer 组件** - 新布局：左侧步骤说明 + 右侧 iframe 嵌入
- **WelcomeCenterLayout 组件** - 点击"看案例"时从 API 加载详情
- **userId 传递链路** - API 请求携带 `X-User-Id` header 实现用户过滤

## Capabilities

### New Capabilities

- `cases-api`: 案例数据 API 接口（列表查询、详情获取、管理操作）
- `cases-user-filtering`: 根据 userId 过滤案例列表的用户维度能力
- `cases-iframe-embedding`: 案例详情 iframe 自动嵌入外部网页
- `cases-management`: 后台案例管理页面（案例定义 + 用户分配）

### Modified Capabilities

<!-- 无现有能力需要修改 -->