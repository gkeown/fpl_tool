from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.config import Settings, get_settings
from fpl.db.models import (
    Fixture,
    Gameweek,
    IngestLog,
    MyAccount,
    MyTeamPlayer,
    Player,
    PlayerGameweekStats,
    Team,
)

logger = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# API fetch helpers
# ---------------------------------------------------------------------------


async def fetch_bootstrap(
    client: httpx.AsyncClient, settings: Settings
) -> dict[str, Any]:
    """Fetch bootstrap-static data from the FPL API."""
    url = f"{settings.fpl_base_url}/bootstrap-static/"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


async def fetch_fixtures(
    client: httpx.AsyncClient, settings: Settings
) -> list[dict[str, Any]]:
    """Fetch all fixtures from the FPL API."""
    url = f"{settings.fpl_base_url}/fixtures/"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


async def fetch_player_history(
    client: httpx.AsyncClient, settings: Settings, player_id: int
) -> dict[str, Any]:
    """Fetch element-summary (history) for a single player."""
    url = f"{settings.fpl_base_url}/element-summary/{player_id}/"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


async def fetch_entry(
    client: httpx.AsyncClient, settings: Settings, team_id: int
) -> dict[str, Any]:
    """Fetch public entry (manager) info."""
    url = f"{settings.fpl_base_url}/entry/{team_id}/"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


async def fetch_entry_picks(
    client: httpx.AsyncClient,
    settings: Settings,
    team_id: int,
    gameweek: int,
) -> dict[str, Any]:
    """Fetch team picks for a specific gameweek (public endpoint)."""
    url = f"{settings.fpl_base_url}/entry/{team_id}/event/{gameweek}/picks/"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


def upsert_my_team(
    session: Session,
    team_id: int,
    entry_data: dict[str, Any],
    picks_data: dict[str, Any],
) -> int:
    """Upsert user's team data from public entry + picks endpoints."""
    now = _now_utc()

    # Upsert MyAccount
    entry_history = picks_data.get("entry_history", {})
    account_values = {
        "id": 1,
        "fpl_team_id": team_id,
        "player_name": (
            f"{entry_data.get('player_first_name', '')} "
            f"{entry_data.get('player_last_name', '')}"
        ).strip(),
        "overall_points": entry_data.get("summary_overall_points", 0),
        "overall_rank": entry_data.get("summary_overall_rank", 0),
        "bank": entry_history.get("bank", 0),
        "total_transfers": entry_data.get("last_deadline_total_transfers", 0),
        "free_transfers": max(
            1,
            2 - entry_history.get("event_transfers", 0),
        ),
        "gameweek_points": entry_history.get("points", 0),
        "fetched_at": now,
    }

    stmt = sqlite_insert(MyAccount).values([account_values])
    stmt = stmt.on_conflict_do_update(
        index_elements=[MyAccount.id],
        set_={col: stmt.excluded[col] for col in account_values if col != "id"},
    )
    session.execute(stmt)

    # Clear old team and insert new picks
    session.query(MyTeamPlayer).delete()

    picks = picks_data.get("picks", [])
    for pick in picks:
        player = session.get(Player, pick["element"])
        cost = player.now_cost if player else 0

        mtp = MyTeamPlayer(
            player_id=pick["element"],
            selling_price=cost,
            purchase_price=cost,
            position=pick["position"],
            is_captain=pick.get("is_captain", False),
            is_vice_captain=pick.get("is_vice_captain", False),
            multiplier=pick.get("multiplier", 1),
            fetched_at=now,
        )
        session.add(mtp)

    session.flush()
    return len(picks)


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------


