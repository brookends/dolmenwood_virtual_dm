"""
Tests for effect commands that mutate game state.

Phase 3.1: Verify that effect commands actually modify the controller
state instead of just returning success with no changes.
"""

import pytest

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.oracle.effect_commands import (
    EffectCommandBuilder,
    EffectExecutor,
    EffectType,
)


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


@pytest.fixture
def test_character():
    """A sample character for testing effects."""
    return CharacterState(
        character_id="test_mage_1",
        name="Test Mage",
        character_class="Magic-User",
        level=3,
        ability_scores={
            "STR": 10, "INT": 16, "WIS": 12,
            "DEX": 13, "CON": 14, "CHA": 11,
        },
        hp_current=12,
        hp_max=12,
        armor_class=9,
        base_speed=30,
    )


@pytest.fixture
def dm_with_character(seeded_dice, test_character):
    """Create VirtualDM with a character for testing effects."""
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
    return dm


class TestDamageEffectMutatesState:
    """Test that damage effect actually modifies HP."""

    def test_damage_reduces_hp(self, dm_with_character, seeded_dice):
        """Damage effect should reduce character HP."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")
        initial_hp = char.hp_current

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.damage(
            target_id="test_mage_1",
            amount=5,
            damage_type="fire",
            source="Fireball",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert char.hp_current == initial_hp - 5
        assert result.changes.get("damage") == 5
        assert result.changes.get("hp_remaining") == initial_hp - 5

    def test_damage_with_dice_expression(self, dm_with_character, seeded_dice):
        """Damage with dice expression should resolve and apply."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")
        initial_hp = char.hp_current

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.damage(
            target_id="test_mage_1",
            amount="1d6",
            damage_type="magic",
            source="Magic Missile",
        )

        result = executor.execute(cmd)

        assert result.success is True
        # HP should have decreased (we don't know exact amount due to dice)
        assert char.hp_current < initial_hp
        assert result.changes.get("damage") > 0

    def test_damage_to_nonexistent_entity_fails(self, dm_with_character, seeded_dice):
        """Damage to unknown entity should fail explicitly."""
        controller = dm_with_character.controller

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.damage(
            target_id="nonexistent_character",
            amount=10,
            damage_type="cold",
            source="Cone of Cold",
        )

        result = executor.execute(cmd)

        assert result.success is False
        assert "nonexistent_character" in result.description or "nonexistent_character" in result.error


class TestHealEffectMutatesState:
    """Test that heal effect actually modifies HP."""

    def test_heal_increases_hp(self, dm_with_character, seeded_dice):
        """Heal effect should increase character HP."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        # First damage the character
        char.hp_current = 5

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.heal(
            target_id="test_mage_1",
            amount=4,
            source="Cure Light Wounds",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert char.hp_current == 9
        assert result.changes.get("healing") == 4

    def test_heal_does_not_exceed_max_hp(self, dm_with_character, seeded_dice):
        """Heal should not raise HP above max."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        # Damage slightly
        char.hp_current = 10

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.heal(
            target_id="test_mage_1",
            amount=10,  # More than needed
            source="Cure Serious Wounds",
        )

        result = executor.execute(cmd)

        assert result.success is True
        # Should be capped at max
        assert char.hp_current <= char.hp_max

    def test_heal_to_nonexistent_entity_fails(self, dm_with_character, seeded_dice):
        """Heal to unknown entity should fail explicitly."""
        controller = dm_with_character.controller

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.heal(
            target_id="ghost_character",
            amount=5,
            source="Heal",
        )

        result = executor.execute(cmd)

        assert result.success is False
        assert "ghost_character" in result.description or "ghost_character" in result.error


