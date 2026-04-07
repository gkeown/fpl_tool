# FPL CLI

A data-driven Fantasy Premier League CLI assistant. Aggregates free data sources, computes player form heuristics, predicts goals and clean sheets, and recommends transfers and captains.

## Architecture

```
                           ┌──────────────────┐
                           │   fpl CLI (Typer) │
                           └────────┬─────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                   │
         ┌───────────────┐  ┌─────────────┐  ┌────────────────┐
         │  cli/ commands │  │  analysis/  │  │   ingest/      │
         │               │  │             │  │                │
         │ data_cmds     │  │ form        │  │ fpl_api        │
         │ team_cmds     │  │ fdr         │  │ understat      │
         │ player_cmds   │  │ predictions │  │ fbref          │
         │ captain_cmds  │  │ team        │  │ odds           │
         │ transfer_cmds │  │ captaincy   │  │ injuries       │
         │ predict_cmds  │  │ transfers   │  │ mapper         │
         │ price_cmds    │  │ differentials│ │                │
         │ formatters    │  │ price       │  └───────┬────────┘
         └───────────────┘  └──────┬──────┘          │
                                   │                  │
                           ┌───────┴──────────────────┴───┐
                           │     db/ (SQLAlchemy 2.0)     │
                           │                               │
                           │  engine.py  models.py         │
                           │  queries.py                   │
                           └───────────────┬───────────────┘
                                           │
                                    ┌──────┴──────┐
                                    │   SQLite    │
                                    │  data/fpl.db│
                                    └─────────────┘

 Data Sources:
 ┌─────────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────────┐
 │ FPL API         │  │ Understat    │  │ FBref     │  │ The Odds API │
 │ (bootstrap,     │  │ (xG, xA,    │  │ (SCA, GCA,│  │ (1X2, O/U,   │
 │  fixtures,      │  │  npxG per    │  │  pressures│  │  BTTS odds)  │
 │  player history)│  │  match)      │  │  per 90)  │  │              │
 └─────────────────┘  └──────────────┘  └───────────┘  └──────────────┘
```

### Data Flow

1. **Ingest layer** fetches raw data from external APIs/scraped sources
2. **Player ID mapper** resolves identities across sources (FPL ID <-> Understat <-> FBref)
3. **DB layer** stores everything in SQLite via upserts (idempotent)
4. **Analysis layer** reads from DB, computes form scores, FDR, predictions, transfer recommendations
5. **CLI layer** presents results via Rich tables

## Setup

```bash
# Clone and enter directory
cd fantasy_football

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Verify installation
fpl --help
```

### Configuration

Settings are configured via environment variables with the `FPL_` prefix:

| Variable | Default | Description |
|---|---|---|
| `FPL_DB_PATH` | `data/fpl.db` | SQLite database path |
| `FPL_ODDS_API_KEY` | _(empty)_ | API key for the-odds-api.com |
| `FPL_API_FOOTBALL_KEY` | _(empty)_ | API key for api-football.com |
| `FPL_FORM_LOOKBACK_WEEKS` | `5` | Gameweeks to consider for form |
| `FPL_HTTP_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `FPL_HTTP_MAX_CONCURRENT` | `5` | Max concurrent API requests |

Create a `.env` file (gitignored) for persistent configuration:

```bash
FPL_ODDS_API_KEY=your_key_here
FPL_API_FOOTBALL_KEY=your_key_here
```

## Usage

### Data Management

```bash
# Refresh all data sources
fpl data refresh

# Refresh specific source
fpl data refresh --source fpl
fpl data refresh --source understat
fpl data refresh --source odds

# Check data freshness
fpl data status

# Show player ID mapping quality
fpl data map-players --show-unmatched
```

### Player Analysis

```bash
# Search for a player
fpl players search "Saka"

# Detailed player card
fpl players info "Saka"

# Form rankings (top 20 by default)
fpl players form
fpl players form --position MID --top 10
fpl players form --max-cost 7.0

# Find low-ownership differentials
fpl players differentials --max-ownership 10
```

### Fixtures and Predictions

```bash
# Upcoming fixtures
fpl fixtures show
fpl fixtures show --gameweek 32

# Custom fixture difficulty ratings
fpl fixtures difficulty --weeks 6

# Goal predictions with betting odds context
fpl predict goals --gameweek 32

