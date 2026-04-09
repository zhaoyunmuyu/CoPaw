# -*- coding: utf-8 -*-
"""Tenant-local agent resolution tests."""
import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from swe.agents.skills_manager import (
    get_skill_pool_dir,
    get_workspace_skill_manifest_path,
    reconcile_pool_manifest,
)

SRC_ROOT = Path(__file__).parent.parent.parent.parent / "src"
_AGENT_CONTEXT_FILE = SRC_ROOT / "swe" / "app" / "agent_context.py"
_ROUTER_FILE = SRC_ROOT / "swe" / "app" / "routers" / "agents.py"
_MANAGER_FILE = SRC_ROOT / "swe" / "app" / "multi_agent_manager.py"


class FakeWorkspace:
    def __init__(self, agent_id: str, workspace_dir: str, tenant_id: str | None = None):
        self.agent_id = agent_id
        self.workspace_dir = workspace_dir
        self.tenant_id = tenant_id
        self.manager = None
        self.started = False

    async def start(self):
        self.started = True

    def set_manager(self, manager):
        self.manager = manager


class AgentProfileRef(BaseModel):
    id: str
    workspace_dir: str
    enabled: bool = True


class AgentProfileConfig(BaseModel):
    id: str
    name: str
    description: str = ""
    workspace_dir: str
    language: str = "en"
    channels: object | None = None
    mcp: object | None = None
    heartbeat: object | None = None
    tools: object | None = None


class ChannelConfig:
    pass


class MCPConfig:
    pass


class HeartbeatConfig:
    pass


class ToolsConfig:
    pass


def _write_skill(skill_dir: Path, description: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        (
            f"---\nname: {skill_dir.name}\n"
            f"description: {description}\n---\n"
        ),
        encoding="utf-8",
    )


def _restore_original_modules(original_modules):
    for name, module in original_modules.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def _install_test_stubs() -> dict[str, object | None]:
    original_modules = {
        name: sys.modules.get(name)
        for name in [
            "swe.config.utils",
            "swe.config.context",
            "swe.config.config",
            "swe.agents.utils.file_handling",
            "swe.app.utils",
            "swe.agents.memory.agent_md_manager",
            "swe.agents.utils",
            "swe.app.multi_agent_manager",
            "swe.app.workspace",
        ]
    }
    config_utils = types.ModuleType("swe.config.utils")
    config_utils.load_config = lambda *args, **kwargs: None
    config_utils.save_config = lambda *args, **kwargs: None
    config_utils.get_tenant_working_dir = lambda tenant_id=None: Path("/tmp") / (tenant_id or "global")
    config_utils.get_tenant_working_dir_strict = lambda tenant_id=None: Path("/tmp") / tenant_id if tenant_id else (_ for _ in ()).throw(RuntimeError("tenant context required"))
    config_utils.get_tenant_config_path = lambda tenant_id=None: Path("/tmp") / (tenant_id or "global") / "config.json"
    config_utils.get_tenant_config_path_strict = lambda tenant_id=None: Path("/tmp") / tenant_id / "config.json" if tenant_id else (_ for _ in ()).throw(RuntimeError("tenant context required"))
    sys.modules["swe.config.utils"] = config_utils

    context_path = SRC_ROOT / "swe" / "config" / "context.py"
    context_spec = importlib.util.spec_from_file_location("swe.config.context", context_path)
    context_module = importlib.util.module_from_spec(context_spec)
    sys.modules["swe.config.context"] = context_module
    assert context_spec is not None and context_spec.loader is not None
    context_spec.loader.exec_module(context_module)

    config_config = types.ModuleType("swe.config.config")
    config_config.AgentProfileRef = AgentProfileRef
    config_config.AgentProfileConfig = AgentProfileConfig
    config_config.ChannelConfig = ChannelConfig
    config_config.MCPConfig = MCPConfig
    config_config.HeartbeatConfig = HeartbeatConfig
    config_config.ToolsConfig = ToolsConfig
    config_config.generate_short_agent_id = lambda: "stubid"
    config_config.load_agent_config = lambda agent_id: None
    config_config.save_agent_config = lambda agent_id, config: None
    sys.modules["swe.config.config"] = config_config

    file_handling = types.ModuleType("swe.agents.utils.file_handling")
    file_handling.read_text_file_with_encoding_fallback = lambda path: ""
    sys.modules["swe.agents.utils.file_handling"] = file_handling

    app_utils = types.ModuleType("swe.app.utils")
    app_utils.schedule_agent_reload = lambda *args, **kwargs: None
    sys.modules["swe.app.utils"] = app_utils

    memory_manager = types.ModuleType("swe.agents.memory.agent_md_manager")
    memory_manager.AgentMdManager = object
    sys.modules["swe.agents.memory.agent_md_manager"] = memory_manager

    agents_utils = types.ModuleType("swe.agents.utils")
    agents_utils.copy_builtin_qa_md_files = lambda *args, **kwargs: None
    sys.modules["swe.agents.utils"] = agents_utils

    multi_agent_manager = types.ModuleType("swe.app.multi_agent_manager")
    multi_agent_manager.MultiAgentManager = object
    sys.modules["swe.app.multi_agent_manager"] = multi_agent_manager

    workspace_module = types.ModuleType("swe.app.workspace")
    workspace_module.Workspace = FakeWorkspace
    sys.modules["swe.app.workspace"] = workspace_module
    return original_modules



