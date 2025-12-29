"""
Spell Resolver for Dolmenwood Virtual DM.

Handles spell casting outside of combat, including:
- Spell lookup and validation
- Slot consumption
- Effect application and duration tracking
- Concentration management
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from src.data_models import CharacterState, DiceRoller

from src.narrative.intent_parser import SaveType


class DurationType(str, Enum):
    """How a spell's duration is tracked."""
    INSTANT = "instant"             # Immediate effect, no duration
    ROUNDS = "rounds"               # Duration in combat rounds
    TURNS = "turns"                 # Duration in exploration turns (10 min)
    HOURS = "hours"                 # Duration in hours
    DAYS = "days"                   # Duration in days
    CONCENTRATION = "concentration" # Lasts while concentrating
    PERMANENT = "permanent"         # Lasts until dispelled/dismissed
    SPECIAL = "special"             # Custom duration logic


class RangeType(str, Enum):
    """How a spell's range is specified."""
    SELF = "self"                   # Affects caster only
    TOUCH = "touch"                 # Must touch target
    RANGED = "ranged"               # Has a range in feet
    AREA = "area"                   # Affects an area


class SpellEffectType(str, Enum):
    """How a spell's effects are resolved."""
    MECHANICAL = "mechanical"       # Fully resolved by Python (damage, conditions)
    NARRATIVE = "narrative"         # LLM describes, minimal mechanics
    HYBRID = "hybrid"               # Python mechanics + LLM narration


class MagicType(str, Enum):
    """Type of magic."""
    ARCANE = "arcane"               # Wizard/Magic-User spells
    DIVINE = "divine"               # Cleric spells
    FAIRY_GLAMOUR = "fairy_glamour" # Elf/Grimalkin/Woodgrue glamours
    DRUIDIC = "druidic"             # Druid spells


@dataclass
class SpellData:
    """
    Spell data structure for database storage.

    Contains both raw text fields and parsed mechanical components.
    """
    # Core identification
    spell_id: str
    name: str
    level: Optional[int]            # None for fairy glamours
    magic_type: MagicType

    # Raw text fields (from source)
    duration: str                   # Raw text: "1d6 Turns + 1 Turn per Level"
    range: str                      # Raw text: "60'"
    description: str                # Full description

    # Reversible spell info
    reversible: bool = False
    reversed_name: Optional[str] = None

    # Parsed mechanical components
    duration_type: DurationType = DurationType.INSTANT
    duration_value: Optional[str] = None    # Dice notation or fixed value
    duration_per_level: bool = False        # Does duration scale with level?
    range_feet: Optional[int] = None        # Parsed range in feet
    range_type: RangeType = RangeType.RANGED

    # Effect classification
    effect_type: SpellEffectType = SpellEffectType.HYBRID
    save_type: Optional[SaveType] = None
    save_negates: bool = False              # Does save completely negate?

    # Usage limits (especially for glamours)
    usage_frequency: Optional[str] = None   # "once per turn", "once per day per subject"
    kindred_restricted: list[str] = field(default_factory=list)

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
    target_id: str = ""             # Character, NPC, Monster, or "area:location_id"
    target_type: str = "creature"   # "creature", "object", "area"

    # Duration tracking (tied to turn/time system)
    duration_type: DurationType = DurationType.INSTANT
    duration_remaining: Optional[int] = None    # Rounds or Turns remaining
    duration_unit: str = "turns"    # "rounds" or "turns"
    expires_at: Optional[datetime] = None       # For real-time tracking if needed

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
    reason: str = ""                        # Why it succeeded/failed
    effect_created: Optional[ActiveSpellEffect] = None

    # Mechanical outcomes
    damage_dealt: Optional[dict[str, Any]] = None
    conditions_applied: list[str] = field(default_factory=list)
    save_required: bool = False
    save_result: Optional[dict[str, Any]] = None

    # Resource consumption
    slot_consumed: bool = False
    slot_level: Optional[int] = None

    # For LLM narration
    narrative_context: dict[str, Any] = field(default_factory=dict)

    # Errors
    error: Optional[str] = None


