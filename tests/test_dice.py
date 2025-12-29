"""
Unit tests for dice rolling system.

Tests the DiceRoller class and DiceResult from src/data_models.py.
"""

import pytest
from src.data_models import DiceRoller, DiceResult


class TestDiceRoller:
    """Tests for DiceRoller class."""

    def test_singleton_pattern(self):
        """Test that DiceRoller is a singleton."""
        roller1 = DiceRoller()
        roller2 = DiceRoller()
        assert roller1 is roller2

    def test_roll_basic_d6(self, seeded_dice):
        """Test rolling a basic d6."""
        result = seeded_dice.roll("1d6", "test roll")
        assert isinstance(result, DiceResult)
        assert 1 <= result.total <= 6
        assert len(result.rolls) == 1

    def test_roll_multiple_dice(self, seeded_dice):
        """Test rolling multiple dice."""
        result = seeded_dice.roll("3d6", "attribute roll")
        assert len(result.rolls) == 3
        assert all(1 <= r <= 6 for r in result.rolls)
        assert result.total == sum(result.rolls)

    def test_roll_with_positive_modifier(self, seeded_dice):
        """Test rolling with positive modifier."""
        result = seeded_dice.roll("1d20+5", "attack roll")
        assert result.modifier == 5
        assert result.total == result.rolls[0] + 5

    def test_roll_with_negative_modifier(self, seeded_dice):
        """Test rolling with negative modifier."""
        result = seeded_dice.roll("1d8-2", "weak attack")
        assert result.modifier == -2
        assert result.total == result.rolls[0] - 2

    def test_roll_d20_convenience(self, seeded_dice):
        """Test d20 convenience method."""
        result = seeded_dice.roll_d20("attack")
        assert 1 <= result.total <= 20
        assert result.notation == "1d20"

    def test_roll_2d6_convenience(self, seeded_dice):
        """Test 2d6 convenience method."""
        result = seeded_dice.roll_2d6("reaction")
        assert 2 <= result.total <= 12
        assert len(result.rolls) == 2

    def test_roll_d6_convenience(self, seeded_dice):
        """Test d6 convenience method with variable count."""
        result = seeded_dice.roll_d6(4, "4d6")
        assert len(result.rolls) == 4
        assert 4 <= result.total <= 24

    def test_roll_percentile(self, seeded_dice):
        """Test percentile roll."""
        result = seeded_dice.roll_percentile("treasure check")
        assert 1 <= result.total <= 100

    def test_seeded_reproducibility(self):
        """Test that seeded rolls are reproducible."""
        DiceRoller.set_seed(12345)
        first_results = [DiceRoller.roll_d6(1, "test").total for _ in range(5)]

        DiceRoller.set_seed(12345)
        second_results = [DiceRoller.roll_d6(1, "test").total for _ in range(5)]

        assert first_results == second_results

    def test_roll_log(self, clean_dice):
        """Test that rolls are logged."""
        clean_dice.roll("1d6", "first roll")
        clean_dice.roll("1d20", "second roll")
        clean_dice.roll("2d6", "third roll")

        log = clean_dice.get_roll_log()
        assert len(log) == 3
        assert log[0].reason == "first roll"
        assert log[1].reason == "second roll"
        assert log[2].reason == "third roll"

    def test_clear_roll_log(self, clean_dice):
        """Test clearing the roll log."""
        clean_dice.roll("1d6", "test")
        clean_dice.roll("1d6", "test")
        assert len(clean_dice.get_roll_log()) == 2

        clean_dice.clear_roll_log()
        assert len(clean_dice.get_roll_log()) == 0

    def test_implied_single_die(self, seeded_dice):
        """Test rolling 'd6' (implied single die)."""
        result = seeded_dice.roll("d6", "test")
        assert 1 <= result.total <= 6
        assert len(result.rolls) == 1


class TestDiceResult:
    """Tests for DiceResult class."""

    def test_str_without_modifier(self):
        """Test string representation without modifier."""
        result = DiceResult(
            notation="2d6",
            rolls=[3, 5],
            modifier=0,
            total=8,
            reason="test",
        )
        assert "2d6" in str(result)
        assert "8" in str(result)
        assert "[3, 5]" in str(result)

    def test_str_with_positive_modifier(self):
        """Test string representation with positive modifier."""
        result = DiceResult(
            notation="1d20+5",
            rolls=[15],
            modifier=5,
            total=20,
            reason="attack",
        )
        assert "+ 5" in str(result)
        assert "= 20" in str(result)

    def test_str_with_negative_modifier(self):
        """Test string representation with negative modifier."""
        result = DiceResult(
            notation="1d8-2",
            rolls=[5],
            modifier=-2,
            total=3,
            reason="damage",
        )
        assert "- 2" in str(result)
        assert "= 3" in str(result)

    def test_result_has_timestamp(self, seeded_dice):
        """Test that results have timestamps."""
        result = seeded_dice.roll("1d6", "test")
        assert result.timestamp is not None


class TestDiceStatistics:
    """Statistical tests to verify dice distribution."""

    def test_d6_distribution(self, clean_dice):
        """Test that d6 rolls are reasonably distributed."""
        clean_dice.clear_roll_log()
        results = [clean_dice.roll("1d6", "dist test").total for _ in range(600)]

        # Count occurrences of each value
        counts = {i: results.count(i) for i in range(1, 7)}

        # Each value should appear roughly 100 times (600/6)
        # Allow 50% variance for statistical fluctuation
        for value in range(1, 7):
            assert 50 <= counts[value] <= 150, f"Value {value} appeared {counts[value]} times"

    def test_2d6_bell_curve(self, clean_dice):
        """Test that 2d6 follows expected bell curve."""
        clean_dice.clear_roll_log()
        results = [clean_dice.roll("2d6", "bell test").total for _ in range(1000)]

        # 7 should be most common (6 ways to roll it)
        # 2 and 12 should be least common (1 way each)
        count_7 = results.count(7)
        count_2 = results.count(2)
        count_12 = results.count(12)

        # 7 should appear much more than 2 or 12
        assert count_7 > count_2 * 2
        assert count_7 > count_12 * 2

    def test_d20_range(self, clean_dice):
        """Test that d20 covers full range."""
        clean_dice.clear_roll_log()
        results = set()
        for _ in range(1000):
            result = clean_dice.roll_d20("range test").total
            results.add(result)

        # After 1000 rolls, we should have seen all values
        assert len(results) == 20
        assert min(results) == 1
        assert max(results) == 20

    def test_d6_total_is_int_in_range(self, clean_dice):
        """Test that roll().total returns an int in the correct range.

        This ensures code like 'if roll.total == 1' works correctly,
        rather than accidentally comparing DiceResult objects to ints.
        """
        for _ in range(100):
            result = clean_dice.roll("1d6", "range check")
            assert isinstance(result.total, int), "roll().total should be an int"
            assert 1 <= result.total <= 6, f"1d6 total should be 1-6, got {result.total}"
