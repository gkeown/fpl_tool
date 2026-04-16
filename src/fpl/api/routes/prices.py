from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from fpl.analysis.price import predict_price_changes
from fpl.auth import require_admin
from fpl.cli.formatters import format_cost, position_str
from fpl.db.engine import get_session

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/risers")
def risers(top: int = 20) -> list[dict[str, Any]]:
    """Players most likely to rise in price."""
    with get_session() as session:
        movements = predict_price_changes(session, direction="rise", top=top)
        return [
            {
                "rank": rank,
                "id": m.player.fpl_id,
                "player": m.player.web_name,
                "team": m.team.short_name,
                "position": position_str(m.player.element_type),
                "cost": format_cost(m.current_price),
                "ownership": m.ownership,
                "transfers_in_event": m.transfers_in_event,
                "transfers_out_event": m.transfers_out_event,
                "net_transfers_event": m.net_transfers_event,
                "pressure": round(m.pressure, 4),
            }
            for rank, m in enumerate(movements, 1)
        ]


@router.get("/fallers")
def fallers(top: int = 20) -> list[dict[str, Any]]:
    """Players most likely to fall in price."""
    with get_session() as session:
        movements = predict_price_changes(session, direction="fall", top=top)
        return [
            {
                "rank": rank,
                "id": m.player.fpl_id,
                "player": m.player.web_name,
                "team": m.team.short_name,
                "position": position_str(m.player.element_type),
                "cost": format_cost(m.current_price),
                "ownership": m.ownership,
                "transfers_in_event": m.transfers_in_event,
                "transfers_out_event": m.transfers_out_event,
                "net_transfers_event": m.net_transfers_event,
                "pressure": round(m.pressure, 4),
            }
            for rank, m in enumerate(movements, 1)
        ]
