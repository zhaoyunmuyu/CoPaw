# -*- coding: utf-8 -*-
"""Tenant binding regression tests for BaseChannel."""
import asyncio
import importlib
import importlib.util
import sys
import types
from pathlib import Path

SRC_ROOT = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(SRC_ROOT))

_ORIGINAL_MODULES = {
    name: sys.modules.get(name)
    for name in [
        "agentscope_runtime.engine.schemas.agent_schemas",
        "swe.app.channels.renderer",
        "swe.app.channels.schema",
        "swe.app.channels.base",
    ]
}


class _EnumValue(str):
    pass


class _ContentType:
    TEXT = _EnumValue("text")
    REFUSAL = _EnumValue("refusal")
    AUDIO = _EnumValue("audio")


class _RunStatus:
    Completed = "completed"


class _DummyContent:
    pass


schema_module = types.ModuleType("agentscope_runtime.engine.schemas.agent_schemas")
schema_module.RunStatus = _RunStatus
schema_module.ContentType = _ContentType
schema_module.TextContent = _DummyContent
schema_module.ImageContent = _DummyContent
schema_module.VideoContent = _DummyContent
schema_module.AudioContent = _DummyContent
schema_module.FileContent = _DummyContent
schema_module.RefusalContent = _DummyContent
schema_module.MessageType = type("MessageType", (), {})
sys.modules["agentscope_runtime.engine.schemas.agent_schemas"] = schema_module

renderer_module = types.ModuleType("swe.app.channels.renderer")
renderer_module.MessageRenderer = lambda style: object()
renderer_module.RenderStyle = lambda **kwargs: kwargs
sys.modules["swe.app.channels.renderer"] = renderer_module

schema2_module = types.ModuleType("swe.app.channels.schema")
schema2_module.ChannelType = str
schema2_module.DEFAULT_CHANNEL = "console"
sys.modules["swe.app.channels.schema"] = schema2_module

config_utils_module = importlib.import_module("swe.config.utils")
config_utils_module.load_config = lambda: types.SimpleNamespace(
    tools=types.SimpleNamespace(builtin_tools={}),
)

base_spec = importlib.util.spec_from_file_location(
    "swe.app.channels.base",
    SRC_ROOT / "swe" / "app" / "channels" / "base.py",
)
base_module = importlib.util.module_from_spec(base_spec)
sys.modules["swe.app.channels.base"] = base_module
assert base_spec is not None and base_spec.loader is not None
base_spec.loader.exec_module(base_module)

for _name, _module in _ORIGINAL_MODULES.items():
    if _module is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _module

from swe.config.context import get_current_tenant_id, get_current_workspace_dir

BaseChannel = base_module.BaseChannel


class _DummyChannel(BaseChannel):
    channel = "dummy"

    def build_agent_request_from_native(self, payload):
        return types.SimpleNamespace(
            session_id=payload["session_id"],
            user_id=payload["user_id"],
            input=[types.SimpleNamespace(content=payload.get("content_parts", []))],
        )


class _CommandRegistry:
    def is_control_command(self, text):
        return False


def test_consume_one_request_binds_workspace_tenant_context_for_tracker_path(tmp_path):
    observed = {}
    channel = _DummyChannel(process=lambda request: None)
    channel.set_workspace(
        types.SimpleNamespace(
            tenant_id="tenant-a",
            workspace_dir=tmp_path / "tenant-a",
        ),
        command_registry=_CommandRegistry(),
    )

    async def fake_consume_with_tracker(request, payload):
        observed["tenant_id"] = get_current_tenant_id()
        observed["workspace_dir"] = get_current_workspace_dir()
        observed["user_id"] = request.user_id

    channel._consume_with_tracker = fake_consume_with_tracker
    channel._extract_query_from_payload = lambda payload: "hello"

    payload = {
        "session_id": "session-a",
        "user_id": "user-a",
        "content_parts": [],
        "meta": {},
    }

    asyncio.run(channel._consume_one_request(payload))

    assert observed == {
        "tenant_id": "tenant-a",
        "workspace_dir": tmp_path / "tenant-a",
        "user_id": "user-a",
    }
    assert get_current_tenant_id() is None
    assert get_current_workspace_dir() is None
