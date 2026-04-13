"""Tests for _matchweek_dates() weekday-to-window logic."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fpl.api.routes.scores import _matchweek_dates


def _run_with_date(d: date) -> list[str]:
    """Run _matchweek_dates with a mocked today()."""
    with patch("fpl.api.routes.scores.datetime") as mock_dt:
        from datetime import datetime

        mock_dt.now.return_value = datetime.combine(
            d, datetime.min.time()
        )
        return _matchweek_dates()


def test_friday_returns_fri_to_mon() -> None:
    # Fri 2026-04-10 → [Fri 10, Sat 11, Sun 12, Mon 13]
    result = _run_with_date(date(2026, 4, 10))
    assert result == ["20260410", "20260411", "20260412", "20260413"]


def test_saturday_returns_fri_to_mon() -> None:
    # Sat 2026-04-11
    result = _run_with_date(date(2026, 4, 11))
    assert result == ["20260410", "20260411", "20260412", "20260413"]


def test_sunday_returns_fri_to_mon() -> None:
    # Sun 2026-04-12
    result = _run_with_date(date(2026, 4, 12))
    assert result == ["20260410", "20260411", "20260412", "20260413"]


def test_monday_returns_last_weekend() -> None:
    """Monday should show the weekend just past, not next weekend."""
    # Mon 2026-04-13 → last Fri 10 through today Mon 13
    result = _run_with_date(date(2026, 4, 13))
    assert result == ["20260410", "20260411", "20260412", "20260413"]


def test_tuesday_returns_last_weekend() -> None:
    """Tuesday still shows the weekend just past (GW rarely ends Mon)."""
    # Tue 2026-04-14 → last Fri 10 through Mon 13
    result = _run_with_date(date(2026, 4, 14))
    assert result == ["20260410", "20260411", "20260412", "20260413"]


def test_wednesday_returns_upcoming_weekend() -> None:
    """Wednesday shifts to the upcoming weekend."""
    # Wed 2026-04-15 → upcoming Fri 17
    result = _run_with_date(date(2026, 4, 15))
    assert result == ["20260417", "20260418", "20260419", "20260420"]


def test_thursday_returns_upcoming_weekend() -> None:
    # Thu 2026-04-16 → upcoming Fri 17
    result = _run_with_date(date(2026, 4, 16))
    assert result == ["20260417", "20260418", "20260419", "20260420"]
