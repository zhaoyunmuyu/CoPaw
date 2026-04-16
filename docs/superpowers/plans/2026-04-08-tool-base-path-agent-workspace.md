# Tool Base Path Agent Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make built-in local path tools default to the current agent `workspace_dir` when it is available, while preserving tenant-root fallback and existing tenant boundary enforcement.

**Architecture:** Introduce one shared helper in `tenant_path_boundary.py` that resolves the default tool base directory from request context. Route `shell`, `file_io`, `file_search`, `browser_control`, and `desktop_screenshot` through that helper so relative paths and omitted path parameters behave consistently in agent-scoped sessions without changing the final tenant-level authorization boundary.

**Tech Stack:** Python, pathlib, contextvars, pytest, AgentScope tool adapters

---

## File Structure

### Modified files
- `src/swe/security/tenant_path_boundary.py`
  - Add the shared `get_current_tool_base_dir()` helper and keep tenant-boundary validation centralized.
- `src/swe/agents/tools/shell.py`
  - Change `cwd=None` resolution to use the shared helper and keep path validation anchored to the resolved working directory.
- `src/swe/agents/tools/file_io.py`
  - Replace direct `get_current_workspace_dir()` lookup with the shared helper so file read/write/edit/append defaults match `shell`.
- `src/swe/agents/tools/file_search.py`
  - Use the shared helper for both default search root and relative `path=` resolution.
- `src/swe/agents/tools/browser_control.py`
  - Resolve relative output files under `<tool-base-dir>/browser/` instead of mixing `workspace_dir` and `WORKING_DIR` directly.
- `src/swe/agents/tools/desktop_screenshot.py`
  - Save default screenshots into the shared tool base dir.
- `tests/unit/test_tenant_path_boundary.py`
  - Cover the new helper’s workspace-first and tenant-fallback semantics.
- `tests/unit/test_shell_tenant_boundary.py`
  - Cover `cwd=None` behavior when an agent workspace is present.
- `tests/unit/test_tool_tenant_boundary_regression.py`
  - Extend default-root regression coverage for search tools.

### New files
- `tests/unit/test_file_tools_agent_workspace_default.py`
  - Cover `read_file`, `write_file`, and `append_file` defaulting to `workspace_dir`.
- `tests/unit/test_tool_output_base_dir.py`
  - Cover `browser_control._resolve_output_path()` and `desktop_screenshot()` default output locations.

### Existing files to read while implementing
- `src/swe/config/context.py`
- `src/swe/security/tool_guard/guardians/file_guardian.py`
- `src/swe/agents/react_agent.py`
- `tests/unit/test_tool_tenant_boundary_regression.py`

---

### Task 1: Add the shared tool-base helper with failing tenant-boundary tests

**Files:**
- Modify: `src/swe/security/tenant_path_boundary.py`
- Modify: `tests/unit/test_tenant_path_boundary.py`
- Test: `tests/unit/test_tenant_path_boundary.py`

- [ ] **Step 1: Write the failing tests for workspace-first base resolution**

```python
def test_get_current_tool_base_dir_prefers_workspace_dir(mock_working_dir: Path):
    tenant_id = "test_tenant"
    workspace_dir = mock_working_dir / tenant_id / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with tenant_context(tenant_id=tenant_id, workspace_dir=workspace_dir):
        result = get_current_tool_base_dir()

    assert result == workspace_dir.resolve()


def test_get_current_tool_base_dir_falls_back_to_tenant_root(
    mock_working_dir: Path,
):
    tenant_id = "test_tenant"

    with tenant_context(tenant_id=tenant_id):
        result = get_current_tool_base_dir()

    assert result == (mock_working_dir / tenant_id).resolve()
```

- [ ] **Step 2: Add the failing test for rejecting an out-of-tenant workspace**

```python
def test_get_current_tool_base_dir_rejects_workspace_outside_tenant(
    mock_working_dir: Path,
):
    tenant_id = "test_tenant"
    outside_workspace = mock_working_dir / "other_tenant"

    with tenant_context(tenant_id=tenant_id, workspace_dir=outside_workspace):
        with pytest.raises(PathTraversalError):
            get_current_tool_base_dir()
```

- [ ] **Step 3: Run the tests to verify the helper is missing**

