# Plan: Live FPL Gameweek Page

## Goal

A new "Live GW" page showing the current FPL gameweek fixture-by-fixture with goals, assists, bonus points leaders, and DEFCON leaders per fixture — all from the FPL live endpoint and DB.

## Data Sources (all existing)

- **`GET /api/fixtures/`** (FPL) — current GW fixtures with scores, kickoff, finished flag (already in DB)
- **`GET /api/event/{gw}/live/`** (FPL) — per-player live stats including `bps`, `bonus`, `goals_scored`, `assists`, `defensive_contribution`, plus `explain[0].fixture` tying each player to a fixture
- **Player/Team DB tables** — player name resolution (web_name), team short_name

## Backend Changes

### New file: `src/fpl/api/routes/live.py`

One endpoint:

| Method | Path | Description |
|--------|------|-------------|
| `GET /api/live/gameweek` | Return fixtures for current GW with live stats per fixture |

**Response shape:**
```json
{
  "gameweek": 32,
  "fixtures": [
    {
      "fixture_id": 313,
      "kickoff_time": "2026-04-12T14:00:00Z",
      "status": "in",  // scheduled, in, finished
      "minute": null,  // from FPL not available, use ESPN or skip
      "home_team": "Arsenal",
      "home_team_short": "ARS",
      "home_score": 2,
      "away_team": "Chelsea",
      "away_team_short": "CHE",
      "away_score": 0,
      "goal_scorers": [
        {"player": "Saka", "team": "ARS", "count": 1, "assist_by": "Odegaard"},
        ...
      ],
      "top_bps": [
        {"player": "Saka", "team": "ARS", "bps": 60, "bonus": 3, "points": 15},
        {"player": "Rice", "team": "ARS", "bps": 45, "bonus": 2, "points": 9},
        {"player": "Raya", "team": "ARS", "bps": 38, "bonus": 1, "points": 6}
      ],
      "top_defcon": [
        {"player": "Gabriel", "team": "ARS", "defcon": 14},
        {"player": "Saliba", "team": "ARS", "defcon": 12}
      ]
    }
  ]
}
```

### Logic

1. Query DB for current GW fixtures + teams
2. Fetch FPL live endpoint (reuse `_fetch_live_gw` from team route)
3. Query DB for all PL players (web_name, team_id, element_type)
4. For each fixture:
   - Find all players whose `explain[0].fixture == fixture.fpl_id`
   - Split by team (home/away via player.team_id match)
   - **Goal scorers:** players with `stats.goals_scored > 0`, repeat by count
   - **Assisters:** players with `stats.assists > 0` (displayed separately or inline)
   - **Top 3 BPS:** sort all players in this fixture by `stats.bps` desc, take top 3 with `bonus` awarded
   - **Top DEFCON:** top 3 players by `stats.defensive_contribution` (only if > 0)

### Modified: `src/fpl/api/app.py`

Register `live.router` at `/api/live`.

## Frontend Changes

### New page: `pages/LiveGameweekPage.tsx`

Route: `/live-gw`

**Layout:**
- Page header "Live Gameweek N"
- Auto-refresh + timestamp (reuse pattern)
- Grid of fixture cards (1 col mobile, 2 col desktop)
- Each card:
  - Score line at top (home team — score — away team)
  - Status badge (Live 67', HT, FT, Kickoff time)
  - **Goals** section: list of scorers with assist (if available)
  - **Bonus Points** section: top 3 BPS with their BPS/bonus/points
  - **DEFCON** section: top 2-3 defensive contributors

### Modified: `components/AppLayout.tsx`
Add "Live GW" nav item with `Zap` or `Activity` icon between "My Team" and "Leagues".

### Modified: `App.tsx`
Add route `/live-gw`.

### Modified: `lib/api.ts`
Add `api.getLiveGameweek()` method.

## Tests

- Unit test for `_build_fixture_live_data()` helper that groups players by fixture and extracts top BPS/scorers/defcon
- Integration test for `/api/live/gameweek` endpoint against mocked DB + live data

## Acceptance Criteria

1. Live GW page shows all fixtures for current GW
2. Each fixture card shows score, status, goal scorers, assisters
3. Top 3 BPS shown per fixture with player name, team, BPS, bonus, total points
4. Top DEFCON contributors shown per fixture
5. Auto-refreshes during match windows
6. Build + all tests pass

## Files

| File | Action |
|------|--------|
| `src/fpl/api/routes/live.py` | New: live GW endpoint |
| `src/fpl/api/app.py` | Register router |
| `frontend/src/pages/LiveGameweekPage.tsx` | New page |
| `frontend/src/components/AppLayout.tsx` | Nav item |
| `frontend/src/App.tsx` | Route |
| `frontend/src/lib/api.ts` | API method |
| `tests/test_api/test_live_route.py` | New tests |
