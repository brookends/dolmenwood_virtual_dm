"""
Tests for trap tables implementation per Campaign Book p102-103.

Tests cover:
- Trap categories (Pit, Architectural, Mechanism, Magical)
- Trigger types (9 types)
- Trap effects (20 effects with proper mechanics)
- Disarm rules (category-based restrictions)
- Exploration clues
- Bypass options
"""

import pytest
from src.tables.trap_tables import (
    TrapCategory,
    TrapTrigger,
    TrapEffectType,
    TrapEffect,
    Trap,
    TRAP_EFFECTS,
    generate_random_trap,
    get_trap_by_effect,
    get_exploration_clues,
    get_bypass_options,
    can_attempt_disarm,
    attempt_disarm,
    DisarmAttempt,
)
from src.data_models import DiceRoller


class TestTrapCategories:
    """Test trap category definitions per Campaign Book p102."""

    def test_all_categories_exist(self):
        """All four trap categories should be defined."""
        assert TrapCategory.PIT == "pit"
        assert TrapCategory.ARCHITECTURAL == "architectural"
        assert TrapCategory.MECHANISM == "mechanism"
        assert TrapCategory.MAGICAL == "magical"

    def test_category_count(self):
        """Should have exactly 4 categories."""
        assert len(TrapCategory) == 4


class TestTrapTriggers:
    """Test trap trigger types per Campaign Book p102."""

    def test_all_triggers_exist(self):
        """All nine trigger types should be defined."""
        assert TrapTrigger.PRESSURE_PLATE == "pressure_plate"
        assert TrapTrigger.SCALES == "scales"
        assert TrapTrigger.TRIPWIRE == "tripwire"
        assert TrapTrigger.LOCK == "lock"
        assert TrapTrigger.OPENING == "opening"
        assert TrapTrigger.DETECTION == "detection"
        assert TrapTrigger.PROXIMITY == "proximity"
        assert TrapTrigger.SPEECH == "speech"
        assert TrapTrigger.TOUCH == "touch"

    def test_trigger_count(self):
        """Should have exactly 9 trigger types."""
        assert len(TrapTrigger) == 9


class TestTrapEffects:
    """Test trap effects per Campaign Book p103."""

    def test_all_20_effects_defined(self):
        """All 20 trap effects should be defined in TRAP_EFFECTS."""
        assert len(TRAP_EFFECTS) == 20

    def test_acid_spray_effect(self):
        """Acid spray: Save vs Blast or 3d6 acid damage."""
        effect = TRAP_EFFECTS[TrapEffectType.ACID_SPRAY]
        assert effect.save_type == "blast"
        assert effect.damage == "3d6"
        assert not effect.save_negates  # Damage, not condition

    def test_arrow_volley_effect(self):
        """Arrow volley: d4 arrows at +8 to hit, 1d6 damage each."""
        effect = TRAP_EFFECTS[TrapEffectType.ARROW_VOLLEY]
        assert effect.attack_bonus == 8
        assert effect.num_attacks == "1d4"
        assert effect.damage == "1d6"

    def test_crushing_ceiling_effect(self):
        """Crushing ceiling: 10d6 damage after 3 rounds."""
        effect = TRAP_EFFECTS[TrapEffectType.CRUSHING_CEILING]
        assert effect.damage == "10d6"
        assert effect.duration_rounds == 3

    def test_gas_effects_require_save(self):
        """All gas effects should require Save vs Doom."""
        gas_effects = [
            TrapEffectType.GAS_CONFUSION,
            TrapEffectType.GAS_MEMORY,
            TrapEffectType.GAS_PARALYSIS,
            TrapEffectType.GAS_SLEEP,
            TrapEffectType.GAS_POISON,
        ]
        for effect_type in gas_effects:
            effect = TRAP_EFFECTS[effect_type]
            assert effect.save_type == "doom"

    def test_magic_cage_effect(self):
        """Magic cage: Iron cage, 1 turn duration."""
        effect = TRAP_EFFECTS[TrapEffectType.MAGIC_CAGE]
        assert effect.condition_applied == "caged"
        assert effect.duration_turns == 1

    def test_magic_light_blast_no_save(self):
        """Light blast: Blindness 1d6 rounds, no save."""
        effect = TRAP_EFFECTS[TrapEffectType.MAGIC_LIGHT_BLAST]
        assert effect.condition_applied == "blinded"
        assert effect.save_type is None  # No save allowed

    def test_pit_fall_effect(self):
        """Pit fall: Save vs Blast, 1d6 per 10 feet."""
        effect = TRAP_EFFECTS[TrapEffectType.PIT_FALL]
        assert effect.save_type == "blast"
        assert effect.save_negates is True
        assert effect.damage == "1d6"

    def test_all_effects_have_clues(self):
        """Every effect should have at least one exploration clue."""
        for effect_type, effect in TRAP_EFFECTS.items():
            assert len(effect.clues) > 0, f"{effect_type} has no clues"


