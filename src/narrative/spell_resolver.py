"""
Spell Resolver for Dolmenwood Virtual DM.

Handles spell casting outside of combat, including:
- Spell lookup and validation
- Slot consumption (arcane/divine) and usage tracking (glamours/runes)
- Effect application and duration tracking
- Concentration management
- Mechanical effect resolution (damage, conditions, stat modifiers)
- Saving throw resolution
- Game state integration
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
import re
import uuid

if TYPE_CHECKING:
    from src.data_models import CharacterState, DiceRoller
    from src.game_state.global_controller import GlobalController

from src.narrative.intent_parser import SaveType


# =============================================================================
# ENUMS
# =============================================================================


class DurationType(str, Enum):
    """How a spell's duration is tracked."""

    INSTANT = "instant"  # Immediate effect, no duration
    ROUNDS = "rounds"  # Duration in combat rounds
    TURNS = "turns"  # Duration in exploration turns (10 min)
    HOURS = "hours"  # Duration in hours
    DAYS = "days"  # Duration in days
    CONCENTRATION = "concentration"  # Lasts while concentrating
    PERMANENT = "permanent"  # Lasts until dispelled/dismissed
    SPECIAL = "special"  # Custom duration logic


class RangeType(str, Enum):
    """How a spell's range is specified."""

    SELF = "self"  # Affects caster only
    TOUCH = "touch"  # Must touch target
    RANGED = "ranged"  # Has a range in feet
    AREA = "area"  # Affects an area


class SpellEffectType(str, Enum):
    """How a spell's effects are resolved."""

    MECHANICAL = "mechanical"  # Fully resolved by Python (damage, conditions)
    NARRATIVE = "narrative"  # LLM describes, minimal mechanics
    HYBRID = "hybrid"  # Python mechanics + LLM narration


class MagicType(str, Enum):
    """Type of magic."""

    ARCANE = "arcane"  # Wizard/Magic-User spells
    DIVINE = "divine"  # Cleric spells
    FAIRY_GLAMOUR = "fairy_glamour"  # Elf/Grimalkin/Woodgrue glamours
    RUNE = "rune"  # Fairy runes (Enchanter)
    KNACK = "knack"  # Mossling quasi-magical crafts


class RuneMagnitude(str, Enum):
    """Magnitude of fairy runes - determines power and usage limits."""

    LESSER = "lesser"  # Available at level 1+
    GREATER = "greater"  # Available at level 5+
    MIGHTY = "mighty"  # Available at level 9+


class UsageFrequency(str, Enum):
    """How often a glamour or ability can be used."""

    AT_WILL = "at_will"  # No limit
    ONCE_PER_ROUND = "once_per_round"  # Once per combat round
    ONCE_PER_TURN = "once_per_turn"  # Once per exploration turn (10 min)
    ONCE_PER_DAY = "once_per_day"  # Once per day total
    ONCE_PER_DAY_PER_SUBJECT = "once_per_day_per_subject"  # Once per day per target


class MechanicalEffectCategory(str, Enum):
    """Categories of mechanical spell effects."""

    DAMAGE = "damage"  # Deals HP damage
    HEALING = "healing"  # Restores HP
    CONDITION = "condition"  # Applies a condition
    BUFF = "buff"  # Positive stat modifier
    DEBUFF = "debuff"  # Negative stat modifier
    MOVEMENT = "movement"  # Affects movement/position
    SUMMON = "summon"  # Creates creatures/objects
    UTILITY = "utility"  # Other mechanical effects


# =============================================================================
# MECHANICAL EFFECT DATA CLASSES
# =============================================================================


@dataclass
class MechanicalEffect:
    """
    A structured mechanical effect from a spell.

    Parsed from spell descriptions to enable Python-based resolution.
    """

    category: MechanicalEffectCategory
    description: str = ""

    # Damage/healing
    damage_dice: Optional[str] = None  # e.g., "2d6", "1d8+2"
    damage_type: Optional[str] = None  # e.g., "fire", "cold", "holy"
    healing_dice: Optional[str] = None  # e.g., "1d6+1"

    # Conditions
    condition_applied: Optional[str] = None  # e.g., "charmed", "frightened"
    condition_duration: Optional[str] = None  # Duration in turns/rounds

    # Stat modifiers
    stat_modified: Optional[str] = None  # e.g., "AC", "attack", "speed"
    modifier_value: Optional[int] = None  # e.g., +2, -4
    modifier_dice: Optional[str] = None  # For variable modifiers
    condition_context: Optional[str] = None  # When modifier applies: "vs_missiles", "vs_melee"

    # Saving throw for this effect
    save_type: Optional[str] = None  # doom, ray, hold, blast, spell
    save_negates: bool = False  # Save completely negates effect
    save_halves: bool = False  # Save reduces effect by half

    # Targeting
    max_targets: Optional[int] = None  # Number of targets affected
    max_hd_affected: Optional[int] = None  # Max HD of creatures affected
    area_radius: Optional[int] = None  # Radius in feet for area effects


@dataclass
class ParsedMechanicalEffects:
    """Container for all parsed mechanical effects from a spell."""

    effects: list[MechanicalEffect] = field(default_factory=list)
    primary_effect: Optional[MechanicalEffect] = None

    # Quick access flags
    deals_damage: bool = False
    applies_condition: bool = False
    requires_save: bool = False
    affects_multiple: bool = False

    def add_effect(self, effect: MechanicalEffect) -> None:
        """Add an effect and update flags."""
        self.effects.append(effect)
        if self.primary_effect is None:
            self.primary_effect = effect

        if effect.category == MechanicalEffectCategory.DAMAGE:
            self.deals_damage = True
        if effect.category == MechanicalEffectCategory.CONDITION:
            self.applies_condition = True
        if effect.save_type:
            self.requires_save = True
        if effect.max_targets and effect.max_targets > 1:
            self.affects_multiple = True
        if effect.area_radius:
            self.affects_multiple = True


# =============================================================================
# SPELL COMPONENTS DATA CLASSES
# =============================================================================


@dataclass
class SpellComponent:
    """
    A material component required to cast a spell.

    Examples:
    - Fairy Servant: 50gp trinket or magical fungus (consumed)
    - Crystal Resonance: 50gp crystal (may be destroyed - 1-in-20 chance)
    """

    component_type: str  # "trinket", "crystal", "fungus", "gem"
    min_value_gp: int = 0  # Minimum GP value required
    consumed: bool = True  # Whether component is used up on casting
    destruction_chance: float = 0.0  # Chance of destruction (0.0-1.0)
    alternatives: list[str] = field(default_factory=list)  # Alternative component types
    description: str = ""  # Original text description


# =============================================================================
# LEVEL SCALING DATA CLASSES
# =============================================================================


class LevelScalingType(str, Enum):
    """What aspect of the spell scales with level."""

    DURATION = "duration"  # Duration increases with level
    TARGETS = "targets"  # Number of targets increases
    PROJECTILES = "projectiles"  # Number of projectiles/shards
    DAMAGE = "damage"  # Damage dice scale
    HEALING = "healing"  # Healing dice scale
    AREA = "area"  # Area of effect expands
    RANGE = "range"  # Range increases


@dataclass
class LevelScaling:
    """
    Defines how a spell effect scales with caster level.

    Examples:
    - "1 Turn per Level" -> base_value=1, per_levels=1, scaling_type=DURATION
    - "one stream per Level" -> base_value=1, per_levels=1, scaling_type=PROJECTILES
    - "one additional per 3 Levels" -> base_value=1, per_levels=3, scaling_type=PROJECTILES
    """

    scaling_type: LevelScalingType
    base_value: int = 1  # Value at minimum level
    per_levels: int = 1  # Add 1 per X levels
    minimum_level: int = 1  # Level at which scaling starts
    maximum_value: Optional[int] = None  # Cap on the scaled value
    description: str = ""  # Original text for reference

    def calculate_scaled_value(self, caster_level: int) -> int:
        """
        Calculate the scaled value for a given caster level.

        Args:
            caster_level: The caster's level

        Returns:
            The scaled value
        """
        if caster_level < self.minimum_level:
            return self.base_value

        # Calculate additional value from level scaling
        effective_level = caster_level - self.minimum_level + 1
        additional = effective_level // self.per_levels

        scaled = self.base_value + additional

        # Apply cap if specified
        if self.maximum_value is not None:
            scaled = min(scaled, self.maximum_value)

        return scaled


# =============================================================================
# USAGE TRACKING DATA CLASSES
# =============================================================================


