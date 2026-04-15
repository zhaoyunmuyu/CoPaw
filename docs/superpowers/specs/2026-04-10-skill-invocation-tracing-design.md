# 技能调用追踪增强设计文档

## 1. 目标与范围

实现完整的技能调用生命周期追踪，解决当前技能调用无法被识别的问题。

### 1.1 问题背景

当前 Tracing 模块存在以下问题：

| 问题 | 描述 |
|------|------|
| 技能调用无事件 | `on_skill_start`/`on_skill_end` 方法存在但从未被调用 |
| 归属推断不可靠 | 依赖 `uses_tools` 声明，未声明则无法建立工具→技能关系 |
| MCP 工具归属缺失 | 自定义技能使用的 MCP 工具可能未在 `uses_tools` 中声明 |
| 多技能归属冲突 | 多个技能声明同一工具时，可能归属到错误的技能 |

### 1.2 目标

> 让系统能够准确识别技能的调用边界，追踪技能执行期间的所有工具调用（包括 MCP 工具），并建立完整的技能→工具调用链路。

### 1.3 功能范围

**本期实现：**
- 技能调用边界检测机制
- 技能执行上下文管理
- 技能内工具调用的自动归属
- MCP 工具的技能归属
- 多技能归属冲突解决
- 技能-工具调用链路可视化

**本期不实现：**
- 技能嵌套调用追踪（暂不支持技能调用技能）
- 技能调用成本分摊计算
- 技能性能基准对比

---

## 2. 核心概念

### 2.1 技能调用的定义

技能调用是指 LLM 根据技能指令执行一系列工具操作的完整过程：

```
用户请求："帮我分析这个 PDF 文件"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                    技能调用: pdf                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ read_file   │→ │ pdf_parse   │→ │ summarize   │         │
│  │ (内置工具)   │  │ (MCP工具)   │  │ (LLM调用)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 技能调用边界检测

系统需要判断当前工具调用是否属于某个技能：

| 检测方式 | 触发条件 | 置信度 |
|---------|---------|-------|
| 显式声明 | 工具在 `uses_tools` 或 `uses_mcp_tools` 中声明 | 高 |
| 模式匹配 | 工具名匹配声明模式（如 `browser_*`） | 高 |
| 时序推断 | 技能相关工具连续调用 | 中 |
| 输入特征 | 工具输入包含技能专属特征（如 `.xlsx` 文件） | 高 |

### 2.3 技能执行上下文

```python
class SkillExecutionContext:
    """技能执行上下文"""

    skill_name: str              # 技能名称
    start_time: datetime         # 开始时间
    trigger_reason: str          # 触发原因（显式/推断）
    tools_called: list[str]      # 已调用工具列表
    mcp_tools_called: list[str]  # 已调用 MCP 工具列表
    confidence: float            # 归属置信度
```

### 2.4 多技能归属问题

当多个技能声明使用同一工具时，需要正确判定归属：

```
场景示例：

技能 A (xlsx):
  uses_mcp_tools: ["database:query"]

技能 B (report):
  uses_mcp_tools: ["database:query"]

用户请求："生成销售报表"
  → LLM 调用 database:query
  → 应归属到 report 技能
  → 需要智能判定，避免错误归属到 xlsx
```

**归属判定优先级：**
1. 当前已激活的技能 → 继续归属
2. 工具输入包含技能特征 → 切换归属
3. 最近激活的技能 → 优先归属
4. 无法确定 → 多技能权重分配

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                            │
│  - LLM Response 解析                                         │
│  - 技能意图识别                                              │
│  - 工具调用执行                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Skill Invocation Detector                 │
│  - 检测技能调用边界                                          │
│  - 管理技能执行上下文                                        │
│  - 解决多技能归属冲突                                        │
│  - 触发 Tracing 钩子                                        │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   Registry   │ │   Context    │ │   Tracing    │
    │   (映射表)    │ │   Manager    │ │   Hook       │
    └──────────────┘ └──────────────┘ └──────────────┘
```

### 3.2 模块职责

| 模块 | 职责 |
|------|------|
| `SkillInvocationDetector` | 检测技能调用边界，解决归属冲突，管理执行生命周期 |
| `SkillToolRegistry` | 维护技能→工具映射，支持归属查询，缓存优化 |
| `SkillContextManager` | 管理当前活跃的技能执行上下文 |
| `TracingHook` | 发出技能调用事件，关联工具调用 |

### 3.3 调用时序

```
┌──────┐     ┌──────────┐     ┌─────────┐     ┌─────────┐
│ LLM  │     │ Detector │     │ Context │     │ Tracing │
└──┬───┘     └────┬─────┘     └────┬────┘     └────┬────┘
   │              │                │               │
   │ tool_call    │                │               │
   │─────────────>│                │               │
   │              │                │               │
   │              │ detect_skill   │               │
   │              │───────────────>│               │
   │              │                │               │
   │              │ (if new skill) │ on_skill_start│
   │              │───────────────────────────────>│
   │              │                │               │
   │              │ get_context    │               │
   │              │<───────────────│               │
   │              │                │               │
   │              │                │ on_tool_start│
   │              │───────────────────────────────>│
   │              │                │ (with skill) │
   │              │                │               │
   │ tool_result  │                │               │
   │<─────────────│                │               │
   │              │                │               │
   │              │ (if skill end)│ on_skill_end  │
   │              │───────────────────────────────>│
   │              │                │               │
```

---

## 4. 详细设计

### 4.1 技能调用检测器（完整版）

