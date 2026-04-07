# FPL CLI

A data-driven Fantasy Premier League CLI assistant for personal use. Aggregates free data sources (FPL API, Understat, betting odds, projected points), analyses player form and fixture difficulty, predicts goals and clean sheets, and recommends transfers and captains.

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
         │ player_cmds   │  │ predictions │  │ odds           │
         │ captain_cmds  │  │ team        │  │ projections    │
         │ transfer_cmds │  │ captaincy   │  │ injuries       │
         │ predict_cmds  │  │ transfers   │  │ mapper         │
         │ price_cmds    │  │ differentials│ │                │
         │ fixtures_cmds │  │ price       │  └───────┬────────┘
         │ formatters    │  │             │           │
         └───────────────┘  └──────┬──────┘          │
                                   │                  │
                           ┌───────┴──────────────────┴───┐
                           │     db/ (SQLAlchemy 2.0)     │
                           │  engine.py  models.py        │
                           └───────────────┬──────────────┘
                                           │
                                    ┌──────┴──────┐
                                    │   SQLite    │
                                    │  data/fpl.db│
                                    └─────────────┘

 Data Sources:
 ┌─────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
 │ FPL API         │ │ Understat    │ │ The Odds API │ │ FF Pundit        │
 │ (players, xG,   │ │ (xG, xA,    │ │ (1X2, O/U    │ │ (projected pts   │
 │  fixtures, ICT, │ │  npxG, xGC,  │ │  betting     │ │  per GW, start%, │
 │  DEFCON, history)│ │  xGBuildup)  │ │  odds)       │ │  CS%)            │
 └─────────────────┘ └──────────────┘ └──────────────┘ └──────────────────┘
```

### Data Flow

1. **Ingest layer** fetches raw data from FPL API, Understat, The Odds API, and Fantasy Football Pundit
2. **Player ID mapper** resolves identities across sources (FPL ID <-> Understat) using fuzzy name matching
3. **DB layer** stores everything in SQLite via idempotent upserts
4. **Analysis layer** computes form scores, custom FDR, goal predictions, transfer recommendations
5. **CLI layer** presents results via Rich tables

## Setup

```bash
# Clone and enter directory
git clone git@github.com:YOUR_USERNAME/fantasy-football.git
cd fantasy-football

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Verify installation
fpl --help
```

### Configuration

Create a `.env` file in the project root (gitignored):

```bash
# Required: your FPL team ID (find at fantasy.premierleague.com -> Points page URL)
FPL_ID=1234567

# Optional: enables betting odds data (free, 500 credits/month)
# Sign up at https://the-odds-api.com
FPL_ODDS_API_KEY=your_key_here
```

All settings use the `FPL_` prefix and can be set via environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `FPL_ID` | `0` | Your FPL team ID |
| `FPL_DB_PATH` | `data/fpl.db` | SQLite database path |
| `FPL_ODDS_API_KEY` | _(empty)_ | API key for the-odds-api.com |
| `FPL_FORM_LOOKBACK_WEEKS` | `5` | Gameweeks for form calculation |
| `FPL_HTTP_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `FPL_HTTP_MAX_CONCURRENT` | `5` | Max concurrent API requests |

## Quick Start

```bash
# 1. Load all data (~15 seconds)
fpl data refresh

# 2. Load your team
fpl me login

# 3. Explore
fpl me team
fpl me analyse
fpl captain pick --detail
fpl players form --position MID --top 10
fpl predict goals
fpl news
```

## Commands

### Data Management

```bash
fpl data refresh                          # Refresh all sources
fpl data refresh --source fpl             # FPL API only
fpl data refresh --source understat       # Understat xG data
fpl data refresh --source odds            # Betting odds (needs API key)
fpl data refresh --source projections     # Projected points
fpl data refresh --source injuries        # Injury data
fpl data status                           # Show ingest history
```

### Your Team

```bash
fpl me login                              # Load team (uses FPL_ID from .env)
fpl me login 1234567                      # Load team by ID
fpl me team                               # Show squad with form + projected points
fpl me team --detail                      # Expanded view with captain markers
fpl me analyse                            # Full analysis: form, FDR, xPts, weak spots
fpl me analyse --weeks 5                  # Look-ahead window for fixtures
```

### Player Analysis

```bash
fpl players form                          # Top 20 by FPL form (avg pts/game)
fpl players form --position DEF --top 10  # Filter by position
fpl players form --max-cost 6.0           # Budget filter
fpl players search "Saka"                 # Fuzzy name search
fpl players info "Saka"                   # Full player card: stats, xG, DEFCON,
                                          #   projected pts, set-pieces, fixtures
fpl players differentials                 # Low-ownership high-value players
fpl players differentials --max-ownership 5 --position MID
fpl players setpieces                     # Set-piece taker notes (penalties, corners, FKs)
fpl players setpieces --team Arsenal
```

