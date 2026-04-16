from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Generator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

import fpl.api.routes.leagues as leagues_mod
from fpl.db.models import League, LeagueEntry
from fpl.ingest.leagues import upsert_league


SAMPLE_DATA = {
    "league": {"id": 620795, "name": "Test League"},
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


@pytest.fixture()
def _patch_db(db_session: Session):
    """Monkey-patch get_session on the leagues route module."""
    @contextmanager
    def mock_get_session() -> Generator[Session, None, None]:
        yield db_session

    original = leagues_mod.get_session
    leagues_mod.get_session = mock_get_session  # type: ignore[assignment]
    yield
    leagues_mod.get_session = original


def _admin_headers() -> dict[str, str]:
    from fpl.auth import create_token
    token = create_token(1, "testadmin", "admin")
    return {"Authorization": f"Bearer {token}"}


async def test_list_leagues_empty(
    db_session: Session, _patch_db: None,
) -> None:
    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/leagues", headers=_admin_headers()
            )

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_leagues_with_data(
    db_session: Session, _patch_db: None,
) -> None:
    upsert_league(db_session, 620795, SAMPLE_DATA, user_id=1)
    db_session.commit()

    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/leagues", headers=_admin_headers()
            )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["league_id"] == 620795
    assert data[0]["name"] == "Test League"
    assert data[0]["entry_count"] == 2


async def test_delete_league(
    db_session: Session, _patch_db: None,
) -> None:
    upsert_league(db_session, 620795, SAMPLE_DATA, user_id=1)
    db_session.commit()
    league = (
        db_session.query(League)
        .filter(League.league_id == 620795)
        .first()
    )
    assert league is not None

    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/api/leagues/{league.id}",
                headers=_admin_headers(),
            )

    assert resp.status_code == 200
    assert db_session.query(League).count() == 0
    assert db_session.query(LeagueEntry).count() == 0


async def test_delete_nonexistent_league(
    db_session: Session, _patch_db: None,
) -> None:
    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.delete(
                "/api/leagues/999", headers=_admin_headers()
            )

    assert resp.status_code == 404
