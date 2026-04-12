"""Unit tests for provisional bonus computation from BPS rankings."""

from __future__ import annotations

from fpl.api.routes.team import _compute_provisional_bonus


def test_no_players() -> None:
    assert _compute_provisional_bonus([]) == {}


def test_single_player() -> None:
    result = _compute_provisional_bonus([(1, 50)])
    assert result == {1: 3}


def test_three_players_no_ties() -> None:
    result = _compute_provisional_bonus([(1, 50), (2, 45), (3, 40)])
    assert result == {1: 3, 2: 2, 3: 1}


def test_four_players_no_ties() -> None:
    """4th player gets nothing."""
    result = _compute_provisional_bonus(
        [(1, 50), (2, 45), (3, 40), (4, 35)]
    )
    assert result == {1: 3, 2: 2, 3: 1}


def test_tie_for_first_two_players() -> None:
    """2 tied for 1st → both get 3, next gets 1."""
    result = _compute_provisional_bonus([(1, 50), (2, 50), (3, 40)])
    assert result == {1: 3, 2: 3, 3: 1}


def test_tie_for_first_three_players() -> None:
    """3 tied for 1st → all get 3, no 2nd/3rd."""
    result = _compute_provisional_bonus([(1, 50), (2, 50), (3, 50)])
    assert result == {1: 3, 2: 3, 3: 3}


def test_tie_for_second() -> None:
    """2 tied for 2nd → both get 2, no 3rd place bonus."""
    result = _compute_provisional_bonus(
        [(1, 50), (2, 45), (3, 45), (4, 40)]
    )
    assert result == {1: 3, 2: 2, 3: 2}


def test_tie_for_third() -> None:
    """2 tied for 3rd → both get 1."""
    result = _compute_provisional_bonus(
        [(1, 50), (2, 45), (3, 40), (4, 40)]
    )
    assert result == {1: 3, 2: 2, 3: 1, 4: 1}


def test_zero_bps_excluded() -> None:
    """Players with 0 BPS don't get bonus."""
    result = _compute_provisional_bonus(
        [(1, 50), (2, 0), (3, 0)]
    )
    assert result == {1: 3}


def test_negative_bps_excluded() -> None:
    """Negative BPS (own goals etc) don't earn bonus."""
    result = _compute_provisional_bonus(
        [(1, 50), (2, 45), (3, -5)]
    )
    assert result == {1: 3, 2: 2}


def test_unsorted_input() -> None:
    """Input order doesn't matter."""
    result = _compute_provisional_bonus(
        [(3, 40), (1, 50), (2, 45)]
    )
    assert result == {1: 3, 2: 2, 3: 1}
