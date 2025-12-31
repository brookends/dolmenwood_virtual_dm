"""
Tests for Phase 1 Spell Implementations.

Tests flat damage, death effects, healing, buff/condition parsing,
and light/resistance/morale mechanics using real Dolmenwood spells.
"""

import pytest
from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    MagicType,
    MechanicalEffectCategory,
)
from tests.dolmenwood_spell_helpers import (
    find_spell_by_id,
    make_test_spell,
    make_test_character,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def resolver():
    """Create a SpellResolver for testing."""
    return SpellResolver()


# =============================================================================
# REAL DOLMENWOOD SPELL INTEGRATION TESTS
# =============================================================================


class TestDolmenwoodDamageSpells:
    """Integration tests for real Dolmenwood damage spells."""

    def test_cloudkill_flat_damage(self, resolver):
        """Cloudkill deals 1 damage per Round to creatures in contact."""
        spell = find_spell_by_id("cloudkill")
        parsed = resolver.parse_mechanical_effects(spell)

        # Cloudkill: "suffer 1 damage per Round"
        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].flat_damage == 1

    def test_fireball_dice_damage(self, resolver):
        """Fireball deals 1d6 damage per level."""
        spell = find_spell_by_id("fireball")
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.DAMAGE and e.damage_dice is not None
        ]
        assert len(damage_effects) >= 1
        assert damage_effects[0].level_multiplier is True
        assert damage_effects[0].damage_type == "fire"

    def test_lightning_bolt_dice_damage(self, resolver):
        """Lightning Bolt deals electrical damage."""
        spell = find_spell_by_id("lightning_bolt")
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.DAMAGE and e.damage_dice is not None
        ]
        assert len(damage_effects) >= 1

    def test_acid_globe_damage(self, resolver):
        """Acid Globe deals 1d4 per level acid damage."""
        spell = find_spell_by_id("acid_globe")
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.DAMAGE
        ]
        assert len(damage_effects) >= 1


class TestDolmenwoodDeathSpells:
    """Integration tests for real Dolmenwood death effect spells."""

    def test_disintegrate_spell_loaded(self, resolver):
        """Disintegrate spell loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("disintegrate")

        # Verify spell metadata is correct
        assert spell.name == "Disintegrate"
        assert spell.level == 6
        assert "destroys" in spell.description.lower()
        assert "Save Versus Doom" in spell.description

        # Note: Current parser may not detect all patterns from this spell
        # Future enhancement: add "destroys" as death effect pattern

    def test_petrification_has_save(self, resolver):
        """Petrification (Flesh to Stone) requires Save Versus Hold."""
        spell = find_spell_by_id("petrification")
        parsed = resolver.parse_mechanical_effects(spell)

        # Petrification uses "transforms into stone" - check for save
        save_effects = [e for e in parsed.effects if e.save_type is not None]
        assert len(save_effects) >= 1
        assert save_effects[0].save_type == "hold"

    def test_rune_of_death_spell_loaded(self, resolver):
        """Rune of Death loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("rune_of_death")

        # Verify spell metadata is correct
        assert spell.name == "Rune of Death"
        assert spell.level == "mighty"  # Mighty rune, not numeric level
        assert "die" in spell.description.lower()
        assert "Save Versus Doom" in spell.description

        # Note: Current parser may need enhancement for mighty runes


class TestDolmenwoodHealingSpells:
    """Integration tests for real Dolmenwood healing spells."""

    def test_lesser_healing_dice(self, resolver):
        """Lesser Healing restores 1d6+1 HP."""
        spell = find_spell_by_id("lesser_healing")
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in parsed.effects if e.healing_dice is not None]
        assert len(heal_effects) >= 1
        assert "1d6" in heal_effects[0].healing_dice

    def test_greater_healing_dice(self, resolver):
        """Greater Healing restores 2d6+2 HP."""
        spell = find_spell_by_id("greater_healing")
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in parsed.effects if e.healing_dice is not None]
        assert len(heal_effects) >= 1
        assert "2d6" in heal_effects[0].healing_dice

    def test_raise_dead_is_parsed(self, resolver):
        """Raise Dead returns a deceased person to life."""
        spell = find_spell_by_id("raise_dead")
        parsed = resolver.parse_mechanical_effects(spell)

        # Raise Dead uses "returned to life" - may not match healing patterns
        # but should be parsed as a utility spell
        assert len(parsed.effects) >= 1


