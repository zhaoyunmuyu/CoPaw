# CoPaw 其他模块分析文档

## 概述

本文档涵盖 `src/copaw/` 下的其他支撑模块：环境存储、本地模型、提供商、安全、令牌使用、分词器、隧道和通用工具。

---

## 1. envs/ - 环境存储

**位置**: `src/copaw/envs/`

**用途**: 管理持久化环境变量存储，采用双层持久化策略：JSON 文件存储和运行时 `os.environ` 注入。

### 关键函数 (`store.py`)

| 函数 | 用途 |
|----------|---------|
| `load_envs()` | 从 `envs.json` 加载环境变量 |
| `save_envs()` | 持久化到 `envs.json` 并同步到 `os.environ` |
| `set_env_var()` | 设置单个环境变量 |
| `delete_env_var()` | 删除单个环境变量 |
| `load_envs_into_environ()` | 启动时将持久化的环境变量注入当前进程 |

### 安全特性

- 环境文件存储在 `SECRET_DIR` (`~/.copaw.secret/`)
- 目录权限设置为 0o700
- 文件权限设置为 0o600
- 受保护的启动键（`COPAW_WORKING_DIR`, `COPAW_SECRET_DIR`）不会被持久化存储覆盖

### 数据流

```
应用启动 → load_envs_into_environ()
              ↓
          加载 envs.json
              ↓
          注入到 os.environ（排除受保护键）
              ↓
运行时变更 → set_env_var() → save_envs() → JSON + os.environ 同步
```

---

## 2. local_models/ - 本地模型支持

**位置**: `src/copaw/local_models/`

**用途**: 提供本地 LLM 模型管理，包括从 HuggingFace/ModelScope 下载模型并通过 llama.cpp 服务运行。

### 关键类

#### LocalModelManager (`manager.py`)

外观类，提供本地模型操作的单一入口：

| 方法 | 用途 |
|--------|---------|
| `check_llamacpp_installation()` | 验证 llama.cpp 是否安装 |
| `start_llamacpp_download()` | 下载 llama.cpp 二进制 |
| `get_recommended_models()` | 根据系统内存/VRAM 获取推荐模型 |
| `start_model_download()` | 下载模型仓库 |
| `setup_server()` | 为模型启动 llama.cpp 服务 |
| `shutdown_server()` | 停止 llama.cpp 服务 |

**设计模式**: 单例模式 - `get_instance()` 返回全局实例

#### ModelManager (`model_manager.py`)

处理带进度跟踪的模型下载：

- `DownloadSource` 枚举: HUGGINGFACE, MODELSCOPE, AUTO
- `LocalModelInfo`: 模型元数据的 Pydantic 模型
- 使用多进程（spawn 上下文）进行隔离
- 通过 `DownloadProgressTracker` 进度跟踪

#### LlamaCppBackend (`llamacpp.py`)

管理 llama.cpp 服务生命周期：

- 平台检测（Windows/macOS/Linux, x64/arm64, CUDA 版本）
- 带 SHA256 验证的二进制下载
- 通过异步子进程的服务进程管理
- 通过 `/health` 端点的健康检查

---

## 3. providers/ - 模型提供商配置

**位置**: `src/copaw/providers/`

**用途**: 管理 LLM 提供商配置，包括内置提供商和自定义提供商，支持模型发现和连接测试。

### 关键类

#### Provider (`provider.py`)

所有提供商的抽象基类：

- `ProviderInfo`: 提供商元数据的 Pydantic 模型
- `ModelInfo`: 带多模态能力标志的模型元数据
- 抽象方法: `check_connection()`, `fetch_models()`, `get_chat_model_instance()`

#### ProviderManager (`provider_manager.py`)

所有提供商的单例管理器：

- **内置提供商**: OpenAI, Azure OpenAI, Anthropic, Gemini, DashScope, ModelScope, DeepSeek, Kimi, MiniMax, Ollama, LM Studio
- **自定义提供商支持**: 添加/移除用户定义的提供商
- 持久化到 `SECRET_DIR/providers/` JSON 文件
- 活动模型跟踪
- 多模态能力自动探测

#### LLMRateLimiter (`rate_limiter.py`)

LLM API 调用的全局速率限制：

- **信号量**: 限制并发请求
- **QPM 滑动窗口**: 60 秒窗口的每分钟查询限制
- **全局暂停**: 收到 429 时协调所有等待者
- **抖动**: 随机偏移防止惊群效应

