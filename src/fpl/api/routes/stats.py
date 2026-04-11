"""Player statistics search via API-Football + Understat xG data."""

from __future__ import annotations

import contextlib
import re
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from fpl.config import get_settings

router = APIRouter()


async def _api_football_get(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    """Call API-Football and return the response array."""
    settings = get_settings()
    if not settings.api_football_key:
        raise HTTPException(
            status_code=503,
            detail="API-Football key not configured. Set FPL_API_FOOTBALL_KEY in .env.",
        )
    url = f"{settings.api_football_base_url}{path}"
    headers = {"x-apisports-key": settings.api_football_key}
    resp = await client.get(url, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", [])  # type: ignore[no-any-return]


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


def _parse_player_info(entry: dict[str, Any]) -> dict[str, Any]:
    """Parse player profile from API-Football response."""
    p = entry.get("player", {})
    stats = entry.get("statistics", [])
    first_stat = stats[0] if stats else {}
    team = first_stat.get("team", {})
    league = first_stat.get("league", {})
    games = first_stat.get("games", {})

    return {
        "id": p.get("id"),
        "name": p.get("name", ""),
        "firstname": p.get("firstname", ""),
        "lastname": p.get("lastname", ""),
        "age": p.get("age"),
        "nationality": p.get("nationality", ""),
        "height": p.get("height", ""),
        "weight": p.get("weight", ""),
        "photo": p.get("photo", ""),
        "team": team.get("name", ""),
        "team_logo": team.get("logo", ""),
        "league": league.get("name", ""),
        "league_country": league.get("country", ""),
        "position": games.get("position", ""),
    }


def _parse_season_stats(
    stats_list: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse per-competition stats for a season."""
    result: list[dict[str, Any]] = []
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

        result.append(
            {
                "team": team.get("name", ""),
                "league": league.get("name", ""),
                "league_country": league.get("country", ""),
                "season": league.get("season"),
                "position": games.get("position", ""),
                "rating": _safe_float(games.get("rating")),
                "appearances": _safe_int(games.get("appearences")),
                "lineups": _safe_int(games.get("lineups")),
                "minutes": _safe_int(games.get("minutes")),
                "goals": _safe_int(goals.get("total")),
                "assists": _safe_int(goals.get("assists")),
                "goals_conceded": _safe_int(goals.get("conceded")),
                "saves": _safe_int(goals.get("saves")),
                "shots_total": _safe_int(shots.get("total")),
                "shots_on": _safe_int(shots.get("on")),
                "passes_total": _safe_int(passes.get("total")),
                "passes_key": _safe_int(passes.get("key")),
                "passes_accuracy": _safe_int(passes.get("accuracy")),
                "tackles": _safe_int(tackles.get("total")),
                "blocks": _safe_int(tackles.get("blocks")),
                "interceptions": _safe_int(tackles.get("interceptions")),
                "duels_total": _safe_int(duels.get("total")),
                "duels_won": _safe_int(duels.get("won")),
                "dribbles_attempts": _safe_int(dribbles.get("attempts")),
                "dribbles_success": _safe_int(dribbles.get("success")),
                "fouls_drawn": _safe_int(fouls.get("drawn")),
                "fouls_committed": _safe_int(fouls.get("committed")),
                "yellow_cards": _safe_int(cards.get("yellow")),
                "red_cards": _safe_int(cards.get("red")),
                "penalty_won": _safe_int(penalty.get("won")),
                "penalty_scored": _safe_int(penalty.get("scored")),
                "penalty_missed": _safe_int(penalty.get("missed")),
                "penalty_saved": _safe_int(penalty.get("saved")),
            }
        )
    return result


@router.get("/search")
async def search_players(q: str) -> list[dict[str, Any]]:
    """Search players by name across all leagues."""
    if len(q) < 2:
        raise HTTPException(
            status_code=400, detail="Query must be at least 2 characters."
        )

    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        entries = await _api_football_get(
            client,
            "/players",
            {"search": q, "season": str(settings.api_football_season)},
        )

    return [_parse_player_info(e) for e in entries[:20]]


@router.get("/player/{player_id}")
async def get_player_stats(
    player_id: int, season: int | None = None
) -> dict[str, Any]:
    """Get full season stats for a player."""
    settings = get_settings()
    target_season = season or settings.api_football_season

    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        entries = await _api_football_get(
            client,
            "/players",
            {"id": str(player_id), "season": str(target_season)},
        )

    if not entries:
        raise HTTPException(
            status_code=404, detail="Player not found for this season."
        )

    entry = entries[0]
    player_info = _parse_player_info(entry)
    stats = _parse_season_stats(entry.get("statistics", []))

    return {
        "player": player_info,
        "season": target_season,
        "statistics": stats,
    }


@router.get("/player/{player_id}/xg")
async def get_player_xg(player_id: int) -> dict[str, Any]:
    """Get xG data from Understat for a player (Big 5 leagues only).

    Attempts to find the player on Understat by name match.
    Returns empty data if not found.
    """
    settings = get_settings()

    # First get the player name from API-Football
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        entries = await _api_football_get(
            client,
            "/players",
            {
                "id": str(player_id),
                "season": str(settings.api_football_season),
            },
        )

    if not entries:
        return {"player_id": player_id, "xg_data": []}

    player_name = entries[0].get("player", {}).get("name", "")
    if not player_name:
        return {"player_id": player_id, "xg_data": []}

    # Search Understat for the player
    # Understat uses its own IDs, so we search by name on the league page
    league_map = {
        "England": "EPL",
        "Spain": "La_Liga",
        "Germany": "Bundesliga",
        "Italy": "Serie_A",
        "France": "Ligue_1",
    }

    league_country = ""
    stats = entries[0].get("statistics", [])
    if stats:
        league_country = stats[0].get("league", {}).get("country", "")

    understat_league = league_map.get(league_country)
    if not understat_league:
        return {"player_id": player_id, "xg_data": []}

    # Try to find on Understat by scraping the league page
    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            resp = await client.get(
                f"https://understat.com/league/{understat_league}"
            )
            resp.raise_for_status()
            html = resp.text

        # Find player links matching the name
        # Pattern: /player/{id}
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
            return {"player_id": player_id, "xg_data": []}

        # Fetch player page for xG data
        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            resp = await client.get(
                f"https://understat.com/player/{understat_id}"
            )
            resp.raise_for_status()
            html = resp.text

        # Extract groupsData JSON from script tag
        import json

        pattern = r"var groupsData\s*=\s*JSON\.parse\('(.+?)'\)"
        match = re.search(pattern, html)
        if not match:
            return {
                "player_id": player_id,
                "understat_id": understat_id,
                "xg_data": [],
            }

        raw = match.group(1).encode().decode("unicode_escape")
        groups = json.loads(raw)

        # Extract per-season xG summary
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
                    "xG_buildup": _safe_float(s.get("xGBuildup")),
                }
            )

        return {
            "player_id": player_id,
            "understat_id": understat_id,
            "xg_data": xg_out,
        }
    except Exception:
        return {"player_id": player_id, "xg_data": []}
