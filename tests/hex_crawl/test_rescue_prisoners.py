"""
Tests for press-gang rescue mechanics (Task 9).

This test suite validates:
- prisoners_present effect is created with rolled counts
- get_prisoners_info returns prisoner details
- rescue_prisoners via stealth with skill check
- rescue_prisoners via combat (starts encounter)
- World state change logged on successful rescue
- Action registry integration
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.data_models import DiceRoller, GameDate, CharacterState
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine, POIVisit


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0109 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(
        Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
    )
    assert result.success, f"Failed to load hex 0109: {result.errors}"
    return pipeline


@pytest.fixture
def controller():
    """Create a GlobalController with a test character."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=3, day=15)
    char = CharacterState(
        character_id="rescuer_1",
        name="Brave Hero",
        character_class="Fighter",
        level=3,
        ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 14, "CON": 12, "CHA": 10},
        hp_current=20,
        hp_max=20,
        armor_class=16,
        base_speed=40,
    )
    controller.add_character(char)
    return controller


@pytest.fixture
def engine(controller, pipeline):
    """Create a HexCrawlEngine with hex 0109 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0109"] = pipeline.get_hex("0109")
    engine._current_hex = "0109"
    return engine


# =============================================================================
# PRISONERS_PRESENT EFFECT TESTS
# =============================================================================


class TestPrisonersPresentEffect:
    """Test that prisoners_present effect is created correctly."""

    def test_press_gang_entry_has_prisoners_effect(self, pipeline):
        """Press-Gang Returns entry should have prisoners_present effect."""
        hex_data = pipeline.get_hex("0109")

        # Find Murkin's Army POI
        poi = None
        for p in hex_data.points_of_interest:
            if p.name == "Murkin's Army":
                poi = p
                break

        assert poi is not None

        # Find Camp Activities table
        camp_table = None
        for table in poi.roll_tables:
            table_name = getattr(table, "name", None) or table.get("name")
            if table_name == "Camp Activities":
                camp_table = table
                break

        assert camp_table is not None

        # Find roll 3 entry (Press-Gang Returns)
        entries = getattr(camp_table, "entries", None) or camp_table.get("entries", [])
        press_gang_entry = None
        for entry in entries:
            roll_val = getattr(entry, "roll", None) or entry.get("roll")
            if roll_val == 3:
                press_gang_entry = entry
                break

        assert press_gang_entry is not None

        # Check mechanical_effect structure
        effect = getattr(press_gang_entry, "mechanical_effect", None)
        if effect is None and hasattr(press_gang_entry, "get"):
            effect = press_gang_entry.get("mechanical_effect")

        assert effect is not None
        assert effect.get("type") == "prisoners_present"
        assert effect.get("count") == "1d4"
        assert effect.get("guard_count") == "1d6"

    def test_roll_table_creates_prisoner_effect(self, engine):
        """Rolling press-gang result should create prisoners_present effect with counts."""
        with patch.object(engine.dice, "roll") as mock_roll:
            # Set up sequential returns: table roll, prisoner count, guard count
            mock_results = [
                MagicMock(total=3),  # Roll 3 on d6 = Press-Gang Returns
                MagicMock(total=3),  # 3 prisoners
                MagicMock(total=4),  # 4 guards
            ]
            mock_roll.side_effect = mock_results

            result = engine.roll_on_poi_table("0109", "Camp Activities", "Murkin's Army")

            # Check effect was stored with rolled values
            effects = engine.get_active_effects("0109", "Murkin's Army")
            prisoner_effect = None
            for e in effects:
                if e.get("type") == "prisoners_present":
                    prisoner_effect = e
                    break

            assert prisoner_effect is not None
            assert prisoner_effect.get("prisoner_count") == 3
            assert prisoner_effect.get("guard_count_rolled") == 4
            assert prisoner_effect.get("rescue_available") is True


class TestGetPrisonersInfo:
    """Test get_prisoners_info method."""

    def test_no_prisoners_returns_none(self, engine):
        """No prisoners effect should return None."""
        result = engine.get_prisoners_info("0109", "Murkin's Army")
        assert result is None

    def test_prisoners_present_returns_info(self, engine):
        """Should return prisoner info when effect is present."""
        # Manually set up prisoner effect
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 2,
                    "guard_count_rolled": 3,
                    "rescue_available": True,
                    "description": "Test prisoners",
                    "source": "Camp Activities",
                }
            ]
        )

        result = engine.get_prisoners_info("0109", "Murkin's Army")

        assert result is not None
        assert result["prisoner_count"] == 2
        assert result["guard_count"] == 3
        assert result["rescue_available"] is True


# =============================================================================
# STEALTH RESCUE TESTS
# =============================================================================


class TestStealthRescue:
    """Test stealth-based prisoner rescue."""

    def test_stealth_rescue_success(self, engine):
        """Successful stealth rescue should free prisoners."""
        engine._current_poi = "Murkin's Army"

        # Set up prisoner effect
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 3,
                    "guard_count_rolled": 2,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 6  # High roll - will succeed
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.rescue_prisoners("0109", "rescuer_1", method="stealth")

            assert result["success"] is True
            assert result["stealth_success"] is True
            assert result["prisoners_rescued"] == 3
            assert "message" in result
            assert "free" in result["message"].lower()

    def test_stealth_rescue_clears_effect(self, engine):
        """Successful rescue should clear prisoners effect."""
        engine._current_poi = "Murkin's Army"

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 2,
                    "guard_count_rolled": 1,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 6
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            engine.rescue_prisoners("0109", "rescuer_1", method="stealth")

            # Check prisoners are gone
            prisoners_info = engine.get_prisoners_info("0109", "Murkin's Army")
            assert prisoners_info is None

    def test_stealth_rescue_failure_triggers_combat(self, engine):
        """Failed stealth should trigger combat encounter."""
        engine._current_poi = "Murkin's Army"

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 2,
                    "guard_count_rolled": 4,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 1  # Low roll - will fail
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.rescue_prisoners("0109", "rescuer_1", method="stealth")

            assert result["success"] is False
            assert result["stealth_failed"] is True
            assert result["combat_triggered"] is True
            assert "encounter" in result
            assert result["encounter"]["name"] == "Prisoner Guards"

    def test_stealth_target_based_on_guards(self, engine):
        """More guards should increase stealth difficulty."""
        engine._current_poi = "Murkin's Army"

        # Few guards - target should be 4
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 1,
                    "guard_count_rolled": 1,  # Low guards
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 4
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.rescue_prisoners("0109", "rescuer_1", method="stealth")
            # With 1 guard: target = min(6, 4 + 0) = 4
            assert result.get("stealth_target") == 4


# =============================================================================
# COMBAT RESCUE TESTS
# =============================================================================


class TestCombatRescue:
    """Test combat-based prisoner rescue."""

    def test_combat_rescue_starts_encounter(self, engine):
        """Combat method should create encounter immediately."""
        engine._current_poi = "Murkin's Army"

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 4,
                    "guard_count_rolled": 3,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        result = engine.rescue_prisoners("0109", "rescuer_1", method="combat")

        assert result["success"] is True
        assert result["method"] == "combat"
        assert result["combat_initiated"] is True
        assert "encounter" in result
        assert result["guard_count"] == 3
        assert result["prisoners_count"] == 4

    def test_combat_encounter_has_guards(self, engine):
        """Combat encounter should have correct number of guards."""
        engine._current_poi = "Murkin's Army"

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 2,
                    "guard_count_rolled": 5,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        result = engine.rescue_prisoners("0109", "rescuer_1", method="combat")

        encounter = result["encounter"]
        assert encounter["creatures"][0]["count"] == 5
        assert encounter["creatures"][0]["name"] == "Soldier"

    def test_complete_combat_rescue(self, engine):
        """Completing combat rescue should free prisoners."""
        engine._current_poi = "Murkin's Army"

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 3,
                    "guard_count_rolled": 2,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        result = engine.complete_combat_rescue("0109", "Murkin's Army")

        assert result["success"] is True
        assert result["prisoners_rescued"] == 3

        # Check prisoners are cleared
        prisoners_info = engine.get_prisoners_info("0109", "Murkin's Army")
        assert prisoners_info is None


# =============================================================================
# WORLD STATE CHANGE TESTS
# =============================================================================


class TestWorldStateChanges:
    """Test that rescue logs world state changes."""

    def test_stealth_rescue_logs_change(self, engine):
        """Successful stealth rescue should log world state change."""
        engine._current_poi = "Murkin's Army"

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 2,
                    "guard_count_rolled": 1,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        initial_changes = len(engine._world_state_changes.changes)

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 6
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            engine.rescue_prisoners("0109", "rescuer_1", method="stealth")

        # Should have one new change
        assert len(engine._world_state_changes.changes) == initial_changes + 1

        # Check change details
        change = engine._world_state_changes.changes[-1]
        assert change.change_type == "rescue_success"
        assert change.trigger_action == "rescue_prisoners"
        assert change.trigger_details["method"] == "stealth"
        assert change.trigger_details["prisoner_count"] == 2

    def test_combat_rescue_logs_change(self, engine):
        """Completing combat rescue should log world state change."""
        engine._current_poi = "Murkin's Army"

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 4,
                    "guard_count_rolled": 3,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        initial_changes = len(engine._world_state_changes.changes)

        engine.complete_combat_rescue("0109", "Murkin's Army")

        assert len(engine._world_state_changes.changes) == initial_changes + 1

        change = engine._world_state_changes.changes[-1]
        assert change.trigger_details["method"] == "combat"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestRescueErrors:
    """Test error handling in rescue mechanics."""

    def test_no_prisoners_error(self, engine):
        """Should return error if no prisoners present."""
        engine._current_poi = "Murkin's Army"

        result = engine.rescue_prisoners("0109", "rescuer_1", method="stealth")

        assert result["success"] is False
        assert "error" in result
        assert "prisoners" in result["error"].lower()

    def test_not_at_poi_error(self, engine):
        """Should return error if not at a POI."""
        engine._current_poi = None

        result = engine.rescue_prisoners("0109", "rescuer_1", method="stealth")

        assert result["success"] is False
        assert "error" in result

    def test_invalid_method_error(self, engine):
        """Should return error for unknown rescue method."""
        engine._current_poi = "Murkin's Army"

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {
                    "type": "prisoners_present",
                    "prisoner_count": 1,
                    "guard_count_rolled": 1,
                    "rescue_available": True,
                    "source": "Camp Activities",
                }
            ]
        )

        result = engine.rescue_prisoners("0109", "rescuer_1", method="teleport")

        assert result["success"] is False
        assert "error" in result
        assert "unknown" in result["error"].lower()


# =============================================================================
# ACTION REGISTRY TESTS
# =============================================================================


class TestActionRegistry:
    """Test action registry integration."""

    def test_rescue_action_registered(self):
        """wilderness:rescue_prisoners should be registered."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:rescue_prisoners")

        assert spec is not None
        assert spec.executor is not None

    def test_rescue_action_params(self):
        """Rescue action should have correct parameters."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:rescue_prisoners")

        assert "character_id" in spec.params_schema
        assert spec.params_schema["character_id"]["required"] is True
        assert "method" in spec.params_schema

    def test_complete_combat_rescue_registered(self):
        """wilderness:complete_combat_rescue should be registered."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:complete_combat_rescue")

        assert spec is not None