class SpellResolver:
    """
    Resolves spell casting outside of combat.

    Handles:
    - Spell lookup (from database or cache)
    - Slot/usage validation
    - Effect application
    - Duration tracking
    - Concentration management
    """

    def __init__(self, spell_database: Optional[dict[str, SpellData]] = None):
        """
        Initialize the spell resolver.

        Args:
            spell_database: Optional pre-loaded spell data
        """
        self._spell_cache: dict[str, SpellData] = spell_database or {}
        self._active_effects: list[ActiveSpellEffect] = []

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
        self,
        caster: "CharacterState",
        spell: SpellData,
        target_id: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Check if a caster can cast a spell.

        Args:
            caster: The character attempting to cast
            spell: The spell to cast
            target_id: Optional target ID

        Returns:
            Tuple of (can_cast, reason)
        """
        # Check if caster has the spell prepared
        has_spell = any(s.spell_id == spell.spell_id for s in caster.spells)
        if not has_spell:
            return False, f"{caster.name} does not have {spell.name} prepared"

        # Check spell slot availability (for leveled spells)
        if spell.level is not None:
            # Find the spell in caster's list
            caster_spell = next(
                (s for s in caster.spells if s.spell_id == spell.spell_id),
                None
            )
            if caster_spell and caster_spell.cast_today:
                return False, f"{spell.name} has already been cast today"

        # Check concentration conflicts
        if spell.requires_concentration:
            active_concentration = self.get_concentration_effect(caster.character_id)
            if active_concentration:
                # Would need to break existing concentration
                pass  # Allow, but note the conflict

        # Check usage frequency for glamours
        if spell.usage_frequency:
            # TODO: Track glamour usage per subject/turn/day
            pass

        # Check kindred restrictions (only applies to Mossling Knacks)
        if spell.kindred_restricted:
            caster_kindred = caster.kindred.lower() if hasattr(caster, 'kindred') else ""
            allowed_kindreds = [k.lower() for k in spell.kindred_restricted]
            if caster_kindred not in allowed_kindreds:
                return False, f"Only {', '.join(spell.kindred_restricted)} can cast {spell.name}"

        return True, "Can cast"

    def resolve_spell(
        self,
        caster: "CharacterState",
        spell: SpellData,
        target_id: Optional[str] = None,
        target_description: Optional[str] = None,
        dice_roller: Optional["DiceRoller"] = None
    ) -> SpellCastResult:
        """
        Resolve casting a spell outside of combat.

        Args:
            caster: The character casting the spell
            spell: The spell being cast
            target_id: Optional specific target ID
            target_description: Description of target for narrative
            dice_roller: Dice roller for any rolls needed

        Returns:
            SpellCastResult with outcomes
        """
        # Check if can cast
        can_cast, reason = self.can_cast_spell(caster, spell, target_id)
        if not can_cast:
            return SpellCastResult(
                success=False,
                spell_id=spell.spell_id,
                spell_name=spell.name,
                reason=reason,
                error=reason
            )

        # Break any existing concentration
        if spell.requires_concentration:
            existing = self.get_concentration_effect(caster.character_id)
            if existing:
                existing.break_concentration()

        # Consume spell slot
        slot_consumed = False
        if spell.level is not None:
            for s in caster.spells:
                if s.spell_id == spell.spell_id:
                    s.cast_today = True
                    slot_consumed = True
                    break

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

        # Handle saving throw if needed
        save_result = None
        if spell.save_type:
            # TODO: Roll saving throw for target
            save_result = {
                "save_type": spell.save_type.value,
                "target_id": target_id,
                "result": "pending",  # Would roll actual save
            }

        # Build narrative context for LLM
        narrative_context = {
            "spell_name": spell.name,
            "caster_name": caster.name,
            "target": target_description or target_id,
            "duration": spell.duration,
            "range": spell.range,
            "effect_type": spell.effect_type.value,
            "description": spell.description,
            "requires_concentration": spell.requires_concentration,
        }

        return SpellCastResult(
            success=True,
            spell_id=spell.spell_id,
            spell_name=spell.name,
            reason="Spell cast successfully",
            effect_created=effect_created,
            save_required=spell.save_type is not None,
            save_result=save_result,
            slot_consumed=slot_consumed,
            slot_level=spell.level,
            narrative_context=narrative_context,
        )

    def _calculate_duration(
        self,
        spell: SpellData,
        caster: "CharacterState",
        dice_roller: Optional["DiceRoller"] = None
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
        elif dice_roller and 'd' in spell.duration_value.lower():
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
        return [e for e in self._active_effects
                if e.target_id == entity_id and e.is_active]

    def get_concentration_effect(self, caster_id: str) -> Optional[ActiveSpellEffect]:
        """Get the active concentration effect for a caster."""
        for effect in self._active_effects:
            if (effect.caster_id == caster_id and
                effect.requires_concentration and
                effect.is_active and
                not effect.concentration_broken):
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
            if (effect.caster_id == caster_id and
                effect.requires_concentration and
                effect.is_active):
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
