from __future__ import annotations

import contextlib
import dataclasses
import logging

from sqlalchemy.orm import Session

from fpl.analysis.form import get_current_gameweek
from fpl.db.models import (
    CustomFdr,
    Player,
    PlayerFormScore,
    PlayerGameweekStats,
    Team,
    UnderstatMatch,
)

logger = logging.getLogger(__name__)

_LOOKBACK_GWS = 5
_HAUL_THRESHOLD = 10  # points to count as a "haul"


@dataclasses.dataclass
class CaptainCandidate:
    player: Player
    team: Team
    form_score: float
    fixture_ease: float  # 6 - fdr (higher = easier)
    xg_per90: float
    xa_per90: float
    is_home: bool
    haul_rate: float  # fraction of GWs with >= 10 points
    captain_score: float  # weighted composite (0-10)


def _get_form_score(
    session: Session,
    player_id: int,
    current_gw: int,
) -> float:
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


def _get_next_fixture_fdr(
    session: Session,
    team_id: int,
    current_gw: int,
) -> tuple[float, bool]:
    """Return (overall_difficulty, is_home) for the team's next GW fixture.

    Falls back to (3.0, False) if no FDR data is available.
    """
    fdr: CustomFdr | None = (
        session.query(CustomFdr)
        .filter(
            CustomFdr.team_id == team_id,
            CustomFdr.gameweek > current_gw,
        )
        .order_by(CustomFdr.gameweek)
        .first()
    )
    if fdr is None:
        return 3.0, False
    return fdr.overall_difficulty, fdr.is_home


def _get_xg_xa_per90(
    session: Session,
    player_id: int,
    current_gw: int,
    lookback: int = _LOOKBACK_GWS,
) -> tuple[float, float]:
    """Compute xG/90 and xA/90 from recent GW stats.

    Prefers Understat season aggregate if available; otherwise uses FPL expected
    stats from the last *lookback* gameweeks.
    """
    # Try Understat season aggregate first
    agg: UnderstatMatch | None = (
        session.query(UnderstatMatch)
        .filter(
            UnderstatMatch.player_id == player_id,
            UnderstatMatch.opponent == "season_aggregate",
        )
        .first()
    )
    if agg is not None and agg.minutes > 0:
        return agg.xg / agg.minutes * 90.0, agg.xa / agg.minutes * 90.0

    # Fall back to FPL expected_goals / expected_assists from recent GWs
    recent: list[PlayerGameweekStats] = (
        session.query(PlayerGameweekStats)
        .filter(
            PlayerGameweekStats.player_id == player_id,
            PlayerGameweekStats.gameweek <= current_gw,
        )
        .order_by(PlayerGameweekStats.gameweek.desc())
        .limit(lookback)
        .all()
    )
    if not recent:
        return 0.0, 0.0

    total_mins = sum(s.minutes for s in recent)
    if total_mins == 0:
        return 0.0, 0.0

    def _sum_str(field: str) -> float:
        total = 0.0
        for s in recent:
            raw = getattr(s, field, "0")
            with contextlib.suppress(ValueError, TypeError):
                total += float(raw)
        return total

    xg = _sum_str("expected_goals") / total_mins * 90.0
    xa = _sum_str("expected_assists") / total_mins * 90.0
    return xg, xa


def _get_haul_rate(
    session: Session,
    player_id: int,
    current_gw: int,
    lookback: int = _LOOKBACK_GWS,
) -> float:
    """Fraction of recent GWs where the player scored >= 10 points."""
    recent: list[PlayerGameweekStats] = (
        session.query(PlayerGameweekStats)
        .filter(
            PlayerGameweekStats.player_id == player_id,
            PlayerGameweekStats.gameweek <= current_gw,
        )
        .order_by(PlayerGameweekStats.gameweek.desc())
        .limit(lookback)
        .all()
    )
    if not recent:
        return 0.0

    hauls = sum(1 for s in recent if s.total_points >= _HAUL_THRESHOLD)
    return hauls / len(recent)


