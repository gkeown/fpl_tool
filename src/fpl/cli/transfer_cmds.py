from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from fpl.analysis.transfers import (
    PlayerComparison,
    TransferSuggestion,
    compare_players,
    suggest_transfers,
)
from fpl.cli.app import transfers_app
from fpl.cli.formatters import fdr_color, form_color, format_cost, position_str
from fpl.db.engine import get_session, init_db
from fpl.db.models import MyAccount

console = Console()


@transfers_app.command()
def suggest(
    free_transfers: int = typer.Option(
        1, "--free-transfers", "-ft", help="Number of free transfers"
    ),
    budget: float | None = typer.Option(
        None, help="Override total budget in millions (e.g. 5.5)"
    ),
    max_hits: int = typer.Option(0, help="Max additional transfers (points hits)"),
    weeks: int = typer.Option(5, help="Weeks ahead to optimise for"),
    top: int = typer.Option(10, help="Number of suggestions to show"),
) -> None:
    """Suggest optimal transfers for your team."""
    init_db()

    with get_session() as session:
        account: MyAccount | None = session.get(MyAccount, 1)
        bank_tenths = account.bank if account is not None else 0
        bank_display = bank_tenths / 10.0

        ft_display = account.free_transfers if account is not None else free_transfers

        # Convert user-supplied budget override from millions to tenths
        budget_tenths: int | None = None
        if budget is not None:
            budget_tenths = round(budget * 10)

        suggestions: list[TransferSuggestion] = suggest_transfers(
            session,
            free_transfers=free_transfers,
            budget=budget_tenths,
            max_hits=max_hits,
            weeks_ahead=weeks,
            top=top,
        )

        if not suggestions:
            console.print(
                "[yellow]No transfer suggestions available. "
                "Ensure you have synced your team ('fpl me login') "
                "and run 'fpl data refresh'.[/yellow]"
            )
            return

        title = (
            f"Transfer Suggestions ({ft_display} FT, Bank: "
            f"[bold]£{bank_display:.1f}m[/bold])"
        )
        tbl = Table(title=title, show_header=True, header_style="bold cyan")
        tbl.add_column("Rank", justify="right", style="dim")
        tbl.add_column("Out", min_width=14)
        tbl.add_column("In", min_width=14)
        tbl.add_column("Pos", justify="center")
        tbl.add_column("Delta", justify="right")
        tbl.add_column("Cost", justify="right")
        tbl.add_column("Form", min_width=10)
        tbl.add_column("FDR", min_width=10)

        for rank, s in enumerate(suggestions, 1):
            out_cost = format_cost(s.out_player.now_cost)
            in_cost = format_cost(s.in_player.now_cost)

            impact = s.budget_impact
            if impact > 0:
                cost_str = f"[red]+{format_cost(impact)}[/red]"
            elif impact < 0:
                cost_str = f"[green]-{format_cost(abs(impact))}[/green]"
            else:
                cost_str = "[dim]0.0[/dim]"

            out_form_col = form_color(s.out_form)
            in_form_col = form_color(s.in_form)
            form_str = (
                f"[{out_form_col}]{s.out_form:.0f}[/{out_form_col}]"
                f"->[{in_form_col}]{s.in_form:.0f}[/{in_form_col}]"
            )

            out_fdr_col = fdr_color(s.out_fdr)
            in_fdr_col = fdr_color(s.in_fdr)
            fdr_str = (
                f"[{out_fdr_col}]{s.out_fdr:.1f}[/{out_fdr_col}]"
                f"->[{in_fdr_col}]{s.in_fdr:.1f}[/{in_fdr_col}]"
            )

            tbl.add_row(
                str(rank),
                f"{s.out_player.web_name} ({out_cost})",
                f"{s.in_player.web_name} ({in_cost})",
                position_str(s.out_player.element_type),
                f"[bold green]+{s.delta_value:.1f}[/bold green]",
                cost_str,
                form_str,
                fdr_str,
            )

        console.print(tbl)
        console.print(
            "[dim]Delta = value score improvement. "
            "FDR shown as out->in (lower = easier).[/dim]"
        )


