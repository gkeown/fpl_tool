"""Integration tests for ESPN player search and stats API.

Verifies that ESPN search and athlete detail endpoints return
expected response structures.

Run with:
    pytest tests/test_integration/test_espn_stats_live.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integration

ESPN_SEARCH = "https://site.api.espn.com/apis/common/v3/search"
ESPN_ATHLETE = (
    "https://site.api.espn.com/apis/common/v3/sports/soccer"
)


async def test_search_returns_players() -> None:
    """Searching for 'Saka' should return player results."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                ESPN_SEARCH,
                params={
                    "query": "Saka",
                    "type": "player",
                    "sport": "soccer",
                    "limit": "10",
                },
            )
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()
    items = data.get("items", [])
    assert len(items) > 0

    # Find Bukayo Saka
    saka = next(
        (i for i in items if "Bukayo" in i.get("displayName", "")),
        None,
    )
    assert saka is not None
    assert saka.get("type") == "player"
    assert "id" in saka
    assert saka.get("league") == "eng.1"


async def test_search_result_structure() -> None:
    """Each search result should have required fields."""

    async def _fetch() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                ESPN_SEARCH,
                params={
                    "query": "Haaland",
                    "type": "player",
                    "sport": "soccer",
                    "limit": "5",
                },
            )
            resp.raise_for_status()
            return resp.json().get("items", [])

    items = await _fetch()
    assert len(items) > 0

    player = items[0]
    assert "id" in player
    assert "displayName" in player
    assert "league" in player


async def test_athlete_detail_has_stats() -> None:
    """Fetching a known player should return stats summary."""

    async def _fetch() -> dict[str, Any]:
        # First find Saka's ESPN ID
        async with httpx.AsyncClient(timeout=15) as client:
            search_resp = await client.get(
                ESPN_SEARCH,
                params={
                    "query": "Bukayo Saka",
                    "type": "player",
                    "sport": "soccer",
                    "limit": "5",
                },
            )
            search_resp.raise_for_status()
            items = search_resp.json().get("items", [])
            saka = next(
                (
                    i
                    for i in items
                    if "Bukayo" in i.get("displayName", "")
                ),
                None,
            )
            assert saka is not None
            pid = saka["id"]

            # Fetch athlete detail
            resp = await client.get(
                f"{ESPN_ATHLETE}/eng.1/athletes/{pid}"
            )
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()
    athlete = data.get("athlete", {})
    assert athlete.get("displayName")

    summary = athlete.get("statsSummary", {})
    assert "statistics" in summary
    stats = summary["statistics"]
    assert len(stats) > 0

    stat_names = {s["name"] for s in stats}
    assert "totalGoals" in stat_names or "starts-subIns" in stat_names


async def test_athlete_detail_has_profile_info() -> None:
    """Athlete detail should include position, team, nationality."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            # Use a known ESPN ID for Haaland
            search_resp = await client.get(
                ESPN_SEARCH,
                params={
                    "query": "Erling Haaland",
                    "type": "player",
                    "sport": "soccer",
                    "limit": "3",
                },
            )
            search_resp.raise_for_status()
            items = search_resp.json().get("items", [])
            haaland = next(
                (
                    i
                    for i in items
                    if "Haaland" in i.get("displayName", "")
                ),
                None,
            )
            assert haaland is not None

            resp = await client.get(
                f"{ESPN_ATHLETE}/eng.1/athletes/{haaland['id']}"
            )
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()
    athlete = data.get("athlete", {})
    assert athlete.get("position", {}).get("displayName")
    assert athlete.get("team", {}).get("displayName")


async def test_search_across_leagues() -> None:
    """Search should find players from non-PL leagues."""

    async def _fetch() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                ESPN_SEARCH,
                params={
                    "query": "Mbappe",
                    "type": "player",
                    "sport": "soccer",
                    "limit": "10",
                },
            )
            resp.raise_for_status()
            return resp.json().get("items", [])

    items = await _fetch()
    mbappe = next(
        (
            i
            for i in items
            if "Mbappé" in i.get("displayName", "")
            or "Mbappe" in i.get("displayName", "")
        ),
        None,
    )
    assert mbappe is not None
    # Mbappe should be in La Liga (Real Madrid)
    assert mbappe.get("league") in ("esp.1", "fra.1")