class TestTrapModel:
    """Test Trap dataclass functionality."""

    def test_trap_creation(self):
        """Trap should be created with all required fields."""
        trap = Trap(
            trap_id="test_trap_1",
            name="Test Pit Trap",
            category=TrapCategory.PIT,
            trigger=TrapTrigger.PRESSURE_PLATE,
            effect=TRAP_EFFECTS[TrapEffectType.PIT_FALL],
        )
        assert trap.trap_id == "test_trap_1"
        assert trap.category == TrapCategory.PIT
        assert trap.trigger_chance == 2  # Default

    def test_pit_cannot_be_disarmed(self):
        """Pit traps cannot be disarmed, only bypassed."""
        trap = Trap(
            trap_id="pit_1",
            name="Pit Trap",
            category=TrapCategory.PIT,
            trigger=TrapTrigger.PRESSURE_PLATE,
            effect=TRAP_EFFECTS[TrapEffectType.PIT_FALL],
        )
        assert not trap.can_be_disarmed()
        assert not trap.requires_thief()
        assert not trap.requires_magic()

    def test_architectural_cannot_be_disarmed(self):
        """Architectural traps cannot be disarmed, only bypassed."""
        trap = Trap(
            trap_id="arch_1",
            name="Arrow Trap",
            category=TrapCategory.ARCHITECTURAL,
            trigger=TrapTrigger.TRIPWIRE,
            effect=TRAP_EFFECTS[TrapEffectType.ARROW_VOLLEY],
        )
        assert not trap.can_be_disarmed()

    def test_mechanism_requires_thief(self):
        """Mechanism traps require thief to disarm."""
        trap = Trap(
            trap_id="mech_1",
            name="Blade Trap",
            category=TrapCategory.MECHANISM,
            trigger=TrapTrigger.LOCK,
            effect=TRAP_EFFECTS[TrapEffectType.SPEAR_WALL],
        )
        assert trap.can_be_disarmed()
        assert trap.requires_thief()
        assert not trap.requires_magic()

    def test_magical_requires_magic(self):
        """Magical traps require magic to disarm."""
        trap = Trap(
            trap_id="magic_1",
            name="Symbol Trap",
            category=TrapCategory.MAGICAL,
            trigger=TrapTrigger.PROXIMITY,
            effect=TRAP_EFFECTS[TrapEffectType.MAGIC_SYMBOL],
        )
        assert trap.can_be_disarmed()
        assert not trap.requires_thief()
        assert trap.requires_magic()

    def test_disarm_method_descriptions(self):
        """Each category should have appropriate disarm method description."""
        pit_trap = Trap(
            trap_id="pit",
            name="Pit",
            category=TrapCategory.PIT,
            trigger=TrapTrigger.PRESSURE_PLATE,
            effect=TRAP_EFFECTS[TrapEffectType.PIT_FALL],
        )
        assert "bypassed" in pit_trap.get_disarm_method().lower()

        mech_trap = Trap(
            trap_id="mech",
            name="Mechanism",
            category=TrapCategory.MECHANISM,
            trigger=TrapTrigger.LOCK,
            effect=TRAP_EFFECTS[TrapEffectType.SPEAR_WALL],
        )
        assert "thief" in mech_trap.get_disarm_method().lower()

        magic_trap = Trap(
            trap_id="magic",
            name="Magic",
            category=TrapCategory.MAGICAL,
            trigger=TrapTrigger.TOUCH,
            effect=TRAP_EFFECTS[TrapEffectType.MAGIC_CAGE],
        )
        assert "dispel" in magic_trap.get_disarm_method().lower()

    def test_to_dict(self):
        """Trap should serialize to dictionary."""
        trap = Trap(
            trap_id="test",
            name="Test Trap",
            category=TrapCategory.MECHANISM,
            trigger=TrapTrigger.PRESSURE_PLATE,
            effect=TRAP_EFFECTS[TrapEffectType.SPIKES],
        )
        data = trap.to_dict()
        assert data["trap_id"] == "test"
        assert data["category"] == "mechanism"
        assert data["trigger"] == "pressure_plate"
        assert "effect" in data


