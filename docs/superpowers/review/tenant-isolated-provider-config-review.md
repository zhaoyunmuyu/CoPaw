# tenant-isolated-provider-config 代码检视补充报告

- 检视范围：tenant-isolated provider config 改动中的问题 2、问题 3
- 参考设计：`openspec/changes/tenant-isolated-provider-config/design.md`
- 重点文件：
  - `src/copaw/app/middleware/tenant_workspace.py`
  - `src/copaw/cli/providers_cmd.py`
- 检视目标：分析并发初始化与 CLI 多租户支持两个问题的根因、影响范围与修复建议

---

## 一、总体结论

这两个问题都不是“代码风格”层面的问题，而是会直接影响多租户 provider 配置正确性的实现缺陷：

1. `TenantWorkspaceMiddleware` 中租户 provider 配置初始化的加锁方案不成立，在并发场景下可能把新 tenant 初始化成**空配置**或**不完整配置**。
2. `copaw models` 虽然引入了 `--tenant-id`，但交互式子命令没有把 tenant 透传到底层 manager，导致用户以为自己在操作某个 tenant，实际却修改了 `default`。

这两个问题都会破坏设计文档要求的“tenant-isolated provider configuration”。前者破坏**首次初始化正确性**，后者破坏**运维/管理操作正确性**。

---

## 二、问题 2：provider 初始化加锁存在并发竞态

### 2.1 相关代码位置

- `src/copaw/app/middleware/tenant_workspace.py:242-337`
- 核心逻辑位于 `_ensure_provider_config()`

关键片段：

```python
with open(lock_file, "w", encoding="utf-8") as f:
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        time.sleep(0.1)
        if tenant_providers_dir.exists():
            return
        # Otherwise continue with initialization
```

后续又会继续执行：

- `shutil.copytree(default_dir, tenant_providers_dir)`
- 或创建空目录结构

异常分支里还会兜底：

```python
if not tenant_providers_dir.exists():
    tenant_providers_dir.mkdir(parents=True, exist_ok=True)
    (tenant_providers_dir / "builtin").mkdir(exist_ok=True)
    (tenant_providers_dir / "custom").mkdir(exist_ok=True)
```

### 2.2 根因分析

当前实现的问题不在于“用了文件锁”，而在于**拿不到锁时仍可能继续执行初始化逻辑**。

实际执行路径如下：

1. 请求 A 进入，发现 `tenant_providers_dir` 不存在。
2. 请求 A 成功获取锁，开始从 `default/providers` 复制。
3. 请求 B 几乎同时进入，也发现 `tenant_providers_dir` 不存在。
4. 请求 B 获取锁失败，进入 `except`。
5. 请求 B 仅 `sleep(0.1)` 一次，然后重新检查目录。
6. 如果此时请求 A 还没复制完成，`tenant_providers_dir` 仍可能不存在。
7. 请求 B 会**继续往下执行初始化分支**，尽管它并没有拿到锁。

这就违反了“只有锁持有者才能做初始化”的基本约束。

### 2.3 会导致什么问题

#### 场景 A：`copytree()` 冲突

如果 A 正在复制，B 也进入 `copytree()`，可能触发文件已存在、目录状态变化等异常。

#### 场景 B：异常后退化成空目录

更严重的是，异常分支会把初始化失败直接兜底为：

- 创建 `providers/`
- 创建 `builtin/`
- 创建 `custom/`

但**不会补齐 default tenant 中已有的 provider 配置文件**。

结果就是：

- 设计上应当“继承 default tenant provider config”的新 tenant
- 实际可能只得到一个空壳目录
- 表现为 tenant 首次访问时 provider 列表、API key、active model 等状态异常

这不是临时失败，而是**持久化错误状态**：目录一旦建出来，后续 fast path 会直接 `return`，错误配置就被固化了。

### 2.4 为什么这是高优先级缺陷

因为这个问题满足以下三个条件：

- 发生在 tenant 首次初始化路径上
- 结果会落盘，影响后续所有请求
- 会让“继承 default 配置”的核心能力失效

也就是说，它不是偶发 warning，而是会造成真实租户数据状态错误。

### 2.5 修复建议

#### 建议 1：没有拿到锁就不要继续初始化

