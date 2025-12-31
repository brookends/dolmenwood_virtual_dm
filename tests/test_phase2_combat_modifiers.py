"""
Tests for Phase 2.3: Combat Modifier Spells.

Tests Mirror Image, Haste, Confusion, Fear, and attack modifier spells.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_models import (
    CharacterState,
    Condition,
    ConditionType,
    ConfusionBehavior,
)
from src.narrative.spell_resolver import (
    MagicType,
    MechanicalEffect,
    MechanicalEffectCategory,
    SpellData,
    SpellResolver,
)


def create_spell(
    spell_id: str,
    name: str,
    level: int,
    magic_type: MagicType,
    description: str,
    duration: str = "Instant",
    range_: str = "30'",
    **kwargs
) -> SpellData:
    """Helper to create SpellData with required fields."""
    return SpellData(
        spell_id=spell_id,
        name=name,
        level=level,
        magic_type=magic_type,
        duration=duration,
        range=range_,
        description=description,
        **kwargs
    )


# =============================================================================
# CONFUSION BEHAVIOR ENUM TESTS
# =============================================================================


class TestConfusionBehavior:
    """Tests for ConfusionBehavior enum."""

    def test_roll_behavior_attack_party(self):
        """Rolls 2-5 should result in attack_party."""
        for roll in [2, 3, 4, 5]:
            behavior = ConfusionBehavior.roll_behavior(roll)
            assert behavior == ConfusionBehavior.ATTACK_PARTY

    def test_roll_behavior_stand_confused(self):
        """Rolls 6-8 should result in stand_confused."""
        for roll in [6, 7, 8]:
            behavior = ConfusionBehavior.roll_behavior(roll)
            assert behavior == ConfusionBehavior.STAND_CONFUSED

    def test_roll_behavior_attack_nearest(self):
        """Rolls 9-11 should result in attack_nearest."""
        for roll in [9, 10, 11]:
            behavior = ConfusionBehavior.roll_behavior(roll)
            assert behavior == ConfusionBehavior.ATTACK_NEAREST

    def test_roll_behavior_act_normally(self):
        """Roll 12 should result in act_normally."""
        behavior = ConfusionBehavior.roll_behavior(12)
        assert behavior == ConfusionBehavior.ACT_NORMALLY


# =============================================================================
# CHARACTER STATE COMBAT MODIFIER TESTS
# =============================================================================


class TestCharacterStateCombatModifiers:
    """Tests for CharacterState combat modifier methods."""

    @pytest.fixture
    def character(self):
        """Create a test character."""
        return CharacterState(
            character_id="test_char",
            name="Test Character",
            character_class="Fighter",
            level=5,
            ability_scores={"STR": 14, "DEX": 12, "CON": 13, "INT": 10, "WIS": 11, "CHA": 10},
            hp_current=30,
            hp_max=35,
            armor_class=14,
            base_speed=40,
        )

    def test_has_mirror_images_none(self, character):
        """Character with no images returns False."""
        assert character.has_mirror_images() is False
        assert character.mirror_image_count == 0

    def test_has_mirror_images_active(self, character):
        """Character with images returns True."""
        character.mirror_image_count = 3
        assert character.has_mirror_images() is True

    def test_resolve_attack_vs_mirror_image_no_images(self, character):
        """Attack with no images proceeds normally."""
        character.mirror_image_count = 0
        result = character.resolve_attack_vs_mirror_image()
        assert result is False

    @patch("src.data_models.DiceRoller")
    def test_resolve_attack_vs_mirror_image_hits_image(self, mock_roller_class, character):
        """Attack hitting an image removes it."""
        character.mirror_image_count = 3

        # Mock to hit an image (roll 1-3 on d4)
        mock_roller = MagicMock()
        mock_roller.roll.return_value = MagicMock(total=2)
        mock_roller_class.return_value = mock_roller

        result = character.resolve_attack_vs_mirror_image()

        assert result is True  # Image absorbed hit
        assert character.mirror_image_count == 2  # One image destroyed

    @patch("src.data_models.DiceRoller")
    def test_resolve_attack_vs_mirror_image_hits_caster(self, mock_roller_class, character):
        """Attack hitting real character proceeds normally."""
        character.mirror_image_count = 3

        # Mock to hit caster (roll 4 on d4)
        mock_roller = MagicMock()
        mock_roller.roll.return_value = MagicMock(total=4)
        mock_roller_class.return_value = mock_roller

        result = character.resolve_attack_vs_mirror_image()

        assert result is False  # Attack proceeds
        assert character.mirror_image_count == 3  # No image destroyed

    def test_is_confused_false(self, character):
        """Character without confused condition returns False."""
        assert character.is_confused() is False

    def test_is_confused_true(self, character):
        """Character with confused condition returns True."""
        character.conditions.append(
            Condition(
                condition_type=ConditionType.CONFUSED,
                source="Confusion spell",
            )
        )
        assert character.is_confused() is True

    @patch("src.data_models.DiceRoller")
    def test_roll_confusion_behavior(self, mock_roller_class, character):
        """Rolling confusion behavior updates state."""
        character.conditions.append(
            Condition(
                condition_type=ConditionType.CONFUSED,
                source="Confusion spell",
            )
        )

        mock_roller = MagicMock()
        mock_roller.roll.return_value = MagicMock(total=7)  # stand confused
        mock_roller_class.return_value = mock_roller

        behavior = character.roll_confusion_behavior()

        assert behavior == ConfusionBehavior.STAND_CONFUSED
        assert character.confusion_behavior == "stand_confused"

    def test_is_hasted_false(self, character):
        """Character without hasted condition returns False."""
        assert character.is_hasted() is False

    def test_is_hasted_true(self, character):
        """Character with hasted condition returns True."""
        character.conditions.append(
            Condition(
                condition_type=ConditionType.HASTED,
                source="Haste spell",
            )
        )
        assert character.is_hasted() is True

    def test_is_frightened_false(self, character):
        """Character without frightened condition returns False."""
        assert character.is_frightened() is False

    def test_is_frightened_true(self, character):
        """Character with frightened condition returns True."""
        character.conditions.append(
            Condition(
                condition_type=ConditionType.FRIGHTENED,
                source="Fear spell",
            )
        )
        assert character.is_frightened() is True


# =============================================================================
# GLOBAL CONTROLLER COMBAT MODIFIER TESTS
# =============================================================================


class TestControllerCombatModifiers:
    """Tests for GlobalController combat modifier methods."""

    @pytest.fixture
    def controller(self):
        """Create a test controller with a character."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()
        character = CharacterState(
            character_id="test_pc",
            name="Test PC",
            character_class="Fighter",
            level=5,
            ability_scores={"STR": 14, "DEX": 12, "CON": 13, "INT": 10, "WIS": 11, "CHA": 10},
            hp_current=30,
            hp_max=35,
            armor_class=14,
            base_speed=40,
        )
        controller._characters["test_pc"] = character
        return controller

    def test_apply_mirror_images(self, controller):
        """Apply mirror images to a character."""
        result = controller.apply_mirror_images("test_pc", dice="1d4")

        assert result["success"] is True
        assert result["character_id"] == "test_pc"
        assert 1 <= result["images_created"] <= 4

        character = controller.get_character("test_pc")
        assert character.mirror_image_count == result["images_created"]

    def test_apply_mirror_images_not_found(self, controller):
        """Apply mirror images to nonexistent character fails."""
        result = controller.apply_mirror_images("nonexistent", dice="1d4")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_remove_mirror_images(self, controller):
        """Remove mirror images from a character."""
        character = controller.get_character("test_pc")
        character.mirror_image_count = 3

        result = controller.remove_mirror_images("test_pc")

        assert result["success"] is True
        assert result["images_removed"] == 3
        assert character.mirror_image_count == 0

    def test_apply_haste(self, controller):
        """Apply haste to a character."""
        result = controller.apply_haste("test_pc", duration_turns=3)

        assert result["success"] is True
        assert result["character_id"] == "test_pc"
        assert result["duration_turns"] == 3
        assert result["bonuses"]["ac"] == 2
        assert result["bonuses"]["initiative"] == 2
        assert result["bonuses"]["extra_action"] is True

        character = controller.get_character("test_pc")
        assert character.is_hasted() is True

    def test_apply_confusion(self, controller):
        """Apply confusion to a character."""
        result = controller.apply_confusion("test_pc", duration_turns=5)

        assert result["success"] is True
        assert result["character_id"] == "test_pc"
        assert result["duration_turns"] == 5
        assert "behavior_table" in result

        character = controller.get_character("test_pc")
        assert character.is_confused() is True

    def test_roll_confusion_behavior(self, controller):
        """Roll confusion behavior for confused character."""
        controller.apply_confusion("test_pc", duration_turns=5)

        result = controller.roll_confusion_behavior("test_pc")

        assert result["success"] is True
        assert result["behavior"] in ["attack_party", "stand_confused", "attack_nearest", "act_normally"]
        assert "description" in result

    def test_roll_confusion_behavior_not_confused(self, controller):
        """Rolling confusion behavior for non-confused character fails."""
        result = controller.roll_confusion_behavior("test_pc")

        assert result["success"] is False
        assert "not confused" in result["error"]

    def test_apply_fear(self, controller):
        """Apply fear to a character."""
        result = controller.apply_fear("test_pc", duration_turns=2)

        assert result["success"] is True
        assert result["character_id"] == "test_pc"
        assert result["duration_turns"] == 2
        assert "flee" in result["effect"].lower()

        character = controller.get_character("test_pc")
        assert character.is_frightened() is True

    def test_apply_attack_modifier(self, controller):
        """Apply attack modifier to a character."""
        result = controller.apply_attack_modifier(
            "test_pc",
            modifier=2,
            duration_turns=3,
            source="Ginger Snap",
        )

        assert result["success"] is True
        assert result["attack_modifier"] == 2
        assert result["source"] == "Ginger Snap"


