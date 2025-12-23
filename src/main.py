"""
Dolmenwood Virtual DM - Main Entry Point

A Python-based companion tool for solo TTRPG play in Dolmenwood.
Designed for use with Mythic Game Master Emulator 2e.

This module provides the main entry point and the VirtualDM class
that coordinates all game subsystems.
"""

import sys
from pathlib import Path

# Add the project root to the Python path for module discovery
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import logging
from typing import Any, Optional

from src.data_models import (
    GameDate,
    GameTime,
    CharacterState,
    PartyResources,
    LocationType,
    Season,
    Weather,
)
from src.game_state import GameState, StateMachine, GlobalController, TimeTracker
from src.hex_crawl import HexCrawlEngine
from src.dungeon import DungeonEngine
from src.combat import CombatEngine
from src.settlement import SettlementEngine
from src.downtime import DowntimeEngine


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VirtualDM:
    """
    The Virtual DM orchestrates all game subsystems.

    This is the main interface for the Dolmenwood Virtual DM system.
    It provides access to all engines and manages the game state.

    The Virtual DM acts as a procedural referee and world simulator,
    not a storyteller. It enforces OSR procedures with mechanical
    precision while the LLM layer (external) adds atmospheric description.

    Key Design Principles (from spec):
    - Hard-code procedures, not judgment
    - LLM provides description only (external to this system)
    - All uncertainty via explicit procedures (dice rolls, tables)
    - Failure precedes success
    - Time, risk, resources drive play
    """

    def __init__(
        self,
        initial_state: GameState = GameState.WILDERNESS_TRAVEL,
        game_date: Optional[GameDate] = None,
        game_time: Optional[GameTime] = None,
    ):
        """
        Initialize the Virtual DM.

        Args:
            initial_state: Starting game state (default: WILDERNESS_TRAVEL)
            game_date: Starting date (default: Year 1, Month 1, Day 1)
            game_time: Starting time (default: 08:00)
        """
        logger.info("Initializing Dolmenwood Virtual DM...")

        # Initialize the global controller (manages state, time, characters)
        self.controller = GlobalController(
            initial_state=initial_state,
            game_date=game_date,
            game_time=game_time,
        )

        # Initialize all engines
        self.hex_crawl = HexCrawlEngine(self.controller)
        self.dungeon = DungeonEngine(self.controller)
        self.combat = CombatEngine(self.controller)
        self.settlement = SettlementEngine(self.controller)
        self.downtime = DowntimeEngine(self.controller)

        logger.info(f"Virtual DM initialized in state: {initial_state.value}")

    # =========================================================================
    # STATE ACCESS
    # =========================================================================

    @property
    def current_state(self) -> GameState:
        """Get the current game state."""
        return self.controller.current_state

    @property
    def state_machine(self) -> StateMachine:
        """Get the state machine."""
        return self.controller.state_machine

    @property
    def time_tracker(self) -> TimeTracker:
        """Get the time tracker."""
        return self.controller.time_tracker

    def get_full_state(self) -> dict[str, Any]:
        """
        Get complete game state for display or persistence.

        Returns:
            Dictionary with all game state
        """
        return self.controller.get_full_state()

    def get_valid_actions(self) -> list[str]:
        """
        Get valid actions/triggers from current state.

        Returns:
            List of valid action names
        """
        return self.controller.get_valid_actions()

    # =========================================================================
    # CHARACTER MANAGEMENT
    # =========================================================================

    def add_character(self, character: CharacterState) -> None:
        """Add a character to the party."""
        self.controller.add_character(character)
        logger.info(f"Added character: {character.name}")

    def create_character(
        self,
        character_id: str,
        name: str,
        character_class: str,
        level: int,
        ability_scores: dict[str, int],
        hp_max: int,
        armor_class: int = 10,
        movement_rate: int = 120,
    ) -> CharacterState:
        """
        Create and add a new character.

        Args:
            character_id: Unique identifier
            name: Character name
            character_class: Class (Fighter, Magic-User, etc.)
            level: Character level
            ability_scores: Dict of STR, INT, WIS, DEX, CON, CHA
            hp_max: Maximum HP
            armor_class: AC (descending, default 10)
            movement_rate: Movement in feet per turn

        Returns:
            The created CharacterState
        """
        character = CharacterState(
            character_id=character_id,
            name=name,
            character_class=character_class,
            level=level,
            ability_scores=ability_scores,
            hp_current=hp_max,
            hp_max=hp_max,
            armor_class=armor_class,
            movement_rate=movement_rate,
        )
        self.add_character(character)
        return character

    def get_character(self, character_id: str) -> Optional[CharacterState]:
        """Get a character by ID."""
        return self.controller.get_character(character_id)

    def get_party(self) -> list[CharacterState]:
        """Get all party members."""
        return self.controller.get_all_characters()

    # =========================================================================
    # RESOURCE MANAGEMENT
    # =========================================================================

    def set_party_resources(
        self,
        food_days: float = 0,
        water_days: float = 0,
        torches: int = 0,
        lantern_oil: int = 0,
    ) -> None:
        """Set party resources."""
        resources = PartyResources(
            food_days=food_days,
            water_days=water_days,
            torches=torches,
            lantern_oil_flasks=lantern_oil,
        )
        self.controller.party_state.resources = resources

    def get_resources(self) -> PartyResources:
        """Get current party resources."""
        return self.controller.party_state.resources

    # =========================================================================
    # QUICK ACTIONS
    # =========================================================================

    def travel_to_hex(self, hex_id: str) -> dict[str, Any]:
        """
        Travel to an adjacent hex.

        Only valid in WILDERNESS_TRAVEL state.

        Args:
            hex_id: Target hex ID

        Returns:
            Travel result dictionary
        """
        if self.current_state != GameState.WILDERNESS_TRAVEL:
            return {"error": f"Cannot travel from state: {self.current_state.value}"}

        return self.hex_crawl.travel_to_hex(hex_id)

    def enter_dungeon(self, dungeon_id: str, entry_room: str) -> dict[str, Any]:
        """
        Enter a dungeon.

        Args:
            dungeon_id: Dungeon identifier
            entry_room: Entry room ID

        Returns:
            Entry result dictionary
        """
        return self.dungeon.enter_dungeon(dungeon_id, entry_room)

    def enter_settlement(self, settlement_id: str) -> dict[str, Any]:
        """
        Enter a settlement.

        Args:
            settlement_id: Settlement identifier

        Returns:
            Entry result dictionary
        """
        return self.settlement.enter_settlement(settlement_id)

    def rest(self, rest_type: str = "long") -> dict[str, Any]:
        """
        Rest the party.

        Args:
            rest_type: "short", "long", or "full"

        Returns:
            Rest result dictionary
        """
        from src.downtime.downtime_engine import RestType

        type_map = {
            "short": RestType.SHORT_REST,
            "long": RestType.LONG_REST,
            "full": RestType.FULL_REST,
        }

        return self.downtime.rest(type_map.get(rest_type, RestType.LONG_REST))

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def get_session_log(self) -> list[dict[str, Any]]:
        """Get the session event log."""
        return self.controller.get_session_log()

    def get_dice_log(self) -> list:
        """Get all dice rolls this session."""
        from src.data_models import DiceRoller
        return DiceRoller.get_roll_log()

    def clear_dice_log(self) -> None:
        """Clear the dice roll log."""
        from src.data_models import DiceRoller
        DiceRoller.clear_roll_log()

    def get_time_summary(self) -> dict[str, Any]:
        """Get current time state."""
        return self.time_tracker.get_time_summary()

    # =========================================================================
    # DISPLAY HELPERS
    # =========================================================================

    def status(self) -> str:
        """
        Get a formatted status string for display.

        Returns:
            Multi-line status string
        """
        state = self.get_full_state()
        time = state["time"]
        party = state["party"]

        lines = [
            "=" * 50,
            "DOLMENWOOD VIRTUAL DM STATUS",
            "=" * 50,
            f"State: {state['state_machine']['current_state']}",
            f"Date: {time['date']} ({time['season']})",
            f"Time: {time['time']} ({time['time_of_day']})",
            f"Location: {party['location']}",
            "",
            "Party Resources:",
            f"  Food: {party['resources']['food_days']:.1f} days",
            f"  Water: {party['resources']['water_days']:.1f} days",
            f"  Torches: {party['resources']['torches']}",
            f"  Oil: {party['resources']['oil_flasks']} flasks",
        ]

        if party["light_source"]:
            lines.append(f"  Active Light: {party['light_source']} ({party['light_remaining']} turns)")

        lines.append("")
        lines.append("Party Members:")
        for cid, cdata in state["characters"].items():
            lines.append(f"  {cdata['name']} ({cdata['class']} {cdata['level']}): {cdata['hp']}")
            if cdata["conditions"]:
                lines.append(f"    Conditions: {', '.join(cdata['conditions'])}")

        lines.append("")
        lines.append("Valid Actions: " + ", ".join(self.get_valid_actions()))
        lines.append("=" * 50)

        return "\n".join(lines)


