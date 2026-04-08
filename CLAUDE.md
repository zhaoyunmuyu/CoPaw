# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Deployment Environment

- OS: Linux 3.15 内核
- 部署方式: Kubernetes 容器多实例部署
- 外部依赖:
  - Redis 集群（可连接）
  - MySQL 数据库（可连接）

## Build and Development Commands

### Python Backend

本项目使用 Python 虚拟环境进行依赖管理：

```bash
# 创建虚拟环境（在项目根目录）
python -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 确认已在虚拟环境中（which python 应指向 venv 路径）
which python
```

**注意：** 所有 Python 依赖均安装在虚拟环境中，开发前请确保已激活虚拟环境。

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run pre-commit checks (required before PR)
pre-commit run --all-files

# Run all tests
pytest

# Run specific test
pytest tests/test_session.py
pytest tests/ -k "memory"  # by keyword
```

### Console Frontend (TypeScript/React)

```bash
cd console
pnpm install
pnpm run build      # Build to dist/
pnpm run format     # Format code (required before PR)
pnpm run dev        # Development server
```

### Full Setup from Source

```bash
# Build console first
cd console && pnpm install && pnpm run build
cd ..

# Copy console build to package
mkdir -p src/swe/console
cp -R console/dist/. src/swe/console/

# Install Python package
pip install -e ".[dev]"

# Initialize and run
swe init --defaults
swe app
```

### Website (Documentation Site)

```bash
cd website
pnpm install
pnpm run build     # Output to dist/
pnpm run dev       # Development server
```

## Architecture Overview

### High-Level Structure

SWE is a personal AI assistant that connects to multiple chat platforms (DingTalk, Feishu, QQ, Discord, iMessage, Telegram) and runs scheduled tasks. The architecture consists of:

```
src/swe/
├── app/           # FastAPI server, channels, runners, routers
├── agents/        # Agent logic, skills, tools, memory, routing
├── channels/      # Chat platform connectors
├── cli/           # Click-based CLI commands
├── config/        # Configuration loading and watching
├── providers/     # LLM provider definitions and registry
└── console/       # React web UI (built output)
```

### Core Components

**App Layer (`src/swe/app/`):**
- `_app.py`: FastAPI application with lifespan management for channels, cron, MCP, and chat managers
- `channels/`: Platform connectors (DingTalk, Feishu, QQ, Discord, Telegram, iMessage, Voice/Twilio). Each channel converts platform-specific payloads to unified `content_parts`, processes via agent, and sends responses
- `runner/`: `AgentRunner` manages agent sessions, chat state, and tool execution
- `crons/`: Scheduled task executor with heartbeat support using APScheduler
- `mcp/`: MCP (Model Context Protocol) client manager for hot-plug tool discovery

**Agents Layer (`src/swe/agents/`):**
- `routing_chat_model.py`: Routes LLM requests between local (llama.cpp/MLX/Ollama) and cloud providers
- `skills/`: Built-in skills (cron, pdf, docx, pptx, xlsx, browser, file_reader, news). Each skill is a directory with `SKILL.md` (instructions) and optional `references/` and `scripts/`
- `tools/`: Agent tools (browser control, screenshots, file search, memory search, time)
- `memory/`: Long-term memory management with AgentScope's ReMe integration

**Providers Layer (`src/swe/providers/`):**
- `registry.py`: Provider definitions (DashScope, ModelScope, Ollama, custom OpenAI-compatible)
- `models.py`: Model slot configurations for local/cloud routing
- `ollama_manager.py`: Ollama model management

**CLI (`src/swe/cli/`):**
- Commands: `init`, `app`, `channels`, `skills`, `cron`, `env`, `daemon`, `clean`, `uninstall`, `providers`, `desktop`

**Config (`src/swe/config/`):**
- `config.py`: Pydantic models for config.json (channels, agents, MCP, heartbeat, routing)
- `watcher.py`: Hot-reload config changes without restart

### Data Flow

1. **Message Ingress:** Channel receives platform payload → converts to `content_parts` → queues for agent
2. **Agent Processing:** `AgentRunner` processes request → routes to LLM (local/cloud) → executes tools → returns response
3. **Response:** Channel formats and sends reply to platform
4. **Scheduled Tasks:** `CronManager` triggers heartbeat or custom jobs at configured intervals

### Multi-User Concurrent Support

SWE supports serving multiple users concurrently with full data isolation. Each user's request is routed to their own directory:

```
~/.swe/
├── alice/
│   ├── config.json
│   ├── active_skills/
│   ├── customized_skills/
│   ├── memory/
│   ├── models/
│   └── sessions/
├── bob/
│   └── ...
└── (default user)
    └── ...
