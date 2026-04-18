# Performance Improvements — Plan

## 1. Diagnosis

Three compounding problems make the app feel slow, in priority order:

### 1.1 Sync SQLAlchemy inside `async def` handlers blocks the event loop

`get_session()` returns a synchronous SQLAlchemy session (stdlib `sqlite3` driver). Every route — `live.py`, `team.py`, `fixtures.py`, `players.py` — calls `session.query(...)` directly on the event loop inside `async def` handlers.

While a query runs, the single FastAPI event loop thread is blocked. No other request can progress. `live.py` and `team.py` each call `session.query(Player).all()` (600+ rows, fully hydrated ORM objects) plus several other queries per request — 20–80 ms of blocked loop per call. Under concurrent load (React TanStack Query fires 4–6 parallel queries on page load) this serialises everything.

### 1.2 Every `/api/live/gameweek` and `/api/me/team` triggers an FPL API round-trip

- `live.py` calls `_fetch_live_gw_with_explain` on every `GET /api/live/gameweek` — a 200–500 ms external HTTP GET with a cache-busting timestamp param.
- `team.py` calls `_fetch_live_gw` on every `GET /api/me/team` — same endpoint, same cost, not shared with `live.py`.
- A page rendering both components pays the cost **twice**.
- TanStack Query refetches on tab focus, window focus, and periodic intervals — so a user switching tabs re-pays 400–1000 ms per visit.

The FPL `event/{gw}/live/` payload is 1–3 MB; parsing explain/BPS in Python adds another 30–100 ms.

This is likely the single biggest user-visible latency.

### 1.3 APScheduler jobs run on the event loop and block it for seconds

Three `AsyncIOScheduler` jobs run in the same event loop. Internally, `run_fpl_ingest` calls synchronous `upsert_players`, `upsert_fixtures`, `upsert_player_histories` (each an `executemany` of 100s–1000s of rows) directly on the event loop. During match windows all three jobs overlap, monopolising the loop for seconds at a time — exactly when users have the app open.

The startup `_auto_setup` call in `lifespan` also blocks the app from serving any request until the first full ingest completes (30–60 s on cold start).

### 1.4 N+1 queries in form endpoint

`players.py:get_form` issues a separate `PlayerGameweekStats` query per player (up to 20 queries serialised). Minor compared to the above but trivial to fix.

---

## 2. User question answered

> "Is it because I am refreshing so much data, or because it is all done synchronously?"

**Primarily the latter.** The refresh volume isn't the problem — it's that sync DB work and external HTTP calls happen on the single event loop thread, serialising every concurrent request. The live-endpoint per-request FPL fetch is the most user-visible symptom.

---

## 3. Proposed fixes (prioritised by ROI)

### P1 — Short-TTL in-memory cache for `event/live/` (biggest UX win)

Add a shared cache module `src/fpl/cache/live_gw.py` with a 30 s TTL and single-flight semantics (concurrent callers during a cache miss await the same future, not 10 parallel FPL requests).

Both `live.py` and `team.py` import from this module. The scheduler's `refresh_live_cache` primes it. Worst-case staleness is 30 s — acceptable for live match data and avoids the old 5-minute stale-data bug.

**Expected impact:** Eliminates 200–500 ms from ~95% of live and team requests. Tab-focus refetches hit hot cache in < 10 ms.

### P0 — Offload sync DB work to the thread pool

FastAPI runs plain `def` (non-async) route handlers in a default thread pool automatically. The simplest migration: convert DB-only routes from `async def` to `def`. For mixed routes (DB + external HTTP), extract the DB block into a sync helper and call it via `asyncio.to_thread`.

```python
# Mixed route pattern
def _load_team_from_db(user_id: int) -> dict:
    with get_session() as session:
        ...
        return snapshot

async def get_team(...):
    db_data = await asyncio.to_thread(_load_team_from_db, user_id)
    live_data = await get_live_gw_cached(current_gw)  # shared cache
    return _build_response(db_data, live_data)
```

The default thread pool has 40 workers — plenty for SQLite WAL-mode concurrent reads.

### P2b — Non-blocking app startup

Move `_auto_setup` to a background task so the app serves requests immediately on startup:

```python
async def lifespan(app):
    init_db()
    asyncio.create_task(_auto_setup())  # fire and forget
    start_scheduler()
    yield
    stop_scheduler()
```

### P2a — Move ingest upserts off the event loop

Wrap the blocking DB upsert calls inside `run_fpl_ingest` with `asyncio.to_thread`. The HTTP fetching (already async) stays on the loop; only the sync bulk-upsert moves to a worker thread.

### P3 — Fix N+1 in form endpoint

Replace 20 serial `PlayerGameweekStats` queries with one `WHERE player_id IN (...)` query, grouped in Python.

---

## 4. Out of scope

- Postgres migration
- Async SQLAlchemy / aiosqlite (driver immaturity, churn not worth it)
- Moving scheduler to a separate process
- Redis / external cache
- Trimming ingest data volume

---

## 5. Acceptance criteria

1. `GET /api/live/gameweek` p50: **< 50 ms** on cache hit, < 600 ms on miss (vs ~400 ms today)
2. `GET /api/me/team` p50: **< 80 ms** on live-cache hit (vs ~500 ms today)
3. 20 concurrent `/api/players/form` requests complete in **< 400 ms total** (vs ~4 s serialised today)
4. App start to first request served: **< 2 s** (vs 30–60 s today)
5. During scheduler tick, a concurrent simple DB read completes in **< 100 ms**
6. Live data never more than **30 s stale** under match load

---

## 6. Test plan

### New tests
- `tests/cache/test_live_gw_cache.py`
  - Cache hit returns same object without re-calling FPL
  - TTL expiry triggers refetch
  - Single-flight: 10 concurrent callers on miss → exactly 1 upstream fetch
- `tests/api/test_concurrency.py`
  - 20 concurrent requests to a DB-heavy endpoint; total wall time < N × single-request time

### Updated tests
- `test_live_route.py` — patch the shared cache module, not `_fetch_live_gw_with_explain` directly; add fixture to clear cache between tests
- `test_team.py` — same cache-clearing fixture

---

## 7. Execution order

| Priority | Change | Effort | Impact |
|----------|--------|--------|--------|
| P1 | Shared live-GW cache (30 s TTL, single-flight) | 2 h | Huge — eliminates per-request FPL round-trips |
| P2b | Non-blocking lifespan startup | 15 min | Cold-start UX |
| P0 | Threadpool offload for DB-heavy routes | 3 h | Concurrency under load |
| P2a | Ingest upserts off event loop | 2 h | Match-window scheduler impact |
| P3 | Fix N+1 in form endpoint | 20 min | Minor |

Ship P1 + P2b as the first change — they're orthogonal, low risk, and immediately visible to the user. P0 + P2a as a follow-on.
