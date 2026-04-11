from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter

from fpl.db.engine import get_session
from fpl.db.models import IngestLog, League, MyAccount

router = APIRouter()


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


_SOURCES = ("fpl", "understat", "odds", "injuries", "projections", "team", "leagues")


def _last_success_age_secs(source: str, session: object) -> float | None:
    from sqlalchemy.orm import Session

    s: Session = session  # type: ignore[assignment]
    log: IngestLog | None = (
        s.query(IngestLog)
        .filter(IngestLog.source == source, IngestLog.status == "success")
        .order_by(IngestLog.finished_at.desc())
        .first()
    )
    if log is None or not log.finished_at:
        return None
    try:
        finished = datetime.fromisoformat(log.finished_at)
    except (ValueError, TypeError):
        return None
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=UTC)
    return (datetime.now(UTC) - finished).total_seconds()


@router.get("/status")
def status() -> list[dict[str, Any]]:
    """Latest ingest status per source."""
    with get_session() as session:
        all_logs: list[IngestLog] = (
            session.query(IngestLog).order_by(IngestLog.started_at.desc()).all()
        )

        # Keep only the latest run per source
        seen: set[str] = set()
        latest: list[IngestLog] = []
        for log in all_logs:
            if log.source not in seen:
                seen.add(log.source)
                latest.append(log)

        results: list[dict[str, Any]] = []
        for log in latest:
            duration_secs: float | None = None
            if log.started_at and log.finished_at:
                try:
                    started = datetime.fromisoformat(log.started_at)
                    finished = datetime.fromisoformat(log.finished_at)
                    duration_secs = (finished - started).total_seconds()
                except (ValueError, TypeError):
                    pass

            age_secs: float | None = None
            if log.finished_at:
                try:
                    finished_dt = datetime.fromisoformat(log.finished_at)
                    if finished_dt.tzinfo is None:
                        finished_dt = finished_dt.replace(tzinfo=UTC)
                    age_secs = (datetime.now(UTC) - finished_dt).total_seconds()
                except (ValueError, TypeError):
                    pass

            results.append(
                {
                    "source": log.source,
                    "status": log.status,
                    "records_upserted": log.records_upserted,
                    "started_at": log.started_at,
                    "finished_at": log.finished_at,
                    "duration_secs": duration_secs,
                    "age_secs": age_secs,
                    "error_message": log.error_message,
                }
            )

        return results


@router.post("/refresh")
async def refresh(source: str = "all", force: bool = False) -> dict[str, str]:
    """Trigger data refresh. source: fpl|understat|odds|injuries|projections|all"""

    results: dict[str, str] = {}

    async def _run_fpl() -> None:
        with get_session() as session:
            from fpl.ingest.fpl_api import run_fpl_ingest

            await run_fpl_ingest(session)

    async def _run_understat() -> None:
        with get_session() as session:
            from fpl.ingest.understat import run_understat_ingest

            await run_understat_ingest(session)

    async def _run_odds() -> None:
        with get_session() as session:
            from fpl.ingest.odds import run_odds_ingest

            await run_odds_ingest(session)

    async def _run_injuries() -> None:
        with get_session() as session:
            from fpl.ingest.injuries import run_injuries_ingest

            run_injuries_ingest(session)

    async def _run_projections() -> None:
        with get_session() as session:
            from fpl.ingest.projections import run_projections_ingest

            await run_projections_ingest(session)

    async def _run_team() -> None:
        with get_session() as session:
            account: MyAccount | None = session.get(MyAccount, 1)
            team_id = account.fpl_team_id if account else None
        if team_id is None:
            raise ValueError("No team loaded — load one via Settings first")

        import json

        from fpl.config import get_settings
        from fpl.ingest.fpl_api import (
            fetch_entry,
            fetch_entry_history,
            fetch_entry_picks,
            upsert_my_team,
        )

        started = _now_utc()
        settings = get_settings()
        headers = {"User-Agent": settings.user_agent}
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            entry = await fetch_entry(client, settings, team_id)
            current_gw = entry.get("current_event", 1)
            picks = await fetch_entry_picks(
                client, settings, team_id, current_gw
            )
            history = await fetch_entry_history(
                client, settings, team_id
            )
            with get_session() as session:
                count = upsert_my_team(session, team_id, entry, picks)
                # Store chips + active chip
                account = session.get(MyAccount, 1)
                if account:
                    chips = history.get("chips", [])
                    account.chips_json = json.dumps(chips)
                    account.active_chip = picks.get("active_chip")
                session.add(
                    IngestLog(
                        source="team",
                        status="success",
                        records_upserted=count,
                        started_at=started,
                        finished_at=_now_utc(),
                    )
                )

    async def _run_leagues() -> None:
        from fpl.config import get_settings as _get_settings
        from fpl.ingest.leagues import fetch_league_standings, upsert_league

        with get_session() as session:
            leagues = session.query(League).all()
            league_ids = [lg.league_id for lg in leagues]

        if not league_ids:
            return

        started = _now_utc()
        settings = _get_settings()
        headers = {"User-Agent": settings.user_agent}
        total = 0
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            for lid in league_ids:
                data = await fetch_league_standings(client, settings, lid)
                with get_session() as session:
                    total += upsert_league(session, lid, data)

        with get_session() as session:
            session.add(
                IngestLog(
                    source="leagues",
                    status="success",
                    records_upserted=total,
                    started_at=started,
                    finished_at=_now_utc(),
                )
            )

    _RUNNER_MAP = {
        "fpl": _run_fpl,
        "understat": _run_understat,
        "odds": _run_odds,
        "injuries": _run_injuries,
        "projections": _run_projections,
        "team": _run_team,
        "leagues": _run_leagues,
    }

    sources_to_run = list(_RUNNER_MAP.keys()) if source == "all" else [source]

    for src in sources_to_run:
        if src not in _RUNNER_MAP:
            results[src] = "unknown source"
            continue

        if not force:
            with get_session() as session:
                age = _last_success_age_secs(src, session)
            if age is not None and age < 3600:
                results[src] = f"fresh ({int(age // 60)}m ago) — skipped"
                continue

        try:
            runner = _RUNNER_MAP[src]
            await runner()
            results[src] = "ok"
        except Exception as exc:
            results[src] = f"error: {exc}"

    # Recompute analytics if any source ran successfully
    if any(v == "ok" for v in results.values()):
        try:
            with get_session() as session:
                from fpl.analysis.fdr import compute_fdr
                from fpl.analysis.form import (
                    compute_form_scores,
                    get_current_gameweek,
                )
                from fpl.analysis.predictions import compute_predictions

                gw = get_current_gameweek(session)
                if gw > 0:
                    compute_form_scores(session, gw)
                    compute_fdr(session)
                    compute_predictions(session, gw + 1)
            results["analytics"] = "recomputed"
        except Exception as exc:
            results["analytics"] = f"error: {exc}"

    return results


@router.get("/news")
def news(top: int = 10) -> list[dict[str, Any]]:
    """Latest FPL news from Fantasy Football Scout RSS."""
    try:
        import feedparser  # type: ignore[import-untyped]
    except ImportError:
        return [{"error": "feedparser not installed"}]

    feed_url = "https://www.fantasyfootballscout.co.uk/feed/"
    try:
        feed = feedparser.parse(feed_url)
    except Exception as exc:
        return [{"error": str(exc)}]

    entries = feed.get("entries", [])[:top]
    results: list[dict[str, Any]] = []
    for entry in entries:
        results.append(
            {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", ""),
                "author": entry.get("author", ""),
            }
        )
    return results
