"""
Tests for stealth camp entry (sneak_into_poi) functionality.

This test suite validates:
- Skill-based stealth checks using skill_resolver
- Successful infiltration avoids hazards and enters POI
- Failed infiltration triggers investigation hazard (camp alarm)
- Sentry count affects difficulty
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
    # Add a test character with all required fields
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


class TestSneakIntoPOIExists:
    """Test that the sneak_into_poi method exists and has proper signature."""

    def test_method_exists(self, engine):
        """sneak_into_poi method should exist on engine."""
        assert hasattr(engine, "sneak_into_poi")
        assert callable(engine.sneak_into_poi)

    def test_returns_dict(self, engine):
        """Method should return a dictionary."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            result = engine.sneak_into_poi(
                "0109", "Murkin's Army", "thief_1"
            )

            assert isinstance(result, dict)


# =============================================================================
# STEALTH SUCCESS TESTS
# =============================================================================


class TestStealthSuccess:
    """Test successful stealth infiltration."""

    def test_high_roll_succeeds(self, engine):
        """High stealth roll should succeed."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6  # High roll
            mock_roll.return_value = mock_result

            # Mock skill resolver to return high roll
            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 6
                mock_skill_result.success = True
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                assert result.get("success") is True
                assert result.get("stealth_success") is True

    def test_success_enters_poi(self, engine):
        """Successful stealth should set current POI."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 1  # Sentry roll (low)
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 6
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                assert result.get("success") is True
                assert engine._current_poi == "Murkin's Army"

    def test_success_message_mentions_undetected(self, engine):
        """Success message should mention being undetected."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 2
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 6
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                message = result.get("message", "").lower()
                assert "undetected" in message or "sneak" in message

    def test_success_includes_poi_info(self, engine):
        """Success result should include POI information."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 2
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 6
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                assert "poi_name" in result
                assert result["poi_name"] == "Murkin's Army"
                assert "poi_type" in result


# =============================================================================
# STEALTH FAILURE TESTS
# =============================================================================


