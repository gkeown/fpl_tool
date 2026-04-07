from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.analysis.transfers import (
    compare_players,
    suggest_transfers,
)
from fpl.db.models import (
    Base,
    CustomFdr,
    Gameweek,
    MyAccount,
    MyTeamPlayer,
    Player,
    PlayerFormScore,
    PlayerGameweekStats,
    Team,
    UnderstatMatch,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


def _make_team(session: Session, fpl_id: int, short_name: str = "TST") -> Team:
    team = Team(
        fpl_id=fpl_id,
        code=fpl_id,
        name=f"Team {fpl_id}",
        short_name=short_name,
        strength=3,
        strength_attack_home=1200,
        strength_attack_away=1100,
        strength_defence_home=1200,
        strength_defence_away=1100,
        played=10,
        win=5,
        draw=2,
        loss=3,
        points=17,
        position=5,
        updated_at=_now(),
    )
    session.add(team)
    session.flush()
    return team


def _make_player(
    session: Session,
    fpl_id: int,
    team_id: int,
    element_type: int = 3,
    now_cost: int = 80,
    status: str = "a",
    minutes: int = 900,
    selected_by_percent: str = "5.0",
    web_name: str | None = None,
) -> Player:
    player = Player(
        fpl_id=fpl_id,
        code=fpl_id,
        first_name="Test",
        second_name=f"Player{fpl_id}",
        web_name=web_name or f"Player{fpl_id}",
        team_id=team_id,
        element_type=element_type,
        now_cost=now_cost,
        selected_by_percent=selected_by_percent,
        status=status,
        form="5.0",
        points_per_game="5.0",
        total_points=50,
        minutes=minutes,
        goals_scored=3,
        assists=2,
        clean_sheets=1,
        bonus=5,
        transfers_in=500,
        transfers_out=200,
        goals_conceded=5,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=1,
        red_cards=0,
        saves=0,
        starts=10,
        expected_goals="2.50",
        expected_assists="1.50",
        expected_goal_involvements="4.00",
        expected_goals_conceded="4.00",
        updated_at=_now(),
    )
    session.add(player)
    session.flush()
    return player


def _make_my_team_player(
    session: Session,
    player_id: int,
    selling_price: int = 80,
    position: int = 5,
    is_captain: bool = False,
) -> MyTeamPlayer:
    mtp = MyTeamPlayer(
        player_id=player_id,
        selling_price=selling_price,
        purchase_price=selling_price,
        position=position,
        is_captain=is_captain,
        is_vice_captain=False,
        multiplier=2 if is_captain else 1,
        fetched_at=_now(),
    )
    session.add(mtp)
    session.flush()
    return mtp


def _make_form_score(
    session: Session,
    player_id: int,
    gameweek: int,
    form_score: float = 60.0,
) -> PlayerFormScore:
    fs = PlayerFormScore(
        player_id=player_id,
        gameweek=gameweek,
        form_score=form_score,
        xg_component=6.0,
        xa_component=5.0,
        bps_component=6.0,
        ict_component=6.0,
        minutes_component=7.0,
        points_component=6.0,
        computed_at=_now(),
    )
    session.add(fs)
    session.flush()
    return fs


def _make_gameweek(session: Session, gw_id: int, is_current: bool = True) -> Gameweek:
    gw = Gameweek(
        id=gw_id,
        name=f"Gameweek {gw_id}",
        deadline_time="2025-03-01T11:00:00Z",
        finished=False,
        is_current=is_current,
        is_next=False,
        is_previous=False,
        updated_at=_now(),
    )
    session.add(gw)
    session.flush()
    return gw


def _make_custom_fdr(
    session: Session,
    team_id: int,
    gameweek: int,
    opponent_id: int,
    overall_difficulty: float = 2.5,
) -> CustomFdr:
    fdr = CustomFdr(
        team_id=team_id,
        gameweek=gameweek,
        opponent_id=opponent_id,
        is_home=True,
        attack_difficulty=overall_difficulty,
        defence_difficulty=overall_difficulty,
        overall_difficulty=overall_difficulty,
        computed_at=_now(),
    )
    session.add(fdr)
    session.flush()
    return fdr


def _make_account(
    session: Session, bank: int = 50, free_transfers: int = 1
) -> MyAccount:
    acc = MyAccount(
        id=1,
        fpl_team_id=12345,
        player_name="Test Manager",
        overall_points=1500,
        overall_rank=100000,
        bank=bank,
        total_transfers=10,
        free_transfers=free_transfers,
        gameweek_points=50,
        fetched_at=_now(),
    )
    session.add(acc)
    session.flush()
    return acc


def _make_gw_stat(
    session: Session,
    player_id: int,
    gameweek: int,
    fixture_id: int,
    minutes: int = 90,
    total_points: int = 6,
) -> PlayerGameweekStats:
    stat = PlayerGameweekStats(
        player_id=player_id,
        gameweek=gameweek,
        fixture_id=fixture_id,
        opponent_team=2,
        was_home=True,
        minutes=minutes,
        total_points=total_points,
        goals_scored=1,
        assists=0,
        clean_sheets=0,
        bonus=1,
        bps=20,
        ict_index="6.0",
        influence="15.0",
        creativity="10.0",
        threat="20.0",
        selected=500000,
        transfers_in=500,
        transfers_out=100,
        value=80,
        expected_goals="0.35",
        expected_assists="0.15",
        expected_goals_conceded="0.80",
        goals_conceded=1,
        own_goals=0,
        penalties_saved=0,
        penalties_missed=0,
        yellow_cards=0,
        red_cards=0,
        saves=0,
        starts=1,
    )
    session.add(stat)
    session.flush()
    return stat


# ---------------------------------------------------------------------------
# Tests: suggest_transfers
# ---------------------------------------------------------------------------


def test_suggest_transfers_returns_empty_when_no_team(db_session: Session) -> None:
    """Should return empty list when MyTeamPlayer table is empty."""
    _make_gameweek(db_session, 30)
    db_session.commit()

    result = suggest_transfers(db_session)
    assert result == []


def test_suggest_transfers_finds_improvement(db_session: Session) -> None:
    """Should find a better replacement when one exists at same position."""
    team1 = _make_team(db_session, 1)
    team2 = _make_team(db_session, 2)
    opp_team = _make_team(db_session, 99)

    gw = _make_gameweek(db_session, 30)

    # Out player: low form, costly, in squad
    out_player = _make_player(db_session, 1, team1.fpl_id, element_type=3, now_cost=100)
    _make_my_team_player(db_session, out_player.fpl_id, selling_price=100)
    _make_form_score(db_session, out_player.fpl_id, gw.id, form_score=20.0)
    _make_custom_fdr(db_session, team1.fpl_id, 31, opp_team.fpl_id, 4.0)
    _make_custom_fdr(db_session, team1.fpl_id, 32, opp_team.fpl_id, 4.0)
    _make_custom_fdr(db_session, team1.fpl_id, 33, opp_team.fpl_id, 4.0)

    # In player: high form, cheap, not in squad, same position
    in_player = _make_player(db_session, 2, team2.fpl_id, element_type=3, now_cost=80)
    _make_form_score(db_session, in_player.fpl_id, gw.id, form_score=90.0)
    _make_custom_fdr(db_session, team2.fpl_id, 31, opp_team.fpl_id, 1.5)
    _make_custom_fdr(db_session, team2.fpl_id, 32, opp_team.fpl_id, 1.5)
    _make_custom_fdr(db_session, team2.fpl_id, 33, opp_team.fpl_id, 1.5)

    _make_account(db_session, bank=50)
    db_session.commit()

    result = suggest_transfers(db_session, top=5)

    assert len(result) >= 1
    top_suggestion = result[0]
    assert top_suggestion.out_player.fpl_id == out_player.fpl_id
    assert top_suggestion.in_player.fpl_id == in_player.fpl_id
    assert top_suggestion.delta_value > 0


def test_suggest_transfers_respects_budget_constraint(db_session: Session) -> None:
    """Should not suggest a player the user cannot afford."""
    team1 = _make_team(db_session, 1)
    team2 = _make_team(db_session, 2)
    opp_team = _make_team(db_session, 99)

    gw = _make_gameweek(db_session, 30)

    out_player = _make_player(db_session, 1, team1.fpl_id, element_type=3, now_cost=60)
    _make_my_team_player(db_session, out_player.fpl_id, selling_price=60)
    _make_form_score(db_session, out_player.fpl_id, gw.id, form_score=10.0)
    _make_custom_fdr(db_session, team1.fpl_id, 31, opp_team.fpl_id, 4.5)

    # Expensive in player — costs more than bank + selling price
    expensive_player = _make_player(
        db_session, 2, team2.fpl_id, element_type=3, now_cost=200
    )
    _make_form_score(db_session, expensive_player.fpl_id, gw.id, form_score=95.0)
    _make_custom_fdr(db_session, team2.fpl_id, 31, opp_team.fpl_id, 1.0)

    # Bank is 0 and selling price is 60, so max budget = 60 < 200
    _make_account(db_session, bank=0)
    db_session.commit()

    result = suggest_transfers(db_session, top=10)

    # The expensive player should not appear in suggestions
    in_player_ids = {s.in_player.fpl_id for s in result}
    assert expensive_player.fpl_id not in in_player_ids


def test_suggest_transfers_respects_position_constraint(db_session: Session) -> None:
    """Should only suggest players at the same position as the outgoing player."""
    team1 = _make_team(db_session, 1)
    team2 = _make_team(db_session, 2)
    opp_team = _make_team(db_session, 99)

    gw = _make_gameweek(db_session, 30)

    # Out player is a MID (element_type=3)
    out_player = _make_player(db_session, 1, team1.fpl_id, element_type=3, now_cost=80)
    _make_my_team_player(db_session, out_player.fpl_id, selling_price=80)
    _make_form_score(db_session, out_player.fpl_id, gw.id, form_score=20.0)
    _make_custom_fdr(db_session, team1.fpl_id, 31, opp_team.fpl_id, 4.0)

    # In player is a FWD (element_type=4) — wrong position
    fwd_player = _make_player(db_session, 2, team2.fpl_id, element_type=4, now_cost=70)
    _make_form_score(db_session, fwd_player.fpl_id, gw.id, form_score=95.0)
    _make_custom_fdr(db_session, team2.fpl_id, 31, opp_team.fpl_id, 1.0)

    _make_account(db_session, bank=50)
    db_session.commit()

    result = suggest_transfers(db_session, top=10)

    # The FWD should not be suggested as a replacement for the MID
    in_player_ids = {s.in_player.fpl_id for s in result}
    assert fwd_player.fpl_id not in in_player_ids


def test_suggest_transfers_max_three_per_team_constraint(db_session: Session) -> None:
    """Should not suggest bringing in a 4th player from the same team.

    Scenario: squad has 3 MIDs from team_target and 1 MID from team_out.
    Out: MID from team_out (a different team).
    In: MID from team_target — would create 4 from team_target, so blocked.
    """
    team_target = _make_team(db_session, 2)  # already 3 in squad
    team_out = _make_team(db_session, 3)  # team of the outgoing player
    opp_team = _make_team(db_session, 99)

    gw = _make_gameweek(db_session, 30)

    # 3 players from team_target in squad; use DEF to avoid confusing with MID
    for pid in [10, 11, 12]:
        p = _make_player(
            db_session, pid, team_target.fpl_id, element_type=2, now_cost=60
        )
        _make_my_team_player(db_session, p.fpl_id, selling_price=60, position=pid)
        _make_form_score(db_session, p.fpl_id, gw.id, form_score=50.0)

    # Insert FDR once for team_target (shared across all 3 players)
    _make_custom_fdr(db_session, team_target.fpl_id, 31, opp_team.fpl_id, 2.0)

    # Outgoing player: DEF from team_out
    out_player = _make_player(
        db_session, 20, team_out.fpl_id, element_type=2, now_cost=55
    )
    _make_my_team_player(db_session, out_player.fpl_id, selling_price=55, position=5)
    _make_form_score(db_session, out_player.fpl_id, gw.id, form_score=10.0)
    _make_custom_fdr(db_session, team_out.fpl_id, 31, opp_team.fpl_id, 4.5)

    # Potential in player from team_target (DEF) — would be 4th from that team
    blocked_player = _make_player(
        db_session, 30, team_target.fpl_id, element_type=2, now_cost=50
    )
    _make_form_score(db_session, blocked_player.fpl_id, gw.id, form_score=95.0)
    # FDR already set for team_target above

    _make_account(db_session, bank=50)
    db_session.commit()

    result = suggest_transfers(db_session, top=20)

    # Filter to suggestions where out_player is the team_out DEF (player 20)
    relevant = [s for s in result if s.out_player.fpl_id == out_player.fpl_id]
    in_player_ids = {s.in_player.fpl_id for s in relevant}
    assert blocked_player.fpl_id not in in_player_ids


def test_suggest_transfers_excludes_existing_squad_members(
    db_session: Session,
) -> None:
    """Players already in the squad should never appear as incoming suggestions."""
    team1 = _make_team(db_session, 1)
    opp_team = _make_team(db_session, 99)

    gw = _make_gameweek(db_session, 30)

    # Two players in squad
    p1 = _make_player(db_session, 1, team1.fpl_id, element_type=3, now_cost=80)
    p2 = _make_player(db_session, 2, team1.fpl_id, element_type=3, now_cost=80)

    _make_my_team_player(db_session, p1.fpl_id, selling_price=80, position=5)
    _make_my_team_player(db_session, p2.fpl_id, selling_price=80, position=6)

    _make_form_score(db_session, p1.fpl_id, gw.id, form_score=20.0)
    _make_form_score(db_session, p2.fpl_id, gw.id, form_score=95.0)

    _make_custom_fdr(db_session, team1.fpl_id, 31, opp_team.fpl_id, 4.0)

    _make_account(db_session, bank=100)
    db_session.commit()

    result = suggest_transfers(db_session, top=10)

    in_player_ids = {s.in_player.fpl_id for s in result}
    assert p1.fpl_id not in in_player_ids
    assert p2.fpl_id not in in_player_ids


def test_suggest_transfers_uses_bank_from_account(db_session: Session) -> None:
    """Budget should default to MyAccount.bank + selling price."""
    team1 = _make_team(db_session, 1)
    team2 = _make_team(db_session, 2)
    opp_team = _make_team(db_session, 99)

    gw = _make_gameweek(db_session, 30)

    out_player = _make_player(db_session, 1, team1.fpl_id, element_type=3, now_cost=70)
    _make_my_team_player(db_session, out_player.fpl_id, selling_price=70)
    _make_form_score(db_session, out_player.fpl_id, gw.id, form_score=10.0)
    _make_custom_fdr(db_session, team1.fpl_id, 31, opp_team.fpl_id, 4.5)

    # Available = bank (30) + selling (70) = 100 → affordable
    in_player = _make_player(db_session, 2, team2.fpl_id, element_type=3, now_cost=95)
    _make_form_score(db_session, in_player.fpl_id, gw.id, form_score=90.0)
    _make_custom_fdr(db_session, team2.fpl_id, 31, opp_team.fpl_id, 1.5)

    _make_account(db_session, bank=30)
    db_session.commit()

    result = suggest_transfers(db_session, top=10)

    in_player_ids = {s.in_player.fpl_id for s in result}
    assert in_player.fpl_id in in_player_ids


# ---------------------------------------------------------------------------
# Tests: compare_players
# ---------------------------------------------------------------------------


def test_compare_players_returns_none_when_player_not_found(
    db_session: Session,
) -> None:
    """Should return None when either player cannot be found."""
    _make_team(db_session, 1)
    _make_player(db_session, 1, 1, web_name="Salah")
    _make_gameweek(db_session, 30)
    db_session.commit()

    result = compare_players(db_session, "Salah", "zzzzzzzzzzqqqqqqqq")
    assert result is None


def test_compare_players_returns_both_comparisons(db_session: Session) -> None:
    """Should return two PlayerComparison objects when both players are found."""
    team = _make_team(db_session, 1)
    p1 = _make_player(db_session, 1, team.fpl_id, now_cost=95, web_name="Salah")
    p2 = _make_player(db_session, 2, team.fpl_id, now_cost=85, web_name="Haaland")

    gw = _make_gameweek(db_session, 30)
    _make_form_score(db_session, p1.fpl_id, gw.id, form_score=80.0)
    _make_form_score(db_session, p2.fpl_id, gw.id, form_score=90.0)
    db_session.commit()

    result = compare_players(db_session, "Salah", "Haaland")

    assert result is not None
    c1, c2 = result
    assert c1.player.fpl_id == p1.fpl_id
    assert c2.player.fpl_id == p2.fpl_id


def test_compare_players_stats_are_correct(db_session: Session) -> None:
    """Verify that comparison stats reflect the player data correctly."""
    team = _make_team(db_session, 1)
    opp = _make_team(db_session, 2)
    p1 = _make_player(db_session, 1, team.fpl_id, now_cost=100, web_name="Kane")

    gw = _make_gameweek(db_session, 30)
    _make_form_score(db_session, p1.fpl_id, gw.id, form_score=75.0)
    _make_custom_fdr(db_session, team.fpl_id, 31, opp.fpl_id, 2.0)
    _make_gw_stat(db_session, p1.fpl_id, 30, 3000, minutes=90, total_points=10)

    p2 = _make_player(db_session, 2, team.fpl_id, now_cost=90, web_name="Vardy")
    _make_form_score(db_session, p2.fpl_id, gw.id, form_score=60.0)
    db_session.commit()

    result = compare_players(db_session, "Kane", "Vardy")

    assert result is not None
    c1, c2 = result
    assert c1.cost == 100
    assert c2.cost == 90
    assert abs(c1.form_score - 75.0) < 1e-6
    assert abs(c2.form_score - 60.0) < 1e-6
    assert c1.goals == p1.goals_scored
    assert c1.assists == p1.assists
    assert c1.clean_sheets == p1.clean_sheets


def test_compare_players_uses_understat_xg(db_session: Session) -> None:
    """xG/90 should prefer Understat season aggregate when available."""
    team = _make_team(db_session, 1)
    p1 = _make_player(db_session, 1, team.fpl_id, web_name="PlayerA")
    p2 = _make_player(db_session, 2, team.fpl_id, web_name="PlayerB")

    gw = _make_gameweek(db_session, 30)
    _make_form_score(db_session, p1.fpl_id, gw.id)
    _make_form_score(db_session, p2.fpl_id, gw.id)

    agg = UnderstatMatch(
        player_id=p1.fpl_id,
        date="season_aggregate",
        opponent="season_aggregate",
        was_home=True,
        minutes=900,
        goals=9,
        xg=9.0,
        assists=4,
        xa=3.6,
        shots=40,
        key_passes=20,
        npg=9,
        npxg=8.5,
    )
    db_session.add(agg)
    db_session.commit()

    result = compare_players(db_session, "PlayerA", "PlayerB")

    assert result is not None
    c1, _ = result
    # 9.0 xg / 900 mins * 90 = 0.9
    assert abs(c1.xg_per90 - 0.9) < 1e-6
