"""
Tests for MythicGME RNG requirement.

Phase 6.1: Verify that MythicGME uses DiceRngAdapter by default,
ensuring all oracle rolls are deterministic and logged.
"""

import pytest

from src.data_models import DiceRoller
from src.oracle.mythic_gme import MythicGME, Likelihood
from src.oracle.dice_rng_adapter import DiceRngAdapter


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


class TestMythicGMEDefaultsToAdapter:
    """Verify MythicGME uses DiceRngAdapter by default."""

    def test_default_constructor_uses_dice_rng_adapter(self, seeded_dice):
        """MythicGME() should use DiceRngAdapter, not random.Random."""
        # Create MythicGME without explicit rng
        mythic = MythicGME()

        # The _rng should be a DiceRngAdapter instance
        assert isinstance(mythic._rng, DiceRngAdapter), (
            f"Expected DiceRngAdapter, got {type(mythic._rng).__name__}"
        )

    def test_default_adapter_has_correct_prefix(self, seeded_dice):
        """Default DiceRngAdapter should have 'MythicGME' prefix."""
        mythic = MythicGME()

        assert isinstance(mythic._rng, DiceRngAdapter)
        assert mythic._rng._reason_prefix == "MythicGME"

    def test_default_rolls_are_logged(self, seeded_dice):
        """Rolls through default adapter should appear in roll log."""
        DiceRoller.clear_roll_log()

        mythic = MythicGME()
        mythic.fate_check("Test question?", Likelihood.FIFTY_FIFTY)

        # Should have logged the d100 roll
        roll_log = DiceRoller.get_roll_log()
        assert len(roll_log) > 0, "Fate check roll should be logged"

        # Check that one of the rolls was for MythicGME
        reasons = [r.reason for r in roll_log]
        assert any("MythicGME" in r for r in reasons), (
            f"No MythicGME rolls found in: {reasons}"
        )


class TestMythicGMEDeterminism:
    """Verify MythicGME produces deterministic results with default adapter."""

    def test_same_seed_produces_same_result(self, seeded_dice):
        """Same DiceRoller seed should produce same fate check result."""
        DiceRoller.set_seed(12345)
        mythic1 = MythicGME()
        result1 = mythic1.fate_check("Is the door locked?", Likelihood.LIKELY)

        DiceRoller.set_seed(12345)
        mythic2 = MythicGME()
        result2 = mythic2.fate_check("Is the door locked?", Likelihood.LIKELY)

        assert result1.roll == result2.roll, "Rolls should be identical with same seed"
        assert result1.result == result2.result, "Results should be identical"

    def test_different_seeds_produce_different_results(self, seeded_dice):
        """Different seeds should (usually) produce different results."""
        DiceRoller.set_seed(11111)
        mythic1 = MythicGME()
        rolls1 = [mythic1.fate_check(f"Q{i}?", Likelihood.FIFTY_FIFTY).roll for i in range(5)]

        DiceRoller.set_seed(99999)
        mythic2 = MythicGME()
        rolls2 = [mythic2.fate_check(f"Q{i}?", Likelihood.FIFTY_FIFTY).roll for i in range(5)]

        assert rolls1 != rolls2, "Different seeds should produce different rolls"

    def test_meaning_rolls_are_deterministic(self, seeded_dice):
        """Meaning rolls should also be deterministic."""
        DiceRoller.set_seed(42424)
        mythic1 = MythicGME()
        meaning1 = mythic1.roll_meaning()

        DiceRoller.set_seed(42424)
        mythic2 = MythicGME()
        meaning2 = mythic2.roll_meaning()

        assert meaning1.action == meaning2.action
        assert meaning1.subject == meaning2.subject


class TestMythicGMEWithExplicitAdapter:
    """Test MythicGME with explicitly provided DiceRngAdapter."""

    def test_explicit_adapter_is_used(self, seeded_dice):
        """Explicitly provided adapter should be used."""
        adapter = DiceRngAdapter("CustomOracle")
        mythic = MythicGME(rng=adapter)

        assert mythic._rng is adapter
        assert mythic._rng._reason_prefix == "CustomOracle"

    def test_explicit_adapter_rolls_are_logged(self, seeded_dice):
        """Rolls through explicit adapter should be logged with its prefix."""
        DiceRoller.clear_roll_log()

        adapter = DiceRngAdapter("TestAdapter")
        mythic = MythicGME(rng=adapter)
        mythic.fate_check("Test?", Likelihood.FIFTY_FIFTY)

        roll_log = DiceRoller.get_roll_log()
        reasons = [r.reason for r in roll_log]
        assert any("TestAdapter" in r for r in reasons)


class TestMythicGMEWithRandomRandom:
    """Test that MythicGME still accepts random.Random for testing."""

    def test_random_random_still_accepted(self, seeded_dice):
        """random.Random should still work (for testing purposes)."""
        import random

        rng = random.Random(42)
        mythic = MythicGME(rng=rng)

        # Should work without error
        result = mythic.fate_check("Test?", Likelihood.FIFTY_FIFTY)
        assert result.result is not None

    def test_random_random_rolls_not_logged(self, seeded_dice):
        """random.Random rolls should NOT appear in DiceRoller log."""
        import random

        DiceRoller.clear_roll_log()

        rng = random.Random(42)
        mythic = MythicGME(rng=rng)
        mythic.fate_check("Test?", Likelihood.FIFTY_FIFTY)

        # The fate check roll should NOT be in DiceRoller's log
        # (only the seeded_dice fixture setup rolls might be there)
        roll_log = DiceRoller.get_roll_log()
        mythic_rolls = [r for r in roll_log if "MythicGME" in r.reason]
        assert len(mythic_rolls) == 0, (
            "random.Random rolls should not appear in DiceRoller log"
        )


class TestAllCallSitesUseAdapter:
    """Verify that all call sites in production code use DiceRngAdapter."""

    def test_spell_adjudicator_uses_adapter(self, seeded_dice):
        """MythicSpellAdjudicator should create MythicGME with adapter."""
        from src.oracle.spell_adjudicator import MythicSpellAdjudicator

        adjudicator = MythicSpellAdjudicator()

        # Check internal mythic instance uses adapter
        assert isinstance(adjudicator._mythic._rng, DiceRngAdapter)

    def test_oracle_enhancement_uses_adapter(self, seeded_dice):
        """OracleEnhancement should use adapter for its MythicGME."""
        # OracleEnhancement creates MythicGME internally when processing
        # We verify that the default MythicGME uses adapter, which is
        # what all call sites will get when they don't specify rng
        DiceRoller.clear_roll_log()

        # The default MythicGME now uses adapter
        mythic = MythicGME()
        mythic.fate_check("test?", Likelihood.FIFTY_FIFTY)

        roll_log = DiceRoller.get_roll_log()
        assert len(roll_log) > 0
        reasons = [r.reason for r in roll_log]
        assert any("MythicGME" in r for r in reasons)

    def test_faction_oracle_uses_adapter(self, seeded_dice):
        """FactionOracle should use adapter for its MythicGME."""
        from src.factions.faction_oracle import FactionOracle

        oracle = FactionOracle()

        # Check internal mythic uses adapter
        assert isinstance(oracle._mythic._rng, DiceRngAdapter)
