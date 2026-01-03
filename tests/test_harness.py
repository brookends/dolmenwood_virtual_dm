"""
Tests for P2-12: Deterministic test harness.

Verifies that:
1. VirtualDMTestBuilder creates properly configured VirtualDM instances
2. MockVirtualDM provides a lightweight testing interface
3. Seeded dice produce reproducible results
4. Mock oracle/LLM fixtures work correctly
"""

import pytest

from src.data_models import DiceRoller
from src.game_state.state_machine import GameState
from tests.helpers import (
    VirtualDMTestBuilder,
    MockVirtualDM,
    seed_all_randomness,
    reset_randomness,
    create_test_combatant,
    create_test_encounter,
)


# =============================================================================
# TESTS: VirtualDMTestBuilder
# =============================================================================


class TestVirtualDMTestBuilder:
    """Test VirtualDMTestBuilder functionality."""

    def test_builds_virtual_dm_with_defaults(self, seeded_dice):
        """Builder should create a working VirtualDM with defaults."""
        dm = VirtualDMTestBuilder().build()

        assert dm is not None
        assert dm.current_state == GameState.WILDERNESS_TRAVEL

    def test_sets_initial_state(self, seeded_dice):
        """Builder should set initial game state."""
        dm = (VirtualDMTestBuilder()
            .with_state(GameState.DUNGEON_EXPLORATION)
            .build())

        assert dm.current_state == GameState.DUNGEON_EXPLORATION

    def test_adds_character(self, seeded_dice):
        """Builder should add characters to the party."""
        dm = (VirtualDMTestBuilder()
            .with_character("Test Hero", "Fighter", level=5)
            .build())

        characters = dm.controller.get_all_characters()
        assert len(characters) == 1
        assert characters[0].name == "Test Hero"
        assert characters[0].level == 5

    def test_adds_sample_party(self, seeded_dice):
        """Builder should add a standard party."""
        dm = (VirtualDMTestBuilder()
            .with_sample_party()
            .build())

        characters = dm.controller.get_all_characters()
        assert len(characters) == 3
        names = [c.name for c in characters]
        assert "Aldric" in names
        assert "Shadowmere" in names

    def test_sets_game_date(self, seeded_dice):
        """Builder should set game date."""
        dm = (VirtualDMTestBuilder()
            .with_date(year=5, month=10, day=25)
            .build())

        assert dm.controller.world_state.current_date.year == 5
        assert dm.controller.world_state.current_date.month == 10
        assert dm.controller.world_state.current_date.day == 25

    def test_sets_game_time(self, seeded_dice):
        """Builder should set game time."""
        dm = (VirtualDMTestBuilder()
            .with_time(hour=14, minute=30)
            .build())

        assert dm.controller.world_state.current_time.hour == 14
        assert dm.controller.world_state.current_time.minute == 30

    def test_uses_mock_llm(self, seeded_dice):
        """Builder should use mock LLM by default."""
        dm = (VirtualDMTestBuilder()
            .with_mock_llm()
            .build())

        # dm_agent should be None or mock when LLM is mocked
        assert dm._dm_agent is None or not hasattr(dm._dm_agent, 'real_client')

    def test_preset_wilderness_dm(self, seeded_dice):
        """wilderness_dm preset should create wilderness-ready VirtualDM."""
        dm = VirtualDMTestBuilder.wilderness_dm()

        assert dm.current_state == GameState.WILDERNESS_TRAVEL
        assert len(dm.controller.get_all_characters()) == 3

    def test_preset_dungeon_dm(self, seeded_dice):
        """dungeon_dm preset should create dungeon-ready VirtualDM."""
        dm = VirtualDMTestBuilder.dungeon_dm()

        assert dm.current_state == GameState.DUNGEON_EXPLORATION
        assert len(dm.controller.get_all_characters()) == 3

    def test_preset_settlement_dm(self, seeded_dice):
        """settlement_dm preset should create settlement-ready VirtualDM."""
        dm = VirtualDMTestBuilder.settlement_dm()

        assert dm.current_state == GameState.SETTLEMENT_EXPLORATION

    def test_chaining_methods(self, seeded_dice):
        """Builder methods should be chainable."""
        dm = (VirtualDMTestBuilder()
            .with_seed(123)
            .with_state(GameState.ENCOUNTER)
            .with_date(year=2, month=3, day=4)
            .with_time(hour=15, minute=45)
            .with_character("Hero", "Fighter")
            .with_mock_llm()
            .build())

        assert dm is not None
        assert dm.current_state == GameState.ENCOUNTER


# =============================================================================
# TESTS: MockVirtualDM
# =============================================================================


class TestMockVirtualDM:
    """Test MockVirtualDM lightweight mock."""

    def test_creates_mock_with_default_state(self):
        """Mock should have default wilderness travel state."""
        dm = MockVirtualDM()

        assert dm.current_state == GameState.WILDERNESS_TRAVEL

    def test_creates_mock_with_custom_state(self):
        """Mock should accept custom state."""
        dm = MockVirtualDM(state=GameState.DUNGEON_EXPLORATION)

        assert dm.current_state == GameState.DUNGEON_EXPLORATION

    def test_has_controller(self):
        """Mock should have a controller."""
        dm = MockVirtualDM()

        assert dm.controller is not None
        assert hasattr(dm.controller, 'party_state')

    def test_has_engine_mocks(self):
        """Mock should have engine mocks."""
        dm = MockVirtualDM()

        assert dm.hex_crawl is not None
        assert dm.dungeon is not None
        assert dm.encounter is not None
        assert dm.settlement is not None
        assert dm.downtime is not None

    def test_get_valid_actions_returns_empty(self):
        """Mock get_valid_actions should return empty list."""
        dm = MockVirtualDM()

        assert dm.get_valid_actions() == []


