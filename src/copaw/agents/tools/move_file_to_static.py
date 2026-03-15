# -*- coding: utf-8 -*-
"""Move file to static folder tool."""

import json
import os
import shutil

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from copaw.constant import get_request_working_dir, get_request_user_id


def _tool_error(msg: str) -> ToolResponse:
    """Return error response."""
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(
                    {"ok": False, "error": msg},
                    ensure_ascii=False,
                    indent=2,
                ),
            ),
        ],
    )


def _tool_ok(path: str, message: str) -> ToolResponse:
    """Return success response."""
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(
                    {
                        "ok": True,
                        "path": path,
                        "message": message,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            ),
        ],
    )


async def move_file_to_static(file_path: str) -> ToolResponse:
    """Move a file to the static folder under the working directory.

    This tool moves the specified file to the `static` subdirectory of the
    current working directory. If the `static` folder does not exist, it
    will be created automatically.

    Args:
        file_path (`str`):
            The absolute or relative path of the file to move.

    Returns:
        `ToolResponse`:
            JSON with "ok", "path" (final file path in static folder),
            and "message" or "error".
    """
    # Validate input
    if not file_path or not file_path.strip():
        return _tool_error("file_path is required")

    file_path = file_path.strip()

    # Check if source file exists
    if not os.path.exists(file_path):
        return _tool_error(f"File not found: {file_path}")

    if not os.path.isfile(file_path):
        return _tool_error(f"Path is not a file: {file_path}")

    # Get working directory and create static folder if needed
    working_dir = get_request_working_dir()
    static_dir = working_dir / "static"

    try:
        static_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return _tool_error(f"Failed to create static directory: {e!s}")

    # Build destination path
    file_name = os.path.basename(file_path)
    dest_path = static_dir / file_name

    # If destination already exists, add a suffix to avoid collision
    if dest_path.exists():
        base, ext = os.path.splitext(file_name)
        counter = 1
        while dest_path.exists():
            dest_path = static_dir / f"{base}_{counter}{ext}"
            counter += 1

    # Move the file
    try:
        shutil.move(file_path, dest_path)
    except Exception as e:
        return _tool_error(f"Failed to move file: {e!s}")

    # Get user_id for response
    user_id = get_request_user_id() or "default"
    file_name = os.path.basename(file_path)

    return _tool_ok(
        f"cmb-swe+{user_id}+{file_name}",
        f"File moved to {dest_path}",
    )
