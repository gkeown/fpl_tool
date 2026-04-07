from __future__ import annotations

import contextlib
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
    UnderstatMatch,
)

logger = logging.getLogger(__name__)

_LOOKBACK_GWS = 5
_POSITION_MAP: dict[str, int] = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}


@dataclasses.dataclass
class TransferSuggestion:
    out_player: Player
    in_player: Player
    out_team: Team
    in_team: Team
    delta_value: float  # improvement score
    out_form: float
    in_form: float
    out_fdr: float  # avg upcoming FDR
    in_fdr: float
    budget_impact: int  # cost difference in tenths (negative = saves money)


@dataclasses.dataclass
class PlayerComparison:
    player: Player
    team: Team
    form_score: float
    cost: int
    xg_per90: float
    xa_per90: float
    points_per90: float
    upcoming_fdr: float
    minutes: int
    goals: int
    assists: int
    clean_sheets: int


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
    weeks_ahead: int,
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
        return 3.0  # neutral default
    return sum(f.overall_difficulty for f in fdrs) / len(fdrs)


def _get_xg_xa_per90(
    session: Session,
    player_id: int,
    current_gw: int,
    lookback: int = _LOOKBACK_GWS,
) -> tuple[float, float]:
    """Return (xg_per90, xa_per90) preferring Understat data."""
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

    return (
        _sum_str("expected_goals") / total_mins * 90.0,
        _sum_str("expected_assists") / total_mins * 90.0,
    )


def _get_points_per90(
    session: Session,
    player_id: int,
    current_gw: int,
    lookback: int = _LOOKBACK_GWS,
) -> float:
    """Return points per 90 minutes over the last lookback gameweeks."""
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
    total_mins = sum(s.minutes for s in recent)
    if total_mins == 0:
        return 0.0
    total_pts = sum(s.total_points for s in recent)
    return total_pts / total_mins * 90.0


def _player_value_score(
    form_score: float,
    avg_fdr: float,
    cost: int,
) -> float:
    """Score a player: form * fixture_ease / (cost / 10).

    fixture_ease = 6 - avg_fdr (range 1-5 maps to ease 1-5).
    """
    fixture_ease = max(0.0, 6.0 - avg_fdr)
    cost_millions = cost / 10.0
    if cost_millions <= 0:
        return 0.0
    return form_score * fixture_ease / cost_millions


def suggest_transfers(
    session: Session,
    free_transfers: int = 1,
    budget: int | None = None,
    max_hits: int = 0,
    weeks_ahead: int = 5,
    top: int = 10,
) -> list[TransferSuggestion]:
    """Suggest optimal transfers for the user's team.

    Args:
        session: Database session.
        free_transfers: Number of free transfers available.
        budget: Total budget in tenths of a million. If None, loaded from
            MyAccount.bank (the user's bank balance; selling price is added
            per transfer).
        max_hits: Maximum number of additional transfers beyond free_transfers.
        weeks_ahead: Number of gameweeks ahead to consider for FDR.
        top: Maximum number of suggestions to return.

    Returns:
        List of TransferSuggestion ordered by delta_value descending.
    """
    my_team_players: list[MyTeamPlayer] = session.query(MyTeamPlayer).all()
    if not my_team_players:
        logger.warning("No team data found. Run 'fpl me login' first.")
        return []

    current_gw = get_current_gameweek(session)

    account: MyAccount | None = session.get(MyAccount, 1)
    bank_balance = account.bank if account is not None else 0
    if budget is not None:
        bank_balance = budget

    # Build a map of player_id -> MyTeamPlayer for quick lookup
    my_team_map: dict[int, MyTeamPlayer] = {
        mtp.player_id: mtp for mtp in my_team_players
    }
    squad_player_ids: set[int] = set(my_team_map.keys())

    # Count players per team in squad (for max-3-per-team constraint)
    # Map: team_id -> count
    squad_team_counts: dict[int, int] = {}
    for mtp in my_team_players:
        player: Player | None = session.get(Player, mtp.player_id)
        if player is not None:
            squad_team_counts[player.team_id] = (
                squad_team_counts.get(player.team_id, 0) + 1
            )

    # Score every available (status='a') player in the game
    all_players: list[Player] = (
        session.query(Player).filter(Player.status == "a", Player.minutes > 0).all()
    )

    # Precompute form and FDR for all players
    player_form: dict[int, float] = {}
    player_fdr: dict[int, float] = {}
    player_value: dict[int, float] = {}

    for p in all_players:
        form = _get_form_score(session, p.fpl_id, current_gw)
        fdr = _get_avg_fdr(session, p.team_id, current_gw, weeks_ahead)
        player_form[p.fpl_id] = form
        player_fdr[p.fpl_id] = fdr
        player_value[p.fpl_id] = _player_value_score(form, fdr, p.now_cost)

    # Index all players by element_type for fast lookup
    players_by_position: dict[int, list[Player]] = {}
    for p in all_players:
        players_by_position.setdefault(p.element_type, []).append(p)

    suggestions: list[TransferSuggestion] = []

    for mtp in my_team_players:
        out_player: Player | None = session.get(Player, mtp.player_id)
        if out_player is None:
            continue

        out_team: Team | None = session.get(Team, out_player.team_id)
        if out_team is None:
            continue

        out_form = player_form.get(out_player.fpl_id, 0.0)
        out_fdr = player_fdr.get(out_player.fpl_id, 3.0)
        out_val = player_value.get(
            out_player.fpl_id,
            _player_value_score(out_form, out_fdr, out_player.now_cost),
        )

        # Budget available for this transfer: bank + selling price of outgoing
        available_budget = bank_balance + mtp.selling_price

        pos = out_player.element_type
        candidates = players_by_position.get(pos, [])

        for in_player in candidates:
            # Skip players already in squad
            if in_player.fpl_id in squad_player_ids:
                continue

            # Budget check
            if in_player.now_cost > available_budget:
                continue

            # Max 3 per team constraint:
            # If adding this player would push the squad over 3 from their team,
            # skip. We subtract 1 for the outgoing player's team if same team.
            in_team_current_count = squad_team_counts.get(in_player.team_id, 0)
            # If the incoming player is from the same team as the outgoing player,
            # the outgoing player's slot is freed — count stays the same.
            if in_player.team_id == out_player.team_id:
                # No net change in team count
                if in_team_current_count > 3:
                    continue
            else:
                if in_team_current_count >= 3:
                    continue

            in_form = player_form.get(in_player.fpl_id, 0.0)
            in_fdr = player_fdr.get(in_player.fpl_id, 3.0)
            in_val = player_value.get(in_player.fpl_id, 0.0)

            delta = in_val - out_val
            if delta <= 0:
                continue

            in_team: Team | None = session.get(Team, in_player.team_id)
            if in_team is None:
                continue

            suggestions.append(
                TransferSuggestion(
                    out_player=out_player,
                    in_player=in_player,
                    out_team=out_team,
                    in_team=in_team,
                    delta_value=delta,
                    out_form=out_form,
                    in_form=in_form,
                    out_fdr=out_fdr,
                    in_fdr=in_fdr,
                    budget_impact=in_player.now_cost - mtp.selling_price,
                )
            )

    suggestions.sort(key=lambda s: s.delta_value, reverse=True)

    # Deduplicate: only keep the best suggestion per out_player
    seen_out: set[int] = set()
    deduped: list[TransferSuggestion] = []
    for s in suggestions:
        if s.out_player.fpl_id not in seen_out:
            seen_out.add(s.out_player.fpl_id)
            deduped.append(s)
        if len(deduped) >= top:
            break

    return deduped[:top]


