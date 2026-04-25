# -*- coding: utf-8 -*-
"""Agent-scoped LLM request rate limiter.

How it works:
1. QPM sliding window: tracks request timestamps in a 60-second window.
   Before each call, if the window is full, the caller waits until the
   oldest timestamp slides out — proactively preventing 429s.
2. asyncio.Semaphore caps the number of concurrent in-flight LLM calls.
3. A scoped pause timestamp: when a 429 is received every subsequent acquire()
   in the same tenant-local agent scope waits until the pause expires,
   eliminating thundering-herd retries inside that scope.
4. Per-waiter jitter: each caller adds a small random offset on top of
   the remaining pause time, so they spread out when waking up.

acquire() execution order:
    wait for 429 cooldown → wait for QPM slot → wait for semaphore slot
"""

from __future__ import annotations

import asyncio
import collections
import logging
import random
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RateLimiterScopeKey:
    """Tenant-local agent identity for process-local LLM limiting."""

    tenant_id: str
    agent_id: str


@dataclass(frozen=True, slots=True)
class _RateLimiterConfigFingerprint:
    max_concurrent: int
    max_qpm: int
    default_pause_seconds: float
    jitter_range: float


@dataclass(slots=True)
class _RateLimiterRegistryEntry:
    limiter: "LLMRateLimiter"
    config: _RateLimiterConfigFingerprint
    last_used_at: float


