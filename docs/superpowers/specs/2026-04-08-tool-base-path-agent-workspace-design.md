# 工具默认基础路径切换到 Agent Workspace 设计

**日期**: 2026-04-08
**主题**: tool-base-path-agent-workspace
**状态**: 已实现

---

## 1. 概述

### 1.1 背景

当前多租户路径隔离已经在内建工具中落地，但默认基础路径的语义并不统一：

- `file_io`、`file_search` 在存在 `current_workspace_dir` 时，默认优先使用当前 agent 的 `workspace_dir`
- `shell` 在 `cwd=None` 时，仍默认回退到租户根目录 `WORKING_DIR/<tenant_id>`
- `browser_control`、`desktop_screenshot` 也各自维护了类似但不完全一致的默认路径逻辑

这导致同一 agent 会话内，不同工具对“相对路径从哪里开始解析”这一点存在分叉。用户期望的是：如果当前请求已经绑定到某个 agent，那么未显式传入路径参数时，工具默认都应从该 agent 对应的 workspace 开始工作。

### 1.2 目标

统一本地路径类工具的默认基础路径语义：

- 在存在 `current_workspace_dir` 上下文时，默认基础路径使用当前 agent 的 `workspace_dir`
- 在不存在 `current_workspace_dir` 但存在租户上下文时，兼容回退到租户根目录
- 保持现有 tenant boundary 安全模型不变
- 消除各工具各自实现默认基路径逻辑的分叉

### 1.3 非目标

本次设计不包含以下变更：

- 不把安全边界从 tenant 级下沉到 agent 级
- 不限制工具显式访问同 tenant 下其他绝对路径
- 不调整 agent 配置、provider 配置、memory 目录等路径 helper
- 不修改非本地路径工具的行为

### 1.4 成功标准

- `shell`、文件读写类工具、文件搜索类工具、浏览器本地输出工具的默认基础路径语义统一
- 当前 agent 会话中未显式传入路径时，默认落到 `workspace_dir`
- 无 `workspace_dir` 场景仍兼容租户根目录回退
- 现有 tenant boundary 拒绝跨租户访问的能力不回退

---

## 2. 当前问题

### 2.1 现状

当前代码中已有两层路径语义：

- 安全边界：由 `tenant_path_boundary` 控制，限制所有解析后的路径必须位于 `WORKING_DIR/<tenant_id>` 内
- 默认基础路径：由各工具自行决定，相对路径在没有显式绝对路径时从哪里解析

问题不在安全边界本身，而在默认基础路径未统一。

### 2.2 用户可见问题

在同一个 agent 会话里：

- `read_file("a.txt")` 可能从 agent workspace 读取
- `grep_search()` 可能只在 agent workspace 内搜索
- `execute_shell_command("ls")` 却可能在租户根目录执行

这会造成以下问题：

- 用户对相对路径解析位置产生误判
- 工具组合使用时行为不一致
- 需要额外显式传 `cwd` 才能让 `shell` 与文件工具对齐
- 后续新工具容易继续复制这种不一致

---

## 3. 设计原则

### 3.1 统一默认语义

只要当前请求已绑定 agent 的 `workspace_dir`，所有本地路径工具都默认以该目录作为基础路径。

### 3.2 安全模型不变

默认基础路径的变化不改变最终授权边界。即使默认落在 agent workspace，工具的最终允许访问范围仍然是当前 tenant 根目录内的路径。

### 3.3 兼容优先

对于 CLI、后台任务、测试等没有显式绑定 `workspace_dir` 的场景，继续允许回退到 tenant root，而不是直接报错。

### 3.4 单点收敛

默认基础路径规则应集中在共享 helper 中实现，避免 `shell`、`file_io`、`file_search`、`browser_control`、`desktop_screenshot` 重复维护各自版本。

---

## 4. 方案比较

### 4.1 方案 A：只修补 shell

仅修改 `shell.execute_shell_command(..., cwd=None)` 的默认行为，使其优先使用 `current_workspace_dir`。

优点：

- 改动最小
- 风险最低

缺点：

- 默认路径规则仍分散在多个工具中
- 后续工具容易继续不一致
- 不能从结构上消除重复逻辑

### 4.2 方案 B：引入共享默认基础路径 helper

新增共享 helper，统一返回当前工具应使用的默认基础路径：

- 有 `current_workspace_dir` 时，返回 agent `workspace_dir`
- 否则回退到当前 tenant root

所有本地路径工具统一依赖这个 helper。

优点：

- 语义统一
- 实现集中
- 易于测试和后续扩展
- 与现有 tenant boundary 设计兼容

缺点：

- 需要调整多个工具文件
- 需要补充更多回归测试

### 4.3 方案 C：强制 agent-only

所有本地路径工具都要求必须存在 `workspace_dir` 上下文，否则直接报错。

优点：

- 默认行为最清晰
- agent 会话隔离表达更强

缺点：

- 会打破 CLI / 后台场景兼容性
- 需要更大范围梳理上下文绑定入口
- 超出本次目标

### 4.4 结论

选择方案 B。

它可以在不改变 tenant 安全边界的前提下，统一默认路径语义，并且兼顾已有非 agent 场景的兼容性。

---

## 5. 详细设计

### 5.1 新增共享 helper

在 `src/swe/security/tenant_path_boundary.py` 中新增共享 helper，例如：

- `get_current_tool_base_dir()`

语义：

