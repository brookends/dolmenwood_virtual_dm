"""
Tests for stealth departure (leave_poi_stealth) functionality.

This test suite validates:
- Skill-based stealth checks for leaving POIs
- Successful departure goes unnoticed
- Failed departure at Hunting Lodge triggers Brynne pursuit
- Pursuit encounter data is properly constructed
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.data_models import DiceRoller, GameDate, CharacterState
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine


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
        character_id="thief_1",
        name="Sneaky Pete",
        character_class="Thief",
        level=3,
        ability_scores={"STR": 10, "INT": 12, "WIS": 10, "DEX": 16, "CON": 12, "CHA": 10},
        hp_current=15,
        hp_max=15,
        armor_class=13,
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
# BASIC METHOD TESTS
# =============================================================================


class TestLeavePOIStealthExists:
    """Test that the leave_poi_stealth method exists and has proper signature."""

    def test_method_exists(self, engine):
        """leave_poi_stealth method should exist on engine."""
        assert hasattr(engine, "leave_poi_stealth")
        assert callable(engine.leave_poi_stealth)

    def test_returns_dict(self, engine):
        """Method should return a dictionary."""
        # Set current POI first
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 6
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.leave_poi_stealth("0109", "thief_1")

                assert isinstance(result, dict)


# =============================================================================
# STEALTH SUCCESS TESTS
# =============================================================================


class TestStealthDepartureSuccess:
    """Test successful stealth departure."""

    def test_high_roll_succeeds(self, engine):
        """High stealth roll should allow undetected departure."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 6  # High roll
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            assert result.get("success") is True
            assert result.get("stealth_success") is True
            assert result.get("pursuit_triggered") is False

    def test_success_clears_current_poi(self, engine):
        """Successful departure should clear current POI."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 6
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            assert result.get("success") is True
            assert engine._current_poi is None

    def test_success_message_mentions_unnoticed(self, engine):
        """Success message should mention leaving unnoticed."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 6
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            message = result.get("message", "").lower()
            assert "unnoticed" in message or "slip" in message


# =============================================================================
# STEALTH FAILURE TESTS
# =============================================================================


class TestStealthDepartureFailure:
    """Test failed stealth departure."""

    def test_low_roll_fails(self, engine):
        """Low stealth roll should fail stealth check."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 1  # Low roll
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            assert result.get("stealth_success") is False
            assert result.get("stealth_failed") is True

    def test_failure_still_leaves_poi(self, engine):
        """Failed stealth should still leave the POI."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 1
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            # Should still successfully leave (just detected)
            assert result.get("success") is True
            assert engine._current_poi is None


# =============================================================================
# BRYNNE PURSUIT TESTS
# =============================================================================


