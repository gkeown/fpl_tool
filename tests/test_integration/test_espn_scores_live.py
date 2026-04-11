"""Integration tests for ESPN live scores API.

Verifies that the ESPN scoreboard and standings endpoints return
expected response structures for all major leagues.

Run with:
    pytest tests/test_integration/test_espn_scores_live.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integration

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer"

LEAGUES = ["eng.1", "eng.2", "ita.1", "esp.1", "ger.1", "fra.1"]


@pytest.fixture(scope="module")
def pl_scoreboard() -> dict[str, Any]:
    """Fetch PL scoreboard once for all tests."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{ESPN_BASE}/eng.1/scoreboard")
            resp.raise_for_status()
            return resp.json()

    return asyncio.run(_fetch())


async def test_scoreboard_has_events(pl_scoreboard: dict[str, Any]) -> None:
    """Scoreboard response should have an events array."""
    assert "events" in pl_scoreboard
    assert isinstance(pl_scoreboard["events"], list)


async def test_scoreboard_event_structure(
    pl_scoreboard: dict[str, Any],
) -> None:
    """Each event should have required fields."""
    events = pl_scoreboard["events"]
    if not events:
        pytest.skip("No PL fixtures today")

    event = events[0]
    assert "id" in event
    assert "date" in event
    assert "status" in event
    assert "competitions" in event

    comp = event["competitions"][0]
    assert "competitors" in comp
    assert len(comp["competitors"]) == 2

    for c in comp["competitors"]:
        assert "team" in c
        assert "score" in c
        assert "homeAway" in c
        assert c["homeAway"] in ("home", "away")


async def test_scoreboard_status_fields(
    pl_scoreboard: dict[str, Any],
) -> None:
    """Status should have type with name and state."""
    events = pl_scoreboard["events"]
    if not events:
        pytest.skip("No PL fixtures today")

    status = events[0]["status"]
    assert "type" in status
    assert "name" in status["type"]
    assert status["type"]["name"].startswith("STATUS_")


async def test_scoreboard_details_for_scoring(
    pl_scoreboard: dict[str, Any],
) -> None:
    """Finished matches should have details with scoringPlay events."""
    events = pl_scoreboard["events"]
    finished = [
        e
        for e in events
        if e["status"]["type"].get("state") == "post"
    ]
    if not finished:
        pytest.skip("No finished PL fixtures today")

    comp = finished[0]["competitions"][0]
    details = comp.get("details", [])
    goals = [d for d in details if d.get("scoringPlay")]

    # A finished match with a non-0-0 score should have goals
    scores = [
        int(c.get("score", 0))
        for c in comp["competitors"]
    ]
    if sum(scores) > 0:
        assert len(goals) > 0
        goal = goals[0]
        assert "type" in goal
        assert "athletesInvolved" in goal
        assert "clock" in goal


@pytest.mark.parametrize("slug", LEAGUES)
async def test_scoreboard_reachable_for_all_leagues(slug: str) -> None:
    """Each league's scoreboard endpoint should return 200."""

    async def _fetch() -> int:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{ESPN_BASE}/{slug}/scoreboard"
            )
            return resp.status_code

    status = await _fetch()
    assert status == 200


@pytest.mark.parametrize("slug", LEAGUES)
async def test_standings_reachable_for_all_leagues(slug: str) -> None:
    """Each league's standings endpoint should return 200."""

    async def _fetch() -> int:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{ESPN_STANDINGS}/{slug}/standings"
            )
            return resp.status_code

    status = await _fetch()
    assert status == 200


async def test_standings_structure() -> None:
    """PL standings should have entries with stats."""

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{ESPN_STANDINGS}/eng.1/standings"
            )
            resp.raise_for_status()
            return resp.json()

    data = await _fetch()
    children = data.get("children", [])
    assert len(children) > 0

    entries = children[0]["standings"]["entries"]
    assert len(entries) == 20  # PL has 20 teams

    entry = entries[0]
    assert "team" in entry
    assert "stats" in entry
    assert entry["team"].get("displayName")

    stat_names = {s["name"] for s in entry["stats"]}
    assert "points" in stat_names
    assert "wins" in stat_names
    assert "gamesPlayed" in stat_names
    assert "pointsFor" in stat_names
