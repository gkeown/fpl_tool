from __future__ import annotations

from sqlalchemy.orm import Session

from fpl.config import Settings, get_settings
from fpl.db.models import (
    Base,
    Player,
    Team,
)
from fpl.types import IngestSource, PlayerStatus, Position


def test_all_tables_created(db_session: Session) -> None:
    """All ORM tables should be created in the in-memory DB."""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "teams",
        "players",
        "player_gameweek_stats",
        "fixtures",
        "gameweeks",
        "player_id_maps",
        "understat_matches",
        "fbref_season_stats",
        "injuries",
        "my_team_players",
        "my_account",
        "ownership_snapshots",
        "player_form_scores",
        "custom_fdr",
        "team_predictions",
        "betting_odds",
        "player_projections",
        "ingest_logs",
        "leagues",
        "league_entries",
    }
    assert expected == table_names


def test_settings_defaults() -> None:
    """Settings should load with sensible defaults."""
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert str(settings.db_path) == "data/fpl.db"
    assert "fantasy.premierleague.com" in settings.fpl_base_url
    assert settings.form_lookback_weeks == 5


def test_position_enum() -> None:
    assert Position.GKP == 1
    assert Position.FWD == 4


def test_player_status_enum() -> None:
    assert PlayerStatus.AVAILABLE == "a"
    assert PlayerStatus.INJURED == "i"


def test_ingest_source_enum() -> None:
    assert IngestSource.FPL_BOOTSTRAP == "fpl_bootstrap"
    assert IngestSource.ODDS == "odds"


def test_insert_team_and_player(db_session: Session) -> None:
    """Basic insert/query smoke test for FK relationships."""
    team = Team(
        fpl_id=1,
        code=100,
        name="Arsenal",
        short_name="ARS",
        strength=5,
        strength_attack_home=1300,
        strength_attack_away=1250,
        strength_defence_home=1280,
        strength_defence_away=1200,
        updated_at="2026-04-06T00:00:00",
    )
    db_session.add(team)
    db_session.flush()

    player = Player(
        fpl_id=10,
        code=200,
        first_name="Bukayo",
        second_name="Saka",
        web_name="Saka",
        team_id=1,
        element_type=Position.MID,
        now_cost=105,
        selected_by_percent="45.2",
        status=PlayerStatus.AVAILABLE,
        form="8.5",
        points_per_game="6.2",
        total_points=150,
        minutes=2500,
        goals_scored=12,
        assists=10,
        clean_sheets=8,
        bonus=25,
        transfers_in=500000,
        transfers_out=100000,
        goals_conceded=0,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=0,
        red_cards=0,
        saves=0,
        starts=25,
        expected_goals="8.50",
        expected_assists="6.20",
        expected_goal_involvements="14.70",
        expected_goals_conceded="18.00",
        updated_at="2026-04-06T00:00:00",
    )
    db_session.add(player)
    db_session.flush()

    result = db_session.get(Player, 10)
    assert result is not None
    assert result.web_name == "Saka"
    assert result.team.name == "Arsenal"