def _fuzzy_find_player(session: Session, name: str) -> Player | None:
    """Find a player by fuzzy name match. Returns the best match or None."""
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        logger.error("rapidfuzz is required for player name matching.")
        return None

    players: list[Player] = session.query(Player).all()
    if not players:
        return None

    choices: dict[str, int] = {}
    for p in players:
        key = f"{p.web_name} {p.first_name} {p.second_name}"
        choices[key] = p.fpl_id

    best = process.extractOne(name, list(choices.keys()), scorer=fuzz.WRatio)
    if best is None or best[1] < 60:
        return None

    return session.get(Player, choices[best[0]])


def compare_players(
    session: Session,
    name1: str,
    name2: str,
) -> tuple[PlayerComparison, PlayerComparison] | None:
    """Head-to-head comparison of two players.

    Args:
        session: Database session.
        name1: Name of the first player (fuzzy matched).
        name2: Name of the second player (fuzzy matched).

    Returns:
        A tuple of two PlayerComparison objects, or None if either player is
        not found.
    """
    p1 = _fuzzy_find_player(session, name1)
    if p1 is None:
        logger.warning("Player not found: %s", name1)
        return None

    p2 = _fuzzy_find_player(session, name2)
    if p2 is None:
        logger.warning("Player not found: %s", name2)
        return None

    current_gw = get_current_gameweek(session)

    def _build_comparison(player: Player) -> PlayerComparison:
        team: Team | None = session.get(Team, player.team_id)
        if team is None:
            # Create a placeholder team to avoid None issues
            team = Team(
                fpl_id=0,
                code=0,
                name="Unknown",
                short_name="UNK",
                strength=0,
                strength_attack_home=0,
                strength_attack_away=0,
                strength_defence_home=0,
                strength_defence_away=0,
                updated_at="",
            )

        form = _get_form_score(session, player.fpl_id, current_gw)
        xg, xa = _get_xg_xa_per90(session, player.fpl_id, current_gw)
        pts_per90 = _get_points_per90(session, player.fpl_id, current_gw)
        avg_fdr = _get_avg_fdr(session, player.team_id, current_gw, 5)

        return PlayerComparison(
            player=player,
            team=team,
            form_score=form,
            cost=player.now_cost,
            xg_per90=xg,
            xa_per90=xa,
            points_per90=pts_per90,
            upcoming_fdr=avg_fdr,
            minutes=player.minutes,
            goals=player.goals_scored,
            assists=player.assists,
            clean_sheets=player.clean_sheets,
        )

    return _build_comparison(p1), _build_comparison(p2)
