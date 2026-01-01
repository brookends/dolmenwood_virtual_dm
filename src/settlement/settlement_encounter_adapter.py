"""
Settlement Encounter Adapter for Dolmenwood Virtual DM.

This module provides the translation layer between settlement encounter data
(which uses descriptive strings like "3d6 shorthorn soldiers") and the
EncounterFactory/EncounterEngine system (which needs structured RolledEncounter
objects with monster registry IDs).

The adapter:
1. Parses actor strings to extract quantity dice and actor type
2. Maps actor types to MonsterRegistry IDs
3. Creates RolledEncounter objects for EncounterFactory
4. Handles special cases (NPCs, narrative encounters, etc.)
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

from src.data_models import DiceRoller
from src.tables.encounter_roller import (
    RolledEncounter,
    EncounterEntry,
    EncounterEntryType,
)
from src.tables.wilderness_encounter_tables import EncounterCategory


logger = logging.getLogger(__name__)


# =============================================================================
# ACTOR TYPE CLASSIFICATION
# =============================================================================


class SettlementActorType(str, Enum):
    """Classification of settlement encounter actors."""

    MONSTER = "monster"  # Standard monster from registry
    NPC = "npc"  # Named NPC (uses NPC system)
    MORTAL = "mortal"  # Generic mortals (townsfolk, merchants, etc.)
    SPECIAL = "special"  # Special handling required
    NARRATIVE = "narrative"  # No combat stats needed


# =============================================================================
# ACTOR MAPPING TABLE
# =============================================================================


# Maps settlement encounter actor strings to MonsterRegistry IDs
# Format: "actor_string": ("monster_id", SettlementActorType, optional_notes)
SETTLEMENT_ACTOR_MAP: dict[str, tuple[str, SettlementActorType, Optional[str]]] = {
    # === BREGGLE VARIANTS ===
    "shorthorn soldiers": ("breggle_shorthorn", SettlementActorType.MONSTER, None),
    "shorthorn guards": ("breggle_shorthorn", SettlementActorType.MONSTER, None),
    "shorthorns": ("breggle_shorthorn", SettlementActorType.MONSTER, None),
    "longhorn guards": ("breggle_longhorn", SettlementActorType.MONSTER, None),
    "longhorn nobles": ("breggle_longhorn", SettlementActorType.MONSTER, "Noble variant"),
    "longhorns": ("breggle_longhorn", SettlementActorType.MONSTER, None),
    # === HUMANOID COMBATANTS ===
    "ruffians": ("thief_footpad", SettlementActorType.MONSTER, "Level 1 thieves"),
    "thieves": ("thief_footpad", SettlementActorType.MONSTER, None),
    "pickpocket": ("thief_footpad", SettlementActorType.MONSTER, "Single thief"),
    "guards": ("standard_mercenary", SettlementActorType.MONSTER, None),
    "soldiers": ("standard_mercenary", SettlementActorType.MONSTER, None),
    "clerics": ("level_1_cleric_acolyte", SettlementActorType.MONSTER, None),
    # === FAIRY CREATURES ===
    "sprites": ("sprite", SettlementActorType.MONSTER, None),
    "grimalkin": ("grimalkin", SettlementActorType.MONSTER, None),
    "mosslings": ("mossling", SettlementActorType.MONSTER, None),
    "Mossling": ("mossling", SettlementActorType.MONSTER, None),
    "2d4 mosslings": ("mossling", SettlementActorType.MONSTER, "Quantity embedded"),
    "nutcaps": ("nutcap", SettlementActorType.MONSTER, None),
    "Nutcap": ("nutcap", SettlementActorType.MONSTER, None),
    # === MONSTERS ===
    "Crookhorn": ("crookhorn", SettlementActorType.MONSTER, None),
    "Crookhorns": ("crookhorn", SettlementActorType.MONSTER, None),
    "Crookhorn Guards": ("crookhorn", SettlementActorType.MONSTER, None),
    "griffon": ("griffon", SettlementActorType.MONSTER, None),
    "bog corpses": ("bog_corpse", SettlementActorType.MONSTER, None),
    "Zombie": ("zombie", SettlementActorType.MONSTER, None),
    "barrowbogey": ("barrowbogey", SettlementActorType.MONSTER, None),
    "bestial centaur": ("centaur_bestial", SettlementActorType.MONSTER, None),
    "ochre slime-hulk": ("ochre_slime_hulk", SettlementActorType.MONSTER, None),
    "Ochre Slime-hulk": ("ochre_slime_hulk", SettlementActorType.MONSTER, None),
    "clockwork guardian": ("clockwork_guardian", SettlementActorType.MONSTER, None),
    "Giant Mutant Snail": ("snail_giant_mutant", SettlementActorType.MONSTER, None),
    "the Hag": ("the_hag", SettlementActorType.MONSTER, "Unique creature"),
    "Big Chook": ("big_chook", SettlementActorType.MONSTER, "Unique creature"),
    # === ELEMENTALS/SPECIAL ===
    "fire elemental": ("fire_elemental", SettlementActorType.MONSTER, None),
    "lost soul": ("spectre", SettlementActorType.MONSTER, "Use Spectre stats"),
    # === GENERIC MORTALS (non-combat or low-threat) ===
    "merchants": ("townsfolk", SettlementActorType.MORTAL, None),
    "nobles": ("townsfolk", SettlementActorType.MORTAL, "Noble townsfolk"),
    "villagers": ("townsfolk", SettlementActorType.MORTAL, None),
    # === SPECIAL CASES ===
    "random monster": (None, SettlementActorType.SPECIAL, "Roll on monster table"),
}


# Aliases for case-insensitive matching
SETTLEMENT_ACTOR_ALIASES: dict[str, str] = {
    "sprite": "sprites",
    "thief": "thieves",
    "guard": "guards",
    "soldier": "soldiers",
    "merchant": "merchants",
    "noble": "nobles",
    "ruffian": "ruffians",
    "crookhorn": "Crookhorn",
    "crookhorns": "Crookhorns",
    "mossling": "Mossling",
    "nutcap": "Nutcap",
    "zombie": "Zombie",
}


# =============================================================================
# PARSED ACTOR RESULT
# =============================================================================


@dataclass
class ParsedActor:
    """Result of parsing a settlement actor string."""

    original_string: str
    actor_type: str  # Normalized actor type string
    quantity_dice: str  # Dice expression like "3d6" or "1" for single
    quantity: int  # Rolled quantity
    monster_id: Optional[str]  # MonsterRegistry ID if applicable
    actor_classification: SettlementActorType
    notes: Optional[str] = None
    parse_success: bool = True
    error_message: Optional[str] = None


@dataclass
class SettlementEncounterConversion:
    """Result of converting a settlement encounter for EncounterEngine."""

    # Original data
    settlement_id: str
    settlement_name: str
    description: str
    time_of_day: str

    # Parsed actors
    parsed_monsters: list[ParsedActor] = field(default_factory=list)
    parsed_npcs: list[ParsedActor] = field(default_factory=list)

    # Conversion result
    rolled_encounter: Optional[RolledEncounter] = None
    requires_engine: bool = False
    is_narrative_only: bool = False

    # Any issues encountered
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# =============================================================================
# ACTOR STRING PARSER
# =============================================================================


class SettlementActorParser:
    """
    Parses settlement encounter actor strings.

    Handles formats like:
    - "3d6 shorthorn soldiers"
    - "2d4 mosslings"
    - "1d4 sprites"
    - "griffon"
    - "Father Dobey"
    - "Berkmaster Baldricke"
    """

    # Pattern to extract dice quantity and actor type
    # Matches: "3d6 sprites", "2d4 mosslings", "1d4+1 guards"
    DICE_PATTERN = re.compile(
        r"^(\d+d\d+(?:\+\d+)?)\s+(.+)$", re.IGNORECASE
    )

    # Pattern for numeric quantity: "3 guards", "12 soldiers"
    NUMERIC_PATTERN = re.compile(
        r"^(\d+)\s+(.+)$", re.IGNORECASE
    )

    def __init__(self):
        self.dice = DiceRoller()

    def parse_actor_string(self, actor_string: str) -> ParsedActor:
        """
        Parse an actor string from settlement encounter data.

        Args:
            actor_string: String like "3d6 shorthorn soldiers" or "griffon"

        Returns:
            ParsedActor with extracted information
        """
        original = actor_string.strip()

        # Try dice pattern first
        dice_match = self.DICE_PATTERN.match(original)
        if dice_match:
            dice_expr = dice_match.group(1)
            actor_type = dice_match.group(2).strip()
            quantity = self.dice.roll(dice_expr, f"quantity for {actor_type}").total
            return self._create_parsed_actor(
                original, actor_type, dice_expr, quantity
            )

        # Try numeric pattern
        numeric_match = self.NUMERIC_PATTERN.match(original)
        if numeric_match:
            quantity = int(numeric_match.group(1))
            actor_type = numeric_match.group(2).strip()
            return self._create_parsed_actor(
                original, actor_type, str(quantity), quantity
            )

        # No quantity specified - assume single
        return self._create_parsed_actor(original, original, "1", 1)

    def _create_parsed_actor(
        self,
        original: str,
        actor_type: str,
        quantity_dice: str,
        quantity: int,
    ) -> ParsedActor:
        """Create a ParsedActor from extracted components."""
        # Normalize actor type for lookup
        normalized = actor_type.lower().strip()

        # Check aliases first
        if normalized in SETTLEMENT_ACTOR_ALIASES:
            lookup_key = SETTLEMENT_ACTOR_ALIASES[normalized]
        else:
            lookup_key = actor_type

        # Look up in mapping table
        if lookup_key in SETTLEMENT_ACTOR_MAP:
            monster_id, classification, notes = SETTLEMENT_ACTOR_MAP[lookup_key]
            return ParsedActor(
                original_string=original,
                actor_type=actor_type,
                quantity_dice=quantity_dice,
                quantity=quantity,
                monster_id=monster_id,
                actor_classification=classification,
                notes=notes,
                parse_success=True,
            )

        # Try case-insensitive search
        for key, (monster_id, classification, notes) in SETTLEMENT_ACTOR_MAP.items():
            if key.lower() == normalized:
                return ParsedActor(
                    original_string=original,
                    actor_type=actor_type,
                    quantity_dice=quantity_dice,
                    quantity=quantity,
                    monster_id=monster_id,
                    actor_classification=classification,
                    notes=notes,
                    parse_success=True,
                )

        # Not found in mapping - likely a named NPC
        # Check if it looks like a proper name (capitalized words)
        words = actor_type.split()
        if all(w[0].isupper() for w in words if w):
            return ParsedActor(
                original_string=original,
                actor_type=actor_type,
                quantity_dice=quantity_dice,
                quantity=quantity,
                monster_id=None,
                actor_classification=SettlementActorType.NPC,
                notes="Named NPC - use NPC system",
                parse_success=True,
            )

        # Unknown actor type
        return ParsedActor(
            original_string=original,
            actor_type=actor_type,
            quantity_dice=quantity_dice,
            quantity=quantity,
            monster_id=None,
            actor_classification=SettlementActorType.NARRATIVE,
            notes="Unknown actor type - narrative handling",
            parse_success=False,
            error_message=f"No mapping found for actor type: {actor_type}",
        )


# =============================================================================
# SETTLEMENT ENCOUNTER ADAPTER
# =============================================================================


class SettlementEncounterAdapter:
    """
    Converts settlement encounter data into EncounterFactory-compatible format.

    This is the main integration point between SettlementEngine and
    EncounterEngine/EncounterFactory.
    """

    def __init__(self):
        self.parser = SettlementActorParser()
        self.dice = DiceRoller()

    def convert_encounter(
        self,
        encounter_data: dict[str, Any],
        settlement_id: str,
        settlement_name: str,
    ) -> SettlementEncounterConversion:
        """
        Convert settlement encounter data to EncounterFactory format.

        Args:
            encounter_data: Dict from SettlementEngine._prepare_encounter_for_engine()
            settlement_id: Settlement identifier
            settlement_name: Settlement name

        Returns:
            SettlementEncounterConversion with conversion results
        """
        result = SettlementEncounterConversion(
            settlement_id=settlement_id,
            settlement_name=settlement_name,
            description=encounter_data.get("context", ""),
            time_of_day=encounter_data.get("time_of_day", ""),
        )

        # Parse all actors
        actors = encounter_data.get("actors", [])
        for actor_str in actors:
            parsed = self.parser.parse_actor_string(actor_str)

            if parsed.actor_classification == SettlementActorType.MONSTER:
                result.parsed_monsters.append(parsed)
            elif parsed.actor_classification in (
                SettlementActorType.NPC,
                SettlementActorType.MORTAL,
            ):
                result.parsed_npcs.append(parsed)
            else:
                result.parsed_npcs.append(parsed)

            if not parsed.parse_success:
                result.warnings.append(parsed.error_message or f"Failed to parse: {actor_str}")

        # Determine if encounter requires EncounterEngine
        has_combat_monsters = any(
            p.actor_classification == SettlementActorType.MONSTER
            and p.monster_id is not None
            for p in result.parsed_monsters
        )

        result.requires_engine = has_combat_monsters
        result.is_narrative_only = not has_combat_monsters

        # Create RolledEncounter if combat is possible
        if result.requires_engine:
            result.rolled_encounter = self._create_rolled_encounter(result)

        return result

    def _create_rolled_encounter(
        self,
        conversion: SettlementEncounterConversion,
    ) -> RolledEncounter:
        """Create a RolledEncounter from parsed settlement encounter data."""
        # Use the first monster as the primary entry
        if conversion.parsed_monsters:
            primary = conversion.parsed_monsters[0]
            monster_id = primary.monster_id or "unknown"
            name = primary.actor_type
            number_appearing = primary.quantity
            entry_type = EncounterEntryType.MONSTER
            category = EncounterCategory.MONSTER
        else:
            # NPC-only encounter
            primary = conversion.parsed_npcs[0] if conversion.parsed_npcs else None
            monster_id = ""
            name = primary.actor_type if primary else "Unknown"
            number_appearing = primary.quantity if primary else 1
            entry_type = EncounterEntryType.EVERYDAY_MORTAL
            category = EncounterCategory.MORTAL

        entry = EncounterEntry(
            name=name,
            entry_type=entry_type,
            number_appearing=str(number_appearing),
            monster_id=monster_id,
        )

        return RolledEncounter(
            entry=entry,
            entry_type=entry_type,
            category=category,
            number_appearing=number_appearing,
            number_appearing_dice=primary.quantity_dice if primary else "1",
            activity=conversion.description,
            terrain_type=f"settlement:{conversion.settlement_id}",
        )

    def create_encounter_from_settlement(
        self,
        encounter_engine_data: dict[str, Any],
    ) -> Optional[RolledEncounter]:
        """
        Convenience method to create RolledEncounter from SettlementEngine data.

        Args:
            encounter_engine_data: Dict from SettlementEngine._prepare_encounter_for_engine()

        Returns:
            RolledEncounter if combat encounter, None if narrative only
        """
        conversion = self.convert_encounter(
            encounter_engine_data,
            encounter_engine_data.get("settlement_id", ""),
            encounter_engine_data.get("settlement_name", ""),
        )

        return conversion.rolled_encounter


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================


_adapter: Optional[SettlementEncounterAdapter] = None
_parser: Optional[SettlementActorParser] = None


def get_settlement_encounter_adapter() -> SettlementEncounterAdapter:
    """Get the shared SettlementEncounterAdapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = SettlementEncounterAdapter()
    return _adapter


