# Plan: Match Detail View

## Goal

From the Scores page, clicking a match opens a detailed view showing:
- Team stats (possession, shots, passes, tackles, etc.)
- Starting XI + benches for both teams with jerseys, positions
- Key events (goals, cards, subs)

## Data Source

ESPN match summary endpoint (already using ESPN for scores):
```
GET https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={fixture_id}
```

Returns:
- `boxscore.teams[]` — team info + ~28 statistical fields per team
- `rosters[]` — starting XI and bench with player info, jerseys, positions
- `keyEvents[]` — goals, cards, subs with minute and player
- `header` — scoreline, status, venue
- `commentary` — play-by-play (optional)

## Backend

### New endpoint: `GET /api/scores/match/{fixture_id}?league={slug}`

Returns a shaped match detail with:
- `teams`: [home, away] with `{name, short, score, stats}`
- `rosters`: [home, away] with `{starters, subs, manager}`
- `events`: array of `{minute, type, player, team, text}`
- `venue`, `status`, `attendance`

The `fixture_id` is the ESPN event ID (already surfaced on the scores page as `match.fixture_id`). The league slug is needed because ESPN's summary endpoint is nested under league.

No cache needed — each match detail is fetched on demand when the user clicks.

## Frontend

### New page: `pages/MatchDetailPage.tsx`

Route: `/match/:leagueSlug/:fixtureId`

**Layout:**
- Back button
- Match header: team badges, teams, score, status/minute
- Tabs: Stats / Lineups / Events
- **Stats tab**: side-by-side bar comparison for each metric (possession as %, others as raw + bar proportional to max)
- **Lineups tab**: two columns (home/away) each with:
  - Starting XI grouped by position
  - Bench (substitutes)
- **Events tab**: timeline list with minute + event text

### Modified: `pages/ScoresPage.tsx`
Make the fixture cards clickable → navigate to match detail.

### Modified: `lib/api.ts`
Add `getMatchDetail(leagueSlug, fixtureId)` method.

### Modified: `App.tsx`
Add the new route.

## Acceptance Criteria

1. Click any match on Scores page → opens detail view
2. Team stats show all ~28 metrics with clear comparison
3. Starting XI and bench shown for both teams
4. Key events (goals, cards, subs) shown in chronological order
5. Works for finished, in-progress, and not-started matches
6. Back button returns to scores
7. Build passes, no regressions
