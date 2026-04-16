from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(unique=True)
    role: Mapped[str]  # "admin" or "guest"
    fpl_team_id: Mapped[int] = mapped_column(default=0)
    league_ids: Mapped[str] = mapped_column(default="")
    created_at: Mapped[str]


class Team(Base):
    __tablename__ = "teams"

    fpl_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[int]
    name: Mapped[str]
    short_name: Mapped[str]
    strength: Mapped[int]
    strength_attack_home: Mapped[int]
    strength_attack_away: Mapped[int]
    strength_defence_home: Mapped[int]
    strength_defence_away: Mapped[int]
    played: Mapped[int] = mapped_column(default=0)
    win: Mapped[int] = mapped_column(default=0)
    draw: Mapped[int] = mapped_column(default=0)
    loss: Mapped[int] = mapped_column(default=0)
    points: Mapped[int] = mapped_column(default=0)
    position: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[str]

    players: Mapped[list[Player]] = relationship(back_populates="team")
    home_fixtures: Mapped[list[Fixture]] = relationship(
        foreign_keys="Fixture.team_h", back_populates="home_team"
    )
    away_fixtures: Mapped[list[Fixture]] = relationship(
        foreign_keys="Fixture.team_a", back_populates="away_team"
    )
    custom_fdrs_as_team: Mapped[list[CustomFdr]] = relationship(
        foreign_keys="CustomFdr.team_id", back_populates="team"
    )
    custom_fdrs_as_opponent: Mapped[list[CustomFdr]] = relationship(
        foreign_keys="CustomFdr.opponent_id", back_populates="opponent"
    )
    team_predictions: Mapped[list[TeamPrediction]] = relationship(back_populates="team")


class Player(Base):
    __tablename__ = "players"

    fpl_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[int]
    first_name: Mapped[str]
    second_name: Mapped[str]
    web_name: Mapped[str]
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.fpl_id"))
    element_type: Mapped[int]
    now_cost: Mapped[int]
    selected_by_percent: Mapped[str]
    status: Mapped[str]
    news: Mapped[str | None]
    chance_of_playing_next: Mapped[int | None]
    form: Mapped[str]
    points_per_game: Mapped[str]
    ep_next: Mapped[str | None]
    total_points: Mapped[int]
    minutes: Mapped[int]
    goals_scored: Mapped[int]
    assists: Mapped[int]
    clean_sheets: Mapped[int]
    bonus: Mapped[int]
    transfers_in: Mapped[int]
    transfers_out: Mapped[int]
    transfers_in_event: Mapped[int] = mapped_column(default=0)
    transfers_out_event: Mapped[int] = mapped_column(default=0)
    goals_conceded: Mapped[int]
    own_goals: Mapped[int]
    penalties_saved: Mapped[int]
    penalties_missed: Mapped[int]
    yellow_cards: Mapped[int]
    red_cards: Mapped[int]
    saves: Mapped[int]
    starts: Mapped[int]
    expected_goals: Mapped[str]
    expected_assists: Mapped[str]
    expected_goal_involvements: Mapped[str]
    expected_goals_conceded: Mapped[str]
    penalties_order: Mapped[int | None]
    corners_and_indirect_freekicks_order: Mapped[int | None]
    direct_freekicks_order: Mapped[int | None]
    clearances_blocks_interceptions: Mapped[int] = mapped_column(default=0)
    recoveries: Mapped[int] = mapped_column(default=0)
    tackles: Mapped[int] = mapped_column(default=0)
    defensive_contribution: Mapped[int] = mapped_column(default=0)
    event_points: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[str]

    team: Mapped[Team] = relationship(back_populates="players")
    gameweek_stats: Mapped[list[PlayerGameweekStats]] = relationship(
        back_populates="player"
    )
    id_maps: Mapped[list[PlayerIdMap]] = relationship(back_populates="player")
    understat_matches: Mapped[list[UnderstatMatch]] = relationship(
        back_populates="player"
    )
    fbref_season_stats: Mapped[list[FbrefSeasonStats]] = relationship(
        back_populates="player"
    )
    injuries: Mapped[list[Injury]] = relationship(back_populates="player")
    my_team_entries: Mapped[list[MyTeamPlayer]] = relationship(back_populates="player")
    ownership_snapshots: Mapped[list[OwnershipSnapshot]] = relationship(
        back_populates="player"
    )
    form_scores: Mapped[list[PlayerFormScore]] = relationship(back_populates="player")
    projections: Mapped[list[PlayerProjection]] = relationship(back_populates="player")


