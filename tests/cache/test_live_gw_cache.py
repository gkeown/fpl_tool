"""Tests for the shared live-GW in-memory cache."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

import fpl.cache.live_gw as cache_mod
from fpl.cache.live_gw import get_live_gw, get_cached_age, invalidate


def _make_data(tag: str = "v1") -> dict[int, dict[str, Any]]:
    return {1: {"stats": {"total_points": 5}, "explain": [], "provisional_bonus": 0, "tag": tag}}


@pytest.fixture(autouse=True)
def clear_cache():
    """Wipe module-level cache and lock state before every test."""
    cache_mod._cache.clear()
    cache_mod._locks.clear()
    yield
    cache_mod._cache.clear()
    cache_mod._locks.clear()


async def test_cache_hit_does_not_call_fetcher_again() -> None:
    """Second call within TTL returns cached data without calling fetcher."""
    fetcher = AsyncMock(return_value=_make_data("v1"))

    first = await get_live_gw(32, fetcher)
    second = await get_live_gw(32, fetcher)

    assert first == second
    assert fetcher.call_count == 1, "fetcher should only be called once on a cache hit"


async def test_ttl_expiry_triggers_refetch() -> None:
    """After TTL expires, the next call fetches fresh data."""
    fetcher = AsyncMock(side_effect=[_make_data("v1"), _make_data("v2")])

    first = await get_live_gw(32, fetcher)
    assert first[1]["tag"] == "v1"

    # Manually backdate the cache entry so it looks stale
    old_time, old_data = cache_mod._cache[32]
    cache_mod._cache[32] = (old_time - cache_mod._TTL - 1.0, old_data)

    second = await get_live_gw(32, fetcher)
    assert second[1]["tag"] == "v2"
    assert fetcher.call_count == 2


async def test_single_flight_concurrent_callers_fetch_once() -> None:
    """10 concurrent callers on a cache miss result in exactly one fetch."""
    fetch_count = 0
    fetch_started = asyncio.Event()
    can_complete = asyncio.Event()

    async def slow_fetcher(gw: int) -> dict[int, dict[str, Any]]:
        nonlocal fetch_count
        fetch_count += 1
        fetch_started.set()
        await can_complete.wait()
        return _make_data("v1")

    # Launch 10 concurrent callers
    tasks = [asyncio.create_task(get_live_gw(32, slow_fetcher)) for _ in range(10)]

    # Wait until at least one fetch has started, then unblock
    await fetch_started.wait()
    can_complete.set()

    results = await asyncio.gather(*tasks)

    assert fetch_count == 1, f"Expected 1 fetch, got {fetch_count}"
    # All callers received the same data
    for result in results:
        assert result[1]["tag"] == "v1"


async def test_invalidate_clears_cache() -> None:
    """invalidate() removes the cached entry so the next call fetches fresh."""
    fetcher = AsyncMock(side_effect=[_make_data("v1"), _make_data("v2")])

    await get_live_gw(32, fetcher)
    assert get_cached_age(32) is not None

    invalidate(32)
    assert get_cached_age(32) is None

    result = await get_live_gw(32, fetcher)
    assert result[1]["tag"] == "v2"
    assert fetcher.call_count == 2


async def test_invalidate_noop_when_not_cached() -> None:
    """invalidate() on an uncached GW does not raise."""
    invalidate(99)  # should not raise


async def test_get_cached_age_returns_none_when_not_cached() -> None:
    """get_cached_age returns None for an uncached GW."""
    assert get_cached_age(99) is None


async def test_get_cached_age_returns_elapsed_seconds() -> None:
    """get_cached_age returns a non-negative float after a successful fetch."""
    fetcher = AsyncMock(return_value=_make_data())
    await get_live_gw(32, fetcher)

    age = get_cached_age(32)
    assert age is not None
    assert 0.0 <= age < 5.0  # Should be nearly instant in tests


async def test_different_gw_keys_are_independent() -> None:
    """Cache entries for different GWs do not interfere with each other."""
    fetcher_32 = AsyncMock(return_value=_make_data("gw32"))
    fetcher_33 = AsyncMock(return_value=_make_data("gw33"))

    result_32 = await get_live_gw(32, fetcher_32)
    result_33 = await get_live_gw(33, fetcher_33)

    assert result_32[1]["tag"] == "gw32"
    assert result_33[1]["tag"] == "gw33"

    invalidate(32)
    assert get_cached_age(32) is None
    assert get_cached_age(33) is not None
