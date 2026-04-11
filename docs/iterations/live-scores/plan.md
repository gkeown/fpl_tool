# Plan: Live Scores Section

## Goal

Add a live scores page showing current/today's fixtures across the 5 major European leagues: Premier League, Serie A, La Liga, Bundesliga, and Ligue 1. Include goal scorers for all leagues and assist providers for Premier League matches.

## API: API-Football (already configured)

- **Base URL:** `https://v3.football.api-sports.io` (already in `config.py` as `api_football_base_url`)
- **Auth:** `x-apisports-key` header (already in `config.py` as `api_football_key`)
- **Free tier:** 100 requests/day, live scores updated every 15 seconds

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /fixtures?date=YYYY-MM-DD&league=39&season=2025` | Today's fixtures for a league |
| `GET /fixtures?live=39-135-140-78-61` | Live matches across all 5 leagues |
| `GET /fixtures/events?fixture={id}` | Goal scorers + assists for a match |

### League IDs

| League | ID |
|--------|-----|
| Premier League | 39 |
| Serie A | 135 |
| La Liga | 140 |
| Bundesliga | 78 |
| Ligue 1 | 61 |

### Match Status Codes

`NS` (not started), `1H` (first half), `HT` (half time), `2H` (second half), `FT` (full time), `ET` (extra time), `PST` (postponed)

### Response Shapes

**Fixture:**
```json
{
  "fixture": { "id": 868078, "date": "...", "status": { "short": "1H", "elapsed": 23 } },
  "league": { "id": 39, "name": "Premier League" },
  "teams": { "home": { "name": "Arsenal" }, "away": { "name": "Liverpool" } },
  "goals": { "home": 1, "away": 0 },
  "events": [
    {
      "time": { "elapsed": 15, "extra": null },
      "team": { "name": "Arsenal" },
      "player": { "name": "B. Saka" },
      "assist": { "name": "M. Odegaard" },
      "type": "Goal",
      "detail": "Normal Goal"
    }
  ]
}
```

## Backend Changes

### New file: `src/fpl/api/routes/scores.py`

Two endpoints, both async (live FPL API calls, no DB):

| Method | Path | Description |
|--------|------|-------------|
| `GET /api/scores/today` | Fetch today's fixtures for all 5 leagues, grouped by league. Include events for each fixture. |
| `GET /api/scores/live` | Fetch only live matches (in-play right now) |

The `today` endpoint is the primary one. It fetches fixtures for each league for today's date, then for PL fixtures fetches events to get assisters. For non-PL leagues, goal scorers come from the fixture response's events array (fetched inline with `?events=true` parameter if available, or via separate events call).

**Response shape:**
```json
{
  "date": "2026-04-11",
  "leagues": [
    {
      "id": 39,
      "name": "Premier League",
      "country": "England",
      "matches": [
        {
          "fixture_id": 868078,
          "status": "1H",
          "elapsed": 23,
          "home_team": "Arsenal",
          "away_team": "Liverpool",
          "home_goals": 1,
          "away_goals": 0,
          "kickoff": "2026-04-11T15:00:00+00:00",
          "events": [
            {
              "minute": 15,
              "extra_minute": null,
              "type": "Goal",
              "detail": "Normal Goal",
              "player": "B. Saka",
              "assist": "M. Odegaard",
              "team": "Arsenal"
            }
          ]
        }
      ]
    }
  ]
}
```

For non-PL leagues, `assist` will be `null` in goal events (to save API calls within the 100/day limit).

**API call budget per refresh:**
- 5 calls for today's fixtures (one per league)
- Events are included in fixture response with no extra calls when using fixture endpoint with events
- Total: ~5 calls per refresh, budget allows ~20 refreshes/day

### Modified: `src/fpl/api/app.py`

Register `scores.router` at `/api/scores`.

### Modified: `src/fpl/config.py`

Add `api_football_season: int = 2025` for the current season parameter.

## Frontend Changes

### New page: `pages/ScoresPage.tsx`

Route: `/scores`

**Layout:**
- Page header "Live Scores" with auto-refresh indicator
- Tabs for each league (PL, Serie A, La Liga, Bundesliga, Ligue 1) + "All" tab
- Each match shown as a card:
  - Match status badge (Live pulsing green, HT amber, FT muted, NS with kickoff time)
  - Home team — score — Away team (large, centered)
  - Elapsed time for live matches
  - Goal scorers listed below each match with minute + player name
  - PL matches also show assist provider
- Auto-refresh every 60 seconds when live matches exist
- Empty state: "No matches today" when no fixtures

### Modified: `components/AppLayout.tsx`

Add "Scores" nav item with `Radio` icon (like a broadcast) after Leagues.

### Modified: `App.tsx`

Add route `/scores` → `ScoresPage`.

### Modified: `lib/api.ts`

Add types and API method:
- `ScoresResponse`, `LeagueScores`, `MatchScore`, `MatchEvent`
- `api.getTodayScores()`, `api.getLiveScores()`

## Acceptance Criteria

1. Scores page shows today's fixtures grouped by league
2. Live matches show pulsing status indicator and elapsed time
3. Goal scorers shown for all leagues with minute
4. Assists shown for Premier League goals
5. Finished/upcoming matches display correctly
6. Page auto-refreshes when live matches exist
7. Works without API key (graceful error message)
8. All existing tests pass
9. Frontend build succeeds

## Files

| File | Action |
|------|--------|
| `src/fpl/api/routes/scores.py` | New: scores endpoints |
| `src/fpl/api/app.py` | Register scores router |
| `src/fpl/config.py` | Add season setting |
| `frontend/src/lib/api.ts` | Add types + methods |
| `frontend/src/pages/ScoresPage.tsx` | New: live scores page |
| `frontend/src/components/AppLayout.tsx` | Add Scores nav item |
| `frontend/src/App.tsx` | Add route |
| `docs/iterations/live-scores/plan.md` | This plan |
