# -*- coding: utf-8 -*-
"""Tenant-scoped skill pool router tests."""
import asyncio
import importlib.util
import json
import sys
import types
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

SRC_ROOT = Path(__file__).parent.parent.parent.parent / "src"
_ROUTER_FILE = SRC_ROOT / "swe" / "app" / "routers" / "skills.py"
_SKILLS_MANAGER_FILE = SRC_ROOT / "swe" / "agents" / "skills_manager.py"


def _ensure_package(package_name: str) -> None:
    parts = package_name.split(".")
    for index in range(1, len(parts) + 1):
        name = ".".join(parts[:index])
        if name in sys.modules:
            continue
        package = types.ModuleType(name)
        package.__path__ = [str(SRC_ROOT.joinpath(*parts[:index]))]
        sys.modules[name] = package


def _load_module(
    module_name: str,
    file_path: Path,
    package_name: str,
) -> ModuleType:
    _ensure_package(package_name)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(cast(ModuleSpec, spec))
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return cast(ModuleType, module)


skills_manager = _load_module(
    "swe.agents.skills_manager",
    _SKILLS_MANAGER_FILE,
    "swe.agents",
)
get_pool_skill_manifest_path = skills_manager.get_pool_skill_manifest_path
get_skill_pool_dir = skills_manager.get_skill_pool_dir
get_workspace_skill_manifest_path = (
    skills_manager.get_workspace_skill_manifest_path
)
get_workspace_skills_dir = skills_manager.get_workspace_skills_dir
reconcile_pool_manifest = skills_manager.reconcile_pool_manifest
reconcile_workspace_manifest = skills_manager.reconcile_workspace_manifest

skills_router = _load_module(
    "swe.app.routers.skills",
    _ROUTER_FILE,
    "swe.app.routers",
)


def _request(tenant_id: str | None = "tenant-a") -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(tenant_id=tenant_id))


def _write_skill(skill_dir: Path, description: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        (
            f"---\nname: {skill_dir.name}\n"
            f"description: {description}\n---\n"
        ),
        encoding="utf-8",
    )


def _write_workspace_scaffold(workspace_dir: Path) -> None:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "sessions").mkdir(exist_ok=True)
    (workspace_dir / "memory").mkdir(exist_ok=True)
    for filename, payload in {
        "agent.json": {},
        "chats.json": {"version": 1, "chats": []},
        "jobs.json": {"version": 1, "jobs": []},
        "token_usage.json": {},
    }.items():
        (workspace_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _set_workspace_skill_state(
    workspace_dir: Path,
    skill_name: str,
    *,
    enabled: bool,
    description: str,
) -> None:
    _write_workspace_scaffold(workspace_dir)
    _write_skill(
        get_workspace_skills_dir(workspace_dir) / skill_name,
        description,
    )
    reconcile_workspace_manifest(workspace_dir)

    manifest_path = get_workspace_skill_manifest_path(workspace_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["skills"][skill_name]["enabled"] = enabled
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _workspace_skill_enabled(workspace_dir: Path, skill_name: str) -> bool:
    manifest = json.loads(
        get_workspace_skill_manifest_path(workspace_dir).read_text(
            encoding="utf-8",
        ),
    )
    return bool(manifest["skills"][skill_name]["enabled"])


def _stub_agent_request(
    monkeypatch,
    *,
    workspace_dir: Path,
    agent_id: str,
    tenant_id: str,
) -> None:
    async def fake_get_agent_for_request(request):
        del request
        return SimpleNamespace(
            workspace_dir=str(workspace_dir),
            agent_id=agent_id,
            tenant_id=tenant_id,
        )

    monkeypatch.setitem(
        sys.modules,
        "swe.app.agent_context",
        SimpleNamespace(get_agent_for_request=fake_get_agent_for_request),
    )


def test_list_pool_skills_passes_tenant_working_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_dir = tmp_path / "tenant-a"
    observed: dict[str, Path] = {}

    def resolve_tenant_dir(*args, **kwargs) -> Path:
        del args, kwargs
        return tenant_dir

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        resolve_tenant_dir,
    )

    def fake_build_pool_skill_specs(*, working_dir: Path) -> list[object]:
        observed["working_dir"] = working_dir
        return []

    monkeypatch.setattr(
        skills_router,
        "_build_pool_skill_specs",
        fake_build_pool_skill_specs,
    )

    result = asyncio.run(skills_router.list_pool_skills(_request()))

    assert result == []
    assert observed["working_dir"] == tenant_dir


def test_list_pool_skills_returns_tenant_local_results(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_a_dir = tmp_path / "tenant-a"
    tenant_b_dir = tmp_path / "tenant-b"
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_a_dir) / "alpha",
        "tenant-a skill",
    )
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_b_dir) / "beta",
        "tenant-b skill",
    )
    reconcile_pool_manifest(working_dir=tenant_a_dir)
    reconcile_pool_manifest(working_dir=tenant_b_dir)

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )

    tenant_a = asyncio.run(
        skills_router.list_pool_skills(_request("tenant-a")),
    )
    tenant_b = asyncio.run(
        skills_router.list_pool_skills(_request("tenant-b")),
    )

    assert [skill.name for skill in tenant_a] == ["alpha"]
    assert [skill.name for skill in tenant_b] == ["beta"]