```python
# src/swe/agents/skill_invocation_detector.py

class SkillInvocationDetector:
    """技能调用检测器

    负责检测工具调用是否属于某个技能的执行流程，
    管理技能执行的开始和结束边界，解决多技能归属冲突。
    """

    def __init__(
        self,
        registry: SkillToolRegistry,
        context_manager: SkillContextManager,
        tracing_hook: Optional[TracingHook] = None,
    ):
        self._registry = registry
        self._context_manager = context_manager
        self._tracing_hook = tracing_hook

        # 状态追踪
        self._skill_activation_time: dict[str, datetime] = {}
        self._skill_call_history: dict[str, int] = {}
        self._enabled_skills: set[str] = set()

        # 配置
        self._idle_threshold = 3
        self._idle_counters: dict[str, int] = {}

    def set_enabled_skills(self, skills: list[str]) -> None:
        """设置当前启用的技能"""
        self._enabled_skills = set(skills)

    async def on_tool_call(
        self,
        tool_name: str,
        tool_input: dict,
        mcp_server: Optional[str] = None,
    ) -> tuple[Optional[str], dict[str, float]]:
        """处理工具调用，返回主技能和权重分布

        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            mcp_server: MCP 服务器名称（如果是 MCP 工具）

        Returns:
            (primary_skill, weights)
            - primary_skill: 主归属技能
            - weights: 所有归属技能的权重分布
        """
        # 1. 查询归属技能（使用缓存优化的查询）
        skills = self._registry.get_skills_for_tool(tool_name, mcp_server)

        if not skills:
            return None, {}

        # 2. 当前激活技能检查
        current = self._context_manager.current_skill
        if current:
            if current in skills:
                # 继续当前技能
                self._update_skill_state(current)
                return current, {current: 1.0}

            # 非当前技能的工具，检查空闲
            self._idle_counters[current] = self._idle_counters.get(current, 0) + 1
            if self._idle_counters[current] >= self._idle_threshold:
                await self._end_skill(current)
                current = None

        # 3. 计算归属权重（解决多技能冲突）
        weights = self._calculate_weights(skills, tool_name, tool_input)

        # 4. 选择主技能
        primary_skill = max(weights, key=weights.get)

        # 5. 如果没有激活技能，激活新的
        if not current and primary_skill:
            await self._start_skill(primary_skill, tool_name)

        # 6. 更新状态
        self._update_skill_state(primary_skill)

        return primary_skill, weights

    async def on_reasoning_end(self) -> None:
        """LLM 推理结束时，结束所有活跃技能"""
        active_skill = self._context_manager.current_skill
        if active_skill:
            await self._end_skill(active_skill)

    def _calculate_weights(
        self,
        skills: list[str],
        tool_name: str,
        tool_input: dict,
    ) -> dict[str, float]:
        """计算归属权重

        多维度判定因子：
        1. 最近激活时间（0-0.4）
        2. 工具输入特征匹配（0-0.3）
        3. 调用频率（0-0.2）
        4. 是否启用（0-0.1）
        """
        if len(skills) == 1:
            return {skills[0]: 1.0}

        scores = {}

        for skill in skills:
            score = 0.0

            # 因子1：最近激活时间（5分钟内递减）
            if skill in self._skill_activation_time:
                elapsed = (datetime.now() - self._skill_activation_time[skill]).seconds
                recency = max(0, 0.4 * (1 - elapsed / 300))
                score += recency

            # 因子2：工具输入特征匹配
            input_score = self._match_tool_input(skill, tool_name, tool_input)
            score += input_score * 0.3

            # 因子3：调用频率
            calls = self._skill_call_history.get(skill, 0)
            frequency = min(0.2, calls * 0.02)
            score += frequency

            # 因子4：是否启用
            if skill in self._enabled_skills:
                score += 0.1

            scores[skill] = score

        # 归一化
        total = sum(scores.values())
        if total > 0:
            return {k: v / total for k, v in scores.items()}
        else:
            n = len(skills)
            return {s: 1.0 / n for s in skills}

    def _match_tool_input(
        self,
        skill: str,
        tool_name: str,
        tool_input: dict,
    ) -> float:
        """匹配工具输入特征

        检查工具输入是否包含技能专属特征：
        - 文件扩展名（xlsx → .xlsx, .csv）
        - 关键词（pdf → "PDF", "pdf"）
        """
        skill_features = self._get_skill_features(skill)
        if not skill_features:
            return 0.5

        input_str = str(tool_input).lower()
        matches = sum(1 for f in skill_features if f.lower() in input_str)

        return matches / len(skill_features)

    def _get_skill_features(self, skill: str) -> list[str]:
        """获取技能专属特征"""
        FEATURES = {
            "xlsx": [".xlsx", ".xls", ".csv", "excel", "spreadsheet"],
            "pdf": [".pdf", "PDF"],
            "docx": [".docx", ".doc", "word", "document"],
            "pptx": [".pptx", ".ppt", "powerpoint", "presentation"],
        }
        return FEATURES.get(skill, [])

    def _update_skill_state(self, skill: str) -> None:
        """更新技能状态"""
        self._skill_activation_time[skill] = datetime.now()
        self._skill_call_history[skill] = self._skill_call_history.get(skill, 0) + 1
        if skill in self._idle_counters:
            self._idle_counters[skill] = 0

    async def _start_skill(self, skill_name: str, trigger_tool: str) -> None:
        """开始技能调用"""
        self._context_manager.push_skill(skill_name)

        if self._tracing_hook:
            await self._tracing_hook.on_skill_start(
                skill_name=skill_name,
                skill_input={"trigger_tool": trigger_tool},
            )

    async def _end_skill(self, skill_name: str) -> None:
        """结束技能调用"""
        tool_count = self._skill_call_history.get(skill_name, 0)

        if self._tracing_hook:
            await self._tracing_hook.on_skill_end(
                skill_output={"tools_called": tool_count},
            )

        self._context_manager.pop_skill()
```

### 4.2 技能上下文管理器

