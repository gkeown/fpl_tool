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


def _assert_window(result: list[str], tue: date) -> None:
    """Assert the window starts on the given Tuesday and spans 7 days."""
    from datetime import timedelta

    expected = [
        (tue + timedelta(days=d)).strftime("%Y%m%d")
        for d in range(7)
    ]
    assert result == expected, f"Expected {expected}, got {result}"


def test_tuesday_returns_last_tuesday() -> None:
    # Tue 2026-04-14 → last Tue Apr 7 through Mon Apr 13
    result = _run_with_date(date(2026, 4, 14))
    _assert_window(result, date(2026, 4, 7))


def test_monday_returns_last_tuesday() -> None:
    # Mon 2026-04-13 → last Tue Apr 7 through Mon Apr 13
    result = _run_with_date(date(2026, 4, 13))
    _assert_window(result, date(2026, 4, 7))


def test_wednesday_returns_this_tuesday() -> None:
    # Wed 2026-04-15 → this Tue Apr 14 through Mon Apr 20
    result = _run_with_date(date(2026, 4, 15))
    _assert_window(result, date(2026, 4, 14))


def test_thursday_returns_this_tuesday() -> None:
    # Thu 2026-04-16 → this Tue Apr 14 through Mon Apr 20
    result = _run_with_date(date(2026, 4, 16))
    _assert_window(result, date(2026, 4, 14))


def test_friday_returns_this_tuesday() -> None:
    # Fri 2026-04-17 → this Tue Apr 14 through Mon Apr 20
    result = _run_with_date(date(2026, 4, 17))
    _assert_window(result, date(2026, 4, 14))


def test_saturday_returns_this_tuesday() -> None:
    # Sat 2026-04-18 → this Tue Apr 14 through Mon Apr 20
    result = _run_with_date(date(2026, 4, 18))
    _assert_window(result, date(2026, 4, 14))


def test_sunday_returns_this_tuesday() -> None:
    # Sun 2026-04-19 → this Tue Apr 14 through Mon Apr 20
    result = _run_with_date(date(2026, 4, 19))
    _assert_window(result, date(2026, 4, 14))


def test_window_is_always_7_days() -> None:
    """Every day of the week should return exactly 7 dates."""
    for d in range(7):
        result = _run_with_date(date(2026, 4, 13 + d))
        assert len(result) == 7, f"Weekday {d}: got {len(result)}"
