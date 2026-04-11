from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Generator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

import fpl.api.routes.data as data_mod
from fpl.db.models import IngestLog


@pytest.fixture()
def _patch_db(db_session: Session):
    """Monkey-patch get_session on the data route module for the test duration."""
    @contextmanager
    def mock_get_session() -> Generator[Session, None, None]:
        yield db_session

    original = data_mod.get_session
    data_mod.get_session = mock_get_session  # type: ignore[assignment]
    yield
    data_mod.get_session = original


async def test_data_status_returns_empty_list(
    db_session: Session, _patch_db: None,
) -> None:
    """GET /api/data/status should return empty list when no ingest logs exist."""
    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data/status")

    assert resp.status_code == 200
    assert resp.json() == []


async def test_data_status_returns_latest_per_source(
    db_session: Session, _patch_db: None,
) -> None:
    """GET /api/data/status should return only the latest log per source."""
    db_session.add(IngestLog(
        source="fpl", started_at="2025-03-14T10:00:00Z",
        finished_at="2025-03-14T10:01:00Z", status="success",
        records_upserted=500,
    ))
    db_session.add(IngestLog(
        source="fpl", started_at="2025-03-14T12:00:00Z",
        finished_at="2025-03-14T12:02:00Z", status="success",
        records_upserted=505,
    ))
    db_session.add(IngestLog(
        source="odds", started_at="2025-03-14T11:00:00Z",
        finished_at="2025-03-14T11:00:30Z", status="success",
        records_upserted=20,
    ))
    db_session.commit()

    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data/status")

    data = resp.json()
    sources = {d["source"]: d for d in data}

    assert len(data) == 2
    assert sources["fpl"]["records_upserted"] == 505
    assert sources["odds"]["records_upserted"] == 20

    assert sources["fpl"]["duration_secs"] is not None
    assert sources["fpl"]["duration_secs"] == pytest.approx(120.0, abs=1.0)


async def test_data_status_handles_failed_ingest(
    db_session: Session, _patch_db: None,
) -> None:
    """Failed ingests should show error_message in status."""
    db_session.add(IngestLog(
        source="understat", started_at="2025-03-14T10:00:00Z",
        finished_at="2025-03-14T10:00:05Z", status="failed",
        records_upserted=0, error_message="Connection timeout",
    ))
    db_session.commit()

    with patch("fpl.api.app.init_db"):
        from fpl.api.app import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data/status")

    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "failed"
    assert data[0]["error_message"] == "Connection timeout"
    assert data[0]["records_upserted"] == 0