```python
# src/swe/agents/skill_context_manager.py

from contextvars import ContextVar
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SkillExecutionContext:
    """技能执行上下文"""
    skill_name: str
    start_time: datetime
    trigger_reason: str = "inferred"
    tools_called: list[str] = field(default_factory=list)
    mcp_tools_called: list[str] = field(default_factory=list)
    confidence: float = 1.0


class SkillContextManager:
    """技能上下文管理器

    使用 ContextVar 实现请求级别的技能上下文隔离。
    """

    _current_context: ContextVar[Optional[SkillExecutionContext]] = ContextVar(
        "skill_context", default=None
    )
    _context_stack: ContextVar[list[SkillExecutionContext]] = ContextVar(
        "skill_context_stack", default=[]
    )

    def push_skill(self, skill_name: str, trigger_reason: str = "inferred") -> None:
        """开始技能执行上下文"""
        context = SkillExecutionContext(
            skill_name=skill_name,
            start_time=datetime.now(),
            trigger_reason=trigger_reason,
        )

        stack = self._context_stack.get()
        stack = stack + [context]
        self._context_stack.set(stack)
        self._current_context.set(context)

    def pop_skill(self) -> Optional[SkillExecutionContext]:
        """结束技能执行上下文"""
        stack = self._context_stack.get()
        if not stack:
            return None

        context = stack[-1]
        stack = stack[:-1]
        self._context_stack.set(stack)
        self._current_context.set(stack[-1] if stack else None)

        return context

    @property
    def current_skill(self) -> Optional[str]:
        """获取当前活跃的技能名称"""
        context = self._current_context.get()
        return context.skill_name if context else None

    @property
    def current_context(self) -> Optional[SkillExecutionContext]:
        """获取当前上下文"""
        return self._current_context.get()

    def record_tool_call(
        self,
        tool_name: str,
        mcp_server: Optional[str] = None,
    ) -> None:
        """记录工具调用"""
        context = self._current_context.get()
        if not context:
            return

        if mcp_server:
            context.mcp_tools_called.append(f"{mcp_server}:{tool_name}")
        else:
            context.tools_called.append(tool_name)

    def clear(self) -> None:
        """清理所有上下文"""
        self._current_context.set(None)
        self._context_stack.set([])


# 全局实例
_skill_context_manager: Optional[SkillContextManager] = None


def get_skill_context_manager() -> SkillContextManager:
    """获取全局技能上下文管理器"""
    global _skill_context_manager
    if _skill_context_manager is None:
        _skill_context_manager = SkillContextManager()
    return _skill_context_manager
```

### 4.3 技能-工具注册表（带缓存优化）

```python
# src/swe/agents/skill_tool_registry.py (增强版)

import re
from typing import Optional

class SkillToolRegistry:
    """技能-工具注册表

    功能：
    1. MCP 工具声明支持
    2. 模式匹配（通配符）
    3. 查询结果缓存（性能优化）
    """

    def __init__(self) -> None:
        self._skill_to_tools: dict[str, list[str]] = {}
        self._tool_to_skills: dict[str, list[str]] = {}
        self._tool_patterns: list[tuple[str, str]] = []

        # MCP 工具映射
        self._mcp_tool_to_skills: dict[str, list[str]] = {}

        # 查询缓存（性能优化）
        self._tool_to_skills_cache: dict[str, list[str]] = {}
        self._cache_valid: bool = True

    def register_skill_tools(
        self,
        skill_name: str,
        tools: list[str],
    ) -> None:
        """注册技能使用的内置工具"""
        if not tools:
            return

        self._skill_to_tools[skill_name] = list(tools)
        self._cache_valid = False

        for tool in tools:
            if "*" in tool:
                self._tool_patterns.append((tool, skill_name))
            else:
                if tool not in self._tool_to_skills:
                    self._tool_to_skills[tool] = []
                if skill_name not in self._tool_to_skills[tool]:
                    self._tool_to_skills[tool].append(skill_name)

    def register_mcp_tools(
        self,
        skill_name: str,
        mcp_tools: list[str],
    ) -> None:
        """注册技能使用的 MCP 工具

        格式：
        - "server:tool" 特定服务器的特定工具
        - "server:*" 某服务器的所有工具
        - "tool" 任意服务器的同名工具
        """
        self._cache_valid = False

        for mcp_tool in mcp_tools:
            if mcp_tool not in self._mcp_tool_to_skills:
                self._mcp_tool_to_skills[mcp_tool] = []
            if skill_name not in self._mcp_tool_to_skills[mcp_tool]:
                self._mcp_tool_to_skills[mcp_tool].append(skill_name)

    def get_skills_for_tool(
        self,
        tool_name: str,
        mcp_server: Optional[str] = None,
    ) -> list[str]:
        """获取工具归属的技能（带缓存）

        优先级：
        1. 命中缓存 → 直接返回
        2. 精确匹配 → 返回结果
        3. 模式匹配 → 返回结果
        4. MCP 工具匹配 → 返回结果
        """
        # 构建缓存 key
        cache_key = f"{mcp_server}:{tool_name}" if mcp_server else tool_name

        # 命中缓存
        if self._cache_valid and cache_key in self._tool_to_skills_cache:
            return self._tool_to_skills_cache[cache_key]

        # 计算归属
        skills: set[str] = set()

        # 普通工具精确匹配
        if tool_name in self._tool_to_skills:
            skills.update(self._tool_to_skills[tool_name])

        # 模式匹配
        for pattern, skill_name in self._tool_patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                skills.add(skill_name)

        # MCP 工具匹配
        if mcp_server:
            # 精确匹配 "server:tool"
            full_key = f"{mcp_server}:{tool_name}"
            if full_key in self._mcp_tool_to_skills:
                skills.update(self._mcp_tool_to_skills[full_key])

            # 服务器通配 "server:*"
            server_wildcard = f"{mcp_server}:*"
            if server_wildcard in self._mcp_tool_to_skills:
                skills.update(self._mcp_tool_to_skills[server_wildcard])

        # 工具名通配 "tool"（任意服务器）
        if tool_name in self._mcp_tool_to_skills:
            skills.update(self._mcp_tool_to_skills[tool_name])

        result = sorted(skills)

        # 更新缓存
        self._tool_to_skills_cache[cache_key] = result

        return result

    def rebuild_cache(self) -> None:
        """重建完整缓存"""
        if self._cache_valid:
            return

        self._tool_to_skills_cache.clear()

        # 预计算所有已知工具的归属
        for tool in self._tool_to_skills.keys():
            self._tool_to_skills_cache[tool] = self._compute_skills_for_tool(tool)

        self._cache_valid = True

    def _compute_skills_for_tool(self, tool_name: str) -> list[str]:
        """计算工具归属（内部方法）"""
        skills: set[str] = set()

        if tool_name in self._tool_to_skills:
            skills.update(self._tool_to_skills[tool_name])

        for pattern, skill_name in self._tool_patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                skills.add(skill_name)

        return sorted(skills)

    def clear(self) -> None:
        """清理所有注册"""
        self._skill_to_tools.clear()
        self._tool_to_skills.clear()
        self._tool_patterns.clear()
        self._mcp_tool_to_skills.clear()
        self._tool_to_skills_cache.clear()
        self._cache_valid = True
```

### 4.4 SKILL.md 声明格式扩展