def _load_module(module_name: str, file_path: Path, package_name: str):
    if package_name not in sys.modules:
        pkg = types.ModuleType(package_name)
        pkg.__path__ = [str(file_path.parent)]
        sys.modules[package_name] = pkg
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


_ORIGINAL_MODULES = _install_test_stubs()
agent_context = _load_module(
    "swe.app.agent_context",
    _AGENT_CONTEXT_FILE,
    "swe.app",
)
agents_router = _load_module(
    "swe.app.routers.agents",
    _ROUTER_FILE,
    "swe.app.routers",
)
multi_agent_manager = _load_module(
    "swe.app.multi_agent_manager",
    _MANAGER_FILE,
    "swe.app",
)
_restore_original_modules(_ORIGINAL_MODULES)


def test_get_tenant_aware_config_uses_tenant_config_path(monkeypatch):
    expected_config = SimpleNamespace(name="tenant-config")
    observed = {}

    def fake_get_tenant_config_path(tenant_id=None):
        assert tenant_id == "tenant-a"
        return Path("/tmp/tenant-a/config.json")

    def fake_load_config(path=None):
        observed["path"] = path
        return expected_config

    monkeypatch.setattr(agent_context, "get_tenant_config_path", fake_get_tenant_config_path, raising=False)
    monkeypatch.setattr(agent_context, "load_config", fake_load_config)

    resolved = agent_context._get_tenant_aware_config("tenant-a")

    assert resolved is expected_config
    assert observed["path"] == Path("/tmp/tenant-a/config.json")


def test_get_agent_for_request_prefers_request_workspace():
    workspace = object()
    request = SimpleNamespace(
        state=SimpleNamespace(workspace=workspace),
        headers={},
        app=SimpleNamespace(state=SimpleNamespace()),
    )

    resolved = asyncio.run(agent_context.get_agent_for_request(request))

    assert resolved is workspace


def test_get_agent_for_request_explicit_agent_id_overrides_request_workspace(monkeypatch):
    workspace = SimpleNamespace(agent_id="default")
    manager_calls = []

    class Manager:
        async def get_agent(self, agent_id, tenant_id=None):
            manager_calls.append(agent_id)
            return SimpleNamespace(agent_id=agent_id)

    config = SimpleNamespace(
        agents=SimpleNamespace(
            profiles={"other": SimpleNamespace(enabled=True)},
            active_agent="default",
        ),
    )
    request = SimpleNamespace(
        state=SimpleNamespace(workspace=workspace, tenant_id="tenant-a"),
        headers={},
        app=SimpleNamespace(
            state=SimpleNamespace(multi_agent_manager=Manager()),
        ),
    )

    monkeypatch.setattr(agent_context, "_get_tenant_aware_config", lambda tenant_id=None: config)

    resolved = asyncio.run(agent_context.get_agent_for_request(request, agent_id="other"))

    assert resolved.agent_id == "other"
    assert manager_calls == ["other"]


