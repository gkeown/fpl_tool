from __future__ import annotations

import dataclasses
import logging

from sqlalchemy.orm import Session

from fpl.analysis.form import get_current_gameweek
from fpl.db.models import CustomFdr, Player, PlayerFormScore, Team

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Differential:
    player: Player
    team: Team
    form_score: float
    ownership: float  # selected_by_percent as a float
    cost: int
    upcoming_fdr: float
    value_score: float  # form * fixture_ease / (cost / 10)


def _get_form_score(
    session: Session,
    player_id: int,
    current_gw: int,
) -> float:
    """Return the most recent form score for the player, or 0.0 if none."""
    score: PlayerFormScore | None = (
        session.query(PlayerFormScore)
        .filter(
            PlayerFormScore.player_id == player_id,
            PlayerFormScore.gameweek <= current_gw,
        )
        .order_by(PlayerFormScore.gameweek.desc())
        .first()
    )
    return score.form_score if score is not None else 0.0


def _get_avg_fdr(
    session: Session,
    team_id: int,
    current_gw: int,
    weeks_ahead: int = 5,
) -> float:
    """Return the average overall FDR for the team over the next weeks_ahead GWs."""
    fdrs: list[CustomFdr] = (
        session.query(CustomFdr)
        .filter(
            CustomFdr.team_id == team_id,
            CustomFdr.gameweek > current_gw,
            CustomFdr.gameweek <= current_gw + weeks_ahead,
        )
        .order_by(CustomFdr.gameweek)
        .all()
    )
    if not fdrs:
        return 3.0
    return sum(f.overall_difficulty for f in fdrs) / len(fdrs)


def find_differentials(
    session: Session,
    max_ownership: float = 10.0,
    min_minutes: int = 200,
    position: int | None = None,
    top: int = 20,
) -> list[Differential]:
    """Find high-value, low-ownership players.

    Args:
        session: Database session.
        max_ownership: Maximum selected_by_percent to include (default 10.0%).
        min_minutes: Minimum total minutes played this season.
        position: element_type filter (1=GKP, 2=DEF, 3=MID, 4=FWD). None = all.
        top: Maximum number of results to return.

    Returns:
        List of Differential ordered by value_score descending.
    """
    current_gw = get_current_gameweek(session)

    query = session.query(Player).filter(
        Player.status == "a",
        Player.minutes >= min_minutes,
    )

    if position is not None:
        query = query.filter(Player.element_type == position)

    players: list[Player] = query.all()

    differentials: list[Differential] = []

    for player in players:
        try:
            ownership = float(player.selected_by_percent)
        except (ValueError, TypeError):
            ownership = 0.0

        if ownership >= max_ownership:
            continue

        team: Team | None = session.get(Team, player.team_id)
        if team is None:
            continue

        form = _get_form_score(session, player.fpl_id, current_gw)
        avg_fdr = _get_avg_fdr(session, player.team_id, current_gw)
        fixture_ease = max(0.0, 6.0 - avg_fdr)
        cost_millions = player.now_cost / 10.0
        value_score = form * fixture_ease / cost_millions if cost_millions > 0 else 0.0

        differentials.append(
            Differential(
                player=player,
                team=team,
                form_score=form,
                ownership=ownership,
                cost=player.now_cost,
                upcoming_fdr=avg_fdr,
                value_score=value_score,
            )
        )

    differentials.sort(key=lambda d: d.value_score, reverse=True)
    return differentials[:top]
