# Agent Init API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `POST /api/agent/init` so callers can append text to a top-level Markdown file in the specified agent workspace under the current tenant, creating the file when missing.

**Architecture:** Extend the existing agent router in `src/swe/app/routers/agent.py` with a narrow request model, a filename validation helper, and one append endpoint that resolves the target workspace with the existing tenant-aware `get_agent_for_request(...)` flow. Cover the contract with a focused router test module that exercises success paths, validation, tenant isolation, agent isolation, and propagated `404` / `403` errors without booting the full application stack.

**Tech Stack:** FastAPI, Pydantic, httpx `AsyncClient`, pytest

---

### Task 1: Add Core Contract Tests and Minimal Endpoint

**Files:**
- Create: `tests/unit/routers/test_agent_init.py`
- Modify: `src/swe/app/routers/agent.py`
- Test: `tests/unit/routers/test_agent_init.py`

- [ ] **Step 1: Write the failing router tests for the happy path, file creation, filename normalization, invalid filenames, and missing tenant header**

```python
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Unit tests for POST /api/agent/init."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from swe.app.middleware.tenant_identity import TenantIdentityMiddleware
from swe.app.routers.agent import router

app = FastAPI()
app.add_middleware(
    TenantIdentityMiddleware,
    require_tenant=True,
    default_tenant_id=None,
)
app.include_router(router, prefix="/api")


@pytest.fixture
def api_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncClient:
    """Build an API client with tenant-local fake agent workspaces."""

    async def fake_get_agent_for_request(request, agent_id=None):
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            raise AssertionError("tenant middleware should reject first")

        target_agent = agent_id or "default"
        if target_agent == "missing":
            raise HTTPException(
                status_code=404,
                detail="Agent 'missing' not found",
            )
        if target_agent == "disabled":
            raise HTTPException(
                status_code=403,
                detail="Agent 'disabled' is disabled",
            )

        workspace_dir = tmp_path / tenant_id / "workspaces" / target_agent
        workspace_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(
            agent_id=target_agent,
            workspace_dir=workspace_dir,
        )

    monkeypatch.setattr(
        "swe.app.routers.agent.get_agent_for_request",
        fake_get_agent_for_request,
    )
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def test_post_init_appends_to_existing_markdown(
    api_client: AsyncClient,
    tmp_path: Path,
):
    target = tmp_path / "tenant-a" / "workspaces" / "writer" / "PROFILE.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("existing", encoding="utf-8")

    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "PROFILE.md",
                    "text": "\nappended",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 200
    assert response.json() == {
        "appended": True,
        "filename": "PROFILE.md",
        "agent_id": "writer",
    }
    assert target.read_text(encoding="utf-8") == "existing\nappended"


def test_post_init_creates_markdown_when_missing(
    api_client: AsyncClient,
    tmp_path: Path,
):
    target = tmp_path / "tenant-a" / "workspaces" / "writer" / "BOOTSTRAP.md"

    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "BOOTSTRAP",
                    "text": "seed text",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 200
    assert response.json() == {
        "appended": True,
        "filename": "BOOTSTRAP.md",
        "agent_id": "writer",
    }
    assert target.read_text(encoding="utf-8") == "seed text"


@pytest.mark.parametrize(
    "filename",
    [
        "memory/PROFILE.md",
        "../PROFILE.md",
        "nested/PROFILE.md",
        "a\\\\b.md",
    ],
)
def test_post_init_rejects_non_top_level_markdown_filenames(
    api_client: AsyncClient,
    filename: str,
):
    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": filename,
                    "text": "seed text",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "filename must be a top-level Markdown file name"
    )


def test_post_init_allows_empty_text(
    api_client: AsyncClient,
    tmp_path: Path,
):
    target = tmp_path / "tenant-a" / "workspaces" / "writer" / "PROFILE.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("existing", encoding="utf-8")

    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "PROFILE.md",
                    "text": "",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 200
    assert target.read_text(encoding="utf-8") == "existing"


def test_post_init_requires_agent_id(api_client: AsyncClient):
    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "PROFILE.md",
                    "text": "seed text",
                    "agentId": "   ",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 400
    assert response.json()["detail"] == "agentId is required"


def test_post_init_requires_filename(api_client: AsyncClient):
    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "   ",
                    "text": "seed text",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 400
    assert response.json()["detail"] == "filename is required"


def test_post_init_requires_text_field(api_client: AsyncClient):
    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "PROFILE.md",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 400
    assert response.json()["detail"] == "text is required"


def test_post_init_requires_tenant_header(api_client: AsyncClient):
    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                json={
                    "filename": "PROFILE.md",
                    "text": "seed text",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Tenant-Id header is required"
```

- [ ] **Step 2: Run the new router tests and confirm they fail before implementation**

