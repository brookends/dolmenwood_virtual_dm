"""
Pytest fixtures for Dolmenwood Virtual DM test suite.

Provides reusable test fixtures for game state, characters, encounters,
and LLM mocking.
"""

import pytest
from typing import Optional

from src.data_models import (
    DiceRoller,
    GameDate,
    GameTime,
    Season,
    Weather,
    LocationType,
    CharacterState,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    Combatant,
    StatBlock,
    PartyState,
    PartyResources,
    Location,
    LocationState,
    WorldState,
    NPC,
    HexLocation,
)
from src.game_state.state_machine import GameState, StateMachine
from src.game_state.global_controller import GlobalController
from src.encounter.encounter_engine import EncounterEngine, EncounterOrigin
from src.combat.combat_engine import CombatEngine
from src.ai.llm_provider import LLMConfig, LLMProvider, LLMManager, MockLLMClient
from src.ai.dm_agent import DMAgent, DMAgentConfig


# =============================================================================
# DICE FIXTURES
# =============================================================================


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


@pytest.fixture
def clean_dice():
    """Provide a clean DiceRoller without seed."""
    DiceRoller.clear_roll_log()
    yield DiceRoller()
    DiceRoller.clear_roll_log()


# =============================================================================
# TIME AND DATE FIXTURES
# =============================================================================


@pytest.fixture
def game_date():
    """Default game date for testing."""
    return GameDate(year=1, month=6, day=15)


@pytest.fixture
def game_time():
    """Default game time for testing (10:00 AM)."""
    return GameTime(hour=10, minute=0)


# =============================================================================
# CHARACTER FIXTURES
# =============================================================================


@pytest.fixture
def sample_fighter():
    """A sample fighter character for testing."""
    return CharacterState(
        character_id="fighter_1",
        name="Aldric the Bold",
        character_class="Fighter",
        level=3,
        ability_scores={
            "STR": 16,
            "INT": 10,
            "WIS": 12,
            "DEX": 14,
            "CON": 15,
            "CHA": 11,
        },
        hp_current=24,
        hp_max=24,
        armor_class=4,  # Chain + shield
        movement_rate=90,
    )


@pytest.fixture
def sample_thief():
    """A sample thief character for testing."""
    return CharacterState(
        character_id="thief_1",
        name="Shadowmere",
        character_class="Thief",
        level=2,
        ability_scores={
            "STR": 10,
            "INT": 13,
            "WIS": 9,
            "DEX": 17,
            "CON": 12,
            "CHA": 14,
        },
        hp_current=8,
        hp_max=8,
        armor_class=6,  # Leather
        movement_rate=120,
    )


@pytest.fixture
def sample_cleric():
    """A sample cleric character for testing."""
    return CharacterState(
        character_id="cleric_1",
        name="Brother Aldwin",
        character_class="Cleric",
        level=2,
        ability_scores={
            "STR": 12,
            "INT": 11,
            "WIS": 16,
            "DEX": 10,
            "CON": 14,
            "CHA": 13,
        },
        hp_current=12,
        hp_max=12,
        armor_class=5,  # Chain
        movement_rate=60,
    )


@pytest.fixture
def sample_party(sample_fighter, sample_thief, sample_cleric):
    """A complete party of three adventurers."""
    return [sample_fighter, sample_thief, sample_cleric]


# =============================================================================
# MONSTER/COMBATANT FIXTURES
# =============================================================================


@pytest.fixture
def goblin_stat_block():
    """Stat block for a goblin."""
    return StatBlock(
        armor_class=6,
        hit_dice="1d8-1",
        hp_current=4,
        hp_max=4,
        movement=60,
        attacks=[{"name": "Short sword", "damage": "1d6", "bonus": 0}],
        morale=7,
        save_as="Normal Man",
    )


@pytest.fixture
def orc_stat_block():
    """Stat block for an orc."""
    return StatBlock(
        armor_class=6,
        hit_dice="1d8",
        hp_current=5,
        hp_max=5,
        movement=90,
        attacks=[{"name": "Battleaxe", "damage": "1d8", "bonus": 1}],
        morale=8,
        save_as="Fighter 1",
    )


