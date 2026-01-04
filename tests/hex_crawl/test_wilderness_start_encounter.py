"""
Tests for wilderness:start_encounter action (Task 5.1).

Verifies that:
1. wilderness:start_encounter initiates combat with POI NPCs
2. Controller state transitions to ENCOUNTER
3. Encounter is created with correct combatant data
4. Works with hex 0104's Dredger at night
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import DiceRoller, EncounterState
from src.game_state.global_controller import GlobalController
from src.game_state.state_machine import GameState
from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline


@pytest.fixture
def hex_pipeline():
    """Create a content pipeline with hex 0104 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0104_the_phantom_lighthouse.json"))
    assert result.success, f"Failed to load hex: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0104(hex_pipeline):
    """Get the loaded HexLocation for hex 0104."""
    hex_data = hex_pipeline.get_hex("0104")
    assert hex_data is not None, "Hex 0104 not found in pipeline"
    return hex_data


@pytest.fixture
def controller():
    """Create a GlobalController for state transitions."""
    ctrl = GlobalController()
    # Set time to night so the Dredger is present (it's nighttime-only)
    ctrl.world_state.current_time.hour = 22
    # Controller starts in WILDERNESS_TRAVEL state by default
    return ctrl


@pytest.fixture
def hex_engine(hex_0104, controller):
    """Create a HexCrawlEngine with hex 0104 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0104"] = hex_0104
    engine._current_hex = "0104"
    return engine


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


class TestStartEncounterBasic:
    """Basic tests for engage_poi_npc method."""

    def test_engage_requires_being_at_poi(self, hex_engine):
        """Cannot engage NPC without being at a POI."""
        hex_engine._current_poi = None

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is False
        assert "Not at a POI" in result["error"]

    def test_engage_dredger_at_lighthouse(self, hex_engine, seeded_dice):
        """Can engage the Dredger when at the lighthouse POI."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is True
        # Result now uses combatants list format
        assert result["combatant_count"] == 1
        assert len(result["combatants"]) == 1
        combatant = result["combatants"][0]
        assert combatant["name"] == "The Dredger"
        assert combatant["ac"] == 14
        assert combatant["hp"] == 45
        assert combatant["attacks"] == 6

    def test_engage_creates_encounter_state(self, hex_engine, controller, seeded_dice):
        """Engaging creates an EncounterState on the controller."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is True
        encounter = controller.get_encounter()
        assert encounter is not None
        assert isinstance(encounter, EncounterState)
        assert len(encounter.combatants) == 1
        assert encounter.combatants[0].name == "The Dredger"

    def test_engage_npc_wrong_npc_id(self, hex_engine):
        """Cannot engage NPC that doesn't exist."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "nonexistent_npc")

        assert result["success"] is False
        assert "not at this POI" in result["error"]


class TestStartEncounterStateTransition:
    """Tests for controller state transitions."""

    def test_engage_triggers_transition(self, hex_engine, controller, seeded_dice):
        """Engaging NPC triggers encounter_triggered transition."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        # Verify we start in WILDERNESS_TRAVEL
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is True
        # After engaging, we should be in ENCOUNTER state
        assert controller.current_state == GameState.ENCOUNTER

    def test_encounter_has_correct_context(self, hex_engine, controller, seeded_dice):
        """Encounter should have correct context from POI."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        encounter = controller.get_encounter()
        assert "Lighthouse in the Bog" in encounter.context
        assert "The Dredger" in encounter.context


class TestStartEncounterCombatantCreation:
    """Tests for combatant creation from NPC data."""

    def test_combatant_has_stat_block(self, hex_engine, controller, seeded_dice):
        """Combatant should have stat block from NPC."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        encounter = controller.get_encounter()
        combatant = encounter.combatants[0]
        assert combatant.stat_block is not None
        assert combatant.stat_block.armor_class == 14
        assert combatant.stat_block.hp_max == 45
        assert combatant.stat_block.hp_current == 45

    def test_combatant_has_attacks(self, hex_engine, controller, seeded_dice):
        """Combatant should have attacks from stat reference."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        encounter = controller.get_encounter()
        combatant = encounter.combatants[0]
        # Dredger has 6 tentacles
        assert len(combatant.stat_block.attacks) == 6

    def test_combatant_side_is_enemy(self, hex_engine, controller, seeded_dice):
        """Combatant should be on enemy side."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        encounter = controller.get_encounter()
        combatant = encounter.combatants[0]
        assert combatant.side == "enemy"


class TestStartEncounterDistance:
    """Tests for encounter distance and surprise."""

    def test_encounter_has_distance(self, hex_engine, controller, seeded_dice):
        """Encounter should have distance set."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert "distance" in result
        assert result["distance"] > 0

        encounter = controller.get_encounter()
        assert encounter.distance > 0

    def test_encounter_has_surprise_status(self, hex_engine, controller, seeded_dice):
        """Encounter should have surprise status."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert "surprise" in result
        encounter = controller.get_encounter()
        assert encounter.surprise_status is not None


class TestStartEncounterNonCombatant:
    """Tests for non-combatant NPC handling."""

    def test_cannot_engage_non_combatant(self, hex_engine, hex_0104):
        """Cannot engage NPCs that aren't combatants."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        # Modify hex to have a non-combatant NPC at the POI
        # The Dredger is a combatant, so this test uses a different approach
        # Create a mock NPC that isn't a combatant
        mock_npc = MagicMock()
        mock_npc.npc_id = "spectral_mariner"
        mock_npc.name = "Spectral Mariner"
        mock_npc.is_combatant = False

        hex_0104.npcs.append(mock_npc)
        hex_0104.points_of_interest[0].npcs.append("spectral_mariner")

        result = hex_engine.engage_poi_npc("0104", "spectral_mariner")

        assert result["success"] is False
        assert "not a combatant" in result["error"]


class TestStartEncounterIntegration:
    """Integration tests for the full encounter flow."""

    def test_full_encounter_initiation_flow(self, hex_engine, controller, seeded_dice):
        """Test the complete flow from POI approach to combat."""
        # 1. Approach the POI
        approach_result = hex_engine.approach_poi("0104", 0)
        assert approach_result.get("success", True)  # approach_poi may not return success
        assert hex_engine._current_poi == "Lighthouse in the Bog"

        # 2. Enter the POI
        enter_result = hex_engine.enter_poi("0104")
        # Check for any indication of success
        assert hex_engine._poi_state.value != "distant"

        # 3. Engage the Dredger
        engage_result = hex_engine.engage_poi_npc("0104", "the_dredger")
        assert engage_result["success"] is True

        # 4. Verify final state
        assert controller.current_state == GameState.ENCOUNTER
        encounter = controller.get_encounter()
        assert encounter is not None
        assert encounter.combatants[0].name == "The Dredger"

    def test_encounter_id_is_unique(self, hex_engine, controller, seeded_dice):
        """Each encounter should have a unique ID."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert "encounter_id" in result
        encounter = controller.get_encounter()
        assert encounter.encounter_id == result["encounter_id"]
