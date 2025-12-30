"""
Table management and resolution system for the Dolmenwood Virtual DM.

Provides centralized access to all game tables, handles table resolution
including nested rolls, and manages context-sensitive modifiers.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import json
from pathlib import Path

from src.data_models import DiceRoller
from src.tables.table_types import (
    TableCategory,
    DieType,
    TableEntry,
    DolmenwoodTable,
    TableResult,
    TableContext,
    SkillCheck,
)


class TableManager:
    """
    Central manager for all game tables.

    Handles table registration, lookup, and resolution including
    context-sensitive modifiers and nested table rolls.
    """

    def __init__(self):
        # Tables indexed by ID
        self._tables: dict[str, DolmenwoodTable] = {}

        # Tables indexed by category
        self._by_category: dict[TableCategory, list[str]] = {cat: [] for cat in TableCategory}

        # Hex-specific tables
        self._hex_tables: dict[str, dict[str, str]] = {}  # hex_id -> {name: table_id}

        # Dungeon-specific tables
        self._dungeon_tables: dict[str, dict[str, str]] = {}

        # Settlement-specific tables
        self._settlement_tables: dict[str, dict[str, str]] = {}

        # Register built-in tables
        self._register_builtin_tables()

    def _register_builtin_tables(self) -> None:
        """Register the built-in game tables."""
        # Reaction table (2d6)
        self.register_table(self._create_reaction_table())

        # Morale modifier table
        self.register_table(self._create_morale_situation_table())

        # Surprise table
        self.register_table(self._create_surprise_table())

        # Generic encounter type table
        self.register_table(self._create_encounter_type_table())

        # Weather tables by season
        for season in ["spring", "summer", "autumn", "winter"]:
            self.register_table(self._create_weather_table(season))

    def _create_reaction_table(self) -> DolmenwoodTable:
        """Create the standard 2d6 reaction table."""
        return DolmenwoodTable(
            table_id="reaction_2d6",
            name="Reaction Roll",
            category=TableCategory.REACTION,
            die_type=DieType.D6,
            num_dice=2,
            description="Roll 2d6 + CHA modifier when encountering creatures",
            source_reference="OSE Core Rules",
            entries=[
                TableEntry(
                    roll_min=2,
                    roll_max=2,
                    title="Hostile, attacks",
                    result="The creature attacks immediately.",
                    mechanical_effect="immediate_attack",
                ),
                TableEntry(
                    roll_min=3,
                    roll_max=5,
                    title="Hostile",
                    result="The creature is hostile and may attack.",
                    mechanical_effect="hostile",
                ),
                TableEntry(
                    roll_min=6,
                    roll_max=8,
                    title="Uncertain",
                    result="The creature is confused or uncertain. It may be influenced by actions.",
                    mechanical_effect="uncertain",
                ),
                TableEntry(
                    roll_min=9,
                    roll_max=11,
                    title="Indifferent",
                    result="The creature is not interested in attacking. It may consider offers.",
                    mechanical_effect="indifferent",
                ),
                TableEntry(
                    roll_min=12,
                    roll_max=12,
                    title="Friendly",
                    result="The creature is friendly and helpful.",
                    mechanical_effect="friendly",
                ),
            ],
        )

    def _create_morale_situation_table(self) -> DolmenwoodTable:
        """Create morale situational modifier reference table."""
        return DolmenwoodTable(
            table_id="morale_modifiers",
            name="Morale Situational Modifiers",
            category=TableCategory.MORALE,
            die_type=DieType.D6,
            num_dice=1,
            description="Modifiers to apply to morale checks based on situation",
            entries=[
                TableEntry(
                    roll_min=1,
                    roll_max=1,
                    title="First ally killed",
                    result="-1 to morale",
                    modifier=-1,
                ),
                TableEntry(
                    roll_min=2,
                    roll_max=2,
                    title="Half allies killed",
                    result="-2 to morale",
                    modifier=-2,
                ),
                TableEntry(
                    roll_min=3,
                    roll_max=3,
                    title="Leader killed",
                    result="-2 to morale",
                    modifier=-2,
                ),
                TableEntry(
                    roll_min=4,
                    roll_max=4,
                    title="Outnumbered 2:1",
                    result="-1 to morale",
                    modifier=-1,
                ),
                TableEntry(
                    roll_min=5,
                    roll_max=5,
                    title="Winning clearly",
                    result="+1 to morale",
                    modifier=+1,
                ),
                TableEntry(
                    roll_min=6,
                    roll_max=6,
                    title="Fighting for lair/treasure",
                    result="+2 to morale",
                    modifier=+2,
                ),
            ],
        )

    def _create_surprise_table(self) -> DolmenwoodTable:
        """Create surprise determination table."""
        return DolmenwoodTable(
            table_id="surprise_d6",
            name="Surprise Check",
            category=TableCategory.SURPRISE,
            die_type=DieType.D6,
            num_dice=1,
            description="Roll 1d6 for each side; 1-2 indicates surprise",
            entries=[
                TableEntry(
                    roll_min=1, roll_max=2, result="Surprised", mechanical_effect="surprised"
                ),
                TableEntry(
                    roll_min=3,
                    roll_max=6,
                    result="Not surprised",
                    mechanical_effect="not_surprised",
                ),
            ],
        )

    def _create_encounter_type_table(self) -> DolmenwoodTable:
        """Create generic encounter type table."""
        return DolmenwoodTable(
            table_id="encounter_type_d6",
            name="Encounter Type",
            category=TableCategory.ENCOUNTER_TYPE,
            die_type=DieType.D6,
            num_dice=1,
            description="Determine the general type of wilderness encounter",
            entries=[
                TableEntry(
                    roll_min=1,
                    roll_max=2,
                    title="Monster",
                    result="A monster encounter",
                    mechanical_effect="monster",
                    sub_table="encounter_monster",
                ),
                TableEntry(
                    roll_min=3,
                    roll_max=3,
                    title="NPC",
                    result="An NPC encounter",
                    mechanical_effect="npc",
                    sub_table="encounter_npc",
                ),
                TableEntry(
                    roll_min=4,
                    roll_max=4,
                    title="Lair",
                    result="Discovery of a monster lair",
                    mechanical_effect="lair",
                ),
                TableEntry(
                    roll_min=5,
                    roll_max=5,
                    title="Spoor/Sign",
                    result="Signs of creature activity",
                    mechanical_effect="spoor",
                ),
                TableEntry(
                    roll_min=6,
                    roll_max=6,
                    title="Special",
                    result="A special or environmental encounter",
                    mechanical_effect="special",
                    sub_table="encounter_special",
                ),
            ],
        )

    def _create_weather_table(self, season: str) -> DolmenwoodTable:
        """Create weather table for a specific season."""
        season_entries = {
            "spring": [
                TableEntry(roll_min=1, roll_max=2, result="Clear skies"),
                TableEntry(roll_min=3, roll_max=4, result="Overcast"),
                TableEntry(roll_min=5, roll_max=5, result="Light rain"),
                TableEntry(roll_min=6, roll_max=6, result="Heavy rain"),
            ],
            "summer": [
                TableEntry(roll_min=1, roll_max=3, result="Clear and warm"),
                TableEntry(roll_min=4, roll_max=4, result="Overcast"),
                TableEntry(roll_min=5, roll_max=5, result="Hot and humid"),
                TableEntry(roll_min=6, roll_max=6, result="Thunderstorm"),
            ],
            "autumn": [
                TableEntry(roll_min=1, roll_max=2, result="Clear and cool"),
                TableEntry(roll_min=3, roll_max=4, result="Overcast and misty"),
                TableEntry(roll_min=5, roll_max=5, result="Rain"),
                TableEntry(roll_min=6, roll_max=6, result="Heavy fog"),
            ],
            "winter": [
                TableEntry(roll_min=1, roll_max=1, result="Clear and cold"),
                TableEntry(roll_min=2, roll_max=3, result="Overcast"),
                TableEntry(roll_min=4, roll_max=4, result="Light snow"),
                TableEntry(roll_min=5, roll_max=5, result="Heavy snow"),
                TableEntry(roll_min=6, roll_max=6, result="Blizzard"),
            ],
        }

        return DolmenwoodTable(
            table_id=f"weather_{season}",
            name=f"Weather ({season.capitalize()})",
            category=TableCategory.WEATHER,
            die_type=DieType.D6,
            num_dice=1,
            description=f"Daily weather for {season}",
            context_required=season,
            entries=season_entries.get(season, []),
        )

    def register_table(self, table: DolmenwoodTable) -> None:
        """
        Register a table with the manager.

        Args:
            table: The table to register
        """
        self._tables[table.table_id] = table
        self._by_category[table.category].append(table.table_id)

        # Index by location if applicable
        if table.hex_id:
            if table.hex_id not in self._hex_tables:
                self._hex_tables[table.hex_id] = {}
            self._hex_tables[table.hex_id][table.name] = table.table_id

        if table.dungeon_id:
            if table.dungeon_id not in self._dungeon_tables:
                self._dungeon_tables[table.dungeon_id] = {}
            self._dungeon_tables[table.dungeon_id][table.name] = table.table_id

        if table.settlement_id:
            if table.settlement_id not in self._settlement_tables:
                self._settlement_tables[table.settlement_id] = {}
            self._settlement_tables[table.settlement_id][table.name] = table.table_id

    def get_table(self, table_id: str) -> Optional[DolmenwoodTable]:
        """Get a table by ID."""
        return self._tables.get(table_id)

    def get_tables_by_category(self, category: TableCategory) -> list[DolmenwoodTable]:
        """Get all tables in a category."""
        return [
            self._tables[tid] for tid in self._by_category.get(category, []) if tid in self._tables
        ]

    def get_hex_tables(self, hex_id: str) -> dict[str, DolmenwoodTable]:
        """Get all tables specific to a hex."""
        result = {}
        for name, table_id in self._hex_tables.get(hex_id, {}).items():
            if table_id in self._tables:
                result[name] = self._tables[table_id]
        return result

    def roll_table(
        self,
        table_id: str,
        context: Optional[TableContext] = None,
        modifier: int = 0,
        resolve_nested: bool = True,
    ) -> TableResult:
        """
        Roll on a table and return the full result.

        Args:
            table_id: ID of the table to roll on
            context: Optional context for modifiers
            modifier: Explicit modifier to apply
            resolve_nested: Whether to resolve nested table references

        Returns:
            TableResult with full details
        """
        table = self._tables.get(table_id)
        if not table:
            return TableResult(
                table_id=table_id,
                table_name="Unknown",
                category=TableCategory.FLAVOR,
                roll_total=0,
                result_text=f"Table '{table_id}' not found",
            )

        # Calculate total modifier
        total_modifier = modifier
        if context:
            total_modifier += context.get_total_modifier()

        # Roll the dice
        die_size = int(table.die_type.value[1:])
        dice_result = DiceRoller.roll(f"{table.num_dice}d{die_size}", f"table roll: {table_id}")
        roll_total = dice_result.total + table.base_modifier + total_modifier

        # Clamp to valid range
        roll_total = max(table.get_min_roll(), min(table.get_max_roll(), roll_total))

        # Find matching entry
        entry = None
        for e in table.entries:
            if e.matches_roll(roll_total):
                entry = e
                break

        result_text = entry.result if entry else "No matching entry"

        result = TableResult(
            table_id=table_id,
            table_name=table.name,
            category=table.category,
            roll_total=roll_total,
            dice_rolled=dice_result.rolls,
            modifier_applied=total_modifier,
            entry=entry,
            result_text=result_text,
        )

        # Log to RunLog for observability
        self._log_table_lookup(
            table_id=table_id,
            table_name=table.name,
            roll_total=roll_total,
            result_text=result_text,
            modifier_applied=total_modifier,
        )

        # Resolve quantity if specified
        if entry and entry.quantity:
            result.quantity_rolled = self._roll_dice_notation(entry.quantity)

        # Resolve nested tables if requested
        if resolve_nested and entry and entry.sub_table:
            sub_result = self.roll_table(entry.sub_table, context, 0, True)
            result.sub_results.append(sub_result)

        return result

    def _log_table_lookup(
        self,
        table_id: str,
        table_name: str,
        roll_total: int,
        result_text: str,
        modifier_applied: int = 0,
    ) -> None:
        """Log a table lookup to the observability RunLog."""
        try:
            from src.observability.run_log import get_run_log

            get_run_log().log_table_lookup(
                table_id=table_id,
                table_name=table_name,
                roll_total=roll_total,
                result_text=result_text,
                modifier_applied=modifier_applied,
            )
        except ImportError:
            pass  # Observability module not available

    def _roll_dice_notation(self, notation: str) -> int:
        """
        Roll dice using standard notation (e.g., '2d6', '1d20+5').

        Args:
            notation: Dice notation string

        Returns:
            Total result
        """
        modifier = 0
        if "+" in notation:
            dice_part, mod_part = notation.split("+")
            modifier = int(mod_part)
        elif "-" in notation:
            dice_part, mod_part = notation.split("-")
            modifier = -int(mod_part)
        else:
            dice_part = notation

        num_dice, die_size = dice_part.lower().split("d")
        num_dice = int(num_dice) if num_dice else 1
        die_size = int(die_size)

        dice_result = DiceRoller.roll(f"{num_dice}d{die_size}", "quantity roll")
        return dice_result.total + modifier

    def roll_surprise(self, modifier: int = 0) -> tuple[int, bool]:
        """
        Roll a surprise check.

        Args:
            modifier: Modifier to surprise roll

        Returns:
            Tuple of (roll, is_surprised)
        """
        roll = DiceRoller.roll("1d6", "surprise check").total + modifier
        return roll, roll <= 2

    def skill_check(self, skill_name: str, base_chance: int, modifier: int = 0) -> SkillCheck:
        """
        Perform an X-in-6 skill check.

        Args:
            skill_name: Name of the skill
            base_chance: Base X in X-in-6
            modifier: Situational modifier

        Returns:
            SkillCheck result
        """
        return SkillCheck.check(skill_name, base_chance, modifier)

    def check_encounter(self, base_chance: int = 2, modifier: int = 0) -> SkillCheck:
        """Check for a random encounter (default 2-in-6)."""
        return self.skill_check("Encounter", base_chance, modifier)

    def check_lost(self, base_chance: int = 2, modifier: int = 0) -> SkillCheck:
        """Check if party gets lost (default 2-in-6)."""
        return self.skill_check("Lost", base_chance, modifier)

    def check_forage(self, base_chance: int = 1, modifier: int = 0) -> SkillCheck:
        """Check foraging success (default 1-in-6)."""
        return self.skill_check("Forage", base_chance, modifier)

    def register_hex_table(
        self,
        hex_id: str,
        table_name: str,
        die_type: str,
        entries: list[dict],
        category: TableCategory = TableCategory.ENCOUNTER_HEX,
    ) -> str:
        """
        Register a hex-specific table from hex data.

        Args:
            hex_id: The hex ID this table belongs to
            table_name: Name of the table
            die_type: Die type string (e.g., "d6", "d8")
            entries: List of entry dictionaries
            category: Table category

        Returns:
            The generated table ID
        """
        table_id = f"{hex_id}_{table_name.lower().replace(' ', '_')}"

        # Convert die type string to enum
        die_enum = DieType.D6
        for dt in DieType:
            if dt.value.lower() == die_type.lower():
                die_enum = dt
                break

        # Convert entries
        table_entries = []
        for entry in entries:
            roll_val = entry.get("roll", 1)
            table_entries.append(
                TableEntry(
                    roll_min=roll_val,
                    roll_max=roll_val,
                    title=entry.get("title"),
                    result=entry.get("description", ""),
                    monster_refs=entry.get("monsters", []),
                    npc_refs=entry.get("npcs", []),
                    item_refs=entry.get("items", []),
                    mechanical_effect=entry.get("mechanical_effect"),
                    sub_table=entry.get("sub_table"),
                )
            )

        table = DolmenwoodTable(
            table_id=table_id,
            name=table_name,
            category=category,
            die_type=die_enum,
            num_dice=1,
            hex_id=hex_id,
            entries=table_entries,
        )

        self.register_table(table)
        return table_id

    def load_tables_from_json(self, file_path: Path) -> int:
        """
        Load tables from a JSON file.

        Args:
            file_path: Path to JSON file containing table definitions

        Returns:
            Number of tables loaded
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        tables_data = data.get("tables", [data]) if isinstance(data, dict) else data

        for table_data in tables_data:
            table = self._parse_table_json(table_data)
            if table:
                self.register_table(table)
                count += 1

        return count

    def _parse_table_json(self, data: dict) -> Optional[DolmenwoodTable]:
        """Parse a table from JSON data."""
        try:
            # Get category
            cat_str = data.get("category", "flavor")
            category = TableCategory.FLAVOR
            for cat in TableCategory:
                if cat.value == cat_str:
                    category = cat
                    break

            # Get die type
            die_str = data.get("die_type", "d6")
            die_type = DieType.D6
            for dt in DieType:
                if dt.value.lower() == die_str.lower():
                    die_type = dt
                    break

            # Parse entries
            entries = []
            for entry_data in data.get("entries", []):
                roll = entry_data.get("roll", 1)
                roll_min = entry_data.get("roll_min", roll)
                roll_max = entry_data.get("roll_max", roll)

                entries.append(
                    TableEntry(
                        roll_min=roll_min,
                        roll_max=roll_max,
                        title=entry_data.get("title"),
                        result=entry_data.get("result", entry_data.get("description", "")),
                        monster_refs=entry_data.get("monsters", []),
                        npc_refs=entry_data.get("npcs", []),
                        item_refs=entry_data.get("items", []),
                        mechanical_effect=entry_data.get("mechanical_effect"),
                        sub_table=entry_data.get("sub_table"),
                        quantity=entry_data.get("quantity"),
                    )
                )

            return DolmenwoodTable(
                table_id=data.get("table_id", data.get("id", "")),
                name=data.get("name", ""),
                category=category,
                die_type=die_type,
                num_dice=data.get("num_dice", 1),
                base_modifier=data.get("base_modifier", 0),
                description=data.get("description", ""),
                source_reference=data.get("source_reference", ""),
                entries=entries,
                hex_id=data.get("hex_id"),
                dungeon_id=data.get("dungeon_id"),
                settlement_id=data.get("settlement_id"),
            )

        except Exception as e:
            print(f"Error parsing table: {e}")
            return None


# Global table manager instance
_table_manager: Optional[TableManager] = None


def get_table_manager() -> TableManager:
    """Get the global TableManager instance."""
    global _table_manager
    if _table_manager is None:
        _table_manager = TableManager()
    return _table_manager