def test_get_agent_for_request_uses_tenant_workspace_for_active_agent(monkeypatch):
    tenant_workspace = SimpleNamespace(agent_id="alpha")
    tenant_config = SimpleNamespace(
        agents=SimpleNamespace(
            profiles={"alpha": SimpleNamespace(enabled=True)},
            active_agent="alpha",
        ),
    )

    class Manager:
        async def get_agent(self, agent_id):
            return SimpleNamespace(agent_id="global-default")

    request = SimpleNamespace(
        state=SimpleNamespace(workspace=tenant_workspace, tenant_id="tenant-a"),
        headers={},
        app=SimpleNamespace(
            state=SimpleNamespace(multi_agent_manager=Manager()),
        ),
    )

    monkeypatch.setattr(agent_context, "_get_tenant_aware_config", lambda tenant_id=None: tenant_config)

    resolved = asyncio.run(agent_context.get_agent_for_request(request))

    assert resolved is tenant_workspace


def test_multi_agent_manager_uses_tenant_config_when_tenant_id_provided(monkeypatch):
    observed = []
    tenant_ref = SimpleNamespace(workspace_dir="/tmp/tenant-a/workspaces/tenant-only")

    monkeypatch.setattr(
        multi_agent_manager,
        "get_tenant_config_path",
        lambda tenant_id=None: Path(f"/tmp/{tenant_id}/config.json"),
        raising=False,
    )

    def fake_load_config(path=None):
        observed.append(path)
        return SimpleNamespace(
            agents=SimpleNamespace(profiles={"tenant-only": tenant_ref}),
        )

    monkeypatch.setattr(multi_agent_manager, "load_config", fake_load_config)

    manager = multi_agent_manager.MultiAgentManager()
    resolved = asyncio.run(manager.get_agent("tenant-only", tenant_id="tenant-a"))

    assert observed == [Path("/tmp/tenant-a/config.json")]
    assert resolved.workspace_dir == tenant_ref.workspace_dir


def test_multi_agent_manager_uses_global_config(monkeypatch):
    tenant_only_ref = SimpleNamespace(workspace_dir="/tmp/tenant-a/workspaces/tenant-only")
    global_ref = SimpleNamespace(workspace_dir="/tmp/global/workspaces/tenant-only")

    monkeypatch.setattr(
        multi_agent_manager,
        "load_config",
        lambda: SimpleNamespace(
            agents=SimpleNamespace(profiles={"tenant-only": global_ref}),
        ),
    )

    manager = multi_agent_manager.MultiAgentManager()
    resolved = asyncio.run(manager.get_agent("tenant-only"))

    assert resolved.workspace_dir == global_ref.workspace_dir
    assert resolved.workspace_dir != tenant_only_ref.workspace_dir


def test_create_agent_uses_tenant_config_path(tmp_path, monkeypatch):
    config = SimpleNamespace(agents=SimpleNamespace(profiles={}))
    request = SimpleNamespace(
        state=SimpleNamespace(tenant_id="tenant-a"),
        app=SimpleNamespace(state=SimpleNamespace()),
    )
    body = agents_router.CreateAgentRequest(name="Tenant Agent")
    observed = {}

    monkeypatch.setattr(
        agents_router,
        "get_tenant_config_path",
        lambda tenant_id=None: tmp_path / tenant_id / "config.json",
        raising=False,
    )
    monkeypatch.setattr(
        agents_router,
        "get_tenant_config_path_strict",
        lambda tenant_id=None: tmp_path / tenant_id / "config.json",
        raising=False,
    )

    def fake_load_config(path=None, *args, **kwargs):
        observed["load_path"] = path
        return config

    def fake_save_config(saved_config, path=None, *args, **kwargs):
        observed["save_path"] = path

    monkeypatch.setattr(agents_router, "load_config", fake_load_config)
    monkeypatch.setattr(agents_router, "save_config", fake_save_config)
    monkeypatch.setattr(
        agents_router,
        "_save_agent_config_for_request",
        lambda agent_id, cfg, req: None,
    )
    monkeypatch.setattr(agents_router, "save_agent_config", lambda agent_id, cfg: None)
    monkeypatch.setattr(agents_router, "generate_short_agent_id", lambda: "abc123")
    monkeypatch.setattr(agents_router, "_initialize_agent_workspace", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        agents_router,
        "get_tenant_working_dir",
        lambda tenant_id=None: tmp_path / tenant_id,
    )

    asyncio.run(agents_router.create_agent(request, body))

    assert observed["load_path"] == tmp_path / "tenant-a" / "config.json"
    assert observed["save_path"] == tmp_path / "tenant-a" / "config.json"


