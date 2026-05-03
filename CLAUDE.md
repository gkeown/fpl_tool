# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

FPL Tool — a data-driven Fantasy Premier League assistant. FastAPI backend fetches from multiple sources (FPL API, Understat, ESPN, The Odds API, Fantasy Football Pundit, API-Football), stores in SQLite via SQLAlchemy 2.0, and serves analysis through both a CLI and a React frontend. Multi-tenant with admin and guest roles via JWT auth.

## Commands

### Development

```bash
make install              # Create venv, pip install -e ".[dev]", npm install frontend
make dev                  # Run backend (:8000) + frontend (:8080) with hot reload
make dev-api              # Backend only (uvicorn --reload)
make dev-frontend         # Frontend only (Vite dev server, proxies /api to :8000)
make build                # Build frontend for production
make run                  # Build frontend + serve everything from FastAPI
```

### Docker

```bash
make up                   # Build and start on port 3001
make down                 # Stop (keep data volume)
make clean                # Stop and wipe all data
make logs                 # Tail container logs
```

### Testing

```bash
make test                 # Unit tests only (no network, -m "not integration")
make test-integration     # Integration tests only (hits live APIs)
make test-all             # All tests
pytest tests/test_analysis/test_form.py -v                # Single test file
pytest tests/test_analysis/test_form.py::test_name -v     # Single test
```

All tests use `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed.

### Code Quality

```bash
make lint                 # black --check + ruff check + mypy strict
make format               # black + ruff --fix
```

### Frontend Testing

```bash
cd frontend && npm run test        # Vitest (run once)
cd frontend && npm run test:watch  # Vitest (watch mode)
cd frontend && npm run lint        # ESLint
```

## Architecture

### Backend (`src/fpl/`)

- **`config.py`** — Pydantic `BaseSettings` with `FPL_` env prefix, loads from `.env`.
- **`auth.py`** — JWT auth (HS256, 30-day expiry). `create_token()`, `decode_token()`, `get_current_user()`, `require_admin()` FastAPI dependencies.
- **`scheduler.py`** — APScheduler with three jobs: FPL refresh (60s), score cache refresh (30s), live GW cache refresh (60s). Runs only during UK match windows (Sat/Sun 12:00–23:00, Mon–Fri 19:00–23:00).
- **`types.py`** — Enums: `Position`, `PlayerStatus`, `IngestSource`.
- **`db/engine.py`** — Synchronous SQLAlchemy 2.0 engine + session factory. WAL mode + busy timeout for concurrent access. `init_db()` creates all tables.
- **`db/models.py`** — SQLAlchemy `DeclarativeBase` models (23 tables). Schema created on first run.
- **`db/queries.py`** — Query functions that accept a `Session`.
- **`ingest/`** — One module per data source. All use httpx for HTTP. Fetchers are imported individually, not via a registry.
- **`analysis/`** — Pure computation modules: form scoring, FDR, goal predictions, captaincy, transfers, differentials, price changes. Each takes DB data and returns results.
- **`cli/`** — Click-based CLI commands organized by domain (`data_cmds.py`, `player_cmds.py`, etc.). Entry point: `fpl.cli.app:app`.
- **`api/app.py`** — FastAPI app with lifespan (calls `init_db()` + auto-setup on startup). CORS allows all origins. Serves built frontend from `frontend/dist/` as a catch-all SPA route.
- **`api/routes/`** — REST endpoints under `/api/`. Thirteen routers: auth, players, team, fixtures, leagues, predict, transfers, captain, prices, data, scores, stats, live.

### Frontend (`frontend/`)

- React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui.
- TanStack Query 5 for data fetching and caching.
- `vite.config.ts` proxies `/api` to `localhost:8000` during dev. Dev server runs on port 8080.
- Pages in `src/pages/`, reusable components in `src/components/`, path alias `@/` maps to `src/`.
- Auth guards: `RequireAuth` (any logged-in user), `RequireAdmin` (admin role only).
- 19 pages: Login, GuestSetup, Dashboard, MyTeam, Players, PlayerDetail, Fixtures, Transfers, Prices, Captain, Leagues, OpponentTeam, Scores, Tables, Stats, MatchDetail, LiveGameweek, Settings, NotFound.

### Data Flow

1. **Ingest** fetches raw data from FPL API, Understat, ESPN, Odds API, Fantasy Football Pundit, API-Football
2. **Player ID mapper** (`ingest/mapper.py`) resolves identities across sources using fuzzy name matching (rapidfuzz token_sort_ratio ≥ 85) + manual overrides
3. **DB** stores via idempotent upserts (SQLAlchemy + SQLite WAL mode)
4. **Analysis** computes derived metrics (form, FDR, predictions, recommendations)
5. **Scheduler** auto-refreshes data during match windows; live endpoints bypass cache for real-time data
6. **CLI/API** presents results via Rich tables or JSON responses

### Key Design Decisions

- **Multi-tenant auth** — JWT tokens, admin vs. guest roles, per-user fpl_team_id and league subscriptions.
- **Synchronous SQLAlchemy** — despite async fetchers, DB access is synchronous via `Session`. WAL mode enables concurrent reads during auto-refresh.
- **SQLite only** — no external DB. Schema auto-created, migrations via Alembic.
- **All env vars prefixed `FPL_`** — e.g., `FPL_ID`, `FPL_ODDS_API_KEY`, `FPL_DB_PATH`, `FPL_ADMIN_PASSWORD`, `FPL_GUEST_CODE`, `FPL_JWT_SECRET`.
- **Docker-first deployment** — multi-stage build (Node → Python), port 3001, SQLite volume for persistence.

## Testing Patterns

- Unit tests get an isolated in-memory SQLite DB via `conftest.py` fixtures.
- External HTTP is mocked with `pytest-httpx`. No network calls in unit tests.
- Integration tests are marked `@pytest.mark.integration` and live in `tests/test_integration/`.
- Test structure mirrors source: `test_ingest/`, `test_analysis/`, `test_integration/`.

## Environment

Required: `FPL_ID` (your FPL team ID).
Auth: `FPL_ADMIN_PASSWORD`, `FPL_GUEST_CODE`, `FPL_JWT_SECRET` (JWT signing key).
Optional: `FPL_ODDS_API_KEY` (betting odds), `FPL_API_FOOTBALL_KEY` (historical stats), `FPL_LEAGUE_IDS` (comma-separated, auto-subscribed on startup).
All config in `.env` — see `src/fpl/config.py` for full list with defaults.

## Development workflow and coding standards

This project inherits the cross-project canonical procedure from `~/CLAUDE.md`:

- **Workflow**: `~/wiki/docs/process/development-workflow.md` — Plan → Code → Review → Explain. Iteration artifacts (`plan.md`, `tdd-trace.md`, `code-review-N.md`, `summary.md`, `code-review-walkthrough.md`) go in `fantasy_football/docs/iterations/<story>/`. Cross-project log entries and ADRs go in `~/wiki/docs/`.
- **Standards**: `~/wiki/docs/process/review-coding-standards.md` — 17 enforceable sections (A–Q). Any MUST violation → CHANGES REQUESTED.
- **Git/commits**: covered by Section L of the standards (no AI attribution, no ticket IDs, imperative mood, ≤72-char subject, no `--no-verify`).

Per-project CLAUDE.md cites these — does not duplicate. If something here appears to conflict with the canonical docs, the canonical docs win; flag the conflict so this file can be fixed.