class PlayerGameweekStats(Base):
    __tablename__ = "player_gameweek_stats"
    __table_args__ = (UniqueConstraint("player_id", "gameweek", "fixture_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.fpl_id"))
    gameweek: Mapped[int]
    fixture_id: Mapped[int]
    opponent_team: Mapped[int] = mapped_column(ForeignKey("teams.fpl_id"))
    was_home: Mapped[bool]
    minutes: Mapped[int]
    total_points: Mapped[int]
    goals_scored: Mapped[int]
    assists: Mapped[int]
    clean_sheets: Mapped[int]
    bonus: Mapped[int]
    bps: Mapped[int]
    ict_index: Mapped[str]
    influence: Mapped[str]
    creativity: Mapped[str]
    threat: Mapped[str]
    selected: Mapped[int]
    transfers_in: Mapped[int]
    transfers_out: Mapped[int]
    value: Mapped[int]
    expected_goals: Mapped[str]
    expected_assists: Mapped[str]
    expected_goals_conceded: Mapped[str]
    goals_conceded: Mapped[int]
    own_goals: Mapped[int]
    penalties_saved: Mapped[int]
    penalties_missed: Mapped[int]
    yellow_cards: Mapped[int]
    red_cards: Mapped[int]
    saves: Mapped[int]
    starts: Mapped[int]
    clearances_blocks_interceptions: Mapped[int] = mapped_column(default=0)
    recoveries: Mapped[int] = mapped_column(default=0)
    tackles: Mapped[int] = mapped_column(default=0)
    defensive_contribution: Mapped[int] = mapped_column(default=0)

    player: Mapped[Player] = relationship(back_populates="gameweek_stats")


class Fixture(Base):
    __tablename__ = "fixtures"

    fpl_id: Mapped[int] = mapped_column(primary_key=True)
    gameweek: Mapped[int | None]
    kickoff_time: Mapped[str | None]
    team_h: Mapped[int] = mapped_column(ForeignKey("teams.fpl_id"))
    team_a: Mapped[int] = mapped_column(ForeignKey("teams.fpl_id"))
    team_h_score: Mapped[int | None]
    team_a_score: Mapped[int | None]
    team_h_difficulty: Mapped[int]
    team_a_difficulty: Mapped[int]
    finished: Mapped[bool] = mapped_column(default=False)
    finished_provisional: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[str]

    home_team: Mapped[Team] = relationship(
        foreign_keys=[team_h], back_populates="home_fixtures"
    )
    away_team: Mapped[Team] = relationship(
        foreign_keys=[team_a], back_populates="away_fixtures"
    )
    betting_odds: Mapped[list[BettingOdds]] = relationship(back_populates="fixture")
    team_predictions: Mapped[list[TeamPrediction]] = relationship(
        back_populates="fixture"
    )


class Gameweek(Base):
    __tablename__ = "gameweeks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    deadline_time: Mapped[str]
    finished: Mapped[bool] = mapped_column(default=False)
    is_current: Mapped[bool] = mapped_column(default=False)
    is_next: Mapped[bool] = mapped_column(default=False)
    is_previous: Mapped[bool] = mapped_column(default=False)
    average_score: Mapped[int | None]
    highest_score: Mapped[int | None]
    updated_at: Mapped[str]


class PlayerIdMap(Base):
    __tablename__ = "player_id_maps"

    fpl_id: Mapped[int] = mapped_column(ForeignKey("players.fpl_id"), primary_key=True)
    source: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str]
    confidence: Mapped[float]
    matched_by: Mapped[str]

    player: Mapped[Player] = relationship(back_populates="id_maps")


