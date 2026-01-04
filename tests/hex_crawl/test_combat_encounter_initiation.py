"""
Tests for combat encounter initiation from hazards and group_count handling.

Task 12 - Validates that:
1. engage_poi_npc expands group_count to create multiple combatants
2. Hazard resolution starts actual combat encounters
3. Controller transitions to ENCOUNTER state properly
4. Combat engine can resolve outcomes instead of narration-only
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.data_models import DiceRoller, EncounterState, Combatant
from src.game_state.global_controller import GlobalController
from src.game_state.state_machine import GameState
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0108 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    # 0108 has group_count NPCs (Grerg's Gang with 1d4+1d4)
    result = loader.load_file(
        Path("data/content/hexes/0108_the_cabbage_plot.json")
    )
    assert result.success, f"Failed to load hex 0108: {result.errors}"
    return pipeline


@pytest.fixture
def pipeline_0104():
    """Create a content pipeline with hex 0104 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(
        Path("data/content/hexes/0104_the_phantom_lighthouse.json")
    )
    assert result.success, f"Failed to load hex 0104: {result.errors}"
    return pipeline


@pytest.fixture
def controller():
    """Create a GlobalController."""
    ctrl = GlobalController()
    ctrl.world_state.current_time.hour = 22  # Night time for NPC presence
    return ctrl


@pytest.fixture
def engine(controller, pipeline):
    """Create a HexCrawlEngine with hex 0108 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0108"] = pipeline.get_hex("0108")
    engine._current_hex = "0108"
    return engine


@pytest.fixture
def engine_0104(controller, pipeline_0104):
    """Create a HexCrawlEngine with hex 0104 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0104"] = pipeline_0104.get_hex("0104")
    engine._current_hex = "0104"
    return engine


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


# =============================================================================
# GROUP COUNT TESTS - engage_poi_npc
# =============================================================================


