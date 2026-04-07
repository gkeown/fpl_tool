"""Integration tests that hit the live Understat API.

Run with:
    pytest tests/test_integration/test_understat_live.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from fpl.config import get_settings
from fpl.ingest.understat import UNDERSTAT_TEAMS, fetch_team_data

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def arsenal_data() -> dict[str, Any]:
    """Fetch Arsenal data once for all tests in this module."""
    settings = get_settings()

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={
                "User-Agent": settings.user_agent,
                "X-Requested-With": "XMLHttpRequest",
            },
        ) as client:
            return await fetch_team_data(client, "Arsenal", "2025")

    result: dict[str, Any] = asyncio.run(_fetch())
    return result


class TestUnderstatResponseShape:
    """Verify the live Understat API returns expected structure."""

    def test_response_has_required_top_level_keys(
        self, arsenal_data: dict[str, Any]
    ) -> None:
        required = {"dates", "players", "statistics"}
        assert required.issubset(
            arsenal_data.keys()
        ), f"Missing keys: {required - arsenal_data.keys()}"

    def test_players_array_not_empty(self, arsenal_data: dict[str, Any]) -> None:
        players = arsenal_data["players"]
        assert len(players) > 10, f"Expected 10+ players, got {len(players)}"

    def test_player_has_required_fields(self, arsenal_data: dict[str, Any]) -> None:
        player = arsenal_data["players"][0]
        required = {
            "id",
            "player_name",
            "games",
            "time",
            "goals",
            "xG",
            "assists",
            "xA",
            "shots",
            "key_passes",
            "npg",
            "npxG",
            "position",
            "team_title",
        }
        missing = required - player.keys()
        assert not missing, f"Player missing fields: {missing}"

    def test_player_stats_are_numeric_strings(
        self, arsenal_data: dict[str, Any]
    ) -> None:
        player = arsenal_data["players"][0]
        for field in ("xG", "xA", "npxG"):
            val = player[field]
            assert isinstance(val, str), f"{field} should be string, got {type(val)}"
            float(val)  # should not raise

    def test_dates_array_not_empty(self, arsenal_data: dict[str, Any]) -> None:
        dates = arsenal_data["dates"]
        assert len(dates) > 0, "Expected at least 1 match in dates"

    def test_date_entry_has_required_fields(self, arsenal_data: dict[str, Any]) -> None:
        entry = arsenal_data["dates"][0]
        required = {
            "id",
            "isResult",
            "side",
            "h",
            "a",
            "goals",
            "xG",
            "datetime",
        }
        missing = required - entry.keys()
        assert not missing, f"Date entry missing fields: {missing}"

    def test_date_entry_has_team_structure(self, arsenal_data: dict[str, Any]) -> None:
        entry = arsenal_data["dates"][0]
        for side in ("h", "a"):
            team = entry[side]
            assert "id" in team, f"Missing 'id' in {side} team"
            assert "title" in team, f"Missing 'title' in {side} team"
            assert "short_title" in team, f"Missing 'short_title' in {side} team"

    def test_date_entry_xg_is_per_side(self, arsenal_data: dict[str, Any]) -> None:
        entry = arsenal_data["dates"][0]
        xg = entry["xG"]
        assert "h" in xg, "Missing 'h' in xG"
        assert "a" in xg, "Missing 'a' in xG"
        float(xg["h"])  # should not raise
        float(xg["a"])

    def test_all_20_teams_accessible(self) -> None:
        """Verify at least a few teams can be fetched (not all 20 to save time)."""
        settings = get_settings()
        sample_teams = ["Arsenal", "Liverpool", "Manchester_City"]

        async def _fetch_all() -> list[str]:
            failures: list[str] = []
            async with httpx.AsyncClient(
                timeout=settings.http_timeout,
                headers={
                    "User-Agent": settings.user_agent,
                    "X-Requested-With": "XMLHttpRequest",
                },
            ) as client:
                for team in sample_teams:
                    try:
                        data = await fetch_team_data(client, team, "2025")
                        if "players" not in data:
                            failures.append(f"{team}: missing 'players' key")
                    except Exception as exc:
                        failures.append(f"{team}: {exc}")
            return failures

        failures = asyncio.run(_fetch_all())
        assert not failures, f"Failed teams: {failures}"

    def test_team_name_map_covers_20_teams(self) -> None:
        assert (
            len(UNDERSTAT_TEAMS) == 20
        ), f"Expected 20 team mappings, got {len(UNDERSTAT_TEAMS)}"
