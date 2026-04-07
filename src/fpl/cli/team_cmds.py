from __future__ import annotations

import asyncio
import contextlib

import typer
from rich.console import Console
from rich.table import Table

from fpl.analysis.form import get_current_gameweek
from fpl.analysis.team import TeamAnalysis, analyse_team
from fpl.cli.app import me_app
from fpl.cli.formatters import (
    fdr_color,
    form_color,
    format_cost,
    fpl_form_color,
    position_str,
)
from fpl.config import get_settings
from fpl.db.engine import get_session, init_db
from fpl.db.models import MyAccount, MyTeamPlayer, Player, PlayerProjection, Team

console = Console()


@me_app.command()
def login(
    team_id: int | None = typer.Argument(
        default=None,
        help=(
            "Your FPL team ID (or set FPL_ID in .env). "
            "Find it at fantasy.premierleague.com -> Points page URL."
        ),
    ),
) -> None:
    """Store your FPL team ID and fetch your squad."""
    init_db()

    settings = get_settings()

    # Use provided team_id, fall back to config
    if team_id is None:
        team_id = settings.id
    if team_id == 0:
        console.print(
            "[red]No team ID provided. Either pass it as an argument "
            "or set FPL_ID in your .env file.[/red]"
        )
        raise typer.Exit(1) from None

    async def _fetch() -> None:
        import httpx

        from fpl.ingest.fpl_api import (
            fetch_entry,
            fetch_entry_picks,
            upsert_my_team,
        )

        headers = {"User-Agent": settings.user_agent}
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            console.print(f"Fetching team {team_id}...")
            entry = await fetch_entry(client, settings, team_id)

            name = (
                f"{entry.get('player_first_name', '')} "
                f"{entry.get('player_last_name', '')}"
            ).strip()
            console.print(f"Manager: [bold]{name}[/bold]")

            current_gw = entry.get("current_event", 1)
            console.print(f"Loading GW{current_gw} picks...")
            picks = await fetch_entry_picks(client, settings, team_id, current_gw)

            with get_session() as session:
                count = upsert_my_team(session, team_id, entry, picks)
                console.print(
                    f"[green]Saved {count} players. "
                    f"Use 'fpl me team' to view your squad.[/green]"
                )

    try:
        asyncio.run(_fetch())
    except Exception as exc:
        console.print(f"[red]Failed to fetch team: {exc}[/red]")
        console.print(
            "[dim]Check your team ID is correct. You can find it at "
            "fantasy.premierleague.com -> Points page URL.[/dim]"
        )
        raise typer.Exit(1) from None


def _status_icon(status: str) -> str:
    return {
        "a": "[green]✓[/green]",
        "d": "[yellow]?[/yellow]",
        "i": "[red]✗[/red]",
        "s": "[red]S[/red]",
        "u": "[dim]-[/dim]",
    }.get(status, status)


