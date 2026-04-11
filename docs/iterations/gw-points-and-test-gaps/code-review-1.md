# Code Review 1: Current GW Points + Test Gaps

## Verdict: APPROVED

All acceptance criteria met.

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `Player.event_points` field exists | PASS — added with `default=0` |
| 2 | `event_points` captured from FPL API bootstrap | PASS — `e.get("event_points", 0)` in upsert_players |
| 3 | `GET /api/me/team` includes `event_points`, `gw_points`, `gameweek_points` | PASS |
| 4 | Captain multiplier applied to `gw_points` | PASS — `event_pts * mtp.multiplier` |
| 5 | My Team table shows GW Pts column | PASS — green highlight for 8+ pts |
| 6 | Dashboard shows actual GW points total | PASS — hero stat is now `gameweek_points` |
| 7 | New API route tests pass | PASS — 7 new tests (4 team, 3 data) |
| 8 | `event_points` ingest tests pass | PASS — 2 new tests (capture + default) |
| 9 | All existing tests pass | PASS — 162 total |
| 10 | Lint + type check | PASS |
| 11 | Frontend build | PASS |

## Test Coverage Added

- `tests/test_api/test_team_route.py` (4 tests): GW points in response, captain multiplier, 404 when no team, player field completeness
- `tests/test_api/test_data_route.py` (3 tests): empty status, dedup per source, failed ingest error_message
- `tests/test_ingest/test_fpl_api.py` (2 tests): event_points captured, defaults to 0 when missing
- `tests/test_api/conftest.py`: Shared fixture using tmp_path SQLite for thread-safe route testing

## Notes

- API route tests use monkey-patched `get_session` on the specific route module (not `unittest.mock.patch`) because sync FastAPI endpoints run in a worker thread where `patch` context managers don't apply
- Tests use file-based SQLite (`tmp_path`) instead of in-memory, because in-memory SQLite is per-connection and can't be shared across the worker thread that FastAPI spawns for sync endpoints
