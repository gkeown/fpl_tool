from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from fpl.analysis.form import get_current_gameweek
from fpl.analysis.team import analyse_team
from fpl.cli.formatters import position_str
from fpl.config import get_settings
from fpl.db.engine import get_session
from fpl.db.models import (
    Fixture,
    MyAccount,
    MyTeamPlayer,
    Player,
    PlayerProjection,
    Team,
)

router = APIRouter()


def _compute_provisional_bonus(
    players_by_bps: list[tuple[int, int]],
) -> dict[int, int]:
    """Compute provisional bonus points from BPS rankings.

    Top 3 BPS get 3/2/1 bonus, handling ties per FPL rules:
    - Tie for 1st (2 players): both get 3, next player gets 1
    - Tie for 2nd (2 players): both get 2, no 3rd place bonus
    - Tie for 1st (3+ players): all get 3

    Args:
        players_by_bps: list of (player_id, bps) tuples

    Returns:
        {player_id: bonus_points} for players earning 1, 2, or 3
    """
    sorted_players = sorted(
        [(pid, bps) for pid, bps in players_by_bps if bps > 0],
        key=lambda x: -x[1],
    )
    if not sorted_players:
        return {}

    result: dict[int, int] = {}
    rank_points = [3, 2, 1]
    i = 0
    rank_idx = 0
    n = len(sorted_players)
    while i < n and rank_idx < 3:
        cur_bps = sorted_players[i][1]
        # Find all players tied at this BPS
        tied: list[int] = [sorted_players[i][0]]
        j = i + 1
        while j < n and sorted_players[j][1] == cur_bps:
            tied.append(sorted_players[j][0])
            j += 1
        points = rank_points[rank_idx]
        for pid in tied:
            result[pid] = points
        rank_idx += len(tied)
        i = j
    return result


async def _fetch_live_gw(gw: int) -> dict[int, dict[str, Any]]:
    """Fetch live GW data from FPL API. Returns {player_id: stats}.

    Injects a `provisional_bonus` field into each player's stats
    computed from the BPS ranking within their fixture. Used when
    the match is in progress and the confirmed `bonus` field is 0.
    """
    settings = get_settings()
    headers = {"User-Agent": settings.user_agent}
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            url = f"{settings.fpl_base_url}/event/{gw}/live/"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            elements = data.get("elements", [])

            # Group players by fixture (via explain[0].fixture)
            # DGW players contribute to the first fixture only; BPS
            # rankings for DGW are fuzzy so provisional bonus there
            # is approximate.
            by_fixture: dict[int, list[tuple[int, int]]] = {}
            player_fixture: dict[int, int] = {}
            for el in elements:
                pid = el["id"]
                explain = el.get("explain", [])
                if not explain:
                    continue
                fixture_id = explain[0].get("fixture")
                if fixture_id is None:
                    continue
                bps = el.get("stats", {}).get("bps", 0) or 0
                by_fixture.setdefault(fixture_id, []).append(
                    (pid, bps)
                )
                player_fixture[pid] = fixture_id

            # Compute provisional bonus per fixture
            provisional: dict[int, int] = {}
            for _fid, players in by_fixture.items():
                provisional.update(
                    _compute_provisional_bonus(players)
                )

            return {
                el["id"]: {
                    **el.get("stats", {}),
                    "provisional_bonus": provisional.get(
                        el["id"], 0
                    ),
                }
                for el in elements
            }
    except Exception:
        return {}