```yaml
---
name: my_skill
description: "一个使用多个 MCP 工具的技能示例"
metadata:
  swe:
    # 内置工具声明
    uses_tools:
      - read_file
      - write_file
      - execute_shell_command

    # MCP 工具声明（新增）
    uses_mcp_tools:
      # 精确匹配：特定服务器的特定工具
      - "filesystem:read_file"
      - "filesystem:write_file"

      # 服务器通配：某服务器的所有工具
      - "database:*"

      # 工具名通配：任意服务器的同名工具
      - "search_web"

    # 技能触发关键词（可选，用于增强检测）
    trigger_keywords:
      - "分析表格"
      - "处理 Excel"
      - "生成报表"
---
```

### 4.5 TracingHook 增强

```python
# src/swe/agents/hooks/tracing.py (增强)

class TracingHook:
    """追踪钩子（增强版）"""

    def __init__(
        self,
        trace_id: str,
        user_id: str,
        session_id: str,
        channel: str,
    ):
        # ... 现有初始化 ...

        # 新增：技能上下文管理器
        self._skill_context = get_skill_context_manager()

        # 新增：技能调用检测器
        self._detector: Optional[SkillInvocationDetector] = None

    def set_detector(self, detector: "SkillInvocationDetector") -> None:
        """设置技能调用检测器"""
        self._detector = detector

    async def on_tool_start(
        self,
        tool_name: str,
        tool_input: Optional[dict[str, Any]],
        tool_call_id: Optional[str] = None,
        mcp_server: Optional[str] = None,
    ) -> str:
        """工具调用开始（增强）"""
        # 1. 让检测器处理工具调用
        if self._detector:
            await self._detector.on_tool_call(tool_name, tool_input, mcp_server)

        # 2. 如果在技能上下文中，跳过单独的工具追踪
        if self._in_skill_context:
            logger.debug(
                "Skipping tool '%s' tracing (inside skill context)",
                tool_name,
            )
            self._skill_context.record_tool_call(tool_name, mcp_server)
            return ""

        # ... 现有工具追踪逻辑 ...

    async def on_reasoning_end(self) -> None:
        """LLM 推理结束"""
        if self._detector:
            await self._detector.on_reasoning_end()
```

### 4.6 Agent 集成

```python
# src/swe/agents/react_agent.py (修改)

class SWEAgent:
    """Agent 主类"""

    def _setup_tracing(self, trace_id: str, **kwargs) -> Optional[TracingHook]:
        """设置追踪钩子"""
        if not has_trace_manager():
            return None

        hook = TracingHook(
            trace_id=trace_id,
            user_id=kwargs.get("user_id", "unknown"),
            session_id=kwargs.get("session_id", "unknown"),
            channel=kwargs.get("channel", "console"),
        )

        # 新增：创建技能调用检测器
        detector = SkillInvocationDetector(
            registry=get_skill_tool_registry(),
            context_manager=get_skill_context_manager(),
            tracing_hook=hook,
        )
        hook.set_detector(detector)

        TracingHookRegistry.register(trace_id, hook)
        return hook
```

---

## 5. 存量技能支持

### 5.1 问题说明

存量技能的 SKILL.md 未声明 `uses_tools` 或 `uses_mcp_tools`，当前逻辑无法建立工具归属：

```
工具调用 → get_skills_for_tool()
                ↓
        查询 registry（只包含显式声明的工具）
                ↓
        存量技能未声明 → 返回空列表
                ↓
        无法归属到任何技能 ❌
```

### 5.2 解决方案：多层级归属推断

**核心思路**：当显式声明缺失时，启用多层级推断机制。

```
工具调用 → get_skills_for_tool()
                ↓
        第1层：显式声明（uses_tools）→ 置信度 1.0
                ↓ 未命中
        第2层：技能特征匹配（文件类型、关键词）→ 置信度 0.8
                ↓ 未命中
        第3层：工具序列模式（预定义模式）→ 置信度 0.6
                ↓ 未命中
        第4层：技能名称关联（技能名与工具名关联）→ 置信度 0.4
                ↓ 未命中
        无法归属
```

### 5.3 技能特征推断器

```python
# src/swe/agents/skill_feature_inferencer.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class SkillFeature:
    """技能特征定义"""
    skill_name: str
    file_extensions: list[str]      # 关联的文件扩展名
    keywords: list[str]             # 触发关键词
    tools_hint: list[str]           # 可能使用的工具
    tool_patterns: list[str]        # 工具调用模式


# 内置技能特征库（无需声明即可推断）
BUILTIN_SKILL_FEATURES: dict[str, SkillFeature] = {
    "xlsx": SkillFeature(
        skill_name="xlsx",
        file_extensions=[".xlsx", ".xls", ".csv", ".tsv"],
        keywords=["excel", "spreadsheet", "表格", "工作表"],
        tools_hint=["execute_shell_command", "read_file", "write_file"],
        tool_patterns=["*.xlsx", "*.xls", "*.csv"],
    ),
    "pdf": SkillFeature(
        skill_name="pdf",
        file_extensions=[".pdf"],
        keywords=["pdf", "PDF", "PDF文档"],
        tools_hint=["execute_shell_command", "read_file"],
        tool_patterns=["*.pdf"],
    ),
    "docx": SkillFeature(
        skill_name="docx",
        file_extensions=[".docx", ".doc"],
        keywords=["word", "document", "文档"],
        tools_hint=["execute_shell_command", "read_file", "write_file"],
        tool_patterns=["*.docx", "*.doc"],
    ),
    "pptx": SkillFeature(
        skill_name="pptx",
        file_extensions=[".pptx", ".ppt"],
        keywords=["powerpoint", "presentation", "演示", "PPT"],
        tools_hint=["execute_shell_command", "read_file", "write_file"],
        tool_patterns=["*.pptx", "*.ppt"],
    ),
}


class SkillFeatureInferencer:
    """技能特征推断器

    当技能未显式声明工具时，通过特征推断归属。
    """

    def __init__(
        self,
        builtin_features: Optional[dict[str, SkillFeature]] = None,
    ):
        self._features = builtin_features or BUILTIN_SKILL_FEATURES

    def infer_skill_from_tool_input(
        self,
        tool_name: str,
        tool_input: dict,
        enabled_skills: list[str],
    ) -> tuple[Optional[str], float]:
        """从工具输入推断技能归属

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            enabled_skills: 当前启用的技能列表

        Returns:
            (skill_name, confidence) 或 (None, 0.0)
        """
        input_str = str(tool_input).lower()
        best_skill = None
        best_confidence = 0.0

        for skill_name in enabled_skills:
            feature = self._features.get(skill_name)
            if not feature:
                continue

            # 检查文件扩展名
            for ext in feature.file_extensions:
                if ext.lower() in input_str:
                    return skill_name, 0.8

            # 检查关键词
            keyword_matches = sum(
                1 for kw in feature.keywords
                if kw.lower() in input_str
            )
            if keyword_matches > 0:
                confidence = min(0.7, keyword_matches * 0.3)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_skill = skill_name

            # 检查工具提示
            if tool_name in feature.tools_hint:
                confidence = 0.5
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_skill = skill_name

        return best_skill, best_confidence

    def infer_skill_from_tool_sequence(
        self,
        recent_tools: list[str],
        enabled_skills: list[str],
    ) -> tuple[Optional[str], float]:
        """从工具调用序列推断技能

        Args:
            recent_tools: 最近调用的工具列表（按时间顺序）
            enabled_skills: 当前启用的技能列表

        Returns:
            (skill_name, confidence) 或 (None, 0.0)
        """
        # 预定义的工具序列模式
        SEQUENCE_PATTERNS = {
            "xlsx": [
                ["read_file", "execute_shell_command"],
                ["execute_shell_command", "write_file"],
            ],
            "pdf": [
                ["read_file", "execute_shell_command"],
            ],
        }

        for skill_name in enabled_skills:
            patterns = SEQUENCE_PATTERNS.get(skill_name, [])
            for pattern in patterns:
                if self._match_sequence(recent_tools, pattern):
                    return skill_name, 0.6

        return None, 0.0

    def _match_sequence(
        self,
        recent: list[str],
        pattern: list[str],
    ) -> bool:
        """检查最近工具序列是否匹配模式"""
        if len(recent) < len(pattern):
            return False

        # 检查最近 N 个工具是否匹配模式
        recent_slice = recent[-len(pattern):]
        return recent_slice == pattern

    def get_skills_for_tool(
        self,
        tool_name: str,
        enabled_skills: list[str],
    ) -> list[tuple[str, float]]:
        """获取工具可能归属的技能列表

        Returns:
            [(skill_name, confidence), ...] 按置信度降序
        """
        results = []

        for skill_name in enabled_skills:
            feature = self._features.get(skill_name)
            if not feature:
                continue

            # 检查工具是否在提示列表中
            if tool_name in feature.tools_hint:
                results.append((skill_name, 0.4))

        return sorted(results, key=lambda x: x[1], reverse=True)
```

