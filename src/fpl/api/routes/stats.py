"""Player statistics search.

Primary: ESPN public API for search + current season stats (no key, unlimited).
Supplementary: Understat for xG/xA (Big 5 leagues, scraped).
Optional: API-Football for deeper historical stats (requires key, 100 req/day).
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from fpl.config import get_settings

router = APIRouter()

_ESPN_SEARCH = "https://site.api.espn.com/apis/common/v3/search"
_ESPN_ATHLETE = (
    "https://site.api.espn.com/apis/common/v3/sports/soccer"
)

# League slugs ESPN uses
_ESPN_LEAGUES = [
    "eng.1", "eng.2", "ita.1", "esp.1", "ger.1", "fra.1",
]

# API-Football league IDs for deeper stats
_AF_LEAGUES = [39, 140, 135, 78, 61, 40]


def _safe_int(val: Any) -> int:
    if val is None:
        return 0
    with contextlib.suppress(ValueError, TypeError):
        return int(val)
    return 0


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    with contextlib.suppress(ValueError, TypeError):
        return round(float(val), 2)
    return None


# ------------------------------------------------------------------
# ESPN-based search + current season stats
# ------------------------------------------------------------------


async def _espn_search(
    client: httpx.AsyncClient, query: str
) -> list[dict[str, Any]]:
    """Search players via ESPN."""
    resp = await client.get(
        _ESPN_SEARCH,
        params={
            "query": query,
            "type": "player",
            "sport": "soccer",
            "limit": "25",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", [])  # type: ignore[no-any-return]


async def _espn_player_detail(
    client: httpx.AsyncClient,
    player_id: str,
    league_slug: str,
) -> dict[str, Any] | None:
    """Fetch player detail from ESPN."""
    url = f"{_ESPN_ATHLETE}/{league_slug}/athletes/{player_id}"
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json().get("athlete", {})  # type: ignore[no-any-return]
    except Exception:
        return None


def _parse_espn_search_result(
    item: dict[str, Any],
) -> dict[str, Any]:
    """Parse an ESPN search result."""
    league_rels = item.get("leagueRelationships", [])
    league_slug = item.get("league", "")
    team_name = ""
    for rel in league_rels:
        if rel.get("type") == "team":
            team_name = rel.get("displayName", "")
            break

    return {
        "id": item.get("id", ""),
        "name": item.get("displayName", ""),
        "short_name": item.get("shortName", ""),
        "team": team_name,
        "league": league_slug,
        "source": "espn",
    }


def _parse_espn_stats(
    athlete: dict[str, Any],
) -> dict[str, Any]:
    """Parse ESPN athlete data into stats."""
    summary_stats = athlete.get("statsSummary", {})
    stats_list = summary_stats.get("statistics", [])
    stat_map: dict[str, Any] = {}
    for s in stats_list:
        stat_map[s.get("name", "")] = s.get("value")

    position = athlete.get("position", {}).get("displayName", "")
    team = athlete.get("team", {}).get("displayName", "")
    age = athlete.get("age")
    nationality = athlete.get("citizenship", "")
    height = athlete.get("height", {}).get("displayValue", "")
    weight = athlete.get("weight", {}).get("displayValue", "")
    photo = athlete.get("headshot", {}).get("href", "")

    # Parse starts (sub) format: "23 (5)"
    starts_val = stat_map.get("starts-subIns")
    starts = 0
    sub_ins = 0
    appearances = 0
    if starts_val is not None:
        # displayValue is like "23 (5)"
        for s in stats_list:
            if s.get("name") == "starts-subIns":
                dv = s.get("displayValue", "")
                parts = re.findall(r"\d+", dv)
                if len(parts) >= 2:
                    starts = int(parts[0])
                    sub_ins = int(parts[1])
                elif len(parts) == 1:
                    starts = int(parts[0])
                appearances = starts + sub_ins
                break

    return {
        "player": {
            "name": athlete.get("displayName", ""),
            "firstname": athlete.get("firstName", ""),
            "lastname": athlete.get("lastName", ""),
            "age": age,
            "nationality": nationality,
            "height": height,
            "weight": weight,
            "photo": photo,
            "team": team,
            "position": position,
            "league": summary_stats.get("displayName", ""),
        },
        "season_label": summary_stats.get("displayName", ""),
        "statistics": [
            {
                "team": team,
                "league": summary_stats.get("displayName", ""),
                "position": position,
                "appearances": appearances,
                "lineups": starts,
                "goals": _safe_int(stat_map.get("totalGoals")),
                "assists": _safe_int(stat_map.get("goalAssists")),
                "shots_total": _safe_int(stat_map.get("totalShots")),
                "shots_on": _safe_int(
                    stat_map.get("shotsOnTarget")
                ),
                "yellow_cards": _safe_int(
                    stat_map.get("yellowCards")
                ),
                "red_cards": _safe_int(
                    stat_map.get("redCards")
                ),
                "fouls_committed": _safe_int(
                    stat_map.get("foulsCommitted")
                ),
                "fouls_drawn": _safe_int(
                    stat_map.get("foulsSuffered")
                ),
                "tackles": _safe_int(
                    stat_map.get("totalTackles")
                ),
                "interceptions": _safe_int(
                    stat_map.get("interceptions")
                ),
                "saves": _safe_int(stat_map.get("saves")),
                "goals_conceded": _safe_int(
                    stat_map.get("goalsConceded")
                ),
                "minutes": _safe_int(
                    stat_map.get("minutesPlayed")
                ),
                "rating": None,
                "passes_total": 0,
                "passes_key": 0,
                "passes_accuracy": 0,
                "blocks": 0,
                "duels_total": 0,
                "duels_won": 0,
                "dribbles_attempts": 0,
                "dribbles_success": 0,
                "penalty_won": 0,
                "penalty_scored": 0,
                "penalty_missed": 0,
                "penalty_saved": 0,
                "league_country": "",
                "season": None,
            }
        ],
    }


# ------------------------------------------------------------------
# API-Football for deeper historical stats (optional)
# ------------------------------------------------------------------


async def _af_player_stats(
    client: httpx.AsyncClient,
    player_id: int,
    season: int,
) -> dict[str, Any] | None:
    """Fetch player stats from API-Football (optional)."""
    settings = get_settings()
    if not settings.api_football_key:
        return None

    url = f"{settings.api_football_base_url}/players"
    headers = {"x-apisports-key": settings.api_football_key}
    try:
        resp = await client.get(
            url,
            params={"id": str(player_id), "season": str(season)},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("response", [])
        if not entries:
            return None
        return entries[0]  # type: ignore[no-any-return]
    except Exception:
        return None


def _parse_af_stats(
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Parse API-Football player stats."""
    p = entry.get("player", {})
    stats_list = entry.get("statistics", [])

    parsed_stats: list[dict[str, Any]] = []
    for s in stats_list:
        team = s.get("team", {})
        league = s.get("league", {})
        games = s.get("games", {})
        goals = s.get("goals", {})
        shots = s.get("shots", {})
        passes = s.get("passes", {})
        tackles = s.get("tackles", {})
        duels = s.get("duels", {})
        dribbles = s.get("dribbles", {})
        fouls = s.get("fouls", {})
        cards = s.get("cards", {})
        penalty = s.get("penalty", {})

        parsed_stats.append(
            {
                "team": team.get("name", ""),
                "league": league.get("name", ""),
                "league_country": league.get("country", ""),
                "season": league.get("season"),
                "position": games.get("position", ""),
                "rating": _safe_float(games.get("rating")),
                "appearances": _safe_int(
                    games.get("appearences")
                ),
                "lineups": _safe_int(games.get("lineups")),
                "minutes": _safe_int(games.get("minutes")),
                "goals": _safe_int(goals.get("total")),
                "assists": _safe_int(goals.get("assists")),
                "goals_conceded": _safe_int(
                    goals.get("conceded")
                ),
                "saves": _safe_int(goals.get("saves")),
                "shots_total": _safe_int(shots.get("total")),
                "shots_on": _safe_int(shots.get("on")),
                "passes_total": _safe_int(passes.get("total")),
                "passes_key": _safe_int(passes.get("key")),
                "passes_accuracy": _safe_int(
                    passes.get("accuracy")
                ),
                "tackles": _safe_int(tackles.get("total")),
                "blocks": _safe_int(tackles.get("blocks")),
                "interceptions": _safe_int(
                    tackles.get("interceptions")
                ),
                "duels_total": _safe_int(duels.get("total")),
                "duels_won": _safe_int(duels.get("won")),
                "dribbles_attempts": _safe_int(
                    dribbles.get("attempts")
                ),
                "dribbles_success": _safe_int(
                    dribbles.get("success")
                ),
                "fouls_drawn": _safe_int(fouls.get("drawn")),
                "fouls_committed": _safe_int(
                    fouls.get("committed")
                ),
                "yellow_cards": _safe_int(cards.get("yellow")),
                "red_cards": _safe_int(cards.get("red")),
                "penalty_won": _safe_int(penalty.get("won")),
                "penalty_scored": _safe_int(
                    penalty.get("scored")
                ),
                "penalty_missed": _safe_int(
                    penalty.get("missed")
                ),
                "penalty_saved": _safe_int(
                    penalty.get("saved")
                ),
            }
        )

    return {
        "player": {
            "id": p.get("id"),
            "name": p.get("name", ""),
            "firstname": p.get("firstname", ""),
            "lastname": p.get("lastname", ""),
            "age": p.get("age"),
            "nationality": p.get("nationality", ""),
            "height": p.get("height", ""),
            "weight": p.get("weight", ""),
            "photo": p.get("photo", ""),
            "team": (
                parsed_stats[0]["team"] if parsed_stats else ""
            ),
            "position": (
                parsed_stats[0]["position"]
                if parsed_stats
                else ""
            ),
            "league": (
                parsed_stats[0]["league"]
                if parsed_stats
                else ""
            ),
        },
        "statistics": parsed_stats,
    }


