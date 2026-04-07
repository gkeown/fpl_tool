from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(name="fpl", help="FPL Fantasy Football CLI", no_args_is_help=True)

_console = Console()

data_app = typer.Typer(
    name="data", help="Data ingestion and management", no_args_is_help=True
)
me_app = typer.Typer(name="me", help="Your FPL team", no_args_is_help=True)
players_app = typer.Typer(
    name="players", help="Player search and analysis", no_args_is_help=True
)
fixtures_app = typer.Typer(
    name="fixtures", help="Fixture schedule and difficulty", no_args_is_help=True
)
predict_app = typer.Typer(
    name="predict", help="Goal and clean sheet predictions", no_args_is_help=True
)
transfers_app = typer.Typer(
    name="transfers", help="Transfer recommendations", no_args_is_help=True
)
prices_app = typer.Typer(
    name="prices", help="Price change predictions", no_args_is_help=True
)
captain_app = typer.Typer(
    name="captain", help="Captain recommendations", no_args_is_help=True
)

app.add_typer(data_app)
app.add_typer(me_app)
app.add_typer(players_app)
app.add_typer(fixtures_app)
app.add_typer(predict_app)
app.add_typer(transfers_app)
app.add_typer(prices_app)
app.add_typer(captain_app)


@app.callback()
def main() -> None:
    """FPL Fantasy Football CLI — data-driven FPL assistant."""


@app.command()
def news(
    top: int = typer.Option(10, help="Number of headlines to show"),
) -> None:
    """Show latest FPL news from Fantasy Football Scout."""
    try:
        import feedparser  # type: ignore[import-untyped]
    except ImportError:
        _console.print(
            "[red]feedparser is not installed. " "Run: pip install feedparser[/red]"
        )
        raise typer.Exit(1) from None

    feed_url = "https://www.fantasyfootballscout.co.uk/feed/"
    feed = feedparser.parse(feed_url)

    if not feed.entries:
        _console.print(
            "[yellow]No news articles found. "
            "Check your internet connection.[/yellow]"
        )
        return

    from rich.table import Table

    tbl = Table(
        title="Latest FPL News",
        show_header=True,
        header_style="bold cyan",
        show_lines=False,
    )
    tbl.add_column("Date", style="dim", min_width=12, no_wrap=True)
    tbl.add_column("Headline")

    for entry in feed.entries[:top]:
        # published_parsed is a time.struct_time or None
        published = entry.get("published_parsed")
        if published is not None:
            import time

            date_str = time.strftime("%Y-%m-%d", published)
        else:
            date_str = "Unknown"

        title = entry.get("title", "(no title)")
        tbl.add_row(date_str, title)

    _console.print(tbl)


import fpl.cli.captain_cmds  # noqa: E402
import fpl.cli.data_cmds  # noqa: E402
import fpl.cli.fixtures_cmds  # noqa: E402
import fpl.cli.player_cmds  # noqa: E402
import fpl.cli.predict_cmds  # noqa: E402
import fpl.cli.price_cmds  # noqa: E402
import fpl.cli.team_cmds  # noqa: E402
import fpl.cli.transfer_cmds  # noqa: F401, E402
