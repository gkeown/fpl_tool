from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Generator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

import fpl.api.routes.live as live_mod
from fpl.cache.live_gw import invalidate as invalidate_live_cache
from fpl.db.models import Fixture, Gameweek, Player, Team


@pytest.fixture()
def _patch_db(db_session: Session):
    """Monkey-patch get_session on the live route module."""
    @contextmanager
    def mock_get_session() -> Generator[Session, None, None]:
        yield db_session

    original = live_mod.get_session
    live_mod.get_session = mock_get_session  # type: ignore[assignment]
    yield
    live_mod.get_session = original


def _seed_gw(session: Session) -> None:
    """Seed 1 fixture with 4 players (2 per team)."""
    now = "2026-04-12T12:00:00Z"

    session.add_all([
        Team(
            fpl_id=1, code=3, name="Arsenal", short_name="ARS",
            strength=4, strength_attack_home=1270,
            strength_attack_away=1230, strength_defence_home=1260,
            strength_defence_away=1240, updated_at=now,
        ),
        Team(
            fpl_id=14, code=43, name="Manchester City", short_name="MCI",
            strength=5, strength_attack_home=1350,
            strength_attack_away=1310, strength_defence_home=1300,
            strength_defence_away=1280, updated_at=now,
        ),
    ])

    session.add(Gameweek(
        id=32, name="GW32", deadline_time="2026-04-12T11:00:00Z",
        finished=False, is_current=True, is_next=False, is_previous=False,
        updated_at=now,
    ))

    session.add(Fixture(
        fpl_id=500, gameweek=32,
        kickoff_time="2026-04-12T14:00:00Z",
        team_h=1, team_a=14,
        team_h_score=2, team_a_score=1,
        team_h_difficulty=4, team_a_difficulty=4,
        finished=False, updated_at=now,
    ))

    base = {
        "first_name": "T", "code": 1, "selected_by_percent": "10.0",
        "status": "a", "form": "5.0", "points_per_game": "5.0",
        "total_points": 100, "minutes": 2000, "goals_scored": 5,
        "assists": 3, "clean_sheets": 5, "bonus": 10,
        "transfers_in": 0, "transfers_out": 0, "goals_conceded": 10,
        "own_goals": 0, "penalties_saved": 0, "penalties_missed": 0,
        "yellow_cards": 0, "red_cards": 0, "saves": 0, "starts": 25,
        "expected_goals": "0", "expected_assists": "0",
        "expected_goal_involvements": "0", "expected_goals_conceded": "0",
        "updated_at": now,
    }

    for pid, name, team_id, etype in [
        (100, "Saka", 1, 3),
        (101, "Gabriel", 1, 2),
        (200, "Haaland", 14, 4),
        (201, "Dias", 14, 2),
    ]:
        session.add(Player(
            fpl_id=pid, second_name=name, web_name=name,
            team_id=team_id, element_type=etype, now_cost=100,
            **base,
        ))

    session.commit()


def _explain_entry(
    fixture: int,
    goals: int = 0,
    assists: int = 0,
    bonus: int = 0,
    defcon: int = 0,
    points: int = 0,
) -> dict:
    """Build an explain entry for a single fixture.

    Note: BPS is NOT included in explain entries in the real FPL API —
    only point-awarding events are. BPS lives in top-level stats.
    """
    stats = []
    if goals:
        stats.append(
            {"identifier": "goals_scored", "value": goals, "points": goals * 5}
        )
    if assists:
        stats.append(
            {"identifier": "assists", "value": assists, "points": assists * 3}
        )
    if bonus:
        stats.append({"identifier": "bonus", "value": bonus, "points": bonus})
    if defcon:
        stats.append(
            {
                "identifier": "defensive_contribution",
                "value": defcon,
                "points": 0,
            }
        )
    if points and not (goals or assists or bonus):
        stats.append({"identifier": "minutes", "value": 90, "points": points})
    return {"fixture": fixture, "stats": stats}


