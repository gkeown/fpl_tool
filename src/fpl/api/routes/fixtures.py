from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from fpl.analysis.form import get_current_gameweek, get_next_gameweek
from fpl.db.engine import get_session
from fpl.db.models import BettingOdds, CustomFdr, Fixture, Team

router = APIRouter()


@router.get("/")
def get_fixtures(gameweek: int | None = None) -> list[dict[str, Any]]:
    """Fixtures for a given gameweek (defaults to current)."""
    with get_session() as session:
        gw = gameweek if gameweek is not None else get_current_gameweek(session)

        fixtures: list[Fixture] = (
            session.query(Fixture)
            .filter(Fixture.gameweek == gw)
            .order_by(Fixture.kickoff_time)
            .all()
        )

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}

        return [
            {
                "id": f.fpl_id,
                "gameweek": f.gameweek,
                "kickoff_time": f.kickoff_time,
                "home_team_id": f.team_h,
                "home_team": (
                    team_lookup[f.team_h].name
                    if f.team_h in team_lookup
                    else str(f.team_h)
                ),
                "home_team_short": (
                    team_lookup[f.team_h].short_name
                    if f.team_h in team_lookup
                    else str(f.team_h)
                ),
                "away_team_id": f.team_a,
                "away_team": (
                    team_lookup[f.team_a].name
                    if f.team_a in team_lookup
                    else str(f.team_a)
                ),
                "away_team_short": (
                    team_lookup[f.team_a].short_name
                    if f.team_a in team_lookup
                    else str(f.team_a)
                ),
                "home_score": f.team_h_score,
                "away_score": f.team_a_score,
                "home_difficulty": f.team_h_difficulty,
                "away_difficulty": f.team_a_difficulty,
                "finished": f.finished,
            }
            for f in fixtures
        ]


@router.get("/difficulty")
def get_difficulty(weeks: int = 6) -> dict[str, Any]:
    """FDR heatmap data: {teams, gameweeks, ratings: {team_id: {gw: rating}}}"""
    with get_session() as session:
        current_gw = get_current_gameweek(session)
        max_gw = current_gw + weeks

        fdrs: list[CustomFdr] = (
            session.query(CustomFdr)
            .filter(
                CustomFdr.gameweek > current_gw,
                CustomFdr.gameweek <= max_gw,
            )
            .order_by(CustomFdr.team_id, CustomFdr.gameweek)
            .all()
        )

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}
        gw_range = list(range(current_gw + 1, max_gw + 1))

        # Build team list (only teams with FDR data)
        team_ids_with_data: set[int] = {f.team_id for f in fdrs}
        teams_out: list[dict[str, Any]] = []
        for tid in sorted(team_ids_with_data):
            t = team_lookup.get(tid)
            if t:
                teams_out.append(
                    {"id": tid, "name": t.name, "short_name": t.short_name}
                )

        # Build ratings: {team_id: {gw: {rating, opponent, is_home}}}
        ratings: dict[int, dict[int, dict[str, Any]]] = {}
        for fdr in fdrs:
            opp = team_lookup.get(fdr.opponent_id)
            ratings.setdefault(fdr.team_id, {})[fdr.gameweek] = {
                "overall": round(fdr.overall_difficulty, 2),
                "attack": round(fdr.attack_difficulty, 2),
                "defence": round(fdr.defence_difficulty, 2),
                "opponent": opp.short_name if opp else "?",
                "is_home": fdr.is_home,
            }

        return {
            "teams": teams_out,
            "gameweeks": gw_range,
            "ratings": {str(tid): gw_data for tid, gw_data in ratings.items()},
        }


@router.get("/odds")
def get_odds(gameweek: int | None = None) -> list[dict[str, Any]]:
    """Betting odds for a gameweek (defaults to next)."""
    with get_session() as session:
        gw = gameweek if gameweek is not None else get_next_gameweek(session)

        fixtures: list[Fixture] = (
            session.query(Fixture)
            .filter(Fixture.gameweek == gw)
            .order_by(Fixture.kickoff_time)
            .all()
        )

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}

        results: list[dict[str, Any]] = []
        for fix in fixtures:
            h = team_lookup.get(fix.team_h)
            a = team_lookup.get(fix.team_a)

            h2h: BettingOdds | None = (
                session.query(BettingOdds)
                .filter(
                    BettingOdds.fixture_id == fix.fpl_id,
                    BettingOdds.market == "h2h",
                    BettingOdds.bookmaker == "consensus",
                )
                .first()
            )
            totals: BettingOdds | None = (
                session.query(BettingOdds)
                .filter(
                    BettingOdds.fixture_id == fix.fpl_id,
                    BettingOdds.market == "totals",
                    BettingOdds.bookmaker == "consensus",
                )
                .first()
            )

            results.append(
                {
                    "fixture_id": fix.fpl_id,
                    "gameweek": gw,
                    "kickoff_time": fix.kickoff_time,
                    "home_team": h.name if h else str(fix.team_h),
                    "away_team": a.name if a else str(fix.team_a),
                    "home_win": h2h.home_odds if h2h else None,
                    "draw": h2h.draw_odds if h2h else None,
                    "away_win": h2h.away_odds if h2h else None,
                    "over_2_5": totals.over_2_5 if totals else None,
                    "under_2_5": totals.under_2_5 if totals else None,
                    "btts_yes": totals.btts_yes if totals else None,
                    "btts_no": totals.btts_no if totals else None,
                }
            )

        return results
