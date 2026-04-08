# Repository Guidelines

## Deployment Environment

- OS: Linux 3.15 内核
- 部署方式: Kubernetes 容器多实例部署
- 外部依赖:
  - Redis 集群（可连接）
  - MySQL 数据库（可连接）

## Project Structure & Module Organization

Core Python code lives in `src/swe/`. Key areas include `cli/` for the `swe` entrypoints, `app/channels/` for channel adapters, `providers/` and `local_models/` for model integration, and `agents/skills/` for built-in skills. Tests live in `tests/`, with focused suites such as `tests/lock/`, `tests/store/`, and `tests/app/backup/`. Frontend apps are split into `console/` (main web UI) and `website/` (docs/site). Deployment helpers live under `deploy/` and `scripts/`; longer-form design notes are in `docs/superpowers/specs/`.

## Testing

Tests are in `tests/`. Use pytest markers:

**Important:** Always run tests using the project's virtual environment:

```bash
# Run all tests with venv
venv/bin/python -m pytest

# Run specific test file
venv/bin/python -m pytest tests/test_session.py

# Run specific test directory
venv/bin/python -m pytest tests/unit/tenant_models/ -v
## Coding Style & Naming Conventions


## Multi-User Concurrent Support

CoPaw supports serving multiple users concurrently with full data isolation. Each user's request is routed to their own directory:

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

## Provider Configuration Isolation

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

Python uses 4-space indentation, `snake_case` modules, and Black with a 79-character line length. Pre-commit also runs mypy, flake8, pylint, Bandit, and basic file hygiene hooks. TypeScript/React in `console/` and `website/` uses 2-space indentation, `PascalCase` component names, and Prettier 3; `console/` additionally enforces ESLint rules via `npm run lint`. Follow existing directory naming such as `channel.py`, `registry.py`, and `test_redlock.py`.

## Testing Guidelines

Write Python tests with `pytest` and name files `test_*.py`. Keep tests close to the affected subsystem, for example `tests/channels/` or `tests/lock/`. Use `pytest -m "not slow"` when you need to skip slow cases. There is no dedicated frontend test runner in this repo today, so frontend changes should at minimum pass formatting and build checks.

## Commit & Pull Request Guidelines

Use Conventional Commits: `feat(scope): summary`, `fix(scope): summary`, `docs(scope): summary`. Recent history follows this closely, for example `feat(lock): ...` and `fix(lock): ...`. PR titles should use the same format. Include a clear description, linked issue, security notes when relevant, testing steps, and local verification output for `pre-commit run --all-files` and `pytest`. Update docs in `website/public/docs/` when behavior changes, and include screenshots for visible Console or website UI changes.
