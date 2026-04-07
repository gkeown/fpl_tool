from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.analysis.differentials import find_differentials
from fpl.db.models import (
    Base,
    CustomFdr,
    Gameweek,
    Player,
    PlayerFormScore,
    Team,
)

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


def _make_team(session: Session, fpl_id: int, short_name: str = "TST") -> Team:
    team = Team(
        fpl_id=fpl_id,
        code=fpl_id,
        name=f"Team {fpl_id}",
        short_name=short_name,
        strength=3,
        strength_attack_home=1200,
        strength_attack_away=1100,
        strength_defence_home=1200,
        strength_defence_away=1100,
        played=10,
        win=5,
        draw=2,
        loss=3,
        points=17,
        position=5,
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
    now_cost: int = 70,
    status: str = "a",
    minutes: int = 900,
    selected_by_percent: str = "5.0",
) -> Player:
    player = Player(
        fpl_id=fpl_id,
        code=fpl_id,
        first_name="Test",
        second_name=f"Player{fpl_id}",
        web_name=f"Player{fpl_id}",
        team_id=team_id,
        element_type=element_type,
        now_cost=now_cost,
        selected_by_percent=selected_by_percent,
        status=status,
        form="5.0",
        points_per_game="5.0",
        total_points=50,
        minutes=minutes,
        goals_scored=3,
        assists=2,
        clean_sheets=1,
        bonus=5,
        transfers_in=500,
        transfers_out=200,
        goals_conceded=5,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=1,
        red_cards=0,
        saves=0,
        starts=10,
        expected_goals="2.50",
        expected_assists="1.50",
        expected_goal_involvements="4.00",
        expected_goals_conceded="4.00",
        updated_at=_now(),
    )
    session.add(player)
    session.flush()
    return player


def _make_form_score(
    session: Session,
    player_id: int,
    gameweek: int,
    form_score: float = 60.0,
) -> PlayerFormScore:
    fs = PlayerFormScore(
        player_id=player_id,
        gameweek=gameweek,
        form_score=form_score,
        xg_component=6.0,
        xa_component=5.0,
        bps_component=6.0,
        ict_component=6.0,
        minutes_component=7.0,
        points_component=6.0,
        computed_at=_now(),
    )
    session.add(fs)
    session.flush()
    return fs


def _make_gameweek(session: Session, gw_id: int, is_current: bool = True) -> Gameweek:
    gw = Gameweek(
        id=gw_id,
        name=f"Gameweek {gw_id}",
        deadline_time="2025-03-01T11:00:00Z",
        finished=False,
        is_current=is_current,
        is_next=False,
        is_previous=False,
        updated_at=_now(),
    )
    session.add(gw)
    session.flush()
    return gw


def _make_custom_fdr(
    session: Session,
    team_id: int,
    gameweek: int,
    opponent_id: int,
    overall_difficulty: float = 2.5,
) -> CustomFdr:
    fdr = CustomFdr(
        team_id=team_id,
        gameweek=gameweek,
        opponent_id=opponent_id,
        is_home=True,
        attack_difficulty=overall_difficulty,
        defence_difficulty=overall_difficulty,
        overall_difficulty=overall_difficulty,
        computed_at=_now(),
    )
    session.add(fdr)
    session.flush()
    return fdr


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_find_differentials_returns_empty_when_no_players(
    db_session: Session,
) -> None:
    """Should return empty list when no players in DB."""
    _make_gameweek(db_session, 30)
    db_session.commit()

    result = find_differentials(db_session)
    assert result == []


def test_find_differentials_filters_by_ownership(db_session: Session) -> None:
    """Players with ownership >= max_ownership should be excluded."""
    team = _make_team(db_session, 1)
    opp = _make_team(db_session, 99)
    gw = _make_gameweek(db_session, 30)

    low_own = _make_player(db_session, 1, team.fpl_id, selected_by_percent="5.0")
    high_own = _make_player(db_session, 2, team.fpl_id, selected_by_percent="25.0")
    _make_form_score(db_session, low_own.fpl_id, gw.id, form_score=70.0)
    _make_form_score(db_session, high_own.fpl_id, gw.id, form_score=90.0)
    _make_custom_fdr(db_session, team.fpl_id, 31, opp.fpl_id, 2.0)
    db_session.commit()

    result = find_differentials(db_session, max_ownership=10.0)

    player_ids = {d.player.fpl_id for d in result}
    assert low_own.fpl_id in player_ids
    assert high_own.fpl_id not in player_ids


def test_find_differentials_filters_by_min_minutes(db_session: Session) -> None:
    """Players below min_minutes threshold should be excluded."""
    team = _make_team(db_session, 1)
    opp = _make_team(db_session, 99)
    gw = _make_gameweek(db_session, 30)

    active = _make_player(
        db_session, 1, team.fpl_id, minutes=500, selected_by_percent="4.0"
    )
    inactive = _make_player(
        db_session, 2, team.fpl_id, minutes=50, selected_by_percent="4.0"
    )
    _make_form_score(db_session, active.fpl_id, gw.id, form_score=70.0)
    _make_form_score(db_session, inactive.fpl_id, gw.id, form_score=70.0)
    _make_custom_fdr(db_session, team.fpl_id, 31, opp.fpl_id, 2.0)
    db_session.commit()

    result = find_differentials(db_session, min_minutes=200)

    player_ids = {d.player.fpl_id for d in result}
    assert active.fpl_id in player_ids
    assert inactive.fpl_id not in player_ids


