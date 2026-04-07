from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.config import get_settings
from fpl.db.models import (
    Gameweek,
    Player,
    PlayerFormScore,
    PlayerGameweekStats,
    UnderstatMatch,
)

logger = logging.getLogger(__name__)

# Per-position weights; keys are element_type values (1=GKP, 2=DEF, 3=MID, 4=FWD)
POSITION_WEIGHTS: dict[int, dict[str, float]] = {
    1: {  # GKP
        "points": 0.25,
        "bps": 0.20,
        "clean_sheets": 0.25,
        "saves": 0.15,
        "minutes": 0.15,
    },
    2: {  # DEF
        "points": 0.20,
        "bps": 0.15,
        "clean_sheets": 0.20,
        "xg": 0.10,
        "xa": 0.10,
        "ict": 0.10,
        "minutes": 0.15,
    },
    3: {  # MID
        "points": 0.20,
        "xg": 0.20,
        "xa": 0.15,
        "bps": 0.10,
        "ict": 0.15,
        "minutes": 0.10,
        "goals": 0.10,
    },
    4: {  # FWD
        "points": 0.15,
        "xg": 0.25,
        "xa": 0.10,
        "bps": 0.10,
        "ict": 0.10,
        "minutes": 0.10,
        "goals": 0.20,
    },
}


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def get_current_gameweek(session: Session) -> int:
    """Get the current or most recent finished gameweek number."""
    # Prefer is_current
    current = session.query(Gameweek).filter(Gameweek.is_current.is_(True)).first()
    if current is not None:
        return current.id

    # Fall back to the highest finished gameweek
    finished = (
        session.query(Gameweek)
        .filter(Gameweek.finished.is_(True))
        .order_by(Gameweek.id.desc())
        .first()
    )
    if finished is not None:
        return finished.id

    # No finished gameweeks yet — return 1
    return 1


def get_next_gameweek(session: Session) -> int:
    """Get the next unfinished gameweek number."""
    next_gw = session.query(Gameweek).filter(Gameweek.is_next.is_(True)).first()
    if next_gw is not None:
        return next_gw.id

    # Fall back to current + 1
    current = get_current_gameweek(session)
    return min(current + 1, 38)


def _calculate_per90(stats: list[PlayerGameweekStats], field: str) -> float:
    """Calculate a per-90-minute rate for a field across gameweek stats."""
    total_minutes = sum(s.minutes for s in stats)
    if total_minutes == 0:
        return 0.0

    total_value = 0.0
    for s in stats:
        raw = getattr(s, field, 0)
        if isinstance(raw, str):
            try:
                raw = float(raw)
            except (ValueError, TypeError):
                raw = 0.0
        total_value += float(raw)

    return total_value / total_minutes * 90.0


def _percentile_rank(value: float, all_values: list[float]) -> float:
    """Return 0-10 percentile rank of value within all_values.

    rank = (count of values <= value) / total * 10.0
    """
    if not all_values:
        return 0.0
    count_lte = sum(1 for v in all_values if v <= value)
    return count_lte / len(all_values) * 10.0


def _get_understat_per90(session: Session, player_id: int) -> tuple[float, float]:
    """Return (xg_per90, xa_per90) from Understat season aggregate row.

    Falls back to (0.0, 0.0) if no data is available.
    """
    agg = (
        session.query(UnderstatMatch)
        .filter(
            UnderstatMatch.player_id == player_id,
            UnderstatMatch.opponent == "season_aggregate",
        )
        .first()
    )
    if agg is None or agg.minutes == 0:
        return 0.0, 0.0
    xg_per90 = agg.xg / agg.minutes * 90.0
    xa_per90 = agg.xa / agg.minutes * 90.0
    return xg_per90, xa_per90


