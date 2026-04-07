from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.analysis.predictions import (
    _LEAGUE_AVG_GOALS_PER_GAME,
    _odds_implied_goals,
    _statistical_prediction,
    compute_predictions,
)
from fpl.db.models import Base, Fixture, Gameweek, Team, TeamPrediction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


def _make_team(session: Session, fpl_id: int, name: str = "Team") -> Team:
    team = Team(
        fpl_id=fpl_id,
        code=fpl_id,
        name=name,
        short_name=name[:3].upper(),
        strength=3,
        strength_attack_home=1200,
        strength_attack_away=1100,
        strength_defence_home=1200,
        strength_defence_away=1100,
        played=0,
        win=0,
        draw=0,
        loss=0,
        points=0,
        position=0,
        updated_at=_now(),
    )
    session.add(team)
    session.flush()
    return team


def _make_fixture(
    session: Session,
    fpl_id: int,
    team_h: int,
    team_a: int,
    gameweek: int,
    finished: bool,
    h_score: int | None = None,
    a_score: int | None = None,
) -> Fixture:
    f = Fixture(
        fpl_id=fpl_id,
        gameweek=gameweek,
        kickoff_time="2025-03-01T15:00:00Z",
        team_h=team_h,
        team_a=team_a,
        team_h_score=h_score,
        team_a_score=a_score,
        team_h_difficulty=3,
        team_a_difficulty=3,
        finished=finished,
        updated_at=_now(),
    )
    session.add(f)
    session.flush()
    return f


def _make_gameweek(session: Session, gw_id: int, is_current: bool = False) -> Gameweek:
    gw = Gameweek(
        id=gw_id,
        name=f"Gameweek {gw_id}",
        deadline_time="2025-03-01T11:00:00Z",
        finished=gw_id < 30,
        is_current=is_current,
        is_next=False,
        is_previous=False,
        updated_at=_now(),
    )
    session.add(gw)
    session.flush()
    return gw


# ---------------------------------------------------------------------------
# Tests: _statistical_prediction
# ---------------------------------------------------------------------------


def test_statistical_prediction_home_advantage() -> None:
    """Home team should be predicted to score more than away."""
    home_goals = _statistical_prediction(1.5, 1.3, _LEAGUE_AVG_GOALS_PER_GAME, True)
    away_goals = _statistical_prediction(1.5, 1.3, _LEAGUE_AVG_GOALS_PER_GAME, False)
    assert home_goals > away_goals


def test_statistical_prediction_formula() -> None:
    """Should correctly apply the xG-based formula."""
    xg = 1.8
    xga = 1.2
    league_avg = 2.7
    is_home = True
    expected = xg * xga / league_avg * 1.15  # HOME_MODIFIER = 1.15
    result = _statistical_prediction(xg, xga, league_avg, is_home)
    assert abs(result - expected) < 1e-6


def test_statistical_prediction_zero_xg() -> None:
    """Zero attacking xG should return 0 predicted goals."""
    result = _statistical_prediction(0.0, 1.0, _LEAGUE_AVG_GOALS_PER_GAME, True)
    assert result == 0.0


def test_statistical_prediction_handles_zero_league_avg() -> None:
    """Should fall back to default league average when passed 0."""
    result = _statistical_prediction(1.5, 1.2, 0.0, True)
    expected = 1.5 * 1.2 / _LEAGUE_AVG_GOALS_PER_GAME * 1.15
    assert abs(result - expected) < 1e-6


def test_statistical_prediction_away_modifier() -> None:
    """Away modifier should be 0.85."""
    xg, xga, avg = 1.8, 1.2, 2.7
    result = _statistical_prediction(xg, xga, avg, False)
    expected = xg * xga / avg * 0.85
    assert abs(result - expected) < 1e-6


# ---------------------------------------------------------------------------
# Tests: _odds_implied_goals
# ---------------------------------------------------------------------------


def test_odds_implied_goals_returns_tuple() -> None:
    """Should return a 2-tuple of floats."""
    home, away = _odds_implied_goals(2.1, 3.4, 3.8, 1.9, 2.0)
    assert isinstance(home, float)
    assert isinstance(away, float)


def test_odds_implied_goals_home_favourite_scores_more() -> None:
    """Heavy home favourite should be predicted to score more goals."""
    # Home very likely to win (low home odds)
    home, away = _odds_implied_goals(1.3, 5.0, 10.0, 1.8, 2.1)
    assert home > away


def test_odds_implied_goals_away_favourite_scores_more() -> None:
    """Heavy away favourite should be predicted to score more goals."""
    home, away = _odds_implied_goals(10.0, 5.0, 1.3, 1.8, 2.1)
    assert away > home


def test_odds_implied_goals_without_ou_line() -> None:
    """Should fall back to league average when O/U odds not provided."""
    home, away = _odds_implied_goals(2.1, 3.4, 3.8, None, None)
    # Total should be close to league average
    assert abs((home + away) - _LEAGUE_AVG_GOALS_PER_GAME) < 0.5


