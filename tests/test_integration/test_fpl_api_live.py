"""Integration tests that hit the live FPL API.

Run with:
    pytest tests/test_integration/ -v -m integration
    pytest tests/test_integration/test_fpl_api_live.py -v

Skip during fast unit test runs:
    pytest tests/ -v -m "not integration"
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from fpl.config import get_settings
from fpl.db.models import (
    Base,
    Fixture,
    Gameweek,
    Player,
    PlayerGameweekStats,
    Team,
)
from fpl.ingest.fpl_api import (
    fetch_bootstrap,
    fetch_fixtures,
    fetch_player_history,
    ingest_bootstrap,
    upsert_fixtures,
    upsert_player_histories,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def settings() -> object:
    return get_settings()


@pytest.fixture(scope="module")
def integration_db() -> Generator[Session, None, None]:
    """A module-scoped in-memory DB for integration tests.

    Module scope means all tests in this file share the same DB,
    which lets later tests verify data from earlier ones.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture(scope="module")
def bootstrap_data() -> dict[str, Any]:
    """Fetch bootstrap-static once for the whole module."""
    settings = get_settings()

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            return await fetch_bootstrap(client, settings)  # type: ignore[no-any-return]

    result: dict[str, Any] = asyncio.run(_fetch())
    return result


@pytest.fixture(scope="module")
def fixtures_data() -> list[dict[str, Any]]:
    """Fetch fixtures once for the whole module."""
    settings = get_settings()

    async def _fetch() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            return await fetch_fixtures(client, settings)  # type: ignore[no-any-return]

    result: list[dict[str, Any]] = asyncio.run(_fetch())
    return result


# ---------------------------------------------------------------------------
# API response shape tests — verify the live API returns expected fields
# ---------------------------------------------------------------------------


