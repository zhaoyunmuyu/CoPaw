## Context

当前案例详情功能的实现状态：

**前端组件结构**：
- `FeaturedCases` - 案例列表展示（硬编码 DEFAULT_CASES）
- `CaseDetailDrawer` - 详情抽屉（硬编码表格和步骤）
- `WelcomeCenterLayout` - 欢迎页布局，传递案例数据

**数据来源**：
- 前端 `defaultConfig.ts` 硬编码 `prompts` 数组
- 无后端 API 支持

**用户上下文**：
- 已有 `iframeStore` 存储父窗口传递的 `userId`
- API 请求携带 `X-User-Id` header（通过 `buildAuthHeaders`）

**约束条件**：
- 存储方案：使用 Config File（JSON），不使用数据库
- 用户隔离：当前所有租户使用相同案例列表，但需支持 userId 过滤
- iframe 安全：嵌入的外部网页需考虑跨域和沙箱属性

## Goals / Non-Goals

**Goals:**

1. 实现案例数据从 API 动态加载，替代前端硬编码
2. 支持根据 `userId` 过滤案例列表（不同用户看到不同案例）
3. 案例详情右侧自动 iframe 嵌入外部网页（`iframe_url` 字段）
4. 提供后台管理页面，支持案例创建/编辑和用户分配

**Non-Goals:**

1. 不实现数据库存储（使用 JSON 配置文件）
2. 不实现多租户完全隔离（所有租户共享案例定义，通过 userId 映射过滤）
3. 不实现 iframe 内"去电访"/"去洞察"按钮功能（由嵌入网页自身处理）
4. 不实现案例历史版本管理

## Decisions

### Decision 1: 存储方案 - JSON 配置文件

**选择**：使用两个 JSON 文件存储案例数据
- `WORKING_DIR/cases.json` - 案例定义（全局共享）
- `WORKING_DIR/user_cases.json` - 用户-案例映射

**替代方案**：
- MySQL 数据库：项目已支持，但需求明确不使用数据库
- 单文件方案：难以维护用户映射关系

**理由**：
1. 配置文件简单，无需数据库迁移
2. 与现有 `config.json`、`jobs.json` 模式一致
3. 支持热更新（可扩展 config watcher）

### Decision 2: userId 过滤机制

**选择**：通过 `user_cases.json` 映射实现用户维度过滤
- `default` 数组定义默认案例列表
- 特定 userId 可覆盖默认配置

**替代方案**：
- 直接在案例中标记 `target_users`：难以管理
- 数据库用户表：超出非目标范围

**理由**：
1. 管理员可灵活分配用户可见案例
2. 新用户自动使用 `default` 配置
3. 与 iframe 传递的 userId 集成简单

### Decision 3: iframe 嵌入布局

**选择**：左右分栏布局
- 左侧（flex: 1）：步骤说明（可滚动）
- 右侧（flex: 2）：iframe 嵌入外部网页

**替代方案**：
- 全屏 iframe：用户无法看到步骤说明
- Tab 切换：交互复杂，不利于同时查看

**理由**：
1. 用户可同时查看步骤和业务数据
2. iframe 占更大空间，业务数据是重点
3. 与现有布局风格一致

### Decision 4: API 设计

**选择**：
- `GET /cases` - 返回用户可见案例列表（不含详情）
- `GET /cases/{case_id}` - 返回案例详情
- 管理接口：`POST/PUT/DELETE /cases`、用户映射管理

**userId 获取优先级**：
1. `X-User-Id` header（iframe 传递）
2. `?user_id=` query 参数
3. fallback `"default"`

**理由**：
1. 混合加载方案：列表启动加载，详情点击加载
2. 与现有 authHeaders 模式一致
3. 管理接口与业务接口分离

## Risks / Trade-offs

### Risk 1: iframe 跨域问题
- **风险**：嵌入的外部网页可能有跨域限制
- **缓解**：添加 `sandbox="allow-scripts allow-same-origin"` 属性，URL 配置时需确保可访问

### Risk 2: JSON 文件并发写入
- **风险**：多实例部署时，配置文件写入可能冲突
- **缓解**：当前仅管理员操作，频率低；后续可扩展为数据库存储

### Risk 3: userId 未配置时的 fallback
- **风险**：新用户未在 `user_cases.json` 中配置
- **缓解**：强制使用 `default` 数组作为 fallback

### Trade-off 1: 不支持实时热更新
- 当前修改 JSON 文件需重启或手动触发
- 可接受：管理操作频率低，后续可扩展 config watcher

### Trade-off 2: iframe 安全依赖外部系统
- iframe 内内容由外部系统控制，安全由外部系统负责
- 可接受：`iframe_url` 由管理员配置，来源可信

## Open Questions

1. **iframe 加载失败时的 fallback 展示**：是否需要显示错误提示或空白？
   - 建议：显示加载失败提示，提供刷新按钮

2. **案例排序规则**：是否支持用户维度排序？
   - 建议：全局 `sort_order`，后续可扩展用户维度排序

3. **订阅为定时任务功能**：是否在本变更中实现？
   - 建议：单独变更，本变更仅实现数据加载