### 5.4 增强的归属检测流程

```python
# src/swe/agents/skill_invocation_detector.py (增强)

class SkillInvocationDetector:
    """技能调用检测器（支持存量技能）"""

    def __init__(
        self,
        registry: SkillToolRegistry,
        context_manager: SkillContextManager,
        inferencer: SkillFeatureInferencer,
        tracing_hook: Optional[TracingHook] = None,
    ):
        self._registry = registry
        self._context_manager = context_manager
        self._inferencer = inferencer
        self._tracing_hook = tracing_hook

        # ... 其他初始化 ...

    async def on_tool_call(
        self,
        tool_name: str,
        tool_input: dict,
        mcp_server: Optional[str] = None,
    ) -> tuple[Optional[str], dict[str, float]]:
        """处理工具调用（支持多层级推断）"""

        # 第1层：显式声明查询
        skills = self._registry.get_skills_for_tool(tool_name, mcp_server)
        if skills:
            # 有显式声明，进入正常流程
            return self._handle_declared_skills(skills, tool_name, tool_input)

        # 第2-4层：推断归属（存量技能支持）
        return self._infer_skill_attribution(tool_name, tool_input, mcp_server)

    def _infer_skill_attribution(
        self,
        tool_name: str,
        tool_input: dict,
        mcp_server: Optional[str] = None,
    ) -> tuple[Optional[str], dict[str, float]]:
        """多层级推断技能归属"""

        enabled_skills = list(self._enabled_skills)

        # 第2层：技能特征匹配（文件类型、关键词）
        skill, confidence = self._inferencer.infer_skill_from_tool_input(
            tool_name, tool_input, enabled_skills
        )
        if skill and confidence >= 0.6:
            return skill, {skill: confidence}

        # 第3层：工具序列模式
        recent_tools = self._get_recent_tools()
        skill, confidence = self._inferencer.infer_skill_from_tool_sequence(
            recent_tools, enabled_skills
        )
        if skill and confidence >= 0.5:
            return skill, {skill: confidence}

        # 第4层：技能名称关联
        inferred = self._inferencer.get_skills_for_tool(tool_name, enabled_skills)
        if inferred:
            primary_skill = inferred[0][0]
            weights = {s: c for s, c in inferred}
            return primary_skill, weights

        # 无法归属
        return None, {}
```

### 5.5 归属置信度分级

| 层级 | 推断方式 | 置信度 | 数据来源 |
|------|---------|--------|---------|
| 1 | 显式声明 | 1.0 | SKILL.md `uses_tools` |
| 2 | 文件扩展名匹配 | 0.8 | 内置特征库 |
| 2 | 关键词匹配 | 0.5-0.7 | 内置特征库 |
| 3 | 工具序列模式 | 0.6 | 预定义模式 |
| 4 | 工具提示关联 | 0.4 | 内置特征库 |

### 5.6 归属准确率对比

| 技能类型 | 显式声明 | 推断支持 | 预期准确率 |
|---------|---------|---------|-----------|
| 新技能（有声明） | ✅ | - | 100% |
| 存量内置技能（xlsx/pdf等） | ❌ | ✅ 特征库 | 85%+ |
| 存量自定义技能（无特征） | ❌ | ❌ | 0%（无法识别） |

### 5.7 存量自定义技能支持

对于存量自定义技能，提供两种升级路径：

**路径 A：补充声明（推荐）**

```yaml
# 在 SKILL.md 中添加声明
metadata:
  swe:
    uses_tools:
      - execute_shell_command
      - read_file
    uses_mcp_tools:
      - "my_server:*"
```

**路径 B：注册特征（框架支持）**

```python
# 在技能目录下创建 skill_features.json
{
    "file_extensions": [".myext"],
    "keywords": ["mykeyword", "我的关键词"],
    "tools_hint": ["execute_shell_command"]
}
```