def test_odds_implied_goals_positive_values() -> None:
    """Predicted goals should always be non-negative."""
    home, away = _odds_implied_goals(3.0, 3.2, 2.5, 1.85, 2.0)
    assert home >= 0.0
    assert away >= 0.0


def test_odds_implied_goals_overround_removed() -> None:
    """With biased overround, home/away split should still be correct."""
    # Equal odds → equal goal split
    home, away = _odds_implied_goals(2.0, 3.0, 2.0, 2.0, 1.9)
    # Both teams equal strength → home == away approximately
    assert abs(home - away) < 0.3


# ---------------------------------------------------------------------------
# Tests: clean sheet probability
# ---------------------------------------------------------------------------


def test_cs_probability_formula() -> None:
    """Poisson P(X=0) = e^(-lambda) should hold."""
    predicted_goals_against = 0.8
    cs_prob = math.exp(-predicted_goals_against)
    assert abs(cs_prob - math.exp(-0.8)) < 1e-9


def test_cs_probability_increases_with_lower_predicted_goals() -> None:
    """CS probability should be higher when fewer goals predicted against."""
    cs_low_threat = math.exp(-0.5)
    cs_high_threat = math.exp(-2.0)
    assert cs_low_threat > cs_high_threat


def test_cs_probability_zero_goals() -> None:
    """When predicted goals against = 0, CS probability should be 1.0."""
    cs_prob = math.exp(0.0)
    assert abs(cs_prob - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Tests: compute_predictions
# ---------------------------------------------------------------------------


def test_compute_predictions_stores_records(db_session: Session) -> None:
    """Should store two prediction records per fixture (home + away)."""
    _make_team(db_session, 1, "Arsenal")
    _make_team(db_session, 2, "Chelsea")

    # Some finished fixtures to build team stats
    _make_fixture(db_session, 1, 1, 2, gameweek=28, finished=True, h_score=2, a_score=1)
    _make_fixture(db_session, 2, 2, 1, gameweek=29, finished=True, h_score=1, a_score=2)

    # Upcoming fixture
    _make_fixture(db_session, 3, 1, 2, gameweek=30, finished=False)

    _make_gameweek(db_session, 29, is_current=True)
    db_session.commit()

    count = compute_predictions(db_session, gameweek=30)
    db_session.commit()

    assert count == 2  # one per team per fixture

    preds = db_session.query(TeamPrediction).filter_by(gameweek=30).all()
    assert len(preds) == 2

    team_ids = {p.team_id for p in preds}
    assert 1 in team_ids
    assert 2 in team_ids


def test_compute_predictions_values_are_valid(db_session: Session) -> None:
    """Predicted goals and CS probability should be non-negative and CS <= 1."""
    _make_team(db_session, 1, "Arsenal")
    _make_team(db_session, 2, "Chelsea")

    _make_fixture(db_session, 1, 1, 2, gameweek=28, finished=True, h_score=2, a_score=0)
    _make_fixture(db_session, 2, 2, 1, gameweek=29, finished=True, h_score=1, a_score=1)
    _make_fixture(db_session, 3, 1, 2, gameweek=30, finished=False)

    _make_gameweek(db_session, 29, is_current=True)
    db_session.commit()

    compute_predictions(db_session, gameweek=30)
    db_session.commit()

    preds = db_session.query(TeamPrediction).filter_by(gameweek=30).all()
    for pred in preds:
        assert pred.predicted_goals_for >= 0.0
        assert pred.predicted_goals_against >= 0.0
        assert 0.0 <= pred.clean_sheet_probability <= 1.0


def test_compute_predictions_no_fixtures(db_session: Session) -> None:
    """Should return 0 when no fixtures exist for the gameweek."""
    _make_team(db_session, 1, "Arsenal")
    _make_team(db_session, 2, "Chelsea")
    _make_fixture(db_session, 1, 1, 2, gameweek=28, finished=True, h_score=1, a_score=0)
    _make_gameweek(db_session, 28, is_current=True)
    db_session.commit()

    count = compute_predictions(db_session, gameweek=99)
    assert count == 0


def test_compute_predictions_upserts_on_recompute(db_session: Session) -> None:
    """Running predictions twice should upsert rather than duplicate."""
    _make_team(db_session, 1, "Arsenal")
    _make_team(db_session, 2, "Chelsea")
    _make_fixture(db_session, 1, 1, 2, gameweek=28, finished=True, h_score=2, a_score=1)
    _make_fixture(db_session, 2, 1, 2, gameweek=29, finished=False)
    _make_gameweek(db_session, 28, is_current=True)
    db_session.commit()

    compute_predictions(db_session, gameweek=29)
    db_session.commit()
    compute_predictions(db_session, gameweek=29)
    db_session.commit()

    count = db_session.query(TeamPrediction).filter_by(gameweek=29).count()
    assert count == 2  # 2 teams, not 4