def compute_form_scores(
    session: Session,
    gameweek: int,
    lookback: int | None = None,
) -> int:
    """Compute and cache form scores for all active players. Returns count."""
    settings = get_settings()
    if lookback is None:
        lookback = settings.form_lookback_weeks

    # Fetch all active players (minutes > 0)
    players: list[Player] = session.query(Player).filter(Player.minutes > 0).all()
    if not players:
        logger.warning("No active players found; skipping form score computation.")
        return 0

    # Collect per-player raw per-90 stats
    # Structure: {player_id: {component: per90_value}}
    raw_stats: dict[int, dict[str, float]] = {}
    player_position: dict[int, int] = {}

    for player in players:
        pos = player.element_type
        player_position[player.fpl_id] = pos

        # Get last N gameweeks of stats
        gw_stats: list[PlayerGameweekStats] = (
            session.query(PlayerGameweekStats)
            .filter(
                PlayerGameweekStats.player_id == player.fpl_id,
                PlayerGameweekStats.gameweek <= gameweek,
            )
            .order_by(PlayerGameweekStats.gameweek.desc())
            .limit(lookback)
            .all()
        )

        if not gw_stats:
            continue

        total_minutes = sum(s.minutes for s in gw_stats)
        if total_minutes == 0:
            continue

        # Try Understat xG/xA first, fall back to FPL expected_goals/expected_assists
        us_xg, us_xa = _get_understat_per90(session, player.fpl_id)

        if us_xg > 0 or us_xa > 0:
            xg_per90 = us_xg
            xa_per90 = us_xa
        else:
            xg_per90 = _calculate_per90(gw_stats, "expected_goals")
            xa_per90 = _calculate_per90(gw_stats, "expected_assists")

        raw_stats[player.fpl_id] = {
            "points": _calculate_per90(gw_stats, "total_points"),
            "bps": _calculate_per90(gw_stats, "bps"),
            "clean_sheets": _calculate_per90(gw_stats, "clean_sheets"),
            "saves": _calculate_per90(gw_stats, "saves"),
            "xg": xg_per90,
            "xa": xa_per90,
            "ict": _calculate_per90(gw_stats, "ict_index"),
            "goals": _calculate_per90(gw_stats, "goals_scored"),
            "minutes": float(total_minutes),
        }

    if not raw_stats:
        return 0

    # Group players by position for percentile normalisation
    # Build per-position value lists for each component
    positions_seen = set(player_position[pid] for pid in raw_stats)
    # {position: {component: [values]}}
    pos_component_values: dict[int, dict[str, list[float]]] = {
        pos: {} for pos in positions_seen
    }
    for pid, components in raw_stats.items():
        pos = player_position[pid]
        for comp, val in components.items():
            pos_component_values[pos].setdefault(comp, []).append(val)

    # Compute form scores
    now = _now_utc()
    records: list[dict[str, object]] = []

    for pid, components in raw_stats.items():
        pos = player_position[pid]
        weights = POSITION_WEIGHTS.get(pos, POSITION_WEIGHTS[3])

        weighted_sum = 0.0
        total_weight = 0.0

        component_scores: dict[str, float] = {}
        for comp, weight in weights.items():
            val = components.get(comp, 0.0)
            all_vals = pos_component_values[pos].get(comp, [val])
            pct = _percentile_rank(val, all_vals)
            component_scores[comp] = pct
            weighted_sum += pct * weight
            total_weight += weight

        form_score = (weighted_sum / total_weight * 10.0) if total_weight > 0 else 0.0
        form_score = min(100.0, max(0.0, form_score))

        records.append(
            {
                "player_id": pid,
                "gameweek": gameweek,
                "form_score": form_score,
                "xg_component": component_scores.get("xg", 0.0),
                "xa_component": component_scores.get("xa", 0.0),
                "bps_component": component_scores.get("bps", 0.0),
                "ict_component": component_scores.get("ict", 0.0),
                "minutes_component": component_scores.get("minutes", 0.0),
                "points_component": component_scores.get("points", 0.0),
                "computed_at": now,
            }
        )

    if not records:
        return 0

    stmt = sqlite_insert(PlayerFormScore).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=[PlayerFormScore.player_id, PlayerFormScore.gameweek],
        set_={
            col: stmt.excluded[col]
            for col in (
                "form_score",
                "xg_component",
                "xa_component",
                "bps_component",
                "ict_component",
                "minutes_component",
                "points_component",
                "computed_at",
            )
        },
    )
    session.execute(stmt)

    logger.info("Computed form scores for %d players at GW%d", len(records), gameweek)
    return len(records)
