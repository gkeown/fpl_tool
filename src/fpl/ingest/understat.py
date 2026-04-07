from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.config import get_settings
from fpl.db.models import IngestLog, PlayerIdMap, Team, UnderstatMatch
from fpl.ingest.mapper import run_mapping

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Team name mapping: FPL name -> Understat URL slug
# ---------------------------------------------------------------------------

UNDERSTAT_TEAMS: dict[str, str] = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston_Villa",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal_Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Ipswich": "Ipswich",
    "Leicester": "Leicester",
    "Liverpool": "Liverpool",
    "Manchester City": "Manchester_City",
    "Manchester United": "Manchester_United",
    "Newcastle": "Newcastle_United",
    "Nottingham Forest": "Nottingham_Forest",
    "Southampton": "Southampton",
    "Tottenham": "Tottenham",
    "West Ham": "West_Ham",
    "Wolves": "Wolverhampton_Wanderers",
}

_UNDERSTAT_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
}

# Current EPL season start year (2025/26 season → "2025")
_CURRENT_SEASON = "2025"


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# API fetch helpers
# ---------------------------------------------------------------------------


async def fetch_team_data(
    client: httpx.AsyncClient, team_name: str, season: str
) -> dict[str, Any]:
    """Fetch team data from Understat internal API.

    Args:
        client: Async HTTP client.
        team_name: Understat URL slug (e.g. "Arsenal", "Manchester_City").
        season: Season start year as string (e.g. "2025").

    Returns:
        Dict with "dates" (per-match team xG) and "players" (season aggregates).
    """
    settings = get_settings()
    url = f"{settings.understat_base_url}/getTeamData/{team_name}/{season}"
    response = await client.get(url, headers=_UNDERSTAT_HEADERS)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------


def _resolve_fpl_id(session: Session, source_id: str) -> int | None:
    """Look up FPL player ID from player_id_maps for the understat source."""
    mapping = (
        session.query(PlayerIdMap)
        .filter(PlayerIdMap.source == "understat", PlayerIdMap.source_id == source_id)
        .first()
    )
    return mapping.fpl_id if mapping else None


def upsert_understat_players(
    session: Session,
    players_data: list[dict[str, Any]],
    season: str,
) -> int:
    """Store season-level player aggregates into understat_matches.

    Each player gets a single row with date=season, opponent='season_aggregate'.
    Only players that have been mapped to an FPL ID are stored.

    Args:
        session: Active DB session.
        players_data: List of player dicts from the Understat API.
        season: Season year string (e.g. "2025").

    Returns:
        Number of rows upserted.
    """
    values_list: list[dict[str, Any]] = []

    for p in players_data:
        fpl_id = _resolve_fpl_id(session, str(p["id"]))
        if fpl_id is None:
            logger.debug(
                "Skipping Understat player %s (%s) — no FPL mapping",
                p.get("player_name"),
                p.get("id"),
            )
            continue

        values_list.append(
            {
                "player_id": fpl_id,
                "date": season,
                "opponent": "season_aggregate",
                "was_home": True,  # not meaningful for aggregates
                "minutes": int(p.get("time", 0)),
                "goals": int(p.get("goals", 0)),
                "xg": float(p.get("xG", 0)),
                "assists": int(p.get("assists", 0)),
                "xa": float(p.get("xA", 0)),
                "shots": int(p.get("shots", 0)),
                "key_passes": int(p.get("key_passes", 0)),
                "npg": int(p.get("npg", 0)),
                "npxg": float(p.get("npxG", 0)),
            }
        )

    if not values_list:
        return 0

    stmt = sqlite_insert(UnderstatMatch).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            UnderstatMatch.player_id,
            UnderstatMatch.date,
            UnderstatMatch.opponent,
        ],
        set_={
            col: stmt.excluded[col]
            for col in (
                "was_home",
                "minutes",
                "goals",
                "xg",
                "assists",
                "xa",
                "shots",
                "key_passes",
                "npg",
                "npxg",
            )
        },
    )
    session.execute(stmt)
    return len(values_list)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


async def run_understat_ingest(session: Session) -> None:
    """Fetch Understat team/player data and persist to the database.

    Steps:
    1. Iterate over all 20 EPL teams (2-second delay between requests).
    2. For each team: collect player season aggregates.
    3. Run the FPL player mapper against the collected players.
    4. Upsert mapped player data into understat_matches.
    """
    settings = get_settings()
    started_at = _now_utc()

    log = IngestLog(source="understat", started_at=started_at, status="running")
    session.add(log)
    session.flush()

    total_records = 0

    try:
        # Collect all players across all teams so we can run the mapper once
        all_players: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            # Determine which teams are actually in the DB (current season only)
            db_team_names = {t.name for t in session.query(Team).all()}

            for fpl_team_name, understat_slug in UNDERSTAT_TEAMS.items():
                if fpl_team_name not in db_team_names:
                    logger.debug("Team %s not found in DB, skipping", fpl_team_name)
                    continue

                logger.info(
                    "Fetching Understat data for %s (%s)...",
                    fpl_team_name,
                    understat_slug,
                )
                try:
                    data = await fetch_team_data(
                        client, understat_slug, _CURRENT_SEASON
                    )
                    players = data.get("players", [])
                    # Annotate each player with the FPL team name for the mapper
                    for p in players:
                        p.setdefault("team_title", fpl_team_name)
                    all_players.extend(players)
                    logger.debug("  Got %d players for %s", len(players), fpl_team_name)
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch Understat data for %s: %s",
                        fpl_team_name,
                        exc,
                    )

                # Rate limit: 2 seconds between team requests
                await asyncio.sleep(2)

        if not all_players:
            logger.warning("No Understat player data collected; aborting ingest")
            log.status = "success"
            log.finished_at = _now_utc()
            log.records_upserted = 0
            return

        # Run name-based mapping
        logger.info(
            "Running player mapping for %d Understat players...", len(all_players)
        )
        result = run_mapping(
            session,
            source="understat",
            source_players=all_players,
            team_name_field="team_title",
            source_name_field="player_name",
            source_id_field="id",
        )
        session.flush()

        logger.info(
            "Mapping complete: %d exact, %d fuzzy, %d manual, %d unmatched",
            result.exact_matches,
            result.fuzzy_matches,
            result.manual_matches,
            result.unmatched,
        )
        if result.unmatched_players:
            logger.debug("Unmatched players: %s", result.unmatched_players)

        # Upsert player season aggregates
        total_records = upsert_understat_players(session, all_players, _CURRENT_SEASON)
        logger.info("Upserted %d Understat player season records", total_records)

        log.status = "success"
        log.finished_at = _now_utc()
        log.records_upserted = total_records

    except Exception as exc:
        logger.exception("Understat ingest failed: %s", exc)
        log.status = "failed"
        log.finished_at = _now_utc()
        log.error_message = str(exc)
        raise
