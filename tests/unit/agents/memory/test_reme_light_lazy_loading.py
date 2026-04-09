# -*- coding: utf-8 -*-
"""Regression tests for ReMe lazy loading and optional chromadb handling."""

import importlib
import subprocess
import sys
from types import SimpleNamespace


def test_importing_memory_package_does_not_import_reme():
    """The memory package should not eagerly import reme."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import swe.agents.memory; "
                "raise SystemExit("
                "0 if not any(name.startswith('reme') for name in sys.modules)"
                " else 1)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_importing_workspace_runtime_does_not_import_reme():
    """Workspace import should not eagerly load reme runtime."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import swe.app.workspace.workspace; "
                "raise SystemExit("
                "0 if not any(name.startswith('reme') for name in sys.modules)"
                " else 1)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_importing_reme_light_memory_manager_does_not_import_reme(monkeypatch):
    """The memory manager module should import without touching reme."""
    module_name = "swe.agents.memory.reme_light_memory_manager"

    for name in [module_name, "swe.agents.memory"]:
        sys.modules.pop(name, None)

    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("reme.reme_light"):
            raise AssertionError("reme.reme_light imported eagerly")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    module = importlib.import_module(module_name)

    assert module.ReMeLightMemoryManager is not None


def test_import_reme_light_retries_with_shim_for_local_backend(monkeypatch):
    """A chromadb import failure should retry with shim for non-chroma backends."""
    import swe.agents.memory.reme_light_memory_manager as module

    fake_module = SimpleNamespace(ReMeLight=object())
    calls: list[str] = []

    def fake_import_module(name: str):
        calls.append(name)
        if len(calls) == 1:
            raise AttributeError(
                "'NoneType' object has no attribute 'ClientAPI'",
            )
        return fake_module

    shim_called: list[bool] = []
    clear_called: list[bool] = []

    monkeypatch.setattr(module.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(
        module,
        "_install_chromadb_compat_shim",
        lambda: shim_called.append(True),
    )
    monkeypatch.setattr(
        module,
        "_clear_cached_reme_modules",
        lambda: clear_called.append(True),
    )

    result = module._import_reme_light("local")

    assert result is fake_module.ReMeLight
    assert calls == ["reme.reme_light", "reme.reme_light"]
    assert shim_called == [True]
    assert clear_called == [True]