@router.get("/team")
async def get_team() -> dict[str, Any]:
    """Current squad with form + projected points + live bonus."""
    with get_session() as session:
        rows = (
            session.query(MyTeamPlayer, Player, Team)
            .join(Player, Player.fpl_id == MyTeamPlayer.player_id)
            .join(Team, Team.fpl_id == Player.team_id)
            .order_by(MyTeamPlayer.position)
            .all()
        )

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="No team data found. Load a team via POST /api/me/login.",
            )

        current_gw = get_current_gameweek(session)
        account: MyAccount | None = session.get(MyAccount, 1)

        # Build opponent + live fixture lookup from current GW fixtures
        all_teams = {t.fpl_id: t.short_name for t in session.query(Team).all()}
        gw_fixtures: list[Fixture] = (
            session.query(Fixture)
            .filter(Fixture.gameweek == current_gw)
            .all()
        )

        # Next 5 fixtures per team (GW+1 onwards)
        future_fixtures: list[Fixture] = (
            session.query(Fixture)
            .filter(Fixture.gameweek > current_gw)
            .order_by(Fixture.gameweek, Fixture.kickoff_time)
            .all()
        )
        # team_id -> list of fixture dicts (opponent, is_home, fdr, gw)
        next_fixtures_by_team: dict[int, list[dict[str, Any]]] = {}
        for fix in future_fixtures:
            home_entry = {
                "gw": fix.gameweek,
                "opponent": all_teams.get(fix.team_a, "?"),
                "is_home": True,
                "fdr": fix.team_h_difficulty,
            }
            away_entry = {
                "gw": fix.gameweek,
                "opponent": all_teams.get(fix.team_h, "?"),
                "is_home": False,
                "fdr": fix.team_a_difficulty,
            }
            next_fixtures_by_team.setdefault(fix.team_h, []).append(
                home_entry
            )
            next_fixtures_by_team.setdefault(fix.team_a, []).append(
                away_entry
            )
        # Limit to 5 per team
        for tid in next_fixtures_by_team:
            next_fixtures_by_team[tid] = next_fixtures_by_team[tid][:5]
        now_iso = datetime.now(UTC).isoformat()
        # team_id -> (opponent_short_name, is_home)
        opponent_lookup: dict[int, tuple[str, bool]] = {}
        # team_id -> True if their fixture is currently in progress
        live_team_ids: set[int] = set()
        for fix in gw_fixtures:
            opponent_lookup[fix.team_h] = (
                all_teams.get(fix.team_a, "?"),
                True,
            )
            opponent_lookup[fix.team_a] = (
                all_teams.get(fix.team_h, "?"),
                False,
            )
            # Fixture is live if kickoff passed and not finished
            if (
                fix.kickoff_time
                and fix.kickoff_time <= now_iso
                and not fix.finished
                and not fix.finished_provisional
            ):
                live_team_ids.add(fix.team_h)
                live_team_ids.add(fix.team_a)

        # Snapshot DB data while session is open
        db_players: list[dict[str, Any]] = []
        for mtp, player, tm in rows:
            opp = opponent_lookup.get(player.team_id)
            fixture_live = player.team_id in live_team_ids
            db_players.append(
                {
                    "fpl_id": player.fpl_id,
                    "web_name": player.web_name,
                    "team_short": tm.short_name,
                    "team_id": player.team_id,
                    "fixture_live": fixture_live,
                    "element_type": player.element_type,
                    "now_cost": player.now_cost,
                    "selling_price": mtp.selling_price,
                    "form": player.form,
                    "event_points": player.event_points or 0,
                    "defcon": player.defensive_contribution,
                    "opponent": (
                        f"{opp[0]} (H)" if opp and opp[1]
                        else f"{opp[0]} (A)" if opp
                        else "-"
                    ),
                    "next_fixtures": next_fixtures_by_team.get(
                        player.team_id, []
                    ),
                    "status": player.status,
                    "chance_of_playing": player.chance_of_playing_next,
                    "news": player.news,
                    "position": mtp.position,
                    "is_captain": mtp.is_captain,
                    "is_vice_captain": mtp.is_vice_captain,
                    "multiplier": mtp.multiplier,
                }
            )

        import json

        chips: list[dict[str, Any]] = []
        if account and account.chips_json:
            with contextlib.suppress(json.JSONDecodeError):
                chips = json.loads(account.chips_json)
        active_chip = account.active_chip if account else None
        gw_points_official = account.gameweek_points if account else 0
        bank = float(account.bank) / 10 if account else 0.0
        free_transfers = account.free_transfers if account else 1
        overall_points = account.overall_points if account else 0
        overall_rank = account.overall_rank if account else 0

    # Fetch live GW data (outside session — async call)
    live_data = await _fetch_live_gw(current_gw) if current_gw else {}

    players_out: list[dict[str, Any]] = []
    for p in db_players:
        pid = p["fpl_id"]
        # Use live total_points and bonus if available
        live_stats = live_data.get(pid, {})
        live_pts = live_stats.get("total_points")
        confirmed_bonus = live_stats.get("bonus", 0) or 0
        provisional_bonus = live_stats.get("provisional_bonus", 0) or 0
        live_bonus = (
            confirmed_bonus if confirmed_bonus > 0 else provisional_bonus
        )
        live_defcon = live_stats.get("defensive_contribution", 0)
        live_minutes = live_stats.get("minutes", 0)
        live_yellow = live_stats.get("yellow_cards", 0)
        live_red = live_stats.get("red_cards", 0)
        live_xgi = live_stats.get("expected_goal_involvements", "0.00")
        try:
            xgi_val = round(float(live_xgi), 2)
        except (ValueError, TypeError):
            xgi_val = 0.0
        event_pts = live_pts if live_pts is not None else p["event_points"]
        is_playing = p["fixture_live"] and live_minutes > 0

        players_out.append(
            {
                "id": pid,
                "web_name": p["web_name"],
                "team": p["team_short"],
                "position": position_str(p["element_type"]),
                "cost": float(p["now_cost"]) / 10,
                "selling_price": float(p["selling_price"]) / 10,
                "opponent": p["opponent"],
                "next_fixtures": p["next_fixtures"],
                "event_points": event_pts,
                "gw_points": event_pts * p["multiplier"],
                "gw_bonus": live_bonus,
                "defcon": live_defcon,
                "yellow_cards": live_yellow,
                "red_cards": live_red,
                "xgi": xgi_val,
                "minutes": live_minutes,
                "is_playing": is_playing,
                "fixture_live": p["fixture_live"],
                "status": p["status"],
                "chance_of_playing": p["chance_of_playing"],
                "news": p["news"],
                "is_starter": p["position"] <= 11,
                "squad_position": p["position"],
                "is_captain": p["is_captain"],
                "is_vice_captain": p["is_vice_captain"],
                "multiplier": p["multiplier"],
            }
        )

    return {
        "gameweek": current_gw,
        "gameweek_points": gw_points_official,
        "bank": bank,
        "free_transfers": free_transfers,
        "overall_points": overall_points,
        "overall_rank": overall_rank,
        "active_chip": active_chip,
        "chips": chips,
        "players": players_out,
    }


