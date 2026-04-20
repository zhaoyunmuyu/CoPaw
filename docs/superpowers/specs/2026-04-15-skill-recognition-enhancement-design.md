# 技能识别功能增强设计

> 设计日期: 2026-04-15
> 状态: 设计中

## 1. 背景与问题

### 1.1 当前问题

用户希望准确识别对话中实际使用的技能，支持两类场景：

1. **问答类技能**：根据用户消息内容匹配技能的触发关键词
   - 例如：用户问"黄金定期利率多少？"，应识别到"黄金产品问答"技能

2. **工具类技能**：根据工具调用参数匹配技能特征
   - 例如：工具调用参数包含 `.xlsx`，应识别到 xlsx 技能
   - 例如：MCP 调用到 `filesystem` 服务器，应识别到相关技能

### 1.2 现有系统限制

| 组件 | 当前行为 | 限制 |
|------|----------|------|
| `SkillFeatureInferencer` | 只支持内置技能的硬编码特征 | 自定义技能无法使用 |
| `SkillInvocationDetector` | 只在工具调用时检测 | 无法识别纯问答类技能 |
| 特征提取 | 需要 `uses_tools` 显式声明 | 用户需要手动配置 |

### 1.3 目标

- **准确识别**：支持问答类和工具类两种技能的识别
- **自动特征提取**：从 SKILL.md 自动提取识别特征
- **显式覆盖**：支持用户显式声明覆盖自动提取
- **最小性能开销**：特征提取一次，运行时零开销
- **向后兼容**：现有 SKILL.md 无需修改

---

## 2. 设计方案

### 2.1 核心思路

```
┌─────────────────────────────────────────────────────────────────┐
│                     SKILL.md 特征自动提取                        │
├─────────────────────────────────────────────────────────────────┤
│ 1. 触发关键词                                                    │
│    - 显式声明: ## 触发关键词 下的列表                            │
│    - 自动提取: 从 description 分词提取                           │
│                                                                 │
│ 2. 文件扩展名                                                    │
│    - 正则匹配: .xlsx, .pdf, .docx 等                            │
│                                                                 │
│ 3. MCP 信息（如有）                                              │
│    - 服务器名、工具名                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      运行时匹配                                  │
├─────────────────────────────────────────────────────────────────┤
│ Layer 0: 用户消息匹配（新增）                                    │
│    用户消息 → 关键词匹配 → 识别问答类技能                        │
│                                                                 │
│ Layer 1-4: 工具调用匹配（增强）                                  │
│    工具参数 → 文件扩展名/MCP → 识别工具类技能                    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 检测层级设计

```
Layer 0: 用户消息检测（新增）
    触发时机: 收到用户消息时（trace 开始）
    检测逻辑: 关键词匹配
    置信度: 0.7-0.95
    适用场景: 问答类技能、纯对话技能
          ↓
Layer 1: 显式声明（现有）
    触发时机: 工具调用开始
    检测逻辑: 检查 uses_tools 声明
    置信度: 1.0
    适用场景: 明确工具归属的技能
          ↓
Layer 2: 特征匹配（增强）
    触发时机: 工具调用开始（无显式声明）
    检测逻辑:
      - 文件扩展名匹配: 置信度 0.8
      - MCP server 匹配: 置信度 0.85
      - 关键词匹配: 置信度 0.4-0.7
    适用场景: 文件处理技能、MCP 技能
          ↓
Layer 3: 序列模式（现有）
    触发时机: 工具调用序列匹配
    置信度: 0.6
    适用场景: 特定工具组合的技能
          ↓
Layer 4: 工具提示（现有）
    触发时机: 无法匹配其他层级时
    置信度: 0.4
    适用场景: 最后的推断层
