from __future__ import annotations

import logging
import math
from datetime import UTC, datetime

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.db.models import BettingOdds, Fixture, TeamPrediction

logger = logging.getLogger(__name__)

_LEAGUE_AVG_GOALS_PER_GAME = 2.7  # EPL long-run average
_HOME_MODIFIER = 1.15
_AWAY_MODIFIER = 0.85


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def _statistical_prediction(
    attacking_xg_per_game: float,
    defending_xga_per_game: float,
    league_avg: float,
    is_home: bool,
) -> float:
    """Predicted goals using xG-based model.

    Uses Dixon-Coles-style approach:
        lambda = attack_xg * defence_xga / league_avg * home_away_modifier
    """
    if league_avg <= 0:
        league_avg = _LEAGUE_AVG_GOALS_PER_GAME

    modifier = _HOME_MODIFIER if is_home else _AWAY_MODIFIER
    predicted = attacking_xg_per_game * defending_xga_per_game / league_avg * modifier
    return max(0.0, predicted)


def _odds_implied_goals(
    home_odds: float,
    draw_odds: float,
    away_odds: float,
    over_2_5: float | None,
    under_2_5: float | None,
) -> tuple[float, float]:
    """Derive expected goals from betting odds.

    Returns (home_expected_goals, away_expected_goals).

    Algorithm:
    1. Remove overround from 1X2 odds to get implied probabilities.
    2. Estimate total expected goals from O/U 2.5 line.
    3. Split total goals between home/away using 1X2 strength proxy.
    """
    # Step 1: remove overround from 1X2
    inv_home = 1.0 / home_odds if home_odds > 0 else 0.0
    inv_draw = 1.0 / draw_odds if draw_odds > 0 else 0.0
    inv_away = 1.0 / away_odds if away_odds > 0 else 0.0
    overround = inv_home + inv_draw + inv_away
    if overround <= 0:
        return 0.0, 0.0

    prob_home = inv_home / overround
    prob_away = inv_away / overround

    # Step 2: estimate total goals from O/U 2.5
    total_goals: float
    if (
        over_2_5 is not None
        and under_2_5 is not None
        and over_2_5 > 0
        and under_2_5 > 0
    ):
        inv_over = 1.0 / over_2_5
        inv_under = 1.0 / under_2_5
        ou_overround = inv_over + inv_under
        over_implied = inv_over / ou_overround
        under_implied = inv_under / ou_overround

        # P(X > 2.5) ≈ 1 - Poisson_CDF(2, lambda)
        # Approximation: total_goals ≈ 2.5 - ln(under_implied) / 0.4
        # Clamp to a reasonable range.
        try:
            total_goals = max(0.5, min(6.0, 2.5 - math.log(under_implied) / 0.4))
        except (ValueError, ZeroDivisionError):
            total_goals = _LEAGUE_AVG_GOALS_PER_GAME
        _ = over_implied  # used implicitly via under_implied
    else:
        total_goals = _LEAGUE_AVG_GOALS_PER_GAME

    # Step 3: split total goals using 1X2 strength proxy
    # Treat prob_home / (prob_home + prob_away) as home team goal share.
    strength_sum = prob_home + prob_away
    home_share = 0.5 if strength_sum <= 0 else prob_home / strength_sum

    home_goals = total_goals * home_share
    away_goals = total_goals * (1.0 - home_share)
    return home_goals, away_goals


