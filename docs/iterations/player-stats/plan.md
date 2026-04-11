# Plan: Player Statistics Search

## Goal

Add a player statistics page where you can search any player across European leagues and view detailed season stats relevant to their position, with ratings and xG/xA where available.

## Data Sources

### Primary: API-Football (already configured)
- **Search:** `GET /players?search={name}&league={id}&season={year}`
- **Player stats:** `GET /players?id={id}&season={year}` — returns full stats per competition
- **Auth:** `x-apisports-key` header (FPL_API_FOOTBALL_KEY)
- **Limit:** 100 req/day, each search/lookup = 1 request

### Supplementary: Understat (already in codebase)
- **Player page:** `https://understat.com/player/{id}` — JSON embedded in script tags
- **Data:** xG, xA, npxG, xGChain, xGBuildup per season
- **Coverage:** Big 5 leagues only
- **No auth required**

## API-Football Response Shape

`GET /players?id=276&season=2025` returns:
```json
{
  "response": [{
    "player": {
      "id": 276, "name": "Bukayo Saka", "firstname": "Bukayo",
      "lastname": "Saka", "age": 24, "nationality": "England",
      "height": "178 cm", "weight": "72 kg", "photo": "..."
    },
    "statistics": [{
      "team": { "id": 42, "name": "Arsenal", "logo": "..." },
      "league": { "id": 39, "name": "Premier League", "country": "England", "season": 2025 },
      "games": { "appearences": 30, "lineups": 28, "minutes": 2500, "position": "Attacker", "rating": "7.2" },
      "goals": { "total": 14, "conceded": null, "assists": 11 },
      "shots": { "total": 80, "on": 35 },
      "passes": { "total": 1200, "key": 65, "accuracy": 82 },
      "tackles": { "total": 30, "blocks": 5, "interceptions": 15 },
      "duels": { "total": 300, "won": 150 },
      "dribbles": { "attempts": 120, "success": 70 },
      "fouls": { "drawn": 45, "committed": 20 },
      "cards": { "yellow": 3, "red": 0 },
      "penalty": { "won": 2, "committed": 0, "scored": 2, "missed": 0 }
    }]
  }]
}
```

## Backend Changes

### New file: `src/fpl/api/routes/stats.py`

3 endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET /api/stats/search?q={name}` | Search players by name via API-Football |
| `GET /api/stats/player/{id}?season={year}` | Get full stats for a player for a season |
| `GET /api/stats/player/{id}/xg` | Get xG data from Understat (if player found) |

The search endpoint returns a list of matches with player ID, name, team, league, nationality, position, photo.

The player detail endpoint returns the full stats grouped by competition, with position-relevant stat highlighting.

### Modified: `src/fpl/api/app.py`
Register `stats.router` at `/api/stats`.

## Frontend Changes

### New page: `pages/StatsPage.tsx`
Route: `/stats`

**Layout:**
- Search bar at top (searches on Enter)
- Search results as clickable cards showing player name, team, league, nationality, position
- Clicking a player shows their full season stats in a detailed view:
  - Player header: name, team, position, nationality, age, rating
  - Season selector (dropdown for different years)
  - Stats grid adapted to position:
    - **All:** Apps, minutes, goals, assists, cards, rating
    - **Attackers/Midfielders:** shots, key passes, dribbles, xG, xA
    - **Defenders:** tackles, interceptions, blocks, duels, clean sheets
    - **Goalkeepers:** saves, clean sheets, goals conceded, penalty saves
  - xG/xA section if Understat data available

### Modified: `components/AppLayout.tsx`
Add "Stats" nav item with `BarChart3` icon.

### Modified: `App.tsx`
Add route `/stats`.

### Modified: `lib/api.ts`
Add types and API methods.

## Acceptance Criteria

1. Search finds players across all European leagues
2. Player detail shows season stats with position-relevant layout
3. Stats include: apps, goals, assists, minutes, rating, shots, passes, tackles, cards
4. GK stats show saves, clean sheets
5. xG/xA shown when Understat data available
6. Season selector allows viewing different years
7. Graceful error when API key not configured
8. Build succeeds, tests pass

## Files

| File | Action |
|------|--------|
| `src/fpl/api/routes/stats.py` | New: search + player detail endpoints |
| `src/fpl/api/app.py` | Register stats router |
| `frontend/src/pages/StatsPage.tsx` | New: player stats page |
| `frontend/src/components/AppLayout.tsx` | Add nav item |
| `frontend/src/App.tsx` | Add route |
| `frontend/src/lib/api.ts` | Add types + methods |
