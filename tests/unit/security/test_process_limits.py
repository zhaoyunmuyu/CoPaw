# -*- coding: utf-8 -*-
"""Tests for tenant-scoped process limit policy resolution."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import call, patch

import pytest
from pydantic import ValidationError

from swe.config.config import Config
from swe.config.context import tenant_context
from swe.config.utils import save_config


def _write_tenant_config(
    base_dir: Path,
    tenant_id: str,
    *,
    enabled: bool,
    shell: bool = True,
    mcp_stdio: bool = True,
    cpu_time_limit_seconds: int | None = None,
    memory_max_mb: int | None = None,
) -> None:
    tenant_dir = base_dir / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    save_config(
        Config.model_validate(
            {
                "security": {
                    "process_limits": {
                        "enabled": enabled,
                        "shell": shell,
                        "mcp_stdio": mcp_stdio,
                        "cpu_time_limit_seconds": cpu_time_limit_seconds,
                        "memory_max_mb": memory_max_mb,
                    },
                },
            },
        ),
        tenant_dir / "config.json",
    )


def test_process_limits_config_rejects_enabled_policy_without_limits() -> None:
    with pytest.raises(ValidationError):
        Config.model_validate(
            {
                "security": {
                    "process_limits": {
                        "enabled": True,
                        "shell": True,
                        "mcp_stdio": True,
                    },
                },
            },
        )


def test_process_limits_config_rejects_enabled_policy_without_scope() -> None:
    with pytest.raises(ValidationError):
        Config.model_validate(
            {
                "security": {
                    "process_limits": {
                        "enabled": True,
                        "shell": False,
                        "mcp_stdio": False,
                        "cpu_time_limit_seconds": 2,
                    },
                },
            },
        )


def test_process_limits_config_defaults_to_disabled() -> None:
    config = Config()

    assert config.security.process_limits.enabled is False
    assert config.security.process_limits.shell is True
    assert config.security.process_limits.mcp_stdio is True
    assert config.security.process_limits.cpu_time_limit_seconds is None
    assert config.security.process_limits.memory_max_mb is None


def test_resolve_current_process_limit_policy_uses_current_tenant_config(
    tmp_path: Path,
) -> None:
    from swe.security.process_limits import resolve_current_process_limit_policy

    _write_tenant_config(
        tmp_path,
        "tenant-a",
        enabled=True,
        cpu_time_limit_seconds=2,
        memory_max_mb=128,
    )
    _write_tenant_config(
        tmp_path,
        "tenant-b",
        enabled=True,
        shell=False,
        cpu_time_limit_seconds=4,
        memory_max_mb=256,
    )

    with patch("swe.constant.WORKING_DIR", tmp_path), patch(
        "swe.config.utils.WORKING_DIR",
        tmp_path,
    ):
        with tenant_context(tenant_id="tenant-b"):
            shell_policy = resolve_current_process_limit_policy("shell")
            mcp_policy = resolve_current_process_limit_policy("mcp_stdio")

    assert shell_policy.enabled is False
    assert mcp_policy.enabled is True
    assert mcp_policy.tenant_id == "tenant-b"
    assert mcp_policy.cpu_time_limit_seconds == 4
    assert mcp_policy.memory_max_bytes == 256 * 1024 * 1024
    assert mcp_policy.diagnostic is None


def test_resolved_policy_builds_unix_preexec_fn(tmp_path: Path) -> None:
    from swe.security.process_limits import resolve_current_process_limit_policy

    _write_tenant_config(
        tmp_path,
        "tenant-a",
        enabled=True,
        cpu_time_limit_seconds=3,
        memory_max_mb=64,
    )

    with patch("swe.constant.WORKING_DIR", tmp_path), patch(
        "swe.config.utils.WORKING_DIR",
        tmp_path,
    ), patch("swe.security.process_limits.sys.platform", "linux"):
        with tenant_context(tenant_id="tenant-a"):
            policy = resolve_current_process_limit_policy("shell")

        with patch("swe.security.process_limits.resource.setrlimit") as mock_setrlimit:
            preexec_fn = policy.build_preexec_fn()
            assert preexec_fn is not None
            preexec_fn()

    assert mock_setrlimit.call_args_list == [
        call(policy.rlimit_cpu, (3, 3)),
        call(policy.rlimit_as, (64 * 1024 * 1024, 64 * 1024 * 1024)),
    ]


def test_resolved_policy_reports_unsupported_platform(tmp_path: Path) -> None:
    from swe.security.process_limits import resolve_current_process_limit_policy

    _write_tenant_config(
        tmp_path,
        "tenant-a",
        enabled=True,
        cpu_time_limit_seconds=2,
        memory_max_mb=32,
    )

    with patch("swe.constant.WORKING_DIR", tmp_path), patch(
        "swe.config.utils.WORKING_DIR",
        tmp_path,
    ), patch("swe.security.process_limits.sys.platform", "win32"):
        with tenant_context(tenant_id="tenant-a"):
            policy = resolve_current_process_limit_policy("shell")

    assert policy.enabled is True
    assert policy.should_enforce is False
    assert policy.build_preexec_fn() is None
    assert "not enforced on this platform" in (policy.diagnostic or "")
