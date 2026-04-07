from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.table import Table

from fpl.cli.app import data_app
from fpl.cli.formatters import format_duration, format_time_ago
from fpl.db.engine import get_session, init_db
from fpl.db.models import IngestLog

console = Console()

_FRESH_THRESHOLD_SECS = 3600  # 1 hour


def _last_success_age(source: str) -> float | None:
    """Return seconds since the last successful ingest for *source*, or None."""
    with get_session() as session:
        log = (
            session.query(IngestLog)
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


@data_app.command()
def refresh(
    source: str = typer.Option(
        "all",
        help=(
            "Data source to refresh: "
            "fpl, understat, fbref, odds, injuries, projections, all"
        ),
    ),
    force: bool = typer.Option(
        False, "--force", help="Force refresh even if data is fresh"
    ),
) -> None:
    """Refresh data from external sources."""
    init_db()

    if source in ("fpl", "all"):
        _refresh_source(
            source_key="fpl",
            label="FPL",
            force=force,
            runner=_run_fpl,
        )

    if source in ("understat", "all"):
        _refresh_source(
            source_key="understat",
            label="Understat",
            force=force,
            runner=_run_understat,
        )

    if source in ("odds", "all"):
        _refresh_source(
            source_key="odds",
            label="odds",
            force=force,
            runner=_run_odds,
        )

    if source in ("injuries", "all"):
        _refresh_source(
            source_key="injuries",
            label="injury",
            force=force,
            runner=_run_injuries,
        )

    if source in ("fbref", "all"):
        # fbref is always skipped (browser automation required) — no freshness check
        console.print("[bold]Refreshing FBref data...[/bold]")
        console.print("[yellow]FBref skipped (browser automation required).[/yellow]")

    if source in ("projections", "all"):
        _refresh_projections(force=force)

    # Compute analytics after data refresh
    console.print("[bold]Computing form scores and FDR...[/bold]")
    try:
        with get_session() as session:
            from fpl.analysis.fdr import compute_fdr
            from fpl.analysis.form import compute_form_scores, get_current_gameweek
            from fpl.analysis.predictions import compute_predictions

            gw = get_current_gameweek(session)
            if gw > 0:
                form_count = compute_form_scores(session, gw)
                fdr_count = compute_fdr(session)
                pred_count = compute_predictions(session, gw + 1)
                console.print(
                    f"[green]Computed {form_count} form scores, "
                    f"{fdr_count} FDR ratings, "
                    f"{pred_count} predictions.[/green]"
                )
            else:
                console.print("[yellow]No gameweek data yet.[/yellow]")
    except Exception as exc:
        console.print(f"[yellow]Analytics computation failed: {exc}[/yellow]")


# ---------------------------------------------------------------------------
# Internal per-source helpers
# ---------------------------------------------------------------------------


def _is_fresh(source_key: str) -> tuple[bool, str]:
    """Return (is_fresh, human_readable_age) for *source_key*."""
    age = _last_success_age(source_key)
    if age is None:
        return False, ""
    if age < _FRESH_THRESHOLD_SECS:
        mins = int(age // 60)
        age_label = f"{mins} minute{'s' if mins != 1 else ''} ago"
        return True, age_label
    return False, ""


def _refresh_source(
    source_key: str,
    label: str,
    force: bool,
    runner: object,
) -> None:
    """Generic refresh wrapper with freshness check and error isolation."""
    from collections.abc import Callable

    run: Callable[[], None] = runner  # type: ignore[assignment]

    if not force:
        fresh, age_label = _is_fresh(source_key)
        if fresh:
            console.print(
                f"[cyan]{label} data is fresh (last updated {age_label}). "
                f"Use --force to refresh anyway.[/cyan]"
            )
            return

    console.print(f"[bold]Refreshing {label} data...[/bold]")
    try:
        run()
        console.print(f"[green]{label} data refresh complete.[/green]")
    except Exception as exc:
        console.print(
            f"[yellow]{label} refresh failed: {exc}. "
            f"Continuing without {label.lower()} data.[/yellow]"
        )


def _run_fpl() -> None:
    with get_session() as session:
        from fpl.ingest.fpl_api import run_fpl_ingest

        asyncio.run(run_fpl_ingest(session))


def _run_understat() -> None:
    with get_session() as session:
        from fpl.ingest.understat import run_understat_ingest

        asyncio.run(run_understat_ingest(session))


def _run_odds() -> None:
    with get_session() as session:
        from fpl.ingest.odds import run_odds_ingest

        asyncio.run(run_odds_ingest(session))


def _run_injuries() -> None:
    with get_session() as session:
        from fpl.ingest.injuries import run_injuries_ingest

        run_injuries_ingest(session)


def _refresh_projections(force: bool) -> None:
    """Refresh projections with its own freshness check and skip-zero handling."""
    if not force:
        fresh, age_label = _is_fresh("projections")
        if fresh:
            console.print(
                f"[cyan]Projections data is fresh (last updated {age_label}). "
                "Use --force to refresh anyway.[/cyan]"
            )
            return

    console.print("[bold]Fetching projected points...[/bold]")
    try:
        with get_session() as session:
            from fpl.ingest.projections import run_projections_ingest

            asyncio.run(run_projections_ingest(session))

            last_log = (
                session.query(IngestLog)
                .filter(IngestLog.source == "projections")
                .order_by(IngestLog.started_at.desc())
                .first()
            )
            skipped = (
                last_log
                and last_log.error_message
                and "all zero" in last_log.error_message
            )
            if skipped:
                console.print(
                    "[yellow]Projections between GW updates "
                    "(all zeros) — keeping previous data.[/yellow]"
                )
            else:
                console.print("[green]Projections refresh complete.[/green]")
    except Exception as exc:
        console.print(
            f"[yellow]Projections fetch failed: {exc}. "
            "Continuing without projections.[/yellow]"
        )


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


@data_app.command()
def status() -> None:
    """Show data freshness and ingest status."""
    init_db()
    with get_session() as session:
        all_logs: list[IngestLog] = (
            session.query(IngestLog).order_by(IngestLog.started_at.desc()).all()
        )
        if not all_logs:
            console.print("[yellow]No ingest runs recorded yet.[/yellow]")
            return

        # Keep only the latest run per source
        seen: set[str] = set()
        latest: list[IngestLog] = []
        for log in all_logs:
            if log.source not in seen:
                seen.add(log.source)
                latest.append(log)

        # Summary: show age of most recent successful FPL ingest
        fpl_log: IngestLog | None = next(
            (lg for lg in latest if lg.source == "fpl" and lg.status == "success"),
            None,
        )
        if fpl_log and fpl_log.finished_at:
            try:
                finished_dt = datetime.fromisoformat(fpl_log.finished_at)
                if finished_dt.tzinfo is None:
                    finished_dt = finished_dt.replace(tzinfo=UTC)
                age_secs = (datetime.now(UTC) - finished_dt).total_seconds()
                age_str = format_time_ago(finished_dt)

                if age_secs < 43200:  # < 12 hours
                    age_color = "green"
                elif age_secs < 172800:  # < 2 days
                    age_color = "yellow"
                else:
                    age_color = "red"

                msg = f"[{age_color}]Data last refreshed: {age_str}[/{age_color}]"
                if age_secs > 172800:
                    msg += "  [dim]-- run 'fpl data refresh'[/dim]"
                console.print(msg)
            except (ValueError, TypeError):
                pass

        console.print()

        table = Table(title="Data Status")
        table.add_column("Source", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Records", justify="right")
        table.add_column("Last Updated")
        table.add_column("Duration", justify="right")

        for log in latest:
            status_style = {
                "success": "[green]success[/green]",
                "failed": "[red]failed[/red]",
                "running": "[yellow]running[/yellow]",
            }.get(log.status, log.status)

            # Human-readable duration
            if log.finished_at and log.started_at:
                try:
                    started = datetime.fromisoformat(log.started_at)
                    finished = datetime.fromisoformat(log.finished_at)
                    elapsed = (finished - started).total_seconds()
                    duration = format_duration(elapsed)
                except (ValueError, TypeError):
                    duration = "-"
            else:
                duration = "-"

            # Human-readable last-updated time
            if log.finished_at:
                try:
                    finished_dt = datetime.fromisoformat(log.finished_at)
                    last_updated = format_time_ago(finished_dt)
                except (ValueError, TypeError):
                    last_updated = log.finished_at or "-"
            else:
                last_updated = "-"

            table.add_row(
                log.source,
                status_style,
                str(log.records_upserted),
                last_updated,
                duration,
            )

        console.print(table)
