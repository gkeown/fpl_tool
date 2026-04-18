from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from rapidfuzz import fuzz, process

from fpl.analysis.differentials import find_differentials
from fpl.analysis.form import get_current_gameweek
from fpl.cli.formatters import format_cost, position_str
from fpl.config import get_settings
from fpl.db.engine import get_session
from fpl.db.models import (
    CustomFdr,
    Player,
    PlayerGameweekStats,
    PlayerProjection,
    Team,
)

router = APIRouter()

_POSITION_TYPE: dict[str, int] = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}


def _per90(field: str, stats: list[PlayerGameweekStats], mins: int) -> float:
    if mins == 0:
        return 0.0
    total = sum(float(getattr(s, field, 0) or 0) for s in stats)
    return total / mins * 90.0


@router.get("/form")
def get_form(
    position: str | None = None,
    max_cost: float | None = None,
    min_minutes: int = 90,
    top: int = 20,
) -> list[dict[str, Any]]:
    """Player form rankings."""
    with get_session() as session:
        query = (
            session.query(Player, Team)
            .join(Team, Team.fpl_id == Player.team_id)
            .filter(Player.minutes >= min_minutes)
        )

        if position is not None:
            pos_upper = position.upper()
            if pos_upper not in _POSITION_TYPE:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown position '{position}'. Use GKP, DEF, MID or FWD.",
                )
            query = query.filter(Player.element_type == _POSITION_TYPE[pos_upper])

        if max_cost is not None:
            cost_tenths = int(max_cost * 10)
            query = query.filter(Player.now_cost <= cost_tenths)

        rows = query.all()
        rows.sort(key=lambda r: float(r[0].form), reverse=True)
        rows = rows[:top]

        # Fetch recent stats for all players in a single query, then
        # group in Python — avoids N+1 queries (one per player).
        player_ids = [p.fpl_id for p, _ in rows]
        all_recent: list[PlayerGameweekStats] = (
            session.query(PlayerGameweekStats)
            .filter(PlayerGameweekStats.player_id.in_(player_ids))
            .order_by(
                PlayerGameweekStats.player_id,
                PlayerGameweekStats.gameweek.desc(),
            )
            .all()
        )

        # Group by player_id, keeping at most 5 most-recent rows each
        from collections import defaultdict

        stats_by_player: dict[int, list[PlayerGameweekStats]] = defaultdict(list)
        for s in all_recent:
            bucket = stats_by_player[s.player_id]
            if len(bucket) < 5:
                bucket.append(s)

        records: list[dict[str, Any]] = []
        for rank, (player, team) in enumerate(rows, 1):
            fpl_form = float(player.form)
            recent_stats = stats_by_player[player.fpl_id]
            total_mins = sum(s.minutes for s in recent_stats)
            records.append(
                {
                    "rank": rank,
                    "id": player.fpl_id,
                    "player": player.web_name,
                    "team": team.short_name,
                    "position": position_str(player.element_type),
                    "cost": float(player.now_cost) / 10,
                    "form": fpl_form,
                    "xg_per90": round(
                        _per90("expected_goals", recent_stats, total_mins), 3
                    ),
                    "xa_per90": round(
                        _per90("expected_assists", recent_stats, total_mins), 3
                    ),
                    "pts_per90": round(
                        _per90("total_points", recent_stats, total_mins), 2
                    ),
                }
            )
        return records