Run: `venv/bin/python -m pytest tests/unit/routers/test_agent_init.py -v`

Expected: FAIL with `404 Not Found` or `405 Method Not Allowed` for `POST /api/agent/init`, because the route does not exist yet.

- [ ] **Step 3: Add the request model, filename validation helper, and minimal append endpoint**

Insert the following code near the existing Markdown file models in `src/swe/app/routers/agent.py`:

```python
class AgentInitRequest(BaseModel):
    """Request body for appending text into an agent workspace Markdown file."""

    filename: str | None = Field(
        default=None,
        description="Top-level Markdown file name",
    )
    text: str | None = Field(
        default=None,
        description="Text appended to the file tail",
    )
    agentId: str | None = Field(
        default=None,
        description="Target agent ID",
    )


def _normalize_init_filename(filename: str | None) -> str:
    """Validate and normalize a top-level Markdown filename."""
    candidate = (filename or "").strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="filename is required")

    if "/" in candidate or "\\" in candidate or ".." in candidate:
        raise HTTPException(
            status_code=400,
            detail="filename must be a top-level Markdown file name",
        )

    if not candidate.endswith(".md"):
        candidate = f"{candidate}.md"

    return candidate
```

Add the new route below the existing working file endpoints in `src/swe/app/routers/agent.py`:

```python
@router.post(
    "/init",
    response_model=dict,
    summary="Append text to an agent workspace Markdown file",
    description=(
        "Append text to a top-level Markdown file in the specified "
        "agent workspace under the current tenant."
    ),
)
async def init_agent_file(
    body: AgentInitRequest,
    request: Request,
) -> dict:
    """Append text to a top-level Markdown file for a specific agent."""
    filename = _normalize_init_filename(body.filename)
    agent_id = (body.agentId or "").strip()
    if not agent_id:
        raise HTTPException(status_code=400, detail="agentId is required")
    if body.text is None:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        workspace = await get_agent_for_request(request, agent_id=agent_id)
        workspace_manager = AgentMdManager(str(workspace.workspace_dir))
        workspace_manager.append_working_md(filename, body.text)
        return {
            "appended": True,
            "filename": filename,
            "agent_id": agent_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

- [ ] **Step 4: Run the router tests again and confirm the core contract passes**

Run: `venv/bin/python -m pytest tests/unit/routers/test_agent_init.py -v`

Expected: PASS for:
- `test_post_init_appends_to_existing_markdown`
- `test_post_init_creates_markdown_when_missing`
- `test_post_init_allows_empty_text`
- `test_post_init_requires_filename`
- `test_post_init_requires_agent_id`
- `test_post_init_requires_text_field`
- `test_post_init_rejects_non_top_level_markdown_filenames`
- `test_post_init_requires_tenant_header`

- [ ] **Step 5: Commit only the endpoint implementation and its router tests**

```bash
git add tests/unit/routers/test_agent_init.py src/swe/app/routers/agent.py
git commit -m "feat(agent): add tenant-scoped init append api"
```

### Task 2: Add Isolation and Error Propagation Regressions

**Files:**
- Modify: `tests/unit/routers/test_agent_init.py`
- Modify: `src/swe/app/routers/agent.py`
- Test: `tests/unit/routers/test_agent_init.py`

- [ ] **Step 1: Extend the router tests to prove tenant isolation, agent isolation, and propagated agent errors**

Append the following tests to `tests/unit/routers/test_agent_init.py`:

```python
def test_post_init_writes_only_to_target_agent_workspace(
    api_client: AsyncClient,
    tmp_path: Path,
):
    writer_target = (
        tmp_path / "tenant-a" / "workspaces" / "writer" / "PROFILE.md"
    )
    reviewer_target = (
        tmp_path / "tenant-a" / "workspaces" / "reviewer" / "PROFILE.md"
    )
    writer_target.parent.mkdir(parents=True, exist_ok=True)
    reviewer_target.parent.mkdir(parents=True, exist_ok=True)
    reviewer_target.write_text("keep me", encoding="utf-8")

    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "PROFILE",
                    "text": "writer text",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 200
    assert writer_target.read_text(encoding="utf-8") == "writer text"
    assert reviewer_target.read_text(encoding="utf-8") == "keep me"


def test_post_init_isolated_between_tenants(
    api_client: AsyncClient,
    tmp_path: Path,
):
    tenant_a_target = (
        tmp_path / "tenant-a" / "workspaces" / "writer" / "PROFILE.md"
    )
    tenant_b_target = (
        tmp_path / "tenant-b" / "workspaces" / "writer" / "PROFILE.md"
    )
    tenant_b_target.parent.mkdir(parents=True, exist_ok=True)
    tenant_b_target.write_text("tenant-b", encoding="utf-8")

    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "PROFILE.md",
                    "text": "tenant-a",
                    "agentId": "writer",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 200
    assert tenant_a_target.read_text(encoding="utf-8") == "tenant-a"
    assert tenant_b_target.read_text(encoding="utf-8") == "tenant-b"