def test_create_agent_defaults_to_tenant_workspace(tmp_path, monkeypatch):
    config = SimpleNamespace(agents=SimpleNamespace(profiles={}))
    request = SimpleNamespace(
        state=SimpleNamespace(tenant_id="tenant-a"),
        app=SimpleNamespace(state=SimpleNamespace()),
    )
    body = agents_router.CreateAgentRequest(name="Tenant Agent")

    monkeypatch.setattr(agents_router, "load_config", lambda *args, **kwargs: config)
    monkeypatch.setattr(agents_router, "save_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        agents_router,
        "_save_agent_config_for_request",
        lambda agent_id, cfg, req: None,
    )
    monkeypatch.setattr(agents_router, "save_agent_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(agents_router, "generate_short_agent_id", lambda: "abc123")
    monkeypatch.setattr(agents_router, "_initialize_agent_workspace", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        agents_router,
        "get_tenant_working_dir",
        lambda tenant_id=None: tmp_path / tenant_id,
    )

    response = asyncio.run(agents_router.create_agent(request, body))

    assert response.workspace_dir.endswith("tenant-a/workspaces/abc123")


def test_get_agent_uses_tenant_request_scope(monkeypatch):
    request = SimpleNamespace(
        state=SimpleNamespace(tenant_id="tenant-a"),
        app=SimpleNamespace(state=SimpleNamespace()),
    )
    tenant_config = agents_router.AgentProfileConfig(
        id="tenant-only",
        name="Tenant Agent",
        workspace_dir="/tmp/tenant-a/workspaces/tenant-only",
    )

    monkeypatch.setattr(
        agents_router,
        "_load_agent_config_for_request",
        lambda agent_id, req: tenant_config,
    )
    monkeypatch.setattr(
        agents_router,
        "load_agent_config",
        lambda agent_id: (_ for _ in ()).throw(AssertionError("used global loader")),
    )

    resolved = asyncio.run(
        agents_router.get_agent(agentId="tenant-only", request=request)
    )

    assert resolved is tenant_config


def test_create_agent_requires_tenant_context_for_workspace_path(monkeypatch):
    request = SimpleNamespace(
        state=SimpleNamespace(),
        app=SimpleNamespace(state=SimpleNamespace()),
    )
    body = agents_router.CreateAgentRequest(name="Tenant Agent")
    config = SimpleNamespace(agents=SimpleNamespace(profiles={}))

    monkeypatch.setattr(agents_router, "_get_tenant_config", lambda req: config)
    monkeypatch.setattr(agents_router, "generate_short_agent_id", lambda: "abc123")
    monkeypatch.setattr(agents_router, "_initialize_agent_workspace", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        agents_router,
        "_save_agent_config_for_request",
        lambda agent_id, cfg, req: None,
    )
    monkeypatch.setattr(
        agents_router,
        "get_tenant_working_dir",
        lambda tenant_id=None: Path("/tmp/global-fallback"),
    )

    with pytest.raises(Exception, match="tenant"):
        asyncio.run(agents_router.create_agent(request, body))


def test_create_agent_omitted_skill_names_seed_all_tenant_pool_skills(
    tmp_path,
    monkeypatch,
):
    tenant_dir = tmp_path / "tenant-a"
    request = SimpleNamespace(
        state=SimpleNamespace(tenant_id="tenant-a"),
        app=SimpleNamespace(state=SimpleNamespace()),
    )
    config = SimpleNamespace(agents=SimpleNamespace(profiles={}))

    _write_skill(
        get_skill_pool_dir(working_dir=tenant_dir) / "guidance",
        "tenant guidance",
    )
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_dir) / "docx",
        "tenant docx",
    )
    reconcile_pool_manifest(working_dir=tenant_dir)

    monkeypatch.setattr(agents_router, "_get_tenant_config", lambda req: config)
    monkeypatch.setattr(
        agents_router,
        "_save_tenant_config",
        lambda saved_config, req: None,
    )
    monkeypatch.setattr(
        agents_router,
        "_save_agent_config_for_request",
        lambda agent_id, cfg, req: None,
    )
    monkeypatch.setattr(
        agents_router,
        "_ensure_default_heartbeat_md",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        agents_router,
        "generate_short_agent_id",
        lambda: "agent1",
    )
    monkeypatch.setattr(
        agents_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tenant_dir,
    )

    response = asyncio.run(
        agents_router.create_agent(
            request,
            agents_router.CreateAgentRequest(name="Tenant Agent"),
        ),
    )

    workspace_dir = Path(response.workspace_dir)
    assert (workspace_dir / "skills" / "guidance" / "SKILL.md").exists()
    assert (workspace_dir / "skills" / "docx" / "SKILL.md").exists()

    manifest = json.loads(
        get_workspace_skill_manifest_path(workspace_dir).read_text(
            encoding="utf-8",
        ),
    )
    assert set(manifest["skills"]) == {"guidance", "docx"}


