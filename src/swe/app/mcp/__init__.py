# -*- coding: utf-8 -*-
"""MCP (Model Context Protocol) client management module.

This module provides hot-reloadable MCP client management,
completely independent from other app components.

It also provides drop-in replacements for AgentScope's MCP clients
that solve the CPU leak issue caused by cross-task context manager exits.
"""

import logging
import uuid
from typing import Any

from agentscope.mcp._client_base import MCPClientBase
from agentscope.mcp._mcp_function import MCPToolFunction
from agentscope.tool import ToolResponse
from mcp import ClientSession as _CS
from swe.config.context import get_current_tenant_id

from .manager import MCPClientManager
from .stateful_client import HttpStatefulClient, StdIOStatefulClient
from .watcher import MCPConfigWatcher

logger = logging.getLogger(__name__)

# Monkey-patch MCPToolFunction.__call__ to auto-inject _meta with progressToken.
# progressToken is generated from X-Tenant-Id (from request context) + UUID,
# and forwarded as meta to the MCP SDK's ClientSession.call_tool.
#
# NOTE: We bypass the original __call__ entirely because its signature
# (`**kwargs`) would swallow `meta` into the arguments dict instead of
# passing it as a keyword-only param to `session.call_tool(meta=...)`.
_original_mcp_call = MCPToolFunction.__call__


async def _patched_mcp_call(self: MCPToolFunction, **kwargs: Any) -> Any:
    # Remove any caller-passed _meta; always generate a fresh progressToken.
    kwargs.pop("_meta", None)

    tenant_id = get_current_tenant_id() or "default"
    progress_token = f"{tenant_id}@{uuid.uuid4()}"
    meta = {"progressToken": progress_token}

    if self.client_gen:
        async with self.client_gen() as cli:
            read_stream, write_stream = cli[0], cli[1]
            async with _CS(read_stream, write_stream) as session:
                await session.initialize()
                res = await session.call_tool(
                    self.name,
                    arguments=kwargs,
                    read_timeout_seconds=self.timeout,
                    meta=meta,
                )
    else:
        res = await self.session.call_tool(
            self.name,
            arguments=kwargs,
            read_timeout_seconds=self.timeout,
            meta=meta,
        )

    if self.wrap_tool_result:
        # pylint: disable=protected-access
        as_content = MCPClientBase._convert_mcp_content_to_as_blocks(
            res.content,
        )
        return ToolResponse(content=as_content, metadata=res.meta)

    return res


MCPToolFunction.__call__ = _patched_mcp_call  # type: ignore[method-assign]

__all__ = [
    "HttpStatefulClient",
    "MCPClientManager",
    "MCPConfigWatcher",
    "StdIOStatefulClient",
]
