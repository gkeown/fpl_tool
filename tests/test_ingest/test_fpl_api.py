from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.db.models import Base, Fixture, Gameweek, Player, PlayerGameweekStats, Team
from fpl.ingest.fpl_api import (
    upsert_fixtures,
    upsert_gameweeks,
    upsert_player_histories,
    upsert_players,
    upsert_teams,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def bootstrap_data() -> dict:
    return json.loads((FIXTURES_DIR / "bootstrap_static.json").read_text())


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


def test_upsert_teams_inserts_records(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Teams should be inserted with correct field mapping."""
    count = upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()

    assert count == 2
    team = db_session.get(Team, 1)
    assert team is not None
    assert team.name == "Arsenal"
    assert team.short_name == "ARS"
    assert team.code == 3
    assert team.strength == 4
    assert team.played == 30
    assert team.win == 20
    assert team.draw == 5
    assert team.loss == 5
    assert team.points == 65
    assert team.position == 2


def test_upsert_teams_updates_on_conflict(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Calling upsert twice should update existing records, not duplicate them."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()

    # Modify the data and upsert again
    modified = [dict(t) for t in bootstrap_data["teams"]]
    modified[0]["win"] = 21
    modified[0]["points"] = 66

    count = upsert_teams(db_session, modified)
    db_session.commit()

    assert count == 2
    assert db_session.query(Team).count() == 2  # no duplicates
    team = db_session.get(Team, 1)
    assert team is not None
    assert team.win == 21
    assert team.points == 66


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


def test_upsert_players_inserts_records(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Players should be inserted with correct field mapping from API elements."""
    # Teams must exist first (FK constraint)
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()

    count = upsert_players(db_session, bootstrap_data["elements"])
    db_session.commit()

    assert count == 3

    saka = db_session.get(Player, 301)
    assert saka is not None
    assert saka.first_name == "Bukayo"
    assert saka.second_name == "Saka"
    assert saka.web_name == "Saka"
    assert saka.team_id == 1
    assert saka.element_type == 3
    assert saka.now_cost == 99
    assert saka.goals_scored == 14
    assert saka.assists == 11
    assert saka.goals_conceded == 22
    assert saka.yellow_cards == 3
    assert saka.expected_goals == "11.43"
    assert saka.expected_assists == "8.76"
    assert saka.expected_goal_involvements == "20.19"
    assert saka.penalties_order == 1
    assert saka.direct_freekicks_order is None


def test_upsert_players_goalkeeper_fields(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Goalkeeper-specific fields (saves, penalties_saved) should map correctly."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    upsert_players(db_session, bootstrap_data["elements"])
    db_session.commit()

    raya = db_session.get(Player, 3)
    assert raya is not None
    assert raya.saves == 85
    assert raya.penalties_saved == 2
    assert raya.goals_scored == 0


def test_upsert_players_captures_event_points(
    db_session: Session, bootstrap_data: dict
) -> None:
    """event_points from bootstrap should be stored on the Player model."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    upsert_players(db_session, bootstrap_data["elements"])
    db_session.commit()

    saka = db_session.get(Player, 301)
    assert saka is not None
    assert saka.event_points == 9

    haaland = db_session.get(Player, 427)
    assert haaland is not None
    assert haaland.event_points == 15

    raya = db_session.get(Player, 3)
    assert raya is not None
    assert raya.event_points == 6


def test_upsert_players_defaults_event_points_when_missing(
    db_session: Session, bootstrap_data: dict
) -> None:
    """event_points should default to 0 if not present in API response."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()

    # Remove event_points from one player
    elements = [dict(e) for e in bootstrap_data["elements"]]
    del elements[0]["event_points"]

    upsert_players(db_session, elements)
    db_session.commit()

    saka = db_session.get(Player, 301)
    assert saka is not None
    assert saka.event_points == 0


def test_upsert_players_updates_on_conflict(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Re-upserting players should update existing records without duplicates."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    upsert_players(db_session, bootstrap_data["elements"])
    db_session.commit()

    modified = [dict(e) for e in bootstrap_data["elements"]]
    modified[0]["now_cost"] = 102
    modified[0]["total_points"] = 190

    upsert_players(db_session, modified)
    db_session.commit()

    assert db_session.query(Player).count() == 3
    saka = db_session.get(Player, 301)
    assert saka is not None
    assert saka.now_cost == 102
    assert saka.total_points == 190


# ---------------------------------------------------------------------------
# Gameweeks
# ---------------------------------------------------------------------------


def test_upsert_gameweeks_inserts_records(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Gameweeks should be inserted with correct field mapping."""
    count = upsert_gameweeks(db_session, bootstrap_data["events"])
    db_session.commit()

    assert count == 3

    gw28 = db_session.get(Gameweek, 28)
    assert gw28 is not None
    assert gw28.name == "Gameweek 28"
    assert gw28.finished is True
    assert gw28.is_previous is True
    assert gw28.is_current is False
    assert gw28.is_next is False
    assert gw28.average_score == 52
    assert gw28.highest_score == 142

    gw29 = db_session.get(Gameweek, 29)
    assert gw29 is not None
    assert gw29.is_current is True
    assert gw29.average_score is None

    gw30 = db_session.get(Gameweek, 30)
    assert gw30 is not None
    assert gw30.is_next is True


def test_upsert_gameweeks_updates_on_conflict(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Re-upserting gameweeks should update rather than duplicate."""
    upsert_gameweeks(db_session, bootstrap_data["events"])
    db_session.commit()

    modified = [dict(ev) for ev in bootstrap_data["events"]]
    modified[1]["is_current"] = False
    modified[1]["finished"] = True

    upsert_gameweeks(db_session, modified)
    db_session.commit()

    assert db_session.query(Gameweek).count() == 3
    gw29 = db_session.get(Gameweek, 29)
    assert gw29 is not None
    assert gw29.finished is True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_FIXTURES = [
    {
        "id": 201,
        "event": 29,
        "kickoff_time": "2025-03-15T15:00:00Z",
        "team_h": 1,
        "team_a": 14,
        "team_h_score": None,
        "team_a_score": None,
        "team_h_difficulty": 5,
        "team_a_difficulty": 3,
        "finished": False,
    },
    {
        "id": 202,
        "event": 28,
        "kickoff_time": "2025-03-08T17:30:00Z",
        "team_h": 14,
        "team_a": 1,
        "team_h_score": 3,
        "team_a_score": 1,
        "team_h_difficulty": 3,
        "team_a_difficulty": 5,
        "finished": True,
    },
]


def test_upsert_fixtures_inserts_records(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Fixtures should be inserted with correct field mapping."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()

    count = upsert_fixtures(db_session, SAMPLE_FIXTURES)
    db_session.commit()

    assert count == 2

    f = db_session.get(Fixture, 201)
    assert f is not None
    assert f.gameweek == 29
    assert f.team_h == 1
    assert f.team_a == 14
    assert f.finished is False
    assert f.team_h_score is None
    assert f.team_h_difficulty == 5


def test_upsert_fixtures_updates_scores_on_conflict(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Fixture scores should be updated when the fixture completes."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    upsert_fixtures(db_session, SAMPLE_FIXTURES)
    db_session.commit()

    updated = [dict(f) for f in SAMPLE_FIXTURES]
    updated[0]["finished"] = True
    updated[0]["team_h_score"] = 2
    updated[0]["team_a_score"] = 1

    upsert_fixtures(db_session, updated)
    db_session.commit()

    assert db_session.query(Fixture).count() == 2
    f = db_session.get(Fixture, 201)
    assert f is not None
    assert f.finished is True
    assert f.team_h_score == 2
    assert f.team_a_score == 1


# ---------------------------------------------------------------------------
# Player histories
# ---------------------------------------------------------------------------

SAMPLE_HISTORY = [
    {
        "element": 301,
        "round": 28,
        "fixture": 202,
        "opponent_team": 14,
        "was_home": False,
        "minutes": 90,
        "total_points": 9,
        "goals_scored": 1,
        "assists": 1,
        "clean_sheets": 0,
        "bonus": 3,
        "bps": 38,
        "ict_index": "12.5",
        "influence": "45.2",
        "creativity": "33.1",
        "threat": "28.0",
        "selected": 5400000,
        "transfers_in": 12000,
        "transfers_out": 3000,
        "value": 99,
        "expected_goals": "0.87",
        "expected_assists": "0.65",
        "expected_goals_conceded": "1.20",
        "goals_conceded": 3,
        "own_goals": 0,
        "penalties_saved": 0,
        "penalties_missed": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "saves": 0,
        "starts": 1,
    }
]


def test_upsert_player_histories_inserts_records(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Player history records should be inserted with correct field mapping."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    upsert_players(db_session, bootstrap_data["elements"])
    db_session.commit()
    upsert_fixtures(db_session, SAMPLE_FIXTURES)
    db_session.commit()

    count = upsert_player_histories(db_session, 301, SAMPLE_HISTORY)
    db_session.commit()

    assert count == 1

    record = (
        db_session.query(PlayerGameweekStats)
        .filter_by(player_id=301, gameweek=28, fixture_id=202)
        .one()
    )
    assert record.goals_scored == 1
    assert record.assists == 1
    assert record.minutes == 90
    assert record.total_points == 9
    assert record.expected_goals == "0.87"
    assert record.expected_assists == "0.65"
    assert record.goals_conceded == 3
    assert record.starts == 1
    assert record.bps == 38


def test_upsert_player_histories_updates_on_conflict(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Re-upserting history records should update existing rows without duplicates."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    upsert_players(db_session, bootstrap_data["elements"])
    db_session.commit()
    upsert_fixtures(db_session, SAMPLE_FIXTURES)
    db_session.commit()

    upsert_player_histories(db_session, 301, SAMPLE_HISTORY)
    db_session.commit()

    modified = [dict(h) for h in SAMPLE_HISTORY]
    modified[0]["bonus"] = 0
    modified[0]["total_points"] = 6

    upsert_player_histories(db_session, 301, modified)
    db_session.commit()

    assert db_session.query(PlayerGameweekStats).count() == 1
    record = (
        db_session.query(PlayerGameweekStats)
        .filter_by(player_id=301, gameweek=28, fixture_id=202)
        .one()
    )
    assert record.bonus == 0
    assert record.total_points == 6


def test_upsert_player_histories_empty_list(db_session: Session) -> None:
    """Upserting an empty history list should return 0 and not raise."""
    count = upsert_player_histories(db_session, 301, [])
    assert count == 0