def test_post_init_returns_404_when_agent_is_missing(
    api_client: AsyncClient,
):
    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "PROFILE.md",
                    "text": "seed text",
                    "agentId": "missing",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent 'missing' not found"


def test_post_init_returns_403_when_agent_is_disabled(
    api_client: AsyncClient,
):
    async def run_test():
        async with api_client:
            return await api_client.post(
                "/api/agent/init",
                headers={"X-Tenant-Id": "tenant-a"},
                json={
                    "filename": "PROFILE.md",
                    "text": "seed text",
                    "agentId": "disabled",
                },
            )

    response = asyncio.run(run_test())

    assert response.status_code == 403
    assert response.json()["detail"] == "Agent 'disabled' is disabled"
```

- [ ] **Step 2: Run the expanded router tests and confirm any remaining gaps**

Run: `venv/bin/python -m pytest tests/unit/routers/test_agent_init.py -v`

Expected: If the route still wraps downstream `HTTPException` values into `500`, the two new error-propagation tests fail here. If the route already re-raises `HTTPException`, only genuinely broken isolation cases should fail.

- [ ] **Step 3: Harden the route so downstream agent lookup errors keep their original status codes**

Verify `src/swe/app/routers/agent.py` keeps this exception structure in `init_agent_file(...)`:

```python
    try:
        workspace = await get_agent_for_request(request, agent_id=agent_id)
        workspace_manager = AgentMdManager(str(workspace.workspace_dir))
        workspace_manager.append_working_md(filename, body.text)
        return {
            "appended": True,
            "filename": filename,
            "agent_id": agent_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

If Step 2 exposed any bug, fix it now in this block rather than adding extra layers or a new service abstraction.

- [ ] **Step 4: Run the focused router test file and one adjacent middleware regression test**

Run: `venv/bin/python -m pytest tests/unit/routers/test_agent_init.py tests/unit/app/test_tenant_identity.py -v`

Expected: PASS for the new route contract and existing tenant-header middleware behavior.

- [ ] **Step 5: Commit only the isolation/error regression changes**

```bash
git add tests/unit/routers/test_agent_init.py src/swe/app/routers/agent.py
git commit -m "test(agent): cover init api isolation and errors"
```

### Task 3: Final Verification Before Handoff

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-agent-init-design.md` (only if behavior changed during implementation)
- Test: `tests/unit/routers/test_agent_init.py`
- Test: `tests/unit/app/test_tenant_identity.py`

- [ ] **Step 1: Re-read the spec and confirm the implementation still matches it**

Use this checklist against `docs/superpowers/specs/2026-04-13-agent-init-design.md`:

```text
- Route is POST /api/agent/init
- Body fields are filename, text, agentId
- Tenant comes from X-Tenant-Id only
- Only top-level Markdown filenames are allowed
- Missing file is auto-created
- Response returns appended, filename, agent_id
- Tenant and agent isolation are covered by tests
```

- [ ] **Step 2: Run the final targeted verification commands**

Run: `venv/bin/python -m pytest tests/unit/routers/test_agent_init.py tests/unit/app/test_tenant_identity.py -v`

Expected: PASS

Run: `venv/bin/python -m pytest tests/unit/agents/test_agent_md_manager_utf8.py -v`

Expected: PASS, proving the existing append helper behavior still works.

- [ ] **Step 3: If the spec had to change during implementation, update it in the same review pass**

Only make this edit if the shipped behavior differs from the approved spec. If no spec changes are needed, skip this step.

```markdown
No spec change required when the shipped behavior still matches:
- header-based tenant resolution
- top-level `.md` only
- append-or-create semantics
```

- [ ] **Step 4: Record the exact verification evidence in the final handoff**

Include these facts in the final summary:

```text
- Implemented POST /api/agent/init in src/swe/app/routers/agent.py
- Added router coverage in tests/unit/routers/test_agent_init.py
- Verified tenant middleware behavior with tests/unit/app/test_tenant_identity.py
- Verified AgentMdManager append regression coverage with tests/unit/agents/test_agent_md_manager_utf8.py
```

- [ ] **Step 5: Make the final implementation commit only if Task 3 produced code or spec changes**

```bash
git add src/swe/app/routers/agent.py tests/unit/routers/test_agent_init.py docs/superpowers/specs/2026-04-13-agent-init-design.md
git commit -m "chore(agent): finalize init api verification"
```

If Task 3 produced no file changes, do not create an empty commit.
