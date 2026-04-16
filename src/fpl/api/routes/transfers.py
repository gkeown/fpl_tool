from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from fpl.analysis.transfers import compare_players, suggest_transfers
from fpl.auth import require_admin
from fpl.cli.formatters import format_cost, position_str
from fpl.db.engine import get_session
from fpl.db.models import MyAccount

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/suggest")
def suggest(weeks: int = 5, top: int = 10) -> list[dict[str, Any]]:
    """Transfer suggestions for the user's current team."""
    with get_session() as session:
        account: MyAccount | None = session.get(MyAccount, 1)
        free_transfers = account.free_transfers if account is not None else 1

        suggestions = suggest_transfers(
            session,
            free_transfers=free_transfers,
            weeks_ahead=weeks,
            top=top,
        )

        if not suggestions:
            return []

        return [
            {
                "rank": rank,
                "out_player": s.out_player.web_name,
                "out_player_id": s.out_player.fpl_id,
                "out_team": s.out_team.short_name,
                "out_cost": format_cost(s.out_player.now_cost),
                "in_player": s.in_player.web_name,
                "in_player_id": s.in_player.fpl_id,
                "in_team": s.in_team.short_name,
                "in_cost": format_cost(s.in_player.now_cost),
                "position": position_str(s.out_player.element_type),
                "delta_value": round(s.delta_value, 3),
                "out_form": round(s.out_form, 2),
                "in_form": round(s.in_form, 2),
                "out_fdr": round(s.out_fdr, 2),
                "in_fdr": round(s.in_fdr, 2),
                "budget_impact": float(s.budget_impact) / 10,
            }
            for rank, s in enumerate(suggestions, 1)
        ]


@router.get("/compare")
def compare(player1: str, player2: str) -> dict[str, Any]:
    """Head-to-head player comparison."""
    with get_session() as session:
        result = compare_players(session, player1, player2)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(f"Could not find one or both players: '{player1}', '{player2}'"),
        )

    c1, c2 = result

    def _comp_dict(c: object) -> dict[str, Any]:
        from fpl.analysis.transfers import PlayerComparison

        pc: PlayerComparison = c  # type: ignore[assignment]
        return {
            "id": pc.player.fpl_id,
            "web_name": pc.player.web_name,
            "full_name": (f"{pc.player.first_name} {pc.player.second_name}"),
            "team": pc.team.short_name,
            "position": position_str(pc.player.element_type),
            "cost": float(pc.cost) / 10,
            "form_score": round(pc.form_score, 2),
            "xg_per90": round(pc.xg_per90, 3),
            "xa_per90": round(pc.xa_per90, 3),
            "points_per90": round(pc.points_per90, 2),
            "upcoming_fdr": round(pc.upcoming_fdr, 2),
            "minutes": pc.minutes,
            "goals": pc.goals,
            "assists": pc.assists,
            "clean_sheets": pc.clean_sheets,
            "ownership": pc.player.selected_by_percent,
        }

    return {
        "player1": _comp_dict(c1),
        "player2": _comp_dict(c2),
    }
