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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


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
    players,
    predict,
    prices,
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
