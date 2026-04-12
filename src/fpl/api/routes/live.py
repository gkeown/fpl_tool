"""Live FPL gameweek endpoint.

Returns fixtures for the current gameweek with goal scorers, assisters,
top BPS leaders, and top DEFCON contributors — all computed from the
FPL live endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from fpl.analysis.form import get_current_gameweek
from fpl.cli.formatters import position_str
from fpl.db.engine import get_session
from fpl.db.models import Fixture, Player, Team

router = APIRouter()

# In-memory cache
_live_cache: dict[str, Any] = {}
_live_cache_updated_at: str = ""


async def fetch_live_gameweek() -> dict[str, Any]:
    """Build the live gameweek response from DB + FPL live endpoint."""
    with get_session() as session:
        current_gw = get_current_gameweek(session)
        if not current_gw:
            return {"gameweek": None, "fixtures": []}

        fixtures: list[Fixture] = (
            session.query(Fixture)
            .filter(Fixture.gameweek == current_gw)
            .order_by(Fixture.kickoff_time)
            .all()
        )
        teams = session.query(Team).all()

        # Snapshot fixture data inside session
        fixture_snapshots: list[dict[str, Any]] = [
            {
                "fpl_id": f.fpl_id,
                "kickoff_time": f.kickoff_time,
                "finished": f.finished,
                "team_h": f.team_h,
                "team_a": f.team_a,
                "team_h_score": f.team_h_score,
                "team_a_score": f.team_a_score,
            }
            for f in fixtures
        ]
        team_snapshots: dict[int, dict[str, Any]] = {
            t.fpl_id: {"name": t.name, "short_name": t.short_name}
            for t in teams
        }
        players = session.query(Player).all()
        player_snapshots: dict[int, dict[str, Any]] = {
            p.fpl_id: {
                "web_name": p.web_name,
                "team_id": p.team_id,
                "element_type": p.element_type,
            }
            for p in players
        }

    # Fetch live data (outside session — async)
    live_raw = await _fetch_live_gw_with_explain(current_gw)

    now_iso = datetime.now(UTC).isoformat()

    fixtures_out: list[dict[str, Any]] = []
    for fs in fixture_snapshots:
        home = team_snapshots.get(fs["team_h"])
        away = team_snapshots.get(fs["team_a"])
        if not home or not away:
            continue

        # Status
        if fs["finished"]:
            status = "finished"
        elif fs["kickoff_time"] and fs["kickoff_time"] <= now_iso:
            status = "in"
        else:
            status = "scheduled"

        # Collect players in this fixture from live data.
        # For DGW correctness, parse per-fixture stats from the
        # `explain[].stats` breakdown rather than the aggregated
        # top-level stats dict.
        fixture_players: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for pid, entry in live_raw.items():
            explain = entry.get("explain", [])
            # Find the explain entry for this specific fixture
            fix_explain = next(
                (
                    e
                    for e in explain
                    if e.get("fixture") == fs["fpl_id"]
                ),
                None,
            )
            if fix_explain is None:
                continue

            # Build per-fixture stats from identifier/value pairs
            per_fix_stats: dict[str, int] = {}
            per_fix_points = 0
            for s in fix_explain.get("stats", []):
                ident = s.get("identifier", "")
                per_fix_stats[ident] = s.get("value", 0) or 0
                per_fix_points += s.get("points", 0) or 0

            p = player_snapshots.get(pid)
            if p:
                fixture_players.append(
                    (
                        p,
                        {
                            "bps": per_fix_stats.get("bps", 0),
                            "bonus": per_fix_stats.get("bonus", 0),
                            "goals_scored": per_fix_stats.get(
                                "goals_scored", 0
                            ),
                            "assists": per_fix_stats.get("assists", 0),
                            "defensive_contribution": per_fix_stats.get(
                                "defensive_contribution", 0
                            ),
                            "total_points": per_fix_points,
                        },
                    )
                )

        # Goal scorers
        goal_scorers: list[dict[str, Any]] = []
        assisters: list[dict[str, Any]] = []
        for p, stats in fixture_players:
            team_info = team_snapshots.get(p["team_id"], {})
            team_short = team_info.get("short_name", "?")
            for _ in range(stats.get("goals_scored", 0) or 0):
                goal_scorers.append(
                    {
                        "player": p["web_name"],
                        "team": team_short,
                    }
                )
            for _ in range(stats.get("assists", 0) or 0):
                assisters.append(
                    {
                        "player": p["web_name"],
                        "team": team_short,
                    }
                )

        # Top 3 BPS
        top_bps_sorted = sorted(
            fixture_players,
            key=lambda t: t[1].get("bps", 0) or 0,
            reverse=True,
        )[:3]
        top_bps = []
        for p, stats in top_bps_sorted:
            bps = stats.get("bps", 0) or 0
            if bps <= 0:
                continue
            team_info = team_snapshots.get(p["team_id"], {})
            top_bps.append(
                {
                    "player": p["web_name"],
                    "team": team_info.get("short_name", "?"),
                    "position": position_str(p["element_type"]),
                    "bps": bps,
                    "bonus": stats.get("bonus", 0) or 0,
                    "points": stats.get("total_points", 0) or 0,
                }
            )

        # Top 3 DEFCON
        top_defcon_sorted = sorted(
            (
                (p, stats)
                for p, stats in fixture_players
                if (stats.get("defensive_contribution", 0) or 0) > 0
            ),
            key=lambda t: t[1].get("defensive_contribution", 0) or 0,
            reverse=True,
        )[:3]
        top_defcon = []
        for p, stats in top_defcon_sorted:
            team_info = team_snapshots.get(p["team_id"], {})
            top_defcon.append(
                {
                    "player": p["web_name"],
                    "team": team_info.get("short_name", "?"),
                    "position": position_str(p["element_type"]),
                    "defcon": stats.get("defensive_contribution", 0) or 0,
                }
            )

        fixtures_out.append(
            {
                "fixture_id": fs["fpl_id"],
                "kickoff_time": fs["kickoff_time"],
                "status": status,
                "home_team": home["name"],
                "home_team_short": home["short_name"],
                "home_score": fs["team_h_score"],
                "away_team": away["name"],
                "away_team_short": away["short_name"],
                "away_score": fs["team_a_score"],
                "goal_scorers": goal_scorers,
                "assisters": assisters,
                "top_bps": top_bps,
                "top_defcon": top_defcon,
            }
        )

    return {
        "gameweek": current_gw,
        "fixtures": fixtures_out,
    }


async def _fetch_live_gw_with_explain(
    gw: int,
) -> dict[int, dict[str, Any]]:
    """Fetch live GW data from FPL API, keeping explain + stats."""
    import httpx

    from fpl.config import get_settings

    settings = get_settings()
    headers = {"User-Agent": settings.user_agent}
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            url = f"{settings.fpl_base_url}/event/{gw}/live/"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return {
                el["id"]: {
                    "stats": el.get("stats", {}),
                    "explain": el.get("explain", []),
                }
                for el in data.get("elements", [])
            }
    except Exception:
        return {}


_CACHE_MAX_AGE_SECS = 300  # 5 min — avoid serving stale data indefinitely


async def refresh_live_cache() -> None:
    """Refresh the in-memory live gameweek cache.

    If the fetch returns an empty/failed result, keep the existing
    cache rather than overwriting with stale empty data.
    """
    global _live_cache, _live_cache_updated_at
    result = await fetch_live_gameweek()
    # Don't clobber good cache with empty response on transient failures
    if not result.get("fixtures") and _live_cache.get("fixtures"):
        return
    _live_cache = result
    _live_cache_updated_at = datetime.now(UTC).isoformat()


def _cache_is_fresh() -> bool:
    """Check if the cache is within the max age window."""
    if not _live_cache or not _live_cache_updated_at:
        return False
    try:
        updated = datetime.fromisoformat(_live_cache_updated_at)
        age = (datetime.now(UTC) - updated).total_seconds()
        return age < _CACHE_MAX_AGE_SECS
    except (ValueError, TypeError):
        return False


def _cache_gw_matches(current_gw: int | None) -> bool:
    """Check if the cached GW matches the current GW."""
    if not _live_cache:
        return False
    return _live_cache.get("gameweek") == current_gw


@router.get("/gameweek")
async def get_live_gameweek(force: bool = False) -> dict[str, Any]:
    """Return current gameweek fixtures with live stats.

    Serves from cache when fresh. Re-fetches when:
    - force=true
    - cache is empty
    - cache is older than 5 minutes
    - cached gameweek differs from current (GW rollover)
    """
    global _live_cache, _live_cache_updated_at

    # Determine current GW for cache invalidation
    with get_session() as session:
        current_gw = get_current_gameweek(session)

    use_cache = (
        not force
        and _cache_is_fresh()
        and _cache_gw_matches(current_gw)
    )
    if use_cache:
        return {**_live_cache, "cached_at": _live_cache_updated_at}

    result = await fetch_live_gameweek()
    # Only update cache if fetch produced non-empty data
    if result.get("fixtures") or not _live_cache.get("fixtures"):
        _live_cache = result
        _live_cache_updated_at = datetime.now(UTC).isoformat()

    return {**result, "cached_at": _live_cache_updated_at}
