# -*- coding: utf-8 -*-
"""Tool that returns the current local time with timezone info."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


async def get_current_time() -> ToolResponse:
    """Get the current time in Beijing timezone.

    Returns the Beijing time in a human-readable format.
    Useful for time-sensitive tasks such as scheduling cron jobs.

    Returns:
        `ToolResponse`:
            The current Beijing time string,
            e.g. "2026-02-13 19:30:45 CST (UTC+0800)".
    """
    try:
        beijing_tz = ZoneInfo("Asia/Shanghai")
        now = datetime.now(beijing_tz)
        time_str = now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    except Exception:
        time_str = datetime.now(timezone.utc).isoformat() + " (UTC)"

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=time_str,
            ),
        ],
    )
