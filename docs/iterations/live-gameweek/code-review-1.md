# Code Review 1: Live Gameweek Page

## Verdict: APPROVED (after fixes)

Initial review identified 14 issues. Must-fix items (1, 4, 5, 7) all addressed.

## Must-Fix Items Resolved

| # | Issue | Fix |
|---|-------|-----|
| 1 | DGW fixture attribution wrong — was using top-level aggregate `stats` which doesn't split per-fixture | Rewrote to iterate `explain[]` entries and parse per-fixture stats from `identifier`/`value` pairs |
| 4 | Cache never invalidates on GW rollover or when stale | Added `_cache_is_fresh()` (5-min TTL) and `_cache_gw_matches()` checks in `get_live_gameweek` |
| 5 | Scheduler only refreshed during Sat/Sun/Mon, missing Friday/midweek fixtures | Changed to use wider `_in_score_window()` (Fri-Mon evenings + Sat/Sun days) |
| 7 | Empty live data overwriting good cache on transient FPL API failure | `refresh_live_cache` now keeps existing cache if new fetch returns empty |

## New Tests

- `test_live_gameweek_dgw_attribution` — Seeds 2 fixtures with a player playing in BOTH, verifies goals/BPS attributed to correct fixture (Saka has 1G/30 BPS in fix 500 and 2G/55 BPS in fix 501, not aggregated)

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Live GW page shows all fixtures for current GW | PASS |
| 2 | Each fixture shows score, status, goal scorers, assisters | PASS |
| 3 | Top 3 BPS per fixture with player, team, BPS, bonus, points | PASS |
| 4 | Top DEFCON contributors per fixture | PASS |
| 5 | Auto-refresh during match windows (frontend + backend) | PASS |
| 6 | Build + all tests pass | PASS (186 unit tests) |
| 7 | DGW attribution correct | PASS (new test) |

## Deferred (low priority)

- Remove `any` types in `LiveGameweekPage.tsx` — follow-up cleanup
- Scope player query to current-GW teams only — micro-optimization
- `finished_provisional` check — edge case around bonus calculation window
- Typed `LiveFixture` interface in api.ts
