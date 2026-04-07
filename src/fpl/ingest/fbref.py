from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def run_fbref_ingest(session: Session) -> None:
    """FBref ingest — no longer viable.

    Opta/Stats Perform terminated FBref's data license in January 2026.
    All advanced stats (SCA, GCA, progressive carries/passes, pressures,
    tackles, interceptions, etc.) were permanently removed from FBref.

    The FPL API now provides defensive stats (tackles, recoveries,
    clearances_blocks_interceptions, defensive_contribution) and
    Understat provides xG/xA/xGChain/xGBuildup — together these
    cover the most useful analytical signals without needing FBref.
    """
    logger.info(
        "FBref advanced stats were removed in Jan 2026 (Opta license terminated). "
        "Using FPL + Understat data instead."
    )
