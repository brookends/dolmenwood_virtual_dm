"""
Test helpers for Dolmenwood Virtual DM test suite.

P2-12: Provides deterministic test harness with:
- VirtualDMTestBuilder for easy VirtualDM test setup
- MockVirtualDM for lightweight mocking
- Deterministic seeding utilities
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import MagicMock

from src.main import VirtualDM, GameConfig
from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.data_models import (
    DiceRoller,
    GameDate,
    GameTime,
    CharacterState,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    Combatant,
    StatBlock,
    HexLocation,
    PointOfInterest,
    HexNPC,
)


# =============================================================================
# VIRTUAL DM TEST BUILDER
# =============================================================================


class VirtualDMTestBuilder:
    """
    Builder pattern for creating VirtualDM instances in tests.

    Provides a fluent interface for setting up test VirtualDM with
    deterministic state, mocked LLM, and pre-configured game state.

    Usage:
        dm = (VirtualDMTestBuilder()
            .with_seed(42)
            .with_state(GameState.WILDERNESS_TRAVEL)
            .with_character("Test Fighter", "Fighter", level=3)
            .with_mock_llm()
            .build())

        # Or use preset configurations
        dm = VirtualDMTestBuilder.wilderness_dm()
        dm = VirtualDMTestBuilder.dungeon_dm()
    """

    def __init__(self):
        """Initialize builder with defaults."""
        self._seed: int = 42
        self._initial_state: GameState = GameState.WILDERNESS_TRAVEL
        self._game_date: GameDate = GameDate(year=1, month=6, day=15)
        self._game_time: GameTime = GameTime(hour=10, minute=0)
        self._load_content: bool = False
        self._enable_narration: bool = False
        self._llm_provider: str = "mock"
        self._characters: list[CharacterState] = []
        self._hex_data: dict[str, HexLocation] = {}
        self._current_poi: Optional[str] = None
        self._save_dir: Optional[str] = None

    def with_seed(self, seed: int) -> "VirtualDMTestBuilder":
        """Set the random seed for deterministic tests."""
        self._seed = seed
        return self

    def with_state(self, state: GameState) -> "VirtualDMTestBuilder":
        """Set the initial game state."""
        self._initial_state = state
        return self

    def with_date(self, year: int = 1, month: int = 6, day: int = 15) -> "VirtualDMTestBuilder":
        """Set the game date."""
        self._game_date = GameDate(year=year, month=month, day=day)
        return self

    def with_time(self, hour: int = 10, minute: int = 0) -> "VirtualDMTestBuilder":
        """Set the game time."""
        self._game_time = GameTime(hour=hour, minute=minute)
        return self

    def with_character(
        self,
        name: str,
        character_class: str = "Fighter",
        level: int = 1,
        hp: Optional[int] = None,
        ability_scores: Optional[dict[str, int]] = None,
    ) -> "VirtualDMTestBuilder":
        """Add a character to the party."""
        if hp is None:
            hp = level * 6  # Rough approximation

        if ability_scores is None:
            ability_scores = {
                "STR": 12, "INT": 10, "WIS": 10,
                "DEX": 12, "CON": 12, "CHA": 10
            }

        char_id = f"test_{name.lower().replace(' ', '_')}"
        character = CharacterState(
            character_id=char_id,
            name=name,
            character_class=character_class,
            level=level,
            ability_scores=ability_scores,
            hp_current=hp,
            hp_max=hp,
            armor_class=9 if character_class == "Magic-User" else 7,
            base_speed=40,
        )
        self._characters.append(character)
        return self

    def with_sample_party(self) -> "VirtualDMTestBuilder":
        """Add a standard 3-character party."""
        self.with_character("Aldric", "Fighter", level=3, hp=24)
        self.with_character("Shadowmere", "Thief", level=2, hp=8)
        self.with_character("Brother Aldwin", "Cleric", level=2, hp=12)
        return self

    def with_hex(
        self,
        hex_id: str = "0705",
        name: str = "Test Hex",
        terrain_type: str = "forest",
        pois: Optional[list[PointOfInterest]] = None,
        npcs: Optional[list[HexNPC]] = None,
    ) -> "VirtualDMTestBuilder":
        """Add hex data to the test environment."""
        self._hex_data[hex_id] = HexLocation(
            hex_id=hex_id,
            name=name,
            terrain_type=terrain_type,
            points_of_interest=pois or [],
            npcs=npcs or [],
        )
        return self

    def with_poi(
        self,
        hex_id: str,
        poi_name: str,
        poi_type: str = "dwelling",
        npcs: Optional[list[str]] = None,
    ) -> "VirtualDMTestBuilder":
        """Add a POI to a hex."""
        if hex_id not in self._hex_data:
            self.with_hex(hex_id)

        poi = PointOfInterest(
            name=poi_name,
            poi_type=poi_type,
            description=f"A {poi_type} called {poi_name}",
            npcs=npcs or [],
        )
        self._hex_data[hex_id].points_of_interest.append(poi)
        self._current_poi = poi_name
        return self

    def with_mock_llm(self) -> "VirtualDMTestBuilder":
        """Use mock LLM provider."""
        self._llm_provider = "mock"
        self._enable_narration = False
        return self

    def with_narration(self, enabled: bool = True) -> "VirtualDMTestBuilder":
        """Enable/disable narration."""
        self._enable_narration = enabled
        return self

    def with_content(self, load: bool = True) -> "VirtualDMTestBuilder":
        """Enable/disable content loading."""
        self._load_content = load
        return self

    def with_save_dir(self, path: str) -> "VirtualDMTestBuilder":
        """Set save directory for save/load tests."""
        self._save_dir = path
        return self

    def build(self) -> VirtualDM:
        """Build and return the configured VirtualDM instance."""
        # Seed the dice roller
        DiceRoller.clear_roll_log()
        DiceRoller.set_seed(self._seed)

        # Build config
        config_kwargs: dict[str, Any] = {
            "llm_provider": self._llm_provider,
            "enable_narration": self._enable_narration,
            "load_content": self._load_content,
        }
        if self._save_dir:
            from pathlib import Path
            config_kwargs["save_dir"] = Path(self._save_dir)

        config = GameConfig(**config_kwargs)

        # Create VirtualDM
        dm = VirtualDM(
            config=config,
            initial_state=self._initial_state,
            game_date=self._game_date,
            game_time=self._game_time,
        )

        # Add characters
        for char in self._characters:
            dm.controller.add_character(char)

        # Set up hex data
        for hex_id, hex_data in self._hex_data.items():
            dm.hex_crawl._hex_data[hex_id] = hex_data

        # Set current POI if specified
        if self._current_poi:
            dm.hex_crawl._current_poi = self._current_poi
            dm.hex_crawl._current_poi_index = 0

        return dm

    # =========================================================================
    # PRESET CONFIGURATIONS
    # =========================================================================

    @classmethod
    def wilderness_dm(cls) -> VirtualDM:
        """Create a VirtualDM preset for wilderness travel testing."""
        return (cls()
            .with_state(GameState.WILDERNESS_TRAVEL)
            .with_sample_party()
            .with_mock_llm()
            .build())

    @classmethod
    def dungeon_dm(cls) -> VirtualDM:
        """Create a VirtualDM preset for dungeon exploration testing."""
        return (cls()
            .with_state(GameState.DUNGEON_EXPLORATION)
            .with_sample_party()
            .with_mock_llm()
            .build())

    @classmethod
    def settlement_dm(cls) -> VirtualDM:
        """Create a VirtualDM preset for settlement exploration testing."""
        return (cls()
            .with_state(GameState.SETTLEMENT_EXPLORATION)
            .with_sample_party()
            .with_mock_llm()
            .build())

    @classmethod
    def encounter_dm(cls) -> VirtualDM:
        """Create a VirtualDM preset for encounter testing."""
        return (cls()
            .with_state(GameState.ENCOUNTER)
            .with_sample_party()
            .with_mock_llm()
            .build())

    @classmethod
    def combat_dm(cls) -> VirtualDM:
        """Create a VirtualDM preset for combat testing."""
        return (cls()
            .with_state(GameState.COMBAT)
            .with_sample_party()
            .with_mock_llm()
            .build())


# =============================================================================
# LIGHTWEIGHT MOCK VIRTUAL DM
# =============================================================================


@dataclass
class MockLocation:
    """Mock location for testing."""
    location_id: str = "0705"
    hex_id: str = "0705"


@dataclass
class MockResources:
    """Mock party resources."""
    food_days: int = 10
    water_days: int = 10
    torches: int = 6
    lantern_oil_flasks: int = 4


@dataclass
class MockWorldState:
    """Mock world state for testing."""
    current_date: GameDate = field(default_factory=lambda: GameDate(year=1, month=6, day=15))
    current_time: GameTime = field(default_factory=lambda: GameTime(hour=10, minute=0))


@dataclass
class MockPartyState:
    """Mock party state for testing."""
    location: MockLocation = field(default_factory=MockLocation)
    active_light_source: Optional[str] = "torch"
    light_remaining_turns: int = 6
    resources: MockResources = field(default_factory=MockResources)


@dataclass
class MockCharacter:
    """Mock character for testing."""
    character_id: str = "mock_fighter"
    name: str = "Test Fighter"
    character_class: str = "Fighter"
    level: int = 3
    hp_current: int = 24
    hp_max: int = 24
    armor_class: int = 5
    base_speed: int = 30


class MockController:
    """Mock controller for testing."""

    def __init__(self):
        self.party_state = MockPartyState()
        self.world_state = MockWorldState()
        self._characters = [MockCharacter()]

    def get_active_characters(self):
        return self._characters

    def get_all_characters(self):
        return self._characters

    def transition(self, trigger, context=None):
        pass


class MockResolverResult:
    """Mock result from narrative resolver."""

    def __init__(self, narration: str = "Action resolved."):
        self.narration = narration
        self.apply_damage: list = []
        self.apply_conditions: list = []


class MockDungeonTurnResult:
    """Mock result from dungeon execute_turn."""

    def __init__(self):
        self.messages = ["Searched the room."]
        self.warnings: list = []
        self.action_result = {"message": "Found nothing."}


class MockVirtualDM:
    """
    Lightweight mock VirtualDM for unit testing.

    Use this when you need a VirtualDM-like object without the full
    initialization overhead. For integration tests, use VirtualDMTestBuilder.
    """

    def __init__(self, state: GameState = GameState.WILDERNESS_TRAVEL):
        self.current_state = state
        self.controller = MockController()
        self._dm_agent = None  # No LLM agent

        # Set up engine mocks
        self.hex_crawl = MagicMock()
        self.hex_crawl.handle_player_action = MagicMock(return_value=MockResolverResult())

        self.dungeon = MagicMock()
        self.dungeon.search_room = MagicMock(return_value={"found": [], "time_spent": 1})
        self.dungeon.handle_player_action = MagicMock(return_value=MockResolverResult())
        self.dungeon.execute_turn = MagicMock(return_value=MockDungeonTurnResult())

        self.encounter = MagicMock()
        self.encounter.handle_parley = MagicMock(return_value={"success": True})
        self.encounter.attempt_flee = MagicMock(return_value={"success": True})
        self.encounter.get_current_encounter = MagicMock(return_value=None)

        self.settlement = MagicMock()
        self.settlement.handle_player_action = MagicMock(return_value=MockResolverResult())

        self.downtime = MagicMock()
        self.downtime.handle_player_action = MagicMock(return_value=MockResolverResult())

        self.travel_to_hex = MagicMock(return_value={"success": True})

    def get_valid_actions(self):
        return []


# =============================================================================
# DETERMINISTIC SEEDING UTILITIES
# =============================================================================


def seed_all_randomness(seed: int = 42) -> None:
    """
    Seed all random number generators for deterministic tests.

    This should be called at the start of tests that need reproducibility.
    """
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(seed)


def reset_randomness() -> None:
    """
    Reset randomness state after a test.

    Call this in teardown to ensure clean state for next test.
    """
    DiceRoller.clear_roll_log()


# =============================================================================
# COMBATANT AND ENCOUNTER HELPERS
# =============================================================================


def create_test_combatant(
    name: str = "Test Enemy",
    side: str = "enemy",
    hp: int = 8,
    ac: int = 10,
) -> Combatant:
    """Create a simple test combatant."""
    import uuid
    return Combatant(
        combatant_id=f"{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}",
        name=name,
        side=side,
        stat_block=StatBlock(
            armor_class=ac,
            hit_dice="1d8",
            hp_current=hp,
            hp_max=hp,
            movement=30,
            attacks=[{"name": "Attack", "damage": "1d6", "bonus": 0}],
            morale=7,
        ),
    )


def create_test_encounter(
    num_enemies: int = 1,
    enemy_name: str = "Goblin",
    distance: int = 60,
) -> EncounterState:
    """Create a test encounter with enemies."""
    combatants = [
        create_test_combatant(
            name=f"{enemy_name} {i+1}" if num_enemies > 1 else enemy_name,
            side="enemy",
        )
        for i in range(num_enemies)
    ]

    return EncounterState(
        encounter_type=EncounterType.MONSTER,
        distance=distance,
        surprise_status=SurpriseStatus.NO_SURPRISE,
        actors=[enemy_name.lower()],
        context="wandering",
        terrain="forest",
        combatants=combatants,
    )