class TestTrapGeneration:
    """Test trap generation functions."""

    def test_generate_random_trap(self):
        """Random trap should have all required fields."""
        DiceRoller.set_seed(42)
        dice = DiceRoller()
        trap = generate_random_trap(dice)

        assert trap.trap_id is not None
        assert trap.name is not None
        assert trap.category in TrapCategory
        assert trap.trigger in TrapTrigger
        assert trap.effect is not None

    def test_get_trap_by_effect(self):
        """Should create trap with specific effect."""
        trap = get_trap_by_effect(
            TrapEffectType.ACID_SPRAY,
            TrapCategory.MECHANISM,
            TrapTrigger.TRIPWIRE,
        )
        assert trap.effect.effect_type == TrapEffectType.ACID_SPRAY
        assert trap.category == TrapCategory.MECHANISM
        assert trap.trigger == TrapTrigger.TRIPWIRE


class TestExplorationClues:
    """Test exploration clues system."""

    def test_get_exploration_clues_includes_effect_clues(self):
        """Exploration clues should include effect-specific clues."""
        trap = get_trap_by_effect(
            TrapEffectType.ARROW_VOLLEY,
            TrapCategory.ARCHITECTURAL,
            TrapTrigger.TRIPWIRE,
        )
        clues = get_exploration_clues(trap)

        # Should include effect clues
        assert any("hole" in clue.lower() or "arrow" in clue.lower() for clue in clues)

    def test_get_exploration_clues_includes_trigger_clues(self):
        """Exploration clues should include trigger-specific clues."""
        trap = get_trap_by_effect(
            TrapEffectType.SPIKES,
            TrapCategory.MECHANISM,
            TrapTrigger.TRIPWIRE,
        )
        clues = get_exploration_clues(trap)

        # Should include tripwire clues
        assert any("glint" in clue.lower() or "ankle" in clue.lower() for clue in clues)


class TestBypassOptions:
    """Test bypass options for non-disarmable traps."""

    def test_pit_has_jump_option(self):
        """Pit traps should have jump across option."""
        trap = get_trap_by_effect(
            TrapEffectType.PIT_FALL,
            TrapCategory.PIT,
            TrapTrigger.PRESSURE_PLATE,
        )
        options = get_bypass_options(trap)

        jump_option = next((o for o in options if "jump" in o["method"].lower()), None)
        assert jump_option is not None

    def test_pressure_plate_has_weight_trigger(self):
        """Pressure plate traps should have weight trigger option."""
        trap = get_trap_by_effect(
            TrapEffectType.SPIKES,
            TrapCategory.MECHANISM,
            TrapTrigger.PRESSURE_PLATE,
        )
        options = get_bypass_options(trap)

        weight_option = next((o for o in options if "weight" in o["method"].lower()), None)
        assert weight_option is not None

    def test_tripwire_has_step_over(self):
        """Tripwire traps should have step over option."""
        trap = get_trap_by_effect(
            TrapEffectType.ARROW_VOLLEY,
            TrapCategory.ARCHITECTURAL,
            TrapTrigger.TRIPWIRE,
        )
        options = get_bypass_options(trap)

        step_option = next((o for o in options if "step over" in o["method"].lower()), None)
        assert step_option is not None