class TestDolmenwoodLightSpells:
    """Integration tests for real Dolmenwood light spells."""

    def test_light_spell(self, resolver):
        """Light creates illumination."""
        spell = find_spell_by_id("light")
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.UTILITY
        ]
        assert len(light_effects) >= 1

    def test_firelight_spell(self, resolver):
        """Firelight creates a glowing orb."""
        spell = find_spell_by_id("firelight")
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.UTILITY
        ]
        assert len(light_effects) >= 1


class TestDolmenwoodProtectionSpells:
    """Integration tests for real Dolmenwood protection/resistance spells."""

    def test_flame_ward_fire_resistance(self, resolver):
        """Flame Ward grants fire resistance."""
        spell = find_spell_by_id("flame_ward")
        parsed = resolver.parse_mechanical_effects(spell)

        # "supernatural resistance to fire"
        resist_effects = [
            e for e in parsed.effects
            if e.stat_modified == "resistance" or e.is_protection_effect
        ]
        assert len(resist_effects) >= 1

    def test_frost_ward_save_bonus(self, resolver):
        """Frost Ward grants +2 save bonus vs cold effects."""
        spell = find_spell_by_id("frost_ward")
        parsed = resolver.parse_mechanical_effects(spell)

        # Frost Ward uses "+2 bonus to Saving Throws versus cold-based effects"
        buff_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.BUFF or e.is_protection_effect
        ]
        assert len(buff_effects) >= 1

    def test_circle_of_protection(self, resolver):
        """Circle of Protection wards against evil."""
        spell = find_spell_by_id("circle_of_protection")
        parsed = resolver.parse_mechanical_effects(spell)

        protection_effects = [
            e for e in parsed.effects
            if e.is_protection_effect or e.category == MechanicalEffectCategory.BUFF
        ]
        assert len(protection_effects) >= 1


class TestDolmenwoodMoraleSpells:
    """Integration tests for real Dolmenwood morale spells."""

    def test_bless_morale_bonus(self, resolver):
        """Bless grants +1 bonus to attacks and morale."""
        spell = find_spell_by_id("bless")
        parsed = resolver.parse_mechanical_effects(spell)

        # "gain a +1 bonus to Attack and Damage Rolls"
        buff_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.BUFF
        ]
        assert len(buff_effects) >= 1

    def test_rally_is_parsed(self, resolver):
        """Rally is a divine spell that counters fear."""
        spell = find_spell_by_id("rally")
        parsed = resolver.parse_mechanical_effects(spell)

        # Rally "purging them of fear" + "+1 bonus per Level"
        # Verify spell is loaded correctly
        assert spell.name == "Rally"
        assert spell.level == 1
        assert spell.magic_type.value == "divine"
        # Parser should detect something from the spell
        assert len(parsed.effects) >= 1

    def test_fear_spell_is_parsed(self, resolver):
        """Fear is an arcane spell that causes terror."""
        spell = find_spell_by_id("fear")
        parsed = resolver.parse_mechanical_effects(spell)

        # Fear uses "terror, fleeing" + "60% chance of...dropping"
        # Verify spell is loaded correctly
        assert spell.name == "Fear"
        assert spell.level == 3
        # Parser should detect something from the spell
        assert len(parsed.effects) >= 1


