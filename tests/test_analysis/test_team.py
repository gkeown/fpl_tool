from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.analysis.team import (
    _compute_minutes_probability,
    analyse_team,
)
from fpl.db.models import (
    Base,
    CustomFdr,
    Gameweek,
    MyAccount,
    MyTeamPlayer,
    Player,
    PlayerFormScore,
    PlayerGameweekStats,
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
    status: str = "a",
    news: str | None = None,
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
        status=status,
        news=news,
        form="5.0",
        points_per_game="5.0",
        total_points=50,
        minutes=450,
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
        starts=5,
        expected_goals="2.50",
        expected_assists="1.50",
        expected_goal_involvements="4.00",
        expected_goals_conceded="4.00",
        updated_at=_now(),
    )
    session.add(player)
    session.flush()
    return player


def _make_my_team_player(
    session: Session,
    player_id: int,
    position: int,
    is_captain: bool = False,
    is_vice_captain: bool = False,
) -> MyTeamPlayer:
    mtp = MyTeamPlayer(
        player_id=player_id,
        selling_price=80,
        purchase_price=75,
        position=position,
        is_captain=is_captain,
        is_vice_captain=is_vice_captain,
        multiplier=2 if is_captain else 1,
        fetched_at=_now(),
    )
    session.add(mtp)
    session.flush()
    return mtp


