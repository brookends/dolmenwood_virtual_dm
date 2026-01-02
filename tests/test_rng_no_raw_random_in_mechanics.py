"""
Tests for RNG determinism contract.

Phase 0.2: Verify that gameplay mechanics use DiceRngAdapter instead of
raw random.* calls, ensuring deterministic replay is possible.

This test monkeypatches random module functions to detect any direct usage
from gameplay modules - if raw random is used, replay/determinism breaks.
"""

import pytest
import random
import sys
import traceback
from unittest.mock import patch
from typing import Any, Callable

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.conversation.action_registry import get_default_registry, reset_registry


# =============================================================================
# CONFIGURATION
# =============================================================================

# Modules that should NEVER call random.* directly during gameplay
GAMEPLAY_MODULES = {
    "src.hex_crawl",
    "src.dungeon",
    "src.encounter",
    "src.settlement",
    "src.combat",
    "src.oracle",
    "src.fairy_road",
    "src.narrative",
    "src.conversation",
}

# Modules that are allowed to use random.* (infrastructure, not gameplay)
ALLOWED_MODULES = {
    "random",  # The random module itself
    "uuid",  # UUID generation
    "tempfile",  # Temporary files
    "pytest",  # Test framework
    "unittest",  # Test framework
    "_pytest",  # Pytest internals
    "src.data_models",  # DiceRoller is the approved RNG wrapper
    "src.oracle.dice_rng_adapter",  # The approved RNG adapter
}


# =============================================================================
# RNG DETECTION INFRASTRUCTURE
# =============================================================================


class RawRandomUsageError(Exception):
    """Raised when raw random.* is called from a gameplay module."""

    def __init__(self, function_name: str, caller_module: str, stack: str):
        self.function_name = function_name
        self.caller_module = caller_module
        self.stack = stack
        super().__init__(
            f"Raw {function_name}() called from gameplay module '{caller_module}'\n"
            f"Use DiceRngAdapter or DiceRoller instead.\n"
            f"Stack trace:\n{stack}"
        )


class RandomUsageCollector:
    """Collects violations instead of raising immediately."""

    def __init__(self):
        self.violations: list[tuple[str, str, str]] = []

    def record(self, function_name: str, caller_module: str, stack: str):
        self.violations.append((function_name, caller_module, stack))

    def clear(self):
        self.violations = []

    def has_violations(self) -> bool:
        return len(self.violations) > 0

    def format_report(self) -> str:
        if not self.violations:
            return "No violations found."

        lines = ["RAW RANDOM USAGE DETECTED IN GAMEPLAY MODULES:", ""]
        for func, module, stack in self.violations:
            lines.append(f"  {func}() called from {module}")
            # Show abbreviated stack
            stack_lines = stack.strip().split("\n")
            for line in stack_lines[-6:]:  # Last 6 lines of stack
                lines.append(f"    {line.strip()}")
            lines.append("")

        lines.append("FIX: Replace random.* calls with DiceRngAdapter or DiceRoller")
        return "\n".join(lines)


def _get_caller_module() -> str:
    """Get the module name of the caller (skipping wrapper functions)."""
    frame = sys._getframe(3)  # Skip: _get_caller_module, wrapper, random function
    module = frame.f_globals.get("__name__", "unknown")
    return module


def _is_gameplay_module(module_name: str) -> bool:
    """Check if a module is a gameplay module that shouldn't use raw random."""
    for gameplay_prefix in GAMEPLAY_MODULES:
        if module_name.startswith(gameplay_prefix):
            return True
    return False


def _is_allowed_module(module_name: str) -> bool:
    """Check if a module is explicitly allowed to use random."""
    for allowed in ALLOWED_MODULES:
        if module_name.startswith(allowed):
            return True
    return False


def create_random_trap(
    original_func: Callable,
    function_name: str,
    collector: RandomUsageCollector,
    raise_immediately: bool = False,
) -> Callable:
    """
    Create a wrapper that detects raw random usage from gameplay modules.

    Args:
        original_func: The original random function
        function_name: Name of the function (for error messages)
        collector: Where to record violations
        raise_immediately: If True, raise on first violation
    """

    def wrapper(*args, **kwargs):
        caller_module = _get_caller_module()

        # Check if this is a gameplay module that shouldn't use raw random
        if _is_gameplay_module(caller_module) and not _is_allowed_module(caller_module):
            stack = "".join(traceback.format_stack())

            if raise_immediately:
                raise RawRandomUsageError(function_name, caller_module, stack)

            collector.record(function_name, caller_module, stack)

        # Always call the original function so tests don't break
        return original_func(*args, **kwargs)

    return wrapper


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


