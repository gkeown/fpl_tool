from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.analysis.captaincy import (
    _compute_captain_score,
    _get_haul_rate,
    _get_xg_xa_per90,
    pick_captains,
)
from fpl.db.models import (
    Base,
    CustomFdr,
    Gameweek,
    Player,
    PlayerFormScore,
    PlayerGameweekStats,
    Team,
    UnderstatMatch,
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
) -> Player:
    player = Player(
        fpl_id=fpl_id,
        code=fpl_id,
        first_name="Test",
        second_name=f"Player{fpl_id}",
        web_name=f"Player{fpl_id}",
        team_id=team_id,
        element_type=element_type,
        now_cost=100,
        selected_by_percent="10.0",
        status="a",
        form="6.0",
        points_per_game="6.0",
        total_points=80,
        minutes=900,
        goals_scored=8,
        assists=4,
        clean_sheets=0,
        bonus=15,
        transfers_in=1000,
        transfers_out=300,
        goals_conceded=5,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=1,
        red_cards=0,
        saves=0,
        starts=10,
        expected_goals="6.00",
        expected_assists="3.00",
        expected_goal_involvements="9.00",
        expected_goals_conceded="4.00",
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
    expected_goals: str = "0.40",
    expected_assists: str = "0.20",
) -> PlayerGameweekStats:
    stat = PlayerGameweekStats(
        player_id=player_id,
        gameweek=gameweek,
        fixture_id=fixture_id,
        opponent_team=2,
        was_home=True,
        minutes=minutes,
        total_points=total_points,
        goals_scored=1,
        assists=0,
        clean_sheets=0,
        bonus=2,
        bps=25,
        ict_index="8.0",
        influence="20.0",
        creativity="15.0",
        threat="30.0",
        selected=500000,
        transfers_in=1000,
        transfers_out=200,
        value=100,
        expected_goals=expected_goals,
        expected_assists=expected_assists,
        expected_goals_conceded="0.60",
        goals_conceded=1,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=0,
        red_cards=0,
        saves=0,
        starts=1,
    )
    session.add(stat)
    session.flush()
    return stat


def _make_form_score(
    session: Session,
    player_id: int,
    gameweek: int,
    form_score: float = 75.0,
) -> PlayerFormScore:
    fs = PlayerFormScore(
        player_id=player_id,
        gameweek=gameweek,
        form_score=form_score,
        xg_component=7.5,
        xa_component=5.5,
        bps_component=6.0,
        ict_component=7.0,
        minutes_component=8.0,
        points_component=7.5,
        computed_at=_now(),
    )
    session.add(fs)
    session.flush()
    return fs


def _make_gameweek(session: Session, gw_id: int, is_current: bool = False) -> Gameweek:
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
    overall_difficulty: float = 2.0,
    is_home: bool = True,
) -> CustomFdr:
    fdr = CustomFdr(
        team_id=team_id,
        gameweek=gameweek,
        opponent_id=opponent_id,
        is_home=is_home,
        attack_difficulty=overall_difficulty,
        defence_difficulty=overall_difficulty,
        overall_difficulty=overall_difficulty,
        computed_at=_now(),
    )
    session.add(fdr)
    session.flush()
    return fdr


# ---------------------------------------------------------------------------
# Tests: captain_score formula components
# ---------------------------------------------------------------------------


def test_captain_score_all_components_zero() -> None:
    """With all zero inputs and no home bonus, score should be 0."""
    score = _compute_captain_score(
        form_score=0.0,
        fixture_ease=0.0,
        xg_per90=0.0,
        xa_per90=0.0,
        is_home=False,
        haul_rate=0.0,
        max_xg=1.0,
        max_xa=1.0,
    )
    assert abs(score) < 1e-9


def test_captain_score_home_bonus_applied() -> None:
    """Home bonus (2.0) should be applied with weight 0.10."""
    score_home = _compute_captain_score(
        form_score=0.0,
        fixture_ease=0.0,
        xg_per90=0.0,
        xa_per90=0.0,
        is_home=True,
        haul_rate=0.0,
        max_xg=1.0,
        max_xa=1.0,
    )
    score_away = _compute_captain_score(
        form_score=0.0,
        fixture_ease=0.0,
        xg_per90=0.0,
        xa_per90=0.0,
        is_home=False,
        haul_rate=0.0,
        max_xg=1.0,
        max_xa=1.0,
    )
    # home bonus contribution = 0.10 * 2.0 = 0.2
    assert abs(score_home - score_away - 0.2) < 1e-9


