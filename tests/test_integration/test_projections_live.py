"""Integration tests that hit the live Fantasy Football Pundit CSV.

Run with:
    pytest tests/test_integration/test_projections_live.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fpl.ingest.projections import fetch_pundit_csv

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pundit_rows() -> list[dict[str, Any]]:
    """Fetch Pundit CSV once for all tests."""
    result: list[dict[str, Any]] = asyncio.run(fetch_pundit_csv())
    return result


class TestPunditCsvResponseShape:
    """Verify the Pundit CSV returns expected structure."""

    def test_csv_returns_rows(self, pundit_rows: list[dict[str, Any]]) -> None:
        assert (
            len(pundit_rows) > 400
        ), f"Expected 400+ player rows, got {len(pundit_rows)}"

    def test_csv_has_required_columns(self, pundit_rows: list[dict[str, Any]]) -> None:
        row = pundit_rows[0]
        required = {
            "Name",
            "Team",
            "Position",
            "Price",
            "Ownership",
            "Start",
        }
        missing = required - row.keys()
        assert not missing, f"CSV missing columns: {missing}"

    def test_csv_has_gw_columns(self, pundit_rows: list[dict[str, Any]]) -> None:
        row = pundit_rows[0]
        gw_cols = [k for k in row if k.startswith("GW") and not k.endswith("s")]
        assert len(gw_cols) >= 3, f"Expected 3+ GW columns, got {gw_cols}"

    def test_csv_has_cumulative_columns(
        self, pundit_rows: list[dict[str, Any]]
    ) -> None:
        row = pundit_rows[0]
        next_cols = [k for k in row if k.startswith("Next") and k.endswith("GWs")]
        assert len(next_cols) >= 3, f"Expected 3+ Next*GWs columns, got {next_cols}"

    def test_csv_has_probability_columns(
        self, pundit_rows: list[dict[str, Any]]
    ) -> None:
        row = pundit_rows[0]
        prob_cols = {"CS", "AnytimeGoal", "AnytimeAssist"}
        present = prob_cols.intersection(row.keys())
        assert len(present) >= 2, f"Expected probability columns, found: {present}"

    def test_csv_has_blank_double_flags(
        self, pundit_rows: list[dict[str, Any]]
    ) -> None:
        row = pundit_rows[0]
        assert "Blank" in row or "Double" in row, "Expected Blank/Double flag columns"

    def test_name_field_is_nonempty(self, pundit_rows: list[dict[str, Any]]) -> None:
        for row in pundit_rows[:20]:
            assert row.get("Name", "").strip(), f"Empty name in row: {row}"

    def test_team_field_is_nonempty(self, pundit_rows: list[dict[str, Any]]) -> None:
        teams = {row["Team"].strip() for row in pundit_rows if row.get("Team")}
        assert len(teams) >= 18, f"Expected 18+ teams, got {len(teams)}: {teams}"

    def test_position_values_are_valid(self, pundit_rows: list[dict[str, Any]]) -> None:
        valid = {"GKP", "DEF", "MID", "FWD", "GK", "DF", "MF", "FW"}
        positions = {
            row["Position"].strip() for row in pundit_rows if row.get("Position")
        }
        unknown = positions - valid
        assert not unknown, f"Unknown positions: {unknown}"

    def test_price_is_parseable(self, pundit_rows: list[dict[str, Any]]) -> None:
        """Price may be plain float or formatted like '£5.1m'."""
        for row in pundit_rows[:20]:
            price = row.get("Price", "").strip()
            if price:
                # Strip currency formatting
                cleaned = price.replace("£", "").replace("m", "").strip()
                float(cleaned)  # should not raise

    def test_gw_values_are_numeric_or_empty(
        self, pundit_rows: list[dict[str, Any]]
    ) -> None:
        row = pundit_rows[0]
        gw_cols = [k for k in row if k.startswith("GW") and not k.endswith("s")]
        for col in gw_cols:
            val = row[col]
            if val and val.strip():
                float(val)  # should not raise
