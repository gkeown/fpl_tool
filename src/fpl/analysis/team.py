from __future__ import annotations

import dataclasses
import logging

from sqlalchemy.orm import Session

from fpl.analysis.form import get_current_gameweek
from fpl.db.models import (
    CustomFdr,
    MyAccount,
    MyTeamPlayer,
    Player,
    PlayerFormScore,
    PlayerGameweekStats,
    Team,
)

logger = logging.getLogger(__name__)

_LOOKBACK_GWS = 5


@dataclasses.dataclass
class PlayerAnalysis:
    player: Player
    team: Team
    form_score: float
    upcoming_difficulty: float  # average FDR for next N weeks
    expected_value: float  # form * (6 - difficulty) / 5 * minutes_probability
    is_starter: bool  # position 1-11
    is_captain: bool
    is_vice_captain: bool
    minutes_probability: float  # estimate based on recent starts


@dataclasses.dataclass
class TeamAnalysis:
    players: list[PlayerAnalysis]
    total_strength: float  # sum of expected values for starting XI
    weak_spots: list[str]  # descriptive strings identifying issues
    bank: int  # remaining budget in tenths of a million
    free_transfers: int


def _compute_minutes_probability(
    session: Session,
    player_id: int,
    current_gw: int,
    lookback: int = _LOOKBACK_GWS,
) -> float:
    """Estimate probability that the player will play >= 60 minutes.

    Looks at the last *lookback* gameweek stats. Returns the fraction of
    gameweeks where the player played >= 60 minutes.  Returns 0.5 when no
    recent data is available.
    """
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
        return 0.5

    started = sum(1 for s in recent if s.minutes >= 60)
    return started / len(recent)


def _compute_upcoming_difficulty(
    session: Session,
    team_id: int,
    current_gw: int,
    weeks_ahead: int,
) -> float:
    """Return the average custom FDR for the team over the next *weeks_ahead* GWs."""
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
        return 3.0  # neutral default

    return sum(f.overall_difficulty for f in fdrs) / len(fdrs)


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


def _compute_expected_value(
    form_score: float,
    upcoming_difficulty: float,
    minutes_probability: float,
) -> float:
    """Composite expected value for a player.

    Scales form (0-100 → 0-10), adjusts by fixture ease (6 - diff on 1-5 scale
    gives 1-5, normalised to 0-1 by dividing by 5), then weights by minutes
    probability.
    """
    form_norm = form_score / 10.0  # 0-10
    ease_norm = (6.0 - upcoming_difficulty) / 5.0  # 0-1 (higher = easier)
    return form_norm * ease_norm * minutes_probability


def _identify_weak_spots(analysis: list[PlayerAnalysis]) -> list[str]:
    """Produce human-readable descriptions of squad weaknesses."""
    issues: list[str] = []

    for pa in analysis:
        name = pa.player.web_name
        status = pa.player.status

        if status in ("i", "u", "s"):
            status_label = {"i": "injured", "u": "unavailable", "s": "suspended"}.get(
                status, status
            )
            issues.append(
                f"{name} is {status_label} ({pa.player.news or 'no details'})"
            )
        elif status == "d":
            issues.append(f"{name} is doubtful ({pa.player.news or 'no details'})")

        if pa.form_score < 30.0 and pa.is_starter:
            issues.append(f"{name} has poor form (score: {pa.form_score:.1f})")

        if pa.upcoming_difficulty > 3.5 and pa.is_starter:
            issues.append(
                f"{name} has tough upcoming fixtures "
                f"(avg FDR: {pa.upcoming_difficulty:.1f})"
            )

        if pa.minutes_probability < 0.4 and pa.is_starter:
            issues.append(
                f"{name} has low minutes probability "
                f"({pa.minutes_probability:.0%} chance of 60+ mins)"
            )

    return issues


def analyse_team(session: Session, weeks_ahead: int = 5) -> TeamAnalysis | None:
    """Analyse the user's current FPL team.

    Returns None if no team data exists (user hasn't run 'fpl me login').
    """
    my_team_players: list[MyTeamPlayer] = session.query(MyTeamPlayer).all()
    if not my_team_players:
        return None

    current_gw = get_current_gameweek(session)

    # Load account info for bank / free transfers
    account: MyAccount | None = session.get(MyAccount, 1)
    bank = account.bank if account is not None else 0
    free_transfers = account.free_transfers if account is not None else 1

    # Build analysis per player
    player_analyses: list[PlayerAnalysis] = []

    for mtp in my_team_players:
        player: Player | None = session.get(Player, mtp.player_id)
        if player is None:
            logger.warning(
                "MyTeamPlayer references unknown player_id=%d", mtp.player_id
            )
            continue

        team: Team | None = session.get(Team, player.team_id)
        if team is None:
            logger.warning(
                "Player %d has unknown team_id=%d", player.fpl_id, player.team_id
            )
            continue

        form_score = _get_form_score(session, player.fpl_id, current_gw)
        upcoming_difficulty = _compute_upcoming_difficulty(
            session, player.team_id, current_gw, weeks_ahead
        )
        minutes_prob = _compute_minutes_probability(session, player.fpl_id, current_gw)

        expected_value = _compute_expected_value(
            form_score, upcoming_difficulty, minutes_prob
        )

        player_analyses.append(
            PlayerAnalysis(
                player=player,
                team=team,
                form_score=form_score,
                upcoming_difficulty=upcoming_difficulty,
                expected_value=expected_value,
                is_starter=mtp.position <= 11,
                is_captain=mtp.is_captain,
                is_vice_captain=mtp.is_vice_captain,
                minutes_probability=minutes_prob,
            )
        )

    if not player_analyses:
        return None

    # Total strength = sum of expected values for starting XI
    total_strength = sum(pa.expected_value for pa in player_analyses if pa.is_starter)

    weak_spots = _identify_weak_spots(player_analyses)

    # Sort: starters first (by position), then bench
    player_analyses.sort(
        key=lambda pa: (0 if pa.is_starter else 1, pa.player.element_type)
    )

    return TeamAnalysis(
        players=player_analyses,
        total_strength=total_strength,
        weak_spots=weak_spots,
        bank=bank,
        free_transfers=free_transfers,
    )
