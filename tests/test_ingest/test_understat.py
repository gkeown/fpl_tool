from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.db.models import Base, UnderstatMatch
from fpl.ingest.fpl_api import upsert_players, upsert_teams
from fpl.ingest.mapper import run_mapping
from fpl.ingest.understat import upsert_understat_players

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


@pytest.fixture()
def seeded_session(db_session: Session, bootstrap_data: dict) -> Session:
    """Session with teams and players, plus Understat→FPL mapping for Saka."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    upsert_players(db_session, bootstrap_data["elements"])
    db_session.commit()

    # Pre-insert mapping: Understat id "7254" → FPL id 301 (Saka)
    source_players = [
        {
            "id": "7254",
            "player_name": "Bukayo Saka",
            "team_title": "Arsenal",
        }
    ]
    run_mapping(
        db_session,
        source="understat",
        source_players=source_players,
        team_name_field="team_title",
        source_name_field="player_name",
        source_id_field="id",
    )
    db_session.commit()
    return db_session


# Sample player data mirroring Understat API response
SAMPLE_PLAYERS: list[dict] = [
    {
        "id": "7254",
        "player_name": "Bukayo Saka",
        "games": "29",
        "time": "1927",
        "goals": "11",
        "xG": "9.996114503592253",
        "assists": "4",
        "xA": "2.0942770866677165",
        "shots": "43",
        "key_passes": "16",
        "yellow_cards": "4",
        "red_cards": "0",
        "position": "M",
        "team_title": "Arsenal",
        "npg": "9",
        "npxG": "8.473776828497648",
        "xGChain": "12.3",
        "xGBuildup": "3.1",
    },
    {
        "id": "9999",
        "player_name": "Unknown Player",
        "games": "10",
        "time": "900",
        "goals": "2",
        "xG": "1.5",
        "assists": "1",
        "xA": "0.8",
        "shots": "10",
        "key_passes": "5",
        "yellow_cards": "0",
        "red_cards": "0",
        "position": "F",
        "team_title": "Arsenal",
        "npg": "2",
        "npxG": "1.4",
        "xGChain": "2.0",
        "xGBuildup": "0.5",
    },
]


# ---------------------------------------------------------------------------
# upsert_understat_players
# ---------------------------------------------------------------------------


def test_upsert_understat_players_mapped_player(seeded_session: Session) -> None:
    """A mapped player's season aggregate should be stored in understat_matches."""
    count = upsert_understat_players(seeded_session, SAMPLE_PLAYERS, "2025")
    seeded_session.commit()

    # Only Saka (id 7254) has a mapping; unknown player should be skipped
    assert count == 1

    row = (
        seeded_session.query(UnderstatMatch)
        .filter_by(player_id=301, date="2025", opponent="season_aggregate")
        .first()
    )
    assert row is not None
    assert row.goals == 11
    assert abs(row.xg - 9.996114503592253) < 1e-6
    assert row.assists == 4
    assert abs(row.xa - 2.0942770866677165) < 1e-6
    assert row.shots == 43
    assert row.key_passes == 16
    assert row.npg == 9
    assert abs(row.npxg - 8.473776828497648) < 1e-6
    assert row.minutes == 1927


def test_upsert_understat_players_skips_unmapped(seeded_session: Session) -> None:
    """Players without a mapping (id 9999) should be skipped silently."""
    count = upsert_understat_players(seeded_session, SAMPLE_PLAYERS, "2025")
    seeded_session.commit()

    total_rows = seeded_session.query(UnderstatMatch).count()
    assert total_rows == 1
    # Skipped unknown player → count should be 1, not 2
    assert count == 1


def test_upsert_understat_players_updates_on_conflict(seeded_session: Session) -> None:
    """Re-upserting should update existing rows rather than create duplicates."""
    upsert_understat_players(seeded_session, SAMPLE_PLAYERS, "2025")
    seeded_session.commit()

    updated = [dict(p) for p in SAMPLE_PLAYERS]
    updated[0]["goals"] = "15"
    updated[0]["xG"] = "12.0"

    upsert_understat_players(seeded_session, updated, "2025")
    seeded_session.commit()

    rows = seeded_session.query(UnderstatMatch).filter_by(player_id=301).all()
    assert len(rows) == 1
    assert rows[0].goals == 15
    assert abs(rows[0].xg - 12.0) < 1e-6


def test_upsert_understat_players_empty_list(seeded_session: Session) -> None:
    """An empty player list should return 0 and not raise."""
    count = upsert_understat_players(seeded_session, [], "2025")
    assert count == 0


def test_upsert_understat_players_multiple_seasons(seeded_session: Session) -> None:
    """Data from different seasons should produce separate rows."""
    upsert_understat_players(seeded_session, [SAMPLE_PLAYERS[0]], "2024")
    seeded_session.commit()
    upsert_understat_players(seeded_session, [SAMPLE_PLAYERS[0]], "2025")
    seeded_session.commit()

    rows = seeded_session.query(UnderstatMatch).filter_by(player_id=301).all()
    assert len(rows) == 2
    dates = {r.date for r in rows}
    assert dates == {"2024", "2025"}
