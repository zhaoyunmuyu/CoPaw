# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from agentscope.tool import ToolResponse

from swe.agents.tools.browser_control import _resolve_output_path
from swe.agents.tools.desktop_screenshot import _tool_ok, desktop_screenshot
from swe.config.context import tenant_context
from swe.security.tenant_path_boundary import (
    AbsolutePathDeniedError,
    PathTraversalError,
)


def _tool_response_json(resp: ToolResponse) -> dict:
    block = resp.content[0]
    text = block.get("text") if isinstance(block, dict) else block.text
    return json.loads(text)


def test_browser_control_output_path_uses_workspace_dir(tmp_path: Path):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.agents.tools.browser_control.WORKING_DIR", tmp_path):
        with patch(
            "swe.security.tenant_path_boundary.WORKING_DIR",
            tmp_path,
        ):
            with tenant_context(
                tenant_id="tenant_a",
                workspace_dir=workspace_dir,
            ):
                resolved = _resolve_output_path("shot.png")

    assert resolved == str(workspace_dir / "browser" / "shot.png")


def test_browser_control_output_path_uses_tenant_root_when_workspace_missing(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"

    with patch("swe.agents.tools.browser_control.WORKING_DIR", tmp_path):
        with patch(
            "swe.security.tenant_path_boundary.WORKING_DIR",
            tmp_path,
        ):
            with tenant_context(tenant_id="tenant_a"):
                resolved = _resolve_output_path("shot.png")

    assert resolved == str(tenant_dir / "browser" / "shot.png")


def test_browser_control_output_path_falls_back_to_global_working_dir_without_tenant_context(
    tmp_path: Path,
):
    with patch("swe.agents.tools.browser_control.WORKING_DIR", tmp_path):
        resolved = _resolve_output_path("shot.png")

    assert resolved == str(tmp_path / "browser" / "shot.png")


def test_browser_control_output_path_fails_closed_on_workspace_boundary_violation(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    tenant_dir.mkdir(parents=True)
    outside_workspace = tmp_path / "outside" / "agent_a"
    outside_workspace.mkdir(parents=True)

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(
            tenant_id="tenant_a",
            workspace_dir=outside_workspace,
        ):
            with pytest.raises(PathTraversalError):
                _resolve_output_path("shot.png")


def test_browser_control_output_path_denies_relative_traversal_outside_tenant(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    # From <workspace>/browser/, "../../../../outside.png" escapes tenant_root.
    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(tenant_id="tenant_a", workspace_dir=workspace_dir):
            with pytest.raises(PathTraversalError):
                _resolve_output_path("../../../../outside.png")


def test_browser_control_output_path_denies_absolute_path_outside_tenant(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)
    outside = tmp_path / "outside.png"

    with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
        with tenant_context(tenant_id="tenant_a", workspace_dir=workspace_dir):
            with pytest.raises(AbsolutePathDeniedError):
                _resolve_output_path(str(outside))


@pytest.mark.asyncio
async def test_desktop_screenshot_default_path_uses_workspace_dir(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.agents.tools.desktop_screenshot._capture_mss") as capture:
        capture.return_value = _tool_ok(
            str(workspace_dir / "desktop_screenshot_1.png"),
            "ok",
        )
        with patch(
            "swe.agents.tools.desktop_screenshot.WORKING_DIR",
            tmp_path,
        ):
            with patch(
                "swe.security.tenant_path_boundary.WORKING_DIR",
                tmp_path,
            ):
                with tenant_context(
                    tenant_id="tenant_a",
                    workspace_dir=workspace_dir,
                ):
                    await desktop_screenshot()

    called_path = capture.call_args[0][0]
    assert called_path.startswith(str(workspace_dir))


@pytest.mark.asyncio
async def test_desktop_screenshot_default_path_uses_tenant_root_when_workspace_missing(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"

    with patch("swe.agents.tools.desktop_screenshot._capture_mss") as capture:
        capture.return_value = _tool_ok(
            str(tenant_dir / "desktop_screenshot_1.png"),
            "ok",
        )
        with patch(
            "swe.agents.tools.desktop_screenshot.WORKING_DIR",
            tmp_path,
        ):
            with patch(
                "swe.security.tenant_path_boundary.WORKING_DIR",
                tmp_path,
            ):
                with tenant_context(tenant_id="tenant_a"):
                    await desktop_screenshot()

    called_path = capture.call_args[0][0]
    assert called_path.startswith(str(tenant_dir))


@pytest.mark.asyncio
async def test_desktop_screenshot_global_fallback_without_tenant_context(
    tmp_path: Path,
):
    with patch("swe.agents.tools.desktop_screenshot._capture_mss") as capture:
        capture.return_value = _tool_ok(
            str(tmp_path / "desktop_screenshot_1.png"),
            "ok",
        )
        with patch(
            "swe.agents.tools.desktop_screenshot.WORKING_DIR",
            tmp_path,
        ):
            await desktop_screenshot()

    called_path = capture.call_args[0][0]
    assert called_path.startswith(str(tmp_path))


@pytest.mark.asyncio
async def test_desktop_screenshot_explicit_traversal_path_denied_returns_error(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    workspace_dir = tenant_dir / "workspaces" / "agent_a"
    workspace_dir.mkdir(parents=True)

    with patch("swe.agents.tools.desktop_screenshot._capture_mss") as capture:
        with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
            with tenant_context(
                tenant_id="tenant_a",
                workspace_dir=workspace_dir,
            ):
                resp = await desktop_screenshot("../../../../outside.png")

    capture.assert_not_called()
    payload = _tool_response_json(resp)
    assert payload["ok"] is False


@pytest.mark.asyncio
async def test_desktop_screenshot_invalid_workspace_default_path_returns_error_not_exception(
    tmp_path: Path,
):
    tenant_dir = tmp_path / "tenant_a"
    tenant_dir.mkdir(parents=True)
    outside_workspace = tmp_path / "outside" / "agent_a"
    outside_workspace.mkdir(parents=True)

    with patch("swe.agents.tools.desktop_screenshot._capture_mss") as capture:
        with patch("swe.security.tenant_path_boundary.WORKING_DIR", tmp_path):
            with tenant_context(
                tenant_id="tenant_a",
                workspace_dir=outside_workspace,
            ):
                resp = await desktop_screenshot()

    capture.assert_not_called()
    payload = _tool_response_json(resp)
    assert payload["ok"] is False
