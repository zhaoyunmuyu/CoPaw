# -*- coding: utf-8 -*-
"""Regression tests for authoritative tenant-scoped agent config reads."""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient

from swe.app.routers import agent as agent_router
from swe.app.routers import mcp as mcp_router
from swe.app.routers import tools as tools_router
from swe.app.routers.agent_scoped import AgentContextMiddleware
from swe.app import agent_context
from swe.config.config import (
    AgentProfileConfig,
    AgentProfileRef,
    AgentsRunningConfig,
    BuiltinToolConfig,
    MCPClientConfig,
    MCPConfig,
    ToolsConfig,
)


def _agent_config(
    agent_id: str,
    workspace_dir: str,
    *,
    mcp_clients: dict[str, MCPClientConfig] | None = None,
    builtin_tools: dict[str, BuiltinToolConfig] | None = None,
    running: AgentsRunningConfig | None = None,
) -> AgentProfileConfig:
    return AgentProfileConfig(
        id=agent_id,
        name=agent_id,
        workspace_dir=workspace_dir,
        mcp=MCPConfig(clients=mcp_clients or {}),
        tools=(
            ToolsConfig(builtin_tools=builtin_tools)
            if builtin_tools is not None
            else None
        ),
        running=running or AgentsRunningConfig(),
    )


def _root_config(
    tenant_id: str,
    *,
    active_agent: str = "default",
    agent_ids: tuple[str, ...] = ("default",),
) -> SimpleNamespace:
    profiles = {
        agent_id: AgentProfileRef(
            id=agent_id,
            workspace_dir=f"/tmp/{tenant_id}/workspaces/{agent_id}",
        )
        for agent_id in agent_ids
    }
    return SimpleNamespace(
        agents=SimpleNamespace(
            active_agent=active_agent,
            profiles=profiles,
        ),
    )


class FakeMultiAgentManager:
    """Return stale workspace snapshots to expose authoritative-read bugs."""

    def __init__(
        self,
        workspace_snapshots: dict[tuple[str | None, str], AgentProfileConfig],
    ) -> None:
        self.workspace_snapshots = workspace_snapshots
        self.calls: list[tuple[str, str | None]] = []

    async def get_agent(
        self,
        agent_id: str,
        tenant_id: str | None = None,
    ) -> SimpleNamespace:
        self.calls.append((agent_id, tenant_id))
        snapshot = self.workspace_snapshots[(tenant_id, agent_id)]
        return SimpleNamespace(
            agent_id=agent_id,
            tenant_id=tenant_id,
            workspace_dir=snapshot.workspace_dir,
            config=snapshot.model_copy(deep=True),
        )


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    root_configs: dict[str, SimpleNamespace] = {}
    config_store: dict[tuple[str | None, str], AgentProfileConfig] = {}
    workspace_snapshots: dict[
        tuple[str | None, str],
        AgentProfileConfig,
    ] = {}
    load_calls: list[tuple[str | None, str]] = []
    save_calls: list[tuple[str | None, str]] = []
    reload_calls: list[tuple[str, str | None]] = []

    def fake_load_agent_config(
        agent_id: str,
        config_path=None,
        *,
        tenant_id: str | None = None,
    ) -> AgentProfileConfig:
        del config_path
        load_calls.append((tenant_id, agent_id))
        assert tenant_id is not None
        return config_store[(tenant_id, agent_id)].model_copy(deep=True)

    def fake_save_agent_config(
        agent_id: str,
        agent_config: AgentProfileConfig,
        config_path=None,
        *,
        tenant_id: str | None = None,
    ) -> None:
        del config_path
        save_calls.append((tenant_id, agent_id))
        assert tenant_id is not None
        config_store[(tenant_id, agent_id)] = agent_config.model_copy(
            deep=True,
        )

    def fake_schedule_agent_reload(
        request: Request,
        agent_id: str,
        tenant_id: str | None = None,
    ) -> None:
        del request
        reload_calls.append((agent_id, tenant_id))

    manager = FakeMultiAgentManager(workspace_snapshots)

    app = FastAPI()
    app.add_middleware(AgentContextMiddleware)

    @app.middleware("http")
    async def bind_tenant_id(request: Request, call_next):
        request.state.tenant_id = request.headers.get("X-Tenant-Id")
        return await call_next(request)

    scoped_router = APIRouter(prefix="/agents/{agentId}")
    scoped_router.include_router(mcp_router.router)
    scoped_router.include_router(tools_router.router)
    scoped_router.include_router(agent_router.router)

    app.include_router(mcp_router.router, prefix="/api")
    app.include_router(tools_router.router, prefix="/api")
    app.include_router(agent_router.router, prefix="/api")
    app.include_router(scoped_router, prefix="/api")
    app.state.multi_agent_manager = manager

    monkeypatch.setattr(
        agent_context,
        "_get_tenant_aware_config",
        lambda tenant_id=None, source_id=None: root_configs[tenant_id],
    )
    monkeypatch.setattr(
        "swe.config.config.load_agent_config",
        fake_load_agent_config,
    )
    monkeypatch.setattr(
        "swe.config.config.save_agent_config",
        fake_save_agent_config,
    )
    monkeypatch.setattr(
        agent_context,
        "load_agent_config",
        fake_load_agent_config,
        raising=False,
    )

    for module in (mcp_router, tools_router, agent_router):
        monkeypatch.setattr(
            module,
            "load_agent_config",
            fake_load_agent_config,
            raising=False,
        )
        monkeypatch.setattr(
            module,
            "save_agent_config",
            fake_save_agent_config,
            raising=False,
        )
        monkeypatch.setattr(
            module,
            "schedule_agent_reload",
            fake_schedule_agent_reload,
        )

    return SimpleNamespace(
        client=TestClient(app),
        root_configs=root_configs,
        config_store=config_store,
        workspace_snapshots=workspace_snapshots,
        load_calls=load_calls,
        save_calls=save_calls,
        reload_calls=reload_calls,
        manager=manager,
    )


