"""
Spell Registry for Dolmenwood Virtual DM.

Provides a centralized registry for spell lookup and management.
Similar to MonsterRegistry, this provides easy access to spell data
by ID, name, level, or magic type.

Usage:
    # Get the singleton registry
    registry = get_spell_registry()

    # Load spells (usually done at startup)
    registry.load_from_directory()

    # Look up spells
    fireball = registry.get_by_id("fireball")
    healing_spells = registry.get_by_level(1, MagicType.DIVINE)
    all_glamours = registry.get_by_magic_type(MagicType.FAIRY_GLAMOUR)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.narrative.spell_resolver import SpellData, MagicType, RuneMagnitude


logger = logging.getLogger(__name__)


# Singleton instance
_spell_registry: Optional["SpellRegistry"] = None


@dataclass
class SpellLookupResult:
    """Result of a spell lookup operation."""

    found: bool
    spell: Optional[SpellData] = None
    error: str = ""


@dataclass
class SpellListResult:
    """Result of a spell list operation."""

    spells: list[SpellData] = field(default_factory=list)
    count: int = 0


class SpellRegistry:
    """
    Centralized registry for spell data.

    Provides efficient lookup by various criteria and integrates
    with the SpellResolver for spell casting resolution.
    """

    def __init__(self):
        """Initialize an empty spell registry."""
        # Primary storage: spell_id -> SpellData
        self._spells: dict[str, SpellData] = {}

        # Indexes for efficient lookup
        self._by_name: dict[str, SpellData] = {}  # lowercase name -> spell
        self._by_level: dict[tuple[Optional[int], MagicType], list[SpellData]] = {}
        self._by_magic_type: dict[MagicType, list[SpellData]] = {}
        self._by_rune_magnitude: dict[RuneMagnitude, list[SpellData]] = {}

        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if spells have been loaded."""
        return self._loaded

    @property
    def spell_count(self) -> int:
        """Get total number of registered spells."""
        return len(self._spells)

    def load_from_directory(
        self,
        spell_directory: Optional[Path] = None,
    ) -> int:
        """
        Load all spells from a directory.

        Args:
            spell_directory: Path to spell JSON files.
                Defaults to data/content/spells.

        Returns:
            Number of spells loaded
        """
        from src.content_loader.spell_loader import load_all_spells

        result = load_all_spells(spell_directory)

        if result.errors:
            for error in result.errors:
                logger.error(f"Spell loading error: {error}")

        for spell in result.all_spells:
            self.register(spell)

        self._loaded = True
        logger.info(f"Loaded {self.spell_count} spells into registry")
        return self.spell_count

    def register(self, spell: SpellData) -> None:
        """
        Register a spell in the registry.

        Args:
            spell: SpellData to register
        """
        # Primary storage
        self._spells[spell.spell_id] = spell

        # Name index (lowercase for case-insensitive lookup)
        self._by_name[spell.name.lower()] = spell

        # Level + magic type index
        level_key = (spell.level, spell.magic_type)
        if level_key not in self._by_level:
            self._by_level[level_key] = []
        self._by_level[level_key].append(spell)

        # Magic type index
        if spell.magic_type not in self._by_magic_type:
            self._by_magic_type[spell.magic_type] = []
        self._by_magic_type[spell.magic_type].append(spell)

        # Rune magnitude index
        if spell.rune_magnitude:
            if spell.rune_magnitude not in self._by_rune_magnitude:
                self._by_rune_magnitude[spell.rune_magnitude] = []
            self._by_rune_magnitude[spell.rune_magnitude].append(spell)

    def get_by_id(self, spell_id: str) -> SpellLookupResult:
        """
        Look up a spell by its ID.

        Args:
            spell_id: The spell's unique identifier

        Returns:
            SpellLookupResult with the spell if found
        """
        spell = self._spells.get(spell_id)
        if spell:
            return SpellLookupResult(found=True, spell=spell)
        return SpellLookupResult(found=False, error=f"Spell not found: {spell_id}")

    def get_by_name(self, name: str) -> SpellLookupResult:
        """
        Look up a spell by name (case-insensitive).

        Args:
            name: The spell's name

        Returns:
            SpellLookupResult with the spell if found
        """
        spell = self._by_name.get(name.lower())
        if spell:
            return SpellLookupResult(found=True, spell=spell)
        return SpellLookupResult(found=False, error=f"Spell not found: {name}")

    def get_by_level(
        self,
        level: Optional[int],
        magic_type: Optional[MagicType] = None,
    ) -> SpellListResult:
        """
        Get all spells of a specific level.

        Args:
            level: Spell level (None for level-less spells like glamours)
            magic_type: Optional filter by magic type

        Returns:
            SpellListResult with matching spells
        """
        if magic_type:
            key = (level, magic_type)
            spells = self._by_level.get(key, [])
        else:
            # Get all spells of this level across all magic types
            spells = []
            for (lvl, _), spell_list in self._by_level.items():
                if lvl == level:
                    spells.extend(spell_list)

        return SpellListResult(spells=spells, count=len(spells))

    def get_by_magic_type(self, magic_type: MagicType) -> SpellListResult:
        """
        Get all spells of a specific magic type.

        Args:
            magic_type: The magic type to filter by

        Returns:
            SpellListResult with matching spells
        """
        spells = self._by_magic_type.get(magic_type, [])
        return SpellListResult(spells=spells, count=len(spells))

    def get_by_rune_magnitude(self, magnitude: RuneMagnitude) -> SpellListResult:
        """
        Get all runes of a specific magnitude.

        Args:
            magnitude: The rune magnitude (LESSER, GREATER, MIGHTY)

        Returns:
            SpellListResult with matching runes
        """
        spells = self._by_rune_magnitude.get(magnitude, [])
        return SpellListResult(spells=spells, count=len(spells))

    def get_all(self) -> list[SpellData]:
        """
        Get all registered spells.

        Returns:
            List of all SpellData objects
        """
        return list(self._spells.values())

    def get_all_ids(self) -> list[str]:
        """
        Get all registered spell IDs.

        Returns:
            List of spell IDs
        """
        return list(self._spells.keys())

    def search(
        self,
        name_contains: Optional[str] = None,
        description_contains: Optional[str] = None,
        magic_types: Optional[list[MagicType]] = None,
        min_level: Optional[int] = None,
        max_level: Optional[int] = None,
        has_save: Optional[bool] = None,
    ) -> SpellListResult:
        """
        Search spells with multiple criteria.

        Args:
            name_contains: Filter by name substring (case-insensitive)
            description_contains: Filter by description substring
            magic_types: Filter by list of magic types
            min_level: Minimum spell level
            max_level: Maximum spell level
            has_save: Filter by whether spell requires a save

        Returns:
            SpellListResult with matching spells
        """
        results = []

        for spell in self._spells.values():
            # Name filter
            if name_contains:
                if name_contains.lower() not in spell.name.lower():
                    continue

            # Description filter
            if description_contains:
                if description_contains.lower() not in spell.description.lower():
                    continue

            # Magic type filter
            if magic_types:
                if spell.magic_type not in magic_types:
                    continue

            # Level filters
            if min_level is not None:
                if spell.level is None or spell.level < min_level:
                    continue
            if max_level is not None:
                if spell.level is None or spell.level > max_level:
                    continue

            # Save filter
            if has_save is not None:
                spell_has_save = spell.save_type is not None
                if spell_has_save != has_save:
                    continue

            results.append(spell)

        return SpellListResult(spells=results, count=len(results))

    def clear(self) -> None:
        """Clear all registered spells."""
        self._spells.clear()
        self._by_name.clear()
        self._by_level.clear()
        self._by_magic_type.clear()
        self._by_rune_magnitude.clear()
        self._loaded = False

    def register_with_resolver(self, spell_resolver: "SpellResolver") -> int:
        """
        Register all spells with a SpellResolver instance.

        Args:
            spell_resolver: SpellResolver to register spells with

        Returns:
            Number of spells registered
        """
        count = 0
        for spell in self._spells.values():
            try:
                spell_resolver.register_spell(spell)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register spell '{spell.name}': {e}")
        return count


def get_spell_registry() -> SpellRegistry:
    """
    Get the singleton SpellRegistry instance.

    Returns:
        The global SpellRegistry instance
    """
    global _spell_registry
    if _spell_registry is None:
        _spell_registry = SpellRegistry()
    return _spell_registry


def reset_spell_registry() -> None:
    """Reset the singleton SpellRegistry instance."""
    global _spell_registry
    if _spell_registry:
        _spell_registry.clear()
    _spell_registry = None
