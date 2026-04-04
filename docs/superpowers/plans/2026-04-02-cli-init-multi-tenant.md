# CLI Init Multi-Tenant Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tenant-aware CLI initialization so `copaw init --tenant-id <id>` creates tenant-scoped config and workspace data, while runtime tenant workspace creation reuses the same initialization logic.

**Architecture:** Extract tenant bootstrap logic into a new `TenantInitializer` that owns tenant directory setup and delegates to existing migration/bootstrap helpers with an explicit `working_dir`. Update `init_cmd.py` to derive all init paths from `WORKING_DIR / tenant_id`, and update runtime lazy workspace creation in `TenantWorkspacePool` to call the same initializer before constructing `Workspace`.

**Tech Stack:** Python, Click CLI, pathlib, existing CoPaw config/migration/workspace modules, pytest

---

## File Structure

### New file
- `src/copaw/app/workspace/tenant_initializer.py`
  - Single responsibility: tenant-scoped bootstrap entrypoint shared by CLI init and runtime lazy workspace creation.

### Modified files
- `src/copaw/cli/init_cmd.py`
  - Add `--tenant-id` option, stop using global config/heartbeat path helpers for init, route init flow through `TenantInitializer`, and keep later interactive steps tenant-scoped.
- `src/copaw/app/migration.py`
  - Add `working_dir` parameter to tenant-sensitive bootstrap helpers and internal helpers so they can operate on `WORKING_DIR / tenant_id` instead of only the global root.
- `src/copaw/agents/skills_manager.py`
  - Add optional `working_dir` support to `ensure_skill_pool_initialized()` and any directly-related path helper it needs.
- `src/copaw/app/workspace/tenant_pool.py`
  - Call `TenantInitializer.initialize()` before `Workspace(...)` creation.
- `tests/...`
  - Add focused tests for tenant initializer, migration helper parameterization, and CLI init path behavior.

### Existing files to read while implementing
- `src/copaw/cli/init_cmd.py`
- `src/copaw/app/migration.py`
- `src/copaw/agents/skills_manager.py`
- `src/copaw/app/workspace/tenant_pool.py`
- `src/copaw/config/utils.py`

---

### Task 1: Add failing tests for tenant-scoped bootstrap helpers

**Files:**
- Modify: `tests/` existing migration/bootstrap test file if one exists for `migration.py`; otherwise create `tests/app/test_migration_multi_tenant.py`
- Test: `tests/app/test_migration_multi_tenant.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from copaw.app.migration import ensure_default_agent_exists, ensure_qa_agent_exists
from copaw.constant import BUILTIN_QA_AGENT_ID


def test_ensure_default_agent_exists_uses_explicit_working_dir(tmp_path):
    tenant_dir = tmp_path / "tenant-a"
    tenant_dir.mkdir(parents=True)

    ensure_default_agent_exists(working_dir=tenant_dir)

    assert (tenant_dir / "config.json").exists()
    assert (tenant_dir / "workspaces" / "default").is_dir()
    assert (tenant_dir / "workspaces" / "default" / "chats.json").exists()
    assert (tenant_dir / "workspaces" / "default" / "jobs.json").exists()


def test_ensure_qa_agent_exists_uses_explicit_working_dir(tmp_path):
    tenant_dir = tmp_path / "tenant-b"
    tenant_dir.mkdir(parents=True)

    ensure_default_agent_exists(working_dir=tenant_dir)
    ensure_qa_agent_exists(working_dir=tenant_dir)

    qa_dir = tenant_dir / "workspaces" / BUILTIN_QA_AGENT_ID
    assert qa_dir.is_dir()
    assert (qa_dir / "chats.json").exists()
    assert (qa_dir / "jobs.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/app/test_migration_multi_tenant.py -v`
Expected: FAIL with `TypeError` because helper functions do not yet accept `working_dir`.

- [ ] **Step 3: Add minimal test scaffolding for skill-pool parameterization**