def test_get_mcp_uses_active_agent_and_authoritative_agent_json(
    harness: SimpleNamespace,
) -> None:
    harness.root_configs["tenant-a"] = _root_config(
        "tenant-a",
        active_agent="alpha",
        agent_ids=("alpha", "beta"),
    )
    harness.config_store[("tenant-a", "alpha")] = _agent_config(
        "alpha",
        "/tmp/tenant-a/workspaces/alpha",
        mcp_clients={
            "fresh": MCPClientConfig(
                name="Fresh",
                transport="stdio",
                command="fresh",
            ),
        },
    )
    harness.workspace_snapshots[("tenant-a", "alpha")] = _agent_config(
        "alpha",
        "/tmp/tenant-a/workspaces/alpha",
        mcp_clients={
            "stale": MCPClientConfig(
                name="Stale",
                transport="stdio",
                command="stale",
            ),
        },
    )

    response = harness.client.get(
        "/api/mcp",
        headers={"X-Tenant-Id": "tenant-a"},
    )

    assert response.status_code == 200
    assert [item["key"] for item in response.json()] == ["fresh"]
    assert harness.manager.calls == [("alpha", "tenant-a")]
    assert harness.load_calls == [("tenant-a", "alpha")]


def test_get_mcp_prefers_route_scoped_agent_over_active_agent(
    harness: SimpleNamespace,
) -> None:
    harness.root_configs["tenant-a"] = _root_config(
        "tenant-a",
        active_agent="alpha",
        agent_ids=("alpha", "beta"),
    )
    harness.config_store[("tenant-a", "beta")] = _agent_config(
        "beta",
        "/tmp/tenant-a/workspaces/beta",
        mcp_clients={
            "beta-client": MCPClientConfig(
                name="Beta",
                transport="stdio",
                command="beta",
            ),
        },
    )
    harness.workspace_snapshots[("tenant-a", "beta")] = _agent_config(
        "beta",
        "/tmp/tenant-a/workspaces/beta",
        mcp_clients={
            "stale": MCPClientConfig(
                name="Stale",
                transport="stdio",
                command="stale",
            ),
        },
    )

    response = harness.client.get(
        "/api/agents/beta/mcp",
        headers={"X-Tenant-Id": "tenant-a"},
    )

    assert response.status_code == 200
    assert [item["key"] for item in response.json()] == ["beta-client"]
    assert harness.manager.calls == [("beta", "tenant-a")]
    assert harness.load_calls == [("tenant-a", "beta")]


@pytest.mark.parametrize(
    ("method", "path", "payload", "expected_keys"),
    [
        (
            "post",
            "/api/mcp",
            {
                "client_key": "fetch",
                "client": {
                    "name": "Fetch",
                    "transport": "stdio",
                    "command": "fetch",
                },
            },
            ["fetch"],
        ),
        (
            "put",
            "/api/mcp/fetch",
            {
                "name": "Fetch Updated",
                "transport": "stdio",
                "command": "fetch-updated",
            },
            ["fetch"],
        ),
        (
            "patch",
            "/api/mcp/fetch/toggle",
            None,
            ["fetch"],
        ),
        (
            "delete",
            "/api/mcp/fetch",
            None,
            [],
        ),
    ],
)
def test_mcp_reads_do_not_oscillate_after_mutation(
    harness: SimpleNamespace,
    method: str,
    path: str,
    payload: dict | None,
    expected_keys: list[str],
) -> None:
    harness.root_configs["tenant-a"] = _root_config("tenant-a")
    harness.config_store[("tenant-a", "default")] = _agent_config(
        "default",
        "/tmp/tenant-a/workspaces/default",
        mcp_clients=(
            {
                "fetch": MCPClientConfig(
                    name="Fetch",
                    enabled=False,
                    transport="stdio",
                    command="fetch-old",
                ),
            }
            if method != "post"
            else {}
        ),
    )
    harness.workspace_snapshots[("tenant-a", "default")] = _agent_config(
        "default",
        "/tmp/tenant-a/workspaces/default",
        mcp_clients={
            "fetch": MCPClientConfig(
                name="Fetch",
                enabled=False,
                transport="stdio",
                command="fetch-old",
            ),
        }
        if method != "post"
        else {},
    )

    request = getattr(harness.client, method)
    kwargs = {"headers": {"X-Tenant-Id": "tenant-a"}}
    if payload is not None:
        kwargs["json"] = payload
    mutation_response = request(path, **kwargs)

    assert mutation_response.status_code in {200, 201}
    first_read = harness.client.get(
        "/api/mcp",
        headers={"X-Tenant-Id": "tenant-a"},
    )
    second_read = harness.client.get(
        "/api/mcp",
        headers={"X-Tenant-Id": "tenant-a"},
    )

    assert first_read.status_code == 200
    assert second_read.status_code == 200
    assert [item["key"] for item in first_read.json()] == expected_keys
    assert second_read.json() == first_read.json()
    assert harness.reload_calls == [("default", "tenant-a")]


