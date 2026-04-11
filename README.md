# FPL Tool

A data-driven Fantasy Premier League dashboard for personal use. Aggregates data from multiple free sources, tracks your team and mini league opponents in real-time, and provides live scores, league tables, and player statistics across European football.

## Features

### FPL Dashboard
- **Dashboard** — GW points (live XI total), captain picks, match predictions, news
- **My Team** — Full squad with live GW points, provisional bonus, DEFCON, form, xPts, chip usage
- **Mini Leagues** — Subscribe to leagues, view standings, drill into opponent teams with transfers and chip history
- **Players** — Form rankings, player search, detailed player cards with charts and fixture difficulty
- **Fixtures** — FDR heatmap, goal predictions, betting odds
- **Transfers** — AI-recommended transfers based on form, FDR, and value
- **Prices** — Price risers/fallers with transfer pressure indicators
- **Captain** — Captain recommendations with scoring breakdowns

### Live Football
- **Live Scores** — Current matchweek fixtures for PL, Serie A, La Liga, Bundesliga, Ligue 1 with goal scorers, red cards, and live minute tracking
- **League Tables** — Standings for 6 leagues (PL, Championship, Serie A, La Liga, Bundesliga, Ligue 1) with qualification zone highlighting
- **Player Stats** — Search any player across European leagues for current season stats (goals, assists, shots, tackles, cards) with xG/xA from Understat

### Automation
- **Auto-refresh** — Server-side scheduler refreshes FPL data every 5 min and scores every 60s during match windows (Sat/Sun/Mon)
- **Auto-setup** — Team and leagues load automatically from `.env` on first startup

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   React Frontend                         │
│  Dashboard · My Team · Leagues · Scores · Tables · Stats │
│  Players · Fixtures · Transfers · Prices · Settings      │
├─────────────────────────────────────────────────────────┤
│                   FastAPI Backend                         │
│  /api/me    /api/leagues   /api/scores   /api/stats      │
│  /api/players  /api/fixtures  /api/transfers  /api/data  │
│  /api/captain  /api/predict   /api/prices                │
├─────────────────────────────────────────────────────────┤
│  Ingest Layer          │  Analysis Layer                  │
│  FPL API · Understat   │  Form · FDR · Predictions       │
│  Odds · Projections    │  Captaincy · Transfers           │
│  Injuries · Leagues    │  Team Analysis · Differentials   │
├─────────────────────────────────────────────────────────┤
│  SQLite (SQLAlchemy 2.0)  │  APScheduler (auto-refresh)  │
└─────────────────────────────────────────────────────────┘

External Data Sources:
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ FPL API  │ │Understat │ │ ESPN API │ │ Odds API │ │FF Pundit │
│(players, │ │(xG, xA,  │ │(scores,  │ │(betting  │ │(projected│
│ fixtures,│ │ npxG,    │ │ tables,  │ │ odds)    │ │ points)  │
│ live GW) │ │ buildup) │ │ stats)   │ │          │ │          │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### Data Flow

1. **Ingest** fetches raw data from FPL API, Understat, Odds API, Fantasy Football Pundit
2. **Player ID mapper** resolves identities across sources using fuzzy name matching (rapidfuzz)
3. **DB** stores via idempotent upserts (SQLAlchemy + SQLite)
4. **Analysis** computes form scores, FDR, predictions, transfer recommendations
5. **Live endpoints** fetch real-time data from FPL live GW and ESPN APIs on demand
6. **Scheduler** auto-refreshes data during match windows
7. **Frontend** renders via React with TanStack Query for data fetching and caching

## Quick Start

### Docker (recommended)

```bash
# 1. Configure
cp .env.example .env
# Edit .env with your FPL team ID and league IDs

# 2. Run
make up          # Build and start on port 3001
make down        # Stop (keep data)
make clean       # Stop and wipe all data
make logs        # Tail container logs
```

Open `http://localhost:3001`. Team and leagues load automatically from `.env`.

### Local Development

```bash
# 1. Install
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cd frontend && npm install && cd ..

# 2. Configure
cp .env.example .env

# 3. Run
make dev         # Backend :8000 + frontend :8080 with hot reload
```

## Configuration

All settings use the `FPL_` prefix. Set via `.env` or environment variables.

| Variable | Default | Description |
|---|---|---|
| `FPL_ID` | `0` | Your FPL team ID (auto-loaded on startup) |
| `FPL_LEAGUE_IDS` | _(empty)_ | Comma-separated league IDs to auto-subscribe |
| `FPL_DB_PATH` | `data/fpl.db` | SQLite database path |
| `FPL_ODDS_API_KEY` | _(empty)_ | API key for the-odds-api.com (optional) |
| `FPL_API_FOOTBALL_KEY` | _(empty)_ | API-Football key for historical stats + PL assists (optional) |
| `FPL_AUTO_REFRESH` | `true` | Auto-refresh during match windows |

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ / TypeScript |
| Backend | FastAPI + uvicorn |
| Frontend | React 18 + Vite + Tailwind CSS + shadcn/ui |
| Database | SQLite via SQLAlchemy 2.0 |
| Data fetching | TanStack Query 5 |
| HTTP | httpx (async) |
| Scheduler | APScheduler |
| Live scores | ESPN public API (no key) |
| Player stats | ESPN + Understat (no key) |
| Name matching | rapidfuzz |
| Container | Docker + docker-compose |

## Testing

```bash
# Via script
./scripts/run-tests.sh unit          # 180 unit tests (no network)
./scripts/run-tests.sh integration   # 96 integration tests (live APIs)
./scripts/run-tests.sh all           # Everything
./scripts/run-tests.sh coverage      # Unit tests with coverage

# Direct
make test                            # Unit tests only
make test-integration                # Integration tests only
```

### Test Coverage

| Area | Tests | What's verified |
|---|---|---|
| FPL API ingest | 16 | Teams, players, fixtures, GW history, event_points |
| Analysis modules | 98 | Form, FDR, predictions, captaincy, transfers, differentials, price |
| API routes | 11 | Team endpoint, data status, league CRUD |
| Scheduler | 10 | Match window logic for all days/times |
| Player ID mapping | 18 | Fuzzy/exact matching, normalization |
| Odds/Understat ingest | 14 | Upsert logic, conflict handling |
| ESPN scores (live) | 16 | Scoreboard structure, standings, all 6 leagues |
| ESPN stats (live) | 7 | Search, athlete detail, stat field validation |
| FPL leagues (live) | 7 | Standings, picks, transfers, chips, live GW |
| Other live APIs | 21 | FPL bootstrap, odds, understat, projections |

## Data Sources

| Source | Auth | What it provides |
|---|---|---|
| **FPL API** | None | Players, fixtures, GW stats, xG/xA, DEFCON, live points, chips |
| **ESPN** | None | Live scores, league tables, player search + current season stats |
| **Understat** | None | xG, xA, npxG, xGChain, xGBuildup (Big 5 leagues) |
| **The Odds API** | Free key | 1X2, Over/Under 2.5 betting odds |
| **Fantasy Football Pundit** | None | Per-GW projected points, start%, CS% |
| **API-Football** | Free key | Historical player stats + PL assist enrichment (optional) |
