from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from fpl.analysis.form import get_current_gameweek
from fpl.cli.formatters import position_str
from fpl.config import get_settings
from fpl.db.engine import get_session
from fpl.db.models import (
    Fixture,
    League,
    LeagueEntry,
    Player,
    Team,
)

router = APIRouter()


@router.get("")
def list_leagues() -> list[dict[str, Any]]:
    """List all subscribed leagues."""
    with get_session() as session:
        leagues: list[League] = session.query(League).all()
        return [
            {
                "league_id": lg.league_id,
                "name": lg.name,
                "entry_count": len(lg.entries),
                "fetched_at": lg.fetched_at,
            }
            for lg in leagues
        ]


@router.post("")
async def add_league(league_id: int) -> dict[str, Any]:
    """Subscribe to a league by ID. Fetches standings from FPL API."""
    settings = get_settings()
    headers = {"User-Agent": settings.user_agent}

    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            from fpl.ingest.leagues import fetch_league_standings, upsert_league

            data = await fetch_league_standings(client, settings, league_id)

            with get_session() as session:
                count = upsert_league(session, league_id, data)

        league_name = data.get("league", {}).get("name", f"League {league_id}")
        return {
            "status": "ok",
            "league_id": league_id,
            "name": league_name,
            "entries": count,
        }
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"League {league_id} not found on FPL.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch league {league_id}: {exc}",
        ) from exc


@router.delete("/{league_id}")
def remove_league(league_id: int) -> dict[str, str]:
    """Unsubscribe from a league."""
    with get_session() as session:
        league: League | None = session.get(League, league_id)
        if not league:
            raise HTTPException(status_code=404, detail="League not found.")
        session.delete(league)
    return {"status": "ok", "message": f"League {league_id} removed."}


@router.get("/{league_id}/standings")
async def get_standings(
    league_id: int, force: bool = False
) -> dict[str, Any]:
    """Return league standings. Re-fetches if stale (>1hr) or force=true."""
    with get_session() as session:
        league: League | None = session.get(League, league_id)
        if not league:
            raise HTTPException(status_code=404, detail="League not subscribed.")

        # Check staleness
        stale = force
        if not stale:
            try:
                fetched = datetime.fromisoformat(league.fetched_at)
                if fetched.tzinfo is None:
                    fetched = fetched.replace(tzinfo=UTC)
                age = (datetime.now(UTC) - fetched).total_seconds()
                stale = age > 3600
            except (ValueError, TypeError):
                stale = True

    if stale:
        settings = get_settings()
        headers = {"User-Agent": settings.user_agent}
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            from fpl.ingest.leagues import fetch_league_standings, upsert_league

            data = await fetch_league_standings(client, settings, league_id)
            with get_session() as session:
                upsert_league(session, league_id, data)

    with get_session() as session:
        league = session.get(League, league_id)
        entries: list[LeagueEntry] = (
            session.query(LeagueEntry)
            .filter(LeagueEntry.league_id == league_id)
            .order_by(LeagueEntry.rank)
            .all()
        )

        return {
            "league_id": league_id,
            "name": league.name if league else "",
            "fetched_at": league.fetched_at if league else "",
            "standings": [
                {
                    "entry_id": e.entry_id,
                    "player_name": e.player_name,
                    "entry_name": e.entry_name,
                    "rank": e.rank,
                    "total": e.total,
                    "event_total": e.event_total,
                }
                for e in entries
            ],
        }