```python
# 自动加载特征文件
class SkillFeatureInferencer:
    def load_skill_features(self, skills_dir: Path) -> None:
        """从技能目录加载特征文件"""
        for skill_dir in skills_dir.iterdir():
            feature_file = skill_dir / "skill_features.json"
            if feature_file.exists():
                with open(feature_file) as f:
                    data = json.load(f)
                    self._features[skill_dir.name] = SkillFeature(
                        skill_name=skill_dir.name,
                        file_extensions=data.get("file_extensions", []),
                        keywords=data.get("keywords", []),
                        tools_hint=data.get("tools_hint", []),
                        tool_patterns=data.get("tool_patterns", []),
                    )
```

---

## 6. 性能分析

### 6.1 开销量化

| 操作 | 触发频率 | 单次耗时 | 估算影响 |
|------|---------|---------|---------|
| 字典精确查询 | 每次工具调用 | ~1μs | 可忽略 |
| fnmatch 模式匹配 | 缓存未命中时 | ~10μs/次 | 需优化 |
| ContextVar 读写 | 每次工具调用 | ~0.5μs | 可忽略 |
| 计数器操作 | 每次工具调用 | ~0.1μs | 可忽略 |
| 异步 Tracing 写入 | 每次技能/工具调用 | 批量处理 | 可忽略 |

### 6.2 最坏情况（无缓存）

假设：
- 10 个活跃技能
- 每个技能声明 5 个通配模式
- 每次工具调用执行 50 次 fnmatch
- 单次 fnmatch 约 10μs

**总开销：50 × 10μs = 500μs = 0.5ms**

### 6.3 缓存优化后

| 场景 | 耗时 |
|------|------|
| 缓存命中 | ~5μs（O(1) 字典查询） |
| 缓存未命中 | ~500μs（首次计算） |
| 预期命中率 | > 95% |

**优化后额外开销 < 0.01ms，对整体性能影响可忽略。**

### 6.4 性能对比

| 方案 | 单次查询耗时 | 内存占用 | 准确性 |
|------|-------------|---------|--------|
| 原方案（无优化） | ~500μs | 低 | 中 |
| + 缓存优化 | ~5μs（命中） | 中 | 中 |
| + 置信度计算 | ~50μs | 中 | 高 |
| + 模式匹配 | ~100μs | 高 | 很高 |

**推荐配置**：缓存 + 置信度计算（默认启用）

---

## 7. 数据模型变更

### 7.1 Span 模型扩展

```python
# src/swe/tracing/models.py

class Span(BaseModel):
    # ... 现有字段 ...

    # 技能归属（已存在，扩展使用）
    skill_name: Optional[str] = None
    skill_names: Optional[list[str]] = None
    skill_weights: Optional[dict[str, float]] = None

    # 新增：归属确定性
    attribution_confidence: float = 1.0
    attribution_reason: str = "declared"  # declared / inferred / multi_skill


class SkillCallDetails(BaseModel):
    """技能调用详情"""

    trigger_reason: str = "inferred"
    tools_called: list[str] = []
    mcp_tools_called: list[str] = []
    total_tool_calls: int = 0
    llm_duration_ms: int = 0
    tool_duration_ms: int = 0
    confidence: float = 1.0
```

### 7.2 数据库 Schema 扩展

```sql
-- 新增：技能调用详情表
CREATE TABLE swe_tracing_skill_calls (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trace_id VARCHAR(64) NOT NULL,
    span_id VARCHAR(64) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    trigger_reason VARCHAR(32),
    tools_called JSON,
    mcp_tools_called JSON,
    total_tool_calls INT,
    llm_duration_ms INT,
    tool_duration_ms INT,
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_trace_id (trace_id),
    INDEX idx_skill_name (skill_name),
    FOREIGN KEY (trace_id) REFERENCES swe_tracing_traces(trace_id),
    FOREIGN KEY (span_id) REFERENCES swe_tracing_spans(span_id)
);

-- 修改：Span 表增加字段
ALTER TABLE swe_tracing_spans
ADD COLUMN trigger_reason VARCHAR(32) DEFAULT NULL,
ADD COLUMN confidence FLOAT DEFAULT 1.0;
```

### 7.3 时间线层级展示数据模型

为支持追踪详情页按 **时间 + 技能→工具** 层级展示，新增以下模型：

```python
# src/swe/tracing/models.py

class ToolCallInSkill(BaseModel):
    """技能内的工具调用"""

    span_id: str
    tool_name: str
    mcp_server: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_ms: int
    status: str = "success"  # success / error
    error: Optional[str] = None


class SkillCallTimeline(BaseModel):
    """时间线中的技能调用（含工具层级）"""

    span_id: str
    skill_name: str
    start_time: datetime
    end_time: datetime
    duration_ms: int
    confidence: float = 1.0
    trigger_reason: str = "declared"  # declared / inferred / keyword

    # 该技能下的工具调用（层级结构）
    tools: list[ToolCallInSkill] = []

    # 统计
    total_tool_calls: int = 0
    tool_duration_ms: int = 0


class TimelineEvent(BaseModel):
    """时间线事件（统一格式）"""

    event_type: str  # skill_invocation / tool_call / llm_call
    start_time: datetime
    end_time: datetime
    duration_ms: int

    # 技能调用特有
    skill_name: Optional[str] = None
    confidence: Optional[float] = None
    children: list["TimelineEvent"] = []  # 层级嵌套

    # 工具调用特有
    tool_name: Optional[str] = None
    mcp_server: Optional[str] = None

    # LLM 调用特有
    model_name: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class TraceDetailWithTimeline(BaseModel):
    """追踪详情（含层级时间线）"""

    trace: Trace

    # 扁平列表（向后兼容）
    spans: list[Span] = []

    # 层级时间线（新增）
    timeline: list[TimelineEvent] = []

    # 技能调用汇总
    skill_invocations: list[SkillCallTimeline] = []

    # 统计
    llm_duration_ms: int = 0
    tool_duration_ms: int = 0
    skill_duration_ms: int = 0
    total_skills: int = 0
    total_tools: int = 0
```

### 7.4 时间线构建逻辑