@pytest.fixture
def test_character():
    """A sample character for testing."""
    return CharacterState(
        character_id="test_ranger_1",
        name="Test Ranger",
        character_class="Ranger",
        level=3,
        ability_scores={
            "STR": 14,
            "INT": 12,
            "WIS": 15,
            "DEX": 16,
            "CON": 13,
            "CHA": 10,
        },
        hp_current=20,
        hp_max=20,
        armor_class=5,
        base_speed=30,
    )


@pytest.fixture
def offline_dm(seeded_dice, test_character):
    """Create VirtualDM in offline mode."""
    reset_registry()

    config = GameConfig(
        llm_provider="mock",
        enable_narration=False,
        load_content=False,
    )

    dm = VirtualDM(
        config=config,
        initial_state=GameState.WILDERNESS_TRAVEL,
        game_date=GameDate(year=1, month=6, day=15),
        game_time=GameTime(hour=10, minute=0),
    )

    dm.controller.add_character(test_character)
    dm.controller.party_state.resources.food_days = 10
    dm.controller.party_state.resources.water_days = 10

    return dm


@pytest.fixture
def random_collector():
    """Create a collector for random usage violations."""
    return RandomUsageCollector()


@pytest.fixture
def trap_random(random_collector):
    """
    Monkeypatch random module to detect gameplay usage.

    This patches the most commonly used random functions.
    """
    original_randint = random.randint
    original_choice = random.choice
    original_random = random.random
    original_uniform = random.uniform
    original_randrange = random.randrange
    original_shuffle = random.shuffle
    original_sample = random.sample

    # Install traps
    random.randint = create_random_trap(
        original_randint, "random.randint", random_collector
    )
    random.choice = create_random_trap(
        original_choice, "random.choice", random_collector
    )
    random.random = create_random_trap(
        original_random, "random.random", random_collector
    )
    random.uniform = create_random_trap(
        original_uniform, "random.uniform", random_collector
    )
    random.randrange = create_random_trap(
        original_randrange, "random.randrange", random_collector
    )
    random.shuffle = create_random_trap(
        original_shuffle, "random.shuffle", random_collector
    )
    random.sample = create_random_trap(
        original_sample, "random.sample", random_collector
    )

    yield random_collector

    # Restore originals
    random.randint = original_randint
    random.choice = original_choice
    random.random = original_random
    random.uniform = original_uniform
    random.randrange = original_randrange
    random.shuffle = original_shuffle
    random.sample = original_sample


# =============================================================================
# TESTS
# =============================================================================


class TestRngDeterminismContract:
    """
    Phase 0.2: Contract tests for RNG determinism.

    These tests exercise gameplay mechanics and verify that no raw random.*
    calls are made from gameplay modules.
    """

    def test_foraging_uses_dice_adapter(self, offline_dm, trap_random):
        """Foraging should use DiceRngAdapter, not raw random."""
        registry = get_default_registry()

        # Execute foraging action
        try:
            registry.execute(offline_dm, "wilderness:forage", {})
        except Exception:
            pass  # We only care about random usage, not success

        # Check for violations
        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())

    def test_hunting_uses_dice_adapter(self, offline_dm, trap_random):
        """Hunting should use DiceRngAdapter, not raw random."""
        registry = get_default_registry()

        # Execute hunting action
        try:
            registry.execute(offline_dm, "wilderness:hunt", {})
        except Exception:
            pass  # We only care about random usage, not success

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())

    def test_oracle_fate_check_uses_dice_adapter(self, offline_dm, trap_random):
        """Oracle fate checks should use DiceRngAdapter, not raw random."""
        registry = get_default_registry()

        # Execute oracle fate check
        try:
            registry.execute(
                offline_dm,
                "oracle:fate_check",
                {"question": "Is the door locked?"}
            )
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())

    def test_oracle_detail_check_uses_dice_adapter(self, offline_dm, trap_random):
        """Oracle detail checks should use DiceRngAdapter, not raw random."""
        registry = get_default_registry()

        try:
            registry.execute(offline_dm, "oracle:detail_check", {})
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())

    def test_oracle_random_event_uses_dice_adapter(self, offline_dm, trap_random):
        """Oracle random events should use DiceRngAdapter, not raw random."""
        registry = get_default_registry()

        try:
            registry.execute(offline_dm, "oracle:random_event", {})
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())

    def test_social_oracle_question_uses_dice_adapter(self, offline_dm, trap_random):
        """Social oracle questions should use DiceRngAdapter, not raw random."""
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test"
        )

        try:
            registry.execute(
                offline_dm,
                "social:oracle_question",
                {"question": "Does the merchant trust us?"}
            )
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())

    def test_wilderness_travel_uses_dice_adapter(self, offline_dm, trap_random):
        """Wilderness travel should use DiceRngAdapter, not raw random."""
        registry = get_default_registry()

        try:
            registry.execute(
                offline_dm,
                "wilderness:travel",
                {"direction": "north"}
            )
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())

    def test_wilderness_search_uses_dice_adapter(self, offline_dm, trap_random):
        """Searching a hex should use DiceRngAdapter, not raw random."""
        registry = get_default_registry()

        try:
            registry.execute(offline_dm, "wilderness:search_hex", {})
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())