class TestDisarmRules:
    """Test category-based disarm rules per Campaign Book p102-103."""

    def test_pit_cannot_be_disarmed_by_anyone(self):
        """Pit traps cannot be disarmed by any class."""
        trap = get_trap_by_effect(
            TrapEffectType.PIT_FALL,
            TrapCategory.PIT,
            TrapTrigger.PRESSURE_PLATE,
        )

        can_thief, reason_thief = can_attempt_disarm(trap, "thief")
        can_fighter, reason_fighter = can_attempt_disarm(trap, "fighter")

        assert not can_thief
        assert not can_fighter
        assert "cannot be disarmed" in reason_thief.lower()

    def test_mechanism_requires_thief(self):
        """Mechanism traps require thief class."""
        trap = get_trap_by_effect(
            TrapEffectType.SPEAR_WALL,
            TrapCategory.MECHANISM,
            TrapTrigger.LOCK,
        )

        can_thief, _ = can_attempt_disarm(trap, "thief")
        can_fighter, reason = can_attempt_disarm(trap, "fighter")

        assert can_thief
        assert not can_fighter
        assert "thief" in reason.lower()

    def test_magical_requires_dispel(self):
        """Magical traps require Dispel Magic."""
        trap = get_trap_by_effect(
            TrapEffectType.MAGIC_SYMBOL,
            TrapCategory.MAGICAL,
            TrapTrigger.PROXIMITY,
        )

        can_mage_no_spell, _ = can_attempt_disarm(trap, "magic_user", has_dispel_magic=False)
        can_mage_with_spell, _ = can_attempt_disarm(trap, "magic_user", has_dispel_magic=True)

        assert not can_mage_no_spell
        assert can_mage_with_spell

    def test_magical_with_password(self):
        """Magical traps can be disabled with password."""
        trap = get_trap_by_effect(
            TrapEffectType.MAGIC_CAGE,
            TrapCategory.MAGICAL,
            TrapTrigger.SPEECH,
        )
        trap.password = "xyzzy"

        can_with_password, _ = can_attempt_disarm(trap, "fighter", knows_password=True)
        assert can_with_password


class TestDisarmAttempts:
    """Test actual disarm attempts."""

    def test_thief_disarm_mechanism(self):
        """Thief can attempt to disarm mechanism traps."""
        trap = get_trap_by_effect(
            TrapEffectType.SPEAR_WALL,
            TrapCategory.MECHANISM,
            TrapTrigger.LOCK,
        )
        DiceRoller.set_seed(1)
        dice = DiceRoller()

        result = attempt_disarm(
            trap=trap,
            character_class="thief",
            disarm_chance=95,  # High chance to succeed
            dice=dice,
        )

        assert result.thief_ability_used
        assert result.method_used == "disarm_mechanism"

    def test_password_auto_success(self):
        """Password disarm should auto-succeed."""
        trap = get_trap_by_effect(
            TrapEffectType.MAGIC_CAGE,
            TrapCategory.MAGICAL,
            TrapTrigger.SPEECH,
        )
        trap.password = "friend"

        result = attempt_disarm(
            trap=trap,
            character_class="fighter",
            disarm_chance=0,
            knows_password=True,
        )

        assert result.success
        assert result.password_used
        assert "friend" in result.message

    def test_failed_disarm_may_trigger(self):
        """Failed disarm attempt may trigger the trap."""
        trap = get_trap_by_effect(
            TrapEffectType.SPEAR_WALL,
            TrapCategory.MECHANISM,
            TrapTrigger.LOCK,
        )

        # Run many attempts to find at least one trigger
        triggered_count = 0
        for seed in range(100):
            DiceRoller.set_seed(seed)
            dice = DiceRoller()
            result = attempt_disarm(
                trap=trap,
                character_class="thief",
                disarm_chance=1,  # Very low chance - will fail
                dice=dice,
            )
            if result.trap_triggered:
                triggered_count += 1

        # Should trigger some of the time (roughly 1 in 6)
        assert triggered_count > 0


class TestTrapEffectMechanics:
    """Test specific trap effect mechanics."""

    def test_save_based_effect(self):
        """Effects with saves should have proper save info."""
        effect = TRAP_EFFECTS[TrapEffectType.GAS_PARALYSIS]
        assert effect.save_type == "doom"
        assert effect.save_negates is True
        assert effect.condition_applied == "paralyzed"

    def test_attack_based_effect(self):
        """Attack effects should have attack bonus and damage."""
        effect = TRAP_EFFECTS[TrapEffectType.SPEAR_WALL]
        assert effect.attack_bonus == 6
        assert effect.num_attacks == "1d6"
        assert effect.damage == "1d8"

    def test_duration_effect(self):
        """Duration effects should track rounds or turns."""
        sleep_effect = TRAP_EFFECTS[TrapEffectType.GAS_SLEEP]
        assert sleep_effect.duration_turns == 3

        light_effect = TRAP_EFFECTS[TrapEffectType.MAGIC_LIGHT_BLAST]
        assert light_effect.duration_rounds == 6

    def test_escape_effect(self):
        """Escape effects should have check and DC."""
        cage_effect = TRAP_EFFECTS[TrapEffectType.MAGIC_CAGE]
        assert cage_effect.escape_check == "STR"
        assert cage_effect.escape_dc == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