```python
# src/swe/tracing/store.py

async def build_timeline(self, trace_id: str) -> list[TimelineEvent]:
    """构建层级时间线

    将扁平的 Span 列表转换为层级结构：
    - 技能调用作为父节点
    - 工具调用作为子节点嵌套在对应技能下
    """
    spans = await self.get_spans_by_trace(trace_id)

    # 按 start_time 排序
    spans.sort(key=lambda s: s.start_time)

    timeline: list[TimelineEvent] = []
    skill_stack: list[TimelineEvent] = []  # 技能嵌套栈

    for span in spans:
        if span.event_type == EventType.SKILL_INVOCATION:
            event = TimelineEvent(
                event_type="skill_invocation",
                span_id=span.span_id,
                start_time=span.start_time,
                end_time=span.end_time,
                duration_ms=span.duration_ms or 0,
                skill_name=span.skill_name,
                confidence=span.metadata.get("confidence", 1.0) if span.metadata else 1.0,
                children=[],
            )

            # 检查是否有父技能（嵌套场景）
            if skill_stack:
                skill_stack[-1].children.append(event)
            else:
                timeline.append(event)

            skill_stack.append(event)

        elif span.event_type == EventType.TOOL_CALL_START:
            event = TimelineEvent(
                event_type="tool_call",
                span_id=span.span_id,
                start_time=span.start_time,
                end_time=span.end_time,
                duration_ms=span.duration_ms or 0,
                tool_name=span.tool_name,
                mcp_server=span.mcp_server,
            )

            # 归属到当前技能
            if skill_stack:
                skill_stack[-1].children.append(event)
            else:
                timeline.append(event)

        elif span.event_type == EventType.SKILL_INVOCATION_END:
            # 弹出技能栈
            if skill_stack:
                skill_stack.pop()

    return timeline
```

---

## 8. API 增强

### 8.1 新增端点

| 方法 | 路径 | 说明 |
|-----|------|------|
| GET | `/api/tracing/skills/{skill_name}/tools` | 技能使用的工具统计 |
| GET | `/api/tracing/skills/{skill_name}/mcp` | 技能使用的 MCP 工具统计 |
| GET | `/api/tracing/skills/attribution` | 技能-工具归属详情 |

### 8.2 技能详情响应

```json
{
    "skill_name": "xlsx",
    "total_calls": 150,
    "avg_duration_ms": 2500,
    "success_rate": 0.98,
    "tools_used": [
        {
            "tool_name": "execute_shell_command",
            "count": 300,
            "avg_duration_ms": 800,
            "is_mcp": false
        },
        {
            "tool_name": "database:query",
            "count": 50,
            "avg_duration_ms": 200,
            "is_mcp": true,
            "mcp_server": "database"
        }
    ],
    "mcp_servers_used": ["database", "filesystem"],
    "trigger_reasons": {
        "inferred": 100,
        "declared": 50
    },
    "avg_confidence": 0.95
}
```

### 8.3 多技能归属响应

```json
{
    "tool_name": "database:query",
    "total_calls": 100,
    "skill_attribution": {
        "xlsx": {
            "calls": 30,
            "weight": 0.30,
            "confidence": 0.8
        },
        "report": {
            "calls": 70,
            "weight": 0.70,
            "confidence": 0.9
        }
    },
    "ambiguous_calls": 15,
    "avg_confidence": 0.85
}
```

### 8.4 追踪详情时间线响应

**端点**：`GET /api/tracing/traces/{trace_id}/timeline`

**响应示例**：

```json
{
    "trace_id": "tr_abc123",
    "user_id": "user1",
    "session_id": "session1",
    "channel": "console",
    "status": "completed",
    "start_time": "2026-04-10T10:00:00Z",
    "end_time": "2026-04-10T10:00:30Z",
    "duration_ms": 30000,

    "timeline": [
        {
            "event_type": "llm_call",
            "start_time": "2026-04-10T10:00:00Z",
            "end_time": "2026-04-10T10:00:02Z",
            "duration_ms": 2000,
            "model_name": "gpt-4",
            "input_tokens": 150,
            "output_tokens": 80,
            "children": []
        },
        {
            "event_type": "skill_invocation",
            "start_time": "2026-04-10T10:00:02Z",
            "end_time": "2026-04-10T10:00:15Z",
            "duration_ms": 13000,
            "skill_name": "xlsx",
            "confidence": 0.95,
            "children": [
                {
                    "event_type": "tool_call",
                    "start_time": "2026-04-10T10:00:03Z",
                    "end_time": "2026-04-10T10:00:04Z",
                    "duration_ms": 1000,
                    "tool_name": "read_file",
                    "mcp_server": null,
                    "children": []
                },
                {
                    "event_type": "tool_call",
                    "start_time": "2026-04-10T10:00:05Z",
                    "end_time": "2026-04-10T10:00:12Z",
                    "duration_ms": 7000,
                    "tool_name": "execute_shell_command",
                    "mcp_server": null,
                    "children": []
                }
            ]
        },
        {
            "event_type": "skill_invocation",
            "start_time": "2026-04-10T10:00:15Z",
            "end_time": "2026-04-10T10:00:25Z",
            "duration_ms": 10000,
            "skill_name": "pdf",
            "confidence": 0.90,
            "children": [
                {
                    "event_type": "tool_call",
                    "start_time": "2026-04-10T10:00:16Z",
                    "end_time": "2026-04-10T10:00:18Z",
                    "duration_ms": 2000,
                    "tool_name": "pdf_parse",
                    "mcp_server": "filesystem",
                    "children": []
                }
            ]
        },
        {
            "event_type": "llm_call",
            "start_time": "2026-04-10T10:00:25Z",
            "end_time": "2026-04-10T10:00:30Z",
            "duration_ms": 5000,
            "model_name": "gpt-4",
            "input_tokens": 500,
            "output_tokens": 300,
            "children": []
        }
    ],

    "skill_invocations": [
        {
            "skill_name": "xlsx",
            "start_time": "2026-04-10T10:00:02Z",
            "end_time": "2026-04-10T10:00:15Z",
            "duration_ms": 13000,
            "confidence": 0.95,
            "trigger_reason": "inferred",
            "tools": [
                {
                    "tool_name": "read_file",
                    "start_time": "2026-04-10T10:00:03Z",
                    "duration_ms": 1000
                },
                {
                    "tool_name": "execute_shell_command",
                    "start_time": "2026-04-10T10:00:05Z",
                    "duration_ms": 7000
                }
            ],
            "total_tool_calls": 2,
            "tool_duration_ms": 8000
        },
        {
            "skill_name": "pdf",
            "start_time": "2026-04-10T10:00:15Z",
            "end_time": "2026-04-10T10:00:25Z",
            "duration_ms": 10000,
            "confidence": 0.90,
            "trigger_reason": "declared",
            "tools": [
                {
                    "tool_name": "pdf_parse",
                    "mcp_server": "filesystem",
                    "start_time": "2026-04-10T10:00:16Z",
                    "duration_ms": 2000
                }
            ],
            "total_tool_calls": 1,
            "tool_duration_ms": 2000
        }
    ],

    "summary": {
        "llm_duration_ms": 7000,
        "tool_duration_ms": 10000,
        "skill_duration_ms": 23000,
        "total_skills": 2,
        "total_tools": 3,
        "total_llm_calls": 2
    }
}
```

