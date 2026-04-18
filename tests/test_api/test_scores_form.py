from __future__ import annotations

import pytest

from fpl.api.routes.scores import _compute_team_form


# ---------------------------------------------------------------------------
# Helpers — build synthetic ESPN event dicts matching the real shape
# ---------------------------------------------------------------------------

def _make_event(
    event_id: str,
    date: str,
    state: str,
    home_id: str,
    home_score: str | None,
    away_id: str,
    away_score: str | None,
) -> dict:
    """Return a minimal ESPN scoreboard event dict."""
    home_competitor: dict = {
        "id": home_id,
        "homeAway": "home",
        "score": home_score,
        "team": {"displayName": f"Team {home_id}"},
    }
    away_competitor: dict = {
        "id": away_id,
        "homeAway": "away",
        "score": away_score,
        "team": {"displayName": f"Team {away_id}"},
    }
    return {
        "id": event_id,
        "date": date,
        "status": {
            "type": {
                "state": state,
                "name": "STATUS_FULL_TIME" if state == "post" else "STATUS_SCHEDULED",
            }
        },
        "competitions": [
            {
                "competitors": [home_competitor, away_competitor],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_compute_team_form_win_loss_draw() -> None:
    """W/D/L are computed correctly for home and away perspectives."""
    events = [
        # Team A wins at home (2-0)
        _make_event("1", "2025-03-01T15:00:00Z", "post", "A", "2", "B", "0"),
        # Team A loses away (1-3)
        _make_event("2", "2025-03-08T15:00:00Z", "post", "B", "3", "A", "1"),
        # Team A draws at home (1-1)
        _make_event("3", "2025-03-15T15:00:00Z", "post", "A", "1", "B", "1"),
    ]

    form = _compute_team_form(events, "A")
    assert form == ["W", "L", "D"]


def test_compute_team_form_skips_unfinished() -> None:
    """Events with state 'in' or 'pre' are ignored."""
    events = [
        _make_event("1", "2025-03-01T15:00:00Z", "post", "A", "2", "B", "0"),
        _make_event("2", "2025-03-08T15:00:00Z", "in", "A", "1", "B", "0"),
        _make_event("3", "2025-03-15T15:00:00Z", "pre", "A", None, "B", None),
    ]

    form = _compute_team_form(events, "A")
    assert form == ["W"]


def test_compute_team_form_capped_at_five() -> None:
    """Only the last 5 results are returned when more than 5 exist."""
    events = [
        _make_event("1", "2025-01-01T15:00:00Z", "post", "A", "1", "B", "0"),  # W
        _make_event("2", "2025-01-08T15:00:00Z", "post", "A", "0", "B", "0"),  # D
        _make_event("3", "2025-01-15T15:00:00Z", "post", "B", "2", "A", "1"),  # L
        _make_event("4", "2025-01-22T15:00:00Z", "post", "A", "3", "B", "1"),  # W
        _make_event("5", "2025-01-29T15:00:00Z", "post", "A", "2", "B", "2"),  # D
        _make_event("6", "2025-02-05T15:00:00Z", "post", "B", "0", "A", "1"),  # W
        _make_event("7", "2025-02-12T15:00:00Z", "post", "A", "1", "B", "0"),  # W
    ]

    form = _compute_team_form(events, "A")
    # Oldest result (event 1: W) is dropped; last 5 are events 3-7
    assert len(form) == 5
    assert form == ["L", "W", "D", "W", "W"]


def test_compute_team_form_fewer_than_five() -> None:
    """When fewer than 5 finished results exist, all are returned."""
    events = [
        _make_event("1", "2025-03-01T15:00:00Z", "post", "A", "1", "B", "2"),  # L
        _make_event("2", "2025-03-08T15:00:00Z", "post", "A", "0", "B", "0"),  # D
    ]

    form = _compute_team_form(events, "A")
    assert form == ["L", "D"]


def test_compute_team_form_unknown_team() -> None:
    """A team_id not present in any event returns an empty list."""
    events = [
        _make_event("1", "2025-03-01T15:00:00Z", "post", "A", "2", "B", "1"),
    ]

    form = _compute_team_form(events, "UNKNOWN")
    assert form == []


def test_compute_team_form_skips_missing_scores() -> None:
    """Events where a competitor has None or empty score are excluded."""
    events = [
        # No score yet (pre-match data accidentally marked post)
        _make_event("1", "2025-03-01T15:00:00Z", "post", "A", None, "B", None),
        # Empty string score
        _make_event("2", "2025-03-08T15:00:00Z", "post", "A", "", "B", ""),
        # Valid finished match
        _make_event("3", "2025-03-15T15:00:00Z", "post", "A", "2", "B", "0"),
    ]

    form = _compute_team_form(events, "A")
    assert form == ["W"]