@me_app.command()
def team(
    detail: bool = typer.Option(False, "--detail", help="Show expanded view"),
) -> None:
    """Show your current FPL team with form scores."""
    init_db()

    with get_session() as session:
        current_gw = get_current_gameweek(session)

        # Load my team players, joined to players + teams
        rows = (
            session.query(MyTeamPlayer, Player, Team)
            .join(Player, Player.fpl_id == MyTeamPlayer.player_id)
            .join(Team, Team.fpl_id == Player.team_id)
            .order_by(MyTeamPlayer.position)
            .all()
        )

        if not rows:
            console.print(
                "[yellow]No team data found. "
                "Run 'fpl me login <TEAM_ID>' to load your squad.[/yellow]"
            )
            return

        # Build FPL form lookup from Player.form (avg pts/game, last 30 days)
        form_lookup: dict[int, float] = {
            player.fpl_id: float(player.form) for _mtp, player, _ in rows
        }

        # Build projection lookup: player_id -> gw1_pts (with ep_next fallback)
        player_ids = [player.fpl_id for _mtp, player, _ in rows]
        proj_rows: list[PlayerProjection] = (
            session.query(PlayerProjection)
            .filter(PlayerProjection.player_id.in_(player_ids))
            .all()
        )
        proj_lookup: dict[int, float] = {p.player_id: p.gw1_pts for p in proj_rows}

        # ep_next fallback for players without Pundit projections
        ep_lookup: dict[int, float] = {}
        for _mtp, player, _ in rows:
            if player.fpl_id not in proj_lookup:
                ep_next_val = 0.0
                if player.ep_next:
                    with contextlib.suppress(ValueError):
                        ep_next_val = float(player.ep_next)
                ep_lookup[player.fpl_id] = ep_next_val

        def _xpts(pid: int) -> float:
            return proj_lookup.get(pid, ep_lookup.get(pid, 0.0))

        has_projections = bool(proj_lookup)

        # Load account info
        account: MyAccount | None = session.get(MyAccount, 1)
        bank_str = f"£{format_cost(account.bank)}m" if account is not None else "£?.?m"
        ft_str = str(account.free_transfers) if account is not None else "?"

        title = f"Your FPL Team (GW{current_gw})    Bank: {bank_str}    FT: {ft_str}"
        tbl = Table(title=title, show_header=True, header_style="bold cyan")
        tbl.add_column("Pos", justify="center")
        tbl.add_column("Player", min_width=18)
        tbl.add_column("Team", style="cyan")
        tbl.add_column("Cost", justify="right")
        tbl.add_column("Form", justify="right")
        tbl.add_column("xPts", justify="right")
        tbl.add_column("Status", justify="center")

        if detail:
            tbl.add_column("Cap", justify="center")

        bench_separator_added = False

        for mtp, player, tm in rows:
            is_bench = mtp.position > 11

            # Add separator row before bench
            if is_bench and not bench_separator_added:
                tbl.add_row("", "[dim]── BENCH ──[/dim]", "", "", "", "", "")
                bench_separator_added = True

            form_val = form_lookup[player.fpl_id]
            form_col = fpl_form_color(form_val)
            status_icon = _status_icon(player.status)
            xpts = _xpts(player.fpl_id)

            cap_marker = ""
            if mtp.is_captain:
                cap_marker = "[bold yellow](C)[/bold yellow]"
            elif mtp.is_vice_captain:
                cap_marker = "[yellow](V)[/yellow]"

            name_display = player.web_name
            if not detail:
                if mtp.is_captain:
                    name_display = f"{player.web_name} [bold yellow](C)[/bold yellow]"
                elif mtp.is_vice_captain:
                    name_display = f"{player.web_name} [yellow](V)[/yellow]"

            xpts_str = f"{xpts:.1f}" if xpts > 0 else "[dim]-[/dim]"

            row_data = [
                position_str(player.element_type),
                name_display,
                tm.short_name,
                f"£{format_cost(player.now_cost)}m",
                f"[{form_col}]{form_val:.1f}[/{form_col}]",
                xpts_str,
                status_icon,
            ]

            if detail:
                row_data.append(cap_marker)

            tbl.add_row(*row_data)

        console.print(tbl)

        if not has_projections:
            console.print(
                "[dim]Tip: run 'fpl data refresh --source projections' "
                "to add xPts projections.[/dim]"
            )
        if not form_lookup or all(v == 0.0 for v in form_lookup.values()):
            console.print(
                "[dim]Tip: run 'fpl data refresh' to update player data.[/dim]"
            )


