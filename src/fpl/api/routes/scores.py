"""Live scores via ESPN public API (no key required, unlimited requests).

Fetches the current matchweek (Friday-Monday) for all 5 major leagues.
Goal scorers and red cards shown for all leagues. Assists shown for
Premier League when API-Football key is configured.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

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
    {"slug": "uefa.champions", "name": "Champions League", "country": "Europe"},
    {"slug": "uefa.europa", "name": "Europa League", "country": "Europe"},
    {"slug": "uefa.europa.conf", "name": "Conference League", "country": "Europe"},
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

    Covers a full Tuesday-to-Monday window (7 days) to capture both
    midweek fixtures (Tue/Wed/Thu) and regular weekend games (Fri-Mon).

    - Mon/Tue: last Tuesday through today (this round still finishing)
    - Wed-Sun: this Tuesday through next Monday (full round window)
    """
    today = datetime.now(UTC).date()
    weekday = today.weekday()  # Mon=0 .. Sun=6

    # Find the Tuesday that starts this matchweek
    if weekday <= 1:  # Mon(0)/Tue(1): last week's Tuesday
        tuesday = today - timedelta(days=weekday + 6)
    else:  # Wed(2)-Sun(6): this week's Tuesday
        tuesday = today - timedelta(days=weekday - 1)

    # Tuesday through Monday (7 days)
    return [
        (tuesday + timedelta(days=d)).strftime("%Y%m%d")
        for d in range(7)
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
        "team_id": str(team_info.get("id", "")),
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


def _apply_live_results(
    table: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mutate standings table with in-progress and recently finished matches.

    ESPN's standings endpoint doesn't include live game impact, so we
    compute provisional updates from the scoreboard:

    - For each event that is in-progress or finished, find the teams
      in the table and update their played/W/D/L/GF/GA/GD/Pts.
    - We include BOTH live (state='in') and final (state='post') to
      handle the lag between a match finishing and ESPN updating its
      standings (which is usually a few minutes).
    """
    by_name: dict[str, dict[str, Any]] = {
        row["team"]: row for row in table
    }

    for event in events:
        comp = event.get("competitions", [{}])[0]
        status = event.get("status", {}).get("type", {})
        state = status.get("state", "")
        # Only apply live or recently-finished games
        if state not in ("in", "post"):
            continue
        # Skip if ESPN has already baked this game into standings.
        # Heuristic: if game is finished and we've seen it in standings,
        # don't double-count. We detect this by checking if the home/away
        # team's game count in the live scoreboard matches what's in the
        # table. In practice, ESPN updates quickly enough that we apply
        # to both in-progress and recently-finished, accepting a small
        # overlap for ~5 min after final whistle.
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue

        home = next(
            (c for c in competitors if c.get("homeAway") == "home"), {}
        )
        away = next(
            (c for c in competitors if c.get("homeAway") == "away"), {}
        )
        home_name = home.get("team", {}).get("displayName", "")
        away_name = away.get("team", {}).get("displayName", "")
        if home_name not in by_name or away_name not in by_name:
            continue

        try:
            home_goals = int(home.get("score", 0))
            away_goals = int(away.get("score", 0))
        except (ValueError, TypeError):
            continue

        home_row = by_name[home_name]
        away_row = by_name[away_name]

        # Only apply for live games — ESPN updates standings for
        # finished games quickly enough that adding them on top would
        # double-count. We specifically filter for state == "in".
        if state != "in":
            continue

        home_row["played"] += 1
        away_row["played"] += 1
        home_row["gf"] += home_goals
        home_row["ga"] += away_goals
        away_row["gf"] += away_goals
        away_row["ga"] += home_goals
        home_row["gd"] = home_row["gf"] - home_row["ga"]
        away_row["gd"] = away_row["gf"] - away_row["ga"]

        if home_goals > away_goals:
            home_row["won"] += 1
            away_row["lost"] += 1
            home_row["points"] += 3
        elif away_goals > home_goals:
            away_row["won"] += 1
            home_row["lost"] += 1
            away_row["points"] += 3
        else:
            home_row["drawn"] += 1
            away_row["drawn"] += 1
            home_row["points"] += 1
            away_row["points"] += 1

        home_row["live"] = True
        away_row["live"] = True

    # Re-sort by points, GD, GF
    table.sort(
        key=lambda r: (
            -r["points"],
            -r["gd"],
            -r["gf"],
            r["team"],
        )
    )
    # Re-number positions
    for i, row in enumerate(table, start=1):
        row["position"] = i

    return table


def _compute_team_form(
    events: list[dict[str, Any]], team_id: str
) -> list[str]:
    """Return last 5 W/D/L results for a team from ESPN event dicts.

    events: list of ESPN scoreboard events (any state; function filters)
    team_id: ESPN team ID string to look up in each event's competitors
    Returns: list of "W"/"D"/"L", ordered oldest first, length <= 5
    """
    finished: list[dict[str, Any]] = []
    for event in events:
        comp = event.get("competitions", [{}])[0]
        status_type = event.get("status", {}).get("type", {})
        state = status_type.get("state", "")
        if state != "post":
            continue
        competitors = comp.get("competitors", [])
        # Require both competitors to have a non-None, non-empty score
        scores_valid = all(
            c.get("score") not in (None, "") for c in competitors
        )
        if not scores_valid or len(competitors) != 2:
            continue
        finished.append(event)

    # Sort ascending by event date ISO string
    finished.sort(key=lambda e: e.get("date", ""))

    results: list[str] = []
    for event in finished:
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        our = next(
            (c for c in competitors if str(c.get("id", "")) == team_id),
            None,
        )
        if our is None:
            continue
        other = next(
            (c for c in competitors if str(c.get("id", "")) != team_id),
            None,
        )
        if other is None:
            continue
        try:
            our_score = int(our["score"])
            other_score = int(other["score"])
        except (ValueError, TypeError, KeyError):
            continue

        if our_score > other_score:
            results.append("W")
        elif our_score < other_score:
            results.append("L")
        else:
            results.append("D")

    return results[-5:]


async def _fetch_league_form(
    client: httpx.AsyncClient,
    slug: str,
    lookback_days: int = 90,
) -> dict[str, list[str]]:
    """Fetch last 5 results per team for a league from ESPN scoreboard history.

    Returns {team_id: ["W","D","L","W","W"]} ordered oldest first.
    """
    today = datetime.now(UTC).date()
    # ESPN scoreboard returns only events on the exact requested date, so we
    # must sample frequently enough to catch every matchday. A 3-day step
    # covers midweek fixtures (Tue/Wed/Thu) that weekly sampling would miss.
    # 90-day lookback handles international breaks where teams may go 3+ weeks
    # without a league fixture (~30 requests per league, run in parallel).
    date_strings: list[str] = []
    step = 0
    while step <= lookback_days:
        sample_date = today - timedelta(days=step)
        date_strings.append(sample_date.strftime("%Y%m%d"))
        step += 3

    async def _fetch_one(date_str: str) -> list[dict[str, Any]]:
        try:
            return await _fetch_espn_league(client, slug, date_str)
        except Exception:
            return []

    results_list = await asyncio.gather(*[_fetch_one(d) for d in date_strings])

    # Deduplicate events by ID
    seen_ids: set[str] = set()
    all_events: list[dict[str, Any]] = []
    for events in results_list:
        for event in events:
            eid = event.get("id", "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                all_events.append(event)

    # Collect all team IDs seen
    team_ids: set[str] = set()
    for event in all_events:
        comp = event.get("competitions", [{}])[0]
        for c in comp.get("competitors", []):
            tid = str(c.get("id", ""))
            if tid:
                team_ids.add(tid)

    return {
        tid: _compute_team_form(all_events, tid) for tid in team_ids
    }


async def fetch_standings() -> dict[str, Any]:
    """Fetch standings for all leagues from ESPN + apply live updates."""
    leagues_out: list[dict[str, Any]] = []

    today = datetime.now(UTC).strftime("%Y%m%d")
    settings = get_settings()

    async with httpx.AsyncClient(timeout=15) as client:
        for league_info in _STANDINGS_LEAGUES:
            try:
                entries = await _fetch_espn_standings(
                    client, league_info["slug"]
                )
            except Exception:
                continue

            table = [_parse_standing(e) for e in entries]

            # Fetch today's events and apply in-progress results
            try:
                events = await _fetch_espn_league(
                    client, league_info["slug"], today
                )
                table = _apply_live_results(table, events)
            except Exception:
                table.sort(key=lambda t: t["position"])

            # Fetch form (last 5 results) per team
            try:
                form_map = await _fetch_league_form(
                    client, league_info["slug"]
                )
                for row in table:
                    row["form"] = form_map.get(row.get("team_id", ""), [])
            except Exception:
                for row in table:
                    row["form"] = []

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


# ---------------------------------------------------------------------------
# Match detail (ESPN summary endpoint)
# ---------------------------------------------------------------------------


def _parse_team_stats(
    team_data: dict[str, Any],
) -> dict[str, Any]:
    """Parse a single team's stats block from ESPN boxscore."""
    team_info = team_data.get("team", {})
    stats: dict[str, Any] = {}
    for s in team_data.get("statistics", []):
        name = s.get("name", "")
        display = s.get("displayValue", "")
        if name:
            stats[name] = display
    return {
        "name": team_info.get("displayName", ""),
        "short": team_info.get("abbreviation", ""),
        "logo": team_info.get("logo", ""),
        "home_away": team_data.get("homeAway", ""),
        "stats": stats,
    }


def _parse_roster(
    roster_data: dict[str, Any],
) -> dict[str, Any]:
    """Parse a team's roster into starters/subs."""
    team_info = roster_data.get("team", {})
    starters: list[dict[str, Any]] = []
    subs: list[dict[str, Any]] = []
    for entry in roster_data.get("roster", []):
        athlete = entry.get("athlete", {})
        position = entry.get("position", {})
        player: dict[str, Any] = {
            "name": athlete.get("displayName", ""),
            "short_name": athlete.get("shortName", ""),
            "jersey": entry.get("jersey", ""),
            "position": position.get("abbreviation", ""),
            "subbed_in": entry.get("subbedIn", {}).get("didSub", False)
            if isinstance(entry.get("subbedIn"), dict)
            else False,
            "subbed_out": entry.get("subbedOut", {}).get("didSub", False)
            if isinstance(entry.get("subbedOut"), dict)
            else False,
        }
        if entry.get("starter"):
            starters.append(player)
        else:
            subs.append(player)
    return {
        "team": team_info.get("displayName", ""),
        "short": team_info.get("abbreviation", ""),
        "starters": starters,
        "subs": subs,
    }


def _parse_key_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse key events (goals, cards, subs) for the timeline."""
    result: list[dict[str, Any]] = []
    for ev in events:
        clock = ev.get("clock", {})
        result.append(
            {
                "minute": clock.get("displayValue", ""),
                "type": ev.get("type", {}).get("text", ""),
                "text": ev.get("text", ""),
                "scoring_play": ev.get("scoringPlay", False),
            }
        )
    return result


@router.get("/match/{fixture_id}")
async def get_match_detail(
    fixture_id: str, league: str = "eng.1"
) -> dict[str, Any]:
    """Return detailed match data for an ESPN fixture.

    Pulls from ESPN's /{league}/summary?event={id} endpoint which
    includes boxscore (team stats), rosters (starters/subs), and
    keyEvents (goals/cards/subs timeline).
    """
    url = f"{_ESPN_BASE}/{league}/summary"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                url, params={"event": fixture_id}
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch match {fixture_id}: {exc}",
            ) from exc

    # Header (scoreline + status)
    header = data.get("header", {})
    competition = (header.get("competitions") or [{}])[0]
    competitors = competition.get("competitors", [])
    home_comp = next(
        (c for c in competitors if c.get("homeAway") == "home"), {}
    )
    away_comp = next(
        (c for c in competitors if c.get("homeAway") == "away"), {}
    )

    status_obj = competition.get("status", {})
    status_type = status_obj.get("type", {})

    # Box score stats
    boxscore_teams = data.get("boxscore", {}).get("teams", [])
    home_stats = None
    away_stats = None
    for t in boxscore_teams:
        parsed = _parse_team_stats(t)
        if parsed["home_away"] == "home":
            home_stats = parsed
        else:
            away_stats = parsed

    # Rosters
    rosters = data.get("rosters", [])
    home_roster = None
    away_roster = None
    for r in rosters:
        parsed = _parse_roster(r)
        if r.get("homeAway") == "home":
            home_roster = parsed
        else:
            away_roster = parsed

    # Key events
    key_events = _parse_key_events(data.get("keyEvents", []))

    # Venue
    game_info = data.get("gameInfo", {})
    venue = game_info.get("venue", {})

    return {
        "fixture_id": fixture_id,
        "league": league,
        "status": {
            "state": status_type.get("state", ""),
            "name": status_type.get("name", ""),
            "description": status_type.get("description", ""),
            "display_clock": status_obj.get("displayClock", ""),
            "period": status_obj.get("period", 0),
        },
        "home": {
            "name": home_comp.get("team", {}).get("displayName", ""),
            "short": home_comp.get("team", {}).get(
                "abbreviation", ""
            ),
            "logo": home_comp.get("team", {}).get("logo", ""),
            "score": home_comp.get("score", "0"),
            "stats": home_stats["stats"] if home_stats else {},
            "roster": home_roster
            or {"starters": [], "subs": [], "team": "", "short": ""},
        },
        "away": {
            "name": away_comp.get("team", {}).get("displayName", ""),
            "short": away_comp.get("team", {}).get(
                "abbreviation", ""
            ),
            "logo": away_comp.get("team", {}).get("logo", ""),
            "score": away_comp.get("score", "0"),
            "stats": away_stats["stats"] if away_stats else {},
            "roster": away_roster
            or {"starters": [], "subs": [], "team": "", "short": ""},
        },
        "events": key_events,
        "venue": venue.get("fullName", ""),
        "attendance": game_info.get("attendance"),
    }
