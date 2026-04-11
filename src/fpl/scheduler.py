"""Auto-refresh scheduler for match-day windows.

Runs a single interval job every 5 minutes. The job checks the current
day/time in UK timezone and only triggers a data refresh during peak
match windows:

  - Saturday:  12:30 - 19:30
  - Sunday:    12:00 - 18:30
  - Monday:    20:00 - 22:30
"""

from __future__ import annotations

import logging
from datetime import time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import (
    AsyncIOScheduler,  # type: ignore[import-untyped]
)

from fpl.config import get_settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# UK timezone for match windows
_UK = ZoneInfo("Europe/London")

# FPL data refresh windows: (day_of_week, start_time, end_time)
# Monday=0 .. Sunday=6
_MATCH_WINDOWS: list[tuple[int, time, time]] = [
    (5, time(12, 30), time(19, 30)),  # Saturday
    (6, time(12, 0), time(18, 30)),   # Sunday
    (0, time(20, 0), time(22, 30)),   # Monday
]

# Score refresh windows (wider, covers all European leagues)
_SCORE_WINDOWS: list[tuple[int, time, time]] = [
    (4, time(19, 0), time(23, 0)),    # Friday evening
    (5, time(12, 0), time(22, 0)),    # Saturday
    (6, time(12, 0), time(22, 0)),    # Sunday
    (0, time(19, 0), time(23, 0)),    # Monday evening
]


def _in_window(
    windows: list[tuple[int, time, time]],
) -> bool:
    """Check if current UK time falls within any of the given windows."""
    from datetime import datetime

    now = datetime.now(_UK)
    day = now.weekday()
    current = now.time()

    for window_day, start, end in windows:
        if day == window_day and start <= current <= end:
            return True
    return False


def _in_match_window() -> bool:
    return _in_window(_MATCH_WINDOWS)


def _in_score_window() -> bool:
    return _in_window(_SCORE_WINDOWS)


async def _auto_refresh() -> None:
    """Run data refresh if within a match window."""
    if not _in_match_window():
        return

    logger.info("Match window active - running auto-refresh")

    try:
        from fpl.api.routes.data import refresh

        # Only refresh live-scoring sources during match windows
        results: dict[str, str] = {}
        for src in ("fpl", "team", "leagues"):
            result = await refresh(source=src, force=True)
            results.update(result)
        logger.info("Auto-refresh complete: %s", results)
    except Exception:
        logger.exception("Auto-refresh failed")


async def _score_refresh() -> None:
    """Refresh live score and standings caches if within a score window."""
    if not _in_score_window():
        return

    try:
        from fpl.api.routes.scores import (
            refresh_score_cache,
            refresh_standings_cache,
        )

        await refresh_score_cache()
        await refresh_standings_cache()
        logger.info("Score + standings caches refreshed")
    except Exception:
        logger.exception("Score cache refresh failed")


def start_scheduler() -> None:
    """Start the background scheduler if auto_refresh is enabled."""
    global _scheduler

    settings = get_settings()
    if not settings.auto_refresh:
        logger.info("Auto-refresh disabled (FPL_AUTO_REFRESH=false)")
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _auto_refresh,
        "interval",
        minutes=5,
        id="match_day_refresh",
        replace_existing=True,
    )
    _scheduler.add_job(
        _score_refresh,
        "interval",
        seconds=60,
        id="score_refresh",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: FPL data every 5m, scores every 60s")


def stop_scheduler() -> None:
    """Shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
