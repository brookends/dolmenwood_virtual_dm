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

import argparse
import logging
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from src.data_models import (
    GameDate,
    GameTime,
    CharacterState,
    PartyResources,
    LocationType,
    LocationState,
    Season,
    Weather,
    TimeOfDay,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    Combatant,
    StatBlock,
    DiceRoller,
    LightSourceType,
)
from src.game_state import GameState, StateMachine, GlobalController, TimeTracker
from src.hex_crawl import HexCrawlEngine
from src.dungeon import DungeonEngine
from src.combat import CombatEngine
from src.settlement import SettlementEngine
from src.downtime import DowntimeEngine
from src.encounter import EncounterEngine, EncounterOrigin, EncounterAction


# Configure logging
def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class GameConfig:
    """Configuration for the game session."""

    data_dir: Path = field(default_factory=lambda: Path("data"))
    campaign_name: str = "default"
    dm_style: str = "standard"

    # LLM Configuration
    llm_provider: str = "mock"  # mock, anthropic, openai, local
    llm_model: Optional[str] = None
    llm_url: Optional[str] = None

    # Database options
    use_vector_db: bool = True
    mock_embeddings: bool = False
    local_embeddings: bool = False
    skip_indexing: bool = False

    # Content options
    content_dir: Optional[Path] = None
    ingest_pdf: Optional[Path] = None
    load_content: bool = False

    # Runtime options
    verbose: bool = False

    def __post_init__(self):
        """Ensure paths are Path objects."""
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
        if isinstance(self.content_dir, str):
            self.content_dir = Path(self.content_dir)
        if isinstance(self.ingest_pdf, str):
            self.ingest_pdf = Path(self.ingest_pdf)


