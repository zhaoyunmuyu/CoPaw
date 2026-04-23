# -*- coding: utf-8 -*-
"""MCP cross-tenant distribution router tests."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from swe.app.routers import mcp as mcp_router
from swe.config.config import AgentProfileConfig, MCPClientConfig, MCPConfig


def _request(
    *,
    tenant_id: str = "tenant-source",
    source_id: str | None = None,
    manager: object | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(tenant_id=tenant_id, source_id=source_id),
        app=SimpleNamespace(
            state=SimpleNamespace(multi_agent_manager=manager),
        ),
    )


def _agent_config(
    agent_id: str,
    workspace_dir: str,
    *,
    clients: dict[str, MCPClientConfig] | None = None,
) -> AgentProfileConfig:
    return AgentProfileConfig(
        id=agent_id,
        name=agent_id,
        workspace_dir=workspace_dir,
        mcp=MCPConfig(clients=clients or {}),
    )


class FakeMultiAgentManager:
    def __init__(self, *, fail_reload_tenant: str | None = None) -> None:
        self.fail_reload_tenant = fail_reload_tenant
        self.reload_calls: list[tuple[str, str | None]] = []

    async def reload_agent(
        self,
        agent_id: str,
        tenant_id: str | None = None,
    ) -> bool:
        self.reload_calls.append((agent_id, tenant_id))
        if tenant_id == self.fail_reload_tenant:
            raise RuntimeError("reload failed")
        return True


def test_distribute_mcp_clients_to_bootstrapped_tenant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = FakeMultiAgentManager()
    request = _request(manager=manager)
    source_agent = _agent_config(
        "qa",
        str(tmp_path / "tenant-source" / "workspaces" / "qa"),
        clients={
            "fetch": MCPClientConfig(
                name="Fetch",
                enabled=True,
                transport="streamable_http",
                url="https://source.example/mcp",
                headers={"Authorization": "Bearer real-secret"},
                env={"API_KEY": "real-env-secret"},
            ),
            "filesystem": MCPClientConfig(
                name="Filesystem",
                enabled=False,
                transport="stdio",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem"],
                cwd="/repo/source",
            ),
        },
    )
    masked_workspace_agent = _agent_config(
        "qa",
        str(tmp_path / "tenant-source" / "workspaces" / "qa"),
        clients={
            "fetch": MCPClientConfig(
                name="Fetch",
                enabled=True,
                transport="streamable_http",
                url="https://source.example/mcp",
                headers={"Authorization": "Be***********cret"},
                env={"API_KEY": "re********cret"},
            ),
        },
    )
    target_default_agent = _agent_config(
        "default",
        str(tmp_path / "tenant-target" / "workspaces" / "default"),
        clients={
            "fetch": MCPClientConfig(
                name="Fetch",
                enabled=False,
                transport="streamable_http",
                url="https://target-old.example/mcp",
                headers={"Authorization": "Bearer old"},
                env={"API_KEY": "old-env"},
            ),
            "tenant-local-only": MCPClientConfig(
                name="Local",
                enabled=True,
                transport="stdio",
                command="python",
                args=["local_server.py"],
            ),
        },
    )
    saved_configs: dict[tuple[str | None, str], AgentProfileConfig] = {}

    async def fake_get_agent_for_request(_request):
        return SimpleNamespace(
            agent_id="qa",
            tenant_id="tenant-source",
            config=masked_workspace_agent,
        )

    def fake_load_agent_config(
        agent_id: str,
        config_path: Path | None = None,
        *,
        tenant_id: str | None = None,
    ) -> AgentProfileConfig:
        del config_path
        if (tenant_id, agent_id) == ("tenant-source", "qa"):
            return source_agent.model_copy(deep=True)
        if (tenant_id, agent_id) == ("tenant-target", "default"):
            return target_default_agent.model_copy(deep=True)
        raise AssertionError(
            f"unexpected load: tenant={tenant_id}, agent={agent_id}",
        )

    def fake_save_agent_config(
        agent_id: str,
        agent_config: AgentProfileConfig,
        config_path: Path | None = None,
        *,
        tenant_id: str | None = None,
    ) -> None:
        del config_path
        saved_configs[(tenant_id, agent_id)] = agent_config.model_copy(
            deep=True,
        )

    class FakeInitializer:
        def __init__(
            self,
            base_working_dir: Path,
            tenant_id: str,
            source_id: str | None = None,
        ) -> None:
            assert base_working_dir == tmp_path
            assert tenant_id == "tenant-target"
            assert source_id is None

        def has_seeded_bootstrap(self) -> bool:
            return True

        def ensure_seeded_bootstrap(self) -> dict[str, object]:
            raise AssertionError("should not bootstrap an existing tenant")

    monkeypatch.setitem(
        sys.modules,
        "swe.app.agent_context",
        SimpleNamespace(get_agent_for_request=fake_get_agent_for_request),
    )
    monkeypatch.setattr(
        mcp_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )
    monkeypatch.setattr(
        mcp_router,
        "load_agent_config",
        fake_load_agent_config,
    )
    monkeypatch.setattr(
        mcp_router,
        "save_agent_config",
        fake_save_agent_config,
    )
    monkeypatch.setattr(mcp_router, "TenantInitializer", FakeInitializer)

    result = asyncio.run(
        mcp_router.distribute_mcp_clients_to_default_agents(
            request,
            mcp_router.MCPDistributionRequest(
                client_keys=["fetch"],
                target_tenant_ids=["tenant-target"],
                overwrite=True,
            ),
        ),
    )

    assert len(result.results) == 1
    tenant_result = result.results[0]
    assert tenant_result.success is True
    assert tenant_result.bootstrapped is False
    assert tenant_result.default_agent_updated == ["fetch"]
    saved_target = saved_configs[("tenant-target", "default")]
    assert saved_target.mcp is not None
    assert saved_target.mcp.clients["fetch"].headers == {
        "Authorization": "Bearer real-secret",
    }
    assert saved_target.mcp.clients["fetch"].env == {
        "API_KEY": "real-env-secret",
    }
    assert (
        saved_target.mcp.clients["fetch"].url == "https://source.example/mcp"
    )
    assert saved_target.mcp.clients["tenant-local-only"].command == "python"
    assert manager.reload_calls == [("default", "tenant-target")]


def test_distribute_mcp_clients_bootstraps_missing_tenant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = FakeMultiAgentManager()
    request = _request(source_id="ruice", manager=manager)
    source_agent = _agent_config(
        "qa",
        str(tmp_path / "tenant-source" / "workspaces" / "qa"),
        clients={
            "filesystem": MCPClientConfig(
                name="Filesystem",
                enabled=False,
                transport="stdio",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem"],
                cwd="/repo/source",
            ),
        },
    )
    target_default_agent = _agent_config(
        "default",
        str(tmp_path / "tenant-new" / "workspaces" / "default"),
        clients={},
    )
    bootstrap_calls: list[str] = []

    async def fake_get_agent_for_request(_request):
        return SimpleNamespace(
            agent_id="qa",
            tenant_id="tenant-source",
            config=source_agent,
        )

    def fake_load_agent_config(
        agent_id: str,
        config_path: Path | None = None,
        *,
        tenant_id: str | None = None,
    ) -> AgentProfileConfig:
        del config_path
        if (tenant_id, agent_id) == ("tenant-source", "qa"):
            return source_agent.model_copy(deep=True)
        if (tenant_id, agent_id) == ("tenant-new", "default"):
            return target_default_agent.model_copy(deep=True)
        raise AssertionError(
            f"unexpected load: tenant={tenant_id}, agent={agent_id}",
        )

    class FakeInitializer:
        def __init__(
            self,
            base_working_dir: Path,
            tenant_id: str,
            source_id: str | None = None,
        ) -> None:
            assert base_working_dir == tmp_path
            self.tenant_id = tenant_id
            self.source_id = source_id

        def has_seeded_bootstrap(self) -> bool:
            return False

        def ensure_seeded_bootstrap(self) -> dict[str, object]:
            assert self.source_id == "ruice"
            bootstrap_calls.append(self.tenant_id)
            return {"minimal": True}

    monkeypatch.setitem(
        sys.modules,
        "swe.app.agent_context",
        SimpleNamespace(get_agent_for_request=fake_get_agent_for_request),
    )
    monkeypatch.setattr(
        mcp_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )
    monkeypatch.setattr(
        mcp_router,
        "load_agent_config",
        fake_load_agent_config,
    )
    monkeypatch.setattr(
        mcp_router,
        "save_agent_config",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(mcp_router, "TenantInitializer", FakeInitializer)

    result = asyncio.run(
        mcp_router.distribute_mcp_clients_to_default_agents(
            request,
            mcp_router.MCPDistributionRequest(
                client_keys=["filesystem"],
                target_tenant_ids=["tenant-new"],
                overwrite=True,
            ),
        ),
    )

    assert bootstrap_calls == ["tenant-new"]
    assert result.results[0].success is True
    assert result.results[0].bootstrapped is True
    assert manager.reload_calls == [("default", "tenant-new")]


def test_distribute_mcp_clients_uses_effective_default_tenant_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = FakeMultiAgentManager()
    request = _request(tenant_id="default", source_id="ruice", manager=manager)
    source_agent = _agent_config(
        "qa",
        str(tmp_path / "default_ruice" / "workspaces" / "qa"),
        clients={
            "fetch": MCPClientConfig(
                name="Fetch",
                enabled=True,
                transport="streamable_http",
                url="https://source.example/mcp",
            ),
        },
    )
    target_default_agent = _agent_config(
        "default",
        str(tmp_path / "default_ruice" / "workspaces" / "default"),
        clients={},
    )
    working_tenant_ids: list[str | None] = []
    load_calls: list[tuple[str | None, str]] = []
    save_calls: list[tuple[str | None, str]] = []

    async def fake_get_agent_for_request(_request):
        return SimpleNamespace(
            agent_id="qa",
            tenant_id="default_ruice",
            config=source_agent,
        )

    def fake_get_tenant_working_dir_strict(tenant_id=None) -> Path:
        working_tenant_ids.append(tenant_id)
        return tmp_path / str(tenant_id)

    def fake_load_agent_config(
        agent_id: str,
        config_path: Path | None = None,
        *,
        tenant_id: str | None = None,
    ) -> AgentProfileConfig:
        del config_path
        load_calls.append((tenant_id, agent_id))
        if (tenant_id, agent_id) == ("default_ruice", "qa"):
            return source_agent.model_copy(deep=True)
        if (tenant_id, agent_id) == ("default_ruice", "default"):
            return target_default_agent.model_copy(deep=True)
        raise AssertionError(
            f"unexpected load: tenant={tenant_id}, agent={agent_id}",
        )

    def fake_save_agent_config(
        agent_id: str,
        agent_config: AgentProfileConfig,
        config_path: Path | None = None,
        *,
        tenant_id: str | None = None,
    ) -> None:
        del agent_config, config_path
        save_calls.append((tenant_id, agent_id))

    class FakeInitializer:
        def __init__(
            self,
            base_working_dir: Path,
            tenant_id: str,
            source_id: str | None = None,
        ) -> None:
            assert base_working_dir == tmp_path
            assert tenant_id == "default"
            assert source_id == "ruice"
            self.effective_tenant_id = "default_ruice"
            self.tenant_dir = tmp_path / self.effective_tenant_id

        def has_seeded_bootstrap(self) -> bool:
            return True

        def ensure_seeded_bootstrap(self) -> dict[str, object]:
            raise AssertionError("should not bootstrap an existing tenant")

    monkeypatch.setitem(
        sys.modules,
        "swe.app.agent_context",
        SimpleNamespace(get_agent_for_request=fake_get_agent_for_request),
    )
    monkeypatch.setattr(
        mcp_router,
        "get_tenant_working_dir_strict",
        fake_get_tenant_working_dir_strict,
    )
    monkeypatch.setattr(
        mcp_router,
        "load_agent_config",
        fake_load_agent_config,
    )
    monkeypatch.setattr(
        mcp_router,
        "save_agent_config",
        fake_save_agent_config,
    )
    monkeypatch.setattr(mcp_router, "TenantInitializer", FakeInitializer)

    result = asyncio.run(
        mcp_router.distribute_mcp_clients_to_default_agents(
            request,
            mcp_router.MCPDistributionRequest(
                client_keys=["fetch"],
                target_tenant_ids=["default"],
                overwrite=True,
            ),
        ),
    )

    assert result.results[0].success is True
    assert working_tenant_ids == ["default_ruice"]
    assert load_calls == [
        ("default_ruice", "qa"),
        ("default_ruice", "default"),
    ]
    assert save_calls == [("default_ruice", "default")]
    assert manager.reload_calls == [("default", "default_ruice")]


def test_distribute_mcp_clients_reports_partial_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = FakeMultiAgentManager(fail_reload_tenant="tenant-fail")
    request = _request(manager=manager)
    source_agent = _agent_config(
        "qa",
        str(tmp_path / "tenant-source" / "workspaces" / "qa"),
        clients={
            "fetch": MCPClientConfig(
                name="Fetch",
                enabled=True,
                transport="streamable_http",
                url="https://source.example/mcp",
                headers={"Authorization": "Bearer real-secret"},
            ),
        },
    )
    target_ok = _agent_config(
        "default",
        str(tmp_path / "tenant-ok" / "workspaces" / "default"),
        clients={},
    )
    target_fail = _agent_config(
        "default",
        str(tmp_path / "tenant-fail" / "workspaces" / "default"),
        clients={},
    )
    saved_configs: dict[tuple[str | None, str], AgentProfileConfig] = {}
    save_calls: list[tuple[str | None, str]] = []

    async def fake_get_agent_for_request(_request):
        return SimpleNamespace(
            agent_id="qa",
            tenant_id="tenant-source",
            config=source_agent,
        )

    def fake_load_agent_config(
        agent_id: str,
        config_path: Path | None = None,
        *,
        tenant_id: str | None = None,
    ) -> AgentProfileConfig:
        del config_path
        if (tenant_id, agent_id) == ("tenant-source", "qa"):
            return source_agent.model_copy(deep=True)
        if (tenant_id, agent_id) == ("tenant-ok", "default"):
            return target_ok.model_copy(deep=True)
        if (tenant_id, agent_id) == ("tenant-fail", "default"):
            return target_fail.model_copy(deep=True)
        raise AssertionError(
            f"unexpected load: tenant={tenant_id}, agent={agent_id}",
        )

    def fake_save_agent_config(
        agent_id: str,
        agent_config: AgentProfileConfig,
        config_path: Path | None = None,
        *,
        tenant_id: str | None = None,
    ) -> None:
        del config_path
        save_calls.append((tenant_id, agent_id))
        saved_configs[(tenant_id, agent_id)] = agent_config.model_copy(
            deep=True,
        )

    monkeypatch.setitem(
        sys.modules,
        "swe.app.agent_context",
        SimpleNamespace(get_agent_for_request=fake_get_agent_for_request),
    )
    monkeypatch.setattr(
        mcp_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )
    monkeypatch.setattr(
        mcp_router,
        "load_agent_config",
        fake_load_agent_config,
    )
    monkeypatch.setattr(
        mcp_router,
        "save_agent_config",
        fake_save_agent_config,
    )
    monkeypatch.setattr(
        mcp_router,
        "TenantInitializer",
        lambda base_working_dir, tenant_id, source_id=None: SimpleNamespace(
            has_seeded_bootstrap=lambda: True,
            ensure_seeded_bootstrap=lambda: {"minimal": True},
        ),
    )

    result = asyncio.run(
        mcp_router.distribute_mcp_clients_to_default_agents(
            request,
            mcp_router.MCPDistributionRequest(
                client_keys=["fetch"],
                target_tenant_ids=["tenant-ok", "tenant-fail"],
                overwrite=True,
            ),
        ),
    )

    assert [item.tenant_id for item in result.results] == [
        "tenant-ok",
        "tenant-fail",
    ]
    assert result.results[0].success is True
    assert result.results[1].success is False
    assert "reload failed" in str(result.results[1].error)
    assert saved_configs[("tenant-fail", "default")].mcp is not None
    assert (
        saved_configs[("tenant-fail", "default")].mcp.clients
        == target_fail.mcp.clients
    )
    assert save_calls == [
        ("tenant-ok", "default"),
        ("tenant-fail", "default"),
        ("tenant-fail", "default"),
    ]
    assert manager.reload_calls == [
        ("default", "tenant-ok"),
        ("default", "tenant-fail"),
        ("default", "tenant-fail"),
    ]


def test_distribute_mcp_clients_rejects_missing_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_get_agent_for_request(_request):
        return SimpleNamespace(
            agent_id="qa",
            tenant_id="tenant-source",
            config=_agent_config(
                "qa",
                str(tmp_path / "tenant-source" / "workspaces" / "qa"),
                clients={
                    "fetch": MCPClientConfig(
                        name="Fetch",
                        transport="streamable_http",
                        url="https://source.example/mcp",
                    ),
                },
            ),
        )

    monkeypatch.setitem(
        sys.modules,
        "swe.app.agent_context",
        SimpleNamespace(get_agent_for_request=fake_get_agent_for_request),
    )

    with pytest.raises(mcp_router.HTTPException) as exc_info:
        asyncio.run(
            mcp_router.distribute_mcp_clients_to_default_agents(
                _request(manager=FakeMultiAgentManager()),
                mcp_router.MCPDistributionRequest(
                    client_keys=["fetch"],
                    target_tenant_ids=["tenant-a"],
                    overwrite=False,
                ),
            ),
        )

    assert exc_info.value.status_code == 400
    assert "overwrite=true" in str(exc_info.value.detail)


def test_distribute_mcp_clients_rejects_missing_source_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_agent = _agent_config(
        "qa",
        str(tmp_path / "tenant-source" / "workspaces" / "qa"),
        clients={},
    )

    async def fake_get_agent_for_request(_request):
        return SimpleNamespace(
            agent_id="qa",
            tenant_id="tenant-source",
            config=source_agent,
        )

    monkeypatch.setitem(
        sys.modules,
        "swe.app.agent_context",
        SimpleNamespace(get_agent_for_request=fake_get_agent_for_request),
    )
    monkeypatch.setattr(
        mcp_router,
        "load_agent_config",
        lambda agent_id, config_path=None, *, tenant_id=None: source_agent.model_copy(
            deep=True,
        ),
    )

    with pytest.raises(mcp_router.HTTPException) as exc_info:
        asyncio.run(
            mcp_router.distribute_mcp_clients_to_default_agents(
                _request(manager=FakeMultiAgentManager()),
                mcp_router.MCPDistributionRequest(
                    client_keys=["missing"],
                    target_tenant_ids=["tenant-a"],
                    overwrite=True,
                ),
            ),
        )

    assert exc_info.value.status_code == 400
    assert "missing" in str(exc_info.value.detail)


def test_list_mcp_distribution_tenants_returns_source_filtered_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str | None] = []
    observed_source_filter: list[bool] = []

    async def fake_list_logical_tenant_ids(
        source_id: str | None = None,
        *,
        source_filter: bool = False,
    ) -> list[str]:
        observed.append(source_id)
        observed_source_filter.append(source_filter)
        return ["default", "tenant-a"]

    monkeypatch.setattr(
        mcp_router,
        "list_logical_tenant_ids",
        fake_list_logical_tenant_ids,
    )

    result = asyncio.run(
        mcp_router.list_mcp_distribution_tenants(
            _request(source_id="ruice"),
        ),
    )

    assert observed == ["ruice"]
    assert observed_source_filter == [True]
    assert result.tenant_ids == ["default", "tenant-a"]


def test_list_mcp_distribution_tenants_empty_when_no_source_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str | None] = []
    observed_source_filter: list[bool] = []

    async def fake_list_logical_tenant_ids(
        source_id: str | None = None,
        *,
        source_filter: bool = False,
    ) -> list[str]:
        observed.append(source_id)
        observed_source_filter.append(source_filter)
        return []

    monkeypatch.setattr(
        mcp_router,
        "list_logical_tenant_ids",
        fake_list_logical_tenant_ids,
    )

    result = asyncio.run(
        mcp_router.list_mcp_distribution_tenants(_request()),
    )

    assert observed == [None]
    assert observed_source_filter == [True]
    assert result.tenant_ids == []
