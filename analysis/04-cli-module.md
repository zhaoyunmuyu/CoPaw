# CoPaw CLI 模块分析文档

## 概述

`src/copaw/cli/` 模块提供 CoPaw 的命令行接口，实现所有用户可见的管理命令。

---

## 模块结构

**位置**: `src/copaw/cli/`

| 文件 | 用途 |
|------|---------|
| `main.py` | 主入口点，延迟加载的命令组 |
| `utils.py` | 交互式提示辅助工具 |
| `env_cmd.py` | 环境变量管理命令 |
| `providers_cmd.py` | 提供商和模型管理命令 |

---

## 核心组件

### LazyGroup (`main.py`)

**设计模式**: 延迟加载模式 - 命令仅在调用时导入，减少启动时间。

```python
class LazyGroup(click.Group):
    """支持延迟加载子命令的自定义 Click 组"""

    def get_command(self, ctx, cmd_name):
        # 仅在需要时导入命令模块
        ...
```

### 主入口点

```python
@click.group(cls=LazyGroup)
def cli():
    """CoPaw CLI 主入口"""
```

**可用子命令**:
- `app` - 运行 FastAPI 应用
- `channels` - 通道管理
- `daemon` - 守护进程管理
- `chats` - 聊天历史管理
- `clean` - 清理操作
- `cron` - 定时任务管理
- `env` - 环境变量管理
- `init` - 初始化配置
- `models` - 提供商和模型管理
- `skills` - 技能管理

---

## 交互式工具 (`utils.py`)

使用 `questionary` 库的集中式交互提示：

| 函数 | 用途 |
|----------|---------|
| `prompt_confirm()` | 带键盘导航的确认提示 |
| `prompt_path()` | 带存在验证的路径输入 |
| `prompt_choice()` | 字符串选项单选 |
| `prompt_select()` | (标签, 值)对单选 |
| `prompt_checkbox()` | 带"全选"开关的多选 |

---

## 环境命令 (`env_cmd.py`)

环境变量管理命令：

| 命令 | 描述 |
|--------|-------------|
| `copaw env list` | 列出所有环境变量 |
| `copaw env set` | 设置环境变量 |
| `copaw env delete` | 删除环境变量 |

**交互式辅助**:
- `configure_env_interactive()` - 添加/编辑环境变量的交互流程

---

## 模型命令 (`providers_cmd.py`)

提供商和模型管理：

| 命令 | 描述 |
|--------|-------------|
| `copaw models list` | 列出所有提供商和模型 |
| `copaw models config` | 配置提供商 |
| `copaw models set-llm` | 设置当前使用的模型 |
| `copaw models add-provider` | 添加新提供商 |
| `copaw models remove-provider` | 移除提供商 |
| `copaw models download` | 下载本地模型 |
| `copaw models local` | 本地模型管理 |

**交互式辅助**:
- `configure_llm_slot_interactive()` - LLM 模型选择的交互流程
- `configure_providers_interactive()` - 完整提供商设置流程

---

## 应用命令 (`app_cmd.py`)

FastAPI 应用运行器：

```python
@click.command()
@click.option("--reload", is_flag=True, help="开发模式热重载")
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8088)
def app_cmd(reload, host, port, log_level):
    """使用 uvicorn 运行 CoPaw FastAPI 应用"""
```

**特性**:
- 支持 `--reload` 用于开发
- 自定义 `--host`, `--port`, `--log-level`
- `SuppressPathAccessLogFilter` - 过滤 uvicorn 访问日志

---

## 数据流

```
用户调用 copaw <command>
        ↓
LazyGroup 加载特定命令模块
        ↓
命令与相应管理器交互（ProviderManager, LocalModelManager 等）
        ↓
结果通过 Click 输出函数显示
```

---

## 设计模式

| 模式 | 实现 |
|---------|---------------|
| **延迟加载** | `LazyGroup` 仅在调用时导入命令 |
| **命令模式** | Click 命令结构 |
| **交互式流程** | `questionary` 库提示 |