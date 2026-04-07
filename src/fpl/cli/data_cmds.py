from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from fpl.cli.app import data_app
from fpl.db.engine import get_session, init_db
from fpl.db.models import IngestLog

console = Console()


@data_app.command()
def refresh(
    source: str = typer.Option(
        "all",
        help=(
            "Data source to refresh: "
            "fpl, understat, fbref, odds, injuries, projections, all"
        ),
    ),
) -> None:
    """Refresh data from external sources."""
    init_db()
    if source in ("fpl", "all"):
        console.print("[bold]Refreshing FPL data...[/bold]")
        with get_session() as session:
            from fpl.ingest.fpl_api import run_fpl_ingest

            asyncio.run(run_fpl_ingest(session))
        console.print("[green]FPL data refresh complete.[/green]")

    if source in ("understat", "all"):
        console.print("[bold]Refreshing Understat data...[/bold]")
        with get_session() as session:
            from fpl.ingest.understat import run_understat_ingest

            asyncio.run(run_understat_ingest(session))
        console.print("[green]Understat data refresh complete.[/green]")

    if source in ("odds", "all"):
        console.print("[bold]Refreshing odds data...[/bold]")
        with get_session() as session:
            from fpl.ingest.odds import run_odds_ingest

            asyncio.run(run_odds_ingest(session))
        console.print("[green]Odds data refresh complete.[/green]")

    if source in ("injuries", "all"):
        console.print("[bold]Syncing injury data...[/bold]")
        with get_session() as session:
            from fpl.ingest.injuries import run_injuries_ingest

            run_injuries_ingest(session)
        console.print("[green]Injury sync complete.[/green]")

    if source in ("fbref", "all"):
        console.print("[bold]Refreshing FBref data...[/bold]")
        with get_session() as session:
            from fpl.ingest.fbref import run_fbref_ingest

            asyncio.run(run_fbref_ingest(session))
        console.print("[yellow]FBref skipped (browser automation required).[/yellow]")

    if source in ("projections", "all"):
        console.print("[bold]Fetching projected points...[/bold]")
        try:
            with get_session() as session:
                from fpl.ingest.projections import run_projections_ingest

                asyncio.run(run_projections_ingest(session))

                # Check if the ingest skipped due to empty data
                from fpl.db.models import IngestLog

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
                    console.print(
                        "[green]Projections refresh complete.[/green]"
                    )
        except Exception as exc:
            console.print(
                f"[yellow]Projections fetch failed: {exc}. "
                "Continuing without projections.[/yellow]"
            )

    # Compute analytics after data refresh
    console.print("[bold]Computing form scores and FDR...[/bold]")
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


@data_app.command()
def status() -> None:
    """Show data freshness and ingest status."""
    init_db()
    with get_session() as session:
        logs = (
            session.query(IngestLog)
            .order_by(IngestLog.started_at.desc())
            .limit(10)
            .all()
        )
        if not logs:
            console.print("[yellow]No ingest runs recorded yet.[/yellow]")
            return

        table = Table(title="Recent Ingest Runs")
        table.add_column("Source", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Records", justify="right")
        table.add_column("Started")
        table.add_column("Duration")

        for log in logs:
            status_style = {
                "success": "[green]success[/green]",
                "failed": "[red]failed[/red]",
                "running": "[yellow]running[/yellow]",
            }.get(log.status, log.status)

            if log.finished_at and log.started_at:
                # Simple string-based duration display
                duration = f"{log.finished_at} → done"
            else:
                duration = "—"

            table.add_row(
                log.source,
                status_style,
                str(log.records_upserted),
                log.started_at,
                duration,
            )

        console.print(table)
