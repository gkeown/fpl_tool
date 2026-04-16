from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.db.models import Base, League, LeagueEntry
from fpl.ingest.leagues import upsert_league


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


SAMPLE_DATA = {
    "league": {
        "id": 620795,
        "name": "Test League",
    },
    "standings": {
        "results": [
            {
                "entry": 100,
                "player_name": "Alice",
                "entry_name": "Team Alice",
                "rank": 1,
                "total": 1800,
                "event_total": 55,
            },
            {
                "entry": 200,
                "player_name": "Bob",
                "entry_name": "Team Bob",
                "rank": 2,
                "total": 1750,
                "event_total": 42,
            },
        ],
    },
}


def test_upsert_league_creates_league_and_entries(
    db_session: Session,
) -> None:
    """Upserting a league should create league + entry records."""
    count = upsert_league(db_session, 620795, SAMPLE_DATA)
    db_session.commit()

    assert count == 2

    league = db_session.query(League).filter(League.league_id == 620795).first()
    assert league is not None
    assert league.name == "Test League"

    entries = db_session.query(LeagueEntry).all()
    assert len(entries) == 2

    alice = (
        db_session.query(LeagueEntry)
        .filter(LeagueEntry.entry_id == 100)
        .first()
    )
    assert alice is not None
    assert alice.player_name == "Alice"
    assert alice.entry_name == "Team Alice"
    assert alice.rank == 1
    assert alice.total == 1800
    assert alice.event_total == 55


def test_upsert_league_updates_on_conflict(db_session: Session) -> None:
    """Re-upserting should update existing entries, not duplicate."""
    upsert_league(db_session, 620795, SAMPLE_DATA)
    db_session.commit()

    # Update standings
    updated = {
        "league": {"id": 620795, "name": "Test League Updated"},
        "standings": {
            "results": [
                {
                    "entry": 100,
                    "player_name": "Alice",
                    "entry_name": "Team Alice",
                    "rank": 2,
                    "total": 1820,
                    "event_total": 60,
                },
                {
                    "entry": 200,
                    "player_name": "Bob",
                    "entry_name": "Team Bob",
                    "rank": 1,
                    "total": 1830,
                    "event_total": 70,
                },
            ],
        },
    }
    upsert_league(db_session, 620795, updated)
    db_session.commit()

    # Should still be 2 entries, not 4
    assert db_session.query(LeagueEntry).count() == 2

    league = db_session.query(League).filter(League.league_id == 620795).first()
    assert league is not None
    assert league.name == "Test League Updated"

    alice = (
        db_session.query(LeagueEntry)
        .filter(LeagueEntry.entry_id == 100)
        .first()
    )
    assert alice is not None
    assert alice.rank == 2
    assert alice.total == 1820


def test_upsert_league_empty_standings(db_session: Session) -> None:
    """Upserting with empty standings should still create the league."""
    data = {"league": {"id": 999, "name": "Empty"}, "standings": {"results": []}}
    count = upsert_league(db_session, 999, data)
    db_session.commit()

    assert count == 0
    league = db_session.query(League).filter(League.league_id == 999).first()
    assert league is not None
    assert league.name == "Empty"


def test_league_cascade_delete(db_session: Session) -> None:
    """Deleting a league should cascade-delete its entries."""
    upsert_league(db_session, 620795, SAMPLE_DATA)
    db_session.commit()

    assert db_session.query(LeagueEntry).count() == 2

    league = db_session.query(League).filter(League.league_id == 620795).first()
    db_session.delete(league)
    db_session.commit()

    assert db_session.query(League).count() == 0
    assert db_session.query(LeagueEntry).count() == 0
