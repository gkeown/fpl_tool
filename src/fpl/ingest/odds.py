from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.config import Settings, get_settings
from fpl.db.models import BettingOdds, Fixture, IngestLog, Team

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Team name mapping: Odds API name -> FPL short name used internally
# ---------------------------------------------------------------------------

ODDS_TEAM_MAP: dict[str, str] = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "AFC Bournemouth": "Bournemouth",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton and Hove Albion": "Brighton",
    "Burnley": "Burnley",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Liverpool": "Liverpool",
    "Manchester City": "Manchester City",
    "Manchester United": "Manchester United",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nottingham Forest",
    "Southampton": "Southampton",
    "Sunderland": "Sunderland",
    "Tottenham Hotspur": "Tottenham",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
}

_EPL_SPORT_KEY = "soccer_epl"


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------


async def fetch_epl_odds(
    client: httpx.AsyncClient, settings: Settings
) -> list[dict[str, Any]]:
    """Fetch EPL h2h and totals odds from The Odds API.

    Args:
        client: Async HTTP client.
        settings: Application settings (must have odds_api_key set).

    Returns:
        List of event dicts from the API.
    """
    url = f"{settings.odds_api_base_url}/sports/{_EPL_SPORT_KEY}/odds"
    params = {
        "apiKey": settings.odds_api_key,
        "regions": "uk",
        "markets": "h2h,totals",
    }
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Fixture matching
# ---------------------------------------------------------------------------


def _build_team_name_index(session: Session) -> dict[str, int]:
    """Return {fpl_team_name: fpl_id} for all teams in the DB."""
    teams = session.query(Team).all()
    return {t.name: t.fpl_id for t in teams}