def compute_predictions(session: Session, gameweek: int | None = None) -> int:
    """Compute goal/CS predictions for fixtures in a gameweek. Returns count stored."""
    from fpl.analysis.fdr import TeamSeasonStats, get_team_season_stats
    from fpl.analysis.form import get_current_gameweek

    if gameweek is None:
        gameweek = get_current_gameweek(session)

    team_stats: dict[int, TeamSeasonStats] = get_team_season_stats(session)

    if not team_stats:
        logger.warning("No team stats available; cannot compute predictions.")
        return 0

    # Compute league average goals per game from finished fixtures
    total_goals = sum(s.goals_scored for s in team_stats.values())
    total_games = sum(s.games_played for s in team_stats.values())
    # Each game is counted twice (once per team), so divide by 2
    league_avg = (
        total_goals / total_games if total_games > 0 else _LEAGUE_AVG_GOALS_PER_GAME
    )

    # Fetch fixtures for the target gameweek
    fixtures: list[Fixture] = (
        session.query(Fixture)
        .filter(Fixture.gameweek == gameweek, Fixture.finished.is_(False))
        .all()
    )

    if not fixtures:
        logger.info("No unfinished fixtures found for GW%d.", gameweek)
        return 0

    # Build betting odds lookup: fixture_id -> BettingOdds (best available)
    odds_rows: list[BettingOdds] = (
        session.query(BettingOdds).filter(BettingOdds.gameweek == gameweek).all()
    )
    # Use first odds record per fixture (could extend to average across bookmakers)
    fixture_odds: dict[int, BettingOdds] = {}
    for odds in odds_rows:
        if odds.fixture_id not in fixture_odds:
            fixture_odds[odds.fixture_id] = odds

    def _safe_stats(tid: int) -> TeamSeasonStats:
        return team_stats.get(
            tid,
            TeamSeasonStats(
                team_id=tid,
                games_played=0,
                goals_scored=0,
                goals_conceded=0,
                xg=0.0,
                xga=0.0,
                goals_per_game=_LEAGUE_AVG_GOALS_PER_GAME / 2,
                goals_conceded_per_game=_LEAGUE_AVG_GOALS_PER_GAME / 2,
            ),
        )

    now = _now_utc()
    records: list[dict[str, object]] = []

    for fixture in fixtures:
        h_stats = _safe_stats(fixture.team_h)
        a_stats = _safe_stats(fixture.team_a)

        # Statistical model
        # Home team attacking vs away team defending
        h_xg_pg = h_stats.xg if h_stats.xg > 0 else h_stats.goals_per_game
        a_xg_pg = a_stats.xg if a_stats.xg > 0 else a_stats.goals_per_game
        h_xga_pg = h_stats.xga if h_stats.xga > 0 else h_stats.goals_conceded_per_game
        a_xga_pg = a_stats.xga if a_stats.xga > 0 else a_stats.goals_conceded_per_game

        stat_home_goals = _statistical_prediction(h_xg_pg, a_xga_pg, league_avg, True)
        stat_away_goals = _statistical_prediction(a_xg_pg, h_xga_pg, league_avg, False)

        # Odds-implied model
        odds = fixture_odds.get(fixture.fpl_id)  # type: ignore[assignment]
        if (
            odds is not None
            and odds.home_odds is not None
            and odds.draw_odds is not None
            and odds.away_odds is not None
            and odds.home_odds > 0
            and odds.draw_odds > 0
            and odds.away_odds > 0
        ):
            odds_home, odds_away = _odds_implied_goals(
                odds.home_odds,
                odds.draw_odds,
                odds.away_odds,
                odds.over_2_5,
                odds.under_2_5,
            )
            combined_home = 0.5 * stat_home_goals + 0.5 * odds_home
            combined_away = 0.5 * stat_away_goals + 0.5 * odds_away
            source = "combined"
        else:
            combined_home = stat_home_goals
            combined_away = stat_away_goals
            source = "statistical"

        # Clean sheet probability using Poisson P(X=0) = e^(-lambda)
        cs_prob_home = math.exp(-combined_away)  # home team clean sheet = away scores 0
        cs_prob_away = math.exp(-combined_home)  # away team clean sheet = home scores 0

        # Store prediction for home team
        records.append(
            {
                "fixture_id": fixture.fpl_id,
                "gameweek": gameweek,
                "team_id": fixture.team_h,
                "predicted_goals_for": combined_home,
                "predicted_goals_against": combined_away,
                "clean_sheet_probability": cs_prob_home,
                "source": source,
                "computed_at": now,
            }
        )

        # Store prediction for away team
        records.append(
            {
                "fixture_id": fixture.fpl_id,
                "gameweek": gameweek,
                "team_id": fixture.team_a,
                "predicted_goals_for": combined_away,
                "predicted_goals_against": combined_home,
                "clean_sheet_probability": cs_prob_away,
                "source": source,
                "computed_at": now,
            }
        )

    if not records:
        return 0

    stmt = sqlite_insert(TeamPrediction).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            TeamPrediction.fixture_id,
            TeamPrediction.team_id,
            TeamPrediction.source,
        ],
        set_={
            col: stmt.excluded[col]
            for col in (
                "gameweek",
                "predicted_goals_for",
                "predicted_goals_against",
                "clean_sheet_probability",
                "computed_at",
            )
        },
    )
    session.execute(stmt)

    logger.info(
        "Stored %d team predictions for GW%d (%s).",
        len(records),
        gameweek,
        source if records else "n/a",
    )
    return len(records)
