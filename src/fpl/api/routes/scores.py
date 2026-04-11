from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from fpl.config import get_settings

router = APIRouter()

_LEAGUES = {
    39: {"name": "Premier League", "country": "England"},
    135: {"name": "Serie A", "country": "Italy"},
    140: {"name": "La Liga", "country": "Spain"},
    78: {"name": "Bundesliga", "country": "Germany"},
    61: {"name": "Ligue 1", "country": "France"},
}


async def _fetch_fixtures(
    client: httpx.AsyncClient,
    settings: object,
    league_id: int,
    date: str,
) -> list[dict[str, Any]]:
    """Fetch today's fixtures for a league from API-Football."""
    s = settings  # type: ignore[assignment]
    url = f"{s.api_football_base_url}/fixtures"
    params = {
        "league": str(league_id),
        "date": date,
        "season": str(s.api_football_season),
    }
    headers = {"x-apisports-key": s.api_football_key}
    resp = await client.get(url, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", [])  # type: ignore[no-any-return]


async def _fetch_events(
    client: httpx.AsyncClient,
    settings: object,
    fixture_id: int,
) -> list[dict[str, Any]]:
    """Fetch events (goals, cards, subs) for a fixture."""
    s = settings  # type: ignore[assignment]
    url = f"{s.api_football_base_url}/fixtures/events"
    params = {"fixture": str(fixture_id)}
    headers = {"x-apisports-key": s.api_football_key}
    resp = await client.get(url, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", [])  # type: ignore[no-any-return]


def _parse_match(fixture: dict[str, Any]) -> dict[str, Any]:
    """Parse a fixture response into our match shape."""
    f = fixture.get("fixture", {})
    status = f.get("status", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})

    return {
        "fixture_id": f.get("id"),
        "status": status.get("short", "NS"),
        "status_long": status.get("long", "Not Started"),
        "elapsed": status.get("elapsed"),
        "home_team": teams.get("home", {}).get("name", ""),
        "away_team": teams.get("away", {}).get("name", ""),
        "home_goals": goals.get("home"),
        "away_goals": goals.get("away"),
        "kickoff": f.get("date", ""),
        "events": [],
    }


def _parse_events(
    events: list[dict[str, Any]], include_assists: bool
) -> list[dict[str, Any]]:
    """Parse events into goal events list."""
    result: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("type") != "Goal":
            continue
        time_info = ev.get("time", {})
        assist_info = ev.get("assist", {})
        result.append(
            {
                "minute": time_info.get("elapsed"),
                "extra_minute": time_info.get("extra"),
                "type": "Goal",
                "detail": ev.get("detail", ""),
                "player": ev.get("player", {}).get("name", ""),
                "assist": (
                    assist_info.get("name")
                    if include_assists
                    else None
                ),
                "team": ev.get("team", {}).get("name", ""),
            }
        )
    return result


@router.get("/today")
async def today_scores(date: str | None = None) -> dict[str, Any]:
    """Fetch today's fixtures for all 5 major leagues with goal scorers.

    Assists are included for Premier League matches only.
    """
    settings = get_settings()
    if not settings.api_football_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "API-Football key not configured. "
                "Set FPL_API_FOOTBALL_KEY in .env."
            ),
        )

    target_date = date or datetime.now(UTC).strftime("%Y-%m-%d")
    headers = {"x-apisports-key": settings.api_football_key}

    leagues_out: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        timeout=settings.http_timeout, headers=headers
    ) as client:
        for league_id, league_info in _LEAGUES.items():
            try:
                fixtures = await _fetch_fixtures(
                    client, settings, league_id, target_date
                )
            except Exception:
                continue

            matches: list[dict[str, Any]] = []
            for fix in fixtures:
                match = _parse_match(fix)

                # Extract goal events from inline events if present
                inline_events = fix.get("events") or []
                is_pl = league_id == 39

                if inline_events:
                    match["events"] = _parse_events(
                        inline_events, include_assists=is_pl
                    )
                elif (
                    match["status"] not in ("NS", "TBD", "PST")
                    and is_pl
                ):
                    # Fetch events separately for PL to get assists
                    try:
                        events = await _fetch_events(
                            client, settings, match["fixture_id"]
                        )
                        match["events"] = _parse_events(
                            events, include_assists=True
                        )
                    except Exception:
                        pass

                matches.append(match)

            if matches:
                leagues_out.append(
                    {
                        "id": league_id,
                        "name": league_info["name"],
                        "country": league_info["country"],
                        "matches": matches,
                    }
                )

    return {
        "date": target_date,
        "leagues": leagues_out,
    }
