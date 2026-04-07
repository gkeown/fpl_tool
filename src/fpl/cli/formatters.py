from __future__ import annotations

_POSITION_MAP: dict[int, str] = {
    1: "GKP",
    2: "DEF",
    3: "MID",
    4: "FWD",
}


def fdr_color(difficulty: float) -> str:
    """Return Rich color markup string for FDR value (green=easy, red=hard)."""
    if difficulty <= 2.0:
        return "bold green"
    elif difficulty <= 3.0:
        return "green"
    elif difficulty <= 3.5:
        return "yellow"
    elif difficulty <= 4.0:
        return "dark_orange"
    else:
        return "bold red"


def form_color(form_score: float) -> str:
    """Return Rich color for custom form score 0-100 (green=high, red=low)."""
    if form_score >= 80.0:
        return "bold green"
    elif form_score >= 60.0:
        return "green"
    elif form_score >= 40.0:
        return "yellow"
    elif form_score >= 20.0:
        return "dark_orange"
    else:
        return "red"


def fpl_form_color(fpl_form: float) -> str:
    """Return Rich color for FPL's own form field (0-10 scale).

    FPL form is average points per game over the last 30 days.
    """
    if fpl_form >= 8.0:
        return "bold green"
    elif fpl_form >= 6.0:
        return "green"
    elif fpl_form >= 4.0:
        return "yellow"
    elif fpl_form >= 2.0:
        return "dark_orange"
    else:
        return "red"


def format_cost(cost_tenths: int) -> str:
    """Format cost from tenths to display string (e.g. 105 -> '10.5')."""
    return f"{cost_tenths / 10:.1f}"


def position_str(element_type: int) -> str:
    """Convert element_type int to position string."""
    return _POSITION_MAP.get(element_type, "UNK")