@transfers_app.command()
def compare(
    player1: str = typer.Argument(..., help="First player name"),
    player2: str = typer.Argument(..., help="Second player name"),
) -> None:
    """Head-to-head player comparison."""
    init_db()

    with get_session() as session:
        result = compare_players(session, player1, player2)

        if result is None:
            console.print(
                f"[red]Could not find one or both players: "
                f"'{player1}', '{player2}'[/red]"
            )
            raise typer.Exit(1)

        c1, c2 = result

        tbl = Table(
            title=f"Player Comparison: {c1.player.web_name} vs {c2.player.web_name}",
            show_header=True,
            header_style="bold cyan",
        )
        tbl.add_column("Stat", style="bold")
        tbl.add_column(
            f"{c1.player.web_name} ({c1.team.short_name})",
            justify="right",
            min_width=16,
        )
        tbl.add_column(
            f"{c2.player.web_name} ({c2.team.short_name})",
            justify="right",
            min_width=16,
        )

        def _fmt_winner(v1: float, v2: float, fmt: str = ".2f") -> tuple[str, str]:
            s1 = f"{v1:{fmt}}"
            s2 = f"{v2:{fmt}}"
            if v1 > v2:
                return f"[bold green]{s1}[/bold green]", s2
            elif v2 > v1:
                return s1, f"[bold green]{s2}[/bold green]"
            return s1, s2

        def _fmt_winner_lower(
            v1: float, v2: float, fmt: str = ".2f"
        ) -> tuple[str, str]:
            """Lower is better (e.g. FDR)."""
            s1 = f"{v1:{fmt}}"
            s2 = f"{v2:{fmt}}"
            if v1 < v2:
                return f"[bold green]{s1}[/bold green]", s2
            elif v2 < v1:
                return s1, f"[bold green]{s2}[/bold green]"
            return s1, s2

        pos1 = position_str(c1.player.element_type)
        pos2 = position_str(c2.player.element_type)

        tbl.add_row("Position", pos1, pos2)
        tbl.add_row(
            "Cost",
            f"£{format_cost(c1.cost)}m",
            f"£{format_cost(c2.cost)}m",
        )

        fc1, fc2 = _fmt_winner(c1.form_score, c2.form_score, ".1f")
        tbl.add_row("Form Score", fc1, fc2)

        xg1, xg2 = _fmt_winner(c1.xg_per90, c2.xg_per90)
        tbl.add_row("xG/90", xg1, xg2)

        xa1, xa2 = _fmt_winner(c1.xa_per90, c2.xa_per90)
        tbl.add_row("xA/90", xa1, xa2)

        pp1, pp2 = _fmt_winner(c1.points_per90, c2.points_per90, ".1f")
        tbl.add_row("Points/90", pp1, pp2)

        fdr1, fdr2 = _fmt_winner_lower(c1.upcoming_fdr, c2.upcoming_fdr, ".1f")
        tbl.add_row("Upcoming FDR", fdr1, fdr2)

        m1, m2 = _fmt_winner(float(c1.minutes), float(c2.minutes), ".0f")
        tbl.add_row("Minutes", m1, m2)

        g1, g2 = _fmt_winner(float(c1.goals), float(c2.goals), ".0f")
        tbl.add_row("Goals", g1, g2)

        a1, a2 = _fmt_winner(float(c1.assists), float(c2.assists), ".0f")
        tbl.add_row("Assists", a1, a2)

        cs1, cs2 = _fmt_winner(float(c1.clean_sheets), float(c2.clean_sheets), ".0f")
        tbl.add_row("Clean Sheets", cs1, cs2)

        console.print(tbl)

        _print_ownership_comparison(c1, c2)


def _print_ownership_comparison(c1: PlayerComparison, c2: PlayerComparison) -> None:
    """Print ownership information below the comparison table."""
    try:
        own1 = float(c1.player.selected_by_percent)
        own2 = float(c2.player.selected_by_percent)
    except (ValueError, TypeError):
        return

    console.print(
        f"\n[dim]Ownership: {c1.player.web_name} {own1:.1f}% | "
        f"{c2.player.web_name} {own2:.1f}%[/dim]"
    )