### Fixtures and Predictions

```bash
fpl fixtures show                         # Upcoming fixture schedule
fpl fixtures show --gameweek 33           # Specific gameweek
fpl fixtures difficulty --weeks 6         # FDR heatmap grid across weeks
fpl fixtures odds                         # Betting odds for next GW fixtures
fpl predict goals                         # Predicted scorelines + CS% per fixture
fpl predict goals --gameweek 33
fpl predict cleansheets --top 10          # Clean sheet probability rankings
```

### Transfers and Captaincy

```bash
fpl captain pick                          # Captain recommendations with xPts
fpl captain pick --top 5 --detail         # Full scoring breakdown
fpl transfers suggest                     # Best transfer suggestions for your team
fpl transfers suggest --free-transfers 2 --max-hits 4
fpl transfers compare "Saka" "Palmer"     # Head-to-head comparison
```

### Price Changes and News

```bash
fpl prices risers --top 10                # Most transferred in this GW
fpl prices fallers --top 10               # Most transferred out this GW
fpl news                                  # Latest FPL headlines (Fantasy Football Scout)
fpl news --top 5
```

## Data Sources

| Source | Auth | What it provides |
|---|---|---|
| **FPL API** | None | Players, fixtures, gameweek stats, xG/xA, ICT, DEFCON, set-piece notes |
| **Understat** | None | Team/player xG, xA, npxG, xGChain, xGBuildup |
| **The Odds API** | Free API key | 1X2, Over/Under 2.5 betting odds per fixture |
| **Fantasy Football Pundit** | None | Per-GW projected points, start%, CS%, blank/double flags |
| **Fantasy Football Scout** | None (RSS) | Latest FPL news headlines |

Note: FBref advanced stats (SCA, GCA, progressive carries) were removed in January 2026 when Opta terminated their data license. The FPL API's own DEFCON stats and Understat data provide equivalent analytical coverage.

## Database Schema

18 tables organized into five groups:

**Core FPL data:** `teams`, `players`, `player_gameweek_stats`, `fixtures`, `gameweeks`

**External data:** `player_id_maps`, `understat_matches`, `fbref_season_stats`, `betting_odds`, `injuries`

**User data:** `my_team_players`, `my_account`

**Computed/cache:** `ownership_snapshots`, `player_form_scores`, `custom_fdr`, `team_predictions`, `player_projections`

**System:** `ingest_logs`

## Testing

### Unit Tests (153 tests, no network)

```bash
pytest tests/ -v -m "not integration"              # Run unit tests
pytest tests/ -m "not integration" --cov=src        # With coverage
```

### Integration Tests (26 tests, hits live APIs)

```bash
pytest tests/test_integration/ -v -m integration    # Live API tests
pytest tests/ -v                                    # All tests
```

Integration tests verify:
- **API Response Shape** (11 tests) -- live FPL API returns expected fields
- **Ingest Pipeline** (12 tests) -- fetch, upsert, query cycle with real data
- **End-to-End** (3 tests) -- full pipeline with data consistency checks

### Test Structure

```
tests/
├── conftest.py                  # In-memory SQLite fixture
├── fixtures/                    # JSON API snapshots
├── test_skeleton.py             # Project structure + model tests
├── test_ingest/
│   ├── test_fpl_api.py          # FPL upsert logic (12 tests)
│   ├── test_understat.py        # Understat upsert (5 tests)
│   ├── test_odds.py             # Odds matching + upsert (9 tests)
│   └── test_mapper.py           # Player ID mapping (18 tests)
├── test_analysis/
│   ├── test_form.py             # Form engine (16 tests)
│   ├── test_fdr.py              # Fixture difficulty (9 tests)
│   ├── test_predictions.py      # Goal predictions (19 tests)
│   ├── test_team.py             # Team analysis (12 tests)
│   ├── test_captaincy.py        # Captain picker (16 tests)
│   ├── test_transfers.py        # Transfer recommender (11 tests)
│   ├── test_differentials.py    # Differentials (8 tests)
│   └── test_price.py            # Price predictor (9 tests)
└── test_integration/
    └── test_fpl_api_live.py     # Live API integration (26 tests)
```

### Code Quality

```bash
black src/ tests/                           # Format
ruff check src/ tests/                      # Lint
mypy src/                                   # Type check (strict)
black --check src/ tests/ && ruff check src/ tests/ && mypy src/ && pytest tests/ -m "not integration"
```

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ with strict type hints |
| CLI | Typer + Rich |
| Database | SQLite via SQLAlchemy 2.0 (`Mapped[T]`) |
| HTTP | httpx (async) |
| Name matching | rapidfuzz |
| Migrations | Alembic |
| News feed | feedparser (RSS) |
| Formatting | black |
| Linting | ruff |
| Type checking | mypy (strict mode) |
| Testing | pytest + pytest-asyncio + pytest-httpx |
