"""
Advancement system for Dolmenwood Virtual DM.

Handles XP awards and character leveling per Dolmenwood Campaign Book rules (p106-107).
"""

from src.advancement.xp_manager import (
    XPAwardType,
    MilestoneType,
    ExplorationGoal,
    MILESTONE_AWARDS,
    XPAwardResult,
    LevelUpResult,
    XPManager,
)

__all__ = [
    "XPAwardType",
    "MilestoneType",
    "ExplorationGoal",
    "MILESTONE_AWARDS",
    "XPAwardResult",
    "LevelUpResult",
    "XPManager",
]
