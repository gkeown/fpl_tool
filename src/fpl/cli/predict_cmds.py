from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from fpl.cli.app import predict_app
from fpl.cli.formatters import check_data_staleness, output_json
from fpl.db.engine import get_session, init_db
from fpl.db.models import Fixture, Team, TeamPrediction

console = Console()


@predict_app.command()
def goals(
    gameweek: int | None = typer.Option(None, help="Gameweek number (default: next)"),
    team: str | None = typer.Option(None, help="Filter by team name"),
    output_format: str = typer.Option(
        "table", "--format", help="Output format: table or json"
    ),
) -> None:
    """Show predicted goals for/against for each fixture."""
    init_db()

    with get_session() as session:
        warning = check_data_staleness(session)
        if warning:
            console.print(warning)

        from fpl.analysis.form import get_next_gameweek

        gw = gameweek if gameweek is not None else get_next_gameweek(session)

        # Fetch predictions joined to fixtures
        predictions: list[TeamPrediction] = (
            session.query(TeamPrediction).filter(TeamPrediction.gameweek == gw).all()
        )

        if not predictions:
            console.print(
                f"[yellow]No predictions found for GW{gw}. "
                "Run 'fpl data refresh' and re-compute predictions first.[/yellow]"
            )
            return

        fixtures: list[Fixture] = (
            session.query(Fixture).filter(Fixture.gameweek == gw).all()
        )

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}
        # Map fixture_id -> {team_id: TeamPrediction}
        pred_map: dict[int, dict[int, TeamPrediction]] = {}
        for p in predictions:
            pred_map.setdefault(p.fixture_id, {})[p.team_id] = p

        if output_format == "json":
            records = []
            for fixture in fixtures:
                h_team = team_lookup.get(fixture.team_h)
                a_team = team_lookup.get(fixture.team_a)
                h_name = h_team.name if h_team else str(fixture.team_h)
                a_name = a_team.name if a_team else str(fixture.team_a)

                if team is not None:
                    team_lower = team.lower()
                    if (
                        team_lower not in h_name.lower()
                        and team_lower not in a_name.lower()
                    ):
                        continue

                fmap = pred_map.get(fixture.fpl_id, {})
                h_pred = fmap.get(fixture.team_h)
                a_pred = fmap.get(fixture.team_a)

                records.append(
                    {
                        "gameweek": gw,
                        "home_team": h_name,
                        "away_team": a_name,
                        "home_predicted_goals": (
                            round(h_pred.predicted_goals_for, 3) if h_pred else None
                        ),
                        "away_predicted_goals": (
                            round(a_pred.predicted_goals_for, 3) if a_pred else None
                        ),
                        "home_cs_pct": (
                            round(h_pred.clean_sheet_probability * 100, 1)
                            if h_pred
                            else None
                        ),
                        "away_cs_pct": (
                            round(a_pred.clean_sheet_probability * 100, 1)
                            if a_pred
                            else None
                        ),
                    }
                )
            output_json(records)
            return

        table = Table(
            title=f"GW{gw} Goal Predictions",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column(f"GW{gw}", style="dim")
        table.add_column("Home", min_width=14)
        table.add_column("Pred", justify="right")
        table.add_column("Away", min_width=14)
        table.add_column("Pred", justify="right")
        table.add_column("CS%(H)", justify="right")
        table.add_column("CS%(A)", justify="right")

        for fixture in fixtures:
            h_team = team_lookup.get(fixture.team_h)
            a_team = team_lookup.get(fixture.team_a)
            h_name = h_team.name if h_team else str(fixture.team_h)
            a_name = a_team.name if a_team else str(fixture.team_a)

            if team is not None:
                team_lower = team.lower()
                if (
                    team_lower not in h_name.lower()
                    and team_lower not in a_name.lower()
                ):
                    continue

            fmap = pred_map.get(fixture.fpl_id, {})
            h_pred = fmap.get(fixture.team_h)
            a_pred = fmap.get(fixture.team_a)

            h_goals_str = f"{h_pred.predicted_goals_for:.2f}" if h_pred else "-"
            a_goals_str = f"{a_pred.predicted_goals_for:.2f}" if a_pred else "-"
            cs_h_str = f"{h_pred.clean_sheet_probability * 100:.0f}%" if h_pred else "-"
            cs_a_str = f"{a_pred.clean_sheet_probability * 100:.0f}%" if a_pred else "-"

            table.add_row(
                "",
                h_name,
                h_goals_str,
                a_name,
                a_goals_str,
                cs_h_str,
                cs_a_str,
            )

        console.print(table)


@predict_app.command()
def cleansheets(
    gameweek: int | None = typer.Option(None, help="Gameweek number (default: next)"),
    top: int = typer.Option(20, help="Number of teams to show"),
    output_format: str = typer.Option(
        "table", "--format", help="Output format: table or json"
    ),
) -> None:
    """Show clean sheet probability rankings."""
    init_db()

    with get_session() as session:
        warning = check_data_staleness(session)
        if warning:
            console.print(warning)

        from fpl.analysis.form import get_next_gameweek

        gw = gameweek if gameweek is not None else get_next_gameweek(session)

        predictions: list[TeamPrediction] = (
            session.query(TeamPrediction)
            .filter(TeamPrediction.gameweek == gw)
            .order_by(TeamPrediction.clean_sheet_probability.desc())
            .limit(top)
            .all()
        )

        if not predictions:
            console.print(f"[yellow]No predictions found for GW{gw}.[/yellow]")
            return

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}
        fixture_lookup: dict[int, Fixture] = {
            f.fpl_id: f
            for f in session.query(Fixture).filter(Fixture.gameweek == gw).all()
        }

        def _fixture_str(pred: TeamPrediction) -> tuple[str, str, str]:
            fixture = fixture_lookup.get(pred.fixture_id)
            if fixture is not None:
                is_home = fixture.team_h == pred.team_id
                opp_id = fixture.team_a if is_home else fixture.team_h
                opp = team_lookup.get(opp_id)
                opp_name = opp.short_name if opp else "?"
                ha = "H" if is_home else "A"
                return f"vs {opp_name} ({ha})", opp_name, ha
            return "-", "", ""

        if output_format == "json":
            records = []
            for rank, pred in enumerate(predictions, 1):
                team_obj = team_lookup.get(pred.team_id)
                team_name = team_obj.name if team_obj else str(pred.team_id)
                fix_str, opp_name, ha = _fixture_str(pred)
                records.append(
                    {
                        "rank": rank,
                        "team": team_name,
                        "fixture": fix_str,
                        "opponent": opp_name,
                        "home_away": ha,
                        "cs_pct": round(pred.clean_sheet_probability * 100, 1),
                        "predicted_goals_against": round(
                            pred.predicted_goals_against, 3
                        ),
                    }
                )
            output_json(records)
            return

        table = Table(
            title=f"GW{gw} Clean Sheet Probabilities",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Rank", justify="right", style="dim")
        table.add_column("Team", min_width=16)
        table.add_column("Fixture", min_width=20)
        table.add_column("CS%", justify="right")
        table.add_column("Pred GA", justify="right")

        for rank, pred in enumerate(predictions, 1):
            team_obj = team_lookup.get(pred.team_id)
            team_name = team_obj.name if team_obj else str(pred.team_id)
            fix_str, _, _ = _fixture_str(pred)
            cs_pct = f"{pred.clean_sheet_probability * 100:.0f}%"
            pred_ga = f"{pred.predicted_goals_against:.2f}"

            table.add_row(
                str(rank),
                team_name,
                fix_str,
                cs_pct,
                pred_ga,
            )

        console.print(table)