def upsert_teams(session: Session, teams_data: list[dict[str, Any]]) -> int:
    """Upsert teams from bootstrap teams array. Returns count upserted."""
    if not teams_data:
        return 0

    now = _now_utc()
    values_list = [
        {
            "fpl_id": t["id"],
            "code": t["code"],
            "name": t["name"],
            "short_name": t["short_name"],
            "strength": t["strength"],
            "strength_attack_home": t["strength_attack_home"],
            "strength_attack_away": t["strength_attack_away"],
            "strength_defence_home": t["strength_defence_home"],
            "strength_defence_away": t["strength_defence_away"],
            "played": t.get("played", 0),
            "win": t.get("win", 0),
            "draw": t.get("draw", 0),
            "loss": t.get("loss", 0),
            "points": t.get("points", 0),
            "position": t.get("position", 0),
            "updated_at": now,
        }
        for t in teams_data
    ]

    update_columns = [c for c in values_list[0] if c != "fpl_id"]
    stmt = sqlite_insert(Team).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Team.fpl_id],
        set_={col: stmt.excluded[col] for col in update_columns},
    )
    session.execute(stmt)
    return len(values_list)


def upsert_players(session: Session, elements_data: list[dict[str, Any]]) -> int:
    """Upsert players from bootstrap elements array. Returns count upserted."""
    if not elements_data:
        return 0

    now = _now_utc()
    values_list = [
        {
            "fpl_id": e["id"],
            "code": e["code"],
            "first_name": e["first_name"],
            "second_name": e["second_name"],
            "web_name": e["web_name"],
            "team_id": e["team"],
            "element_type": e["element_type"],
            "now_cost": e["now_cost"],
            "selected_by_percent": e["selected_by_percent"],
            "status": e["status"],
            "news": e.get("news"),
            "chance_of_playing_next": e.get("chance_of_playing_next_round"),
            "form": e.get("form") or "0.0",
            "points_per_game": e.get("points_per_game") or "0.0",
            "ep_next": e.get("ep_next"),
            "total_points": e.get("total_points", 0),
            "minutes": e.get("minutes", 0),
            "goals_scored": e.get("goals_scored", 0),
            "assists": e.get("assists", 0),
            "clean_sheets": e.get("clean_sheets", 0),
            "bonus": e.get("bonus", 0),
            "transfers_in": e.get("transfers_in", 0),
            "transfers_out": e.get("transfers_out", 0),
            "transfers_in_event": e.get("transfers_in_event", 0),
            "transfers_out_event": e.get("transfers_out_event", 0),
            "goals_conceded": e.get("goals_conceded", 0),
            "own_goals": e.get("own_goals", 0),
            "penalties_saved": e.get("penalties_saved", 0),
            "penalties_missed": e.get("penalties_missed", 0),
            "yellow_cards": e.get("yellow_cards", 0),
            "red_cards": e.get("red_cards", 0),
            "saves": e.get("saves", 0),
            "starts": e.get("starts", 0),
            "expected_goals": e.get("expected_goals") or "0.00",
            "expected_assists": e.get("expected_assists") or "0.00",
            "expected_goal_involvements": e.get("expected_goal_involvements") or "0.00",
            "expected_goals_conceded": e.get("expected_goals_conceded") or "0.00",
            "penalties_order": e.get("penalties_order"),
            "corners_and_indirect_freekicks_order": e.get(
                "corners_and_indirect_freekicks_order"
            ),
            "direct_freekicks_order": e.get("direct_freekicks_order"),
            "clearances_blocks_interceptions": e.get(
                "clearances_blocks_interceptions", 0
            ),
            "recoveries": e.get("recoveries", 0),
            "tackles": e.get("tackles", 0),
            "defensive_contribution": e.get("defensive_contribution", 0),
            "updated_at": now,
        }
        for e in elements_data
    ]

    update_columns = [c for c in values_list[0] if c != "fpl_id"]
    stmt = sqlite_insert(Player).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Player.fpl_id],
        set_={col: stmt.excluded[col] for col in update_columns},
    )
    session.execute(stmt)
    return len(values_list)


