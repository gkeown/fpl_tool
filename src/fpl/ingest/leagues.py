from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.config import Settings
from fpl.db.models import League, LeagueEntry


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


async def fetch_league_standings(
    client: httpx.AsyncClient, settings: Settings, league_id: int
) -> dict[str, Any]:
    """Fetch classic league standings from the FPL API."""
    url = f"{settings.fpl_base_url}/leagues-classic/{league_id}/standings/"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


async def fetch_entry_transfers(
    client: httpx.AsyncClient, settings: Settings, team_id: int
) -> list[dict[str, Any]]:
    """Fetch all transfers for a manager (public endpoint)."""
    url = f"{settings.fpl_base_url}/entry/{team_id}/transfers/"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


def upsert_league(
    session: Session, league_id: int, data: dict[str, Any]
) -> int:
    """Upsert league info and standings entries. Returns count of entries."""
    now = _now_utc()
    league_info = data.get("league", {})

    # Upsert league record
    league_values = {
        "league_id": league_id,
        "name": league_info.get("name", f"League {league_id}"),
        "fetched_at": now,
    }
    stmt = sqlite_insert(League).values([league_values])
    stmt = stmt.on_conflict_do_update(
        index_elements=[League.league_id],
        set_={"name": stmt.excluded.name, "fetched_at": stmt.excluded.fetched_at},
    )
    session.execute(stmt)

    # Upsert standing entries
    standings = data.get("standings", {}).get("results", [])
    if not standings:
        return 0

    entry_values = [
        {
            "league_id": league_id,
            "entry_id": s["entry"],
            "player_name": s.get("player_name", ""),
            "entry_name": s.get("entry_name", ""),
            "rank": s.get("rank", 0),
            "total": s.get("total", 0),
            "event_total": s.get("event_total", 0),
            "fetched_at": now,
        }
        for s in standings
    ]

    for vals in entry_values:
        entry_stmt = sqlite_insert(LeagueEntry).values([vals])
        entry_stmt = entry_stmt.on_conflict_do_update(
            index_elements=[LeagueEntry.league_id, LeagueEntry.entry_id],
            set_={
                col: entry_stmt.excluded[col]
                for col in vals
                if col not in ("league_id", "entry_id")
            },
        )
        session.execute(entry_stmt)

    return len(entry_values)
