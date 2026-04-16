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
    session: Session,
    league_id: int,
    data: dict[str, Any],
    user_id: int = 1,
) -> int:
    """Upsert league info and standings entries. Returns count of entries."""
    now = _now_utc()
    league_info = data.get("league", {})
    league_name = league_info.get("name", f"League {league_id}")

    # Find or create league for this user
    existing: League | None = (
        session.query(League)
        .filter(League.user_id == user_id, League.league_id == league_id)
        .first()
    )
    if existing:
        existing.name = league_name
        existing.fetched_at = now
        league_pk = existing.id
    else:
        new_league = League(
            user_id=user_id,
            league_id=league_id,
            name=league_name,
            fetched_at=now,
        )
        session.add(new_league)
        session.flush()
        league_pk = new_league.id

    # Upsert standing entries
    standings = data.get("standings", {}).get("results", [])
    if not standings:
        return 0

    for s in standings:
        vals = {
            "league_id": league_pk,
            "entry_id": s["entry"],
            "player_name": s.get("player_name", ""),
            "entry_name": s.get("entry_name", ""),
            "rank": s.get("rank", 0),
            "total": s.get("total", 0),
            "event_total": s.get("event_total", 0),
            "fetched_at": now,
        }
        entry_stmt = sqlite_insert(LeagueEntry).values([vals])
        entry_stmt = entry_stmt.on_conflict_do_update(
            index_elements=[
                LeagueEntry.league_id,
                LeagueEntry.entry_id,
            ],
            set_={
                col: entry_stmt.excluded[col]
                for col in vals
                if col not in ("league_id", "entry_id")
            },
        )
        session.execute(entry_stmt)

    return len(standings)
