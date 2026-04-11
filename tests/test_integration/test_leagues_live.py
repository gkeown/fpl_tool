"""Integration tests for FPL league and entry endpoints.

Verifies that the FPL API returns expected structures for
league standings, entry data, picks, transfers, and history.

Run with:
    pytest tests/test_integration/test_leagues_live.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from fpl.config import get_settings

pytestmark = pytest.mark.integration

# Use a known public league and entry for testing
TEST_LEAGUE_ID = 314  # Overall league (large, always exists)
TEST_ENTRY_ID = 2931407  # A public FPL team


@pytest.fixture(scope="module")
def settings():
    return get_settings()


async def test_league_standings_structure(settings: Any) -> None:
    """Classic league standings should return league info + results."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            url = f"{settings.fpl_base_url}/leagues-classic/{TEST_LEAGUE_ID}/standings/"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()

    assert "league" in data
    assert "standings" in data
    assert data["league"].get("id") == TEST_LEAGUE_ID
    assert data["league"].get("name")

    results = data["standings"].get("results", [])
    assert len(results) > 0

    entry = results[0]
    assert "entry" in entry
    assert "player_name" in entry
    assert "entry_name" in entry
    assert "rank" in entry
    assert "total" in entry
    assert isinstance(entry["total"], int)


async def test_entry_data_structure(settings: Any) -> None:
    """Public entry endpoint should return manager info."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            url = f"{settings.fpl_base_url}/entry/{TEST_ENTRY_ID}/"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()

    assert data.get("id") == TEST_ENTRY_ID
    assert "player_first_name" in data
    assert "player_last_name" in data
    assert "summary_overall_points" in data
    assert "summary_overall_rank" in data
    assert "summary_event_points" in data
    assert "current_event" in data
    assert isinstance(data["current_event"], int)
    assert "last_deadline_bank" in data
    assert "last_deadline_value" in data


async def test_entry_picks_structure(settings: Any) -> None:
    """Entry picks should return 15 players with captain info."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            # Get current event
            entry_url = f"{settings.fpl_base_url}/entry/{TEST_ENTRY_ID}/"
            resp = await client.get(entry_url)
            resp.raise_for_status()
            gw = resp.json().get("current_event", 1)

            picks_url = f"{settings.fpl_base_url}/entry/{TEST_ENTRY_ID}/event/{gw}/picks/"
            resp = await client.get(picks_url)
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()

    assert "picks" in data
    assert "entry_history" in data
    assert "active_chip" in data

    picks = data["picks"]
    assert len(picks) == 15

    pick = picks[0]
    assert "element" in pick
    assert "position" in pick
    assert "is_captain" in pick
    assert "is_vice_captain" in pick
    assert "multiplier" in pick

    # Exactly one captain
    captains = [p for p in picks if p["is_captain"]]
    assert len(captains) == 1

    history = data["entry_history"]
    assert "bank" in history
    assert "points" in history


async def test_entry_transfers_structure(settings: Any) -> None:
    """Entry transfers should return array of transfer objects."""

    async def _fetch() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            url = f"{settings.fpl_base_url}/entry/{TEST_ENTRY_ID}/transfers/"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()

    assert isinstance(data, list)
    assert len(data) > 0

    transfer = data[0]
    assert "element_in" in transfer
    assert "element_in_cost" in transfer
    assert "element_out" in transfer
    assert "element_out_cost" in transfer
    assert "event" in transfer
    assert "time" in transfer
    assert isinstance(transfer["element_in"], int)
    assert isinstance(transfer["event"], int)


async def test_entry_history_has_chips(settings: Any) -> None:
    """Entry history should include chips array."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            url = f"{settings.fpl_base_url}/entry/{TEST_ENTRY_ID}/history/"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()

    assert "chips" in data
    assert isinstance(data["chips"], list)
    assert "current" in data
    assert isinstance(data["current"], list)

    # Chips should have name and event
    if data["chips"]:
        chip = data["chips"][0]
        assert "name" in chip
        assert "event" in chip
        assert chip["name"] in (
            "wildcard", "freehit", "bboost", "3xc", "manager",
        )


async def test_live_gw_endpoint_structure(settings: Any) -> None:
    """The /event/{gw}/live/ endpoint should return player live stats."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            # Get current GW from bootstrap
            bootstrap_url = f"{settings.fpl_base_url}/bootstrap-static/"
            resp = await client.get(bootstrap_url)
            resp.raise_for_status()
            events = resp.json().get("events", [])
            current_gw = next(
                (e["id"] for e in events if e.get("is_current")),
                1,
            )

            live_url = f"{settings.fpl_base_url}/event/{current_gw}/live/"
            resp = await client.get(live_url)
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()

    assert "elements" in data
    elements = data["elements"]
    assert len(elements) > 0

    el = elements[0]
    assert "id" in el
    assert "stats" in el

    stats = el["stats"]
    assert "total_points" in stats
    assert "bonus" in stats
    assert "bps" in stats
    assert "minutes" in stats
    assert "defensive_contribution" in stats
