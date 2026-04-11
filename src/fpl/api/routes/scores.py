"""Live scores via ESPN public API (no key required, unlimited requests).

Goal scorers are shown for all leagues. Assists are shown for Premier
League matches when an API-Football key is configured (optional).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter

from fpl.config import get_settings

router = APIRouter()

_ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

_LEAGUES = [
    {"slug": "eng.1", "name": "Premier League", "country": "England"},
    {"slug": "ita.1", "name": "Serie A", "country": "Italy"},
    {"slug": "esp.1", "name": "La Liga", "country": "Spain"},
    {"slug": "ger.1", "name": "Bundesliga", "country": "Germany"},
    {"slug": "fra.1", "name": "Ligue 1", "country": "France"},
]

# ESPN status.type.name -> short code mapping
_STATUS_MAP: dict[str, str] = {
    "STATUS_SCHEDULED": "NS",
    "STATUS_FIRST_HALF": "1H",
    "STATUS_HALFTIME": "HT",
    "STATUS_SECOND_HALF": "2H",
    "STATUS_FULL_TIME": "FT",
    "STATUS_FINAL": "FT",
    "STATUS_FINAL_AET": "AET",
    "STATUS_FINAL_PEN": "PEN",
    "STATUS_POSTPONED": "PST",
    "STATUS_CANCELED": "CANC",
    "STATUS_DELAYED": "DEL",
    "STATUS_EXTRA_TIME_FIRST_HALF": "ET",
    "STATUS_EXTRA_TIME_HALF_TIME": "ET",
    "STATUS_EXTRA_TIME_SECOND_HALF": "ET",
    "STATUS_PENALTY_SHOOTOUT": "PEN",
}


async def _fetch_espn_league(
    client: httpx.AsyncClient, slug: str, date_str: str
) -> list[dict[str, Any]]:
    """Fetch scoreboard for a league from ESPN."""
    url = f"{_ESPN_BASE}/{slug}/scoreboard"
    params = {"dates": date_str}
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("events", [])  # type: ignore[no-any-return]


def _parse_espn_match(event: dict[str, Any]) -> dict[str, Any]:
    """Parse an ESPN event into our match shape."""
    comp = event.get("competitions", [{}])[0]
    status_obj = event.get("status", comp.get("status", {}))
    status_type = status_obj.get("type", {})
    status_name = status_type.get("name", "STATUS_SCHEDULED")
    status_code = _STATUS_MAP.get(status_name, "NS")

    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})

    # Parse elapsed from displayClock (e.g. "67'")
    display_clock = status_obj.get("displayClock", "")
    elapsed = None
    if status_code in ("1H", "2H", "ET"):
        try:
            elapsed = int(display_clock.replace("'", "").split("+")[0])
        except (ValueError, AttributeError):
            elapsed = status_obj.get("period", None)

    has_started = status_code not in ("NS", "PST", "CANC", "DEL", "TBD")

    # Extract goal events from details
    details = comp.get("details", [])
    events_out: list[dict[str, Any]] = []
    for d in details:
        if not d.get("scoringPlay"):
            continue
        clock = d.get("clock", {})
        athletes = d.get("athletesInvolved", [])
        scorer = athletes[0].get("displayName", "") if athletes else ""
        team_id = d.get("team", {}).get("id", "")

        # Resolve team name from competitors
        team_name = ""
        for c in competitors:
            if c.get("id") == team_id:
                team_name = c.get("team", {}).get("displayName", "")
                break

        type_text = d.get("type", {}).get("text", "Goal")
        is_penalty = d.get("penaltyKick", False)
        is_own_goal = d.get("ownGoal", False)
        detail = "Penalty" if is_penalty else "Own Goal" if is_own_goal else type_text

        events_out.append(
            {
                "minute": clock.get("displayValue", ""),
                "extra_minute": None,
                "type": "Goal",
                "detail": detail,
                "player": scorer,
                "assist": None,
                "team": team_name,
            }
        )

    return {
        "fixture_id": event.get("id", ""),
        "status": status_code,
        "status_long": status_type.get("description", ""),
        "elapsed": elapsed,
        "home_team": home.get("team", {}).get("displayName", ""),
        "away_team": away.get("team", {}).get("displayName", ""),
        "home_goals": int(home.get("score", 0)) if has_started else None,
        "away_goals": int(away.get("score", 0)) if has_started else None,
        "kickoff": event.get("date", ""),
        "events": events_out,
    }


async def _enrich_pl_assists(
    client: httpx.AsyncClient,
    matches: list[dict[str, Any]],
) -> None:
    """Add assist info to PL goals using API-Football (if key configured)."""
    settings = get_settings()
    if not settings.api_football_key:
        return

    for match in matches:
        if match["status"] in ("NS", "PST", "CANC") or not match["events"]:
            continue
        try:
            url = f"{settings.api_football_base_url}/fixtures"
            # Search by date and teams
            resp = await client.get(
                url,
                params={
                    "league": "39",
                    "season": str(settings.api_football_season),
                    "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                },
                headers={"x-apisports-key": settings.api_football_key},
            )
            resp.raise_for_status()
            api_fixtures = resp.json().get("response", [])

            # Find matching fixture by team names
            for af in api_fixtures:
                af_home = af.get("teams", {}).get("home", {}).get("name", "")
                if not (
                    af_home in match["home_team"]
                    or match["home_team"] in af_home
                ):
                    continue

                # Extract assists from API-Football events
                af_events = af.get("events", [])
                assist_map: dict[str, str] = {}
                for ev in af_events:
                    if ev.get("type") != "Goal":
                        continue
                    scorer = ev.get("player", {}).get("name", "")
                    assister = ev.get("assist", {}).get("name")
                    if scorer and assister:
                        minute = ev.get("time", {}).get("elapsed", 0)
                        assist_map[f"{minute}_{scorer}"] = assister

                # Match assists to ESPN goals
                for goal in match["events"]:
                    minute_str = goal["minute"].replace("'", "")
                    try:
                        minute_int = int(minute_str.split("+")[0])
                    except ValueError:
                        continue
                    # Fuzzy: match by minute (within 1 min tolerance)
                    for k, v in assist_map.items():
                        km = int(k.split("_")[0])
                        if abs(km - minute_int) <= 1:
                            goal["assist"] = v
                            break
                break
        except Exception:
            continue


@router.get("/today")
async def today_scores(date: str | None = None) -> dict[str, Any]:
    """Fetch today's fixtures for all 5 major leagues.

    Uses ESPN public API (no key needed, unlimited).
    If FPL_API_FOOTBALL_KEY is set, PL goals are enriched with assists.
    """
    target_date = date or datetime.now(UTC).strftime("%Y-%m-%d")
    espn_date = target_date.replace("-", "")

    leagues_out: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=15) as client:
        for league_info in _LEAGUES:
            try:
                events = await _fetch_espn_league(
                    client, league_info["slug"], espn_date
                )
            except Exception:
                continue

            matches = [_parse_espn_match(ev) for ev in events]

            # Enrich PL matches with assists if API key available
            if league_info["slug"] == "eng.1" and matches:
                import contextlib

                with contextlib.suppress(Exception):
                    await _enrich_pl_assists(client, matches)

            if matches:
                leagues_out.append(
                    {
                        "id": league_info["slug"],
                        "name": league_info["name"],
                        "country": league_info["country"],
                        "matches": matches,
                    }
                )

    return {
        "date": target_date,
        "leagues": leagues_out,
    }
