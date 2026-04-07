from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from rich.console import Console

_POSITION_MAP: dict[int, str] = {
    1: "GKP",
    2: "DEF",
    3: "MID",
    4: "FWD",
}


def fdr_color(difficulty: float) -> str:
    """Return Rich color markup string for FDR value (green=easy, red=hard)."""
    if difficulty <= 2.0:
        return "bold green"
    elif difficulty <= 3.0:
        return "green"
    elif difficulty <= 3.5:
        return "yellow"
    elif difficulty <= 4.0:
        return "dark_orange"
    else:
        return "bold red"


def form_color(form_score: float) -> str:
    """Return Rich color for custom form score 0-100 (green=high, red=low)."""
    if form_score >= 80.0:
        return "bold green"
    elif form_score >= 60.0:
        return "green"
    elif form_score >= 40.0:
        return "yellow"
    elif form_score >= 20.0:
        return "dark_orange"
    else:
        return "red"


def fpl_form_color(fpl_form: float) -> str:
    """Return Rich color for FPL's own form field (0-10 scale).

    FPL form is average points per game over the last 30 days.
    """
    if fpl_form >= 8.0:
        return "bold green"
    elif fpl_form >= 6.0:
        return "green"
    elif fpl_form >= 4.0:
        return "yellow"
    elif fpl_form >= 2.0:
        return "dark_orange"
    else:
        return "red"


def format_cost(cost_tenths: int) -> str:
    """Format cost from tenths to display string (e.g. 105 -> '10.5')."""
    return f"{cost_tenths / 10:.1f}"


def position_str(element_type: int) -> str:
    """Convert element_type int to position string."""
    return _POSITION_MAP.get(element_type, "UNK")


def format_duration(seconds: float) -> str:
    """Format elapsed seconds as a human-readable duration string.

    Args:
        seconds: Elapsed time in seconds.

    Returns:
        String like "8.2s" or "2m 14s".
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs}s"


def format_time_ago(dt: datetime) -> str:
    """Return a human-readable 'time ago' string for a datetime.

    Args:
        dt: A timezone-aware or naive datetime (treated as UTC if naive).

    Returns:
        String like "2 hours ago", "3 days ago", "45 minutes ago".
    """
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta_secs = (now - dt).total_seconds()

    if delta_secs < 60:
        return "just now"
    elif delta_secs < 3600:
        mins = int(delta_secs // 60)
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    elif delta_secs < 86400:
        hours = int(delta_secs // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(delta_secs // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


def check_data_staleness(session: object) -> str | None:
    """Return a warning string if FPL data is stale, else None.

    Checks the most recent successful FPL ingest log. If older than 24 hours,
    returns a yellow warning string with Rich markup.

    Args:
        session: An active SQLAlchemy Session.

    Returns:
        A Rich-markup warning string, or None if data is fresh.
    """
    from sqlalchemy.orm import Session as _Session

    from fpl.db.models import IngestLog

    s: _Session = session  # type: ignore[assignment]

    last_ok = (
        s.query(IngestLog)
        .filter(IngestLog.source == "fpl", IngestLog.status == "success")
        .order_by(IngestLog.finished_at.desc())
        .first()
    )
    if last_ok is None or last_ok.finished_at is None:
        return (
            "[yellow]No FPL data found. "
            "Run 'fpl data refresh' to load data.[/yellow]"
        )

    try:
        finished = datetime.fromisoformat(last_ok.finished_at)
    except (ValueError, TypeError):
        return None

    now = datetime.now(UTC)
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=UTC)
    age_secs = (now - finished).total_seconds()

    if age_secs > 86400:  # older than 24 hours
        age_str = format_time_ago(finished)
        return (
            f"[yellow]Data is {age_str}. " "Run 'fpl data refresh' to update.[/yellow]"
        )
    return None


def output_json(data: list[dict[str, Any]]) -> None:
    """Print data as JSON to stdout.

    Args:
        data: List of dicts to serialise and print.
    """
    console = Console()
    console.print_json(json.dumps(data, indent=2, default=str))
