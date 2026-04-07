"""Integration tests for the FPL set-piece notes API and RSS feed.

Run with:
    pytest tests/test_integration/test_setpieces_live.py -v
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from fpl.config import get_settings

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def setpiece_data() -> dict[str, Any]:
    """Fetch set-piece notes once for all tests."""
    settings = get_settings()
    url = "https://fantasy.premierleague.com/api/team/set-piece-notes/"
    resp = httpx.get(
        url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.http_timeout,
    )
    resp.raise_for_status()
    result: dict[str, Any] = resp.json()
    return result


class TestSetPieceNotesShape:
    """Verify the FPL set-piece notes API returns expected structure."""

    def test_response_has_teams_key(self, setpiece_data: dict[str, Any]) -> None:
        assert "teams" in setpiece_data

    def test_teams_array_has_20_entries(self, setpiece_data: dict[str, Any]) -> None:
        teams = setpiece_data["teams"]
        assert len(teams) == 20, f"Expected 20 teams, got {len(teams)}"

    def test_team_entry_has_id_and_notes(self, setpiece_data: dict[str, Any]) -> None:
        team = setpiece_data["teams"][0]
        assert "id" in team
        assert "notes" in team
        assert isinstance(team["notes"], list)

    def test_note_has_info_message(self, setpiece_data: dict[str, Any]) -> None:
        """At least some teams should have set-piece notes."""
        all_notes: list[dict[str, Any]] = []
        for team in setpiece_data["teams"]:
            all_notes.extend(team["notes"])
        assert len(all_notes) > 0, "No set-piece notes found"
        note = all_notes[0]
        assert "info_message" in note
        assert len(note["info_message"]) > 0

    def test_note_has_expected_fields(
        self, setpiece_data: dict[str, Any]
    ) -> None:
        for team in setpiece_data["teams"]:
            for note in team["notes"]:
                assert "info_message" in note
                assert "external_link" in note or "source_link" in note

    def test_team_ids_are_valid(self, setpiece_data: dict[str, Any]) -> None:
        ids = {t["id"] for t in setpiece_data["teams"]}
        assert all(1 <= tid <= 20 for tid in ids), f"Team IDs out of range: {ids}"


class TestRssFeedShape:
    """Verify the Fantasy Football Scout RSS feed is accessible."""

    def test_rss_feed_returns_xml(self) -> None:
        resp = httpx.get(
            "https://www.fantasyfootballscout.co.uk/feed/",
            timeout=30,
            follow_redirects=True,
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert (
            "xml" in content_type or "rss" in content_type
        ), f"Expected XML content-type, got: {content_type}"

    def test_rss_feed_parseable_with_feedparser(self) -> None:
        import feedparser

        feed = feedparser.parse("https://www.fantasyfootballscout.co.uk/feed/")
        assert feed.entries, "No entries in RSS feed"
        assert len(feed.entries) >= 5, f"Expected 5+ entries, got {len(feed.entries)}"

    def test_rss_entry_has_title_and_link(self) -> None:
        import feedparser

        feed = feedparser.parse("https://www.fantasyfootballscout.co.uk/feed/")
        entry = feed.entries[0]
        assert entry.get("title"), "Entry missing title"
        assert entry.get("link"), "Entry missing link"

    def test_rss_entry_has_published_date(self) -> None:
        import feedparser

        feed = feedparser.parse("https://www.fantasyfootballscout.co.uk/feed/")
        entry = feed.entries[0]
        assert entry.get("published") or entry.get("updated"), "Entry missing date"
