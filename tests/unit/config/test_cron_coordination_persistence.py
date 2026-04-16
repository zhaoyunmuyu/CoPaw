# -*- coding: utf-8 -*-
"""Tests for cron_coordination config persistence cleanup.

These tests verify:
- Legacy cron_coordination in config.json is ignored during load
- save_config does not persist cron_coordination
- Environment-derived values are used instead
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from swe.config.config import Config, CronCoordinationConfig
from swe.config.utils import load_config, save_config
from swe.constant import (
    CRON_CLUSTER_MODE,
    CRON_COORDINATION_ENABLED,
    CRON_LEASE_RENEW_INTERVAL_SECONDS,
    CRON_LEASE_TTL_SECONDS,
    CRON_REDIS_URL,
)


class TestCronCoordinationConfigPersistence:
    """Tests for cron_coordination persistence cleanup."""

    def test_load_config_ignores_legacy_cron_coordination(
        self,
        tmp_path: Path,
    ) -> None:
        """Legacy cron_coordination section in config.json should be ignored."""
        config_path = tmp_path / "config.json"

        # Create config with legacy cron_coordination section
        legacy_config = {
            "cron_coordination": {
                "enabled": True,
                "cluster_mode": True,
                "redis_url": "redis://custom:6379/0",
                "lease_ttl_seconds": 60,
            },
            "user_timezone": "America/New_York",
        }
        config_path.write_text(json.dumps(legacy_config), encoding="utf-8")

        # Load config - should succeed without cron_coordination
        config = load_config(config_path)

        # Config should load successfully
        assert isinstance(config, Config)
        # cron_coordination should not be accessible (field removed)
        assert not hasattr(config, "cron_coordination")

    def test_save_config_excludes_cron_coordination(
        self,
        tmp_path: Path,
    ) -> None:
        """Saved config.json should not contain cron_coordination."""
        config_path = tmp_path / "config.json"

        # Create and save a config
        config = Config(user_timezone="Asia/Tokyo")
        save_config(config, config_path)

        # Read the saved file
        saved_data = json.loads(config_path.read_text(encoding="utf-8"))

        # Should not contain cron_coordination
        assert "cron_coordination" not in saved_data

    def test_legacy_config_rewritten_without_cron_coordination(
        self,
        tmp_path: Path,
    ) -> None:
        """Legacy config with cron_coordination should be rewritten without it."""
        config_path = tmp_path / "config.json"

        # Create config with legacy cron_coordination
        legacy_config = {
            "cron_coordination": {
                "enabled": True,
                "redis_url": "redis://old:6379/0",
            },
            "user_timezone": "Europe/London",
        }
        config_path.write_text(json.dumps(legacy_config), encoding="utf-8")

        # Load the legacy config
        config = load_config(config_path)

        # Save it back
        save_config(config, config_path)

        # Read and verify
        saved_data = json.loads(config_path.read_text(encoding="utf-8"))

        # cron_coordination should be removed
        assert "cron_coordination" not in saved_data
        # Other fields should be preserved
        assert saved_data.get("user_timezone") == "Europe/London"


class TestCronCoordinationModel:
    """Tests for CronCoordinationConfig model (kept for backward compat)."""

    def test_cron_coordination_config_defaults(self) -> None:
        """CronCoordinationConfig should still work with defaults."""
        cc = CronCoordinationConfig()

        assert cc.enabled is CRON_COORDINATION_ENABLED
        assert cc.cluster_mode is CRON_CLUSTER_MODE
        assert cc.redis_url == CRON_REDIS_URL
        assert cc.lease_ttl_seconds == CRON_LEASE_TTL_SECONDS
        assert (
            cc.lease_renew_interval_seconds
            == CRON_LEASE_RENEW_INTERVAL_SECONDS
        )

    def test_cron_coordination_config_custom_values(self) -> None:
        """CronCoordinationConfig should accept custom values."""
        cc = CronCoordinationConfig(
            enabled=True,
            cluster_mode=True,
            redis_url="redis://custom:6379/1",
            lease_ttl_seconds=60,
        )

        assert cc.enabled is True
        assert cc.cluster_mode is True
        assert cc.redis_url == "redis://custom:6379/1"
        assert cc.lease_ttl_seconds == 60

    def test_cron_coordination_config_validation(self) -> None:
        """CronCoordinationConfig should validate lease configuration."""
        # Invalid: ttl <= renew_interval
        with pytest.raises(
            ValueError,
            match="lease_ttl_seconds must be greater",
        ):
            CronCoordinationConfig(
                enabled=True,
                lease_ttl_seconds=10,
                lease_renew_interval_seconds=10,
            )

        # Valid: ttl > renew_interval
        cc = CronCoordinationConfig(
            enabled=True,
            lease_ttl_seconds=30,
            lease_renew_interval_seconds=10,
        )
        assert cc.lease_ttl_seconds == 30
        assert cc.lease_renew_interval_seconds == 10