```

---

## 3. 数据结构设计

### 3.1 SkillFeature 扩展

```python
@dataclass
class SkillFeature:
    """技能特征定义（扩展版）"""

    # 原有字段
    skill_name: str
    file_extensions: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    tools_hint: list[str] = field(default_factory=list)
    tool_patterns: list[list[str]] = field(default_factory=list)

    # 新增字段
    trigger_keywords: list[str] = field(default_factory=list)      # 显式触发关键词
    description_keywords: list[str] = field(default_factory=list)  # 自动提取关键词
    mcp_servers: list[str] = field(default_factory=list)           # MCP server 列表
    is_conversational: bool = False                                 # 是否问答类技能
    feature_source: str = "builtin"                                 # 特征来源
```

### 3.2 SKILL.md 格式约定

**标准格式**：

```yaml
---
name: 黄金产品问答
description: 黄金产品问答技能。当客户询问黄金投资、黄金产品...
metadata:
  swe:
    uses_tools:
      - mcp_finance_api
---

## 触发关键词

- 黄金、金价、金子、贵金属
- 实物金、金条、金币、金饰
- 黄金账户、黄金活期、黄金定期
```

**解析优先级**：
1. `trigger_keywords`: 从正文 `## 触发关键词` 段落提取（显式覆盖）
2. `description_keywords`: 从 frontmatter description 自动提取
3. `keywords`: 合并 trigger_keywords + description_keywords

---

## 4. 模块设计

### 4.1 新增模块: SkillFeatureExtractor

**文件路径**: `src/swe/agents/skill_feature_extractor.py`

**职责**: 在技能加载时从 SKILL.md 提取特征

```python
class SkillFeatureExtractor:
    """从 SKILL.md 提取技能特征"""

    def extract_from_content(self, content: str) -> ExtractedSkillFeatures:
        """从 SKILL.md 内容提取所有特征"""

    def _extract_trigger_keywords_section(self, body: str) -> list[str]:
        """解析 ## 触发关键词 段落"""

    def _extract_description_keywords(self, description: str) -> list[str]:
        """从 description 自动分词提取关键词"""

    def _extract_file_extensions(self, content: str) -> list[str]:
        """正则提取文件扩展名"""

    def _extract_mcp_servers(self, content: str) -> list[str]:
        """提取 MCP server 引用"""
```

### 4.2 修改模块: SkillFeatureInferencer

**文件路径**: `src/swe/agents/skill_feature_inferencer.py`

**新增方法**：

```python
class SkillFeatureInferencer:
    # ... 现有代码 ...

    def infer_skill_from_user_message(
        self,
        user_message: str,
        enabled_skills: list[str],
    ) -> tuple[Optional[str], float]:
        """从用户消息推断技能归属（Layer 0）"""

    def infer_skill_from_mcp_server(
        self,
        mcp_server: str,
        enabled_skills: list[str],
    ) -> tuple[Optional[str], float]:
        """从 MCP server 名称推断技能归属"""
```

### 4.3 修改模块: SkillInvocationDetector

**文件路径**: `src/swe/agents/skill_invocation_detector.py`

**新增字段**：

```python
# 缓存用户消息检测结果
_message_detected_skill: Optional[str] = None
_message_detected_confidence: float = 0.0
```

**新增方法**：

```python
def detect_from_user_message(self, user_message: str) -> tuple[Optional[str], float]:
    """Layer 0: 从用户消息检测技能"""
```

**修改方法**：

```python
async def on_tool_call(self, tool_name, tool_input, mcp_server):
    """增强的工具调用检测，集成 Layer 0 缓存"""
    # 1. 检查 Layer 0 缓存
    # 2. Layer 1-4 检测（现有逻辑）
    # 3. 增加 MCP server 匹配
```

### 4.4 修改模块: skill_tool_registry.py

**文件路径**: `src/swe/agents/skill_tool_registry.py`

**修改函数**: `build_skill_tool_registry()`

```python
def build_skill_tool_registry(workspace_dir, enabled_skills):
    """构建技能注册表并提取特征"""
    # 1. 现有逻辑：提取 uses_tools
    # 2. 新增：调用 SkillFeatureExtractor 提取特征
    # 3. 新增：注册特征到 SkillFeatureInferencer
```

