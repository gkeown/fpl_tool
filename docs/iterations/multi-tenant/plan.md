# Plan: Multi-Tenant Authentication

## Goal

Add two user roles — **Admin** (full access) and **Guest** (restricted access) — with per-user FPL team/league data. Guests can share the app URL and set up their own team, but see a restricted feature set.

## Roles & Permission Matrix

| Feature | Admin | Guest |
|---------|-------|-------|
| Dashboard | Full | Own team data |
| My Team (GW stats) | Full | Full |
| My Team → Upcoming Fixtures | Yes | **No** |
| Live GW | Full | Full |
| Leagues (standings) | Full | Own leagues |
| Opponent Team → Chips Used | Yes | **No** |
| Opponent Team → Recent Transfers | Yes | **No** |
| Fixtures (FDR heatmap) | Yes | **No** |
| Transfers (suggestions) | Yes | **No** |
| Prices (risers/fallers) | Yes | **No** |
| Scores | Full | Full |
| Tables | Full | Full |
| Stats | Full | Full |
| Settings | Full | **No** (own setup only) |

## Authentication Design

### Approach: JWT tokens + password/invite code

Simple, stateless, fits the personal-tool context. No external auth service needed.

**Config (.env):**
```
FPL_ADMIN_PASSWORD=mysecretpassword
FPL_GUEST_CODE=sharethiswithfriends
FPL_JWT_SECRET=random-256-bit-secret
```

### New DB model: `User`

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(unique=True)
    role: Mapped[str]  # "admin" or "guest"
    fpl_team_id: Mapped[int] = mapped_column(default=0)
    league_ids: Mapped[str] = mapped_column(default="")  # comma-separated
    created_at: Mapped[str]
```

No password stored on the User row — admin authenticates via the env password, guests via the invite code. The User row just tracks their identity, role, and FPL preferences.

### Auth flow:

1. **Login page** — username + password/code
2. Backend checks:
   - If password matches `FPL_ADMIN_PASSWORD` → create/find user with `role=admin`
   - If password matches `FPL_GUEST_CODE` → create/find user with `role=guest`
   - Else → 401
3. Return JWT token with `{user_id, username, role}` payload
4. Frontend stores token in localStorage, sends as `Authorization: Bearer <token>` header
5. Backend middleware extracts user from JWT on every request

### Per-user data isolation:

**Shared (no user_id):** Player, Team, Fixture, Gameweek, PlayerGameweekStats, IngestLog, all analysis tables — global FPL data

**Per-user (add user_id FK):**
- `MyAccount` → add `user_id` column, change PK from `id=1` to auto-increment
- `MyTeamPlayer` → add `user_id` column
- `League` → add `user_id` column (each user subscribes independently)
- `LeagueEntry` → inherits isolation via League FK

Migration: existing admin data gets `user_id=1` (the first User created).

## Backend Changes

### New files:

**`src/fpl/auth.py`** — JWT encode/decode, password verification, FastAPI dependency

```python
from fastapi import Depends, HTTPException, Request
from jose import jwt

def get_current_user(request: Request) -> dict:
    """Extract user from JWT token in Authorization header."""
    ...

