# Plan: League Tables

## Goal

Add a league tables page showing current standings for 6 leagues: Premier League, Championship, Serie A, La Liga, Bundesliga, Ligue 1.

## API

ESPN public standings endpoint (no key, unlimited):
`GET https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings`

| League | Slug |
|--------|------|
| Premier League | eng.1 |
| Championship | eng.2 |
| Serie A | ita.1 |
| La Liga | esp.1 |
| Bundesliga | ger.1 |
| Ligue 1 | fra.1 |

Response: `children[0].standings.entries[]` with team info + stats (rank, gamesPlayed, wins, ties, losses, pointsFor, pointsAgainst, pointDifferential, points). Teams have `note.description` for qualification zones (Champions League, Relegation, etc).

## Changes

### Backend: `src/fpl/api/routes/scores.py`

Add endpoint `GET /api/scores/standings` that fetches standings for all 6 leagues from ESPN. Cache in memory (same pattern as score cache), refreshed by scheduler.

### Frontend: `pages/TablesPage.tsx`

New page at `/tables`. Tabs for each league. Table columns: #, Team, P, W, D, L, GF, GA, GD, Pts. Highlight qualification/relegation zones with subtle color coding.

### Navigation + routing

Add "Tables" nav item with `TableProperties` icon. Add route `/tables`.

## Acceptance Criteria

1. Tables page shows standings for all 6 leagues
2. Correct columns: position, team, played, W/D/L, GF/GA/GD, points
3. Qualification zones highlighted (CL, Europa, relegation)
4. Manual refresh button, auto-refresh during match windows
5. Build succeeds, tests pass

## Files

| File | Action |
|------|--------|
| `src/fpl/api/routes/scores.py` | Add standings endpoint |
| `src/fpl/scheduler.py` | Add standings to score cache refresh |
| `frontend/src/pages/TablesPage.tsx` | New page |
| `frontend/src/components/AppLayout.tsx` | Add nav item |
| `frontend/src/App.tsx` | Add route |
| `frontend/src/lib/api.ts` | Add types + method |