def test_update_pool_skill_config_uses_tenant_manifest_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_dir = tmp_path / "tenant-a"
    observed: dict[str, Path] = {}

    def resolve_tenant_dir(*args, **kwargs) -> Path:
        del args, kwargs
        return tenant_dir

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        resolve_tenant_dir,
    )

    def fake_get_pool_skill_manifest_path(
        *,
        working_dir: Path,
    ) -> Path:
        observed["working_dir"] = working_dir
        return tenant_dir / "skill_pool" / "skill.json"

    monkeypatch.setattr(
        skills_router,
        "get_pool_skill_manifest_path",
        fake_get_pool_skill_manifest_path,
    )

    def always_mutate(*args, **kwargs) -> bool:
        del args, kwargs
        return True

    monkeypatch.setattr(
        skills_router,
        "_mutate_json",
        always_mutate,
    )

    result = asyncio.run(
        skills_router.update_pool_skill_config(
            "demo",
            skills_router.SkillConfigRequest(config={"x": 1}),
            _request(),
        ),
    )

    assert result == {"updated": True}
    assert observed["working_dir"] == tenant_dir


def test_update_pool_skill_config_only_mutates_current_tenant(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_a_dir = tmp_path / "tenant-a"
    tenant_b_dir = tmp_path / "tenant-b"
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_a_dir) / "shared",
        "tenant-a skill",
    )
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_b_dir) / "shared",
        "tenant-b skill",
    )
    reconcile_pool_manifest(working_dir=tenant_a_dir)
    reconcile_pool_manifest(working_dir=tenant_b_dir)

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )

    updated = asyncio.run(
        skills_router.update_pool_skill_config(
            "shared",
            skills_router.SkillConfigRequest(config={"tenant": "a"}),
            _request("tenant-a"),
        ),
    )
    tenant_a_config = asyncio.run(
        skills_router.get_pool_skill_config("shared", _request("tenant-a")),
    )
    tenant_b_config = asyncio.run(
        skills_router.get_pool_skill_config("shared", _request("tenant-b")),
    )

    assert updated == {"updated": True}
    assert tenant_a_config == {"config": {"tenant": "a"}}
    assert tenant_b_config == {"config": {}}


def test_list_broadcast_tenants_returns_discovered_tenant_ids(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        skills_router,
        "list_all_tenant_ids",
        lambda: ["default", "tenant-a", "tenant-b"],
    )

    result = asyncio.run(skills_router.list_broadcast_tenants())

    assert result.tenant_ids == ["default", "tenant-a", "tenant-b"]


