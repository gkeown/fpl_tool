from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.analysis.fdr import TeamSeasonStats, _normalize_to_range, get_team_season_stats
from fpl.db.models import Base, Fixture, Team

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


# ---------------------------------------------------------------------------
# Tests: _normalize_to_range
# ---------------------------------------------------------------------------


def test_normalize_to_range_midpoint() -> None:
    """Middle value should map to middle of output range."""
    result = _normalize_to_range(5.0, 0.0, 10.0, 1.0, 5.0)
    assert abs(result - 3.0) < 1e-6


def test_normalize_to_range_minimum() -> None:
    """Minimum input should map to output minimum."""
    result = _normalize_to_range(0.0, 0.0, 10.0, 1.0, 5.0)
    assert abs(result - 1.0) < 1e-6


def test_normalize_to_range_maximum() -> None:
    """Maximum input should map to output maximum."""
    result = _normalize_to_range(10.0, 0.0, 10.0, 1.0, 5.0)
    assert abs(result - 5.0) < 1e-6


def test_normalize_to_range_equal_bounds() -> None:
    """When min == max, should return midpoint of output range."""
    result = _normalize_to_range(5.0, 5.0, 5.0, 1.0, 5.0)
    assert abs(result - 3.0) < 1e-6


# ---------------------------------------------------------------------------
# Tests: get_team_season_stats
# ---------------------------------------------------------------------------


def test_get_team_season_stats_basic(db_session: Session) -> None:
    """Should compute correct goals scored/conceded per game from finished fixtures."""
    _make_team(db_session, 1, "Arsenal")
    _make_team(db_session, 2, "Chelsea")

    # Arsenal 2-1 Chelsea
    _make_fixture(db_session, 1, 1, 2, gameweek=1, finished=True, h_score=2, a_score=1)
    # Chelsea 3-0 Arsenal
    _make_fixture(db_session, 2, 2, 1, gameweek=2, finished=True, h_score=3, a_score=0)
    db_session.commit()

    stats = get_team_season_stats(db_session)

    assert 1 in stats
    assert 2 in stats

    arsenal = stats[1]
    assert arsenal.games_played == 2
    assert arsenal.goals_scored == 2  # 2 home + 0 away
    assert arsenal.goals_conceded == 4  # 1 conceded home + 3 conceded away
    assert abs(arsenal.goals_per_game - 1.0) < 1e-6
    assert abs(arsenal.goals_conceded_per_game - 2.0) < 1e-6

    chelsea = stats[2]
    assert chelsea.games_played == 2
    assert chelsea.goals_scored == 4  # 1 away + 3 home
    assert chelsea.goals_conceded == 2  # 2 conceded away + 0 conceded home
    assert abs(chelsea.goals_per_game - 2.0) < 1e-6
    assert abs(chelsea.goals_conceded_per_game - 1.0) < 1e-6


def test_get_team_season_stats_excludes_unfinished(db_session: Session) -> None:
    """Unfinished fixtures should not contribute to stats."""
    _make_team(db_session, 1, "Arsenal")
    _make_team(db_session, 2, "Chelsea")

    _make_fixture(db_session, 1, 1, 2, gameweek=1, finished=True, h_score=2, a_score=0)
    _make_fixture(db_session, 2, 2, 1, gameweek=2, finished=False)  # upcoming
    db_session.commit()

    stats = get_team_season_stats(db_session)

    # Only 1 finished fixture
    assert stats[1].games_played == 1
    assert stats[2].games_played == 1


def test_get_team_season_stats_empty_db(db_session: Session) -> None:
    """Should return empty dict when no finished fixtures exist."""
    stats = get_team_season_stats(db_session)
    assert stats == {}


def test_get_team_season_stats_goals_per_game(db_session: Session) -> None:
    """goals_per_game should be goals_scored / games_played."""
    _make_team(db_session, 1, "Arsenal")
    _make_team(db_session, 2, "Chelsea")
    _make_team(db_session, 3, "Liverpool")

    # 3 fixtures for Arsenal: scored 6, played 3 → 2.0 per game
    _make_fixture(db_session, 1, 1, 2, gameweek=1, finished=True, h_score=2, a_score=1)
    _make_fixture(db_session, 2, 1, 3, gameweek=2, finished=True, h_score=3, a_score=0)
    _make_fixture(db_session, 3, 2, 1, gameweek=3, finished=True, h_score=1, a_score=1)
    db_session.commit()

    stats = get_team_season_stats(db_session)
    arsenal = stats[1]
    assert arsenal.games_played == 3
    assert arsenal.goals_scored == 6
    assert abs(arsenal.goals_per_game - 2.0) < 1e-6


# ---------------------------------------------------------------------------
# Tests: TeamSeasonStats dataclass
# ---------------------------------------------------------------------------


def test_team_season_stats_is_dataclass() -> None:
    """TeamSeasonStats should be a proper dataclass with correct fields."""
    import dataclasses

    assert dataclasses.is_dataclass(TeamSeasonStats)

    stats = TeamSeasonStats(
        team_id=1,
        games_played=10,
        goals_scored=20,
        goals_conceded=8,
        xg=1.8,
        xga=0.7,
        goals_per_game=2.0,
        goals_conceded_per_game=0.8,
    )
    assert stats.team_id == 1
    assert stats.games_played == 10
    assert stats.xg == 1.8
    assert stats.xga == 0.7
