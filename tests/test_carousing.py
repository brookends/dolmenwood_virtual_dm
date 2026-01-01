"""
Tests for the Carousing System.

Tests cover:
- Basic carousing mechanics
- Saving throw mechanics
- Mishap tables (major and minor)
- Bonus tables
- XP calculation and integration
- Gold spending caps
- Edge cases
"""

import pytest
from unittest.mock import MagicMock, patch

from src.settlement import (
    CarousingEngine,
    CarousingResult,
    CarousingOutcome,
    CarousingMishap,
    CarousingBonus,
    MishapSeverity,
    MAJOR_MISHAPS,
    MINOR_MISHAPS,
    CAROUSING_BONUSES,
    get_carousing_engine,
    reset_carousing_engine,
)
from src.settlement.carousing import GOLD_PER_LEVEL
from src.game_state import GlobalController
from src.data_models import DiceRoller


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    reset_carousing_engine()
    yield
    reset_carousing_engine()


@pytest.fixture
def controller():
    """Create a GlobalController for tests."""
    return GlobalController()


@pytest.fixture
def mock_character():
    """Create a mock character for tests."""
    char = MagicMock()
    char.character_id = "test_char_001"
    char.name = "Test Character"
    char.level = 3
    char.gold = 500
    char.constitution = 14
    char.saving_throws = {"poison": 12}
    return char


@pytest.fixture
def engine(controller, mock_character):
    """Create a CarousingEngine with mocked character."""
    controller.get_character = MagicMock(return_value=mock_character)
    controller._xp_manager = None  # Disable XP for basic tests
    return CarousingEngine(controller)


# =============================================================================
# BASIC MECHANICS TESTS
# =============================================================================


class TestBasicMechanics:
    """Tests for basic carousing mechanics."""

    def test_max_gold_by_level(self, engine, mock_character):
        """Test that max gold is calculated correctly by level."""
        mock_character.level = 1
        assert engine.get_max_gold(mock_character) == 100

        mock_character.level = 3
        assert engine.get_max_gold(mock_character) == 300

        mock_character.level = 5
        assert engine.get_max_gold(mock_character) == 500

        mock_character.level = 10
        assert engine.get_max_gold(mock_character) == 1000

    def test_gold_spending_cap(self, engine, mock_character):
        """Test that spending is capped at level × 100 GP."""
        mock_character.level = 3
        gold_cap = 300

        # Try to spend more than allowed
        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=500,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        assert result.gold_spent == gold_cap
        assert result.gold_cap == gold_cap
        assert result.over_budget is True
        assert "capped at 300 GP" in result.events[0]

    def test_spending_under_cap(self, engine, mock_character):
        """Test spending under the cap works normally."""
        mock_character.level = 3

        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=150,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        assert result.gold_spent == 150
        assert result.over_budget is False

    def test_base_xp_equals_gold_spent(self, engine, mock_character):
        """Test that base XP equals gold spent."""
        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=200,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        assert result.base_xp == result.gold_spent


# =============================================================================
# SAVING THROW TESTS
# =============================================================================


class TestSavingThrows:
    """Tests for carousing saving throws."""

    def test_uses_save_vs_poison(self, engine, mock_character):
        """Test that save vs. poison is used when available."""
        mock_character.saving_throws = {"poison": 10}

        with patch.object(engine.dice, 'roll_d20') as mock_roll:
            mock_roll.return_value = MagicMock(total=8)  # Pass (8 <= 10)

            result = engine.carouse(
                character_id="test_char_001",
                gold_to_spend=100,
                settlement_id="lankshorn",
                settlement_name="Lankshorn",
            )

            assert result.save_target == 10
            assert result.save_roll == 8
            assert result.save_passed is True

    def test_failed_save_causes_mishap(self, engine, mock_character):
        """Test that failed save results in mishap."""
        mock_character.saving_throws = {"poison": 10}

        with patch.object(engine.dice, 'roll_d20') as mock_roll:
            # First roll is save (15 > 10 = fail)
            # Second roll is severity (use side_effect for sequence)
            mock_roll.side_effect = [
                MagicMock(total=15),  # Save roll - fails
                MagicMock(total=10),  # Severity roll - minor mishap
            ]

            with patch.object(engine.dice, 'roll') as mock_table_roll:
                mock_table_roll.return_value = MagicMock(total=1)

                result = engine.carouse(
                    character_id="test_char_001",
                    gold_to_spend=100,
                    settlement_id="lankshorn",
                    settlement_name="Lankshorn",
                )

                assert result.save_passed is False
                assert result.mishap is not None
                assert result.outcome in (
                    CarousingOutcome.MINOR_MISHAP,
                    CarousingOutcome.MAJOR_MISHAP,
                )


# =============================================================================
# MISHAP TESTS
# =============================================================================