async def _mock_live_fetch(gw: int) -> dict:
    """Mock FPL live endpoint response (all players in fixture 500).

    provisional_bonus is pre-computed from BPS rankings across all players:
    Saka 60 → 3, Haaland 45 → 2, Gabriel 35 → 1, Dias 20 → 0.
    """
    return {
        100: {  # Saka: 2 goals, 60 BPS, 3 bonus, 5 DEFCON
            "stats": {"bps": 60},
            "explain": [
                _explain_entry(
                    500, goals=2, bonus=3, defcon=5, points=15
                )
            ],
            "provisional_bonus": 3,
        },
        101: {  # Gabriel: 1 assist, 35 BPS, 1 bonus, 14 DEFCON
            "stats": {"bps": 35},
            "explain": [
                _explain_entry(
                    500, assists=1, bonus=1, defcon=14, points=8
                )
            ],
            "provisional_bonus": 1,
        },
        200: {  # Haaland: 1 goal, 45 BPS, 2 bonus, 3 DEFCON
            "stats": {"bps": 45},
            "explain": [
                _explain_entry(
                    500, goals=1, bonus=2, defcon=3, points=10
                )
            ],
            "provisional_bonus": 2,
        },
        201: {  # Dias: 20 BPS, 10 DEFCON
            "stats": {"bps": 20},
            "explain": [
                _explain_entry(500, defcon=10, points=3)
            ],
            "provisional_bonus": 0,
        },
    }


async def test_live_gameweek_returns_fixture(
    db_session: Session, _patch_db: None,
) -> None:
    """GET /api/live/gameweek should return fixture with live stats."""
    _seed_gw(db_session)
    # Clear any existing cache
    invalidate_live_cache(32)

    with patch("fpl.api.app.init_db"), \
         patch(
             "fpl.api.routes.live._fetch_live_gw_with_explain",
             _mock_live_fetch,
         ):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/live/gameweek?force=true")

    assert resp.status_code == 200
    data = resp.json()
    assert data["gameweek"] == 32
    assert len(data["fixtures"]) == 1

    fix = data["fixtures"][0]
    assert fix["home_team"] == "Arsenal"
    assert fix["away_team"] == "Manchester City"
    assert fix["home_score"] == 2
    assert fix["away_score"] == 1


async def test_live_gameweek_goal_scorers(
    db_session: Session, _patch_db: None,
) -> None:
    """Goal scorers should be listed with correct counts (Saka 2, Haaland 1)."""
    _seed_gw(db_session)
    invalidate_live_cache(32)

    with patch("fpl.api.app.init_db"), \
         patch(
             "fpl.api.routes.live._fetch_live_gw_with_explain",
             _mock_live_fetch,
         ):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/live/gameweek?force=true")

    fix = resp.json()["fixtures"][0]
    scorers = fix["goal_scorers"]
    # 2 Saka goals + 1 Haaland goal = 3 entries
    assert len(scorers) == 3
    saka_goals = [g for g in scorers if g["player"] == "Saka"]
    haaland_goals = [g for g in scorers if g["player"] == "Haaland"]
    assert len(saka_goals) == 2
    assert len(haaland_goals) == 1


async def test_live_gameweek_assisters(
    db_session: Session, _patch_db: None,
) -> None:
    """Assisters should include Gabriel (1 assist)."""
    _seed_gw(db_session)
    invalidate_live_cache(32)

    with patch("fpl.api.app.init_db"), \
         patch(
             "fpl.api.routes.live._fetch_live_gw_with_explain",
             _mock_live_fetch,
         ):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/live/gameweek?force=true")

    fix = resp.json()["fixtures"][0]
    assisters = fix["assisters"]
    assert len(assisters) == 1
    assert assisters[0]["player"] == "Gabriel"
    assert assisters[0]["team"] == "ARS"


async def test_live_gameweek_top_bps(
    db_session: Session, _patch_db: None,
) -> None:
    """Top BPS should be sorted descending: Saka (60), Haaland (45), Gabriel (35)."""
    _seed_gw(db_session)
    invalidate_live_cache(32)

    with patch("fpl.api.app.init_db"), \
         patch(
             "fpl.api.routes.live._fetch_live_gw_with_explain",
             _mock_live_fetch,
         ):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/live/gameweek?force=true")

    fix = resp.json()["fixtures"][0]
    top_bps = fix["top_bps"]
    assert len(top_bps) == 3
    assert top_bps[0]["player"] == "Saka"
    assert top_bps[0]["bps"] == 60
    assert top_bps[0]["bonus"] == 3
    assert top_bps[1]["player"] == "Haaland"
    assert top_bps[1]["bps"] == 45
    assert top_bps[2]["player"] == "Gabriel"
    assert top_bps[2]["bps"] == 35


