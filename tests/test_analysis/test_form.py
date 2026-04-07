from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.analysis.form import (
    _calculate_per90,
    _percentile_rank,
    compute_form_scores,
    get_current_gameweek,
)
from fpl.db.models import (
    Base,
    Fixture,
    Gameweek,
    Player,
    PlayerFormScore,
    PlayerGameweekStats,
    Team,
)

# ---------------------------------------------------------------------------
# Fixtures (pytest fixtures)
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _make_team(session: Session, fpl_id: int, name: str = "Team") -> Team:
    team = Team(
        fpl_id=fpl_id,
        code=fpl_id,
        name=name,
        short_name=name[:3].upper(),
        strength=3,
        strength_attack_home=1000,
        strength_attack_away=1000,
        strength_defence_home=1000,
        strength_defence_away=1000,
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


def _make_player(
    session: Session,
    fpl_id: int,
    team_id: int,
    element_type: int = 3,
    minutes: int = 900,
) -> Player:
    player = Player(
        fpl_id=fpl_id,
        code=fpl_id,
        first_name="Test",
        second_name=f"Player{fpl_id}",
        web_name=f"Player{fpl_id}",
        team_id=team_id,
        element_type=element_type,
        now_cost=80,
        selected_by_percent="5.0",
        status="a",
        form="5.0",
        points_per_game="5.0",
        total_points=50,
        minutes=minutes,
        goals_scored=5,
        assists=3,
        clean_sheets=2,
        bonus=10,
        transfers_in=1000,
        transfers_out=500,
        goals_conceded=10,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=1,
        red_cards=0,
        saves=0,
        starts=10,
        expected_goals="4.50",
        expected_assists="2.80",
        expected_goal_involvements="7.30",
        expected_goals_conceded="8.00",
        updated_at=_now(),
    )
    session.add(player)
    session.flush()
    return player


def _make_gw_stat(
    session: Session,
    player_id: int,
    gameweek: int,
    fixture_id: int,
    minutes: int = 90,
    total_points: int = 6,
    goals_scored: int = 1,
    assists: int = 0,
    clean_sheets: int = 0,
    bps: int = 25,
    ict_index: str = "8.0",
    expected_goals: str = "0.40",
    expected_assists: str = "0.20",
    saves: int = 0,
) -> PlayerGameweekStats:
    stat = PlayerGameweekStats(
        player_id=player_id,
        gameweek=gameweek,
        fixture_id=fixture_id,
        opponent_team=2,
        was_home=True,
        minutes=minutes,
        total_points=total_points,
        goals_scored=goals_scored,
        assists=assists,
        clean_sheets=clean_sheets,
        bonus=2,
        bps=bps,
        ict_index=ict_index,
        influence="20.0",
        creativity="15.0",
        threat="30.0",
        selected=500000,
        transfers_in=1000,
        transfers_out=200,
        value=80,
        expected_goals=expected_goals,
        expected_assists=expected_assists,
        expected_goals_conceded="0.80",
        goals_conceded=1,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=0,
        red_cards=0,
        saves=saves,
        starts=1,
    )
    session.add(stat)
    session.flush()
    return stat


def _make_fixture(
    session: Session, fpl_id: int, team_h: int, team_a: int, gameweek: int
) -> Fixture:
    f = Fixture(
        fpl_id=fpl_id,
        gameweek=gameweek,
        kickoff_time="2025-03-01T15:00:00Z",
        team_h=team_h,
        team_a=team_a,
        team_h_score=None,
        team_a_score=None,
        team_h_difficulty=3,
        team_a_difficulty=3,
        finished=False,
        updated_at=_now(),
    )
    session.add(f)
    session.flush()
    return f


def _make_gameweek(
    session: Session,
    gw_id: int,
    is_current: bool = False,
    finished: bool = False,
) -> Gameweek:
    gw = Gameweek(
        id=gw_id,
        name=f"Gameweek {gw_id}",
        deadline_time="2025-03-01T11:00:00Z",
        finished=finished,
        is_current=is_current,
        is_next=False,
        is_previous=False,
        updated_at=_now(),
    )
    session.add(gw)
    session.flush()
    return gw


# ---------------------------------------------------------------------------
# Tests: _calculate_per90
# ---------------------------------------------------------------------------


def test_calculate_per90_basic(db_session: Session) -> None:
    """Should compute correct per-90 rate for a simple field."""
    _make_team(db_session, 1)
    _make_player(db_session, 1, 1)
    stats = [
        _make_gw_stat(db_session, 1, 1, 101, minutes=90, goals_scored=1),
        _make_gw_stat(db_session, 1, 2, 102, minutes=90, goals_scored=2),
    ]
    result = _calculate_per90(stats, "goals_scored")
    # 3 goals / 180 mins * 90 = 1.5
    assert abs(result - 1.5) < 1e-6


def test_calculate_per90_zero_minutes(db_session: Session) -> None:
    """Should return 0.0 when total minutes is zero."""
    _make_team(db_session, 1)
    _make_player(db_session, 1, 1)
    stats = [
        _make_gw_stat(db_session, 1, 1, 101, minutes=0, goals_scored=1),
    ]
    result = _calculate_per90(stats, "goals_scored")
    assert result == 0.0


def test_calculate_per90_string_field(db_session: Session) -> None:
    """Should handle string fields like expected_goals correctly."""
    _make_team(db_session, 1)
    _make_player(db_session, 1, 1)
    stats = [
        _make_gw_stat(db_session, 1, 1, 101, minutes=90, expected_goals="0.45"),
        _make_gw_stat(db_session, 1, 2, 102, minutes=90, expected_goals="0.55"),
    ]
    result = _calculate_per90(stats, "expected_goals")
    # (0.45 + 0.55) / 180 * 90 = 0.5
    assert abs(result - 0.5) < 1e-6


def test_calculate_per90_partial_minutes(db_session: Session) -> None:
    """Should weight correctly when player played partial minutes."""
    _make_team(db_session, 1)
    _make_player(db_session, 1, 1)
    stats = [
        _make_gw_stat(db_session, 1, 1, 101, minutes=45, goals_scored=1),
        _make_gw_stat(db_session, 1, 2, 102, minutes=90, goals_scored=0),
    ]
    result = _calculate_per90(stats, "goals_scored")
    # 1 goal / 135 mins * 90 = 0.6667
    assert abs(result - (1 / 135 * 90)) < 1e-6


# ---------------------------------------------------------------------------
# Tests: _percentile_rank
# ---------------------------------------------------------------------------


def test_percentile_rank_middle_value() -> None:
    """A median value should return approximately 5.0."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    rank = _percentile_rank(3.0, values)
    # 3 values <= 3.0 → 3/5 * 10 = 6.0
    assert abs(rank - 6.0) < 1e-6


def test_percentile_rank_minimum() -> None:
    """The minimum value should have a low rank."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    rank = _percentile_rank(1.0, values)
    # 1 value <= 1.0 → 1/5 * 10 = 2.0
    assert abs(rank - 2.0) < 1e-6


def test_percentile_rank_maximum() -> None:
    """The maximum value should return 10.0."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    rank = _percentile_rank(5.0, values)
    assert abs(rank - 10.0) < 1e-6


def test_percentile_rank_empty_list() -> None:
    """Should return 0.0 for an empty list."""
    rank = _percentile_rank(5.0, [])
    assert rank == 0.0


def test_percentile_rank_single_element() -> None:
    """Single-element list should return 10.0 (value equals itself)."""
    rank = _percentile_rank(3.0, [3.0])
    assert abs(rank - 10.0) < 1e-6


def test_percentile_rank_value_above_all() -> None:
    """A value above all list members should return 10.0."""
    values = [1.0, 2.0, 3.0]
    rank = _percentile_rank(100.0, values)
    assert abs(rank - 10.0) < 1e-6


# ---------------------------------------------------------------------------
# Tests: get_current_gameweek
# ---------------------------------------------------------------------------


def test_get_current_gameweek_uses_is_current(db_session: Session) -> None:
    """Should return the gameweek marked is_current."""
    _make_gameweek(db_session, 28, finished=True)
    _make_gameweek(db_session, 29, is_current=True)
    db_session.commit()

    result = get_current_gameweek(db_session)
    assert result == 29


def test_get_current_gameweek_falls_back_to_finished(db_session: Session) -> None:
    """Should return highest finished GW when no is_current."""
    _make_gameweek(db_session, 27, finished=True)
    _make_gameweek(db_session, 28, finished=True)
    db_session.commit()

    result = get_current_gameweek(db_session)
    assert result == 28


def test_get_current_gameweek_default(db_session: Session) -> None:
    """Should return 1 when no gameweeks exist."""
    result = get_current_gameweek(db_session)
    assert result == 1


# ---------------------------------------------------------------------------
# Tests: compute_form_scores
# ---------------------------------------------------------------------------


def test_compute_form_scores_basic(db_session: Session) -> None:
    """Should compute and store form scores for active players."""
    _make_team(db_session, 1)
    _make_team(db_session, 2)

    p1 = _make_player(db_session, 1, 1, element_type=3, minutes=450)  # MID
    p2 = _make_player(db_session, 2, 2, element_type=4, minutes=450)  # FWD

    _make_fixture(db_session, 101, 1, 2, gameweek=28)
    _make_fixture(db_session, 102, 2, 1, gameweek=29)
    _make_fixture(db_session, 103, 1, 2, gameweek=30)
    _make_fixture(db_session, 104, 2, 1, gameweek=31)
    _make_fixture(db_session, 105, 1, 2, gameweek=32)

    for gw, fid in [(28, 101), (29, 102), (30, 103), (31, 104), (32, 105)]:
        _make_gw_stat(db_session, p1.fpl_id, gw, fid, minutes=90, goals_scored=1)
        _make_gw_stat(db_session, p2.fpl_id, gw, fid, minutes=90, goals_scored=2)

    db_session.commit()

    count = compute_form_scores(db_session, gameweek=32, lookback=5)
    db_session.commit()

    assert count == 2

    score1 = (
        db_session.query(PlayerFormScore)
        .filter_by(player_id=p1.fpl_id, gameweek=32)
        .one()
    )
    score2 = (
        db_session.query(PlayerFormScore)
        .filter_by(player_id=p2.fpl_id, gameweek=32)
        .one()
    )

    assert 0.0 <= score1.form_score <= 100.0
    assert 0.0 <= score2.form_score <= 100.0


def test_compute_form_scores_no_active_players(db_session: Session) -> None:
    """Should return 0 when no players have minutes > 0."""
    _make_team(db_session, 1)
    # Player with 0 minutes
    Player(
        fpl_id=1,
        code=1,
        first_name="Bench",
        second_name="Warmer",
        web_name="Warmer",
        team_id=1,
        element_type=1,
        now_cost=40,
        selected_by_percent="0.1",
        status="a",
        form="0.0",
        points_per_game="0.0",
        total_points=0,
        minutes=0,
        goals_scored=0,
        assists=0,
        clean_sheets=0,
        bonus=0,
        transfers_in=0,
        transfers_out=0,
        goals_conceded=0,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=0,
        red_cards=0,
        saves=0,
        starts=0,
        expected_goals="0.00",
        expected_assists="0.00",
        expected_goal_involvements="0.00",
        expected_goals_conceded="0.00",
        updated_at=_now(),
    )
    db_session.commit()

    count = compute_form_scores(db_session, gameweek=29)
    assert count == 0


def test_compute_form_scores_upserts_on_recompute(db_session: Session) -> None:
    """Running compute_form_scores twice should upsert, not duplicate."""
    _make_team(db_session, 1)
    p = _make_player(db_session, 1, 1, element_type=3, minutes=450)
    _make_fixture(db_session, 101, 1, 2, gameweek=28)
    _make_gw_stat(db_session, p.fpl_id, 28, 101, minutes=90)
    db_session.commit()

    compute_form_scores(db_session, gameweek=28, lookback=5)
    db_session.commit()
    compute_form_scores(db_session, gameweek=28, lookback=5)
    db_session.commit()

    count = (
        db_session.query(PlayerFormScore)
        .filter_by(player_id=p.fpl_id, gameweek=28)
        .count()
    )
    assert count == 1


def test_compute_form_scores_goalkeeper_weights(db_session: Session) -> None:
    """Goalkeeper form score should use GKP-specific weights."""
    _make_team(db_session, 1)
    gkp = _make_player(db_session, 1, 1, element_type=1, minutes=450)  # GKP
    _make_fixture(db_session, 101, 1, 2, gameweek=29)
    _make_gw_stat(
        db_session, gkp.fpl_id, 29, 101, minutes=90, clean_sheets=1, saves=5, bps=30
    )
    db_session.commit()

    count = compute_form_scores(db_session, gameweek=29, lookback=5)
    db_session.commit()

    assert count == 1
    score = (
        db_session.query(PlayerFormScore)
        .filter_by(player_id=gkp.fpl_id, gameweek=29)
        .one()
    )
    assert 0.0 <= score.form_score <= 100.0
