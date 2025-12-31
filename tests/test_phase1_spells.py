"""
Tests for Phase 1 Spell Implementations.

Tests flat damage, death effects, healing, buff/condition parsing,
and light/resistance/morale mechanics.
"""

import pytest
from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    MagicType,
    MechanicalEffectCategory,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def resolver():
    """Create a SpellResolver for testing."""
    return SpellResolver()


def make_spell(
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
# FLAT DAMAGE PARSING TESTS
# =============================================================================


class TestFlatDamageParsing:
    """Tests for flat (non-dice) damage parsing."""

    def test_parse_deals_flat_damage(self, resolver):
        """Test 'deals X damage' pattern."""
        spell = make_spell(
            "ignite", "Ignite", 1, MagicType.ARCANE,
            "The caster deals 1 damage per round to flammable targets."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].flat_damage == 1

    def test_parse_takes_flat_damage(self, resolver):
        """Test 'takes X damage' pattern."""
        spell = make_spell(
            "minor_burn", "Minor Burn", 1, MagicType.ARCANE,
            "The target takes 2 points of damage from the flames."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].flat_damage == 2

    def test_parse_damage_per_turn(self, resolver):
        """Test 'X damage per turn' pattern."""
        spell = make_spell(
            "burning_aura", "Burning Aura", 2, MagicType.ARCANE,
            "Creatures in the aura suffer 3 damage per turn."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].flat_damage == 3

    def test_flat_damage_with_type(self, resolver):
        """Test flat damage identifies damage type."""
        spell = make_spell(
            "frost_touch", "Frost Touch", 1, MagicType.ARCANE,
            "The target takes 2 points of damage from cold on contact."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in parsed.effects if e.flat_damage is not None]
        assert len(damage_effects) >= 1
        assert damage_effects[0].damage_type == "cold"


# =============================================================================
# DEATH EFFECT PARSING TESTS
# =============================================================================


class TestDeathEffectParsing:
    """Tests for death effect parsing."""

    def test_parse_dies_instantly(self, resolver):
        """Test 'dies instantly' death effect."""
        spell = make_spell(
            "death_bolt", "Death Bolt", 6, MagicType.ARCANE,
            "The target dies instantly if they fail their save versus Doom."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in parsed.effects if e.is_death_effect]
        assert len(death_effects) >= 1
        assert death_effects[0].death_on_failed_save is True
        assert death_effects[0].save_type == "doom"

    def test_parse_disintegrate(self, resolver):
        """Test 'disintegrate' death effect."""
        spell = make_spell(
            "disintegrate", "Disintegrate", 6, MagicType.ARCANE,
            "On a failed save versus Doom, the target is disintegrated."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in parsed.effects if e.is_death_effect]
        assert len(death_effects) >= 1
        assert death_effects[0].death_on_failed_save is True

    def test_parse_death_with_hd_threshold(self, resolver):
        """Test death effect with HD threshold."""
        spell = make_spell(
            "word_of_doom", "Word of Doom", 6, MagicType.ARCANE,
            "Creatures with 6 or fewer HD are slain instantly on a failed save versus Spell."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in parsed.effects if e.is_death_effect]
        assert len(death_effects) >= 1
        assert death_effects[0].death_hd_threshold == 6

    def test_parse_turn_to_stone(self, resolver):
        """Test 'turn to stone' petrification effect."""
        spell = make_spell(
            "petrify", "Petrify", 6, MagicType.ARCANE,
            "The target turns to stone on a failed save versus Doom."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in parsed.effects if e.is_death_effect]
        assert len(death_effects) >= 1


# =============================================================================
# HEALING PARSING TESTS
# =============================================================================


class TestHealingParsing:
    """Tests for healing effect parsing."""

    def test_parse_dice_healing(self, resolver):
        """Test dice-based healing pattern."""
        spell = make_spell(
            "lesser_healing", "Lesser Healing", 1, MagicType.DIVINE,
            "The caster heals 1d6+1 Hit Points."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in parsed.effects if e.healing_dice is not None]
        assert len(heal_effects) >= 1
        assert "1d6" in heal_effects[0].healing_dice

    def test_parse_flat_healing(self, resolver):
        """Test flat healing pattern."""
        spell = make_spell(
            "minor_mend", "Minor Mend", 0, MagicType.DIVINE,
            "The target regains 5 Hit Points."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in parsed.effects if e.flat_healing is not None]
        assert len(heal_effects) >= 1
        assert heal_effects[0].flat_healing == 5

    def test_parse_restores_hp(self, resolver):
        """Test 'restores' healing pattern."""
        spell = make_spell(
            "restoration", "Restoration", 2, MagicType.DIVINE,
            "This spell restores 2d6 HP to the target."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in parsed.effects if e.healing_dice is not None]
        assert len(heal_effects) >= 1


# =============================================================================
# LIGHT EFFECT PARSING TESTS
# =============================================================================


class TestLightParsing:
    """Tests for light effect parsing."""

    def test_parse_creates_light(self, resolver):
        """Test 'creates light' pattern."""
        spell = make_spell(
            "light", "Light", 1, MagicType.DIVINE,
            "The caster creates bright light in a 30' radius."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.UTILITY
            and "light" in e.description.lower()
        ]
        assert len(light_effects) >= 1
        assert light_effects[0].area_radius == 30

    def test_parse_illuminates(self, resolver):
        """Test 'illuminates' pattern."""
        spell = make_spell(
            "glow", "Glow", 1, MagicType.ARCANE,
            "The object illuminates a 20 foot area."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.UTILITY
        ]
        assert len(light_effects) >= 1
        assert light_effects[0].area_radius == 20

    def test_parse_sheds_light(self, resolver):
        """Test 'sheds light' pattern."""
        spell = make_spell(
            "torch_spell", "Torch", 1, MagicType.ARCANE,
            "The spell sheds light within a 40' radius."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.UTILITY
        ]
        assert len(light_effects) >= 1


# =============================================================================
# RESISTANCE/WARD PARSING TESTS
# =============================================================================


class TestResistanceParsing:
    """Tests for resistance/ward effect parsing."""

    def test_parse_fire_resistance(self, resolver):
        """Test fire resistance pattern."""
        spell = make_spell(
            "flame_ward", "Flame Ward", 2, MagicType.DIVINE,
            "Grants resistance to fire damage."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        resist_effects = [e for e in parsed.effects if e.stat_modified == "resistance"]
        assert len(resist_effects) >= 1
        assert resist_effects[0].damage_type == "fire"

    def test_parse_cold_protection(self, resolver):
        """Test cold protection pattern."""
        spell = make_spell(
            "frost_ward", "Frost Ward", 1, MagicType.DIVINE,
            "Provides protection from cold and frost damage."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        resist_effects = [e for e in parsed.effects if e.stat_modified == "resistance"]
        assert len(resist_effects) >= 1
        assert resist_effects[0].damage_type == "cold"

    def test_parse_poison_immunity(self, resolver):
        """Test poison immunity pattern."""
        spell = make_spell(
            "neutralize_poison", "Neutralize Poison", 4, MagicType.DIVINE,
            "The target becomes immune to poison."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        resist_effects = [e for e in parsed.effects if e.stat_modified == "resistance"]
        assert len(resist_effects) >= 1
        assert resist_effects[0].damage_type == "poison"


# =============================================================================
# MORALE PARSING TESTS
# =============================================================================


class TestMoraleParsing:
    """Tests for morale bonus parsing."""

    def test_parse_grants_morale(self, resolver):
        """Test 'grants morale' pattern."""
        spell = make_spell(
            "rally", "Rally", 1, MagicType.DIVINE,
            "The spell grants a bonus to morale for allies."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        morale_effects = [e for e in parsed.effects if e.stat_modified == "morale"]
        assert len(morale_effects) >= 1
        assert morale_effects[0].modifier_value == 1

    def test_parse_morale_bonus(self, resolver):
        """Test 'morale bonus' pattern."""
        spell = make_spell(
            "inspire", "Inspire", 2, MagicType.DIVINE,
            "Allies receive a morale boost in combat."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        morale_effects = [e for e in parsed.effects if e.stat_modified == "morale"]
        assert len(morale_effects) >= 1

    def test_parse_bolsters_morale(self, resolver):
        """Test 'bolsters morale' pattern."""
        spell = make_spell(
            "courage", "Courage", 2, MagicType.DIVINE,
            "The prayer bolsters morale among the faithful."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        morale_effects = [e for e in parsed.effects if e.stat_modified == "morale"]
        assert len(morale_effects) >= 1


# =============================================================================
# BUFF MODIFIER PARSING TESTS
# =============================================================================


class TestBuffModifierParsing:
    """Tests for stat modifier buff parsing."""

    def test_parse_plus_attack_bonus(self, resolver):
        """Test +X attack bonus pattern."""
        spell = make_spell(
            "bless", "Bless", 2, MagicType.DIVINE,
            "Allies gain +1 bonus to attack rolls and saving throws."
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
        spell = make_spell(
            "curse", "Curse", 3, MagicType.ARCANE,
            "The target suffers -2 penalty to attack rolls."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        debuff_effects = [e for e in parsed.effects if e.category == MechanicalEffectCategory.DEBUFF]
        assert len(debuff_effects) >= 1
        assert debuff_effects[0].modifier_value == -2

    def test_parse_ac_override(self, resolver):
        """Test AC override pattern."""
        spell = make_spell(
            "shield_of_force", "Shield of Force", 1, MagicType.ARCANE,
            "Grants the caster AC 17 against missile attacks."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        ac_effects = [e for e in parsed.effects if e.ac_override is not None]
        assert len(ac_effects) >= 1
        assert ac_effects[0].ac_override == 17
        assert ac_effects[0].condition_context == "vs_missiles"


# =============================================================================
# CONDITION PARSING TESTS
# =============================================================================


class TestConditionParsing:
    """Tests for condition effect parsing."""

    def test_parse_paralysis(self, resolver):
        """Test paralysis condition pattern."""
        spell = make_spell(
            "hold_person", "Hold Person", 2, MagicType.DIVINE,
            "The target is paralyzed on a failed save versus Hold."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        condition_effects = [e for e in parsed.effects if e.condition_applied == "paralyzed"]
        assert len(condition_effects) >= 1
        assert condition_effects[0].save_type == "hold"

    def test_parse_sleep(self, resolver):
        """Test sleep condition pattern."""
        spell = make_spell(
            "vapours_of_dream", "Vapours of Dream", 1, MagicType.ARCANE,
            "Creatures fall asleep on a failed save versus Spell."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        condition_effects = [e for e in parsed.effects if e.condition_applied == "unconscious"]
        assert len(condition_effects) >= 1

    def test_parse_charm(self, resolver):
        """Test charm condition pattern."""
        spell = make_spell(
            "charm_person", "Charm Person", 1, MagicType.ARCANE,
            "The target is charmed on a failed save versus Spell."
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
        from src.data_models import CharacterState, DiceRoller

        spell = make_spell(
            "test_spell", "Test Spell", 1, MagicType.ARCANE,
            "The target takes 5 damage.",
            mechanical_effects={"effects": [{"category": "damage", "flat_damage": 5}]}
        )

        caster = CharacterState(
            character_id="caster_1",
            name="Test Caster",
            character_class="Magic-User",
            level=5,
            ability_scores={"STR": 10, "DEX": 10, "CON": 10, "INT": 16, "WIS": 10, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=12,
            base_speed=40,
        )

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
        from src.data_models import CharacterState, DiceRoller

        spell = make_spell(
            "test_heal", "Test Heal", 1, MagicType.DIVINE,
            "The target restores 10 HP.",
            mechanical_effects={"effects": [{"category": "healing", "flat_healing": 10}]}
        )

        caster = CharacterState(
            character_id="caster_1",
            name="Test Caster",
            character_class="Cleric",
            level=5,
            ability_scores={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 16, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=14,
            base_speed=40,
        )

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


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestPhase1Integration:
    """Integration tests for Phase 1 spell mechanics."""

    def test_bless_spell_parsing(self, resolver):
        """Test full parsing of Bless spell."""
        spell = make_spell(
            "bless", "Bless", 2, MagicType.DIVINE,
            "The blessing grants allies +1 to attack rolls and saving throws for the duration."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        buff_effects = [e for e in parsed.effects if e.category == MechanicalEffectCategory.BUFF]
        assert len(buff_effects) >= 1

    def test_fireball_spell_parsing(self, resolver):
        """Test full parsing of Fireball spell."""
        spell = make_spell(
            "fireball", "Fireball", 3, MagicType.ARCANE,
            "A ball of fire explodes dealing 1d6 damage per level of the caster. Save versus Blast for half damage."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.DAMAGE and e.damage_dice is not None
        ]
        assert len(damage_effects) >= 1
        assert damage_effects[0].level_multiplier is True
        assert damage_effects[0].damage_type == "fire"

    def test_disintegrate_spell_parsing(self, resolver):
        """Test full parsing of Disintegrate spell."""
        spell = make_spell(
            "disintegrate", "Disintegrate", 6, MagicType.ARCANE,
            "The target is disintegrated on a failed save versus Doom. Nothing remains but dust."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in parsed.effects if e.is_death_effect]
        assert len(death_effects) >= 1
        assert death_effects[0].death_on_failed_save is True
        assert death_effects[0].save_type == "doom"

    def test_light_spell_parsing(self, resolver):
        """Test full parsing of Light spell."""
        spell = make_spell(
            "light", "Light", 1, MagicType.DIVINE,
            "The caster creates bright light within a 30' radius. The light lasts 1 Turn per Level."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [e for e in parsed.effects if e.category == MechanicalEffectCategory.UTILITY]
        assert len(light_effects) >= 1
        assert light_effects[0].area_radius == 30
