"""
Tests for Phase 2.5: Buff Enhancement Spells.

Tests immunity spells, vision enhancements, stat overrides, and dispel/removal spells.
Uses real Dolmenwood spells where available.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_models import (
    CharacterState,
    Condition,
    ConditionType,
    LocationState,
    LocationType,
    AreaEffect,
    AreaEffectType,
)
from src.narrative.spell_resolver import (
    MagicType,
    MechanicalEffect,
    MechanicalEffectCategory,
    SpellData,
    SpellResolver,
)
from tests.dolmenwood_spell_helpers import find_spell_by_id, make_test_spell


# =============================================================================
# REAL DOLMENWOOD SPELL INTEGRATION TESTS
# =============================================================================


class TestDolmenwoodBuffSpells:
    """Integration tests using real Dolmenwood buff spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_missile_ward_spell_loaded(self, resolver):
        """Missile Ward spell loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("missile_ward")

        assert spell.name == "Missile Ward"
        assert spell.level == 3
        # Verify spell is about missile immunity
        desc_lower = spell.description.lower()
        assert "missile" in desc_lower or "arrow" in desc_lower

    def test_water_breathing_immunity(self, resolver):
        """Water Breathing allows underwater breathing."""
        spell = find_spell_by_id("water_breathing")
        parsed = resolver.parse_mechanical_effects(spell)

        assert spell.name == "Water Breathing"
        immunity_effects = [e for e in parsed.effects if e.grants_immunity]
        assert len(immunity_effects) >= 1

    def test_air_sphere_spell_loaded(self, resolver):
        """Air Sphere spell loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("air_sphere")

        assert spell.name == "Air Sphere"
        assert spell.level == 5
        # Verify spell is about air/gas protection
        desc_lower = spell.description.lower()
        assert "air" in desc_lower or "gas" in desc_lower

    def test_dark_sight_spell_loaded(self, resolver):
        """Dark Sight spell loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("dark_sight")

        assert spell.name == "Dark Sight"
        assert spell.level == 3
        # Verify spell is about seeing in darkness
        desc_lower = spell.description.lower()
        assert "dark" in desc_lower or "light" in desc_lower

    def test_perceive_the_invisible_spell_loaded(self, resolver):
        """Perceive the Invisible loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("perceive_the_invisible")

        assert spell.name == "Perceive the Invisible"
        assert spell.level == 2
        # Verify spell is about seeing invisible
        desc_lower = spell.description.lower()
        assert "invisible" in desc_lower

    def test_dispel_magic_spell_loaded(self, resolver):
        """Dispel Magic spell loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("dispel_magic")

        assert spell.name == "Dispel Magic"
        assert spell.level == 3
        # Verify spell is about dispelling
        desc_lower = spell.description.lower()
        assert "dispel" in desc_lower or "end" in desc_lower or "cancel" in desc_lower

    def test_remove_curse_spell_loaded(self, resolver):
        """Remove Curse spell loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("remove_curse")

        assert spell.name == "Remove Curse"
        assert spell.level == 3
        # Verify spell is about curse removal
        assert "curse" in spell.description.lower()

    def test_remove_poison(self, resolver):
        """Remove Poison neutralizes toxins."""
        spell = find_spell_by_id("remove_poison")
        parsed = resolver.parse_mechanical_effects(spell)

        assert spell.name == "Remove Poison"
        removal_effects = [e for e in parsed.effects if e.removes_condition]
        assert len(removal_effects) >= 1

    def test_cure_affliction(self, resolver):
        """Cure Affliction removes diseases."""
        spell = find_spell_by_id("cure_affliction")
        parsed = resolver.parse_mechanical_effects(spell)

        assert spell.name == "Cure Affliction"
        removal_effects = [e for e in parsed.effects if e.removes_condition]
        assert len(removal_effects) >= 1

    def test_feeblemind_stat_override(self, resolver):
        """Feeblemind reduces intelligence to animal level."""
        spell = find_spell_by_id("feeblemind")
        parsed = resolver.parse_mechanical_effects(spell)

        assert spell.name == "Feeblemind"
        override_effects = [e for e in parsed.effects if e.is_stat_override]
        assert len(override_effects) >= 1
        assert override_effects[0].override_stat == "INT"


# =============================================================================
# PATTERN PARSING UNIT TESTS
# =============================================================================


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
    """Helper to create SpellData with required fields for pattern tests."""
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
# SPELL PARSING TESTS
# =============================================================================