def test_captain_score_form_dominates() -> None:
    """Form (weight 0.35) should significantly raise score."""
    score_high_form = _compute_captain_score(
        form_score=100.0,
        fixture_ease=0.0,
        xg_per90=0.0,
        xa_per90=0.0,
        is_home=False,
        haul_rate=0.0,
        max_xg=1.0,
        max_xa=1.0,
    )
    # form_norm = 100/100*10 = 10; contribution = 0.35 * 10 = 3.5
    assert abs(score_high_form - 3.5) < 1e-9


def test_captain_score_max_all_components() -> None:
    """Maximum inputs (all at ceiling) should produce a score close to 10."""
    score = _compute_captain_score(
        form_score=100.0,  # form_norm = 10, weight 0.35 → 3.5
        fixture_ease=5.0,  # ease_norm = 10, weight 0.25 → 2.5
        xg_per90=1.0,  # xg_norm = 10, weight 0.15 → 1.5
        xa_per90=1.0,  # xa_norm = 10, weight 0.10 → 1.0
        is_home=True,  # bonus = 2.0, weight 0.10 → 0.2
        haul_rate=1.0,  # haul_norm = 10, weight 0.05 → 0.5
        max_xg=1.0,
        max_xa=1.0,
    )
    # 3.5 + 2.5 + 1.5 + 1.0 + 0.2 + 0.5 = 9.2
    assert abs(score - 9.2) < 1e-6


def test_captain_score_haul_rate_component() -> None:
    """Haul rate of 0.5 should contribute 0.05 * 5.0 = 0.25."""
    score_with = _compute_captain_score(
        form_score=0.0,
        fixture_ease=0.0,
        xg_per90=0.0,
        xa_per90=0.0,
        is_home=False,
        haul_rate=0.5,
        max_xg=1.0,
        max_xa=1.0,
    )
    assert abs(score_with - 0.25) < 1e-9


# ---------------------------------------------------------------------------
# Tests: haul_rate calculation
# ---------------------------------------------------------------------------


def test_haul_rate_all_hauls(db_session: Session) -> None:
    """Player who scored >= 10 pts every GW should have haul_rate=1.0."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    for gw in range(26, 31):
        _make_gw_stat(db_session, player.fpl_id, gw, gw * 100, total_points=12)
    _make_gameweek(db_session, 30, is_current=True)
    db_session.commit()

    rate = _get_haul_rate(db_session, player.fpl_id, current_gw=30)
    assert abs(rate - 1.0) < 1e-9


def test_haul_rate_no_hauls(db_session: Session) -> None:
    """Player who never scored >= 10 pts should have haul_rate=0.0."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    for gw in range(26, 31):
        _make_gw_stat(db_session, player.fpl_id, gw, gw * 100, total_points=6)
    _make_gameweek(db_session, 30, is_current=True)
    db_session.commit()

    rate = _get_haul_rate(db_session, player.fpl_id, current_gw=30)
    assert abs(rate - 0.0) < 1e-9


def test_haul_rate_partial(db_session: Session) -> None:
    """Player with 2 hauls out of 4 games should have rate=0.5."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    _make_gw_stat(db_session, player.fpl_id, 27, 2700, total_points=14)
    _make_gw_stat(db_session, player.fpl_id, 28, 2800, total_points=6)
    _make_gw_stat(db_session, player.fpl_id, 29, 2900, total_points=15)
    _make_gw_stat(db_session, player.fpl_id, 30, 3000, total_points=3)
    _make_gameweek(db_session, 30, is_current=True)
    db_session.commit()

    rate = _get_haul_rate(db_session, player.fpl_id, current_gw=30)
    assert abs(rate - 0.5) < 1e-9


def test_haul_rate_no_data(db_session: Session) -> None:
    """Player with no GW data should have haul_rate=0.0."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    db_session.commit()

    rate = _get_haul_rate(db_session, player.fpl_id, current_gw=30)
    assert abs(rate - 0.0) < 1e-9


# ---------------------------------------------------------------------------
# Tests: pick_captains
# ---------------------------------------------------------------------------


def test_pick_captains_returns_empty_when_no_form_data(db_session: Session) -> None:
    """Should return an empty list when no form scores are computed."""
    _make_team(db_session, 1)
    _make_player(db_session, 1, 1)
    _make_gameweek(db_session, 30, is_current=True)
    db_session.commit()

    result = pick_captains(db_session, player_ids=None, top=5)
    assert result == []


def test_pick_captains_considers_all_when_no_squad(db_session: Session) -> None:
    """With player_ids=None, all players with form data are considered."""
    team = _make_team(db_session, 1)
    p1 = _make_player(db_session, 1, team.fpl_id)
    p2 = _make_player(db_session, 2, team.fpl_id)
    _make_gameweek(db_session, 30, is_current=True)
    _make_form_score(db_session, p1.fpl_id, 30, form_score=80.0)
    _make_form_score(db_session, p2.fpl_id, 30, form_score=60.0)
    db_session.commit()

    result = pick_captains(db_session, player_ids=None, top=5)

    assert len(result) == 2
    # Player with higher form should rank first
    assert result[0].player.fpl_id == p1.fpl_id