@router.get("/analyse")
def analyse(weeks: int = 5) -> dict[str, Any]:
    """Full team analysis."""
    with get_session() as session:
        analysis = analyse_team(session, weeks_ahead=weeks)

        if analysis is None:
            raise HTTPException(
                status_code=404,
                detail="No team data found. Load a team via POST /api/me/login.",
            )

        squad_ids = [pa.player.fpl_id for pa in analysis.players]
        proj_rows: list[PlayerProjection] = (
            session.query(PlayerProjection)
            .filter(PlayerProjection.player_id.in_(squad_ids))
            .all()
        )
        proj_by_id: dict[int, PlayerProjection] = {p.player_id: p for p in proj_rows}

        def _ep_next(player: Player) -> float:
            if player.ep_next:
                with contextlib.suppress(ValueError):
                    return float(player.ep_next)
            return 0.0

        players_out: list[dict[str, Any]] = []
        for pa in analysis.players:
            proj = proj_by_id.get(pa.player.fpl_id)
            players_out.append(
                {
                    "id": pa.player.fpl_id,
                    "web_name": pa.player.web_name,
                    "team": pa.team.short_name,
                    "position": position_str(pa.player.element_type),
                    "cost": float(pa.player.now_cost) / 10,
                    "form_score": round(pa.form_score, 2),
                    "upcoming_difficulty": round(pa.upcoming_difficulty, 2),
                    "minutes_probability": round(pa.minutes_probability, 3),
                    "expected_value": round(pa.expected_value, 3),
                    "is_starter": pa.is_starter,
                    "is_captain": pa.is_captain,
                    "is_vice_captain": pa.is_vice_captain,
                    "status": pa.player.status,
                    "news": pa.player.news,
                    "xpts_gw1": round(proj.gw1_pts if proj else _ep_next(pa.player), 2),
                    "xpts_3gw": round(proj.next_3gw_pts if proj else 0.0, 2),
                    "xpts_5gw": round(proj.next_5gw_pts if proj else 0.0, 2),
                }
            )

        starters = [pa for pa in analysis.players if pa.is_starter]
        total_gw1 = sum(
            (
                proj_by_id[pa.player.fpl_id].gw1_pts
                if pa.player.fpl_id in proj_by_id
                else _ep_next(pa.player)
            )
            for pa in starters
        )
        total_3gw = sum(
            proj_by_id[pa.player.fpl_id].next_3gw_pts
            for pa in starters
            if pa.player.fpl_id in proj_by_id
        )
        total_5gw = sum(
            proj_by_id[pa.player.fpl_id].next_5gw_pts
            for pa in starters
            if pa.player.fpl_id in proj_by_id
        )

        return {
            "squad_strength": round(analysis.total_strength, 3),
            "bank": float(analysis.bank) / 10,
            "free_transfers": analysis.free_transfers,
            "weak_spots": analysis.weak_spots,
            "projected_xi_gw1": round(total_gw1, 2),
            "projected_xi_3gw": round(total_3gw, 2),
            "projected_xi_5gw": round(total_5gw, 2),
            "players": players_out,
        }


@router.post("/login")
async def login(team_id: int) -> dict[str, str]:
    """Load FPL team by ID."""
    settings = get_settings()

    from fpl.ingest.fpl_api import fetch_entry, fetch_entry_picks, upsert_my_team

    headers = {"User-Agent": settings.user_agent}
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            entry = await fetch_entry(client, settings, team_id)
            current_gw = entry.get("current_event", 1)
            picks = await fetch_entry_picks(client, settings, team_id, current_gw)

            with get_session() as session:
                count = upsert_my_team(session, team_id, entry, picks)

        name = (
            f"{entry.get('player_first_name', '')} "
            f"{entry.get('player_last_name', '')}"
        ).strip()
        return {
            "status": "ok",
            "manager": name,
            "gameweek": str(current_gw),
            "players_saved": str(count),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch team {team_id}: {exc}"
        ) from exc