这是最核心的修正。

拿不到锁时，应该：

- 阻塞等待锁释放；或
- 重试直到确认目录已创建；或
- 明确失败返回

但**不能在未持锁情况下继续执行初始化**。

建议改法：

- 使用阻塞式 `LOCK_EX`，拿到锁后再做第二次 existence check
- 或保留 non-blocking，但要用循环等待，直到：
  - 成功拿到锁；或
  - 发现目录已由其他进程初始化完成

推荐伪代码：

```python
with open(lock_file, "w", encoding="utf-8") as f:
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except (IOError, OSError):
            if tenant_providers_dir.exists():
                return
            time.sleep(0.05)

    if tenant_providers_dir.exists():
        return

    # only lock owner may initialize
```

如果不担心阻塞时长，直接用阻塞式 exclusive lock 反而更简单可靠。

#### 建议 2：复制失败时不要静默退化为空配置

当前异常处理把“复制失败”与“default 本来为空”混为一谈，这是不对的。

应该区分：

- **预期情况**：default tenant 没有 provider 配置，此时创建空目录是合理的
- **异常情况**：本应复制成功，但复制中断/冲突/权限问题失败，此时应当报错并中止，而不是生成空壳配置

建议：

- 仅在 `default_dir` 不存在或确实为空时创建空目录
- 若 `copytree()` 失败，应记录 error 并抛出，让请求失败，而不是 silently degrade

否则会把并发 bug、磁盘异常、权限问题伪装成“成功初始化”。

#### 建议 3：锁文件清理策略要更保守

当前 `finally` 中无条件 `unlink(lock_file)`：

```python
if lock_file.exists():
    lock_file.unlink()
```

这在大多数情况下可能能工作，但在多进程竞争下并不稳妥：

- 一个进程可能还持有该文件描述符对应的锁
- 另一个进程已经重新打开/复用了同路径文件

更稳妥的做法：

- 可以保留锁文件常驻，只依赖 `flock` 管理互斥，不需要每次删除
- 如果一定要删除，也应确保只有当前持锁方在完成后删除，并评估竞态窗口

对这种“只作为锁载体”的文件，**不删除通常比频繁删除更安全**。

#### 建议 4：补一组并发初始化测试

建议新增测试覆盖：

1. 同一 tenant 两个并发初始化请求
   - 断言最终结果为完整复制 default 配置
2. `copytree()` 失败
   - 断言不会留下伪成功的空配置
3. default 为空时初始化
   - 断言生成空目录结构是允许的

没有这组测试，后续很容易再次回归。

---

## 三、问题 3：CLI 子命令没有真正支持 `--tenant-id`

### 3.1 相关代码位置

- `src/copaw/cli/providers_cmd.py:473-485`
- `src/copaw/cli/providers_cmd.py:563-582`
- `src/copaw/cli/providers_cmd.py:133-165`
- `src/copaw/cli/providers_cmd.py:350-470`

`models_group()` 已经把 tenant_id 存进 Click context：

```python
ctx.obj["tenant_id"] = tenant_id
```

但交互式命令路径没有把这个值继续往下传。

例如：

```python
@models_group.command("config")
def config_cmd() -> None:
    configure_providers_interactive()
```

而 `configure_providers_interactive()` 内部调用：

- `configure_provider_api_key_interactive()`
- `_manager()`
- `configure_llm_slot_interactive()`

这些函数默认都会走：

```python
def _manager(tenant_id: str | None = None) -> ProviderManager:
    return ProviderManager.get_instance(tenant_id)
```

也就是 **tenant_id 未透传时回落到 default tenant**。

### 3.2 问题本质

这是一个“入口支持了多租户，但执行链路没有完整透传上下文”的问题。

换句话说：

- CLI 表面上暴露了 `--tenant-id`
- 非交互式部分命令确实用了它
- 但交互式配置命令仍偷偷操作默认租户

这种问题比“完全不支持 tenant-id”更危险，因为它会制造**错误的安全感**。

### 3.3 受影响命令

当前明确有问题的包括：

- `copaw models config`
- `copaw models config-key`
- `copaw models set-llm`

以及这些命令内部调用链上的交互辅助函数：

