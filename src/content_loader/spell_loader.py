"""
Spell Data Loader for Dolmenwood Virtual DM.

Loads spell data from JSON files in the data/content/spells directory
and parses raw text fields (duration, range, description) into structured
mechanical components for the SpellResolver.

JSON File Format:
{
    "_metadata": {
        "source_file": "path/to/source.pdf",
        "pages": [82],
        "content_type": "spells",
        "item_count": 5
    },
    "items": [
        {
            "name": "Crystal Resonance",
            "spell_id": "crystal_resonance",
            "level": 1,
            "magic_type": "arcane",
            "duration": "Special",
            "range": "10'",
            "description": "...",
            "reversible": false,
            "reversed_name": null
        }
    ]
}
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.narrative.spell_resolver import (
    SpellData,
    DurationType,
    RangeType,
    MagicType,
    SpellEffectType,
    RuneMagnitude,
    UsageFrequency,
    LevelScaling,
    LevelScalingType,
    SpellComponent,
)
from src.narrative.intent_parser import SaveType


logger = logging.getLogger(__name__)


# =============================================================================
# RESULT DATACLASSES
# =============================================================================


@dataclass
class SpellFileMetadata:
    """Metadata from a spell JSON file."""

    source_file: str = ""
    pages: list[int] = field(default_factory=list)
    content_type: str = "spells"
    item_count: int = 0
    errors: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class SpellFileLoadResult:
    """Result of loading a single spell JSON file."""

    file_path: Path
    success: bool
    metadata: Optional[SpellFileMetadata] = None
    spells_loaded: int = 0
    spells_failed: int = 0
    errors: list[str] = field(default_factory=list)
    loaded_spells: list[SpellData] = field(default_factory=list)


@dataclass
class SpellDirectoryLoadResult:
    """Result of loading all spell files from a directory."""

    directory: Path
    files_processed: int = 0
    files_successful: int = 0
    files_failed: int = 0
    total_spells_loaded: int = 0
    total_spells_failed: int = 0
    file_results: list[SpellFileLoadResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    all_spells: list[SpellData] = field(default_factory=list)


# =============================================================================
# SPELL PARSER
# =============================================================================


class SpellParser:
    """
    Parses raw spell text fields into structured mechanical components.

    Handles:
    - Duration parsing (turns, rounds, hours, concentration, etc.)
    - Range parsing (self, touch, feet)
    - Save type detection
    - Level scaling detection
    - Usage frequency parsing (for glamours)
    - Rune magnitude parsing
    - Material component parsing
    """

    # Duration patterns
    DURATION_PATTERNS = [
        # "6 Turns" or "1d6 Turns"
        (r"(\d+(?:d\d+)?)\s*turns?", DurationType.TURNS),
        # "1 Round" or "3 Rounds"
        (r"(\d+)\s*rounds?", DurationType.ROUNDS),
        # "1 Hour" or "1d4 Hours"
        (r"(\d+(?:d\d+)?)\s*hours?", DurationType.HOURS),
        # "1 Day" or "1d6 Days"
        (r"(\d+(?:d\d+)?)\s*days?", DurationType.DAYS),
        # "Concentration"
        (r"concentration", DurationType.CONCENTRATION),
        # "Permanent" or "Until dispelled"
        (r"permanent|until dispelled|indefinite", DurationType.PERMANENT),
        # "Instant" or "Instantaneous"
        (r"instant(?:aneous)?", DurationType.INSTANT),
    ]

    # Range patterns
    RANGE_PATTERNS = [
        (r"the caster|self|caster only", RangeType.SELF, None),
        (r"touch", RangeType.TOUCH, None),
        (r"(\d+)'", RangeType.RANGED, "feet"),
        (r"(\d+)\s*feet", RangeType.RANGED, "feet"),
        (r"(\d+)\s*yards?", RangeType.RANGED, "yards"),
    ]

    # Save type patterns
    SAVE_PATTERNS = [
        (r"save\s+(?:vs\.?|versus)\s+doom", SaveType.DOOM),
        (r"save\s+(?:vs\.?|versus)\s+ray", SaveType.RAY),
        (r"save\s+(?:vs\.?|versus)\s+hold", SaveType.HOLD),
        (r"save\s+(?:vs\.?|versus)\s+blast", SaveType.BLAST),
        (r"save\s+(?:vs\.?|versus)\s+spell", SaveType.SPELL),
    ]

    # Usage frequency patterns (for glamours)
    USAGE_PATTERNS = [
        (r"once per round", UsageFrequency.ONCE_PER_ROUND),
        (r"once per turn", UsageFrequency.ONCE_PER_TURN),
        (r"once per day per subject", UsageFrequency.ONCE_PER_DAY_PER_SUBJECT),
        (r"once per day", UsageFrequency.ONCE_PER_DAY),
        (r"at will", UsageFrequency.AT_WILL),
    ]

    # Level scaling patterns
    LEVEL_SCALING_PATTERNS = [
        # "1 Turn per Level" or "+1 Turn per Level"
        (r"\+?\s*(\d+)\s*turns?\s*per\s*level", LevelScalingType.DURATION, "turns"),
        # "1 Round per Level"
        (r"\+?\s*(\d+)\s*rounds?\s*per\s*level", LevelScalingType.DURATION, "rounds"),
        # "1d6 per Level" or "one die per Level" (damage)
        (r"(\d+)?d(\d+)\s*per\s*level", LevelScalingType.DAMAGE, "dice"),
        # "one target per Level" or "1 target per Level"
        (r"(?:one|1)\s*(?:target|creature)s?\s*per\s*level", LevelScalingType.TARGETS, None),
        # "one shard per Level" or "one stream per Level"
        (r"(?:one|1)\s*(?:shard|stream|projectile)s?\s*per\s*level", LevelScalingType.PROJECTILES, None),
        # "additional per 3 Levels"
        (r"additional\s*per\s*(\d+)\s*levels?", LevelScalingType.PROJECTILES, "per_n"),
    ]

    def parse_duration(self, duration_text: str) -> tuple[DurationType, Optional[str], bool]:
        """
        Parse duration text into structured components.

        Args:
            duration_text: Raw duration text (e.g., "6 Turns + 1 Turn per Level")

        Returns:
            Tuple of (duration_type, duration_value, duration_per_level)
        """
        text_lower = duration_text.lower()
        duration_type = DurationType.SPECIAL
        duration_value = None
        per_level = "per level" in text_lower

        for pattern, dtype in self.DURATION_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                duration_type = dtype
                if match.groups():
                    duration_value = match.group(1)
                break

        # Handle "Special" duration
        if "special" in text_lower:
            duration_type = DurationType.SPECIAL

        return duration_type, duration_value, per_level

    def parse_range(self, range_text: str) -> tuple[RangeType, Optional[int]]:
        """
        Parse range text into structured components.

        Args:
            range_text: Raw range text (e.g., "60'" or "Touch")

        Returns:
            Tuple of (range_type, range_feet)
        """
        text_lower = range_text.lower()

        for pattern, rtype, unit in self.RANGE_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                if rtype == RangeType.RANGED and match.groups():
                    feet = int(match.group(1))
                    if unit == "yards":
                        feet *= 3
                    return rtype, feet
                return rtype, None

        return RangeType.RANGED, None

    def parse_save_type(self, description: str) -> tuple[Optional[SaveType], bool]:
        """
        Parse save type from spell description.

        Args:
            description: Spell description text

        Returns:
            Tuple of (save_type, save_negates)
        """
        text_lower = description.lower()

        for pattern, save_type in self.SAVE_PATTERNS:
            if re.search(pattern, text_lower):
                # Check if save negates the effect
                save_negates = bool(re.search(
                    r"save.*negates|negated.*save|save.*avoid|avoid.*save",
                    text_lower
                ))
                return save_type, save_negates

        return None, False

    def parse_level_scaling(self, text: str) -> list[LevelScaling]:
        """
        Parse level scaling from duration or description text.

        Args:
            text: Text to parse for level scaling

        Returns:
            List of LevelScaling objects
        """
        text_lower = text.lower()
        scalings = []

        for pattern, scaling_type, info in self.LEVEL_SCALING_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                scaling = LevelScaling(
                    scaling_type=scaling_type,
                    base_value=1,
                    per_levels=1,
                    description=match.group(0),
                )
                if info == "per_n" and match.groups():
                    scaling.per_levels = int(match.group(1))
                scalings.append(scaling)

        return scalings

    def parse_usage_frequency(self, text: str) -> Optional[UsageFrequency]:
        """
        Parse usage frequency from spell description (for glamours).

        Args:
            text: Spell description

        Returns:
            UsageFrequency enum value or None
        """
        text_lower = text.lower()

        for pattern, frequency in self.USAGE_PATTERNS:
            if re.search(pattern, text_lower):
                return frequency

        return None

    def parse_target_restrictions(self, description: str) -> dict[str, Any]:
        """
        Parse target restrictions from spell description.

        Args:
            description: Spell description

        Returns:
            Dict with max_target_level, max_target_hd, affects_living_only
        """
        text_lower = description.lower()
        restrictions = {
            "max_target_level": None,
            "max_target_hd": None,
            "affects_living_only": False,
        }

        # "Level X or lower" or "X HD or fewer"
        level_match = re.search(r"level\s+(\d+)\s+or\s+(?:lower|less)", text_lower)
        if level_match:
            restrictions["max_target_level"] = int(level_match.group(1))

        hd_match = re.search(r"(\d+)\s*hd?\s+or\s+(?:fewer|less)", text_lower)
        if hd_match:
            restrictions["max_target_hd"] = int(hd_match.group(1))

        # "living creatures only" or "affects only living"
        if re.search(r"living\s+(creatures?|beings?)\s+only|only\s+(?:affects?|works?\s+on)\s+living", text_lower):
            restrictions["affects_living_only"] = True

        return restrictions

    def parse_concentration(self, description: str) -> tuple[bool, bool, bool]:
        """
        Parse concentration requirements from description.

        Args:
            description: Spell description

        Returns:
            Tuple of (requires_concentration, allows_movement, allows_actions)
        """
        text_lower = description.lower()

        requires_concentration = bool(re.search(
            r"concentration|must concentrate|concentrating",
            text_lower
        ))

        if not requires_concentration:
            return False, True, True

        allows_movement = not bool(re.search(
            r"cannot move|must remain stationary|immobile while",
            text_lower
        ))

        allows_actions = not bool(re.search(
            r"cannot take (?:other )?actions|cannot attack|no other actions",
            text_lower
        ))

        return requires_concentration, allows_movement, allows_actions

    def parse_components(self, description: str) -> list[SpellComponent]:
        """
        Parse material components from spell description.

        Args:
            description: Spell description

        Returns:
            List of SpellComponent objects
        """
        text_lower = description.lower()
        components = []

        # Pattern: "X gp Y" or "worth at least X gp"
        value_patterns = [
            r"(\d+)\s*gp\s+(\w+)",  # "50gp crystal"
            r"(\w+)\s+(?:\()?(?:worth\s+)?(?:at\s+least\s+)?(\d+)\s*gp",  # "crystal worth 50gp"
        ]

        for pattern in value_patterns:
            for match in re.finditer(pattern, text_lower):
                groups = match.groups()
                try:
                    if groups[0].isdigit():
                        value = int(groups[0])
                        comp_type = groups[1]
                    else:
                        comp_type = groups[0]
                        value = int(groups[1])

                    consumed = "consumed" in text_lower or "vanishes" in text_lower
                    destruction_chance = 0.0
                    if "1-in-20" in text_lower:
                        destruction_chance = 0.05

                    components.append(SpellComponent(
                        component_type=comp_type,
                        min_value_gp=value,
                        consumed=consumed,
                        destruction_chance=destruction_chance,
                    ))
                except (ValueError, IndexError):
                    continue

        return components


# =============================================================================
# SPELL DATA LOADER
# =============================================================================


class SpellDataLoader:
    """
    Loads spell data from JSON files and converts to SpellData objects.

    Usage:
        loader = SpellDataLoader()

        # Load all spells from directory
        result = loader.load_directory(Path("data/content/spells"))

        # Or load a single file
        result = loader.load_file(Path("data/content/spells/arcane_level_1_1.json"))
    """

    # Magic type mapping from JSON values
    MAGIC_TYPE_MAP = {
        "arcane": MagicType.ARCANE,
        "divine": MagicType.DIVINE,
        "holy": MagicType.DIVINE,  # Alias
        "fairy_glamour": MagicType.FAIRY_GLAMOUR,
        "glamour": MagicType.FAIRY_GLAMOUR,  # Alias
        "rune": MagicType.RUNE,
        "knack": MagicType.KNACK,
    }

    def __init__(self):
        """Initialize the spell loader."""
        self._parser = SpellParser()

    def load_file(self, file_path: Path) -> SpellFileLoadResult:
        """
        Load spells from a single JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            SpellFileLoadResult with loaded spells and any errors
        """
        result = SpellFileLoadResult(file_path=file_path, success=False)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result.errors.append(f"JSON parse error: {e}")
            return result
        except FileNotFoundError:
            result.errors.append(f"File not found: {file_path}")
            return result
        except Exception as e:
            result.errors.append(f"Error reading file: {e}")
            return result

        # Parse metadata
        metadata_dict = data.get("_metadata", {})
        result.metadata = SpellFileMetadata(
            source_file=metadata_dict.get("source_file", ""),
            pages=metadata_dict.get("pages", []),
            content_type=metadata_dict.get("content_type", "spells"),
            item_count=metadata_dict.get("item_count", 0),
            errors=metadata_dict.get("errors", []),
            note=metadata_dict.get("note", ""),
        )

        # Parse spell items
        items = data.get("items", [])
        for item in items:
            try:
                spell = self._parse_spell_item(item, file_path.name)
                if spell:
                    result.loaded_spells.append(spell)
                    result.spells_loaded += 1
            except Exception as e:
                result.errors.append(f"Error parsing spell '{item.get('name', 'unknown')}': {e}")
                result.spells_failed += 1

        result.success = result.spells_failed == 0
        return result

    def load_directory(self, directory: Path) -> SpellDirectoryLoadResult:
        """
        Load all spell JSON files from a directory.

        Args:
            directory: Path to the directory containing spell JSON files

        Returns:
            SpellDirectoryLoadResult with all loaded spells
        """
        result = SpellDirectoryLoadResult(directory=directory)

        if not directory.exists():
            result.errors.append(f"Directory not found: {directory}")
            return result

        if not directory.is_dir():
            result.errors.append(f"Path is not a directory: {directory}")
            return result

        # Find all JSON files
        json_files = sorted(directory.glob("*.json"))
        result.files_processed = len(json_files)

        for json_file in json_files:
            file_result = self.load_file(json_file)
            result.file_results.append(file_result)

            if file_result.success:
                result.files_successful += 1
            else:
                result.files_failed += 1

            result.total_spells_loaded += file_result.spells_loaded
            result.total_spells_failed += file_result.spells_failed
            result.all_spells.extend(file_result.loaded_spells)

        return result

    def _parse_spell_item(self, item: dict[str, Any], source_file: str) -> Optional[SpellData]:
        """
        Parse a single spell item from JSON into a SpellData object.

        Args:
            item: Dict containing spell data
            source_file: Name of the source JSON file

        Returns:
            SpellData object or None if parsing fails
        """
        # Required fields
        spell_id = item.get("spell_id", "")
        name = item.get("name", "")
        if not spell_id or not name:
            logger.warning(f"Spell missing id or name: {item}")
            return None

        # Magic type
        magic_type_str = item.get("magic_type", "arcane").lower()
        magic_type = self.MAGIC_TYPE_MAP.get(magic_type_str, MagicType.ARCANE)

        # Level (None for glamours)
        level = item.get("level")
        if level == "" or level == "N/A":
            level = None

        # Parse rune magnitude from level if it's a string like "lesser", "greater", "mighty"
        rune_magnitude = None
        if isinstance(level, str):
            level_lower = level.lower()
            if level_lower == "lesser":
                rune_magnitude = RuneMagnitude.LESSER
                level = None
            elif level_lower == "greater":
                rune_magnitude = RuneMagnitude.GREATER
                level = None
            elif level_lower == "mighty":
                rune_magnitude = RuneMagnitude.MIGHTY
                level = None

        # Raw text fields
        duration_raw = item.get("duration", "Instant")
        range_raw = item.get("range", "Self")
        description = item.get("description", "")

        # Parse structured fields
        duration_type, duration_value, duration_per_level = self._parser.parse_duration(duration_raw)
        range_type, range_feet = self._parser.parse_range(range_raw)
        save_type, save_negates = self._parser.parse_save_type(description)
        level_scaling = self._parser.parse_level_scaling(duration_raw + " " + description)
        usage_frequency = self._parser.parse_usage_frequency(description)
        target_restrictions = self._parser.parse_target_restrictions(description)
        requires_conc, allows_move, allows_actions = self._parser.parse_concentration(description)
        components = self._parser.parse_components(description)

        return SpellData(
            spell_id=spell_id,
            name=name,
            level=level,
            magic_type=magic_type,
            duration=duration_raw,
            range=range_raw,
            description=description,
            reversible=item.get("reversible", False),
            reversed_name=item.get("reversed_name"),
            # Parsed fields
            duration_type=duration_type,
            duration_value=duration_value,
            duration_per_level=duration_per_level,
            range_type=range_type,
            range_feet=range_feet,
            save_type=save_type,
            save_negates=save_negates,
            level_scaling=level_scaling,
            parsed_usage_frequency=usage_frequency,
            rune_magnitude=rune_magnitude,
            requires_concentration=requires_conc,
            concentration_allows_movement=allows_move,
            concentration_allows_actions=allows_actions,
            required_components=components,
            # Target restrictions
            max_target_level=target_restrictions.get("max_target_level"),
            max_target_hd=target_restrictions.get("max_target_hd"),
            affects_living_only=target_restrictions.get("affects_living_only", False),
            # Source
            source_book=source_file,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def load_all_spells(
    spell_directory: Optional[Path] = None,
) -> SpellDirectoryLoadResult:
    """
    Convenience function to load all spells from the default directory.

    Args:
        spell_directory: Optional custom directory path.
            Defaults to data/content/spells relative to project root.

    Returns:
        SpellDirectoryLoadResult with all loaded spells
    """
    if spell_directory is None:
        # Default to project's data directory
        spell_directory = Path(__file__).parent.parent.parent / "data" / "content" / "spells"

    loader = SpellDataLoader()
    return loader.load_directory(spell_directory)


def register_spells_with_resolver(
    spells: list[SpellData],
    spell_resolver: Any,
) -> int:
    """
    Register a list of spells with a SpellResolver instance.

    Args:
        spells: List of SpellData objects to register
        spell_resolver: SpellResolver instance with register_spell method

    Returns:
        Number of spells registered
    """
    count = 0
    for spell in spells:
        try:
            spell_resolver.register_spell(spell)
            count += 1
        except Exception as e:
            logger.error(f"Failed to register spell '{spell.name}': {e}")
    return count
