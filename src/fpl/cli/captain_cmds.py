from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from fpl.analysis.captaincy import CaptainCandidate, pick_captains
from fpl.analysis.form import get_current_gameweek
from fpl.cli.app import captain_app
from fpl.cli.formatters import (
    check_data_staleness,
    fdr_color,
    form_color,
    format_cost,
    position_str,
)
from fpl.db.engine import get_session, init_db
from fpl.db.models import CustomFdr, MyTeamPlayer, Player, PlayerProjection, Team

console = Console()


def _fixture_label(
    session: object,
    team_id: int,
    current_gw: int,
    is_home: bool,
) -> str:
    """Build a short fixture label, e.g. 'vs WHU (H)'."""
    from sqlalchemy.orm import Session

    s: Session = session  # type: ignore[assignment]

    fdr: CustomFdr | None = (
        s.query(CustomFdr)
        .filter(
            CustomFdr.team_id == team_id,
            CustomFdr.gameweek > current_gw,
        )
        .order_by(CustomFdr.gameweek)
        .first()
    )
    if fdr is None:
        return "TBC"

    opp: Team | None = s.get(Team, fdr.opponent_id)
    opp_name = opp.short_name if opp is not None else "???"
    ha = "H" if is_home else "A"
    return f"vs {opp_name} ({ha})"


@captain_app.command(name="pick")
def pick(
    top: int = typer.Option(5, "--top", help="Number of candidates to show"),
    detail: bool = typer.Option(False, "--detail", help="Show scoring breakdown"),
) -> None:
    """Get captain recommendations for the next gameweek."""
    init_db()

    with get_session() as session:
        warning = check_data_staleness(session)
        if warning:
            console.print(warning)

        current_gw = get_current_gameweek(session)

        # Determine if the user has a team loaded
        my_team: list[MyTeamPlayer] = session.query(MyTeamPlayer).all()
        player_ids: list[int] | None = None
        source_label = "All Players"

        if my_team:
            player_ids = [mtp.player_id for mtp in my_team]
            source_label = "Your Squad"

        candidates: list[CaptainCandidate] = pick_captains(
            session, player_ids=player_ids, top=top
        )

        if not candidates:
            console.print(
                "[yellow]No captain data available. "
                "Run 'fpl data refresh' to compute form and FDR scores.[/yellow]"
            )
            return

        # Load projection data for candidate players
        candidate_ids = [c.player.fpl_id for c in candidates]
        proj_rows: list[PlayerProjection] = (
            session.query(PlayerProjection)
            .filter(PlayerProjection.player_id.in_(candidate_ids))
            .all()
        )
        proj_by_id: dict[int, PlayerProjection] = {p.player_id: p for p in proj_rows}

        def _xpts_next_gw(player: Player) -> float | None:
            proj = proj_by_id.get(player.fpl_id)
            if proj is not None:
                return proj.gw1_pts
            if player.ep_next:
                try:
                    return float(player.ep_next)
                except ValueError:
                    pass
            return None

        has_projections = bool(proj_by_id)

        next_gw = current_gw + 1
        title = f"Captain Recommendations (GW{next_gw})  —  {source_label}"
        tbl = Table(title=title, show_header=True, header_style="bold cyan")
        tbl.add_column("Rank", justify="right", style="dim")
        tbl.add_column("Player", min_width=14)
        tbl.add_column("Team", style="cyan")
        tbl.add_column("Pos", justify="center")
        tbl.add_column("Cost", justify="right")
        tbl.add_column("Fixture", min_width=12)
        tbl.add_column("Score", justify="right")
        tbl.add_column("Form", justify="right")
        tbl.add_column("Fix Ease", justify="right")
        tbl.add_column("xPts", justify="right")

        if detail:
            tbl.add_column("xG/90", justify="right")
            tbl.add_column("xA/90", justify="right")
            tbl.add_column("Home", justify="center")
            tbl.add_column("Haul%", justify="right")

        for rank, c in enumerate(candidates, 1):
            form_col = form_color(c.form_score)
            # fixture_ease is (6 - fdr), so fdr = 6 - fixture_ease
            implied_fdr = 6.0 - c.fixture_ease
            ease_col = fdr_color(implied_fdr)

            fixture_str = _fixture_label(session, c.team.fpl_id, current_gw, c.is_home)

            xpts_val = _xpts_next_gw(c.player)
            xpts_str = f"{xpts_val:.1f}" if xpts_val is not None else "[dim]-[/dim]"

            row: list[str] = [
                str(rank),
                c.player.web_name,
                c.team.short_name,
                position_str(c.player.element_type),
                f"£{format_cost(c.player.now_cost)}m",
                fixture_str,
                f"[bold]{c.captain_score:.1f}[/bold]",
                f"[{form_col}]{c.form_score:.1f}[/{form_col}]",
                f"[{ease_col}]{c.fixture_ease:.1f}[/{ease_col}]",
                xpts_str,
            ]

            if detail:
                home_icon = "[green]✓[/green]" if c.is_home else "[dim]-[/dim]"
                row.extend(
                    [
                        f"{c.xg_per90:.2f}",
                        f"{c.xa_per90:.2f}",
                        home_icon,
                        f"{c.haul_rate:.0%}",
                    ]
                )

            tbl.add_row(*row)

        console.print(tbl)

        if not has_projections:
            console.print(
                "[dim]Run 'fpl data refresh --source projections' "
                "to add xPts projections.[/dim]"
            )
        if not detail:
            console.print("[dim]Use --detail for full scoring breakdown.[/dim]")
