# -*- coding: utf-8 -*-
# pylint: disable=protected-access
from __future__ import annotations

from typing import Any

import pytest

from swe.config.config import MCPClientConfig


@pytest.mark.asyncio
async def test_create_streamable_http_mcp_client_uses_explicit_httpx_timeouts(
    monkeypatch,
) -> None:
    from swe.app.runner import runner as runner_module

    captured: dict[str, Any] = {}

    class _FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["http_client_kwargs"] = kwargs

    class _FakeHttpStatefulClient:
        def __init__(self, **kwargs):
            captured["stateful_client_kwargs"] = kwargs

    def _fake_streamable_http_client(*, url, http_client):
        captured["streamable_http"] = {
            "url": url,
            "http_client": http_client,
        }
        return "streamable-http-context"

    monkeypatch.setattr(
        runner_module.httpx,
        "AsyncClient",
        _FakeAsyncClient,
    )
    monkeypatch.setattr(
        runner_module,
        "HttpStatefulClient",
        _FakeHttpStatefulClient,
    )
    monkeypatch.setattr(
        runner_module,
        "streamable_http_client",
        _fake_streamable_http_client,
    )

    client = await runner_module._create_mcp_client_with_headers(
        MCPClientConfig(
            name="demo",
            transport="streamable_http",
            url="https://mcp.example.test/stream",
            headers={"X-Static": "static"},
        ),
        passthrough_headers={"Authorization": "Bearer test-token"},
    )

    timeout = captured["http_client_kwargs"]["timeout"]
    assert timeout.connect == runner_module._MCP_HTTP_TIMEOUT_SECONDS
    assert timeout.read == runner_module._MCP_HTTP_SSE_READ_TIMEOUT_SECONDS
    assert timeout.write == runner_module._MCP_HTTP_TIMEOUT_SECONDS
    assert timeout.pool == runner_module._MCP_HTTP_TIMEOUT_SECONDS
    assert captured["http_client_kwargs"]["headers"] == {
        "X-Static": "static",
        "Authorization": "Bearer test-token",
    }
    assert captured["stateful_client_kwargs"] == {
        "name": "demo",
        "transport": "streamable_http",
        "url": "https://mcp.example.test/stream",
        "headers": None,
    }
    assert client.client == "streamable-http-context"
    assert (
        getattr(client, "_swe_rebuild_info")["_http_client"]
        is captured["streamable_http"]["http_client"]
    )


@pytest.mark.asyncio
async def test_create_sse_mcp_client_passes_explicit_read_timeout(
    monkeypatch,
) -> None:
    from swe.app.runner import runner as runner_module

    captured: dict[str, Any] = {}

    class _FakeHttpStatefulClient:
        def __init__(self, **kwargs):
            captured["stateful_client_kwargs"] = kwargs

    def _fake_sse_client(**kwargs):
        captured["sse_client_kwargs"] = kwargs
        return "sse-context"

    def _unexpected_async_client(**kwargs):
        raise AssertionError("SSE transport should not construct httpx client")

    monkeypatch.setattr(
        runner_module,
        "HttpStatefulClient",
        _FakeHttpStatefulClient,
    )
    monkeypatch.setattr(
        runner_module,
        "sse_client",
        _fake_sse_client,
    )
    monkeypatch.setattr(
        runner_module.httpx,
        "AsyncClient",
        _unexpected_async_client,
    )

    client = await runner_module._create_mcp_client_with_headers(
        MCPClientConfig(
            name="demo",
            transport="sse",
            url="https://mcp.example.test/sse",
            headers={"X-Static": "static"},
        ),
        passthrough_headers={"Authorization": "Bearer test-token"},
    )

    assert captured["sse_client_kwargs"] == {
        "url": "https://mcp.example.test/sse",
        "headers": {
            "X-Static": "static",
            "Authorization": "Bearer test-token",
        },
        "timeout": runner_module._MCP_HTTP_TIMEOUT_SECONDS,
        "sse_read_timeout": runner_module._MCP_HTTP_SSE_READ_TIMEOUT_SECONDS,
    }
    assert client.client == "sse-context"
    assert getattr(client, "_swe_rebuild_info")["_http_client"] is None