@router.get("/{league_id}/entry/{entry_id}")
async def get_league_entry(league_id: int, entry_id: int) -> dict[str, Any]:
    """Fetch an opponent's full team (live from FPL API)."""
    settings = get_settings()
    headers = {"User-Agent": settings.user_agent}

    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            from fpl.ingest.fpl_api import (
                fetch_entry,
                fetch_entry_history,
                fetch_entry_picks,
            )
            from fpl.ingest.leagues import fetch_entry_transfers

            entry = await fetch_entry(client, settings, entry_id)
            current_gw = entry.get("current_event", 1)
            picks = await fetch_entry_picks(
                client, settings, entry_id, current_gw
            )
            transfers = await fetch_entry_transfers(
                client, settings, entry_id
            )
            history = await fetch_entry_history(
                client, settings, entry_id
            )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch team {entry_id}: {exc}",
        ) from exc

    pick_list = picks.get("picks", [])
    entry_history = picks.get("entry_history", {})
    player_ids = [p["element"] for p in pick_list]

    with get_session() as session:
        current_gw_db = get_current_gameweek(session)

        # Fetch player + team data
        player_rows = (
            session.query(Player, Team)
            .join(Team, Team.fpl_id == Player.team_id)
            .filter(Player.fpl_id.in_(player_ids))
            .all()
        )
        player_map: dict[int, tuple[Player, Team]] = {
            p.fpl_id: (p, t) for p, t in player_rows
        }

        # Build opponent + live fixture lookup from current GW fixtures
        all_teams = {
            t.fpl_id: t.short_name
            for t in session.query(Team).all()
        }
        gw_fixtures: list[Fixture] = (
            session.query(Fixture)
            .filter(Fixture.gameweek == current_gw_db)
            .all()
        )
        now_iso = datetime.now(UTC).isoformat()
        opponent_lookup: dict[int, tuple[str, bool]] = {}
        live_team_ids: set[int] = set()
        for fix in gw_fixtures:
            opponent_lookup[fix.team_h] = (
                all_teams.get(fix.team_a, "?"),
                True,
            )
            opponent_lookup[fix.team_a] = (
                all_teams.get(fix.team_h, "?"),
                False,
            )
            if (
                fix.kickoff_time
                and fix.kickoff_time <= now_iso
                and not fix.finished
                and not fix.finished_provisional
            ):
                live_team_ids.add(fix.team_h)
                live_team_ids.add(fix.team_a)

        # Resolve transfer player names
        all_transfer_pids: set[int] = set()
        for t in transfers:
            all_transfer_pids.add(t["element_in"])
            all_transfer_pids.add(t["element_out"])
        transfer_players: list[Player] = (
            session.query(Player)
            .filter(Player.fpl_id.in_(all_transfer_pids))
            .all()
            if all_transfer_pids
            else []
        )
        name_lookup: dict[int, str] = {
            p.fpl_id: p.web_name for p in transfer_players
        }

        # Fetch live GW data for bonus + defcon
        from fpl.api.routes.team import _fetch_live_gw

        live_data = await _fetch_live_gw(current_gw_db)

        # Build player dicts while session is still open
        players_out: list[dict[str, Any]] = []
        for pick in pick_list:
            pid = pick["element"]
            pd = player_map.get(pid)
            if not pd:
                continue
            player, tm = pd
            multiplier = pick.get("multiplier", 1)
            live_stats = live_data.get(pid, {})
            live_pts = live_stats.get("total_points")
            event_pts = (
                live_pts
                if live_pts is not None
                else (player.event_points or 0)
            )
            opp = opponent_lookup.get(player.team_id)
            opp_str = (
                f"{opp[0]} (H)" if opp and opp[1]
                else f"{opp[0]} (A)" if opp
                else "-"
            )

            players_out.append(
                {
                    "id": player.fpl_id,
                    "web_name": player.web_name,
                    "team": tm.short_name,
                    "position": position_str(player.element_type),
                    "cost": float(player.now_cost) / 10,
                    "form": float(player.form),
                    "opponent": opp_str,
                    "event_points": event_pts,
                    "gw_points": event_pts * multiplier,
                    "gw_bonus": (
                        live_stats.get("bonus", 0)
                        or live_stats.get("provisional_bonus", 0)
                        or 0
                    ),
                    "defcon": live_stats.get(
                        "defensive_contribution", 0
                    ),
                    "yellow_cards": live_stats.get("yellow_cards", 0),
                    "red_cards": live_stats.get("red_cards", 0),
                    "xgi": round(
                        float(
                            live_stats.get(
                                "expected_goal_involvements", "0"
                            )
                            or 0
                        ),
                        2,
                    ),
                    "minutes": live_stats.get("minutes", 0),
                    "is_playing": (
                        player.team_id in live_team_ids
                        and live_stats.get("minutes", 0) > 0
                    ),
                    "fixture_live": player.team_id in live_team_ids,
                    "status": player.status,
                    "chance_of_playing": player.chance_of_playing_next,
                    "news": player.news,
                    "is_starter": pick["position"] <= 11,
                    "squad_position": pick["position"],
                    "is_captain": pick.get("is_captain", False),
                    "is_vice_captain": pick.get("is_vice_captain", False),
                    "multiplier": multiplier,
                }
            )

    transfers_out: list[dict[str, Any]] = [
        {
            "event": t["event"],
            "element_in": t["element_in"],
            "element_in_name": name_lookup.get(
                t["element_in"], f"ID {t['element_in']}"
            ),
            "element_in_cost": t["element_in_cost"],
            "element_out": t["element_out"],
            "element_out_name": name_lookup.get(
                t["element_out"], f"ID {t['element_out']}"
            ),
            "element_out_cost": t["element_out_cost"],
            "time": t.get("time", ""),
        }
        for t in sorted(
            transfers, key=lambda x: x.get("time", ""), reverse=True
        )
    ]

    manager_name = (
        f"{entry.get('player_first_name', '')} "
        f"{entry.get('player_last_name', '')}"
    ).strip()

    return {
        "entry_id": entry_id,
        "manager_name": manager_name,
        "team_name": entry.get("name", ""),
        "gameweek": current_gw,
        "gameweek_points": entry.get("summary_event_points", 0),
        "overall_points": entry.get("summary_overall_points", 0),
        "overall_rank": entry.get("summary_overall_rank", 0),
        "bank": entry_history.get("bank", 0) / 10,
        "squad_value": entry.get("last_deadline_value", 0) / 10,
        "free_transfers": max(
            1, 2 - entry_history.get("event_transfers", 0)
        ),
        "transfers_made": entry_history.get("event_transfers", 0),
        "active_chip": picks.get("active_chip"),
        "chips": history.get("chips", []),
        "players": players_out,
        "transfers": transfers_out,
    }