def test_mcp_reads_are_isolated_between_tenants_with_same_agent_id(
    harness: SimpleNamespace,
) -> None:
    for tenant_id in ("tenant-a", "tenant-b"):
        harness.root_configs[tenant_id] = _root_config(tenant_id)

    harness.config_store[("tenant-a", "default")] = _agent_config(
        "default",
        "/tmp/tenant-a/workspaces/default",
        mcp_clients={
            "tenant-a-only": MCPClientConfig(
                name="Tenant A",
                transport="stdio",
                command="tenant-a",
            ),
        },
    )
    harness.config_store[("tenant-b", "default")] = _agent_config(
        "default",
        "/tmp/tenant-b/workspaces/default",
        mcp_clients={
            "tenant-b-only": MCPClientConfig(
                name="Tenant B",
                transport="stdio",
                command="tenant-b",
            ),
        },
    )
    harness.workspace_snapshots[("tenant-a", "default")] = _agent_config(
        "default",
        "/tmp/tenant-a/workspaces/default",
        mcp_clients={},
    )
    harness.workspace_snapshots[("tenant-b", "default")] = _agent_config(
        "default",
        "/tmp/tenant-b/workspaces/default",
        mcp_clients={
            "stale": MCPClientConfig(
                name="Stale",
                transport="stdio",
                command="stale",
            ),
        },
    )

    response_a = harness.client.get(
        "/api/mcp",
        headers={"X-Tenant-Id": "tenant-a"},
    )
    response_b = harness.client.get(
        "/api/mcp",
        headers={"X-Tenant-Id": "tenant-b"},
    )

    assert [item["key"] for item in response_a.json()] == ["tenant-a-only"]
    assert [item["key"] for item in response_b.json()] == ["tenant-b-only"]


def test_tools_list_reads_authoritative_agent_json(
    harness: SimpleNamespace,
) -> None:
    harness.root_configs["tenant-a"] = _root_config("tenant-a")
    harness.config_store[("tenant-a", "default")] = _agent_config(
        "default",
        "/tmp/tenant-a/workspaces/default",
        builtin_tools={
            "fetch_tool": BuiltinToolConfig(
                name="fetch_tool",
                enabled=True,
                description="fresh",
            ),
        },
    )
    harness.workspace_snapshots[("tenant-a", "default")] = _agent_config(
        "default",
        "/tmp/tenant-a/workspaces/default",
        builtin_tools={
            "stale_tool": BuiltinToolConfig(
                name="stale_tool",
                enabled=False,
                description="stale",
            ),
        },
    )

    response = harness.client.get(
        "/api/tools",
        headers={"X-Tenant-Id": "tenant-a"},
    )

    assert response.status_code == 200
    tool_names = [item["name"] for item in response.json()]
    assert "fetch_tool" in tool_names
    assert "stale_tool" not in tool_names
    assert harness.load_calls == [("tenant-a", "default")]


def test_running_config_reads_authoritative_agent_json(
    harness: SimpleNamespace,
) -> None:
    harness.root_configs["tenant-a"] = _root_config("tenant-a")
    harness.config_store[("tenant-a", "default")] = _agent_config(
        "default",
        "/tmp/tenant-a/workspaces/default",
        running=AgentsRunningConfig(max_input_length=8192),
    )
    harness.workspace_snapshots[("tenant-a", "default")] = _agent_config(
        "default",
        "/tmp/tenant-a/workspaces/default",
        running=AgentsRunningConfig(max_input_length=1024),
    )

    response = harness.client.get(
        "/api/agent/running-config",
        headers={"X-Tenant-Id": "tenant-a"},
    )

    assert response.status_code == 200
    assert response.json()["max_input_length"] == 8192
    assert harness.load_calls == [("tenant-a", "default")]