class TestStealthFailure:
    """Test failed stealth infiltration."""

    def test_low_roll_fails(self, engine):
        """Low stealth roll should fail."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 3  # Moderate sentry count
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 1  # Low roll - will fail
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                assert result.get("success") is False
                assert result.get("stealth_failed") is True

    def test_failure_triggers_hazard(self, engine):
        """Failed stealth should trigger investigation hazard."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 3
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 1
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                # Should indicate hazard was triggered
                assert "hazard_result" in result
                assert result.get("hazard_result") == "camp_alarm"

    def test_failure_message_mentions_spotted(self, engine):
        """Failure message should mention being spotted."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 3
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 1
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                message = result.get("message", "").lower()
                assert "spotted" in message or "alarm" in message

    def test_failure_does_not_enter_poi(self, engine):
        """Failed stealth should not enter the POI."""
        engine._current_poi = None

        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 3
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 1
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                assert result.get("success") is False
                assert engine._current_poi is None


# =============================================================================
# SENTRY COUNT TESTS
# =============================================================================


class TestSentryCountDifficulty:
    """Test that sentry count affects stealth difficulty."""

    def test_no_sentries_easier(self, engine):
        """No sentries should make stealth easier (lower target)."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 0  # No sentries
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 4  # Moderate roll
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                # Target should be 4 with 0 sentries
                assert result.get("stealth_target") == 4

    def test_medium_sentries_moderate(self, engine):
        """2-4 sentries should have moderate target (5)."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 3  # 3 sentries
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 5
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                # Target should be 5 with 3 sentries
                assert result.get("stealth_target") == 5

    def test_many_sentries_harder(self, engine):
        """5+ sentries should make stealth harder (target 6)."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6  # 6 sentries
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 6
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                # Target should be 6 with 6 sentries
                assert result.get("stealth_target") == 6

    def test_sentry_count_in_result(self, engine):
        """Result should include sentry count."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 4
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 6
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                assert "sentry_count" in result
                assert result["sentry_count"] == 4


# =============================================================================
# STEALTH MODIFIER TESTS
# =============================================================================


class TestStealthModifier:
    """Test that stealth modifier affects the roll."""

    def test_positive_modifier_helps(self, engine):
        """Positive modifier should increase effective roll."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 2  # Low sentry count
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 3  # Would fail without modifier
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1",
                    stealth_modifier=2  # +2 makes effective roll 5
                )

                assert result.get("stealth_modifier") == 2
                assert result.get("effective_roll") == 5

    def test_negative_modifier_hurts(self, engine):
        """Negative modifier should decrease effective roll."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 2
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 5  # Would succeed normally
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1",
                    stealth_modifier=-2  # -2 makes effective roll 3
                )

                assert result.get("stealth_modifier") == -2
                assert result.get("effective_roll") == 3


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestStealthErrors:
    """Test error handling in stealth infiltration."""

    def test_invalid_hex(self, engine):
        """Invalid hex should return error."""
        result = engine.sneak_into_poi("9999", "Some Place", "thief_1")

        assert result.get("success") is False
        assert "error" in result

    def test_invalid_poi(self, engine):
        """Invalid POI name should return error."""
        result = engine.sneak_into_poi(
            "0109", "Nonexistent Location", "thief_1"
        )

        assert result.get("success") is False
        assert "not found" in result.get("error", "").lower()

    def test_hidden_poi_not_visible(self, engine):
        """Hidden POI should not be sneakable if not discovered."""
        result = engine.sneak_into_poi(
            "0109", "Lady Borrid's Hidden Vault", "thief_1"
        )

        assert result.get("success") is False
        assert "cannot find" in result.get("error", "").lower()


# =============================================================================
# ACTION REGISTRY TESTS
# =============================================================================


class TestActionRegistryIntegration:
    """Test that the action is properly registered."""

    def test_action_registered(self):
        """wilderness:sneak_into_poi should be registered."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:sneak_into_poi")

        assert spec is not None
        assert spec.executor is not None

    def test_action_has_correct_params(self):
        """Action should have correct parameter schema."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:sneak_into_poi")

        assert "poi_name" in spec.params_schema
        assert spec.params_schema["poi_name"]["required"] is True
        assert "character_id" in spec.params_schema
        assert spec.params_schema["character_id"]["required"] is True


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestMurkinsArmyInfiltration:
    """Integration tests for Murkin's Army camp infiltration."""

    def test_camp_has_sentries(self, engine):
        """Murkin's Army should have variable sentries defined."""
        hex_data = engine._hex_data["0109"]
        camp = next(
            p for p in hex_data.points_of_interest
            if p.name == "Murkin's Army"
        )

        assert camp.variable_inhabitants is not None
        # Check that there's a sentry/patrol definition
        variable = camp.variable_inhabitants.get("variable", [])
        has_sentries = any(
            any(keyword in v.get("description", "").lower()
                for keyword in ["sentry", "sentries", "patrol", "guard"])
            for v in variable
        )
        assert has_sentries, "Camp should have sentry/patrol definition"

    def test_full_infiltration_flow_success(self, engine):
        """Test complete successful infiltration flow."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 2  # Low sentry count
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 6  # High stealth roll
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                # Should succeed
                assert result["success"] is True
                assert result["stealth_success"] is True

                # Should enter camp
                assert engine._current_poi == "Murkin's Army"

                # Should have interior description available
                assert result.get("interior") is not None

    def test_full_infiltration_flow_failure(self, engine):
        """Test complete failed infiltration flow."""
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 4  # Moderate sentry count
            mock_roll.return_value = mock_result

            with patch(
                "src.resolution.skill_resolver.get_skill_resolver"
            ) as mock_resolver:
                mock_skill_result = MagicMock()
                mock_skill_result.roll = 1  # Low stealth roll
                mock_resolver.return_value.resolve_skill_check.return_value = (
                    mock_skill_result
                )

                result = engine.sneak_into_poi(
                    "0109", "Murkin's Army", "thief_1"
                )

                # Should fail
                assert result["success"] is False
                assert result["stealth_failed"] is True

                # Should trigger camp alarm
                assert result.get("hazard_result") == "camp_alarm"

                # Should NOT enter camp
                assert engine._current_poi != "Murkin's Army"