def test_find_differentials_filters_by_position(db_session: Session) -> None:
    """Should only return players at the specified position."""
    team = _make_team(db_session, 1)
    opp = _make_team(db_session, 99)
    gw = _make_gameweek(db_session, 30)

    mid = _make_player(
        db_session, 1, team.fpl_id, element_type=3, selected_by_percent="5.0"
    )
    fwd = _make_player(
        db_session, 2, team.fpl_id, element_type=4, selected_by_percent="5.0"
    )
    _make_form_score(db_session, mid.fpl_id, gw.id, form_score=70.0)
    _make_form_score(db_session, fwd.fpl_id, gw.id, form_score=70.0)
    _make_custom_fdr(db_session, team.fpl_id, 31, opp.fpl_id, 2.0)
    db_session.commit()

    result = find_differentials(db_session, position=3)  # MID only

    player_ids = {d.player.fpl_id for d in result}
    assert mid.fpl_id in player_ids
    assert fwd.fpl_id not in player_ids


def test_find_differentials_ranks_by_value_score(db_session: Session) -> None:
    """Higher value_score players should rank first."""
    team = _make_team(db_session, 1)
    opp = _make_team(db_session, 99)
    gw = _make_gameweek(db_session, 30)

    # p1: good form, easy fixtures, cheap
    p1 = _make_player(
        db_session,
        1,
        team.fpl_id,
        now_cost=60,
        selected_by_percent="3.0",
    )
    # p2: poor form
    p2 = _make_player(
        db_session,
        2,
        team.fpl_id,
        now_cost=60,
        selected_by_percent="3.0",
    )

    _make_form_score(db_session, p1.fpl_id, gw.id, form_score=80.0)
    _make_form_score(db_session, p2.fpl_id, gw.id, form_score=20.0)
    _make_custom_fdr(db_session, team.fpl_id, 31, opp.fpl_id, 1.5)
    db_session.commit()

    result = find_differentials(db_session)

    assert len(result) >= 2
    assert result[0].player.fpl_id == p1.fpl_id


def test_find_differentials_top_limit(db_session: Session) -> None:
    """Result should be capped at the top argument."""
    team = _make_team(db_session, 1)
    opp = _make_team(db_session, 99)
    gw = _make_gameweek(db_session, 30)
    _make_custom_fdr(db_session, team.fpl_id, 31, opp.fpl_id, 2.0)

    for i in range(1, 11):
        p = _make_player(db_session, i, team.fpl_id, selected_by_percent="3.0")
        _make_form_score(db_session, p.fpl_id, gw.id, form_score=float(i * 5))

    db_session.commit()

    result = find_differentials(db_session, top=5)
    assert len(result) <= 5


def test_find_differentials_excludes_unavailable_players(
    db_session: Session,
) -> None:
    """Players with status != 'a' should not appear in results."""
    team = _make_team(db_session, 1)
    opp = _make_team(db_session, 99)
    gw = _make_gameweek(db_session, 30)

    available = _make_player(
        db_session, 1, team.fpl_id, status="a", selected_by_percent="4.0"
    )
    injured = _make_player(
        db_session, 2, team.fpl_id, status="i", selected_by_percent="4.0"
    )
    _make_form_score(db_session, available.fpl_id, gw.id, form_score=70.0)
    _make_form_score(db_session, injured.fpl_id, gw.id, form_score=70.0)
    _make_custom_fdr(db_session, team.fpl_id, 31, opp.fpl_id, 2.0)
    db_session.commit()

    result = find_differentials(db_session)

    player_ids = {d.player.fpl_id for d in result}
    assert available.fpl_id in player_ids
    assert injured.fpl_id not in player_ids


def test_find_differentials_value_score_calculation(db_session: Session) -> None:
    """value_score should equal form * fixture_ease / (cost/10)."""
    team = _make_team(db_session, 1)
    opp = _make_team(db_session, 99)
    gw = _make_gameweek(db_session, 30)

    p = _make_player(
        db_session,
        1,
        team.fpl_id,
        now_cost=80,
        selected_by_percent="5.0",
    )
    _make_form_score(db_session, p.fpl_id, gw.id, form_score=60.0)
    _make_custom_fdr(db_session, team.fpl_id, 31, opp.fpl_id, 2.0)  # ease = 4.0
    db_session.commit()

    result = find_differentials(db_session)

    assert len(result) == 1
    d = result[0]
    # value_score = 60.0 * (6.0 - 2.0) / (80 / 10) = 60 * 4 / 8 = 30.0
    expected = 60.0 * 4.0 / 8.0
    assert abs(d.value_score - expected) < 1e-6
