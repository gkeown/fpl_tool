from __future__ import annotations

import enum


class Position(enum.IntEnum):
    GKP = 1
    DEF = 2
    MID = 3
    FWD = 4


class PlayerStatus(enum.StrEnum):
    AVAILABLE = "a"
    DOUBTFUL = "d"
    INJURED = "i"
    UNAVAILABLE = "u"
    SUSPENDED = "s"
    NOT_AVAILABLE = "n"


class IngestSource(enum.StrEnum):
    FPL_BOOTSTRAP = "fpl_bootstrap"
    FPL_FIXTURES = "fpl_fixtures"
    FPL_PLAYER_HISTORY = "fpl_player_history"
    UNDERSTAT = "understat"
    FBREF = "fbref"
    ODDS = "odds"
    INJURIES = "injuries"