async def test_live_gameweek_top_defcon(
    db_session: Session, _patch_db: None,
) -> None:
    """Top DEFCON should be Gabriel (14), Dias (10), Saka (5)."""
    _seed_gw(db_session)
    invalidate_live_cache(32)

    with patch("fpl.api.app.init_db"), \
         patch(
             "fpl.api.routes.live._fetch_live_gw_with_explain",
             _mock_live_fetch,
         ):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/live/gameweek?force=true")

    fix = resp.json()["fixtures"][0]
    top_defcon = fix["top_defcon"]
    # Gabriel (DEF, 14 >= 10) and Dias (DEF, 10 >= 10) qualify.
    # Saka (MID, 5 < 12) is filtered out — below MID threshold.
    # Haaland (FWD, 3 < 12) also filtered out.
    assert len(top_defcon) == 2
    assert top_defcon[0]["player"] == "Gabriel"
    assert top_defcon[0]["defcon"] == 14
    assert top_defcon[1]["player"] == "Dias"
    assert top_defcon[1]["defcon"] == 10


async def _mock_live_fetch_defcon_thresholds(gw: int) -> dict:
    """Test DEFCON thresholds: DEF/GK >= 10, MID/FWD >= 12."""
    return {
        100: {  # Saka (MID): 12 DEFCON (meets threshold)
            "stats": {"bps": 30},
            "explain": [_explain_entry(500, defcon=12, points=5)],
        },
        101: {  # Gabriel (DEF): 9 DEFCON (below threshold)
            "stats": {"bps": 25},
            "explain": [_explain_entry(500, defcon=9, points=3)],
        },
        200: {  # Haaland (FWD): 11 DEFCON (below MID/FWD threshold)
            "stats": {"bps": 20},
            "explain": [_explain_entry(500, defcon=11, points=4)],
        },
        201: {  # Dias (DEF): 10 DEFCON (exactly meets DEF threshold)
            "stats": {"bps": 15},
            "explain": [_explain_entry(500, defcon=10, points=5)],
        },
    }


async def test_live_gameweek_defcon_thresholds(
    db_session: Session, _patch_db: None,
) -> None:
    """Only players meeting position-based DEFCON threshold qualify."""
    _seed_gw(db_session)
    invalidate_live_cache(32)

    with patch("fpl.api.app.init_db"), \
         patch(
             "fpl.api.routes.live._fetch_live_gw_with_explain",
             _mock_live_fetch_defcon_thresholds,
         ):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/live/gameweek?force=true")

    fix = resp.json()["fixtures"][0]
    top_defcon = fix["top_defcon"]
    # Only Saka (MID, 12) and Dias (DEF, 10) qualify
    # Gabriel (DEF, 9) below DEF threshold
    # Haaland (FWD, 11) below MID/FWD threshold
    assert len(top_defcon) == 2
    players = {d["player"] for d in top_defcon}
    assert "Saka" in players
    assert "Dias" in players
    assert "Gabriel" not in players
    assert "Haaland" not in players


def _seed_dgw(session: Session) -> None:
    """Seed a double-gameweek scenario with 2 fixtures."""
    now = "2026-04-12T12:00:00Z"
    session.add_all([
        Team(
            fpl_id=1, code=3, name="Arsenal", short_name="ARS",
            strength=4, strength_attack_home=1270,
            strength_attack_away=1230, strength_defence_home=1260,
            strength_defence_away=1240, updated_at=now,
        ),
        Team(
            fpl_id=14, code=43, name="Manchester City", short_name="MCI",
            strength=5, strength_attack_home=1350,
            strength_attack_away=1310, strength_defence_home=1300,
            strength_defence_away=1280, updated_at=now,
        ),
        Team(
            fpl_id=10, code=10, name="Chelsea", short_name="CHE",
            strength=4, strength_attack_home=1270,
            strength_attack_away=1230, strength_defence_home=1260,
            strength_defence_away=1240, updated_at=now,
        ),
    ])
    session.add(Gameweek(
        id=32, name="GW32", deadline_time="2026-04-12T11:00:00Z",
        finished=False, is_current=True, is_next=False, is_previous=False,
        updated_at=now,
    ))
    # Fixture 500: Arsenal vs City
    session.add(Fixture(
        fpl_id=500, gameweek=32,
        kickoff_time="2026-04-12T14:00:00Z",
        team_h=1, team_a=14, team_h_score=1, team_a_score=0,
        team_h_difficulty=4, team_a_difficulty=4,
        finished=False, updated_at=now,
    ))
    # Fixture 501: Arsenal vs Chelsea (DGW for Arsenal)
    session.add(Fixture(
        fpl_id=501, gameweek=32,
        kickoff_time="2026-04-14T19:00:00Z",
        team_h=1, team_a=10, team_h_score=2, team_a_score=1,
        team_h_difficulty=3, team_a_difficulty=4,
        finished=False, updated_at=now,
    ))

    base = {
        "first_name": "T", "code": 1, "selected_by_percent": "10.0",
        "status": "a", "form": "5.0", "points_per_game": "5.0",
        "total_points": 100, "minutes": 2000, "goals_scored": 5,
        "assists": 3, "clean_sheets": 5, "bonus": 10,
        "transfers_in": 0, "transfers_out": 0, "goals_conceded": 10,
        "own_goals": 0, "penalties_saved": 0, "penalties_missed": 0,
        "yellow_cards": 0, "red_cards": 0, "saves": 0, "starts": 25,
        "expected_goals": "0", "expected_assists": "0",
        "expected_goal_involvements": "0", "expected_goals_conceded": "0",
        "updated_at": now,
    }

    for pid, name, team_id in [
        (100, "Saka", 1),  # Arsenal (DGW player)
        (200, "Haaland", 14),  # City
        (300, "Palmer", 10),  # Chelsea
    ]:
        session.add(Player(
            fpl_id=pid, second_name=name, web_name=name,
            team_id=team_id, element_type=3, now_cost=100,
            **base,
        ))

    session.commit()