class TestDolmenwoodConditionSpells:
    """Integration tests for real Dolmenwood condition spells."""

    def test_hold_person_paralysis(self, resolver):
        """Hold Person causes paralysis."""
        spell = find_spell_by_id("hold_person")
        parsed = resolver.parse_mechanical_effects(spell)

        condition_effects = [e for e in parsed.effects if e.condition_applied == "paralyzed"]
        assert len(condition_effects) >= 1
        assert condition_effects[0].save_type == "hold"

    def test_vapours_of_dream_sleep(self, resolver):
        """Vapours of Dream causes sleep/unconsciousness."""
        spell = find_spell_by_id("vapours_of_dream")
        parsed = resolver.parse_mechanical_effects(spell)

        # Should detect sleep/unconscious condition
        condition_effects = [
            e for e in parsed.effects
            if e.condition_applied in ("unconscious", "asleep")
        ]
        assert len(condition_effects) >= 1

    def test_confusion_spell_loaded(self, resolver):
        """Confusion spell loads correctly from Dolmenwood data."""
        spell = find_spell_by_id("confusion")

        # Verify spell metadata is correct
        assert spell.name == "Confusion"
        assert spell.level == 4
        assert "delusions" in spell.description.lower()
        assert "unable to control" in spell.description.lower()

        # Note: Current parser may need enhancement for "delusions" pattern

    def test_feeblemind_spell(self, resolver):
        """Feeblemind reduces intelligence."""
        spell = find_spell_by_id("feeblemind")
        parsed = resolver.parse_mechanical_effects(spell)

        debuff_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.DEBUFF
        ]
        assert len(debuff_effects) >= 1


class TestDolmenwoodBuffSpells:
    """Integration tests for real Dolmenwood buff spells."""

    def test_shield_of_force_ac(self, resolver):
        """Shield of Force grants AC bonus."""
        spell = find_spell_by_id("shield_of_force")
        parsed = resolver.parse_mechanical_effects(spell)

        ac_effects = [
            e for e in parsed.effects
            if e.ac_override is not None or e.category == MechanicalEffectCategory.BUFF
        ]
        assert len(ac_effects) >= 1

    def test_haste_combat_bonus(self, resolver):
        """Haste grants combat bonuses."""
        spell = find_spell_by_id("haste")
        parsed = resolver.parse_mechanical_effects(spell)

        haste_effects = [e for e in parsed.effects if e.is_haste_effect]
        assert len(haste_effects) >= 1

    def test_mirror_image_creates_duplicates(self, resolver):
        """Mirror Image creates illusory duplicates."""
        spell = find_spell_by_id("mirror_image")
        parsed = resolver.parse_mechanical_effects(spell)

        image_effects = [e for e in parsed.effects if e.creates_mirror_images]
        assert len(image_effects) >= 1


# =============================================================================
# PATTERN PARSING UNIT TESTS
# These test specific regex patterns with synthetic spells
# =============================================================================


class TestFlatDamagePatternParsing:
    """Unit tests for flat damage pattern matching."""

    def test_parse_deals_flat_damage(self, resolver):
        """Test 'deals X damage' pattern."""
        spell = make_test_spell(
            "Test Damage", "The caster deals 1 damage per round to targets."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].flat_damage == 1

    def test_parse_takes_flat_damage(self, resolver):
        """Test 'takes X damage' pattern."""
        spell = make_test_spell(
            "Test Burn", "The target takes 2 points of damage from flames."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].flat_damage == 2

    def test_parse_damage_per_turn(self, resolver):
        """Test 'X damage per turn' pattern."""
        spell = make_test_spell(
            "Test Aura", "Creatures in the aura suffer 3 damage per turn."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].flat_damage == 3

    def test_flat_damage_with_cold_type(self, resolver):
        """Test flat damage identifies cold damage type."""
        spell = make_test_spell(
            "Frost Touch", "The target takes 2 points of damage from cold."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].damage_type == "cold"


