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
    DRUIDIC = "druidic"  # Druid spells
    RUNE = "rune"  # Fairy runes (Enchanter)


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

        if spell.effect_type in (SpellEffectType.MECHANICAL, SpellEffectType.HYBRID):
            effects_result = self._apply_mechanical_effects(
                spell=spell,
                caster=caster,
                targets_affected=targets_affected,
                targets_saved=targets_saved,
                save_negates=spell.save_negates,
                dice_roller=dice_roller,
            )
            damage_dealt = effects_result.get("damage_dealt", {})
            healing_applied = effects_result.get("healing_applied", {})
            conditions_applied = effects_result.get("conditions_applied", [])
            stat_modifiers_applied = effects_result.get("stat_modifiers_applied", [])

        # Calculate duration
        duration_remaining = self._calculate_duration(spell, caster, dice_roller)

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

    def _apply_mechanical_effects(
        self,
        spell: SpellData,
        caster: "CharacterState",
        targets_affected: list[str],
        targets_saved: list[str],
        save_negates: bool,
        dice_roller: Optional["DiceRoller"],
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
                            self._controller.apply_healing(target_id, healing)

                # Apply conditions
                if effect.category == MechanicalEffectCategory.CONDITION and effect.condition_applied:
                    result["conditions_applied"].append(effect.condition_applied)

                    # Apply to game state if controller available
                    if self._controller:
                        self._controller.apply_condition(
                            target_id, effect.condition_applied, source=spell.name
                        )

                # Record stat modifiers (these are typically handled by active effects)
                if effect.category in (MechanicalEffectCategory.BUFF, MechanicalEffectCategory.DEBUFF):
                    if effect.modifier_value is not None:
                        result["stat_modifiers_applied"].append({
                            "target_id": target_id,
                            "stat": effect.stat_modified or "general",
                            "modifier": effect.modifier_value,
                            "source": spell.name,
                        })

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
