# -*- coding: utf-8 -*-

from typing import Any, List

from fastapi import APIRouter, Body, Header, HTTPException, Path, Request

from ...config import (
    load_config,
    save_config,
    get_heartbeat_config,
    ChannelConfig,
    ChannelConfigUnion,
    get_available_channels,
    get_config_path,
)
from ..channels.registry import BUILTIN_CHANNEL_KEYS
from ...config.config import AgentsLLMRoutingConfig, HeartbeatConfig

from .schemas_config import HeartbeatBody

router = APIRouter(prefix="/config", tags=["config"])


@router.get(
    "/channels",
    summary="List all channels",
    description="Retrieve configuration for all available channels",
)
async def list_channels(
    x_user_id: str | None = Header(None, alias="X-User-ID")
) -> dict:
    """List all channel configs (filtered by available channels)."""
    user_id = x_user_id or "default"
    config_path = get_config_path(user_id)
    config = load_config(config_path)
    available = get_available_channels()

    # Get all channel configs from model_dump and __pydantic_extra__
    all_configs = config.channels.model_dump()
    extra = getattr(config.channels, "__pydantic_extra__", None) or {}
    all_configs.update(extra)

    # Return all available channels (use default config if not saved)
    result = {}
    for key in available:
        if key in all_configs:
            channel_data = (
                dict(all_configs[key])
                if isinstance(all_configs[key], dict)
                else all_configs[key]
            )
        else:
            # Channel registered but no config saved yet, use empty default
            channel_data = {"enabled": False, "bot_prefix": ""}
        if isinstance(channel_data, dict):
            channel_data["isBuiltin"] = key in BUILTIN_CHANNEL_KEYS
        result[key] = channel_data

    return result


@router.get(
    "/channels/types",
    summary="List channel types",
    description="Return all available channel type identifiers",
)
async def list_channel_types() -> List[str]:
    """Return available channel type identifiers (env-filtered)."""
    return list(get_available_channels())


@router.put(
    "/channels",
    response_model=ChannelConfig,
    summary="Update all channels",
    description="Update configuration for all channels at once",
)
async def put_channels(
    channels_config: ChannelConfig = Body(
        ...,
        description="Complete channel configuration",
    ),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> ChannelConfig:
    """Update all channel configs."""
    user_id = x_user_id or "default"
    config_path = get_config_path(user_id)
    config = load_config(config_path)
    config.channels = channels_config
    save_config(config, config_path)
    return channels_config


@router.get(
    "/channels/{channel_name}",
    response_model=ChannelConfigUnion,
    summary="Get channel config",
    description="Retrieve configuration for a specific channel by name",
)
async def get_channel(
    channel_name: str = Path(
        ...,
        description="Name of the channel to retrieve",
        min_length=1,
    ),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> ChannelConfigUnion:
    """Get a specific channel config by name."""
    user_id = x_user_id or "default"
    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    config_path = get_config_path(user_id)
    config = load_config(config_path)
    single_channel_config = getattr(config.channels, channel_name, None)
    if single_channel_config is None:
        extra = getattr(config.channels, "__pydantic_extra__", None) or {}
        single_channel_config = extra.get(channel_name)
    if single_channel_config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    return single_channel_config


@router.put(
    "/channels/{channel_name}",
    response_model=ChannelConfigUnion,
    summary="Update channel config",
    description="Update configuration for a specific channel by name",
)
async def put_channel(
    channel_name: str = Path(
        ...,
        description="Name of the channel to update",
        min_length=1,
    ),
    single_channel_config: dict = Body(
        ...,
        description="Updated channel configuration",
    ),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> ChannelConfigUnion:
    """Update a specific channel config by name."""
    user_id = x_user_id or "default"
    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    config_path = get_config_path(user_id)
    config = load_config(config_path)

    # Create the appropriate config object based on channel_name
    if channel_name == "telegram":
        from ...config.config import TelegramConfig

        channel_config = TelegramConfig(**single_channel_config)
    elif channel_name == "dingtalk":
        from ...config.config import DingTalkConfig

        channel_config = DingTalkConfig(**single_channel_config)
    elif channel_name == "discord":
        from ...config.config import DiscordConfig

        channel_config = DiscordConfig(**single_channel_config)
    elif channel_name == "feishu":
        from ...config.config import FeishuConfig

        channel_config = FeishuConfig(**single_channel_config)
    elif channel_name == "qq":
        from ...config.config import QQConfig

        channel_config = QQConfig(**single_channel_config)
    elif channel_name == "imessage":
        from ...config.config import IMessageChannelConfig

        channel_config = IMessageChannelConfig(**single_channel_config)
    elif channel_name == "console":
        from ...config.config import ConsoleConfig

        channel_config = ConsoleConfig(**single_channel_config)
    elif channel_name == "voice":
        from ...config.config import VoiceChannelConfig

        channel_config = VoiceChannelConfig(**single_channel_config)
    else:
        # For custom channels, just use the dict
        channel_config = single_channel_config

    # Allow setting extra (plugin) channel config
    setattr(config.channels, channel_name, channel_config)
    save_config(config, config_path)
    return channel_config


@router.get(
    "/heartbeat",
    summary="Get heartbeat config",
    description="Return current heartbeat config (interval, target, etc.)",
)
async def get_heartbeat(
    x_user_id: str | None = Header(None, alias="X-User-ID")
) -> Any:
    """Return effective heartbeat config (from file or default)."""
    user_id = x_user_id or "default"
    config_path = get_config_path(user_id)
    hb = (
        get_heartbeat_config()
        if not config_path.exists()
        else load_config(config_path).agents.defaults.heartbeat
    )
    if hb is None:
        hb = get_heartbeat_config()
    return hb.model_dump(mode="json", by_alias=True)


@router.put(
    "/heartbeat",
    summary="Update heartbeat config",
    description="Update heartbeat and hot-reload the scheduler",
)
async def put_heartbeat(
    request: Request,
    body: HeartbeatBody = Body(..., description="Heartbeat configuration"),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> Any:
    """Update heartbeat config and reschedule the heartbeat job."""
    user_id = x_user_id or "default"
    config_path = get_config_path(user_id)
    config = load_config(config_path)
    hb = HeartbeatConfig(
        enabled=body.enabled,
        every=body.every,
        target=body.target,
        active_hours=body.active_hours,
    )
    config.agents.defaults.heartbeat = hb
    save_config(config, config_path)

    cron_manager = getattr(request.app.state, "cron_manager", None)
    if cron_manager is not None:
        await cron_manager.reschedule_heartbeat(user_id)

    return hb.model_dump(mode="json", by_alias=True)


@router.get(
    "/agents/llm-routing",
    response_model=AgentsLLMRoutingConfig,
    summary="Get agent LLM routing settings",
)
async def get_agents_llm_routing(
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> AgentsLLMRoutingConfig:
    user_id = x_user_id or "default"
    config_path = get_config_path(user_id)
    config = load_config(config_path)
    return config.agents.llm_routing


@router.put(
    "/agents/llm-routing",
    response_model=AgentsLLMRoutingConfig,
    summary="Update agent LLM routing settings",
)
async def put_agents_llm_routing(
    body: AgentsLLMRoutingConfig = Body(...),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> AgentsLLMRoutingConfig:
    user_id = x_user_id or "default"
    config_path = get_config_path(user_id)
    config = load_config(config_path)
    config.agents.llm_routing = body
    save_config(config, config_path)
    return body