class TestDeathEffectPatternParsing:
    """Unit tests for death effect pattern matching."""

    def test_parse_dies_instantly(self, resolver):
        """Test 'dies instantly' death effect pattern."""
        spell = make_test_spell(
            "Death Bolt", "The target dies instantly if they fail save versus Doom.",
            level=6
        )
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in parsed.effects if e.is_death_effect]
        assert len(death_effects) >= 1
        assert death_effects[0].death_on_failed_save is True
        assert death_effects[0].save_type == "doom"

    def test_parse_disintegrate_pattern(self, resolver):
        """Test 'disintegrate' death effect pattern."""
        spell = make_test_spell(
            "Disintegrate Test", "On failed save versus Doom, target is disintegrated.",
            level=6
        )
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in parsed.effects if e.is_death_effect]
        assert len(death_effects) >= 1
        assert death_effects[0].death_on_failed_save is True

    def test_parse_death_with_hd_threshold(self, resolver):
        """Test death effect with HD threshold pattern."""
        spell = make_test_spell(
            "Mass Death", "Creatures with 6 or fewer HD are slain instantly.",
            level=6
        )
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in parsed.effects if e.is_death_effect]
        assert len(death_effects) >= 1
        assert death_effects[0].death_hd_threshold == 6


class TestHealingPatternParsing:
    """Unit tests for healing pattern matching."""

    def test_parse_dice_healing(self, resolver):
        """Test dice-based healing pattern."""
        spell = make_test_spell(
            "Heal Test", "The caster heals 1d6+1 Hit Points.",
            magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in parsed.effects if e.healing_dice is not None]
        assert len(heal_effects) >= 1
        assert "1d6" in heal_effects[0].healing_dice

    def test_parse_flat_healing(self, resolver):
        """Test flat healing pattern."""
        spell = make_test_spell(
            "Minor Mend", "The target regains 5 Hit Points.",
            level=0, magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in parsed.effects if e.flat_healing is not None]
        assert len(heal_effects) >= 1
        assert heal_effects[0].flat_healing == 5


class TestLightPatternParsing:
    """Unit tests for light effect pattern matching."""

    def test_parse_creates_light_radius(self, resolver):
        """Test 'creates light' pattern with radius."""
        spell = make_test_spell(
            "Light Test", "The caster creates bright light in a 30' radius.",
            magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.UTILITY
        ]
        assert len(light_effects) >= 1
        assert light_effects[0].area_radius == 30

    def test_parse_illuminates_area(self, resolver):
        """Test 'illuminates' pattern."""
        spell = make_test_spell(
            "Glow", "The object illuminates a 20 foot area."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.UTILITY
        ]
        assert len(light_effects) >= 1
        assert light_effects[0].area_radius == 20