def upsert_gameweeks(session: Session, events_data: list[dict[str, Any]]) -> int:
    """Upsert gameweeks from bootstrap events array. Returns count upserted."""
    if not events_data:
        return 0

    now = _now_utc()
    values_list = [
        {
            "id": ev["id"],
            "name": ev["name"],
            "deadline_time": ev["deadline_time"],
            "finished": ev.get("finished", False),
            "is_current": ev.get("is_current", False),
            "is_next": ev.get("is_next", False),
            "is_previous": ev.get("is_previous", False),
            "average_score": ev.get("average_entry_score"),
            "highest_score": ev.get("highest_score"),
            "updated_at": now,
        }
        for ev in events_data
    ]

    update_columns = [c for c in values_list[0] if c != "id"]
    stmt = sqlite_insert(Gameweek).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Gameweek.id],
        set_={col: stmt.excluded[col] for col in update_columns},
    )
    session.execute(stmt)
    return len(values_list)


def upsert_fixtures(session: Session, fixtures_data: list[dict[str, Any]]) -> int:
    """Upsert fixtures from fixtures API. Returns count upserted."""
    if not fixtures_data:
        return 0

    now = _now_utc()
    values_list = [
        {
            "fpl_id": f["id"],
            "gameweek": f.get("event"),
            "kickoff_time": f.get("kickoff_time"),
            "team_h": f["team_h"],
            "team_a": f["team_a"],
            "team_h_score": f.get("team_h_score"),
            "team_a_score": f.get("team_a_score"),
            "team_h_difficulty": f.get("team_h_difficulty", 0),
            "team_a_difficulty": f.get("team_a_difficulty", 0),
            "finished": f.get("finished", False),
            "updated_at": now,
        }
        for f in fixtures_data
    ]

    update_columns = [c for c in values_list[0] if c != "fpl_id"]
    stmt = sqlite_insert(Fixture).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Fixture.fpl_id],
        set_={col: stmt.excluded[col] for col in update_columns},
    )
    session.execute(stmt)
    return len(values_list)


def upsert_player_histories(
    session: Session, player_id: int, history_data: list[dict[str, Any]]
) -> int:
    """Upsert player gameweek history records. Returns count upserted."""
    if not history_data:
        return 0

    values_list = [
        {
            "player_id": h["element"],
            "gameweek": h["round"],
            "fixture_id": h["fixture"],
            "opponent_team": h["opponent_team"],
            "was_home": h.get("was_home", False),
            "minutes": h.get("minutes", 0),
            "total_points": h.get("total_points", 0),
            "goals_scored": h.get("goals_scored", 0),
            "assists": h.get("assists", 0),
            "clean_sheets": h.get("clean_sheets", 0),
            "bonus": h.get("bonus", 0),
            "bps": h.get("bps", 0),
            "ict_index": h.get("ict_index") or "0.0",
            "influence": h.get("influence") or "0.0",
            "creativity": h.get("creativity") or "0.0",
            "threat": h.get("threat") or "0.0",
            "selected": h.get("selected", 0),
            "transfers_in": h.get("transfers_in", 0),
            "transfers_out": h.get("transfers_out", 0),
            "value": h.get("value", 0),
            "expected_goals": h.get("expected_goals") or "0.00",
            "expected_assists": h.get("expected_assists") or "0.00",
            "expected_goals_conceded": h.get("expected_goals_conceded") or "0.00",
            "goals_conceded": h.get("goals_conceded", 0),
            "own_goals": h.get("own_goals", 0),
            "penalties_saved": h.get("penalties_saved", 0),
            "penalties_missed": h.get("penalties_missed", 0),
            "yellow_cards": h.get("yellow_cards", 0),
            "red_cards": h.get("red_cards", 0),
            "saves": h.get("saves", 0),
            "starts": h.get("starts", 0),
            "clearances_blocks_interceptions": h.get(
                "clearances_blocks_interceptions", 0
            ),
            "recoveries": h.get("recoveries", 0),
            "tackles": h.get("tackles", 0),
            "defensive_contribution": h.get("defensive_contribution", 0),
        }
        for h in history_data
    ]

    # Conflict target is the unique constraint (player_id, gameweek, fixture_id)
    update_columns = [
        c for c in values_list[0] if c not in ("player_id", "gameweek", "fixture_id")
    ]
    stmt = sqlite_insert(PlayerGameweekStats).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            PlayerGameweekStats.player_id,
            PlayerGameweekStats.gameweek,
            PlayerGameweekStats.fixture_id,
        ],
        set_={col: stmt.excluded[col] for col in update_columns},
    )
    session.execute(stmt)
    return len(values_list)


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------


