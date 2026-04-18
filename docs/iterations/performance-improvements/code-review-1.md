# Code Review 1 — Performance Improvements

**Verdict: CHANGES REQUESTED**

The core of the plan is implemented correctly and the cache abstraction is clean. Single-flight works, the `team.py` projection is correct, and the form N+1 is resolved. However, there are several real issues that should be fixed before merging: a subtle data-freshness bug, a resource leak pattern, and a test that does not actually exercise single-flight as it appears to.

---

## Correctness

### 1. Cache miss returning `{}` poisons the cache for 30 s  (HIGH)

`_fetch_live_gw_with_explain` swallows all exceptions and returns `{}` on failure (`live.py` line 392-393). `get_live_gw` stores that empty dict in the cache with a fresh timestamp and will happily serve it for 30 seconds. During a flaky network blip at kickoff, every user sees an empty live view for half a minute even though the next poll would have succeeded.

Recommendation: either don't cache empty responses, or raise and let the caller decide. At minimum:

```python
data = await fetcher(gw)
if data:  # don't cache a failure
    _cache[gw] = (time.monotonic(), data)
return data
```

### 2. `_locks` grows unbounded and is never cleaned  (LOW/MEDIUM)

`_locks.setdefault(gw, asyncio.Lock())` keeps a `Lock` for every GW ever requested. Over a full season that's 38 entries — negligible in practice, but `invalidate(gw)` deliberately leaves the lock behind (only `_cache` is popped). If the module is ever imported in a context where GW ids can be arbitrary (tests pass `99`), the map grows. Minor; worth popping the lock in `invalidate()` for symmetry, or documenting why it's kept.

### 3. Lock created at module import time is bound to the wrong event loop  (MEDIUM, latent)

`asyncio.Lock()` in modern Python 3.10+ lazily binds to the running loop on first `acquire`, so this is fine under uvicorn. But tests that create a new loop per test (not the case here — `asyncio_mode = "auto"` uses one per test) could hit `RuntimeError: ... attached to a different loop`. The autouse `clear_cache` fixture wipes `_locks` between tests, which masks the issue. Document or leave as is — flagging for awareness.

### 4. `invalidate()` call sites  (MEDIUM)

The plan called for cache invalidation "at the right times." I can find no call to `invalidate()` outside tests. `refresh_live_cache` (the scheduler hook) now just calls `fetch_live_gameweek()` which respects the 30 s TTL — so the scheduler's 60 s tick cannot force a fresh pull. That may be intentional (the TTL handles it) but it means:

- On GW rollover, the previous GW's entry stays in `_cache` (harmless — different key).
- If the admin hits "refresh" expecting fresh data, they get whatever is < 30 s old.

The docstring on `refresh_live_cache` says "No longer maintains a cache — the endpoint always fetches fresh." That's no longer true — the endpoint now has a 30 s TTL. Update the docstring, and consider calling `invalidate(current_gw)` from the scheduler tick so the next user request gets fresh data while the TTL still protects against thundering herds.

### 5. Fire-and-forget `_auto_setup` task is orphaned  (MEDIUM)

`asyncio.create_task(_auto_setup())` in the lifespan context manager:
- The returned task is not stored anywhere. If it raises a non-Exception (e.g. CancelledError on shutdown), it may log "Task exception was never retrieved".
- On shutdown (`yield` returns), the task may still be running. It'll be cancelled when the loop closes, potentially mid-DB-write, leaving partial state.

Minimum fix: keep a reference and cancel/await it cleanly on shutdown.

```python
setup_task = asyncio.create_task(_auto_setup())
start_scheduler()
try:
    yield
finally:
    stop_scheduler()
    setup_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await setup_task
```

Also add a done-callback that logs exceptions so silent failures during startup are surfaced.

### 6. SQLAlchemy session across threads — looks safe  (OK)

`_load_db_snapshot` and `_load_team_db_snapshot` open a fresh `get_session()` inside the thread and close it via context manager before returning. Snapshots are plain dicts/tuples, detached from the session. No leakage. Good.

### 7. `team.py` projection of `provisional_bonus`  (OK)

The projection `{**entry.get("stats", {}), "provisional_bonus": entry.get("provisional_bonus", 0)}` correctly lifts `provisional_bonus` to a top-level key so `get_team` can read `live_stats.get("provisional_bonus")`. `confirmed_bonus if confirmed_bonus > 0 else provisional_bonus` is the right ordering. Correct.

### 8. Form N+1 fix  (OK with nit)

The single `in_()` query plus Python grouping is correct. Nit: `from collections import defaultdict` should be at the top of the file, not inside the function (PEP 8). ruff would flag this.

---

## Data integrity

- **30 s TTL staleness**: In the worst case a user sees 29 s old data, which is acceptable for live-match UX. Goal/bonus/BPS updates from FPL are not faster than this anyway.
- **GW rollover**: different GW keys, so no cross-contamination. Fine.
- **Empty-cache poisoning** — see issue #1 above. This is the main integrity concern.