# ------------------------------------------------------------------
# Understat xG
# ------------------------------------------------------------------


async def _fetch_understat_xg(
    player_name: str, league_country: str
) -> dict[str, Any]:
    """Fetch xG data from Understat by scraping player page."""
    league_map = {
        "England": "EPL",
        "Spain": "La_Liga",
        "Germany": "Bundesliga",
        "Italy": "Serie_A",
        "France": "Ligue_1",
    }
    understat_league = league_map.get(league_country)
    if not understat_league:
        return {"xg_data": []}

    settings = get_settings()
    headers = {"User-Agent": settings.user_agent}

    try:
        async with httpx.AsyncClient(
            timeout=15, headers=headers
        ) as client:
            resp = await client.get(
                f"https://understat.com/league/{understat_league}"
            )
            resp.raise_for_status()
            html = resp.text

        name_parts = player_name.lower().split()
        last_name = name_parts[-1] if name_parts else ""

        pattern = r'href="/player/(\d+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html)

        understat_id: int | None = None
        for uid, uname in matches:
            if last_name in uname.lower():
                understat_id = int(uid)
                break

        if understat_id is None:
            return {"xg_data": []}

        async with httpx.AsyncClient(
            timeout=15, headers=headers
        ) as client:
            resp = await client.get(
                f"https://understat.com/player/{understat_id}"
            )
            resp.raise_for_status()
            html = resp.text

        pat = r"var groupsData\s*=\s*JSON\.parse\('(.+?)'\)"
        match = re.search(pat, html)
        if not match:
            return {"understat_id": understat_id, "xg_data": []}

        raw = match.group(1).encode().decode("unicode_escape")
        groups = json.loads(raw)

        season_data = groups.get("season", [])
        xg_out: list[dict[str, Any]] = []
        for s in season_data:
            xg_out.append(
                {
                    "season": s.get("season", ""),
                    "games": _safe_int(s.get("games")),
                    "goals": _safe_int(s.get("goals")),
                    "assists": _safe_int(s.get("assists")),
                    "xG": _safe_float(s.get("xG")),
                    "xA": _safe_float(s.get("xA")),
                    "npg": _safe_int(s.get("npg")),
                    "npxG": _safe_float(s.get("npxG")),
                    "xG_chain": _safe_float(s.get("xGChain")),
                    "xG_buildup": _safe_float(
                        s.get("xGBuildup")
                    ),
                }
            )

        return {"understat_id": understat_id, "xg_data": xg_out}
    except Exception:
        return {"xg_data": []}


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/search")
async def search_players(q: str) -> list[dict[str, Any]]:
    """Search players by name via ESPN (current season, all leagues)."""
    if len(q) < 2:
        raise HTTPException(
            status_code=400,
            detail="Query must be at least 2 characters.",
        )

    async with httpx.AsyncClient(timeout=15) as client:
        items = await _espn_search(client, q)

    results: list[dict[str, Any]] = []
    for item in items:
        if item.get("type") != "player":
            continue
        results.append(_parse_espn_search_result(item))

    return results[:20]