@dataclass
class GlamourUsageRecord:
    """Tracks usage of a glamour for frequency limits."""

    spell_id: str
    caster_id: str

    # Per-turn tracking
    last_turn_used: int = -1  # Turn number when last used

    # Per-day tracking
    times_used_today: int = 0

    # Per-subject tracking (for "once per day per subject")
    subjects_today: set[str] = field(default_factory=set)

    def can_use(
        self,
        frequency: UsageFrequency,
        current_turn: int,
        target_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Check if this glamour can be used based on frequency limits.

        Returns:
            Tuple of (can_use, reason)
        """
        if frequency == UsageFrequency.AT_WILL:
            return True, "No usage limit"

        if frequency == UsageFrequency.ONCE_PER_TURN:
            if self.last_turn_used == current_turn:
                return False, "Already used this turn"
            return True, "Can use"

        if frequency == UsageFrequency.ONCE_PER_DAY:
            if self.times_used_today >= 1:
                return False, "Already used today"
            return True, "Can use"

        if frequency == UsageFrequency.ONCE_PER_DAY_PER_SUBJECT:
            if target_id and target_id in self.subjects_today:
                return False, f"Already used on this subject today"
            return True, "Can use"

        return True, "Unknown frequency - allowing"

    def record_use(
        self,
        frequency: UsageFrequency,
        current_turn: int,
        target_id: Optional[str] = None,
    ) -> None:
        """Record that this glamour was used."""
        self.last_turn_used = current_turn
        self.times_used_today += 1

        if target_id and frequency == UsageFrequency.ONCE_PER_DAY_PER_SUBJECT:
            self.subjects_today.add(target_id)

    def reset_daily(self) -> None:
        """Reset daily usage counters (called at dawn/rest)."""
        self.times_used_today = 0
        self.subjects_today = set()


@dataclass
class RuneUsageState:
    """
    Tracks rune usage for an Enchanter.

    Runes have different usage limits based on magnitude:
    - Lesser runes: Typically usable multiple times per day
    - Greater runes: Usually 1-2 uses per day
    - Mighty runes: Often 1 use per day or per adventure
    """

    caster_id: str

    # Daily usage by magnitude
    lesser_uses_today: int = 0
    greater_uses_today: int = 0
    mighty_uses_today: int = 0

    # Per-rune tracking
    rune_uses: dict[str, int] = field(default_factory=dict)

    # Maximum uses per magnitude per day (based on character level)
    max_lesser_daily: int = 3
    max_greater_daily: int = 2
    max_mighty_daily: int = 1

    def can_use_rune(
        self, rune_id: str, magnitude: RuneMagnitude
    ) -> tuple[bool, str]:
        """Check if a rune can be used."""
        if magnitude == RuneMagnitude.LESSER:
            if self.lesser_uses_today >= self.max_lesser_daily:
                return False, f"No lesser rune uses remaining today (max {self.max_lesser_daily})"
        elif magnitude == RuneMagnitude.GREATER:
            if self.greater_uses_today >= self.max_greater_daily:
                return False, f"No greater rune uses remaining today (max {self.max_greater_daily})"
        elif magnitude == RuneMagnitude.MIGHTY:
            if self.mighty_uses_today >= self.max_mighty_daily:
                return False, f"No mighty rune uses remaining today (max {self.max_mighty_daily})"

        return True, "Can use rune"

    def use_rune(self, rune_id: str, magnitude: RuneMagnitude) -> None:
        """Record that a rune was used."""
        if magnitude == RuneMagnitude.LESSER:
            self.lesser_uses_today += 1
        elif magnitude == RuneMagnitude.GREATER:
            self.greater_uses_today += 1
        elif magnitude == RuneMagnitude.MIGHTY:
            self.mighty_uses_today += 1

        self.rune_uses[rune_id] = self.rune_uses.get(rune_id, 0) + 1

    def reset_daily(self) -> None:
        """Reset daily rune usage (called at dawn/rest)."""
        self.lesser_uses_today = 0
        self.greater_uses_today = 0
        self.mighty_uses_today = 0
        self.rune_uses = {}

    def get_remaining(self, magnitude: RuneMagnitude) -> int:
        """Get remaining uses for a magnitude."""
        if magnitude == RuneMagnitude.LESSER:
            return max(0, self.max_lesser_daily - self.lesser_uses_today)
        elif magnitude == RuneMagnitude.GREATER:
            return max(0, self.max_greater_daily - self.greater_uses_today)
        elif magnitude == RuneMagnitude.MIGHTY:
            return max(0, self.max_mighty_daily - self.mighty_uses_today)
        return 0


# =============================================================================
# SAVE RESOLUTION
# =============================================================================


@dataclass
class SaveResult:
    """Result of a saving throw."""

    success: bool
    save_type: str
    target_id: str
    roll: int
    modifier: int
    total: int
    target_number: int
    natural_20: bool = False
    natural_1: bool = False

    @property
    def effect_negated(self) -> bool:
        """Whether the effect is completely negated by the save."""
        return self.success

    @property
    def effect_halved(self) -> bool:
        """Whether the effect is halved (for damage saves)."""
        return self.success


# =============================================================================
# SPELL DATA CLASSES
# =============================================================================


@dataclass
class SpellData:
    """
    Spell data structure for database storage.

    Contains both raw text fields and parsed mechanical components.
    """

    # Core identification
    spell_id: str
    name: str
    level: Optional[int]  # None for fairy glamours
    magic_type: MagicType

    # Raw text fields (from source)
    duration: str  # Raw text: "1d6 Turns + 1 Turn per Level"
    range: str  # Raw text: "60'"
    description: str  # Full description

    # Reversible spell info
    reversible: bool = False
    reversed_name: Optional[str] = None

    # Parsed mechanical components
    duration_type: DurationType = DurationType.INSTANT
    duration_value: Optional[str] = None  # Dice notation or fixed value
    duration_per_level: bool = False  # Does duration scale with level?
    range_feet: Optional[int] = None  # Parsed range in feet
    range_type: RangeType = RangeType.RANGED

    # Effect classification
    effect_type: SpellEffectType = SpellEffectType.HYBRID
    save_type: Optional[SaveType] = None
    save_negates: bool = False  # Does save completely negate?

    # Target restrictions (HD/level limits)
    max_target_level: Optional[int] = None  # Max level of affected targets
    max_target_hd: Optional[int] = None  # Max HD of affected monsters
    affects_living_only: bool = False  # Only affects living creatures

    # Usage limits (especially for glamours)
    usage_frequency: Optional[str] = None  # "once per turn", "once per day per subject"
    parsed_usage_frequency: Optional[UsageFrequency] = None  # Parsed enum value
    kindred_restricted: list[str] = field(default_factory=list)

    # Rune-specific (for fairy runes)
    rune_magnitude: Optional[RuneMagnitude] = None  # lesser, greater, mighty

    # Concentration
    requires_concentration: bool = False
    concentration_allows_movement: bool = True
    concentration_allows_actions: bool = False

    # Mechanical effects (parsed from description)
    mechanical_effects: dict[str, Any] = field(default_factory=dict)

    # Level scaling effects (parsed from description)
    level_scaling: list["LevelScaling"] = field(default_factory=list)

    # Material components required
    required_components: list["SpellComponent"] = field(default_factory=list)

    # Source tracking
    page_reference: str = ""
    source_book: str = ""


@dataclass
class ActiveSpellEffect:
    """
    Tracks an active spell effect on an entity.

    Tied to the turn/time system for duration tracking.
    """

    # Identification
    effect_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    spell_id: str = ""
    spell_name: str = ""

    # Caster and target
    caster_id: str = ""
    target_id: str = ""  # Character, NPC, Monster, or "area:location_id"
    target_type: str = "creature"  # "creature", "object", "area"

    # Duration tracking (tied to turn/time system)
    duration_type: DurationType = DurationType.INSTANT
    duration_remaining: Optional[int] = None  # Rounds or Turns remaining
    duration_unit: str = "turns"  # "rounds" or "turns"
    expires_at: Optional[datetime] = None  # For real-time tracking if needed

    # Concentration
    requires_concentration: bool = False
    concentration_broken: bool = False

    # Effect details
    effect_type: SpellEffectType = SpellEffectType.HYBRID
    mechanical_effects: dict[str, Any] = field(default_factory=dict)
    narrative_description: str = ""

    # State
    is_active: bool = True
    dismissed: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    # Recurring save mechanics (for effects like Ingratiate's daily saves)
    recurring_save_type: Optional[str] = None  # "spell", "doom", etc.
    recurring_save_frequency: Optional[str] = None  # "daily", "hourly", "per_turn"
    recurring_save_ends_effect: bool = True  # If save succeeds, does effect end?
    last_save_check_day: int = 0  # Day number of last save check (for daily)
    last_save_check_turn: int = 0  # Turn number of last save check (for per_turn)

    def tick(self, time_unit: str = "turns") -> bool:
        """
        Advance time and check if effect expires.

        Args:
            time_unit: "rounds" or "turns"

        Returns:
            True if effect has expired
        """
        if not self.is_active:
            return True

        if self.duration_type == DurationType.PERMANENT:
            return False

        if self.duration_type == DurationType.INSTANT:
            return True

        if self.concentration_broken:
            self.is_active = False
            return True

        if self.duration_remaining is not None and self.duration_unit == time_unit:
            self.duration_remaining -= 1
            if self.duration_remaining <= 0:
                self.is_active = False
                return True

        return False

    def break_concentration(self) -> bool:
        """
        Break concentration on this effect.

        Called when caster takes damage or performs another action.

        Returns:
            True if effect was concentration-based and is now broken
        """
        if self.requires_concentration and not self.concentration_broken:
            self.concentration_broken = True
            self.is_active = False
            return True
        return False

    def dismiss(self) -> bool:
        """
        Dismiss the spell effect voluntarily.

        Returns:
            True if effect was dismissed
        """
        if self.is_active:
            self.dismissed = True
            self.is_active = False
            return True
        return False


@dataclass
class SpellCastResult:
    """Result of attempting to cast a spell."""

    success: bool
    spell_id: str
    spell_name: str

    # What happened
    reason: str = ""  # Why it succeeded/failed
    effect_created: Optional[ActiveSpellEffect] = None

    # Mechanical outcomes
    damage_dealt: Optional[dict[str, Any]] = None  # {target_id: amount, ...}
    healing_applied: Optional[dict[str, Any]] = None  # {target_id: amount, ...}
    conditions_applied: list[str] = field(default_factory=list)
    stat_modifiers_applied: list[dict[str, Any]] = field(default_factory=list)

    # Save resolution
    save_required: bool = False
    save_result: Optional[SaveResult] = None
    save_results: list[SaveResult] = field(default_factory=list)  # For multi-target

    # Resource consumption
    slot_consumed: bool = False
    slot_level: Optional[int] = None
    glamour_usage_recorded: bool = False
    rune_usage_recorded: bool = False

    # Targets affected
    targets_affected: list[str] = field(default_factory=list)
    targets_saved: list[str] = field(default_factory=list)
    targets_failed_save: list[str] = field(default_factory=list)

    # For LLM narration
    narrative_context: dict[str, Any] = field(default_factory=dict)
    effect_type: SpellEffectType = SpellEffectType.HYBRID

    # Errors
    error: Optional[str] = None


class SpellResolver:
    """
    Resolves spell casting outside of combat.

    Handles:
    - Spell lookup (from database or cache)
    - Slot/usage validation (arcane/divine spell slots)
    - Glamour usage tracking (per-turn, per-day, per-subject)
    - Rune magnitude usage tracking (lesser/greater/mighty daily limits)
    - Saving throw resolution
    - Mechanical effect application (damage, conditions, stat modifiers)
    - Duration tracking
    - Concentration management
    - Game state integration
    """

    def __init__(
        self,
        spell_database: Optional[dict[str, SpellData]] = None,
        controller: Optional["GlobalController"] = None,
    ):
        """
        Initialize the spell resolver.

        Args:
            spell_database: Optional pre-loaded spell data
            controller: Optional game controller for applying effects
        """
        self._spell_cache: dict[str, SpellData] = spell_database or {}
        self._active_effects: list[ActiveSpellEffect] = []
        self._controller = controller

        # Usage tracking for glamours: {(caster_id, spell_id): GlamourUsageRecord}
        self._glamour_usage: dict[tuple[str, str], GlamourUsageRecord] = {}

        # Usage tracking for runes: {caster_id: RuneUsageState}
        self._rune_usage: dict[str, RuneUsageState] = {}

        # Current turn number for tracking "once per turn" limits
        self._current_turn: int = 0

        # Dice roller reference
        self._dice: Optional["DiceRoller"] = None

    def set_controller(self, controller: "GlobalController") -> None:
        """Set the game controller for effect application."""
        self._controller = controller

    def set_turn(self, turn: int) -> None:
        """Update the current turn number for usage tracking."""
        self._current_turn = turn

    def advance_turn(self) -> None:
        """Advance the turn counter by 1."""
        self._current_turn += 1

    def lookup_spell(self, spell_id: str) -> Optional[SpellData]:
        """
        Look up a spell by ID.

        Args:
            spell_id: The spell's unique identifier

        Returns:
            SpellData if found, None otherwise
        """
        return self._spell_cache.get(spell_id)

    def lookup_spell_by_name(self, name: str) -> Optional[SpellData]:
        """
        Look up a spell by name (case-insensitive).

        Args:
            name: The spell's name

        Returns:
            SpellData if found, None otherwise
        """
        name_lower = name.lower()
        for spell in self._spell_cache.values():
            if spell.name.lower() == name_lower:
                return spell
        return None

    def can_cast_spell(
        self, caster: "CharacterState", spell: SpellData, target_id: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Check if a caster can cast a spell.

        Validates:
        - Character's class can cast this spell type
        - Spell is prepared/known
        - Spell slot is available (for ranked spells)
        - Kindred restrictions (for Mossling Knacks)

        Args:
            caster: The character attempting to cast
            spell: The spell to cast
            target_id: Optional target ID

        Returns:
            Tuple of (can_cast, reason)
        """
        from src.classes.class_manager import get_class_manager

        class_manager = get_class_manager()

        # Check if caster's class can use this magic type
        spell_magic_type = spell.magic_type.value if spell.magic_type else "unknown"
        if not class_manager.can_character_cast_spell_type(caster, spell_magic_type):
            class_magic = class_manager.get_character_magic_type(caster)
            magic_name = class_magic.value if class_magic else "no"
            return False, (
                f"{caster.name}'s class cannot cast {spell_magic_type} spells "
                f"(has {magic_name} magic)"
            )

        # Check if caster has the spell prepared/known
        has_spell = any(s.spell_id == spell.spell_id for s in caster.spells)

        # For glamours, also check class_data.glamours_known
        if not has_spell and spell.magic_type == MagicType.FAIRY_GLAMOUR:
            glamours = caster.get_glamours_known() if hasattr(caster, "get_glamours_known") else []
            has_spell = spell.spell_id in glamours

        # For runes, check class_data.runes_known
        if not has_spell and spell_magic_type == "rune":
            runes = caster.get_runes_known() if hasattr(caster, "get_runes_known") else []
            has_spell = spell.spell_id in runes

        if not has_spell:
            return False, f"{caster.name} does not have {spell.name} prepared"

        # Check spell slot availability (for ranked spells: arcane, holy)
        if spell.level is not None and spell.magic_type in (MagicType.ARCANE, MagicType.DIVINE):
            # Use the new spell slot system
            if hasattr(caster, "has_spell_slot") and not caster.has_spell_slot(spell.level):
                return False, f"{caster.name} has no Rank {spell.level} spell slots remaining"

            # Legacy check: spell cast_today flag
            caster_spell = next((s for s in caster.spells if s.spell_id == spell.spell_id), None)
            if caster_spell and caster_spell.cast_today:
                return False, f"{spell.name} has already been cast today"

        # Check concentration conflicts
        if spell.requires_concentration:
            active_concentration = self.get_concentration_effect(caster.character_id)
            if active_concentration:
                # Would need to break existing concentration - allow but note
                pass

        # Check usage frequency for glamours
        if spell.magic_type == MagicType.FAIRY_GLAMOUR:
            can_use, reason = self._check_glamour_usage(
                caster.character_id, spell, target_id
            )
            if not can_use:
                return False, reason

        # Check rune usage limits
        if spell.magic_type == MagicType.RUNE:
            can_use, reason = self._check_rune_usage(caster.character_id, spell)
            if not can_use:
                return False, reason

        # Check kindred restrictions (only applies to Mossling Knacks)
        if spell.kindred_restricted:
            caster_kindred = caster.kindred.lower() if hasattr(caster, "kindred") else ""
            allowed_kindreds = [k.lower() for k in spell.kindred_restricted]
            if caster_kindred not in allowed_kindreds:
                return False, f"Only {', '.join(spell.kindred_restricted)} can cast {spell.name}"

        return True, "Can cast"

    def resolve_spell(
        self,
        caster: "CharacterState",
        spell: SpellData,
        target_id: Optional[str] = None,
        target_ids: Optional[list[str]] = None,
        target_description: Optional[str] = None,
        dice_roller: Optional["DiceRoller"] = None,
    ) -> SpellCastResult:
        """
        Resolve casting a spell outside of combat.

        Performs complete spell resolution including:
        - Resource consumption (spell slots, glamour usage, rune usage)
        - Saving throw resolution
        - Mechanical effect application (damage, healing, conditions)
        - Duration and concentration tracking
        - Game state integration

        Args:
            caster: The character casting the spell
            spell: The spell being cast
            target_id: Optional single target ID
            target_ids: Optional list of target IDs (for multi-target spells)
            target_description: Description of target for narrative
            dice_roller: Dice roller for any rolls needed

        Returns:
            SpellCastResult with complete outcomes
        """
        # Store dice roller for use in helper methods
        self._dice = dice_roller

        # Combine single target and multiple targets
        all_targets = []
        if target_ids:
            all_targets.extend(target_ids)
        if target_id and target_id not in all_targets:
            all_targets.append(target_id)
        if not all_targets:
            all_targets = [caster.character_id]  # Self-target if no target specified

        # Check if can cast
        can_cast, reason = self.can_cast_spell(caster, spell, target_id)
        if not can_cast:
            return SpellCastResult(
                success=False,
                spell_id=spell.spell_id,
                spell_name=spell.name,
                reason=reason,
                error=reason,
                effect_type=spell.effect_type,
            )

        # Break any existing concentration
        if spell.requires_concentration:
            existing = self.get_concentration_effect(caster.character_id)
            if existing:
                existing.break_concentration()

        # Consume resources based on magic type
        slot_consumed = False
        glamour_usage_recorded = False
        rune_usage_recorded = False

        if spell.level is not None and spell.magic_type in (MagicType.ARCANE, MagicType.DIVINE):
            # Consume spell slot for arcane/divine magic
            if hasattr(caster, "use_spell_slot"):
                slot_consumed = caster.use_spell_slot(spell.level)

            # Also mark the specific spell as cast (legacy support)
            for s in caster.spells:
                if s.spell_id == spell.spell_id:
                    s.cast_today = True
                    if not slot_consumed:
                        slot_consumed = True
                    break

        elif spell.magic_type == MagicType.FAIRY_GLAMOUR:
            # Record glamour usage
            self._record_glamour_usage(caster.character_id, spell, target_id)
            glamour_usage_recorded = True

        elif spell.magic_type == MagicType.RUNE:
            # Record rune usage
            self._record_rune_usage(caster.character_id, spell)
            rune_usage_recorded = True

        # Resolve saving throws for each target
        save_results: list[SaveResult] = []
        targets_saved: list[str] = []
        targets_failed_save: list[str] = []
        targets_affected: list[str] = []

        for tid in all_targets:
            if spell.save_type and dice_roller:
                save_result = self._resolve_saving_throw(
                    target_id=tid,
                    save_type=spell.save_type,
                    caster_level=caster.level,
                    dice_roller=dice_roller,
                )
                save_results.append(save_result)

                if save_result.success:
                    targets_saved.append(tid)
                    if not spell.save_negates:
                        # Save halves or partial effect
                        targets_affected.append(tid)
                else:
                    targets_failed_save.append(tid)
                    targets_affected.append(tid)
            else:
                # No save required - target is affected
                targets_affected.append(tid)

        # Apply mechanical effects
        damage_dealt: dict[str, Any] = {}
        healing_applied: dict[str, Any] = {}
        conditions_applied: list[str] = []
        stat_modifiers_applied: list[dict[str, Any]] = []

        # Calculate duration first (needed for buff application)
        duration_remaining = self._calculate_duration(spell, caster, dice_roller)

        # Generate effect ID for tracking buffs from this spell cast
        import uuid
        effect_id = f"spell_{spell.spell_id}_{uuid.uuid4().hex[:8]}"

        if spell.effect_type in (SpellEffectType.MECHANICAL, SpellEffectType.HYBRID):
            effects_result = self._apply_mechanical_effects(
                spell=spell,
                caster=caster,
                targets_affected=targets_affected,
                targets_saved=targets_saved,
                save_negates=spell.save_negates,
                dice_roller=dice_roller,
                duration_turns=duration_remaining if spell.duration_type == DurationType.TURNS else None,
                effect_id=effect_id,
            )
            damage_dealt = effects_result.get("damage_dealt", {})
            healing_applied = effects_result.get("healing_applied", {})
            conditions_applied = effects_result.get("conditions_applied", [])
            stat_modifiers_applied = effects_result.get("stat_modifiers_applied", [])

        # Create active effect if duration > instant
        effect_created = None
        if spell.duration_type != DurationType.INSTANT:
            effect_created = ActiveSpellEffect(
                spell_id=spell.spell_id,
                spell_name=spell.name,
                caster_id=caster.character_id,
                target_id=target_id or caster.character_id,
                target_type="creature",
                duration_type=spell.duration_type,
                duration_remaining=duration_remaining,
                duration_unit="turns" if spell.duration_type == DurationType.TURNS else "rounds",
                requires_concentration=spell.requires_concentration,
                effect_type=spell.effect_type,
                mechanical_effects=spell.mechanical_effects.copy(),
                narrative_description=spell.description,
            )
            self._active_effects.append(effect_created)

        # Build narrative context for LLM
        narrative_context = {
            "spell_name": spell.name,
            "caster_name": caster.name,
            "target": target_description or target_id,
            "targets": all_targets,
            "duration": spell.duration,
            "range": spell.range,
            "effect_type": spell.effect_type.value,
            "description": spell.description,
            "requires_concentration": spell.requires_concentration,
            "damage_dealt": damage_dealt,
            "healing_applied": healing_applied,
            "conditions_applied": conditions_applied,
            "targets_saved": targets_saved,
            "targets_affected": targets_affected,
        }

        return SpellCastResult(
            success=True,
            spell_id=spell.spell_id,
            spell_name=spell.name,
            reason="Spell cast successfully",
            effect_created=effect_created,
            damage_dealt=damage_dealt if damage_dealt else None,
            healing_applied=healing_applied if healing_applied else None,
            conditions_applied=conditions_applied,
            stat_modifiers_applied=stat_modifiers_applied,
            save_required=spell.save_type is not None,
            save_result=save_results[0] if save_results else None,
            save_results=save_results,
            slot_consumed=slot_consumed,
            slot_level=spell.level,
            glamour_usage_recorded=glamour_usage_recorded,
            rune_usage_recorded=rune_usage_recorded,
            targets_affected=targets_affected,
            targets_saved=targets_saved,
            targets_failed_save=targets_failed_save,
            narrative_context=narrative_context,
            effect_type=spell.effect_type,
        )

    def _calculate_duration(
        self, spell: SpellData, caster: "CharacterState", dice_roller: Optional["DiceRoller"] = None
    ) -> Optional[int]:
        """Calculate the duration of a spell in appropriate units."""
        if spell.duration_type in (DurationType.INSTANT, DurationType.PERMANENT):
            return None

        if spell.duration_value is None:
            return None

        # Parse duration value
        base_duration = 0
        if spell.duration_value.isdigit():
            base_duration = int(spell.duration_value)
        elif dice_roller and "d" in spell.duration_value.lower():
            # Roll dice for duration
            result = dice_roller.roll(spell.duration_value, f"{spell.name} duration")
            base_duration = result.total
        else:
            # Try to parse as number
            try:
                base_duration = int(spell.duration_value)
            except ValueError:
                base_duration = 1

        # Add per-level bonus
        if spell.duration_per_level:
            base_duration += caster.level

        return base_duration

    def get_active_effects(self, entity_id: str) -> list[ActiveSpellEffect]:
        """Get all active effects on an entity."""
        return [e for e in self._active_effects if e.target_id == entity_id and e.is_active]

    def get_concentration_effect(self, caster_id: str) -> Optional[ActiveSpellEffect]:
        """Get the active concentration effect for a caster."""
        for effect in self._active_effects:
            if (
                effect.caster_id == caster_id
                and effect.requires_concentration
                and effect.is_active
                and not effect.concentration_broken
            ):
                return effect
        return None

    def break_concentration(self, caster_id: str) -> list[ActiveSpellEffect]:
        """
        Break concentration for a caster (e.g., on taking damage).

        Args:
            caster_id: The caster whose concentration is broken

        Returns:
            List of effects that were broken
        """
        broken = []
        for effect in self._active_effects:
            if effect.caster_id == caster_id and effect.requires_concentration and effect.is_active:
                if effect.break_concentration():
                    broken.append(effect)
        return broken

    def tick_effects(self, time_unit: str = "turns") -> list[ActiveSpellEffect]:
        """
        Advance time for all active effects.

        Args:
            time_unit: "rounds" or "turns"

        Returns:
            List of effects that expired
        """
        expired = []
        for effect in self._active_effects:
            if effect.tick(time_unit):
                expired.append(effect)

        # Clean up expired effects
        self._active_effects = [e for e in self._active_effects if e.is_active]

        return expired

    def dismiss_effect(self, effect_id: str) -> Optional[ActiveSpellEffect]:
        """
        Dismiss a spell effect by ID.

        Args:
            effect_id: The effect to dismiss

        Returns:
            The dismissed effect, or None if not found
        """
        for effect in self._active_effects:
            if effect.effect_id == effect_id:
                effect.dismiss()
                return effect
        return None

    def register_spell(self, spell: SpellData) -> None:
        """Register a spell in the cache."""
        self._spell_cache[spell.spell_id] = spell

    def clear_expired_effects(self) -> int:
        """Remove all expired effects and return count removed."""
        before = len(self._active_effects)
        self._active_effects = [e for e in self._active_effects if e.is_active]
        return before - len(self._active_effects)

    def check_recurring_saves(
        self,
        current_day: int,
        current_turn: int,
        dice_roller: Optional["DiceRoller"] = None,
    ) -> list[dict[str, Any]]:
        """
        Check recurring saves for all active effects.

        Called during time advancement to process effects like Ingratiate
        that require periodic saving throws.

        Args:
            current_day: Current day number
            current_turn: Current turn number
            dice_roller: Dice roller for save rolls

        Returns:
            List of save results with effect outcomes
        """
        results = []

        for effect in self._active_effects:
            if not effect.is_active:
                continue
            if not effect.recurring_save_type:
                continue

            needs_check = False
            if effect.recurring_save_frequency == "daily":
                if current_day > effect.last_save_check_day:
                    needs_check = True
                    effect.last_save_check_day = current_day
            elif effect.recurring_save_frequency == "per_turn":
                if current_turn > effect.last_save_check_turn:
                    needs_check = True
                    effect.last_save_check_turn = current_turn

            if not needs_check:
                continue

            # Make the save
            if dice_roller:
                roll = dice_roller.roll("1d20", f"{effect.spell_name} recurring save")
                roll_value = roll.total
            else:
                import random
                roll_value = random.randint(1, 20)

            # Default save target is 15 for spell effects
            save_target = 15
            success = roll_value >= save_target or roll_value == 20

            result = {
                "effect_id": effect.effect_id,
                "spell_name": effect.spell_name,
                "target_id": effect.target_id,
                "save_type": effect.recurring_save_type,
                "roll": roll_value,
                "target": save_target,
                "success": success,
                "effect_ended": False,
            }

            if success and effect.recurring_save_ends_effect:
                effect.is_active = False
                effect.dismissed = True
                result["effect_ended"] = True

                # Remove any buffs associated with this effect
                if self._controller:
                    self._controller.remove_buff(
                        effect.target_id,
                        source_id=effect.effect_id,
                    )

            results.append(result)

        # Clean up ended effects
        self._active_effects = [e for e in self._active_effects if e.is_active]

        return results

    def parse_recurring_save(self, spell: SpellData) -> dict[str, Any]:
        """
        Parse recurring save requirements from spell description.

        Detects patterns like:
        - "Save Versus Spell once per day"
        - "makes a further save once per day"

        Args:
            spell: The spell to parse

        Returns:
            Dict with recurring save info:
            - save_type: str or None
            - frequency: str or None ("daily", "per_turn")
            - ends_effect: bool
        """
        description = spell.description.lower()
        result: dict[str, Any] = {
            "save_type": None,
            "frequency": None,
            "ends_effect": True,
        }

        # Pattern: "save versus X once per day"
        daily_save_pattern = r"save\s+(?:versus|vs\.?)\s+(\w+)\s+once\s+per\s+day"
        daily_match = re.search(daily_save_pattern, description)
        if daily_match:
            result["save_type"] = daily_match.group(1)
            result["frequency"] = "daily"

        # Pattern: "makes a further save" or "another save"
        if "once per day" in description and "save" in description:
            if not result["save_type"]:
                result["save_type"] = "spell"  # Default
                result["frequency"] = "daily"

        return result

    # =========================================================================
    # SPELL COMPONENT VERIFICATION
    # =========================================================================

    def parse_spell_components(self, spell: SpellData) -> list[SpellComponent]:
        """
        Parse material components from spell description.

        Detects patterns like:
        - "requires a 50gp trinket" / "50gp crystal"
        - "component is consumed" / "used up"
        - "magical fungus" as alternative

        Args:
            spell: The spell to parse

        Returns:
            List of SpellComponent objects
        """
        description = spell.description.lower()
        components: list[SpellComponent] = []

        # Pattern: "Xgp trinket/crystal/component"
        value_pattern = r"(\d+)\s*gp\s+(trinket|crystal|gem|component|item)"
        value_matches = re.findall(value_pattern, description)
        for value, comp_type in value_matches:
            component = SpellComponent(
                component_type=comp_type,
                min_value_gp=int(value),
                consumed="consumed" in description or "used up" in description,
                description=f"{value}gp {comp_type}",
            )

            # Check for destruction chance (e.g., "1-in-20 chance of shattering")
            destroy_pattern = r"(\d+)-in-(\d+)\s+chance"
            destroy_match = re.search(destroy_pattern, description)
            if destroy_match:
                numerator = int(destroy_match.group(1))
                denominator = int(destroy_match.group(2))
                component.destruction_chance = numerator / denominator

            # Check for alternatives (e.g., "or magical fungus")
            if "or magical fungus" in description or "magical fungus" in description:
                component.alternatives = ["magical_fungus"]

            components.append(component)

        return components

    def verify_components(
        self,
        caster: "CharacterState",
        spell: SpellData,
    ) -> tuple[bool, str, list[Any]]:
        """
        Verify that the caster has required spell components.

        Args:
            caster: The character casting the spell
            spell: The spell being cast

        Returns:
            Tuple of (has_components, reason, matching_items)
        """
        # Parse components if not already done
        if not spell.required_components:
            spell.required_components = self.parse_spell_components(spell)

        # If no components required, automatically valid
        if not spell.required_components:
            return True, "No components required", []

        matching_items = []

        for component in spell.required_components:
            found = False
            found_item = None

            # Search inventory for matching item
            for item in caster.inventory:
                # Check primary type match
                type_match = (
                    component.component_type.lower() in item.item_type.lower()
                    or component.component_type.lower() in item.name.lower()
                )

                # Check alternative types
                alt_match = any(
                    alt.lower() in item.item_type.lower() or alt.lower() in item.name.lower()
                    for alt in component.alternatives
                )

                if type_match or alt_match:
                    # Check value requirement
                    item_value = item.value_gp or 0
                    if item_value >= component.min_value_gp:
                        found = True
                        found_item = item
                        break

            if not found:
                return (
                    False,
                    f"Missing component: {component.description}",
                    matching_items,
                )
            matching_items.append(found_item)

        return True, "All components available", matching_items

    def consume_components(
        self,
        caster: "CharacterState",
        spell: SpellData,
        matching_items: list[Any],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Consume or potentially destroy spell components.

        Args:
            caster: The character casting the spell
            spell: The spell being cast
            matching_items: Items matched by verify_components
            dice_roller: For destruction chance rolls

        Returns:
            Dict with consumption results
        """
        result = {
            "consumed": [],
            "destroyed": [],
            "preserved": [],
        }

        if not spell.required_components:
            return result

        for i, component in enumerate(spell.required_components):
            if i >= len(matching_items):
                break

            item = matching_items[i]

            if component.consumed:
                # Remove item from inventory
                caster.remove_item(item.item_id, quantity=1)
                result["consumed"].append(item.name)

            elif component.destruction_chance > 0:
                # Roll for destruction
                if dice_roller:
                    roll = dice_roller.roll_percentile("Component destruction check")
                    destroyed = roll.total <= (component.destruction_chance * 100)
                else:
                    import random
                    destroyed = random.random() < component.destruction_chance

                if destroyed:
                    caster.remove_item(item.item_id, quantity=1)
                    result["destroyed"].append(item.name)
                else:
                    result["preserved"].append(item.name)
            else:
                result["preserved"].append(item.name)

        return result

    # =========================================================================
    # GLAMOUR USAGE TRACKING
    # =========================================================================

    def _parse_usage_frequency(self, frequency_str: Optional[str]) -> UsageFrequency:
        """Parse a usage frequency string into an enum value."""
        if not frequency_str:
            return UsageFrequency.AT_WILL

        freq_lower = frequency_str.lower()

        if "per day per subject" in freq_lower:
            return UsageFrequency.ONCE_PER_DAY_PER_SUBJECT
        elif "per day" in freq_lower:
            return UsageFrequency.ONCE_PER_DAY
        elif "per turn" in freq_lower:
            return UsageFrequency.ONCE_PER_TURN
        elif "per round" in freq_lower:
            return UsageFrequency.ONCE_PER_ROUND
        else:
            return UsageFrequency.AT_WILL

    def _check_glamour_usage(
        self,
        caster_id: str,
        spell: SpellData,
        target_id: Optional[str],
    ) -> tuple[bool, str]:
        """
        Check if a glamour can be used based on its frequency limits.

        Returns:
            Tuple of (can_use, reason)
        """
        # Determine usage frequency
        frequency = spell.parsed_usage_frequency
        if frequency is None:
            frequency = self._parse_usage_frequency(spell.usage_frequency)

        if frequency == UsageFrequency.AT_WILL:
            return True, "No usage limit"

        # Get or create usage record
        key = (caster_id, spell.spell_id)
        if key not in self._glamour_usage:
            self._glamour_usage[key] = GlamourUsageRecord(
                spell_id=spell.spell_id,
                caster_id=caster_id,
            )

        record = self._glamour_usage[key]
        return record.can_use(frequency, self._current_turn, target_id)

    def _record_glamour_usage(
        self,
        caster_id: str,
        spell: SpellData,
        target_id: Optional[str],
    ) -> None:
        """Record that a glamour was used."""
        frequency = spell.parsed_usage_frequency
        if frequency is None:
            frequency = self._parse_usage_frequency(spell.usage_frequency)

        key = (caster_id, spell.spell_id)
        if key not in self._glamour_usage:
            self._glamour_usage[key] = GlamourUsageRecord(
                spell_id=spell.spell_id,
                caster_id=caster_id,
            )

        self._glamour_usage[key].record_use(frequency, self._current_turn, target_id)

    def get_glamour_usage(self, caster_id: str, spell_id: str) -> Optional[GlamourUsageRecord]:
        """Get the usage record for a specific glamour."""
        return self._glamour_usage.get((caster_id, spell_id))

    def reset_glamour_usage_daily(self, caster_id: Optional[str] = None) -> int:
        """
        Reset daily glamour usage counters.

        Args:
            caster_id: Optional - reset only for this caster. If None, reset all.

        Returns:
            Number of records reset
        """
        count = 0
        for key, record in self._glamour_usage.items():
            if caster_id is None or key[0] == caster_id:
                record.reset_daily()
                count += 1
        return count

    # =========================================================================
    # RUNE USAGE TRACKING
    # =========================================================================

    def _get_rune_magnitude(self, spell: SpellData) -> RuneMagnitude:
        """Get the magnitude of a rune spell."""
        if spell.rune_magnitude:
            return spell.rune_magnitude

        # Try to parse from level field
        if spell.level:
            level_str = str(spell.level).lower()
            if level_str == "lesser":
                return RuneMagnitude.LESSER
            elif level_str == "greater":
                return RuneMagnitude.GREATER
            elif level_str == "mighty":
                return RuneMagnitude.MIGHTY

        # Default to lesser
        return RuneMagnitude.LESSER

    def _check_rune_usage(
        self,
        caster_id: str,
        spell: SpellData,
    ) -> tuple[bool, str]:
        """
        Check if a rune can be used based on magnitude limits.

        Returns:
            Tuple of (can_use, reason)
        """
        magnitude = self._get_rune_magnitude(spell)

        # Get or create rune usage state
        if caster_id not in self._rune_usage:
            self._rune_usage[caster_id] = RuneUsageState(caster_id=caster_id)

        return self._rune_usage[caster_id].can_use_rune(spell.spell_id, magnitude)

    def _record_rune_usage(
        self,
        caster_id: str,
        spell: SpellData,
    ) -> None:
        """Record that a rune was used."""
        magnitude = self._get_rune_magnitude(spell)

        if caster_id not in self._rune_usage:
            self._rune_usage[caster_id] = RuneUsageState(caster_id=caster_id)

        self._rune_usage[caster_id].use_rune(spell.spell_id, magnitude)

    def get_rune_usage(self, caster_id: str) -> Optional[RuneUsageState]:
        """Get the rune usage state for a caster."""
        return self._rune_usage.get(caster_id)

    def set_rune_limits(
        self,
        caster_id: str,
        level: int,
    ) -> None:
        """
        Set rune usage limits based on character level.

        Enchanters gain more daily rune uses as they level.
        """
        if caster_id not in self._rune_usage:
            self._rune_usage[caster_id] = RuneUsageState(caster_id=caster_id)

        state = self._rune_usage[caster_id]

        # Scale limits by level (example scaling - adjust per rules)
        state.max_lesser_daily = 2 + (level // 3)  # 2 at L1, 3 at L3, 4 at L6, etc.
        state.max_greater_daily = max(1, (level - 4) // 2)  # 1 at L5, 2 at L7, etc.
        state.max_mighty_daily = max(1, (level - 8) // 3)  # 1 at L9, etc.

    def reset_rune_usage_daily(self, caster_id: Optional[str] = None) -> int:
        """
        Reset daily rune usage counters.

        Args:
            caster_id: Optional - reset only for this caster. If None, reset all.

        Returns:
            Number of records reset
        """
        count = 0
        for key, state in self._rune_usage.items():
            if caster_id is None or key == caster_id:
                state.reset_daily()
                count += 1
        return count

    # =========================================================================
    # SAVING THROW RESOLUTION
    # =========================================================================

    def _resolve_saving_throw(
        self,
        target_id: str,
        save_type: SaveType,
        caster_level: int,
        dice_roller: "DiceRoller",
        modifier: int = 0,
    ) -> SaveResult:
        """
        Resolve a saving throw for a target.

        Args:
            target_id: The target making the save
            save_type: Type of save (doom, ray, hold, blast, spell)
            caster_level: Level of the caster (may affect DC)
            dice_roller: Dice roller to use
            modifier: Any bonus/penalty to the roll

        Returns:
            SaveResult with complete save information
        """
        # Roll d20 for the save
        roll_result = dice_roller.roll("1d20", f"Save vs {save_type.value}")
        roll = roll_result.total

        # Check for natural 20/1
        natural_20 = roll == 20
        natural_1 = roll == 1

        # Get target's saving throw value
        # Try to get from controller/game state
        target_save = self._get_save_target(target_id, save_type)

        total = roll + modifier

        # In OSR games, you typically need to roll >= save target to succeed
        # Natural 20 always succeeds, natural 1 always fails
        if natural_20:
            success = True
        elif natural_1:
            success = False
        else:
            success = total >= target_save

        return SaveResult(
            success=success,
            save_type=save_type.value,
            target_id=target_id,
            roll=roll,
            modifier=modifier,
            total=total,
            target_number=target_save,
            natural_20=natural_20,
            natural_1=natural_1,
        )

    def _get_save_target(self, target_id: str, save_type: SaveType) -> int:
        """
        Get the saving throw target number for a target.

        Args:
            target_id: The entity making the save
            save_type: Type of save

        Returns:
            Target number needed to succeed
        """
        # Try to get from controller
        if self._controller:
            character = self._controller.get_character(target_id)
            if character:
                saves = getattr(character, "saving_throws", None)
                if saves:
                    save_map = {
                        SaveType.DOOM: saves.doom if hasattr(saves, "doom") else 14,
                        SaveType.RAY: saves.ray if hasattr(saves, "ray") else 14,
                        SaveType.HOLD: saves.hold if hasattr(saves, "hold") else 14,
                        SaveType.BLAST: saves.blast if hasattr(saves, "blast") else 14,
                        SaveType.SPELL: saves.spell if hasattr(saves, "spell") else 14,
                    }
                    return save_map.get(save_type, 14)

        # Default save targets by type (for monsters/NPCs without full stats)
        default_saves = {
            SaveType.DOOM: 14,
            SaveType.RAY: 15,
            SaveType.HOLD: 16,
            SaveType.BLAST: 17,
            SaveType.SPELL: 17,
        }
        return default_saves.get(save_type, 15)

    # =========================================================================
    # MECHANICAL EFFECT PARSING AND APPLICATION
    # =========================================================================

    def parse_mechanical_effects(self, spell: SpellData) -> ParsedMechanicalEffects:
        """
        Parse a spell's description to extract structured mechanical effects.

        This is a heuristic parser that looks for common patterns in spell
        descriptions to identify damage dice, conditions, and other effects.
        """
        parsed = ParsedMechanicalEffects()
        description = spell.description.lower()

        # Look for damage patterns: "Xd6 damage", "deals Xd8", etc.
        damage_pattern = r"(\d+d\d+(?:\s*\+\s*\d+)?)\s*(?:points?\s+of\s+)?(?:damage|hp|hit\s+points?)"
        damage_matches = re.findall(damage_pattern, description, re.IGNORECASE)
        for damage_dice in damage_matches:
            effect = MechanicalEffect(
                category=MechanicalEffectCategory.DAMAGE,
                damage_dice=damage_dice.replace(" ", ""),
                description=f"Deals {damage_dice} damage",
            )

            # Try to identify damage type
            for dtype in ["fire", "cold", "lightning", "acid", "poison", "holy", "necrotic"]:
                if dtype in description:
                    effect.damage_type = dtype
                    break

            parsed.add_effect(effect)

        # Look for healing patterns
        heal_pattern = r"(?:heals?|restores?|regains?)\s*(\d+d\d+(?:\s*\+\s*\d+)?)"
        heal_matches = re.findall(heal_pattern, description, re.IGNORECASE)
        for heal_dice in heal_matches:
            effect = MechanicalEffect(
                category=MechanicalEffectCategory.HEALING,
                healing_dice=heal_dice.replace(" ", ""),
                description=f"Heals {heal_dice} HP",
            )
            parsed.add_effect(effect)

        # Look for condition patterns
        condition_keywords = {
            "charmed": "charmed",
            "charming": "charmed",
            "charm": "charmed",
            "frightened": "frightened",
            "fear": "frightened",
            "paralyzed": "paralyzed",
            "paralysis": "paralyzed",
            "paralysed": "paralyzed",
            "petrified": "petrified",
            "stone": "petrified",
            "blinded": "blinded",
            "blind": "blinded",
            "deafened": "deafened",
            "deaf": "deafened",
            "poisoned": "poisoned",
            "poison": "poisoned",
            "asleep": "unconscious",
            "sleep": "unconscious",
            "unconscious": "unconscious",
            "stunned": "stunned",
            "stun": "stunned",
            "invisible": "invisible",
            "invisibility": "invisible",
        }

        for keyword, condition in condition_keywords.items():
            if keyword in description:
                # Avoid false positives by checking context
                # Skip if it's about removing the condition
                if f"remove {keyword}" in description or f"cure {keyword}" in description:
                    continue

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.CONDITION,
                    condition_applied=condition,
                    description=f"Applies {condition} condition",
                )

                # Check for save type in description
                for save in ["doom", "ray", "hold", "blast", "spell"]:
                    if f"save versus {save}" in description or f"save vs {save}" in description:
                        effect.save_type = save
                        if "or" in description or "negates" in description:
                            effect.save_negates = True
                        break

                parsed.add_effect(effect)
                break  # Only add one condition per spell to avoid duplicates

        # Look for stat modifier patterns
        stat_pattern = r"([+-]\d+)\s*(?:bonus|penalty)?\s*(?:to\s+)?(?:attack|ac|armor class|saving throw)"
        stat_matches = re.findall(stat_pattern, description, re.IGNORECASE)
        for modifier in stat_matches:
            mod_val = int(modifier)
            category = MechanicalEffectCategory.BUFF if mod_val > 0 else MechanicalEffectCategory.DEBUFF
            effect = MechanicalEffect(
                category=category,
                modifier_value=mod_val,
                description=f"Grants {modifier} modifier",
            )
            parsed.add_effect(effect)

        return parsed

    def parse_level_scaling(self, spell: SpellData) -> list[LevelScaling]:
        """
        Parse level scaling patterns from spell description.

        Detects patterns like:
        - "one per Level" -> 1 additional per level
        - "one stream per Level" -> projectiles scale
        - "one additional per 3 Levels" -> scales per 3 levels
        - "1 Turn per Level" -> duration scales
        - "at higher Levels...one additional per 3 Levels" -> complex scaling

        Args:
            spell: The spell to parse

        Returns:
            List of LevelScaling objects found in description
        """
        scalings: list[LevelScaling] = []
        description = spell.description.lower()
        duration_str = spell.duration.lower() if spell.duration else ""

        # Pattern: "X per Level" or "X per level of the caster"
        per_level_pattern = r"(\d+|one|two|three|four|five)\s*(?:stream|shard|target|flame|creature)?s?\s+per\s+level"
        matches = re.findall(per_level_pattern, description)
        for match in matches:
            base = self._parse_number_word(match)
            # Determine type based on context
            if "stream" in description or "shard" in description or "projectile" in description:
                scaling_type = LevelScalingType.PROJECTILES
            elif "target" in description or "creature" in description or "flame" in description:
                scaling_type = LevelScalingType.TARGETS
            else:
                scaling_type = LevelScalingType.PROJECTILES  # Default for counted things
            scalings.append(LevelScaling(
                scaling_type=scaling_type,
                base_value=base,
                per_levels=1,
                description=match,
            ))

        # Pattern: "one additional per X Levels" (like Ioun Shard: "one additional per 3 Levels")
        additional_pattern = r"(\d+|one|two)\s+additional\s+(?:shard|target|stream)?s?\s+per\s+(\d+)\s+levels?"
        add_matches = re.findall(additional_pattern, description)
        for add_val, per_lvl in add_matches:
            base = self._parse_number_word(add_val)
            per = int(per_lvl)
            scalings.append(LevelScaling(
                scaling_type=LevelScalingType.PROJECTILES,
                base_value=1,  # Base shard/target
                per_levels=per,
                minimum_level=1,
                description=f"{add_val} additional per {per_lvl} levels",
            ))

        # Duration scaling in duration field: "X Turns + Y Turn per Level"
        duration_scale_pattern = r"(\d+)\s*turns?\s*\+\s*(\d+)\s*turn\s+per\s+level"
        dur_match = re.search(duration_scale_pattern, duration_str)
        if dur_match:
            base_dur = int(dur_match.group(1))
            per_level_dur = int(dur_match.group(2))
            scalings.append(LevelScaling(
                scaling_type=LevelScalingType.DURATION,
                base_value=base_dur,
                per_levels=1,  # 1 per level
                description=f"{base_dur} turns + {per_level_dur} per level",
            ))

        # Concentration duration: "up to X Round per Level"
        conc_pattern = r"up\s+to\s+(\d+)\s+rounds?\s+per\s+level"
        conc_match = re.search(conc_pattern, duration_str)
        if conc_match:
            per_round = int(conc_match.group(1))
            scalings.append(LevelScaling(
                scaling_type=LevelScalingType.DURATION,
                base_value=per_round,
                per_levels=1,
                description=f"up to {per_round} round per level",
            ))

        return scalings

    def _parse_number_word(self, word: str) -> int:
        """Convert number words to integers."""
        word_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        word_lower = word.lower().strip()
        if word_lower in word_map:
            return word_map[word_lower]
        try:
            return int(word_lower)
        except ValueError:
            return 1

    def get_scaled_value(
        self,
        spell: SpellData,
        scaling_type: LevelScalingType,
        caster_level: int,
    ) -> int:
        """
        Get the scaled value for a specific scaling type.

        Args:
            spell: The spell with level scaling
            scaling_type: The type of scaling to look up
            caster_level: The caster's level

        Returns:
            The scaled value, or 1 if no scaling found
        """
        # Parse scaling if not already done
        if not spell.level_scaling:
            spell.level_scaling = self.parse_level_scaling(spell)

        for scaling in spell.level_scaling:
            if scaling.scaling_type == scaling_type:
                return scaling.calculate_scaled_value(caster_level)

        return 1  # Default

    def parse_target_restrictions(self, spell: SpellData) -> dict[str, Any]:
        """
        Parse HD/level restrictions from spell description.

        Detects patterns like:
        - "Level 4 or lower" / "of level 4 or lower"
        - "X HD or less" / "of X HD or fewer"
        - "Living creatures"

        Args:
            spell: The spell to parse

        Returns:
            Dict with parsed restrictions:
            - max_level: int or None
            - max_hd: int or None
            - living_only: bool
        """
        description = spell.description.lower()
        result: dict[str, Any] = {
            "max_level": None,
            "max_hd": None,
            "living_only": False,
        }

        # Pattern: "Level X or lower" / "of Level X or lower"
        level_pattern = r"(?:of\s+)?level\s+(\d+)\s+or\s+(?:lower|less|fewer)"
        level_match = re.search(level_pattern, description)
        if level_match:
            result["max_level"] = int(level_match.group(1))

        # Pattern: "X HD or less/fewer" / "of X HD or less"
        hd_pattern = r"(\d+)\s*hd\s+or\s+(?:less|fewer|lower)"
        hd_match = re.search(hd_pattern, description)
        if hd_match:
            result["max_hd"] = int(hd_match.group(1))

        # Pattern: "living creatures" / "affects living"
        if "living creature" in description or "affects living" in description:
            result["living_only"] = True

        return result

    def filter_valid_targets(
        self,
        spell: SpellData,
        target_ids: list[str],
        get_target_info: Optional[callable] = None,
    ) -> tuple[list[str], list[str]]:
        """
        Filter targets based on spell's HD/level restrictions.

        Args:
            spell: The spell being cast
            target_ids: List of potential target IDs
            get_target_info: Callback to get target level/HD:
                            fn(target_id) -> {"level": int, "hd": int, "is_living": bool}

        Returns:
            Tuple of (valid_targets, excluded_targets)
        """
        if not get_target_info:
            # No way to check, assume all valid
            return target_ids, []

        # Parse restrictions if not already set
        if spell.max_target_level is None and spell.max_target_hd is None:
            restrictions = self.parse_target_restrictions(spell)
            spell.max_target_level = restrictions["max_level"]
            spell.max_target_hd = restrictions["max_hd"]
            spell.affects_living_only = restrictions["living_only"]

        # If no restrictions, all targets are valid
        if (spell.max_target_level is None and
            spell.max_target_hd is None and
            not spell.affects_living_only):
            return target_ids, []

        valid = []
        excluded = []

        for target_id in target_ids:
            try:
                info = get_target_info(target_id)
                target_level = info.get("level", 0)
                target_hd = info.get("hd", target_level)  # Default HD to level
                is_living = info.get("is_living", True)

                # Check living restriction
                if spell.affects_living_only and not is_living:
                    excluded.append(target_id)
                    continue

                # Check level restriction
                if spell.max_target_level is not None:
                    if target_level > spell.max_target_level:
                        excluded.append(target_id)
                        continue

                # Check HD restriction
                if spell.max_target_hd is not None:
                    if target_hd > spell.max_target_hd:
                        excluded.append(target_id)
                        continue

                valid.append(target_id)

            except Exception:
                # If we can't get info, assume valid
                valid.append(target_id)

        return valid, excluded

    def _apply_mechanical_effects(
        self,
        spell: SpellData,
        caster: "CharacterState",
        targets_affected: list[str],
        targets_saved: list[str],
        save_negates: bool,
        dice_roller: Optional["DiceRoller"],
        duration_turns: Optional[int] = None,
        effect_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Apply mechanical effects from a spell.

        Args:
            spell: The spell being cast
            caster: The caster
            targets_affected: List of target IDs that are affected
            targets_saved: List of target IDs that made their save
            save_negates: Whether save completely negates effects
            dice_roller: Dice roller for damage/healing
            duration_turns: Duration in turns for buffs/debuffs
            effect_id: The spell effect ID for buff source tracking

        Returns:
            Dictionary with applied effects:
            - damage_dealt: {target_id: amount}
            - healing_applied: {target_id: amount}
            - conditions_applied: list of condition names
            - stat_modifiers_applied: list of modifier dicts
        """
        result: dict[str, Any] = {
            "damage_dealt": {},
            "healing_applied": {},
            "conditions_applied": [],
            "stat_modifiers_applied": [],
        }

        # Parse effects if not already parsed
        if spell.mechanical_effects:
            parsed = ParsedMechanicalEffects()
            for effect_data in spell.mechanical_effects.get("effects", []):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory(effect_data.get("category", "utility")),
                    damage_dice=effect_data.get("damage_dice"),
                    damage_type=effect_data.get("damage_type"),
                    healing_dice=effect_data.get("healing_dice"),
                    condition_applied=effect_data.get("condition_applied"),
                    modifier_value=effect_data.get("modifier_value"),
                    save_type=effect_data.get("save_type"),
                    save_negates=effect_data.get("save_negates", False),
                    save_halves=effect_data.get("save_halves", False),
                )
                parsed.add_effect(effect)
        else:
            # Parse from description
            parsed = self.parse_mechanical_effects(spell)

        # Apply each effect to each target
        for effect in parsed.effects:
            for target_id in targets_affected:
                # Check if save negates this effect for this target
                target_saved = target_id in targets_saved
                if target_saved and effect.save_negates:
                    continue

                # Apply damage
                if effect.category == MechanicalEffectCategory.DAMAGE and effect.damage_dice:
                    if dice_roller:
                        roll = dice_roller.roll(effect.damage_dice, f"{spell.name} damage")
                        damage = roll.total

                        # Half damage on save
                        if target_saved and effect.save_halves:
                            damage = max(1, damage // 2)

                        result["damage_dealt"][target_id] = damage

                        # Apply to game state if controller available
                        if self._controller:
                            self._controller.apply_damage(
                                target_id, damage, effect.damage_type or "magic"
                            )

                # Apply healing
                if effect.category == MechanicalEffectCategory.HEALING and effect.healing_dice:
                    if dice_roller:
                        roll = dice_roller.roll(effect.healing_dice, f"{spell.name} healing")
                        healing = roll.total
                        result["healing_applied"][target_id] = healing

                        # Apply to game state if controller available
                        if self._controller:
                            self._controller.heal_character(target_id, healing)

                # Apply conditions
                if effect.category == MechanicalEffectCategory.CONDITION and effect.condition_applied:
                    result["conditions_applied"].append(effect.condition_applied)

                    # Apply to game state if controller available
                    if self._controller:
                        self._controller.apply_condition(
                            target_id, effect.condition_applied, source=spell.name
                        )

                # Apply stat modifiers (buffs/debuffs)
                if effect.category in (MechanicalEffectCategory.BUFF, MechanicalEffectCategory.DEBUFF):
                    if effect.modifier_value is not None:
                        modifier_info = {
                            "target_id": target_id,
                            "stat": effect.stat_modified or "general",
                            "modifier": effect.modifier_value,
                            "source": spell.name,
                            "condition": effect.condition_context,  # For conditional modifiers
                        }
                        result["stat_modifiers_applied"].append(modifier_info)

                        # Apply to game state if controller available
                        if self._controller:
                            self._controller.apply_buff(
                                character_id=target_id,
                                stat=effect.stat_modified or "general",
                                value=effect.modifier_value,
                                source=spell.name,
                                source_id=effect_id,
                                duration_turns=duration_turns,
                                condition=effect.condition_context,
                            )

        return result

    # =========================================================================
    # DAILY RESET
    # =========================================================================

    def reset_daily(self, caster_id: Optional[str] = None) -> dict[str, int]:
        """
        Reset all daily usage counters (glamours and runes).

        Called at dawn or after a full rest.

        Args:
            caster_id: Optional - reset only for this caster

        Returns:
            Dictionary with counts of reset records
        """
        glamour_count = self.reset_glamour_usage_daily(caster_id)
        rune_count = self.reset_rune_usage_daily(caster_id)

        return {
            "glamour_records_reset": glamour_count,
            "rune_records_reset": rune_count,
        }


# =============================================================================
# SPELL NARRATOR - LLM INTEGRATION
# =============================================================================


class SpellNarrator:
    """
    Generates immersive spell narration using LLM integration.

    This class bridges the spell resolver's mechanical outputs with
    the LLM-powered narrative system, producing rich descriptions
    of spell casting appropriate to Dolmenwood's aesthetic.

    Usage:
        narrator = SpellNarrator(llm_manager)
        narration = narrator.narrate_spell_cast(spell_result, spell_data, context)
    """

    def __init__(self, llm_manager: Optional[Any] = None):
        """
        Initialize the spell narrator.

        Args:
            llm_manager: Optional LLMManager instance. If None, returns
                        fallback narration based on spell description.
        """
        self._llm_manager = llm_manager

    def narrate_spell_cast(
        self,
        result: SpellCastResult,
        spell: SpellData,
        caster_name: str,
        caster_level: int = 1,
        location_context: str = "",
        time_of_day: str = "",
        weather: str = "",
        narrative_hints: Optional[list[str]] = None,
    ) -> str:
        """
        Generate narrative description of a spell being cast.

        Uses the SpellCastNarrationSchema to guide LLM output,
        incorporating resolved mechanical effects into the description.

        Args:
            result: The SpellCastResult from the resolver
            spell: The SpellData for the cast spell
            caster_name: Display name of the caster
            caster_level: Level of the caster (for scaling narration)
            location_context: Description of current location
            time_of_day: Time of day (affects atmosphere)
            weather: Current weather (affects atmosphere)
            narrative_hints: Additional narrative guidance

        Returns:
            Immersive narrative description of the spell cast
        """
        if not result.success:
            return self._narrate_failed_cast(result, spell, caster_name)

        # Build inputs for the schema
        from src.ai.prompt_schemas import (
            SpellCastNarrationInputs,
            SpellCastNarrationSchema,
        )
        from src.ai.llm_provider import LLMMessage, LLMRole

        # Convert damage dict to simple format (target -> damage int)
        damage_dealt = {}
        if result.damage_dealt:
            for target, value in result.damage_dealt.items():
                if isinstance(value, dict):
                    damage_dealt[target] = value.get("total", 0)
                else:
                    damage_dealt[target] = value

        # Convert healing dict similarly
        healing_applied = {}
        if result.healing_applied:
            for target, value in result.healing_applied.items():
                if isinstance(value, dict):
                    healing_applied[target] = value.get("total", 0)
                else:
                    healing_applied[target] = value

        # Convert stat modifiers to strings
        stat_modifiers = []
        if result.stat_modifiers_applied:
            for mod in result.stat_modifiers_applied:
                if isinstance(mod, dict):
                    stat = mod.get("stat", "")
                    value = mod.get("modifier", 0)
                    stat_modifiers.append(f"{stat} {value:+d}")

        inputs = SpellCastNarrationInputs(
            spell_name=spell.name,
            spell_description=spell.description,
            magic_type=spell.magic_type.value if hasattr(spell.magic_type, 'value') else str(spell.magic_type),
            effect_type=spell.effect_type.value if hasattr(spell.effect_type, 'value') else str(spell.effect_type),
            caster_name=caster_name,
            caster_level=caster_level,
            target_description=result.narrative_context.get("target", ""),
            targets=result.targets_affected or [],
            range_text=spell.range or "",
            duration_text=spell.duration or "",
            requires_concentration=spell.requires_concentration,
            damage_dealt=damage_dealt,
            healing_applied=healing_applied,
            conditions_applied=result.conditions_applied or [],
            stat_modifiers_applied=stat_modifiers,
            targets_saved=result.targets_saved or [],
            targets_affected=result.targets_affected or [],
            save_type=spell.save_type.value if spell.save_type and hasattr(spell.save_type, 'value') else (spell.save_type or ""),
            location_context=location_context,
            time_of_day=time_of_day,
            weather=weather,
            narrative_hints=narrative_hints or [],
        )

        schema = SpellCastNarrationSchema(inputs)

        # If no LLM available, return fallback
        if not self._llm_manager or not self._llm_manager.is_available():
            return self._generate_fallback_narration(spell, result, caster_name)

        # Build LLM request
        system_prompt = schema.get_system_prompt()
        user_prompt = schema.build_prompt()

        messages = [LLMMessage(role=LLMRole.USER, content=user_prompt)]

        try:
            response = self._llm_manager.complete(
                messages=messages,
                system_prompt=system_prompt,
                allow_narration_context=True,
            )

            if response.authority_violations:
                # Log violations but still return content
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Spell narration violations: {response.authority_violations}")

            return response.content if response.content else self._generate_fallback_narration(
                spell, result, caster_name
            )

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"LLM narration failed: {e}")
            return self._generate_fallback_narration(spell, result, caster_name)

    def _narrate_failed_cast(
        self,
        result: SpellCastResult,
        spell: SpellData,
        caster_name: str,
    ) -> str:
        """Generate narration for a failed spell cast."""
        reason = result.reason or "unknown reason"
        return (
            f"{caster_name} attempts to cast {spell.name}, but the magic "
            f"falters and dissipates. ({reason})"
        )

    def _generate_fallback_narration(
        self,
        spell: SpellData,
        result: SpellCastResult,
        caster_name: str,
    ) -> str:
        """
        Generate fallback narration when LLM is unavailable.

        Provides a serviceable description based on spell data.
        """
        magic_verbs = {
            "arcane": "intones arcane syllables and traces glowing sigils",
            "divine": "offers a prayer and channels divine radiance",
            "fairy_glamour": "weaves silvery glamour with a lilting song",
            "rune": "traces a luminous rune in the air",
            "knack": "hums an earthy tune and communes with nature",
        }

        magic_type = spell.magic_type.value if hasattr(spell.magic_type, 'value') else str(spell.magic_type)
        verb = magic_verbs.get(magic_type, "channels mystical energy")

        parts = [f"{caster_name} {verb}, casting {spell.name}."]

        # Add effect descriptions
        if result.damage_dealt:
            total = sum(
                (v.get("total", 0) if isinstance(v, dict) else v)
                for v in result.damage_dealt.values()
            )
            parts.append(f"The spell strikes for {total} damage.")

        if result.healing_applied:
            total = sum(
                (v.get("total", 0) if isinstance(v, dict) else v)
                for v in result.healing_applied.values()
            )
            parts.append(f"Healing energy restores {total} hit points.")

        if result.conditions_applied:
            conditions = ", ".join(result.conditions_applied)
            parts.append(f"The magic induces {conditions}.")

        if result.targets_saved:
            saved_count = len(result.targets_saved)
            parts.append(f"{saved_count} target(s) resist part of the effect.")

        return " ".join(parts)

    def classify_spell_effect_type(self, spell: SpellData) -> SpellEffectType:
        """
        Classify a spell's effect type based on its description.

        This helps determine how the spell should be resolved:
        - MECHANICAL: Has clear damage, healing, or condition effects
        - NARRATIVE: Primarily descriptive, referee-adjudicated effects
        - HYBRID: Has both mechanical and narrative components

        Args:
            spell: The spell to classify

        Returns:
            The appropriate SpellEffectType
        """
        # Only return early if explicitly set to MECHANICAL or NARRATIVE
        # HYBRID is the default and triggers classification
        if spell.effect_type and spell.effect_type != SpellEffectType.HYBRID:
            return spell.effect_type

        description = spell.description.lower()

        # Strong mechanical indicators
        mechanical_patterns = [
            r"\d+d\d+",  # Dice notation
            r"inflicts?\s+\d+\s+damage",
            r"heals?\s+\d+",
            r"save\s+(?:versus|vs)",
            r"ac\s+\d+",
            r"attack\s+roll",
        ]

        # Strong narrative indicators
        narrative_patterns = [
            r"referee\s+(?:determines|decides|adjudicates)",
            r"at\s+the\s+(?:dm|referee)'s\s+discretion",
            r"creates?\s+(?:an?\s+)?(?:illusion|image|sound)",
            r"allows?\s+(?:the\s+caster\s+to|you\s+to)\s+(?:sense|detect|perceive)",
            r"provides?\s+(?:information|insight|knowledge)",
        ]

        has_mechanical = any(
            re.search(pattern, description) for pattern in mechanical_patterns
        )
        has_narrative = any(
            re.search(pattern, description) for pattern in narrative_patterns
        )

        if has_mechanical and has_narrative:
            return SpellEffectType.HYBRID
        elif has_mechanical:
            return SpellEffectType.MECHANICAL
        else:
            return SpellEffectType.NARRATIVE
