"""
Tests for Phase 2.6-2.7: Summon/Control and Curse Systems.

Tests summoning spells, undead animation, and curse effects.
"""

import pytest
from unittest.mock import MagicMock

from src.data_models import (
    CharacterState,
    LocationState,
    LocationType,
    ConditionType,
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
# SUMMON SPELL PARSING TESTS
# =============================================================================


class TestSummonSpellParsing:
    """Tests for parsing summon/animate spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_animate_dead(self, resolver):
        """Parse Animate Dead spell."""
        spell = create_spell(
            spell_id="animate_dead",
            name="Animate Dead",
            magic_type=MagicType.ARCANE,
            level=5,
            description="Animate the dead. Raises up to 1 HD of undead per caster level.",
            duration="Permanent",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        summon_effects = [e for e in parsed.effects if e.is_summon_effect]
        assert len(summon_effects) >= 1

        effect = summon_effects[0]
        assert effect.summon_type == "undead"
        assert effect.summoner_controls is True

    def test_parse_conjure_animals(self, resolver):
        """Parse Conjure Animals spell."""
        spell = create_spell(
            spell_id="conjure_animals",
            name="Conjure Animals",
            magic_type=MagicType.DIVINE,
            level=4,
            description="Summons 2d6 animals to fight for the caster.",
            duration="1 Turn per level",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        summon_effects = [e for e in parsed.effects if e.is_summon_effect]
        assert len(summon_effects) >= 1

        effect = summon_effects[0]
        assert effect.summon_type == "animal"
        assert effect.summoner_controls is True

    def test_parse_conjure_elemental(self, resolver):
        """Parse Conjure Elemental spell."""
        spell = create_spell(
            spell_id="conjure_elemental",
            name="Conjure Elemental",
            magic_type=MagicType.ARCANE,
            level=5,
            description="Summons an elemental of 16 HD to serve the caster.",
            duration="Until dismissed",
            range_="240'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        summon_effects = [e for e in parsed.effects if e.is_summon_effect]
        assert len(summon_effects) >= 1

        effect = summon_effects[0]
        assert effect.summon_type == "elemental"
        assert effect.summoner_controls is True

    def test_parse_raise_zombies(self, resolver):
        """Parse spell that raises zombies."""
        spell = create_spell(
            spell_id="raise_zombies",
            name="Raise Zombies",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Creates 1d4 zombies from fresh corpses.",
            duration="Permanent",
            range_="30'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        summon_effects = [e for e in parsed.effects if e.is_summon_effect]
        assert len(summon_effects) >= 1

        effect = summon_effects[0]
        assert effect.summon_type == "undead"

    def test_parse_animate_objects(self, resolver):
        """Parse Animate Objects spell."""
        spell = create_spell(
            spell_id="animate_objects",
            name="Animate Objects",
            magic_type=MagicType.ARCANE,
            level=5,
            description="Animates statues or objects to fight.",
            duration="1 Turn per level",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        summon_effects = [e for e in parsed.effects if e.is_summon_effect]
        assert len(summon_effects) >= 1

        effect = summon_effects[0]
        assert effect.summon_type == "construct"


# =============================================================================
# CURSE SPELL PARSING TESTS
# =============================================================================


class TestCurseSpellParsing:
    """Tests for parsing curse spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_curse(self, resolver):
        """Parse basic Curse spell."""
        spell = create_spell(
            spell_id="curse",
            name="Curse",
            magic_type=MagicType.DIVINE,
            level=3,
            description="Places a curse on the target. Save vs spell negates. The curse is permanent until removed.",
            duration="Permanent",
            range_="30'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        curse_effects = [e for e in parsed.effects if e.is_curse_effect]
        assert len(curse_effects) >= 1

        effect = curse_effects[0]
        assert effect.curse_type == "major"
        assert effect.curse_is_permanent is True
        assert effect.requires_remove_curse is True
        assert effect.save_type == "spell"

    def test_parse_bestow_curse(self, resolver):
        """Parse Bestow Curse spell."""
        spell = create_spell(
            spell_id="bestow_curse",
            name="Bestow Curse",
            magic_type=MagicType.ARCANE,
            level=4,
            description="Bestow curse upon the target, reducing their Strength by -4.",
            duration="Permanent",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        curse_effects = [e for e in parsed.effects if e.is_curse_effect]
        assert len(curse_effects) >= 1

        effect = curse_effects[0]
        assert effect.curse_type == "major"

    def test_parse_bane(self, resolver):
        """Parse Bane spell."""
        spell = create_spell(
            spell_id="bane",
            name="Bane",
            magic_type=MagicType.DIVINE,
            level=1,
            description="Inflicts a minor bane on enemies, causing ill luck.",
            duration="1 Turn",
            range_="50'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        curse_effects = [e for e in parsed.effects if e.is_curse_effect]
        assert len(curse_effects) >= 1

        effect = curse_effects[0]
        assert effect.curse_type == "minor"

    def test_parse_wasting_curse(self, resolver):
        """Parse wasting/withering curse."""
        spell = create_spell(
            spell_id="wasting_curse",
            name="Withering Touch",
            magic_type=MagicType.ARCANE,
            level=4,
            description="A wasting curse that drains the target's vitality.",
            duration="Permanent",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        curse_effects = [e for e in parsed.effects if e.is_curse_effect]
        assert len(curse_effects) >= 1

        effect = curse_effects[0]
        assert effect.curse_type == "wasting"


# =============================================================================
# CONTROLLER SUMMON TESTS
# =============================================================================


class TestControllerSummonMethods:
    """Tests for GlobalController summon methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add a location
        location = LocationState(
            location_id="test_room",
            name="Test Room",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="dungeon",
        )
        controller._locations["test_room"] = location

        # Add a wizard
        wizard = CharacterState(
            character_id="wizard",
            name="Test Wizard",
            character_class="Magician",
            level=7,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 17, "WIS": 12, "CHA": 11},
            hp_current=20,
            hp_max=25,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["wizard"] = wizard

        return controller

    def test_summon_creatures(self, controller):
        """Test summoning creatures."""
        result = controller.summon_creatures(
            caster_id="wizard",
            location_id="test_room",
            creature_type="animal",
            count=3,
            duration_turns=6,
        )

        assert result["success"] is True
        assert result["creature_type"] == "animal"
        assert result["count"] == 3
        assert len(result["summoned_creature_ids"]) == 3
        assert result["caster_controls"] is True

    def test_animate_dead(self, controller):
        """Test animating dead."""
        result = controller.animate_dead(
            caster_id="wizard",
            location_id="test_room",
            corpse_count=4,
        )

        assert result["success"] is True
        assert result["spell"] == "Animate Dead"
        assert result["corpses_animated"] == 4
        assert result["max_hd_controlled"] == 7  # 7th level wizard
        assert len(result["undead_ids"]) == 4
        assert result["permanent"] is True

    def test_dismiss_summoned(self, controller):
        """Test dismissing summoned creatures."""
        # First summon
        summon_result = controller.summon_creatures(
            caster_id="wizard",
            location_id="test_room",
            creature_type="elemental",
            count=1,
        )

        # Then dismiss
        dismiss_result = controller.dismiss_summoned(
            caster_id="wizard",
            creature_ids=summon_result["summoned_creature_ids"],
        )

        assert dismiss_result["success"] is True
        assert dismiss_result["dismissed_count"] == 1

    def test_summon_location_not_found(self, controller):
        """Test summoning at invalid location."""
        result = controller.summon_creatures(
            caster_id="wizard",
            location_id="nonexistent",
            creature_type="animal",
            count=1,
        )

        assert "error" in result

    def test_summon_caster_not_found(self, controller):
        """Test summoning with invalid caster."""
        result = controller.summon_creatures(
            caster_id="nonexistent",
            location_id="test_room",
            creature_type="animal",
            count=1,
        )

        assert "error" in result


# =============================================================================
# CONTROLLER CURSE TESTS
# =============================================================================


class TestControllerCurseMethods:
    """Tests for GlobalController curse methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add characters
        wizard = CharacterState(
            character_id="wizard",
            name="Test Wizard",
            character_class="Magician",
            level=5,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 17, "WIS": 12, "CHA": 11},
            hp_current=15,
            hp_max=18,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["wizard"] = wizard

        fighter = CharacterState(
            character_id="fighter",
            name="Test Fighter",
            character_class="Fighter",
            level=5,
            ability_scores={"STR": 17, "DEX": 12, "CON": 14, "INT": 10, "WIS": 11, "CHA": 13},
            hp_current=30,
            hp_max=35,
            armor_class=16,
            base_speed=40,
        )
        controller._characters["fighter"] = fighter

        return controller

    def test_apply_curse(self, controller):
        """Test applying a curse."""
        result = controller.apply_curse(
            caster_id="wizard",
            target_id="fighter",
            curse_type="major",
            is_permanent=True,
        )

        assert result["success"] is True
        assert result["curse_type"] == "major"
        assert result["requires_remove_curse"] is True

        # Verify condition was added
        fighter = controller._characters["fighter"]
        cursed_conditions = [c for c in fighter.conditions if c.condition_type == ConditionType.CURSED]
        assert len(cursed_conditions) == 1

    def test_apply_curse_with_stat_penalty(self, controller):
        """Test applying a curse with stat penalty."""
        result = controller.apply_curse(
            caster_id="wizard",
            target_id="fighter",
            curse_type="ability_drain",
            stat_affected="STR",
            modifier=-4,
            is_permanent=True,
        )

        assert result["success"] is True
        assert result["stat_affected"] == "STR"
        assert result["modifier"] == -4

        # Verify stat modifier was applied
        fighter = controller._characters["fighter"]
        assert fighter.get_stat_modifier_total("STR") == -4

    def test_remove_curse(self, controller):
        """Test removing a curse."""
        # First apply a curse
        controller.apply_curse(
            caster_id="wizard",
            target_id="fighter",
            curse_type="major",
        )

        # Then remove it
        result = controller.remove_curse_from_target(
            caster_id="wizard",
            target_id="fighter",
        )

        assert result["success"] is True
        assert result["curses_removed"] == 1

        # Verify condition was removed
        fighter = controller._characters["fighter"]
        cursed_conditions = [c for c in fighter.conditions if c.condition_type == ConditionType.CURSED]
        assert len(cursed_conditions) == 0

    def test_bestow_curse_stat_penalty(self, controller):
        """Test bestow curse with stat penalty."""
        result = controller.bestow_curse(
            caster_id="wizard",
            target_id="fighter",
            effect_choice="stat_penalty",
            stat="DEX",
        )

        assert result["success"] is True
        assert result["stat_affected"] == "DEX"
        assert result["modifier"] == -4

    def test_bestow_curse_attack_penalty(self, controller):
        """Test bestow curse with attack penalty."""
        result = controller.bestow_curse(
            caster_id="wizard",
            target_id="fighter",
            effect_choice="attack_penalty",
        )

        assert result["success"] is True
        assert result["stat_affected"] == "attack"
        assert result["modifier"] == -4

    def test_curse_target_not_found(self, controller):
        """Test cursing nonexistent target."""
        result = controller.apply_curse(
            caster_id="wizard",
            target_id="nonexistent",
        )

        assert "error" in result

    def test_remove_curse_no_curse(self, controller):
        """Test removing curse when none exists."""
        result = controller.remove_curse_from_target(
            caster_id="wizard",
            target_id="fighter",
        )

        assert result["success"] is False
        assert result["curses_removed"] == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestSummonCurseIntegration:
    """Integration tests for summon and curse systems."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add a location
        location = LocationState(
            location_id="crypt",
            name="Dark Crypt",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="dungeon",
        )
        controller._locations["crypt"] = location

        # Add a necromancer
        necromancer = CharacterState(
            character_id="necromancer",
            name="Dark Wizard",
            character_class="Magician",
            level=9,
            ability_scores={"STR": 8, "DEX": 12, "CON": 10, "INT": 18, "WIS": 14, "CHA": 8},
            hp_current=25,
            hp_max=30,
            armor_class=12,
            base_speed=40,
        )
        controller._characters["necromancer"] = necromancer

        # Add a hero
        hero = CharacterState(
            character_id="hero",
            name="Brave Knight",
            character_class="Fighter",
            level=7,
            ability_scores={"STR": 18, "DEX": 14, "CON": 16, "INT": 10, "WIS": 12, "CHA": 15},
            hp_current=50,
            hp_max=55,
            armor_class=18,
            base_speed=40,
        )
        controller._characters["hero"] = hero

        return controller

    def test_necromancer_workflow(self, controller):
        """Test complete necromancer summoning workflow."""
        # Animate some undead
        animate_result = controller.animate_dead(
            caster_id="necromancer",
            location_id="crypt",
            corpse_count=3,
        )
        assert animate_result["success"] is True
        assert animate_result["max_hd_controlled"] == 9

        # Curse the hero
        curse_result = controller.apply_curse(
            caster_id="necromancer",
            target_id="hero",
            curse_type="ability_drain",
            stat_affected="STR",
            modifier=-4,
        )
        assert curse_result["success"] is True

        # Verify hero is cursed and weakened
        hero = controller._characters["hero"]
        assert any(c.condition_type == ConditionType.CURSED for c in hero.conditions)
        assert hero.get_stat_modifier_total("STR") == -4

    def test_curse_and_remove_workflow(self, controller):
        """Test curse application and removal workflow."""
        # Curse the hero
        curse_result = controller.apply_curse(
            caster_id="necromancer",
            target_id="hero",
            curse_type="major",
        )
        assert curse_result["success"] is True

        # Hero is cursed
        hero = controller._characters["hero"]
        assert any(c.condition_type == ConditionType.CURSED for c in hero.conditions)

        # Remove the curse (by a cleric, simulated here)
        remove_result = controller.remove_curse_from_target(
            caster_id="necromancer",  # In reality, would be a different caster
            target_id="hero",
        )
        assert remove_result["success"] is True
        assert remove_result["curses_removed"] == 1

        # Hero is no longer cursed
        assert not any(c.condition_type == ConditionType.CURSED for c in hero.conditions)
