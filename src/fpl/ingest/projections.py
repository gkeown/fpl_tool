from __future__ import annotations

import csv
import io
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from rapidfuzz import fuzz, process
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.db.models import IngestLog, Player, PlayerProjection, Team

logger = logging.getLogger(__name__)

_PUNDIT_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRaiTmUKjtQ7MxiGibN2GAZ8m9NHF3IA2U-yE0PhBpCOXHewhs57Prj"
    "ZO7GQzZvrEGGBW7HFEE43yX0/pub?output=csv"
)
_FUZZY_THRESHOLD = 80


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def _safe_float(value: str, default: float = 0.0) -> float:
    """Parse a string to float, returning *default* on failure."""
    try:
        return float(value.strip()) if value.strip() else default
    except (ValueError, AttributeError):
        return default


def _safe_bool(value: str) -> bool:
    """Treat '1', 'true', 'yes' (case-insensitive) as True."""
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _detect_gw_columns(fieldnames: list[str]) -> list[str]:
    """Return column names that start with 'GW', sorted by their numeric suffix."""
    gw_cols = [f for f in fieldnames if f.upper().startswith("GW")]
    gw_cols.sort(key=lambda c: int("".join(filter(str.isdigit, c)) or "0"))
    return gw_cols


def _build_player_index(
    session: Session,
) -> dict[int, tuple[str, str]]:
    """Return {fpl_id: (full_name_lower, team_short_name_lower)} for all players."""
    rows = session.query(Player, Team).join(Team, Team.fpl_id == Player.team_id).all()
    return {
        p.fpl_id: (
            f"{p.first_name} {p.second_name}".lower(),
            t.short_name.lower(),
        )
        for p, t in rows
    }


def _match_player(
    pundit_name: str,
    pundit_team: str,
    player_index: dict[int, tuple[str, str]],
) -> int | None:
    """Fuzzy-match a Pundit CSV row to an FPL player_id.

    Strategy:
    1. Filter candidates to the same team (exact short_name match, case-insensitive).
    2. Run rapidfuzz WRatio against full names in that subset.
    3. Accept the best match if score >= _FUZZY_THRESHOLD.
    4. If no same-team match passes, run against all players (wider search).
    """
    name_lower = pundit_name.strip().lower()
    team_lower = pundit_team.strip().lower()

    # Build candidate pools
    same_team: dict[int, str] = {
        pid: names[0] for pid, names in player_index.items() if names[1] == team_lower
    }
    pool = (
        same_team
        if same_team
        else {pid: names[0] for pid, names in player_index.items()}
    )

    if not pool:
        return None

    choices = {str(pid): full_name for pid, full_name in pool.items()}
    result = process.extractOne(
        name_lower,
        choices,
        scorer=fuzz.WRatio,
        score_cutoff=_FUZZY_THRESHOLD,
    )
    if result is None:
        # Fallback: try against all players if same-team search found nothing
        if same_team:
            all_choices = {str(pid): names[0] for pid, names in player_index.items()}
            result = process.extractOne(
                name_lower,
                all_choices,
                scorer=fuzz.WRatio,
                score_cutoff=_FUZZY_THRESHOLD,
            )
        if result is None:
            return None

    _match_value, _score, matched_key = result
    return int(matched_key)


async def fetch_pundit_csv() -> list[dict[str, Any]]:
    """Download the Fantasy Football Pundit CSV and return parsed rows."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(_PUNDIT_CSV_URL)
        response.raise_for_status()
        text = response.text

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    return list(reader)


def parse_pundit_rows(
    rows: list[dict[str, Any]],
    player_index: dict[int, tuple[str, str]],
) -> list[dict[str, Any]]:
    """Convert raw CSV rows into DB-ready dicts keyed by FPL player_id.

    GW columns are labeled GW<N> where N is the actual gameweek number.
    The first GW column found maps to gw1_pts, second to gw2_pts, etc.
    """
    if not rows:
        return []

    fieldnames: list[str] = list(rows[0].keys())
    gw_cols = _detect_gw_columns(fieldnames)
    # Map first 5 GW columns to gw1_pts … gw5_pts
    gw_slot_names = ["gw1_pts", "gw2_pts", "gw3_pts", "gw4_pts", "gw5_pts"]

    now = _now_utc()
    results: list[dict[str, Any]] = []

    for row in rows:
        pundit_name = row.get("Name", "").strip()
        pundit_team = row.get("Team", "").strip()

        if not pundit_name:
            continue

        fpl_id = _match_player(pundit_name, pundit_team, player_index)
        if fpl_id is None:
            logger.debug(
                "No FPL match for Pundit player '%s' (%s)", pundit_name, pundit_team
            )
            continue

        record: dict[str, Any] = {
            "player_id": fpl_id,
            "gw1_pts": 0.0,
            "gw2_pts": 0.0,
            "gw3_pts": 0.0,
            "gw4_pts": 0.0,
            "gw5_pts": 0.0,
            "next_3gw_pts": _safe_float(row.get("Next3GWs", "")),
            "next_5gw_pts": _safe_float(row.get("Next5GWs", "")),
            "start_probability": _safe_float(row.get("Start", "")),
            "cs_probability": _safe_float(row.get("CS", "")),
            "is_blank": _safe_bool(row.get("Blank", "0")),
            "is_double": _safe_bool(row.get("Double", "0")),
            "source": "pundit",
            "fetched_at": now,
        }

        for slot, col in zip(gw_slot_names, gw_cols, strict=False):
            record[slot] = _safe_float(row.get(col, ""))

        results.append(record)

    return results


def upsert_projections(session: Session, records: list[dict[str, Any]]) -> int:
    """Upsert projection records into player_projections. Returns count."""
    if not records:
        return 0

    update_cols = [c for c in records[0] if c != "player_id"]
    stmt = sqlite_insert(PlayerProjection).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=[PlayerProjection.player_id],
        set_={col: stmt.excluded[col] for col in update_cols},
    )
    session.execute(stmt)
    return len(records)


async def run_projections_ingest(session: Session) -> None:
    """Fetch projected points from Fantasy Football Pundit."""
    started_at = _now_utc()

    log = IngestLog(source="projections", started_at=started_at, status="running")
    session.add(log)
    session.flush()

    try:
        logger.info("Fetching Fantasy Football Pundit CSV...")
        raw_rows = await fetch_pundit_csv()
        logger.info("Downloaded %d rows from Pundit CSV", len(raw_rows))

        player_index = _build_player_index(session)
        logger.info("Built player index with %d FPL players", len(player_index))

        records = parse_pundit_rows(raw_rows, player_index)
        logger.info(
            "Matched %d/%d Pundit rows to FPL players",
            len(records),
            len(raw_rows),
        )

        # Check if projections are empty (between GW updates)
        non_zero = sum(1 for r in records if r.get("gw1_pts", 0) > 0)
        if non_zero == 0 and records:
            logger.warning(
                "All projections are zero — Pundit CSV likely "
                "between GW updates. Skipping upsert to preserve "
                "existing data."
            )
            log.status = "success"
            log.finished_at = _now_utc()
            log.records_upserted = 0
            log.error_message = "Skipped: projections all zero (between GW updates)"
            return

        count = upsert_projections(session, records)
        logger.info("Upserted %d projection records", count)

        log.status = "success"
        log.finished_at = _now_utc()
        log.records_upserted = count

    except Exception as exc:
        logger.exception("Projections ingest failed: %s", exc)
        log.status = "failed"
        log.finished_at = _now_utc()
        log.error_message = str(exc)
        raise
