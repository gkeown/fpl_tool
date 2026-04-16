"""Authentication endpoints: login, current user, guest setup."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from fpl.auth import create_token, get_current_user
from fpl.config import get_settings
from fpl.db.engine import get_session
from fpl.db.models import User

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupRequest(BaseModel):
    fpl_team_id: int
    league_ids: str = ""


@router.post("/login")
def login(body: LoginRequest) -> dict[str, Any]:
    """Authenticate and return a JWT token.

    Admin: password matches FPL_ADMIN_PASSWORD.
    Guest: password matches FPL_GUEST_CODE.
    """
    settings = get_settings()
    username = body.username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")

    # Determine role
    if body.password == settings.admin_password:
        role = "admin"
    elif body.password == settings.guest_code:
        role = "guest"
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Find or create user
    with get_session() as session:
        user: User | None = (
            session.query(User)
            .filter(User.username == username)
            .first()
        )
        if user is None:
            user = User(
                username=username,
                role=role,
                created_at=datetime.now(UTC).isoformat(),
            )
            session.add(user)
            session.flush()
        elif user.role != role:
            # Upgrade guest to admin if they use admin password,
            # but never downgrade admin to guest
            if role == "admin":
                user.role = "admin"

        user_id = user.id
        user_role = user.role
        user_fpl_team = user.fpl_team_id
        user_leagues = user.league_ids

    token = create_token(user_id, username, user_role)
    return {
        "token": token,
        "user": {
            "id": user_id,
            "username": username,
            "role": user_role,
            "fpl_team_id": user_fpl_team,
            "league_ids": user_leagues,
        },
    }


@router.get("/me")
def me(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return current user info."""
    with get_session() as session:
        db_user: User | None = session.get(User, user["user_id"])
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id": db_user.id,
            "username": db_user.username,
            "role": db_user.role,
            "fpl_team_id": db_user.fpl_team_id,
            "league_ids": db_user.league_ids,
        }


@router.post("/setup")
async def setup(
    body: SetupRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Set FPL team ID and league IDs for the current user.

    Fetches team data and subscribes to leagues.
    """
    user_id = user["user_id"]

    with get_session() as session:
        db_user: User | None = session.get(User, user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        db_user.fpl_team_id = body.fpl_team_id
        db_user.league_ids = body.league_ids

    # Load the team
    settings = get_settings()
    headers = {"User-Agent": settings.user_agent}
    try:
        from fpl.ingest.fpl_api import (
            fetch_entry,
            fetch_entry_picks,
        )

        async with httpx.AsyncClient(
            timeout=settings.http_timeout, headers=headers
        ) as client:
            entry = await fetch_entry(
                client, settings, body.fpl_team_id
            )
            current_gw = entry.get("current_event", 1)
            picks = await fetch_entry_picks(
                client, settings, body.fpl_team_id, current_gw
            )

            from fpl.ingest.fpl_api import upsert_my_team

            with get_session() as session:
                # Clear old team data for this user
                from fpl.db.models import MyAccount, MyTeamPlayer

                session.query(MyTeamPlayer).filter(
                    MyTeamPlayer.user_id == user_id
                ).delete()
                session.query(MyAccount).filter(
                    MyAccount.user_id == user_id
                ).delete()
                session.flush()

                upsert_my_team(
                    session,
                    body.fpl_team_id,
                    entry,
                    picks,
                    user_id=user_id,
                )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to load team: {exc}",
        ) from exc

    # Subscribe to leagues
    if body.league_ids.strip():
        league_id_list = [
            int(x.strip())
            for x in body.league_ids.split(",")
            if x.strip().isdigit()
        ]
        for lid in league_id_list:
            try:
                from fpl.ingest.leagues import (
                    fetch_league_standings,
                    upsert_league,
                )

                async with httpx.AsyncClient(
                    timeout=settings.http_timeout, headers=headers
                ) as client:
                    data = await fetch_league_standings(
                        client, settings, lid
                    )
                    with get_session() as session:
                        upsert_league(
                            session, lid, data, user_id=user_id
                        )
            except Exception:
                pass

    return {"status": "ok", "team_id": body.fpl_team_id}