class TestGroupCountExpansion:
    """Test that engage_poi_npc properly expands group_count NPCs."""

    def test_npc_with_static_group_count_creates_multiple_combatants(
        self, engine, seeded_dice
    ):
        """NPC with static group_count creates that many combatants."""
        # Create a mock NPC with static group_count
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "test_group"
        mock_npc.name = "Test Group"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = 3  # Static count
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        # Create a test POI
        test_poi = MagicMock()
        test_poi.name = "Test Area"
        test_poi.npcs = ["test_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Test Area"

        result = engine.engage_poi_npc("0108", "test_group")

        assert result["success"] is True
        assert result["combatant_count"] == 3
        assert len(result["combatants"]) == 3

    def test_npc_with_dice_group_count_rolls_for_combatant_count(
        self, engine, seeded_dice
    ):
        """NPC with dice expression group_count rolls for count."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "dice_group"
        mock_npc.name = "Dice Group"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = "1d4"  # Dice expression
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "Dice Test Area"
        test_poi.npcs = ["dice_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Dice Test Area"

        result = engine.engage_poi_npc("0108", "dice_group")

        assert result["success"] is True
        # With seed 42, 1d4 should give a consistent result
        assert result["combatant_count"] >= 1
        assert result["combatant_count"] <= 4
        assert len(result["combatants"]) == result["combatant_count"]

    def test_single_npc_without_group_count_creates_one_combatant(
        self, engine_0104, controller, seeded_dice
    ):
        """Single NPC without group_count creates exactly one combatant."""
        engine_0104._current_poi = "Lighthouse in the Bog"

        result = engine_0104.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is True
        assert result["combatant_count"] == 1

    def test_group_combatants_have_numbered_names(self, engine, controller, seeded_dice):
        """Group combatants should have numbered names like 'Name #1'."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "numbered_group"
        mock_npc.name = "Soldier"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = 3
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "Numbered Test Area"
        test_poi.npcs = ["numbered_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Numbered Test Area"

        result = engine.engage_poi_npc("0108", "numbered_group")

        assert result["success"] is True
        encounter = controller.get_encounter()
        assert encounter is not None
        names = [c.name for c in encounter.combatants]
        assert "Soldier #1" in names
        assert "Soldier #2" in names
        assert "Soldier #3" in names

    def test_group_info_included_in_result(self, engine, seeded_dice):
        """Result should include group_info for group NPCs."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "info_group"
        mock_npc.name = "Info Group"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = "2d4"
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "Info Test Area"
        test_poi.npcs = ["info_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Info Test Area"

        result = engine.engage_poi_npc("0108", "info_group")

        assert result["success"] is True
        assert result["group_info"] is not None
        assert result["group_info"]["is_group"] is True
        assert "total_count" in result["group_info"]


# =============================================================================
# ENCOUNTER STATE TESTS
# =============================================================================


class TestEncounterStateCreation:
    """Test that encounter state is properly created for groups."""

    def test_encounter_has_all_group_combatants(self, engine, controller, seeded_dice):
        """EncounterState should contain all group combatants."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "enc_group"
        mock_npc.name = "Encounter Group"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = 4
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "Encounter Test Area"
        test_poi.npcs = ["enc_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Encounter Test Area"

        result = engine.engage_poi_npc("0108", "enc_group")

        assert result["success"] is True
        encounter = controller.get_encounter()
        assert encounter is not None
        assert len(encounter.combatants) == 4

    def test_all_combatants_are_enemies(self, engine, controller, seeded_dice):
        """All group combatants should be on enemy side."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "enemy_group"
        mock_npc.name = "Enemy Group"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = 3
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "Enemy Test Area"
        test_poi.npcs = ["enemy_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Enemy Test Area"

        engine.engage_poi_npc("0108", "enemy_group")

        encounter = controller.get_encounter()
        for combatant in encounter.combatants:
            assert combatant.side == "enemy"

    def test_each_combatant_has_unique_id(self, engine, controller, seeded_dice):
        """Each combatant in a group should have a unique ID."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "unique_group"
        mock_npc.name = "Unique Group"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = 5
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "Unique Test Area"
        test_poi.npcs = ["unique_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Unique Test Area"

        engine.engage_poi_npc("0108", "unique_group")

        encounter = controller.get_encounter()
        ids = [c.combatant_id for c in encounter.combatants]
        assert len(ids) == len(set(ids))  # All IDs are unique

    def test_group_encounter_transitions_to_encounter_state(
        self, engine, controller, seeded_dice
    ):
        """Engaging group NPC should transition to ENCOUNTER state."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "state_group"
        mock_npc.name = "State Group"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = 2
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "State Test Area"
        test_poi.npcs = ["state_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "State Test Area"

        # Start in wilderness travel
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        engine.engage_poi_npc("0108", "state_group")

        # Should now be in encounter state
        assert controller.current_state == GameState.ENCOUNTER


# =============================================================================
# HAZARD COMBAT INITIATION TESTS
# =============================================================================


class TestHazardCombatInitiation:
    """Test that hazards properly initiate combat encounters."""

    def test_create_encounter_from_hazard_returns_encounter_state(
        self, engine, seeded_dice
    ):
        """create_encounter_from_hazard should return EncounterState."""
        # Create a mock hazard result that triggers NPC encounter
        hazard_result = {
            "triggered": True,
            "result": "grerg",  # An NPC ID in hex 0108
            "description": "Grerg's gang ambushes you!",
        }
        context = {"hex_id": "0108", "trigger_type": "evening_stay"}

        # Need to mock finding the NPC
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "grerg"
        mock_npc.name = "Grerg"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = None
        mock_npc.group_composition = None
        hex_data.npcs.append(mock_npc)

        encounter = engine.create_encounter_from_hazard(hazard_result, context)

        # Should return an EncounterState
        assert encounter is not None
        assert isinstance(encounter, EncounterState)

    def test_hazard_encounter_has_combatants(self, engine, seeded_dice):
        """Hazard-created encounter should have combatants."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "hazard_npc"
        mock_npc.name = "Hazard Enemy"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = None
        mock_npc.group_composition = None
        hex_data.npcs.append(mock_npc)

        hazard_result = {
            "triggered": True,
            "result": "hazard_npc",
            "description": "An enemy appears!",
        }
        context = {"hex_id": "0108", "trigger_type": "investigation"}

        encounter = engine.create_encounter_from_hazard(hazard_result, context)

        assert encounter is not None
        assert len(encounter.combatants) >= 1

    def test_non_triggered_hazard_returns_none(self, engine):
        """Non-triggered hazard should return None."""
        hazard_result = {
            "triggered": False,
            "result": None,
        }
        context = {"hex_id": "0108"}

        encounter = engine.create_encounter_from_hazard(hazard_result, context)

        assert encounter is None

    def test_hazard_encounter_has_source_info(self, engine, seeded_dice):
        """Hazard encounter should have source info in contextual_data."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "source_npc"
        mock_npc.name = "Source Enemy"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = None
        mock_npc.group_composition = None
        hex_data.npcs.append(mock_npc)

        hazard_result = {
            "triggered": True,
            "result": "source_npc",
            "description": "Enemy appears!",
        }
        context = {"hex_id": "0108", "trigger_type": "evening_stay"}

        encounter = engine.create_encounter_from_hazard(hazard_result, context)

        assert encounter is not None
        assert encounter.contextual_data is not None
        assert encounter.contextual_data.get("source") == "hazard"
        assert encounter.contextual_data.get("trigger_type") == "evening_stay"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestCombatEncounterIntegration:
    """Integration tests for the full combat encounter flow."""

    def test_full_group_engagement_flow(self, engine, controller, seeded_dice):
        """Test the complete flow from POI to combat with group NPC."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "flow_group"
        mock_npc.name = "Flow Group"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = 3
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "Flow Test Area"
        test_poi.npcs = ["flow_group"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Flow Test Area"

        # 1. Engage the group
        result = engine.engage_poi_npc("0108", "flow_group")
        assert result["success"] is True

        # 2. Verify we're in ENCOUNTER state
        assert controller.current_state == GameState.ENCOUNTER

        # 3. Verify encounter has correct combatant count
        encounter = controller.get_encounter()
        assert encounter is not None
        assert len(encounter.combatants) == 3

        # 4. Verify each combatant has stat block
        for combatant in encounter.combatants:
            assert combatant.stat_block is not None

    def test_single_npc_engagement_still_works(
        self, engine_0104, controller, seeded_dice
    ):
        """Test that single NPC engagement still works correctly."""
        engine_0104._current_poi = "Lighthouse in the Bog"

        result = engine_0104.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is True
        assert result["combatant_count"] == 1
        assert controller.current_state == GameState.ENCOUNTER

        encounter = controller.get_encounter()
        assert len(encounter.combatants) == 1
        assert encounter.combatants[0].name == "The Dredger"

    def test_encounter_ready_for_combat_resolution(
        self, engine, controller, seeded_dice
    ):
        """Encounter should be ready for combat engine resolution."""
        hex_data = engine._hex_data["0108"]
        mock_npc = MagicMock()
        mock_npc.npc_id = "combat_ready"
        mock_npc.name = "Combat Ready"
        mock_npc.is_combatant = True
        mock_npc.stat_reference = "Level 1 AC 12 HP 8 Att Sword (+1, 1d8)"
        mock_npc.group_count = 2
        mock_npc.group_composition = None
        mock_npc.time_presence = None
        hex_data.npcs.append(mock_npc)

        test_poi = MagicMock()
        test_poi.name = "Combat Ready Area"
        test_poi.npcs = ["combat_ready"]
        test_poi.restricted_times = []
        hex_data.points_of_interest.append(test_poi)

        engine._current_poi = "Combat Ready Area"

        engine.engage_poi_npc("0108", "combat_ready")

        encounter = controller.get_encounter()

        # Encounter should have all necessary attributes for combat
        assert encounter.distance > 0
        assert encounter.surprise_status is not None
        assert all(c.stat_block for c in encounter.combatants)
        # Combatants should have HP for tracking damage
        for combatant in encounter.combatants:
            if combatant.stat_block:
                assert combatant.stat_block.hp_max > 0
                assert combatant.stat_block.hp_current > 0