def require_admin(user = Depends(get_current_user)):
    """Raise 403 if user is not admin."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user
```

**`src/fpl/api/routes/auth.py`** — Login endpoint

```
POST /api/auth/login  {username, password} → {token, user}
GET  /api/auth/me → current user info
POST /api/auth/setup {fpl_team_id, league_ids} → save user preferences
```

### Modified routes:

**All routes** get the current user via `Depends(get_current_user)`:
- `team.py` — filter MyAccount/MyTeamPlayer by `user_id`, strip `next_fixtures` for guests
- `leagues.py` — filter League by `user_id`, strip chips/transfers for guests  
- `fixtures.py`, `transfers.py`, `prices.py` — reject guests with 403
- `data.py` — restrict refresh to admin only (or per-user team refresh)
- `settings.py` — admin only

### Modified: `src/fpl/api/app.py`
- Register auth router at `/api/auth`
- Add CORS to allow Authorization header
- No global middleware — individual routes opt in via `Depends`

### Modified: `src/fpl/config.py`
- Add `admin_password`, `guest_code`, `jwt_secret` settings

## Frontend Changes

### New page: `pages/LoginPage.tsx`
- Username + password form
- Detects role from response
- Stores JWT in localStorage
- Redirects to Dashboard

### New: `lib/auth.ts`
- `getToken()`, `setToken()`, `clearToken()`, `getUser()` from localStorage
- `isAdmin()`, `isGuest()` helpers
- Attach token to all API calls via fetch wrapper

### Modified: `lib/api.ts`
- Add Authorization header to all requests

### Modified: `components/AppLayout.tsx`
- Conditionally render nav items based on role
- Hide Fixtures, Transfers, Prices for guests
- Add logout button

### Modified: `App.tsx`
- Wrap routes in auth check — redirect to login if no token
- Protected routes for admin-only pages

### Modified pages:
- `MyTeamPage.tsx` — conditionally render NextFixturesTable
- `OpponentTeamPage.tsx` — conditionally render Chips Used + Recent Transfers
- `SettingsPage.tsx` — admin-only gate (guests get their own setup page)

### New page: `pages/GuestSetupPage.tsx`
- Simple form: FPL Team ID + League IDs
- Saves via `POST /api/auth/setup`
- Replaces Settings for guests

## Migration Strategy

1. Add `User` table + `user_id` columns to MyAccount, MyTeamPlayer, League
2. Lightweight SQLite migration in `init_db()` (ALTER TABLE ADD COLUMN)
3. Create admin user (user_id=1) on first startup
4. Backfill existing data with `user_id=1`
5. Existing admin experience unchanged — login with admin password

## Dependencies

```
pip install python-jose[cryptography]
```

Add to pyproject.toml dependencies.

## Acceptance Criteria

1. Login page with username + password
2. Admin has full access (identical to current experience)
3. Guest can set their own FPL team ID and leagues
4. Guest sees their own team data, not admin's
5. Guest cannot see: Upcoming Fixtures, Chips Used, Recent Transfers, Fixtures page, Transfers page, Prices page, Settings
6. Guest can see: Dashboard, My Team (restricted), Leagues (restricted), Scores, Tables, Stats, Live GW
7. Multiple guests can use the app simultaneously with different teams
8. Existing admin data preserved after migration
9. All tests pass

## Files

| File | Action |
|------|--------|
| `src/fpl/auth.py` | New: JWT + auth dependencies |
| `src/fpl/api/routes/auth.py` | New: login, me, setup endpoints |
| `src/fpl/db/models.py` | Add User model, user_id to per-user tables |
| `src/fpl/db/engine.py` | Migration for user_id columns |
| `src/fpl/config.py` | Add auth settings |
| `src/fpl/api/app.py` | Register auth router |
| `src/fpl/api/routes/team.py` | User-scoped queries + guest filtering |
| `src/fpl/api/routes/leagues.py` | User-scoped queries + guest filtering |
| `src/fpl/api/routes/fixtures.py` | Admin gate |
| `src/fpl/api/routes/transfers.py` | Admin gate |
| `src/fpl/api/routes/prices.py` | Admin gate |
| `src/fpl/api/routes/data.py` | User-scoped refresh |
| `pyproject.toml` | Add python-jose dependency |
| `frontend/src/lib/auth.ts` | New: token management |
| `frontend/src/lib/api.ts` | Add auth header |
| `frontend/src/pages/LoginPage.tsx` | New: login form |
| `frontend/src/pages/GuestSetupPage.tsx` | New: guest team setup |
| `frontend/src/components/AppLayout.tsx` | Role-based nav |
| `frontend/src/App.tsx` | Auth wrapper + protected routes |
| `frontend/src/pages/MyTeamPage.tsx` | Conditional NextFixtures |
| `frontend/src/pages/OpponentTeamPage.tsx` | Conditional chips/transfers |
| `.env.example` | Add auth settings |
| `tests/test_auth.py` | New: auth + permission tests |