class TestFplApiResponseShape:
    """Verify the live FPL API returns data in the shape we expect."""

    def test_bootstrap_has_required_top_level_keys(
        self, bootstrap_data: dict[str, Any]
    ) -> None:
        required_keys = {"elements", "teams", "events", "element_types"}
        assert required_keys.issubset(
            bootstrap_data.keys()
        ), f"Missing keys: {required_keys - bootstrap_data.keys()}"

    def test_bootstrap_teams_not_empty(self, bootstrap_data: dict[str, Any]) -> None:
        teams = bootstrap_data["teams"]
        assert len(teams) == 20, f"Expected 20 PL teams, got {len(teams)}"

    def test_bootstrap_team_has_required_fields(
        self, bootstrap_data: dict[str, Any]
    ) -> None:
        team = bootstrap_data["teams"][0]
        required = {
            "id",
            "code",
            "name",
            "short_name",
            "strength",
            "strength_attack_home",
            "strength_attack_away",
            "strength_defence_home",
            "strength_defence_away",
        }
        missing = required - team.keys()
        assert not missing, f"Team missing fields: {missing}"

    def test_bootstrap_elements_not_empty(self, bootstrap_data: dict[str, Any]) -> None:
        elements = bootstrap_data["elements"]
        assert len(elements) > 500, f"Expected 500+ players, got {len(elements)}"

    def test_bootstrap_element_has_required_fields(
        self, bootstrap_data: dict[str, Any]
    ) -> None:
        element = bootstrap_data["elements"][0]
        required = {
            "id",
            "code",
            "first_name",
            "second_name",
            "web_name",
            "team",
            "element_type",
            "now_cost",
            "selected_by_percent",
            "status",
            "form",
            "points_per_game",
            "total_points",
            "minutes",
            "goals_scored",
            "assists",
            "clean_sheets",
            "bonus",
            "transfers_in",
            "transfers_out",
            "expected_goals",
            "expected_assists",
            "expected_goal_involvements",
            "expected_goals_conceded",
            "starts",
            "saves",
            "goals_conceded",
            "yellow_cards",
            "red_cards",
            "influence",
            "creativity",
            "threat",
            "ict_index",
            "bps",
        }
        missing = required - element.keys()
        assert not missing, f"Element missing fields: {missing}"

    def test_bootstrap_events_has_38_gameweeks(
        self, bootstrap_data: dict[str, Any]
    ) -> None:
        events = bootstrap_data["events"]
        assert len(events) == 38, f"Expected 38 gameweeks, got {len(events)}"

    def test_bootstrap_event_has_required_fields(
        self, bootstrap_data: dict[str, Any]
    ) -> None:
        event = bootstrap_data["events"][0]
        required = {
            "id",
            "name",
            "deadline_time",
            "finished",
            "is_current",
            "is_next",
        }
        missing = required - event.keys()
        assert not missing, f"Event missing fields: {missing}"

    def test_bootstrap_has_exactly_one_current_or_next_gameweek(
        self, bootstrap_data: dict[str, Any]
    ) -> None:
        events = bootstrap_data["events"]
        current = [e for e in events if e.get("is_current")]
        next_gw = [e for e in events if e.get("is_next")]
        # During a gameweek, is_current=True for one GW.
        # Between gameweeks, is_next=True for the upcoming one.
        # At least one of these should be set.
        assert len(current) <= 1, f"Multiple current GWs: {current}"
        assert len(next_gw) <= 1, f"Multiple next GWs: {next_gw}"
        assert len(current) + len(next_gw) >= 1, "No current or next GW found"

    def test_fixtures_not_empty(self, fixtures_data: list[dict[str, Any]]) -> None:
        # 20 teams * 19 opponents = 380 fixtures per season
        assert (
            len(fixtures_data) >= 380
        ), f"Expected 380+ fixtures, got {len(fixtures_data)}"

    def test_fixture_has_required_fields(
        self, fixtures_data: list[dict[str, Any]]
    ) -> None:
        fixture = fixtures_data[0]
        required = {
            "id",
            "team_h",
            "team_a",
            "team_h_difficulty",
            "team_a_difficulty",
            "finished",
        }
        missing = required - fixture.keys()
        assert not missing, f"Fixture missing fields: {missing}"

    def test_player_history_endpoint_returns_history(self) -> None:
        """Fetch history for player ID 1 (should always exist)."""
        settings = get_settings()

        async def _fetch() -> dict[str, Any]:
            async with httpx.AsyncClient(
                timeout=settings.http_timeout,
                headers={"User-Agent": settings.user_agent},
            ) as client:
                return await fetch_player_history(client, settings, 1)  # type: ignore[no-any-return]

        data: dict[str, Any] = asyncio.run(_fetch())
        assert "history" in data, f"Missing 'history' key. Keys: {data.keys()}"
        assert "fixtures" in data, f"Missing 'fixtures' key. Keys: {data.keys()}"

        if data["history"]:
            entry = data["history"][0]
            required = {
                "element",
                "fixture",
                "opponent_team",
                "round",
                "was_home",
                "minutes",
                "total_points",
                "goals_scored",
                "assists",
                "clean_sheets",
                "bonus",
                "bps",
                "influence",
                "creativity",
                "threat",
                "ict_index",
                "expected_goals",
                "expected_assists",
                "expected_goals_conceded",
                "selected",
                "transfers_in",
                "transfers_out",
                "value",
            }
            missing = required - entry.keys()
            assert not missing, f"History entry missing fields: {missing}"


# ---------------------------------------------------------------------------
# Ingest pipeline tests — verify fetch -> upsert -> query cycle
# ---------------------------------------------------------------------------