def get_settlement_actor_parser() -> SettlementActorParser:
    """Get the shared SettlementActorParser instance."""
    global _parser
    if _parser is None:
        _parser = SettlementActorParser()
    return _parser


def parse_settlement_actor(actor_string: str) -> ParsedActor:
    """
    Parse a settlement actor string.

    Convenience function for quick parsing.

    Args:
        actor_string: String like "3d6 shorthorn soldiers"

    Returns:
        ParsedActor with parsed information
    """
    return get_settlement_actor_parser().parse_actor_string(actor_string)


def convert_settlement_encounter(
    encounter_engine_data: dict[str, Any],
) -> SettlementEncounterConversion:
    """
    Convert settlement encounter data for EncounterEngine.

    Convenience function for the full conversion pipeline.

    Args:
        encounter_engine_data: Dict from SettlementEngine._prepare_encounter_for_engine()

    Returns:
        SettlementEncounterConversion with all parsed data
    """
    adapter = get_settlement_encounter_adapter()
    return adapter.convert_encounter(
        encounter_engine_data,
        encounter_engine_data.get("settlement_id", ""),
        encounter_engine_data.get("settlement_name", ""),
    )


def reset_adapter() -> None:
    """Reset the shared adapter instances."""
    global _adapter, _parser
    _adapter = None
    _parser = None
