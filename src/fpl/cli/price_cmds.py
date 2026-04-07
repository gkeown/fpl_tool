from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from fpl.analysis.price import PriceMovement, predict_price_changes
from fpl.cli.app import prices_app
from fpl.cli.formatters import (
    check_data_staleness,
    format_cost,
    output_json,
    position_str,
)
from fpl.db.engine import get_session, init_db

console = Console()


def _movements_to_records(
    movements: list[PriceMovement],
) -> list[dict[str, Any]]:
    """Convert PriceMovement list to a list of plain dicts for JSON output."""
    records = []
    for rank, m in enumerate(movements, 1):
        records.append(
            {
                "rank": rank,
                "player": m.player.web_name,
                "team": m.team.short_name,
                "position": position_str(m.player.element_type),
                "price": float(m.current_price) / 10,
                "ownership_pct": m.ownership,
                "transfers_in_event": m.transfers_in_event,
                "transfers_out_event": m.transfers_out_event,
                "net_transfers_event": m.net_transfers_event,
                "pressure": round(m.pressure, 4),
            }
        )
    return records


def _render_price_table(
    movements: list[PriceMovement],
    title: str,
    direction: str,
) -> None:
    """Render a Rich table of price movements."""
    if not movements:
        console.print(
            "[yellow]No price movement data available. "
            "Run 'fpl data refresh' first.[/yellow]"
        )
        return

    tbl = Table(title=title, show_header=True, header_style="bold cyan")
    tbl.add_column("Rank", justify="right", style="dim")
    tbl.add_column("Player", min_width=14)
    tbl.add_column("Team", style="cyan")
    tbl.add_column("Pos", justify="center")
    tbl.add_column("Price", justify="right")
    tbl.add_column("Own%", justify="right")
    tbl.add_column("Trans In", justify="right")
    tbl.add_column("Trans Out", justify="right")
    tbl.add_column("Net", justify="right")
    tbl.add_column("Pressure", justify="right")

    for rank, m in enumerate(movements, 1):
        net = m.net_transfers_event
        if direction == "rise":
            net_color = "green" if net > 0 else "red"
            pressure_color = "bold green" if m.pressure > 0 else "dim"
        else:
            net_color = "red" if net < 0 else "green"
            pressure_color = "bold red" if m.pressure < 0 else "dim"

        tbl.add_row(
            str(rank),
            m.player.web_name,
            m.team.short_name,
            position_str(m.player.element_type),
            f"£{format_cost(m.current_price)}m",
            f"{m.ownership:.1f}%",
            f"{m.transfers_in_event:,}",
            f"{m.transfers_out_event:,}",
            f"[{net_color}]{net:+,}[/{net_color}]",
            f"[{pressure_color}]{m.pressure:+.3f}[/{pressure_color}]",
        )

    console.print(tbl)
    console.print(
        "[dim]Based on current GW transfer activity. "
        "Pressure = net_transfers / total_selected * 100.[/dim]"
    )


@prices_app.command()
def risers(
    top: int = typer.Option(20, help="Number of risers to show"),
    output_format: str = typer.Option(
        "table", "--format", help="Output format: table or json"
    ),
) -> None:
    """Show players most likely to rise in price."""
    init_db()

    with get_session() as session:
        warning = check_data_staleness(session)
        if warning:
            console.print(warning)

        movements: list[PriceMovement] = predict_price_changes(
            session, direction="rise", top=top
        )

    if output_format == "json":
        output_json(_movements_to_records(movements))
        return

    _render_price_table(
        movements,
        title="Predicted Price Risers",
        direction="rise",
    )


@prices_app.command()
def fallers(
    top: int = typer.Option(20, help="Number of fallers to show"),
    output_format: str = typer.Option(
        "table", "--format", help="Output format: table or json"
    ),
) -> None:
    """Show players most likely to fall in price."""
    init_db()

    with get_session() as session:
        warning = check_data_staleness(session)
        if warning:
            console.print(warning)

        movements: list[PriceMovement] = predict_price_changes(
            session, direction="fall", top=top
        )

    if output_format == "json":
        output_json(_movements_to_records(movements))
        return

    _render_price_table(
        movements,
        title="Predicted Price Fallers",
        direction="fall",
    )