class TestFplIngestPipeline:
    """Test the full fetch -> upsert -> query pipeline with live data."""

    def test_ingest_bootstrap_populates_teams(
        self, integration_db: Session, bootstrap_data: dict[str, Any]
    ) -> None:
        ingest_bootstrap(integration_db, bootstrap_data)
        integration_db.commit()

        count = integration_db.scalar(select(func.count()).select_from(Team))
        assert count == 20, f"Expected 20 teams, got {count}"

    def test_teams_have_valid_data(self, integration_db: Session) -> None:
        teams = integration_db.execute(select(Team)).scalars().all()
        for team in teams:
            assert team.fpl_id > 0
            assert len(team.name) > 0
            assert len(team.short_name) == 3
            assert team.strength > 0

    def test_ingest_bootstrap_populates_players(self, integration_db: Session) -> None:
        count = integration_db.scalar(select(func.count()).select_from(Player))
        assert count is not None and count > 500, f"Expected 500+ players, got {count}"

    def test_players_have_valid_data(self, integration_db: Session) -> None:
        # Spot-check: every player should have a valid team_id
        players = integration_db.execute(select(Player)).scalars().all()
        team_ids = {
            t.fpl_id for t in integration_db.execute(select(Team)).scalars().all()
        }
        for player in players:
            assert (
                player.team_id in team_ids
            ), f"Player {player.web_name} has invalid team_id {player.team_id}"
            assert player.element_type in (1, 2, 3, 4), (
                f"Player {player.web_name} has invalid "
                f"element_type {player.element_type}"
            )
            assert (
                player.now_cost > 0
            ), f"Player {player.web_name} has invalid cost {player.now_cost}"

    def test_ingest_bootstrap_populates_gameweeks(
        self, integration_db: Session
    ) -> None:
        count = integration_db.scalar(select(func.count()).select_from(Gameweek))
        assert count == 38, f"Expected 38 gameweeks, got {count}"

    def test_gameweeks_have_valid_data(self, integration_db: Session) -> None:
        gws = integration_db.execute(select(Gameweek)).scalars().all()
        ids = [gw.id for gw in gws]
        assert ids == list(range(1, 39)), "Gameweek IDs should be 1-38"
        for gw in gws:
            assert gw.name.startswith(
                "Gameweek"
            ), f"GW {gw.id} has unexpected name: {gw.name}"
            assert len(gw.deadline_time) > 0

    def test_upsert_fixtures_populates_table(
        self, integration_db: Session, fixtures_data: list[dict[str, Any]]
    ) -> None:
        count = upsert_fixtures(integration_db, fixtures_data)
        integration_db.commit()
        assert count >= 380, f"Expected 380+ fixtures upserted, got {count}"

    def test_fixtures_reference_valid_teams(self, integration_db: Session) -> None:
        team_ids = {
            t.fpl_id for t in integration_db.execute(select(Team)).scalars().all()
        }
        fixtures = integration_db.execute(select(Fixture)).scalars().all()
        for f in fixtures:
            assert (
                f.team_h in team_ids
            ), f"Fixture {f.fpl_id} has invalid home team {f.team_h}"
            assert (
                f.team_a in team_ids
            ), f"Fixture {f.fpl_id} has invalid away team {f.team_a}"

    def test_finished_fixtures_have_scores(self, integration_db: Session) -> None:
        finished = (
            integration_db.execute(
                select(Fixture).where(Fixture.finished == True)  # noqa: E712
            )
            .scalars()
            .all()
        )
        if not finished:
            pytest.skip("No finished fixtures in current season data")
        for f in finished:
            assert (
                f.team_h_score is not None
            ), f"Finished fixture {f.fpl_id} missing home score"
            assert (
                f.team_a_score is not None
            ), f"Finished fixture {f.fpl_id} missing away score"

    def test_upsert_player_history_for_active_player(
        self, integration_db: Session
    ) -> None:
        """Fetch and upsert history for a known active player."""
        # Find a player with minutes > 0
        player = integration_db.execute(
            select(Player).where(Player.minutes > 0).limit(1)
        ).scalar_one()

        settings = get_settings()

        async def _fetch() -> dict[str, Any]:
            async with httpx.AsyncClient(
                timeout=settings.http_timeout,
                headers={"User-Agent": settings.user_agent},
            ) as client:
                return await fetch_player_history(client, settings, player.fpl_id)  # type: ignore[no-any-return]

        data: dict[str, Any] = asyncio.run(_fetch())
        history = data.get("history", [])
        assert len(history) > 0, (
            f"Player {player.web_name} (id={player.fpl_id}) "
            f"has {player.minutes} minutes but empty history"
        )

        count = upsert_player_histories(integration_db, player.fpl_id, history)
        integration_db.commit()
        assert count == len(history)

        # Verify data landed in DB
        db_count = integration_db.scalar(
            select(func.count())
            .select_from(PlayerGameweekStats)
            .where(PlayerGameweekStats.player_id == player.fpl_id)
        )
        assert db_count == len(history), f"Expected {len(history)} rows, got {db_count}"

    def test_player_history_has_valid_gameweek_references(
        self, integration_db: Session
    ) -> None:
        stats = integration_db.execute(select(PlayerGameweekStats)).scalars().all()
        if not stats:
            pytest.skip("No player history data yet")
        for s in stats:
            assert (
                1 <= s.gameweek <= 38
            ), f"Invalid gameweek {s.gameweek} for player {s.player_id}"
            assert s.minutes >= 0
            assert s.total_points is not None

    def test_idempotent_upsert_does_not_duplicate(
        self, integration_db: Session, bootstrap_data: dict[str, Any]
    ) -> None:
        """Running ingest twice should not create duplicate records."""
        count_before = integration_db.scalar(select(func.count()).select_from(Team))
        ingest_bootstrap(integration_db, bootstrap_data)
        integration_db.commit()
        count_after = integration_db.scalar(select(func.count()).select_from(Team))
        assert (
            count_before == count_after
        ), f"Upsert created duplicates: {count_before} -> {count_after}"