def test_pick_captains_filters_to_squad(db_session: Session) -> None:
    """With player_ids provided, only those players should be candidates."""
    team = _make_team(db_session, 1)
    p1 = _make_player(db_session, 1, team.fpl_id)
    p2 = _make_player(db_session, 2, team.fpl_id)
    _make_gameweek(db_session, 30, is_current=True)
    _make_form_score(db_session, p1.fpl_id, 30, form_score=80.0)
    _make_form_score(db_session, p2.fpl_id, 30, form_score=90.0)
    db_session.commit()

    # Only pass player 1 in the squad
    result = pick_captains(db_session, player_ids=[p1.fpl_id], top=5)

    assert len(result) == 1
    assert result[0].player.fpl_id == p1.fpl_id


def test_pick_captains_top_limit(db_session: Session) -> None:
    """Result should be capped at the *top* argument."""
    team = _make_team(db_session, 1)
    for i in range(1, 8):
        p = _make_player(db_session, i, team.fpl_id)
        _make_form_score(db_session, p.fpl_id, 30, form_score=float(i * 10))
    _make_gameweek(db_session, 30, is_current=True)
    db_session.commit()

    result = pick_captains(db_session, player_ids=None, top=3)

    assert len(result) == 3


def test_pick_captains_fixture_ease_affects_ranking(db_session: Session) -> None:
    """Easier fixture should outscore same form with harder fix."""
    team1 = _make_team(db_session, 1)
    team2 = _make_team(db_session, 2)
    team3 = _make_team(db_session, 3)

    p_easy = _make_player(db_session, 1, team1.fpl_id)
    p_hard = _make_player(db_session, 2, team2.fpl_id)

    _make_gameweek(db_session, 30, is_current=True)

    # Equal form scores
    _make_form_score(db_session, p_easy.fpl_id, 30, form_score=70.0)
    _make_form_score(db_session, p_hard.fpl_id, 30, form_score=70.0)

    # Easy fixture for p_easy (FDR=1.5 → ease=4.5)
    _make_custom_fdr(db_session, team1.fpl_id, 31, team3.fpl_id, overall_difficulty=1.5)
    # Hard fixture for p_hard (FDR=4.5 → ease=1.5)
    _make_custom_fdr(db_session, team2.fpl_id, 31, team3.fpl_id, overall_difficulty=4.5)

    db_session.commit()

    result = pick_captains(db_session, player_ids=[p_easy.fpl_id, p_hard.fpl_id], top=2)

    assert len(result) == 2
    assert result[0].player.fpl_id == p_easy.fpl_id


def test_pick_captains_uses_understat_xg(db_session: Session) -> None:
    """xG/90 should be read from Understat season_aggregate when available."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    _make_gameweek(db_session, 30, is_current=True)
    _make_form_score(db_session, player.fpl_id, 30, form_score=70.0)

    # Add Understat season aggregate with known xG/xA
    agg = UnderstatMatch(
        player_id=player.fpl_id,
        date="season_aggregate",
        opponent="season_aggregate",
        was_home=True,
        minutes=900,
        goals=8,
        xg=9.0,
        assists=4,
        xa=3.6,
        shots=40,
        key_passes=20,
        npg=8,
        npxg=8.5,
    )
    db_session.add(agg)
    db_session.commit()

    xg, xa = _get_xg_xa_per90(db_session, player.fpl_id, current_gw=30)

    # 9.0 xg / 900 mins * 90 = 0.9
    assert abs(xg - 0.9) < 1e-6
    # 3.6 xa / 900 mins * 90 = 0.36
    assert abs(xa - 0.36) < 1e-6


def test_pick_captains_xg_falls_back_to_gw_stats(db_session: Session) -> None:
    """Without Understat data, xG/90 should be derived from GW stats."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    _make_gameweek(db_session, 30, is_current=True)

    # 2 GW stats, 90 mins each, 0.40 xg each → 0.80 total / 180 mins * 90 = 0.40 per90
    _make_gw_stat(
        db_session,
        player.fpl_id,
        29,
        2900,
        minutes=90,
        expected_goals="0.40",
        expected_assists="0.20",
    )
    _make_gw_stat(
        db_session,
        player.fpl_id,
        30,
        3000,
        minutes=90,
        expected_goals="0.40",
        expected_assists="0.20",
    )
    db_session.commit()

    xg, xa = _get_xg_xa_per90(db_session, player.fpl_id, current_gw=30)

    assert abs(xg - 0.40) < 1e-6
    assert abs(xa - 0.20) < 1e-6