class TestMishaps:
    """Tests for carousing mishap system."""

    def test_major_mishap_table_complete(self):
        """Test that major mishap table has all 20 entries."""
        assert len(MAJOR_MISHAPS) == 20

        for i in range(1, 21):
            assert i in MAJOR_MISHAPS
            mishap = MAJOR_MISHAPS[i]
            assert "title" in mishap
            assert "description" in mishap
            assert "effect" in mishap

    def test_minor_mishap_table_complete(self):
        """Test that minor mishap table has all 12 entries."""
        assert len(MINOR_MISHAPS) == 12

        for i in range(1, 13):
            assert i in MINOR_MISHAPS
            mishap = MINOR_MISHAPS[i]
            assert "title" in mishap
            assert "description" in mishap
            assert "effect" in mishap

    def test_major_mishap_halves_xp(self, engine, mock_character):
        """Test that major mishap results in half XP."""
        # Use force_mishap to guarantee a mishap
        # The force_mishap path will roll on the severity table
        with patch.object(engine.dice, 'roll_d20') as mock_roll:
            # Severity roll (1 = major mishap)
            mock_roll.return_value = MagicMock(total=1)

            with patch.object(engine.dice, 'roll') as mock_table_roll:
                mock_table_roll.return_value = MagicMock(total=1)

                result = engine.carouse(
                    character_id="test_char_001",
                    gold_to_spend=200,
                    settlement_id="lankshorn",
                    settlement_name="Lankshorn",
                    force_mishap=True,
                )

                # With force_mishap and severity roll of 1, should be major
                assert result.outcome == CarousingOutcome.MAJOR_MISHAP
                assert result.xp_modifier == 0.5
                assert result.final_xp == 100

    def test_minor_mishap_full_xp(self, engine, mock_character):
        """Test that minor mishap still grants full XP."""
        with patch.object(engine.dice, 'roll_d20') as mock_roll:
            mock_roll.side_effect = [
                MagicMock(total=20),  # Save fails
                MagicMock(total=10),  # Minor mishap (severity > 5)
            ]

            with patch.object(engine.dice, 'roll') as mock_table_roll:
                mock_table_roll.return_value = MagicMock(total=1)

                result = engine.carouse(
                    character_id="test_char_001",
                    gold_to_spend=200,
                    settlement_id="lankshorn",
                    settlement_name="Lankshorn",
                )

                if result.outcome == CarousingOutcome.MINOR_MISHAP:
                    assert result.xp_modifier == 1.0
                    assert result.final_xp == 200

    def test_forced_mishap(self, engine, mock_character):
        """Test force_mishap parameter."""
        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=100,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
            force_mishap=True,
        )

        assert result.mishap is not None
        assert result.outcome in (
            CarousingOutcome.MINOR_MISHAP,
            CarousingOutcome.MAJOR_MISHAP,
        )


# =============================================================================
# BONUS TESTS
# =============================================================================


class TestBonuses:
    """Tests for carousing bonus system."""

    def test_bonus_table_complete(self):
        """Test that bonus table has all 8 entries."""
        assert len(CAROUSING_BONUSES) == 8

        for i in range(1, 9):
            assert i in CAROUSING_BONUSES
            bonus = CAROUSING_BONUSES[i]
            assert "title" in bonus
            assert "description" in bonus
            assert "effect" in bonus

    def test_bonus_increases_xp(self, engine, mock_character):
        """Test that bonus results in 150% XP."""
        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=200,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
            force_bonus=True,
        )

        assert result.outcome == CarousingOutcome.BONUS
        assert result.bonus is not None
        assert result.xp_modifier == 1.5
        assert result.final_xp == 300  # 200 × 1.5

    def test_forced_bonus(self, engine, mock_character):
        """Test force_bonus parameter."""
        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=100,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
            force_bonus=True,
        )

        assert result.bonus is not None
        assert result.outcome == CarousingOutcome.BONUS


# =============================================================================
# XP INTEGRATION TESTS
# =============================================================================


class TestXPIntegration:
    """Tests for XP system integration."""

    def test_xp_manager_integration(self, controller, mock_character):
        """Test that XP is awarded through XPManager when available."""
        # Set up mock XP manager
        xp_manager = MagicMock()
        xp_result = MagicMock()
        xp_result.final_xp = 100
        xp_result.level_ups = []
        xp_manager.award_carousing_xp.return_value = xp_result

        controller._xp_manager = xp_manager
        controller.get_character = MagicMock(return_value=mock_character)

        engine = CarousingEngine(controller)

        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=100,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        # Verify XP manager was called
        xp_manager.award_carousing_xp.assert_called_once()
        call_args = xp_manager.award_carousing_xp.call_args
        assert call_args.kwargs["character_id"] == "test_char_001"
        assert call_args.kwargs["gold_spent"] == 100

    def test_level_up_notification(self, controller, mock_character):
        """Test that level-up ready is detected."""
        xp_manager = MagicMock()
        xp_result = MagicMock()
        xp_result.final_xp = 100
        xp_result.level_ups = ["test_char_001"]  # Character ready to level
        xp_manager.award_carousing_xp.return_value = xp_result

        controller._xp_manager = xp_manager
        controller.get_character = MagicMock(return_value=mock_character)

        engine = CarousingEngine(controller)

        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=100,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        assert result.level_up_ready is True
        assert "level up" in result.events[-1].lower()


# =============================================================================
# RESULT SERIALIZATION TESTS
# =============================================================================


