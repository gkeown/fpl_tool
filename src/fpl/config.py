from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FPL_", env_file=".env", extra="ignore"
    )

    id: int = 0  # FPL team ID
    db_path: Path = Path("data/fpl.db")
    fpl_base_url: str = "https://fantasy.premierleague.com/api"
    understat_base_url: str = "https://understat.com"
    fbref_base_url: str = "https://fbref.com"
    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"
    user_agent: str = "FPL-CLI/0.1.0"
    form_lookback_weeks: int = 5
    fdr_lookback_weeks: int = 10
    http_timeout: int = 30
    http_max_concurrent: int = 5


def get_settings() -> Settings:
    return Settings()
