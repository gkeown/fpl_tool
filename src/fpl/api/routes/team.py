from __future__ import annotations

import contextlib
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from fpl.analysis.form import get_current_gameweek
from fpl.analysis.team import analyse_team
from fpl.cli.formatters import position_str
from fpl.config import get_settings
from fpl.db.engine import get_session
from fpl.db.models import (
    MyAccount,
    MyTeamPlayer,
    Player,
    PlayerGameweekStats,
    PlayerProjection,
    Team,
)

router = APIRouter()


@router.get("/team")
def get_team() -> dict[str, Any]:
    """Current squad with form + projected points."""
    with get_session() as session:
        rows = (
            session.query(MyTeamPlayer, Player, Team)
            .join(Player, Player.fpl_id == MyTeamPlayer.player_id)
            .join(Team, Team.fpl_id == Player.team_id)
            .order_by(MyTeamPlayer.position)
            .all()
        )

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="No team data found. Load a team via POST /api/me/login.",
            )

        current_gw = get_current_gameweek(session)
        account: MyAccount | None = session.get(MyAccount, 1)

        player_ids = [player.fpl_id for _mtp, player, _ in rows]
        proj_rows: list[PlayerProjection] = (
            session.query(PlayerProjection)
            .filter(PlayerProjection.player_id.in_(player_ids))
            .all()
        )
        proj_lookup: dict[int, float] = {p.player_id: p.gw1_pts for p in proj_rows}

        # Bonus points for current GW
        bonus_rows: list[PlayerGameweekStats] = (
            session.query(PlayerGameweekStats)
            .filter(
                PlayerGameweekStats.player_id.in_(player_ids),
                PlayerGameweekStats.gameweek == current_gw,
            )
            .all()
        )
        bonus_lookup: dict[int, int] = {}
        for br in bonus_rows:
            bonus_lookup[br.player_id] = (
                bonus_lookup.get(br.player_id, 0) + br.bonus
            )

        ep_lookup: dict[int, float] = {}
        for _mtp, player, _ in rows:
            if player.fpl_id not in proj_lookup:
                ep_val = 0.0
                if player.ep_next:
                    with contextlib.suppress(ValueError):
                        ep_val = float(player.ep_next)
                ep_lookup[player.fpl_id] = ep_val

        def _xpts(pid: int) -> float:
            return proj_lookup.get(pid, ep_lookup.get(pid, 0.0))

        players_out: list[dict[str, Any]] = []
        for mtp, player, tm in rows:
            event_pts = player.event_points or 0
            players_out.append(
                {
                    "id": player.fpl_id,
                    "web_name": player.web_name,
                    "team": tm.short_name,
                    "position": position_str(player.element_type),
                    "cost": float(player.now_cost) / 10,
                    "selling_price": float(mtp.selling_price) / 10,
                    "form": float(player.form),
                    "xpts_next_gw": round(_xpts(player.fpl_id), 2),
                    "event_points": event_pts,
                    "gw_points": event_pts * mtp.multiplier,
                    "gw_bonus": bonus_lookup.get(player.fpl_id, 0),
                    "status": player.status,
                    "news": player.news,
                    "is_starter": mtp.position <= 11,
                    "squad_position": mtp.position,
                    "is_captain": mtp.is_captain,
                    "is_vice_captain": mtp.is_vice_captain,
                    "multiplier": mtp.multiplier,
                }
            )

        return {
            "gameweek": current_gw,
            "gameweek_points": account.gameweek_points if account else 0,
            "bank": float(account.bank) / 10 if account else 0.0,
            "free_transfers": account.free_transfers if account else 1,
            "overall_points": account.overall_points if account else 0,
            "overall_rank": account.overall_rank if account else 0,
            "players": players_out,
        }


@router.get("/analyse")
def analyse(weeks: int = 5) -> dict[str, Any]:
    """Full team analysis."""
    with get_session() as session:
        analysis = analyse_team(session, weeks_ahead=weeks)

        if analysis is None:
            raise HTTPException(
                status_code=404,
                detail="No team data found. Load a team via POST /api/me/login.",
            )

        squad_ids = [pa.player.fpl_id for pa in analysis.players]
        proj_rows: list[PlayerProjection] = (
            session.query(PlayerProjection)
            .filter(PlayerProjection.player_id.in_(squad_ids))
            .all()
        )
        proj_by_id: dict[int, PlayerProjection] = {p.player_id: p for p in proj_rows}

        def _ep_next(player: Player) -> float:
            if player.ep_next:
                with contextlib.suppress(ValueError):
                    return float(player.ep_next)
            return 0.0

        players_out: list[dict[str, Any]] = []
        for pa in analysis.players:
            proj = proj_by_id.get(pa.player.fpl_id)
            players_out.append(
                {
                    "id": pa.player.fpl_id,
                    "web_name": pa.player.web_name,
                    "team": pa.team.short_name,
                    "position": position_str(pa.player.element_type),
                    "cost": float(pa.player.now_cost) / 10,
                    "form_score": round(pa.form_score, 2),
                    "upcoming_difficulty": round(pa.upcoming_difficulty, 2),
                    "minutes_probability": round(pa.minutes_probability, 3),
                    "expected_value": round(pa.expected_value, 3),
                    "is_starter": pa.is_starter,
                    "is_captain": pa.is_captain,
                    "is_vice_captain": pa.is_vice_captain,
                    "status": pa.player.status,
                    "news": pa.player.news,
                    "xpts_gw1": round(proj.gw1_pts if proj else _ep_next(pa.player), 2),
                    "xpts_3gw": round(proj.next_3gw_pts if proj else 0.0, 2),
                    "xpts_5gw": round(proj.next_5gw_pts if proj else 0.0, 2),
                }
            )

        starters = [pa for pa in analysis.players if pa.is_starter]
        total_gw1 = sum(
            (
                proj_by_id[pa.player.fpl_id].gw1_pts
                if pa.player.fpl_id in proj_by_id
                else _ep_next(pa.player)
            )
            for pa in starters
        )
        total_3gw = sum(
            proj_by_id[pa.player.fpl_id].next_3gw_pts
            for pa in starters
            if pa.player.fpl_id in proj_by_id
        )
        total_5gw = sum(
            proj_by_id[pa.player.fpl_id].next_5gw_pts
            for pa in starters
            if pa.player.fpl_id in proj_by_id
        )

        return {
            "squad_strength": round(analysis.total_strength, 3),
            "bank": float(analysis.bank) / 10,
            "free_transfers": analysis.free_transfers,
            "weak_spots": analysis.weak_spots,
            "projected_xi_gw1": round(total_gw1, 2),
            "projected_xi_3gw": round(total_3gw, 2),
            "projected_xi_5gw": round(total_5gw, 2),
            "players": players_out,
        }


@router.post("/login")
async def login(team_id: int) -> dict[str, str]:
    """Load FPL team by ID."""
    settings = get_settings()

    from fpl.ingest.fpl_api import fetch_entry, fetch_entry_picks, upsert_my_team

    headers = {"User-Agent": settings.user_agent}
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            entry = await fetch_entry(client, settings, team_id)
            current_gw = entry.get("current_event", 1)
            picks = await fetch_entry_picks(client, settings, team_id, current_gw)

            with get_session() as session:
                count = upsert_my_team(session, team_id, entry, picks)

        name = (
            f"{entry.get('player_first_name', '')} "
            f"{entry.get('player_last_name', '')}"
        ).strip()
        return {
            "status": "ok",
            "manager": name,
            "gameweek": str(current_gw),
            "players_saved": str(count),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch team {team_id}: {exc}"
        ) from exc