```

**Implementation:**
- `src/swe/constant.py` provides `contextvars`-based request isolation
- `set_request_user_id(user_id)` sets the current request's user context
- `get_request_working_dir()` returns the user-specific working directory
- `AgentRunner.query_handler()` automatically sets up request context per query

**Key functions:**
- `get_request_working_dir()` - Request-scoped working directory
- `get_request_secret_dir()` - Request-scoped secret directory (providers.json)
- `get_active_skills_dir()` - Request-scoped active skills directory
- `get_memory_dir()` - Request-scoped memory directory
- `get_models_dir()` - Request-scoped models directory

**Channel requests:** User isolation is automatic - each channel message carries `sender_id` which becomes `request.user_id`, and `query_handler` sets the context.

**CLI/Single-user mode:** Use `copay app --user-id <id>` for single-user mode (uses `set_current_user()` for process-wide directory setting).

### Provider Configuration Isolation

Provider configurations (API keys, base URLs, active model selection) are now tenant-isolated:

```
~/.swe.secret/
├── default/
│   └── providers/          # Default tenant provider config
│       ├── builtin/        # Built-in provider configs (openai.json, etc.)
│       ├── custom/         # Custom provider configs
│       └── active_model.json
├── alice/
│   └── providers/          # Alice's isolated provider config
├── bob/
│   └── providers/          # Bob's isolated provider config
```

**Key features:**
- Each tenant has completely isolated provider configuration
- `ProviderManager.get_instance(tenant_id)` returns tenant-specific manager
- New tenants automatically inherit configuration from default tenant on first access
- CLI supports `--tenant-id` flag for multi-tenant management

**Migration from global storage:**
Run the migration script to move existing global provider config to tenant-isolated storage:

```bash
python scripts/migrate_provider_config.py --dry-run   # Preview changes
python scripts/migrate_provider_config.py             # Perform migration
```

This creates a backup at `~/.swe.secret/providers.backup.<timestamp>/` before migrating.

### Key Configuration Files

- `config.json` (working dir): Runtime config for channels, agents, MCP, heartbeat
- `providers/` (secret dir): **Tenant-isolated** LLM provider configurations per tenant at `~/.swe.secret/{tenant_id}/providers/`
- `.env` (working dir): API keys (DASHSCOPE_API_KEY, TAVILY_API_KEY, etc.)

### Skills System

Skills define agent capabilities. Each skill directory contains:
- `SKILL.md`: Instructions with YAML front matter (`name`, `description`, optional `metadata`)
- `references/`: Reference documents
- `scripts/`: Executable scripts or tools

Built-in skills live in `src/swe/agents/skills/`. Custom skills load from the working directory's `customized_skills/`.

### Channel Development

To add a new channel:
1. Create subclass of `BaseChannel` in `src/swe/app/channels/`
2. Set `channel` class attribute to unique key
3. Implement message handling: receive → content_parts → process → send
4. Add config class in `src/swe/config/config.py`
5. Register in `src/swe/app/channels/registry.py`

### Model Provider Development

To add a built-in provider:
1. Add `ProviderDefinition` in `src/swe/providers/registry.py`
2. Implement `ChatModel` class (if not OpenAI-compatible) inheriting from `agentscope.model.ChatModelBase`
3. Register in provider registry's chat model map

### Testing

Tests are in `tests/`. Use pytest markers:
- `@pytest.mark.slow` for slow tests (skip with `-m "not slow"`)

**Important:** Always run tests using the project's virtual environment:

```bash
# Run all tests with venv
venv/bin/python -m pytest

# Run specific test file
venv/bin/python -m pytest tests/test_session.py

# Run specific test directory
venv/bin/python -m pytest tests/unit/tenant_models/ -v
```

### Pre-commit Hooks

Pre-commit runs: AST check, YAML/XML/TOML/JSON check, Black (79 char line), Flake8, Pylint, mypy (with relaxed settings), Prettier (TypeScript only).

Skills and `scripts/pack/` are excluded from most hooks.
