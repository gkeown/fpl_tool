# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

FPL Tool — a data-driven Fantasy Premier League assistant. Typer CLI + FastAPI backend fetch from multiple sources (FPL API, Understat, The Odds API, Fantasy Football Pundit, RSS), store in SQLite via SQLAlchemy 2.0, and serve analysis through both CLI commands and a React frontend. Designed for single-user personal use.

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
- **`db/engine.py`** — Synchronous SQLAlchemy 2.0 engine + session factory. `init_db()` creates all tables via `Base.metadata.create_all`. No async DB — uses regular `Session`.
- **`db/models.py`** — SQLAlchemy `DeclarativeBase` models (18 tables). Schema created on first run.
- **`db/queries.py`** — Query functions that accept a `Session`.
- **`ingest/`** — One module per data source. All use httpx for HTTP. Fetchers are imported individually, not via a registry.
- **`analysis/`** — Pure computation modules: form scoring, FDR, goal predictions, captaincy, transfers, differentials, price changes. Each takes DB data and returns results.
- **`cli/`** — Typer commands organized by domain (`data_cmds.py`, `player_cmds.py`, etc.). Entry point: `fpl.cli.app:app`.
- **`api/app.py`** — FastAPI app with lifespan (calls `init_db()` on startup). CORS allows all origins. Serves built frontend from `frontend/dist/` as a catch-all SPA route.
- **`api/routes/`** — REST endpoints under `/api/`. Eight routers: players, team, fixtures, predict, transfers, captain, prices, data.

### Frontend (`frontend/`)

- React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui + MUI (Data Grid).
- TanStack Query 5 for data fetching.
- `vite.config.ts` proxies `/api` to `localhost:8000` during dev. Dev server runs on port 8080.
- Pages in `src/pages/`, reusable components in `src/components/`, path alias `@/` maps to `src/`.

### Data Flow

1. **Ingest** fetches raw data from external APIs (FPL, Understat, Odds API, FFP, RSS)
2. **Player ID mapper** (`ingest/mapper.py`) resolves identities across sources using fuzzy name matching (rapidfuzz)
3. **DB** stores via idempotent upserts (SQLAlchemy)
4. **Analysis** computes derived metrics (form, FDR, predictions, recommendations)
5. **CLI/API** presents results via Rich tables or JSON responses

### Key Design Decisions

- **Synchronous SQLAlchemy** — despite async fetchers, DB access is synchronous via `Session`.
- **SQLite only** — no external DB. Schema auto-created, migrations via Alembic.
- **All env vars prefixed `FPL_`** — e.g., `FPL_ID`, `FPL_ODDS_API_KEY`, `FPL_DB_PATH`.

## Testing Patterns

- Unit tests get an isolated in-memory SQLite DB via `conftest.py` fixtures.
- External HTTP is mocked with `pytest-httpx`. No network calls in unit tests.
- Integration tests are marked `@pytest.mark.integration` and live in `tests/test_integration/`.
- Test structure mirrors source: `test_ingest/`, `test_analysis/`, `test_integration/`.

## Environment

Required: `FPL_ID` (your FPL team ID).
Optional: `FPL_ODDS_API_KEY` (betting odds), `FPL_API_FOOTBALL_KEY`.
All config in `.env` — see `src/fpl/config.py` for full list with defaults.

## Development Workflow

All major changes follow the **Plan → Code → Review** cycle defined in `development-workflow.md`. This is mandatory, not optional.

1. **Plan** — A full spec is produced and approved by the user before any code is written. The spec defines scope, files to change, acceptance criteria, and test plan.
2. **Code** — Implementation follows the approved plan. Deviations are flagged before proceeding. Tests are written alongside code, not after. Focus on what real integration tests can be added to test the change or if current integration tests already cover the functionality.
3. **Review** — All changes are evaluated against the plan's acceptance criteria, `CLAUDE.md` standards, and best practices. The review produces a structured verdict: **APPROVED** or **CHANGES REQUESTED**.
4. **Loop** — If changes are requested, code is revised and re-reviewed until approved. Only then are changes committed.

Trivial changes (typos, config values, single-line fixes) are exempt. The user can override any phase explicitly.

**Iteration tracking:** For each change that goes through the Plan → Code → Review loop, create a folder under `docs/iterations/<story-or-change-name>/` containing markdown documents for each phase: `plan.md`, `code-review-N.md` (one per review cycle). These documents capture the output of each agent, iterations, and improvements between cycles.

## Git and Commits

- **Never include "Co-Authored-By: Claude", "Generated by Claude", or any AI attribution in commit messages.** Commits should read as if written by a human engineer.
- **Never reference story numbers, ticket IDs, or issue numbers in commit messages.** Describe what the change does, not which ticket it belongs to. Traceability belongs in the branch name or PR, not the commit message.
- Write commit messages in imperative mood ("Add feature", not "Added feature").
- Include bullet points for each discrete change in the commit body.
- Keep the subject line under 72 characters. Put detail in the body.