```python
from copaw.agents.skills_manager import ensure_skill_pool_initialized


def test_ensure_skill_pool_initialized_uses_explicit_working_dir(tmp_path):
    tenant_dir = tmp_path / "tenant-skill"
    tenant_dir.mkdir(parents=True)

    created = ensure_skill_pool_initialized(working_dir=tenant_dir)

    assert (tenant_dir / "skill_pool").is_dir()
    assert created in (True, False)
```

- [ ] **Step 4: Run the single test to verify it fails**

Run: `pytest tests/app/test_migration_multi_tenant.py::test_ensure_skill_pool_initialized_uses_explicit_working_dir -v`
Expected: FAIL with `TypeError` because `ensure_skill_pool_initialized()` does not yet accept `working_dir`.

- [ ] **Step 5: Commit**

```bash
git add tests/app/test_migration_multi_tenant.py
git commit -m "test: cover tenant-scoped bootstrap helpers"
```

### Task 2: Parameterize migration and skill-pool helpers by working directory

**Files:**
- Modify: `src/copaw/app/migration.py`
- Modify: `src/copaw/agents/skills_manager.py`
- Test: `tests/app/test_migration_multi_tenant.py`

- [ ] **Step 1: Update helper signatures in `migration.py`**

```python
def ensure_default_agent_exists(working_dir: Path | None = None) -> None:
    try:
        _do_ensure_default_agent(working_dir=working_dir)
    except Exception as e:
        logger.error(
            f"Failed to ensure default agent exists: {e}. "
            "Application may not work correctly.",
            exc_info=True,
        )


def _do_ensure_default_agent(working_dir: Path | None = None) -> None:
    wd = Path(working_dir or WORKING_DIR).expanduser()
    config_path = wd / "config.json"
    config = load_config(config_path)
```

- [ ] **Step 2: Replace hard-coded `WORKING_DIR` usage inside the default/QA/skill migration helpers**

```python
wd = Path(working_dir or WORKING_DIR).expanduser()
default_workspace = wd / "workspaces" / "default"
qa_workspace = wd / "workspaces" / qa_id
legacy_root = wd
workspaces_root = wd / "workspaces"

save_config(config, wd / "config.json")
```

Make the same pattern consistent in:
- `ensure_default_agent_exists`
- `_do_ensure_default_agent`
- `ensure_qa_agent_exists`
- `_do_ensure_qa_agent`
- `migrate_legacy_skills_to_skill_pool`
- `_do_migrate_legacy_skills`

- [ ] **Step 3: Add `working_dir` support to `ensure_skill_pool_initialized()`**

```python
def ensure_skill_pool_initialized(working_dir: Path | None = None) -> bool:
    root = Path(working_dir or WORKING_DIR).expanduser()
    pool_dir = root / "skill_pool"
    pool_dir.mkdir(parents=True, exist_ok=True)
    ...
```

If a helper like `get_skill_pool_dir()` is used internally, add an optional `working_dir` parameter there too and thread it through rather than duplicating path logic.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/app/test_migration_multi_tenant.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/migration.py src/copaw/agents/skills_manager.py tests/app/test_migration_multi_tenant.py
git commit -m "refactor: parameterize tenant bootstrap paths"
```

### Task 3: Add failing tests for the new TenantInitializer and runtime integration

**Files:**
- Create: `tests/app/workspace/test_tenant_initializer.py`
- Modify: `tests/app/workspace/` existing tenant pool test file if present; otherwise keep all new tests in `tests/app/workspace/test_tenant_initializer.py`
- Test: `tests/app/workspace/test_tenant_initializer.py`

- [ ] **Step 1: Write the failing tests for `TenantInitializer`**

```python
from copaw.app.workspace.tenant_initializer import TenantInitializer
from copaw.constant import BUILTIN_QA_AGENT_ID


def test_tenant_initializer_creates_expected_structure(tmp_path):
    initializer = TenantInitializer(tmp_path, "tenant-acme")

    initializer.initialize()

    tenant_dir = tmp_path / "tenant-acme"
    assert tenant_dir.is_dir()
    assert (tenant_dir / "workspaces" / "default").is_dir()
    assert (tenant_dir / "workspaces" / BUILTIN_QA_AGENT_ID).is_dir()
    assert (tenant_dir / "skill_pool").is_dir()