async def _mock_live_fetch_dgw(gw: int) -> dict:
    """Mock DGW: Saka has TWO explain entries (one per fixture).

    Goals/assists/DEFCON/bonus must be attributed to the correct
    fixture. BPS is top-level (aggregate across all fixtures for DGW
    players) and is always included in the top BPS ranking.
    """
    return {
        100: {  # Saka: 1 goal in fix 500, 2 goals in fix 501
            "stats": {"bps": 85},  # aggregate across both matches
            "explain": [
                _explain_entry(500, goals=1, defcon=5, points=8),
                _explain_entry(501, goals=2, bonus=3, points=15),
            ],
            "provisional_bonus": 3,
        },
        200: {  # Haaland: fix 500 only
            "stats": {"bps": 20},
            "explain": [_explain_entry(500, points=2)],
            "provisional_bonus": 0,
        },
        300: {  # Palmer: fix 501 only
            "stats": {"bps": 40},
            "explain": [_explain_entry(501, goals=1, bonus=2, points=10)],
            "provisional_bonus": 2,
        },
    }


async def test_live_gameweek_dgw_attribution(
    db_session: Session, _patch_db: None,
) -> None:
    """DGW players' stats must be attributed to the correct fixture."""
    _seed_dgw(db_session)
    invalidate_live_cache(32)

    with patch("fpl.api.app.init_db"), \
         patch(
             "fpl.api.routes.live._fetch_live_gw_with_explain",
             _mock_live_fetch_dgw,
         ):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/live/gameweek?force=true")

    fixtures = resp.json()["fixtures"]
    assert len(fixtures) == 2

    fix_500 = next(f for f in fixtures if f["fixture_id"] == 500)
    fix_501 = next(f for f in fixtures if f["fixture_id"] == 501)

    # Fixture 500: Saka 1 goal + Haaland 0 goals
    fix_500_scorers = fix_500["goal_scorers"]
    assert len(fix_500_scorers) == 1
    assert fix_500_scorers[0]["player"] == "Saka"

    # Fixture 501: Saka 2 goals + Palmer 1 goal
    fix_501_scorers = fix_501["goal_scorers"]
    assert len(fix_501_scorers) == 3
    saka_501 = [g for g in fix_501_scorers if g["player"] == "Saka"]
    palmer_501 = [g for g in fix_501_scorers if g["player"] == "Palmer"]
    assert len(saka_501) == 2
    assert len(palmer_501) == 1

    # BPS: Saka 85 (DGW aggregate) tops fix 500, Haaland 20 second.
    # DGW players use aggregate top-level BPS — best approximation available.
    fix_500_bps = fix_500["top_bps"]
    assert len(fix_500_bps) == 2
    assert fix_500_bps[0]["player"] == "Saka"
    assert fix_500_bps[0]["bps"] == 85
    assert fix_500_bps[1]["player"] == "Haaland"
    assert fix_500_bps[1]["bps"] == 20

    # Fixture 501: Saka 85 (DGW aggregate) tops, Palmer 40 second.
    fix_501_bps = fix_501["top_bps"]
    assert len(fix_501_bps) == 2
    assert fix_501_bps[0]["player"] == "Saka"
    assert fix_501_bps[0]["bps"] == 85
    assert fix_501_bps[1]["player"] == "Palmer"
    assert fix_501_bps[1]["bps"] == 40