class TestDiceRollerDeterminism:
    """Verify that DiceRoller produces deterministic results with seed."""

    def test_dice_roller_is_deterministic(self, seeded_dice):
        """Same seed should produce same roll sequence."""
        DiceRoller.set_seed(12345)
        # Extract just the total values (ignoring timestamps)
        rolls_1 = [DiceRoller.roll_d20().total for _ in range(10)]

        DiceRoller.set_seed(12345)
        rolls_2 = [DiceRoller.roll_d20().total for _ in range(10)]

        assert rolls_1 == rolls_2, "DiceRoller not deterministic with same seed"

    def test_different_seeds_different_results(self, seeded_dice):
        """Different seeds should (usually) produce different results."""
        DiceRoller.set_seed(11111)
        rolls_1 = [DiceRoller.roll_d20().total for _ in range(10)]

        DiceRoller.set_seed(99999)
        rolls_2 = [DiceRoller.roll_d20().total for _ in range(10)]

        # These should almost certainly be different
        assert rolls_1 != rolls_2, "Different seeds produced same results"


class TestMythicGMEDeterminism:
    """Verify MythicGME uses DiceRngAdapter for determinism."""

    def test_mythic_with_adapter_is_deterministic(self, seeded_dice):
        """MythicGME with DiceRngAdapter should be deterministic."""
        from src.oracle.mythic_gme import MythicGME, Likelihood
        from src.oracle.dice_rng_adapter import DiceRngAdapter

        # First run
        DiceRoller.set_seed(42)
        adapter1 = DiceRngAdapter("test1")
        mythic1 = MythicGME(rng=adapter1)
        result1 = mythic1.fate_check("Is it locked?", Likelihood.LIKELY)

        # Second run with same seed
        DiceRoller.set_seed(42)
        adapter2 = DiceRngAdapter("test2")
        mythic2 = MythicGME(rng=adapter2)
        result2 = mythic2.fate_check("Is it locked?", Likelihood.LIKELY)

        # FateCheckResult uses 'result' field (a FateResult enum)
        assert result1.result == result2.result, (
            "MythicGME not deterministic with same seed"
        )
        assert result1.roll == result2.roll, (
            "MythicGME roll not deterministic"
        )


class TestEncounterRngDeterminism:
    """Test that encounter resolution uses deterministic RNG."""

    def test_encounter_action_uses_dice_adapter(self, offline_dm, trap_random):
        """Encounter actions should use DiceRngAdapter."""
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.ENCOUNTER,
            reason="test"
        )

        try:
            registry.execute(
                offline_dm,
                "encounter:action",
                {"action": "parley", "actor": "party"}
            )
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())


class TestCombatRngDeterminism:
    """Test that combat resolution uses deterministic RNG."""

    def test_combat_resolve_uses_dice_adapter(self, offline_dm, trap_random):
        """Combat resolution should use DiceRngAdapter."""
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.COMBAT,
            reason="test"
        )

        try:
            registry.execute(offline_dm, "combat:resolve_round", {})
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())

    def test_combat_flee_uses_dice_adapter(self, offline_dm, trap_random):
        """Fleeing combat should use DiceRngAdapter."""
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.COMBAT,
            reason="test"
        )

        try:
            registry.execute(offline_dm, "combat:flee", {})
        except Exception:
            pass

        if trap_random.has_violations():
            pytest.fail(trap_random.format_report())
