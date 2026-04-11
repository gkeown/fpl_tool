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


def test_list_leagues_empty(db_session: Session, _patch_db: None) -> None:
    """GET /api/leagues should return empty list when none subscribed."""
    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app
        import httpx

        transport = ASGITransport(app=app)
        # Sync route, use sync client pattern via async
        import asyncio

        async def _run() -> httpx.Response:
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.get("/api/leagues")

        resp = asyncio.get_event_loop().run_until_complete(_run())

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_leagues_with_data(
    db_session: Session, _patch_db: None
) -> None:
    """GET /api/leagues should return subscribed leagues."""
    upsert_league(db_session, 620795, SAMPLE_DATA)
    db_session.commit()

    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        import asyncio

        async def _run():
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.get("/api/leagues")

        resp = asyncio.get_event_loop().run_until_complete(_run())

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["league_id"] == 620795
    assert data[0]["name"] == "Test League"
    assert data[0]["entry_count"] == 2


def test_delete_league(db_session: Session, _patch_db: None) -> None:
    """DELETE /api/leagues/{id} should remove league and entries."""
    upsert_league(db_session, 620795, SAMPLE_DATA)
    db_session.commit()

    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        import asyncio

        async def _run():
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.delete("/api/leagues/620795")

        resp = asyncio.get_event_loop().run_until_complete(_run())

    assert resp.status_code == 200
    assert db_session.query(League).count() == 0
    assert db_session.query(LeagueEntry).count() == 0


def test_delete_nonexistent_league(
    db_session: Session, _patch_db: None
) -> None:
    """DELETE on a non-subscribed league should return 404."""
    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app

        transport = ASGITransport(app=app)
        import asyncio

        async def _run():
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.delete("/api/leagues/999")

        resp = asyncio.get_event_loop().run_until_complete(_run())

    assert resp.status_code == 404
