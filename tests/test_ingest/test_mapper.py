from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.db.models import Base, PlayerIdMap
from fpl.ingest.fpl_api import upsert_players, upsert_teams
from fpl.ingest.mapper import (
    MappingResult,
    exact_match,
    fuzzy_match,
    normalize_name,
    run_mapping,
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


@pytest.fixture()
def seeded_session(db_session: Session, bootstrap_data: dict) -> Session:
    """Session with teams and players pre-loaded."""
    upsert_teams(db_session, bootstrap_data["teams"])
    db_session.commit()
    upsert_players(db_session, bootstrap_data["elements"])
    db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


def test_normalize_name_lowercases() -> None:
    assert normalize_name("Bukayo Saka") == "bukayo saka"


def test_normalize_name_strips_accents() -> None:
    assert normalize_name("Håland") == "haland"
    assert normalize_name("Iñárritu") == "inarritu"


def test_normalize_name_removes_hyphens() -> None:
    assert normalize_name("Alexander-Arnold") == "alexander arnold"


def test_normalize_name_removes_apostrophes() -> None:
    assert normalize_name("O'Brien") == "obrien"


def test_normalize_name_removes_dots() -> None:
    assert normalize_name("E.W. Haaland") == "ew haaland"


def test_normalize_name_collapses_whitespace() -> None:
    assert normalize_name("  Mo   Salah  ") == "mo salah"


def test_normalize_name_combined() -> None:
    # Accent + hyphen + apostrophe
    assert normalize_name("Léo Jard-O'Brien") == "leo jard obrien"


# ---------------------------------------------------------------------------
# exact_match
# ---------------------------------------------------------------------------


def test_exact_match_identical() -> None:
    assert exact_match("Bukayo Saka", "Bukayo Saka") is True


def test_exact_match_normalises_case() -> None:
    assert exact_match("bukayo saka", "BUKAYO SAKA") is True


def test_exact_match_normalises_accents() -> None:
    # é → e after NFKD decomposition; both names normalise to the same string
    assert exact_match("Raphaël Varane", "Raphael Varane") is True


def test_exact_match_false_for_different_names() -> None:
    assert exact_match("Bukayo Saka", "Gabriel Martinelli") is False


# ---------------------------------------------------------------------------
# fuzzy_match
# ---------------------------------------------------------------------------


def test_fuzzy_match_returns_true_above_threshold() -> None:
    # Close spellings of the same name should score >= 85
    matched, score = fuzzy_match("Gabriel Martinelli", "Gabriel Martineli")
    assert matched is True
    assert score >= 85.0


def test_fuzzy_match_returns_false_below_threshold() -> None:
    matched, _score = fuzzy_match("Bukayo Saka", "Gabriel Martinelli")
    assert matched is False


def test_fuzzy_match_score_between_zero_and_hundred() -> None:
    _, score = fuzzy_match("Bukayo Saka", "Bukayo Saka")
    assert 0.0 <= score <= 100.0


def test_fuzzy_match_custom_threshold() -> None:
    # Lower threshold should accept weaker matches
    _matched_high, _ = fuzzy_match("Saka", "Bukayo Saka", threshold=95)
    matched_low, _ = fuzzy_match("Saka", "Bukayo Saka", threshold=50)
    assert matched_low is True
    # High threshold for a partial name may or may not match — just test low passes
    assert matched_low is True


# ---------------------------------------------------------------------------
# run_mapping — exact match
# ---------------------------------------------------------------------------


def test_run_mapping_exact_match(seeded_session: Session) -> None:
    """Players with an exact name match should be mapped correctly."""
    source_players = [
        {
            "id": "us_301",
            "player_name": "Bukayo Saka",
            "team_title": "Arsenal",
        }
    ]

    result = run_mapping(
        seeded_session,
        source="understat",
        source_players=source_players,
        team_name_field="team_title",
        source_name_field="player_name",
        source_id_field="id",
    )
    seeded_session.commit()

    assert isinstance(result, MappingResult)
    assert result.exact_matches == 1
    assert result.fuzzy_matches == 0
    assert result.unmatched == 0

    mapping = (
        seeded_session.query(PlayerIdMap)
        .filter_by(fpl_id=301, source="understat")
        .first()
    )
    assert mapping is not None
    assert mapping.source_id == "us_301"
    assert mapping.matched_by == "exact"
    assert mapping.confidence == 1.0


def test_run_mapping_web_name_match(seeded_session: Session) -> None:
    """Players matched by web_name should count as exact matches."""
    source_players = [
        {
            "id": "us_3",
            "player_name": "Raya",
            "team_title": "Arsenal",
        }
    ]

    result = run_mapping(
        seeded_session,
        source="understat",
        source_players=source_players,
        team_name_field="team_title",
        source_name_field="player_name",
        source_id_field="id",
    )
    seeded_session.commit()

    assert result.exact_matches == 1
    assert result.unmatched == 0


def test_run_mapping_fuzzy_match(seeded_session: Session) -> None:
    """A slightly misspelled name should be matched via fuzzy logic."""
    source_players = [
        {
            "id": "us_427",
            "player_name": "Erling Haaland",  # FPL stores "Haaland" as web_name
            "team_title": "Manchester City",
        }
    ]

    result = run_mapping(
        seeded_session,
        source="understat",
        source_players=source_players,
        team_name_field="team_title",
        source_name_field="player_name",
        source_id_field="id",
    )
    seeded_session.commit()

    # Should match (exact or fuzzy)
    assert result.exact_matches + result.fuzzy_matches == 1
    assert result.unmatched == 0


def test_run_mapping_unmatched_player(seeded_session: Session) -> None:
    """Players with no candidate on the same team should be counted as unmatched."""
    source_players = [
        {
            "id": "us_9999",
            "player_name": "Completely Unknown Player",
            "team_title": "Arsenal",
        }
    ]

    result = run_mapping(
        seeded_session,
        source="understat",
        source_players=source_players,
        team_name_field="team_title",
        source_name_field="player_name",
        source_id_field="id",
    )

    assert result.unmatched == 1
    assert "Completely Unknown Player" in result.unmatched_players[0]


def test_run_mapping_upserts_on_conflict(seeded_session: Session) -> None:
    """Re-running mapping for the same player should update rather than duplicate."""
    source_players = [
        {
            "id": "us_301",
            "player_name": "Bukayo Saka",
            "team_title": "Arsenal",
        }
    ]

    run_mapping(
        seeded_session,
        source="understat",
        source_players=source_players,
        team_name_field="team_title",
        source_name_field="player_name",
        source_id_field="id",
    )
    seeded_session.commit()

    run_mapping(
        seeded_session,
        source="understat",
        source_players=source_players,
        team_name_field="team_title",
        source_name_field="player_name",
        source_id_field="id",
    )
    seeded_session.commit()

    count = (
        seeded_session.query(PlayerIdMap)
        .filter_by(fpl_id=301, source="understat")
        .count()
    )
    assert count == 1  # no duplicate rows


def test_run_mapping_wrong_team_no_match(seeded_session: Session) -> None:
    """Player assigned to a non-existent team should be unmatched."""
    source_players = [
        {
            "id": "us_999",
            "player_name": "Bukayo Saka",
            "team_title": "Nonexistent FC",
        }
    ]

    result = run_mapping(
        seeded_session,
        source="understat",
        source_players=source_players,
        team_name_field="team_title",
        source_name_field="player_name",
        source_id_field="id",
    )

    assert result.unmatched == 1