class TestImmunitySpellParsing:
    """Tests for parsing immunity spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_missile_ward(self, resolver):
        """Parse Missile Ward spell."""
        spell = create_spell(
            spell_id="missile_ward",
            name="Missile Ward",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Target becomes immune to normal missiles. Arrows and bolts pass harmlessly through.",
            duration="6 Turns",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        immunity_effects = [e for e in parsed.effects if e.grants_immunity]
        assert len(immunity_effects) >= 1

        effect = immunity_effects[0]
        assert effect.immunity_type == "missiles"

    def test_parse_water_breathing(self, resolver):
        """Parse Water Breathing spell."""
        spell = create_spell(
            spell_id="water_breathing",
            name="Water Breathing",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Target can breathe underwater for the duration.",
            duration="1 day",
            range_="30'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        immunity_effects = [e for e in parsed.effects if e.grants_immunity]
        assert len(immunity_effects) >= 1

        effect = immunity_effects[0]
        assert effect.immunity_type == "drowning"

    def test_parse_air_sphere(self, resolver):
        """Parse Air Sphere spell."""
        spell = create_spell(
            spell_id="air_sphere",
            name="Air Sphere",
            magic_type=MagicType.ARCANE,
            level=5,
            description="Creates a sphere of fresh air. Target is immune to gas and gaseous attacks.",
            duration="1 Turn per level",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        immunity_effects = [e for e in parsed.effects if e.grants_immunity]
        assert len(immunity_effects) >= 1

        effect = immunity_effects[0]
        assert effect.immunity_type == "gas"


class TestVisionSpellParsing:
    """Tests for parsing vision enhancement spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_dark_sight(self, resolver):
        """Parse Dark Sight spell."""
        spell = create_spell(
            spell_id="dark_sight",
            name="Dark Sight",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Target gains darksight, allowing them to see in the dark.",
            duration="1 day",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        vision_effects = [e for e in parsed.effects if e.enhances_vision]
        assert len(vision_effects) >= 1

        effect = vision_effects[0]
        assert effect.vision_type == "darkvision"

    def test_parse_infravision(self, resolver):
        """Parse Infravision spell."""
        spell = create_spell(
            spell_id="infravision",
            name="Infravision",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Grants infravision to the target.",
            duration="1 day",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        vision_effects = [e for e in parsed.effects if e.enhances_vision]
        assert len(vision_effects) >= 1

        effect = vision_effects[0]
        assert effect.vision_type == "infravision"

    def test_parse_perceive_invisible(self, resolver):
        """Parse Perceive the Invisible spell."""
        spell = create_spell(
            spell_id="perceive_invisible",
            name="Perceive the Invisible",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Target can see invisible creatures and objects.",
            duration="6 Turns",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        vision_effects = [e for e in parsed.effects if e.enhances_vision]
        assert len(vision_effects) >= 1

        effect = vision_effects[0]
        assert effect.vision_type == "see_invisible"


class TestStatOverrideSpellParsing:
    """Tests for parsing stat override spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_feeblemind(self, resolver):
        """Parse Feeblemind spell."""
        spell = create_spell(
            spell_id="feeblemind",
            name="Feeblemind",
            magic_type=MagicType.ARCANE,
            level=5,
            description="Target's intelligence is reduced to that of an animal. Save vs spell negates.",
            duration="Permanent",
            range_="240'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        override_effects = [e for e in parsed.effects if e.is_stat_override]
        assert len(override_effects) >= 1

        effect = override_effects[0]
        assert effect.override_stat == "INT"
        assert effect.override_value == 3
        assert effect.save_type == "spell"


class TestDispelSpellParsing:
    """Tests for parsing dispel and removal spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_dispel_magic(self, resolver):
        """Parse Dispel Magic spell."""
        spell = create_spell(
            spell_id="dispel_magic",
            name="Dispel Magic",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Removes magical effects from a target. Ends enchantments and cancels spells.",
            duration="Instant",
            range_="120'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        dispel_effects = [e for e in parsed.effects if e.is_dispel_effect]
        assert len(dispel_effects) >= 1

        effect = dispel_effects[0]
        assert effect.dispel_target == "all"

    def test_parse_remove_curse(self, resolver):
        """Parse Remove Curse spell."""
        spell = create_spell(
            spell_id="remove_curse",
            name="Remove Curse",
            magic_type=MagicType.DIVINE,
            level=3,
            description="Lifts a curse from the target.",
            duration="Instant",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        dispel_effects = [e for e in parsed.effects if e.is_dispel_effect or e.removes_condition]
        assert len(dispel_effects) >= 1

        effect = dispel_effects[0]
        assert effect.condition_removed == "cursed"

    def test_parse_remove_poison(self, resolver):
        """Parse Neutralize Poison spell."""
        spell = create_spell(
            spell_id="neutralize_poison",
            name="Neutralize Poison",
            magic_type=MagicType.DIVINE,
            level=4,
            description="Cures poison in the target, neutralizing all toxins.",
            duration="Instant",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        removal_effects = [e for e in parsed.effects if e.removes_condition]
        assert len(removal_effects) >= 1

        effect = removal_effects[0]
        assert effect.condition_removed == "poisoned"

    def test_parse_cure_disease(self, resolver):
        """Parse Cure Affliction spell."""
        spell = create_spell(
            spell_id="cure_affliction",
            name="Cure Affliction",
            magic_type=MagicType.DIVINE,
            level=3,
            description="Removes all diseases and afflictions from the target.",
            duration="Instant",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        removal_effects = [e for e in parsed.effects if e.removes_condition]
        assert len(removal_effects) >= 1

        effect = removal_effects[0]
        assert effect.condition_removed == "diseased"


# =============================================================================
# GLOBAL CONTROLLER TESTS
# =============================================================================


class TestControllerImmunityMethods:
    """Tests for GlobalController immunity methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with a character."""
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

    def test_grant_immunity_missiles(self, controller):
        """Test granting missile immunity."""
        result = controller.grant_immunity(
            character_id="test_pc",
            immunity_type="missiles",
            duration_turns=6,
            source="Missile Ward",
        )

        assert result["success"] is True
        assert result["immunity_type"] == "missiles"
        assert result["duration_turns"] == 6

    def test_grant_immunity_drowning(self, controller):
        """Test granting drowning immunity."""
        result = controller.grant_immunity(
            character_id="test_pc",
            immunity_type="drowning",
            duration_turns=144,  # 1 day
            source="Water Breathing",
        )

        assert result["success"] is True
        assert result["immunity_type"] == "drowning"

    def test_grant_immunity_not_found(self, controller):
        """Test granting immunity to nonexistent character."""
        result = controller.grant_immunity(
            character_id="nonexistent",
            immunity_type="missiles",
            duration_turns=6,
        )

        assert result["success"] is False


class TestControllerVisionMethods:
    """Tests for GlobalController vision enhancement methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with a character."""
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

    def test_grant_darkvision(self, controller):
        """Test granting darkvision."""
        result = controller.grant_vision_enhancement(
            character_id="test_pc",
            vision_type="darkvision",
            duration_turns=144,
            range_feet=60,
            source="Dark Sight",
        )

        assert result["success"] is True
        assert result["vision_type"] == "darkvision"
        assert result["range_feet"] == 60

    def test_grant_see_invisible(self, controller):
        """Test granting see invisible."""
        result = controller.grant_vision_enhancement(
            character_id="test_pc",
            vision_type="see_invisible",
            duration_turns=6,
            source="Perceive the Invisible",
        )

        assert result["success"] is True
        assert result["vision_type"] == "see_invisible"

        # Check character state was updated
        character = controller.get_character("test_pc")
        assert character.can_see_invisible is True


class TestControllerStatOverrideMethods:
    """Tests for GlobalController stat override methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with a character."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        character = CharacterState(
            character_id="test_pc",
            name="Test PC",
            character_class="Magician",
            level=5,
            ability_scores={"STR": 8, "DEX": 12, "CON": 10, "INT": 17, "WIS": 11, "CHA": 10},
            hp_current=15,
            hp_max=18,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["test_pc"] = character
        return controller

    def test_apply_feeblemind(self, controller):
        """Test applying Feeblemind (INT override)."""
        result = controller.apply_stat_override(
            character_id="test_pc",
            stat="INT",
            value=3,
            duration_turns=999,  # Permanent-ish
            source="Feeblemind",
        )

        assert result["success"] is True
        assert result["stat"] == "INT"
        assert result["original_value"] == 17
        assert result["new_value"] == 3


class TestControllerDispelMethods:
    """Tests for GlobalController dispel methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with a character and location."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add character with some conditions
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
        # Add a magical condition
        character.conditions.append(
            Condition(
                condition_type=ConditionType.HASTED,
                source="Haste spell",
                source_spell_id="haste",
                duration_turns=3,
            )
        )
        character.mirror_image_count = 3
        controller._characters["test_pc"] = character

        # Add location with area effect
        location = LocationState(
            location_id="test_room",
            name="Test Room",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="dungeon",
        )
        location.area_effects.append(
            AreaEffect(
                effect_type=AreaEffectType.WEB,
                name="Web",
                location_id="test_room",
                source_spell_id="web",
            )
        )
        controller._locations["test_room"] = location

        return controller

    def test_dispel_magic_on_character(self, controller):
        """Test dispelling magic on a character."""
        result = controller.dispel_magic(
            target_id="test_pc",
            caster_level=10,
            target_type="character",
        )

        assert result["success"] is True
        assert result["target_type"] == "character"
        # Mirror images should be removed
        character = controller.get_character("test_pc")
        assert character.mirror_image_count == 0

    def test_dispel_magic_on_location(self, controller):
        """Test dispelling magic on a location."""
        result = controller.dispel_magic(
            target_id="test_room",
            caster_level=10,
            target_type="location",
        )

        assert result["success"] is True
        assert result["target_type"] == "location"
        assert result["total_dispelled"] >= 1

        # Web should be removed
        location = controller._locations["test_room"]
        assert len(location.area_effects) == 0


class TestControllerConditionRemoval:
    """Tests for GlobalController condition removal methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with a poisoned character."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        character = CharacterState(
            character_id="test_pc",
            name="Test PC",
            character_class="Fighter",
            level=5,
            ability_scores={"STR": 14, "DEX": 12, "CON": 13, "INT": 10, "WIS": 11, "CHA": 10},
            hp_current=20,
            hp_max=35,
            armor_class=14,
            base_speed=40,
        )
        # Add poisoned condition
        character.conditions.append(
            Condition(
                condition_type=ConditionType.POISONED,
                source="Giant Spider",
            )
        )
        # Add cursed condition
        character.conditions.append(
            Condition(
                condition_type=ConditionType.CURSED,
                source="Cursed Ring",
            )
        )
        controller._characters["test_pc"] = character
        return controller

    def test_remove_poison(self, controller):
        """Test removing poison condition."""
        character = controller.get_character("test_pc")
        assert character.has_condition(ConditionType.POISONED) is True

        result = controller.remove_condition("test_pc", "poisoned")

        assert result["success"] is True
        assert result["removed_count"] == 1
        assert character.has_condition(ConditionType.POISONED) is False

    def test_remove_curse(self, controller):
        """Test removing curse condition."""
        character = controller.get_character("test_pc")
        assert character.has_condition(ConditionType.CURSED) is True

        result = controller.remove_condition("test_pc", "cursed")

        assert result["success"] is True
        assert result["removed_count"] == 1
        assert character.has_condition(ConditionType.CURSED) is False

    def test_remove_nonexistent_condition(self, controller):
        """Test removing condition that doesn't exist."""
        result = controller.remove_condition("test_pc", "diseased")

        assert result["success"] is True
        assert result["removed_count"] == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestBuffSpellIntegration:
    """Integration tests for buff spell workflow."""

    @pytest.fixture
    def controller(self):
        """Create a controller with party."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

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

    def test_buff_and_dispel_workflow(self, controller):
        """Test applying buffs then dispelling them."""
        # Apply missile immunity to fighter
        immunity_result = controller.grant_immunity(
            character_id="fighter",
            immunity_type="missiles",
            duration_turns=6,
            source="Missile Ward",
        )
        assert immunity_result["success"] is True

        # Apply see invisible to wizard
        vision_result = controller.grant_vision_enhancement(
            character_id="wizard",
            vision_type="see_invisible",
            duration_turns=6,
            source="Perceive the Invisible",
        )
        assert vision_result["success"] is True

        wizard = controller.get_character("wizard")
        assert wizard.can_see_invisible is True

        # Dispel magic on wizard
        dispel_result = controller.dispel_magic(
            target_id="wizard",
            caster_level=10,
            target_type="character",
        )
        assert dispel_result["success"] is True

        # See invisible should be removed
        assert wizard.can_see_invisible is False

    def test_condition_removal_workflow(self, controller):
        """Test applying and removing conditions."""
        fighter = controller.get_character("fighter")

        # Poison the fighter
        fighter.conditions.append(
            Condition(
                condition_type=ConditionType.POISONED,
                source="Trap",
            )
        )
        assert fighter.has_condition(ConditionType.POISONED) is True

        # Remove the poison
        result = controller.remove_condition("fighter", "poisoned")
        assert result["success"] is True
        assert fighter.has_condition(ConditionType.POISONED) is False