@router.get("/player/{player_id}")
async def get_player_stats(
    player_id: str,
    season: int | None = None,
    league: str | None = None,
) -> dict[str, Any]:
    """Get stats for a player.

    Uses ESPN for current season (default).
    If season is specified and API-Football key is available,
    fetches deeper historical stats from API-Football.
    """
    settings = get_settings()

    # For historical seasons, try API-Football
    if season and settings.api_football_key:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout
        ) as client:
            af_data = await _af_player_stats(
                client, int(player_id), season
            )
        if af_data:
            result = _parse_af_stats(af_data)
            result["season"] = season
            result["source"] = "api-football"
            return result

    # Default: ESPN current season
    league_slug = league or "eng.1"

    # Try each league if the first fails
    leagues_to_try = (
        [league_slug]
        if league_slug not in _ESPN_LEAGUES
        else [league_slug]
        + [lg for lg in _ESPN_LEAGUES if lg != league_slug]
    )

    async with httpx.AsyncClient(timeout=15) as client:
        for slug in leagues_to_try:
            athlete = await _espn_player_detail(
                client, player_id, slug
            )
            if athlete and athlete.get("statsSummary"):
                result = _parse_espn_stats(athlete)
                result["season"] = "current"
                result["source"] = "espn"
                return result

    raise HTTPException(
        status_code=404,
        detail="Player not found.",
    )


@router.get("/player/{player_id}/xg")
async def get_player_xg(
    player_id: str,
    league: str | None = None,
) -> dict[str, Any]:
    """Get xG data from Understat (Big 5 leagues only)."""
    # Get player name from ESPN first
    league_slug = league or "eng.1"

    async with httpx.AsyncClient(timeout=15) as client:
        athlete = await _espn_player_detail(
            client, player_id, league_slug
        )

    if not athlete:
        return {"player_id": player_id, "xg_data": []}

    player_name = athlete.get("displayName", "")
    # Map ESPN league slug to country
    country_map = {
        "eng.1": "England",
        "eng.2": "England",
        "esp.1": "Spain",
        "ger.1": "Germany",
        "ita.1": "Italy",
        "fra.1": "France",
    }
    country = country_map.get(league_slug, "")

    xg_result = await _fetch_understat_xg(player_name, country)
    return {"player_id": player_id, **xg_result}