1. 读取 `current_workspace_dir`
2. 如果存在：
   - 校验该目录位于当前 tenant root 内
   - 返回该目录
3. 如果不存在：
   - 返回 `get_current_tenant_root()`

异常行为：

- 如果 tenant 上下文缺失，沿用现有 tenant boundary 错误
- 如果 `workspace_dir` 超出 tenant boundary，抛出路径越界错误

### 5.2 shell 工具调整

文件：`src/swe/agents/tools/shell.py`

调整点：

- `_resolve_cwd(cwd=None)` 不再直接返回 tenant root
- 当 `cwd is None` 时，调用共享 helper 获取默认基础路径
- 相对路径校验继续使用最终 `working_dir` 作为 `base_dir`

结果：

- `execute_shell_command("ls")` 会在当前 agent workspace 执行
- `execute_shell_command("cat file.txt")` 的相对路径校验也基于 agent workspace

### 5.3 文件读写工具调整

文件：`src/swe/agents/tools/file_io.py`

调整点：

- `_resolve_file_path()` 不再直接读取 `get_current_workspace_dir()`
- 改为调用共享 helper 作为 `resolve_tenant_path(..., base_dir=...)` 的 base

结果：

- `read_file/write_file/edit_file/append_file` 的默认相对路径语义与 `shell` 保持一致

### 5.4 文件搜索工具调整

文件：`src/swe/agents/tools/file_search.py`

调整点：

- 无 `path` 参数时，默认搜索根目录改为共享 helper
- 有 `path` 参数时，若为相对路径，解析 base 也统一使用共享 helper

结果：

- `grep_search()` / `glob_search()` 的默认搜索根目录与其他工具一致

### 5.5 其他本地路径工具对齐

至少纳入本次统一的工具：

- `src/swe/agents/tools/browser_control.py`
- `src/swe/agents/tools/desktop_screenshot.py`

原因：

- 二者都存在“使用 `workspace_dir or WORKING_DIR`”的默认目录逻辑
- 若本次不对齐，会继续留下工具间不一致

### 5.6 文档与注释同步

需要同步更新以下内容：

- `shell.py` 中关于默认 `cwd` 的 docstring
- `file_io.py` 中关于“current tenant workspace”的注释，改为“current agent workspace if available, otherwise tenant workspace”
- `file_search.py` 和其他相关工具中的默认路径说明

---

## 6. 兼容性与行为边界

### 6.1 保持不变的行为

以下行为本次不变：

- 工具仍然不能跨 tenant 访问路径
- tenant root 仍是最终授权边界
- 显式绝对路径只要位于当前 tenant 内，仍然允许访问
- 无 `workspace_dir` 上下文时，仍允许回退到 tenant root

### 6.2 变化的行为

以下行为会变化：

- `shell` 在 `cwd=None` 时不再默认运行于 tenant root，而是当前 agent workspace
- `grep_search()` / `glob_search()` 未传 `path` 时默认只搜索当前 agent workspace
- 其他采用共享 helper 的工具，其默认输出目录或默认读取目录会优先使用 agent workspace

### 6.3 风险点

主要风险不在安全性，而在兼容性预期：

- 少量已有测试可能默认假设 `shell` 运行在 tenant root
- 某些依赖“tenant root 为默认 cwd”的老逻辑，可能需要改为显式传 `cwd`
- 不同工具原本分散的注释和错误文案可能与新行为不一致

这些风险可以通过定向单测和文案同步控制。

---

## 7. 测试设计

### 7.1 tenant_path_boundary 单测

文件：`tests/unit/test_tenant_path_boundary.py`

新增验证：

- 有 `tenant_id + workspace_dir` 时，共享 helper 返回 workspace_dir
- 无 `workspace_dir` 时，共享 helper 回退到 tenant root
- 若 `workspace_dir` 不在 tenant 内，共享 helper 拒绝

### 7.2 shell 单测

文件：`tests/unit/test_shell_tenant_boundary.py`

新增或调整验证：

- `cwd=None` 时默认使用当前 agent workspace
- shell 中的相对路径解析基于 agent workspace
- `../` 仍不能逃出租户边界
- 显式 sibling tenant 绝对路径仍被拒绝

### 7.3 文件工具回归测试

建议新增或扩展工具回归测试，覆盖：

- `read_file/write_file/edit_file/append_file` 相对路径相对当前 agent workspace
- `grep_search()` / `glob_search()` 默认只扫描当前 agent workspace
- 当 tenant 下存在多个 agent workspace 时，默认搜索或读写不会自动落到其他 workspace

### 7.4 其他工具定向测试

对 `browser_control` 与 `desktop_screenshot` 补充基础路径测试，验证它们也遵循共享 helper。

---

## 8. 实施步骤

1. 在 `tenant_path_boundary.py` 增加共享默认基础路径 helper
2. 修改 `shell.py` 使用共享 helper
3. 修改 `file_io.py` 使用共享 helper
4. 修改 `file_search.py` 使用共享 helper
5. 对齐 `browser_control.py` 与 `desktop_screenshot.py`
6. 更新相关注释和 docstring
7. 补充单元测试与回归测试

---

## 9. 验收标准

- 同一 agent 会话内，本地路径工具对相对路径的默认解析位置一致
- `shell` 默认 `cwd` 与文件工具默认路径一致
- tenant boundary 拒绝跨租户访问的测试仍通过
- 无 `workspace_dir` 场景的兼容回退仍通过
