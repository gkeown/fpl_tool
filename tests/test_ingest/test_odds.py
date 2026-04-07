from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.db.models import Base, BettingOdds
from fpl.ingest.fpl_api import upsert_fixtures, upsert_teams
from fpl.ingest.odds import match_odds_to_fixtures, upsert_odds

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
    """Session with teams and an unfinished fixture pre-loaded."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()

    # Arsenal (fpl_id=1) vs Manchester City (fpl_id=14)
    fixture = [
        {
            "id": 501,
            "event": 32,
            "kickoff_time": "2026-04-11T14:00:00Z",
            "team_h": 1,
            "team_a": 14,
            "team_h_score": None,
            "team_a_score": None,
            "team_h_difficulty": 4,
            "team_a_difficulty": 4,
            "finished": False,
        }
    ]
    upsert_fixtures(db_session, fixture)
    db_session.commit()
    return db_session


# Sample Odds API response for Arsenal vs Manchester City
SAMPLE_ODDS_EVENT: dict = {
    "id": "event_abc",
    "sport_key": "soccer_epl",
    "commence_time": "2026-04-11T14:00:00Z",
    "home_team": "Arsenal",
    "away_team": "Manchester City",
    "bookmakers": [
        {
            "key": "williamhill",
            "title": "William Hill",
            "last_update": "2026-04-10T10:00:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Arsenal", "price": 2.10},
                        {"name": "Manchester City", "price": 3.40},
                        {"name": "Draw", "price": 3.20},
                    ],
                },
                {
                    "key": "totals",
                    "outcomes": [
                        {"name": "Over", "point": 2.5, "price": 1.80},
                        {"name": "Under", "point": 2.5, "price": 2.00},
                    ],
                },
            ],
        },
        {
            "key": "betfair",
            "title": "Betfair",
            "last_update": "2026-04-10T10:00:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Arsenal", "price": 2.20},
                        {"name": "Manchester City", "price": 3.20},
                        {"name": "Draw", "price": 3.40},
                    ],
                }
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# match_odds_to_fixtures
# ---------------------------------------------------------------------------


def test_match_odds_finds_fixture(seeded_session: Session) -> None:
    """An odds event should be matched to the correct fixture by teams + date."""
    matched = match_odds_to_fixtures(seeded_session, [SAMPLE_ODDS_EVENT])
    assert len(matched) == 1
    assert matched[0]["fixture"].fpl_id == 501


def test_match_odds_no_match_for_unknown_team(seeded_session: Session) -> None:
    """Events with team names not in ODDS_TEAM_MAP should be skipped."""
    bad_event = dict(SAMPLE_ODDS_EVENT)
    bad_event["home_team"] = "Unknown FC"
    matched = match_odds_to_fixtures(seeded_session, [bad_event])
    assert len(matched) == 0


def test_match_odds_no_match_for_finished_fixture(
    db_session: Session, bootstrap_data: dict
) -> None:
    """Finished fixtures should not be matched."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    finished_fixture = [
        {
            "id": 502,
            "event": 30,
            "kickoff_time": "2026-04-11T14:00:00Z",
            "team_h": 1,
            "team_a": 14,
            "team_h_score": 2,
            "team_a_score": 1,
            "team_h_difficulty": 4,
            "team_a_difficulty": 4,
            "finished": True,
        }
    ]
    upsert_fixtures(db_session, finished_fixture)
    db_session.commit()

    matched = match_odds_to_fixtures(db_session, [SAMPLE_ODDS_EVENT])
    assert len(matched) == 0


def test_match_odds_no_match_for_wrong_date(seeded_session: Session) -> None:
    """Events with a different date should not match."""
    wrong_date = dict(SAMPLE_ODDS_EVENT)
    wrong_date["commence_time"] = "2026-05-01T14:00:00Z"
    matched = match_odds_to_fixtures(seeded_session, [wrong_date])
    assert len(matched) == 0


# ---------------------------------------------------------------------------
# upsert_odds
# ---------------------------------------------------------------------------


def test_upsert_odds_inserts_per_bookmaker_rows(seeded_session: Session) -> None:
    """Each bookmaker + market combination should produce a row, plus consensus."""
    matched = match_odds_to_fixtures(seeded_session, [SAMPLE_ODDS_EVENT])
    count = upsert_odds(seeded_session, matched)
    seeded_session.commit()

    # williamhill h2h, williamhill totals, betfair h2h → 3 rows + 2 consensus = 5
    assert count == 5
    all_rows = seeded_session.query(BettingOdds).filter_by(fixture_id=501).all()
    assert len(all_rows) == 5


def test_upsert_odds_consensus_averages(seeded_session: Session) -> None:
    """Consensus h2h odds should be the average across bookmakers."""
    matched = match_odds_to_fixtures(seeded_session, [SAMPLE_ODDS_EVENT])
    upsert_odds(seeded_session, matched)
    seeded_session.commit()

    consensus = (
        seeded_session.query(BettingOdds)
        .filter_by(fixture_id=501, market="h2h", bookmaker="consensus")
        .first()
    )
    assert consensus is not None
    # Average of williamhill (2.10) and betfair (2.20) = 2.15
    assert abs(consensus.home_odds - 2.15) < 1e-6
    # Average of draw: (3.20 + 3.40) / 2 = 3.30
    assert abs(consensus.draw_odds - 3.30) < 1e-6
    # Average of away: (3.40 + 3.20) / 2 = 3.30
    assert abs(consensus.away_odds - 3.30) < 1e-6


def test_upsert_odds_totals_stored(seeded_session: Session) -> None:
    """Totals (over/under 2.5) should be stored with correct values."""
    matched = match_odds_to_fixtures(seeded_session, [SAMPLE_ODDS_EVENT])
    upsert_odds(seeded_session, matched)
    seeded_session.commit()

    totals = (
        seeded_session.query(BettingOdds)
        .filter_by(fixture_id=501, market="totals", bookmaker="williamhill")
        .first()
    )
    assert totals is not None
    assert abs(totals.over_2_5 - 1.80) < 1e-6
    assert abs(totals.under_2_5 - 2.00) < 1e-6
    assert totals.home_odds is None


def test_upsert_odds_updates_on_conflict(seeded_session: Session) -> None:
    """Re-upserting the same event should update rows, not create duplicates."""
    matched = match_odds_to_fixtures(seeded_session, [SAMPLE_ODDS_EVENT])
    upsert_odds(seeded_session, matched)
    seeded_session.commit()

    # Change the odds and re-upsert
    updated_event = dict(SAMPLE_ODDS_EVENT)
    updated_event["bookmakers"] = [
        {
            "key": "williamhill",
            "title": "William Hill",
            "last_update": "2026-04-10T12:00:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Arsenal", "price": 2.50},
                        {"name": "Manchester City", "price": 3.00},
                        {"name": "Draw", "price": 3.10},
                    ],
                }
            ],
        }
    ]
    updated_matched = match_odds_to_fixtures(seeded_session, [updated_event])
    upsert_odds(seeded_session, updated_matched)
    seeded_session.commit()

    wh_rows = (
        seeded_session.query(BettingOdds)
        .filter_by(fixture_id=501, market="h2h", bookmaker="williamhill")
        .all()
    )
    assert len(wh_rows) == 1
    assert abs(wh_rows[0].home_odds - 2.50) < 1e-6


def test_upsert_odds_empty_input(seeded_session: Session) -> None:
    """Empty matched list should return 0 and not raise."""
    count = upsert_odds(seeded_session, [])
    assert count == 0