class LLMRateLimiter:
    """Scoped LLM request rate limiter.

    Coroutine-safe: all mutable state is protected by asyncio primitives and
    is intended for use within a single event loop.

    Args:
        max_concurrent: Maximum concurrent in-flight LLM calls (semaphore).
        max_qpm: Maximum queries per minute (sliding window). 0 = disabled.
        default_pause_seconds: Scope-local pause duration on a 429 response.
        jitter_range: Random jitter (seconds) added on top of the pause.
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        max_qpm: int = 0,
        default_pause_seconds: float = 5.0,
        jitter_range: float = 1.0,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._pause_until: float = 0.0
        self._lock = asyncio.Lock()
        self._default_pause = default_pause_seconds
        self._jitter_range = jitter_range

        # QPM sliding window — stores monotonic timestamps of dispatched calls.
        self._max_qpm = max_qpm
        self._request_times: collections.deque[float] = collections.deque()
        self._qpm_lock = asyncio.Lock()

        # Own counter instead of reading semaphore._value (private API).
        self._in_flight: int = 0

        self._total_acquired: int = 0
        self._total_paused: int = 0
        self._total_qpm_waited: int = 0
        self._total_rate_limited: int = 0

    async def acquire(self) -> None:
        """Acquire an execution permit.

        Execution order:
        1. If a scoped 429 pause is active, wait until it expires (plus
           per-waiter jitter to avoid a new burst on wake-up).  The while-loop
           re-checks after each sleep because a new 429 may have extended the
           pause while we were waiting.
        2. If RPM limiting is enabled, wait until a slot opens in the 60-second
           sliding window, then record this call's timestamp.
        3. Acquire the semaphore slot (concurrency cap).

        The hard upper-bound timeout is enforced by asyncio.wait_for() at
        every call site in RetryChatModel.
        """
        # Step 1 — 429 cooldown.
        while True:
            now = time.monotonic()
            remaining = self._pause_until - now
            if remaining <= 0:
                break
            jitter = random.uniform(0, self._jitter_range)
            wait_time = remaining + jitter
            self._total_paused += 1
            logger.debug(
                "LLM rate limiter: 429 cooldown %.1fs "
                "(remaining=%.1fs + jitter=%.1fs)",
                wait_time,
                remaining,
                jitter,
            )
            await asyncio.sleep(wait_time)

        # Step 2 — QPM sliding window.
        if self._max_qpm > 0:
            await self._acquire_qpm_slot()

        # Step 3 — concurrency semaphore.
        await self._semaphore.acquire()
        self._in_flight += 1
        self._total_acquired += 1

    async def _acquire_qpm_slot(self) -> None:
        """Wait until the 60-second sliding window has room, then record the
        current timestamp to claim the slot.

        Under the qpm_lock we atomically prune expired entries, check capacity,
        and append the new timestamp.  If the window is full we compute the
        minimum wait time, release the lock, sleep, then retry.
        """
        while True:
            async with self._qpm_lock:
                now = time.monotonic()
                cutoff = now - 60.0
                # Evict timestamps that have slid out of the window.
                while self._request_times and self._request_times[0] < cutoff:
                    self._request_times.popleft()

                if len(self._request_times) < self._max_qpm:
                    # Slot available — record and return.
                    self._request_times.append(now)
                    return

                # Window full — compute how long until the oldest entry
                # expires.
                oldest = self._request_times[0]
                wait_time = oldest + 60.0 - now + 0.05  # 50 ms margin

            self._total_qpm_waited += 1
            logger.debug(
                "LLM QPM limit (%d/min) reached, waiting %.1fs for slot",
                self._max_qpm,
                wait_time,
            )
            await asyncio.sleep(wait_time)

    def release(self) -> None:
        """Release the semaphore slot.
        Must be paired with a prior acquire()."""
        self._in_flight -= 1
        self._semaphore.release()

    async def report_rate_limit(
        self,
        retry_after: float | None = None,
    ) -> None:
        """Record a 429 response and set the scoped pause timestamp.

        Args:
            retry_after: Seconds from the API's Retry-After header.
                         Falls back to the configured default when None.
        """
        pause = retry_after if retry_after is not None else self._default_pause
        async with self._lock:
            new_until = time.monotonic() + pause
            if new_until > self._pause_until:
                self._pause_until = new_until
                self._total_rate_limited += 1
                logger.warning(
                    "LLM rate limiter: scoped pause set for %.1fs "
                    "(total_rate_limited=%d)",
                    pause,
                    self._total_rate_limited,
                )

    def stats(self) -> dict:
        """Return a snapshot of runtime statistics for logging or
        monitoring."""
        now = time.monotonic()
        cutoff = now - 60.0
        requests_last_60s = sum(1 for t in self._request_times if t >= cutoff)
        return {
            "max_concurrent": self._max_concurrent,
            "current_in_flight": self._in_flight,
            "current_available": max(
                0,
                self._max_concurrent - self._in_flight,
            ),
            "max_qpm": self._max_qpm,
            "requests_last_60s": requests_last_60s,
            "is_paused": now < self._pause_until,
            "pause_remaining_s": max(0.0, self._pause_until - now),
            "total_acquired": self._total_acquired,
            "total_paused": self._total_paused,
            "total_qpm_waited": self._total_qpm_waited,
            "total_rate_limited": self._total_rate_limited,
        }


# Process-local scoped registry.
_limiter_registry: dict[
    RateLimiterScopeKey,
    _RateLimiterRegistryEntry,
] = {}
_registry_lock: asyncio.Lock | None = None


def _get_init_lock() -> asyncio.Lock:
    global _registry_lock
    if _registry_lock is None:
        _registry_lock = asyncio.Lock()
    return _registry_lock


def _normalize_scope_key(
    scope_key: RateLimiterScopeKey | None,
    tenant_id: str | None = None,
    agent_id: str | None = None,
) -> RateLimiterScopeKey:
    if scope_key is not None:
        return RateLimiterScopeKey(
            tenant_id=scope_key.tenant_id or "default",
            agent_id=scope_key.agent_id or "default",
        )

    resolved_tenant_id = tenant_id
    if not resolved_tenant_id:
        try:
            from ..config.context import get_current_effective_tenant_id

            resolved_tenant_id = get_current_effective_tenant_id()
        except Exception:
            resolved_tenant_id = None

    resolved_agent_id = agent_id
    if not resolved_agent_id:
        try:
            from ..app.agent_context import get_current_agent_id

            resolved_agent_id = get_current_agent_id(resolved_tenant_id)
        except Exception:
            resolved_agent_id = None

    return RateLimiterScopeKey(
        tenant_id=resolved_tenant_id or "default",
        agent_id=resolved_agent_id or "default",
    )


def _normalize_config_fingerprint(
    max_concurrent: int | None,
    max_qpm: int | None,
    default_pause_seconds: float | None,
    jitter_range: float | None,
) -> _RateLimiterConfigFingerprint:
    from ..constant import (
        LLM_MAX_CONCURRENT,
        LLM_MAX_QPM,
        LLM_RATE_LIMIT_JITTER,
        LLM_RATE_LIMIT_PAUSE,
    )

    return _RateLimiterConfigFingerprint(
        max_concurrent=max(
            1,
            (
                max_concurrent
                if max_concurrent is not None
                else LLM_MAX_CONCURRENT
            ),
        ),
        max_qpm=max(0, max_qpm if max_qpm is not None else LLM_MAX_QPM),
        default_pause_seconds=max(
            1.0,
            (
                default_pause_seconds
                if default_pause_seconds is not None
                else LLM_RATE_LIMIT_PAUSE
            ),
        ),
        jitter_range=max(
            0.0,
            (
                jitter_range
                if jitter_range is not None
                else LLM_RATE_LIMIT_JITTER
            ),
        ),
    )


async def get_rate_limiter(
    scope_key: RateLimiterScopeKey | None = None,
    tenant_id: str | None = None,
    agent_id: str | None = None,
    max_concurrent: int | None = None,
    max_qpm: int | None = None,
    default_pause_seconds: float | None = None,
    jitter_range: float | None = None,
) -> LLMRateLimiter:
    """Return the scoped LLMRateLimiter, lazily initialised.

    Limiters are process-local and keyed by effective tenant plus resolved
    agent. If a later lookup for the same scope uses changed limiter settings,
    the registry entry is replaced for subsequent calls while any in-flight
    calls on the old limiter drain naturally.

    Args:
        scope_key: Explicit tenant-local agent limiter scope.
        tenant_id: Effective tenant ID when no scope key is provided.
        agent_id: Resolved agent ID when no scope key is provided.
        max_concurrent: Cap on concurrent in-flight LLM calls.
        max_qpm: Maximum queries per minute (sliding window). 0 = disabled.
        default_pause_seconds: Pause duration (s) applied on a 429 response.
        jitter_range: Random jitter (s) added on top of the pause.
    """
    resolved_scope = _normalize_scope_key(
        scope_key,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )
    config = _normalize_config_fingerprint(
        max_concurrent=max_concurrent,
        max_qpm=max_qpm,
        default_pause_seconds=default_pause_seconds,
        jitter_range=jitter_range,
    )
    now = time.monotonic()

    entry = _limiter_registry.get(resolved_scope)
    if entry is not None and entry.config == config:
        entry.last_used_at = now
        return entry.limiter

    async with _get_init_lock():
        entry = _limiter_registry.get(resolved_scope)
        if entry is not None and entry.config == config:
            entry.last_used_at = time.monotonic()
            return entry.limiter

        limiter = LLMRateLimiter(
            max_concurrent=config.max_concurrent,
            max_qpm=config.max_qpm,
            default_pause_seconds=config.default_pause_seconds,
            jitter_range=config.jitter_range,
        )
        _limiter_registry[resolved_scope] = _RateLimiterRegistryEntry(
            limiter=limiter,
            config=config,
            last_used_at=time.monotonic(),
        )
        if entry is None:
            logger.info(
                "LLM rate limiter initialized: scope=%s/%s, "
                "max_concurrent=%d, max_qpm=%d, default_pause=%.1fs, "
                "jitter=%.1fs",
                resolved_scope.tenant_id,
                resolved_scope.agent_id,
                config.max_concurrent,
                config.max_qpm,
                config.default_pause_seconds,
                config.jitter_range,
            )
        else:
            logger.info(
                "LLM rate limiter replaced: scope=%s/%s, "
                "max_concurrent=%d, max_qpm=%d, default_pause=%.1fs, "
                "jitter=%.1fs",
                resolved_scope.tenant_id,
                resolved_scope.agent_id,
                config.max_concurrent,
                config.max_qpm,
                config.default_pause_seconds,
                config.jitter_range,
            )
    return limiter


def cleanup_idle_rate_limiters(max_idle_seconds: float) -> int:
    """Remove idle scoped limiter entries with no in-flight calls.

    This helper is intentionally explicit so service lifecycle code can choose
    when to run cleanup. Entries with active calls are never removed.
    """
    now = time.monotonic()
    removed = 0
    for scope, entry in list(_limiter_registry.items()):
        if entry.limiter.stats()["current_in_flight"] > 0:
            continue
        if now - entry.last_used_at < max_idle_seconds:
            continue
        del _limiter_registry[scope]
        removed += 1
        logger.info(
            "LLM rate limiter cleaned up: scope=%s/%s",
            scope.tenant_id,
            scope.agent_id,
        )
    return removed


def reset_rate_limiter() -> None:
    """Reset all scoped limiter entries (for testing or service restart)."""
    _limiter_registry.clear()
