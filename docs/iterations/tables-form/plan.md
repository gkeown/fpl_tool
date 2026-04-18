# Plan: "Last 5 Games Form" for Tables Page

## Key Finding

The Tables page does **not** use the local DB `Fixture` table. Standings come from ESPN's API (`scores.py`), covering 7 European leagues (PL, Championship, SPL, Serie A, La Liga, Bundesliga, Ligue 1). The DB `Fixture` table only covers the Premier League with FPL team IDs, and has no name linkage to ESPN rows. Therefore form must come from ESPN scoreboard history — the same source as the standings.

---

## Backend changes (`src/fpl/api/routes/scores.py`)

### New: `_compute_team_form(events, team_id) -> list[str]`
Pure function. Given a list of ESPN finished events and a team ID:
1. Filter to `state == "post"` with scores present.
2. Sort by kickoff ascending.
3. For each event determine W/D/L from the team's perspective (home or away).
4. Return last 5 results, ordered oldest → newest.

### New: `_fetch_league_form(client, slug, dates) -> dict[str, list[str]]`
Fetch ~9 weeks of ESPN scoreboard history for a league. Keyed by `team.id` (robust — avoids name-matching drift). Returns `{team_id: ["W","D","L","W","W"]}`.

### Wire into `fetch_standings`
After parsing the standings table, run `_fetch_league_form` per league (using `asyncio.gather` across leagues where possible). Attach `row["form"] = form_map.get(row["team_id"], [])` to every row. Missing = `[]`.

### Endpoint shape (additive)
```json
{
  "leagues": [{
    "id": "eng.1",
    "table": [{
      "position": 1, "team": "Liverpool", ...,
      "form": ["W","W","D","L","W"]
    }]
  }]
}
```

---

## Frontend changes (`frontend/src/pages/TablesPage.tsx`)

### New component: `FormBadges`
Props: `form: string[]`. Renders 0–5 pill badges:
- `W` → green (`bg-fpl-green text-white`)
- `D` → amber (`bg-amber-400 text-black`)
- `L` → red/pink (`bg-fpl-pink text-white` or `bg-red-500`)
- Oldest left → newest right
- Hidden below `sm` breakpoint (`hidden sm:table-cell`)

Add `Form` column header between `GD` and `Pts`.

---

## Scope

All 7 leagues in the Tables page. FPL mini-leagues (fantasy points) out of scope. No new DB tables, no migrations.

---

## Test Plan

`tests/test_api/test_scores_form.py` (new):
1. `_compute_team_form` basic W/D/L classification
2. Skips unfinished/missing-score events
3. Caps at last 5 (older results dropped)
4. Fewer than 5 results handled
5. `fetch_standings` attaches form to each row (mocked httpx)
6. Unknown team gets `form == []`

---

## Acceptance Criteria

1. `/standings` rows each have `form: string[]`, values `W/D/L`, oldest→newest, length ≤ 5
2. Tables page renders coloured pills per row across all 7 league tabs
3. Missing form (promoted club, name mismatch) renders empty — no crash
4. Form column hidden on mobile, visible sm+
5. No extra frontend round-trip; form included in existing cache refresh
6. No new DB columns, no migrations