---

## 5. 数据流设计

### 5.1 技能加载流程

```
ReactAgent._register_skills()
    │
    ├── resolve_effective_skills()          # 获取启用的技能列表
    │
    ├── toolkit.register_agent_skill()      # 注入技能到 prompt
    │
    └── build_skill_tool_registry()         # 构建 + 特征提取
            │
            ├── 遍历每个启用的技能
            │       │
            │       ├── 提取 uses_tools (现有)
            │       │
            │       └── SkillFeatureExtractor.extract_from_content()
            │               │
            │               ├── trigger_keywords (显式)
            │               ├── description_keywords (自动)
            │               ├── file_extensions
            │               └── mcp_servers
            │
            └── SkillFeatureInferencer.register_feature()
```

### 5.2 运行时检测流程

```
用户消息到达
    │
    └── TraceManager.start_trace(user_message)
            │
            └── setup_skill_detector()
                    │
                    └── detector.detect_from_user_message()
                            │
                            ├── 遍历 enabled_skills
                            ├── 检查 trigger_keywords
                            ├── 检查 keywords
                            └── 缓存结果到 _message_detected_skill

工具调用发生
    │
    └── TraceManager.emit_tool_call_start()
            │
            └── detector.on_tool_call()
                    │
                    ├── Layer 0: 检查缓存（如有）
                    ├── Layer 1: 检查 uses_tools 声明
                    ├── Layer 2: 特征匹配（文件扩展名、MCP、关键词）
                    ├── Layer 3: 序列模式
                    └── Layer 4: 工具提示
```

---

## 6. 关键代码示例

### 6.1 触发关键词提取

```python
def _extract_trigger_keywords_section(self, body_content: str) -> list[str]:
    """从 ## 触发关键词 段落提取关键词"""
    keywords = []

    # 匹配标题
    pattern = re.compile(r'^##\s*触发关键词', re.IGNORECASE | re.MULTILINE)
    match = pattern.search(body_content)
    if not match:
        return keywords

    # 提取段落内容直到下一个 ## 标题
    start_pos = match.end()
    next_header = re.search(r'^##\s', body_content[start_pos:], re.MULTILINE)
    end_pos = start_pos + (next_header.start() if next_header else len(body_content) - start_pos)

    section = body_content[start_pos:end_pos].strip()

    # 解析列表项
    for line in section.split('\n'):
        line = line.strip()
        if line.startswith('-') or line.startswith('*'):
            line = line.lstrip('-*').strip()
            # 支持多种分隔符：中文逗号、英文逗号、顿号
            parts = re.split(r'[，,；;、\s]+', line)
            keywords.extend(p.strip() for p in parts if p.strip())

    return keywords
```

### 6.2 用户消息检测

```python
def infer_skill_from_user_message(
    self,
    user_message: str,
    enabled_skills: list[str],
) -> tuple[Optional[str], float]:
    """从用户消息推断技能"""
    message_lower = user_message.lower()
    best_skill, best_confidence = None, 0.0

    for skill_name in enabled_skills:
        feature = self._features.get(skill_name)
        if not feature:
            continue

        # 检查显式触发关键词（高置信度）
        trigger_matches = 0
        if feature.trigger_keywords:
            for kw in feature.trigger_keywords:
                if kw.lower() in message_lower:
                    trigger_matches += 1

        if trigger_matches > 0:
            confidence = min(0.95, 0.7 + trigger_matches * 0.1)
            if confidence > best_confidence:
                best_confidence = confidence
                best_skill = skill_name
            continue

        # 检查自动提取的关键词
        keyword_matches = sum(
            1 for kw in feature.keywords
            if kw.lower() in message_lower
        )

        if keyword_matches > 0:
            confidence = min(0.85, 0.4 + keyword_matches * 0.15)
            if confidence > best_confidence:
                best_confidence = confidence
                best_skill = skill_name

    return best_skill, best_confidence
```

---