def match_odds_to_fixtures(
    session: Session, odds_data: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Match Odds API events to FPL fixture IDs.

    Matching is done by home team + away team (after normalising via
    ODDS_TEAM_MAP) and kickoff date (first 10 chars of ISO datetime).

    Args:
        session: Active DB session.
        odds_data: Raw event list from The Odds API.

    Returns:
        List of dicts combining fixture_id, gameweek, and odds data.
    """
    team_index = _build_team_name_index(session)
    fixtures = session.query(Fixture).filter(Fixture.finished.is_(False)).all()

    # Build fixture index: (team_h_fpl_id, team_a_fpl_id, date_prefix) -> fixture
    fixture_index: dict[tuple[int, int, str], Fixture] = {}
    for f in fixtures:
        if f.kickoff_time:
            date_prefix = f.kickoff_time[:10]
            fixture_index[(f.team_h, f.team_a, date_prefix)] = f

    matched: list[dict[str, Any]] = []

    for event in odds_data:
        odds_home = ODDS_TEAM_MAP.get(event.get("home_team", ""))
        odds_away = ODDS_TEAM_MAP.get(event.get("away_team", ""))

        if not odds_home or not odds_away:
            logger.debug(
                "Unknown team in odds event: %s vs %s",
                event.get("home_team"),
                event.get("away_team"),
            )
            continue

        home_fpl_id = team_index.get(odds_home)
        away_fpl_id = team_index.get(odds_away)

        if home_fpl_id is None or away_fpl_id is None:
            logger.debug(
                "Could not resolve FPL team IDs for: %s vs %s", odds_home, odds_away
            )
            continue

        # Normalise commence_time to date prefix
        commence = event.get("commence_time", "")
        date_prefix = commence[:10] if commence else ""

        fixture = fixture_index.get((home_fpl_id, away_fpl_id, date_prefix))
        if fixture is None:
            logger.debug(
                "No unfinished fixture found for %s vs %s on %s",
                odds_home,
                odds_away,
                date_prefix,
            )
            continue

        matched.append(
            {
                "fixture": fixture,
                "event": event,
            }
        )

    return matched


# ---------------------------------------------------------------------------
# Odds extraction helpers
# ---------------------------------------------------------------------------


def _extract_h2h(
    outcomes: list[dict[str, Any]], home_team: str, away_team: str
) -> tuple[float | None, float | None, float | None]:
    """Extract (home_odds, draw_odds, away_odds) from h2h outcomes."""
    home_odds: float | None = None
    draw_odds: float | None = None
    away_odds: float | None = None

    for o in outcomes:
        name = o.get("name", "")
        price = float(o.get("price", 0))
        if name == home_team:
            home_odds = price
        elif name == away_team:
            away_odds = price
        elif name == "Draw":
            draw_odds = price

    return home_odds, draw_odds, away_odds


def _extract_totals(
    outcomes: list[dict[str, Any]],
) -> tuple[float | None, float | None]:
    """Extract (over_2_5, under_2_5) from totals outcomes where point=2.5."""
    over_2_5: float | None = None
    under_2_5: float | None = None

    for o in outcomes:
        name = o.get("name", "")
        point = o.get("point")
        price = float(o.get("price", 0))
        if point == 2.5:
            if name == "Over":
                over_2_5 = price
            elif name == "Under":
                under_2_5 = price

    return over_2_5, under_2_5


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def upsert_odds(session: Session, matched_odds: list[dict[str, Any]]) -> int:
    """Upsert consensus (per-bookmaker) odds into betting_odds table.

    Each bookmaker is stored as a separate row. Consensus rows are also
    inserted with bookmaker='consensus' using the average across all books.

    Args:
        session: Active DB session.
        matched_odds: Output of match_odds_to_fixtures.

    Returns:
        Number of rows upserted.
    """
    if not matched_odds:
        return 0

    fetched_at = _now_utc()
    values_list: list[dict[str, Any]] = []

    for item in matched_odds:
        fixture: Fixture = item["fixture"]
        event: dict[str, Any] = item["event"]

        home_team = ODDS_TEAM_MAP.get(event.get("home_team", ""), "")
        away_team = ODDS_TEAM_MAP.get(event.get("away_team", ""), "")
        gameweek: int = fixture.gameweek or 0

        bookmaker_h2h: list[tuple[str, float, float, float]] = []
        bookmaker_over: list[tuple[str, float, float]] = []

        for bm in event.get("bookmakers", []):
            bm_key: str = bm.get("key", "unknown")
            for market in bm.get("markets", []):
                mkey = market.get("key", "")
                outcomes = market.get("outcomes", [])

                if mkey == "h2h":
                    home, draw, away = _extract_h2h(outcomes, home_team, away_team)
                    if home is not None and draw is not None and away is not None:
                        values_list.append(
                            {
                                "fixture_id": fixture.fpl_id,
                                "gameweek": gameweek,
                                "source": "the_odds_api",
                                "market": "h2h",
                                "home_odds": home,
                                "draw_odds": draw,
                                "away_odds": away,
                                "over_2_5": None,
                                "under_2_5": None,
                                "btts_yes": None,
                                "btts_no": None,
                                "bookmaker": bm_key,
                                "fetched_at": fetched_at,
                            }
                        )
                        bookmaker_h2h.append((bm_key, home, draw, away))

                elif mkey == "totals":
                    over, under = _extract_totals(outcomes)
                    if over is not None and under is not None:
                        values_list.append(
                            {
                                "fixture_id": fixture.fpl_id,
                                "gameweek": gameweek,
                                "source": "the_odds_api",
                                "market": "totals",
                                "home_odds": None,
                                "draw_odds": None,
                                "away_odds": None,
                                "over_2_5": over,
                                "under_2_5": under,
                                "btts_yes": None,
                                "btts_no": None,
                                "bookmaker": bm_key,
                                "fetched_at": fetched_at,
                            }
                        )
                        bookmaker_over.append((bm_key, over, under))

        # Consensus row for h2h
        if bookmaker_h2h:
            avg_home = sum(r[1] for r in bookmaker_h2h) / len(bookmaker_h2h)
            avg_draw = sum(r[2] for r in bookmaker_h2h) / len(bookmaker_h2h)
            avg_away = sum(r[3] for r in bookmaker_h2h) / len(bookmaker_h2h)
            values_list.append(
                {
                    "fixture_id": fixture.fpl_id,
                    "gameweek": gameweek,
                    "source": "the_odds_api",
                    "market": "h2h",
                    "home_odds": avg_home,
                    "draw_odds": avg_draw,
                    "away_odds": avg_away,
                    "over_2_5": None,
                    "under_2_5": None,
                    "btts_yes": None,
                    "btts_no": None,
                    "bookmaker": "consensus",
                    "fetched_at": fetched_at,
                }
            )

        # Consensus row for totals
        if bookmaker_over:
            avg_over = sum(r[1] for r in bookmaker_over) / len(bookmaker_over)
            avg_under = sum(r[2] for r in bookmaker_over) / len(bookmaker_over)
            values_list.append(
                {
                    "fixture_id": fixture.fpl_id,
                    "gameweek": gameweek,
                    "source": "the_odds_api",
                    "market": "totals",
                    "home_odds": None,
                    "draw_odds": None,
                    "away_odds": None,
                    "over_2_5": avg_over,
                    "under_2_5": avg_under,
                    "btts_yes": None,
                    "btts_no": None,
                    "bookmaker": "consensus",
                    "fetched_at": fetched_at,
                }
            )

    if not values_list:
        return 0

    stmt = sqlite_insert(BettingOdds).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            BettingOdds.fixture_id,
            BettingOdds.source,
            BettingOdds.market,
            BettingOdds.bookmaker,
        ],
        set_={
            col: stmt.excluded[col]
            for col in (
                "gameweek",
                "home_odds",
                "draw_odds",
                "away_odds",
                "over_2_5",
                "under_2_5",
                "btts_yes",
                "btts_no",
                "fetched_at",
            )
        },
    )
    session.execute(stmt)
    return len(values_list)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


async def run_odds_ingest(session: Session) -> None:
    """Fetch EPL odds from The Odds API and upsert into betting_odds.

    If no API key is configured, logs a warning and returns early.
    """
    settings = get_settings()
    started_at = _now_utc()

    log = IngestLog(source="odds", started_at=started_at, status="running")
    session.add(log)
    session.flush()

    if not settings.odds_api_key:
        logger.warning(
            "No Odds API key configured (FPL_ODDS_API_KEY). "
            "Set the environment variable to enable odds ingest. Skipping."
        )
        log.status = "success"
        log.finished_at = _now_utc()
        log.records_upserted = 0
        return

    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            logger.info("Fetching EPL odds from The Odds API...")
            odds_data = await fetch_epl_odds(client, settings)
            logger.info("Received %d event(s) from Odds API", len(odds_data))

        matched = match_odds_to_fixtures(session, odds_data)
        logger.info("Matched %d event(s) to FPL fixtures", len(matched))

        count = upsert_odds(session, matched)
        logger.info("Upserted %d odds rows", count)

        log.status = "success"
        log.finished_at = _now_utc()
        log.records_upserted = count

    except Exception as exc:
        logger.exception("Odds ingest failed: %s", exc)
        log.status = "failed"
        log.finished_at = _now_utc()
        log.error_message = str(exc)
        raise
