# Code Review 1 — Tables Page "Last 5 Games Form"

**Verdict: APPROVED (with minor, non-blocking suggestions)**

Reviewed files:
- `/Users/gerardkeown/fantasy_football/src/fpl/api/routes/scores.py`
- `/Users/gerardkeown/fantasy_football/frontend/src/pages/TablesPage.tsx`
- `/Users/gerardkeown/fantasy_football/tests/test_api/test_scores_form.py`

## Summary

The implementation matches the approved plan. `_compute_team_form` is a pure, correct function; `_fetch_league_form` performs parallel weekly date sampling with proper dedup; standings rows are enriched via a `team_id` lookup with a clean `[]` fallback; and the frontend renders colored W/D/L badges using the project's Tailwind tokens. Tests cover the key branches with realistic ESPN shapes.

---

## Correctness

### `_compute_team_form` (scores.py:517-574)
- Team identification uses `str(c.get("id", ""))` on both sides — matches the `team_id` stored by `_parse_standing` (also stringified). Correct.
- W/D/L classification is perspective-agnostic — it compares `our_score` vs `other_score` rather than home vs away. Correct for both sides.
- State filter `state != "post"` correctly excludes `pre`, `in`, `canceled`, etc.
- Score validity check rejects `None` and `""` before casting — prevents silent 0-0 draws from unfinished matches.
- Date sort uses lexicographic ISO8601 comparison. Safe for standard ESPN `YYYY-MM-DDTHH:MM:SSZ` strings. **Minor caveat**: if ESPN ever returns a timezone offset like `+00:00` instead of `Z`, lexicographic order would still hold for same-UTC matches, but mixed-offset strings could mis-sort. Not observed in practice; acceptable.
- `results[-5:]` returns oldest-first within the last 5 window. Matches the plan.

### `_fetch_league_form` (scores.py:577-627)
- Weekly step with `lookback_days=63` generates 10 sample dates (`0,7,...,63`) — plan said ~9; this is effectively the same. Fine.
- `asyncio.gather` runs them in parallel — good.
- Dedup by event id before aggregation — correct.
- Collects `team_ids` dynamically from events, then calls `_compute_team_form` per team. Works, but is O(teams * events). With ~20 PL teams and ~60-80 dedup'd events that's ~1.5k iterations per league — trivial.
- Each league triggers 10 ESPN scoreboard calls in `fetch_standings`. Across 7 standings leagues, that's ~70 extra requests per refresh — up from ~7. Reasonable given ESPN is unkeyed/unlimited and standings cache is driven by the scheduler (not per-request), but worth noting. **Consider**: sharing the event pool with the live-results fetch (`_fetch_espn_league(..., today)`) already happening on scores.py:651 — today's fetch is duplicated inside `_fetch_league_form` for step=0. Optimization, not a blocker.

### `fetch_standings` wiring (scores.py:658-666)
- `form_map.get(row.get("team_id", ""), [])` — correct fallback. Promoted clubs and any team whose id was missed still get `form: []`.
- The outer `try/except` assigns `[]` to every row if the call fails wholesale. Good defensive path.

### `_parse_standing` (scores.py:391-409)
- `team_id` is stringified via `str(team_info.get("id", ""))`. Matches `_compute_team_form`'s comparison.

## Performance / Robustness
- ~70 extra HTTP calls per standings cache refresh. Driven by scheduler; user-facing `/api/scores/standings` serves from cache when available. Acceptable.
- Each ESPN call in `_fetch_league_form` is wrapped in `try/except Exception: return []` — individual failures don't poison the batch. Good.
- Score parsing uses `int(...)` inside `try/except (ValueError, TypeError, KeyError)` — safe.
- Competitor list length is validated (`len(competitors) != 2`) before indexing — safe.

## Code Quality
- `from __future__ import annotations` present (scores.py:8).
- `asyncio` imported at module top (scores.py:10). Good.
- Type hints complete on new functions. `settings: Any` on `_fetch_league_form` is the one weak spot — `get_settings()` returns `Settings`, so annotating `fpl.config.Settings` would be stricter. The parameter is also currently unused inside the body (lookback is passed separately). Consider dropping the `settings` parameter entirely if it isn't needed, or annotating it properly. **Non-blocking.**
- No inline imports, no CLAUDE.md violations found.

## Tests (test_scores_form.py)
- Synthetic events include `id`, `date`, `status.type.state`, `competitions[0].competitors[*]` with `id`, `homeAway`, `score`, `team.displayName` — matches the real ESPN scoreboard shape exercised by `_parse_espn_match` and `_apply_live_results`.
- Six tests cover: W/D/L correctness from both perspectives, skipping in/pre states, 5-cap with correct oldest-first ordering, fewer-than-5 passthrough, unknown team id, and missing/empty scores.
- All tests are pure and independent — no shared mutable state, no fixture pollution risk.
- **Gap (minor)**: no test specifically asserts the oldest→newest ordering when input events arrive out of date order. The cap test implicitly exercises this because events are already sorted, but a shuffled-input test would pin the sort contract. Not required.
- **Gap (minor)**: no test for `_fetch_league_form` dedup behaviour. It's harder to unit-test (async + httpx), but one pytest-httpx test would be a strong addition given it's the integration seam. Not blocking per the plan.

## Frontend (TablesPage.tsx)

### `FormBadges` (lines 43-63)
- Handles `undefined` via `if (!form || form.length === 0)` — renders em-dash. Good.
- Handles empty array — same branch. Good.
- Partial arrays (length 1-4) render correctly.
- Uses `bg-fpl-green` and `bg-red-500` — consistent with the rest of the file (see zone borders using `fpl-green`, `fpl-pink`, `fpl-gold`, confirmed in `tailwind.config.ts`). Draw uses `bg-amber-400` which is not a project token but is used acceptably here; `bg-fpl-gold` would match the plan's "amber" intent and be more consistent with other file usage. **Minor nit, not blocking.**
- Loss uses `bg-red-500` (generic Tailwind). `bg-fpl-pink` (#e90052) would match the relegation zone border style used elsewhere in the same file. **Minor stylistic suggestion.**

### Table integration
- `<th>` (line 80) and `<td>` (line 112) both use `hidden sm:table-cell`. Correct — avoids row-shift on mobile.
- `row.form ?? []` on line 113 — defensive access confirmed.
- Column placement between GD and Pts matches the plan.

## Top Issues / Suggestions
1. (Nit) `_fetch_league_form` accepts `settings: Any` but never uses it. Either drop the parameter or annotate it properly.
2. (Nit) Draw badge uses `bg-amber-400`; loss uses `bg-red-500`. For theme consistency consider `bg-fpl-gold` / `bg-fpl-pink`.
3. (Nit) `_fetch_league_form` duplicates the `today` scoreboard fetch already made for live results. Could share to save one call per league (7 calls/refresh).
4. (Optional) Add a pytest-httpx test for `_fetch_league_form` to cover dedup across overlapping date windows.

None of the above block approval. The feature works as specified, the code is typed and defensive, and the tests cover the computational core.

**Verdict: APPROVED**