# =============================================================================
# VIRTUAL DM CLASS
# =============================================================================

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
        config: Optional[GameConfig] = None,
        initial_state: GameState = GameState.WILDERNESS_TRAVEL,
        game_date: Optional[GameDate] = None,
        game_time: Optional[GameTime] = None,
    ):
        """
        Initialize the Virtual DM.

        Args:
            config: Game configuration object
            initial_state: Starting game state (default: WILDERNESS_TRAVEL)
            game_date: Starting date (default: Year 1, Month 1, Day 1)
            game_time: Starting time (default: 08:00)
        """
        self.config = config or GameConfig()
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
        self.encounter = EncounterEngine(self.controller)

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
            armor_class: AC (ascending, default 10 unarmored)
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
        return DiceRoller.get_roll_log()

    def clear_dice_log(self) -> None:
        """Clear the dice roll log."""
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
        time_state = state["time"]
        party = state["party"]

        lines = [
            "=" * 60,
            "DOLMENWOOD VIRTUAL DM STATUS",
            "=" * 60,
            f"State: {state['state_machine']['current_state']}",
            f"Date: {time_state['date']} ({time_state['season']})",
            f"Time: {time_state['time']} ({time_state['time_of_day']})",
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
        lines.append("=" * 60)

        return "\n".join(lines)


# =============================================================================
# DEMO SESSION CREATION
# =============================================================================

def create_demo_session(config: Optional[GameConfig] = None) -> VirtualDM:
    """
    Create a demo session with sample characters.

    Returns:
        Initialized VirtualDM with demo party
    """
    dm = VirtualDM(
        config=config,
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


# =============================================================================
# CLI INTERFACE
# =============================================================================

class DolmenwoodCLI:
    """Interactive command-line interface for the game."""

    def __init__(self, dm: VirtualDM):
        self.dm = dm
        self.running = False
        self.commands = {
            "status": self.cmd_status,
            "help": self.cmd_help,
            "quit": self.cmd_quit,
            "exit": self.cmd_quit,
            "travel": self.cmd_travel,
            "actions": self.cmd_actions,
            "roll": self.cmd_roll,
            "time": self.cmd_time,
            "party": self.cmd_party,
            "resources": self.cmd_resources,
            "log": self.cmd_log,
            "dice": self.cmd_dice,
            "transition": self.cmd_transition,
        }

    def run(self) -> None:
        """Run the interactive CLI loop."""
        self.running = True
        print("\n" + "=" * 60)
        print("DOLMENWOOD VIRTUAL DM - Interactive Mode")
        print("=" * 60)
        print("Type 'help' for available commands, 'quit' to exit.\n")

        while self.running:
            try:
                user_input = input(f"[{self.dm.current_state.value}]> ").strip()
                if not user_input:
                    continue

                self.process_command(user_input)

            except KeyboardInterrupt:
                print("\nInterrupted. Type 'quit' to exit.")
            except EOFError:
                self.running = False

        print("\nFarewell, adventurer!")

    def process_command(self, user_input: str) -> None:
        """Process a user command."""
        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")

    def cmd_help(self, args: str) -> None:
        """Show help information."""
        print("""
Available Commands:
  status      - Show current game status
  actions     - Show valid actions from current state
  travel HEX  - Travel to adjacent hex (e.g., 'travel 0710')
  transition  - Trigger a state transition (e.g., 'transition enter_dungeon')
  roll DICE   - Roll dice (e.g., 'roll 2d6+3')
  time        - Show current game time
  party       - Show party information
  resources   - Show party resources
  log         - Show session event log
  dice        - Show dice roll history
  help        - Show this help
  quit/exit   - Exit the game
""")

    def cmd_status(self, args: str) -> None:
        """Show game status."""
        print(self.dm.status())

    def cmd_quit(self, args: str) -> None:
        """Quit the game."""
        self.running = False

    def cmd_travel(self, args: str) -> None:
        """Travel to a hex."""
        if not args:
            print("Usage: travel HEX_ID (e.g., 'travel 0710')")
            return
        result = self.dm.travel_to_hex(args.strip())
        print(json.dumps(result, indent=2, default=str))

    def cmd_actions(self, args: str) -> None:
        """Show valid actions."""
        actions = self.dm.get_valid_actions()
        print("Valid actions from current state:")
        for action in actions:
            print(f"  - {action}")

    def cmd_roll(self, args: str) -> None:
        """Roll dice."""
        if not args:
            print("Usage: roll DICE (e.g., 'roll 2d6+3', 'roll 1d20')")
            return
        try:
            result = DiceRoller.roll(args.strip())
            print(f"Rolling {args}: {result}")
        except Exception as e:
            print(f"Error rolling dice: {e}")

    def cmd_time(self, args: str) -> None:
        """Show current time."""
        summary = self.dm.get_time_summary()
        print(f"Date: {summary['date']} ({summary['season']})")
        print(f"Time: {summary['time']} ({summary['time_of_day']})")

    def cmd_party(self, args: str) -> None:
        """Show party information."""
        party = self.dm.get_party()
        print("\nParty Members:")
        print("-" * 40)
        for char in party:
            print(f"  {char.name}")
            print(f"    Class: {char.character_class} Level {char.level}")
            print(f"    HP: {char.hp_current}/{char.hp_max}")
            print(f"    AC: {char.armor_class}")
            if char.conditions:
                print(f"    Conditions: {', '.join(c.name for c in char.conditions)}")
        print("-" * 40)

    def cmd_resources(self, args: str) -> None:
        """Show party resources."""
        res = self.dm.get_resources()
        print("\nParty Resources:")
        print(f"  Food: {res.food_days:.1f} days")
        print(f"  Water: {res.water_days:.1f} days")
        print(f"  Torches: {res.torches}")
        print(f"  Lantern Oil: {res.lantern_oil_flasks} flasks")
        print(f"  Gold: {res.gold} gp")

    def cmd_log(self, args: str) -> None:
        """Show session log."""
        log = self.dm.get_session_log()
        print("\nSession Log (last 10 entries):")
        print("-" * 40)
        for entry in log[-10:]:
            print(f"  {entry}")
        print("-" * 40)

    def cmd_dice(self, args: str) -> None:
        """Show dice roll history."""
        rolls = self.dm.get_dice_log()
        print("\nDice Roll History (last 10):")
        print("-" * 40)
        for roll in rolls[-10:]:
            print(f"  {roll}")
        print("-" * 40)

    def cmd_transition(self, args: str) -> None:
        """Trigger a state transition."""
        if not args:
            print("Usage: transition TRIGGER_NAME")
            print("Valid triggers:", ", ".join(self.dm.get_valid_actions()))
            return

        trigger = args.strip()
        try:
            new_state = self.dm.controller.transition(trigger)
            print(f"Transitioned to: {new_state.value}")
        except Exception as e:
            print(f"Transition failed: {e}")


# =============================================================================
# INDIVIDUAL LOOP TESTERS
# =============================================================================

def test_hex_exploration_loop(dm: VirtualDM) -> None:
    """Test the hex exploration/wilderness travel loop."""
    print("\n" + "=" * 60)
    print("TESTING: Hex Exploration Loop")
    print("=" * 60)

    print("\n1. Initial state:")
    print(f"   Current state: {dm.current_state.value}")
    print(f"   Location: {dm.controller.party_state.location}")

    print("\n2. Advancing travel segment...")
    result = dm.controller.advance_travel_segment()
    print(f"   Result: {json.dumps(result, indent=4, default=str)}")

    print("\n3. Rolling for encounter check...")
    roll = DiceRoller.roll("1d6")
    print(f"   Encounter check roll: {roll}")
    if roll == 1:
        print("   Encounter triggered!")
    else:
        print("   No encounter.")

    print("\n4. Rolling weather...")
    weather = dm.controller.roll_weather()
    print(f"   Weather: {weather}")

    print("\n5. Checking time advancement...")
    time_summary = dm.get_time_summary()
    print(f"   Current time: {time_summary['time']} ({time_summary['time_of_day']})")

    print("\n6. Simulating travel to adjacent hex...")
    adjacent_hexes = ["0710", "0708", "0809", "0609"]
    target = adjacent_hexes[0]
    print(f"   Attempting travel to hex {target}...")
    travel_result = dm.travel_to_hex(target)
    print(f"   Travel result: {json.dumps(travel_result, indent=4, default=str)}")

    print("\n" + "=" * 60)
    print("Hex Exploration Loop Test Complete")
    print("=" * 60)


def test_encounter_loop(dm: VirtualDM) -> None:
    """Test the encounter resolution loop."""
    print("\n" + "=" * 60)
    print("TESTING: Encounter Loop")
    print("=" * 60)

    # Create a test encounter
    combatants = [
        Combatant(
            combatant_id="char_001",
            name="Sir Aldric",
            side="party",
            stat_block=StatBlock(
                armor_class=4,
                hit_dice="3d8",
                hp_current=24,
                hp_max=24,
                movement=90,
                attacks=[{"name": "Sword", "damage": "1d8+3", "bonus": 3}],
                morale=12,
            ),
        ),
        Combatant(
            combatant_id="goblin_1",
            name="Goblin Scout",
            side="enemy",
            stat_block=StatBlock(
                armor_class=7,
                hit_dice="1d8-1",
                hp_current=4,
                hp_max=4,
                movement=60,
                attacks=[{"name": "Short Sword", "damage": "1d6", "bonus": 0}],
                morale=7,
            ),
        ),
    ]

    encounter = EncounterState(
        encounter_type=EncounterType.MONSTER,
        distance=60,
        surprise_status=SurpriseStatus.NO_SURPRISE,
        actors=["goblin scout"],
        context="patrolling the forest",
        terrain="forest",
        combatants=combatants,
    )

    print("\n1. Starting encounter...")
    result = dm.encounter.start_encounter(
        encounter=encounter,
        origin=EncounterOrigin.WILDERNESS,
    )
    print(f"   Encounter started: {result['encounter_started']}")
    print(f"   Origin: {result['origin']}")

    print("\n2. Running automatic phases...")
    phase_result = dm.encounter.auto_run_phases()
    print(f"   Surprise status: {phase_result.get('surprise', {})}")
    print(f"   Distance: {phase_result.get('distance', {})}")
    print(f"   Initiative: {phase_result.get('initiative', {})}")

    print("\n3. Testing encounter actions...")
    print("   Available actions: ATTACK, PARLEY, EVASION, WAIT")

    # Test parley action
    print("\n   Testing PARLEY action...")
    parley_result = dm.encounter.execute_action(EncounterAction.PARLEY, actor="party")
    print(f"   Reaction roll: {parley_result.reaction_roll}")
    print(f"   Reaction result: {parley_result.reaction_result}")

    print("\n4. Encounter summary:")
    summary = dm.encounter.get_encounter_summary()
    print(f"   {json.dumps(summary, indent=4, default=str)}")

    # Reset state for other tests
    if dm.encounter.is_active():
        dm.encounter.conclude_encounter("test_complete")

    print("\n" + "=" * 60)
    print("Encounter Loop Test Complete")
    print("=" * 60)


def test_dungeon_exploration_loop(dm: VirtualDM) -> None:
    """Test the dungeon exploration loop."""
    print("\n" + "=" * 60)
    print("TESTING: Dungeon Exploration Loop")
    print("=" * 60)

    print("\n1. Current state before entering dungeon:")
    print(f"   State: {dm.current_state.value}")

    print("\n2. Entering dungeon...")
    # Transition to dungeon state
    if dm.current_state == GameState.WILDERNESS_TRAVEL:
        dm.controller.transition("enter_dungeon")
    print(f"   New state: {dm.current_state.value}")

    print("\n3. Setting dungeon location...")
    dm.controller.set_party_location(
        LocationType.DUNGEON_ROOM,
        "test_dungeon",
        "entry_chamber",
    )
    print(f"   Location: {dm.controller.party_state.location}")

    print("\n4. Activating light source...")
    dm.controller.party_state.active_light_source = LightSourceType.TORCH
    dm.controller.party_state.light_remaining_turns = 6
    print(f"   Light source: {dm.controller.party_state.active_light_source}")
    print(f"   Turns remaining: {dm.controller.party_state.light_remaining_turns}")

    print("\n5. Rolling for wandering monster check...")
    roll = DiceRoller.roll("1d6")
    print(f"   Wandering monster check: {roll}")
    if roll == 1:
        print("   Monster encountered!")
    else:
        print("   No monster.")

    print("\n6. Simulating dungeon turn (advancing time)...")
    result = dm.controller.advance_time(1)  # 1 turn = 10 minutes
    print(f"   Time advancement result: {result}")
    print(f"   Light remaining: {dm.controller.party_state.light_remaining_turns} turns")

    print("\n7. Exiting dungeon...")
    dm.controller.transition("exit_dungeon")
    print(f"   New state: {dm.current_state.value}")

    print("\n" + "=" * 60)
    print("Dungeon Exploration Loop Test Complete")
    print("=" * 60)


def test_combat_loop(dm: VirtualDM) -> None:
    """Test the combat loop."""
    print("\n" + "=" * 60)
    print("TESTING: Combat Loop")
    print("=" * 60)

    # Prepare for combat
    combatants = [
        Combatant(
            combatant_id="char_001",
            name="Sir Aldric",
            side="party",
            stat_block=StatBlock(
                armor_class=4,
                hit_dice="3d8",
                hp_current=24,
                hp_max=24,
                movement=90,
                attacks=[{"name": "Longsword", "damage": "1d8+3", "bonus": 3}],
                morale=12,
            ),
        ),
        Combatant(
            combatant_id="char_002",
            name="Mira Thornwood",
            side="party",
            stat_block=StatBlock(
                armor_class=9,
                hit_dice="3d4",
                hp_current=8,
                hp_max=8,
                movement=120,
                attacks=[{"name": "Dagger", "damage": "1d4", "bonus": 0}],
                morale=8,
            ),
        ),
        Combatant(
            combatant_id="goblin_1",
            name="Goblin Warrior",
            side="enemy",
            stat_block=StatBlock(
                armor_class=7,
                hit_dice="1d8",
                hp_current=5,
                hp_max=5,
                movement=60,
                attacks=[{"name": "Sword", "damage": "1d6", "bonus": 0}],
                morale=7,
            ),
        ),
        Combatant(
            combatant_id="goblin_2",
            name="Goblin Archer",
            side="enemy",
            stat_block=StatBlock(
                armor_class=7,
                hit_dice="1d8",
                hp_current=4,
                hp_max=4,
                movement=60,
                attacks=[{"name": "Shortbow", "damage": "1d6", "bonus": 0}],
                morale=7,
            ),
        ),
    ]

    encounter = EncounterState(
        encounter_type=EncounterType.MONSTER,
        distance=30,
        surprise_status=SurpriseStatus.NO_SURPRISE,
        actors=["goblin warriors"],
        terrain="dungeon",
        combatants=combatants,
    )

    print("\n1. Setting up combat...")
    # Transition to combat state
    dm.controller.transition("encounter_triggered")
    dm.controller.transition("encounter_to_combat")
    print(f"   State: {dm.current_state.value}")

    print("\n2. Starting combat...")
    from src.combat.combat_engine import CombatAction, CombatActionType

    start_result = dm.combat.start_combat(encounter, GameState.WILDERNESS_TRAVEL)
    print(f"   Combat started: {start_result['combat_started']}")
    print(f"   Party combatants: {len(start_result['party_combatants'])}")
    print(f"   Enemy combatants: {len(start_result['enemy_combatants'])}")

    print("\n3. Executing combat round 1...")
    party_actions = [
        CombatAction(
            combatant_id="char_001",
            action_type=CombatActionType.MELEE_ATTACK,
            target_id="goblin_1",
        ),
    ]
    round_result = dm.combat.execute_round(party_actions)
    print(f"   Round number: {round_result.round_number}")
    print(f"   Party initiative: {round_result.party_initiative}")
    print(f"   Enemy initiative: {round_result.enemy_initiative}")
    print(f"   First to act: {round_result.first_side}")
    print(f"   Actions resolved: {len(round_result.actions_resolved)}")

    for action in round_result.actions_resolved[:3]:
        print(f"     - {action.attacker_id} attacked {action.defender_id}: "
              f"{'HIT' if action.hit else 'MISS'} "
              f"(roll: {action.attack_roll}, damage: {action.damage_dealt})")

    print("\n4. Combat summary:")
    summary = dm.combat.get_combat_summary()
    print(f"   {json.dumps(summary, indent=4, default=str)}")

    print("\n5. Ending combat...")
    end_result = dm.combat.end_combat()
    print(f"   Rounds fought: {end_result['rounds_fought']}")
    print(f"   New state: {dm.current_state.value}")

    print("\n" + "=" * 60)
    print("Combat Loop Test Complete")
    print("=" * 60)


def test_settlement_loop(dm: VirtualDM) -> None:
    """Test the settlement exploration loop."""
    print("\n" + "=" * 60)
    print("TESTING: Settlement Exploration Loop")
    print("=" * 60)

    print("\n1. Current state:")
    print(f"   State: {dm.current_state.value}")

    print("\n2. Entering settlement...")
    if dm.current_state == GameState.WILDERNESS_TRAVEL:
        dm.controller.transition("enter_settlement")
    elif dm.current_state != GameState.SETTLEMENT_EXPLORATION:
        # Reset to wilderness first
        dm.controller.force_state(GameState.WILDERNESS_TRAVEL, "test reset")
        dm.controller.transition("enter_settlement")

    print(f"   New state: {dm.current_state.value}")

    print("\n3. Setting settlement location...")
    dm.controller.set_party_location(
        LocationType.SETTLEMENT,
        "prigwort",
        "The Wicked Owl Inn",
    )
    print(f"   Location: {dm.controller.party_state.location}")

    print("\n4. Available settlement actions:")
    actions = dm.get_valid_actions()
    for action in actions:
        print(f"   - {action}")

    print("\n5. Simulating visit to inn...")
    print("   (Settlement engine would provide NPC interactions, services, rumors)")

    print("\n6. Leaving settlement...")
    dm.controller.transition("exit_settlement")
    print(f"   New state: {dm.current_state.value}")

    print("\n" + "=" * 60)
    print("Settlement Exploration Loop Test Complete")
    print("=" * 60)


def test_social_interaction_loop(dm: VirtualDM) -> None:
    """Test the social interaction loop."""
    print("\n" + "=" * 60)
    print("TESTING: Social Interaction Loop")
    print("=" * 60)

    print("\n1. Setting up for social interaction...")
    # Need to be in settlement first
    if dm.current_state != GameState.SETTLEMENT_EXPLORATION:
        if dm.current_state == GameState.WILDERNESS_TRAVEL:
            dm.controller.transition("enter_settlement")
        else:
            dm.controller.force_state(GameState.SETTLEMENT_EXPLORATION, "test setup")

    print(f"   State: {dm.current_state.value}")

    print("\n2. Initiating conversation...")
    dm.controller.transition("initiate_conversation")
    print(f"   New state: {dm.current_state.value}")

    print("\n3. Rolling NPC reaction...")
    reaction_result = DiceRoller.roll("2d6")
    reaction_roll = reaction_result.total
    print(f"   Reaction roll: {reaction_result}")

    # Interpret reaction
    if reaction_roll <= 2:
        reaction = "Hostile, attacks"
    elif reaction_roll <= 5:
        reaction = "Unfriendly, may attack"
    elif reaction_roll <= 8:
        reaction = "Neutral, uncertain"
    elif reaction_roll <= 11:
        reaction = "Indifferent, uninterested"
    else:
        reaction = "Friendly, helpful"
    print(f"   Reaction: {reaction}")

    print("\n4. Simulating conversation...")
    print("   (Social interaction engine would manage dialogue, information exchange)")
    print("   Topics: Local rumors, directions, services, quests")

    print("\n5. Ending conversation...")
    dm.controller.transition("conversation_end_settlement")
    print(f"   New state: {dm.current_state.value}")

    # Return to wilderness
    dm.controller.transition("exit_settlement")
    print(f"   Final state: {dm.current_state.value}")

    print("\n" + "=" * 60)
    print("Social Interaction Loop Test Complete")
    print("=" * 60)


# =============================================================================
# ARGUMENT PARSING
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Dolmenwood Virtual DM - A procedural companion for solo TTRPG play",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                          # Run interactive mode
  python -m src.main --test-hex               # Test hex exploration loop
  python -m src.main --test-combat            # Test combat loop
  python -m src.main --campaign my_campaign   # Load specific campaign
  python -m src.main --llm-provider anthropic # Use Anthropic for descriptions
        """
    )

    # General options
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory for game data storage (default: data)",
    )
    parser.add_argument(
        "--campaign",
        type=str,
        default="default",
        help="Campaign name to load/create (default: default)",
    )
    parser.add_argument(
        "--dm-style",
        type=str,
        default="standard",
        choices=["standard", "verbose", "terse", "atmospheric"],
        help="DM narration style (default: standard)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    # LLM options
    llm_group = parser.add_argument_group("LLM Options")
    llm_group.add_argument(
        "--llm-provider",
        type=str,
        default="mock",
        choices=["mock", "anthropic", "openai", "local"],
        help="LLM provider for descriptions (default: mock)",
    )
    llm_group.add_argument(
        "--llm-model",
        type=str,
        help="Specific model to use (provider-dependent)",
    )
    llm_group.add_argument(
        "--llm-url",
        type=str,
        help="URL for local LLM server",
    )

    # Database options
    db_group = parser.add_argument_group("Database Options")
    db_group.add_argument(
        "--no-vector-db",
        action="store_true",
        help="Disable vector database for content search",
    )
    db_group.add_argument(
        "--mock-embeddings",
        action="store_true",
        help="Use mock embeddings (for testing)",
    )
    db_group.add_argument(
        "--local-embeddings",
        action="store_true",
        help="Use local embedding model",
    )
    db_group.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Skip content indexing on startup",
    )

    # Content options
    content_group = parser.add_argument_group("Content Options")
    content_group.add_argument(
        "--content-dir",
        type=Path,
        help="Directory containing game content files",
    )
    content_group.add_argument(
        "--ingest-pdf",
        type=Path,
        help="PDF file to ingest into content database",
    )
    content_group.add_argument(
        "--load-content",
        action="store_true",
        help="Load content from database on startup",
    )

    # Test loop options
    test_group = parser.add_argument_group("Test Loop Options")
    test_group.add_argument(
        "--test-hex",
        action="store_true",
        help="Test the hex exploration/wilderness travel loop",
    )
    test_group.add_argument(
        "--test-encounter",
        action="store_true",
        help="Test the encounter resolution loop",
    )
    test_group.add_argument(
        "--test-dungeon",
        action="store_true",
        help="Test the dungeon exploration loop",
    )
    test_group.add_argument(
        "--test-combat",
        action="store_true",
        help="Test the combat loop",
    )
    test_group.add_argument(
        "--test-settlement",
        action="store_true",
        help="Test the settlement exploration loop",
    )
    test_group.add_argument(
        "--test-social",
        action="store_true",
        help="Test the social interaction loop",
    )
    test_group.add_argument(
        "--test-all",
        action="store_true",
        help="Run all loop tests",
    )

    return parser.parse_args()


def create_config_from_args(args: argparse.Namespace) -> GameConfig:
    """Create GameConfig from parsed arguments."""
    return GameConfig(
        data_dir=args.data_dir,
        campaign_name=args.campaign,
        dm_style=args.dm_style,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_url=args.llm_url,
        use_vector_db=not args.no_vector_db,
        mock_embeddings=args.mock_embeddings,
        local_embeddings=args.local_embeddings,
        skip_indexing=args.skip_indexing,
        content_dir=args.content_dir,
        ingest_pdf=args.ingest_pdf,
        load_content=args.load_content,
        verbose=args.verbose,
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for CLI usage."""
    args = parse_arguments()
    setup_logging(args.verbose)

    print("=" * 60)
    print("DOLMENWOOD VIRTUAL DM v0.1.0")
    print("A procedural companion for solo TTRPG play")
    print("=" * 60)

    # Create configuration
    config = create_config_from_args(args)

    # Check for PDF ingestion
    if args.ingest_pdf:
        print(f"\nPDF ingestion requested: {args.ingest_pdf}")
        print("(PDF ingestion would process the file into the content database)")
        # TODO: Implement PDF ingestion when content system is ready

    # Create demo session
    dm = create_demo_session(config)

    # Check for test loop modes
    test_any = (
        args.test_hex or args.test_encounter or args.test_dungeon or
        args.test_combat or args.test_settlement or args.test_social or
        args.test_all
    )

    if test_any:
        print("\nRunning loop tests...\n")

        if args.test_hex or args.test_all:
            test_hex_exploration_loop(dm)
            dm = create_demo_session(config)  # Reset for next test

        if args.test_encounter or args.test_all:
            test_encounter_loop(dm)
            dm = create_demo_session(config)

        if args.test_dungeon or args.test_all:
            test_dungeon_exploration_loop(dm)
            dm = create_demo_session(config)

        if args.test_combat or args.test_all:
            test_combat_loop(dm)
            dm = create_demo_session(config)

        if args.test_settlement or args.test_all:
            test_settlement_loop(dm)
            dm = create_demo_session(config)

        if args.test_social or args.test_all:
            test_social_interaction_loop(dm)

        print("\n" + "=" * 60)
        print("All requested loop tests complete!")
        print("=" * 60)
    else:
        # Display initial status
        print(dm.status())

        # Run interactive CLI
        cli = DolmenwoodCLI(dm)
        cli.run()

    return dm


if __name__ == "__main__":
    main()