#### RetryChatModel (`retry_chat_model.py`)

瞬时错误的自动重试包装器：

- `RetryConfig`: max_retries, backoff_base, backoff_cap
- 指数退避重试
- 流式支持，带正确的信号量管理

---

## 4. security/ - 安全特性

**位置**: `src/copaw/security/`

**用途**: 提供两个安全子系统：工具调用守卫（执行前扫描）和技能扫描（静态分析）。

### tool_guard/ 子模块

#### ToolGuardEngine (`engine.py`)

编排安全守卫：

| 方法 | 用途 |
|--------|---------|
| `guard()` | 执行前扫描工具参数 |
| `is_denied()` | 检查工具是否无条件阻止 |
| `is_guarded()` | 检查工具是否在守卫范围内 |

#### Models (`models.py`)

- `GuardSeverity`: CRITICAL, HIGH, MEDIUM, LOW, INFO, SAFE
- `GuardThreatCategory`: 命令注入、数据泄露、路径遍历等
- `GuardFinding`: 单个安全发现
- `ToolGuardResult`: 聚合结果，带 `is_safe` 属性

#### 守卫实现

- `RuleBasedToolGuardian`: YAML 正则签名匹配
- `FilePathToolGuardian`: 敏感文件路径检测

### skill_scanner/ 子模块

#### SkillScanner (`scanner.py`)

扫描技能目录的安全威胁：

- 使用 ThreadPoolExecutor 进行超时处理
- 基于 mtime 的结果缓存

#### 扫描策略 (`scan_policy.py`)

可配置的扫描行为，模式: block, warn, off

---

## 5. token_usage/ - 令牌使用跟踪

**位置**: `src/copaw/token_usage/`

**用途**: 跟踪 LLM API 令牌消费，用于监控和成本估算。

### 关键类

#### TokenUsageManager (`manager.py`)

令牌使用记录的单例管理器：

| 方法 | 用途 |
|--------|---------|
| `record()` | 记录提供商/模型/日期的令牌使用 |
| `get_summary()` | 获取聚合统计，支持日期范围、模型、提供商过滤 |

**特性**:
- 持久化到 `WORKING_DIR/token_usage.json`
- 线程安全（使用 asyncio Lock）

#### 模型

- `TokenUsageStats`: prompt_tokens, completion_tokens, call_count
- `TokenUsageRecord`: 单条查询记录
- `TokenUsageSummary`: 完整聚合，带 by_model, by_provider, by_date 分解

#### TokenRecordingModelWrapper (`model_wrapper.py`)

包装 ChatModelBase 自动记录使用：

- 拦截 `__call__()` 从响应提取使用量
- 支持流式和非流式响应
- 流完成后记录使用

---

## 6. tokenizer/ - 分词工具

**位置**: `src/copaw/tokenizer/` 和 `src/copaw/agents/utils/copaw_token_counter.py`

**用途**: 提供令牌计数功能，用于上下文管理和内存压缩。

### 分词器文件

- `tokenizer.json`: HuggingFace 分词器模型
- `vocab.json`: 词汇映射
- `merges.txt`: BPE 合并
- `tokenizer_config.json`: 配置

### 关键类 (`copaw_token_counter.py`)

#### CopawTokenCounter

扩展 HuggingFaceTokenCounter：

- 支持 HuggingFace 镜像（中国用户）
- 捆绑本地分词器用于离线使用
- `count()`: 计算消息或文本中的令牌
- `estimate_tokens()`: 快速字符估算回退

#### CopawEstimateTokenCounter

轻量级估算计数器：

- 无分词器加载开销
- 使用字符估算，可配置除数（默认 3.75）
- 适合精度不如性能重要的场景

---

## 7. tunnel/ - Cloudflare 隧道

**位置**: `src/copaw/tunnel/`

**用途**: 提供 Cloudflare Quick Tunnel 集成，将本地 CoPaw 服务暴露到互联网。

### 关键类

#### CloudflareTunnelDriver (`cloudflare.py`)

管理 cloudflared 隧道子进程：

| 方法 | 用途 |
|--------|---------|
| `start(local_port)` | 启动隧道并返回公开 URL |
| `stop()` | 终止隧道子进程 |
| `health_check()` | 验证隧道运行状态 |
| `get_public_url()` | 获取 *.trycloudflare.com URL |