# Clean sheet probability rankings
fpl predict cleansheets --top 10
```

### Team Management

```bash
# Store FPL credentials
fpl me login

# View your team with form scores
fpl me team --detail

# Analyse team — weak spots, improvement suggestions
fpl me analyse --weeks 5
```

### Transfers and Captaincy

```bash
# Captain recommendations
fpl captain --top 5 --detail

# Transfer suggestions
fpl transfers suggest
fpl transfers suggest --free-transfers 2 --max-hits 4

# Head-to-head player comparison
fpl transfers compare "Saka" "Salah"
```

### Price Predictions

```bash
# Players likely to rise in price
fpl prices risers --top 10

# Players likely to fall
fpl prices fallers --top 10
```

## Database Schema

17 tables organized into four groups:

**Core FPL data:** `teams`, `players`, `player_gameweek_stats`, `fixtures`, `gameweeks`

**External data:** `player_id_maps`, `understat_matches`, `fbref_season_stats`, `betting_odds`, `injuries`

**User data:** `my_team_players`, `my_account`

**Computed/cache:** `ownership_snapshots`, `player_form_scores`, `custom_fdr`, `team_predictions`

**System:** `ingest_logs`

Migrations managed by Alembic:

```bash
# Generate a migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Testing

### Unit Tests (fast, no network)

```bash
# Run unit tests only (no external API calls)
pytest tests/ -v -m "not integration"

# Run with coverage
pytest tests/ -m "not integration" --cov=src --cov-report=term-missing

# Run specific test module
pytest tests/test_ingest/test_fpl_api.py -v

# Run a specific test
pytest tests/test_skeleton.py::test_all_tables_created -v
```

### Integration Tests (hit live APIs)

Integration tests verify the end-to-end flow against live external APIs. They are marked with `@pytest.mark.integration` so you can run them separately.

```bash
# Run integration tests only
pytest tests/test_integration/ -v -m integration

# Run all tests (unit + integration)
pytest tests/ -v
```

Integration tests cover three areas:

1. **API Response Shape** (11 tests) — verify that the live FPL API returns the fields our code expects (catches API changes between seasons)
2. **Ingest Pipeline** (12 tests) — fetch live data, upsert into in-memory SQLite, verify record counts, FK integrity, data validity
3. **End-to-End** (3 tests) — full pipeline: fetch bootstrap + fixtures + player histories, ingest, verify data consistency

### Test Structure

```
tests/
├── conftest.py              # In-memory SQLite fixture (db_session)
├── fixtures/                # JSON snapshots of API responses
│   └── bootstrap_static.json
├── test_skeleton.py         # Project structure and model tests
├── test_ingest/
│   └── test_fpl_api.py      # FPL API upsert logic tests (unit)
├── test_integration/
│   └── test_fpl_api_live.py # Live API integration tests (26 tests)
└── test_analysis/           # Analysis module tests (form, FDR, etc.)
```

Unit tests use an in-memory SQLite database with no external dependencies. Integration tests hit live APIs but still use in-memory SQLite so they leave no artifacts.

### Code Quality

```bash
# Format
black src/ tests/

# Lint
ruff check src/ tests/
ruff check --fix src/ tests/   # auto-fix

# Type check (strict mode)
mypy src/

# All checks at once
black --check src/ tests/ && ruff check src/ tests/ && mypy src/ && pytest tests/ -v
```

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| CLI framework | Typer + Rich |
| Database | SQLite via SQLAlchemy 2.0 |
| HTTP client | httpx (async) |
| Web scraping | BeautifulSoup4 + lxml |
| Name matching | rapidfuzz |
| Migrations | Alembic |
| Credentials | keyring |
| Formatting | black |
| Linting | ruff |
| Type checking | mypy (strict) |
| Testing | pytest + pytest-asyncio + pytest-httpx |

## Project Status

- [x] Milestone 0: Project skeleton, DB models, CLI framework
- [x] Milestone 1: FPL API ingest (bootstrap, fixtures, player histories)
- [ ] Milestone 2: Understat + FBref + betting odds + injuries + player ID mapping
- [ ] Milestone 3: Form engine + fixture difficulty + goal/clean sheet predictions
- [ ] Milestone 4: Team analyser + captaincy picker
- [ ] Milestone 5: Transfer recommender
- [ ] Milestone 6: Differentials + price predictor
- [ ] Milestone 7: Polish (output formats, smart refresh, error handling)
