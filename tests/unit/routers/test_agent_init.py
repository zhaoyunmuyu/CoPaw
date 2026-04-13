# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Unit tests for tenant-scoped agent init append API."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from swe.app.middleware.tenant_identity import TenantIdentityMiddleware
from swe.app.routers.agent import router


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a focused app with tenant middleware and patched resolver."""
    app = FastAPI()
    app.add_middleware(
        TenantIdentityMiddleware,
        require_tenant=True,
        default_tenant_id=None,
    )
    app.include_router(router, prefix="/api")
    app.include_router(router, prefix="/api/agents/{agentId}")

    async def fake_get_agent_for_request(
        request: Request,
        agent_id: str | None = None,
    ):
        if agent_id == "missing":
            raise HTTPException(status_code=404, detail="Agent 'missing' not found")
        if agent_id == "disabled":
            raise HTTPException(status_code=403, detail="Agent 'disabled' is disabled")

        tenant_id = request.state.tenant_id
        workspace_dir = tmp_path / tenant_id / "agents" / (agent_id or "default")
        workspace_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(
            workspace_dir=workspace_dir,
            agent_id=agent_id,
        )

    monkeypatch.setattr(
        "swe.app.routers.agent.get_agent_for_request",
        fake_get_agent_for_request,
    )
    return TestClient(app, raise_server_exceptions=False)


def test_init_happy_path_appends_existing_top_level_md(client: TestClient, tmp_path: Path):
    workspace = tmp_path / "tenant-a" / "agents" / "agent-1"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "PROFILE.md"
    target.write_text("prefix\n", encoding="utf-8")

    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.md",
            "text": "append",
            "agentId": "agent-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "appended": True,
        "filename": "PROFILE.md",
        "agent_id": "agent-1",
    }
    assert target.read_text(encoding="utf-8") == "prefix\nappend"


def test_init_creates_file_when_missing(client: TestClient, tmp_path: Path):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "NOTES.md",
            "text": "new-content",
            "agentId": "agent-2",
        },
    )

    created = tmp_path / "tenant-a" / "agents" / "agent-2" / "NOTES.md"
    assert response.status_code == 200
    assert created.exists() is True
    assert created.read_text(encoding="utf-8") == "new-content"


def test_init_normalizes_filename_with_md_suffix(client: TestClient, tmp_path: Path):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-b"},
        json={
            "filename": "PROFILE",
            "text": "hello",
            "agentId": "agent-3",
        },
    )

    normalized = tmp_path / "tenant-b" / "agents" / "agent-3" / "PROFILE.md"
    assert response.status_code == 200
    assert response.json()["filename"] == "PROFILE.md"
    assert normalized.read_text(encoding="utf-8") == "hello"


def test_init_normalizes_uppercase_md_extension(client: TestClient, tmp_path: Path):
    workspace = tmp_path / "tenant-a" / "agents" / "agent-1"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "PROFILE.md"
    target.write_text("prefix\n", encoding="utf-8")

    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.MD",
            "text": "append",
            "agentId": "agent-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "PROFILE.md"
    assert target.read_text(encoding="utf-8") == "prefix\nappend"
    assert (workspace / "PROFILE.MD.md").exists() is False


@pytest.mark.parametrize(
    "filename",
    [
        "memory/PROFILE.md",
        "../PROFILE.md",
        "nested/PROFILE.md",
        r"a\b.md",
    ],
)
def test_init_rejects_path_based_filename(client: TestClient, filename: str):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": filename,
            "text": "x",
            "agentId": "agent-1",
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "filename must be a top-level Markdown file name"
    )


@pytest.mark.parametrize("filename", [".md", "..", "...", ".profile.md"])
def test_init_rejects_dot_only_or_hidden_filenames(
    client: TestClient,
    filename: str,
):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": filename,
            "text": "x",
            "agentId": "agent-1",
        },
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "filename must be a top-level Markdown file name"
    )


def test_init_rejects_non_markdown_extension(client: TestClient):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.txt",
            "text": "x",
            "agentId": "agent-1",
        },
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "filename must be a top-level Markdown file name"
    )


def test_init_rejects_blank_filename(client: TestClient):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "   ",
            "text": "x",
            "agentId": "agent-1",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "filename is required"


def test_init_rejects_missing_filename(client: TestClient):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "text": "x",
            "agentId": "agent-1",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "filename is required"


def test_init_rejects_blank_agent_id(client: TestClient):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.md",
            "text": "x",
            "agentId": "  ",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "agentId is required"


def test_init_rejects_missing_agent_id(client: TestClient):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.md",
            "text": "x",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "agentId is required"


def test_init_rejects_missing_text_field(client: TestClient):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.md",
            "agentId": "agent-1",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "text is required"


def test_init_accepts_empty_text_without_content_change(client: TestClient, tmp_path: Path):
    workspace = tmp_path / "tenant-a" / "agents" / "agent-1"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "PROFILE.md"
    target.write_text("stable", encoding="utf-8")

    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.md",
            "text": "",
            "agentId": "agent-1",
        },
    )
    assert response.status_code == 200
    assert target.read_text(encoding="utf-8") == "stable"


def test_init_rejects_missing_tenant_header(client: TestClient):
    response = client.post(
        "/api/agent/init",
        json={
            "filename": "PROFILE.md",
            "text": "x",
            "agentId": "agent-1",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "X-Tenant-Id header is required"


def test_init_openapi_schema_marks_fields_required_and_non_nullable(
    client: TestClient,
):
    openapi = client.app.openapi()
    body_schema = openapi["components"]["schemas"]["AgentInitRequest"]

    assert set(body_schema["required"]) == {"filename", "text", "agentId"}
    assert body_schema["properties"]["filename"]["type"] == "string"
    assert body_schema["properties"]["text"]["type"] == "string"
    assert body_schema["properties"]["agentId"]["type"] == "string"
    assert "anyOf" not in body_schema["properties"]["filename"]
    assert "anyOf" not in body_schema["properties"]["text"]
    assert "anyOf" not in body_schema["properties"]["agentId"]


def test_init_rejects_agent_scoped_path_and_does_not_write(
    client: TestClient,
    tmp_path: Path,
):
    response = client.post(
        "/api/agents/path-agent/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.md",
            "text": "x",
            "agentId": "body-agent",
        },
    )
    assert response.status_code == 404
    assert (
        tmp_path / "tenant-a" / "agents" / "body-agent" / "PROFILE.md"
    ).exists() is False


@pytest.mark.parametrize(
    ("payload", "expected_detail"),
    [
        (
            {"filename": None, "text": "x", "agentId": "agent-1"},
            "filename is required",
        ),
        (
            {"filename": 123, "text": "x", "agentId": "agent-1"},
            "filename is required",
        ),
        (
            {"filename": "PROFILE.md", "text": None, "agentId": "agent-1"},
            "text is required",
        ),
        (
            {"filename": "PROFILE.md", "text": 123, "agentId": "agent-1"},
            "text is required",
        ),
        (
            {"filename": "PROFILE.md", "text": "x", "agentId": None},
            "agentId is required",
        ),
        (
            {"filename": "PROFILE.md", "text": "x", "agentId": {"k": "v"}},
            "agentId is required",
        ),
    ],
)
def test_init_rejects_null_or_wrong_types_with_400(
    client: TestClient,
    payload: dict,
    expected_detail: str,
):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json=payload,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail


def test_init_does_not_accept_snake_case_agent_id(client: TestClient):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.md",
            "text": "x",
            "agent_id": "agent-1",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "agentId is required"


@pytest.mark.parametrize(
    ("agent_id", "expected_status", "expected_detail"),
    [
        ("missing", 404, "Agent 'missing' not found"),
        ("disabled", 403, "Agent 'disabled' is disabled"),
    ],
)
def test_init_propagates_resolver_http_errors(
    client: TestClient,
    agent_id: str,
    expected_status: int,
    expected_detail: str,
):
    response = client.post(
        "/api/agent/init",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "filename": "PROFILE.md",
            "text": "x",
            "agentId": agent_id,
        },
    )
    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
