# Plan: Current GW Points + Test Gap Coverage

## Problem

1. The My Team page and Dashboard show only projected/expected points — not actual points scored in the current gameweek.
2. The API route tests and team data flow are untested.

## Analysis

**How current GW points work in FPL:**
- The FPL bootstrap-static API returns `event_points` per player element — the points scored in the current gameweek.
- We currently don't capture this field. We store `total_points` (season cumulative) but not per-GW.
- `PlayerGameweekStats.total_points` has per-GW points but requires a join by gameweek number.
- `MyAccount.gameweek_points` stores the user's total GW score (from entry_history) but we don't expose it in the API response.

**Simplest approach: Add `event_points` to the Player model.** The FPL API already provides it in bootstrap-static. We just need to store it and expose it. No extra API calls or complex joins needed.

## Changes

### 1. Backend: Add `event_points` to Player model

**File: `src/fpl/db/models.py`**
- Add `event_points: Mapped[int] = mapped_column(default=0)` to the Player class.

**File: `src/fpl/ingest/fpl_api.py`**
- Add `"event_points": e.get("event_points", 0)` to the `upsert_players` values dict.

### 2. Backend: Expose GW points in team API

**File: `src/fpl/api/routes/team.py`**
- In `get_team()`: Add `event_points` (raw) and `gw_points` (event_points * multiplier) to each player dict.
- Add `gameweek_points` (from MyAccount) to the top-level response — this is the user's actual GW total.

### 3. Frontend: Show GW points

**File: `frontend/src/pages/MyTeamPage.tsx`**
- Add "GW Pts" column to the team table showing `gw_points` (multiplied). Captain row shows 2x.

**File: `frontend/src/pages/DashboardPage.tsx`**
- Add actual GW points total alongside the projected xPts in the Team Summary card.

### 4. Tests

**Gaps identified:**
- No tests for API routes at all (team, data, players, fixtures, etc.)
- No tests for `event_points` population
- No tests for team GW points calculation
- No tests for the data refresh endpoint

**New test files:**
- `tests/test_api/test_team_route.py` — Tests for GET /api/me/team and GET /api/me/analyse
- `tests/test_api/test_data_route.py` — Tests for GET /api/data/status and POST /api/data/refresh
- `tests/test_ingest/test_fpl_api.py` — Add test for `event_points` in `upsert_players`

## Acceptance Criteria

1. `Player.event_points` field exists and is populated from FPL API bootstrap
2. `GET /api/me/team` response includes `event_points`, `gw_points`, and top-level `gameweek_points`
3. My Team table shows a "GW Pts" column with multiplied points
4. Dashboard shows actual GW points total
5. New API route tests pass
6. Existing tests still pass
7. Build succeeds

## Files Changed

| File | Change |
|------|--------|
| `src/fpl/db/models.py` | Add `event_points` field |
| `src/fpl/ingest/fpl_api.py` | Capture `event_points` in upsert |
| `src/fpl/api/routes/team.py` | Expose GW points in response |
| `frontend/src/pages/MyTeamPage.tsx` | Add GW Pts column |
| `frontend/src/pages/DashboardPage.tsx` | Show actual GW points |
| `tests/test_api/__init__.py` | New test package |
| `tests/test_api/test_team_route.py` | New: team API tests |
| `tests/test_api/test_data_route.py` | New: data API tests |
| `tests/test_ingest/test_fpl_api.py` | Add event_points test |