@me_app.command()
def analyse(
    weeks: int = typer.Option(
        5, "--weeks", help="Look-ahead window for fixture difficulty"
    ),
) -> None:
    """Analyse your team — identify weak spots and suggest improvements."""
    init_db()

    with get_session() as session:
        analysis: TeamAnalysis | None = analyse_team(session, weeks_ahead=weeks)

        if analysis is None:
            console.print(
                "[yellow]No team data found. "
                "Run 'fpl me login <TEAM_ID>' to load your squad.[/yellow]"
            )
            return

        current_gw = get_current_gameweek(session)

        # Load projection data for squad players
        squad_ids = [pa.player.fpl_id for pa in analysis.players]
        proj_rows: list[PlayerProjection] = (
            session.query(PlayerProjection)
            .filter(PlayerProjection.player_id.in_(squad_ids))
            .all()
        )
        proj_by_id: dict[int, PlayerProjection] = {p.player_id: p for p in proj_rows}

        def _ep_next(player: Player) -> float:
            if player.ep_next:
                try:
                    return float(player.ep_next)
                except ValueError:
                    pass
            return 0.0

        def _proj_gw1(player: Player) -> float:
            proj = proj_by_id.get(player.fpl_id)
            return proj.gw1_pts if proj is not None else _ep_next(player)

        def _proj_3gw(player: Player) -> float:
            proj = proj_by_id.get(player.fpl_id)
            return proj.next_3gw_pts if proj is not None else 0.0

        def _proj_5gw(player: Player) -> float:
            proj = proj_by_id.get(player.fpl_id)
            return proj.next_5gw_pts if proj is not None else 0.0

        has_projections = bool(proj_by_id)

        # Team overview table
        tbl = Table(
            title=f"Team Analysis (GW{current_gw}, next {weeks} GWs)",
            show_header=True,
            header_style="bold cyan",
        )
        tbl.add_column("Pos", justify="center")
        tbl.add_column("Player", min_width=18)
        tbl.add_column("Team", style="cyan")
        tbl.add_column("Form", justify="right")
        tbl.add_column("Avg FDR", justify="right")
        tbl.add_column("Min%", justify="right")
        tbl.add_column("xVal", justify="right")
        tbl.add_column("xPts(1)", justify="right")
        tbl.add_column("xPts(3)", justify="right")
        tbl.add_column("xPts(5)", justify="right")
        tbl.add_column("Status", justify="center")

        bench_separator_added = False

        for pa in analysis.players:
            is_bench = not pa.is_starter
            if is_bench and not bench_separator_added:
                tbl.add_row(
                    "", "[dim]── BENCH ──[/dim]", "", "", "", "", "", "", "", "", ""
                )
                bench_separator_added = True

            form_col = form_color(pa.form_score)
            fdr_col = fdr_color(pa.upcoming_difficulty)
            status_icon = _status_icon(pa.player.status)

            name = pa.player.web_name
            if pa.is_captain:
                name = f"{name} [bold yellow](C)[/bold yellow]"
            elif pa.is_vice_captain:
                name = f"{name} [yellow](V)[/yellow]"

            gw1 = _proj_gw1(pa.player)
            gw3 = _proj_3gw(pa.player)
            gw5 = _proj_5gw(pa.player)

            tbl.add_row(
                position_str(pa.player.element_type),
                name,
                pa.team.short_name,
                f"[{form_col}]{pa.form_score:.1f}[/{form_col}]",
                f"[{fdr_col}]{pa.upcoming_difficulty:.1f}[/{fdr_col}]",
                f"{pa.minutes_probability:.0%}",
                f"{pa.expected_value:.2f}",
                f"{gw1:.1f}" if gw1 > 0 else "[dim]-[/dim]",
                f"{gw3:.1f}" if gw3 > 0 else "[dim]-[/dim]",
                f"{gw5:.1f}" if gw5 > 0 else "[dim]-[/dim]",
                status_icon,
            )

        console.print(tbl)

        # Projected points totals (starting XI only)
        starters = [pa for pa in analysis.players if pa.is_starter]
        total_gw1 = sum(_proj_gw1(pa.player) for pa in starters)
        total_gw3 = sum(_proj_3gw(pa.player) for pa in starters)
        total_gw5 = sum(_proj_5gw(pa.player) for pa in starters)

        if has_projections:
            console.print(
                f"\n[bold]Squad Projected Points (XI):[/bold]  "
                f"Next GW: [cyan]{total_gw1:.1f}[/cyan]  |  "
                f"Next 3 GWs: [cyan]{total_gw3:.1f}[/cyan]  |  "
                f"Next 5 GWs: [cyan]{total_gw5:.1f}[/cyan]"
            )

        # Summary
        console.print(
            f"[bold]Squad Strength (XI):[/bold] {analysis.total_strength:.2f}  "
            f"[bold]Bank:[/bold] £{format_cost(analysis.bank)}m  "
            f"[bold]Free Transfers:[/bold] {analysis.free_transfers}"
        )

        if analysis.weak_spots:
            console.print("\n[bold red]Weak Spots / Concerns:[/bold red]")
            for issue in analysis.weak_spots:
                console.print(f"  [yellow]•[/yellow] {issue}")
        else:
            console.print("\n[bold green]No major concerns identified.[/bold green]")

        if not has_projections:
            console.print(
                "\n[dim]Tip: run 'fpl data refresh --source projections' "
                "to add xPts projections.[/dim]"
            )
        if all(pa.form_score == 0.0 for pa in analysis.players):
            console.print(
                "\n[dim]Tip: run 'fpl data refresh' to compute "
                "form and FDR scores.[/dim]"
            )
