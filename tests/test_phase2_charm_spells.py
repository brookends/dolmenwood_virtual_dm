"""
Tests for Phase 2.1: Charm/Control Spell Support.

Tests charm spell parsing, application, recurring saves, and command effects.
"""

import pytest
from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    MagicType,
    MechanicalEffectCategory,
)
from src.data_models import CharacterState, ConditionType
from src.game_state.global_controller import GlobalController


# =============================================================================
# FIXTURES
# =============================================================================


def make_spell(
    spell_id: str,
    name: str,
    level: int,
    magic_type: MagicType,
    description: str,
    duration: str = "Permanent until broken",
    range_: str = "120'",
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


@pytest.fixture
def resolver():
    """Create a SpellResolver instance."""
    return SpellResolver()


@pytest.fixture
def magic_user():
    """Create a magic-user character (caster)."""
    return CharacterState(
        character_id="mage_1",
        name="Elara",
        character_class="Magic-User",
        level=5,
        ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 17, "WIS": 12, "CHA": 12},
        hp_current=12,
        hp_max=12,
        armor_class=12,
        base_speed=40,
    )


@pytest.fixture
def target_npc():
    """Create a target NPC character."""
    return CharacterState(
        character_id="npc_1",
        name="Villager Bob",
        character_class="Commoner",
        level=1,
        ability_scores={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        hp_current=5,
        hp_max=5,
        armor_class=10,
        base_speed=40,
    )


@pytest.fixture
def controller_with_characters(magic_user, target_npc):
    """Create a GlobalController with both characters registered."""
    controller = GlobalController()
    controller.add_character(magic_user)
    controller.add_character(target_npc)
    return controller, magic_user, target_npc


# =============================================================================
# CHARM SPELL PARSING TESTS
# =============================================================================


class TestCharmSpellParsing:
    """Tests for parsing charm spells from descriptions."""

    def test_parse_ingratiate_spell(self, resolver):
        """Ingratiate spell should parse as a charm effect with daily saves."""
        spell = make_spell(
            spell_id="ingratiate",
            name="Ingratiate",
            level=1,
            magic_type=MagicType.ARCANE,
            description="""Enchants a small object with the power to charm a person who
            willingly accepts it as a gift. Recipient: A single mortal, fairy, or demi-fey
            who accepts the enchanted object must Save Versus Spell or be charmed.
            The charm lasts indefinitely, but the subject makes a further Save Versus
            Spell once per day. If one of these saves succeeds, the charm ends.""",
            duration="3 Turns",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        # Should have a charm effect
        charm_effects = [e for e in parsed.effects if e.is_charm_effect]
        assert len(charm_effects) == 1

        effect = charm_effects[0]
        assert effect.condition_applied == "charmed"
        assert effect.recurring_save_frequency == "daily"
        assert effect.save_type == "spell"
        assert effect.save_negates is True

    def test_parse_dominate_spell(self, resolver):
        """Dominate spell should parse with multi-target and level limit."""
        spell = make_spell(
            spell_id="dominate",
            name="Dominate",
            level=4,
            magic_type=MagicType.ARCANE,
            description="""Places a powerful charm on one or more living creatures.
            Subjects: Either 3d6 creatures of up to Level 3 or a single creature
            of higher Level. Each subject must Save Versus Spell or be charmed.
            Charm duration: The charm lasts indefinitely, but each subject makes
            a further Save Versus Spell once per day. Commands: If they share a
            language, the caster may give the charmed subjects commands.""",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        charm_effects = [e for e in parsed.effects if e.is_charm_effect]
        assert len(charm_effects) == 1

        effect = charm_effects[0]
        assert effect.condition_applied == "charmed"
        assert effect.recurring_save_frequency == "daily"
        assert effect.multi_target_dice == "3d6"
        assert effect.target_level_limit == 3
        assert effect.charm_obeys_commands is True

    def test_parse_charm_serpents(self, resolver):
        """Charm Serpents should parse as a charm effect (hypnotises)."""
        spell = make_spell(
            spell_id="charm_serpents",
            name="Charm Serpents",
            level=2,
            magic_type=MagicType.DIVINE,
            description="""This prayer hypnotises snakes; the serpents rear upright
            and sway to and fro, but they never attack while charmed. Number of
            snakes affected: Snakes whose Levels total up to twice the caster's Level.""",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        charm_effects = [e for e in parsed.effects if e.is_charm_effect]
        assert len(charm_effects) == 1

        effect = charm_effects[0]
        assert effect.condition_applied == "charmed"

    def test_parse_command_spell(self, resolver):
        """Command spell should parse as a command effect."""
        spell = make_spell(
            spell_id="command",
            name="Command",
            level=1,
            magic_type=MagicType.DIVINE,
            description="""The caster utters a command charged with holy power.
            A selected creature within range is magically compelled to obey for
            1 Round. Command: The command is limited to a single word (e.g. flee,
            back, stop, surrender). Saving Throw: The subject may Save Versus
            Hold to resist the command.""",
            duration="1 Round",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        command_effects = [e for e in parsed.effects if e.command_word_only]
        assert len(command_effects) == 1

        effect = command_effects[0]
        assert effect.condition_applied == "commanded"
        assert effect.is_charm_effect is True
        assert effect.save_type == "hold"
        assert effect.save_negates is True

    def test_non_charm_spell_not_parsed(self, resolver):
        """Non-charm spells should not have charm effects."""
        spell = make_spell(
            spell_id="fireball",
            name="Fireball",
            level=3,
            magic_type=MagicType.ARCANE,
            description="Hurls a ball of fire that explodes for 1d6 damage per level.",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        charm_effects = [e for e in parsed.effects if e.is_charm_effect]
        assert len(charm_effects) == 0


# =============================================================================
# CONTROLLER CHARM TESTS
# =============================================================================


class TestControllerCharmApplication:
    """Tests for GlobalController charm application."""

    def test_apply_charm_success(self, controller_with_characters):
        """Successfully applying a charm via controller."""
        controller, caster, target = controller_with_characters

        result = controller.apply_charm(
            character_id=target.character_id,
            caster_id=caster.character_id,
            source_spell_id="ingratiate",
            source="Ingratiate",
            recurring_save={"save_type": "spell", "frequency": "daily", "ends_on_success": True},
        )

        assert result["charmed"] is True
        assert result["caster_id"] == caster.character_id
        assert result["has_recurring_save"] is True
        assert result["recurring_save_frequency"] == "daily"

        # Verify target is now charmed
        assert target.is_charmed() is True
        assert target.is_charmed_by(caster.character_id) is True

    def test_apply_charm_already_charmed(self, controller_with_characters):
        """Cannot charm an already charmed character."""
        controller, caster, target = controller_with_characters

        # First charm succeeds
        controller.apply_charm(
            character_id=target.character_id,
            caster_id=caster.character_id,
            source_spell_id="ingratiate",
            source="Ingratiate",
        )

        # Second charm fails
        result = controller.apply_charm(
            character_id=target.character_id,
            caster_id="another_caster",
            source_spell_id="dominate",
            source="Dominate",
        )

        assert result["charmed"] is False
        assert "Already charmed" in result["reason"]
        assert result["existing_charmer"] == caster.character_id

    def test_apply_charm_character_not_found(self, controller_with_characters):
        """Charm fails for non-existent character."""
        controller, caster, target = controller_with_characters

        result = controller.apply_charm(
            character_id="nonexistent",
            caster_id=caster.character_id,
            source_spell_id="ingratiate",
            source="Ingratiate",
        )

        assert "error" in result

    def test_break_charm(self, controller_with_characters):
        """Successfully breaking a charm."""
        controller, caster, target = controller_with_characters

        controller.apply_charm(
            character_id=target.character_id,
            caster_id=caster.character_id,
            source_spell_id="ingratiate",
            source="Ingratiate",
        )

        assert target.is_charmed() is True

        result = controller.break_charm(
            character_id=target.character_id,
            reason="Successful save",
        )

        assert result["charm_broken"] is True
        assert result["former_charmer"] == caster.character_id
        assert target.is_charmed() is False

    def test_break_charm_when_not_charmed(self, controller_with_characters):
        """Breaking charm when not charmed returns appropriate result."""
        controller, caster, target = controller_with_characters

        result = controller.break_charm(
            character_id=target.character_id,
            reason="No reason",
        )

        assert result["charm_broken"] is False
        assert "not charmed" in result["reason"]


# =============================================================================
# CHARACTER STATE CHARM TESTS
# =============================================================================


class TestCharacterStateCharm:
    """Tests for CharacterState charm methods."""

    def test_is_hostile_to_charmer(self, magic_user, target_npc):
        """Charmed characters are not hostile to their charmer."""
        target_npc.apply_charm(
            caster_id=magic_user.character_id,
            source_spell_id="ingratiate",
            source="Ingratiate",
        )

        assert target_npc.is_hostile_to(magic_user.character_id) is False
        assert target_npc.is_hostile_to("some_other_person") is True

    def test_get_charm_caster(self, magic_user, target_npc):
        """Can retrieve who charmed a character."""
        assert target_npc.get_charm_caster() is None

        target_npc.apply_charm(
            caster_id=magic_user.character_id,
            source_spell_id="ingratiate",
            source="Ingratiate",
        )

        assert target_npc.get_charm_caster() == magic_user.character_id

    def test_check_charm_saves_daily(self, magic_user, target_npc):
        """Daily charm saves are detected correctly."""
        target_npc.apply_charm(
            caster_id=magic_user.character_id,
            source_spell_id="ingratiate",
            source="Ingratiate",
            recurring_save={"save_type": "spell", "frequency": "daily", "ends_on_success": True},
        )

        # Day 0: No save needed
        needs_save = target_npc.check_charm_saves(current_day=0)
        assert len(needs_save) == 0

        # Day 1: Save needed
        needs_save = target_npc.check_charm_saves(current_day=1)
        assert len(needs_save) == 1
        assert needs_save[0].condition_type == ConditionType.CHARMED


# =============================================================================
# SPELL EFFECT APPLICATION TESTS
# =============================================================================


class TestCharmSpellApplication:
    """Tests for applying charm spell effects."""

    def test_charm_effect_applied_via_resolver(self, controller_with_characters, resolver):
        """Charm effects are properly applied through spell resolution."""
        controller, caster, target = controller_with_characters
        resolver.set_controller(controller)

        spell = make_spell(
            spell_id="ingratiate",
            name="Ingratiate",
            level=1,
            magic_type=MagicType.ARCANE,
            description="""Enchants a small object with the power to charm a person.
            The recipient must Save Versus Spell or be charmed. The charm lasts
            indefinitely, but the subject makes a further Save Versus Spell once
            per day.""",
        )

        # Apply effects (simulating failed save)
        result = resolver._apply_mechanical_effects(
            spell=spell,
            caster=caster,
            targets_affected=[target.character_id],
            targets_saved=[],  # Target failed save
            save_negates=True,
            dice_roller=None,
            duration_turns=None,
            effect_id="test_effect",
        )

        # Should have charm effects
        assert "charm_effects" in result
        assert len(result["charm_effects"]) == 1
        assert result["charm_effects"][0]["target_id"] == target.character_id
        assert result["charm_effects"][0]["caster_id"] == caster.character_id

        # Target should be charmed
        assert target.is_charmed() is True
        assert target.is_charmed_by(caster.character_id) is True

    def test_charm_not_applied_on_save(self, controller_with_characters, resolver):
        """Charm effects are not applied when target saves."""
        controller, caster, target = controller_with_characters
        resolver.set_controller(controller)

        spell = make_spell(
            spell_id="ingratiate",
            name="Ingratiate",
            level=1,
            magic_type=MagicType.ARCANE,
            description="""Enchants a small object with the power to charm a person.
            The recipient must Save Versus Spell or be charmed.""",
        )

        # Apply effects (simulating successful save)
        result = resolver._apply_mechanical_effects(
            spell=spell,
            caster=caster,
            targets_affected=[target.character_id],
            targets_saved=[target.character_id],  # Target made save
            save_negates=True,
            dice_roller=None,
            duration_turns=None,
            effect_id="test_effect",
        )

        # Should not have charm effects
        assert "charm_effects" not in result or len(result.get("charm_effects", [])) == 0

        # Target should not be charmed
        assert target.is_charmed() is False


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestCharmIntegration:
    """Integration tests for the full charm spell workflow."""

    def test_ingratiate_full_workflow(self, controller_with_characters, resolver):
        """Full workflow for Ingratiate spell."""
        controller, caster, target = controller_with_characters
        resolver.set_controller(controller)

        # Create the actual Ingratiate spell
        spell = make_spell(
            spell_id="ingratiate",
            name="Ingratiate",
            level=1,
            magic_type=MagicType.ARCANE,
            description="""Enchants a small object with the power to charm a person who
            willingly accepts it as a gift. Recipient: A single mortal, fairy, or demi-fey
            who accepts the enchanted object must Save Versus Spell or be charmed.
            Restrictions: Large creatures or those of below Sentient intelligence are immune.
            Charm duration: The charm lasts indefinitely, but the subject makes a further
            Save Versus Spell once per day. If one of these saves succeeds, the charm ends.
            Friendship: The subject regards the caster as a close friend and comes to the
            caster's defence. Commands: If they share a language, the caster may give the
            charmed subject commands, which they obey. Resisting commands: Subjects resist
            commands that contradict their habits or Alignment.""",
            duration="3 Turns",
        )

        # 1. Parse the spell
        parsed = resolver.parse_mechanical_effects(spell)
        charm_effects = [e for e in parsed.effects if e.is_charm_effect]
        assert len(charm_effects) == 1
        assert charm_effects[0].recurring_save_frequency == "daily"
        assert charm_effects[0].charm_obeys_commands is True

        # 2. Apply the charm (target fails save)
        result = resolver._apply_mechanical_effects(
            spell=spell,
            caster=caster,
            targets_affected=[target.character_id],
            targets_saved=[],
            save_negates=True,
            dice_roller=None,
            duration_turns=None,
            effect_id="ingratiate_effect_1",
        )

        # 3. Verify target is charmed
        assert target.is_charmed() is True
        assert target.is_charmed_by(caster.character_id) is True
        assert target.is_hostile_to(caster.character_id) is False

        # 4. Check charm condition has recurring save info
        charm = target.get_condition(ConditionType.CHARMED)
        assert charm is not None
        assert charm.recurring_save is not None
        assert charm.recurring_save["frequency"] == "daily"

    def test_dominate_multi_target(self, resolver):
        """Dominate spell should parse multi-target dice."""
        spell = make_spell(
            spell_id="dominate",
            name="Dominate",
            level=4,
            magic_type=MagicType.ARCANE,
            description="""Places a powerful charm on one or more living creatures.
            Subjects: Either 3d6 creatures of up to Level 3 or a single creature of
            higher Level, as chosen by the caster. Each subject must Save Versus
            Spell or be charmed.""",
        )

        parsed = resolver.parse_mechanical_effects(spell)
        charm_effects = [e for e in parsed.effects if e.is_charm_effect]

        assert len(charm_effects) == 1
        assert charm_effects[0].multi_target_dice == "3d6"
        assert charm_effects[0].target_level_limit == 3
