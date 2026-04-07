from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from fpl.analysis.captaincy import pick_captains
from fpl.analysis.form import get_current_gameweek
from fpl.cli.formatters import format_cost, position_str
from fpl.db.engine import get_session
from fpl.db.models import (
    CustomFdr,
    MyTeamPlayer,
    Player,
    PlayerProjection,
    Team,
)

router = APIRouter()


def _next_fixture_label(
    session: object,
    team_id: int,
    current_gw: int,
    is_home: bool,
) -> str:
    from sqlalchemy.orm import Session

    s: Session = session  # type: ignore[assignment]
    fdr: CustomFdr | None = (
        s.query(CustomFdr)
        .filter(
            CustomFdr.team_id == team_id,
            CustomFdr.gameweek > current_gw,
        )
        .order_by(CustomFdr.gameweek)
        .first()
    )
    if fdr is None:
        return "TBC"
    opp: Team | None = s.get(Team, fdr.opponent_id)
    opp_name = opp.short_name if opp is not None else "???"
    ha = "H" if is_home else "A"
    return f"vs {opp_name} ({ha})"


@router.get("/pick")
def pick(top: int = 5) -> list[dict[str, Any]]:
    """Captain recommendations for the next gameweek."""
    with get_session() as session:
        current_gw = get_current_gameweek(session)

        my_team: list[MyTeamPlayer] = session.query(MyTeamPlayer).all()
        player_ids: list[int] | None = None
        if my_team:
            player_ids = [mtp.player_id for mtp in my_team]

        candidates = pick_captains(session, player_ids=player_ids, top=top)

        if not candidates:
            return []

        candidate_ids = [c.player.fpl_id for c in candidates]
        proj_rows: list[PlayerProjection] = (
            session.query(PlayerProjection)
            .filter(PlayerProjection.player_id.in_(candidate_ids))
            .all()
        )
        proj_by_id: dict[int, PlayerProjection] = {p.player_id: p for p in proj_rows}

        def _xpts(player: Player) -> float | None:
            proj = proj_by_id.get(player.fpl_id)
            if proj is not None:
                return proj.gw1_pts
            if player.ep_next:
                try:
                    return float(player.ep_next)
                except ValueError:
                    pass
            return None

        results: list[dict[str, Any]] = []
        for rank, c in enumerate(candidates, 1):
            fixture_str = _next_fixture_label(
                session, c.team.fpl_id, current_gw, c.is_home
            )
            xpts_val = _xpts(c.player)

            results.append(
                {
                    "rank": rank,
                    "id": c.player.fpl_id,
                    "player": c.player.web_name,
                    "team": c.team.short_name,
                    "position": position_str(c.player.element_type),
                    "cost": format_cost(c.player.now_cost),
                    "fixture": fixture_str,
                    "is_home": c.is_home,
                    "captain_score": round(c.captain_score, 2),
                    "form_score": round(c.form_score, 2),
                    "fixture_ease": round(c.fixture_ease, 2),
                    "xg_per90": round(c.xg_per90, 3),
                    "xa_per90": round(c.xa_per90, 3),
                    "haul_rate": round(c.haul_rate, 3),
                    "xpts_next_gw": xpts_val,
                }
            )

        return results