def create_demo_session() -> VirtualDM:
    """
    Create a demo session with sample characters.

    Returns:
        Initialized VirtualDM with demo party
    """
    dm = VirtualDM(
        initial_state=GameState.WILDERNESS_TRAVEL,
        game_date=GameDate(year=1, month=6, day=15),
        game_time=GameTime(hour=9, minute=0),
    )

    # Create sample party
    dm.create_character(
        character_id="char_001",
        name="Sir Aldric",
        character_class="Fighter",
        level=3,
        ability_scores={"STR": 16, "INT": 10, "WIS": 12, "DEX": 13, "CON": 14, "CHA": 11},
        hp_max=24,
        armor_class=4,  # Plate + Shield
    )

    dm.create_character(
        character_id="char_002",
        name="Mira Thornwood",
        character_class="Magic-User",
        level=3,
        ability_scores={"STR": 8, "INT": 17, "WIS": 14, "DEX": 12, "CON": 10, "CHA": 13},
        hp_max=8,
        armor_class=9,  # No armor
    )

    dm.create_character(
        character_id="char_003",
        name="Brother Cormac",
        character_class="Cleric",
        level=2,
        ability_scores={"STR": 12, "INT": 11, "WIS": 16, "DEX": 10, "CON": 13, "CHA": 14},
        hp_max=12,
        armor_class=5,  # Chain + Shield
    )

    dm.create_character(
        character_id="char_004",
        name="Wren",
        character_class="Thief",
        level=3,
        ability_scores={"STR": 11, "INT": 14, "WIS": 10, "DEX": 17, "CON": 12, "CHA": 13},
        hp_max=10,
        armor_class=7,  # Leather
    )

    # Set resources
    dm.set_party_resources(
        food_days=7,
        water_days=7,
        torches=10,
        lantern_oil=4,
    )

    # Set starting location
    dm.controller.set_party_location(LocationType.HEX, "0709")

    return dm


def main():
    """Main entry point for CLI usage."""
    print("Dolmenwood Virtual DM v0.1.0")
    print("A procedural companion for solo TTRPG play\n")

    # Create demo session
    dm = create_demo_session()

    # Display initial status
    print(dm.status())

    print("\nVirtual DM ready. Use the VirtualDM object for interaction.")
    print("Example: dm.travel_to_hex('0710')")

    return dm


if __name__ == "__main__":
    main()
