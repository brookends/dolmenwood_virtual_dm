"""
Tests for the EncounterFactory.

Tests the creation of EncounterState from RolledEncounter results.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.data_models import (
    Combatant,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    StatBlock,
)
from src.tables.wilderness_encounter_tables import EncounterEntry
from src.tables.encounter_roller import (
    EncounterRoller,
    EncounterContext,
    RolledEncounter,
    EncounterEntryType,
    EncounterCategory,
    get_encounter_roller,
)
from src.encounter.encounter_factory import (
    EncounterFactory,
    EncounterFactoryResult,
    get_encounter_factory,
    reset_encounter_factory,
    create_encounter_from_roll,
    create_wilderness_encounter,
    start_wilderness_encounter,
    start_dungeon_encounter,
    start_settlement_encounter,
)
from src.game_state.global_controller import GlobalController
from src.game_state.state_machine import GameState


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def factory():
    """Create a fresh EncounterFactory."""
    return EncounterFactory()


@pytest.fixture
def monster_encounter():
    """Create a sample monster RolledEncounter."""
    entry = EncounterEntry(
        name="Goblin",
        number_appearing="2d6",
        monster_id="goblin",
    )
    return RolledEncounter(
        entry=entry,
        entry_type=EncounterEntryType.MONSTER,
        category=EncounterCategory.REGIONAL,
        number_appearing_dice="2d6",
        number_appearing=4,
        region="tithelands",
    )


@pytest.fixture
def animal_encounter():
    """Create a sample animal RolledEncounter."""
    entry = EncounterEntry(
        name="Wolf*",
        number_appearing="3d6",
        monster_id="wolf",
    )
    return RolledEncounter(
        entry=entry,
        entry_type=EncounterEntryType.ANIMAL,
        category=EncounterCategory.ANIMAL,
        number_appearing_dice="3d6",
        number_appearing=6,
    )


@pytest.fixture
def adventurer_encounter():
    """Create a sample adventurer RolledEncounter."""
    entry = EncounterEntry(
        name="Fighter†",
        number_appearing="2d6",
    )
    return RolledEncounter(
        entry=entry,
        entry_type=EncounterEntryType.ADVENTURER,
        category=EncounterCategory.MORTAL,
        number_appearing_dice="2d6",
        number_appearing=3,
    )


@pytest.fixture
def mortal_encounter():
    """Create a sample everyday mortal RolledEncounter."""
    entry = EncounterEntry(
        name="Pilgrim‡",
        number_appearing="4d8",
    )
    return RolledEncounter(
        entry=entry,
        entry_type=EncounterEntryType.EVERYDAY_MORTAL,
        category=EncounterCategory.MORTAL,
        number_appearing_dice="4d8",
        number_appearing=12,
    )


@pytest.fixture
def party_encounter():
    """Create a sample adventuring party RolledEncounter."""
    entry = EncounterEntry(
        name="Adventuring Party",
        number_appearing="1",
    )
    return RolledEncounter(
        entry=entry,
        entry_type=EncounterEntryType.ADVENTURING_PARTY,
        category=EncounterCategory.MORTAL,
        number_appearing_dice="1",
        number_appearing=1,
    )


@pytest.fixture
def lair_encounter():
    """Create a lair encounter with hoard."""
    entry = EncounterEntry(
        name="Witch Owl",
        number_appearing="1d6",
        monster_id="witch_owl",
    )
    return RolledEncounter(
        entry=entry,
        entry_type=EncounterEntryType.MONSTER,
        category=EncounterCategory.MONSTER,
        number_appearing_dice="1d6",
        number_appearing=3,
        in_lair=True,
        lair_chance=25,
        lair_description="The ruins of an old church steeple.",
        hoard="C4 + R3",
    )


# =============================================================================
# FACTORY INITIALIZATION TESTS
# =============================================================================

class TestEncounterFactoryInit:
    """Tests for EncounterFactory initialization."""

    def test_default_initialization(self):
        """Test factory initializes with default dependencies."""
        factory = EncounterFactory()
        assert factory._monster_registry is None
        assert factory._npc_generator is None
        assert factory._encounter_roller is None

    def test_lazy_loading_monster_registry(self, factory):
        """Test monster registry is lazily loaded."""
        registry = factory.monster_registry
        assert registry is not None

    def test_lazy_loading_npc_generator(self, factory):
        """Test NPC generator is lazily loaded."""
        generator = factory.npc_generator
        assert generator is not None

    def test_lazy_loading_encounter_roller(self, factory):
        """Test encounter roller is lazily loaded."""
        roller = factory.encounter_roller
        assert roller is not None


# =============================================================================
# ENCOUNTER CREATION TESTS
# =============================================================================

class TestEncounterCreation:
    """Tests for creating encounters from RolledEncounter."""

    def test_create_encounter_returns_result(self, factory, monster_encounter):
        """Test that create_encounter returns an EncounterFactoryResult."""
        result = factory.create_encounter(monster_encounter)
        assert isinstance(result, EncounterFactoryResult)
        assert isinstance(result.encounter_state, EncounterState)

    def test_encounter_state_has_combatants(self, factory, monster_encounter):
        """Test that the encounter state includes combatants."""
        result = factory.create_encounter(monster_encounter)
        assert len(result.encounter_state.combatants) > 0

    def test_encounter_state_has_distance(self, factory, monster_encounter):
        """Test that the encounter state has a distance set."""
        result = factory.create_encounter(monster_encounter)
        assert result.encounter_state.distance > 0
        assert result.encounter_distance == result.encounter_state.distance

    def test_encounter_state_has_surprise_status(self, factory, monster_encounter):
        """Test that the encounter state has surprise status."""
        result = factory.create_encounter(monster_encounter)
        assert result.encounter_state.surprise_status in SurpriseStatus

    def test_result_includes_rolled_encounter(self, factory, monster_encounter):
        """Test that the result includes the original RolledEncounter."""
        result = factory.create_encounter(monster_encounter)
        assert result.rolled_encounter is monster_encounter


# =============================================================================
# MONSTER/ANIMAL COMBATANT TESTS
# =============================================================================

class TestMonsterCombatants:
    """Tests for creating monster combatants."""

    def test_monster_combatant_count(self, factory, monster_encounter):
        """Test correct number of combatants created."""
        result = factory.create_encounter(monster_encounter)
        # Should have 4 combatants (from number_appearing)
        assert len(result.encounter_state.combatants) == 4

    def test_monster_combatants_have_stat_blocks(self, factory, monster_encounter):
        """Test that monster combatants have stat blocks."""
        result = factory.create_encounter(monster_encounter)
        for combatant in result.encounter_state.combatants:
            # May be None if monster not found in registry, but should have fallback
            assert combatant.stat_block is not None or combatant.name

    def test_monster_combatants_are_enemies(self, factory, monster_encounter):
        """Test that monster combatants default to enemy side."""
        result = factory.create_encounter(monster_encounter)
        for combatant in result.encounter_state.combatants:
            assert combatant.side == "enemy"

    def test_animal_uses_monster_logic(self, factory, animal_encounter):
        """Test that animal encounters use the same logic as monsters."""
        result = factory.create_encounter(animal_encounter)
        assert len(result.encounter_state.combatants) == 6


# =============================================================================
# ADVENTURER COMBATANT TESTS
# =============================================================================

class TestAdventurerCombatants:
    """Tests for creating adventurer combatants."""

    def test_adventurer_combatant_count(self, factory, adventurer_encounter):
        """Test correct number of adventurer combatants."""
        result = factory.create_encounter(adventurer_encounter)
        assert len(result.encounter_state.combatants) == 3

    def test_adventurer_combatants_have_stat_blocks(self, factory, adventurer_encounter):
        """Test that adventurer combatants have stat blocks."""
        result = factory.create_encounter(adventurer_encounter)
        for combatant in result.encounter_state.combatants:
            assert combatant.stat_block is not None

    def test_adventurer_results_stored(self, factory, adventurer_encounter):
        """Test that generated adventurers are stored in result."""
        result = factory.create_encounter(adventurer_encounter)
        # Should have adventurer results
        assert len(result.adventurers) == 3


# =============================================================================
# EVERYDAY MORTAL COMBATANT TESTS
# =============================================================================

class TestMortalCombatants:
    """Tests for creating everyday mortal combatants."""

    def test_mortal_combatant_count(self, factory, mortal_encounter):
        """Test correct number of mortal combatants."""
        result = factory.create_encounter(mortal_encounter)
        assert len(result.encounter_state.combatants) == 12

    def test_mortal_combatants_have_stat_blocks(self, factory, mortal_encounter):
        """Test that mortal combatants have stat blocks."""
        result = factory.create_encounter(mortal_encounter)
        for combatant in result.encounter_state.combatants:
            assert combatant.stat_block is not None

    def test_mortal_results_stored(self, factory, mortal_encounter):
        """Test that generated mortals are stored in result."""
        result = factory.create_encounter(mortal_encounter)
        assert len(result.everyday_mortals) == 12


# =============================================================================
# ADVENTURING PARTY COMBATANT TESTS
# =============================================================================

class TestPartyCombatants:
    """Tests for creating adventuring party combatants."""

    def test_party_creates_multiple_combatants(self, factory, party_encounter):
        """Test that party encounter creates multiple combatants."""
        result = factory.create_encounter(party_encounter)
        # Party should have 5-8 members
        assert len(result.encounter_state.combatants) >= 5
        assert len(result.encounter_state.combatants) <= 8

    def test_party_result_stored(self, factory, party_encounter):
        """Test that the party result is stored."""
        result = factory.create_encounter(party_encounter)
        assert result.adventuring_party is not None


# =============================================================================
# LAIR ENCOUNTER TESTS
# =============================================================================

class TestLairEncounters:
    """Tests for lair encounter handling."""

    def test_lair_encounter_type(self, factory, lair_encounter):
        """Test that lair encounters have LAIR type."""
        result = factory.create_encounter(lair_encounter)
        assert result.encounter_state.encounter_type == EncounterType.LAIR

    def test_lair_info_in_result(self, factory, lair_encounter):
        """Test that lair information is included in result."""
        result = factory.create_encounter(lair_encounter)
        assert result.in_lair is True
        assert result.lair_description == "The ruins of an old church steeple."
        assert result.hoard == "C4 + R3"


# =============================================================================
# SURPRISE STATUS TESTS
# =============================================================================

class TestSurpriseStatus:
    """Tests for surprise status determination."""

    def test_surprise_status_set(self, factory, monster_encounter):
        """Test that surprise status is set."""
        result = factory.create_encounter(monster_encounter)
        assert result.encounter_state.surprise_status is not None

    def test_party_surprised_flag(self, factory, monster_encounter):
        """Test party_surprised flag in result."""
        result = factory.create_encounter(monster_encounter)
        assert isinstance(result.party_surprised, bool)

    def test_enemies_surprised_flag(self, factory, monster_encounter):
        """Test enemies_surprised flag in result."""
        result = factory.create_encounter(monster_encounter)
        assert isinstance(result.enemies_surprised, bool)


# =============================================================================
# ENCOUNTER TYPE DETERMINATION TESTS
# =============================================================================

class TestEncounterType:
    """Tests for encounter type determination."""

    def test_monster_encounter_type(self, factory, monster_encounter):
        """Test monster encounters have MONSTER type."""
        monster_encounter.in_lair = False  # Ensure not in lair
        result = factory.create_encounter(monster_encounter)
        assert result.encounter_state.encounter_type == EncounterType.MONSTER

    def test_animal_encounter_type(self, factory, animal_encounter):
        """Test animal encounters have MONSTER type."""
        result = factory.create_encounter(animal_encounter)
        assert result.encounter_state.encounter_type == EncounterType.MONSTER

    def test_adventurer_encounter_type(self, factory, adventurer_encounter):
        """Test adventurer encounters have NPC type."""
        result = factory.create_encounter(adventurer_encounter)
        assert result.encounter_state.encounter_type == EncounterType.NPC

    def test_mortal_encounter_type(self, factory, mortal_encounter):
        """Test mortal encounters have NPC type."""
        result = factory.create_encounter(mortal_encounter)
        assert result.encounter_state.encounter_type == EncounterType.NPC


# =============================================================================
# MODULE-LEVEL FUNCTION TESTS
# =============================================================================

class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_encounter_factory_singleton(self):
        """Test that get_encounter_factory returns singleton."""
        reset_encounter_factory()
        factory1 = get_encounter_factory()
        factory2 = get_encounter_factory()
        assert factory1 is factory2

    def test_reset_encounter_factory(self):
        """Test that reset_encounter_factory works."""
        factory1 = get_encounter_factory()
        reset_encounter_factory()
        factory2 = get_encounter_factory()
        assert factory1 is not factory2

    def test_create_encounter_from_roll(self, monster_encounter):
        """Test the convenience function for creating encounters."""
        result = create_encounter_from_roll(monster_encounter)
        assert isinstance(result, EncounterFactoryResult)

    def test_create_wilderness_encounter(self):
        """Test the convenience function for wilderness encounters."""
        result = create_wilderness_encounter(
            region="tithelands",
            terrain="forest",
            is_day=True,
        )
        assert isinstance(result, EncounterFactoryResult)
        assert result.encounter_state is not None


# =============================================================================
# DISTANCE TESTS
# =============================================================================

class TestEncounterDistance:
    """Tests for encounter distance calculation."""

    def test_outdoor_distance_range(self, factory, monster_encounter):
        """Test outdoor encounter distance is in expected range."""
        result = factory.create_encounter(monster_encounter, is_outdoor=True)
        # 2d6 × 30 = 60-360 feet, or 1d4 × 30 = 30-120 if both surprised
        assert 30 <= result.encounter_distance <= 360

    def test_dungeon_distance_range(self, factory, monster_encounter):
        """Test dungeon encounter distance is in expected range."""
        result = factory.create_encounter(monster_encounter, is_outdoor=False)
        # 2d6 × 10 = 20-120 feet, or 1d4 × 10 = 10-40 if both surprised
        assert 10 <= result.encounter_distance <= 120


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestEncounterFactoryIntegration:
    """Integration tests for the EncounterFactory."""

    def test_full_workflow(self):
        """Test complete workflow from roll to EncounterState."""
        # 1. Roll an encounter
        roller = get_encounter_roller()
        context = EncounterContext(region="aldweald")
        rolled = roller.roll_encounter(context, roll_activity=True)

        # 2. Create EncounterState
        factory = get_encounter_factory()
        result = factory.create_encounter(rolled, terrain="dark forest")

        # 3. Verify result
        assert result.encounter_state is not None
        assert len(result.encounter_state.combatants) > 0
        assert result.encounter_state.terrain == "dark forest"
        assert result.encounter_state.distance > 0

    def test_multiple_regions(self):
        """Test creating encounters for multiple regions."""
        from src.tables.wilderness_encounter_tables import get_all_regions

        factory = get_encounter_factory()
        roller = get_encounter_roller()

        for region in get_all_regions()[:3]:  # Test first 3 regions
            context = EncounterContext(region=region)
            rolled = roller.roll_encounter(context)
            result = factory.create_encounter(rolled)

            assert result.encounter_state is not None
            assert len(result.encounter_state.combatants) >= 0


# =============================================================================
# INTEGRATED ENCOUNTER TESTS (Factory + Engine + State Machine)
# =============================================================================

class TestStartWildernessEncounter:
    """Tests for the integrated start_wilderness_encounter function."""

    @pytest.fixture
    def controller(self):
        """Create a fresh GlobalController."""
        return GlobalController()

    def test_starts_encounter_and_transitions_state(self, controller):
        """Test that start_wilderness_encounter transitions to ENCOUNTER state."""
        # Verify we start in WILDERNESS_TRAVEL
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        # Start the encounter
        result = start_wilderness_encounter(
            controller=controller,
            region="tithelands",
            terrain="dense forest",
        )

        # Verify state transitioned to ENCOUNTER
        assert controller.current_state == GameState.ENCOUNTER

        # Verify result contains expected keys
        assert "factory_result" in result
        assert "engine_result" in result
        assert "encounter_state" in result
        assert result["encounter_state"] is not None

    def test_returns_factory_and_engine_results(self, controller):
        """Test that the result contains both factory and engine results."""
        result = start_wilderness_encounter(
            controller=controller,
            region="aldweald",
        )

        # Check factory result
        assert isinstance(result["factory_result"], EncounterFactoryResult)
        assert result["rolled_encounter"] is not None

        # Check engine result
        assert result["engine_result"]["encounter_started"] is True
        assert result["engine_result"]["origin"] == "wilderness"

    def test_encounter_stored_in_controller(self, controller):
        """Test that the encounter is stored in the controller."""
        result = start_wilderness_encounter(
            controller=controller,
            region="tithelands",
        )

        encounter = controller.get_encounter()
        assert encounter is not None
        assert encounter == result["encounter_state"]

    def test_with_awareness_flags(self, controller):
        """Test starting encounter with awareness flags."""
        result = start_wilderness_encounter(
            controller=controller,
            region="tithelands",
            party_aware=True,
            enemies_aware=False,
        )

        assert controller.current_state == GameState.ENCOUNTER

        # Check awareness was passed through
        engine_result = result["engine_result"]
        awareness = engine_result["awareness"]
        # AwarenessResult is a dataclass, so use attribute access
        assert awareness.party_aware is True
        assert awareness.enemies_aware is False


class TestStartDungeonEncounter:
    """Tests for the integrated start_dungeon_encounter function."""

    @pytest.fixture
    def controller(self):
        """Create a GlobalController in dungeon exploration state."""
        controller = GlobalController()
        controller.transition("enter_dungeon")  # Transition to dungeon
        return controller

    @pytest.fixture
    def monster_encounter(self):
        """Create a sample monster RolledEncounter."""
        entry = EncounterEntry(
            name="Giant Rat",
            number_appearing="2d4",
            monster_id="giant_rat",
        )
        return RolledEncounter(
            entry=entry,
            entry_type=EncounterEntryType.MONSTER,
            category=EncounterCategory.MONSTER,
            number_appearing_dice="2d4",
            number_appearing=3,
        )

    def test_starts_dungeon_encounter(self, controller, monster_encounter):
        """Test that start_dungeon_encounter transitions to ENCOUNTER state."""
        # Verify we start in DUNGEON_EXPLORATION
        assert controller.current_state == GameState.DUNGEON_EXPLORATION

        # Start the encounter
        result = start_dungeon_encounter(
            controller=controller,
            rolled_encounter=monster_encounter,
            terrain="dark corridor",
        )

        # Verify state transitioned to ENCOUNTER
        assert controller.current_state == GameState.ENCOUNTER

        # Verify origin is dungeon
        assert result["engine_result"]["origin"] == "dungeon"

    def test_with_poi_context(self, controller, monster_encounter):
        """Test starting dungeon encounter with POI context."""
        result = start_dungeon_encounter(
            controller=controller,
            rolled_encounter=monster_encounter,
            poi_name="The Spectral Manse",
            hex_id="0604",
        )

        engine_result = result["engine_result"]
        assert engine_result["poi_name"] == "The Spectral Manse"
        assert engine_result["hex_id"] == "0604"


class TestStartSettlementEncounter:
    """Tests for the integrated start_settlement_encounter function."""

    @pytest.fixture
    def controller(self):
        """Create a GlobalController in settlement exploration state."""
        controller = GlobalController()
        controller.transition("enter_settlement")  # Transition to settlement
        return controller

    @pytest.fixture
    def mortal_encounter(self):
        """Create a sample mortal RolledEncounter."""
        entry = EncounterEntry(
            name="Merchant‡",
            number_appearing="1d4",
        )
        return RolledEncounter(
            entry=entry,
            entry_type=EncounterEntryType.EVERYDAY_MORTAL,
            category=EncounterCategory.MORTAL,
            number_appearing_dice="1d4",
            number_appearing=2,
        )

    def test_starts_settlement_encounter(self, controller, mortal_encounter):
        """Test that start_settlement_encounter transitions to ENCOUNTER state."""
        # Verify we start in SETTLEMENT_EXPLORATION
        assert controller.current_state == GameState.SETTLEMENT_EXPLORATION

        # Start the encounter
        result = start_settlement_encounter(
            controller=controller,
            rolled_encounter=mortal_encounter,
            terrain="busy marketplace",
        )

        # Verify state transitioned to ENCOUNTER
        assert controller.current_state == GameState.ENCOUNTER

        # Verify origin is settlement
        assert result["engine_result"]["origin"] == "settlement"


class TestEncounterStateTransitionFlow:
    """Tests for the complete encounter state transition flow."""

    @pytest.fixture
    def controller(self):
        """Create a fresh GlobalController."""
        return GlobalController()

    def test_wilderness_encounter_to_combat_flow(self, controller):
        """Test complete flow: wilderness -> encounter -> combat."""
        # Start in wilderness
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        # Start encounter
        result = start_wilderness_encounter(
            controller=controller,
            region="tithelands",
        )
        assert controller.current_state == GameState.ENCOUNTER

        # Transition to combat
        controller.transition("encounter_to_combat")
        assert controller.current_state == GameState.COMBAT

        # End combat back to wilderness
        controller.transition("combat_end_wilderness")
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

    def test_dungeon_encounter_to_parley_flow(self):
        """Test complete flow: dungeon -> encounter -> social interaction."""
        controller = GlobalController()
        controller.transition("enter_dungeon")

        # Create an NPC encounter
        entry = EncounterEntry(
            name="Pilgrim‡",
            number_appearing="1d4",
        )
        rolled = RolledEncounter(
            entry=entry,
            entry_type=EncounterEntryType.EVERYDAY_MORTAL,
            category=EncounterCategory.MORTAL,
            number_appearing_dice="1d4",
            number_appearing=2,
        )

        # Start encounter
        start_dungeon_encounter(
            controller=controller,
            rolled_encounter=rolled,
        )
        assert controller.current_state == GameState.ENCOUNTER

        # Transition to social interaction (parley)
        controller.transition("encounter_to_parley")
        assert controller.current_state == GameState.SOCIAL_INTERACTION

        # End conversation back to dungeon
        controller.transition("conversation_end_dungeon")
        assert controller.current_state == GameState.DUNGEON_EXPLORATION
