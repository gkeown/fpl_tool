"""Shared in-memory cache for the FPL event/{gw}/live/ endpoint.

Provides a 30-second TTL cache with single-flight semantics: if a cache miss
is in progress, concurrent callers wait for the single in-flight fetch to
complete rather than each starting their own request.

The cached value is the processed result from _fetch_live_gw_with_explain in
live.py: dict[player_id, {stats, explain, provisional_bonus}].  team.py
projects from this richer format down to the flat stats dict it needs.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any

_TTL = 30.0

# gw -> (fetched_at_monotonic, data)
_cache: dict[int, tuple[float, dict[int, dict[str, Any]]]] = {}

# One lock per GW — created on first use
_locks: dict[int, asyncio.Lock] = {}


async def get_live_gw(
    gw: int,
    fetcher: Callable[[int], Coroutine[Any, Any, dict[int, dict[str, Any]]]],
) -> dict[int, dict[str, Any]]:
    """Return cached live GW data, refreshing if older than TTL.

    fetcher is an async callable(gw) -> dict that performs the actual FPL
    HTTP fetch.  Single-flight semantics: concurrent callers during a cache
    miss all wait on the same lock and share the single fetch result.

    Args:
        gw: The gameweek number to fetch data for.
        fetcher: Async callable that fetches and processes the raw FPL data.

    Returns:
        Processed live GW data keyed by player ID.
    """
    now = time.monotonic()
    entry = _cache.get(gw)
    if entry and now - entry[0] < _TTL:
        return entry[1]

    lock = _locks.setdefault(gw, asyncio.Lock())
    async with lock:
        # Re-check after acquiring lock — another caller may have populated it
        entry = _cache.get(gw)
        if entry and time.monotonic() - entry[0] < _TTL:
            return entry[1]
        data = await fetcher(gw)
        # Don't cache empty results — a transient network failure returns {}
        # and would poison the cache for up to TTL seconds.
        if data:
            _cache[gw] = (time.monotonic(), data)
        return data


def invalidate(gw: int) -> None:
    """Force the next call to refetch by removing the cached entry.

    Used by the scheduler and tests to ensure a fresh fetch on the next
    request.

    Args:
        gw: The gameweek number whose cache entry should be cleared.
    """
    _cache.pop(gw, None)


def get_cached_age(gw: int) -> float | None:
    """Return seconds since last fetch, or None if not cached.

    Args:
        gw: The gameweek number to check.

    Returns:
        Age in seconds, or None if the entry does not exist.
    """
    entry = _cache.get(gw)
    return time.monotonic() - entry[0] if entry else None