class UnderstatMatch(Base):
    __tablename__ = "understat_matches"
    __table_args__ = (UniqueConstraint("player_id", "date", "opponent"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.fpl_id"))
    date: Mapped[str]
    opponent: Mapped[str]
    was_home: Mapped[bool]
    minutes: Mapped[int]
    goals: Mapped[int]
    xg: Mapped[float]
    assists: Mapped[int]
    xa: Mapped[float]
    shots: Mapped[int]
    key_passes: Mapped[int]
    npg: Mapped[int]
    npxg: Mapped[float]

    player: Mapped[Player] = relationship(back_populates="understat_matches")


class FbrefSeasonStats(Base):
    __tablename__ = "fbref_season_stats"
    __table_args__ = (UniqueConstraint("player_id", "season"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.fpl_id"))
    season: Mapped[str]
    progressive_carries: Mapped[float | None]
    progressive_passes: Mapped[float | None]
    shot_creating_actions: Mapped[float | None]
    goal_creating_actions: Mapped[float | None]
    pressures: Mapped[float | None]
    tackles_won: Mapped[float | None]
    interceptions: Mapped[float | None]
    blocks: Mapped[float | None]
    aerial_won: Mapped[float | None]
    touches_att_pen: Mapped[float | None]
    carries_final_third: Mapped[float | None]
    passes_into_final_third: Mapped[float | None]

    player: Mapped[Player] = relationship(back_populates="fbref_season_stats")


class Injury(Base):
    __tablename__ = "injuries"
    __table_args__ = (UniqueConstraint("player_id", "source", "description"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.fpl_id"))
    status: Mapped[str]
    description: Mapped[str]
    expected_return: Mapped[str | None]
    source: Mapped[str]
    first_seen: Mapped[str]
    last_seen: Mapped[str]
    resolved: Mapped[bool] = mapped_column(default=False)

    player: Mapped[Player] = relationship(back_populates="injuries")


class MyTeamPlayer(Base):
    __tablename__ = "my_team_players"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(default=1)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.fpl_id"))
    selling_price: Mapped[int]
    purchase_price: Mapped[int]
    position: Mapped[int]
    is_captain: Mapped[bool] = mapped_column(default=False)
    is_vice_captain: Mapped[bool] = mapped_column(default=False)
    multiplier: Mapped[int] = mapped_column(default=1)
    fetched_at: Mapped[str]

    player: Mapped[Player] = relationship(back_populates="my_team_entries")


class MyAccount(Base):
    __tablename__ = "my_account"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(default=1, unique=True)
    fpl_team_id: Mapped[int]
    player_name: Mapped[str]
    overall_points: Mapped[int]
    overall_rank: Mapped[int]
    bank: Mapped[int]
    total_transfers: Mapped[int]
    free_transfers: Mapped[int]
    gameweek_points: Mapped[int]
    active_chip: Mapped[str | None] = mapped_column(default=None)
    chips_json: Mapped[str | None] = mapped_column(default=None)
    fetched_at: Mapped[str]


class OwnershipSnapshot(Base):
    __tablename__ = "ownership_snapshots"
    __table_args__ = (UniqueConstraint("player_id", "snapshot_time"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.fpl_id"))
    gameweek: Mapped[int]
    snapshot_time: Mapped[str]
    selected_by_percent: Mapped[str]
    transfers_in_delta: Mapped[int]
    transfers_out_delta: Mapped[int]
    net_transfer_delta: Mapped[int]

    player: Mapped[Player] = relationship(back_populates="ownership_snapshots")


class PlayerFormScore(Base):
    __tablename__ = "player_form_scores"

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.fpl_id"), primary_key=True
    )
    gameweek: Mapped[int] = mapped_column(primary_key=True)
    form_score: Mapped[float]
    xg_component: Mapped[float]
    xa_component: Mapped[float]
    bps_component: Mapped[float]
    ict_component: Mapped[float]
    minutes_component: Mapped[float]
    points_component: Mapped[float]
    computed_at: Mapped[str]

    player: Mapped[Player] = relationship(back_populates="form_scores")


class CustomFdr(Base):
    __tablename__ = "custom_fdr"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.fpl_id"), primary_key=True)
    gameweek: Mapped[int] = mapped_column(primary_key=True)
    opponent_id: Mapped[int] = mapped_column(
        ForeignKey("teams.fpl_id"), primary_key=True
    )
    is_home: Mapped[bool]
    attack_difficulty: Mapped[float]
    defence_difficulty: Mapped[float]
    overall_difficulty: Mapped[float]
    computed_at: Mapped[str]

    team: Mapped[Team] = relationship(
        foreign_keys=[team_id], back_populates="custom_fdrs_as_team"
    )
    opponent: Mapped[Team] = relationship(
        foreign_keys=[opponent_id], back_populates="custom_fdrs_as_opponent"
    )


class TeamPrediction(Base):
    __tablename__ = "team_predictions"
    __table_args__ = (UniqueConstraint("fixture_id", "team_id", "source"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.fpl_id"))
    gameweek: Mapped[int]
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.fpl_id"))
    predicted_goals_for: Mapped[float]
    predicted_goals_against: Mapped[float]
    clean_sheet_probability: Mapped[float]
    source: Mapped[str]
    computed_at: Mapped[str]

    fixture: Mapped[Fixture] = relationship(back_populates="team_predictions")
    team: Mapped[Team] = relationship(back_populates="team_predictions")


class BettingOdds(Base):
    __tablename__ = "betting_odds"
    __table_args__ = (UniqueConstraint("fixture_id", "source", "market", "bookmaker"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.fpl_id"))
    gameweek: Mapped[int]
    source: Mapped[str]
    market: Mapped[str]
    home_odds: Mapped[float | None]
    draw_odds: Mapped[float | None]
    away_odds: Mapped[float | None]
    over_2_5: Mapped[float | None]
    under_2_5: Mapped[float | None]
    btts_yes: Mapped[float | None]
    btts_no: Mapped[float | None]
    bookmaker: Mapped[str]
    fetched_at: Mapped[str]

    fixture: Mapped[Fixture] = relationship(back_populates="betting_odds")


class PlayerProjection(Base):
    __tablename__ = "player_projections"

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.fpl_id"), primary_key=True
    )
    gw1_pts: Mapped[float] = mapped_column(default=0.0)  # next GW
    gw2_pts: Mapped[float] = mapped_column(default=0.0)
    gw3_pts: Mapped[float] = mapped_column(default=0.0)
    gw4_pts: Mapped[float] = mapped_column(default=0.0)
    gw5_pts: Mapped[float] = mapped_column(default=0.0)
    next_3gw_pts: Mapped[float] = mapped_column(default=0.0)
    next_5gw_pts: Mapped[float] = mapped_column(default=0.0)
    start_probability: Mapped[float] = mapped_column(default=0.0)
    cs_probability: Mapped[float] = mapped_column(default=0.0)
    is_blank: Mapped[bool] = mapped_column(default=False)
    is_double: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(default="pundit")
    fetched_at: Mapped[str]

    player: Mapped[Player] = relationship(back_populates="projections")


class League(Base):
    __tablename__ = "leagues"
    __table_args__ = (UniqueConstraint("user_id", "league_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(default=1)
    league_id: Mapped[int]
    name: Mapped[str]
    fetched_at: Mapped[str]

    entries: Mapped[list[LeagueEntry]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )


class LeagueEntry(Base):
    __tablename__ = "league_entries"
    __table_args__ = (UniqueConstraint("league_id", "entry_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    entry_id: Mapped[int]
    player_name: Mapped[str]
    entry_name: Mapped[str]
    rank: Mapped[int]
    total: Mapped[int]
    event_total: Mapped[int] = mapped_column(default=0)
    fetched_at: Mapped[str]

    league: Mapped[League] = relationship(back_populates="entries")


class IngestLog(Base):
    __tablename__ = "ingest_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str]
    started_at: Mapped[str]
    finished_at: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="running")
    records_upserted: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None]