@router.get("/search")
def search_players(q: str, top: int = 10) -> list[dict[str, Any]]:
    """Fuzzy player search."""
    with get_session() as session:
        players: list[Player] = session.query(Player).all()

        if not players:
            return []

        choices: dict[str, int] = {}
        for p in players:
            key = f"{p.web_name} ({p.first_name} {p.second_name})"
            choices[key] = p.fpl_id

        matches = process.extract(
            q,
            list(choices.keys()),
            scorer=fuzz.WRatio,
            limit=top,
        )

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}
        player_lookup: dict[int, Player] = {p.fpl_id: p for p in players}

        results: list[dict[str, Any]] = []
        for match_str, score, _ in matches:
            if score < 50:
                continue
            pid = choices[match_str]
            p = player_lookup[pid]
            team = team_lookup.get(p.team_id)
            results.append(
                {
                    "id": p.fpl_id,
                    "player": f"{p.first_name} {p.second_name}",
                    "web_name": p.web_name,
                    "team": team.short_name if team else "?",
                    "position": position_str(p.element_type),
                    "cost": float(p.now_cost) / 10,
                    "status": p.status,
                    "score": score,
                }
            )
        return results


@router.get("/differentials")
def get_differentials(
    max_ownership: float = 10.0,
    position: str | None = None,
    min_minutes: int = 200,
    top: int = 20,
) -> list[dict[str, Any]]:
    """Low-ownership high-value players."""
    pos_filter: int | None = None
    if position is not None:
        pos_upper = position.upper()
        if pos_upper not in _POSITION_TYPE:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown position '{position}'. Use GKP, DEF, MID or FWD.",
            )
        pos_filter = _POSITION_TYPE[pos_upper]

    with get_session() as session:
        diffs = find_differentials(
            session,
            max_ownership=max_ownership,
            min_minutes=min_minutes,
            position=pos_filter,
            top=top,
        )
        return [
            {
                "rank": rank,
                "id": d.player.fpl_id,
                "player": d.player.web_name,
                "team": d.team.short_name,
                "position": position_str(d.player.element_type),
                "cost": float(d.cost) / 10,
                "ownership": d.ownership,
                "form_score": round(d.form_score, 2),
                "upcoming_fdr": round(d.upcoming_fdr, 2),
                "value_score": round(d.value_score, 3),
            }
            for rank, d in enumerate(diffs, 1)
        ]


@router.get("/setpieces")
async def get_setpieces(team: str | None = None) -> list[dict[str, Any]]:
    """Set-piece taker notes."""
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
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch set-piece notes: {exc}"
        ) from exc

    with get_session() as session:
        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}

    team_filter = team.lower() if team else None

    results: list[dict[str, Any]] = []
    for entry in data.get("teams", []):
        tid = entry.get("id")
        team_obj = team_lookup.get(tid)
        team_name = team_obj.name if team_obj else f"Team {tid}"

        if team_filter and team_filter not in team_name.lower():
            continue

        notes = [
            n.get("info_message", "")
            for n in entry.get("notes", [])
            if n.get("info_message")
        ]
        if notes:
            results.append(
                {
                    "team_id": tid,
                    "team": team_name,
                    "notes": notes,
                }
            )

    results.sort(key=lambda r: r["team"])
    return results


