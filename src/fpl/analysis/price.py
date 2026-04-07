from __future__ import annotations

import dataclasses
import logging

from sqlalchemy.orm import Session

from fpl.db.models import Player, Team

logger = logging.getLogger(__name__)

# Approximate total FPL player count used when bootstrapped data is unavailable.
_DEFAULT_TOTAL_PLAYERS = 8_000_000


@dataclasses.dataclass
class PriceMovement:
    player: Player
    team: Team
    current_price: int
    ownership: float
    transfers_in_event: int
    transfers_out_event: int
    net_transfers_event: int
    pressure: float  # normalised indicator


def predict_price_changes(
    session: Session,
    direction: str = "rise",
    top: int = 20,
) -> list[PriceMovement]:
    """Predict price changes based on current gameweek transfer activity.

    Uses per-gameweek transfer data (transfers_in_event / transfers_out_event)
    which reflects the most recent GW's transfer activity — the primary driver
    of FPL price changes.

    Pressure heuristic:
        pressure = net_transfers_event / max(total_selected, 1) * 100

    Args:
        session: Database session.
        direction: "rise" to show likely risers, "fall" to show likely fallers.
        top: Maximum number of results to return.

    Returns:
        List of PriceMovement sorted by pressure (descending for risers,
        ascending for fallers).
    """
    if direction not in ("rise", "fall"):
        raise ValueError(f"direction must be 'rise' or 'fall', got {direction!r}")

    players: list[Player] = session.query(Player).filter(Player.status == "a").all()

    movements: list[PriceMovement] = []

    for player in players:
        try:
            ownership = float(player.selected_by_percent)
        except (ValueError, TypeError):
            ownership = 0.0

        total_selected = ownership / 100.0 * _DEFAULT_TOTAL_PLAYERS
        net_event = player.transfers_in_event - player.transfers_out_event

        # Skip players with negligible transfer activity
        if abs(net_event) < 100:
            continue

        pressure = net_event / max(total_selected, 1) * 100.0

        team: Team | None = session.get(Team, player.team_id)
        if team is None:
            continue

        movements.append(
            PriceMovement(
                player=player,
                team=team,
                current_price=player.now_cost,
                ownership=ownership,
                transfers_in_event=player.transfers_in_event,
                transfers_out_event=player.transfers_out_event,
                net_transfers_event=net_event,
                pressure=pressure,
            )
        )

    if direction == "rise":
        movements.sort(key=lambda m: m.net_transfers_event, reverse=True)
    else:
        movements.sort(key=lambda m: m.net_transfers_event)

    return movements[:top]