def test_tenant_initializer_is_idempotent(tmp_path):
    initializer = TenantInitializer(tmp_path, "tenant-acme")

    initializer.initialize()
    initializer.initialize()

    tenant_dir = tmp_path / "tenant-acme"
    assert (tenant_dir / "workspaces" / "default" / "jobs.json").exists()
```

- [ ] **Step 2: Write the failing runtime integration test**

```python
from copaw.app.workspace.tenant_pool import TenantWorkspacePool


def test_tenant_pool_get_or_create_initializes_tenant_dir(tmp_path):
    pool = TenantWorkspacePool(tmp_path)

    workspace = pool.get_or_create("tenant-runtime")

    assert workspace is not None
    assert (tmp_path / "tenant-runtime" / "workspaces" / "default").is_dir()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/app/workspace/test_tenant_initializer.py -v`
Expected: FAIL with `ModuleNotFoundError` for `tenant_initializer` and/or missing initialized directories from `TenantWorkspacePool`.

- [ ] **Step 4: Commit**

```bash
git add tests/app/workspace/test_tenant_initializer.py
git commit -m "test: cover tenant initializer and pool integration"
```

### Task 4: Implement `TenantInitializer` and wire it into `TenantWorkspacePool`

**Files:**
- Create: `src/copaw/app/workspace/tenant_initializer.py`
- Modify: `src/copaw/app/workspace/tenant_pool.py`
- Test: `tests/app/workspace/test_tenant_initializer.py`

- [ ] **Step 1: Create `TenantInitializer` with focused, idempotent methods**

```python
from pathlib import Path

from ..migration import (
    ensure_default_agent_exists,
    ensure_qa_agent_exists,
    migrate_legacy_skills_to_skill_pool,
)
from ...agents.skills_manager import ensure_skill_pool_initialized