### 8.5 前端时间线渲染示例

```html
<!-- 时间线组件渲染示例 -->
<div class="timeline">
    <!-- LLM 调用 -->
    <div class="event llm-call" style="margin-left: 0">
        <span class="time">10:00:00 - 10:00:02</span>
        <span class="type">LLM</span>
        <span class="detail">gpt-4 (150→80 tokens)</span>
    </div>

    <!-- 技能调用（带子事件） -->
    <div class="event skill-invocation" style="margin-left: 0">
        <span class="time">10:00:02 - 10:00:15</span>
        <span class="type">技能</span>
        <span class="detail">xlsx (置信度 95%)</span>

        <!-- 嵌套的工具调用 -->
        <div class="children">
            <div class="event tool-call" style="margin-left: 20px">
                <span class="time">10:00:03 - 10:00:04</span>
                <span class="type">工具</span>
                <span class="detail">read_file</span>
            </div>
            <div class="event tool-call" style="margin-left: 20px">
                <span class="time">10:00:05 - 10:00:12</span>
                <span class="type">工具</span>
                <span class="detail">execute_shell_command</span>
            </div>
        </div>
    </div>

    <!-- 另一个技能调用 -->
    <div class="event skill-invocation" style="margin-left: 0">
        <span class="time">10:00:15 - 10:00:25</span>
        <span class="type">技能</span>
        <span class="detail">pdf (置信度 90%)</span>

        <div class="children">
            <div class="event tool-call" style="margin-left: 20px">
                <span class="time">10:00:16 - 10:00:18</span>
                <span class="type">工具 (MCP)</span>
                <span class="detail">filesystem:pdf_parse</span>
            </div>
        </div>
    </div>
</div>
```

---

## 9. 监控指标

```python
# Prometheus 指标
skill_attribution_duration = Histogram(
    "skill_attribution_duration_seconds",
    "Skill attribution latency",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1],
)

skill_cache_hits = Counter(
    "skill_cache_hits_total",
    "Skill tool cache hits",
    ["result"],  # hit / miss
)

multi_skill_attribution = Counter(
    "multi_skill_attribution_total",
    "Multi-skill tool attributions",
    ["skill_count"],
)
```

---

## 10. 向后兼容

### 10.1 配置兼容

现有配置无需修改即可升级：

```python
# 默认行为：如果未声明 uses_mcp_tools，仍通过 uses_tools 推断
def get_skills_for_tool(tool_name, mcp_server=None):
    # 优先使用 MCP 工具声明
    if mcp_server:
        mcp_skills = self.get_skills_for_mcp_tool(tool_name, mcp_server)
        if mcp_skills:
            return mcp_skills

    # 回退到普通工具声明
    return self._get_skills_for_regular_tool(tool_name)
```

### 10.2 数据迁移

现有数据无需迁移，新字段使用默认值。

---

## 11. 测试计划

### 11.1 单元测试

| 测试项 | 描述 |
|-------|------|
| `test_detect_skill_boundary` | 测试技能边界检测 |
| `test_mcp_tool_attribution` | 测试 MCP 工具归属 |
| `test_idle_threshold` | 测试空闲阈值结束技能 |
| `test_context_isolation` | 测试上下文隔离 |
| `test_pattern_matching` | 测试通配符模式匹配 |
| `test_multi_skill_conflict` | 测试多技能归属冲突 |
| `test_cache_optimization` | 测试缓存优化效果 |
| `test_attribution_weights` | 测试归属权重计算 |

### 11.2 集成测试

| 测试项 | 描述 |
|-------|------|
| `test_skill_with_mcp_tools` | 端到端：使用 MCP 工具的技能 |
| `test_multi_skill_session` | 多技能会话追踪 |
| `test_tracing_persistence` | 追踪数据持久化 |

---

## 12. 实施计划

### 12.1 阶段一：核心实现（2天）

1. 实现 `SkillContextManager`
2. 实现 `SkillInvocationDetector`（含多技能归属）
3. 增强 `SkillToolRegistry`（含缓存优化）
4. 集成到 `TracingHook`

### 12.2 阶段二：数据层（1天）

1. 扩展 Span 模型
2. 数据库 Schema 变更
3. 统计查询实现

### 12.3 阶段三：API 与文档（1天）

1. 新增 API 端点
2. 更新 SKILL.md 模板
3. 编写测试用例

---

## 13. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 技能边界误判 | 工具归属错误技能 | 多维度判定 + 置信度标记 |
| MCP 工具声明缺失 | 无法建立归属 | 提供声明模板，支持通配符 |
| 多技能归属冲突 | 归属准确率下降 | 时序 + 输入特征 + 权重分配 |
| 性能影响 | 追踪开销增加 | 缓存优化，异步写入 |
| 内存占用 | 缓存占用内存 | LRU 缓存淘汰 |

---

## 14. 归属准确率预期

| 场景 | 方案 | 准确率 |
|------|------|--------|
| 单技能声明工具 | 直接归属 | 100% |
| 多技能声明同一工具 | 时序 + 置信度 | 85%+ |
| 无声明工具 | 模式匹配推断 | 70%+ |

**结论**：通过多维度判定，可将归属准确率从 50%（随机）提升到 85%+。

---

## 15. 版本历史

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| 1.0.0 | 2026-04-10 | 初始设计文档 |
| 1.1.0 | 2026-04-10 | 合并性能分析与多技能归属解决方案 |
| 1.2.0 | 2026-04-10 | 新增存量技能支持（§5 多层级归属推断） |
| 1.2.1 | 2026-04-10 | 修正命名空间示例为 `swe`，添加兼容性说明 |
| 1.3.0 | 2026-04-10 | 新增时间线层级展示数据模型（§7.3-7.4）、API 响应格式（§8.4-8.5） |