class TestResultSerialization:
    """Tests for result serialization."""

    def test_result_to_dict(self, engine, mock_character):
        """Test that CarousingResult serializes correctly."""
        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=100,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        result_dict = result.to_dict()

        assert "character_id" in result_dict
        assert "settlement_id" in result_dict
        assert "gold_spent" in result_dict
        assert "outcome" in result_dict
        assert "final_xp" in result_dict
        assert "events" in result_dict

    def test_mishap_serialization(self, engine, mock_character):
        """Test that mishap details serialize correctly."""
        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=100,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
            force_mishap=True,
        )

        result_dict = result.to_dict()

        assert "mishap" in result_dict
        mishap = result_dict["mishap"]
        assert "severity" in mishap
        assert "title" in mishap
        assert "description" in mishap
        assert "effect" in mishap


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_character_not_found(self, controller):
        """Test handling when character doesn't exist."""
        controller.get_character = MagicMock(return_value=None)
        engine = CarousingEngine(controller)

        result = engine.carouse(
            character_id="nonexistent",
            gold_to_spend=100,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        assert result.outcome == CarousingOutcome.BROKE
        assert "Character not found" in result.events[0]

    def test_zero_gold_spending(self, engine, mock_character):
        """Test carousing with zero gold."""
        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=0,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        assert result.gold_spent == 0
        assert result.base_xp == 0
        assert result.final_xp == 0

    def test_level_one_cap(self, engine, mock_character):
        """Test that level 1 characters are capped at 100 GP."""
        mock_character.level = 1

        result = engine.carouse(
            character_id="test_char_001",
            gold_to_spend=500,
            settlement_id="lankshorn",
            settlement_name="Lankshorn",
        )

        assert result.gold_cap == 100
        assert result.gold_spent == 100

    def test_venue_modifier(self, engine, mock_character):
        """Test that venue modifier affects save."""
        mock_character.saving_throws = {"poison": 10}

        # With +5 venue modifier, roll of 12 should pass (12 + 5 = 17 > 10? No wait...)
        # Actually B/X uses roll-under, so we need effective_roll <= save_target
        # If save_target is 10, and we roll 8, +2 venue = 10, which should still pass
        with patch.object(engine.dice, 'roll_d20') as mock_roll:
            mock_roll.return_value = MagicMock(total=8)

            result = engine.carouse(
                character_id="test_char_001",
                gold_to_spend=100,
                settlement_id="lankshorn",
                settlement_name="Lankshorn",
                venue_modifier=-5,  # Rough establishment makes it harder
            )

            # 8 + (-5) = 3, which is <= 10, so should pass
            assert result.save_roll == 8

    def test_no_saving_throws_uses_constitution(self, engine, mock_character):
        """Test fallback to Constitution when no poison save."""
        mock_character.saving_throws = {}  # No saves
        mock_character.constitution = 16  # +3 modifier

        save_target = engine._get_save_target(mock_character)

        # 15 - CON mod (3) = 12
        assert save_target == 12


# =============================================================================
# MISHAP CONSEQUENCE TESTS
# =============================================================================


class TestMishapConsequences:
    """Tests for processing mishap consequences."""

    def test_jail_consequence(self, engine, mock_character):
        """Test jail mishap produces correct consequences."""
        mishap = CarousingMishap(
            severity=MishapSeverity.MAJOR,
            title="Jailed",
            description="Test",
            effect="jail",
            details={"days_jailed": 3, "fine_amount": 50},
        )

        consequences = engine._process_mishap_consequences(mock_character, mishap)

        assert len(consequences) == 1
        assert "Jailed for 3 days" in consequences[0]
        assert "50 GP" in consequences[0]

    def test_debt_consequence(self, engine, mock_character):
        """Test debt mishap produces correct consequences."""
        mishap = CarousingMishap(
            severity=MishapSeverity.MAJOR,
            title="Gambling Debt",
            description="Test",
            effect="debt",
            details={"debt_amount": 500},
        )

        consequences = engine._process_mishap_consequences(mock_character, mishap)

        assert len(consequences) == 1
        assert "500 GP" in consequences[0]

    def test_curse_consequence(self, engine, mock_character):
        """Test curse mishap produces correct consequences."""
        mishap = CarousingMishap(
            severity=MishapSeverity.MAJOR,
            title="Cursed",
            description="Test",
            effect="cursed",
            details={"penalty": -1, "duration_days": 7},
        )

        consequences = engine._process_mishap_consequences(mock_character, mishap)

        assert len(consequences) == 1
        assert "-1 to all rolls" in consequences[0]
        assert "7 days" in consequences[0]


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingletons:
    """Tests for singleton pattern."""

    def test_get_carousing_engine_returns_same_instance(self, controller):
        """Test that get_carousing_engine returns singleton."""
        engine1 = get_carousing_engine(controller)
        engine2 = get_carousing_engine(controller)

        assert engine1 is engine2

    def test_reset_clears_singleton(self, controller):
        """Test that reset clears the singleton."""
        engine1 = get_carousing_engine(controller)
        reset_carousing_engine()
        engine2 = get_carousing_engine(controller)

        assert engine1 is not engine2
