"""Integration tests that hit the live Odds API.

Requires FPL_ODDS_API_KEY to be set. Tests are skipped if no key is configured.

Run with:
    pytest tests/test_integration/test_odds_live.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from fpl.config import get_settings
from fpl.ingest.odds import ODDS_TEAM_MAP, fetch_epl_odds

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def settings() -> Any:
    return get_settings()


@pytest.fixture(scope="module")
def odds_data(settings: Any) -> list[dict[str, Any]]:
    """Fetch EPL odds once for all tests. Skip if no API key."""
    if not settings.odds_api_key:
        pytest.skip("FPL_ODDS_API_KEY not set")

    async def _fetch() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            return await fetch_epl_odds(client, settings)

    result: list[dict[str, Any]] = asyncio.run(_fetch())
    return result


class TestOddsApiResponseShape:
    """Verify The Odds API returns expected structure."""

    def test_response_is_list(self, odds_data: list[dict[str, Any]]) -> None:
        assert isinstance(odds_data, list)

    def test_events_not_empty(self, odds_data: list[dict[str, Any]]) -> None:
        # There should be upcoming EPL fixtures with odds
        # (may be empty during off-season)
        if not odds_data:
            pytest.skip("No upcoming EPL events with odds")

    def test_event_has_required_fields(self, odds_data: list[dict[str, Any]]) -> None:
        if not odds_data:
            pytest.skip("No events")
        event = odds_data[0]
        required = {
            "id",
            "sport_key",
            "commence_time",
            "home_team",
            "away_team",
            "bookmakers",
        }
        missing = required - event.keys()
        assert not missing, f"Event missing fields: {missing}"

    def test_sport_key_is_epl(self, odds_data: list[dict[str, Any]]) -> None:
        if not odds_data:
            pytest.skip("No events")
        for event in odds_data:
            assert (
                event["sport_key"] == "soccer_epl"
            ), f"Unexpected sport: {event['sport_key']}"

    def test_bookmakers_array_exists(self, odds_data: list[dict[str, Any]]) -> None:
        if not odds_data:
            pytest.skip("No events")
        event = odds_data[0]
        assert isinstance(event["bookmakers"], list)
        assert len(event["bookmakers"]) > 0, "No bookmakers for event"

    def test_bookmaker_has_required_fields(
        self, odds_data: list[dict[str, Any]]
    ) -> None:
        if not odds_data:
            pytest.skip("No events")
        bm = odds_data[0]["bookmakers"][0]
        required = {"key", "title", "markets"}
        missing = required - bm.keys()
        assert not missing, f"Bookmaker missing fields: {missing}"

    def test_market_has_outcomes(self, odds_data: list[dict[str, Any]]) -> None:
        if not odds_data:
            pytest.skip("No events")
        bm = odds_data[0]["bookmakers"][0]
        market = bm["markets"][0]
        assert "key" in market
        assert "outcomes" in market
        assert len(market["outcomes"]) > 0

    def test_outcome_has_name_and_price(self, odds_data: list[dict[str, Any]]) -> None:
        if not odds_data:
            pytest.skip("No events")
        bm = odds_data[0]["bookmakers"][0]
        outcome = bm["markets"][0]["outcomes"][0]
        assert "name" in outcome
        assert "price" in outcome
        assert isinstance(outcome["price"], (int, float))
        assert outcome["price"] > 0

    def test_h2h_market_has_three_outcomes(
        self, odds_data: list[dict[str, Any]]
    ) -> None:
        """H2H market should have home/draw/away outcomes."""
        if not odds_data:
            pytest.skip("No events")
        for event in odds_data:
            for bm in event["bookmakers"]:
                for market in bm["markets"]:
                    if market["key"] == "h2h":
                        names = {o["name"] for o in market["outcomes"]}
                        assert "Draw" in names, f"H2H missing Draw outcome: {names}"
                        assert len(names) == 3, f"H2H should have 3 outcomes: {names}"
                        return
        pytest.skip("No h2h market found in any event")

    def test_team_names_are_recognisable(self, odds_data: list[dict[str, Any]]) -> None:
        """Teams from the API should be in our mapping."""
        if not odds_data:
            pytest.skip("No events")
        unknown: set[str] = set()
        for event in odds_data:
            for name in (event["home_team"], event["away_team"]):
                if name not in ODDS_TEAM_MAP:
                    unknown.add(name)
        assert not unknown, (
            f"Unknown team names from Odds API: {unknown}. " "Update ODDS_TEAM_MAP."
        )
