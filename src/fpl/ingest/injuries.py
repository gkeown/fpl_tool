from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.db.models import IngestLog, Injury, Player

logger = logging.getLogger(__name__)

# FPL status codes considered "unavailable"
_UNAVAILABLE_STATUSES = {"d", "i", "s", "u", "n"}


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# FPL-sourced injury sync
# ---------------------------------------------------------------------------


def sync_injuries_from_fpl(session: Session) -> int:
    """Scan the players table and upsert injury records for non-available players.

    For each player whose status is not 'a' (available):
    - Creates or updates an injury record with source='fpl'.
    - Updates last_seen timestamp.

    For players who have become available:
    - Marks their open FPL-sourced injury records as resolved.

    Args:
        session: Active DB session.

    Returns:
        Count of currently active (non-resolved) injury records after sync.
    """
    now = _now_utc()
    players = session.query(Player).all()

    injured_ids: set[int] = set()
    values_list: list[dict[str, Any]] = []

    for player in players:
        if player.status != "a":
            injured_ids.add(player.fpl_id)
            description = player.news or f"Status: {player.status}"
            values_list.append(
                {
                    "player_id": player.fpl_id,
                    "status": player.status,
                    "description": description,
                    "expected_return": None,
                    "source": "fpl",
                    "first_seen": now,
                    "last_seen": now,
                    "resolved": False,
                }
            )

    if values_list:
        stmt = sqlite_insert(Injury).values(values_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Injury.player_id, Injury.source, Injury.description],
            set_={
                "status": stmt.excluded.status,
                "last_seen": stmt.excluded.last_seen,
                "resolved": False,
            },
        )
        session.execute(stmt)
        logger.info("Upserted %d active injury record(s)", len(values_list))

    # Mark previously open injuries as resolved for now-available players
    open_fpl_injuries = (
        session.query(Injury)
        .filter(Injury.source == "fpl", Injury.resolved == False)  # noqa: E712
        .all()
    )
    resolved_count = 0
    for injury in open_fpl_injuries:
        if injury.player_id not in injured_ids:
            injury.resolved = True
            resolved_count += 1

    if resolved_count:
        logger.info("Marked %d injury record(s) as resolved", resolved_count)

    # Return count of currently active injuries
    active_count = (
        session.query(Injury)
        .filter(Injury.source == "fpl", Injury.resolved == False)  # noqa: E712
        .count()
    )
    return active_count


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def run_injuries_ingest(session: Session) -> None:
    """Sync injury data from the players table (sourced from FPL API).

    This is a lightweight sync — it reads from the already-ingested players
    table rather than making additional HTTP requests.
    """
    started_at = _now_utc()

    log = IngestLog(source="injuries", started_at=started_at, status="running")
    session.add(log)
    session.flush()

    try:
        logger.info("Syncing injury data from FPL player records...")
        active_count = sync_injuries_from_fpl(session)
        logger.info("Injury sync complete. Active injuries: %d", active_count)

        log.status = "success"
        log.finished_at = _now_utc()
        log.records_upserted = active_count

    except Exception as exc:
        logger.exception("Injury sync failed: %s", exc)
        log.status = "failed"
        log.finished_at = _now_utc()
        log.error_message = str(exc)
        raise
