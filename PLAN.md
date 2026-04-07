# FPL CLI Application — Implementation Plan

## Context
Build a personal FPL (Fantasy Premier League) CLI tool that aggregates free data sources, computes player form heuristics, and recommends transfers/captains. Greenfield Python project in an empty repo. Local-only, single-user, SQLite-backed, daily/on-demand refresh.

## Tech Stack
- **Python 3.12**, type hints everywhere, `from __future__ import annotations`
- **Typer** (CLI) + **Rich** (output formatting)
- **SQLAlchemy 2.0** (ORM, `Mapped[]` style) + **SQLite**
- **httpx** (async HTTP) + **BeautifulSoup/lxml** (scraping)
- **rapidfuzz** (player name matching across sources)
- **Alembic** (schema migrations)
- **keyring** (FPL credentials)
- **black**, **ruff**, **mypy** (strict) for code quality

## Project Structure
```
fantasy_football/
├── pyproject.toml
├── .gitignore
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── src/fpl/
│   ├── __init__.py
│   ├── config.py              # pydantic-settings, DB path, API URLs
│   ├── types.py               # Position enum, shared types
│   ├── db/
│   │   ├── engine.py          # get_engine(), get_session()
│   │   ├── models.py          # All ORM models
│   │   └── queries.py         # Common query helpers
│   ├── ingest/
│   │   ├── fpl_api.py         # FPL API client (async)
│   │   ├── understat.py       # Understat xG/xA scraper
│   │   ├── fbref.py           # FBref advanced stats scraper
│   │   ├── odds.py            # Betting odds from The Odds API + API-Football
│   │   ├── injuries.py        # Injury aggregation
│   │   └── mapper.py          # Cross-source player ID mapping
│   ├── analysis/
│   │   ├── form.py            # Player form engine
│   │   ├── fdr.py             # Custom fixture difficulty
│   │   ├── predictions.py     # Team goal predictions + clean sheet probability
│   │   ├── team.py            # Team analyser
│   │   ├── transfers.py       # Transfer recommender
│   │   ├── captaincy.py       # Captain picker
│   │   ├── differentials.py   # Low-ownership gems
│   │   └── price.py           # Price change predictor
│   └── cli/
│       ├── app.py             # Root Typer app
│       ├── data_cmds.py       # fpl data refresh/status/map-players
│       ├── team_cmds.py       # fpl me team/analyse
│       ├── player_cmds.py     # fpl players search/form/info/differentials
│       ├── transfer_cmds.py   # fpl transfers suggest/compare
│       ├── captain_cmds.py    # fpl captain
│       ├── predict_cmds.py    # fpl predict goals/cleansheets
│       ├── price_cmds.py      # fpl prices risers/fallers
│       └── formatters.py      # Rich table/output helpers
├── tests/
│   ├── conftest.py
│   ├── fixtures/              # JSON API snapshots
│   ├── test_ingest/
│   └── test_analysis/
└── data/
    └── .gitkeep
```

## CLI Commands
```
fpl data refresh [--source fpl|understat|fbref|odds|injuries|all]
fpl data status
fpl data map-players [--show-unmatched]
fpl me login
fpl me team [--detail]
fpl me analyse [--weeks N]
fpl players search <query>
fpl players info <name-or-id>
fpl players form [--position POS] [--max-cost N] [--top N]
fpl players differentials [--max-ownership N] [--position POS]
fpl fixtures show [--gameweek N] [--team NAME]
fpl fixtures difficulty [--weeks N]
fpl predict goals [--gameweek N] [--team NAME]
fpl predict cleansheets [--gameweek N] [--top N]
fpl captain [--top N] [--detail]
fpl transfers suggest [--free-transfers N] [--budget N] [--max-hits N] [--weeks N]
fpl transfers compare <player1> <player2>
fpl prices risers [--top N]
fpl prices fallers [--top N]
```

## Database Schema