---

## Code quality

- `_live_cache = {}` stub in `live.py` (line 28) with comment "Exposed for tests that need to clear cache state between runs" is a smell. Nothing references it; the real cache lives in `fpl.cache.live_gw`. Either delete it or repurpose the comment. Dead code.
- `import time` inside `_fetch_live_gw_with_explain` (line 357) — move to module top. Same for `import httpx` and `from fpl.config import get_settings` at line 343-345. Style violation per CLAUDE.md standards.
- `_fetch_live_gw_with_explain` is defined in `live.py` but imported lazily in `team.py` (`from fpl.api.routes.live import _fetch_live_gw_with_explain`). Circular-import avoidance, but the fetcher arguably belongs in `fpl/cache/live_gw.py` or a sibling module — it's not route logic. Consider moving to avoid the cross-route import.
- `refresh_live_cache` is now essentially a no-op that does a fetch and stamps a timestamp. Either delete it and update the scheduler, or make it do something useful (e.g. `invalidate(gw)` then fetch).
- Type hints on `_load_team_db_snapshot` return type are `dict[str, Any] | None` — fine but the caller unpacks eight keys, so a `TypedDict` would be clearer. Minor.
- `from collections.abc import Callable, Coroutine` / `Callable[[int], Coroutine[Any, Any, dict[...]]]` is correct but `Callable[[int], Awaitable[...]]` is slightly more idiomatic and accepts more callables (e.g. async functions wrapped in partials). Optional.

---

## Tests

### Cache tests

- `test_single_flight_concurrent_callers_fetch_once` — **does not reliably test single-flight.** It launches 10 tasks, then `await fetch_started.wait()`. But until the event loop schedules the first task's `async with lock`, no other task has queued. Because `await` yields control, ordering is generally: task 1 acquires the lock and awaits `can_complete`; tasks 2-10 queue at the lock. That's the case the test passes. However, if the scheduler interleaved differently (e.g. all 10 pass the TTL check, then task 1 acquires lock and fetches), the test still passes for the wrong reason. To make it bulletproof: assert that by the time `can_complete.set()` fires, tasks 2-10 are blocked on the lock (e.g. check `len(lock._waiters)` or use an `asyncio.Barrier`). As written, it's a reasonable smoke test — not load-bearing.
- `clear_cache` autouse fixture correctly wipes both `_cache` and `_locks` before and after. Good, prevents state leak.
- Tests use `from fpl.cache.live_gw import ...` which is the post-refactor symbol — targeting is correct.

### Live route tests

- `patch("fpl.api.routes.live._fetch_live_gw_with_explain", _mock_live_fetch)` — correct symbol after the refactor (the fetcher still lives in `live.py`).
- `invalidate_live_cache(32)` is called before each test to prevent cross-test leakage. Good.
- No test covers the empty-response poisoning case (issue #1) or the team.py projection path. Worth adding a short test that asserts `get_team` receives `provisional_bonus` via the shared cache.

---

## Plan adherence

| Item | Status | Notes |
|------|--------|-------|
| P1: shared 30 s TTL cache w/ single-flight | Done | Issue #1 on empty responses |
| P1: used by both `live.py` and `team.py` | Done | Projection correct |
| P2b: non-blocking `_auto_setup` | Done | Issue #5 on orphan task |
| P0: `asyncio.to_thread` for sync DB | Done | `get_team` and `live` both offload |
| P2a: ingest upserts off event loop | Done | `run_fpl_ingest` wraps upserts in `to_thread` |
| P3: form N+1 fix | Done | Minor nit on import location |

**Beyond-plan changes**: `refresh_live_cache` was gutted to a near-no-op but not deleted or re-scoped. Should be tidied.

---

## Required changes before APPROVED

1. **Don't cache empty/failure responses** in `get_live_gw` (issue #1).
2. **Hold the `_auto_setup` task reference** and await/cancel it in the lifespan's shutdown path (issue #5).
3. **Either delete `refresh_live_cache` or make it call `invalidate()`** before fetching, and update its docstring (issue #4 / code quality).
4. **Remove the `_live_cache = {}` dead stub** in `live.py`.
5. **Hoist inline imports** (`import time`, `import httpx`, `from collections import defaultdict`) to module top per CLAUDE.md standards.

## Nice-to-have (not blocking)

- Move `_fetch_live_gw_with_explain` out of `live.py` (e.g. into `fpl/cache/live_gw.py` or `fpl/ingest/fpl_api.py`) to eliminate the cross-route import from `team.py`.
- Strengthen `test_single_flight_concurrent_callers_fetch_once` to assert waiters are actually blocked on the lock.
- Add an integration-level test asserting `get_team` observes `provisional_bonus` via the cache projection.
- Pop `_locks[gw]` in `invalidate()` for symmetry.
