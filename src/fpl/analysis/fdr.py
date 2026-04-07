from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.db.models import CustomFdr, Fixture, Team, UnderstatMatch

logger = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


@dataclasses.dataclass
class TeamSeasonStats:
    team_id: int
    games_played: int
    goals_scored: int
    goals_conceded: int
    xg: float  # from Understat if available, else 0
    xga: float
    goals_per_game: float
    goals_conceded_per_game: float


def get_team_season_stats(session: Session) -> dict[int, TeamSeasonStats]:
    """Compute goals scored/conceded per game for each team from finished fixtures."""
    finished: list[Fixture] = (
        session.query(Fixture)
        .filter(
            Fixture.finished.is_(True),
            Fixture.team_h_score.isnot(None),
            Fixture.team_a_score.isnot(None),
        )
        .all()
    )

    # Accumulate raw counts
    goals_scored: dict[int, int] = {}
    goals_conceded: dict[int, int] = {}
    games_played: dict[int, int] = {}

    for f in finished:
        h_score = f.team_h_score or 0
        a_score = f.team_a_score or 0

        goals_scored[f.team_h] = goals_scored.get(f.team_h, 0) + h_score
        goals_conceded[f.team_h] = goals_conceded.get(f.team_h, 0) + a_score
        games_played[f.team_h] = games_played.get(f.team_h, 0) + 1

        goals_scored[f.team_a] = goals_scored.get(f.team_a, 0) + a_score
        goals_conceded[f.team_a] = goals_conceded.get(f.team_a, 0) + h_score
        games_played[f.team_a] = games_played.get(f.team_a, 0) + 1

    # Understat team-level xG/xGA is not stored per-team in our schema.
    # We derive a rough proxy from player-level UnderstatMatch season aggregates.
    # Sum xg (attack) and xa can't give us xGA directly, so we skip it here.
    # (xGA per team would require team-level Understat data we don't ingest.)
    all_team_ids = set(games_played.keys())

    result: dict[int, TeamSeasonStats] = {}
    for team_id in all_team_ids:
        gp = games_played[team_id]
        gs = goals_scored.get(team_id, 0)
        gc = goals_conceded.get(team_id, 0)
        result[team_id] = TeamSeasonStats(
            team_id=team_id,
            games_played=gp,
            goals_scored=gs,
            goals_conceded=gc,
            xg=0.0,
            xga=0.0,
            goals_per_game=gs / gp if gp > 0 else 0.0,
            goals_conceded_per_game=gc / gp if gp > 0 else 0.0,
        )

    # Enrich with Understat xG where available (sum across all players for that team,
    # using only season_aggregate rows).  This gives attack xG only.
    team_xg: dict[int, float] = {}
    # Iterate player aggregates
    # and look up the player's team to aggregate xG at team level.
    from fpl.db.models import Player

    player_xg_rows = (
        session.query(Player.team_id, UnderstatMatch.xg)
        .join(UnderstatMatch, UnderstatMatch.player_id == Player.fpl_id)
        .filter(UnderstatMatch.opponent == "season_aggregate")
        .all()
    )
    for team_id_val, xg_val in player_xg_rows:
        team_xg[team_id_val] = team_xg.get(team_id_val, 0.0) + xg_val

    # Normalise xG by games played and store
    for team_id, stats in result.items():
        if team_id in team_xg and stats.games_played > 0:
            result[team_id] = dataclasses.replace(
                stats, xg=team_xg[team_id] / stats.games_played
            )

    return result


def _normalize_to_range(
    value: float,
    min_val: float,
    max_val: float,
    out_min: float = 1.0,
    out_max: float = 5.0,
) -> float:
    """Linearly scale value from [min_val, max_val] to [out_min, out_max]."""
    if max_val == min_val:
        return (out_min + out_max) / 2.0
    scaled = (value - min_val) / (max_val - min_val)
    return out_min + scaled * (out_max - out_min)


