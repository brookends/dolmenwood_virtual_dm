"""
Monster Registry for Dolmenwood Virtual DM.

Provides fast in-memory lookup of monsters by ID or name,
and conversion to StatBlock for combat use.

For NPCs without explicit stat blocks, delegates to NPCGenerator
to auto-generate stats from descriptions like "level 4 breggle fighter".
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.data_models import (
    DiceRoller,
    Monster,
    MonsterSaves,
    StatBlock,
    Combatant,
)

logger = logging.getLogger(__name__)


@dataclass
class MonsterLookupResult:
    """Result of a monster lookup operation."""

    monster: Optional[Monster] = None
    found: bool = False
    error: Optional[str] = None
    source_file: Optional[str] = None


@dataclass
class StatBlockResult:
    """Result of converting a monster/NPC to a StatBlock."""

    stat_block: Optional[StatBlock] = None
    source_type: str = ""  # "monster", "npc_generated", "npc_data"
    source_id: str = ""
    success: bool = False
    error: Optional[str] = None


@dataclass
class NPCStatRequest:
    """
    Request for NPC stat generation from a description.

    NPCs can be specified in hex/location data as simple descriptions
    like "level 4 breggle fighter" or "3rd level human cleric".
    """

    description: str
    name: Optional[str] = None
    # Additional overrides
    hp_override: Optional[int] = None
    ac_override: Optional[int] = None
    morale_override: Optional[int] = None


class MonsterRegistry:
    """
    In-memory registry of all Dolmenwood monsters.

    Loads monster data from JSON files and provides fast lookup
    by monster_id or name. Also handles NPC stat generation
    for NPCs described by text (e.g., "level 4 fighter").

    Usage:
        # Initialize and load monsters
        registry = MonsterRegistry()
        registry.load_from_directory(Path("data/content/monsters"))

        # Or use the convenience method
        registry = MonsterRegistry.create_default()

        # Look up a monster
        result = registry.get_monster("goblin")
        if result.found:
            monster = result.monster
            stat_block = monster.to_stat_block()

        # Get stat block directly
        stat_result = registry.get_stat_block("devil_goat")
        if stat_result.success:
            combatant = Combatant(
                combatant_id="enemy_1",
                name="Devil Goat",
                side="enemy",
                stat_block=stat_result.stat_block
            )

        # Generate NPC stats from description
        stat_result = registry.get_npc_stat_block(
            NPCStatRequest(
                description="level 4 breggle fighter",
                name="Guard Captain"
            )
        )
    """

    # Default data directory relative to project root
    DEFAULT_DATA_DIR = Path("data/content/monsters")

    def __init__(self):
        """Initialize an empty monster registry."""
        # Primary index: monster_id -> Monster
        self._monsters: dict[str, Monster] = {}

        # Secondary index: lowercase name -> monster_id
        self._name_index: dict[str, str] = {}

        # Track source files for each monster
        self._source_files: dict[str, str] = {}

        # Lazy-loaded NPC generator
        self._npc_generator: Optional[Any] = None

        # Load statistics
        self._load_stats = {
            "files_loaded": 0,
            "monsters_loaded": 0,
            "errors": [],
        }

    @classmethod
    def create_default(cls, data_dir: Optional[Path] = None) -> "MonsterRegistry":
        """
        Create a MonsterRegistry and load from the default data directory.

        Args:
            data_dir: Override default data directory path

        Returns:
            Initialized MonsterRegistry with all monsters loaded
        """
        registry = cls()

        if data_dir is None:
            # Find project root by looking for data directory
            current = Path(__file__).resolve()
            for parent in current.parents:
                candidate = parent / "data" / "content" / "monsters"
                if candidate.exists():
                    data_dir = candidate
                    break

            if data_dir is None:
                # Fallback to relative path
                data_dir = Path("data/content/monsters")

        registry.load_from_directory(data_dir)
        return registry

    def load_from_directory(self, directory: Path) -> dict[str, Any]:
        """
        Load all monster JSON files from a directory.

        Args:
            directory: Path to directory containing monster JSON files

        Returns:
            Dictionary with load statistics
        """
        if not directory.exists():
            error = f"Monster directory not found: {directory}"
            logger.error(error)
            self._load_stats["errors"].append(error)
            return self._load_stats

        json_files = sorted(directory.glob("*.json"))
        logger.info(f"Found {len(json_files)} monster JSON files in {directory}")

        for json_file in json_files:
            self._load_file(json_file)

        logger.info(
            f"Loaded {self._load_stats['monsters_loaded']} monsters "
            f"from {self._load_stats['files_loaded']} files"
        )

        return self._load_stats

    def _load_file(self, file_path: Path) -> None:
        """Load monsters from a single JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            error = f"Invalid JSON in {file_path}: {e}"
            logger.error(error)
            self._load_stats["errors"].append(error)
            return
        except Exception as e:
            error = f"Error reading {file_path}: {e}"
            logger.error(error)
            self._load_stats["errors"].append(error)
            return

        items = data.get("items", [])
        if not items:
            return

        self._load_stats["files_loaded"] += 1

        for item in items:
            try:
                monster = self._parse_monster(item)
                self._add_monster(monster, str(file_path))
                self._load_stats["monsters_loaded"] += 1
            except Exception as e:
                error = f"Error parsing monster {item.get('name', '?')} from {file_path}: {e}"
                logger.warning(error)
                self._load_stats["errors"].append(error)

    def _parse_monster(self, item: dict[str, Any]) -> Monster:
        """Parse a monster item from JSON into a Monster dataclass."""
        return Monster(
            # Core identification
            name=item.get("name", "Unknown Monster"),
            monster_id=item.get(
                "monster_id", item.get("name", "unknown").lower().replace(" ", "_")
            ),
            # Combat statistics
            armor_class=item.get("armor_class", 10),
            hit_dice=item.get("hit_dice", "1d8"),
            hp=item.get("hp", 4),
            level=item.get("level", 1),
            morale=item.get("morale", 7),
            # Movement
            movement=item.get("movement", "40'"),
            speed=item.get("speed", 40),
            burrow_speed=item.get("burrow_speed"),
            fly_speed=item.get("fly_speed"),
            swim_speed=item.get("swim_speed"),
            # Combat
            attacks=item.get("attacks", []),
            damage=item.get("damage", []),
            # Saving throws
            save_doom=item.get("save_doom", 14),
            save_ray=item.get("save_ray", 15),
            save_hold=item.get("save_hold", 16),
            save_blast=item.get("save_blast", 17),
            save_spell=item.get("save_spell", 18),
            saves_as=item.get("saves_as"),
            # Treasure
            treasure_type=item.get("treasure_type"),
            hoard=item.get("hoard"),
            possessions=item.get("possessions"),
            # Classification
            size=item.get("size", "Medium"),
            monster_type=item.get("monster_type", "Mortal"),
            sentience=item.get("sentience", "Sentient"),
            alignment=item.get("alignment", "Neutral"),
            intelligence=item.get("intelligence"),
            # Abilities
            special_abilities=item.get("special_abilities", []),
            immunities=item.get("immunities", []),
            resistances=item.get("resistances", []),
            vulnerabilities=item.get("vulnerabilities", []),
            # Description and behavior
            description=item.get("description"),
            behavior=item.get("behavior"),
            speech=item.get("speech"),
            traits=item.get("traits", []),
            # Encounter information
            number_appearing=item.get("number_appearing"),
            lair_percentage=item.get("lair_percentage"),
            encounter_scenarios=item.get("encounter_scenarios", []),
            lair_descriptions=item.get("lair_descriptions", []),
            # Experience and habitat
            xp_value=item.get("xp_value", 0),
            habitat=item.get("habitat", []),
            # Source tracking
            page_reference=item.get("page_reference", ""),
        )

    def _add_monster(self, monster: Monster, source_file: str) -> None:
        """Add a monster to the registry indexes."""
        monster_id = monster.monster_id

        # Check for duplicates
        if monster_id in self._monsters:
            logger.warning(
                f"Duplicate monster_id '{monster_id}': "
                f"replacing {self._source_files.get(monster_id)} with {source_file}"
            )

        # Add to primary index
        self._monsters[monster_id] = monster
        self._source_files[monster_id] = source_file

        # Add to name index (lowercase for case-insensitive lookup)
        name_key = monster.name.lower()
        if name_key not in self._name_index:
            self._name_index[name_key] = monster_id

    def get_monster(self, monster_id: str) -> MonsterLookupResult:
        """
        Look up a monster by its ID.

        Args:
            monster_id: The monster's unique identifier (e.g., "goblin", "devil_goat")

        Returns:
            MonsterLookupResult with the monster if found
        """
        monster = self._monsters.get(monster_id)
        if monster:
            return MonsterLookupResult(
                monster=monster,
                found=True,
                source_file=self._source_files.get(monster_id),
            )

        return MonsterLookupResult(
            found=False,
            error=f"Monster not found: {monster_id}",
        )

    def get_monster_by_name(self, name: str) -> MonsterLookupResult:
        """
        Look up a monster by its display name (case-insensitive).

        Args:
            name: The monster's name (e.g., "Goblin", "Devil Goat")

        Returns:
            MonsterLookupResult with the monster if found
        """
        name_key = name.lower()
        monster_id = self._name_index.get(name_key)

        if monster_id:
            return self.get_monster(monster_id)

        return MonsterLookupResult(
            found=False,
            error=f"Monster not found by name: {name}",
        )

    def search_monsters(self, query: str, limit: int = 10) -> list[Monster]:
        """
        Search for monsters matching a query string.

        Searches monster names and IDs for partial matches.

        Args:
            query: Search string
            limit: Maximum number of results to return

        Returns:
            List of matching Monster objects
        """
        query_lower = query.lower()
        matches = []

        for monster_id, monster in self._monsters.items():
            # Check if query matches id or name
            if query_lower in monster_id.lower() or query_lower in monster.name.lower():
                matches.append(monster)
                if len(matches) >= limit:
                    break

        return matches

    def get_monsters_by_type(self, monster_type: str) -> list[Monster]:
        """
        Get all monsters of a specific type.

        Args:
            monster_type: Type like "Undead", "Fairy", "Mortal", etc.

        Returns:
            List of matching Monster objects
        """
        type_lower = monster_type.lower()
        return [m for m in self._monsters.values() if m.monster_type.lower() == type_lower]

    def get_monsters_by_level(self, level: int) -> list[Monster]:
        """
        Get all monsters of a specific level/hit dice.

        Args:
            level: Monster level (hit dice count)

        Returns:
            List of matching Monster objects
        """
        return [m for m in self._monsters.values() if m.level == level]

    def get_stat_block(self, monster_id: str) -> StatBlockResult:
        """
        Get a StatBlock for a monster, ready for combat use.

        Creates a new StatBlock with rolled HP based on hit dice.

        Args:
            monster_id: The monster's unique identifier

        Returns:
            StatBlockResult with the StatBlock if successful
        """
        lookup = self.get_monster(monster_id)
        if not lookup.found:
            return StatBlockResult(
                success=False,
                error=lookup.error,
            )

        monster = lookup.monster
        stat_block = self._create_stat_block_from_monster(monster)

        return StatBlockResult(
            stat_block=stat_block,
            source_type="monster",
            source_id=monster_id,
            success=True,
        )

    def _create_stat_block_from_monster(self, monster: Monster, roll_hp: bool = True) -> StatBlock:
        """
        Create a StatBlock from a Monster, optionally rolling HP.

        Args:
            monster: The Monster to convert
            roll_hp: If True, roll HP from hit dice; if False, use monster.hp

        Returns:
            StatBlock ready for combat
        """
        # Roll HP if requested
        if roll_hp:
            hp_roll = DiceRoller.roll(monster.hit_dice, f"HP for {monster.name}")
            hp = hp_roll.total
        else:
            hp = monster.hp

        # Parse attacks into StatBlock format
        attack_list = []
        for i, atk_str in enumerate(monster.attacks):
            damage = monster.damage[i] if i < len(monster.damage) else "1d6"
            bonus = self._parse_attack_bonus(atk_str, monster.level)
            attack_list.append(
                {
                    "name": atk_str,
                    "damage": damage,
                    "bonus": bonus,
                }
            )

        return StatBlock(
            armor_class=monster.armor_class,
            hit_dice=monster.hit_dice,
            hp_current=hp,
            hp_max=hp,
            movement=monster.speed,
            attacks=attack_list,
            morale=monster.morale,
            save_as=monster.saves_as or f"Monster {monster.level}",
            special_abilities=monster.special_abilities.copy(),
        )

    def _parse_attack_bonus(self, attack_str: str, default_level: int) -> int:
        """
        Parse attack bonus from an attack string like "Claw (+2, 1d6)".

        Args:
            attack_str: Attack description string
            default_level: Fallback to monster level if no bonus found

        Returns:
            Attack bonus as integer
        """
        # Try to find (+N) or (+N,
        match = re.search(r"\(\+?(-?\d+)", attack_str)
        if match:
            return int(match.group(1))
        return default_level

    def get_npc_stat_block(self, request: NPCStatRequest) -> StatBlockResult:
        """
        Generate a StatBlock for an NPC from a text description.

        Uses NPCGenerator to create stats for descriptions like
        "level 4 breggle fighter" or "3rd level human cleric".

        Args:
            request: NPCStatRequest with the description and optional overrides

        Returns:
            StatBlockResult with the generated StatBlock
        """
        # Lazy-load NPCGenerator to avoid circular imports
        if self._npc_generator is None:
            try:
                from src.npc.npc_generator import NPCGenerator

                self._npc_generator = NPCGenerator()
            except ImportError as e:
                return StatBlockResult(
                    success=False,
                    error=f"Could not import NPCGenerator: {e}",
                )

        # Generate the NPC
        result = self._npc_generator.generate_from_description(
            request.description,
            name=request.name,
        )

        if not result.success:
            return StatBlockResult(
                success=False,
                error="; ".join(result.errors),
            )

        character = result.character

        # Build attack list from character class
        attacks = self._build_npc_attacks(character)

        # Create StatBlock from CharacterState
        hp = request.hp_override or character.hp_current
        ac = request.ac_override or character.armor_class
        morale = request.morale_override or getattr(character, "morale", 7)

        stat_block = StatBlock(
            armor_class=ac,
            hit_dice=f"{character.level}d8",  # Approximate
            hp_current=hp,
            hp_max=character.hp_max,
            movement=character.base_speed,
            attacks=attacks,
            morale=morale,
            save_as=f"{character.character_class.capitalize()} {character.level}",
            special_abilities=[],  # Could add class abilities here
        )

        return StatBlockResult(
            stat_block=stat_block,
            source_type="npc_generated",
            source_id=character.character_id,
            success=True,
        )

    def _build_npc_attacks(self, character) -> list[dict]:
        """Build attack list for an NPC based on their class."""
        # Simple default attack based on class
        attack_bonus = character.attack_bonus or character.level

        class_weapons = {
            "fighter": {"name": "Sword", "damage": "1d8"},
            "knight": {"name": "Lance", "damage": "1d10"},
            "hunter": {"name": "Bow", "damage": "1d6"},
            "thief": {"name": "Dagger", "damage": "1d4"},
            "cleric": {"name": "Mace", "damage": "1d6"},
            "friar": {"name": "Staff", "damage": "1d4"},
            "magician": {"name": "Staff", "damage": "1d4"},
            "bard": {"name": "Rapier", "damage": "1d6"},
            "enchanter": {"name": "Dagger", "damage": "1d4"},
        }

        weapon = class_weapons.get(
            character.character_class.lower(), {"name": "Weapon", "damage": "1d6"}
        )

        return [
            {
                "name": f"{weapon['name']} (+{attack_bonus})",
                "damage": weapon["damage"],
                "bonus": attack_bonus,
            }
        ]

    def create_combatant(
        self,
        monster_id: str,
        combatant_id: str,
        side: str = "enemy",
        name_override: Optional[str] = None,
        roll_hp: bool = True,
    ) -> Optional[Combatant]:
        """
        Create a Combatant from a monster, ready for combat.

        Convenience method that combines lookup, stat block creation,
        and Combatant initialization.

        Args:
            monster_id: The monster's unique identifier
            combatant_id: Unique ID for this combatant instance
            side: "party" or "enemy"
            name_override: Optional custom name for this instance
            roll_hp: If True, roll HP from hit dice

        Returns:
            Combatant instance or None if monster not found
        """
        lookup = self.get_monster(monster_id)
        if not lookup.found:
            logger.warning(f"Cannot create combatant: {lookup.error}")
            return None

        monster = lookup.monster
        stat_block = self._create_stat_block_from_monster(monster, roll_hp=roll_hp)

        return Combatant(
            combatant_id=combatant_id,
            name=name_override or monster.name,
            side=side,
            stat_block=stat_block,
        )

    def create_combatant_from_npc(
        self,
        request: NPCStatRequest,
        combatant_id: str,
        side: str = "enemy",
    ) -> Optional[Combatant]:
        """
        Create a Combatant from an NPC description.

        Args:
            request: NPCStatRequest with the description
            combatant_id: Unique ID for this combatant instance
            side: "party" or "enemy"

        Returns:
            Combatant instance or None if generation failed
        """
        result = self.get_npc_stat_block(request)
        if not result.success:
            logger.warning(f"Cannot create NPC combatant: {result.error}")
            return None

        name = request.name or f"NPC ({request.description})"

        return Combatant(
            combatant_id=combatant_id,
            name=name,
            side=side,
            stat_block=result.stat_block,
        )

    def roll_number_appearing(self, monster_id: str) -> int:
        """
        Roll the number appearing for a monster type.

        Args:
            monster_id: The monster's unique identifier

        Returns:
            Number of monsters appearing (minimum 1)
        """
        lookup = self.get_monster(monster_id)
        if not lookup.found:
            return 1

        monster = lookup.monster
        if not monster.number_appearing:
            return 1

        try:
            roll = DiceRoller.roll(monster.number_appearing, f"Number appearing: {monster.name}")
            return max(1, roll.total)
        except Exception:
            return 1

    def get_all_monster_ids(self) -> list[str]:
        """Get list of all loaded monster IDs."""
        return list(self._monsters.keys())

    def get_all_monsters(self) -> list[Monster]:
        """Get list of all loaded monsters."""
        return list(self._monsters.values())

    def __len__(self) -> int:
        """Return the number of loaded monsters."""
        return len(self._monsters)

    def __contains__(self, monster_id: str) -> bool:
        """Check if a monster ID is in the registry."""
        return monster_id in self._monsters


# Module-level singleton for convenience
_default_registry: Optional[MonsterRegistry] = None


def get_monster_registry() -> MonsterRegistry:
    """
    Get the default MonsterRegistry singleton.

    Creates and loads the registry on first call.

    Returns:
        The shared MonsterRegistry instance
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = MonsterRegistry.create_default()
    return _default_registry


def reset_monster_registry() -> None:
    """Reset the default registry singleton (useful for testing)."""
    global _default_registry
    _default_registry = None
