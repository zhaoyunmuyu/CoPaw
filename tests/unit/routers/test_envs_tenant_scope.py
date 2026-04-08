# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Unit tests for tenant-scoped env router and env store behavior."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

ROUTERS_DIR = (
    Path(__file__).resolve().parents[3] / "src" / "swe" / "app" / "routers"
)
if "swe.app.routers" not in sys.modules:
    routers_pkg = types.ModuleType("swe.app.routers")
    routers_pkg.__path__ = [str(ROUTERS_DIR)]
    sys.modules["swe.app.routers"] = routers_pkg
if "swe.config" not in sys.modules:
    config_pkg = types.ModuleType("swe.config")
    config_pkg.__path__ = []
    sys.modules["swe.config"] = config_pkg
if "swe.config.utils" not in sys.modules:
    config_utils_module = types.ModuleType("swe.config.utils")

    def get_tenant_secrets_dir(tenant_id=None):
        raise RuntimeError("test should patch get_tenant_secrets_dir")

    config_utils_module.get_tenant_secrets_dir = get_tenant_secrets_dir
    sys.modules["swe.config.utils"] = config_utils_module

from swe.app.routers.envs import router
from swe.envs.store import delete_env_var, load_envs, save_envs

app = FastAPI()


@app.middleware("http")
async def bind_tenant_id(request: Request, call_next):
    """Bind tenant ID from request header for router tests."""
    request.state.tenant_id = request.headers.get("X-Tenant-Id")
    return await call_next(request)


app.include_router(router, prefix="/api")


@pytest.fixture(autouse=True)
def _use_tmp_env_paths(tmp_path: Path):
    """Redirect tenant secrets directories to a temp directory."""

    def mock_get_tenant_secrets_dir(tenant_id=None):
        return tmp_path / (tenant_id or "default") / ".secret"

    with patch(
        "swe.app.routers.envs.get_tenant_secrets_dir",
        mock_get_tenant_secrets_dir,
    ):
        yield tmp_path


@pytest.fixture
def client():
    """Create a sync test client."""
    return TestClient(app)


def test_save_envs_with_custom_path_does_not_mutate_process_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Custom-path env writes should stay file-scoped."""
    envs_path = tmp_path / "tenant-a" / ".secret" / "envs.json"
    monkeypatch.delenv("TENANT_ONLY_KEY", raising=False)

    save_envs({"TENANT_ONLY_KEY": "value-a"}, envs_path)

    assert load_envs(envs_path) == {"TENANT_ONLY_KEY": "value-a"}
    assert "TENANT_ONLY_KEY" not in os.environ


def test_delete_env_var_with_custom_path_does_not_remove_process_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Custom-path deletes should not remove process env vars."""
    envs_path = tmp_path / "tenant-a" / ".secret" / "envs.json"
    monkeypatch.setenv("TENANT_ONLY_KEY", "runtime")
    save_envs({"TENANT_ONLY_KEY": "tenant"}, envs_path)

    delete_env_var("TENANT_ONLY_KEY", envs_path)

    assert load_envs(envs_path) == {}
    assert os.environ["TENANT_ONLY_KEY"] == "runtime"


def test_tenant_env_api_is_file_scoped_not_process_scoped(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    _use_tmp_env_paths: Path,
):
    """Tenant env API writes should not mutate process-global env."""
    monkeypatch.delenv("TENANT_ONLY_KEY", raising=False)

    response = client.put(
        "/api/envs",
        headers={"X-Tenant-Id": "tenant-a"},
        json={"TENANT_ONLY_KEY": "value-a"},
    )

    envs_path = _use_tmp_env_paths / "tenant-a" / ".secret" / "envs.json"

    assert response.status_code == 200
    assert load_envs(envs_path) == {"TENANT_ONLY_KEY": "value-a"}
    assert "TENANT_ONLY_KEY" not in os.environ
