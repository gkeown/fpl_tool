from __future__ import annotations

import dataclasses
import json
import logging
import unicodedata
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fpl.db.models import Player, PlayerIdMap, Team

logger = logging.getLogger(__name__)

_OVERRIDES_PATH = Path(__file__).parents[3] / "data" / "player_overrides.json"


# ---------------------------------------------------------------------------
# Name normalisation helpers
# ---------------------------------------------------------------------------


def normalize_name(name: str) -> str:
    """Lowercase, strip accents, remove hyphens/apostrophes, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    cleaned = ascii_name.replace("-", " ").replace("'", "").replace(".", "")
    return " ".join(cleaned.lower().split())


def exact_match(fpl_name: str, source_name: str) -> bool:
    """Return True if the two names are identical after normalisation."""
    return normalize_name(fpl_name) == normalize_name(source_name)


def fuzzy_match(
    fpl_name: str, source_name: str, threshold: int = 85
) -> tuple[bool, float]:
    """Return (matched, score) using token-sort ratio."""
    score = float(
        fuzz.token_sort_ratio(normalize_name(fpl_name), normalize_name(source_name))
    )
    return score >= threshold, score


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class MappingResult:
    source: str
    exact_matches: int
    fuzzy_matches: int
    manual_matches: int
    unmatched: int
    unmatched_players: list[str]


# ---------------------------------------------------------------------------
# Override loader
# ---------------------------------------------------------------------------


def _load_overrides() -> dict[str, Any]:
    """Load manual overrides from data/player_overrides.json."""
    try:
        return json.loads(_OVERRIDES_PATH.read_text())  # type: ignore[no-any-return]
    except FileNotFoundError:
        logger.debug("player_overrides.json not found; skipping manual overrides")
        return {}


# ---------------------------------------------------------------------------
# Core mapping logic
# ---------------------------------------------------------------------------


def _build_fpl_index(
    session: Session,
) -> dict[int, list[dict[str, Any]]]:
    """Return {team_fpl_id: [{fpl_id, full_name, web_name}, ...]}."""
    players = session.query(Player).all()
    index: dict[int, list[dict[str, Any]]] = {}
    for p in players:
        entry = {
            "fpl_id": p.fpl_id,
            "full_name": f"{p.first_name} {p.second_name}",
            "web_name": p.web_name,
            "team_id": p.team_id,
        }
        index.setdefault(p.team_id, []).append(entry)
    return index


def _resolve_team_fpl_id(session: Session, team_name: str) -> int | None:
    """Look up team fpl_id by name."""
    team = session.query(Team).filter(Team.name == team_name).first()
    return team.fpl_id if team else None


def run_mapping(
    session: Session,
    source: str,
    source_players: list[dict[str, Any]],
    team_name_field: str = "team_title",
    source_name_field: str = "player_name",
    source_id_field: str = "id",
) -> MappingResult:
    """Map source player records to FPL player IDs.

    Args:
        session: Active DB session.
        source: Source identifier string (e.g. "understat").
        source_players: List of dicts, each with at minimum team name, player
            name, and source ID fields.
        team_name_field: Key in source dict containing the team name.
        source_name_field: Key in source dict containing the player name.
        source_id_field: Key in source dict containing the source's player ID.

    Returns:
        MappingResult summarising match outcomes.
    """
    overrides: dict[str, str] = _load_overrides().get(f"fpl_to_{source}", {})
    fpl_index = _build_fpl_index(session)

    # Build a reverse map: fpl_id (str) -> team_id (so we can look up overrides)
    all_fpl_players: dict[int, dict[str, Any]] = {}
    for entries in fpl_index.values():
        for e in entries:
            all_fpl_players[e["fpl_id"]] = e

    exact_matches = 0
    fuzzy_matches = 0
    manual_matches = 0
    unmatched: list[str] = []

    values_list: list[dict[str, Any]] = []

    for sp in source_players:
        source_id = str(sp[source_id_field])
        source_name = sp[source_name_field]
        team_name = sp[team_name_field]

        # --- Manual override (keyed by source_id) ---
        if source_id in overrides:
            fpl_id = int(overrides[source_id])
            values_list.append(
                {
                    "fpl_id": fpl_id,
                    "source": source,
                    "source_id": source_id,
                    "confidence": 1.0,
                    "matched_by": "manual",
                }
            )
            manual_matches += 1
            continue

        # Resolve team to get candidate FPL players
        team_fpl_id = _resolve_team_fpl_id(session, team_name)
        candidates = fpl_index.get(team_fpl_id, []) if team_fpl_id else []

        matched_fpl_id: int | None = None
        match_method = ""
        match_confidence = 0.0

        # --- Exact match ---
        for candidate in candidates:
            if exact_match(candidate["full_name"], source_name) or exact_match(
                candidate["web_name"], source_name
            ):
                matched_fpl_id = candidate["fpl_id"]
                match_method = "exact"
                match_confidence = 1.0
                break

        # --- Fuzzy match ---
        if matched_fpl_id is None:
            best_score = 0.0
            best_candidate_id: int | None = None
            for candidate in candidates:
                for ref in (candidate["full_name"], candidate["web_name"]):
                    matched, score = fuzzy_match(ref, source_name)
                    if matched and score > best_score:
                        best_score = score
                        best_candidate_id = candidate["fpl_id"]
            if best_candidate_id is not None:
                matched_fpl_id = best_candidate_id
                match_method = "fuzzy"
                match_confidence = best_score / 100.0

        if matched_fpl_id is not None:
            values_list.append(
                {
                    "fpl_id": matched_fpl_id,
                    "source": source,
                    "source_id": source_id,
                    "confidence": match_confidence,
                    "matched_by": match_method,
                }
            )
            if match_method == "exact":
                exact_matches += 1
            else:
                fuzzy_matches += 1
        else:
            unmatched.append(f"{source_name} ({team_name})")
            logger.debug("No FPL match for %s player: %s", source, source_name)

    # Bulk upsert mappings
    if values_list:
        stmt = sqlite_insert(PlayerIdMap).values(values_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=[PlayerIdMap.fpl_id, PlayerIdMap.source],
            set_={
                "source_id": stmt.excluded.source_id,
                "confidence": stmt.excluded.confidence,
                "matched_by": stmt.excluded.matched_by,
            },
        )
        session.execute(stmt)

    return MappingResult(
        source=source,
        exact_matches=exact_matches,
        fuzzy_matches=fuzzy_matches,
        manual_matches=manual_matches,
        unmatched=len(unmatched),
        unmatched_players=unmatched,
    )
