"""Live FPL gameweek endpoint.

Returns fixtures for the current gameweek with goal scorers, assisters,
top BPS leaders, and top DEFCON contributors — all computed from the
FPL live endpoint.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter

from fpl.analysis.form import get_current_gameweek
from fpl.cache.live_gw import get_live_gw, invalidate as _invalidate_live_cache
from fpl.cli.formatters import position_str
from fpl.config import get_settings
from fpl.db.engine import get_session
from fpl.db.models import Fixture, Player, Team

router = APIRouter()

# Last-fetched timestamp — read by data.py for the Settings page
_live_cache_updated_at: str = ""


def _load_db_snapshot() -> (
    tuple[
        int | None,
        list[dict[str, Any]],
        dict[int, dict[str, Any]],
        dict[int, dict[str, Any]],
    ]
):
    """Load gameweek, fixtures, teams, and players from DB.

    Returns:
        Tuple of (current_gw, fixture_snapshots, team_snapshots, player_snapshots).
        current_gw is None when no current gameweek exists.
    """
    with get_session() as session:
        current_gw = get_current_gameweek(session)
        if not current_gw:
            return None, [], {}, {}

        fixtures: list[Fixture] = (
            session.query(Fixture)
            .filter(Fixture.gameweek == current_gw)
            .order_by(Fixture.kickoff_time)
            .all()
        )
        teams = session.query(Team).all()

        fixture_snapshots: list[dict[str, Any]] = [
            {
                "fpl_id": f.fpl_id,
                "kickoff_time": f.kickoff_time,
                "finished": f.finished or f.finished_provisional,
                "team_h": f.team_h,
                "team_a": f.team_a,
                "team_h_score": f.team_h_score,
                "team_a_score": f.team_a_score,
            }
            for f in fixtures
        ]
        team_snapshots: dict[int, dict[str, Any]] = {
            t.fpl_id: {"name": t.name, "short_name": t.short_name} for t in teams
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

    return current_gw, fixture_snapshots, team_snapshots, player_snapshots


async def fetch_live_gameweek() -> dict[str, Any]:
    """Build the live gameweek response from DB + FPL live endpoint."""
    current_gw, fixture_snapshots, team_snapshots, player_snapshots = (
        await asyncio.to_thread(_load_db_snapshot)
    )

    if not current_gw:
        return {"gameweek": None, "fixtures": []}

    # Fetch live data (outside session — async, shared cache)
    live_raw = await get_live_gw(current_gw, _fetch_live_gw_with_explain)

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
        # For DGW correctness, parse per-fixture stats from
        # `explain[].stats` breakdown. Note that `bps` is NOT in the
        # explain breakdown (only point-awarding events are), so we
        # fall back to top-level `stats.bps` — correct for single-GW
        # players, best-effort for the rare DGW case.
        fixture_players: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for pid, entry in live_raw.items():
            explain = entry.get("explain", [])
            top_stats = entry.get("stats", {})

            # Find the explain entry for this specific fixture
            fix_explain = next(
                (e for e in explain if e.get("fixture") == fs["fpl_id"]),
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

            # BPS is not in the explain breakdown — pull from top-level stats.
            # Bonus is computed from BPS rankings after all players are
            # collected (see _compute_provisional_bonus below).
            # top_stats.bps is always the total accumulated BPS for this GW,
            # which is correct even for DGW players (both fixtures combined).
            is_single_fixture = len(explain) == 1
            bps = top_stats.get("bps", 0) or 0

            p = player_snapshots.get(pid)
            if p:
                fixture_players.append(
                    (
                        p,
                        {
                            "bps": bps,
                            "bonus": entry.get("provisional_bonus", 0),
                            "goals_scored": per_fix_stats.get("goals_scored", 0),
                            "assists": per_fix_stats.get("assists", 0),
                            "defensive_contribution": per_fix_stats.get(
                                "defensive_contribution", 0
                            ),
                            "minutes": (
                                top_stats.get("minutes", 0) or 0
                                if is_single_fixture
                                else per_fix_stats.get("minutes", 0)
                            ),
                            "saves": top_stats.get("saves", 0) or 0,
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

        # Top DEFCON — only players who meet the scoring threshold:
        # DEF/GK need >= 10 CBIT, MID/FWD need >= 12
        def _meets_defcon(element_type: int, defcon_value: int) -> bool:
            threshold = 10 if element_type <= 2 else 12
            return defcon_value >= threshold

        top_defcon_sorted = sorted(
            (
                (p, stats)
                for p, stats in fixture_players
                if _meets_defcon(
                    p["element_type"],
                    stats.get("defensive_contribution", 0) or 0,
                )
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

        # GK saves — element_type 1 = GKP
        gk_saves: list[dict[str, Any]] = []
        for p, stats in fixture_players:
            if p["element_type"] != 1:
                continue
            saves = stats.get("saves", 0) or 0
            if saves <= 0:
                continue
            team_info = team_snapshots.get(p["team_id"], {})
            gk_saves.append(
                {
                    "player": p["web_name"],
                    "team": team_info.get("short_name", "?"),
                    "saves": saves,
                }
            )

        match_minute = (
            max(
                (s.get("minutes", 0) or 0 for _, s in fixture_players),
                default=0,
            )
            if status == "in"
            else 0
        )

        fixtures_out.append(
            {
                "fixture_id": fs["fpl_id"],
                "kickoff_time": fs["kickoff_time"],
                "status": status,
                "match_minute": match_minute,
                "home_team": home["name"],
                "home_team_short": home["short_name"],
                "home_score": fs["team_h_score"],
                "away_team": away["name"],
                "away_team_short": away["short_name"],
                "away_score": fs["team_a_score"],
                "goal_scorers": goal_scorers,
                "assisters": assisters,
                "gk_saves": gk_saves,
                "top_bps": top_bps,
                "top_defcon": top_defcon,
            }
        )

    return {
        "gameweek": current_gw,
        "fixtures": fixtures_out,
    }


def _compute_provisional_bonus(
    players_by_bps: list[tuple[int, int]],
) -> dict[int, int]:
    """Compute provisional bonus from BPS rankings.

    Mirrors the algorithm in team.py so both views stay consistent.
    Uses standard ranking with gaps: a 2-way tie for 1st means the
    next distinct BPS value is 3rd, not 2nd.
    """
    sorted_players = sorted(
        [(pid, bps) for pid, bps in players_by_bps if bps > 0],
        key=lambda x: -x[1],
    )
    if not sorted_players:
        return {}
    result: dict[int, int] = {}
    rank_points = [3, 2, 1]
    i = 0
    rank_idx = 0
    n = len(sorted_players)
    while i < n and rank_idx < 3:
        cur_bps = sorted_players[i][1]
        tied: list[int] = [sorted_players[i][0]]
        j = i + 1
        while j < n and sorted_players[j][1] == cur_bps:
            tied.append(sorted_players[j][0])
            j += 1
        points = rank_points[rank_idx]
        for pid in tied:
            result[pid] = points
        rank_idx += len(tied)
        i = j
    return result


async def _fetch_live_gw_with_explain(
    gw: int,
) -> dict[int, dict[str, Any]]:
    """Fetch live GW data from FPL API, keeping explain + stats.

    Provisional bonus is computed here from ALL players in each fixture
    (not filtered by our DB) so the ranking matches what FPL shows.
    """
    settings = get_settings()
    headers = {
        "User-Agent": settings.user_agent,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            # Timestamp param forces a unique URL on every request,
            # bypassing CDN edge caches that ignore Cache-Control headers.
            url = f"{settings.fpl_base_url}/event/{gw}/live/?_={int(time.time())}"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            elements = data.get("elements", [])

            # Group all players by fixture and compute provisional bonus
            # using every player FPL knows about — matches My Team's approach.
            by_fixture: dict[int, list[tuple[int, int]]] = {}
            for el in elements:
                explain = el.get("explain", [])
                if not explain:
                    continue
                fixture_id = explain[0].get("fixture")
                if fixture_id is None:
                    continue
                bps = el.get("stats", {}).get("bps", 0) or 0
                by_fixture.setdefault(fixture_id, []).append((el["id"], bps))

            provisional: dict[int, int] = {}
            for _fid, players in by_fixture.items():
                provisional.update(_compute_provisional_bonus(players))

            return {
                el["id"]: {
                    "stats": el.get("stats", {}),
                    "explain": el.get("explain", []),
                    "provisional_bonus": provisional.get(el["id"], 0),
                }
                for el in elements
            }
    except Exception:
        return {}


async def refresh_live_cache() -> None:
    """Called by the scheduler during match windows.

    Invalidates the in-memory cache first so the next fetch always
    goes to FPL, then warms the cache and updates the Settings timestamp.
    """
    global _live_cache_updated_at
    # Load current GW to know which cache key to bust
    current_gw, *_ = await asyncio.to_thread(_load_db_snapshot)
    if current_gw:
        _invalidate_live_cache(current_gw)
    await fetch_live_gameweek()
    _live_cache_updated_at = datetime.now(UTC).isoformat()


@router.get("/gameweek")
async def get_live_gameweek() -> dict[str, Any]:
    """Return current gameweek fixtures with live stats from FPL API."""
    global _live_cache_updated_at
    result = await fetch_live_gameweek()
    now = datetime.now(UTC).isoformat()
    _live_cache_updated_at = now
    return {**result, "fetched_at": now}