def _compute_captain_score(
    form_score: float,
    fixture_ease: float,
    xg_per90: float,
    xa_per90: float,
    is_home: bool,
    haul_rate: float,
    max_xg: float,
    max_xa: float,
) -> float:
    """Weighted composite captain score (roughly 0-10).

    Weights:
        0.35  form (normalised form_score/100 * 10)
        0.25  fixture ease (fixture_ease/5 * 10)
        0.15  xG/90 (normalised against max)
        0.10  xA/90 (normalised against max)
        0.10  home bonus (2.0 if home, else 0.0)
        0.05  haul rate (haul_rate * 10)
    """
    form_norm = (form_score / 100.0) * 10.0
    ease_norm = (fixture_ease / 5.0) * 10.0
    xg_norm = (xg_per90 / max_xg * 10.0) if max_xg > 0 else 0.0
    xa_norm = (xa_per90 / max_xa * 10.0) if max_xa > 0 else 0.0
    home_bonus = 2.0 if is_home else 0.0
    haul_norm = haul_rate * 10.0

    return (
        0.35 * form_norm
        + 0.25 * ease_norm
        + 0.15 * xg_norm
        + 0.10 * xa_norm
        + 0.10 * home_bonus
        + 0.05 * haul_norm
    )


def pick_captains(
    session: Session,
    player_ids: list[int] | None = None,
    top: int = 5,
) -> list[CaptainCandidate]:
    """Rank captain candidates.

    If *player_ids* is provided (e.g. the user's squad), only those players are
    considered.  If None, all players with form data are considered.

    Returns at most *top* candidates sorted by captain_score descending.
    """
    current_gw = get_current_gameweek(session)

    if player_ids is not None:
        players: list[Player] = (
            session.query(Player).filter(Player.fpl_id.in_(player_ids)).all()
        )
    else:
        # All players with at least one form score
        scored_ids: list[int] = [
            row[0]
            for row in session.query(PlayerFormScore.player_id)
            .filter(PlayerFormScore.gameweek <= current_gw)
            .distinct()
            .all()
        ]
        if not scored_ids:
            return []
        players = session.query(Player).filter(Player.fpl_id.in_(scored_ids)).all()

    if not players:
        return []

    # Pre-compute xG/xA for all candidates to find global maxima for normalisation
    xg_xa: dict[int, tuple[float, float]] = {}
    for p in players:
        xg_xa[p.fpl_id] = _get_xg_xa_per90(session, p.fpl_id, current_gw)

    max_xg = max((v[0] for v in xg_xa.values()), default=1.0) or 1.0
    max_xa = max((v[1] for v in xg_xa.values()), default=1.0) or 1.0

    candidates: list[CaptainCandidate] = []

    for player in players:
        team: Team | None = session.get(Team, player.team_id)
        if team is None:
            continue

        form_score = _get_form_score(session, player.fpl_id, current_gw)
        fdr, is_home = _get_next_fixture_fdr(session, player.team_id, current_gw)
        fixture_ease = 6.0 - fdr
        xg_per90, xa_per90 = xg_xa[player.fpl_id]
        haul_rate = _get_haul_rate(session, player.fpl_id, current_gw)

        score = _compute_captain_score(
            form_score=form_score,
            fixture_ease=fixture_ease,
            xg_per90=xg_per90,
            xa_per90=xa_per90,
            is_home=is_home,
            haul_rate=haul_rate,
            max_xg=max_xg,
            max_xa=max_xa,
        )

        candidates.append(
            CaptainCandidate(
                player=player,
                team=team,
                form_score=form_score,
                fixture_ease=fixture_ease,
                xg_per90=xg_per90,
                xa_per90=xa_per90,
                is_home=is_home,
                haul_rate=haul_rate,
                captain_score=score,
            )
        )

    candidates.sort(key=lambda c: c.captain_score, reverse=True)
    return candidates[:top]