def compute_fdr(session: Session, weeks_ahead: int = 6) -> int:
    """Compute custom FDR for upcoming fixtures. Returns count stored."""
    team_stats = get_team_season_stats(session)
    all_teams: list[Team] = session.query(Team).all()

    if not all_teams or not team_stats:
        logger.warning("Insufficient data to compute FDR.")
        return 0

    # Determine the current / next gameweek range
    from fpl.analysis.form import get_current_gameweek

    current_gw = get_current_gameweek(session)
    max_gw = current_gw + weeks_ahead

    # Fetch upcoming (unfinished) fixtures within the window
    upcoming: list[Fixture] = (
        session.query(Fixture)
        .filter(
            Fixture.finished.is_(False),
            Fixture.gameweek.isnot(None),
            Fixture.gameweek > current_gw,
            Fixture.gameweek <= max_gw,
        )
        .all()
    )

    if not upcoming:
        logger.info("No upcoming fixtures found for FDR computation.")
        return 0

    # Pre-compute normalisation bounds across all teams
    all_team_ids = [t.fpl_id for t in all_teams]

    def _safe_stats(tid: int) -> TeamSeasonStats:
        return team_stats.get(
            tid,
            TeamSeasonStats(
                team_id=tid,
                games_played=0,
                goals_scored=0,
                goals_conceded=0,
                xg=0.0,
                xga=0.0,
                goals_per_game=0.0,
                goals_conceded_per_game=0.0,
            ),
        )

    # Build FPL strength lookup
    team_strength: dict[int, Team] = {t.fpl_id: t for t in all_teams}

    # Find global min/max for normalisation
    gpg_values = [_safe_stats(tid).goals_per_game for tid in all_team_ids]
    gcpg_values = [_safe_stats(tid).goals_conceded_per_game for tid in all_team_ids]
    xg_values = [_safe_stats(tid).xg for tid in all_team_ids]

    sa_home_values = [
        team_strength[tid].strength_attack_home
        for tid in all_team_ids
        if tid in team_strength
    ]
    sa_away_values = [
        team_strength[tid].strength_attack_away
        for tid in all_team_ids
        if tid in team_strength
    ]
    sd_home_values = [
        team_strength[tid].strength_defence_home
        for tid in all_team_ids
        if tid in team_strength
    ]
    sd_away_values = [
        team_strength[tid].strength_defence_away
        for tid in all_team_ids
        if tid in team_strength
    ]

    def _minmax(vals: list[float]) -> tuple[float, float]:
        if not vals:
            return 0.0, 1.0
        return min(vals), max(vals)

    gpg_min, gpg_max = _minmax(gpg_values)
    gcpg_min, gcpg_max = _minmax(gcpg_values)
    xg_min, xg_max = _minmax(xg_values)
    sa_h_min, sa_h_max = _minmax([float(v) for v in sa_home_values])
    sa_a_min, sa_a_max = _minmax([float(v) for v in sa_away_values])
    sd_h_min, sd_h_max = _minmax([float(v) for v in sd_home_values])
    sd_a_min, sd_a_max = _minmax([float(v) for v in sd_away_values])

    now = _now_utc()
    records: list[dict[str, object]] = []

    for fixture in upcoming:
        gw = fixture.gameweek
        if gw is None:
            continue

        for is_home in (True, False):
            team_id = fixture.team_h if is_home else fixture.team_a
            opponent_id = fixture.team_a if is_home else fixture.team_h

            opp_stats = _safe_stats(opponent_id)
            opp_team = team_strength.get(opponent_id)

            # Home/away factor: home teams concede less → easier to score vs them? No:
            # home_away_factor represents how hard it is to score against this opponent.
            # Opponent at home → they're stronger defensively → harder to score against.
            home_away_factor = 1.0 if not is_home else 0.0  # 1 = we're away (harder)

            # Normalise opponent defensive strength (higher = harder to score against)
            if opp_team is not None:
                opp_sd = float(
                    opp_team.strength_defence_home
                    if not is_home
                    else opp_team.strength_defence_away
                )
                opp_sa = float(
                    opp_team.strength_attack_home
                    if not is_home
                    else opp_team.strength_attack_away
                )
                norm_sd = _normalize_to_range(
                    opp_sd,
                    sd_h_min if not is_home else sd_a_min,
                    sd_h_max if not is_home else sd_a_max,
                    0.0,
                    1.0,
                )
                norm_sa = _normalize_to_range(
                    opp_sa,
                    sa_h_min if not is_home else sa_a_min,
                    sa_h_max if not is_home else sa_a_max,
                    0.0,
                    1.0,
                )
            else:
                norm_sd = 0.5
                norm_sa = 0.5

            norm_gcpg = _normalize_to_range(
                opp_stats.goals_conceded_per_game, gcpg_min, gcpg_max, 0.0, 1.0
            )
            norm_gpg = _normalize_to_range(
                opp_stats.goals_per_game, gpg_min, gpg_max, 0.0, 1.0
            )
            norm_xga = _normalize_to_range(opp_stats.xga, xg_min, xg_max, 0.0, 1.0)
            norm_xg = _normalize_to_range(opp_stats.xg, xg_min, xg_max, 0.0, 1.0)

            # attack_difficulty = how hard it is for US to score (opponent defends well)
            # Higher norm_sd → opponent defends well → harder for us
            # Higher norm_gcpg → opponent concedes more → easier for us (invert)
            attack_difficulty_raw = (
                0.4 * norm_sd
                + 0.3 * (1.0 - norm_gcpg)  # invert: fewer goals conceded = harder
                + 0.2 * (1.0 - norm_xga)  # lower xGA conceded = harder
                + 0.1 * home_away_factor
            )

            # defence_difficulty = how hard it is for US to keep a clean sheet
            # Higher norm_sa → opponent attacks well → harder for us
            defence_difficulty_raw = (
                0.4 * norm_sa + 0.3 * norm_gpg + 0.2 * norm_xg + 0.1 * home_away_factor
            )

            overall_raw = 0.5 * attack_difficulty_raw + 0.5 * defence_difficulty_raw

            # Scale to 1.0-5.0
            attack_difficulty = _normalize_to_range(
                attack_difficulty_raw, 0.0, 1.0, 1.0, 5.0
            )
            defence_difficulty = _normalize_to_range(
                defence_difficulty_raw, 0.0, 1.0, 1.0, 5.0
            )
            overall_difficulty = _normalize_to_range(overall_raw, 0.0, 1.0, 1.0, 5.0)

            records.append(
                {
                    "team_id": team_id,
                    "gameweek": gw,
                    "opponent_id": opponent_id,
                    "is_home": is_home,
                    "attack_difficulty": attack_difficulty,
                    "defence_difficulty": defence_difficulty,
                    "overall_difficulty": overall_difficulty,
                    "computed_at": now,
                }
            )

    if not records:
        return 0

    stmt = sqlite_insert(CustomFdr).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=[CustomFdr.team_id, CustomFdr.gameweek, CustomFdr.opponent_id],
        set_={
            col: stmt.excluded[col]
            for col in (
                "is_home",
                "attack_difficulty",
                "defence_difficulty",
                "overall_difficulty",
                "computed_at",
            )
        },
    )
    session.execute(stmt)

    logger.info("Computed FDR for %d team/fixture combinations.", len(records))
    return len(records)
