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
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import json
import re
import uuid

if TYPE_CHECKING:
    from src.data_models import CharacterState, DiceRoller
    from src.game_state.global_controller import GlobalController

from src.narrative.intent_parser import SaveType
from src.oracle.spell_adjudicator import (
    MythicSpellAdjudicator,
    SpellAdjudicationType,
    AdjudicationContext,
    AdjudicationResult,
)
from src.oracle.mythic_gme import Likelihood


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
    flat_healing: Optional[int] = None  # Fixed healing amount (no dice)
    bonus_hp_dice: Optional[str] = None  # Temporary/bonus HP (Aid spell)

    # Conditions
    condition_applied: Optional[str] = None  # e.g., "charmed", "frightened"
    condition_duration: Optional[str] = None  # Duration in turns/rounds

    # Stat modifiers
    stat_modified: Optional[str] = None  # e.g., "AC", "attack", "speed"
    modifier_value: Optional[int] = None  # e.g., +2, -4
    modifier_dice: Optional[str] = None  # For variable modifiers
    condition_context: Optional[str] = None  # When modifier applies: "vs_missiles", "vs_melee"
    ac_override: Optional[int] = None  # Set AC to specific value (e.g., Shield of Force: AC 17)

    # Level scaling
    level_multiplier: bool = False  # Multiply damage/healing by caster level

    # Saving throw for this effect
    save_type: Optional[str] = None  # doom, ray, hold, blast, spell
    save_negates: bool = False  # Save completely negates effect
    save_halves: bool = False  # Save reduces effect by half

    # Death effects (Cloudkill, Disintegrate, Word of Doom, etc.)
    is_death_effect: bool = False  # This is a death/destruction effect
    death_on_failed_save: bool = False  # Failed save = instant death/destruction
    death_hd_threshold: Optional[int] = None  # Only affects creatures below this HD

    # Flat damage (for spells like Ignite that deal fixed damage)
    flat_damage: Optional[int] = None  # Fixed damage amount (no dice)

    # Targeting
    max_targets: Optional[int] = None  # Number of targets affected
    max_hd_affected: Optional[int] = None  # Max HD of creatures affected
    area_radius: Optional[int] = None  # Radius in feet for area effects

    # Charm/Control effects (Ingratiate, Dominate, Command, etc.)
    is_charm_effect: bool = False  # This is a charm/mind-control spell
    recurring_save_frequency: Optional[str] = None  # "daily", "hourly", "per_turn"
    charm_obeys_commands: bool = False  # Subject obeys verbal commands
    command_word_only: bool = False  # Single-word command (Command spell)
    multi_target_dice: Optional[str] = None  # For multi-target charms (e.g., "3d6")
    target_level_limit: Optional[int] = None  # Max level of affected creatures

    # Glyph/Lock effects (Glyph of Sealing, Glyph of Locking, Knock, etc.)
    is_glyph_effect: bool = False  # This spell creates/affects a glyph
    glyph_type: Optional[str] = None  # "sealing", "locking", "trap"
    has_password: bool = False  # Glyph can be bypassed with password
    can_bypass_level_diff: Optional[int] = None  # Higher-level casters can bypass
    is_unlock_effect: bool = False  # This spell unlocks/dispels (Knock)
    dispels_sealing: bool = False  # Dispels Glyph of Sealing
    disables_locking: bool = False  # Temporarily disables Glyph of Locking
    is_trap_glyph: bool = False  # This creates a trap glyph
    trap_trigger: Optional[str] = None  # "touch", "open", "read"

    # Combat modifier effects (Mirror Image, Haste, Confusion, Fear)
    is_combat_modifier: bool = False  # This spell modifies combat behavior
    creates_mirror_images: bool = False  # Mirror Image spell
    mirror_image_dice: Optional[str] = None  # Dice for images (e.g., "1d4")
    is_haste_effect: bool = False  # Haste spell (extra action, +AC, +initiative)
    is_confusion_effect: bool = False  # Confusion spell (random behavior)
    is_fear_effect: bool = False  # Fear spell (targets must flee/cower)
    attack_bonus: Optional[int] = None  # Attack bonus from spells like Ginger Snap
    initiative_bonus: Optional[int] = None  # Initiative modifier

    # Area/Zone effects (Web, Silence, Darkness, Fog Cloud, etc.)
    is_area_effect: bool = False  # This spell creates a persistent area effect
    area_effect_type: Optional[str] = None  # "web", "silence", "darkness", "fog", etc.
    blocks_movement: bool = False  # Area blocks/restricts movement
    blocks_vision: bool = False  # Area blocks vision (darkness, fog)
    blocks_sound: bool = False  # Area blocks sound (silence)
    blocks_spellcasting: bool = False  # Area prevents verbal spellcasting
    creates_hazard: bool = False  # Area deals damage or applies effects
    entangles: bool = False  # Area restrains creatures (web, entangle)

    # Buff/Immunity effects (Missile Ward, Water Breathing, etc.)
    grants_immunity: bool = False  # This spell grants immunity to something
    immunity_type: Optional[str] = None  # "missiles", "drowning", "gas", "fire", etc.
    enhances_vision: bool = False  # Dark Sight, Infravision, etc.
    vision_type: Optional[str] = None  # "darkvision", "infravision", "see_invisible"

    # Stat override effects (Feeblemind, etc.)
    is_stat_override: bool = False  # This spell overrides a stat to a fixed value
    override_stat: Optional[str] = None  # Which stat is overridden
    override_value: Optional[int] = None  # The value it's set to

    # Dispel/Removal effects
    is_dispel_effect: bool = False  # This spell removes other spell effects
    dispel_target: Optional[str] = None  # "all", "specific", "curse", "poison", etc.
    removes_condition: bool = False  # This spell removes a condition
    condition_removed: Optional[str] = None  # Which condition is removed

    # Summon/Control effects (Animate Dead, Conjure Animals, etc.)
    is_summon_effect: bool = False  # This spell summons/animates creatures
    summon_type: Optional[str] = None  # "undead", "animal", "elemental", "construct"
    summon_hd_max: Optional[int] = None  # Max HD of creatures summoned
    summon_count_dice: Optional[str] = None  # Dice for number of creatures
    summon_count_fixed: Optional[int] = None  # Fixed number of creatures
    summon_duration: Optional[str] = None  # Duration of summoning
    summoner_controls: bool = False  # If summoner controls the creatures
    summon_level_scaling: bool = False  # If HD/count scales with caster level

    # Curse effects (Curse, Bane, Bestow Curse, etc.)
    is_curse_effect: bool = False  # This is a curse spell
    curse_type: Optional[str] = None  # "minor", "major", "ability_drain", "wasting"
    curse_stat_affected: Optional[str] = None  # Which stat is cursed
    curse_modifier: Optional[int] = None  # How much the stat is reduced
    curse_is_permanent: bool = False  # Curse is permanent until removed
    requires_remove_curse: bool = False  # Requires Remove Curse to remove

    # Teleportation effects (Teleport, Dimension Door, etc.)
    is_teleport_effect: bool = False  # This spell teleports targets
    teleport_type: Optional[str] = None  # "short", "long", "planar"
    teleport_range: Optional[int] = None  # Max distance in feet
    teleport_accuracy: Optional[str] = None  # "exact", "approximate", "random"
    allows_passengers: bool = False  # Can bring other creatures
    max_passengers: Optional[int] = None  # How many can travel with caster

    # Divination effects (Detect Magic, Locate Object, etc.)
    is_divination_effect: bool = False  # This spell provides information
    divination_type: Optional[str] = None  # "detect", "locate", "scry", "communicate"
    detects_what: Optional[str] = None  # What is detected: "magic", "evil", "traps", etc.
    divination_range: Optional[int] = None  # Detection range in feet

    # Movement enhancement effects (Fly, Levitate, etc.)
    grants_movement: bool = False  # This spell grants a movement type
    movement_type: Optional[str] = None  # "fly", "levitate", "swim", "climb", "phase"
    movement_speed: Optional[int] = None  # Speed in feet per turn

    # Invisibility/Illusion effects
    is_invisibility_effect: bool = False  # This spell grants invisibility
    invisibility_type: Optional[str] = None  # "normal", "improved", "greater"
    is_illusion_effect: bool = False  # This spell creates an illusion
    illusion_type: Optional[str] = None  # "visual", "auditory", "phantasm"

    # Protection effects (Protection from Evil, etc.)
    is_protection_effect: bool = False  # This spell provides protection
    protection_type: Optional[str] = None  # "evil", "good", "elements", "magic"
    protection_bonus: Optional[int] = None  # AC/save bonus granted

    # Barrier/Wall effects (Wall of Fire, Wall of Ice, etc.)
    is_barrier_effect: bool = False  # This spell creates a barrier
    barrier_type: Optional[str] = None  # "fire", "ice", "stone", "force"
    barrier_damage: Optional[str] = None  # Damage on contact/passage
    barrier_blocks_movement: bool = True
    barrier_blocks_vision: bool = False

    # Compulsion/Geas effects
    is_compulsion_effect: bool = False  # This spell creates a geas/quest
    compulsion_type: Optional[str] = None  # "geas", "quest", "command"
    compulsion_penalty: Optional[str] = None  # Penalty for violation

    # Anti-magic effects
    is_antimagic_effect: bool = False  # This spell blocks/dispels magic
    antimagic_type: Optional[str] = None  # "dispel", "suppress", "nullify"
    antimagic_radius: Optional[int] = None  # Radius of effect

    # Oracle adjudication (Phase 4 - spells that defer to Mythic GME)
    requires_oracle: bool = False  # This spell requires oracle adjudication
    oracle_adjudication_type: Optional[str] = None  # "wish", "divination", "illusion", etc.
    oracle_question: Optional[str] = None  # Question for oracle if applicable


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

    # Oracle adjudication flag
    requires_oracle_adjudication: bool = False
    oracle_adjudication_type: Optional[str] = None

    def add_effect(self, effect: MechanicalEffect) -> None:
        """Add an effect and update flags."""
        self.effects.append(effect)
        if self.primary_effect is None:
            self.primary_effect = effect

        # Track oracle requirement
        if effect.requires_oracle:
            self.requires_oracle_adjudication = True
            if effect.oracle_adjudication_type:
                self.oracle_adjudication_type = effect.oracle_adjudication_type

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

    # Spell type/school classification (e.g., ["illusion", "phantasm"])
    # Used for condition-based memorization restrictions (dreamlessness affects illusions)
    spell_types: list[str] = field(default_factory=list)

    def get_spell_types(self) -> list[str]:
        """
        Get spell types, inferring from name/id if not explicitly set.

        Types relevant for memorization restrictions:
        - illusion: Phantasm, Hallucinatory terrain, etc.
        - phantasm: Phantasm spell specifically
        - invisibility: Invisibility spells
        """
        if self.spell_types:
            return self.spell_types

        # Infer from spell_id or name
        inferred = []
        name_lower = self.name.lower()
        spell_id_lower = self.spell_id.lower()

        if "phantasm" in name_lower or "phantasm" in spell_id_lower:
            inferred.append("phantasm")
            inferred.append("illusion")
        elif "illusion" in name_lower or "hallucinat" in name_lower:
            inferred.append("illusion")
        elif "invisib" in name_lower or "invisib" in spell_id_lower:
            inferred.append("invisibility")
            inferred.append("illusion")  # Invisibility is a type of illusion

        return inferred


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
    caster_level: int = 0  # Caster's level when the spell was cast (for dispel calculations)
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

        # Oracle-adjudicated spell registry and adjudicator
        self._oracle_spell_registry: dict[str, dict[str, Any]] = {}
        self._spell_adjudicator: Optional[MythicSpellAdjudicator] = None
        self._load_oracle_spell_registry()

        # Current casting context for special handlers
        self._current_context: dict[str, Any] = {}

    def _load_oracle_spell_registry(self) -> None:
        """Load the oracle-only spells registry from JSON."""
        registry_path = Path(__file__).parent.parent.parent / "data" / "system" / "oracle_only_spells.json"
        if registry_path.exists():
            with open(registry_path) as f:
                data = json.load(f)
                for entry in data.get("oracle_only_spells", []):
                    self._oracle_spell_registry[entry["spell_id"]] = entry

    def get_spell_adjudicator(self) -> MythicSpellAdjudicator:
        """Get or create the spell adjudicator instance."""
        if self._spell_adjudicator is None:
            self._spell_adjudicator = MythicSpellAdjudicator()
        return self._spell_adjudicator

    def is_oracle_spell(self, spell_id: str) -> bool:
        """Check if a spell is resolved via oracle adjudication."""
        return spell_id in self._oracle_spell_registry

    def get_oracle_spell_config(self, spell_id: str) -> Optional[dict[str, Any]]:
        """Get the oracle configuration for a spell."""
        return self._oracle_spell_registry.get(spell_id)

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
                caster_level=caster.level if hasattr(caster, "level") else 1,
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

        # Check for special spell handlers (spells needing custom logic)
        special_result = self._handle_special_spell(
            spell=spell,
            caster=caster,
            targets_affected=targets_affected,
            dice_roller=dice_roller,
        )
        if special_result:
            # Merge special result data into narrative context
            narrative_context.update(special_result.get("narrative_context", {}))
            # Add any items created
            if special_result.get("items_created"):
                narrative_context["items_created"] = special_result["items_created"]

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

        # Track dice we've already parsed to avoid duplicates
        parsed_dice: set[str] = set()

        # =================================================================
        # FIX 1: Level-scaled damage (must check BEFORE regular damage)
        # Pattern: "Xd6 damage per Level of the caster"
        # =================================================================
        level_damage_pattern = r"(\d+d\d+(?:\s*\+\s*\d+)?)\s+damage\s+per\s+level"
        level_damage_matches = re.findall(level_damage_pattern, description, re.IGNORECASE)
        for damage_dice in level_damage_matches:
            dice_clean = damage_dice.replace(" ", "")
            parsed_dice.add(dice_clean)
            effect = MechanicalEffect(
                category=MechanicalEffectCategory.DAMAGE,
                damage_dice=dice_clean,
                level_multiplier=True,  # Multiply by caster level
                description=f"Deals {dice_clean} × caster level damage",
            )

            # Try to identify damage type
            for dtype in ["fire", "cold", "lightning", "acid", "poison", "holy", "necrotic"]:
                if dtype in description:
                    effect.damage_type = dtype
                    break

            parsed.add_effect(effect)

        # =================================================================
        # FIX 2: Regular damage (skip if in damage reduction context)
        # Pattern: "Xd6 damage", but NOT "Xd6 damage is reduced"
        # =================================================================
        damage_pattern = r"(\d+d\d+(?:\s*\+\s*\d+)?)\s*(?:points?\s+of\s+)?damage"
        for match in re.finditer(damage_pattern, description, re.IGNORECASE):
            damage_dice = match.group(1).replace(" ", "")

            # Skip if already parsed as level-scaled damage
            if damage_dice in parsed_dice:
                continue

            # FIX: Check if this is damage reduction context (false positive)
            # Look at text AFTER the match for "reduced", "reduction", "less"
            after_text = description[match.end():match.end() + 30]
            if "reduced" in after_text or "reduction" in after_text or "less" in after_text:
                continue  # This describes damage reduction, not damage dealt

            parsed_dice.add(damage_dice)
            effect = MechanicalEffect(
                category=MechanicalEffectCategory.DAMAGE,
                damage_dice=damage_dice,
                description=f"Deals {damage_dice} damage",
            )

            # Try to identify damage type
            for dtype in ["fire", "cold", "lightning", "acid", "poison", "holy", "necrotic"]:
                if dtype in description:
                    effect.damage_type = dtype
                    break

            parsed.add_effect(effect)

        # =================================================================
        # FIX 2.5: Flat damage patterns (no dice)
        # Patterns: "1 damage per round", "2 points of damage", "takes 1 damage"
        # =================================================================
        flat_damage_patterns = [
            r"(?:deals?|takes?|causes?|inflicts?)\s+(\d+)\s+(?:points?\s+of\s+)?damage",
            r"(\d+)\s+(?:points?\s+of\s+)?damage\s+per\s+(?:round|turn)",
            r"suffer(?:s|ing)?\s+(\d+)\s+(?:points?\s+of\s+)?damage",
        ]
        for pattern in flat_damage_patterns:
            flat_matches = re.findall(pattern, description, re.IGNORECASE)
            for flat_dmg in flat_matches:
                damage_val = int(flat_dmg)
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.DAMAGE,
                    flat_damage=damage_val,
                    description=f"Deals {damage_val} flat damage",
                )

                # Try to identify damage type
                for dtype in ["fire", "cold", "lightning", "acid", "poison", "holy", "necrotic"]:
                    if dtype in description:
                        effect.damage_type = dtype
                        break

                parsed.add_effect(effect)
                break  # Only add one flat damage effect

        # =================================================================
        # FIX 2.6: Death effects (instant death on failed save)
        # Patterns: "dies instantly", "killed outright", "slain", "disintegrate"
        # =================================================================
        death_patterns = [
            r"(?:die|dies|death),?\s*(?:instantly|immediately|outright)",
            r"or\s+die\b",  # "must save or die"
            r"(?:killed|slain)\s*(?:instantly|outright|immediately)?",
            r"disintegrate[sd]?",
            r"disintegration",  # "resist disintegration"
            r"destroys?\s+(?:the\s+)?(?:material\s+)?(?:form|body)",  # "destroys the material form"
            r"turns?\s+to\s+(?:dust|stone|ash)",
            r"(?:slay|slays|slaying)\s+",
            r"creature[s]?\s+with\s+(\d+)\s+(?:or\s+fewer\s+)?(?:hd|hit\s+dice).*(?:die|killed|slain)",
        ]
        for pattern in death_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Check for HD threshold in death effects
                hd_match = re.search(
                    r"(\d+)\s+(?:or\s+fewer\s+)?(?:hd|hit\s+dice)",
                    description, re.IGNORECASE
                )
                hd_threshold = int(hd_match.group(1)) if hd_match else None

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.DAMAGE,
                    is_death_effect=True,
                    death_on_failed_save=True,
                    death_hd_threshold=hd_threshold,
                    description="Death effect on failed save",
                )

                # Check for save type
                for save in ["doom", "ray", "hold", "blast", "spell"]:
                    if f"save versus {save}" in description or f"save vs {save}" in description:
                        effect.save_type = save
                        effect.save_negates = True
                        break

                parsed.add_effect(effect)
                break  # Only add one death effect

        # =================================================================
        # FIX 3: Healing patterns (exclude from damage parsing)
        # Only match "restores/heals Xd6", NOT "Xd6 Hit Points" alone
        # =================================================================
        heal_pattern = r"(?:heals?|restores?|regains?)\s+(\d+d\d+(?:\s*\+\s*\d+)?)"
        heal_matches = re.findall(heal_pattern, description, re.IGNORECASE)
        for heal_dice in heal_matches:
            dice_clean = heal_dice.replace(" ", "")
            # Mark as parsed so damage parser skips it
            parsed_dice.add(dice_clean)
            effect = MechanicalEffect(
                category=MechanicalEffectCategory.HEALING,
                healing_dice=dice_clean,
                description=f"Heals {dice_clean} HP",
            )
            parsed.add_effect(effect)

        # =================================================================
        # FIX 3.5: Flat healing patterns (no dice)
        # Patterns: "heals 5 Hit Points", "restores 10 HP"
        # =================================================================
        flat_heal_patterns = [
            r"(?:heals?|restores?|regains?)\s+(\d+)\s+(?:hit\s+points?|hp)",
            r"(?:heals?|restores?|regains?)\s+(\d+)\s+(?:points?\s+of\s+)?(?:health|vitality)",
        ]
        for pattern in flat_heal_patterns:
            flat_heal_matches = re.findall(pattern, description, re.IGNORECASE)
            for heal_val in flat_heal_matches:
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.HEALING,
                    flat_healing=int(heal_val),
                    description=f"Heals {heal_val} HP",
                )
                parsed.add_effect(effect)
                break  # Only add one flat healing effect

        # =================================================================
        # FIX 3.6: Bonus/temporary HP patterns (Aid spell)
        # Patterns: "gains 1d6 bonus Hit Points", "temporary hit points"
        # =================================================================
        bonus_hp_patterns = [
            r"gains?\s+(\d+d\d+(?:\s*\+\s*\d+)?)\s+(?:bonus|temporary|extra)\s+hit\s+points?",
            r"(\d+d\d+(?:\s*\+\s*\d+)?)\s+(?:bonus|temporary|extra)\s+hit\s+points?",
            r"temporary\s+hit\s+points?\s+(?:equal\s+to\s+)?(\d+d\d+)",
        ]
        for pattern in bonus_hp_patterns:
            bonus_matches = re.findall(pattern, description, re.IGNORECASE)
            for bonus_dice in bonus_matches:
                dice_clean = bonus_dice.replace(" ", "")
                parsed_dice.add(dice_clean)
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    bonus_hp_dice=dice_clean,
                    description=f"Grants {dice_clean} temporary HP",
                )
                parsed.add_effect(effect)
                break

        # =================================================================
        # FIX 4: Condition patterns with better context checking
        # =================================================================
        # Note: "charmed/charming/charm" are NOT included here because
        # charm effects are handled by the specialized charm patterns section
        # to ensure proper recurring save and caster tracking.
        condition_keywords = {
            "frightened": "frightened",
            "fear": "frightened",
            "terror": "frightened",  # "struck with terror", "terrifies"
            "terrifies": "frightened",
            "terrified": "frightened",
            "fleeing": "frightened",  # Fear spell causes fleeing
            "paralyzed": "paralyzed",
            "paralysis": "paralyzed",
            "paralysed": "paralyzed",
            "petrified": "petrified",
            "blinded": "blinded",
            "blind": "blinded",
            "deafened": "deafened",
            "deaf": "deafened",
            "poisoned": "poisoned",
            "asleep": "unconscious",
            "sleep": "unconscious",
            "unconscious": "unconscious",
            "stunned": "stunned",
            "stun": "stunned",
            "confused": "confused",  # Confusion spell
            "confusion": "confused",
            "delusions": "confused",  # "stricken with delusions"
            "uncontrollably": "confused",  # "become uncontrollably..."
        }
        # Note: Removed "stone" -> petrified (too many false positives)
        # Note: Removed "invisible" (often describes objects, not conditions)
        # Note: Removed "poison" (conflicts with poisoned, use poisoned only)
        # Note: Removed "charmed/charm" -> handled by charm patterns section

        for keyword, condition in condition_keywords.items():
            if keyword in description:
                # FIX: Better cure/remove detection with more patterns
                removal_patterns = [
                    f"cure {keyword}", f"cures {keyword}", f"curing {keyword}",
                    f"remove {keyword}", f"removes {keyword}", f"removing {keyword}",
                    f"negat" in description and keyword in description,  # "negating paralysis"
                    f"end {keyword}", f"ends {keyword}",
                    f"nullif" in description and keyword in description,  # "nullifying"
                    f"purge {keyword}", f"purges {keyword}",
                ]
                if any(pattern if isinstance(pattern, bool) else pattern in description
                       for pattern in removal_patterns):
                    continue

                # FIX: For "invisible", only apply if it's about creatures becoming invisible
                if keyword in ("invisible", "invisibility"):
                    creature_invisible_patterns = [
                        "creature.*invisible", "invisible.*creature",
                        "caster.*invisible", "caster is rendered invisible",
                        "subject.*invisible", "rendered invisible",
                        "become invisible", "becomes invisible",
                        "disappear from sight", "shimmers and disappears",
                    ]
                    if not any(re.search(p, description) for p in creature_invisible_patterns):
                        continue  # Probably "invisible barrier" or similar

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

        # =================================================================
        # FIX 5: AC override patterns (e.g., "grants AC 17")
        # =================================================================
        ac_override_pattern = r"(?:grants?|provides?|gives?|has)\s+(?:the\s+)?(?:caster\s+)?(?:an?\s+)?ac\s+(\d+)"
        ac_matches = re.findall(ac_override_pattern, description, re.IGNORECASE)
        for ac_value in ac_matches:
            effect = MechanicalEffect(
                category=MechanicalEffectCategory.BUFF,
                ac_override=int(ac_value),
                stat_modified="AC",
                description=f"Sets AC to {ac_value}",
            )

            # Check for conditional context (e.g., "AC 17 vs missiles")
            # Look for "missile" near this AC value
            if "missile" in description:
                effect.condition_context = "vs_missiles"
            elif "other" in description and "attack" in description:
                effect.condition_context = "vs_other"

            parsed.add_effect(effect)

        # =================================================================
        # Stat modifier patterns (expanded for British spelling)
        # =================================================================
        stat_patterns = [
            # "+1 bonus to attack" / "+1 to saving throw"
            r"([+-]\d+)\s*(?:bonus|penalty)?\s*(?:to\s+)?(?:attack|ac|armou?r\s+class|saving\s+throws?)",
            # "+1 Armour Class and Saving Throw bonus"
            r"([+-]\d+)\s+(?:armou?r\s+class|ac|saving\s+throws?|attack)[^.]*bonus",
            # "gain a +2 bonus"
            r"gains?\s+a?\s*([+-]\d+)\s+bonus",
        ]

        found_modifiers: set[int] = set()
        for pattern in stat_patterns:
            stat_matches = re.findall(pattern, description, re.IGNORECASE)
            for modifier in stat_matches:
                mod_val = int(modifier)
                if mod_val in found_modifiers:
                    continue  # Avoid duplicate modifiers
                found_modifiers.add(mod_val)

                category = MechanicalEffectCategory.BUFF if mod_val > 0 else MechanicalEffectCategory.DEBUFF
                effect = MechanicalEffect(
                    category=category,
                    modifier_value=mod_val,
                    description=f"Grants {modifier} modifier",
                )
                parsed.add_effect(effect)

        # =================================================================
        # Light source patterns (for Light spell)
        # =================================================================
        light_patterns = [
            r"(?:creates?|produces?|emits?|sheds?)\s+(?:bright\s+)?light",
            r"illuminat(?:es?|ing)\s+(?:a\s+)?(\d+)['\s]?\s*(?:foot|ft)?",
            r"light\s+(?:within|in)\s+a\s+(\d+)['\s]?\s*(?:foot|ft)?",
        ]
        for pattern in light_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Extract radius if present
                radius_match = re.search(r"(\d+)['\s]?\s*(?:foot|ft|radius)", description, re.IGNORECASE)
                radius = int(radius_match.group(1)) if radius_match else 30

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    description=f"Creates light ({radius}' radius)",
                    area_radius=radius,
                )
                parsed.add_effect(effect)
                break

        # =================================================================
        # Resistance/immunity patterns (for Ward spells)
        # =================================================================
        resistance_keywords = {
            "fire": ["fire", "flame", "heat", "burn"],
            "cold": ["cold", "ice", "frost", "freeze"],
            "lightning": ["lightning", "electric", "shock"],
            "poison": ["poison", "venom", "toxin"],
            "acid": ["acid", "corrosive"],
        }
        for damage_type, keywords in resistance_keywords.items():
            for keyword in keywords:
                resist_patterns = [
                    rf"resist(?:ance|s)?\s+(?:to\s+)?{keyword}",
                    rf"(?:immune|immunity)\s+(?:to\s+)?{keyword}",
                    rf"{keyword}\s+(?:damage\s+)?(?:is\s+)?(?:reduced|halved)",
                    rf"protect(?:s|ion)?\s+(?:from|against)\s+{keyword}",
                    rf"reduce\s+{keyword}\s+damage",  # "Reduce cold damage by..."
                    rf"{keyword}-based",  # "cold-based effects"
                    rf"untroubled\s+by\s+[^.]*{keyword}",  # "untroubled by...cold"
                    rf"rebuking\s+[^.]*{keyword}",  # "rebuking...cold and frost"
                    rf"ward\s+[^.]*{keyword}",  # ward spells often protect against element
                ]
                for pattern in resist_patterns:
                    if re.search(pattern, description, re.IGNORECASE):
                        effect = MechanicalEffect(
                            category=MechanicalEffectCategory.BUFF,
                            stat_modified="resistance",
                            damage_type=damage_type,
                            description=f"Resistance to {damage_type} damage",
                        )
                        parsed.add_effect(effect)
                        break

        # =================================================================
        # Morale bonus patterns (for Rally spell)
        # =================================================================
        morale_patterns = [
            r"(?:grants?|provides?|gives?)\s+(?:a\s+)?(?:bonus\s+(?:to\s+)?)?morale",
            r"morale\s+(?:bonus|boost|increase)",
            r"(?:bolsters?|improves?|strengthens?)\s+morale",
            r"(?:allies?|companions?)\s+(?:are\s+)?(?:immune|resist)\s+(?:to\s+)?fear",
        ]
        for pattern in morale_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    stat_modified="morale",
                    modifier_value=1,  # Default morale bonus
                    description="Grants morale bonus",
                )
                parsed.add_effect(effect)
                break

        # =================================================================
        # Immunity patterns (for Missile Ward, Proof Against Deadly Harm)
        # =================================================================
        immunity_patterns = [
            (r"(?:complete\s+)?protection\s+(?:from|against)\s+(?:normal\s+)?missiles?", "missiles"),
            (r"immune\s+to\s+(?:normal\s+)?missiles?", "missiles"),
            (r"immune\s+to\s+damage\s+from\s+(?:one\s+)?(?:specific\s+)?(?:type\s+of\s+)?weapons?", "weapon_type"),
            (r"completely\s+immune\s+to\s+damage", "damage_type"),
            (r"protection\s+from\s+(?:normal\s+)?(?:attacks?|weapons?)", "normal_attacks"),
            (r"hinders?\s+attacks?\s+against", "attacks_hindered"),  # Sanctuary
            (r"cannot\s+(?:be\s+)?(?:hit|struck)\s+by", "immunity"),
        ]
        for pattern, immunity_type in immunity_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    stat_modified="immunity",
                    condition_context=immunity_type,
                    description=f"Immunity/protection ({immunity_type})",
                )
                parsed.add_effect(effect)
                break

        # =================================================================
        # Charm/Control spell patterns
        # Detects: Ingratiate, Dominate, Command, Charm Serpents, etc.
        # =================================================================
        charm_patterns = [
            # "be charmed" / "or be charmed" / "is charmed"
            r"(?:must|or)\s+(?:be\s+)?charmed",
            # "is charmed" / "are charmed"
            r"(?:is|are)\s+charmed",
            # "charm a person" / "charms a creature"
            r"charm(?:s)?\s+(?:a\s+)?(?:person|creature|humanoid|subject)",
            # "places a powerful charm" / "enchants...charm"
            r"(?:places?|enchants?)\s+(?:a\s+)?(?:\w+\s+)?charm",
            # "hypnotises" (for Charm Serpents)
            r"hypnotis(?:es?|ed)",
        ]

        for pattern in charm_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.CONDITION,
                    condition_applied="charmed",
                    is_charm_effect=True,
                    description="Applies charm effect",
                )

                # Check for daily save pattern
                if re.search(r"save\s+(?:versus\s+spell\s+)?once\s+per\s+day", description, re.IGNORECASE):
                    effect.recurring_save_frequency = "daily"

                # Check for command obedience
                if re.search(r"(?:obey|commands?|orders?)\s+(?:they\s+)?(?:are\s+)?(?:obeyed|follow)", description, re.IGNORECASE) or \
                   re.search(r"(?:give|gives?)\s+(?:the\s+)?(?:charmed\s+)?(?:subject|creature)s?\s+commands", description, re.IGNORECASE) or \
                   re.search(r"caster\s+may\s+give.*commands", description, re.IGNORECASE):
                    effect.charm_obeys_commands = True

                # Check for multi-target dice (Dominate: "3d6 creatures")
                multi_match = re.search(r"(\d+d\d+)\s+creatures?\s+of", description, re.IGNORECASE)
                if multi_match:
                    effect.multi_target_dice = multi_match.group(1)

                # Check for level limit (Dominate: "up to Level 3")
                level_match = re.search(r"(?:of\s+)?(?:up\s+to\s+)?level\s+(\d+)\s+(?:or\s+(?:lower|less|fewer))?", description, re.IGNORECASE)
                if level_match:
                    effect.target_level_limit = int(level_match.group(1))

                # Check for save type (use regex to handle whitespace variations)
                for save in ["doom", "ray", "hold", "blast", "spell"]:
                    save_pattern = rf"save\s+(?:versus|vs\.?)\s+{save}"
                    if re.search(save_pattern, description, re.IGNORECASE):
                        effect.save_type = save
                        effect.save_negates = True
                        break

                parsed.add_effect(effect)
                break  # Only add one charm effect

        # =================================================================
        # Command spell patterns (single-word command)
        # =================================================================
        command_patterns = [
            r"(?:utters?\s+)?(?:a\s+)?command\s+(?:word|charged\s+with)",
            r"compelled\s+to\s+obey\s+for\s+\d+\s+round",
            r"command\s+is\s+limited\s+to\s+a\s+single\s+word",
        ]

        for pattern in command_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Don't add if we already parsed a charm effect
                if not any(e.is_charm_effect for e in parsed.effects):
                    effect = MechanicalEffect(
                        category=MechanicalEffectCategory.CONDITION,
                        condition_applied="commanded",
                        is_charm_effect=True,
                        command_word_only=True,
                        description="One-word command effect",
                    )

                    # Check for save type (use regex to handle whitespace variations)
                    for save in ["doom", "ray", "hold", "blast", "spell"]:
                        save_pattern = rf"save\s+(?:versus|vs\.?)\s+{save}"
                        if re.search(save_pattern, description, re.IGNORECASE):
                            effect.save_type = save
                            effect.save_negates = True
                            break

                    parsed.add_effect(effect)
                    break

        # =================================================================
        # Glyph spell patterns (Glyph of Sealing, Glyph of Locking, etc.)
        # =================================================================
        glyph_patterns = [
            # "glyph of sealing" / "glowing rune...preventing"
            (r"glyph\s+of\s+sealing", "sealing"),
            # "glowing rune...preventing" (sealing without name)
            (r"glowing\s+rune.*(?:preventing|sealed)", "sealing"),
            # "glyph of locking"
            (r"glyph\s+of\s+locking", "locking"),
            # "glowing rune...locking" (locking without name)
            (r"glowing\s+rune.*magically\s+locking", "locking"),
            # "serpent glyph" / trap glyphs
            (r"serpent\s+glyph", "trap"),
        ]

        for pattern, glyph_t in glyph_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_glyph_effect=True,
                    glyph_type=glyph_t,
                    description=f"Places a {glyph_t} glyph",
                )

                # Check for password feature
                if re.search(r"password", description, re.IGNORECASE):
                    effect.has_password = True

                # Check for level bypass (e.g., "3 Levels higher", "3 or more Levels higher")
                level_diff_match = re.search(
                    r"(\d+)\s+(?:or\s+more\s+)?levels?\s+(?:or\s+more\s+)?(?:higher|above)",
                    description, re.IGNORECASE
                )
                if level_diff_match:
                    effect.can_bypass_level_diff = int(level_diff_match.group(1))

                # Check for trap features
                if glyph_t == "trap":
                    effect.is_trap_glyph = True
                    # Look for trigger condition
                    if "touch" in description:
                        effect.trap_trigger = "touch"
                    elif "open" in description:
                        effect.trap_trigger = "open"
                    elif "step" in description:
                        effect.trap_trigger = "step"

                parsed.add_effect(effect)
                break

        # =================================================================
        # Knock spell patterns (unlock/dispel)
        # =================================================================
        knock_patterns = [
            r"knocks?\s+on.*portal",
            r"portal.*magically\s+opens",
            r"(?:locks?|bars?)\s+(?:are\s+)?(?:unlocked|removed)",
            r"glyphs?\s+of\s+sealing\s+(?:are\s+)?dispelled",
        ]

        for pattern in knock_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_unlock_effect=True,
                    description="Unlocks and dispels magical seals",
                )

                # Check specific dispel/disable behaviors
                if re.search(r"sealing.*dispelled", description, re.IGNORECASE):
                    effect.dispels_sealing = True

                if re.search(r"(?:locking|magical\s+seals?).*disabled", description, re.IGNORECASE):
                    effect.disables_locking = True

                parsed.add_effect(effect)
                break

        # =================================================================
        # Combat Modifier Spells (Mirror Image, Haste, Confusion, Fear)
        # =================================================================

        # Mirror Image patterns
        mirror_image_patterns = [
            r"mirror\s+image",
            r"illusory\s+(?:duplicates?|copies|images?)",
            r"(\d+d\d+)\s+(?:illusory\s+)?(?:images?|duplicates?)",
        ]

        for pattern in mirror_image_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    is_combat_modifier=True,
                    creates_mirror_images=True,
                    description="Creates illusory duplicates",
                )

                # Try to find dice for number of images
                dice_match = re.search(r"(\d+d\d+)\s+(?:illusory\s+)?(?:images?|duplicates?|copies)", description, re.IGNORECASE)
                if dice_match:
                    effect.mirror_image_dice = dice_match.group(1)
                else:
                    # Default per OSE
                    effect.mirror_image_dice = "1d4"

                parsed.add_effect(effect)
                break

        # Haste spell patterns
        haste_patterns = [
            r"\bhaste\b",
            r"(?:double|extra)\s+(?:movement|actions?)",
            r"(?:act|move)\s+twice",
            r"accelerat(?:e|ed|ion)",
        ]

        for pattern in haste_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    condition_applied="hasted",
                    is_combat_modifier=True,
                    is_haste_effect=True,
                    description="Grants extra actions and speed",
                )

                # Look for specific bonuses
                ac_bonus_match = re.search(r"\+(\d+)\s+(?:to\s+)?(?:ac|armou?r)", description, re.IGNORECASE)
                if ac_bonus_match:
                    effect.modifier_value = int(ac_bonus_match.group(1))
                    effect.stat_modified = "AC"
                else:
                    # Default per OSE Haste
                    effect.modifier_value = 2
                    effect.stat_modified = "AC"

                init_match = re.search(r"\+(\d+)\s+(?:to\s+)?initiative", description, re.IGNORECASE)
                if init_match:
                    effect.initiative_bonus = int(init_match.group(1))
                else:
                    effect.initiative_bonus = 2  # Default

                parsed.add_effect(effect)
                break

        # Confusion spell patterns
        confusion_patterns = [
            r"\bconfusion\b",
            r"(?:become|are|is)\s+confused",
            r"confused?\s+(?:targets?|creatures?|subjects?)",
            r"(?:random|erratic)\s+behavior",
            r"behave\s+(?:erratically|randomly)",
        ]

        for pattern in confusion_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.CONDITION,
                    condition_applied="confused",
                    is_combat_modifier=True,
                    is_confusion_effect=True,
                    description="Causes random behavior",
                )

                # Check for save type
                if re.search(r"save\s+vs\.?\s*spell", description, re.IGNORECASE):
                    effect.save_type = "spell"
                    effect.save_negates = True

                # Check for multi-target (e.g., "3d6 creatures")
                hd_match = re.search(r"(\d+d\d+)\s+(?:HD|hit\s+dice|creatures?)", description, re.IGNORECASE)
                if hd_match:
                    effect.multi_target_dice = hd_match.group(1)

                parsed.add_effect(effect)
                break

        # Fear spell patterns
        fear_patterns = [
            r"\bfear\b",
            r"\bfrightened?\b",
            r"flee\s+in\s+(?:terror|fear|panic)",
            r"must\s+flee",
            r"overcome\s+with\s+fear",
        ]

        for pattern in fear_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.CONDITION,
                    condition_applied="frightened",
                    is_combat_modifier=True,
                    is_fear_effect=True,
                    description="Causes targets to flee in fear",
                )

                # Check for save type
                if re.search(r"save\s+vs\.?\s*spell", description, re.IGNORECASE):
                    effect.save_type = "spell"
                    effect.save_negates = True

                parsed.add_effect(effect)
                break

        # Attack modifier spells (Ginger Snap, Bless, etc.)
        attack_bonus_patterns = [
            (r"\+(\d+)\s+(?:to\s+)?(?:attack|hit)\s+(?:rolls?|bonus)", "attack"),
            (r"attack\s+(?:rolls?\s+)?(?:gain|have|get)\s+\+(\d+)", "attack"),
            (r"ginger\s+snap", "ginger_snap"),
        ]

        for pattern, effect_type in attack_bonus_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    is_combat_modifier=True,
                    stat_modified="attack",
                    description="Modifies attack rolls",
                )

                if effect_type == "ginger_snap":
                    # Ginger Snap gives +2 to attack per OSE
                    effect.attack_bonus = 2
                    effect.modifier_value = 2
                else:
                    effect.attack_bonus = int(match.group(1))
                    effect.modifier_value = int(match.group(1))

                parsed.add_effect(effect)
                break

        # =================================================================
        # Area/Zone Effect Spells (Web, Silence, Darkness, Fog Cloud, etc.)
        # =================================================================

        # Web spell patterns
        web_patterns = [
            r"\bweb\b",
            r"sticky\s+(?:webs?|strands?)",
            r"(?:magical|giant)\s+spider\s*web",
            r"webs?\s+(?:fill|cover|block)",
        ]

        for pattern in web_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_area_effect=True,
                    area_effect_type="web",
                    blocks_movement=True,
                    entangles=True,
                    description="Creates entangling webs",
                )

                # Check for save to avoid
                if re.search(r"save", description, re.IGNORECASE):
                    effect.save_type = "spell"
                    effect.save_negates = True

                parsed.add_effect(effect)
                break

        # Silence spell patterns
        silence_patterns = [
            r"\bsilence\b",
            r"zone\s+of\s+silence",
            r"no\s+sound",
            r"sound.*cannot.*pass",
            r"prevents?\s+(?:sound|speech|verbal)",
        ]

        for pattern in silence_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_area_effect=True,
                    area_effect_type="silence",
                    blocks_sound=True,
                    blocks_spellcasting=True,
                    description="Creates a zone of silence",
                )

                parsed.add_effect(effect)
                break

        # Darkness spell patterns
        darkness_patterns = [
            r"\bdarkness\b",
            r"magical\s+darkness",
            r"impenetrable\s+dark",
            r"blocks?\s+(?:all\s+)?light",
            r"(?:light|torches?|lanterns?)\s+(?:cannot|won't|don't)\s+(?:penetrate|work|illuminate)",
        ]

        for pattern in darkness_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_area_effect=True,
                    area_effect_type="darkness",
                    blocks_vision=True,
                    description="Creates magical darkness",
                )

                parsed.add_effect(effect)
                break

        # Fog/Obscurement spell patterns
        fog_patterns = [
            r"\bfog\b",
            r"fog\s*cloud",
            r"mist",
            r"obscur(?:es?|ing|ement)",
            r"thick\s+(?:cloud|vapor|haze)",
        ]

        for pattern in fog_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_area_effect=True,
                    area_effect_type="fog",
                    blocks_vision=True,
                    description="Creates obscuring fog/mist",
                )

                parsed.add_effect(effect)
                break

        # Push/Wind spell patterns (Gust of Wind)
        wind_patterns = [
            r"gust\s+of\s+wind",
            r"powerful\s+wind",
            r"push(?:es)?\s+(?:back|away)",
            r"blow(?:s|n)?\s+(?:back|away)",
        ]

        for pattern in wind_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_area_effect=True,
                    area_effect_type="wind",
                    description="Creates a pushing wind effect",
                )

                # Check for save to resist
                if re.search(r"save", description, re.IGNORECASE):
                    effect.save_type = "spell"
                    effect.save_negates = True

                parsed.add_effect(effect)
                break

        # Hazard zone patterns (Stinking Cloud, Deathly Blossom, etc.)
        hazard_patterns = [
            r"stinking\s+cloud",
            r"nauseat(?:ing|es?)",
            r"poison(?:ous)?\s+(?:gas|cloud|vapor)",
            r"deathly\s+blossom",
            r"thorns?\s+(?:grow|spring|burst)",
            r"(?:fire|flame|ice|acid)\s+(?:fills?|covers?|spreads?)",
        ]

        for pattern in hazard_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_area_effect=True,
                    area_effect_type="hazard",
                    creates_hazard=True,
                    description="Creates a hazardous zone",
                )

                # Check for damage
                damage_match = re.search(r"(\d+d\d+)\s*(?:points?\s+of\s+)?damage", description, re.IGNORECASE)
                if damage_match:
                    effect.damage_dice = damage_match.group(1)

                # Check for save
                if re.search(r"save", description, re.IGNORECASE):
                    effect.save_type = "spell"
                    if re.search(r"half\s+damage|halves", description, re.IGNORECASE):
                        effect.save_halves = True
                    else:
                        effect.save_negates = True

                parsed.add_effect(effect)
                break

        # Entangle spell patterns
        entangle_patterns = [
            r"\bentangle\b",
            r"vines?\s+(?:and\s+roots?\s+)?(?:grow|wrap|grasp)",
            r"(?:vines?\s+and\s+)?roots?\s+wrap",
            r"plants?\s+(?:grab|restrain|hold)",
            r"roots?\s+(?:burst|spring|grab)",
        ]

        for pattern in entangle_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_area_effect=True,
                    area_effect_type="entangle",
                    blocks_movement=True,
                    entangles=True,
                    description="Creates entangling vegetation",
                )

                if re.search(r"save", description, re.IGNORECASE):
                    effect.save_type = "spell"
                    effect.save_negates = True

                parsed.add_effect(effect)
                break

        # =================================================================
        # Buff/Immunity Spells (Missile Ward, Water Breathing, etc.)
        # =================================================================

        # Missile immunity patterns
        missile_immunity_patterns = [
            r"(?:immune|immunity)\s+(?:to\s+)?(?:normal\s+)?missiles?",
            r"missiles?\s+(?:cannot|can't|do\s+not)\s+(?:harm|hurt|affect)",
            r"missile\s+ward",
            r"(?:arrows?|bolts?|projectiles?)\s+pass\s+(?:through|harmlessly)",
        ]

        for pattern in missile_immunity_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    grants_immunity=True,
                    immunity_type="missiles",
                    description="Grants immunity to normal missiles",
                )
                parsed.add_effect(effect)
                break

        # Drowning/breathing immunity patterns
        breathing_patterns = [
            r"water\s+breathing",
            r"breathe?\s+(?:under\s*)?water",
            r"(?:immune|immunity)\s+(?:to\s+)?drowning",
            r"cannot\s+drown",
            r"gills?",
        ]

        for pattern in breathing_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    grants_immunity=True,
                    immunity_type="drowning",
                    description="Grants ability to breathe underwater",
                )
                parsed.add_effect(effect)
                break

        # Gas/poison gas immunity patterns
        gas_immunity_patterns = [
            r"air\s+sphere",
            r"(?:immune|immunity)\s+(?:to\s+)?(?:gas|gaseous|poison\s+gas)",
            r"gas(?:es)?\s+(?:cannot|can't)\s+(?:harm|affect)",
            r"(?:protected|safe)\s+from\s+gas",
        ]

        for pattern in gas_immunity_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    grants_immunity=True,
                    immunity_type="gas",
                    description="Grants immunity to gaseous effects",
                )
                parsed.add_effect(effect)
                break

        # Vision enhancement patterns
        vision_patterns = [
            (r"dark\s*sight", "darkvision"),
            (r"infravision", "infravision"),
            (r"see\s+(?:in\s+)?(?:the\s+)?dark", "darkvision"),
            (r"(?:see|perceive)\s+(?:the\s+)?invisible", "see_invisible"),
            (r"true\s*(?:sight|seeing)", "truesight"),
        ]

        for pattern, vision_type in vision_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    enhances_vision=True,
                    vision_type=vision_type,
                    description=f"Grants {vision_type} vision",
                )
                parsed.add_effect(effect)
                break

        # Stat override patterns (Feeblemind)
        stat_override_patterns = [
            (r"feeblemind", "INT", 3),
            (r"intelligence\s+(?:is\s+)?reduced\s+to\s+(?:that\s+of\s+)?(?:an?\s+)?animal", "INT", 3),
            (r"intelligence\s+(?:becomes?|reduced\s+to|set\s+to)\s+(\d+)", "INT", None),
            (r"wisdom\s+(?:becomes?|reduced\s+to|set\s+to)\s+(\d+)", "WIS", None),
        ]

        for pattern, stat, fixed_value in stat_override_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                value = fixed_value
                if value is None and match.lastindex:
                    value = int(match.group(1))
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.DEBUFF,
                    is_stat_override=True,
                    override_stat=stat,
                    override_value=value,
                    description=f"Sets {stat} to {value}",
                )

                # Feeblemind typically requires save
                if "feeblemind" in pattern or "feeblemind" in spell.name.lower():
                    effect.save_type = "spell"
                    effect.save_negates = True

                parsed.add_effect(effect)
                break

        # Dispel Magic patterns
        dispel_patterns = [
            r"dispel\s+magic",
            r"(?:removes?|ends?|cancels?)\s+(?:all\s+)?(?:magical?\s+)?effects?",
            r"(?:negates?|suppresses?)\s+(?:magical?\s+)?(?:effects?|enchantments?)",
        ]

        for pattern in dispel_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_dispel_effect=True,
                    dispel_target="all",
                    description="Dispels magical effects",
                )
                parsed.add_effect(effect)
                break

        # Remove Curse patterns
        remove_curse_patterns = [
            r"remove\s+curse",
            r"(?:lifts?|breaks?|ends?)\s+(?:a\s+)?curse",
            r"curse.*(?:removed|lifted|broken)",
        ]

        for pattern in remove_curse_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_dispel_effect=True,
                    dispel_target="curse",
                    removes_condition=True,
                    condition_removed="cursed",
                    description="Removes curses",
                )
                parsed.add_effect(effect)
                break

        # Remove Poison patterns
        remove_poison_patterns = [
            r"remove\s+poison",
            r"neutralize\s+poison",
            r"cure(?:s)?\s+poison",
            r"poison.*(?:removed|neutralized|cured)",
        ]

        for pattern in remove_poison_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    removes_condition=True,
                    condition_removed="poisoned",
                    description="Removes poison effects",
                )
                parsed.add_effect(effect)
                break

        # Cure Affliction / Disease patterns
        cure_affliction_patterns = [
            r"cure\s+(?:affliction|disease)",
            r"(?:removes?|cures?)\s+(?:all\s+)?(?:afflictions?|diseases?)",
            r"(?:disease|affliction).*(?:removed|cured)",
        ]

        for pattern in cure_affliction_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    removes_condition=True,
                    condition_removed="diseased",
                    description="Removes diseases and afflictions",
                )
                parsed.add_effect(effect)
                break

        # Summon/Animate patterns (ordered from specific to generic)
        summon_patterns = [
            # Animate Dead patterns
            (r"animate\s+(?:the\s+)?dead", "undead", True),
            (r"(?:raises?|creates?)\s+(?:\d+(?:d\d+)?\s+)?(?:undead|skeletons?|zombies?)", "undead", True),
            (r"corpses?\s+(?:rise|animate|become)", "undead", True),
            # Elemental patterns (before generic to ensure priority)
            (r"(?:summons?|conjures?|calls?)\s+(?:an?\s+)?elementals?", "elemental", True),
            # Construct patterns
            (r"(?:animates?|brings?\s+to\s+life)\s+(?:an?\s+)?(?:statues?|constructs?|objects?)", "construct", True),
            # Animal patterns (with dice notation support)
            (r"(?:conjures?|summons?)\s+(?:\d+(?:d\d+)?\s+)?(?:animals?|beasts?)", "animal", True),
            (r"(?:call|summon)\s+(?:forth\s+)?(?:animals?|beasts?)", "animal", True),
            # Generic summon (last - catches everything else)
            (r"(?:summons?|conjures?|calls?\s+forth)\s+", None, True),
        ]

        for pattern, summon_type, controls in summon_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Try to extract HD limit
                hd_match = re.search(r"up\s+to\s+(\d+)\s*(?:HD|hit\s+dice)", description, re.IGNORECASE)
                max_hd = int(hd_match.group(1)) if hd_match else None

                # Try to extract count (dice or fixed)
                count_dice_match = re.search(r"(\d+d\d+)\s+(?:creatures?|undead|skeletons?|zombies?|animals?|beasts?)", description, re.IGNORECASE)
                count_fixed_match = re.search(r"(?:summons?|raises?|animates?|conjures?|creates?)\s+(\d+)\s+", description, re.IGNORECASE)

                count_dice = count_dice_match.group(1) if count_dice_match else None
                count_fixed = int(count_fixed_match.group(1)) if count_fixed_match else None

                # Check for level scaling
                level_scaling = bool(re.search(r"per\s+(?:caster\s+)?level", description, re.IGNORECASE))

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_summon_effect=True,
                    summon_type=summon_type,
                    summon_hd_max=max_hd,
                    summon_count_dice=count_dice,
                    summon_count_fixed=count_fixed,
                    summoner_controls=controls,
                    summon_level_scaling=level_scaling,
                    description=f"Summons {summon_type or 'creature'}",
                )
                parsed.add_effect(effect)
                break

        # Curse patterns (ordered from specific to generic)
        curse_patterns = [
            # Wasting/decay curses (check first since they contain "curse" often)
            (r"(?:wasting|withering|decay)\s+(?:curse)?", "wasting", True),
            (r"drains?\s+(?:the\s+)?(?:target's?\s+)?(?:vitality|life|essence)", "wasting", True),
            # Ability drain curses
            (r"(?:reduces?|drains?|lowers?)\s+(?:target's?\s+)?(?:strength|dexterity|constitution|intelligence|wisdom|charisma)", "ability_drain", True),
            # Bane/minor curses
            (r"\bbane\b", "minor", True),
            (r"(?:ill\s+luck|bad\s+fortune|misfortune)", "minor", True),
            # Standard curse (last - catches generic curses)
            (r"bestow\s+curse", "major", True),
            (r"\bcurse\b", "major", True),
        ]

        for pattern, curse_type, requires_remove in curse_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Check for stat affected
                stat_match = re.search(r"(?:strength|str|dexterity|dex|constitution|con|intelligence|int|wisdom|wis|charisma|cha)", description, re.IGNORECASE)
                stat_affected = None
                if stat_match:
                    stat_map = {
                        "strength": "STR", "str": "STR",
                        "dexterity": "DEX", "dex": "DEX",
                        "constitution": "CON", "con": "CON",
                        "intelligence": "INT", "int": "INT",
                        "wisdom": "WIS", "wis": "WIS",
                        "charisma": "CHA", "cha": "CHA",
                    }
                    stat_affected = stat_map.get(stat_match.group(0).lower())

                # Check for modifier
                modifier_match = re.search(r"[-−](\d+)", description)
                modifier = -int(modifier_match.group(1)) if modifier_match else None

                # Check for permanent
                is_permanent = bool(re.search(r"permanent|until\s+removed", description, re.IGNORECASE))

                # Check for save
                has_save = bool(re.search(r"save|saving\s+throw", description, re.IGNORECASE))

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.DEBUFF,
                    is_curse_effect=True,
                    curse_type=curse_type,
                    curse_stat_affected=stat_affected,
                    curse_modifier=modifier,
                    curse_is_permanent=is_permanent,
                    requires_remove_curse=requires_remove,
                    save_type="spell" if has_save else None,
                    save_negates=has_save,
                    description=f"Applies {curse_type} curse",
                )
                parsed.add_effect(effect)
                break

        # Teleportation patterns (ordered from specific to generic)
        teleport_patterns = [
            (r"plane\s+shift", "planar", None),
            (r"(?:gate|portal)\s+(?:to|between)", "planar", None),
            (r"dimension\s+door", "short", 360),
            (r"(?:blink|phase)\s+(?:to|through|away)", "short", 30),
            (r"teleport", "long", None),
            (r"transport(?:s|ed)?\s+(?:to|instantly)", "long", None),
        ]

        for pattern, teleport_type, range_val in teleport_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Check for passengers
                passenger_match = re.search(r"(?:with\s+)?(?:up\s+to\s+)?(\d+)\s+(?:other\s+)?(?:creatures?|passengers?|beings?)", description, re.IGNORECASE)
                max_passengers = int(passenger_match.group(1)) if passenger_match else None
                allows_passengers = max_passengers is not None or bool(re.search(r"(?:others?|companions?|passengers?)", description, re.IGNORECASE))

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_teleport_effect=True,
                    teleport_type=teleport_type,
                    teleport_range=range_val,
                    allows_passengers=allows_passengers,
                    max_passengers=max_passengers,
                    description=f"Teleportation ({teleport_type})",
                )
                parsed.add_effect(effect)
                break

        # Divination/Detection patterns
        divination_patterns = [
            (r"detect\s+magic", "detect", "magic"),
            (r"detect\s+evil", "detect", "evil"),
            (r"detect\s+(?:good|law|chaos)", "detect", "alignment"),
            (r"detect\s+(?:traps?|snares?)", "detect", "traps"),
            (r"detect\s+(?:invisib(?:le|ility)|hidden)", "detect", "invisible"),
            (r"locate\s+object", "locate", "object"),
            (r"locate\s+(?:creature|person|being)", "locate", "creature"),
            (r"clairvoyance|scry(?:ing)?", "scry", "remote_viewing"),
            (r"esp|read\s+(?:mind|thought)", "detect", "thoughts"),
            (r"tongues?|comprehend\s+languages?", "communicate", "languages"),
        ]

        for pattern, div_type, what in divination_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Try to extract range
                range_match = re.search(r"(\d+)['\"]?\s*(?:feet|ft|radius)?", description)
                div_range = int(range_match.group(1)) if range_match else None

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_divination_effect=True,
                    divination_type=div_type,
                    detects_what=what,
                    divination_range=div_range,
                    description=f"Divination: {what}",
                )
                parsed.add_effect(effect)
                break

        # Movement enhancement patterns
        movement_patterns = [
            (r"\bfly\b|flight|airborne", "fly", 120),
            (r"levitat(?:e|ion)", "levitate", 20),
            (r"water\s+walk(?:ing)?", "water_walk", None),
            (r"spider\s+climb|wall\s+crawl", "climb", 60),
            (r"swim(?:ming)?.*(?:speed|fast)", "swim", 120),
            (r"phase|ethereal|incorporeal", "phase", 60),
            (r"haste|speed|swiftness", "haste", None),
        ]

        for pattern, move_type, speed in movement_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Try to extract speed if mentioned
                speed_match = re.search(r"(\d+)['\"]?\s*(?:per\s+)?(?:turn|round|movement)", description)
                if speed_match:
                    speed = int(speed_match.group(1))

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    grants_movement=True,
                    movement_type=move_type,
                    movement_speed=speed,
                    description=f"Grants {move_type} movement",
                )
                parsed.add_effect(effect)
                break

        # Invisibility patterns
        invisibility_patterns = [
            (r"improved\s+invisib(?:le|ility)", "improved"),
            (r"greater\s+invisib(?:le|ility)", "greater"),
            (r"invisib(?:le|ility)", "normal"),
        ]

        for pattern, inv_type in invisibility_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    is_invisibility_effect=True,
                    invisibility_type=inv_type,
                    description=f"Grants {inv_type} invisibility",
                )
                parsed.add_effect(effect)
                break

        # Illusion patterns
        illusion_patterns = [
            (r"phantasm(?:al)?", "phantasm"),
            (r"illusion(?:ary)?", "visual"),
            (r"(?:creates?\s+)?(?:illusory|fake|false)\s+(?:image|sound|appearance)", "visual"),
            (r"silent\s+image|visual\s+illusion", "visual"),
            (r"(?:ghost|phantom)\s+sound|auditory\s+illusion", "auditory"),
        ]

        for pattern, ill_type in illusion_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_illusion_effect=True,
                    illusion_type=ill_type,
                    description=f"Creates {ill_type} illusion",
                )
                parsed.add_effect(effect)
                break

        # Protection patterns
        protection_patterns = [
            (r"protection\s+(?:from\s+)?evil", "evil", 1),
            (r"protection\s+(?:from\s+)?good", "good", 1),
            (r"protection\s+(?:from\s+)?(?:elements?|fire|cold|lightning)", "elements", 2),
            (r"magic\s+circle", "evil", 2),
            (r"(?:ward|shield)\s+(?:against|from)\s+magic", "magic", None),
            (r"anti-?magic", "magic", None),
        ]

        for pattern, prot_type, bonus in protection_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Try to extract bonus
                bonus_match = re.search(r"\+(\d+)\s*(?:to\s+)?(?:AC|saves?|armor)", description)
                if bonus_match:
                    bonus = int(bonus_match.group(1))

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.BUFF,
                    is_protection_effect=True,
                    protection_type=prot_type,
                    protection_bonus=bonus,
                    description=f"Protection from {prot_type}",
                )
                parsed.add_effect(effect)
                break

        # Barrier/Wall patterns
        barrier_patterns = [
            (r"wall\s+of\s+fire", "fire", "2d6", False),
            (r"wall\s+of\s+ice", "ice", None, True),
            (r"wall\s+of\s+stone", "stone", None, True),
            (r"wall\s+of\s+iron", "iron", None, True),
            (r"wall\s+of\s+force", "force", None, False),
            (r"wall\s+of\s+thorns?", "thorns", "1d6", False),
            (r"blade\s+barrier", "blades", "8d8", False),
        ]

        for pattern, barrier_type, damage, blocks_vision in barrier_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_barrier_effect=True,
                    barrier_type=barrier_type,
                    barrier_damage=damage,
                    barrier_blocks_movement=True,
                    barrier_blocks_vision=blocks_vision,
                    description=f"Creates wall of {barrier_type}",
                )
                parsed.add_effect(effect)
                break

        # Geas/Compulsion patterns
        compulsion_patterns = [
            (r"\bgeas\b", "geas"),
            (r"holy\s+quest", "quest"),
            (r"(?:compel|compulsion)\s+(?:to|toward)", "compulsion"),
            (r"(?:must|shall)\s+(?:obey|serve|complete)", "command"),
        ]

        for pattern, comp_type in compulsion_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.CONDITION,
                    is_compulsion_effect=True,
                    compulsion_type=comp_type,
                    description=f"Applies {comp_type}",
                )

                # Check for save
                if re.search(r"save|saving\s+throw", description, re.IGNORECASE):
                    effect.save_type = "spell"
                    effect.save_negates = True

                parsed.add_effect(effect)
                break

        # Anti-magic patterns
        antimagic_patterns = [
            (r"anti-?magic\s+(?:shell|field|zone)", "nullify"),
            (r"dispel\s+(?:all\s+)?magic", "dispel"),
            (r"suppress(?:es?)?\s+(?:all\s+)?magic", "suppress"),
            (r"(?:negates?|cancels?)\s+(?:all\s+)?magic", "nullify"),
        ]

        for pattern, am_type in antimagic_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                # Try to extract radius
                radius_match = re.search(r"(\d+)['\"]?\s*(?:foot|feet|ft)?\s*radius", description, re.IGNORECASE)
                radius = int(radius_match.group(1)) if radius_match else None

                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    is_antimagic_effect=True,
                    antimagic_type=am_type,
                    antimagic_radius=radius,
                    description=f"Anti-magic ({am_type})",
                )
                parsed.add_effect(effect)
                break

        # =====================================================================
        # ORACLE ADJUDICATION PATTERNS (Phase 4)
        # These spells defer to MythicSpellAdjudicator for resolution
        # =====================================================================

        # Wish/Reality-altering spells
        wish_patterns = [
            r"\bwish\b",
            r"alter\s+reality",
            r"miracle",
            r"limited\s+wish",
        ]

        for pattern in wish_patterns:
            if re.search(pattern, description, re.IGNORECASE) or \
               re.search(pattern, spell.name, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    requires_oracle=True,
                    oracle_adjudication_type="wish",
                    description="Wish - requires oracle adjudication",
                )
                parsed.add_effect(effect)
                break

        # Divination spells that need oracle interpretation
        divination_oracle_patterns = [
            (r"commune|communion", "divination"),
            (r"contact\s+(?:other\s+)?plane", "divination"),
            (r"augury|omen", "divination"),
            (r"legend\s+lore", "divination"),
            (r"speak\s+with\s+(?:dead|spirits?)", "divination"),
            (r"divination", "divination"),
        ]

        for pattern, adj_type in divination_oracle_patterns:
            if re.search(pattern, description, re.IGNORECASE) or \
               re.search(pattern, spell.name, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    requires_oracle=True,
                    oracle_adjudication_type=adj_type,
                    description=f"Divination - requires oracle adjudication",
                )
                parsed.add_effect(effect)
                break

        # Illusion spells that need belief adjudication
        illusion_oracle_patterns = [
            r"phantasmal\s+(?:force|killer)",
            r"programmed\s+illusion",
            r"project\s+image",
            r"simulacrum",
            r"veil",
        ]

        for pattern in illusion_oracle_patterns:
            if re.search(pattern, description, re.IGNORECASE) or \
               re.search(pattern, spell.name, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    requires_oracle=True,
                    oracle_adjudication_type="illusion_belief",
                    description="Illusion - requires belief adjudication",
                )
                parsed.add_effect(effect)
                break

        # Summoning control spells
        summoning_oracle_patterns = [
            r"conjure\s+elemental",
            r"summon\s+(?:demon|devil|fiend)",
            r"planar\s+(?:binding|ally)",
            r"gate",
        ]

        for pattern in summoning_oracle_patterns:
            if re.search(pattern, description, re.IGNORECASE) or \
               re.search(pattern, spell.name, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    requires_oracle=True,
                    oracle_adjudication_type="summoning_control",
                    description="Summoning - requires control adjudication",
                )
                parsed.add_effect(effect)
                break

        # Communication spells
        communication_oracle_patterns = [
            r"speak\s+with\s+(?:animals|plants|monsters)",
            r"tongues",
            r"sending",
            r"message",
            r"telepathy",
        ]

        for pattern in communication_oracle_patterns:
            if re.search(pattern, description, re.IGNORECASE) or \
               re.search(pattern, spell.name, re.IGNORECASE):
                effect = MechanicalEffect(
                    category=MechanicalEffectCategory.UTILITY,
                    requires_oracle=True,
                    oracle_adjudication_type="communication",
                    description="Communication - requires narrative adjudication",
                )
                parsed.add_effect(effect)
                break

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
                    flat_damage=effect_data.get("flat_damage"),
                    flat_healing=effect_data.get("flat_healing"),
                    condition_applied=effect_data.get("condition_applied"),
                    modifier_value=effect_data.get("modifier_value"),
                    save_type=effect_data.get("save_type"),
                    save_negates=effect_data.get("save_negates", False),
                    save_halves=effect_data.get("save_halves", False),
                    is_death_effect=effect_data.get("is_death_effect", False),
                    death_on_failed_save=effect_data.get("death_on_failed_save", False),
                    death_hd_threshold=effect_data.get("death_hd_threshold"),
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

                # Apply death effects first (instant death on failed save)
                if effect.category == MechanicalEffectCategory.DAMAGE and effect.is_death_effect:
                    if not target_saved and effect.death_on_failed_save:
                        # Check HD threshold if applicable
                        apply_death = True
                        if effect.death_hd_threshold and self._controller:
                            target = self._controller.get_character(target_id)
                            if target and target.level > effect.death_hd_threshold:
                                apply_death = False  # Too many HD, effect doesn't work

                        if apply_death:
                            # Track as death effect in result
                            if "death_effects" not in result:
                                result["death_effects"] = []
                            result["death_effects"].append({
                                "target_id": target_id,
                                "effect": "instant_death",
                                "hd_threshold": effect.death_hd_threshold,
                            })

                            # Set HP to 0 in game state
                            if self._controller:
                                target = self._controller.get_character(target_id)
                                if target:
                                    target.hp_current = 0

                    continue  # Death effects don't also deal regular damage

                # Apply damage (dice-based)
                if effect.category == MechanicalEffectCategory.DAMAGE and effect.damage_dice:
                    if dice_roller:
                        # Handle level-scaled damage (e.g., Fireball: 1d6 per level)
                        if effect.level_multiplier:
                            # Roll damage dice once per caster level
                            total_damage = 0
                            for _ in range(caster.level):
                                roll = dice_roller.roll(effect.damage_dice, f"{spell.name} damage")
                                total_damage += roll.total
                            damage = total_damage
                        else:
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

                # Apply flat damage (no dice)
                if effect.category == MechanicalEffectCategory.DAMAGE and effect.flat_damage:
                    damage = effect.flat_damage

                    # Half damage on save (if applicable)
                    if target_saved and effect.save_halves:
                        damage = max(1, damage // 2)

                    result["damage_dealt"][target_id] = damage

                    # Apply to game state if controller available
                    if self._controller:
                        self._controller.apply_damage(
                            target_id, damage, effect.damage_type or "magic"
                        )

                # Apply healing (dice-based)
                if effect.category == MechanicalEffectCategory.HEALING and effect.healing_dice:
                    if dice_roller:
                        roll = dice_roller.roll(effect.healing_dice, f"{spell.name} healing")
                        healing = roll.total
                        result["healing_applied"][target_id] = healing

                        # Apply to game state if controller available
                        if self._controller:
                            self._controller.heal_character(target_id, healing)

                # Apply flat healing (no dice)
                if effect.category == MechanicalEffectCategory.HEALING and effect.flat_healing:
                    healing = effect.flat_healing
                    result["healing_applied"][target_id] = healing

                    # Apply to game state if controller available
                    if self._controller:
                        self._controller.heal_character(target_id, healing)

                # Apply conditions
                if effect.category == MechanicalEffectCategory.CONDITION and effect.condition_applied:
                    result["conditions_applied"].append(effect.condition_applied)

                    # Apply to game state if controller available
                    if self._controller:
                        # Special handling for charm effects
                        if effect.is_charm_effect and effect.condition_applied == "charmed":
                            # Use apply_charm which sets up recurring saves
                            recurring_save = None
                            if effect.recurring_save_frequency:
                                recurring_save = {
                                    "save_type": effect.save_type or "spell",
                                    "frequency": effect.recurring_save_frequency,
                                    "modifier": 0,
                                    "ends_on_success": True,
                                }

                            self._controller.apply_charm(
                                character_id=target_id,
                                caster_id=caster.character_id,
                                source_spell_id=spell.spell_id,
                                source=spell.name,
                                recurring_save=recurring_save,
                            )

                            # Track charm-specific info in result
                            if "charm_effects" not in result:
                                result["charm_effects"] = []
                            result["charm_effects"].append({
                                "target_id": target_id,
                                "caster_id": caster.character_id,
                                "spell_name": spell.name,
                                "obeys_commands": effect.charm_obeys_commands,
                                "recurring_save": effect.recurring_save_frequency,
                            })
                        else:
                            # Standard condition application
                            self._controller.apply_condition(
                                target_id, effect.condition_applied, source=spell.name
                            )

                # Apply stat modifiers (buffs/debuffs)
                if effect.category in (MechanicalEffectCategory.BUFF, MechanicalEffectCategory.DEBUFF):
                    # Handle AC override (e.g., Shield of Force: AC 17)
                    if effect.ac_override is not None:
                        modifier_info = {
                            "target_id": target_id,
                            "stat": "AC",
                            "ac_override": effect.ac_override,
                            "source": spell.name,
                            "condition": effect.condition_context,
                        }
                        result["stat_modifiers_applied"].append(modifier_info)

                        # Apply to game state if controller available
                        if self._controller:
                            self._controller.apply_buff(
                                character_id=target_id,
                                stat="AC",
                                value=effect.ac_override,
                                source=spell.name,
                                source_id=effect_id,
                                duration_turns=duration_turns,
                                condition=effect.condition_context,
                                is_override=True,  # Flag that this overrides AC, not adds to it
                            )

                    elif effect.modifier_value is not None:
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

    # =========================================================================
    # SPECIAL SPELL HANDLERS
    # =========================================================================

    def _handle_special_spell(
        self,
        spell: SpellData,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Handle spells that need custom logic beyond standard resolution.

        Args:
            spell: The spell being cast
            caster: The character casting
            targets_affected: List of affected target IDs
            dice_roller: Dice roller for any rolls needed

        Returns:
            Dictionary with special effect data, or None if no special handling
        """
        handlers = {
            "purify_food_and_drink": self._handle_purify_food_and_drink,
            "crystal_resonance": self._handle_crystal_resonance,
            # Phase 1 spell handlers
            "ventriloquism": self._handle_ventriloquism,
            "create_food": self._handle_create_food,
            "create_water": self._handle_create_water,
            "air_sphere": self._handle_air_sphere,
            "detect_disguise": self._handle_detect_disguise,
            # Phase 2 condition-based spell handlers
            "deathly_blossom": self._handle_deathly_blossom,
            "en_croute": self._handle_en_croute,
            "awe": self._handle_awe,
            "animal_growth": self._handle_animal_growth,
            # Phase 3 utility spell handlers
            "dispel_magic": self._handle_dispel_magic,
            # Phase 4 movement spell handlers
            "levitate": self._handle_levitate,
            "fly": self._handle_fly,
            "telekinesis": self._handle_telekinesis,
            # Phase 5 utility and transformation spell handlers
            "passwall": self._handle_passwall,
            "fools_gold": self._handle_fools_gold,
            "ginger_snap": self._handle_ginger_snap,
            # Phase 6 door/lock and trap spell handlers
            "through_the_keyhole": self._handle_through_the_keyhole,
            "lock_singer": self._handle_lock_singer,
            "serpent_glyph": self._handle_serpent_glyph,
            # Phase 7 teleportation, condition, and healing spell handlers
            "dimension_door": self._handle_dimension_door,
            "confusion": self._handle_confusion,
            "greater_healing": self._handle_greater_healing,
            # Phase 8 summoning and area effect spell handlers
            "animate_dead": self._handle_animate_dead,
            "cloudkill": self._handle_cloudkill,
            "insect_plague": self._handle_insect_plague,
            # Phase 9 transformation and utility spell handlers
            "petrification": self._handle_petrification,
            "invisibility": self._handle_invisibility,
            "knock": self._handle_knock,
            # Phase 10 remaining moderate/significant spell handlers
            "arcane_cypher": self._handle_arcane_cypher,
            "trap_the_soul": self._handle_trap_the_soul,
            "holy_quest": self._handle_holy_quest,
            "polymorph": self._handle_polymorph,
        }

        handler = handlers.get(spell.spell_id)
        if handler:
            return handler(caster, targets_affected, dice_roller)

        # Check for oracle-adjudicated spells
        if self.is_oracle_spell(spell.spell_id):
            return self._handle_oracle_spell(spell, caster, targets_affected, dice_roller)

        return None

    def _handle_oracle_spell(
        self,
        spell: SpellData,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle spells that are resolved via oracle adjudication.

        These are the 21 "Skip" spells from the formal plan that require
        Mythic GME oracle resolution rather than mechanical parsing.

        Args:
            spell: The spell being cast
            caster: The character casting
            targets_affected: List of affected target IDs
            dice_roller: Dice roller for any rolls needed

        Returns:
            Dictionary with oracle adjudication results and narrative context
        """
        config = self.get_oracle_spell_config(spell.spell_id)
        if not config:
            return {"error": f"Oracle spell config not found for {spell.spell_id}"}

        adjudicator = self.get_spell_adjudicator()
        adjudication_type = config.get("adjudication_type", "generic")
        question_template = config.get("default_question_template", "")

        # Build adjudication context
        target_description = ", ".join(targets_affected) if targets_affected else "the area"
        context = AdjudicationContext(
            spell_name=spell.name,
            caster_name=caster.name,
            caster_level=caster.level,
            target_description=target_description,
            intention=self._current_context.get("intention", spell.name),
        )

        # Route to appropriate adjudicator method based on type
        result: AdjudicationResult
        if adjudication_type == "wish":
            wish_text = self._current_context.get("wish_text", spell.name)
            result = adjudicator.adjudicate_wish(
                wish_text=wish_text,
                context=context,
                wish_power="major",  # Rune of Wishing is mighty tier
            )
        elif adjudication_type == "divination":
            question = self._current_context.get("question", question_template)
            result = adjudicator.adjudicate_divination(
                question=question,
                context=context,
                divination_type="general",
            )
        elif adjudication_type == "illusion_belief":
            result = adjudicator.adjudicate_illusion_belief(
                context=context,
                illusion_quality="standard",
            )
        elif adjudication_type == "summoning_control":
            creature_type = self._current_context.get("creature_type", "summoned creature")
            result = adjudicator.adjudicate_summoning_control(
                context=context,
                creature_type=creature_type,
            )
        else:
            # Generic adjudication for unspecified types
            result = adjudicator.adjudicate_generic(
                question=question_template,
                context=context,
            )

        # Build narrative context from adjudication result
        narrative_context = {
            "oracle_adjudication": {
                "adjudication_type": result.adjudication_type.value,
                "success_level": result.success_level.value,
                "summary": result.summary,
                "requires_interpretation": result.requires_interpretation(),
            },
            "spell_id": spell.spell_id,
            "spell_name": spell.name,
            "caster_name": caster.name,
            "targets": targets_affected,
        }

        # Include meaning roll for LLM interpretation if present
        if result.meaning_roll:
            narrative_context["oracle_adjudication"]["meaning_pair"] = (
                f"{result.meaning_roll.action} + {result.meaning_roll.subject}"
            )

        # Include complication if present
        if result.has_complication and result.complication_meaning:
            narrative_context["oracle_adjudication"]["complication"] = (
                f"{result.complication_meaning.action} + {result.complication_meaning.subject}"
            )

        # Track as active effect if spell has duration
        duration_str = spell.duration.lower() if spell.duration else ""
        if duration_str and duration_str not in ("instant", "instantaneous"):
            # Use spell's pre-parsed duration_type, or infer from raw string
            duration_type = spell.duration_type
            duration_value = 1  # Default value

            # If duration_type is INSTANT but raw string suggests otherwise, infer
            if duration_type == DurationType.INSTANT:
                if "turn" in duration_str:
                    duration_type = DurationType.TURNS
                elif "round" in duration_str:
                    duration_type = DurationType.ROUNDS
                elif "hour" in duration_str:
                    duration_type = DurationType.HOURS
                elif "day" in duration_str:
                    duration_type = DurationType.DAYS
                elif "permanent" in duration_str:
                    duration_type = DurationType.PERMANENT
                else:
                    duration_type = DurationType.SPECIAL

            # Try to extract numeric duration
            numbers = re.findall(r"\d+", duration_str)
            if numbers:
                duration_value = int(numbers[0])

            if duration_type != DurationType.INSTANT:
                # Use first target or "area" if no specific targets
                target_id = targets_affected[0] if targets_affected else "area"
                active_effect = ActiveSpellEffect(
                    effect_id=str(uuid.uuid4()),
                    spell_id=spell.spell_id,
                    spell_name=spell.name,
                    caster_id=caster.character_id,
                    caster_level=caster.level,
                    target_id=target_id,
                    target_type="area" if not targets_affected else "creature",
                    duration_type=duration_type,
                    duration_remaining=duration_value,
                    effect_type=SpellEffectType.NARRATIVE,
                    mechanical_effects={"oracle_adjudication": narrative_context.get("oracle_adjudication", {})},
                    narrative_description=result.summary,
                )
                self._active_effects.append(active_effect)
                narrative_context["active_effect_id"] = active_effect.effect_id

        return {
            "oracle_adjudication": result,
            "narrative_context": narrative_context,
        }

    def _handle_purify_food_and_drink(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Purify Food and Drink spell.

        Effects:
        - Purifies up to 12 portions of spoiled/poisoned food and drink
        - Resets freshness on spoiled rations (roll new 1d6 freshness_days)
        - Sets acquired_day to current day
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        current_day = 0  # Will be set from controller if available
        if self._controller:
            current_day = self._controller.time_tracker.days

        purified_items: list[dict[str, Any]] = []
        max_portions = 12

        # Find spoiled rations in caster's inventory
        for item in caster.inventory:
            if len(purified_items) >= max_portions:
                break

            if item.is_perishable and item.is_spoiled(current_day):
                # Roll new freshness
                new_freshness = dice.roll("1d6", "Purified ration freshness").total
                item.freshness_days = new_freshness
                item.acquired_day = current_day
                item.freshness_bonus_days = 0  # Reset any bonus

                purified_items.append({
                    "item_name": item.name,
                    "item_id": item.item_id,
                    "new_freshness_days": new_freshness,
                })

        return {
            "purified_count": len(purified_items),
            "purified_items": purified_items,
            "narrative_context": {
                "purified_items": purified_items,
                "purified_count": len(purified_items),
            },
        }

    def _handle_crystal_resonance(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Crystal Resonance spell.

        Creates a resonant_crystal item in caster's inventory based on energy type chosen.
        Energy types:
        - Light: Crystal acts as magical light source (duration: 1 Turn x caster level)
        - Images: Crystal stores a static image of surroundings
        - Sound: Crystal stores ambient sounds
        - Temperature (Heat): Crystal provides cold weather protection
        - Temperature (Cold): Crystal extends ration freshness by 2d4 days

        Note: This requires player input for energy type selection.
        The spell resolver will return a pending_choice that the caller must resolve.
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()

        # Check for 1-in-20 crystal destruction chance
        destruction_roll = dice.roll("1d20", "Crystal destruction check")
        crystal_shattered = destruction_roll.total == 1

        if crystal_shattered:
            return {
                "success": False,
                "crystal_shattered": True,
                "narrative_context": {
                    "crystal_shattered": True,
                    "destruction_roll": destruction_roll.total,
                },
            }

        # Create the resonant crystal item
        # Note: In actual gameplay, we need player input for energy_type
        # This returns a pending_choice structure for the caller to resolve
        return {
            "success": True,
            "pending_choice": {
                "type": "energy_selection",
                "prompt": "Choose the energy to imprint: Light, Images, Sound, or Temperature",
                "options": ["light", "images", "sound", "temperature"],
                "callback": "complete_crystal_resonance",
            },
            "caster_level": caster.level,
            "narrative_context": {
                "pending_energy_choice": True,
                "available_energies": ["light", "images", "sound", "temperature"],
            },
        }

    def complete_crystal_resonance(
        self,
        caster: "CharacterState",
        energy_type: str,
        temperature_mode: Optional[str] = None,
        dice_roller: Optional["DiceRoller"] = None,
        environmental_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Complete Crystal Resonance spell after player chooses energy type.

        Args:
            caster: The caster
            energy_type: "light", "images", "sound", or "temperature"
            temperature_mode: If energy_type is "temperature", either "heat" or "cold"
            dice_roller: Dice roller for any rolls
            environmental_context: Context about current environment for images/sound

        Returns:
            Dictionary with created item and effects
        """
        from src.data_models import Item, LightSourceType, DiceRoller as DR

        dice = dice_roller or DR()
        current_day = 0
        if self._controller:
            current_day = self._controller.time_tracker.days

        # Base crystal item
        crystal = Item(
            item_id=f"resonant_crystal_{uuid.uuid4().hex[:8]}",
            name="Resonant Crystal",
            weight=1,
            quantity=1,
            magical=True,
            value_gp=50,
            description="A crystal imbued with captured energy.",
        )

        energy_type = energy_type.lower()

        if energy_type == "light":
            # Crystal acts as magical light source
            duration_turns = caster.level * 10  # 1 Turn x caster level (in rounds, 10 rounds/turn)
            crystal.light_source = LightSourceType.MAGICAL
            crystal.light_remaining_turns = duration_turns
            crystal.name = "Resonant Crystal (Light)"
            crystal.description = f"A crystal glowing with captured light. Illuminates for {caster.level} turns."

        elif energy_type == "images":
            # Crystal stores a static image
            image_desc = "the surrounding area"
            if environmental_context:
                image_desc = environmental_context.get("scene_description", image_desc)
            crystal.name = "Resonant Crystal (Images)"
            crystal.description = f"A crystal containing a captured image of {image_desc}."
            crystal.consumption_effect = {
                "type": "images",
                "stored_image": image_desc,
            }

        elif energy_type == "sound":
            # Crystal stores ambient sounds
            sound_desc = "ambient sounds"
            if environmental_context:
                sound_desc = environmental_context.get("ambient_sounds", sound_desc)
            crystal.name = "Resonant Crystal (Sound)"
            crystal.description = f"A crystal that replays: {sound_desc}."
            crystal.consumption_effect = {
                "type": "sound",
                "stored_sound": sound_desc,
            }

        elif energy_type == "temperature":
            if temperature_mode == "heat":
                # Protects from cold weather
                crystal.name = "Resonant Crystal (Heat)"
                crystal.description = "A warm crystal that provides protection from cold weather."
                crystal.consumption_effect = {
                    "type": "temperature",
                    "mode": "cold_protection",
                    "uses_remaining": 1,
                }
            elif temperature_mode == "cold":
                # Extends ration freshness
                preservation_days = dice.roll("2d4", "Ration preservation days").total
                crystal.name = "Resonant Crystal (Cold)"
                crystal.description = f"A cold crystal that can preserve rations for {preservation_days} additional days."
                crystal.consumption_effect = {
                    "type": "temperature",
                    "mode": "preserve_rations",
                    "preservation_days": preservation_days,
                    "used": False,
                }
            else:
                # Default to prompting for temperature mode
                return {
                    "success": True,
                    "pending_choice": {
                        "type": "temperature_mode_selection",
                        "prompt": "Choose temperature mode: Heat (cold protection) or Cold (preserve rations)",
                        "options": ["heat", "cold"],
                    },
                }

        # Add crystal to caster's inventory
        caster.add_item(crystal, current_day)

        return {
            "success": True,
            "items_created": [{
                "item_id": crystal.item_id,
                "name": crystal.name,
                "description": crystal.description,
                "energy_type": energy_type,
                "temperature_mode": temperature_mode,
            }],
            "narrative_context": {
                "crystal_created": True,
                "crystal_name": crystal.name,
                "energy_type": energy_type,
            },
        }

    # =========================================================================
    # PHASE 1 SPELL HANDLERS
    # =========================================================================

    def _handle_ventriloquism(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Ventriloquism spell.

        The caster's voice emanates from any point within 60' for 1 Turn.
        Pure narrative utility - no mechanical effects beyond duration tracking.

        Per Dolmenwood Campaign Book: "The caster's voice emanates from
        any point within range, as the caster desires."
        """
        return {
            "success": True,
            "effect_type": "utility",
            "duration_turns": 1,
            "range_feet": 60,
            "narrative_context": {
                "effect": "voice_projection",
                "description": "Voice can emanate from any point within 60 feet",
                "hints": [
                    "voice seems to come from elsewhere",
                    "sound carries unnaturally",
                    "words echo from an impossible location",
                ],
            },
        }

    def _handle_create_food(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Create Food spell (Divine, Level 5).

        Conjures nourishing food for 12 people and 12 mounts for one day.
        At caster level 10+, creates additional portions: +12 people/mounts per level above 9.

        Per Dolmenwood Campaign Book: "Conjures food sufficient for 12 people
        and 12 mounts for one day."
        """
        from src.data_models import Item

        # Calculate portions based on caster level
        base_people = 12
        base_mounts = 12
        bonus_per_level = max(0, caster.level - 9)
        total_people = base_people + (bonus_per_level * 12)
        total_mounts = base_mounts + (bonus_per_level * 12)

        # Create food items
        items_created = []
        current_day = 0
        if self._controller:
            current_day = self._controller.time_tracker.days

        # Create rations for people (magical items that last 1 day)
        people_rations = Item(
            item_id=f"created_rations_{uuid.uuid4().hex[:8]}",
            name=f"Conjured Rations ({total_people} portions)",
            weight=total_people,  # 1 lb per portion
            quantity=total_people,
            description=f"Magically conjured nourishing food (created day {current_day}). Lasts 1 day.",
            magical=True,
        )

        # Create fodder for mounts (magical items that last 1 day)
        mount_fodder = Item(
            item_id=f"created_fodder_{uuid.uuid4().hex[:8]}",
            name=f"Conjured Fodder ({total_mounts} portions)",
            weight=total_mounts * 5,  # 5 lbs per mount portion
            quantity=total_mounts,
            description=f"Magically conjured feed for mounts (created day {current_day}). Lasts 1 day.",
            magical=True,
        )

        # Add to caster's inventory
        caster.add_item(people_rations)
        caster.add_item(mount_fodder)

        items_created.append({
            "item_id": people_rations.item_id,
            "name": people_rations.name,
            "quantity": total_people,
            "type": "rations",
        })
        items_created.append({
            "item_id": mount_fodder.item_id,
            "name": mount_fodder.name,
            "quantity": total_mounts,
            "type": "fodder",
        })

        return {
            "success": True,
            "items_created": items_created,
            "people_fed": total_people,
            "mounts_fed": total_mounts,
            "caster_level": caster.level,
            "narrative_context": {
                "food_conjured": True,
                "people_portions": total_people,
                "mount_portions": total_mounts,
                "hints": [
                    "food appears wholesome if plain",
                    "nourishing but without memorable taste",
                    "sustenance manifests from divine grace",
                ],
            },
        }

    def _handle_create_water(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Create Water spell (Divine, Level 4).

        Creates approximately 50 gallons of pure water, enough for 12 people
        and 12 mounts for one day. Scales with caster level above 8.

        Per Dolmenwood Campaign Book: "Creates approximately 50 gallons of
        pure water, enough for 12 people and 12 mounts for one day."
        """
        from src.data_models import Item

        # Calculate portions based on caster level
        base_gallons = 50
        base_people = 12
        base_mounts = 12
        bonus_per_level = max(0, caster.level - 8)
        total_gallons = base_gallons + (bonus_per_level * 50)
        total_people = base_people + (bonus_per_level * 12)
        total_mounts = base_mounts + (bonus_per_level * 12)

        current_day = 0
        if self._controller:
            current_day = self._controller.time_tracker.days

        # Create water container (magical item that lasts 1 day)
        water_container = Item(
            item_id=f"created_water_{uuid.uuid4().hex[:8]}",
            name=f"Conjured Water ({total_gallons} gallons)",
            weight=total_gallons * 8,  # 8 lbs per gallon
            quantity=total_gallons,
            description=f"Magically conjured pure water (created day {current_day}). Evaporates after 1 day.",
            magical=True,
        )

        caster.add_item(water_container)

        return {
            "success": True,
            "items_created": [{
                "item_id": water_container.item_id,
                "name": water_container.name,
                "quantity": total_gallons,
                "type": "water",
            }],
            "gallons_created": total_gallons,
            "people_supplied": total_people,
            "mounts_supplied": total_mounts,
            "caster_level": caster.level,
            "narrative_context": {
                "water_conjured": True,
                "gallons": total_gallons,
                "hints": [
                    "water springs forth from nothing",
                    "pure and refreshing",
                    "divine providence made manifest",
                ],
            },
        }

    def _handle_air_sphere(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Air Sphere spell (Arcane, Level 5).

        When immersed in water, surrounds caster with a 10' radius sphere
        of breathable air that moves with them. Duration: 1 day.

        Per Dolmenwood Campaign Book: "When immersed in water, the caster
        is surrounded by a 10' radius sphere of breathable air."
        """
        # Create buff effect for underwater breathing
        buff_id = f"air_sphere_{uuid.uuid4().hex[:8]}"

        # Register as active spell effect if controller available
        if self._controller:
            effect = ActiveSpellEffect(
                effect_id=buff_id,
                spell_id="air_sphere",
                spell_name="Air Sphere",
                caster_id=caster.character_id,
                caster_level=caster.level if hasattr(caster, "level") else 1,
                target_id=caster.character_id,
                effect_type=SpellEffectType.HYBRID,
                duration_type=DurationType.DAYS,
                duration_remaining=1,
                created_at=datetime.now(),
                mechanical_effects={
                    "underwater_breathing": True,
                    "radius_feet": 10,
                    "moves_with_caster": True,
                    "protects_others_in_radius": True,
                },
            )
            self._active_effects.append(effect)

        return {
            "success": True,
            "effect_id": buff_id,
            "effect_type": "buff",
            "conditions_applied": ["underwater_breathing"],
            "duration_days": 1,
            "radius_feet": 10,
            "centered_on": caster.character_id,
            "narrative_context": {
                "sphere_created": True,
                "radius": 10,
                "duration": "1 day",
                "hints": [
                    "a shimmering bubble of air surrounds you",
                    "breathable atmosphere despite the depths",
                    "the sphere moves as you do",
                ],
            },
        }

    def _handle_detect_disguise(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Detect Disguise spell (Divine, Level 1).

        Reveals whether a target is disguised by mundane (non-magical) means.
        The voice of St Dougan says "be wary" (disguised) or "be sure" (not disguised).
        Target may Save Versus Spell to resist.

        Per Dolmenwood Campaign Book: "The saint's advice reveals whether
        a chosen person within range is disguised by mundane means."
        """
        from src.data_models import DiceRoller as DR
        from src.oracle.mythic_gme import MythicGME, Likelihood
        import random

        dice = dice_roller or DR()

        if not targets_affected:
            return {
                "success": False,
                "message": "No target specified for Detect Disguise",
                "narrative_context": {
                    "no_target": True,
                },
            }

        target_id = targets_affected[0]
        results = []

        # Get target character if available
        target_char = None
        if self._controller:
            target_char = self._controller.get_character(target_id)

        # Target gets a save vs spell
        save_succeeded = False
        save_roll = dice.roll_d20("Save vs Spell (Detect Disguise)")

        if target_char:
            save_target = target_char.get_saving_throw("spell")
            save_succeeded = save_roll.total >= save_target
        else:
            # Default save target for unknown targets
            save_succeeded = save_roll.total >= 15

        if save_succeeded:
            # Target resisted - spell reveals nothing
            results.append({
                "target_id": target_id,
                "save_succeeded": True,
                "revealed": False,
                "message": "The spell's power is resisted.",
            })
            return {
                "success": True,
                "targets_saved": [target_id],
                "results": results,
                "narrative_context": {
                    "save_succeeded": True,
                    "st_dougan_silent": True,
                    "hints": ["St Dougan's voice is silent", "the target's nature remains hidden"],
                },
            }

        # Save failed - query oracle for disguise status
        # In a real game, this would check world state or ask the DM
        # Here we use the Mythic GME oracle for a yes/no answer
        from src.oracle.dice_rng_adapter import DiceRngAdapter
        mythic = MythicGME(rng=DiceRngAdapter("SpellOracle"))
        oracle_result = mythic.fate_check(
            f"Is {target_id} disguised by mundane means?",
            Likelihood.FIFTY_FIFTY,
        )

        is_disguised = oracle_result.result.value in ["yes", "exceptional_yes"]
        saint_response = "be wary" if is_disguised else "be sure"

        results.append({
            "target_id": target_id,
            "save_succeeded": False,
            "revealed": True,
            "is_disguised": is_disguised,
            "saint_response": saint_response,
            "oracle_roll": oracle_result.roll,
        })

        return {
            "success": True,
            "results": results,
            "saint_response": saint_response,
            "is_disguised": is_disguised,
            "narrative_context": {
                "st_dougan_speaks": True,
                "response": saint_response,
                "is_disguised": is_disguised,
                "hints": [
                    f'St Dougan whispers: "{saint_response}"',
                    "aged wisdom reveals the truth",
                    "mundane deception cannot hide from divine sight" if is_disguised else "no false face here",
                ],
            },
        }

    # =========================================================================
    # PHASE 2: CONDITION-BASED SPELL HANDLERS
    # =========================================================================

    def _handle_deathly_blossom(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Deathly Blossom rune (Lesser Rune).

        Conjures a rose that causes those who smell it to fall into a
        death-like faint (unconscious) for 1d6 Turns. Target may Save vs Doom.

        Per Dolmenwood Campaign Book: "Conjures a rose of sublime beauty.
        Creatures who inhale its scent must Save Versus Doom or fall into
        a deep faint, appearing dead, for 1d6 Turns."
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()

        # First, create the rose item
        rose_id = f"deathly_rose_{uuid.uuid4().hex[:8]}"
        rose_created = {
            "item_id": rose_id,
            "name": "Rose of Sublime Beauty",
            "description": "A hauntingly beautiful rose conjured by fairy magic. Those who smell it risk falling into a death-like faint.",
            "magical": True,
            "duration_turns": 1,  # Rose lasts 1 turn or until used
            "single_use": True,
        }

        # If no targets, just create the rose
        if not targets_affected:
            return {
                "success": True,
                "rose_created": rose_created,
                "effect_type": "item_creation",
                "targets_affected": [],
                "narrative_context": {
                    "rose_conjured": True,
                    "hints": [
                        "a rose of unearthly beauty manifests",
                        "its petals shimmer with an otherworldly gleam",
                        "the scent promises sweet oblivion",
                    ],
                },
            }

        # Process each target that smells the rose
        results = []
        targets_saved = []
        targets_affected_list = []

        for target_id in targets_affected:
            # Get target's save bonus if available
            save_bonus = 0
            target_char = None
            if self._controller:
                target_char = self._controller.get_character(target_id)
                if target_char:
                    save_bonus = target_char.get_saving_throw("doom") if hasattr(target_char, "get_saving_throw") else 0

            # Roll save vs doom
            save_roll = dice.roll_d20()
            save_total = save_roll.total + save_bonus
            save_target = 15  # Default save target

            if save_total >= save_target:
                # Save succeeded - resisted the rose's effect
                targets_saved.append(target_id)
                results.append({
                    "target_id": target_id,
                    "save_succeeded": True,
                    "save_roll": save_roll.total,
                    "save_total": save_total,
                })
            else:
                # Save failed - fall into death-like faint
                duration_roll = dice.roll("1d6")
                duration_turns = duration_roll.total

                targets_affected_list.append(target_id)
                results.append({
                    "target_id": target_id,
                    "save_succeeded": False,
                    "save_roll": save_roll.total,
                    "save_total": save_total,
                    "condition_applied": "unconscious",
                    "duration_turns": duration_turns,
                    "appears_dead": True,  # Special variant of unconscious
                })

                # Apply the condition via controller if available
                if self._controller and target_char:
                    self._controller.apply_condition(
                        target_id, "unconscious", f"Deathly Blossom ({duration_turns} turns)"
                    )

                # Register as active spell effect
                effect = ActiveSpellEffect(
                    spell_id="deathly_blossom",
                    spell_name="Deathly Blossom",
                    caster_id=caster.character_id,
                    caster_level=caster.level if hasattr(caster, "level") else 1,
                    target_id=target_id,
                    effect_type=SpellEffectType.MECHANICAL,
                    duration_type=DurationType.TURNS,
                    duration_remaining=duration_turns,
                    duration_unit="turns",
                    created_at=datetime.now(),
                    mechanical_effects={
                        "condition": "unconscious",
                        "appears_dead": True,
                        "can_be_awakened": False,  # Only ends when duration expires
                    },
                )
                self._active_effects.append(effect)

        return {
            "success": True,
            "rose_created": rose_created,
            "effect_type": "condition",
            "conditions_applied": ["unconscious"],
            "results": results,
            "targets_saved": targets_saved,
            "targets_affected": targets_affected_list,
            "save_type": "doom",
            "narrative_context": {
                "rose_conjured": True,
                "victims_collapsed": len(targets_affected_list),
                "resisted": len(targets_saved),
                "hints": [
                    "the rose's scent wafts through the air",
                    "victims collapse as if struck dead",
                    "only the faintest rise and fall of breath reveals life",
                ],
            },
        }

    def _handle_en_croute(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle En Croute spell (Arcane, Level 2).

        Encases target in pastry crust, immobilizing them. Escape time based
        on Strength score. Save vs Spell negates.

        Per Dolmenwood Campaign Book: "Encases target in a thick shell of
        crispy pastry crust. The target is immobilised and can only break
        free based on their Strength."
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()

        if not targets_affected:
            return {
                "success": False,
                "message": "No target specified for En Croute",
                "narrative_context": {
                    "no_target": True,
                },
            }

        target_id = targets_affected[0]  # Single target spell

        # Get target's save bonus if available
        save_bonus = 0
        target_char = None
        strength = 10  # Default strength
        if self._controller:
            target_char = self._controller.get_character(target_id)
            if target_char:
                save_bonus = target_char.get_saving_throw("spell") if hasattr(target_char, "get_saving_throw") else 0
                if hasattr(target_char, "strength"):
                    strength = target_char.strength or 10

        # Roll save vs spell
        save_roll = dice.roll_d20()
        save_total = save_roll.total + save_bonus
        save_target = 15  # Default save target

        if save_total >= save_target:
            # Save succeeded - resisted encasement
            return {
                "success": True,
                "target_id": target_id,
                "save_succeeded": True,
                "save_roll": save_roll.total,
                "save_total": save_total,
                "narrative_context": {
                    "spell_resisted": True,
                    "hints": [
                        "the pastry barely forms before crumbling",
                        "target shrugs off the magical encasement",
                    ],
                },
            }

        # Save failed - calculate escape time based on Strength
        # Per Dolmenwood source: escape times in TURNS (except STR 18+ which is 1d4 Rounds)
        # STR 5 or less: 6 Turns, STR 6-8: 4 Turns, STR 9-12: 3 Turns,
        # STR 13-15: 2 Turns, STR 16-17: 1 Turn, STR 18+: 1d4 Rounds
        if strength >= 18:
            # STR 18+ escapes in 1d4 Rounds (much faster!)
            escape_time = dice.roll("1d4").total
            escape_unit = "rounds"
        elif strength >= 16:
            escape_time = 1
            escape_unit = "turns"
        elif strength >= 13:
            escape_time = 2
            escape_unit = "turns"
        elif strength >= 9:
            escape_time = 3
            escape_unit = "turns"
        elif strength >= 6:
            escape_time = 4
            escape_unit = "turns"
        else:
            escape_time = 6
            escape_unit = "turns"

        # Apply the condition via controller if available
        if self._controller and target_char:
            self._controller.apply_condition(
                target_id, "restrained", f"En Croute ({escape_time} {escape_unit})"
            )

        # Register as active spell effect
        duration_type = DurationType.ROUNDS if escape_unit == "rounds" else DurationType.TURNS
        effect = ActiveSpellEffect(
            spell_id="en_croute",
            spell_name="En Croute",
            caster_id=caster.character_id,
            caster_level=caster.level if hasattr(caster, "level") else 1,
            target_id=target_id,
            effect_type=SpellEffectType.MECHANICAL,
            duration_type=duration_type,
            duration_remaining=escape_time,
            duration_unit=escape_unit,
            created_at=datetime.now(),
            mechanical_effects={
                "condition": "restrained",
                "escape_time_remaining": escape_time,
                "escape_unit": escape_unit,
                "original_escape_time": escape_time,
                "target_strength": strength,
                "edible": True,  # Allies can eat to free!
            },
        )
        self._active_effects.append(effect)

        return {
            "success": True,
            "target_id": target_id,
            "save_succeeded": False,
            "save_roll": save_roll.total,
            "save_total": save_total,
            "conditions_applied": ["restrained"],
            "escape_time": escape_time,
            "escape_unit": escape_unit,
            "target_strength": strength,
            "narrative_context": {
                "encased": True,
                "escape_time": escape_time,
                "escape_unit": escape_unit,
                "edible": True,
                "hints": [
                    "golden pastry rapidly encases the target",
                    "a delicious aroma fills the air",
                    f"with STR {strength}, escape will take {escape_time} {escape_unit}",
                    "allies could help by... eating the crust",
                ],
            },
        }

    def _handle_awe(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Awe glamour (Fairy Glamour).

        Triggers a Morale Check for affected creatures; those who fail flee
        for 1d4 Rounds. HD budget: creatures whose Levels total up to caster's Level.

        Per Dolmenwood Campaign Book: "Triggers a Morale Check. Creatures who
        fail flee in terror for 1d4 Rounds."
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()

        if not targets_affected:
            return {
                "success": False,
                "message": "No targets specified for Awe",
                "narrative_context": {
                    "no_targets": True,
                },
            }

        # HD budget based on caster level
        hd_budget = caster.level if hasattr(caster, "level") else 1
        hd_spent = 0

        results = []
        targets_fled = []
        targets_resisted = []
        targets_immune = []

        for target_id in targets_affected:
            target_hd = 1  # Default HD
            morale = 7  # Default morale

            # Get target info if available
            if self._controller:
                target_char = self._controller.get_character(target_id)
                if target_char:
                    target_hd = target_char.level if hasattr(target_char, "level") else 1
                    if hasattr(target_char, "morale"):
                        morale = target_char.morale

            # Check HD budget
            if hd_spent + target_hd > hd_budget:
                targets_immune.append(target_id)
                results.append({
                    "target_id": target_id,
                    "immune": True,
                    "reason": "Exceeds HD budget",
                    "target_hd": target_hd,
                })
                continue

            hd_spent += target_hd

            # Roll morale check (2d6 vs morale score)
            morale_roll = dice.roll("2d6")
            morale_passed = morale_roll.total <= morale

            if morale_passed:
                # Morale passed - not affected
                targets_resisted.append(target_id)
                results.append({
                    "target_id": target_id,
                    "morale_passed": True,
                    "morale_roll": morale_roll.total,
                    "morale_target": morale,
                })
            else:
                # Morale failed - flee for 1d4 rounds
                flee_duration = dice.roll("1d4").total

                targets_fled.append(target_id)
                results.append({
                    "target_id": target_id,
                    "morale_passed": False,
                    "morale_roll": morale_roll.total,
                    "morale_target": morale,
                    "flee_rounds": flee_duration,
                    "condition_applied": "frightened",
                })

                # Apply frightened condition via controller
                if self._controller:
                    self._controller.apply_condition(
                        target_id, "frightened", f"Awe ({flee_duration} rounds)"
                    )

                # Register as active spell effect
                effect = ActiveSpellEffect(
                    spell_id="awe",
                    spell_name="Awe",
                    caster_id=caster.character_id,
                    caster_level=caster.level if hasattr(caster, "level") else 1,
                    target_id=target_id,
                    effect_type=SpellEffectType.MECHANICAL,
                    duration_type=DurationType.ROUNDS,
                    duration_remaining=flee_duration,
                    duration_unit="rounds",
                    created_at=datetime.now(),
                    mechanical_effects={
                        "condition": "frightened",
                        "fleeing": True,
                        "flee_direction": "away_from_caster",
                    },
                )
                self._active_effects.append(effect)

        return {
            "success": True,
            "hd_budget": hd_budget,
            "hd_spent": hd_spent,
            "targets_fled": targets_fled,
            "targets_resisted": targets_resisted,
            "targets_immune": targets_immune,
            "results": results,
            "conditions_applied": ["frightened"] if targets_fled else [],
            "narrative_context": {
                "fairy_majesty": True,
                "fled_count": len(targets_fled),
                "resisted_count": len(targets_resisted),
                "hints": [
                    "an overwhelming presence radiates from the caster",
                    "lesser creatures cower before fairy majesty",
                    "those who fail their nerve flee in terror",
                ],
            },
        }

    def _handle_animal_growth(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Animal Growth spell (Divine, Level 3).

        Doubles an animal's size, damage, and carrying capacity.
        Only affects normal or giant animals. Duration: 12 Turns.

        Per Dolmenwood Campaign Book: "Causes 1d4 normal animals or 1 giant
        animal to double in size. Animals' damage is doubled and they can
        carry twice the normal load."
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()

        if not targets_affected:
            # Determine how many animals can be affected
            # 1d4 normal animals OR 1 giant animal
            normal_count = dice.roll("1d4").total
            return {
                "success": True,
                "effect_type": "buff",
                "max_normal_animals": normal_count,
                "max_giant_animals": 1,
                "narrative_context": {
                    "spell_ready": True,
                    "hints": [
                        f"the spell can affect {normal_count} normal animals",
                        "or 1 giant animal",
                        "targets must be normal or giant animals",
                    ],
                },
            }

        # Process affected animals
        results = []
        affected_animals = []
        duration_turns = 12

        for target_id in targets_affected:
            # Apply doubling effect
            affected_animals.append(target_id)
            results.append({
                "target_id": target_id,
                "size_multiplier": 2,
                "damage_multiplier": 2,
                "carry_capacity_multiplier": 2,
                "duration_turns": duration_turns,
            })

            # Register as active spell effect
            effect = ActiveSpellEffect(
                spell_id="animal_growth",
                spell_name="Animal Growth",
                caster_id=caster.character_id,
                caster_level=caster.level if hasattr(caster, "level") else 1,
                target_id=target_id,
                effect_type=SpellEffectType.HYBRID,
                duration_type=DurationType.TURNS,
                duration_remaining=duration_turns,
                duration_unit="turns",
                created_at=datetime.now(),
                mechanical_effects={
                    "size_multiplier": 2,
                    "damage_multiplier": 2,
                    "carry_capacity_multiplier": 2,
                    "stat_modifiers": [
                        {"stat": "damage", "modifier_type": "multiplier", "value": 2},
                        {"stat": "carry_capacity", "modifier_type": "multiplier", "value": 2},
                    ],
                },
            )
            self._active_effects.append(effect)

        return {
            "success": True,
            "effect_type": "buff",
            "targets_affected": affected_animals,
            "results": results,
            "duration_turns": duration_turns,
            "stat_modifiers_applied": [
                {"modifier_type": "multiplier", "stat": "size", "value": 2},
                {"modifier_type": "multiplier", "stat": "damage", "value": 2},
                {"modifier_type": "multiplier", "stat": "carry_capacity", "value": 2},
            ],
            "narrative_context": {
                "growth_applied": True,
                "animals_affected": len(affected_animals),
                "hints": [
                    "the animals swell to twice their normal size",
                    "muscles bulge with divine-enhanced strength",
                    "their attacks now deal double damage",
                    "they can carry twice as much",
                ],
            },
        }

    # -------------------------------------------------------------------------
    # Phase 3: Dispel Magic Handler
    # -------------------------------------------------------------------------

    def _handle_dispel_magic(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Dispel Magic spell.

        Per Dolmenwood source:
        - All spell effects in a 20' cube within range are unravelled
        - Effects created by lower Level casters are automatically dispelled
        - 5% chance per Level difference that higher-Level magic resists
        - Magic items are unaffected
        - Curses from spells (e.g. Hex Weaving) are affected
        - Curses from magic items are unaffected
        """
        from src.data_models import DiceRoller as DR

        caster_level = caster.level if hasattr(caster, "level") else 1
        dice = dice_roller or DR()

        effects_dispelled: list[dict[str, Any]] = []
        effects_resisted: list[dict[str, Any]] = []
        effects_checked: list[str] = []

        # Gather all active effects on all targets in the area
        for target_id in targets_affected:
            target_effects = self.get_active_effects(target_id)
            for effect in target_effects:
                if effect.effect_id in effects_checked:
                    continue
                effects_checked.append(effect.effect_id)

                # Skip if this is a magic item effect (not a spell effect)
                if effect.mechanical_effects.get("from_magic_item", False):
                    continue

                # Calculate dispel chance based on level difference
                effect_caster_level = effect.caster_level or 1
                level_diff = effect_caster_level - caster_level

                if level_diff <= 0:
                    # Lower or equal level: auto-dispel
                    dispelled = True
                    resist_roll = None
                else:
                    # Higher level: 5% per level difference chance to resist
                    resist_chance = level_diff * 5
                    resist_roll = dice.roll("1d100", "Dispel Magic resistance")
                    dispelled = resist_roll.total > resist_chance

                effect_info = {
                    "effect_id": effect.effect_id,
                    "spell_name": effect.spell_name,
                    "spell_id": effect.spell_id,
                    "target_id": effect.target_id,
                    "effect_caster_level": effect_caster_level,
                    "caster_level": caster_level,
                    "level_difference": level_diff,
                }

                if dispelled:
                    # Dispel the effect
                    self.dismiss_effect(effect.effect_id)

                    # Remove associated conditions if controller available
                    if self._controller and effect.mechanical_effects.get("condition"):
                        condition = effect.mechanical_effects["condition"]
                        self._controller.remove_condition(effect.target_id, condition)

                    effect_info["dispelled"] = True
                    effects_dispelled.append(effect_info)
                else:
                    effect_info["dispelled"] = False
                    effect_info["resist_roll"] = resist_roll.total if resist_roll else None
                    effect_info["resist_chance"] = level_diff * 5
                    effects_resisted.append(effect_info)

        return {
            "success": True,
            "caster_level": caster_level,
            "area_size": "20' cube",
            "effects_dispelled": effects_dispelled,
            "effects_resisted": effects_resisted,
            "total_dispelled": len(effects_dispelled),
            "total_resisted": len(effects_resisted),
            "targets_checked": targets_affected,
            "narrative_context": {
                "dispel_cast": True,
                "magic_unravelled": len(effects_dispelled) > 0,
                "some_resisted": len(effects_resisted) > 0,
                "hints": [
                    "coils of coloured energy disintegrate",
                    "spell weaves unravel and fade",
                    "magical effects dissolve into sparkling motes",
                ]
                + (
                    ["some powerful magics resist the dispelling"]
                    if effects_resisted
                    else []
                ),
            },
        }

    # -------------------------------------------------------------------------
    # Phase 4: Movement Spell Handlers
    # -------------------------------------------------------------------------

    def _handle_levitate(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Levitate spell.

        Per Dolmenwood source:
        - Caster may move up and down through the air at will
        - Vertical movement: Up to 20' per Round
        - Horizontal movement: Only by pushing against solid objects
        - Duration: 6 Turns + 1 per Level
        - Can carry normal amount of weight
        """
        from src.data_models import FlightState

        caster_level = caster.level if hasattr(caster, "level") else 1
        duration_turns = 6 + caster_level

        # Grant levitation (hovering state, not full flight)
        if hasattr(caster, "grant_flight"):
            caster.grant_flight(
                speed=20,  # 20' per round vertical only
                source="levitate",
                flight_state=FlightState.HOVERING,
            )

        # Register as active spell effect
        effect_id = f"levitate_{uuid.uuid4().hex[:8]}"
        effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="levitate",
            spell_name="Levitate",
            caster_id=caster.character_id,
            caster_level=caster_level,
            target_id=caster.character_id,
            effect_type=SpellEffectType.HYBRID,
            duration_type=DurationType.TURNS,
            duration_remaining=duration_turns,
            duration_unit="turns",
            created_at=datetime.now(),
            mechanical_effects={
                "movement_mode": "levitating",
                "vertical_speed": 20,
                "horizontal_requires_solid": True,
                "grants_flight_state": "hovering",
            },
        )
        self._active_effects.append(effect)

        return {
            "success": True,
            "effect_id": effect_id,
            "caster_level": caster_level,
            "duration_turns": duration_turns,
            "vertical_speed": 20,
            "movement_mode": "levitating",
            "narrative_context": {
                "levitation_granted": True,
                "vertical_only": True,
                "hints": [
                    "the caster rises untethered from the ground",
                    "gravity's pull weakens as the spell takes hold",
                    "vertical movement at will, horizontal by pushing off solids",
                ],
            },
        }

    def _handle_fly(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Fly spell.

        Per Dolmenwood source:
        - Commands the wind to wrap subject in swirling zephyrs
        - Free movement in any direction, including hovering
        - Speed 120
        - Duration: 1d6 Turns + 1 per Level
        """
        from src.data_models import DiceRoller as DR, FlightState

        dice = dice_roller or DR()
        caster_level = caster.level if hasattr(caster, "level") else 1

        # Roll duration: 1d6 + caster level
        duration_roll = dice.roll("1d6", "Fly duration")
        duration_turns = duration_roll.total + caster_level

        # Determine target (caster or touched creature)
        target_id = caster.character_id
        if targets_affected and len(targets_affected) > 0:
            target_id = targets_affected[0]

        # Get target character for granting flight
        target_char = None
        if self._controller:
            target_char = self._controller.get_character(target_id)
        if not target_char:
            target_char = caster

        # Grant full flight
        if hasattr(target_char, "grant_flight"):
            target_char.grant_flight(
                speed=120,
                source="fly",
                flight_state=FlightState.FLYING,
            )

        # Register as active spell effect
        effect_id = f"fly_{uuid.uuid4().hex[:8]}"
        effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="fly",
            spell_name="Fly",
            caster_id=caster.character_id,
            caster_level=caster_level,
            target_id=target_id,
            effect_type=SpellEffectType.HYBRID,
            duration_type=DurationType.TURNS,
            duration_remaining=duration_turns,
            duration_unit="turns",
            created_at=datetime.now(),
            mechanical_effects={
                "movement_mode": "flying",
                "flight_speed": 120,
                "grants_flight_state": "flying",
                "free_movement": True,
            },
        )
        self._active_effects.append(effect)

        return {
            "success": True,
            "effect_id": effect_id,
            "target_id": target_id,
            "caster_level": caster_level,
            "duration_turns": duration_turns,
            "duration_roll": duration_roll.total,
            "flight_speed": 120,
            "movement_mode": "flying",
            "narrative_context": {
                "flight_granted": True,
                "zephyrs_summoned": True,
                "hints": [
                    "swirling zephyrs wrap around and lift the subject",
                    "the winds obey, carrying the subject through the air",
                    "free movement in any direction at Speed 120",
                ],
            },
        }

    def _handle_telekinesis(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Telekinesis spell.

        Per Dolmenwood source:
        - Move object or creature by thought
        - Weight: 200 coins per Level (200 coins = ~10 lbs)
        - Movement: 20' per Round in any direction
        - Duration: Concentration (up to 6 Rounds)
        - Unwilling targets: Save Versus Hold to resist
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = caster.level if hasattr(caster, "level") else 1

        # Calculate weight limit
        weight_limit_coins = 200 * caster_level
        weight_limit_lbs = weight_limit_coins / 20  # ~10 lbs per 200 coins

        # Process targets (creatures get saves)
        targets_held = []
        targets_resisted = []

        for target_id in targets_affected:
            target_char = None
            if self._controller:
                target_char = self._controller.get_character(target_id)

            if target_char:
                # Creature target - needs Save Versus Hold
                save_modifier = 0
                if hasattr(target_char, "get_saving_throw"):
                    save_modifier = target_char.get_saving_throw("hold") or 0

                save_roll = dice.roll_d20()
                save_total = save_roll.total + save_modifier
                save_target = 15  # Standard save target

                if save_total >= save_target:
                    # Resisted
                    targets_resisted.append({
                        "target_id": target_id,
                        "save_roll": save_roll.total,
                        "save_total": save_total,
                    })
                else:
                    # Held
                    targets_held.append({
                        "target_id": target_id,
                        "save_roll": save_roll.total,
                        "save_total": save_total,
                    })
            else:
                # Object target - no save needed
                targets_held.append({
                    "target_id": target_id,
                    "is_object": True,
                })

        # Register as concentration effect
        effect_id = f"telekinesis_{uuid.uuid4().hex[:8]}"
        effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="telekinesis",
            spell_name="Telekinesis",
            caster_id=caster.character_id,
            caster_level=caster_level,
            target_id=caster.character_id,  # Effect is on caster (concentration)
            effect_type=SpellEffectType.HYBRID,
            duration_type=DurationType.ROUNDS,
            duration_remaining=6,  # Up to 6 rounds
            duration_unit="rounds",
            requires_concentration=True,
            created_at=datetime.now(),
            mechanical_effects={
                "telekinetic_control": True,
                "weight_limit_coins": weight_limit_coins,
                "movement_speed": 20,
                "held_targets": [t["target_id"] for t in targets_held],
            },
        )
        self._active_effects.append(effect)

        return {
            "success": True,
            "effect_id": effect_id,
            "caster_level": caster_level,
            "weight_limit_coins": weight_limit_coins,
            "weight_limit_lbs": weight_limit_lbs,
            "movement_speed": 20,
            "duration_rounds": 6,
            "requires_concentration": True,
            "targets_held": targets_held,
            "targets_resisted": targets_resisted,
            "save_type": "hold",
            "narrative_context": {
                "telekinesis_active": True,
                "concentration_required": True,
                "hints": [
                    "the caster's will extends outward, gripping the target",
                    f"up to {weight_limit_coins} coins of weight can be moved",
                    "movement at 20' per round in any direction",
                    "concentration breaks if caster is harmed or acts",
                ],
            },
        }

    # -------------------------------------------------------------------------
    # PHASE 5 SPELL HANDLERS - Utility and Transformation
    # -------------------------------------------------------------------------

    def _handle_passwall(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Passwall spell - creates temporary passage through stone/rock.

        Effects:
        - Creates a 5' diameter, 10' deep hole in solid rock or stone
        - Duration: 3 Turns
        - Passage is temporary and closes when spell ends

        Args:
            caster: The character casting the spell
            targets_affected: Not used (location-based effect)
            dice_roller: Optional dice roller

        Returns:
            Dictionary with passage effect details
        """
        import uuid

        caster_level = getattr(caster, "level", 1)
        effect_id = f"passwall_{uuid.uuid4().hex[:8]}"

        # Passwall has fixed dimensions per spell description
        diameter = 5  # 5' diameter
        depth = 10  # Up to 10' deep
        duration_turns = 3  # 3 Turns duration

        # Create the temporary passage effect
        effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="passwall",
            spell_name="Passwall",
            caster_id=getattr(caster, "character_id", "unknown"),
            caster_level=caster_level,
            target_id="area:passwall",  # Location effect
            target_type="area",
            effect_type=SpellEffectType.HYBRID,
            duration_type=DurationType.TURNS,
            duration_remaining=duration_turns,
            duration_unit="turns",
            requires_concentration=False,
            created_at=datetime.now(),
            mechanical_effects={
                "passage_type": "temporary_hole",
                "diameter_feet": diameter,
                "depth_feet": depth,
                "material_affected": ["rock", "stone"],
                "blocks_passage_when_ends": True,
            },
        )
        self._active_effects.append(effect)

        return {
            "success": True,
            "effect_id": effect_id,
            "caster_level": caster_level,
            "passage_created": True,
            "diameter_feet": diameter,
            "depth_feet": depth,
            "duration_turns": duration_turns,
            "material_affected": ["rock", "stone"],
            "blocks_when_ends": True,
            "narrative_context": {
                "passage_open": True,
                "hints": [
                    "a 5' diameter hole opens in solid stone",
                    "the passage extends up to 10' deep",
                    "the stone seems to shimmer at the edges",
                    "the passage will close after 3 Turns",
                ],
            },
        }

    def _handle_fools_gold(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Fool's Gold glamour - makes copper coins appear as gold.

        Effects:
        - Up to 20 coins per caster level per day can be glamoured
        - Duration: 1d6 minutes
        - Each viewer may Save Versus Spell to see through the illusion
        - Fairy glamour (not a leveled spell)

        Args:
            caster: The character casting the glamour
            targets_affected: List of viewer IDs who observe the coins
            dice_roller: Optional dice roller

        Returns:
            Dictionary with glamour effect details
        """
        import uuid

        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"fools_gold_{uuid.uuid4().hex[:8]}"

        # Maximum coins that can be glamoured
        max_coins_per_day = 20 * caster_level

        # Roll duration: 1d6 minutes
        duration_minutes = dice.roll("1d6")

        # Track which viewers see through the illusion
        viewers_deceived: list[str] = []
        viewers_saw_through: list[str] = []

        for viewer_id in targets_affected:
            # Each viewer gets a Save Versus Spell
            save_roll = dice.roll("1d20")
            # Assume DC 14 for spell saves as default
            if save_roll >= 14:
                viewers_saw_through.append(viewer_id)
            else:
                viewers_deceived.append(viewer_id)

        # Create the glamour effect
        # Using SPECIAL duration type since Fool's Gold uses minutes (not a standard duration type)
        effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="fools_gold",
            spell_name="Fool's Gold",
            caster_id=getattr(caster, "character_id", "unknown"),
            caster_level=caster_level,
            target_id="object:coins",  # Item effect
            target_type="object",
            effect_type=SpellEffectType.HYBRID,
            duration_type=DurationType.SPECIAL,
            duration_remaining=duration_minutes,
            duration_unit="minutes",
            requires_concentration=False,
            created_at=datetime.now(),
            mechanical_effects={
                "glamour_type": "visual_illusion",
                "appears_as": "gold_coins",
                "actual_material": "copper_coins",
                "max_coins": max_coins_per_day,
                "viewers_deceived": viewers_deceived,
                "viewers_saw_through": viewers_saw_through,
                "save_type": "spell",
                "duration_minutes": duration_minutes,
            },
        )
        self._active_effects.append(effect)

        return {
            "success": True,
            "effect_id": effect_id,
            "caster_level": caster_level,
            "glamour_active": True,
            "max_coins_per_day": max_coins_per_day,
            "duration_minutes": duration_minutes,
            "viewers_deceived": viewers_deceived,
            "viewers_saw_through": viewers_saw_through,
            "save_type": "spell",
            "narrative_context": {
                "illusion_active": True,
                "hints": [
                    "the copper coins gleam with an unmistakable golden luster",
                    "fairy glamour shimmers over the coins",
                    f"the glamour will last for {duration_minutes} minutes",
                    f"up to {max_coins_per_day} coins can be glamoured today",
                ],
            },
        }

    def _handle_ginger_snap(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Ginger Snap spell - transforms limbs into gingerbread.

        Effects:
        - Target transforms partially into gingerbread
        - 1 limb per 3 caster levels affected
        - At level 14+, head can also be transformed
        - Transformed parts are brittle and can be smashed
        - Save Versus Hold to resist
        - Duration: 1d6 Rounds
        - Smashed parts are permanently destroyed

        Args:
            caster: The character casting the spell
            targets_affected: List of target IDs
            dice_roller: Optional dice roller

        Returns:
            Dictionary with transformation effect details
        """
        import uuid

        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"ginger_snap_{uuid.uuid4().hex[:8]}"

        # Calculate limbs affected: 1 per 3 levels
        limbs_affected = caster_level // 3
        if limbs_affected < 1:
            limbs_affected = 1

        # At level 14+, head can also be transformed
        head_vulnerable = caster_level >= 14

        # Roll duration: 1d6 Rounds
        duration_rounds = dice.roll("1d6")

        # Determine which body parts are affected
        body_parts = ["left_arm", "right_arm", "left_leg", "right_leg"]
        affected_parts: list[str] = []

        # Select limbs to transform
        for i in range(min(limbs_affected, len(body_parts))):
            affected_parts.append(body_parts[i])

        if head_vulnerable:
            affected_parts.append("head")

        # Process saving throws for each target
        targets_transformed: list[str] = []
        targets_resisted: list[str] = []
        target_details: dict[str, dict[str, Any]] = {}

        for target_id in targets_affected:
            # Save Versus Hold to resist
            save_roll = dice.roll("1d20")
            # Assume DC 14 for hold saves as default
            if save_roll >= 14:
                targets_resisted.append(target_id)
            else:
                targets_transformed.append(target_id)
                target_details[target_id] = {
                    "parts_transformed": affected_parts.copy(),
                    "parts_smashed": [],
                    "head_vulnerable": head_vulnerable,
                }

        # Create the transformation effect for each transformed target
        for target_id in targets_transformed:
            effect = ActiveSpellEffect(
                effect_id=f"{effect_id}_{target_id}",
                spell_id="ginger_snap",
                spell_name="Ginger Snap",
                caster_id=getattr(caster, "character_id", "unknown"),
                caster_level=caster_level,
                target_id=target_id,
                target_type="creature",
                effect_type=SpellEffectType.MECHANICAL,
                duration_type=DurationType.ROUNDS,
                duration_remaining=duration_rounds,
                duration_unit="rounds",
                requires_concentration=False,
                created_at=datetime.now(),
                mechanical_effects={
                    "transformation_type": "gingerbread",
                    "limbs_affected_count": limbs_affected,
                    "head_vulnerable": head_vulnerable,
                    "parts_transformed": target_details.get(target_id, {}).get(
                        "parts_transformed", []
                    ),
                    "parts_smashed": [],
                    "smashable": True,
                    "permanent_loss_on_smash": True,
                    "save_type": "hold",
                },
            )
            self._active_effects.append(effect)

        return {
            "success": True,
            "effect_id": effect_id,
            "caster_level": caster_level,
            "transformation_active": True,
            "limbs_affected_count": limbs_affected,
            "head_vulnerable": head_vulnerable,
            "affected_parts": affected_parts,
            "duration_rounds": duration_rounds,
            "targets_transformed": targets_transformed,
            "targets_resisted": targets_resisted,
            "target_details": target_details,
            "save_type": "hold",
            "smashable": True,
            "permanent_loss_on_smash": True,
            "narrative_context": {
                "transformation_active": True,
                "hints": [
                    f"{limbs_affected} limb(s) transform into crunchy gingerbread",
                    "transformed parts are brittle and can be snapped",
                    "smashed parts are permanently destroyed when spell ends",
                    f"the transformation lasts for {duration_rounds} rounds",
                ]
                + (
                    ["at this power level, even the head is vulnerable!"]
                    if head_vulnerable
                    else []
                ),
            },
        }

    # -------------------------------------------------------------------------
    # PHASE 6 SPELL HANDLERS - Door/Lock and Trap Spells
    # -------------------------------------------------------------------------

    def _handle_through_the_keyhole(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Through the Keyhole glamour - step through doors with keyholes.

        Effects:
        - Instant teleport through any door with keyhole/aperture
        - Magically sealed doors require Save Versus Spell
        - Once per day per door usage limit

        Args:
            caster: The character using the glamour
            targets_affected: List containing door ID (if applicable)
            dice_roller: Optional dice roller

        Returns:
            Dictionary with glamour effect details
        """
        import uuid

        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"through_keyhole_{uuid.uuid4().hex[:8]}"

        # Check if door is magically sealed (first target could be door info)
        door_id = targets_affected[0] if targets_affected else "unknown_door"
        is_magically_sealed = False
        bypass_succeeded = True

        # If door info indicates magical sealing, require save
        if targets_affected and len(targets_affected) > 1:
            # Second element could indicate magical sealing
            is_magically_sealed = targets_affected[1] == "magically_sealed"

        if is_magically_sealed:
            # Save Versus Spell to bypass magical sealing
            save_roll = dice.roll("1d20")
            # Assume DC 14 for spell saves
            bypass_succeeded = save_roll >= 14

        return {
            "success": bypass_succeeded,
            "effect_id": effect_id,
            "caster_level": caster_level,
            "door_id": door_id,
            "is_magically_sealed": is_magically_sealed,
            "bypass_succeeded": bypass_succeeded,
            "teleported": bypass_succeeded,
            "usage_limit": "once_per_day_per_door",
            "narrative_context": {
                "glamour_used": True,
                "hints": (
                    [
                        "the caster steps through the keyhole as if it were a doorway",
                        "for a moment, they seem to shrink and flow through the aperture",
                        "they reappear on the other side in the blink of an eye",
                    ]
                    if bypass_succeeded
                    else [
                        "magical sealing prevents passage through the keyhole",
                        "the glamour fails to pierce the warding magic",
                    ]
                ),
            },
        }

    def _handle_lock_singer(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Lock Singer knack - Mossling ability to charm locks with song.

        Effects vary by level:
        - Level 1: 2-in-6 per Turn to open simple locks
        - Level 3: Locate key (whispered cant)
        - Level 5: Snap shut locks within 30'
        - Level 7: Open any lock 2-in-6, magical locks with 1-in-6 backfire risk

        Args:
            caster: The Mossling character using the knack
            targets_affected: List containing lock/door ID and ability to use
            dice_roller: Optional dice roller

        Returns:
            Dictionary with knack effect details
        """
        import uuid

        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"lock_singer_{uuid.uuid4().hex[:8]}"

        # Determine which ability is being used based on level
        lock_id = targets_affected[0] if targets_affected else "unknown_lock"
        ability_used = targets_affected[1] if len(targets_affected) > 1 else "open_simple"
        is_magical_lock = targets_affected[2] == "magical" if len(targets_affected) > 2 else False

        result_data: dict[str, Any] = {
            "success": False,
            "effect_id": effect_id,
            "caster_level": caster_level,
            "lock_id": lock_id,
            "ability_used": ability_used,
            "is_magical_lock": is_magical_lock,
            "backfire": False,
            "mouth_sealed_days": 0,
        }

        if ability_used == "open_simple" and caster_level >= 1:
            # 2-in-6 chance per Turn to open simple lock
            roll = dice.roll("1d6")
            result_data["success"] = roll <= 2
            result_data["chance"] = "2-in-6"
            result_data["roll"] = roll
            result_data["time_required"] = "1 Turn per attempt"

        elif ability_used == "locate_key" and caster_level >= 3:
            # Always succeeds - whispered cant reveals key location
            result_data["success"] = True
            result_data["key_location_revealed"] = True

        elif ability_used == "snap_shut" and caster_level >= 5:
            # Simple locks within 30' snap shut after 1 Round of song
            result_data["success"] = True
            result_data["range_feet"] = 30
            result_data["time_required"] = "1 Round of singing"

        elif ability_used == "open_any" and caster_level >= 7:
            # 2-in-6 for any lock, magical locks have backfire risk
            roll = dice.roll("1d6")
            result_data["success"] = roll <= 2
            result_data["chance"] = "2-in-6"
            result_data["roll"] = roll

            if is_magical_lock and result_data["success"]:
                # 1-in-6 chance of backfire on magical locks
                backfire_roll = dice.roll("1d6")
                if backfire_roll == 1:
                    result_data["backfire"] = True
                    result_data["success"] = True  # Still opens, but with consequence
                    # 1d4 days of sealed mouth
                    seal_duration = dice.roll("1d4")
                    result_data["mouth_sealed_days"] = seal_duration

        else:
            # Ability not available at this level
            result_data["success"] = False
            result_data["reason"] = f"ability '{ability_used}' requires higher level"

        # Build narrative hints based on result
        hints = []
        if result_data["success"]:
            if ability_used == "locate_key":
                hints.append("a quiet whining from the lock reveals the key's location")
            elif ability_used == "snap_shut":
                hints.append("locks within earshot snap shut at the mossling's song")
            else:
                hints.append("the lock yields to the mossling's melodious charm")
        else:
            hints.append("the lock remains stubbornly closed despite the song")

        if result_data.get("backfire"):
            hints.append(
                f"the magic backfires! the mossling's mouth is sealed for "
                f"{result_data['mouth_sealed_days']} days"
            )

        result_data["narrative_context"] = {
            "knack_used": True,
            "hints": hints,
        }

        return result_data

    def _handle_serpent_glyph(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Serpent Glyph spell - creates a warding trap glyph.

        Effects:
        - Creates permanent glyph on text or surface (until triggered)
        - When triggered: serpent attacks nearest creature
        - Attack roll = caster's level
        - On hit: victim frozen in temporal stasis for 1d4 days
        - Material component: 100gp powdered amber

        Args:
            caster: The character casting the spell
            targets_affected: List containing surface/text ID and trigger target
            dice_roller: Optional dice roller

        Returns:
            Dictionary with glyph effect details
        """
        import uuid

        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"serpent_glyph_{uuid.uuid4().hex[:8]}"

        # Determine glyph placement type
        surface_id = targets_affected[0] if targets_affected else "unknown_surface"
        glyph_type = targets_affected[1] if len(targets_affected) > 1 else "surface"
        is_triggered = targets_affected[2] == "triggered" if len(targets_affected) > 2 else False
        trigger_target = targets_affected[3] if len(targets_affected) > 3 else None

        result_data: dict[str, Any] = {
            "success": True,
            "effect_id": effect_id,
            "caster_level": caster_level,
            "surface_id": surface_id,
            "glyph_type": glyph_type,  # "text" or "surface"
            "is_visible": glyph_type == "surface",  # Only surface glyphs glow
            "material_component": "powdered amber (100gp)",
            "duration": "permanent_until_triggered",
        }

        if is_triggered and trigger_target:
            # Glyph has been triggered - serpent attacks
            attack_roll = dice.roll("1d20")
            attack_total = attack_roll + caster_level
            # Assume AC 10 as baseline for hitting
            target_ac = 10  # Could be passed in targets_affected
            attack_hits = attack_total >= target_ac

            result_data["triggered"] = True
            result_data["attack_roll"] = attack_roll
            result_data["attack_bonus"] = caster_level
            result_data["attack_total"] = attack_total
            result_data["attack_hits"] = attack_hits
            result_data["trigger_target"] = trigger_target

            if attack_hits:
                # Victim frozen in temporal stasis
                stasis_days = dice.roll("1d4")
                result_data["stasis_applied"] = True
                result_data["stasis_duration_days"] = stasis_days

                # Create temporal stasis effect
                stasis_effect = ActiveSpellEffect(
                    effect_id=f"{effect_id}_stasis",
                    spell_id="serpent_glyph",
                    spell_name="Serpent Glyph (Temporal Stasis)",
                    caster_id=getattr(caster, "character_id", "unknown"),
                    caster_level=caster_level,
                    target_id=trigger_target,
                    target_type="creature",
                    effect_type=SpellEffectType.MECHANICAL,
                    duration_type=DurationType.DAYS,
                    duration_remaining=stasis_days,
                    duration_unit="days",
                    requires_concentration=False,
                    created_at=datetime.now(),
                    mechanical_effects={
                        "condition": "temporal_stasis",
                        "cannot_move": True,
                        "cannot_perceive": True,
                        "cannot_think": True,
                        "cannot_act": True,
                        "invulnerable": True,
                        "bubble_immovable": True,
                        "dispellable": True,
                        "releasable_by_caster": True,
                    },
                )
                self._active_effects.append(stasis_effect)

                result_data["narrative_context"] = {
                    "glyph_triggered": True,
                    "hints": [
                        "a glowing serpent leaps from the glyph!",
                        f"the serpent strikes true (attack roll {attack_total})",
                        f"the victim is frozen in a glittering amber bubble",
                        f"temporal stasis will last {stasis_days} days",
                        "the victim cannot move, perceive, think, or act",
                        "the bubble cannot be moved or penetrated",
                    ],
                }
            else:
                result_data["stasis_applied"] = False
                result_data["narrative_context"] = {
                    "glyph_triggered": True,
                    "hints": [
                        "a glowing serpent leaps from the glyph!",
                        f"the serpent strikes but misses (attack roll {attack_total})",
                        "the serpent dissipates with a flash, a bang, and a puff of smoke",
                    ],
                }
        else:
            # Glyph is being placed, not triggered
            # Create the glyph trap effect
            glyph_effect = ActiveSpellEffect(
                effect_id=effect_id,
                spell_id="serpent_glyph",
                spell_name="Serpent Glyph",
                caster_id=getattr(caster, "character_id", "unknown"),
                caster_level=caster_level,
                target_id=f"glyph:{surface_id}",
                target_type="object",
                effect_type=SpellEffectType.HYBRID,
                duration_type=DurationType.PERMANENT,
                duration_remaining=None,
                duration_unit="permanent",
                requires_concentration=False,
                created_at=datetime.now(),
                mechanical_effects={
                    "trap_type": "serpent_glyph",
                    "glyph_type": glyph_type,
                    "attack_bonus": caster_level,
                    "trigger_action": "read" if glyph_type == "text" else "touch",
                    "is_visible": glyph_type == "surface",
                    "detect_magic_reveals": glyph_type == "text",
                },
            )
            self._active_effects.append(glyph_effect)

            result_data["narrative_context"] = {
                "glyph_placed": True,
                "hints": [
                    f"the serpent glyph is traced upon the {glyph_type}",
                    "powdered amber is sprinkled over the arcane symbol",
                ]
                + (
                    ["the glyph glows pale yellow, clearly visible"]
                    if glyph_type == "surface"
                    else ["the glyph mingles into the script, undetectable except by magic"]
                ),
            }

        return result_data

    # =========================================================================
    # PHASE 7 HANDLERS: Teleportation, Condition, and Healing
    # =========================================================================

    def _handle_dimension_door(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Dimension Door spell.

        Creates paired door-shaped rifts in space for instant teleportation.

        Effects:
        - Opens entrance door within 10' of caster
        - Opens exit door at destination up to 360' away
        - Single creature may step through (or be forced through)
        - Unwilling targets get Save Versus Hold
        - Destination can be known location or coordinate offsets
        - No effect if destination is solid object
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"dimension_door_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        # Spell parameters
        max_range = 360  # feet
        entrance_range = 10  # feet from caster

        # Get targeting information from context
        target_id = targets_affected[0] if targets_affected else None
        is_unwilling = False
        destination_type = "known_location"  # or "offset_coordinates"
        destination_offset = {"north": 0, "east": 0, "up": 0}  # for offset mode
        destination_blocked = False

        # Check for context-provided targeting info
        if hasattr(self, "_current_context") and self._current_context:
            ctx = self._current_context
            is_unwilling = ctx.get("is_unwilling", False)
            destination_type = ctx.get("destination_type", "known_location")
            destination_offset = ctx.get("destination_offset", {"north": 0, "east": 0, "up": 0})
            destination_blocked = ctx.get("destination_blocked", False)

        result_data: dict[str, Any] = {
            "spell_id": "dimension_door",
            "spell_name": "Dimension Door",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "target_id": target_id,
            "max_range": max_range,
            "entrance_range": entrance_range,
            "destination_type": destination_type,
            "success": False,
            "teleported": False,
        }

        # Check if destination is blocked
        if destination_blocked:
            result_data["destination_blocked"] = True
            result_data["narrative_context"] = {
                "spell_fizzled": True,
                "hints": [
                    "the caster attempts to open a dimension door",
                    "but the destination is occupied by a solid object",
                    "the spell has no effect",
                ],
            }
            return result_data

        result_data["success"] = True

        # Handle unwilling target - needs Save Versus Hold
        if is_unwilling and target_id:
            # Roll save for unwilling target
            save_roll = dice.roll("1d20")
            save_target = 14  # Default save target

            # Get actual save target if target has character data
            if hasattr(self, "_controller") and self._controller:
                target_char = self._controller.get_character(target_id)
                if target_char and hasattr(target_char, "saving_throws"):
                    save_target = getattr(target_char.saving_throws, "hold", 14)

            save_success = save_roll >= save_target

            result_data["is_unwilling"] = True
            result_data["save_roll"] = save_roll
            result_data["save_target"] = save_target
            result_data["save_success"] = save_success

            if save_success:
                result_data["teleported"] = False
                result_data["narrative_context"] = {
                    "portal_opened": True,
                    "target_resisted": True,
                    "hints": [
                        "a pair of glowing, door-shaped rifts tear open in the fabric of space",
                        f"the nearby portal manifests beside {target_id}",
                        f"but they resist the dimensional pull (save roll {save_roll})",
                        "the portals shimmer and close without effect",
                    ],
                }
                return result_data
            else:
                result_data["teleported"] = True
                result_data["narrative_context"] = {
                    "portal_opened": True,
                    "target_transported": True,
                    "hints": [
                        "a pair of glowing, door-shaped rifts tear open in the fabric of space",
                        f"the nearby portal manifests beside {target_id}",
                        f"they are sucked through the dimensional door (failed save {save_roll})",
                        "the portals close behind them with a soft 'pop'",
                    ],
                }
        else:
            # Willing target or self-transport
            result_data["is_unwilling"] = False
            result_data["teleported"] = True

            if destination_type == "offset_coordinates":
                offset_desc = []
                if destination_offset.get("north", 0) != 0:
                    offset_desc.append(f"{abs(destination_offset['north'])}' {'north' if destination_offset['north'] > 0 else 'south'}")
                if destination_offset.get("east", 0) != 0:
                    offset_desc.append(f"{abs(destination_offset['east'])}' {'east' if destination_offset['east'] > 0 else 'west'}")
                if destination_offset.get("up", 0) != 0:
                    offset_desc.append(f"{abs(destination_offset['up'])}' {'up' if destination_offset['up'] > 0 else 'down'}")
                offset_str = ", ".join(offset_desc) if offset_desc else "nearby"
                result_data["destination_offset"] = destination_offset

                result_data["narrative_context"] = {
                    "portal_opened": True,
                    "hints": [
                        "a pair of glowing, door-shaped rifts tear open in the fabric of space",
                        f"the caster visualizes coordinates: {offset_str}",
                        "a single step through the nearby door leads to instant arrival",
                        "the portals shimmer and close",
                    ],
                }
            else:
                result_data["narrative_context"] = {
                    "portal_opened": True,
                    "hints": [
                        "a pair of glowing, door-shaped rifts tear open in the fabric of space",
                        "the caster visualizes a known destination",
                        "a single step through the nearby door leads to instant arrival",
                        "the portals shimmer and close",
                    ],
                }

        # Create the teleportation effect (duration 1 Round)
        teleport_effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="dimension_door",
            spell_name="Dimension Door",
            caster_id=getattr(caster, "character_id", "unknown"),
            caster_level=caster_level,
            target_id=target_id or getattr(caster, "character_id", "unknown"),
            target_type="creature",
            effect_type=SpellEffectType.MECHANICAL,
            duration_type=DurationType.ROUNDS,
            duration_remaining=1,
            duration_unit="rounds",
            requires_concentration=False,
            created_at=datetime.now(),
            mechanical_effects={
                "teleportation": True,
                "max_range": max_range,
                "entrance_range": entrance_range,
                "one_way": True,
                "destination_type": destination_type,
                "destination_offset": destination_offset if destination_type == "offset_coordinates" else None,
                "teleported": result_data["teleported"],
            },
        )
        self._active_effects.append(teleport_effect)

        return result_data

    def _handle_confusion(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Confusion spell.

        Strikes creatures with delusions, making them unable to control actions.

        Effects:
        - Affects 3d6 randomly determined creatures in 30' radius
        - Duration: 12 Rounds
        - Creatures Level 3+ get Save Versus Spell each round
        - Creatures Level 2 or lower get no save
        - Roll on Subject Behaviour table each round
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"confusion_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        # Roll for number of creatures affected
        creatures_affected = dice.roll("3d6")
        duration_rounds = 12
        area_radius = 30  # feet

        # Subject Behaviour table outcomes (d10 or d12 equivalent)
        behavior_table = [
            "wander_away",      # 1-2: Wander away for 1 Round
            "wander_away",
            "stand_confused",   # 3-4: Stand confused for 1 Round
            "stand_confused",
            "attack_nearest",   # 5-8: Attack nearest creature
            "attack_nearest",
            "attack_nearest",
            "attack_nearest",
            "act_normally",     # 9-10: Act normally for 1 Round
            "act_normally",
        ]

        result_data: dict[str, Any] = {
            "spell_id": "confusion",
            "spell_name": "Confusion",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "max_creatures_affected": creatures_affected,
            "duration_rounds": duration_rounds,
            "area_radius": area_radius,
            "behavior_table": behavior_table,
            "affected_creatures": [],
            "success": True,
        }

        # Process each potential target
        for target_id in targets_affected[:creatures_affected]:
            creature_data: dict[str, Any] = {
                "target_id": target_id,
                "level": 1,
                "can_save": False,
                "confused": True,
            }

            # Get creature level if available
            if hasattr(self, "_controller") and self._controller:
                target_char = self._controller.get_character(target_id)
                if target_char:
                    creature_data["level"] = getattr(target_char, "level", 1)

            # Creatures Level 3+ can save each round
            if creature_data["level"] >= 3:
                creature_data["can_save"] = True

            # Roll initial behavior
            behavior_roll = dice.roll("1d10") - 1  # 0-9 index
            creature_data["initial_behavior"] = behavior_table[behavior_roll]
            creature_data["behavior_roll"] = behavior_roll + 1

            result_data["affected_creatures"].append(creature_data)

            # Create confusion effect for each affected creature
            confusion_effect = ActiveSpellEffect(
                effect_id=f"{effect_id}_{target_id}",
                spell_id="confusion",
                spell_name="Confusion",
                caster_id=getattr(caster, "character_id", "unknown"),
                caster_level=caster_level,
                target_id=target_id,
                target_type="creature",
                effect_type=SpellEffectType.HYBRID,
                duration_type=DurationType.ROUNDS,
                duration_remaining=duration_rounds,
                duration_unit="rounds",
                requires_concentration=False,
                created_at=datetime.now(),
                mechanical_effects={
                    "condition": "confused",
                    "creature_level": creature_data["level"],
                    "can_save_each_round": creature_data["can_save"],
                    "save_type": "spell",
                    "behavior_table": behavior_table,
                    "current_behavior": creature_data["initial_behavior"],
                },
            )
            self._active_effects.append(confusion_effect)

        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": [
                f"a wave of befuddling magic washes over a 30' radius area",
                f"up to {creatures_affected} creatures are stricken with delusions",
                "affected creatures lose control of their actions",
            ]
            + (
                ["creatures of Level 3 or higher may attempt to resist each Round"]
                if any(c["can_save"] for c in result_data["affected_creatures"])
                else ["none of the affected creatures are powerful enough to resist"]
            ),
        }

        return result_data

    def _handle_greater_healing(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Greater Healing spell.

        A powerful healing prayer that restores significant Hit Points.

        Effects:
        - Heals 2d6+2 Hit Points
        - Cannot exceed target's maximum HP
        - St Wick's voice whispers a parable
        - Instant duration (no ongoing effect)
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)

        # Get target - can be caster or touched creature
        target_id = targets_affected[0] if targets_affected else getattr(caster, "character_id", "unknown")

        # Roll healing amount
        healing_roll = dice.roll("2d6")
        total_healing = healing_roll + 2

        result_data: dict[str, Any] = {
            "spell_id": "greater_healing",
            "spell_name": "Greater Healing",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "target_id": target_id,
            "healing_roll": healing_roll,
            "healing_bonus": 2,
            "total_healing": total_healing,
            "actual_healing": total_healing,  # May be reduced if at max HP
            "success": True,
        }

        # Apply healing if we have access to the target
        if hasattr(self, "_controller") and self._controller:
            target_char = self._controller.get_character(target_id)
            if target_char:
                current_hp = getattr(target_char, "current_hp", 0)
                max_hp = getattr(target_char, "max_hp", current_hp)

                # Calculate actual healing (cannot exceed max HP)
                hp_deficit = max_hp - current_hp
                actual_healing = min(total_healing, hp_deficit)
                result_data["actual_healing"] = actual_healing
                result_data["current_hp_before"] = current_hp
                result_data["current_hp_after"] = current_hp + actual_healing
                result_data["max_hp"] = max_hp

                if actual_healing < total_healing:
                    result_data["healing_capped"] = True
                else:
                    result_data["healing_capped"] = False

        result_data["narrative_context"] = {
            "prayer_answered": True,
            "hints": [
                "the rustic voice of St Wick manifests",
                "a gentle parable is whispered as the caster touches the subject",
                f"healing energy flows forth, restoring {result_data['actual_healing']} Hit Points",
            ]
            + (
                ["the subject's wounds close completely"]
                if result_data.get("healing_capped")
                else ["the subject's wounds begin to mend"]
            ),
        }

        # No active effect needed - this is an instant spell
        # But we track it for narration purposes
        result_data["duration_type"] = "instant"

        return result_data

    # =========================================================================
    # PHASE 8 HANDLERS: Summoning and Area Effects
    # =========================================================================

    def _handle_animate_dead(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Animate Dead spell.

        Raises corpses or skeletons as undead under caster's command.

        Effects:
        - Animates 1 corpse/skeleton per caster Level
        - Created undead use standard stats (not original creature stats)
        - Permanent duration until dispelled or slain
        - Undead obey caster's commands
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"animate_dead_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        # Number of undead equals caster level
        max_undead = caster_level
        corpses_available = len(targets_affected) if targets_affected else max_undead

        # Animate as many as possible up to limit
        undead_created = min(max_undead, corpses_available)

        # Standard undead stats (as per spell description)
        undead_stats = {
            "hit_dice": 1,
            "armor_class": 7,
            "attack_bonus": 0,
            "damage": "1d6",
            "movement": 60,
            "morale": 12,  # Undead don't flee
            "special_abilities": [],  # Cannot use abilities from life
        }

        result_data: dict[str, Any] = {
            "spell_id": "animate_dead",
            "spell_name": "Animate Dead",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "max_undead": max_undead,
            "corpses_available": corpses_available,
            "undead_created": undead_created,
            "undead_stats": undead_stats,
            "animated_corpses": [],
            "success": True,
        }

        # Track each animated corpse
        for i in range(undead_created):
            corpse_id = targets_affected[i] if i < len(targets_affected) else f"corpse_{i+1}"
            undead_id = f"undead_{corpse_id}"

            result_data["animated_corpses"].append({
                "corpse_id": corpse_id,
                "undead_id": undead_id,
                "undead_type": "skeleton" if "skeleton" in str(corpse_id).lower() else "zombie",
            })

        # Create permanent effect for the undead minions
        animate_effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="animate_dead",
            spell_name="Animate Dead",
            caster_id=getattr(caster, "character_id", "unknown"),
            caster_level=caster_level,
            target_id=f"undead_group_{effect_id}",
            target_type="creature_group",
            effect_type=SpellEffectType.MECHANICAL,
            duration_type=DurationType.PERMANENT,
            duration_remaining=None,
            duration_unit="permanent",
            requires_concentration=False,
            created_at=datetime.now(),
            mechanical_effects={
                "summoned_creatures": True,
                "creature_type": "undead",
                "count": undead_created,
                "stats": undead_stats,
                "obeys_caster": True,
                "dispellable": True,
                "ends_when_slain": True,
            },
        )
        self._active_effects.append(animate_effect)

        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": [
                f"dark energy flows from the caster's hands into {undead_created} corpse{'s' if undead_created > 1 else ''}",
                "bones rattle and flesh stirs as the dead rise",
                "hollow eyes glow with unholy light",
                "the undead await their master's commands",
            ],
        }

        return result_data

    def _handle_cloudkill(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Cloudkill spell.

        Creates a deadly poison fog that moves and sinks.

        Effects:
        - 30' diameter poison cloud
        - Moves at Speed 10, sinks to lowest point
        - 1 damage per Round to all in contact
        - Creatures Level 4 or lower: Save Versus Doom or die
        - Duration: 6 Turns
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"cloudkill_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        # Spell parameters
        cloud_diameter = 30  # feet
        duration_turns = 6
        cloud_speed = 10  # movement rate
        damage_per_round = 1
        instant_death_level_threshold = 4

        result_data: dict[str, Any] = {
            "spell_id": "cloudkill",
            "spell_name": "Cloudkill",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "cloud_diameter": cloud_diameter,
            "duration_turns": duration_turns,
            "cloud_speed": cloud_speed,
            "damage_per_round": damage_per_round,
            "instant_death_level_threshold": instant_death_level_threshold,
            "affected_creatures": [],
            "success": True,
        }

        # Process each target in the cloud
        for target_id in targets_affected:
            creature_data: dict[str, Any] = {
                "target_id": target_id,
                "level": 1,
                "damage_taken": damage_per_round,
                "must_save_vs_death": False,
                "save_roll": None,
                "died": False,
            }

            # Get creature level if available
            if hasattr(self, "_controller") and self._controller:
                target_char = self._controller.get_character(target_id)
                if target_char:
                    creature_data["level"] = getattr(target_char, "level", 1)

            # Low level creatures must save or die
            if creature_data["level"] <= instant_death_level_threshold:
                creature_data["must_save_vs_death"] = True
                save_roll = dice.roll("1d20")
                save_target = 12  # Default doom save

                # Get actual save target if available
                if hasattr(self, "_controller") and self._controller:
                    target_char = self._controller.get_character(target_id)
                    if target_char and hasattr(target_char, "saving_throws"):
                        save_target = getattr(target_char.saving_throws, "doom", 12)

                creature_data["save_roll"] = save_roll
                creature_data["save_target"] = save_target
                creature_data["died"] = save_roll < save_target

            result_data["affected_creatures"].append(creature_data)

        # Create the cloud effect
        cloud_effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="cloudkill",
            spell_name="Cloudkill",
            caster_id=getattr(caster, "character_id", "unknown"),
            caster_level=caster_level,
            target_id=f"cloud_area_{effect_id}",
            target_type="area",
            effect_type=SpellEffectType.MECHANICAL,
            duration_type=DurationType.TURNS,
            duration_remaining=duration_turns,
            duration_unit="turns",
            requires_concentration=False,
            created_at=datetime.now(),
            mechanical_effects={
                "area_effect": True,
                "cloud_diameter": cloud_diameter,
                "cloud_speed": cloud_speed,
                "sinks_to_lowest": True,
                "damage_per_round": damage_per_round,
                "instant_death_level_threshold": instant_death_level_threshold,
                "save_type": "doom",
            },
        )
        self._active_effects.append(cloud_effect)

        # Count deaths for narrative
        deaths = sum(1 for c in result_data["affected_creatures"] if c.get("died"))

        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": [
                "a sickly green fog streams from the caster's fingertips",
                f"the poisonous cloud fills a {cloud_diameter}' diameter area",
                "the deadly fog sinks toward the ground, flowing into low places",
            ]
            + (
                [f"{deaths} creature{'s' if deaths > 1 else ''} collapse{'s' if deaths == 1 else ''}, overcome by the poison"]
                if deaths > 0
                else ["creatures caught in the cloud choke and gasp"]
            ),
        }

        return result_data

    def _handle_insect_plague(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Insect Plague spell.

        Summons a swarm of biting insects in a fixed location.

        Effects:
        - 60' diameter swarm, does not move
        - Vision limited to 30' inside swarm
        - 1 damage per Round to all creatures
        - Creatures Level 1-2: Flee in horror (must go 240' away)
        - Duration: 1 Turn per Level
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"insect_plague_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        # Spell parameters
        swarm_diameter = 60  # feet
        duration_turns = caster_level
        damage_per_round = 1
        vision_limit = 30  # feet inside swarm
        flee_level_threshold = 2
        flee_distance = 240  # feet

        result_data: dict[str, Any] = {
            "spell_id": "insect_plague",
            "spell_name": "Insect Plague",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "swarm_diameter": swarm_diameter,
            "duration_turns": duration_turns,
            "damage_per_round": damage_per_round,
            "vision_limit": vision_limit,
            "flee_level_threshold": flee_level_threshold,
            "flee_distance": flee_distance,
            "affected_creatures": [],
            "success": True,
        }

        # Process each target in the swarm
        for target_id in targets_affected:
            creature_data: dict[str, Any] = {
                "target_id": target_id,
                "level": 1,
                "damage_taken": damage_per_round,
                "must_flee": False,
            }

            # Get creature level if available
            if hasattr(self, "_controller") and self._controller:
                target_char = self._controller.get_character(target_id)
                if target_char:
                    creature_data["level"] = getattr(target_char, "level", 1)

            # Low level creatures flee in horror
            if creature_data["level"] <= flee_level_threshold:
                creature_data["must_flee"] = True
                creature_data["flee_distance"] = flee_distance

            result_data["affected_creatures"].append(creature_data)

        # Create the swarm effect
        swarm_effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="insect_plague",
            spell_name="Insect Plague",
            caster_id=getattr(caster, "character_id", "unknown"),
            caster_level=caster_level,
            target_id=f"swarm_area_{effect_id}",
            target_type="area",
            effect_type=SpellEffectType.MECHANICAL,
            duration_type=DurationType.TURNS,
            duration_remaining=duration_turns,
            duration_unit="turns",
            requires_concentration=False,
            created_at=datetime.now(),
            mechanical_effects={
                "area_effect": True,
                "swarm_diameter": swarm_diameter,
                "stationary": True,
                "damage_per_round": damage_per_round,
                "vision_limit": vision_limit,
                "flee_level_threshold": flee_level_threshold,
                "flee_distance": flee_distance,
            },
        )
        self._active_effects.append(swarm_effect)

        # Count fleeing creatures for narrative
        fleeing = sum(1 for c in result_data["affected_creatures"] if c.get("must_flee"))

        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": [
                "a writhing mass of biting insects materializes",
                f"the swarm fills a {swarm_diameter}' diameter area",
                "the drone of thousands of wings fills the air",
                f"vision is limited to {vision_limit}' within the swarm",
            ]
            + (
                [f"{fleeing} low-level creature{'s' if fleeing > 1 else ''} flee{'s' if fleeing == 1 else ''} in horror"]
                if fleeing > 0
                else []
            ),
        }

        return result_data

    # =========================================================================
    # PHASE 9 HANDLERS: Transformation and Utility
    # =========================================================================

    def _handle_petrification(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Petrification spell.

        Can turn flesh to stone or stone to flesh.

        Effects:
        - Flesh to stone: Permanently transforms living creature to stone
          (Save Versus Hold to resist)
        - Stone to flesh: Restores petrified creature to life
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"petrification_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        # Determine mode from context
        mode = "flesh_to_stone"  # or "stone_to_flesh"
        if hasattr(self, "_current_context") and self._current_context:
            mode = self._current_context.get("mode", "flesh_to_stone")

        target_id = targets_affected[0] if targets_affected else None

        result_data: dict[str, Any] = {
            "spell_id": "petrification",
            "spell_name": "Petrification",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "target_id": target_id,
            "mode": mode,
            "success": True,
        }

        if mode == "flesh_to_stone":
            # Target must Save Versus Hold to resist
            save_roll = dice.roll("1d20")
            save_target = 14  # Default hold save

            if hasattr(self, "_controller") and self._controller and target_id:
                target_char = self._controller.get_character(target_id)
                if target_char and hasattr(target_char, "saving_throws"):
                    save_target = getattr(target_char.saving_throws, "hold", 14)

            save_success = save_roll >= save_target

            result_data["save_roll"] = save_roll
            result_data["save_target"] = save_target
            result_data["save_success"] = save_success
            result_data["petrified"] = not save_success

            if save_success:
                result_data["narrative_context"] = {
                    "spell_cast": True,
                    "resisted": True,
                    "hints": [
                        "stone-grey energy crackles toward the target",
                        f"but they resist the transformation (save roll {save_roll})",
                        "the petrifying magic dissipates harmlessly",
                    ],
                }
            else:
                # Create permanent petrification effect
                petri_effect = ActiveSpellEffect(
                    effect_id=effect_id,
                    spell_id="petrification",
                    spell_name="Petrification",
                    caster_id=getattr(caster, "character_id", "unknown"),
                    caster_level=caster_level,
                    target_id=target_id,
                    target_type="creature",
                    effect_type=SpellEffectType.MECHANICAL,
                    duration_type=DurationType.PERMANENT,
                    duration_remaining=None,
                    duration_unit="permanent",
                    requires_concentration=False,
                    created_at=datetime.now(),
                    mechanical_effects={
                        "condition": "petrified",
                        "transformation_type": "flesh_to_stone",
                        "includes_equipment": True,
                        "reversible_by": "stone_to_flesh",
                    },
                )
                self._active_effects.append(petri_effect)

                result_data["narrative_context"] = {
                    "spell_cast": True,
                    "transformation": True,
                    "hints": [
                        "stone-grey energy crackles toward the target",
                        f"they fail to resist (save roll {save_roll})",
                        "their flesh hardens and turns to grey stone",
                        "the transformation is complete and permanent",
                    ],
                }
        else:
            # Stone to flesh - restore petrified creature
            result_data["restored"] = True

            # Remove any petrification effects on the target
            if target_id:
                self._active_effects = [
                    e for e in self._active_effects
                    if not (e.spell_id == "petrification" and e.target_id == target_id)
                ]

            result_data["narrative_context"] = {
                "spell_cast": True,
                "restoration": True,
                "hints": [
                    "warm, life-giving energy flows into the stone",
                    "cracks appear as grey turns to flesh-tone",
                    "the creature gasps as life returns",
                    "they have been restored from petrification",
                ],
            }

        return result_data

    def _handle_invisibility(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Invisibility spell.

        Makes a creature or object invisible.

        Effects:
        - Subject and carried gear become invisible
        - Duration: 1 hour per caster Level
        - Ends if subject attacks or casts a spell
        - Light sources still emit light when invisible
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"invisibility_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        # Duration is 1 hour per level
        duration_hours = caster_level

        # Target can be caster, another creature, or an object
        target_id = targets_affected[0] if targets_affected else getattr(caster, "character_id", "unknown")

        # Determine target type from context
        target_type = "creature"
        if hasattr(self, "_current_context") and self._current_context:
            target_type = self._current_context.get("target_type", "creature")

        result_data: dict[str, Any] = {
            "spell_id": "invisibility",
            "spell_name": "Invisibility",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "target_id": target_id,
            "target_type": target_type,
            "duration_hours": duration_hours,
            "success": True,
        }

        # Create invisibility effect
        invis_effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="invisibility",
            spell_name="Invisibility",
            caster_id=getattr(caster, "character_id", "unknown"),
            caster_level=caster_level,
            target_id=target_id,
            target_type=target_type,
            effect_type=SpellEffectType.MECHANICAL,
            duration_type=DurationType.HOURS,
            duration_remaining=duration_hours,
            duration_unit="hours",
            requires_concentration=False,
            created_at=datetime.now(),
            mechanical_effects={
                "condition": "invisible",
                "includes_gear": target_type == "creature",
                "breaks_on_attack": True,
                "breaks_on_spell_cast": True,
                "light_sources_still_shine": True,
            },
        )
        self._active_effects.append(invis_effect)

        if target_type == "creature":
            result_data["narrative_context"] = {
                "spell_cast": True,
                "hints": [
                    f"the target shimmers and fades from sight",
                    "their clothing and equipment vanish with them",
                    f"the invisibility will last up to {duration_hours} hour{'s' if duration_hours > 1 else ''}",
                    "attacking or casting a spell will break the effect",
                ],
            }
        else:
            result_data["narrative_context"] = {
                "spell_cast": True,
                "hints": [
                    "the object shimmers and disappears from view",
                    f"it will remain invisible for up to {duration_hours} hour{'s' if duration_hours > 1 else ''}",
                ],
            }

        return result_data

    def _handle_knock(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Knock spell.

        Opens locked doors and disables magical seals.

        Effects:
        - Instant duration
        - Unlocks/removes mundane locks and bars
        - Dispels Glyphs of Sealing
        - Disables Glyphs of Locking for 1 Turn
        - Can open known secret doors
        """
        caster_level = getattr(caster, "level", 1)

        # Target is the door/portal being knocked
        target_id = targets_affected[0] if targets_affected else "door"

        # Get door/portal properties from context
        has_mundane_lock = True
        has_bar = False
        has_glyph_of_sealing = False
        has_glyph_of_locking = False
        is_secret_door = False

        if hasattr(self, "_current_context") and self._current_context:
            ctx = self._current_context
            has_mundane_lock = ctx.get("has_mundane_lock", True)
            has_bar = ctx.get("has_bar", False)
            has_glyph_of_sealing = ctx.get("has_glyph_of_sealing", False)
            has_glyph_of_locking = ctx.get("has_glyph_of_locking", False)
            is_secret_door = ctx.get("is_secret_door", False)

        result_data: dict[str, Any] = {
            "spell_id": "knock",
            "spell_name": "Knock",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "target_id": target_id,
            "duration_type": "instant",
            "success": True,
            "effects_applied": [],
        }

        hints = ["the caster knocks on the portal with hand or staff"]

        if has_mundane_lock:
            result_data["effects_applied"].append("mundane_lock_opened")
            hints.append("the lock clicks and unlocks")

        if has_bar:
            result_data["effects_applied"].append("bar_removed")
            hints.append("the bar slides aside with a groan")

        if has_glyph_of_sealing:
            result_data["effects_applied"].append("glyph_of_sealing_dispelled")
            hints.append("the Glyph of Sealing flares and fades, dispelled")

        if has_glyph_of_locking:
            result_data["effects_applied"].append("glyph_of_locking_disabled")
            result_data["glyph_disabled_duration"] = 1  # Turn
            hints.append("the Glyph of Locking dims, disabled for 1 Turn")

        if is_secret_door:
            result_data["effects_applied"].append("secret_door_opened")
            hints.append("the secret portal groans and swings open")

        if not result_data["effects_applied"]:
            hints.append("the portal was already unlocked")

        hints.append("the portal groans, grumbles, and opens")

        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": hints,
        }

        return result_data

    # =========================================================================
    # PHASE 10 HANDLERS - Remaining Moderate/Significant Spells
    # =========================================================================

    def _handle_arcane_cypher(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Arcane Cypher spell.

        Transforms text into incomprehensible arcane sigils readable only by caster.

        Effects:
        - Transforms up to 1 page of text per Level (or 1 spell in spellbook)
        - Duration is permanent
        - Only decoded by magic (e.g. Decipher spell)
        """
        caster_level = getattr(caster, "level", 1)
        effect_id = f"arcane_cypher_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        target_id = targets_affected[0] if targets_affected else "text"
        max_pages = caster_level

        result_data: dict[str, Any] = {
            "spell_id": "arcane_cypher",
            "spell_name": "Arcane Cypher",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "target_id": target_id,
            "max_pages": max_pages,
            "duration_type": "permanent",
            "success": True,
        }

        # Create permanent effect tracking the encrypted text
        effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="arcane_cypher",
            spell_name="Arcane Cypher",
            caster_id=getattr(caster, "character_id", "unknown"),
            caster_level=caster_level,
            target_id=target_id,
            target_type="object",
            effect_type=SpellEffectType.NARRATIVE,
            duration_type=DurationType.PERMANENT,
            duration_remaining=None,
            duration_unit="permanent",
            requires_concentration=False,
            mechanical_effects={
                "encrypted": True,
                "readable_by": [getattr(caster, "character_id", "unknown")],
                "decryption_method": "decipher_spell",
                "pages_affected": max_pages,
            },
        )
        self._active_effects.append(effect)

        result_data["effect_id"] = effect_id
        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": [
                "arcane sigils shimmer across the text",
                f"up to {max_pages} pages transformed into incomprehensible symbols",
                "only the caster can read the encrypted text",
            ],
        }

        return result_data

    def _handle_trap_the_soul(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Trap the Soul spell.

        Traps or releases a creature's life force in a prepared gem/crystal.

        Effects:
        - Trap mode: Save Versus Doom or soul trapped, body comatose (30 days to death)
        - Release mode: Restore soul to body or transfer to another receptacle
        - Receptacle must be worth 1000gp per target Level with name engraved
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"trap_the_soul_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        # Determine mode from context
        mode = "trap"  # or "release"
        if hasattr(self, "_current_context") and self._current_context:
            mode = self._current_context.get("mode", "trap")
            receptacle_id = self._current_context.get("receptacle_id", "gem")
        else:
            receptacle_id = "gem"

        target_id = targets_affected[0] if targets_affected else None

        result_data: dict[str, Any] = {
            "spell_id": "trap_the_soul",
            "spell_name": "Trap the Soul",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "target_id": target_id,
            "mode": mode,
            "receptacle_id": receptacle_id,
            "success": True,
        }

        hints = []

        if mode == "trap":
            # Target must Save Versus Doom
            save_roll = dice.roll("1d20")
            save_target = 12  # Default doom save

            if hasattr(self, "_controller") and self._controller and target_id:
                target_char = self._controller.get_character(target_id)
                if target_char and hasattr(target_char, "saving_throws"):
                    save_target = getattr(target_char.saving_throws, "doom", 12)

            save_success = save_roll >= save_target

            result_data["save_roll"] = save_roll
            result_data["save_target"] = save_target
            result_data["save_success"] = save_success
            result_data["soul_trapped"] = not save_success

            if not save_success:
                # Soul is trapped
                effect = ActiveSpellEffect(
                    effect_id=effect_id,
                    spell_id="trap_the_soul",
                    spell_name="Trap the Soul",
                    caster_id=getattr(caster, "character_id", "unknown"),
                    caster_level=caster_level,
                    target_id=target_id,
                    target_type="creature",
                    effect_type=SpellEffectType.MECHANICAL,
                    duration_type=DurationType.SPECIAL,
                    duration_remaining=30,
                    duration_unit="days",
                    requires_concentration=False,
                    mechanical_effects={
                        "soul_trapped": True,
                        "receptacle_id": receptacle_id,
                        "body_comatose": True,
                        "days_until_death": 30,
                        "can_converse": True,
                    },
                )
                self._active_effects.append(effect)
                result_data["effect_id"] = effect_id

                hints.append("the target's life force is ripped from their body")
                hints.append(f"soul trapped in the {receptacle_id}")
                hints.append("the body falls into a deathlike coma")
                hints.append("without intervention, death will occur in 30 days")
            else:
                hints.append("the target resists the spell")
                hints.append("their soul remains firmly anchored")
        else:
            # Release mode
            result_data["soul_released"] = True
            hints.append("the trapped soul streams forth from the receptacle")
            hints.append("life force restored to the body")

            # Remove any existing trap effect
            self._active_effects = [
                e for e in self._active_effects
                if not (e.spell_id == "trap_the_soul" and e.target_id == target_id)
            ]

        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": hints,
        }

        return result_data

    def _handle_holy_quest(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Holy Quest spell.

        Commands subject to perform a specific quest with penalties for refusal.

        Effects:
        - Target must perform the quest or suffer -2 to Attack Rolls and Saving Throws
        - Save Versus Spell to resist the compulsion
        - Duration until quest is completed
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        effect_id = f"holy_quest_{getattr(caster, 'character_id', 'unknown')}_{id(self)}"

        target_id = targets_affected[0] if targets_affected else None

        # Get quest description from context
        quest_description = "complete the assigned task"
        if hasattr(self, "_current_context") and self._current_context:
            quest_description = self._current_context.get("quest", quest_description)

        result_data: dict[str, Any] = {
            "spell_id": "holy_quest",
            "spell_name": "Holy Quest",
            "caster_id": getattr(caster, "character_id", "unknown"),
            "caster_level": caster_level,
            "target_id": target_id,
            "quest_description": quest_description,
            "success": True,
        }

        # Target may Save Versus Spell to resist
        save_roll = dice.roll("1d20")
        save_target = 14  # Default spell save

        if hasattr(self, "_controller") and self._controller and target_id:
            target_char = self._controller.get_character(target_id)
            if target_char and hasattr(target_char, "saving_throws"):
                save_target = getattr(target_char.saving_throws, "spell", 14)

        save_success = save_roll >= save_target

        result_data["save_roll"] = save_roll
        result_data["save_target"] = save_target
        result_data["save_success"] = save_success
        result_data["compelled"] = not save_success

        hints = ["a clap of thunder accompanies the divine command"]
        hints.append("a ray of holy light illuminates the target")

        if not save_success:
            # Target is compelled
            effect = ActiveSpellEffect(
                effect_id=effect_id,
                spell_id="holy_quest",
                spell_name="Holy Quest",
                caster_id=getattr(caster, "character_id", "unknown"),
                caster_level=caster_level,
                target_id=target_id,
                target_type="creature",
                effect_type=SpellEffectType.MECHANICAL,
                duration_type=DurationType.SPECIAL,
                duration_remaining=None,
                duration_unit="until_quest_complete",
                requires_concentration=False,
                mechanical_effects={
                    "quest": quest_description,
                    "compelled": True,
                    "refusal_penalty": {
                        "attack_rolls": -2,
                        "saving_throws": -2,
                    },
                    "quest_active": True,
                },
            )
            self._active_effects.append(effect)
            result_data["effect_id"] = effect_id

            hints.append(f"the target is compelled to: {quest_description}")
            hints.append("refusal brings divine punishment (-2 to attacks and saves)")
        else:
            hints.append("the target resists the holy compulsion")

        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": hints,
        }

        return result_data

    def _handle_polymorph(
        self,
        caster: "CharacterState",
        targets_affected: list[str],
        dice_roller: Optional["DiceRoller"] = None,
    ) -> dict[str, Any]:
        """
        Handle Polymorph spell.

        Transforms caster or subject into another living creature form.

        Effects:
        - Self: New form level <= caster level, keeps HP/saves/attack/intelligence
        - Other: New form level <= 2x caster level, fully becomes new form (permanent)
        - Physical capabilities acquired, non-physical special powers not acquired (self)
        - Unwilling targets may Save Versus Spell to resist
        """
        from src.data_models import DiceRoller as DR

        dice = dice_roller or DR()
        caster_level = getattr(caster, "level", 1)
        caster_id = getattr(caster, "character_id", "unknown")
        effect_id = f"polymorph_{caster_id}_{id(self)}"

        # Determine if self-cast or other
        target_id = targets_affected[0] if targets_affected else caster_id
        is_self_cast = target_id == caster_id

        # Get new form from context
        new_form = "wolf"  # Default form
        new_form_level = 2
        if hasattr(self, "_current_context") and self._current_context:
            new_form = self._current_context.get("new_form", new_form)
            new_form_level = self._current_context.get("new_form_level", new_form_level)

        result_data: dict[str, Any] = {
            "spell_id": "polymorph",
            "spell_name": "Polymorph",
            "caster_id": caster_id,
            "caster_level": caster_level,
            "target_id": target_id,
            "is_self_cast": is_self_cast,
            "new_form": new_form,
            "new_form_level": new_form_level,
            "success": True,
        }

        hints = []

        # Check level restriction
        max_allowed_level = caster_level if is_self_cast else caster_level * 2
        if new_form_level > max_allowed_level:
            result_data["success"] = False
            result_data["failure_reason"] = "new_form_level_too_high"
            hints.append(f"the {new_form} form is too powerful for this casting")
            result_data["narrative_context"] = {"spell_cast": False, "hints": hints}
            return result_data

        # Handle unwilling targets (not self)
        if not is_self_cast:
            is_unwilling = False
            if hasattr(self, "_current_context") and self._current_context:
                is_unwilling = self._current_context.get("is_unwilling", False)

            if is_unwilling:
                save_roll = dice.roll("1d20")
                save_target = 14  # Default spell save

                if hasattr(self, "_controller") and self._controller:
                    target_char = self._controller.get_character(target_id)
                    if target_char and hasattr(target_char, "saving_throws"):
                        save_target = getattr(target_char.saving_throws, "spell", 14)

                save_success = save_roll >= save_target

                result_data["save_roll"] = save_roll
                result_data["save_target"] = save_target
                result_data["save_success"] = save_success

                if save_success:
                    result_data["success"] = False
                    result_data["failure_reason"] = "target_resisted"
                    hints.append("the target resists the transformation")
                    result_data["narrative_context"] = {"spell_cast": True, "hints": hints}
                    return result_data

        # Calculate duration
        if is_self_cast:
            base_duration = dice.roll("1d6")
            duration = base_duration + caster_level
            duration_type = DurationType.TURNS
            duration_unit = "turns"
        else:
            duration = None
            duration_type = DurationType.PERMANENT
            duration_unit = "permanent"

        result_data["duration"] = duration
        result_data["duration_unit"] = duration_unit

        # Create the polymorph effect
        effect = ActiveSpellEffect(
            effect_id=effect_id,
            spell_id="polymorph",
            spell_name="Polymorph",
            caster_id=caster_id,
            caster_level=caster_level,
            target_id=target_id,
            target_type="creature",
            effect_type=SpellEffectType.MECHANICAL,
            duration_type=duration_type,
            duration_remaining=duration,
            duration_unit=duration_unit,
            requires_concentration=False,
            mechanical_effects={
                "new_form": new_form,
                "new_form_level": new_form_level,
                "is_self_cast": is_self_cast,
                "preserves_hp": True,
                "preserves_saves": is_self_cast,
                "preserves_attack": is_self_cast,
                "preserves_intelligence": is_self_cast,
                "acquires_physical_capabilities": True,
                "acquires_special_powers": not is_self_cast,
                "can_cast_spells": False,
                "reverts_on_death": True,
            },
        )
        self._active_effects.append(effect)
        result_data["effect_id"] = effect_id

        hints.append(f"flesh ripples and transforms into the form of a {new_form}")
        if is_self_cast:
            hints.append(f"transformation lasts {duration} turns")
            hints.append("physical capabilities acquired, spell casting suppressed")
        else:
            hints.append("the transformation is permanent")
            hints.append("the target fully becomes the new creature")

        result_data["narrative_context"] = {
            "spell_cast": True,
            "hints": hints,
        }

        return result_data


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