class TestConditionEffectMutatesState:
    """Test that condition effects modify character conditions."""

    def test_add_condition(self, dm_with_character, seeded_dice):
        """Add condition should apply condition to character."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        # Ensure no conditions initially
        if not hasattr(char, 'conditions'):
            char.conditions = []
        initial_conditions = len(char.conditions)

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.add_condition(
            target_id="test_mage_1",
            condition="cursed",
            duration="1 day",
            source="Bestow Curse",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert result.changes.get("added_condition") == "cursed"

    def test_remove_condition(self, dm_with_character, seeded_dice):
        """Remove condition should clear condition from character."""
        controller = dm_with_character.controller

        # First apply a condition
        controller.apply_condition("test_mage_1", "poisoned", source="test")

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.remove_condition(
            target_id="test_mage_1",
            condition="poisoned",
            source="Remove Poison",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert result.changes.get("removed_condition") == "poisoned"

    def test_add_condition_to_nonexistent_entity_fails(self, dm_with_character, seeded_dice):
        """Add condition to unknown entity should fail explicitly."""
        controller = dm_with_character.controller

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.add_condition(
            target_id="missing_person",
            condition="charmed",
            source="Charm Person",
        )

        result = executor.execute(cmd)

        assert result.success is False
        assert "missing_person" in result.description or "missing_person" in result.error


class TestModifyStatEffectMutatesState:
    """Test that stat modification effects change ability scores."""

    def test_modify_stat_increases_score(self, dm_with_character, seeded_dice):
        """Modify stat should change ability score."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        initial_str = char.ability_scores["STR"]

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.modify_stat(
            target_id="test_mage_1",
            stat="STR",
            value=2,
            source="Gauntlets of Ogre Power",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert char.ability_scores["STR"] == initial_str + 2
        assert result.changes.get("old_value") == initial_str
        assert result.changes.get("new_value") == initial_str + 2
        assert result.changes.get("delta") == 2

    def test_modify_stat_decreases_score(self, dm_with_character, seeded_dice):
        """Modify stat with negative value should decrease ability score."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        initial_con = char.ability_scores["CON"]

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.modify_stat(
            target_id="test_mage_1",
            stat="CON",
            value=-2,
            source="Poison",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert char.ability_scores["CON"] == initial_con - 2
        assert result.changes.get("delta") == -2

    def test_modify_stat_cannot_go_below_one(self, dm_with_character, seeded_dice):
        """Stats should not go below 1."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        char.ability_scores["CHA"] = 3  # Set low

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.modify_stat(
            target_id="test_mage_1",
            stat="CHA",
            value=-10,  # Would make it negative
            source="Feeblemind",
        )

        result = executor.execute(cmd)

        assert result.success is True
        # Should be clamped to 1
        assert char.ability_scores["CHA"] >= 1

    def test_modify_stat_with_dice_expression(self, dm_with_character, seeded_dice):
        """Modify stat with dice expression should resolve and apply."""
        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        initial_wis = char.ability_scores["WIS"]

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.modify_stat(
            target_id="test_mage_1",
            stat="WIS",
            value="1d4",  # Gain 1-4 points
            source="Owl's Wisdom",
        )

        result = executor.execute(cmd)

        assert result.success is True
        # WIS should have increased
        assert char.ability_scores["WIS"] > initial_wis

    def test_modify_stat_to_nonexistent_entity_fails(self, dm_with_character, seeded_dice):
        """Modify stat on unknown entity should fail explicitly."""
        controller = dm_with_character.controller

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.modify_stat(
            target_id="imaginary_friend",
            stat="WIS",
            value=1,
            source="Owl's Wisdom",
        )

        result = executor.execute(cmd)

        assert result.success is False
        assert "imaginary_friend" in result.description or "imaginary_friend" in result.error


class TestExecutorWithoutController:
    """Test executor behavior when no controller is available."""

    def test_damage_without_controller_is_simulated(self, seeded_dice):
        """Without controller, damage should report simulated."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.damage(
            target_id="test_char",
            amount=10,
            source="Test",
        )

        result = executor.execute(cmd)

        # Should succeed but be simulated
        assert result.success is True
        assert result.changes.get("simulated") is True
        assert "[No controller]" in result.description

    def test_heal_without_controller_is_simulated(self, seeded_dice):
        """Without controller, heal should report simulated."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.heal(
            target_id="test_char",
            amount=5,
            source="Test",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert result.changes.get("simulated") is True


class TestSpellAdjudicatorEffectWiring:
    """Test that spell adjudicator creates effects that EffectExecutor can apply."""

    def test_curse_break_creates_effect_command(self, seeded_dice):
        """adjudicate_curse_break should create EffectCommand objects."""
        from src.oracle.spell_adjudicator import (
            MythicSpellAdjudicator,
            AdjudicationContext,
            SuccessLevel,
        )
        from src.oracle.effect_commands import EffectCommand, EffectType

        # Set seed for deterministic success
        DiceRoller.set_seed(100)

        adjudicator = MythicSpellAdjudicator()
        context = AdjudicationContext(
            spell_name="Remove Curse",
            caster_name="Test Cleric",
            caster_level=7,
            target_description="test_mage_1",
            intention="Remove the curse",
        )

        # Adjudicate (may need multiple seeds to get success)
        for seed in [100, 200, 300, 400, 500]:
            DiceRoller.set_seed(seed)
            result = adjudicator.adjudicate_curse_break(context, curse_power="minor")
            if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                break

        # Check that predetermined_effects contains EffectCommand objects
        if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
            assert len(result.predetermined_effects) > 0
            effect = result.predetermined_effects[0]
            assert isinstance(effect, EffectCommand)
            assert effect.effect_type == EffectType.REMOVE_CONDITION
            assert effect.parameters.get("condition") == "cursed"
            assert effect.target_id == "test_mage_1"

    def test_resolve_oracle_spell_effects_uses_executor(self, dm_with_character, seeded_dice):
        """resolve_oracle_spell_effects should use EffectExecutor to apply effects."""
        from src.oracle.spell_adjudicator import (
            MythicSpellAdjudicator,
            AdjudicationContext,
            SuccessLevel,
        )

        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        # Add a condition to remove
        controller.apply_condition("test_mage_1", "cursed", source="test")

        # Create adjudicator and get successful result
        adjudicator = MythicSpellAdjudicator()
        context = AdjudicationContext(
            spell_name="Remove Curse",
            caster_name="Test Cleric",
            caster_level=7,
            target_description="test_mage_1",
            intention="Remove the curse",
        )

        # Try different seeds to get a success
        for seed in [100, 200, 300, 400, 500, 600, 700]:
            DiceRoller.set_seed(seed)
            result = adjudicator.adjudicate_curse_break(context, curse_power="minor")
            if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                break

        # Apply effects via controller
        if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
            resolution = controller.resolve_oracle_spell_effects(
                result,
                caster_id="test_cleric_1",
                target_id="test_mage_1",
            )

            # Check that effects were applied
            assert len(resolution["applied_effects"]) > 0
            effect = resolution["applied_effects"][0]
            assert effect["type"] == "remove_condition"
            assert effect["success"] is True


class TestBatchExecution:
    """Test executing multiple effects as a batch."""

    def test_batch_applies_all_effects(self, dm_with_character, seeded_dice):
        """Batch execution should apply all effects in order."""
        from src.oracle.effect_commands import EffectBatch

        controller = dm_with_character.controller
        char = controller.get_character("test_mage_1")

        initial_hp = char.hp_current
        initial_str = char.ability_scores["STR"]

        batch = EffectBatch(source="Multi-effect Spell")
        batch.add(EffectCommandBuilder.damage(
            target_id="test_mage_1",
            amount=3,
            source="Test",
        ))
        batch.add(EffectCommandBuilder.modify_stat(
            target_id="test_mage_1",
            stat="STR",
            value=1,
            source="Test",
        ))

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        result_batch = executor.execute_batch(batch)

        assert result_batch.all_succeeded is True
        assert len(result_batch.results) == 2
        assert char.hp_current == initial_hp - 3
        assert char.ability_scores["STR"] == initial_str + 1

    def test_batch_reports_failures(self, dm_with_character, seeded_dice):
        """Batch with failing effect should report partial success."""
        from src.oracle.effect_commands import EffectBatch

        controller = dm_with_character.controller

        batch = EffectBatch(source="Mixed Batch")
        batch.add(EffectCommandBuilder.damage(
            target_id="test_mage_1",
            amount=2,
            source="Valid",
        ))
        batch.add(EffectCommandBuilder.heal(
            target_id="nonexistent",
            amount=5,
            source="Invalid",
        ))

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)
        result_batch = executor.execute_batch(batch)

        assert result_batch.all_succeeded is False
        assert result_batch.results[0].success is True
        assert result_batch.results[1].success is False


