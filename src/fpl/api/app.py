from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fpl.db.engine import init_db

_FRONTEND_DIR = Path(
    os.environ.get(
        "FPL_FRONTEND_DIR",
        str(Path(__file__).resolve().parents[3] / "frontend" / "dist"),
    )
)


async def _auto_setup() -> None:
    """Load team + leagues from env config if not already in DB."""
    import logging

    from fpl.config import get_settings
    from fpl.db.engine import get_session
    from fpl.db.models import League, MyAccount

    logger = logging.getLogger(__name__)
    settings = get_settings()

    # Auto-load team if FPL_ID is set and no team is stored
    if settings.id:
        needs_load = False
        with get_session() as session:
            account: MyAccount | None = session.get(MyAccount, 1)
            if account is None or account.fpl_team_id != settings.id:
                needs_load = True

        if needs_load:
            # Refresh core data first so player table is populated
            logger.info("Running initial data refresh...")
            try:
                from fpl.api.routes.data import refresh

                await refresh(source="fpl", force=True)
            except Exception:
                logger.exception("Initial data refresh failed")

            logger.info("Auto-loading team %d from FPL_ID", settings.id)
            try:
                from fpl.api.routes.team import login

                await login(settings.id)
            except Exception:
                logger.exception("Auto-load team failed")

    # Auto-subscribe leagues from FPL_LEAGUE_IDS
    if settings.league_ids.strip():
        league_id_list = [
            int(x.strip())
            for x in settings.league_ids.split(",")
            if x.strip().isdigit()
        ]
        for lid in league_id_list:
            with get_session() as session:
                existing: League | None = session.get(League, lid)
                already_exists = existing is not None
            if not already_exists:
                logger.info("Auto-subscribing to league %d", lid)
                try:
                    from fpl.api.routes.leagues import add_league

                    await add_league(lid)
                except Exception:
                    logger.exception(
                        "Auto-subscribe league %d failed", lid
                    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    await _auto_setup()
    from fpl.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="FPL Tool API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from fpl.api.routes import (  # noqa: E402
    captain,
    data,
    fixtures,
    leagues,
    players,
    predict,
    prices,
    scores,
    team,
    transfers,
)

app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(team.router, prefix="/api/me", tags=["team"])
app.include_router(fixtures.router, prefix="/api/fixtures", tags=["fixtures"])
app.include_router(predict.router, prefix="/api/predict", tags=["predictions"])
app.include_router(transfers.router, prefix="/api/transfers", tags=["transfers"])
app.include_router(captain.router, prefix="/api/captain", tags=["captain"])
app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(leagues.router, prefix="/api/leagues", tags=["leagues"])
app.include_router(scores.router, prefix="/api/scores", tags=["scores"])

# Serve frontend static files if the build exists
if _FRONTEND_DIR.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIR / "assets"),
        name="assets",
    )

    @app.get("/{path:path}")
    async def serve_frontend(path: str) -> FileResponse:
        """Serve the React SPA for any non-API route."""
        file = _FRONTEND_DIR / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(_FRONTEND_DIR / "index.html")
