"""Live scores via ESPN public API (no key required, unlimited requests).

Fetches the current matchweek (Friday-Monday) for all 5 major leagues.
Goal scorers and red cards shown for all leagues. Assists shown for
Premier League when API-Football key is configured.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter

from fpl.config import get_settings

router = APIRouter()

# In-memory caches, updated by the scheduler
_score_cache: dict[str, Any] = {}
_cache_updated_at: str = ""
_standings_cache: dict[str, Any] = {}
_standings_cache_updated_at: str = ""

_ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
_ESPN_STANDINGS_BASE = "https://site.api.espn.com/apis/v2/sports/soccer"

_LEAGUES = [
    {"slug": "eng.1", "name": "Premier League", "country": "England"},
    {"slug": "eng.2", "name": "Championship", "country": "England"},
    {"slug": "sco.1", "name": "Scottish Premiership", "country": "Scotland"},
    {"slug": "ita.1", "name": "Serie A", "country": "Italy"},
    {"slug": "esp.1", "name": "La Liga", "country": "Spain"},
    {"slug": "ger.1", "name": "Bundesliga", "country": "Germany"},
    {"slug": "fra.1", "name": "Ligue 1", "country": "France"},
]

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


def _matchweek_dates() -> list[str]:
    """Return date strings (YYYYMMDD) for the current matchweek.

    Covers Friday through Monday of the current week. If today is
    Tue-Thu, looks at the upcoming weekend instead.
    """
    today = datetime.now(UTC).date()
    weekday = today.weekday()  # Mon=0, Sun=6

    # Find the Friday that starts this matchweek
    if weekday <= 3:  # Mon-Thu: look at the upcoming Fri
        days_to_fri = 4 - weekday
        friday = today + timedelta(days=days_to_fri)
    else:  # Fri-Sun: use this week's Fri
        days_since_fri = weekday - 4
        friday = today - timedelta(days=days_since_fri)

    # Friday through Monday (4 days)
    return [
        (friday + timedelta(days=d)).strftime("%Y%m%d")
        for d in range(4)
    ]


async def _fetch_espn_league(
    client: httpx.AsyncClient, slug: str, date_str: str
) -> list[dict[str, Any]]:
    """Fetch scoreboard for a league from ESPN for a given date."""
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

    display_clock = status_obj.get("displayClock", "")
    elapsed = None
    if status_code in ("1H", "2H", "ET"):
        with contextlib.suppress(ValueError, AttributeError):
            elapsed = int(display_clock.replace("'", "").split("+")[0])

    has_started = status_code not in ("NS", "PST", "CANC", "DEL", "TBD")

    # Extract events from details (goals + red cards)
    details = comp.get("details", [])
    events_out: list[dict[str, Any]] = []
    for d in details:
        is_goal = d.get("scoringPlay", False)
        is_red = d.get("redCard", False)
        if not is_goal and not is_red:
            continue

        clock = d.get("clock", {})
        athletes = d.get("athletesInvolved", [])
        player_name = athletes[0].get("displayName", "") if athletes else ""
        team_id = d.get("team", {}).get("id", "")

        team_name = ""
        for c in competitors:
            if c.get("id") == team_id:
                team_name = c.get("team", {}).get("displayName", "")
                break

        if is_goal:
            type_text = d.get("type", {}).get("text", "Goal")
            is_penalty = d.get("penaltyKick", False)
            is_own_goal = d.get("ownGoal", False)
            detail = (
                "Penalty"
                if is_penalty
                else "Own Goal"
                if is_own_goal
                else type_text
            )
            events_out.append(
                {
                    "minute": clock.get("displayValue", ""),
                    "extra_minute": None,
                    "type": "Goal",
                    "detail": detail,
                    "player": player_name,
                    "assist": None,
                    "team": team_name,
                }
            )
        elif is_red:
            is_yellow_red = d.get("yellowCard", False)
            events_out.append(
                {
                    "minute": clock.get("displayValue", ""),
                    "extra_minute": None,
                    "type": "Red Card",
                    "detail": "Second Yellow"
                    if is_yellow_red
                    else "Red Card",
                    "player": player_name,
                    "assist": None,
                    "team": team_name,
                }
            )

    kickoff = event.get("date", "")

    return {
        "fixture_id": event.get("id", ""),
        "status": status_code,
        "status_long": status_type.get("description", ""),
        "elapsed": elapsed,
        "home_team": home.get("team", {}).get("displayName", ""),
        "away_team": away.get("team", {}).get("displayName", ""),
        "home_goals": int(home.get("score", 0)) if has_started else None,
        "away_goals": int(away.get("score", 0)) if has_started else None,
        "kickoff": kickoff,
        "date": kickoff[:10] if kickoff else "",
        "events": events_out,
    }


async def _enrich_pl_assists(
    client: httpx.AsyncClient,
    matches: list[dict[str, Any]],
) -> None:
    """Add assist info to PL goals using API-Football (if key set)."""
    settings = get_settings()
    if not settings.api_football_key:
        return

    # Group matches by date to minimize API calls
    dates: set[str] = set()
    for m in matches:
        if m.get("date"):
            dates.add(m["date"])

    for match_date in dates:
        try:
            url = f"{settings.api_football_base_url}/fixtures"
            resp = await client.get(
                url,
                params={
                    "league": "39",
                    "season": str(settings.api_football_season),
                    "date": match_date,
                },
                headers={
                    "x-apisports-key": settings.api_football_key
                },
            )
            resp.raise_for_status()
            api_fixtures = resp.json().get("response", [])
        except Exception:
            continue

        for match in matches:
            if match.get("date") != match_date:
                continue
            if match["status"] in ("NS", "PST", "CANC"):
                continue

            for af in api_fixtures:
                af_home = (
                    af.get("teams", {}).get("home", {}).get("name", "")
                )
                if not (
                    af_home in match["home_team"]
                    or match["home_team"] in af_home
                ):
                    continue

                af_events = af.get("events", [])
                for goal in match["events"]:
                    if goal["type"] != "Goal":
                        continue
                    minute_str = goal["minute"].replace("'", "")
                    with contextlib.suppress(ValueError):
                        minute_int = int(minute_str.split("+")[0])
                        for ev in af_events:
                            if ev.get("type") != "Goal":
                                continue
                            ev_min = ev.get("time", {}).get("elapsed", 0)
                            if abs(ev_min - minute_int) <= 1:
                                assister = (
                                    ev.get("assist", {}).get("name")
                                )
                                if assister:
                                    goal["assist"] = assister
                                break
                break


async def fetch_scores(
    date: str | None = None,
) -> dict[str, Any]:
    """Fetch matchweek scores from ESPN. Used by both the endpoint and scheduler."""
    dates = [date.replace("-", "")] if date else _matchweek_dates()

    leagues_out: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=15) as client:
        for league_info in _LEAGUES:
            all_matches: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            for d in dates:
                try:
                    events = await _fetch_espn_league(
                        client, league_info["slug"], d
                    )
                except Exception:
                    continue
                for ev in events:
                    eid = ev.get("id", "")
                    if eid not in seen_ids:
                        seen_ids.add(eid)
                        all_matches.append(_parse_espn_match(ev))

            all_matches.sort(key=lambda m: m.get("kickoff", ""))

            if league_info["slug"] == "eng.1" and all_matches:
                with contextlib.suppress(Exception):
                    await _enrich_pl_assists(client, all_matches)

            if all_matches:
                leagues_out.append(
                    {
                        "id": league_info["slug"],
                        "name": league_info["name"],
                        "country": league_info["country"],
                        "matches": all_matches,
                    }
                )

    display_date = date or datetime.now(UTC).strftime("%Y-%m-%d")
    return {
        "date": display_date,
        "leagues": leagues_out,
    }


async def refresh_score_cache() -> None:
    """Refresh the in-memory score cache. Called by the scheduler."""
    global _score_cache, _cache_updated_at
    result = await fetch_scores()
    _score_cache = result
    _cache_updated_at = datetime.now(UTC).isoformat()


@router.get("/today")
async def today_scores(
    date: str | None = None, force: bool = False
) -> dict[str, Any]:
    """Return current matchweek scores.

    Serves from cache if available and fresh (updated by scheduler).
    Falls back to live fetch if no cache or if force=true or custom date.
    """
    global _score_cache, _cache_updated_at

    if not force and not date and _score_cache:
        return {**_score_cache, "cached_at": _cache_updated_at}

    result = await fetch_scores(date)

    # Update cache if this was a default (no custom date) fetch
    if not date:
        _score_cache = result
        _cache_updated_at = datetime.now(UTC).isoformat()

    return result


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

_STANDINGS_LEAGUES = [
    {"slug": "eng.1", "name": "Premier League", "country": "England"},
    {"slug": "eng.2", "name": "Championship", "country": "England"},
    {"slug": "sco.1", "name": "Scottish Premiership", "country": "Scotland"},
    {"slug": "ita.1", "name": "Serie A", "country": "Italy"},
    {"slug": "esp.1", "name": "La Liga", "country": "Spain"},
    {"slug": "ger.1", "name": "Bundesliga", "country": "Germany"},
    {"slug": "fra.1", "name": "Ligue 1", "country": "France"},
]


async def _fetch_espn_standings(
    client: httpx.AsyncClient, slug: str
) -> list[dict[str, Any]]:
    """Fetch standings for a league from ESPN."""
    url = f"{_ESPN_STANDINGS_BASE}/{slug}/standings"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    children = data.get("children", [])
    if not children:
        return []
    entries = (
        children[0]
        .get("standings", {})
        .get("entries", [])
    )
    return entries  # type: ignore[no-any-return]


def _get_stat(
    entry: dict[str, Any], stat_name: str
) -> int:
    """Extract a stat value from an ESPN standings entry."""
    for s in entry.get("stats", []):
        if s.get("name") == stat_name:
            return int(s.get("value", 0))
    return 0


def _parse_standing(entry: dict[str, Any]) -> dict[str, Any]:
    """Parse an ESPN standings entry into our shape."""
    team_info = entry.get("team", {})
    note = entry.get("note", {})
    return {
        "position": _get_stat(entry, "rank"),
        "team": team_info.get("displayName", ""),
        "team_short": team_info.get("abbreviation", ""),
        "played": _get_stat(entry, "gamesPlayed"),
        "won": _get_stat(entry, "wins"),
        "drawn": _get_stat(entry, "ties"),
        "lost": _get_stat(entry, "losses"),
        "gf": _get_stat(entry, "pointsFor"),
        "ga": _get_stat(entry, "pointsAgainst"),
        "gd": _get_stat(entry, "pointDifferential"),
        "points": _get_stat(entry, "points"),
        "zone": note.get("description", ""),
    }


async def fetch_standings() -> dict[str, Any]:
    """Fetch standings for all leagues from ESPN."""
    leagues_out: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=15) as client:
        for league_info in _STANDINGS_LEAGUES:
            try:
                entries = await _fetch_espn_standings(
                    client, league_info["slug"]
                )
            except Exception:
                continue

            table = [_parse_standing(e) for e in entries]
            table.sort(key=lambda t: t["position"])

            if table:
                leagues_out.append(
                    {
                        "id": league_info["slug"],
                        "name": league_info["name"],
                        "country": league_info["country"],
                        "table": table,
                    }
                )

    return {"leagues": leagues_out}


async def refresh_standings_cache() -> None:
    """Refresh the in-memory standings cache."""
    global _standings_cache, _standings_cache_updated_at
    result = await fetch_standings()
    _standings_cache = result
    _standings_cache_updated_at = datetime.now(UTC).isoformat()


@router.get("/standings")
async def get_standings(force: bool = False) -> dict[str, Any]:
    """Return league standings for all major leagues.

    Serves from cache if available.
    """
    global _standings_cache, _standings_cache_updated_at

    if not force and _standings_cache:
        return {
            **_standings_cache,
            "cached_at": _standings_cache_updated_at,
        }

    result = await fetch_standings()
    _standings_cache = result
    _standings_cache_updated_at = datetime.now(UTC).isoformat()

    return {**result, "cached_at": _standings_cache_updated_at}