### Core FPL Tables
- **teams** — FPL team data (strength ratings, attack/defence home/away)
- **players** — FPL player master data (cost, status, points, form, etc.)
- **player_gameweek_stats** — per-GW performance (points, BPS, ICT, minutes)
- **fixtures** — match schedule with difficulty ratings
- **gameweeks** — GW metadata and deadlines

### External Data Tables
- **player_id_map** — cross-source ID mapping (fpl_id -> understat/fbref)
- **understat_matches** — per-match xG, xA, npxG, shots, key passes
- **fbref_season_stats** — season aggregates (progressive actions, SCA, GCA, pressures)
- **betting_odds** — 1X2, O/U 2.5, BTTS odds per fixture from bookmakers
- **injuries** — aggregated fitness status from multiple sources

### User Data Tables
- **my_team** — user's FPL team snapshot (15 players, prices, captain)
- **my_account** — user's FPL account info (rank, bank, free transfers)

### Computed/Cache Tables
- **ownership_snapshots** — transfer deltas for price prediction
- **player_form_scores** — cached computed form scores per GW
- **custom_fdr** — computed fixture difficulty ratings
- **team_predictions** — predicted goals for/against and CS probability per fixture

### System Tables
- **ingest_log** — idempotency tracking and debugging

## Data Sources

### FPL API (fantasy.premierleague.com/api/)
- No auth needed for bootstrap data, fixtures, player histories
- Auth (cookie session) needed for user's team endpoint
- Endpoints: `/bootstrap-static/`, `/fixtures/`, `/element-summary/{id}/`, `/my-team/{id}/`

### Understat (understat.com)
- xG, xA, npxG, shots, key passes per match
- Data embedded as JSON in `<script>` tags — extract and parse
- Fetch per-team pages: `https://understat.com/team/{Team_Name}/{season}`

### FBref (fbref.com)
- Progressive carries/passes, SCA, GCA, pressures, tackles, interceptions
- HTML table scraping with BeautifulSoup + lxml
- Rate limit: 4-second delay between requests
- Squad stats: `https://fbref.com/en/comps/9/stats/Premier-League-Stats`

### Betting Odds
- **Primary: The Odds API** (the-odds-api.com) — 500 credits/month free, API key auth
  - Markets: 1X2 (h2h), Over/Under (totals), BTTS
  - Batch markets in single request to conserve credits
- **Secondary: API-Football** (api-football.com) — 100 req/day free, header auth
  - Same markets, fallback/cross-reference

### Injury Sources
- FPL's own `status` and `news` fields (from bootstrap data)
- Premier Injuries (premierinjuries.com) for additional detail

## Player ID Mapping Strategy
Three-tier approach (the hardest data engineering problem):
1. **Exact match** — normalize names (lowercase, strip accents/hyphens), match on (name, team). ~85-90%
2. **Fuzzy match** — `rapidfuzz.fuzz.token_sort_ratio` threshold 85, same team constraint. ~8-10%
3. **Manual overrides** — `data/player_overrides.json` for remaining ~2%

---

## Implementation Milestones

### Milestone 0: Project Skeleton
**Goal:** Bootable project with tooling, empty CLI, DB creation.

**Files:** pyproject.toml, .gitignore, config.py, types.py, db/engine.py, db/models.py, cli/app.py, alembic setup, tests/conftest.py

**Key decisions:**
- SQLAlchemy 2.0 `DeclarativeBase` + `Mapped[T]` for mypy strict
- Default DB at `data/fpl.db`, configurable via `FPL_DB_PATH` env var
- Alembic autogenerate from ORM models

---

### Milestone 1: FPL API Ingest
**Goal:** Fetch and store all FPL data — the foundation everything depends on.

**Files:** ingest/fpl_api.py, cli/data_cmds.py, tests

**Key decisions:**
- `httpx.AsyncClient` with semaphore (5 concurrent) for rate limiting
- Upsert via `insert().on_conflict_do_update()`
- Incremental player history fetch (only new GWs since last ingest)
- FPL auth via cookie session for my-team endpoint, credentials in keyring

---