@pytest.fixture
def sample_combatants(sample_fighter, goblin_stat_block):
    """Sample combatants for combat tests."""
    party_combatant = Combatant(
        combatant_id=sample_fighter.character_id,
        name=sample_fighter.name,
        side="party",
        stat_block=StatBlock(
            armor_class=sample_fighter.armor_class,
            hit_dice="3d8",
            hp_current=sample_fighter.hp_current,
            hp_max=sample_fighter.hp_max,
            movement=sample_fighter.movement_rate,
            attacks=[{"name": "Sword", "damage": "1d8+1", "bonus": 3}],
            morale=12,
        ),
        character_ref=sample_fighter.character_id,
    )

    enemy_combatant = Combatant(
        combatant_id="goblin_1",
        name="Goblin",
        side="enemy",
        stat_block=goblin_stat_block,
    )

    return [party_combatant, enemy_combatant]


# =============================================================================
# ENCOUNTER FIXTURES
# =============================================================================


@pytest.fixture
def basic_encounter(sample_combatants):
    """A basic encounter for testing."""
    encounter = EncounterState(
        encounter_type=EncounterType.MONSTER,
        distance=60,
        surprise_status=SurpriseStatus.NO_SURPRISE,
        actors=["goblin"],
        context="patrolling",
        terrain="forest",
        combatants=sample_combatants,
    )
    return encounter


@pytest.fixture
def surprise_encounter(sample_combatants):
    """An encounter where enemies are surprised."""
    encounter = EncounterState(
        encounter_type=EncounterType.MONSTER,
        distance=30,
        surprise_status=SurpriseStatus.ENEMIES_SURPRISED,
        actors=["goblin"],
        context="sleeping",
        terrain="dungeon",
        combatants=sample_combatants,
    )
    return encounter


# =============================================================================
# LOCATION FIXTURES
# =============================================================================


@pytest.fixture
def forest_hex():
    """A sample forest hex location."""
    return HexLocation(
        hex_id="0709",
        name="The Whispering Glade",
        terrain_type="forest",
        terrain="forest",
        tagline="Ancient oaks whisper secrets to those who listen",
        description="A peaceful glade within the deep forest.",
        region="Dolmenwood",
        lost_chance=1,
        encounter_chance=1,
    )


@pytest.fixture
def dungeon_room():
    """A sample dungeon room."""
    return LocationState(
        location_type=LocationType.DUNGEON_ROOM,
        location_id="room_1",
        terrain="stone",
        name="Guard Chamber",
        light_level="dark",
        visited=False,
    )


@pytest.fixture
def settlement():
    """A sample settlement."""
    return LocationState(
        location_type=LocationType.SETTLEMENT,
        location_id="prigwort",
        terrain="settlement",
        name="Prigwort",
        buildings=["Inn", "Market", "Temple"],
        services=["Rest", "Supplies", "Healing"],
        population=350,
        visited=True,
    )


# =============================================================================
# NPC FIXTURES
# =============================================================================


@pytest.fixture
def sample_npc():
    """A sample NPC for dialogue testing."""
    return NPC(
        npc_id="innkeeper_1",
        name="Old Maggie",
        title="Innkeeper",
        location="Prigwort",
        personality="Gruff but kindhearted, suspicious of strangers",
        goals=["Keep her inn profitable", "Protect the village secrets"],
        secrets=["Knows about the hidden Drune circle", "Her son is a werewolf"],
        dialogue_hooks=[
            "Mutters about the old days",
            "Warns travelers about the deep woods",
        ],
    )


# =============================================================================
# GAME STATE FIXTURES
# =============================================================================


@pytest.fixture
def state_machine():
    """A fresh state machine starting in wilderness travel."""
    return StateMachine(GameState.WILDERNESS_TRAVEL)


@pytest.fixture
def state_machine_dungeon():
    """A state machine starting in dungeon exploration."""
    return StateMachine(GameState.DUNGEON_EXPLORATION)


@pytest.fixture
def global_controller(game_date, game_time):
    """A fully initialized global controller."""
    controller = GlobalController(
        initial_state=GameState.WILDERNESS_TRAVEL,
        game_date=game_date,
        game_time=game_time,
    )
    return controller


@pytest.fixture
def controller_with_party(global_controller, sample_party):
    """A global controller with a party of characters."""
    for character in sample_party:
        global_controller.add_character(character)
    global_controller.party_state.resources.food_days = 10
    global_controller.party_state.resources.water_days = 10
    global_controller.party_state.resources.torches = 6
    global_controller.party_state.resources.lantern_oil_flasks = 4
    return global_controller


