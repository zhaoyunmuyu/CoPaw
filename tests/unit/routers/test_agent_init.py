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
from swe.app.routers.agent_scoped import create_agent_scoped_router


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
    app.include_router(create_agent_scoped_router(), prefix="/api")

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


def test_init_isolates_different_agents_within_same_tenant(
    client: TestClient,
    tmp_path: Path,
):
    agent_1_file = tmp_path / "tenant-a" / "agents" / "agent-1" / "PROFILE.md"
    agent_2_file = tmp_path / "tenant-a" / "agents" / "agent-2" / "PROFILE.md"
    agent_1_file.parent.mkdir(parents=True, exist_ok=True)
    agent_2_file.parent.mkdir(parents=True, exist_ok=True)
    agent_1_file.write_text("agent-1\n", encoding="utf-8")
    agent_2_file.write_text("agent-2\n", encoding="utf-8")

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
    assert agent_1_file.read_text(encoding="utf-8") == "agent-1\nappend"
    assert agent_2_file.read_text(encoding="utf-8") == "agent-2\n"


def test_init_isolates_same_agent_id_across_tenants(
    client: TestClient,
    tmp_path: Path,
):
    tenant_a_file = tmp_path / "tenant-a" / "agents" / "agent-1" / "PROFILE.md"
    tenant_b_file = tmp_path / "tenant-b" / "agents" / "agent-1" / "PROFILE.md"
    tenant_a_file.parent.mkdir(parents=True, exist_ok=True)
    tenant_b_file.parent.mkdir(parents=True, exist_ok=True)
    tenant_a_file.write_text("tenant-a\n", encoding="utf-8")
    tenant_b_file.write_text("tenant-b\n", encoding="utf-8")

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
    assert tenant_a_file.read_text(encoding="utf-8") == "tenant-a\nappend"
    assert tenant_b_file.read_text(encoding="utf-8") == "tenant-b\n"


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


def test_init_not_present_in_agent_scoped_openapi_paths(client: TestClient):
    openapi = client.app.openapi()
    assert "/api/agents/{agentId}/agent/init" not in openapi["paths"]


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