def _make_gw_stat(
    session: Session,
    player_id: int,
    gameweek: int,
    fixture_id: int,
    minutes: int = 90,
    total_points: int = 6,
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
        bonus=1,
        bps=20,
        ict_index="6.0",
        influence="15.0",
        creativity="10.0",
        threat="20.0",
        selected=500000,
        transfers_in=500,
        transfers_out=100,
        value=80,
        expected_goals="0.35",
        expected_assists="0.15",
        expected_goals_conceded="0.80",
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
    form_score: float = 70.0,
) -> PlayerFormScore:
    fs = PlayerFormScore(
        player_id=player_id,
        gameweek=gameweek,
        form_score=form_score,
        xg_component=7.0,
        xa_component=5.0,
        bps_component=6.0,
        ict_component=6.0,
        minutes_component=8.0,
        points_component=7.0,
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
    overall_difficulty: float = 3.0,
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


def _make_account(
    session: Session, bank: int = 15, free_transfers: int = 2
) -> MyAccount:
    acc = MyAccount(
        id=1,
        fpl_team_id=12345,
        player_name="Test Manager",
        overall_points=1500,
        overall_rank=100000,
        bank=bank,
        total_transfers=10,
        free_transfers=free_transfers,
        gameweek_points=50,
        fetched_at=_now(),
    )
    session.add(acc)
    session.flush()
    return acc


# ---------------------------------------------------------------------------
# Tests: analyse_team returns None when no team data
# ---------------------------------------------------------------------------


def test_analyse_team_returns_none_when_no_team(db_session: Session) -> None:
    """Should return None when MyTeamPlayer table is empty."""
    result = analyse_team(db_session)
    assert result is None


# ---------------------------------------------------------------------------
# Tests: analyse_team with populated team data
# ---------------------------------------------------------------------------


def test_analyse_team_returns_team_analysis(db_session: Session) -> None:
    """Should return a TeamAnalysis with player entries when team is loaded."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    _make_my_team_player(db_session, player.fpl_id, position=1, is_captain=True)
    _make_gameweek(db_session, 30, is_current=True)
    _make_account(db_session)
    db_session.commit()

    result = analyse_team(db_session)

    assert result is not None
    assert len(result.players) == 1
    assert result.players[0].is_captain is True
    assert result.players[0].is_starter is True  # position 1 <= 11


def test_analyse_team_starters_and_bench(db_session: Session) -> None:
    """Players in position <= 11 should be starters; positions 12-15 are bench."""
    team = _make_team(db_session, 1)
    p1 = _make_player(db_session, 1, team.fpl_id)
    p2 = _make_player(db_session, 2, team.fpl_id)
    _make_my_team_player(db_session, p1.fpl_id, position=1)
    _make_my_team_player(db_session, p2.fpl_id, position=12)
    _make_gameweek(db_session, 30, is_current=True)
    _make_account(db_session)
    db_session.commit()

    result = analyse_team(db_session)

    assert result is not None
    starters = [pa for pa in result.players if pa.is_starter]
    bench = [pa for pa in result.players if not pa.is_starter]
    assert len(starters) == 1
    assert len(bench) == 1


def test_analyse_team_identifies_injured_player(db_session: Session) -> None:
    """Should flag injured starting player in weak_spots."""
    team = _make_team(db_session, 1)
    player = _make_player(
        db_session, 1, team.fpl_id, status="i", news="Hamstring injury"
    )
    _make_my_team_player(db_session, player.fpl_id, position=1)
    _make_gameweek(db_session, 30, is_current=True)
    _make_account(db_session)
    db_session.commit()

    result = analyse_team(db_session)

    assert result is not None
    assert any("injured" in issue.lower() for issue in result.weak_spots)


def test_analyse_team_identifies_poor_form(db_session: Session) -> None:
    """Should flag a starting player with form_score < 30 as a weak spot."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    _make_my_team_player(db_session, player.fpl_id, position=5)
    _make_form_score(db_session, player.fpl_id, gameweek=30, form_score=15.0)
    _make_gameweek(db_session, 30, is_current=True)
    _make_account(db_session)
    db_session.commit()

    result = analyse_team(db_session)

    assert result is not None
    assert any("poor form" in issue.lower() for issue in result.weak_spots)


def test_analyse_team_tough_fixtures_flagged(db_session: Session) -> None:
    """Starter with avg FDR > 3.5 across upcoming fixtures should be flagged."""
    team1 = _make_team(db_session, 1)
    team2 = _make_team(db_session, 2)
    player = _make_player(db_session, 1, team1.fpl_id)
    _make_my_team_player(db_session, player.fpl_id, position=5)
    _make_gameweek(db_session, 30, is_current=True)
    _make_account(db_session)

    # Add tough upcoming fixtures (FDR 4.5 average)
    for gw in range(31, 36):
        _make_custom_fdr(
            db_session, team1.fpl_id, gw, team2.fpl_id, overall_difficulty=4.5
        )

    db_session.commit()

    result = analyse_team(db_session)

    assert result is not None
    assert any("tough" in issue.lower() for issue in result.weak_spots)


def test_analyse_team_bank_and_free_transfers(db_session: Session) -> None:
    """Bank and free_transfers should be read from MyAccount."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    _make_my_team_player(db_session, player.fpl_id, position=1)
    _make_gameweek(db_session, 30, is_current=True)
    _make_account(db_session, bank=25, free_transfers=1)
    db_session.commit()

    result = analyse_team(db_session)

    assert result is not None
    assert result.bank == 25
    assert result.free_transfers == 1


def test_analyse_team_total_strength_only_starters(db_session: Session) -> None:
    """total_strength should only sum expected_values for the starting XI."""
    team = _make_team(db_session, 1)
    p1 = _make_player(db_session, 1, team.fpl_id)
    p2 = _make_player(db_session, 2, team.fpl_id)
    _make_my_team_player(db_session, p1.fpl_id, position=1)
    _make_my_team_player(db_session, p2.fpl_id, position=12)  # bench
    _make_gameweek(db_session, 30, is_current=True)
    _make_account(db_session)
    db_session.commit()

    result = analyse_team(db_session)

    assert result is not None
    # total_strength should equal just the starter's expected_value
    starter_vals = sum(pa.expected_value for pa in result.players if pa.is_starter)
    assert abs(result.total_strength - starter_vals) < 1e-9


# ---------------------------------------------------------------------------
# Tests: minutes_probability calculation
# ---------------------------------------------------------------------------


def test_minutes_probability_all_starts(db_session: Session) -> None:
    """Player who always played 90 mins should have probability 1.0."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    for gw in range(26, 31):
        _make_gw_stat(db_session, player.fpl_id, gw, gw * 100, minutes=90)
    _make_gameweek(db_session, 30, is_current=True)
    db_session.commit()

    prob = _compute_minutes_probability(db_session, player.fpl_id, current_gw=30)
    assert abs(prob - 1.0) < 1e-9


def test_minutes_probability_no_starts(db_session: Session) -> None:
    """Player who never played should have probability 0.0."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    for gw in range(26, 31):
        _make_gw_stat(db_session, player.fpl_id, gw, gw * 100, minutes=0)
    _make_gameweek(db_session, 30, is_current=True)
    db_session.commit()

    prob = _compute_minutes_probability(db_session, player.fpl_id, current_gw=30)
    assert abs(prob - 0.0) < 1e-9


def test_minutes_probability_partial_starts(db_session: Session) -> None:
    """Player who started 3 of 5 games should have probability 0.6."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    _make_gw_stat(db_session, player.fpl_id, 26, 2600, minutes=90)
    _make_gw_stat(db_session, player.fpl_id, 27, 2700, minutes=90)
    _make_gw_stat(db_session, player.fpl_id, 28, 2800, minutes=90)
    _make_gw_stat(db_session, player.fpl_id, 29, 2900, minutes=30)
    _make_gw_stat(db_session, player.fpl_id, 30, 3000, minutes=45)
    _make_gameweek(db_session, 30, is_current=True)
    db_session.commit()

    prob = _compute_minutes_probability(db_session, player.fpl_id, current_gw=30)
    assert abs(prob - 0.6) < 1e-9


def test_minutes_probability_no_data_returns_default(db_session: Session) -> None:
    """Player with no gameweek stats should return default probability 0.5."""
    team = _make_team(db_session, 1)
    player = _make_player(db_session, 1, team.fpl_id)
    db_session.commit()

    prob = _compute_minutes_probability(db_session, player.fpl_id, current_gw=30)
    assert abs(prob - 0.5) < 1e-9