# =============================================================================
# ENGINE FIXTURES
# =============================================================================


@pytest.fixture
def encounter_engine(controller_with_party):
    """An encounter engine with a fully initialized controller."""
    return EncounterEngine(controller_with_party)


@pytest.fixture
def combat_engine(controller_with_party):
    """A combat engine with a fully initialized controller."""
    return CombatEngine(controller_with_party)


# =============================================================================
# LLM/AI FIXTURES
# =============================================================================


@pytest.fixture
def mock_llm_config():
    """LLM configuration using mock provider."""
    return LLMConfig(
        provider=LLMProvider.MOCK,
        model="mock",
        max_tokens=1024,
        temperature=0.7,
    )


@pytest.fixture
def mock_llm_manager(mock_llm_config):
    """LLM manager with mock provider."""
    return LLMManager(mock_llm_config)


@pytest.fixture
def mock_llm_client(mock_llm_config):
    """A mock LLM client for testing."""
    client = MockLLMClient(mock_llm_config)
    client.set_responses([
        "The ancient forest stretches before you, dappled sunlight filtering through the canopy.",
        "The goblin snarls and brandishes its crude blade.",
        "Steel clashes against steel as the battle rages on.",
    ])
    return client


@pytest.fixture
def dm_agent_config():
    """DM Agent configuration with mock provider."""
    return DMAgentConfig(
        llm_provider=LLMProvider.MOCK,
        llm_model="mock",
        max_tokens=1024,
        temperature=0.7,
        cache_responses=False,  # Disable caching for tests
        validate_all_responses=True,
    )


@pytest.fixture
def dm_agent(dm_agent_config):
    """A DM Agent using mock LLM."""
    from src.ai.dm_agent import reset_dm_agent
    reset_dm_agent()  # Clear singleton
    return DMAgent(dm_agent_config)


# =============================================================================
# WORLD STATE FIXTURES
# =============================================================================


@pytest.fixture
def summer_weather():
    """World state for summer with clear weather."""
    return WorldState(
        current_date=GameDate(year=1, month=7, day=15),
        current_time=GameTime(hour=14, minute=0),
        season=Season.SUMMER,
        weather=Weather.CLEAR,
    )


@pytest.fixture
def winter_storm():
    """World state for winter storm conditions."""
    return WorldState(
        current_date=GameDate(year=1, month=1, day=10),
        current_time=GameTime(hour=16, minute=0),
        season=Season.WINTER,
        weather=Weather.BLIZZARD,
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_test_character(
    name: str = "Test Hero",
    character_class: str = "Fighter",
    level: int = 1,
    hp: int = 10,
) -> CharacterState:
    """Helper to create a test character with minimal setup."""
    return CharacterState(
        character_id=f"test_{name.lower().replace(' ', '_')}",
        name=name,
        character_class=character_class,
        level=level,
        ability_scores={
            "STR": 12, "INT": 10, "WIS": 10,
            "DEX": 12, "CON": 12, "CHA": 10,
        },
        hp_current=hp,
        hp_max=hp,
        armor_class=9,
        movement_rate=120,
    )


def create_test_encounter(
    num_enemies: int = 1,
    enemy_name: str = "Goblin",
    distance: int = 60,
) -> EncounterState:
    """Helper to create a test encounter."""
    combatants = []
    for i in range(num_enemies):
        combatants.append(Combatant(
            combatant_id=f"{enemy_name.lower()}_{i+1}",
            name=f"{enemy_name} {i+1}" if num_enemies > 1 else enemy_name,
            side="enemy",
            stat_block=StatBlock(
                armor_class=7,
                hit_dice="1d8",
                hp_current=4,
                hp_max=4,
                movement=60,
                attacks=[{"name": "Attack", "damage": "1d6", "bonus": 0}],
                morale=7,
            ),
        ))

    return EncounterState(
        encounter_type=EncounterType.MONSTER,
        distance=distance,
        surprise_status=SurpriseStatus.NO_SURPRISE,
        actors=[enemy_name.lower()],
        context="wandering",
        terrain="forest",
        combatants=combatants,
    )