## 7. 性能考量

### 7.1 特征提取时机

| 操作 | 时机 | 开销 |
|------|------|------|
| 解析 SKILL.md | 技能加载时（一次） | IO + 解析 |
| 分词提取关键词 | 技能加载时（一次） | CPU |
| 注册到 Inferencer | 技能加载时（一次） | 内存 |

### 7.2 运行时开销

| 操作 | 开销 |
|------|------|
| 用户消息匹配 | O(n×m)，n=技能数，m=关键词数 |
| 工具调用匹配 | O(n)，字符串包含检查 |
| 缓存命中 | O(1) |

### 7.3 优化措施

- 关键词数量限制（max_keywords = 20）
- 使用 Python 内置字符串搜索（`in` 操作）
- 用户消息检测缓存，避免重复匹配

---

## 8. 向后兼容

### 8.1 现有 SKILL.md

- 没有 `## 触发关键词` 段落的技能：自动从 description 提取
- 没有 `uses_tools` 声明的技能：特征匹配层识别
- 现有声明继续有效

### 8.2 现有检测流程

- Layer 1-4 逻辑不变
- Layer 0 可选启用
- 不影响现有 API 接口

### 8.3 数据结构

- 新字段有默认值
- 旧代码访问新字段不会出错

---

## 9. 测试计划

### 9.1 单元测试

**新增文件**: `tests/unit/agents/test_skill_feature_extractor.py`

测试用例：
- `test_extract_trigger_keywords_explicit`: 显式关键词提取
- `test_extract_description_keywords`: 自动关键词提取
- `test_extract_file_extensions`: 文件扩展名提取
- `test_build_skill_feature`: 特征构建

**扩展文件**: `tests/unit/agents/test_skill_invocation_detector.py`

测试用例：
- `test_detect_from_user_message`: 用户消息检测
- `test_message_detection_caching`: 结果缓存
- `test_message_tool_conflict`: 消息与工具冲突
- `test_mcp_server_inference`: MCP server 匹配

### 9.2 集成测试

使用项目根目录的 `SKILL.md`（黄金产品问答）测试：
1. 用户消息"黄金定期利率多少" → 识别到"黄金产品问答"
2. 工具调用包含 `.xlsx` → 识别到 xlsx 技能
3. 检查 timeline 正确展示技能调用

---

## 10. 实施步骤

### Step 1: 新增模块

- [x] 创建 `src/swe/agents/skill_feature_extractor.py`
- [x] 实现 `ExtractedSkillFeatures` 数据类
- [x] 实现 `SkillFeatureExtractor` 类

### Step 2: 扩展现有模块

- [x] 扩展 `SkillFeature` 数据结构
- [x] 新增 `infer_skill_from_user_message` 方法
- [x] 新增 `infer_skill_from_mcp_server` 方法

### Step 3: 增强检测器

- [x] 新增 `_message_detected_skill` 缓存字段
- [x] 新增 `detect_from_user_message` 方法
- [x] 修改 `on_tool_call` 集成缓存

### Step 4: 集成特征提取

- [x] 修改 `build_skill_tool_registry` 函数
- [x] 在技能加载时提取特征

### Step 5: 测试验证

- [x] 编写单元测试
- [x] 集成测试验证
- [ ] 性能测试

---

## 11. 相关文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/swe/agents/skill_feature_extractor.py` | 新增 | 特征提取核心模块 |
| `src/swe/agents/skill_feature_inferencer.py` | 修改 | 扩展数据结构和方法 |
| `src/swe/agents/skill_invocation_detector.py` | 修改 | 新增 Layer 0 检测 |
| `src/swe/agents/skill_tool_registry.py` | 修改 | 增强构建函数 |
| `src/swe/agents/react_agent.py` | 参考 | 技能加载集成点 |
| `src/swe/tracing/manager.py` | 参考 | 追踪集成点 |
| `tests/unit/agents/test_skill_feature_extractor.py` | 新增 | 单元测试 |