### Milestone 2: Understat + FBref + Odds + Injuries + Player Mapping
**Goal:** Scrape external data sources, ingest betting odds, run cross-source ID mapping.

**Files:** ingest/understat.py, ingest/fbref.py, ingest/odds.py, ingest/injuries.py, ingest/mapper.py, data/player_overrides.json

**Betting odds ingestion:**
- The Odds API: batch 1X2 + O/U + BTTS in single request (~6 credits)
- API-Football: fallback, 100 req/day
- API keys via env vars (`FPL_ODDS_API_KEY`, `FPL_API_FOOTBALL_KEY`)
- Refresh weekly or on-demand pre-GW

**Key decisions:**
- Each scraper catches per-player exceptions and continues
- FBref: once-daily max. Understat: after each GW. Odds: weekly/pre-GW
- Mapping runs automatically after full ingest

---

### Milestone 3: Form Engine + Fixture Difficulty + Goal/Clean Sheet Predictions
**Goal:** Core analytics that captaincy, transfers, and differentials depend on.

**Files:** analysis/form.py, analysis/fdr.py, analysis/predictions.py, cli/player_cmds.py, cli/predict_cmds.py, cli/formatters.py

**Form formula** (per position, configurable weights):
```
form_score = weighted_sum(xG/90, xA/90, goals/90, assists/90, BPS/90, ICT/90, points/90, minutes_factor)
```
Normalized to 0-100 via percentile ranks within position. Degrades gracefully without Understat data.

**Goal predictions** — two complementary approaches:

*Statistical model:*
```
predicted_goals(attacking, defending) = team_xg/90 * opponent_xga/90 / league_avg * home_away_mod
```

*Odds-implied:*
```
Convert 1X2 + O/U 2.5 odds → implied probabilities → back-solve expected goals via Poisson
```

*Combined:* 0.5 * statistical + 0.5 * odds-implied

**Clean sheet probability:**
```
P(CS) = e^(-predicted_goals_against)    # Poisson P(X=0)
```
Cross-referenced with BTTS odds, recent defensive form, opponent strength, home/away, injuries.

**Output: `fpl predict goals`**
```
GW30    Home         Pred    Away         Pred    CS%(H)  CS%(A)  O/U 2.5   BTTS
        Arsenal      1.8     Wolves       0.7     49%     17%     Over 1.65 No 1.80
        Man City     2.1     Everton      0.6     55%     12%     Over 1.45 No 1.95
```

---

### Milestone 4: Team Analyser + Captaincy Picker
**Goal:** Personal team features.

**Files:** analysis/team.py, analysis/captaincy.py, cli/team_cmds.py, cli/captain_cmds.py

**Captain formula:**
```
captain_score = 0.35*form + 0.25*fixture_ease + 0.15*xG/90 + 0.10*xA/90 + 0.10*home_bonus + 0.05*haul_rate
```

---

### Milestone 5: Transfer Recommender
**Goal:** The flagship feature — suggest optimal transfers.

**Files:** analysis/transfers.py, cli/transfer_cmds.py

**Algorithm:**
1. Score all players: `form * fixture_ease / cost`
2. For each squad player, find best replacements at same position within budget
3. Rank by `delta_value = new - old`
4. For multi-transfer: check complementary pairs
5. Enforce constraints (max 3/team, valid formation)

---

### Milestone 6: Differentials + Price Predictor
**Goal:** Discovery features.

**Files:** analysis/differentials.py, analysis/price.py, cli/price_cmds.py

- **Differentials:** low ownership (< 10%) + high form + good fixtures
- **Price predictor:** ownership delta tracking, threshold heuristic for rise/fall pressure

---

### Milestone 7: Polish
- `--format [table|json|csv]` output option
- Smart refresh (skip if no new GW)
- Global `--quiet`/`--verbose` flags
- Integration tests
- Error handling for source outages

---

## Verification (after each milestone)
1. `black --check src/ tests/`
2. `ruff check src/ tests/`
3. `mypy src/`
4. `pytest tests/ -v`
5. Manual CLI smoke test
