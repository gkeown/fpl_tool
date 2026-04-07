from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.analysis.price import predict_price_changes
from fpl.db.models import Base, Player, Team

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
    now_cost: int = 80,
    status: str = "a",
    transfers_in_event: int = 10000,
    transfers_out_event: int = 5000,
    selected_by_percent: str = "10.0",
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
        minutes=900,
        goals_scored=3,
        assists=2,
        clean_sheets=1,
        bonus=5,
        transfers_in=100000,
        transfers_out=50000,
        transfers_in_event=transfers_in_event,
        transfers_out_event=transfers_out_event,
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


# ---------------------------------------------------------------------------
# Tests: predict_price_changes
# ---------------------------------------------------------------------------


def test_predict_price_changes_returns_empty_when_no_players(
    db_session: Session,
) -> None:
    result = predict_price_changes(db_session)
    assert result == []


def test_predict_price_changes_risers_sorted_by_pressure_descending(
    db_session: Session,
) -> None:
    team = _make_team(db_session, 1)

    high_riser = _make_player(
        db_session,
        1,
        team.fpl_id,
        transfers_in_event=50000,
        transfers_out_event=1000,
        selected_by_percent="5.0",
    )
    _make_player(
        db_session,
        2,
        team.fpl_id,
        transfers_in_event=5000,
        transfers_out_event=1000,
        selected_by_percent="5.0",
    )
    db_session.commit()

    result = predict_price_changes(db_session, direction="rise", top=10)
    assert len(result) == 2
    assert result[0].player.fpl_id == high_riser.fpl_id
    assert result[0].pressure >= result[1].pressure


def test_predict_price_changes_fallers_sorted_by_pressure_ascending(
    db_session: Session,
) -> None:
    team = _make_team(db_session, 1)

    heavy_faller = _make_player(
        db_session,
        1,
        team.fpl_id,
        transfers_in_event=500,
        transfers_out_event=40000,
        selected_by_percent="10.0",
    )
    _make_player(
        db_session,
        2,
        team.fpl_id,
        transfers_in_event=2000,
        transfers_out_event=6000,
        selected_by_percent="10.0",
    )
    db_session.commit()

    result = predict_price_changes(db_session, direction="fall", top=10)
    assert len(result) == 2
    assert result[0].player.fpl_id == heavy_faller.fpl_id
    assert result[0].pressure <= result[1].pressure


def test_predict_price_changes_pressure_calculation(db_session: Session) -> None:
    """Pressure = net_event / total_selected * 100."""
    team = _make_team(db_session, 1)

    # 10% ownership -> total_selected = 10/100 * 8_000_000 = 800_000
    # net_event = 10_000 - 2_000 = 8_000
    # pressure = 8_000 / 800_000 * 100 = 1.0
    _make_player(
        db_session,
        1,
        team.fpl_id,
        transfers_in_event=10_000,
        transfers_out_event=2_000,
        selected_by_percent="10.0",
    )
    db_session.commit()

    result = predict_price_changes(db_session, direction="rise", top=1)
    assert len(result) == 1
    m = result[0]
    assert m.net_transfers_event == 8_000
    assert abs(m.pressure - 1.0) < 0.01


def test_predict_price_changes_top_limits_results(
    db_session: Session,
) -> None:
    team = _make_team(db_session, 1)
    for i in range(1, 6):
        _make_player(
            db_session,
            i,
            team.fpl_id,
            transfers_in_event=i * 10000,
            transfers_out_event=1000,
            selected_by_percent="5.0",
        )
    db_session.commit()

    result = predict_price_changes(db_session, direction="rise", top=3)
    assert len(result) == 3


def test_predict_price_changes_excludes_non_available(
    db_session: Session,
) -> None:
    team = _make_team(db_session, 1)
    _make_player(
        db_session,
        1,
        team.fpl_id,
        status="a",
        transfers_in_event=100000,
        transfers_out_event=1000,
    )
    _make_player(
        db_session,
        2,
        team.fpl_id,
        status="i",
        transfers_in_event=200000,
        transfers_out_event=1000,
    )
    db_session.commit()

    result = predict_price_changes(db_session, direction="rise", top=10)
    assert all(m.player.status == "a" for m in result)


def test_predict_price_changes_invalid_direction(db_session: Session) -> None:
    with pytest.raises(ValueError, match="direction must be"):
        predict_price_changes(db_session, direction="sideways")


def test_predict_price_changes_net_transfers_computed_correctly(
    db_session: Session,
) -> None:
    team = _make_team(db_session, 1)
    p = _make_player(
        db_session,
        1,
        team.fpl_id,
        transfers_in_event=7000,
        transfers_out_event=3000,
        selected_by_percent="5.0",
    )
    db_session.commit()

    result = predict_price_changes(db_session, direction="rise", top=1)
    assert len(result) == 1
    assert result[0].net_transfers_event == 4000
    assert result[0].transfers_in_event == p.transfers_in_event
    assert result[0].transfers_out_event == p.transfers_out_event


def test_predict_price_changes_skips_low_activity(
    db_session: Session,
) -> None:
    """Players with < 100 net transfers should be filtered out."""
    team = _make_team(db_session, 1)
    _make_player(
        db_session,
        1,
        team.fpl_id,
        transfers_in_event=50,
        transfers_out_event=10,
        selected_by_percent="5.0",
    )
    db_session.commit()

    result = predict_price_changes(db_session, direction="rise", top=10)
    assert len(result) == 0
