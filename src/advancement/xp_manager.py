"""
XP Manager for Dolmenwood Virtual DM.

Implements XP awards and character leveling per Dolmenwood Campaign Book (p106-107).

XP Award Types:
- Treasure Recovered: 1 XP per 1 GP value (primary source, ~75% of XP)
- Defeating Foes: XP from creature stat blocks
- Magic Items (optional): 1/5 of GP value
- Milestones: Based on party average level and milestone type
- Exploration: Deed award for party average level
- Great Deeds: Individual deed award
- Spending Treasure: 1 XP per 1 GP spent on non-trivial expenditures

When to Award:
XP is awarded upon return to safety (home base, inn, or emerging from dungeon).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from src.data_models import CharacterState
    from src.game_state.global_controller import GlobalController

logger = logging.getLogger(__name__)


# =============================================================================
# XP AWARD TYPES
# =============================================================================


class XPAwardType(str, Enum):
    """Types of XP awards per Dolmenwood rules (p106-107)."""
    # Standard awards (always enabled)
    TREASURE = "treasure"           # 1 XP per 1 GP recovered
    FOES_DEFEATED = "foes_defeated" # From creature stat blocks
    # Optional awards (configurable)
    MAGIC_ITEMS = "magic_items"     # 1/5 of GP value (optional)
    MILESTONE_MAJOR = "milestone_major"  # Major story milestone
    MILESTONE_MINOR = "milestone_minor"  # Minor story milestone
    DEED = "deed"                   # Individual great deed
    EXPLORATION = "exploration"     # Exploration goals
    SPENDING = "spending"           # 1 XP per 1 GP spent (optional)
    CAROUSING = "carousing"         # Spending on parties/celebrations


# Standard XP award types that are always enabled
STANDARD_XP_AWARDS: set[XPAwardType] = {
    XPAwardType.TREASURE,
    XPAwardType.FOES_DEFEATED,
}

# Default optional XP award types (can be configured)
DEFAULT_OPTIONAL_XP_AWARDS: set[XPAwardType] = {
    XPAwardType.MAGIC_ITEMS,
    XPAwardType.EXPLORATION,
    XPAwardType.CAROUSING,
}

# Optional XP awards disabled by default
DISABLED_BY_DEFAULT_XP_AWARDS: set[XPAwardType] = {
    XPAwardType.MILESTONE_MAJOR,
    XPAwardType.MILESTONE_MINOR,
    XPAwardType.DEED,
    XPAwardType.SPENDING,
}


class MilestoneType(str, Enum):
    """Types of milestones for XP awards."""
    MAJOR = "major"     # Major story milestone
    MINOR = "minor"     # Minor story milestone
    DEED = "deed"       # Individual great deed


class ExplorationGoal(str, Enum):
    """Types of exploration goals that grant XP (p107)."""
    SETTLEMENT_FIRST_VISIT = "settlement_first_visit"
    HEX_FIRST_ENTRY = "hex_first_entry"
    FOUND_LOST_SHRINE = "found_lost_shrine"
    FOUND_NODAL_STONE = "found_nodal_stone"
    DISCOVERED_HIDDEN_LOCATION = "discovered_hidden_location"
    MET_FACTION_FIRST_TIME = "met_faction_first_time"
    MET_CREATURE_TYPE_FIRST_TIME = "met_creature_type_first_time"
    CONFIRMED_RUMOUR = "confirmed_rumour"


# =============================================================================
# MILESTONE AWARDS TABLE (p107)
# =============================================================================


# Milestone Awards table based on average party level
# Format: {level_range: {milestone_type: xp_award}}
MILESTONE_AWARDS: dict[tuple[int, int], dict[MilestoneType, int]] = {
    (1, 2): {
        MilestoneType.MAJOR: 2000,
        MilestoneType.MINOR: 400,
        MilestoneType.DEED: 200,
    },
    (3, 3): {
        MilestoneType.MAJOR: 5000,
        MilestoneType.MINOR: 1000,
        MilestoneType.DEED: 500,
    },
    (4, 4): {
        MilestoneType.MAJOR: 10000,
        MilestoneType.MINOR: 2000,
        MilestoneType.DEED: 1000,
    },
    (5, 5): {
        MilestoneType.MAJOR: 15000,
        MilestoneType.MINOR: 3000,
        MilestoneType.DEED: 1500,
    },
    (6, 6): {
        MilestoneType.MAJOR: 30000,
        MilestoneType.MINOR: 6000,
        MilestoneType.DEED: 3000,
    },
    (7, 7): {
        MilestoneType.MAJOR: 60000,
        MilestoneType.MINOR: 12000,
        MilestoneType.DEED: 6000,
    },
    (8, 15): {  # Level 8+ uses same values
        MilestoneType.MAJOR: 120000,
        MilestoneType.MINOR: 24000,
        MilestoneType.DEED: 12000,
    },
}


def get_milestone_award(average_level: int, milestone_type: MilestoneType) -> int:
    """
    Get the XP award for a milestone based on average party level.

    Args:
        average_level: Average level of party (rounded down)
        milestone_type: Type of milestone achieved

    Returns:
        XP award amount
    """
    for (min_level, max_level), awards in MILESTONE_AWARDS.items():
        if min_level <= average_level <= max_level:
            return awards.get(milestone_type, 0)
    # Default to level 8+ for very high levels
    return MILESTONE_AWARDS[(8, 15)].get(milestone_type, 0)


# =============================================================================
# RESULT DATACLASSES
# =============================================================================


@dataclass
class XPAwardResult:
    """Result of an XP award operation."""
    award_type: XPAwardType
    base_xp: int                    # XP before multiplier
    multiplier: float = 1.0         # XP rate multiplier
    final_xp: int = 0               # XP after multiplier
    recipients: list[str] = field(default_factory=list)  # Character IDs
    xp_per_character: int = 0       # XP each character receives
    level_ups: list[str] = field(default_factory=list)   # Characters who leveled
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.final_xp == 0:
            self.final_xp = int(self.base_xp * self.multiplier)


@dataclass
class LevelUpResult:
    """Result of a level-up operation."""
    character_id: str
    character_name: str
    old_level: int
    new_level: int
    xp_total: int
    xp_for_next_level: Optional[int]  # None if at max level
    hp_gained: int = 0
    new_abilities: list[str] = field(default_factory=list)
    new_spell_slots: dict[int, int] = field(default_factory=dict)
    attack_bonus_change: int = 0
    saving_throw_changes: dict[str, int] = field(default_factory=dict)


# =============================================================================
# XP MANAGER
# =============================================================================


class XPManager:
    """
    Manages XP awards and character leveling per Dolmenwood rules (p106-107).

    Handles:
    - XP awards from various sources (treasure, foes, milestones, etc.)
    - XP multipliers for rate adjustment
    - Level-up checks and application
    - HP rolling for level-ups
    """

    def __init__(self, controller: "GlobalController"):
        """
        Initialize the XP manager.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self._xp_multiplier: float = 1.0  # Rate adjustment multiplier

        # Import DiceRoller lazily to avoid circular imports
        from src.data_models import DiceRoller
        self.dice = DiceRoller()

        # Enabled XP award types (standard + default optional)
        # Standard awards are always included and cannot be disabled
        self._enabled_award_types: set[XPAwardType] = (
            STANDARD_XP_AWARDS | DEFAULT_OPTIONAL_XP_AWARDS
        )

        # Track exploration discoveries for XP
        self._visited_settlements: set[str] = set()
        self._visited_hexes: set[str] = set()
        self._met_factions: set[str] = set()
        self._met_creature_types: set[str] = set()
        self._confirmed_rumours: set[str] = set()

    @property
    def xp_multiplier(self) -> float:
        """Get the current XP multiplier."""
        return self._xp_multiplier

    @xp_multiplier.setter
    def xp_multiplier(self, value: float) -> None:
        """Set the XP multiplier (for rate adjustment)."""
        self._xp_multiplier = max(0.0, value)
        logger.info(f"XP multiplier set to {self._xp_multiplier}")

    # =========================================================================
    # AWARD TYPE CONFIGURATION
    # =========================================================================

    @property
    def enabled_award_types(self) -> set[XPAwardType]:
        """Get the set of enabled XP award types."""
        return self._enabled_award_types.copy()

    def is_award_type_enabled(self, award_type: XPAwardType) -> bool:
        """
        Check if an XP award type is enabled.

        Args:
            award_type: The award type to check

        Returns:
            True if enabled
        """
        return award_type in self._enabled_award_types

    def enable_award_type(self, award_type: XPAwardType) -> None:
        """
        Enable an XP award type.

        Args:
            award_type: The award type to enable
        """
        self._enabled_award_types.add(award_type)
        logger.info(f"Enabled XP award type: {award_type.value}")

    def disable_award_type(self, award_type: XPAwardType) -> bool:
        """
        Disable an XP award type.

        Standard award types (treasure, foes_defeated) cannot be disabled.

        Args:
            award_type: The award type to disable

        Returns:
            True if disabled, False if it's a standard type that cannot be disabled
        """
        if award_type in STANDARD_XP_AWARDS:
            logger.warning(
                f"Cannot disable standard XP award type: {award_type.value}"
            )
            return False

        self._enabled_award_types.discard(award_type)
        logger.info(f"Disabled XP award type: {award_type.value}")
        return True

    def set_enabled_award_types(self, award_types: set[XPAwardType]) -> None:
        """
        Set the enabled XP award types.

        Standard award types are always included.

        Args:
            award_types: Set of award types to enable
        """
        # Always include standard awards
        self._enabled_award_types = STANDARD_XP_AWARDS | award_types
        logger.info(
            f"Set enabled XP award types: "
            f"{[t.value for t in self._enabled_award_types]}"
        )

    def get_award_type_status(self) -> dict[str, dict[str, Any]]:
        """
        Get status of all XP award types.

        Returns:
            Dictionary with status info for each award type
        """
        status = {}
        for award_type in XPAwardType:
            is_standard = award_type in STANDARD_XP_AWARDS
            status[award_type.value] = {
                "enabled": award_type in self._enabled_award_types,
                "standard": is_standard,
                "can_disable": not is_standard,
            }
        return status

    def _check_award_enabled(self, award_type: XPAwardType) -> bool:
        """
        Check if an award type is enabled, logging if disabled.

        Args:
            award_type: The award type to check

        Returns:
            True if enabled
        """
        if award_type not in self._enabled_award_types:
            logger.debug(f"XP award type disabled: {award_type.value}")
            return False
        return True

    # =========================================================================
    # XP QUERIES
    # =========================================================================

    def get_xp_for_next_level(self, character: "CharacterState") -> Optional[int]:
        """
        Get the XP required for a character's next level.

        Args:
            character: The character to check

        Returns:
            XP threshold for next level, or None if at max level
        """
        from src.classes import ClassManager

        manager = ClassManager()
        class_def = manager.get(character.character_class)
        if not class_def:
            return None

        next_level = character.level + 1
        progression = class_def.get_progression_at_level(next_level)
        if not progression:
            return None  # At max level

        return progression.experience_required

    def get_xp_progress(self, character: "CharacterState") -> dict[str, Any]:
        """
        Get detailed XP progress for a character.

        Args:
            character: The character to check

        Returns:
            Dictionary with XP progress details
        """
        current_xp = character.experience_points
        next_level_xp = self.get_xp_for_next_level(character)

        # Get current level threshold
        from src.classes import ClassManager
        manager = ClassManager()
        class_def = manager.get(character.character_class)
        current_level_xp = 0
        if class_def:
            prog = class_def.get_progression_at_level(character.level)
            if prog:
                current_level_xp = prog.experience_required

        result = {
            "character_id": character.character_id,
            "name": character.name,
            "level": character.level,
            "experience_points": current_xp,
            "current_level_xp": current_level_xp,
            "next_level_xp": next_level_xp,
            "at_max_level": next_level_xp is None,
        }

        if next_level_xp is not None:
            xp_needed = next_level_xp - current_xp
            xp_into_level = current_xp - current_level_xp
            level_xp_range = next_level_xp - current_level_xp
            progress_pct = (xp_into_level / level_xp_range * 100) if level_xp_range > 0 else 100

            result["xp_needed"] = xp_needed
            result["xp_into_level"] = xp_into_level
            result["progress_percent"] = round(progress_pct, 1)

        return result

    def can_level_up(self, character: "CharacterState") -> bool:
        """
        Check if a character has enough XP to level up.

        Args:
            character: The character to check

        Returns:
            True if the character can level up
        """
        next_level_xp = self.get_xp_for_next_level(character)
        if next_level_xp is None:
            return False  # At max level
        return character.experience_points >= next_level_xp

    def get_party_average_level(self) -> int:
        """
        Calculate the average level of the party (rounded down).

        Used for milestone XP calculations.

        Returns:
            Average party level
        """
        characters = self.controller.get_all_characters()
        if not characters:
            return 1

        total_levels = sum(c.level for c in characters if c)
        return total_levels // len(characters)

    # =========================================================================
    # XP AWARDS - STANDARD
    # =========================================================================

    def award_treasure_xp(
        self,
        gold_value: int,
        character_ids: Optional[list[str]] = None,
        apply_multiplier: bool = True
    ) -> XPAwardResult:
        """
        Award XP for treasure recovered (p106).

        1 XP per 1 GP value of treasure (coins, gems, jewellery, art objects).
        Magic items do not grant XP - their powers are their own reward.

        Args:
            gold_value: Total GP value of treasure
            character_ids: Specific characters (default: all party)
            apply_multiplier: Whether to apply XP rate multiplier

        Returns:
            XPAwardResult with details
        """
        multiplier = self._xp_multiplier if apply_multiplier else 1.0
        result = XPAwardResult(
            award_type=XPAwardType.TREASURE,
            base_xp=gold_value,
            multiplier=multiplier,
            details={"gold_value": gold_value},
        )

        self._distribute_xp(result, character_ids)
        return result

    def award_foes_xp(
        self,
        creature_xp_values: list[int],
        character_ids: Optional[list[str]] = None,
        apply_multiplier: bool = True,
        creature_names: Optional[list[str]] = None
    ) -> XPAwardResult:
        """
        Award XP for defeating foes (p106).

        XP from creature stat blocks for slain, fled, or surrendered foes.

        Args:
            creature_xp_values: List of XP values for each creature defeated
            character_ids: Specific characters (default: all party)
            apply_multiplier: Whether to apply XP rate multiplier
            creature_names: Optional names of creatures for logging

        Returns:
            XPAwardResult with details
        """
        total_xp = sum(creature_xp_values)
        multiplier = self._xp_multiplier if apply_multiplier else 1.0

        result = XPAwardResult(
            award_type=XPAwardType.FOES_DEFEATED,
            base_xp=total_xp,
            multiplier=multiplier,
            details={
                "creatures_defeated": len(creature_xp_values),
                "creature_xp_values": creature_xp_values,
                "creature_names": creature_names or [],
            },
        )

        self._distribute_xp(result, character_ids)
        return result

    # =========================================================================
    # XP AWARDS - OPTIONAL
    # =========================================================================

    def award_magic_item_xp(
        self,
        gold_value: int,
        character_ids: Optional[list[str]] = None,
        sold_without_use: bool = False,
        apply_multiplier: bool = True
    ) -> XPAwardResult:
        """
        Award XP for magic items (optional rule, p106).

        1/5 of GP value, or full sale value if sold without using.

        Args:
            gold_value: GP value of the magic item
            character_ids: Specific characters (default: all party)
            sold_without_use: If True, award full GP value as XP
            apply_multiplier: Whether to apply XP rate multiplier

        Returns:
            XPAwardResult with details
        """
        # Check if this award type is enabled
        if not self._check_award_enabled(XPAwardType.MAGIC_ITEMS):
            return XPAwardResult(
                award_type=XPAwardType.MAGIC_ITEMS,
                base_xp=0,
                details={"disabled": True, "gold_value": gold_value},
            )

        if sold_without_use:
            base_xp = gold_value
        else:
            base_xp = gold_value // 5

        multiplier = self._xp_multiplier if apply_multiplier else 1.0

        result = XPAwardResult(
            award_type=XPAwardType.MAGIC_ITEMS,
            base_xp=base_xp,
            multiplier=multiplier,
            details={
                "gold_value": gold_value,
                "sold_without_use": sold_without_use,
            },
        )

        self._distribute_xp(result, character_ids)
        return result

    def award_milestone_xp(
        self,
        milestone_type: MilestoneType,
        character_ids: Optional[list[str]] = None,
        description: str = "",
        apply_multiplier: bool = True
    ) -> XPAwardResult:
        """
        Award XP for achieving a milestone (p107).

        XP based on average party level and milestone type.

        Args:
            milestone_type: Major, minor, or deed milestone
            character_ids: Specific characters (default: all party)
            description: Description of the milestone
            apply_multiplier: Whether to apply XP rate multiplier

        Returns:
            XPAwardResult with details
        """
        # Determine award type based on milestone type
        award_type = (
            XPAwardType.MILESTONE_MAJOR if milestone_type == MilestoneType.MAJOR
            else XPAwardType.MILESTONE_MINOR if milestone_type == MilestoneType.MINOR
            else XPAwardType.DEED
        )

        # Check if this award type is enabled
        if not self._check_award_enabled(award_type):
            return XPAwardResult(
                award_type=award_type,
                base_xp=0,
                details={"disabled": True, "milestone_type": milestone_type.value},
            )

        avg_level = self.get_party_average_level()
        base_xp = get_milestone_award(avg_level, milestone_type)
        multiplier = self._xp_multiplier if apply_multiplier else 1.0

        result = XPAwardResult(
            award_type=award_type,
            base_xp=base_xp,
            multiplier=multiplier,
            details={
                "milestone_type": milestone_type.value,
                "average_party_level": avg_level,
                "description": description,
            },
        )

        self._distribute_xp(result, character_ids)
        return result

    def award_exploration_xp(
        self,
        goal: ExplorationGoal,
        goal_id: str,
        character_ids: Optional[list[str]] = None,
        apply_multiplier: bool = True
    ) -> XPAwardResult:
        """
        Award XP for exploration goals (p107).

        Deed award for party's average level. Tracks discoveries to prevent
        duplicate awards.

        Args:
            goal: Type of exploration goal
            goal_id: Unique identifier for the goal (e.g., hex ID, settlement name)
            character_ids: Specific characters (default: all party)
            apply_multiplier: Whether to apply XP rate multiplier

        Returns:
            XPAwardResult with details
        """
        # Check if this award type is enabled
        if not self._check_award_enabled(XPAwardType.EXPLORATION):
            return XPAwardResult(
                award_type=XPAwardType.EXPLORATION,
                base_xp=0,
                details={"disabled": True, "goal": goal.value, "goal_id": goal_id},
            )

        # Check if already discovered
        tracking_sets = {
            ExplorationGoal.SETTLEMENT_FIRST_VISIT: self._visited_settlements,
            ExplorationGoal.HEX_FIRST_ENTRY: self._visited_hexes,
            ExplorationGoal.MET_FACTION_FIRST_TIME: self._met_factions,
            ExplorationGoal.MET_CREATURE_TYPE_FIRST_TIME: self._met_creature_types,
            ExplorationGoal.CONFIRMED_RUMOUR: self._confirmed_rumours,
        }

        tracking_set = tracking_sets.get(goal)
        if tracking_set is not None:
            if goal_id in tracking_set:
                # Already discovered, no XP
                return XPAwardResult(
                    award_type=XPAwardType.EXPLORATION,
                    base_xp=0,
                    details={
                        "goal": goal.value,
                        "goal_id": goal_id,
                        "already_discovered": True,
                    },
                )
            tracking_set.add(goal_id)

        avg_level = self.get_party_average_level()
        base_xp = get_milestone_award(avg_level, MilestoneType.DEED)
        multiplier = self._xp_multiplier if apply_multiplier else 1.0

        result = XPAwardResult(
            award_type=XPAwardType.EXPLORATION,
            base_xp=base_xp,
            multiplier=multiplier,
            details={
                "goal": goal.value,
                "goal_id": goal_id,
                "average_party_level": avg_level,
            },
        )

        self._distribute_xp(result, character_ids)
        return result

    def award_deed_xp(
        self,
        character_id: str,
        description: str = "",
        apply_multiplier: bool = True
    ) -> XPAwardResult:
        """
        Award XP to individual character for a great deed (p107).

        Uses the deed award for the character's level.

        Args:
            character_id: The character who performed the deed
            description: Description of the deed
            apply_multiplier: Whether to apply XP rate multiplier

        Returns:
            XPAwardResult with details
        """
        # Check if this award type is enabled
        if not self._check_award_enabled(XPAwardType.DEED):
            return XPAwardResult(
                award_type=XPAwardType.DEED,
                base_xp=0,
                details={"disabled": True, "character_id": character_id},
            )

        character = self.controller.get_character(character_id)
        if not character:
            return XPAwardResult(
                award_type=XPAwardType.DEED,
                base_xp=0,
                details={"error": f"Character not found: {character_id}"},
            )

        base_xp = get_milestone_award(character.level, MilestoneType.DEED)
        multiplier = self._xp_multiplier if apply_multiplier else 1.0

        result = XPAwardResult(
            award_type=XPAwardType.DEED,
            base_xp=base_xp,
            multiplier=multiplier,
            details={
                "character_level": character.level,
                "description": description,
            },
        )

        # Award to individual only
        self._distribute_xp(result, [character_id])
        return result

    def award_spending_xp(
        self,
        character_id: str,
        gold_spent: int,
        expenditure_type: str = "non-trivial",
        apply_multiplier: bool = True
    ) -> XPAwardResult:
        """
        Award XP for spending treasure (optional rule, p107).

        1 XP per 1 GP spent on non-trivial expenditures.
        Does not include daily living expenses or adventure gear.

        Args:
            character_id: The character spending gold
            gold_spent: Amount of gold spent
            expenditure_type: Type of expenditure (e.g., "philanthropy", "carousing")
            apply_multiplier: Whether to apply XP rate multiplier

        Returns:
            XPAwardResult with details
        """
        # Check if this award type is enabled
        if not self._check_award_enabled(XPAwardType.SPENDING):
            return XPAwardResult(
                award_type=XPAwardType.SPENDING,
                base_xp=0,
                details={"disabled": True, "gold_spent": gold_spent},
            )

        multiplier = self._xp_multiplier if apply_multiplier else 1.0

        result = XPAwardResult(
            award_type=XPAwardType.SPENDING,
            base_xp=gold_spent,
            multiplier=multiplier,
            details={
                "gold_spent": gold_spent,
                "expenditure_type": expenditure_type,
            },
        )

        # Award to individual only
        self._distribute_xp(result, [character_id])
        return result

    def award_carousing_xp(
        self,
        character_id: str,
        gold_spent: int,
        mishap_modifier: float = 1.0,
        apply_multiplier: bool = True
    ) -> XPAwardResult:
        """
        Award XP for carousing (p107).

        Base XP equals gold spent, modified by mishap results.

        Args:
            character_id: The character carousing
            gold_spent: Amount of gold spent
            mishap_modifier: Multiplier from mishap roll (0.5 for major mishap, 1.5 for bonus)
            apply_multiplier: Whether to apply XP rate multiplier

        Returns:
            XPAwardResult with details
        """
        # Check if this award type is enabled
        if not self._check_award_enabled(XPAwardType.CAROUSING):
            return XPAwardResult(
                award_type=XPAwardType.CAROUSING,
                base_xp=0,
                details={"disabled": True, "gold_spent": gold_spent},
            )

        base_xp = int(gold_spent * mishap_modifier)
        multiplier = self._xp_multiplier if apply_multiplier else 1.0

        result = XPAwardResult(
            award_type=XPAwardType.CAROUSING,
            base_xp=base_xp,
            multiplier=multiplier,
            details={
                "gold_spent": gold_spent,
                "mishap_modifier": mishap_modifier,
            },
        )

        # Award to individual only
        self._distribute_xp(result, [character_id])
        return result

    # =========================================================================
    # XP DISTRIBUTION
    # =========================================================================

    def _distribute_xp(
        self,
        result: XPAwardResult,
        character_ids: Optional[list[str]] = None
    ) -> None:
        """
        Distribute XP to characters and check for level-ups.

        Args:
            result: The XPAwardResult to populate
            character_ids: Specific characters (default: all party)
        """
        if character_ids:
            characters = [
                self.controller.get_character(cid)
                for cid in character_ids
                if self.controller.get_character(cid)
            ]
        else:
            characters = self.controller.get_all_characters()

        if not characters:
            return

        # Calculate XP per character (split evenly)
        total_xp = result.final_xp
        xp_per_char = total_xp // len(characters)
        result.xp_per_character = xp_per_char

        # Apply XP to each character
        for character in characters:
            if not character:
                continue

            result.recipients.append(character.character_id)

            # Add XP
            old_xp = character.experience_points
            character.experience_points += xp_per_char

            logger.info(
                f"{character.name} gained {xp_per_char} XP "
                f"({old_xp} -> {character.experience_points})"
            )

            # Check for level-up
            if self.can_level_up(character):
                result.level_ups.append(character.character_id)

    # =========================================================================
    # LEVELING UP
    # =========================================================================

    def level_up(
        self,
        character_id: str,
        hp_roll: Optional[int] = None
    ) -> Optional[LevelUpResult]:
        """
        Level up a character if they have sufficient XP.

        Per Dolmenwood rules:
        - Check XP threshold for next level
        - Roll or use provided HP gain
        - Update attack bonus, saving throws, abilities
        - Update spell slots for spellcasters

        Args:
            character_id: The character to level up
            hp_roll: Optional pre-rolled HP value (default: roll automatically)

        Returns:
            LevelUpResult if successful, None if cannot level up
        """
        character = self.controller.get_character(character_id)
        if not character:
            logger.warning(f"Character not found: {character_id}")
            return None

        if not self.can_level_up(character):
            logger.info(f"{character.name} does not have enough XP to level up")
            return None

        from src.classes import ClassManager

        manager = ClassManager()
        class_def = manager.get(character.character_class)
        if not class_def:
            logger.warning(f"Unknown class: {character.character_class}")
            return None

        old_level = character.level
        new_level = old_level + 1

        # Store old values for comparison
        old_attack_bonus = character.attack_bonus
        old_saves = character.saving_throws.copy() if character.saving_throws else {}

        # Roll HP if not provided
        if hp_roll is None:
            hit_die = class_def.hit_die
            roll = self.dice.roll(f"1{hit_die}", f"HP for level {new_level}")
            hp_roll = roll.total

            # Apply Constitution modifier
            con_mod = character.get_ability_modifier("constitution")
            hp_roll = max(1, hp_roll + con_mod)  # Minimum 1 HP gained

        # Apply level up
        character.level = new_level
        character.hp_max += hp_roll
        character.hp_current = min(character.hp_current + hp_roll, character.hp_max)

        # Update class data (attack bonus, saves, abilities, spell slots)
        manager.update_character_for_level(character, new_level)

        # Calculate changes
        attack_bonus_change = character.attack_bonus - old_attack_bonus

        save_changes = {}
        if character.saving_throws:
            for save_type, new_val in character.saving_throws.items():
                old_val = old_saves.get(save_type, new_val)
                if new_val != old_val:
                    save_changes[save_type] = old_val - new_val  # Lower is better

        # Get new abilities at this level
        new_abilities = []
        abilities_at_level = class_def.get_abilities_at_level(new_level)
        if abilities_at_level:
            # Find abilities that are new (not at previous level)
            prev_abilities = class_def.get_abilities_at_level(old_level)
            prev_ability_ids = {a.ability_id for a in prev_abilities}
            new_abilities = [
                a.name for a in abilities_at_level
                if a.ability_id not in prev_ability_ids
            ]

        # Get new spell slots
        new_spell_slots = {}
        if class_def.magic_type.value != "none":
            slots = class_def.get_spell_slots(new_level)
            prev_slots = class_def.get_spell_slots(old_level)
            if slots and prev_slots:
                for rank, count in slots.items():
                    prev_count = prev_slots.get(rank, 0)
                    if count > prev_count:
                        new_spell_slots[rank] = count - prev_count

        # Get XP for next level
        xp_for_next = self.get_xp_for_next_level(character)

        result = LevelUpResult(
            character_id=character_id,
            character_name=character.name,
            old_level=old_level,
            new_level=new_level,
            xp_total=character.experience_points,
            xp_for_next_level=xp_for_next,
            hp_gained=hp_roll,
            new_abilities=new_abilities,
            new_spell_slots=new_spell_slots,
            attack_bonus_change=attack_bonus_change,
            saving_throw_changes=save_changes,
        )

        logger.info(
            f"{character.name} leveled up! Level {old_level} -> {new_level}, "
            f"+{hp_roll} HP, +{attack_bonus_change} attack bonus"
        )

        return result

    def level_up_all_ready(self) -> list[LevelUpResult]:
        """
        Level up all characters who have sufficient XP.

        Returns:
            List of LevelUpResult for each character who leveled
        """
        results = []
        characters = self.controller.get_all_characters()

        for character in characters:
            if not character:
                continue

            # Keep leveling while they can (in case of multiple level-ups)
            while self.can_level_up(character):
                result = self.level_up(character.character_id)
                if result:
                    results.append(result)
                else:
                    break

        return results

    # =========================================================================
    # NEW CHARACTER XP
    # =========================================================================

    def get_starting_xp_for_new_character(
        self,
        use_half_average: bool = True
    ) -> int:
        """
        Calculate starting XP for a new character joining the party (p106).

        Per optional rule: new PCs can start with half the XP of the party's
        average, placing them roughly one level below.

        Args:
            use_half_average: If True, use half average party XP; else 0

        Returns:
            Starting XP for new character
        """
        if not use_half_average:
            return 0

        characters = self.controller.get_all_characters()
        if not characters:
            return 0

        total_xp = sum(c.experience_points for c in characters if c)
        average_xp = total_xp // len(characters)

        return average_xp // 2

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def get_exploration_state(self) -> dict[str, Any]:
        """Get current exploration tracking state for serialization."""
        return {
            "visited_settlements": list(self._visited_settlements),
            "visited_hexes": list(self._visited_hexes),
            "met_factions": list(self._met_factions),
            "met_creature_types": list(self._met_creature_types),
            "confirmed_rumours": list(self._confirmed_rumours),
            "xp_multiplier": self._xp_multiplier,
            "enabled_award_types": [t.value for t in self._enabled_award_types],
        }

    def load_exploration_state(self, state: dict[str, Any]) -> None:
        """Load exploration tracking state from serialization."""
        self._visited_settlements = set(state.get("visited_settlements", []))
        self._visited_hexes = set(state.get("visited_hexes", []))
        self._met_factions = set(state.get("met_factions", []))
        self._met_creature_types = set(state.get("met_creature_types", []))
        self._confirmed_rumours = set(state.get("confirmed_rumours", []))
        self._xp_multiplier = state.get("xp_multiplier", 1.0)

        # Load enabled award types (default to standard + default optional if not present)
        enabled_types = state.get("enabled_award_types")
        if enabled_types:
            self._enabled_award_types = STANDARD_XP_AWARDS | {
                XPAwardType(t) for t in enabled_types
                if t in [e.value for e in XPAwardType]
            }
        else:
            self._enabled_award_types = STANDARD_XP_AWARDS | DEFAULT_OPTIONAL_XP_AWARDS