Run: `venv/bin/python -m pytest tests/unit/test_tenant_path_boundary.py -v`
Expected: FAIL with `ImportError` or `NameError` because `get_current_tool_base_dir()` does not exist yet.

- [ ] **Step 4: Add the shared helper in `tenant_path_boundary.py`**

```python
from swe.config.context import get_current_tenant_id, get_current_workspace_dir


def get_current_tool_base_dir() -> Path:
    """Return the default base directory for local path tools.

    Prefer the current agent workspace when it is available, otherwise
    fall back to the current tenant root. In both cases the returned
    directory must remain inside the current tenant boundary.
    """
    tenant_root = get_current_tenant_root().resolve()
    workspace_dir = get_current_workspace_dir()
    if workspace_dir is None:
        return tenant_root

    workspace_resolved = Path(workspace_dir).expanduser().resolve()
    try:
        workspace_resolved.relative_to(tenant_root)
    except ValueError as exc:
        raise PathTraversalError(
            "Workspace directory escapes the tenant workspace boundary.",
            resolved_path=workspace_resolved,
        ) from exc
    return workspace_resolved
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/bin/python -m pytest tests/unit/test_tenant_path_boundary.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/swe/security/tenant_path_boundary.py tests/unit/test_tenant_path_boundary.py
git commit -m "refactor(tools): centralize default tool base dir"
```

### Task 2: Move shell default cwd to the shared helper

**Files:**
- Modify: `src/swe/agents/tools/shell.py`
- Modify: `tests/unit/test_shell_tenant_boundary.py`
- Test: `tests/unit/test_shell_tenant_boundary.py`

- [ ] **Step 1: Add the failing shell tests for `cwd=None`**

```python
def test_resolve_cwd_defaults_to_workspace_dir_when_present(mock_working_dir: Path):
    tenant_dir = mock_working_dir / "test_tenant"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with tenant_context(
        tenant_id="test_tenant",
        workspace_dir=workspace_dir,
    ):
        result = _resolve_cwd(None)

    assert result == workspace_dir.resolve()


def test_validate_shell_paths_uses_workspace_dir_as_base(mock_working_dir: Path):
    tenant_dir = mock_working_dir / "test_tenant"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "local.txt").write_text("ok")

    with tenant_context(
        tenant_id="test_tenant",
        workspace_dir=workspace_dir,
    ):
        result = _validate_shell_paths("cat local.txt", base_dir=_resolve_cwd(None))

    assert result is None
```

- [ ] **Step 2: Run the shell test file to verify failure**

Run: `venv/bin/python -m pytest tests/unit/test_shell_tenant_boundary.py -v`
Expected: FAIL because `_resolve_cwd(None)` still returns the tenant root instead of the agent workspace.

- [ ] **Step 3: Update `shell.py` to use the shared helper**

```python
from ...security.tenant_path_boundary import (
    TenantPathBoundaryError,
    get_current_tenant_root,
    get_current_tool_base_dir,
    is_path_within_tenant_with_base,
)


def _resolve_cwd(cwd: Optional[Path]) -> Path:
    tenant_root = get_current_tenant_root()

    if cwd is None:
        return get_current_tool_base_dir()

    resolved_cwd = cwd.resolve()
    try:
        resolved_cwd.relative_to(tenant_root.resolve())
    except ValueError as exc:
        raise TenantPathBoundaryError(
            f"Working directory '{cwd}' is outside the tenant workspace boundary.",
            resolved_path=resolved_cwd,
        ) from exc
    return resolved_cwd
```

- [ ] **Step 4: Update the shell docstring to reflect the new default**

```python
        cwd (`Optional[Path]`, defaults to `None`):
            The working directory for the command execution.
            If None, defaults to the current agent workspace when available,
            otherwise the current tenant workspace root.
```

- [ ] **Step 5: Run the shell tests to verify they pass**

Run: `venv/bin/python -m pytest tests/unit/test_shell_tenant_boundary.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/swe/agents/tools/shell.py tests/unit/test_shell_tenant_boundary.py
git commit -m "fix(shell): default cwd to agent workspace"
```

### Task 3: Align file read/write/search tools with the shared helper

