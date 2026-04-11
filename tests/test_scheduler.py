"""Unit tests for scheduler match window logic."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fpl.scheduler import _in_window, _MATCH_WINDOWS, _SCORE_WINDOWS

_UK = ZoneInfo("Europe/London")


def _make_dt(weekday: int, hour: int, minute: int = 0) -> datetime:
    """Create a datetime for a specific weekday and time.

    Uses April 2026 which starts on a Wednesday.
    Mon=0 -> Apr 6, Tue=1 -> Apr 7, ..., Sun=6 -> Apr 12
    """
    day_map = {0: 6, 1: 7, 2: 8, 3: 9, 4: 10, 5: 11, 6: 12}
    return datetime(2026, 4, day_map[weekday], hour, minute, tzinfo=_UK)


def test_saturday_afternoon_is_match_window() -> None:
    dt = _make_dt(5, 15)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_MATCH_WINDOWS) is True


def test_saturday_morning_is_not_match_window() -> None:
    dt = _make_dt(5, 10)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_MATCH_WINDOWS) is False


def test_sunday_afternoon_is_match_window() -> None:
    dt = _make_dt(6, 14)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_MATCH_WINDOWS) is True


def test_monday_evening_is_match_window() -> None:
    dt = _make_dt(0, 21)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_MATCH_WINDOWS) is True


def test_tuesday_is_not_match_window() -> None:
    dt = _make_dt(1, 15)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_MATCH_WINDOWS) is False


def test_wednesday_is_not_match_window() -> None:
    dt = _make_dt(2, 20)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_MATCH_WINDOWS) is False


def test_friday_evening_is_score_window() -> None:
    dt = _make_dt(4, 20)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_SCORE_WINDOWS) is True


def test_friday_afternoon_is_not_score_window() -> None:
    dt = _make_dt(4, 14)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_SCORE_WINDOWS) is False


def test_saturday_all_day_is_score_window() -> None:
    dt1 = _make_dt(5, 12)
    dt2 = _make_dt(5, 21)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt1
        assert _in_window(_SCORE_WINDOWS) is True
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt2
        assert _in_window(_SCORE_WINDOWS) is True


def test_saturday_late_night_is_not_score_window() -> None:
    dt = _make_dt(5, 23)
    with patch("fpl.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert _in_window(_SCORE_WINDOWS) is False