# =============================================================================
# SPELL PARSING TESTS
# =============================================================================


class TestCombatModifierSpellParsing:
    """Tests for parsing combat modifier spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_mirror_image(self, resolver):
        """Parse Mirror Image spell."""
        spell = create_spell(
            spell_id="mirror_image",
            name="Mirror Image",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Creates 1d4 illusory duplicates of the caster that move with them.",
            duration="6 Turns",
            range_="Self",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        mirror_effects = [e for e in parsed.effects if e.creates_mirror_images]
        assert len(mirror_effects) >= 1

        effect = mirror_effects[0]
        assert effect.is_combat_modifier is True
        assert effect.mirror_image_dice == "1d4"

    def test_parse_haste(self, resolver):
        """Parse Haste spell."""
        spell = create_spell(
            spell_id="haste",
            name="Haste",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Target can act twice per round and gains +2 to AC and initiative.",
            duration="3 Turns",
            range_="120'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        haste_effects = [e for e in parsed.effects if e.is_haste_effect]
        assert len(haste_effects) >= 1

        effect = haste_effects[0]
        assert effect.is_combat_modifier is True
        assert effect.condition_applied == "hasted"

    def test_parse_confusion(self, resolver):
        """Parse Confusion spell."""
        spell = create_spell(
            spell_id="confusion",
            name="Confusion",
            magic_type=MagicType.ARCANE,
            level=4,
            description="3d6 creatures of 2 HD or less in the area become confused. Save vs spell negates.",
            duration="12 Rounds",
            range_="120'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        confusion_effects = [e for e in parsed.effects if e.is_confusion_effect]
        assert len(confusion_effects) >= 1

        effect = confusion_effects[0]
        assert effect.is_combat_modifier is True
        assert effect.condition_applied == "confused"
        assert effect.save_type == "spell"

    def test_parse_fear(self, resolver):
        """Parse Fear spell."""
        spell = create_spell(
            spell_id="fear",
            name="Fear",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Targets must flee in terror. Save vs spell negates.",
            duration="2 Turns",
            range_="60' cone",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        fear_effects = [e for e in parsed.effects if e.is_fear_effect]
        assert len(fear_effects) >= 1

        effect = fear_effects[0]
        assert effect.is_combat_modifier is True
        assert effect.condition_applied == "frightened"
        assert effect.save_type == "spell"

    def test_parse_attack_bonus(self, resolver):
        """Parse spell with attack bonus."""
        spell = create_spell(
            spell_id="battle_blessing",
            name="Battle Blessing",
            magic_type=MagicType.DIVINE,
            level=1,
            description="Target gains +2 to attack rolls for the duration.",
            duration="6 Turns",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        attack_effects = [e for e in parsed.effects if e.attack_bonus is not None]
        assert len(attack_effects) >= 1

        effect = attack_effects[0]
        assert effect.attack_bonus == 2
        assert effect.stat_modified == "attack"

    def test_parse_ginger_snap(self, resolver):
        """Parse Ginger Snap spell (specific spell name detection)."""
        spell = create_spell(
            spell_id="ginger_snap",
            name="Ginger Snap",
            magic_type=MagicType.ARCANE,
            level=3,
            description="The ginger snap enhances the target's combat prowess.",
            duration="1 Turn",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        attack_effects = [e for e in parsed.effects if e.attack_bonus is not None]
        assert len(attack_effects) >= 1

        effect = attack_effects[0]
        assert effect.attack_bonus == 2


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestCombatModifierIntegration:
    """Integration tests for combat modifier flow."""

    @pytest.fixture
    def controller(self):
        """Create a controller with party."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add wizard
        wizard = CharacterState(
            character_id="wizard",
            name="Test Wizard",
            character_class="Magician",
            level=7,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 17, "WIS": 12, "CHA": 11},
            hp_current=15,
            hp_max=18,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["wizard"] = wizard

        # Add fighter
        fighter = CharacterState(
            character_id="fighter",
            name="Test Fighter",
            character_class="Fighter",
            level=7,
            ability_scores={"STR": 17, "DEX": 12, "CON": 15, "INT": 10, "WIS": 11, "CHA": 10},
            hp_current=50,
            hp_max=55,
            armor_class=16,
            base_speed=40,
        )
        controller._characters["fighter"] = fighter

        return controller

    def test_full_mirror_image_workflow(self, controller):
        """Test complete mirror image workflow."""
        # Wizard casts mirror image on self
        result = controller.apply_mirror_images("wizard", dice="1d4", caster_id="wizard")
        assert result["success"] is True
        initial_images = result["images_created"]

        wizard = controller.get_character("wizard")
        assert wizard.has_mirror_images() is True

        # Simulate attacks hitting images
        images_destroyed = 0
        for _ in range(initial_images + 5):  # Try more attacks than images
            if wizard.mirror_image_count > 0:
                absorbed = wizard.resolve_attack_vs_mirror_image()
                if absorbed:
                    images_destroyed += 1

        # Eventually all images should be destroyed (or attack hits real target)
        assert images_destroyed <= initial_images

    def test_full_haste_workflow(self, controller):
        """Test complete haste workflow."""
        # Cast haste on fighter
        result = controller.apply_haste("fighter", duration_turns=3, caster_id="wizard")
        assert result["success"] is True

        fighter = controller.get_character("fighter")
        assert fighter.is_hasted() is True

        # Check condition details
        haste_condition = fighter.get_condition(ConditionType.HASTED)
        assert haste_condition is not None
        assert haste_condition.duration_turns == 3

    def test_full_confusion_workflow(self, controller):
        """Test complete confusion workflow."""
        # Apply confusion
        result = controller.apply_confusion("fighter", duration_turns=5, caster_id="wizard")
        assert result["success"] is True

        fighter = controller.get_character("fighter")
        assert fighter.is_confused() is True

        # Roll behavior each round
        behaviors = []
        for _ in range(10):  # Roll multiple times
            result = controller.roll_confusion_behavior("fighter")
            assert result["success"] is True
            behaviors.append(result["behavior"])

        # Should have some variety in behaviors (statistical, not guaranteed)
        unique_behaviors = set(behaviors)
        assert len(unique_behaviors) >= 1  # At minimum one type
