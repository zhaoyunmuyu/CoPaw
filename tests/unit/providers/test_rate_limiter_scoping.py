# -*- coding: utf-8 -*-
"""Tests for tenant-local agent scoped LLM rate limiter state."""

import asyncio

import pytest
from agentscope.model import ChatModelBase
from agentscope.model._model_response import ChatResponse

from swe.providers.rate_limiter import (
    RateLimiterScopeKey,
    cleanup_idle_rate_limiters,
    get_rate_limiter,
    reset_rate_limiter,
)
from swe.providers.retry_chat_model import RateLimitConfig, RetryChatModel


class _StaticChatModel(ChatModelBase):
    def __init__(self):
        super().__init__(model_name="test-model", stream=False)

    async def __call__(self, *args, **kwargs):
        return ChatResponse(content=[])


class _BlockingStreamChatModel(ChatModelBase):
    def __init__(self, release_second_chunk: asyncio.Event):
        super().__init__(model_name="test-model", stream=True)
        self._release_second_chunk = release_second_chunk

    async def __call__(self, *args, **kwargs):
        async def _stream():
            yield ChatResponse(content=[])
            await self._release_second_chunk.wait()
            yield ChatResponse(content=[])

        return _stream()


@pytest.fixture(autouse=True)
def _reset_limiter_registry():
    reset_rate_limiter()
    yield
    reset_rate_limiter()


@pytest.mark.asyncio
async def test_same_tenant_same_agent_shares_limiter_state():
    scope = RateLimiterScopeKey("tenant-a", "agent-x")

    first = await get_rate_limiter(
        scope_key=scope,
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )
    second = await get_rate_limiter(
        scope_key=scope,
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )

    assert second is first


@pytest.mark.asyncio
async def test_same_tenant_different_agents_do_not_share_limiter_state():
    agent_x = await get_rate_limiter(
        scope_key=RateLimiterScopeKey("tenant-a", "agent-x"),
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )
    agent_y = await get_rate_limiter(
        scope_key=RateLimiterScopeKey("tenant-a", "agent-y"),
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )

    assert agent_y is not agent_x


@pytest.mark.asyncio
async def test_different_tenants_same_agent_do_not_share_limiter_state():
    tenant_a = await get_rate_limiter(
        scope_key=RateLimiterScopeKey("tenant-a", "default"),
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )
    tenant_b = await get_rate_limiter(
        scope_key=RateLimiterScopeKey("tenant-b", "default"),
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )

    assert tenant_b is not tenant_a


@pytest.mark.asyncio
async def test_rate_limit_cooldown_stays_inside_agent_scope():
    agent_x = await get_rate_limiter(
        scope_key=RateLimiterScopeKey("tenant-a", "agent-x"),
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )
    agent_y = await get_rate_limiter(
        scope_key=RateLimiterScopeKey("tenant-a", "agent-y"),
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )

    await agent_x.report_rate_limit(retry_after=60.0)

    assert agent_x.stats()["is_paused"] is True
    assert agent_y.stats()["is_paused"] is False


@pytest.mark.asyncio
async def test_config_change_replaces_later_limiter_without_interrupting_old():
    scope = RateLimiterScopeKey("tenant-a", "agent-x")
    old_limiter = await get_rate_limiter(
        scope_key=scope,
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )
    await old_limiter.acquire()

    new_limiter = await get_rate_limiter(
        scope_key=scope,
        max_concurrent=3,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )

    assert new_limiter is not old_limiter
    assert old_limiter.stats()["current_in_flight"] == 1
    assert new_limiter.stats()["max_concurrent"] == 3
    assert new_limiter.stats()["current_in_flight"] == 0

    old_limiter.release()


@pytest.mark.asyncio
async def test_cleanup_removes_only_idle_entries():
    idle_scope = RateLimiterScopeKey("tenant-a", "idle-agent")
    busy_scope = RateLimiterScopeKey("tenant-a", "busy-agent")

    await get_rate_limiter(scope_key=idle_scope, max_concurrent=1)
    busy_limiter = await get_rate_limiter(
        scope_key=busy_scope,
        max_concurrent=1,
    )
    await busy_limiter.acquire()

    removed = cleanup_idle_rate_limiters(max_idle_seconds=0)
    same_busy_limiter = await get_rate_limiter(
        scope_key=busy_scope,
        max_concurrent=1,
    )
    new_idle_limiter = await get_rate_limiter(
        scope_key=idle_scope,
        max_concurrent=1,
    )

    assert removed == 1
    assert same_busy_limiter is busy_limiter
    assert new_idle_limiter is not busy_limiter

    busy_limiter.release()


@pytest.mark.asyncio
async def test_retry_chat_model_without_explicit_scope_uses_current_agent(
    monkeypatch,
):
    monkeypatch.setattr(
        "swe.config.context.get_current_effective_tenant_id",
        lambda: "tenant-a",
    )
    monkeypatch.setattr(
        "swe.app.agent_context.get_current_agent_id",
        lambda tenant_id=None: "agent-x",
    )
    model = RetryChatModel(
        _StaticChatModel(),
        rate_limit_config=RateLimitConfig(
            max_concurrent=1,
            max_qpm=0,
            pause_seconds=10.0,
            jitter_range=0.0,
        ),
    )

    await model()

    limiter = await get_rate_limiter(
        tenant_id="tenant-a",
        agent_id="agent-x",
        max_concurrent=1,
        max_qpm=0,
        default_pause_seconds=10.0,
        jitter_range=0.0,
    )

    assert limiter.stats()["total_acquired"] == 1


@pytest.mark.asyncio
async def test_cleanup_keeps_limiter_with_active_stream_after_slot_release():
    release_second_chunk = asyncio.Event()
    scope = RateLimiterScopeKey("tenant-a", "stream-agent")
    model = RetryChatModel(
        _BlockingStreamChatModel(release_second_chunk),
        tenant_id=scope.tenant_id,
        agent_id=scope.agent_id,
        rate_limit_config=RateLimitConfig(
            max_concurrent=1,
            max_qpm=0,
            pause_seconds=10.0,
            jitter_range=0.0,
        ),
    )
    stream = await model()

    try:
        await stream.__anext__()
        limiter = await get_rate_limiter(
            scope_key=scope,
            max_concurrent=1,
            max_qpm=0,
            default_pause_seconds=10.0,
            jitter_range=0.0,
        )

        removed = cleanup_idle_rate_limiters(max_idle_seconds=0)
        same_limiter = await get_rate_limiter(
            scope_key=scope,
            max_concurrent=1,
            max_qpm=0,
            default_pause_seconds=10.0,
            jitter_range=0.0,
        )

        assert limiter.stats()["current_in_flight"] == 0
        assert removed == 0
        assert same_limiter is limiter
    finally:
        release_second_chunk.set()
        await stream.aclose()