async def fetch_all_player_histories(
    client: httpx.AsyncClient,
    settings: Settings,
    player_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    """Fetch history for all player_ids with concurrency limiting."""
    semaphore = asyncio.Semaphore(settings.http_max_concurrent)
    results: dict[int, list[dict[str, Any]]] = {}

    async def _fetch_one(pid: int) -> None:
        async with semaphore:
            try:
                data = await fetch_player_history(client, settings, pid)
                results[pid] = data.get("history", [])
            except Exception as exc:
                logger.warning("Failed to fetch history for player %d: %s", pid, exc)

    await asyncio.gather(*(_fetch_one(pid) for pid in player_ids))
    return results


def ingest_bootstrap(session: Session, data: dict[str, Any]) -> tuple[int, int, int]:
    """Upsert teams, players, and gameweeks from bootstrap data.

    Returns:
        Tuple of (teams_count, players_count, gameweeks_count).
    """
    teams_count = upsert_teams(session, data.get("teams", []))
    players_count = upsert_players(session, data.get("elements", []))
    gameweeks_count = upsert_gameweeks(session, data.get("events", []))
    return teams_count, players_count, gameweeks_count


async def run_fpl_ingest(session: Session) -> None:
    """Main entry point for FPL data ingest.

    Fetches bootstrap, fixtures, and per-player history, then persists
    everything to the database via upserts.
    """
    settings = get_settings()
    started_at = _now_utc()

    log = IngestLog(source="fpl", started_at=started_at, status="running")
    session.add(log)
    session.flush()

    total_records = 0

    try:
        headers = {"User-Agent": settings.user_agent}
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            # Bootstrap: teams, players, gameweeks
            logger.info("Fetching FPL bootstrap-static...")
            bootstrap = await fetch_bootstrap(client, settings)
            teams_count, players_count, gw_count = ingest_bootstrap(session, bootstrap)
            logger.info(
                "Upserted %d teams, %d players, %d gameweeks",
                teams_count,
                players_count,
                gw_count,
            )
            total_records += teams_count + players_count + gw_count

            # Fixtures
            logger.info("Fetching FPL fixtures...")
            fixtures_data = await fetch_fixtures(client, settings)
            fixtures_count = upsert_fixtures(session, fixtures_data)
            logger.info("Upserted %d fixtures", fixtures_count)
            total_records += fixtures_count

            # Per-player history — only fetch players with minutes > 0
            elements = bootstrap.get("elements", [])
            active_ids = [e["id"] for e in elements if e.get("minutes", 0) > 0]
            logger.info("Fetching history for %d active players...", len(active_ids))
            histories = await fetch_all_player_histories(client, settings, active_ids)

            history_total = 0
            for pid, hist in histories.items():
                history_total += upsert_player_histories(session, pid, hist)
            logger.info("Upserted %d player history records", history_total)
            total_records += history_total

        log.status = "success"
        log.finished_at = _now_utc()
        log.records_upserted = total_records

    except Exception as exc:
        logger.exception("FPL ingest failed: %s", exc)
        log.status = "failed"
        log.finished_at = _now_utc()
        log.error_message = str(exc)
        raise