class TenantInitializer:
    def __init__(self, base_working_dir: Path, tenant_id: str):
        self.base_working_dir = Path(base_working_dir).expanduser().resolve()
        self.tenant_id = tenant_id
        self.tenant_dir = self.base_working_dir / tenant_id

    def ensure_directory_structure(self) -> None:
        for path in (
            self.tenant_dir,
            self.tenant_dir / "workspaces",
            self.tenant_dir / "media",
            self.tenant_dir / "secrets",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def ensure_default_agent(self) -> None:
        ensure_default_agent_exists(working_dir=self.tenant_dir)

    def ensure_qa_agent(self) -> None:
        ensure_qa_agent_exists(working_dir=self.tenant_dir)

    def ensure_skill_pool(self) -> None:
        ensure_skill_pool_initialized(working_dir=self.tenant_dir)
        migrate_legacy_skills_to_skill_pool(working_dir=self.tenant_dir)

    def initialize(self) -> None:
        self.ensure_directory_structure()
        self.ensure_default_agent()
        self.ensure_qa_agent()
        self.ensure_skill_pool()
```

- [ ] **Step 2: Integrate the initializer into `TenantWorkspacePool.get_or_create()`**

```python
from .tenant_initializer import TenantInitializer

...
workspace_dir = self._get_tenant_workspace_dir(tenant_id)
initializer = TenantInitializer(self._base_working_dir, tenant_id)
initializer.initialize()
workspace = Workspace(agent_id, str(workspace_dir))
```

Keep the existing locking and error handling exactly as-is.

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/app/workspace/test_tenant_initializer.py -v`
Expected: PASS

- [ ] **Step 4: Run the earlier helper tests to catch integration regressions**

Run: `pytest tests/app/test_migration_multi_tenant.py tests/app/workspace/test_tenant_initializer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/workspace/tenant_initializer.py src/copaw/app/workspace/tenant_pool.py tests/app/workspace/test_tenant_initializer.py
git commit -m "feat: share tenant bootstrap between cli and runtime"
```

### Task 5: Add failing CLI tests for `copaw init --tenant-id`

**Files:**
- Create: `tests/cli/test_init_cmd_multi_tenant.py`
- Test: `tests/cli/test_init_cmd_multi_tenant.py`

- [ ] **Step 1: Write the failing test for explicit tenant ID**

```python
from click.testing import CliRunner

from copaw.cli.init_cmd import init_cmd


def test_init_cmd_writes_to_tenant_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("COPAW_WORKING_DIR", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(
        init_cmd,
        ["--defaults", "--accept-security", "--tenant-id", "tenant-acme"],
    )

    assert result.exit_code == 0
    assert (tmp_path / "tenant-acme" / "config.json").exists()
    assert (tmp_path / "tenant-acme" / "HEARTBEAT.md").exists()
    assert (tmp_path / "tenant-acme" / "workspaces" / "default").is_dir()
```

- [ ] **Step 2: Write the failing backward-compatibility test**

```python
def test_init_cmd_defaults_tenant_id_to_default(tmp_path, monkeypatch):
    monkeypatch.setenv("COPAW_WORKING_DIR", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(init_cmd, ["--defaults", "--accept-security"])

    assert result.exit_code == 0
    assert (tmp_path / "default" / "config.json").exists()
    assert not (tmp_path / "config.json").exists()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/cli/test_init_cmd_multi_tenant.py -v`
Expected: FAIL because `init_cmd` does not yet accept `--tenant-id` and still writes to the global root.

- [ ] **Step 4: Commit**

```bash
git add tests/cli/test_init_cmd_multi_tenant.py
git commit -m "test: cover tenant-aware cli init"
```

### Task 6: Implement tenant-aware CLI init path handling

**Files:**
- Modify: `src/copaw/cli/init_cmd.py`
- Test: `tests/cli/test_init_cmd_multi_tenant.py`

- [ ] **Step 1: Add the `--tenant-id` option and derive tenant-scoped paths**

```python
@click.option(
    "--tenant-id",
    default="default",
    show_default=True,
    help="Tenant ID for multi-tenant isolation.",
)
def init_cmd(
    force: bool,
    use_defaults: bool,
    accept_security: bool,
    tenant_id: str,
) -> None:
    tenant_dir = WORKING_DIR / tenant_id
    config_path = tenant_dir / "config.json"
    heartbeat_path = tenant_dir / "HEARTBEAT.md"
    default_workspace = tenant_dir / "workspaces" / "default"
```

Remove the current `get_config_path()` and `get_heartbeat_query_path()` usage from this command.

- [ ] **Step 2: Route bootstrap through `TenantInitializer`**

```python
from ..app.workspace.tenant_initializer import TenantInitializer

...
initializer = TenantInitializer(WORKING_DIR, tenant_id)
initializer.ensure_directory_structure()
initializer.ensure_default_agent()
initializer.ensure_qa_agent()
initializer.ensure_skill_pool()
```

This replaces direct calls to `ensure_default_agent_exists()`, `ensure_qa_agent_exists()`, and `migrate_legacy_skills_to_skill_pool()` in `init_cmd.py`.

- [ ] **Step 3: Keep the rest of the init flow tenant-scoped**

Use the already-derived tenant paths everywhere later in the function:

```python
working_dir = tenant_dir
click.echo(f"Working dir: {working_dir}")
existing = load_config(config_path) if config_path.is_file() else Config()
...
service = SkillService(default_workspace)
...
copied = copy_md_files(current_language, skip_existing=True, workspace_dir=default_workspace)
```

Do not add any `copaw app` changes in this task.

- [ ] **Step 4: Run CLI tests to verify they pass**

Run: `pytest tests/cli/test_init_cmd_multi_tenant.py -v`
Expected: PASS

- [ ] **Step 5: Run focused regression tests around init if present**

Run: `pytest tests/cli -k "init" -v`
Expected: PASS or only unrelated pre-existing failures.

- [ ] **Step 6: Commit**

```bash
git add src/copaw/cli/init_cmd.py tests/cli/test_init_cmd_multi_tenant.py
git commit -m "feat: add tenant-aware cli init"
```

### Task 7: Align provider/env init plan with actual path behavior or trim the scope

**Files:**
- Modify: `docs/superpowers/specs/2026-04-02-cli-init-multi-tenant-design.md`
- Optionally modify after confirming code reality:
  - `src/copaw/cli/providers_cmd.py`
  - `src/copaw/providers/provider_manager.py`
  - `src/copaw/cli/env_cmd.py`

- [ ] **Step 1: Verify whether provider/env configuration is actually exercised by the new CLI tests**

Run: `pytest tests/cli/test_init_cmd_multi_tenant.py -v -s`
Expected: Confirm whether `--defaults` path reaches provider/env persistence in a way that still writes to global `SECRET_DIR` or global `.env`.

- [ ] **Step 2: If provider/env writes remain global, choose the smallest correct action consistent with current request**

Use this decision table while implementing:

```text
If current code path under test does not touch .env configuration:
- Keep implementation scope to init path, workspace bootstrap, skill pool, config, and heartbeat.
- Update the spec wording later if needed.

If provider configuration is touched and clearly writes to SECRET_DIR globally:
- Either parameterize provider configuration in a narrowly scoped follow-up task,
- or trim the current implementation/spec to avoid claiming tenant-scoped provider persistence in this plan.
```

- [ ] **Step 3: Document the chosen outcome in the plan execution branch**

If trimmed, update the spec sentence to something explicit like:

```markdown
- Provider and env secret storage remain unchanged in this iteration; this change only makes config/workspace/heartbeat/skill bootstrap tenant-scoped.
```

If implemented now, add matching tests before code changes.

- [ ] **Step 4: Re-run the relevant tests**

Run: `pytest tests/cli/test_init_cmd_multi_tenant.py tests/app/test_migration_multi_tenant.py tests/app/workspace/test_tenant_initializer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-02-cli-init-multi-tenant-design.md src/copaw/cli/providers_cmd.py src/copaw/providers/provider_manager.py src/copaw/cli/env_cmd.py
git commit -m "docs: align init tenant scope with implementation"
```

### Task 8: Final verification

**Files:**
- Modify: none
- Test: all files changed above

- [ ] **Step 1: Run the focused test suite**

Run: `pytest tests/app/test_migration_multi_tenant.py tests/app/workspace/test_tenant_initializer.py tests/cli/test_init_cmd_multi_tenant.py -v`
Expected: PASS

- [ ] **Step 2: Run a lightweight CLI smoke test manually**

Run: `python -m copaw.cli init --help`
Expected: Help output includes `--tenant-id`

Run: `python -m copaw.cli init --defaults --accept-security --tenant-id smoke-test`
Expected: Exit code 0 and files created under `~/.copaw/smoke-test/` (or the temp working dir used for smoke testing)

- [ ] **Step 3: Inspect the resulting filesystem layout**

Run: `ls ~/.copaw/smoke-test && ls ~/.copaw/smoke-test/workspaces`
Expected: Shows `config.json`, `HEARTBEAT.md`, `workspaces`, and at least the `default` workspace.

- [ ] **Step 4: Commit any final fixes**

```bash
git add src/copaw/app/workspace/tenant_initializer.py src/copaw/app/workspace/tenant_pool.py src/copaw/app/migration.py src/copaw/agents/skills_manager.py src/copaw/cli/init_cmd.py tests/app/test_migration_multi_tenant.py tests/app/workspace/test_tenant_initializer.py tests/cli/test_init_cmd_multi_tenant.py
git commit -m "test: verify multi-tenant cli initialization"
```

---

## Self-Review

### Spec coverage
- `copaw init` adds `--tenant-id` with default `default`: covered by Tasks 5-6.
- New `TenantInitializer`: covered by Tasks 3-4.
- Migration helpers gain `working_dir`: covered by Tasks 1-2.
- `TenantWorkspacePool.get_or_create()` integration: covered by Tasks 3-4.
- Backward compatibility and non-migration of existing root data: covered by Tasks 5-6 and final smoke verification.

### Placeholder scan
- No `TODO` / `TBD` placeholders remain.
- Every code-changing task includes concrete code snippets and commands.

### Type consistency
- `TenantInitializer(base_working_dir: Path, tenant_id: str)` is used consistently.
- `working_dir: Path | None = None` is used consistently for helper parameterization.
- `tenant_id` default remains `"default"` everywhere in CLI behavior.