#### BinaryManager (`binary_manager.py`)

自动下载 cloudflared 二进制：

- 平台检测
- SHA256 校验和验证
- macOS 从 tar.gz 提取，其他平台直接下载

#### TunnelInfo

隧道元数据的数据类：

- `public_url`: HTTPS URL
- `public_wss_url`: WebSocket Secure URL
- `started_at`: 时间戳
- `pid`: 进程 ID

---

## 8. utils/ - 通用工具

**位置**: `src/copaw/utils/`

**用途**: 提供跨模块的工具函数，用于系统信息、日志和遥测。

### system_info.py

硬件和 OS 检测：

| 函数 | 用途 |
|----------|---------|
| `get_os_name()` | 返回 windows/macos/linux |
| `get_architecture()` | 返回 x64/arm64 |
| `get_macos_version()` | 完整 macOS 版本元组 |
| `get_cuda_version()` | 通过 nvidia-smi 或 nvcc 检测 CUDA |
| `get_memory_size_gb()` | 总系统 RAM |
| `get_vram_size_gb()` | CUDA 设备的 GPU 内存 |

### logging.py

日志配置：

| 函数 | 用途 |
|----------|---------|
| `setup_logger()` | 配置 copaw 命名空间日志，带颜色输出 |
| `add_copaw_file_handler()` | 添加带轮转的文件日志 |
| `ColorFormatter` | 终端输出的彩色日志级别 |
| `SuppressPathAccessLogFilter` | 过滤 uvicorn 访问日志 |

### telemetry.py

匿名使用分析：

| 函数 | 用途 |
|----------|---------|
| `get_system_info()` | 收集匿名系统数据 |
| `collect_and_upload_telemetry()` | 上传到遥测端点 |
| `is_telemetry_opted_out()` | 检查用户退出状态 |

---

## 9. constant.py - 常量和目录解析

**位置**: `src/copaw/constant.py`

**用途**: 集中所有配置常量，提供类型安全的环境变量加载。

### EnvVarLoader 类

类型安全的环境变量解析：

| 方法 | 用途 |
|--------|---------|
| `get_bool()` | 从 "true", "1", "yes" 解析布尔 |
| `get_float()` | 带最小/最大边界解析浮点数 |
| `get_int()` | 带最小/最大边界解析整数 |
| `get_str()` | 带默认回退的字符串 |

### 目录常量

| 常量 | 值 | 描述 |
|--------|---------|-------------|
| `WORKING_DIR` | `~/.copaw` | 主工作目录 |
| `SECRET_DIR` | `~/.copaw.secret` | 秘密存储目录 |
| `DEFAULT_MEDIA_DIR` | `$WORKING_DIR/media` | 媒体文件 |
| `MODELS_DIR` | `$WORKING_DIR/models` | 模型文件 |
| `MEMORY_DIR` | `$WORKING_DIR/memory` | 内存存储 |
| `CUSTOM_CHANNELS_DIR` | `$WORKING_DIR/custom_channels` | 自定义通道 |

### LLM 配置常量

| 常量 | 默认值 | 描述 |
|--------|---------|-------------|
| `LLM_MAX_RETRIES` | 3 | 最大重试次数 |
| `LLM_BACKOFF_BASE` | 1.0 | 指数退避基数 |
| `LLM_BACKOFF_CAP` | 10.0 | 最大退避秒数 |
| `LLM_MAX_CONCURRENT` | 10 | 并发限制 |
| `LLM_MAX_QPM` | 600 | 每分钟查询限制 |
| `LLM_RATE_LIMIT_PAUSE` | 5.0s | 429 暂停时间 |
| `LLM_ACQUIRE_TIMEOUT` | 300s | 最大等待时间 |

---

## 设计模式总结

| 模式 | 使用模块 |
|---------|---------------|
| **单例** | ProviderManager, TokenUsageManager, LocalModelManager, ToolGuardEngine |
| **外观** | LocalModelManager（包装 ModelManager + LlamaCppBackend） |
| **策略** | 提供商实现、分析器、守卫 |
| **观察者** | 进度跟踪、发现聚合 |
| **包装/装饰器** | RetryChatModel, TokenRecordingModelWrapper |
| **工厂** | get_copaw_token_counter(), Provider._provider_from_data() |