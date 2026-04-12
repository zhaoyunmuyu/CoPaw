# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Tests for workspace cron coordination environment-based loading.

These tests verify:
- _get_cron_coordination_config() returns values from environment constants
- config.json cannot override environment-derived values
- Missing env values fall back to hardcoded defaults
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from swe.app.workspace.workspace import Workspace
from swe.constant import (
    CRON_CLUSTER_MODE,
    CRON_LEASE_RENEW_INTERVAL_SECONDS,
    CRON_LEASE_TTL_SECONDS,
    CRON_LOCK_SAFETY_MARGIN_SECONDS,
    CRON_COORDINATION_ENABLED,
    CRON_REDIS_URL,
)


class TestWorkspaceCronCoordinationEnvLoading:
    """Tests for workspace cron coordination env-based loading."""

    def test_get_coordination_config_uses_env_defaults(
        self,
        tmp_path: Path,
    ) -> None:
        """Coordination config should use environment-backed defaults."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        ws = Workspace(
            agent_id="test-agent",
            workspace_dir=workspace_dir,
            tenant_id="test-tenant",
        )

        config = ws._get_cron_coordination_config()

        # Defaults should follow the current env-backed constants
        assert config.enabled is CRON_COORDINATION_ENABLED
        assert config.cluster_mode is CRON_CLUSTER_MODE
        assert config.redis_url == CRON_REDIS_URL
        assert config.lease_ttl_seconds == CRON_LEASE_TTL_SECONDS
        assert (
            config.lease_renew_interval_seconds
            == CRON_LEASE_RENEW_INTERVAL_SECONDS
        )

    def test_get_coordination_config_uses_env_overrides(
        self,
        tmp_path: Path,
    ) -> None:
        """Coordination config should use environment variable overrides."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Mock environment constants
        with patch(
            "swe.constant.CRON_COORDINATION_ENABLED",
            True,
        ), patch(
            "swe.constant.CRON_CLUSTER_MODE",
            True,
        ), patch(
            "swe.constant.CRON_REDIS_URL",
            "redis://env-override:6379/1",
        ), patch(
            "swe.constant.CRON_LEASE_TTL_SECONDS",
            60,
        ), patch(
            "swe.constant.CRON_LEASE_RENEW_INTERVAL_SECONDS",
            20,
        ):
            ws = Workspace(
                agent_id="test-agent",
                workspace_dir=workspace_dir,
                tenant_id="test-tenant",
            )

            config = ws._get_cron_coordination_config()

            # Should use environment overrides
            assert config.enabled is True
            assert config.cluster_mode is True
            assert config.redis_url == "redis://env-override:6379/1"
            assert config.lease_ttl_seconds == 60
            assert config.lease_renew_interval_seconds == 20

    def test_get_coordination_config_ignores_config_json(
        self,
        tmp_path: Path,
    ) -> None:
        """Coordination config should ignore config.json cron_coordination."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Create config.json with cron_coordination
        config_path = workspace_dir / "config.json"
        config_data = {
            "cron_coordination": {
                "enabled": True,
                "cluster_mode": True,
                "redis_url": "redis://config-json:6379/0",
                "lease_ttl_seconds": 99,
            },
        }
        config_path.write_text(json.dumps(config_data), encoding="utf-8")

        ws = Workspace(
            agent_id="test-agent",
            workspace_dir=workspace_dir,
            tenant_id="test-tenant",
        )

        config = ws._get_cron_coordination_config()

        # Should NOT use values from config.json
        assert (
            config.enabled is CRON_COORDINATION_ENABLED
        )  # Env-backed default, not config.json
        assert config.redis_url == CRON_REDIS_URL  # Env-backed default

    def test_get_coordination_config_cluster_nodes_from_env(
        self,
        tmp_path: Path,
    ) -> None:
        """Cluster nodes should be parsed from environment variable."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Mock cluster mode and nodes
        with patch(
            "swe.constant.CRON_CLUSTER_MODE",
            True,
        ), patch(
            "swe.constant.CRON_CLUSTER_NODES",
            "node1:6379,node2:6380,node3:6381",
        ):
            ws = Workspace(
                agent_id="test-agent",
                workspace_dir=workspace_dir,
                tenant_id="test-tenant",
            )

            config = ws._get_cron_coordination_config()

            assert config.cluster_mode is True
            assert config.cluster_nodes is not None
            assert len(config.cluster_nodes) == 3
            assert config.cluster_nodes[0] == {"host": "node1", "port": 6379}
            assert config.cluster_nodes[1] == {"host": "node2", "port": 6380}
            assert config.cluster_nodes[2] == {"host": "node3", "port": 6381}

    def test_get_coordination_config_empty_cluster_nodes_when_standalone(
        self,
        tmp_path: Path,
    ) -> None:
        """Cluster nodes should be None when not in cluster mode."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Standalone mode (default)
        with patch(
            "swe.constant.CRON_CLUSTER_MODE",
            False,
        ), patch(
            "swe.constant.CRON_CLUSTER_NODES",
            "node1:6379,node2:6380",
        ):
            ws = Workspace(
                agent_id="test-agent",
                workspace_dir=workspace_dir,
                tenant_id="test-tenant",
            )

            config = ws._get_cron_coordination_config()

            # In standalone mode, cluster_nodes should be None
            assert config.cluster_mode is False
            assert config.cluster_nodes is None


class TestWorkspaceCronCoordinationFallback:
    """Tests for cron coordination fallback to defaults."""

    def test_missing_env_values_use_defaults(
        self,
        tmp_path: Path,
    ) -> None:
        """Missing environment values should fall back to hardcoded defaults."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # No env overrides - use defaults
        ws = Workspace(
            agent_id="test-agent",
            workspace_dir=workspace_dir,
            tenant_id="test-tenant",
        )

        config = ws._get_cron_coordination_config()

        # Verify defaults match the currently loaded env-backed constants
        assert config.enabled is CRON_COORDINATION_ENABLED
        assert config.cluster_mode is CRON_CLUSTER_MODE
        assert config.redis_url == CRON_REDIS_URL
        assert config.lease_ttl_seconds == CRON_LEASE_TTL_SECONDS
        assert (
            config.lease_renew_interval_seconds
            == CRON_LEASE_RENEW_INTERVAL_SECONDS
        )
        assert config.lease_renew_failure_threshold == 3  # Default
        assert (
            config.lock_safety_margin_seconds
            == CRON_LOCK_SAFETY_MARGIN_SECONDS
        )
        assert (
            config.reload_channel_prefix == "swe:cron:reload"
        )  # Code default

    def test_invalid_lease_config_raises_error(
        self,
        tmp_path: Path,
    ) -> None:
        """Invalid lease config (ttl <= renew_interval) should raise ValueError."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Mock invalid lease values: ttl == renew_interval WITH coordination enabled
        with patch(
            "swe.constant.CRON_COORDINATION_ENABLED",
            True,
        ), patch(
            "swe.constant.CRON_LEASE_TTL_SECONDS",
            10,
        ), patch(
            "swe.constant.CRON_LEASE_RENEW_INTERVAL_SECONDS",
            10,
        ):
            ws = Workspace(
                agent_id="test-agent",
                workspace_dir=workspace_dir,
                tenant_id="test-tenant",
            )

            with pytest.raises(
                ValueError,
                match="lease_ttl_seconds must be greater",
            ):
                ws._get_cron_coordination_config()

    def test_invalid_lease_config_ttl_less_than_renew_raises_error(
        self,
        tmp_path: Path,
    ) -> None:
        """Invalid lease config (ttl < renew_interval) should raise ValueError."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Mock invalid lease values: ttl < renew_interval WITH coordination enabled
        with patch(
            "swe.constant.CRON_COORDINATION_ENABLED",
            True,
        ), patch(
            "swe.constant.CRON_LEASE_TTL_SECONDS",
            5,
        ), patch(
            "swe.constant.CRON_LEASE_RENEW_INTERVAL_SECONDS",
            10,
        ):
            ws = Workspace(
                agent_id="test-agent",
                workspace_dir=workspace_dir,
                tenant_id="test-tenant",
            )

            with pytest.raises(
                ValueError,
                match="lease_ttl_seconds must be greater",
            ):
                ws._get_cron_coordination_config()

    def test_invalid_lease_config_allowed_when_disabled(
        self,
        tmp_path: Path,
    ) -> None:
        """Invalid lease config should NOT raise when coordination is disabled."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Mock invalid lease values BUT coordination is disabled
        with patch(
            "swe.constant.CRON_COORDINATION_ENABLED",
            False,
        ), patch(
            "swe.constant.CRON_LEASE_TTL_SECONDS",
            5,
        ), patch(
            "swe.constant.CRON_LEASE_RENEW_INTERVAL_SECONDS",
            10,
        ):
            ws = Workspace(
                agent_id="test-agent",
                workspace_dir=workspace_dir,
                tenant_id="test-tenant",
            )

            # Should NOT raise even though ttl < renew_interval
            config = ws._get_cron_coordination_config()
            assert config.enabled is False
            assert config.lease_ttl_seconds == 5
            assert config.lease_renew_interval_seconds == 10