**Files:**
- Modify: `src/swe/agents/tools/file_io.py`
- Modify: `src/swe/agents/tools/file_search.py`
- Modify: `tests/unit/test_tool_tenant_boundary_regression.py`
- Create: `tests/unit/test_file_tools_agent_workspace_default.py`
- Test: `tests/unit/test_file_tools_agent_workspace_default.py`
- Test: `tests/unit/test_tool_tenant_boundary_regression.py`

- [ ] **Step 1: Write the failing file-tool tests**

```python
@pytest.mark.asyncio
async def test_read_file_defaults_to_workspace_dir(tmp_path: Path):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "note.txt").write_text("workspace content")
    (tenant_dir / "note.txt").write_text("tenant-root content")

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(tenant_id="tenant_a", workspace_dir=workspace_dir):
            result = await read_file("note.txt")

    assert "workspace content" in result.content[0].get("text", "")


@pytest.mark.asyncio
async def test_write_and_append_file_default_to_workspace_dir(tmp_path: Path):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(tenant_id="tenant_a", workspace_dir=workspace_dir):
            await write_file("note.txt", "hello")
            await append_file("note.txt", " world")

    assert (workspace_dir / "note.txt").read_text() == "hello world"
```

- [ ] **Step 2: Extend the failing search regression tests**

```python
@pytest.mark.asyncio
async def test_default_search_root_is_current_workspace_dir(mock_working_dir: Path):
    workspace_dir = mock_working_dir / "tenant_a" / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "workspace_only.txt").write_text("workspace scoped")
    (mock_working_dir / "tenant_a" / "tenant_only.txt").write_text("tenant scoped")

    with tenant_context(tenant_id="tenant_a", workspace_dir=workspace_dir):
        result = await glob_search("*.txt")

    result_text = result.content[0].get("text", "")
    assert "workspace_only.txt" in result_text
    assert "tenant_only.txt" not in result_text
```

- [ ] **Step 3: Run the targeted tests to verify failure**

Run: `venv/bin/python -m pytest tests/unit/test_file_tools_agent_workspace_default.py tests/unit/test_tool_tenant_boundary_regression.py -v`
Expected: FAIL because some tools still derive defaults from tenant root or their own local fallback logic.

- [ ] **Step 4: Update `file_io.py` and `file_search.py` to use the shared helper**

```python
from ...security.tenant_path_boundary import (
    TenantPathBoundaryError,
    get_current_tool_base_dir,
    make_permission_denied_response,
    resolve_tenant_path,
)


def _resolve_file_path(file_path: str) -> str:
    base_dir = get_current_tool_base_dir()
    resolved = resolve_tenant_path(
        file_path,
        base_dir=base_dir,
        allow_nonexistent=True,
    )
    return str(resolved)
```

```python
def _resolve_search_root(
    path: Optional[str],
    require_dir: bool = False,
) -> "Path | ToolResponse":
    if path is None:
        search_root = get_current_tool_base_dir()
    else:
        try:
            search_root = resolve_tenant_path(
                path,
                base_dir=get_current_tool_base_dir(),
            )
        except TenantPathBoundaryError:
            return _make_response(
                "Error: Search path is outside the allowed workspace.",
            )
```

Update the nearby docstrings so they describe the default as “current agent workspace when available, otherwise tenant workspace”.

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run: `venv/bin/python -m pytest tests/unit/test_file_tools_agent_workspace_default.py tests/unit/test_tool_tenant_boundary_regression.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/swe/agents/tools/file_io.py src/swe/agents/tools/file_search.py tests/unit/test_file_tools_agent_workspace_default.py tests/unit/test_tool_tenant_boundary_regression.py
git commit -m "fix(tools): align file tool defaults with agent workspace"
```

### Task 4: Align browser and screenshot output paths, then run the full verification set

**Files:**
- Modify: `src/swe/agents/tools/browser_control.py`
- Modify: `src/swe/agents/tools/desktop_screenshot.py`
- Create: `tests/unit/test_tool_output_base_dir.py`
- Test: `tests/unit/test_tool_output_base_dir.py`
- Test: `tests/unit/test_tenant_path_boundary.py`
- Test: `tests/unit/test_shell_tenant_boundary.py`
- Test: `tests/unit/test_file_tools_agent_workspace_default.py`
- Test: `tests/unit/test_tool_tenant_boundary_regression.py`

