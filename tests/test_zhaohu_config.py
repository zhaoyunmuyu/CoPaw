# -*- coding: utf-8 -*-
"""Tests for Zhaohu channel wiring."""

from copaw.app.channels.registry import clear_builtin_channel_cache
from copaw.app.channels.registry import get_channel_registry
from copaw.config.config import ChannelConfig, ZhaohuConfig


class TestZhaohuConfig:
    def test_defaults(self):
        config = ZhaohuConfig()
        assert config.enabled is False
        assert config.push_url == ""
        assert config.sys_id == ""
        assert config.robot_open_id == ""
        assert config.channel == "ZH"
        assert config.net == "DMZ"
        assert config.request_timeout == 15.0

    def test_channel_config_includes_zhaohu(self):
        ch = ChannelConfig()
        assert hasattr(ch, "zhaohu")
        assert isinstance(ch.zhaohu, ZhaohuConfig)
        assert ch.zhaohu.enabled is False

    def test_channel_config_from_dict(self):
        data = {
            "zhaohu": {
                "enabled": True,
                "push_url": "https://api.zhaohu.example/push",
                "sys_id": "copaw",
                "robot_open_id": "robot-1",
                "channel": "ZH",
                "net": "DMZ",
                "request_timeout": 20.0,
            },
        }
        ch = ChannelConfig(**data)
        assert ch.zhaohu.enabled is True
        assert ch.zhaohu.push_url == "https://api.zhaohu.example/push"
        assert ch.zhaohu.sys_id == "copaw"
        assert ch.zhaohu.robot_open_id == "robot-1"
        assert ch.zhaohu.request_timeout == 20.0


def test_registry_includes_zhaohu_builtin() -> None:
    clear_builtin_channel_cache()
    registry = get_channel_registry()
    assert "zhaohu" in registry