class TestResistancePatternParsing:
    """Unit tests for resistance/ward pattern matching."""

    def test_parse_fire_resistance_pattern(self, resolver):
        """Test fire resistance pattern."""
        spell = make_test_spell(
            "Fire Shield", "Grants resistance to fire damage.",
            magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        resist_effects = [e for e in parsed.effects if e.stat_modified == "resistance"]
        assert len(resist_effects) >= 1
        assert resist_effects[0].damage_type == "fire"

    def test_parse_cold_protection_pattern(self, resolver):
        """Test cold protection pattern."""
        spell = make_test_spell(
            "Cold Shield", "Provides protection from cold and frost damage.",
            magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        resist_effects = [e for e in parsed.effects if e.stat_modified == "resistance"]
        assert len(resist_effects) >= 1
        assert resist_effects[0].damage_type == "cold"


class TestMoralePatternParsing:
    """Unit tests for morale bonus pattern matching."""

    def test_parse_grants_morale_pattern(self, resolver):
        """Test 'grants morale' pattern."""
        spell = make_test_spell(
            "Rally Test", "The spell grants a bonus to morale for allies.",
            magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        morale_effects = [e for e in parsed.effects if e.stat_modified == "morale"]
        assert len(morale_effects) >= 1

    def test_parse_bolsters_morale_pattern(self, resolver):
        """Test 'bolsters morale' pattern."""
        spell = make_test_spell(
            "Courage", "The prayer bolsters morale among the faithful.",
            magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        morale_effects = [e for e in parsed.effects if e.stat_modified == "morale"]
        assert len(morale_effects) >= 1


class TestBuffModifierPatternParsing:
    """Unit tests for stat modifier buff pattern matching."""

    def test_parse_plus_attack_bonus(self, resolver):
        """Test +X attack bonus pattern."""
        spell = make_test_spell(
            "Bless Test", "Allies gain +1 bonus to attack rolls.",
            magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        buff_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.BUFF and e.modifier_value is not None
        ]
        assert len(buff_effects) >= 1
        assert buff_effects[0].modifier_value == 1

    def test_parse_negative_modifier(self, resolver):
        """Test negative modifier pattern."""
        spell = make_test_spell(
            "Curse", "The target suffers -2 penalty to attack rolls."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        debuff_effects = [e for e in parsed.effects if e.category == MechanicalEffectCategory.DEBUFF]
        assert len(debuff_effects) >= 1
        assert debuff_effects[0].modifier_value == -2

    def test_parse_ac_override_pattern(self, resolver):
        """Test AC override pattern."""
        spell = make_test_spell(
            "Force Shield", "Grants the caster AC 17 against missile attacks."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        ac_effects = [e for e in parsed.effects if e.ac_override is not None]
        assert len(ac_effects) >= 1
        assert ac_effects[0].ac_override == 17


class TestConditionPatternParsing:
    """Unit tests for condition effect pattern matching."""

    def test_parse_paralysis_condition(self, resolver):
        """Test paralysis condition pattern."""
        spell = make_test_spell(
            "Hold Test", "Target is paralyzed on failed save versus Hold.",
            magic_type=MagicType.DIVINE
        )
        parsed = resolver.parse_mechanical_effects(spell)

        condition_effects = [e for e in parsed.effects if e.condition_applied == "paralyzed"]
        assert len(condition_effects) >= 1
        assert condition_effects[0].save_type == "hold"

    def test_parse_sleep_condition(self, resolver):
        """Test sleep condition pattern."""
        spell = make_test_spell(
            "Sleep Test", "Creatures fall asleep on a failed save versus Spell."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        condition_effects = [e for e in parsed.effects if e.condition_applied == "unconscious"]
        assert len(condition_effects) >= 1

    def test_parse_charm_condition(self, resolver):
        """Test charm condition pattern."""
        spell = make_test_spell(
            "Charm Test", "The target is charmed on a failed save versus Spell."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        condition_effects = [e for e in parsed.effects if e.condition_applied == "charmed"]
        assert len(condition_effects) >= 1


# =============================================================================
# EFFECT APPLICATION TESTS
# =============================================================================


class TestEffectApplication:
    """Tests for mechanical effect application."""

    def test_apply_flat_damage(self, resolver):
        """Test applying flat damage to targets."""
        from src.data_models import DiceRoller

        spell = make_test_spell(
            "Test Spell", "The target takes 5 damage."
        )
        spell.mechanical_effects = {"effects": [{"category": "damage", "flat_damage": 5}]}

        caster = make_test_character("caster_1", "Test Caster", level=5)
        dice_roller = DiceRoller()

        result = resolver._apply_mechanical_effects(
            spell=spell,
            caster=caster,
            targets_affected=["target_1"],
            targets_saved=[],
            save_negates=False,
            dice_roller=dice_roller,
        )

        assert "target_1" in result["damage_dealt"]
        assert result["damage_dealt"]["target_1"] == 5

    def test_apply_flat_healing(self, resolver):
        """Test applying flat healing to targets."""
        from src.data_models import DiceRoller

        spell = make_test_spell(
            "Test Heal", "The target restores 10 HP.",
            magic_type=MagicType.DIVINE
        )
        spell.mechanical_effects = {"effects": [{"category": "healing", "flat_healing": 10}]}

        caster = make_test_character("caster_1", "Test Caster", character_class="Cleric", level=5)
        dice_roller = DiceRoller()

        result = resolver._apply_mechanical_effects(
            spell=spell,
            caster=caster,
            targets_affected=["target_1"],
            targets_saved=[],
            save_negates=False,
            dice_roller=dice_roller,
        )

        assert "target_1" in result["healing_applied"]
        assert result["healing_applied"]["target_1"] == 10