def test_broadcast_pool_skills_to_bootstrapped_tenant(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_tenant = tmp_path / "tenant-a"
    target_tenant = tmp_path / "tenant-b"
    target_workspace = target_tenant / "workspaces" / "default"

    _write_skill(
        get_skill_pool_dir(working_dir=source_tenant) / "guidance",
        "source guidance",
    )
    reconcile_pool_manifest(working_dir=source_tenant)

    _write_skill(
        get_skill_pool_dir(working_dir=target_tenant) / "tenant-local-only",
        "tenant local only",
    )
    _write_workspace_scaffold(target_workspace)
    _write_skill(
        get_workspace_skills_dir(target_workspace) / "tenant-local-only",
        "tenant local only",
    )
    reconcile_pool_manifest(working_dir=target_tenant)
    reconcile_workspace_manifest(target_workspace)

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )

    class FakeInitializer:
        def __init__(self, base_working_dir: Path, tenant_id: str):
            self.base_working_dir = base_working_dir
            self.tenant_id = tenant_id

        def has_seeded_bootstrap(self) -> bool:
            return True

        def ensure_seeded_bootstrap(self) -> dict[str, object]:
            raise AssertionError("should not bootstrap an existing tenant")

    monkeypatch.setitem(
        sys.modules,
        "swe.app.workspace.tenant_initializer",
        SimpleNamespace(TenantInitializer=FakeInitializer),
    )

    result = asyncio.run(
        skills_router.broadcast_pool_skills_to_default_agents(
            _request("tenant-a"),
            skills_router.BroadcastDefaultAgentsRequest(
                skill_names=["guidance"],
                target_tenant_ids=["tenant-b"],
                overwrite=True,
            ),
        ),
    )

    assert len(result.results) == 1
    tenant_result = result.results[0]
    assert tenant_result.success is True
    assert tenant_result.bootstrapped is False
    assert tenant_result.pool_updated == ["guidance"]
    assert tenant_result.default_agent_updated == ["guidance"]

    target_pool_skill = (
        get_skill_pool_dir(working_dir=target_tenant) / "guidance" / "SKILL.md"
    ).read_text(encoding="utf-8")
    default_workspace_skill = (
        get_workspace_skills_dir(target_workspace) / "guidance" / "SKILL.md"
    ).read_text(encoding="utf-8")
    untouched_pool_skill = (
        get_skill_pool_dir(working_dir=target_tenant)
        / "tenant-local-only"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    untouched_workspace_skill = (
        get_workspace_skills_dir(target_workspace)
        / "tenant-local-only"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "source guidance" in target_pool_skill
    assert "source guidance" in default_workspace_skill
    assert "tenant local only" in untouched_pool_skill
    assert "tenant local only" in untouched_workspace_skill


def test_broadcast_pool_skills_bootstraps_missing_tenant(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_tenant = tmp_path / "tenant-a"
    target_tenant = tmp_path / "tenant-new"
    _write_skill(
        get_skill_pool_dir(working_dir=source_tenant) / "guidance",
        "source guidance",
    )
    reconcile_pool_manifest(working_dir=source_tenant)

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )

    bootstrap_calls: list[str] = []

    class FakeInitializer:
        def __init__(self, base_working_dir: Path, tenant_id: str):
            self.base_working_dir = base_working_dir
            self.tenant_id = tenant_id

        def has_seeded_bootstrap(self) -> bool:
            return False

        def ensure_seeded_bootstrap(self) -> dict[str, object]:
            bootstrap_calls.append(self.tenant_id)
            tenant_dir = tmp_path / self.tenant_id
            default_workspace = tenant_dir / "workspaces" / "default"
            _write_workspace_scaffold(default_workspace)
            get_skill_pool_dir(working_dir=tenant_dir).mkdir(
                parents=True,
                exist_ok=True,
            )
            get_pool_skill_manifest_path(working_dir=tenant_dir).write_text(
                json.dumps(
                    {
                        "schema_version": "skill-pool-manifest.v1",
                        "version": 1,
                        "skills": {},
                        "builtin_skill_names": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            get_workspace_skill_manifest_path(default_workspace).write_text(
                json.dumps(
                    {
                        "schema_version": "workspace-skill-manifest.v1",
                        "version": 1,
                        "skills": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return {"minimal": True}

    monkeypatch.setitem(
        sys.modules,
        "swe.app.workspace.tenant_initializer",
        SimpleNamespace(TenantInitializer=FakeInitializer),
    )

    result = asyncio.run(
        skills_router.broadcast_pool_skills_to_default_agents(
            _request("tenant-a"),
            skills_router.BroadcastDefaultAgentsRequest(
                skill_names=["guidance"],
                target_tenant_ids=["tenant-new"],
                overwrite=True,
            ),
        ),
    )

    assert bootstrap_calls == ["tenant-new"]
    assert result.results[0].success is True
    assert result.results[0].bootstrapped is True
    assert (target_tenant / "skill_pool" / "guidance" / "SKILL.md").exists()
    assert (
        target_tenant
        / "workspaces"
        / "default"
        / "skills"
        / "guidance"
        / "SKILL.md"
    ).exists()


def test_broadcast_pool_skills_reports_partial_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_tenant = tmp_path / "tenant-a"
    _write_skill(
        get_skill_pool_dir(working_dir=source_tenant) / "guidance",
        "source guidance",
    )
    reconcile_pool_manifest(working_dir=source_tenant)

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )

    class FakeInitializer:
        def __init__(self, base_working_dir: Path, tenant_id: str):
            self.base_working_dir = base_working_dir
            self.tenant_id = tenant_id

        def has_seeded_bootstrap(self) -> bool:
            return self.tenant_id == "tenant-ok"

        def ensure_seeded_bootstrap(self) -> dict[str, object]:
            if self.tenant_id == "tenant-fail":
                raise RuntimeError("bootstrap failed")
            default_workspace = (
                tmp_path / self.tenant_id / "workspaces" / "default"
            )
            _write_workspace_scaffold(default_workspace)
            return {"minimal": True}

    monkeypatch.setitem(
        sys.modules,
        "swe.app.workspace.tenant_initializer",
        SimpleNamespace(TenantInitializer=FakeInitializer),
    )

    ok_workspace = tmp_path / "tenant-ok" / "workspaces" / "default"
    _write_workspace_scaffold(ok_workspace)
    reconcile_workspace_manifest(ok_workspace)
    reconcile_pool_manifest(working_dir=tmp_path / "tenant-ok")

    result = asyncio.run(
        skills_router.broadcast_pool_skills_to_default_agents(
            _request("tenant-a"),
            skills_router.BroadcastDefaultAgentsRequest(
                skill_names=["guidance"],
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
    assert "bootstrap failed" in result.results[1].error
    assert (
        tmp_path / "tenant-ok" / "skill_pool" / "guidance" / "SKILL.md"
    ).exists()


def test_broadcast_pool_skills_rejects_missing_source_skill(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )

    try:
        asyncio.run(
            skills_router.broadcast_pool_skills_to_default_agents(
                _request("tenant-a"),
                skills_router.BroadcastDefaultAgentsRequest(
                    skill_names=["missing-skill"],
                    target_tenant_ids=["tenant-b"],
                    overwrite=True,
                ),
            ),
        )
    except skills_router.HTTPException as exc:
        assert exc.status_code == 400
        assert "missing-skill" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException")


def test_enable_skill_reload_stays_with_current_tenant_runtime(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_a_default = tmp_path / "tenant-a" / "workspaces" / "default"
    tenant_b_default = tmp_path / "tenant-b" / "workspaces" / "default"
    _set_workspace_skill_state(
        tenant_a_default,
        "docx",
        enabled=False,
        description="tenant-a docx",
    )
    _set_workspace_skill_state(
        tenant_b_default,
        "docx",
        enabled=False,
        description="tenant-b docx",
    )
    _stub_agent_request(
        monkeypatch,
        workspace_dir=tenant_a_default,
        agent_id="default",
        tenant_id="tenant-a",
    )

    reload_calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        skills_router,
        "schedule_agent_reload",
        lambda request, agent_id, tenant_id=None: reload_calls.append(
            (agent_id, tenant_id),
        ),
    )

    result = asyncio.run(
        skills_router.enable_skill(_request("tenant-a"), "docx"),
    )

    assert result["enabled"] is True
    assert _workspace_skill_enabled(tenant_a_default, "docx") is True
    assert _workspace_skill_enabled(tenant_b_default, "docx") is False
    assert reload_calls == [("default", "tenant-a")]


def test_disable_skill_reload_does_not_target_other_agents(
    monkeypatch,
    tmp_path: Path,
) -> None:
    default_workspace = tmp_path / "tenant-a" / "workspaces" / "default"
    qa_workspace = tmp_path / "tenant-a" / "workspaces" / "qa"
    _set_workspace_skill_state(
        default_workspace,
        "docx",
        enabled=True,
        description="default docx",
    )
    _set_workspace_skill_state(
        qa_workspace,
        "docx",
        enabled=True,
        description="qa docx",
    )
    _stub_agent_request(
        monkeypatch,
        workspace_dir=default_workspace,
        agent_id="default",
        tenant_id="tenant-a",
    )

    reload_calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        skills_router,
        "schedule_agent_reload",
        lambda request, agent_id, tenant_id=None: reload_calls.append(
            (agent_id, tenant_id),
        ),
    )

    result = asyncio.run(
        skills_router.disable_skill(_request("tenant-a"), "docx"),
    )

    assert result["disabled"] is True
    assert _workspace_skill_enabled(default_workspace, "docx") is False
    assert _workspace_skill_enabled(qa_workspace, "docx") is True
    assert reload_calls == [("default", "tenant-a")]


def test_batch_enable_skills_reloads_once_for_current_tenant_agent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    default_workspace = tmp_path / "tenant-a" / "workspaces" / "default"
    qa_workspace = tmp_path / "tenant-a" / "workspaces" / "qa"
    _set_workspace_skill_state(
        default_workspace,
        "docx",
        enabled=False,
        description="default docx",
    )
    _set_workspace_skill_state(
        default_workspace,
        "excel",
        enabled=False,
        description="default excel",
    )
    _set_workspace_skill_state(
        qa_workspace,
        "docx",
        enabled=False,
        description="qa docx",
    )
    _stub_agent_request(
        monkeypatch,
        workspace_dir=default_workspace,
        agent_id="default",
        tenant_id="tenant-a",
    )

    reload_calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        skills_router,
        "schedule_agent_reload",
        lambda request, agent_id, tenant_id=None: reload_calls.append(
            (agent_id, tenant_id),
        ),
    )

    result = asyncio.run(
        skills_router.batch_enable_skills(
            _request("tenant-a"),
            ["docx", "excel"],
        ),
    )

    assert result["results"]["docx"]["success"] is True
    assert result["results"]["excel"]["success"] is True
    assert _workspace_skill_enabled(default_workspace, "docx") is True
    assert _workspace_skill_enabled(default_workspace, "excel") is True
    assert _workspace_skill_enabled(qa_workspace, "docx") is False
    assert reload_calls == [("default", "tenant-a")]


def test_batch_disable_skills_without_success_does_not_reload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    default_workspace = tmp_path / "tenant-a" / "workspaces" / "default"
    _write_workspace_scaffold(default_workspace)
    reconcile_workspace_manifest(default_workspace)
    _stub_agent_request(
        monkeypatch,
        workspace_dir=default_workspace,
        agent_id="default",
        tenant_id="tenant-a",
    )

    reload_calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        skills_router,
        "schedule_agent_reload",
        lambda request, agent_id, tenant_id=None: reload_calls.append(
            (agent_id, tenant_id),
        ),
    )

    result = asyncio.run(
        skills_router.batch_disable_skills(
            _request("tenant-a"),
            ["missing-skill"],
        ),
    )

    assert result["results"]["missing-skill"]["success"] is False
    assert not reload_calls


def test_batch_disable_skills_does_not_reload_other_tenants(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_a_default = tmp_path / "tenant-a" / "workspaces" / "default"
    tenant_a_qa = tmp_path / "tenant-a" / "workspaces" / "qa"
    tenant_b_default = tmp_path / "tenant-b" / "workspaces" / "default"
    _set_workspace_skill_state(
        tenant_a_default,
        "docx",
        enabled=True,
        description="tenant-a default docx",
    )
    _set_workspace_skill_state(
        tenant_a_qa,
        "docx",
        enabled=True,
        description="tenant-a qa docx",
    )
    _set_workspace_skill_state(
        tenant_b_default,
        "docx",
        enabled=True,
        description="tenant-b default docx",
    )
    _stub_agent_request(
        monkeypatch,
        workspace_dir=tenant_a_default,
        agent_id="default",
        tenant_id="tenant-a",
    )

    reload_calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        skills_router,
        "schedule_agent_reload",
        lambda request, agent_id, tenant_id=None: reload_calls.append(
            (agent_id, tenant_id),
        ),
    )

    result = asyncio.run(
        skills_router.batch_disable_skills(_request("tenant-a"), ["docx"]),
    )

    assert result["results"]["docx"]["success"] is True
    assert _workspace_skill_enabled(tenant_a_default, "docx") is False
    assert _workspace_skill_enabled(tenant_a_qa, "docx") is True
    assert _workspace_skill_enabled(tenant_b_default, "docx") is True
    assert reload_calls == [("default", "tenant-a")]