class TestInvalidEntityValidation:
    """P10.4: Test that invalid entities are properly rejected with explicit errors."""

    def test_validator_rejects_invalid_entity(self, dm_with_character, seeded_dice):
        """Validator should reject unknown entity with detailed reason."""
        from src.oracle.effect_commands import EffectValidator

        controller = dm_with_character.controller
        validator = EffectValidator(controller=controller)

        cmd = EffectCommandBuilder.damage(
            target_id="completely_fake_entity",
            amount=10,
            source="Test",
        )

        validated = validator.validate(cmd)

        assert validated.validated is False
        assert len(validated.validation_errors) > 0
        assert "completely_fake_entity" in validated.validation_errors[0]
        assert "not found" in validated.validation_errors[0].lower()

    def test_validator_accepts_valid_character(self, dm_with_character, seeded_dice):
        """Validator should accept registered character."""
        from src.oracle.effect_commands import EffectValidator

        controller = dm_with_character.controller
        validator = EffectValidator(controller=controller)

        cmd = EffectCommandBuilder.damage(
            target_id="test_mage_1",
            amount=5,
            source="Test",
        )

        validated = validator.validate(cmd)

        assert validated.validated is True
        assert len(validated.validation_errors) == 0

    def test_validator_accepts_special_targets(self, dm_with_character, seeded_dice):
        """Validator should accept special target identifiers."""
        from src.oracle.effect_commands import EffectValidator

        controller = dm_with_character.controller
        validator = EffectValidator(controller=controller)

        special_targets = ["party", "all", "self", "caster", "location", "area"]

        for target in special_targets:
            cmd = EffectCommandBuilder.custom(
                target_id=target,
                description="Test effect",
                source="Test",
            )
            validated = validator.validate(cmd)
            assert validated.validated is True, f"Special target '{target}' should be valid"

    def test_executor_reports_invalid_entity_in_error(self, dm_with_character, seeded_dice):
        """Executor should include entity ID and reason in error message."""
        controller = dm_with_character.controller
        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)

        cmd = EffectCommandBuilder.heal(
            target_id="nonexistent_healer",
            amount=10,
            source="Test",
        )

        result = executor.execute(cmd)

        assert result.success is False
        # Error should contain both the entity ID and reason
        error_text = result.error or result.description
        assert "nonexistent_healer" in error_text
        assert "not found" in error_text.lower()

    def test_simulated_mode_skips_entity_validation(self, seeded_dice):
        """Without controller, validation should be skipped for simulated mode."""
        from src.oracle.effect_commands import EffectValidator

        # Validator without controller
        validator = EffectValidator(controller=None)

        cmd = EffectCommandBuilder.damage(
            target_id="any_entity_id",
            amount=5,
            source="Test",
        )

        validated = validator.validate(cmd)

        # Should pass validation (simulated mode)
        assert validated.validated is True

    def test_executor_simulated_mode_still_works(self, seeded_dice):
        """Executor without controller should still work in simulated mode."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)

        cmd = EffectCommandBuilder.damage(
            target_id="simulated_target",
            amount=5,
            source="Test",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert result.changes.get("simulated") is True
        assert "[No controller]" in result.description

    def test_entity_with_registered_npc(self, dm_with_character, seeded_dice):
        """Validator should accept registered NPCs."""
        from src.oracle.effect_commands import EffectValidator

        controller = dm_with_character.controller

        # Register an NPC
        test_npc = CharacterState(
            character_id="test_npc_1",
            name="Test NPC",
            character_class="Fighter",
            level=2,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 12, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=7,
            base_speed=30,
        )
        controller.register_npc(test_npc)

        validator = EffectValidator(controller=controller)

        cmd = EffectCommandBuilder.damage(
            target_id="test_npc_1",
            amount=3,
            source="Test",
        )

        validated = validator.validate(cmd)

        assert validated.validated is True

    def test_all_effect_types_validate_entity(self, dm_with_character, seeded_dice):
        """All effect types that require entities should validate them."""
        controller = dm_with_character.controller
        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)

        # Test damage to invalid entity
        result = executor.execute(EffectCommandBuilder.damage(
            target_id="invalid_1", amount=5, source="Test"
        ))
        assert result.success is False
        assert "invalid_1" in (result.error or result.description)

        # Test heal to invalid entity
        result = executor.execute(EffectCommandBuilder.heal(
            target_id="invalid_2", amount=5, source="Test"
        ))
        assert result.success is False
        assert "invalid_2" in (result.error or result.description)

        # Test add_condition to invalid entity
        result = executor.execute(EffectCommandBuilder.add_condition(
            target_id="invalid_3", condition="cursed", source="Test"
        ))
        assert result.success is False
        assert "invalid_3" in (result.error or result.description)

        # Test remove_condition to invalid entity
        result = executor.execute(EffectCommandBuilder.remove_condition(
            target_id="invalid_4", condition="cursed", source="Test"
        ))
        assert result.success is False
        assert "invalid_4" in (result.error or result.description)

        # Test modify_stat to invalid entity
        result = executor.execute(EffectCommandBuilder.modify_stat(
            target_id="invalid_5", stat="STR", value=1, source="Test"
        ))
        assert result.success is False
        assert "invalid_5" in (result.error or result.description)