@router.get("/{player_id}")
def get_player(player_id: int) -> dict[str, Any]:
    """Full player detail."""
    with get_session() as session:
        player: Player | None = session.get(Player, player_id)
        if player is None:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

        team: Team | None = session.get(Team, player.team_id)
        team_name = team.name if team else "Unknown"
        team_short = team.short_name if team else "?"

        mins = max(player.minutes, 1)

        # Basic info
        result: dict[str, Any] = {
            "id": player.fpl_id,
            "name": f"{player.first_name} {player.second_name}",
            "web_name": player.web_name,
            "team": team_name,
            "team_short": team_short,
            "position": position_str(player.element_type),
            "cost": format_cost(player.now_cost),
            "form": float(player.form),
            "status": player.status,
            "news": player.news,
            "chance_of_playing_next": player.chance_of_playing_next,
            "selected_by_percent": player.selected_by_percent,
        }

        # Season stats
        result["season_stats"] = {
            "total_points": player.total_points,
            "minutes": player.minutes,
            "goals_scored": player.goals_scored,
            "assists": player.assists,
            "clean_sheets": player.clean_sheets,
            "bonus": player.bonus,
            "expected_goals": player.expected_goals,
            "expected_assists": player.expected_assists,
            "expected_goal_involvements": player.expected_goal_involvements,
            "expected_goals_conceded": player.expected_goals_conceded,
            "saves": player.saves,
            "starts": player.starts,
            "goals_conceded": player.goals_conceded,
            "yellow_cards": player.yellow_cards,
            "red_cards": player.red_cards,
            "transfers_in": player.transfers_in,
            "transfers_out": player.transfers_out,
            "points_per_game": player.points_per_game,
        }

        # Defensive stats (DEF/MID)
        if player.element_type in (2, 3):
            result["defensive_stats"] = {
                "defcon": player.defensive_contribution,
                "defcon_per90": round(player.defensive_contribution / mins * 90, 2),
                "cbi": player.clearances_blocks_interceptions,
                "cbi_per90": round(
                    player.clearances_blocks_interceptions / mins * 90, 2
                ),
                "recoveries": player.recoveries,
                "recoveries_per90": round(player.recoveries / mins * 90, 2),
                "tackles": player.tackles,
                "tackles_per90": round(player.tackles / mins * 90, 2),
            }

        # Set-piece orders
        result["setpiece_orders"] = {
            "penalties_order": player.penalties_order,
            "corners_and_indirect_freekicks_order": (
                player.corners_and_indirect_freekicks_order
            ),
            "direct_freekicks_order": player.direct_freekicks_order,
        }

        # Recent GW history (last 10)
        recent_stats: list[PlayerGameweekStats] = (
            session.query(PlayerGameweekStats)
            .filter(PlayerGameweekStats.player_id == player.fpl_id)
            .order_by(PlayerGameweekStats.gameweek.desc())
            .limit(10)
            .all()
        )
        result["recent_history"] = [
            {
                "gameweek": gw.gameweek,
                "minutes": gw.minutes,
                "total_points": gw.total_points,
                "goals_scored": gw.goals_scored,
                "assists": gw.assists,
                "clean_sheets": gw.clean_sheets,
                "bonus": gw.bonus,
                "bps": gw.bps,
                "ict_index": gw.ict_index,
                "expected_goals": gw.expected_goals,
                "expected_assists": gw.expected_assists,
                "goals_conceded": gw.goals_conceded,
                "saves": gw.saves,
                "defensive_contribution": gw.defensive_contribution,
                "was_home": gw.was_home,
            }
            for gw in recent_stats
        ]

        # Projections
        proj: PlayerProjection | None = session.get(PlayerProjection, player.fpl_id)
        if proj is not None:
            result["projections"] = {
                "gw1_pts": proj.gw1_pts,
                "gw2_pts": proj.gw2_pts,
                "gw3_pts": proj.gw3_pts,
                "gw4_pts": proj.gw4_pts,
                "gw5_pts": proj.gw5_pts,
                "next_3gw_pts": proj.next_3gw_pts,
                "next_5gw_pts": proj.next_5gw_pts,
                "start_probability": proj.start_probability,
                "cs_probability": proj.cs_probability,
                "is_blank": proj.is_blank,
                "is_double": proj.is_double,
                "source": proj.source,
            }
        else:
            result["projections"] = None

        # Upcoming fixtures with FDR
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
        team_names: dict[int, str] = {
            t.fpl_id: t.short_name for t in session.query(Team).all()
        }
        result["upcoming_fixtures"] = [
            {
                "gameweek": fdr.gameweek,
                "opponent": team_names.get(fdr.opponent_id, "?"),
                "is_home": fdr.is_home,
                "overall_difficulty": round(fdr.overall_difficulty, 2),
                "attack_difficulty": round(fdr.attack_difficulty, 2),
                "defence_difficulty": round(fdr.defence_difficulty, 2),
            }
            for fdr in upcoming_fdrs
        ]

        return result
