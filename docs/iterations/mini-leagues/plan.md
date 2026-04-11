# Plan: Mini League Section

## Goal

Add a mini league section where the user can subscribe to FPL classic leagues, view standings, and drill into any opponent's team with the same detail as "My Team" — squad, GW points, expected points, bank, free transfers, form.

## FPL API Endpoints (all public, no auth)

| Endpoint | Returns |
|----------|---------|
| `GET /api/leagues-classic/{league_id}/standings/` | League name, entries with: entry (team_id), player_name, entry_name, rank, total, event_total |
| `GET /api/entry/{team_id}/` | Manager info: current_event, summary_overall_points, summary_overall_rank, summary_event_points, last_deadline_bank, last_deadline_total_transfers, last_deadline_value |
| `GET /api/entry/{team_id}/event/{gw}/picks/` | 15 picks with element (player_id), position, is_captain, is_vice_captain, multiplier; entry_history with bank, points, event_transfers |
| `GET /api/entry/{team_id}/transfers/` | Array of every transfer: element_in, element_in_cost, element_out, element_out_cost, entry, event (GW number), time (ISO timestamp) |

## Data Model

### New DB Models

**`League`** — Subscribed leagues
- `league_id: int` (PK) — FPL league ID
- `name: str` — League name
- `fetched_at: str`

**`LeagueEntry`** — Cached standings per entry
- `id: int` (PK, autoincrement)
- `league_id: int` (FK → leagues.league_id)
- `entry_id: int` — FPL team ID
- `player_name: str`
- `entry_name: str`
- `rank: int`
- `total: int` — Total season points
- `event_total: int` — Current GW points
- `fetched_at: str`
- Unique constraint: (league_id, entry_id)

No separate opponent team model — we'll fetch opponent picks live when the user drills into a team, using the same `fetch_entry` + `fetch_entry_picks` pattern that already exists. This avoids storing 15 rows per opponent per refresh.

## Backend Changes

### New file: `src/fpl/api/routes/leagues.py`