class TestBrynnePursuit:
    """Test Brynne pursuit at the Hunting Lodge."""

    def test_brynne_npc_exists(self, engine):
        """Brynne should exist as an NPC in hex 0109."""
        hex_data = engine._hex_data["0109"]

        brynne = None
        for npc in hex_data.npcs:
            # Handle both HexNPC objects and legacy dict format
            npc_id = getattr(npc, "npc_id", None) or (npc.get("npc_id") if isinstance(npc, dict) else None)
            if npc_id == "brynne_giant_weasel":
                brynne = npc
                break

        assert brynne is not None, "Brynne should exist as NPC"
        npc_name = getattr(brynne, "name", None) or brynne.get("name")
        assert npc_name == "Brynne"

    def test_brynne_has_pursuit_trigger(self, engine):
        """Brynne should have pursuit trigger for the Lodge."""
        hex_data = engine._hex_data["0109"]

        brynne = None
        for npc in hex_data.npcs:
            npc_id = getattr(npc, "npc_id", None) or (npc.get("npc_id") if isinstance(npc, dict) else None)
            if npc_id == "brynne_giant_weasel":
                brynne = npc
                break

        assert brynne is not None
        trigger = getattr(brynne, "pursuit_trigger", None) or (brynne.get("pursuit_trigger") if isinstance(brynne, dict) else None)
        assert trigger is not None
        assert trigger.get("poi_name") == "Lady Borrid's Hunting Lodge"
        assert trigger.get("tracking_bonus") == 2

    def test_failed_stealth_triggers_brynne(self, engine):
        """Failed stealth at Lodge should trigger Brynne pursuit."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 1  # Low roll - will fail
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            assert result.get("pursuit_triggered") is True
            assert "pursuit_encounter" in result

            pursuit = result["pursuit_encounter"]
            assert pursuit.get("pursuer_name") == "Brynne"
            assert pursuit.get("pursuer_id") == "brynne_giant_weasel"

    def test_pursuit_includes_stat_block(self, engine):
        """Pursuit encounter should include Brynne's stat block."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 1
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            assert result.get("pursuit_triggered") is True
            pursuit = result["pursuit_encounter"]
            stat_block = pursuit.get("stat_block")

            assert stat_block is not None
            assert stat_block.get("hit_dice") == "4+4"
            assert stat_block.get("armor_class") == 13

    def test_pursuit_message_mentions_brynne(self, engine):
        """Pursuit message should mention Brynne."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 1
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            message = result.get("message", "")
            assert "Brynne" in message


# =============================================================================
# TRACKING BONUS TESTS
# =============================================================================


class TestTrackingBonus:
    """Test that tracking bonus affects difficulty."""

    def test_lodge_has_higher_target(self, engine):
        """Hunting Lodge should have higher stealth target due to Brynne's tracking."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 5  # Moderate roll
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            # Base target (4) + Brynne's tracking bonus (2) = 6
            assert result.get("stealth_target") == 6

    def test_camp_has_normal_target(self, engine):
        """Camp without pursuit NPC should have normal target."""
        engine._current_poi = "Murkin's Army"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 4
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            # No pursuit trigger at camp, so base target of 4
            assert result.get("stealth_target") == 4


# =============================================================================
# NO PURSUIT AT OTHER LOCATIONS
# =============================================================================


class TestNoPursuitAtOtherLocations:
    """Test that pursuit doesn't trigger at locations without pursuit NPCs."""

    def test_camp_no_pursuit_on_failure(self, engine):
        """Failed stealth at camp should not trigger pursuit."""
        engine._current_poi = "Murkin's Army"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 1  # Low roll
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            assert result.get("stealth_failed") is True
            assert result.get("pursuit_triggered") is False
            assert "pursuit_encounter" not in result


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestStealthDepartureErrors:
    """Test error handling for stealth departure."""

    def test_not_at_poi(self, engine):
        """Should return error if not at a POI."""
        engine._current_poi = None

        result = engine.leave_poi_stealth("0109", "thief_1")

        assert result.get("success") is False
        assert "error" in result

    def test_invalid_hex(self, engine):
        """Should return error for invalid hex."""
        engine._current_poi = "Some POI"

        result = engine.leave_poi_stealth("9999", "thief_1")

        assert result.get("success") is False
        assert "error" in result


# =============================================================================
# ACTION REGISTRY TESTS
# =============================================================================


class TestActionRegistryIntegration:
    """Test that the action is properly registered."""

    def test_action_registered(self):
        """wilderness:leave_poi_stealth should be registered."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:leave_poi_stealth")

        assert spec is not None
        assert spec.executor is not None

    def test_action_has_correct_params(self):
        """Action should have correct parameter schema."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:leave_poi_stealth")

        assert "character_id" in spec.params_schema
        assert spec.params_schema["character_id"]["required"] is True


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestHuntingLodgeDeparture:
    """Integration tests for Hunting Lodge stealth departure."""

    def test_full_stealth_success_flow(self, engine):
        """Test complete successful stealth departure."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 6  # High roll - will succeed
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            assert result["success"] is True
            assert result["stealth_success"] is True
            assert result["pursuit_triggered"] is False
            assert engine._current_poi is None

    def test_full_pursuit_flow(self, engine):
        """Test complete Brynne pursuit flow."""
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 1  # Low roll - will fail
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.leave_poi_stealth("0109", "thief_1")

            # Should leave but with pursuit
            assert result["success"] is True
            assert result["stealth_success"] is False
            assert result["pursuit_triggered"] is True

            # Should have full pursuit encounter data
            pursuit = result["pursuit_encounter"]
            assert pursuit["pursuer_name"] == "Brynne"
            assert pursuit["type"] == "pursuit"
            assert pursuit["stat_block"] is not None

            # Should no longer be at POI
            assert engine._current_poi is None
