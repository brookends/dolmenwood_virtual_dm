"""
Shared test utilities for loading Dolmenwood spell data.

This module provides helpers for loading real Dolmenwood spells from
the JSON data files in /data/content/spells/ for use in integration tests.
"""

import json
from pathlib import Path
from typing import Optional

from src.narrative.spell_resolver import SpellData, MagicType
from src.data_models import CharacterState


# Path to spell data directory
SPELL_DATA_DIR = Path(__file__).parent.parent / "data" / "content" / "spells"

# Cache for loaded spells
_spell_cache: dict[str, dict] = {}


def load_spells_from_json(filename: str) -> list[dict]:
    """Load spells from a JSON file in the spells directory.

    Args:
        filename: Name of the JSON file (e.g., "arcane_level_1_1.json")

    Returns:
        List of spell dictionaries from the file's "items" key
    """
    filepath = SPELL_DATA_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath) as f:
        data = json.load(f)
    return data.get("items", [])


def _build_spell_cache() -> None:
    """Build cache of all spells indexed by spell_id."""
    global _spell_cache
    if _spell_cache:
        return

    for json_file in SPELL_DATA_DIR.glob("*.json"):
        try:
            spells = load_spells_from_json(json_file.name)
            for spell_dict in spells:
                spell_id = spell_dict.get("spell_id")
                if spell_id:
                    _spell_cache[spell_id] = spell_dict
        except (json.JSONDecodeError, KeyError):
            continue


def spell_dict_to_spelldata(spell_dict: dict) -> SpellData:
    """Convert a spell dictionary from JSON to SpellData object.

    Args:
        spell_dict: Dictionary with spell data from JSON

    Returns:
        SpellData object with the spell's properties
    """
    magic_type_map = {
        "arcane": MagicType.ARCANE,
        "divine": MagicType.DIVINE,
        "fairy_glamour": MagicType.FAIRY_GLAMOUR,
    }
    return SpellData(
        spell_id=spell_dict["spell_id"],
        name=spell_dict["name"],
        level=spell_dict.get("level"),
        magic_type=magic_type_map.get(spell_dict.get("magic_type", "arcane"), MagicType.ARCANE),
        duration=spell_dict.get("duration", "Instant"),
        range=spell_dict.get("range", "Self"),
        description=spell_dict.get("description", ""),
        reversible=spell_dict.get("reversible", False),
        reversed_name=spell_dict.get("reversed_name"),
    )


def find_spell_by_id(spell_id: str) -> SpellData:
    """Find a spell by ID across all spell files.

    Args:
        spell_id: The spell_id to search for (e.g., "fireball", "animate_dead")

    Returns:
        SpellData object for the spell

    Raises:
        ValueError: If spell not found
    """
    _build_spell_cache()

    if spell_id in _spell_cache:
        return spell_dict_to_spelldata(_spell_cache[spell_id])

    raise ValueError(f"Spell not found: {spell_id}")


def get_spell_dict(spell_id: str) -> dict:
    """Get raw spell dictionary by ID.

    Args:
        spell_id: The spell_id to search for

    Returns:
        Raw dictionary from JSON

    Raises:
        ValueError: If spell not found
    """
    _build_spell_cache()

    if spell_id in _spell_cache:
        return _spell_cache[spell_id]

    raise ValueError(f"Spell not found: {spell_id}")


def list_spells_by_type(magic_type: str) -> list[str]:
    """List all spell IDs of a given magic type.

    Args:
        magic_type: "arcane", "divine", or "fairy_glamour"

    Returns:
        List of spell_ids matching the type
    """
    _build_spell_cache()
    return [
        spell_id for spell_id, data in _spell_cache.items()
        if data.get("magic_type") == magic_type
    ]


def list_spells_by_level(level: int, magic_type: Optional[str] = None) -> list[str]:
    """List all spell IDs of a given level.

    Args:
        level: Spell level to filter by
        magic_type: Optional magic type filter

    Returns:
        List of spell_ids at that level
    """
    _build_spell_cache()
    result = []
    for spell_id, data in _spell_cache.items():
        if data.get("level") == level:
            if magic_type is None or data.get("magic_type") == magic_type:
                result.append(spell_id)
    return result


def make_test_character(
    char_id: str = "test_char",
    name: str = "Test Character",
    character_class: str = "Magic-User",
    level: int = 10,
    conditions: Optional[list] = None,
) -> CharacterState:
    """Create a CharacterState for testing.

    Args:
        char_id: Character ID
        name: Character name
        character_class: Class name
        level: Character level
        conditions: Optional list of Condition objects

    Returns:
        CharacterState configured for testing
    """
    return CharacterState(
        character_id=char_id,
        name=name,
        character_class=character_class,
        level=level,
        ability_scores={"STR": 10, "INT": 16, "WIS": 12, "DEX": 10, "CON": 10, "CHA": 10},
        hp_current=30,
        hp_max=30,
        armor_class=10,
        base_speed=40,
        conditions=conditions or [],
    )


def make_test_spell(
    name: str,
    description: str,
    level: int = 1,
    magic_type: MagicType = MagicType.ARCANE,
    duration: str = "Instant",
    range_: str = "30'",
) -> SpellData:
    """Create a synthetic SpellData for pattern testing.

    Use this for unit tests that need to test specific patterns
    without relying on actual Dolmenwood spell data.

    Args:
        name: Spell name
        description: Spell description containing patterns to test
        level: Spell level
        magic_type: Type of magic
        duration: Duration string
        range_: Range string

    Returns:
        SpellData configured for testing
    """
    return SpellData(
        spell_id=f"test_{name.lower().replace(' ', '_')}",
        name=name,
        level=level,
        magic_type=magic_type,
        duration=duration,
        range=range_,
        description=description,
    )