# =============================================================================
# TESTS: Seeded Dice Determinism
# =============================================================================


class TestSeededDiceDeterminism:
    """Test that seeded dice produce reproducible results."""

    def test_same_seed_produces_same_rolls(self, seeded_dice_factory):
        """Same seed should produce identical roll sequences."""
        seeded_dice_factory(seed=42)
        rolls1 = [DiceRoller.roll("1d20").total for _ in range(10)]

        seeded_dice_factory(seed=42)
        rolls2 = [DiceRoller.roll("1d20").total for _ in range(10)]

        assert rolls1 == rolls2

    def test_different_seeds_produce_different_rolls(self, seeded_dice_factory):
        """Different seeds should produce different sequences."""
        seeded_dice_factory(seed=42)
        rolls1 = [DiceRoller.roll("1d20").total for _ in range(10)]

        seeded_dice_factory(seed=123)
        rolls2 = [DiceRoller.roll("1d20").total for _ in range(10)]

        assert rolls1 != rolls2

    def test_seed_all_randomness_utility(self):
        """seed_all_randomness should seed the DiceRoller."""
        seed_all_randomness(seed=999)
        roll1 = DiceRoller.roll("1d20").total

        seed_all_randomness(seed=999)
        roll2 = DiceRoller.roll("1d20").total

        assert roll1 == roll2
        reset_randomness()


# =============================================================================
# TESTS: Combatant and Encounter Helpers
# =============================================================================


class TestCombatantHelpers:
    """Test combatant and encounter helper functions."""

    def test_create_test_combatant(self):
        """create_test_combatant should create valid combatant."""
        combatant = create_test_combatant(name="Test Goblin", hp=5, ac=12)

        assert combatant.name == "Test Goblin"
        assert combatant.side == "enemy"
        assert combatant.stat_block is not None
        assert combatant.stat_block.hp_current == 5
        assert combatant.stat_block.armor_class == 12

    def test_create_test_encounter(self):
        """create_test_encounter should create valid encounter."""
        encounter = create_test_encounter(num_enemies=3, enemy_name="Orc")

        assert len(encounter.combatants) == 3
        assert encounter.encounter_type is not None
        for c in encounter.combatants:
            assert "Orc" in c.name


# =============================================================================
# TESTS: Conftest Fixtures
# =============================================================================


class TestConftestFixtures:
    """Test that conftest fixtures work correctly."""

    def test_seeded_dice_fixture(self, seeded_dice):
        """seeded_dice fixture should provide reproducible rolls."""
        roll = DiceRoller.roll("1d20").total
        assert 1 <= roll <= 20

    def test_temp_save_dir_fixture(self, temp_save_dir):
        """temp_save_dir should provide a valid path."""
        assert temp_save_dir.exists()
        assert temp_save_dir.is_dir()

    def test_dm_builder_fixture(self, dm_builder, seeded_dice):
        """dm_builder fixture should provide builder class."""
        dm = dm_builder().with_state(GameState.COMBAT).build()
        assert dm.current_state == GameState.COMBAT

    def test_mock_virtual_dm_fixture(self, mock_virtual_dm):
        """mock_virtual_dm fixture should provide MockVirtualDM."""
        assert mock_virtual_dm.current_state == GameState.WILDERNESS_TRAVEL

    def test_mock_virtual_dm_factory_fixture(self, mock_virtual_dm_factory):
        """mock_virtual_dm_factory should create mocks with custom state."""
        dm = mock_virtual_dm_factory(GameState.DUNGEON_EXPLORATION)
        assert dm.current_state == GameState.DUNGEON_EXPLORATION


# =============================================================================
# TESTS: Mock Oracle
# =============================================================================


class TestMockOracle:
    """Test mock oracle fixture."""

    def test_mock_oracle_fate_check(self, mock_mythic_oracle):
        """Mock oracle should return configured fate results."""
        mock_mythic_oracle.set_fate_result("No", roll=75)

        result = mock_mythic_oracle.fate_check("Is it raining?")

        assert result.answer == "No"
        assert result.roll == 75

    def test_mock_oracle_meaning_table(self, mock_mythic_oracle):
        """Mock oracle should return configured meaning results."""
        mock_mythic_oracle.set_meaning_result("pursue", "goals")

        result = mock_mythic_oracle.meaning_table("action")

        assert result == ("pursue", "goals")


# =============================================================================
# TESTS: Mock DM Agent
# =============================================================================


class TestMockDMAgent:
    """Test mock DM agent fixture."""

    def test_mock_dm_agent_narration(self, mock_dm_agent, mock_dm_agent_responses):
        """Mock DM agent should return configured narration."""
        mock_dm_agent_responses["narration"] = "Custom test narration."

        result = mock_dm_agent.narrate_resolved_action(None)

        assert result.success is True
        assert result.content == "Custom test narration."

    def test_mock_dm_agent_is_available(self, mock_dm_agent):
        """Mock DM agent should report as available."""
        assert mock_dm_agent.is_available() is True
