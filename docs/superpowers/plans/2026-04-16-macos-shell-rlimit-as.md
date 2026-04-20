# macOS Shell RLIMIT_AS Compatibility Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent `execute_shell_command` from failing on macOS when shell memory process limits are configured, while keeping shell CPU limits intact.

**Architecture:** Refine shell process-limit capability resolution in `src/swe/security/process_limits.py` so shell memory enforcement can be disabled independently from shell CPU enforcement on macOS. Keep the shell tool interface unchanged and verify behavior with focused unit tests around policy resolution and shell subprocess injection.

**Tech Stack:** Python, pytest, `resource`, tenant-scoped config models

---

### Task 1: Add a failing macOS policy regression test

**Files:**
- Modify: `tests/unit/security/test_process_limits.py`
- Test: `tests/unit/security/test_process_limits.py`

- [ ] **Step 1: Write the failing test**

```python
def test_shell_policy_skips_memory_rlimit_on_macos(tmp_path: Path) -> None:
    from swe.security.process_limits import resolve_current_process_limit_policy

    _write_tenant_config(
        tmp_path,
        "tenant-a",
        enabled=True,
        cpu_time_limit_seconds=3,
        memory_max_mb=64,
    )

    with patch("swe.constant.WORKING_DIR", tmp_path), patch(
        "swe.config.utils.WORKING_DIR",
        tmp_path,
    ), patch("swe.security.process_limits.sys.platform", "darwin"):
        with tenant_context(tenant_id="tenant-a"):
            policy = resolve_current_process_limit_policy("shell")

        with patch("swe.security.process_limits.resource.setrlimit") as mock_setrlimit:
            preexec_fn = policy.build_preexec_fn()
            assert preexec_fn is not None
            preexec_fn()

    assert mock_setrlimit.call_args_list == [
        call(policy.rlimit_cpu, (3, 3)),
    ]
    assert "memory" in (policy.diagnostic or "").lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/unit/security/test_process_limits.py::test_shell_policy_skips_memory_rlimit_on_macos -v`
Expected: FAIL because the current implementation still applies `RLIMIT_AS` on `darwin` and produces the wrong `setrlimit` calls / missing diagnostic.

- [ ] **Step 3: Write minimal implementation**

```python
memory_supported = not (
    scope == "shell" and sys.platform == "darwin"
)
```

Use that capability to keep shell enforcement enabled when CPU limits are usable, but skip adding `RLIMIT_AS` to the shell `preexec_fn` on macOS and surface a diagnostic.

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/unit/security/test_process_limits.py::test_shell_policy_skips_memory_rlimit_on_macos -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/security/test_process_limits.py src/swe/security/process_limits.py
git commit -m "fix(shell): skip macos memory rlimit in shell preexec"
```

### Task 2: Preserve existing non-macOS behavior

**Files:**
- Modify: `tests/unit/security/test_process_limits.py`
- Test: `tests/unit/security/test_process_limits.py`

- [ ] **Step 1: Reuse and keep the existing Unix coverage**

```python
def test_resolved_policy_builds_unix_preexec_fn(tmp_path: Path) -> None:
    ...
    assert mock_setrlimit.call_args_list == [
        call(policy.rlimit_cpu, (3, 3)),
        call(policy.rlimit_as, (64 * 1024 * 1024, 64 * 1024 * 1024)),
    ]
```

- [ ] **Step 2: Run focused tests**

Run: `venv/bin/python -m pytest tests/unit/security/test_process_limits.py -v`
Expected: PASS, including both the new macOS regression test and the existing Linux-style preexec test.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/security/test_process_limits.py
git commit -m "test(shell): cover macos shell process-limit behavior"
```

### Task 3: Verify shell-tool integration stays intact

**Files:**
- Modify: `tests/unit/test_shell_tenant_boundary.py`
- Test: `tests/unit/test_shell_tenant_boundary.py`

- [ ] **Step 1: Add an integration-oriented regression test**

```python
@pytest.mark.asyncio
async def test_shell_macos_policy_injects_preexec_without_memory_rlimit(
    self,
    mock_working_dir: Path,
):
    from swe.agents.tools.shell import execute_shell_command

    _write_process_limit_config(
        mock_working_dir,
        "test_tenant",
        enabled=True,
        shell=True,
        cpu_time_limit_seconds=2,
        memory_max_mb=64,
    )

    captured = {}

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"ok\n", b""

    async def _fake_create_subprocess_shell(*args, **kwargs):
        captured["preexec_fn"] = kwargs.get("preexec_fn")
        return _FakeProcess()

    with patch("swe.agents.tools.shell.sys.platform", "darwin"), patch(
        "swe.security.process_limits.sys.platform",
        "darwin",
    ), patch(
        "swe.agents.tools.shell.asyncio.create_subprocess_shell",
        side_effect=_fake_create_subprocess_shell,
    ):
        with tenant_context(tenant_id="test_tenant"):
            result = await execute_shell_command("echo ok")

    assert result.content[0]["text"].startswith("ok")
    assert captured["preexec_fn"] is not None
```

- [ ] **Step 2: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/unit/test_shell_tenant_boundary.py::TestValidateShellPaths::test_shell_process_limit_lookup_is_tenant_scoped -v`
Expected: PASS for existing shell preexec injection behavior.

Run: `venv/bin/python -m pytest tests/unit/test_shell_tenant_boundary.py -k process_limit -v`
Expected: PASS for the broader shell process-limit coverage.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_shell_tenant_boundary.py
git commit -m "test(shell): verify macos shell preexec injection"
```

### Task 4: Final verification

**Files:**
- Modify: `src/swe/security/process_limits.py`
- Test: `tests/unit/security/test_process_limits.py`
- Test: `tests/unit/test_shell_tenant_boundary.py`

- [ ] **Step 1: Run targeted verification**

Run: `venv/bin/python -m pytest tests/unit/security/test_process_limits.py tests/unit/test_shell_tenant_boundary.py -v`
Expected: PASS with no regression in shell process-limit coverage.

- [ ] **Step 2: Review diff**

Run: `git diff -- src/swe/security/process_limits.py tests/unit/security/test_process_limits.py tests/unit/test_shell_tenant_boundary.py docs/superpowers/specs/2026-04-16-macos-shell-rlimit-as-design.md docs/superpowers/plans/2026-04-16-macos-shell-rlimit-as.md`
Expected: Only the planned macOS shell compatibility and test/documentation changes appear.