5 endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET /api/leagues` | List subscribed leagues with entry counts |
| `POST /api/leagues` | Subscribe to a league (body: `{league_id: int}`) — fetches league info + standings from FPL API, stores in DB |
| `DELETE /api/leagues/{league_id}` | Unsubscribe — delete league + entries from DB |
| `GET /api/leagues/{league_id}/standings` | Return cached standings, re-fetch if stale (>1hr) or if `?force=true` |
| `GET /api/leagues/{league_id}/entry/{entry_id}` | Fetch opponent's full team live — reuses `fetch_entry` + `fetch_entry_picks` + `fetch_entry_transfers`, joins with Player table to build same response shape as `/api/me/team` plus a `transfers` array |

### New file: `src/fpl/ingest/leagues.py`

- `fetch_league_standings(client, settings, league_id)` — call FPL API
- `fetch_entry_transfers(client, settings, team_id)` — call `/api/entry/{team_id}/transfers/`
- `upsert_league(session, league_id, data)` — upsert League + LeagueEntry rows

### Modified: `src/fpl/api/app.py`

- Register `leagues.router` at `/api/leagues`

### Modified: `src/fpl/db/models.py`

- Add `League` and `LeagueEntry` models

### Modified: `src/fpl/api/routes/data.py`

- Add `leagues` to refresh sources — re-fetch standings for all subscribed leagues

## Frontend Changes

### New page: `pages/LeaguePage.tsx`

Route: `/leagues`

**Layout:**
- If no leagues subscribed: prompt to add one with a league ID input
- League selector dropdown (if multiple leagues)
- Standings table: Rank, Manager, Team Name, GW Pts, Total Pts
- Click any row → navigates to `/leagues/{league_id}/team/{entry_id}`

### New page: `pages/OpponentTeamPage.tsx`

Route: `/leagues/:leagueId/team/:entryId`

**Layout:** Same as MyTeamPage — back button, badge chips (GW, GW Pts, Total Pts, Rank, Bank, FT), Starting XI table, Bench table. Reuses the same PlayerTable component pattern but with data from the opponent API endpoint.

**Transfers section:** Below the squad tables, show a "Recent Transfers" card listing transfers grouped by gameweek (most recent first). Each transfer row shows: GW number, player out (pink, with cost) → player in (green, with cost), timestamp. Show last 3 GWs of transfers by default.

### Modified: `components/AppLayout.tsx`

- Add "Leagues" nav item with `Trophy` icon between "My Team" and "Players"

### Modified: `App.tsx`

- Add routes for `/leagues` and `/leagues/:leagueId/team/:entryId`

### Modified: `lib/api.ts`

- Add types: `LeagueSummary`, `LeagueStanding`, `OpponentTeam`, `Transfer`
- Add API methods: `getLeagues`, `addLeague`, `removeLeague`, `getLeagueStandings`, `getLeagueEntry`

## Auto-Refresh During Match Times

Add a background scheduler that refreshes data sources every 5 minutes during peak game times:
- **Saturday:** 12:30 – 19:30
- **Sunday:** 12:00 – 18:30
- **Monday:** 20:00 – 22:30

### Implementation

**New file: `src/fpl/scheduler.py`**

Use APScheduler's `AsyncIOScheduler` (already a dependency via the existing codebase pattern). Add a single interval job that runs every 5 minutes. The job checks the current day/time (UK timezone) and only runs the refresh if within one of the match windows. If outside the windows, it skips silently.

This keeps the scheduler simple — one job, one interval — rather than complex cron expressions for each window.

**Modified: `src/fpl/api/app.py`**

Start the scheduler in the FastAPI lifespan (after `init_db()`), shut it down on exit.

**Config:**

Add `FPL_AUTO_REFRESH: bool = True` to Settings so it can be disabled.

## Bonus Points Column

Add a "Bonus" column to both My Team and Opponent Team tables showing the bonus points (0-3) awarded in the current gameweek.

### Backend

**Modified: `src/fpl/api/routes/team.py`**
- In `get_team()`: query `PlayerGameweekStats` for the current GW to get per-player `bonus` and `bps` (bonus point system score). Add `gw_bonus` to each player dict.

**Modified: `src/fpl/api/routes/leagues.py`**
- In the opponent team endpoint: same join on `PlayerGameweekStats` for the current GW to include `gw_bonus`.

### Frontend

**Modified: `pages/MyTeamPage.tsx` and `pages/OpponentTeamPage.tsx`**
- Add "Bonus" column after "GW Pts". Show the value with gold highlight for 3 (max bonus).

## Acceptance Criteria

1. User can subscribe to a league by entering a league ID
2. League standings display with rank, manager, team name, GW points, total points
3. Clicking a row shows the opponent's full team with the same columns as My Team
4. Opponent team shows: GW points (with captain multiplier), form, xPts, cost, status
5. Opponent team shows bank, free transfers, total points, rank
6. User can remove a subscribed league
7. Standings refresh on page load (if stale) or via force refresh
8. New route tests for league endpoints
9. All existing tests pass
10. Frontend build succeeds
11. Opponent team page shows recent transfers (in/out per GW)
12. Auto-refresh runs every 5 min during Sat/Sun/Mon match windows
13. Auto-refresh can be disabled via FPL_AUTO_REFRESH=false
14. My Team and Opponent Team tables show a Bonus column (0-3) for current GW

## Files

| File | Action |
|------|--------|
| `src/fpl/db/models.py` | Add League, LeagueEntry models |
| `src/fpl/ingest/leagues.py` | New: fetch + upsert league standings |
| `src/fpl/api/routes/leagues.py` | New: 5 league endpoints |
| `src/fpl/api/app.py` | Register leagues router |
| `src/fpl/api/routes/data.py` | Add leagues to refresh |
| `frontend/src/lib/api.ts` | Add types + API methods |
| `frontend/src/pages/LeaguePage.tsx` | New: league standings page |
| `frontend/src/pages/OpponentTeamPage.tsx` | New: opponent team detail |
| `frontend/src/components/AppLayout.tsx` | Add Leagues nav item |
| `frontend/src/App.tsx` | Add routes |
| `tests/test_api/test_leagues_route.py` | New: league endpoint tests |
| `tests/test_ingest/test_leagues.py` | New: league ingest tests |
| `src/fpl/scheduler.py` | New: APScheduler auto-refresh during match windows |
| `src/fpl/config.py` | Add auto_refresh setting |
