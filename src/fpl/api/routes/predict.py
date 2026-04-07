from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from fpl.analysis.form import get_next_gameweek
from fpl.db.engine import get_session
from fpl.db.models import Fixture, Team, TeamPrediction

router = APIRouter()


@router.get("/goals")
def get_goals(gameweek: int | None = None) -> list[dict[str, Any]]:
    """Predicted goals for each fixture in a gameweek."""
    with get_session() as session:
        gw = gameweek if gameweek is not None else get_next_gameweek(session)

        predictions: list[TeamPrediction] = (
            session.query(TeamPrediction).filter(TeamPrediction.gameweek == gw).all()
        )

        fixtures: list[Fixture] = (
            session.query(Fixture).filter(Fixture.gameweek == gw).all()
        )

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}

        pred_map: dict[int, dict[int, TeamPrediction]] = {}
        for p in predictions:
            pred_map.setdefault(p.fixture_id, {})[p.team_id] = p

        results: list[dict[str, Any]] = []
        for fixture in fixtures:
            h_team = team_lookup.get(fixture.team_h)
            a_team = team_lookup.get(fixture.team_a)
            h_name = h_team.name if h_team else str(fixture.team_h)
            a_name = a_team.name if a_team else str(fixture.team_a)

            fmap = pred_map.get(fixture.fpl_id, {})
            h_pred = fmap.get(fixture.team_h)
            a_pred = fmap.get(fixture.team_a)

            results.append(
                {
                    "gameweek": gw,
                    "fixture_id": fixture.fpl_id,
                    "kickoff_time": fixture.kickoff_time,
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
                    "source": h_pred.source if h_pred else None,
                }
            )

        return results


@router.get("/cleansheets")
def get_cleansheets(gameweek: int | None = None, top: int = 20) -> list[dict[str, Any]]:
    """Clean sheet probability rankings for a gameweek."""
    with get_session() as session:
        gw = gameweek if gameweek is not None else get_next_gameweek(session)

        predictions: list[TeamPrediction] = (
            session.query(TeamPrediction)
            .filter(TeamPrediction.gameweek == gw)
            .order_by(TeamPrediction.clean_sheet_probability.desc())
            .limit(top)
            .all()
        )

        team_lookup: dict[int, Team] = {t.fpl_id: t for t in session.query(Team).all()}
        fixture_lookup: dict[int, Fixture] = {
            f.fpl_id: f
            for f in session.query(Fixture).filter(Fixture.gameweek == gw).all()
        }

        results: list[dict[str, Any]] = []
        for rank, pred in enumerate(predictions, 1):
            team_obj = team_lookup.get(pred.team_id)
            team_name = team_obj.name if team_obj else str(pred.team_id)

            fixture = fixture_lookup.get(pred.fixture_id)
            is_home = False
            opp_name = "?"
            ha = ""
            if fixture is not None:
                is_home = fixture.team_h == pred.team_id
                opp_id = fixture.team_a if is_home else fixture.team_h
                opp = team_lookup.get(opp_id)
                opp_name = opp.short_name if opp else "?"
                ha = "H" if is_home else "A"

            results.append(
                {
                    "rank": rank,
                    "team_id": pred.team_id,
                    "team": team_name,
                    "opponent": opp_name,
                    "home_away": ha,
                    "fixture": f"vs {opp_name} ({ha})" if opp_name != "?" else "-",
                    "cs_pct": round(pred.clean_sheet_probability * 100, 1),
                    "predicted_goals_against": round(pred.predicted_goals_against, 3),
                    "gameweek": gw,
                }
            )

        return results
