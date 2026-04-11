# Code Review 1: Mini Leagues, Auto-Refresh, Bonus Column

## Verdict: APPROVED

All acceptance criteria met. 170 tests passing.

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Subscribe to a league by ID | PASS |
| 2 | Standings display with rank, manager, GW pts, total | PASS |
| 3 | Click row shows opponent's full team | PASS |
| 4 | Opponent team: GW points with captain multiplier, form, xPts, cost, status | PASS |
| 5 | Opponent team: bank, free transfers, total points, rank | PASS |
| 6 | Remove a subscribed league | PASS |
| 7 | Standings refresh on page load (if stale) or via force | PASS |
| 8 | League route tests pass | PASS (4 tests) |
| 9 | League ingest tests pass | PASS (4 tests) |
| 10 | Frontend build succeeds | PASS |
| 11 | Opponent transfers (in/out per GW) | PASS |
| 12 | Auto-refresh during Sat/Sun/Mon match windows | PASS |
| 13 | Auto-refresh configurable via FPL_AUTO_REFRESH | PASS |
| 14 | Bonus column on My Team and Opponent Team | PASS |

## Post-Review Fixes

- Narrowed auto-refresh to only `fpl`, `team`, `leagues` sources (not all 7) during match windows — understat/odds/injuries/projections don't change live

## Observations (non-blocking, future improvements)

- Duplicate `PlayerTable` component between MyTeamPage and OpponentTeamPage could be extracted
- Missing Tuesday/Wednesday midweek fixture windows in scheduler
- Free transfer calculation for opponents is approximate (FPL API doesn't expose it directly)
