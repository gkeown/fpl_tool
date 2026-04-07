from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from fpl.analysis.form import get_next_gameweek
from fpl.cli.app import fixtures_app
from fpl.cli.formatters import fdr_color
from fpl.db.engine import get_session, init_db
from fpl.db.models import BettingOdds, CustomFdr, Fixture, Team

console = Console()


@fixtures_app.command()
def show(
    gameweek: int | None = typer.Option(None, help="Gameweek number"),
    team: str | None = typer.Option(None, help="Filter by team"),
) -> None:
    """Show fixture schedule."""
    init_db()

    with get_session() as session:
        from fpl.analysis.form import get_current_gameweek

        gw = gameweek if gameweek is not None else get_current_gameweek(session)

        query = session.query(Fixture).filter(Fixture.gameweek == gw)
        fixtures: list[Fixture] = query.order_by(Fixture.kickoff_time).all()

        if not fixtures:
            console.print(f"[yellow]No fixtures found for GW{gw}.[/yellow]")
            return

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}

        table = Table(
            title=f"GW{gw} Fixtures",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Kickoff")
        table.add_column("Home", min_width=16)
        table.add_column("Score", justify="center")
        table.add_column("Away", min_width=16)
        table.add_column("FDR(H)", justify="right")
        table.add_column("FDR(A)", justify="right")
        table.add_column("Status")

        for f in fixtures:
            h_team = team_lookup.get(f.team_h)
            a_team = team_lookup.get(f.team_a)
            h_name = h_team.name if h_team else str(f.team_h)
            a_name = a_team.name if a_team else str(f.team_a)

            if team is not None:
                t_lower = team.lower()
                if t_lower not in h_name.lower() and t_lower not in a_name.lower():
                    continue

            kickoff = f.kickoff_time[:16].replace("T", " ") if f.kickoff_time else "TBC"

            if f.team_h_score is not None and f.team_a_score is not None:
                score_str = f"{f.team_h_score} - {f.team_a_score}"
                status = "[green]FT[/green]"
            else:
                score_str = "vs"
                status = "[yellow]upcoming[/yellow]"

            fdr_h_str = str(f.team_h_difficulty)
            fdr_a_str = str(f.team_a_difficulty)

            table.add_row(
                kickoff,
                h_name,
                score_str,
                a_name,
                fdr_h_str,
                fdr_a_str,
                status,
            )

        console.print(table)


@fixtures_app.command()
def difficulty(
    weeks: int = typer.Option(6, help="Number of weeks to look ahead"),
    team: str | None = typer.Option(None, help="Filter by team"),
) -> None:
    """Show custom fixture difficulty ratings."""
    init_db()

    with get_session() as session:
        from fpl.analysis.form import get_current_gameweek

        current_gw = get_current_gameweek(session)
        max_gw = current_gw + weeks

        query = (
            session.query(CustomFdr)
            .filter(
                CustomFdr.gameweek > current_gw,
                CustomFdr.gameweek <= max_gw,
            )
            .order_by(CustomFdr.team_id, CustomFdr.gameweek)
        )

        fdrs: list[CustomFdr] = query.all()

        if not fdrs:
            console.print(
                "[yellow]No FDR data found. Run 'fpl data refresh' first.[/yellow]"
            )
            return

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}

        if team is not None:
            t_lower = team.lower()
            filtered_team_ids = {
                t.fpl_id
                for t in team_lookup.values()
                if t_lower in t.name.lower() or t_lower in t.short_name.lower()
            }
            fdrs = [f for f in fdrs if f.team_id in filtered_team_ids]

        if not fdrs:
            console.print(f"[yellow]No FDR data found for team '{team}'.[/yellow]")
            return

        # Group by team
        team_fdrs: dict[int, list[CustomFdr]] = {}
        for fdr in fdrs:
            team_fdrs.setdefault(fdr.team_id, []).append(fdr)

        # Build gameweek range for columns
        gw_range = list(range(current_gw + 1, max_gw + 1))

        table = Table(
            title=f"Fixture Difficulty Rating (GW{current_gw + 1}-{max_gw})",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Team", min_width=16)
        table.add_column("Avg FDR", justify="right")
        for gw in gw_range:
            table.add_column(f"GW{gw}", justify="center")

        # Sort teams by average FDR (easiest first)
        def _avg_fdr(tid: int) -> float:
            vals = [f.overall_difficulty for f in team_fdrs.get(tid, [])]
            return sum(vals) / len(vals) if vals else 5.0

        sorted_team_ids = sorted(team_fdrs.keys(), key=_avg_fdr)

        for tid in sorted_team_ids:
            t = team_lookup.get(tid)
            t_name = t.name if t else str(tid)
            gw_fdr: dict[int, CustomFdr] = {f.gameweek: f for f in team_fdrs[tid]}

            avg = _avg_fdr(tid)
            avg_col = fdr_color(avg)

            row_cols: list[str] = [t_name, f"[{avg_col}]{avg:.2f}[/{avg_col}]"]
            for gw in gw_range:
                fdr = gw_fdr.get(gw)  # type: ignore[assignment]
                if fdr is None:
                    row_cols.append("[dim]—[/dim]")
                else:
                    diff = fdr.overall_difficulty
                    col = fdr_color(diff)
                    opp = team_lookup.get(fdr.opponent_id)
                    opp_str = opp.short_name if opp else "?"
                    ha = "H" if fdr.is_home else "A"
                    row_cols.append(f"[{col}]{opp_str}({ha})[/{col}]")

            table.add_row(*row_cols)

        console.print(table)


@fixtures_app.command()
def odds(
    gameweek: int | None = typer.Option(None, help="Gameweek number (default: next)"),
) -> None:
    """Show betting odds for upcoming fixtures."""
    init_db()

    with get_session() as session:
        gw = gameweek if gameweek is not None else get_next_gameweek(session)

        fixtures = (
            session.query(Fixture)
            .filter(Fixture.gameweek == gw)
            .order_by(Fixture.kickoff_time)
            .all()
        )

        if not fixtures:
            console.print(f"[yellow]No fixtures found for GW{gw}.[/yellow]")
            return

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}

        # Get consensus odds for each fixture
        odds_map: dict[int, dict[str, BettingOdds]] = {}
        for fix in fixtures:
            h2h = (
                session.query(BettingOdds)
                .filter(
                    BettingOdds.fixture_id == fix.fpl_id,
                    BettingOdds.market == "h2h",
                    BettingOdds.bookmaker == "consensus",
                )
                .first()
            )
            totals = (
                session.query(BettingOdds)
                .filter(
                    BettingOdds.fixture_id == fix.fpl_id,
                    BettingOdds.market == "totals",
                    BettingOdds.bookmaker == "consensus",
                )
                .first()
            )
            fix_odds: dict[str, BettingOdds] = {}
            if h2h:
                fix_odds["h2h"] = h2h
            if totals:
                fix_odds["totals"] = totals
            if fix_odds:
                odds_map[fix.fpl_id] = fix_odds

        if not odds_map:
            console.print(
                f"[yellow]No odds data for GW{gw}. "
                "Set FPL_ODDS_API_KEY and run "
                "'fpl data refresh --source odds'.[/yellow]"
            )
            return

        table = Table(
            title=f"GW{gw} Fixture Odds",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Home", min_width=14)
        table.add_column("H Win", justify="right")
        table.add_column("Draw", justify="right")
        table.add_column("A Win", justify="right")
        table.add_column("Away", min_width=14)
        table.add_column("O2.5", justify="right")
        table.add_column("U2.5", justify="right")

        for fix in fixtures:
            h = team_lookup.get(fix.team_h)
            a = team_lookup.get(fix.team_a)
            h_name = h.name if h else "?"
            a_name = a.name if a else "?"

            fix_odds = odds_map.get(fix.fpl_id, {})
            h2h_odds = fix_odds.get("h2h")
            totals_odds = fix_odds.get("totals")

            h_win = (
                f"{h2h_odds.home_odds:.2f}" if h2h_odds and h2h_odds.home_odds else "-"
            )
            draw = (
                f"{h2h_odds.draw_odds:.2f}" if h2h_odds and h2h_odds.draw_odds else "-"
            )
            a_win = (
                f"{h2h_odds.away_odds:.2f}" if h2h_odds and h2h_odds.away_odds else "-"
            )
            o25 = (
                f"{totals_odds.over_2_5:.2f}"
                if totals_odds and totals_odds.over_2_5
                else "-"
            )
            u25 = (
                f"{totals_odds.under_2_5:.2f}"
                if totals_odds and totals_odds.under_2_5
                else "-"
            )

            table.add_row(h_name, h_win, draw, a_win, a_name, o25, u25)

        console.print(table)
        console.print(
            "[dim]Consensus odds averaged across bookmakers. "
            "Source: The Odds API.[/dim]"
        )
