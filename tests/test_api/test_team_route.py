from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Generator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

import fpl.api.routes.team as team_mod
from fpl.db.models import (
    Fixture,
    Gameweek,
    MyAccount,
    MyTeamPlayer,
    Player,
    Team,
)


@pytest.fixture()
def _patch_db(db_session: Session):
    """Monkey-patch get_session on the team route module for the test duration."""
    @contextmanager
    def mock_get_session() -> Generator[Session, None, None]:
        yield db_session

    original = team_mod.get_session
    team_mod.get_session = mock_get_session  # type: ignore[assignment]
    yield
    team_mod.get_session = original


def _seed_team_data(session: Session) -> None:
    """Seed minimal data for team endpoint tests."""
    now = "2025-03-14T12:00:00Z"

    session.add(Team(
        fpl_id=1, code=3, name="Arsenal", short_name="ARS", strength=4,
        strength_attack_home=1270, strength_attack_away=1230,
        strength_defence_home=1260, strength_defence_away=1240,
        updated_at=now,
    ))
    session.add(Team(
        fpl_id=14, code=43, name="Manchester City", short_name="MCI",
        strength=5, strength_attack_home=1350, strength_attack_away=1310,
        strength_defence_home=1300, strength_defence_away=1280,
        updated_at=now,
    ))

    session.add(Gameweek(
        id=29, name="Gameweek 29", deadline_time="2025-03-14T11:30:00Z",
        finished=False, is_current=True, is_next=False, is_previous=False,
        updated_at=now,
    ))

    # Arsenal (H) vs Man City (A) in GW29
    session.add(Fixture(
        fpl_id=300, gameweek=29, kickoff_time="2025-03-15T15:00:00Z",
        team_h=1, team_a=14, team_h_difficulty=4, team_a_difficulty=3,
        updated_at=now,
    ))

    for pid, name, etype, cost, form, ep, total, event_pts in [
        (301, "Saka", 3, 99, "7.2", "7.5", 185, 9),
        (3, "Raya", 1, 55, "5.2", "5.5", 140, 6),
    ]:
        session.add(Player(
            fpl_id=pid, code=pid + 1000, first_name="Test", second_name=name,
            web_name=name, team_id=1, element_type=etype, now_cost=cost,
            selected_by_percent="20.0", status="a", form=form,
            points_per_game="5.0", ep_next=ep, total_points=total,
            minutes=2500, goals_scored=10, assists=5, clean_sheets=8,
            bonus=15, transfers_in=100, transfers_out=50,
            goals_conceded=20, own_goals=0, penalties_saved=0,
            penalties_missed=0, yellow_cards=2, red_cards=0, saves=0,
            starts=28, expected_goals="8.0", expected_assists="4.0",
            expected_goal_involvements="12.0", expected_goals_conceded="15.0",
            event_points=event_pts, updated_at=now,
        ))

    session.add(MyAccount(
        id=1, fpl_team_id=12345, player_name="Test Manager",
        overall_points=1500, overall_rank=50000, bank=15,
        total_transfers=10, free_transfers=2, gameweek_points=42,
        fetched_at=now,
    ))

    session.add(MyTeamPlayer(
        player_id=301, selling_price=99, purchase_price=95, position=7,
        is_captain=True, is_vice_captain=False, multiplier=2, fetched_at=now,
    ))
    session.add(MyTeamPlayer(
        player_id=3, selling_price=55, purchase_price=50, position=1,
        is_captain=False, is_vice_captain=False, multiplier=1, fetched_at=now,
    ))

    session.commit()


async def _mock_live_gw(gw: int) -> dict:
    return {}


async def test_get_team_returns_gameweek_points(
    db_session: Session, _patch_db: None,
) -> None:
    """GET /api/me/team should return gameweek_points from MyAccount."""
    _seed_team_data(db_session)

    with patch("fpl.api.app.init_db"), \
         patch("fpl.api.routes.team._fetch_live_gw", _mock_live_gw):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/me/team")

    assert resp.status_code == 200
    data = resp.json()
    assert data["gameweek"] == 29
    assert data["gameweek_points"] == 42
    assert data["overall_points"] == 1500
    assert data["bank"] == 1.5
    assert data["free_transfers"] == 2


async def test_get_team_returns_player_gw_points(
    db_session: Session, _patch_db: None,
) -> None:
    """Each player should have event_points and gw_points (with captain multiplier)."""
    _seed_team_data(db_session)

    with patch("fpl.api.app.init_db"), \
         patch("fpl.api.routes.team._fetch_live_gw", _mock_live_gw):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/me/team")

    data = resp.json()
    players = {p["web_name"]: p for p in data["players"]}

    assert players["Saka"]["event_points"] == 9
    assert players["Saka"]["gw_points"] == 18
    assert players["Saka"]["is_captain"] is True

    assert players["Raya"]["event_points"] == 6
    assert players["Raya"]["gw_points"] == 6
    assert players["Raya"]["is_captain"] is False


async def test_get_team_404_when_no_team(
    db_session: Session, _patch_db: None,
) -> None:
    """GET /api/me/team should return 404 when no team is loaded."""
    db_session.add(Gameweek(
        id=29, name="GW29", deadline_time="2025-03-14T11:30:00Z",
        finished=False, is_current=True, is_next=False, is_previous=False,
        updated_at="2025-03-14T12:00:00Z",
    ))
    db_session.commit()

    with patch("fpl.api.app.init_db"), \
         patch("fpl.api.routes.team._fetch_live_gw", _mock_live_gw):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/me/team")

    assert resp.status_code == 404


async def test_get_team_player_fields(
    db_session: Session, _patch_db: None,
) -> None:
    """Each player dict should contain all expected fields."""
    _seed_team_data(db_session)

    with patch("fpl.api.app.init_db"), \
         patch("fpl.api.routes.team._fetch_live_gw", _mock_live_gw):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/me/team")

    data = resp.json()
    player = data["players"][0]
    expected_keys = {
        "id", "web_name", "team", "position", "cost", "selling_price",
        "opponent", "event_points", "gw_points", "status",
        "news", "is_starter", "squad_position", "is_captain",
        "is_vice_captain", "multiplier",
    }
    assert expected_keys.issubset(set(player.keys()))