def test_create_agent_explicit_skill_names_stay_selective(
    tmp_path,
    monkeypatch,
):
    tenant_dir = tmp_path / "tenant-a"
    request = SimpleNamespace(
        state=SimpleNamespace(tenant_id="tenant-a"),
        app=SimpleNamespace(state=SimpleNamespace()),
    )
    config = SimpleNamespace(agents=SimpleNamespace(profiles={}))

    _write_skill(
        get_skill_pool_dir(working_dir=tenant_dir) / "guidance",
        "tenant guidance",
    )
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_dir) / "docx",
        "tenant docx",
    )
    reconcile_pool_manifest(working_dir=tenant_dir)

    monkeypatch.setattr(agents_router, "_get_tenant_config", lambda req: config)
    monkeypatch.setattr(
        agents_router,
        "_save_tenant_config",
        lambda saved_config, req: None,
    )
    monkeypatch.setattr(
        agents_router,
        "_save_agent_config_for_request",
        lambda agent_id, cfg, req: None,
    )
    monkeypatch.setattr(
        agents_router,
        "_ensure_default_heartbeat_md",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        agents_router,
        "generate_short_agent_id",
        lambda: "agent1",
    )
    monkeypatch.setattr(
        agents_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tenant_dir,
    )

    response = asyncio.run(
        agents_router.create_agent(
            request,
            agents_router.CreateAgentRequest(
                name="Tenant Agent",
                skill_names=["guidance"],
            ),
        ),
    )

    workspace_dir = Path(response.workspace_dir)
    assert (workspace_dir / "skills" / "guidance" / "SKILL.md").exists()
    assert not (workspace_dir / "skills" / "docx").exists()

    manifest = json.loads(
        get_workspace_skill_manifest_path(workspace_dir).read_text(
            encoding="utf-8",
        ),
    )
    assert set(manifest["skills"]) == {"guidance"}


def test_create_agent_explicit_empty_skill_names_create_empty_workspace_skills(
    tmp_path,
    monkeypatch,
):
    tenant_dir = tmp_path / "tenant-a"
    request = SimpleNamespace(
        state=SimpleNamespace(tenant_id="tenant-a"),
        app=SimpleNamespace(state=SimpleNamespace()),
    )
    config = SimpleNamespace(agents=SimpleNamespace(profiles={}))

    _write_skill(
        get_skill_pool_dir(working_dir=tenant_dir) / "guidance",
        "tenant guidance",
    )
    reconcile_pool_manifest(working_dir=tenant_dir)

    monkeypatch.setattr(agents_router, "_get_tenant_config", lambda req: config)
    monkeypatch.setattr(
        agents_router,
        "_save_tenant_config",
        lambda saved_config, req: None,
    )
    monkeypatch.setattr(
        agents_router,
        "_save_agent_config_for_request",
        lambda agent_id, cfg, req: None,
    )
    monkeypatch.setattr(
        agents_router,
        "_ensure_default_heartbeat_md",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        agents_router,
        "generate_short_agent_id",
        lambda: "agent1",
    )
    monkeypatch.setattr(
        agents_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tenant_dir,
    )

    response = asyncio.run(
        agents_router.create_agent(
            request,
            agents_router.CreateAgentRequest(
                name="Tenant Agent",
                skill_names=[],
            ),
        ),
    )

    workspace_dir = Path(response.workspace_dir)
    assert not (workspace_dir / "skills" / "guidance").exists()

    manifest = json.loads(
        get_workspace_skill_manifest_path(workspace_dir).read_text(
            encoding="utf-8",
        ),
    )
    assert manifest["skills"] == {}