- `_select_provider_interactive()`
- `configure_provider_api_key_interactive()`
- `_add_models_interactive()`
- `configure_llm_slot_interactive()`
- `configure_providers_interactive()`

这些函数目前都没有 `tenant_id` 参数，或者虽然调用 `_manager()`，但没有传 tenant。

### 3.4 用户实际会遇到的错误行为

例如用户执行：

```bash
copaw models --tenant-id alice config
```

用户预期：

- 配置 `alice` 的 provider、API key、active model

实际结果可能是：

- 修改了 `default` tenant 的 provider 配置
- `alice` 仍保持未配置状态
- 后续排查时极难发现是 CLI 路径写错 tenant，而不是 provider 自身有问题

这会直接破坏多租户隔离的管理语义。

### 3.5 修复建议

#### 建议 1：给所有交互辅助函数显式加 `tenant_id` 参数

建议把以下函数统一改成显式接收 `tenant_id`：

- `_select_provider_interactive(..., tenant_id: str | None = None)`
- `configure_provider_api_key_interactive(..., tenant_id: str | None = None)`
- `_add_models_interactive(provider_id: str, tenant_id: str | None = None)`
- `configure_llm_slot_interactive(*, use_defaults: bool = False, tenant_id: str | None = None)`
- `configure_providers_interactive(*, use_defaults: bool = False, tenant_id: str | None = None)`

然后所有内部 `_manager()` 调用都改为 `_manager(tenant_id)`。

好处是：

- 数据流清晰
- 不依赖隐式全局状态
- 后续测试和代码审查都更容易确认 tenant 是否正确透传

#### 建议 2：交互式子命令入口统一 `@click.pass_context`

例如：

- `config_cmd(ctx)`
- `config_key_cmd(ctx, provider_id)`
- `set_llm_cmd(ctx)`

在命令入口先取：

```python
tenant_id = _get_tenant_id(ctx)
```

再继续传给下游交互函数。

这应该成为 `models_group` 下所有子命令的统一模式，避免部分命令支持、部分命令遗漏。

#### 建议 3：把当前代码里的注释 TODO 变成真实修复

当前 `config_cmd()` 上方其实已经有注释承认问题：

```python
# Note: configure_providers_interactive uses _manager() internally
# which defaults to "default" tenant. For full multi-tenant CLI support,
# the interactive functions would need to be refactored.
```

这说明问题是已知的，但现在仍然暴露给用户使用。

建议不要继续保留这种“接口已开放但实现未完成”的状态，至少应二选一：

- 要么完成透传修复
- 要么暂时禁止这些交互命令与 `--tenant-id` 组合使用，并明确报错

如果项目已经准备正式支持 tenant-isolated provider config，正确做法显然是前者。

#### 建议 4：补齐 CLI 端到端测试

建议至少增加以下测试：

1. `copaw models --tenant-id alice config-key openai`
   - 断言写入 `alice/providers/...`
   - 不影响 `default/providers/...`

2. `copaw models --tenant-id alice set-llm`
   - 断言 active model 写入 alice tenant 范围

3. `copaw models --tenant-id alice config`
   - 断言整条交互链使用 alice manager

4. 对照测试：不传 `--tenant-id`
   - 断言仍落到 default，保证向后兼容

如果没有这类测试，之后极易再次出现“某个交互辅助函数忘记透传 tenant_id”的回归。

---

## 四、建议的落地顺序

建议按下面顺序修：

### 第一优先级
1. 修复 `_ensure_provider_config()` 的锁语义
2. 去掉“复制失败时自动创建空配置”的错误兜底

### 第二优先级
3. 重构交互式 CLI 函数签名，完整透传 `tenant_id`
4. 修复 `config` / `config-key` / `set-llm` 三个命令入口

### 第三优先级
5. 为并发初始化补测试
6. 为 CLI 多租户交互命令补端到端测试

---

## 五、最终判断

针对问题 2 和问题 3，我的判断是：

- **问题 2 是并发正确性缺陷**，会导致 tenant provider 配置被错误初始化。
- **问题 3 是多租户 CLI 语义缺陷**，会导致运维操作误写到 default tenant。

两者都与设计文档中的“tenant-isolated provider configuration”核心目标直接冲突，因此都应视为需要尽快修复的实质性问题，而不是后续可选优化。
