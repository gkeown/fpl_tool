from __future__ import annotations

import asyncio

import typer
from rapidfuzz import fuzz, process
from rich.console import Console
from rich.table import Table

from fpl.analysis.differentials import Differential, find_differentials
from fpl.cli.app import players_app
from fpl.cli.formatters import (
    fdr_color,
    form_color,
    format_cost,
    fpl_form_color,
    position_str,
)
from fpl.db.engine import get_session, init_db
from fpl.db.models import (
    CustomFdr,
    Player,
    PlayerGameweekStats,
    PlayerProjection,
    Team,
)

console = Console()


@players_app.command()
def form(
    position: str | None = typer.Option(
        None, help="Filter by position: GKP, DEF, MID, FWD"
    ),
    max_cost: float | None = typer.Option(None, help="Maximum cost (e.g., 8.0)"),
    min_minutes: int = typer.Option(90, help="Minimum total minutes played"),
    top: int = typer.Option(20, help="Number of players to show"),
) -> None:
    """Show players ranked by FPL form (avg points/game, last 30 days)."""
    init_db()

    _POSITION_TYPE: dict[str, int] = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}

    with get_session() as session:
        query = (
            session.query(Player, Team)
            .join(Team, Team.fpl_id == Player.team_id)
            .filter(Player.minutes >= min_minutes)
        )

        if position is not None:
            pos_upper = position.upper()
            if pos_upper not in _POSITION_TYPE:
                console.print(
                    f"[red]Unknown position '{position}'. "
                    "Use GKP, DEF, MID or FWD.[/red]"
                )
                raise typer.Exit(1)
            query = query.filter(Player.element_type == _POSITION_TYPE[pos_upper])

        if max_cost is not None:
            cost_tenths = int(max_cost * 10)
            query = query.filter(Player.now_cost <= cost_tenths)

        rows = query.all()

        if not rows:
            console.print(
                "[yellow]No player data found. Run 'fpl data refresh' first.[/yellow]"
            )
            return

        # Sort by FPL form descending, take top N
        rows.sort(key=lambda r: float(r[0].form), reverse=True)
        rows = rows[:top]

        table = Table(
            title="Player Form Rankings (FPL)",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Rank", justify="right", style="dim")
        table.add_column("Player", min_width=16)
        table.add_column("Team", style="cyan")
        table.add_column("Pos", justify="center")
        table.add_column("Cost", justify="right")
        table.add_column("Form", justify="right")
        table.add_column("xG/90", justify="right")
        table.add_column("xA/90", justify="right")
        table.add_column("Pts/90", justify="right")

        for rank, (player, team) in enumerate(rows, 1):
            fpl_form = float(player.form)
            color = fpl_form_color(fpl_form)

            # Compute per-90 from recent GW stats for display
            recent_stats: list[PlayerGameweekStats] = (
                session.query(PlayerGameweekStats)
                .filter(PlayerGameweekStats.player_id == player.fpl_id)
                .order_by(PlayerGameweekStats.gameweek.desc())
                .limit(5)
                .all()
            )

            total_mins = sum(s.minutes for s in recent_stats)

            def _per90(
                field: str, stats: list[PlayerGameweekStats], mins: int
            ) -> float:
                if mins == 0:
                    return 0.0
                total = sum(float(getattr(s, field, 0) or 0) for s in stats)
                return total / mins * 90.0

            xg_per90 = _per90("expected_goals", recent_stats, total_mins)
            xa_per90 = _per90("expected_assists", recent_stats, total_mins)
            pts_per90 = _per90("total_points", recent_stats, total_mins)

            table.add_row(
                str(rank),
                player.web_name,
                team.short_name,
                position_str(player.element_type),
                format_cost(player.now_cost),
                f"[{color}]{fpl_form:.1f}[/{color}]",
                f"{xg_per90:.2f}",
                f"{xa_per90:.2f}",
                f"{pts_per90:.1f}",
            )

        console.print(table)
        console.print("[dim]Form = FPL avg points/game over the last 30 days.[/dim]")


@players_app.command()
def search(query: str = typer.Argument(..., help="Player name to search")) -> None:
    """Search for a player by name."""
    init_db()

    with get_session() as session:
        players: list[Player] = session.query(Player).all()

        if not players:
            console.print(
                "[yellow]No player data found. Run 'fpl data refresh' first.[/yellow]"
            )
            return

        # Build searchable strings: combine web_name, first_name, second_name
        choices: dict[str, int] = {}
        for p in players:
            key = f"{p.web_name} ({p.first_name} {p.second_name})"
            choices[key] = p.fpl_id

        matches = process.extract(
            query,
            list(choices.keys()),
            scorer=fuzz.WRatio,
            limit=10,
        )

        if not matches:
            console.print("[yellow]No matches found.[/yellow]")
            return

        table = Table(
            title=f"Search results for '{query}'",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Player")
        table.add_column("Team", style="cyan")
        table.add_column("Pos", justify="center")
        table.add_column("Cost", justify="right")
        table.add_column("Status")
        table.add_column("Score", justify="right", style="dim")

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}
        player_lookup: dict[int, Player] = {p.fpl_id: p for p in players}

        for match_str, score, _ in matches:
            if score < 50:
                continue
            pid = choices[match_str]
            p = player_lookup[pid]
            team = team_lookup.get(p.team_id)
            team_short = team.short_name if team else "?"

            status_color = {
                "a": "green",
                "d": "yellow",
                "i": "red",
                "s": "red",
                "u": "dim",
            }.get(p.status, "white")

            table.add_row(
                f"{p.first_name} {p.second_name} ({p.web_name})",
                team_short,
                position_str(p.element_type),
                format_cost(p.now_cost),
                f"[{status_color}]{p.status}[/{status_color}]",
                str(score),
            )

        console.print(table)


@players_app.command()
def info(name: str = typer.Argument(..., help="Player name or ID")) -> None:
    """Show detailed player information."""
    init_db()

    with get_session() as session:
        player: Player | None = None

        # Try numeric ID first
        if name.isdigit():
            player = session.get(Player, int(name))
        else:
            # Fuzzy search
            players: list[Player] = session.query(Player).all()
            choices: dict[str, int] = {}
            for p in players:
                choices[f"{p.web_name} {p.first_name} {p.second_name}"] = p.fpl_id

            best = process.extractOne(name, list(choices.keys()), scorer=fuzz.WRatio)
            if best is not None and best[1] >= 60:
                player = session.get(Player, choices[best[0]])

        if player is None:
            console.print(f"[red]Player '{name}' not found.[/red]")
            raise typer.Exit(1)

        team = session.get(Team, player.team_id)
        team_name = team.name if team else "Unknown"

        # Header info
        console.print()
        console.print(
            f"[bold]{player.web_name}[/bold]  "
            f"({player.first_name} {player.second_name})  "
            f"[cyan]{team_name}[/cyan]  "
            f"[dim]{position_str(player.element_type)}[/dim]  "
            f"[bold]£{format_cost(player.now_cost)}m[/bold]"
        )
        if player.news:
            console.print(f"[yellow]News: {player.news}[/yellow]")
        console.print()

        # Season stats
        stat_table = Table(title="Season Stats", show_header=True, header_style="bold")
        stat_table.add_column("Stat")
        stat_table.add_column("Value", justify="right")
        stat_table.add_column("Stat")
        stat_table.add_column("Value", justify="right")

        stats_pairs = [
            ("Total Points", str(player.total_points)),
            ("Minutes", str(player.minutes)),
            ("Goals", str(player.goals_scored)),
            ("Assists", str(player.assists)),
            ("Clean Sheets", str(player.clean_sheets)),
            ("Bonus", str(player.bonus)),
            ("xG", player.expected_goals),
            ("xA", player.expected_assists),
            ("Tackles", str(player.tackles)),
            ("Recoveries", str(player.recoveries)),
            ("CBI", str(player.clearances_blocks_interceptions)),
            ("Saves", str(player.saves)),
            ("Selected By", f"{player.selected_by_percent}%"),
            ("Starts", str(player.starts)),
        ]

        for i in range(0, len(stats_pairs), 2):
            left = stats_pairs[i]
            right = stats_pairs[i + 1] if i + 1 < len(stats_pairs) else ("", "")
            stat_table.add_row(left[0], left[1], right[0], right[1])

        console.print(stat_table)

        # Defensive stats for DEF and MID
        if player.element_type in (2, 3):
            mins = max(player.minutes, 1)
            dc_per90 = player.defensive_contribution / mins * 90
            cbi_per90 = (
                player.clearances_blocks_interceptions / mins * 90
            )
            rec_per90 = player.recoveries / mins * 90
            tck_per90 = player.tackles / mins * 90

            def_table = Table(
                title="Defensive Stats (DEFCON)",
                show_header=True,
                header_style="bold",
            )
            def_table.add_column("Stat")
            def_table.add_column("Total", justify="right")
            def_table.add_column("Per 90", justify="right")
            def_table.add_row(
                "DEFCON",
                str(player.defensive_contribution),
                f"{dc_per90:.1f}",
            )
            def_table.add_row(
                "CBI",
                str(player.clearances_blocks_interceptions),
                f"{cbi_per90:.1f}",
            )
            def_table.add_row(
                "Recoveries",
                str(player.recoveries),
                f"{rec_per90:.1f}",
            )
            def_table.add_row(
                "Tackles",
                str(player.tackles),
                f"{tck_per90:.1f}",
            )
            console.print(def_table)

        # Recent GW history
        recent: list[PlayerGameweekStats] = (
            session.query(PlayerGameweekStats)
            .filter(PlayerGameweekStats.player_id == player.fpl_id)
            .order_by(PlayerGameweekStats.gameweek.desc())
            .limit(5)
            .all()
        )

        is_def_or_mid = player.element_type in (2, 3)

        if recent:
            hist_table = Table(
                title="Recent Gameweeks", show_header=True, header_style="bold"
            )
            hist_table.add_column("GW", justify="right")
            hist_table.add_column("Pts", justify="right")
            hist_table.add_column("Mins", justify="right")
            hist_table.add_column("G", justify="right")
            hist_table.add_column("A", justify="right")
            hist_table.add_column("CS", justify="right")
            hist_table.add_column("BPS", justify="right")
            hist_table.add_column("xG")
            hist_table.add_column("xA")
            if is_def_or_mid:
                hist_table.add_column("DC", justify="right")

            for gw in recent:
                row_data = [
                    str(gw.gameweek),
                    str(gw.total_points),
                    str(gw.minutes),
                    str(gw.goals_scored),
                    str(gw.assists),
                    str(gw.clean_sheets),
                    str(gw.bps),
                    gw.expected_goals,
                    gw.expected_assists,
                ]
                if is_def_or_mid:
                    row_data.append(str(gw.defensive_contribution))
                hist_table.add_row(*row_data)

            console.print(hist_table)

        # FPL form
        fpl_form = float(player.form)
        fpl_form_col = fpl_form_color(fpl_form)
        console.print(
            f"\n[bold]FPL Form:[/bold] [{fpl_form_col}]{fpl_form:.1f}[/{fpl_form_col}]"
            "  [dim](avg pts/game, last 30 days)[/dim]"
        )

        # Projected points
        proj: PlayerProjection | None = session.get(
            PlayerProjection, player.fpl_id
        )
        if proj is not None:
            proj_table = Table(
                title="Projected Points",
                show_header=True,
                header_style="bold",
            )
            proj_table.add_column("Next GW", justify="right")
            proj_table.add_column("GW+2", justify="right")
            proj_table.add_column("GW+3", justify="right")
            proj_table.add_column("GW+4", justify="right")
            proj_table.add_column("GW+5", justify="right")
            proj_table.add_column("Next 3", justify="right", style="bold")
            proj_table.add_column("Next 5", justify="right", style="bold")
            proj_table.add_row(
                f"{proj.gw1_pts:.1f}",
                f"{proj.gw2_pts:.1f}",
                f"{proj.gw3_pts:.1f}",
                f"{proj.gw4_pts:.1f}",
                f"{proj.gw5_pts:.1f}",
                f"[cyan]{proj.next_3gw_pts:.1f}[/cyan]",
                f"[cyan]{proj.next_5gw_pts:.1f}[/cyan]",
            )
            console.print(proj_table)
            extras: list[str] = []
            if proj.start_probability > 0:
                extras.append(f"Start%: {proj.start_probability:.0f}%")
            if proj.cs_probability > 0:
                extras.append(f"CS%: {proj.cs_probability:.0f}%")
            if proj.is_double:
                extras.append("[green]Double GW[/green]")
            if proj.is_blank:
                extras.append("[red]Blank GW[/red]")
            if extras:
                console.print("  " + "  |  ".join(extras))
        else:
            ep = player.ep_next
            if ep:
                console.print(
                    f"[bold]FPL xPts (next GW):[/bold] {ep}"
                    "  [dim](run 'fpl data refresh --source "
                    "projections' for full projections)[/dim]"
                )

        # Set-piece notes for this player's team
        async def _fetch_setpiece_notes_for_team(
            tid: int,
        ) -> list[str]:
            import httpx

            from fpl.config import get_settings

            settings = get_settings()
            url = "https://fantasy.premierleague.com/api/team/set-piece-notes/"
            headers = {"User-Agent": settings.user_agent}
            try:
                async with httpx.AsyncClient(
                    timeout=settings.http_timeout, headers=headers
                ) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    for entry in data.get("teams", []):
                        if entry.get("id") == tid:
                            return [
                                n.get("info_message", "")
                                for n in entry.get("notes", [])
                                if n.get("info_message")
                            ]
            except Exception:
                pass
            return []

        sp_notes = asyncio.run(_fetch_setpiece_notes_for_team(player.team_id))
        if sp_notes:
            console.print("\n[bold]Set-Piece Notes:[/bold]")
            for note in sp_notes:
                console.print(f"  [yellow]•[/yellow] {note}")

        # Upcoming fixtures with FDR
        from fpl.analysis.form import get_current_gameweek

        current_gw = get_current_gameweek(session)
        upcoming_fdrs: list[CustomFdr] = (
            session.query(CustomFdr)
            .filter(
                CustomFdr.team_id == player.team_id,
                CustomFdr.gameweek > current_gw,
                CustomFdr.gameweek <= current_gw + 6,
            )
            .order_by(CustomFdr.gameweek)
            .all()
        )

        if upcoming_fdrs:
            from fpl.cli.formatters import fdr_color

            fdr_table = Table(
                title="Upcoming Fixtures (FDR)", show_header=True, header_style="bold"
            )
            fdr_table.add_column("GW", justify="right")
            fdr_table.add_column("Opponent")
            fdr_table.add_column("H/A", justify="center")
            fdr_table.add_column("Overall FDR", justify="right")
            fdr_table.add_column("Attack", justify="right")
            fdr_table.add_column("Defence", justify="right")

            team_names: dict[int, str] = {
                t.fpl_id: t.short_name for t in session.query(Team).all()
            }

            for fdr in upcoming_fdrs:
                opp_name = team_names.get(fdr.opponent_id, "?")
                ha = "H" if fdr.is_home else "A"
                diff = fdr.overall_difficulty
                col = fdr_color(diff)
                fdr_table.add_row(
                    str(fdr.gameweek),
                    opp_name,
                    ha,
                    f"[{col}]{diff:.1f}[/{col}]",
                    f"{fdr.attack_difficulty:.1f}",
                    f"{fdr.defence_difficulty:.1f}",
                )

            console.print(fdr_table)


@players_app.command()
def setpieces(
    team: str | None = typer.Option(None, help="Filter by team name (partial match)"),
) -> None:
    """Show set-piece taker notes for each team."""

    async def _fetch() -> dict[int, list[str]]:
        import httpx

        from fpl.config import get_settings

        settings = get_settings()
        url = "https://fantasy.premierleague.com/api/team/set-piece-notes/"
        headers = {"User-Agent": settings.user_agent}
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        result: dict[int, list[str]] = {}
        for entry in data.get("teams", []):
            tid = entry.get("id")
            notes = [
                n.get("info_message", "")
                for n in entry.get("notes", [])
                if n.get("info_message")
            ]
            if notes:
                result[tid] = notes
        return result

    try:
        notes_by_team_id = asyncio.run(_fetch())
    except Exception as exc:
        console.print(f"[red]Failed to fetch set-piece notes: {exc}[/red]")
        raise typer.Exit(1) from None

    if not notes_by_team_id:
        console.print("[yellow]No set-piece notes available.[/yellow]")
        return

    # Resolve team names from DB
    init_db()
    with get_session() as session:
        teams: list[Team] = session.query(Team).all()
        team_map: dict[int, Team] = {t.fpl_id: t for t in teams}

        console.print()
        console.print("[bold]Set-Piece Notes[/bold]")
        console.print()

        team_filter = team.lower() if team else None

        shown = 0
        for tid, notes in sorted(
            notes_by_team_id.items(),
            key=lambda kv: team_map[kv[0]].name if kv[0] in team_map else "",
        ):
            team_obj = team_map.get(tid)
            team_name = team_obj.name if team_obj is not None else f"Team {tid}"

            if team_filter and team_filter not in team_name.lower():
                continue

            console.print(f"[bold cyan]{team_name}[/bold cyan]")
            for note in notes:
                console.print(f"  [yellow]•[/yellow] {note}")
            console.print()
            shown += 1

        if shown == 0:
            console.print(f"[yellow]No notes found for team '{team}'.[/yellow]")


@players_app.command()
def differentials(
    max_ownership: float = typer.Option(
        10.0, help="Maximum ownership percentage to consider"
    ),
    position: str | None = typer.Option(
        None, help="Filter by position: GKP, DEF, MID, FWD"
    ),
    min_minutes: int = typer.Option(200, help="Minimum total minutes played"),
    top: int = typer.Option(20, help="Number of players to show"),
) -> None:
    """Find high-value, low-ownership differential players."""
    init_db()

    _POSITION_TYPE: dict[str, int] = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    pos_filter: int | None = None

    if position is not None:
        pos_upper = position.upper()
        if pos_upper not in _POSITION_TYPE:
            console.print(
                f"[red]Unknown position '{position}'. "
                "Use GKP, DEF, MID or FWD.[/red]"
            )
            raise typer.Exit(1)
        pos_filter = _POSITION_TYPE[pos_upper]

    with get_session() as session:
        diffs: list[Differential] = find_differentials(
            session,
            max_ownership=max_ownership,
            min_minutes=min_minutes,
            position=pos_filter,
            top=top,
        )

        if not diffs:
            console.print(
                "[yellow]No differentials found. "
                "Run 'fpl data refresh' first.[/yellow]"
            )
            return

        tbl = Table(
            title=f"Differentials (max {max_ownership:.0f}% ownership)",
            show_header=True,
            header_style="bold cyan",
        )
        tbl.add_column("Rank", justify="right", style="dim")
        tbl.add_column("Player", min_width=14)
        tbl.add_column("Team", style="cyan")
        tbl.add_column("Pos", justify="center")
        tbl.add_column("Cost", justify="right")
        tbl.add_column("Own%", justify="right")
        tbl.add_column("Form", justify="right")
        tbl.add_column("FDR", justify="right")
        tbl.add_column("Value", justify="right")

        for rank, d in enumerate(diffs, 1):
            form_col = form_color(d.form_score)
            fdr_col = fdr_color(d.upcoming_fdr)

            tbl.add_row(
                str(rank),
                d.player.web_name,
                d.team.short_name,
                position_str(d.player.element_type),
                f"£{format_cost(d.cost)}m",
                f"{d.ownership:.1f}%",
                f"[{form_col}]{d.form_score:.1f}[/{form_col}]",
                f"[{fdr_col}]{d.upcoming_fdr:.1f}[/{fdr_col}]",
                f"{d.value_score:.2f}",
            )

        console.print(tbl)
        console.print(
            "[dim]Value = form * fixture_ease / cost. "
            "Higher value with low ownership = best differentials.[/dim]"
        )