- [ ] **Step 1: Write the failing output-path tests**

```python
def test_browser_control_output_path_uses_workspace_dir(tmp_path: Path):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.agents.tools.browser_control.WORKING_DIR", tmp_path):
        with patch(
            "swe.security.tenant_path_boundary.WORKING_DIR",
            tmp_path,
        ):
            with tenant_context(
                tenant_id="tenant_a",
                workspace_dir=workspace_dir,
            ):
                resolved = _resolve_output_path("shot.png")

    assert resolved == str(workspace_dir / "browser" / "shot.png")


@pytest.mark.asyncio
async def test_desktop_screenshot_default_path_uses_workspace_dir(tmp_path: Path):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.agents.tools.desktop_screenshot._capture_mss") as capture:
        capture.return_value = _tool_ok(
            str(workspace_dir / "desktop_screenshot_1.png"),
            "ok",
        )
        with patch("swe.agents.tools.desktop_screenshot.WORKING_DIR", tmp_path):
            with patch(
                "swe.security.tenant_path_boundary.WORKING_DIR",
                tmp_path,
            ):
                with tenant_context(
                    tenant_id="tenant_a",
                    workspace_dir=workspace_dir,
                ):
                    await desktop_screenshot()

    called_path = capture.call_args[0][0]
    assert called_path.startswith(str(workspace_dir))
```

- [ ] **Step 2: Run the output-path tests to verify failure**

Run: `venv/bin/python -m pytest tests/unit/test_tool_output_base_dir.py -v`
Expected: FAIL because the tools still derive their default output location from direct `workspace_dir or WORKING_DIR` logic.

- [ ] **Step 3: Update `browser_control.py` and `desktop_screenshot.py` to use the shared helper**

```python
from ...security.tenant_path_boundary import get_current_tool_base_dir


def _resolve_output_path(path: str) -> str:
    if Path(path).is_absolute():
        return path
    base_dir = get_current_tool_base_dir() / "browser"
    base_dir.mkdir(parents=True, exist_ok=True)
    return str(base_dir / path)
```

```python
async def desktop_screenshot(
    path: str = "",
    capture_window: bool = False,
) -> ToolResponse:
    path = (path or "").strip()
    if not path:
        base_dir = get_current_tool_base_dir()
        path = str(base_dir / f"desktop_screenshot_{int(time.time())}.png")
```

Also update the screenshot docstring so “current workspace directory” becomes “current agent workspace when available, otherwise tenant workspace”.

- [ ] **Step 4: Run the full verification set**

Run: `venv/bin/python -m pytest tests/unit/test_tenant_path_boundary.py tests/unit/test_shell_tenant_boundary.py tests/unit/test_file_tools_agent_workspace_default.py tests/unit/test_tool_tenant_boundary_regression.py tests/unit/test_tool_output_base_dir.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/swe/agents/tools/browser_control.py src/swe/agents/tools/desktop_screenshot.py tests/unit/test_tool_output_base_dir.py
git commit -m "fix(tools): unify output paths with agent workspace base"
```

### Task 5: Final verification and handoff

**Files:**
- Modify: `docs/superpowers/specs/2026-04-08-tool-base-path-agent-workspace-design.md`
- Modify: `docs/superpowers/plans/2026-04-08-tool-base-path-agent-workspace.md`

- [ ] **Step 1: Update the design doc status after implementation**

```markdown
**状态**: 已实现
```

- [ ] **Step 2: Run the final focused verification command**

Run: `venv/bin/python -m pytest tests/unit/test_tenant_path_boundary.py tests/unit/test_shell_tenant_boundary.py tests/unit/test_file_tools_agent_workspace_default.py tests/unit/test_tool_tenant_boundary_regression.py tests/unit/test_tool_output_base_dir.py -v`
Expected: PASS

- [ ] **Step 3: Record the verification results in the final report**

```text
Validated shared tool-base resolution, shell default cwd, file tool defaults,
search-root defaults, and browser/screenshot output paths under agent workspace
context with tenant-root fallback preserved.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-04-08-tool-base-path-agent-workspace-design.md docs/superpowers/plans/2026-04-08-tool-base-path-agent-workspace.md
git commit -m "docs(spec): mark tool base path workspace work complete"
```