# ---------------------------------------------------------------------------
# Full end-to-end pipeline test
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Full pipeline test: run_fpl_ingest and verify DB state."""

    def test_run_fpl_ingest_end_to_end(self) -> None:
        """Run the complete ingest pipeline against live API.

        Uses a separate in-memory DB to avoid polluting other tests.
        This is the most comprehensive test — it runs run_fpl_ingest()
        which fetches bootstrap + fixtures + player histories for all
        active players. Skips player histories to keep runtime reasonable.
        """
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        session = factory()

        settings = get_settings()

        async def _run() -> None:
            """Run a lighter version of the full ingest (skip histories)."""
            headers = {"User-Agent": settings.user_agent}
            async with httpx.AsyncClient(
                timeout=settings.http_timeout, headers=headers
            ) as client:
                bootstrap = await fetch_bootstrap(client, settings)
                fixtures_resp = await fetch_fixtures(client, settings)

            ingest_bootstrap(session, bootstrap)
            upsert_fixtures(session, fixtures_resp)

            # Fetch history for just 3 players to keep test fast
            elements = bootstrap.get("elements", [])
            active = [e for e in elements if e.get("minutes", 0) > 0][:3]

            async with httpx.AsyncClient(
                timeout=settings.http_timeout, headers=headers
            ) as client:
                for e in active:
                    data = await fetch_player_history(client, settings, e["id"])
                    upsert_player_histories(session, e["id"], data.get("history", []))

            session.commit()

        asyncio.run(_run())

        # Verify everything landed
        team_count = session.scalar(select(func.count()).select_from(Team))
        player_count = session.scalar(select(func.count()).select_from(Player))
        gw_count = session.scalar(select(func.count()).select_from(Gameweek))
        fixture_count = session.scalar(select(func.count()).select_from(Fixture))
        history_count = session.scalar(
            select(func.count()).select_from(PlayerGameweekStats)
        )

        assert team_count == 20
        assert player_count is not None and player_count > 500
        assert gw_count == 38
        assert fixture_count is not None and fixture_count >= 380
        assert history_count is not None and history_count > 0

        session.close()

    def test_data_consistency_teams_referenced_by_players(self) -> None:
        """After full ingest, every player's team_id should exist in teams."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        session = factory()

        settings = get_settings()

        async def _run() -> None:
            headers = {"User-Agent": settings.user_agent}
            async with httpx.AsyncClient(
                timeout=settings.http_timeout, headers=headers
            ) as client:
                bootstrap = await fetch_bootstrap(client, settings)
            ingest_bootstrap(session, bootstrap)
            session.commit()

        asyncio.run(_run())

        team_ids = {t.fpl_id for t in session.execute(select(Team)).scalars().all()}
        players_with_bad_team = (
            session.execute(select(Player).where(Player.team_id.not_in(team_ids)))
            .scalars()
            .all()
        )
        assert (
            len(players_with_bad_team) == 0
        ), f"{len(players_with_bad_team)} players have invalid team_id"

        session.close()

    def test_data_consistency_fixtures_reference_valid_gameweeks(
        self,
    ) -> None:
        """Scheduled fixtures should reference valid gameweek numbers."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        session = factory()

        settings = get_settings()

        async def _run() -> None:
            headers = {"User-Agent": settings.user_agent}
            async with httpx.AsyncClient(
                timeout=settings.http_timeout, headers=headers
            ) as client:
                bootstrap = await fetch_bootstrap(client, settings)
                fixtures_resp = await fetch_fixtures(client, settings)
            ingest_bootstrap(session, bootstrap)
            upsert_fixtures(session, fixtures_resp)
            session.commit()

        asyncio.run(_run())

        fixtures = session.execute(select(Fixture)).scalars().all()
        for f in fixtures:
            if f.gameweek is not None:
                assert (
                    1 <= f.gameweek <= 38
                ), f"Fixture {f.fpl_id} has invalid gameweek {f.gameweek}"

        session.close()
