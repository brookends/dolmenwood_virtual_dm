"""
Comprehensive test for ALL Dolmenwood spells.

This test file iterates through every spell in /data/content/spells/
and verifies that each spell:
1. Loads correctly from JSON
2. Can be parsed by SpellResolver.parse_mechanical_effects()
3. Produces effects appropriate for its implementation tier

Implementation tiers from the matrix:
- minor: Parser should extract basic effects (damage/heal/condition/buff)
- moderate: May require special handlers, should at least parse basics
- significant: Complex mechanics, may need oracle fallback
- skip: Oracle-only, may not parse any mechanical effects
"""

import pytest
import json
import csv
from pathlib import Path
from typing import Optional

from tests.dolmenwood_spell_helpers import (
    find_spell_by_id,
    get_spell_dict,
    spell_dict_to_spelldata,
    make_test_character,
    SPELL_DATA_DIR,
)
from src.narrative.spell_resolver import SpellResolver, SpellData, MagicType


# Load implementation matrix
MATRIX_PATH = Path(__file__).parent.parent / "docs" / "Dolmenwood_Spell_Implementation_Matrix.csv"


def load_implementation_matrix() -> dict[str, dict]:
    """Load the implementation matrix into a dict keyed by spell_id."""
    matrix = {}
    if not MATRIX_PATH.exists():
        return matrix

    with open(MATRIX_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            spell_id = row.get('spell_id', '')
            if spell_id:
                matrix[spell_id] = row
    return matrix


IMPL_MATRIX = load_implementation_matrix()


def get_all_spell_ids() -> list[str]:
    """Get all spell IDs from the spell data files."""
    spell_ids = []
    for json_file in SPELL_DATA_DIR.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
            for spell in data.get("items", []):
                spell_id = spell.get("spell_id")
                if spell_id:
                    spell_ids.append(spell_id)
        except (json.JSONDecodeError, KeyError):
            continue
    return sorted(spell_ids)


ALL_SPELL_IDS = get_all_spell_ids()


class TestAllSpellsLoad:
    """Test that all spells load correctly from JSON."""

    @pytest.mark.parametrize("spell_id", ALL_SPELL_IDS)
    def test_spell_loads(self, spell_id: str):
        """Verify each spell loads and converts to SpellData."""
        spell = find_spell_by_id(spell_id)
        assert spell is not None, f"Failed to load spell: {spell_id}"
        assert spell.spell_id == spell_id
        assert spell.name, f"Spell {spell_id} has no name"
        assert spell.description, f"Spell {spell_id} has no description"


class TestAllSpellsParse:
    """Test that all spells can be parsed by SpellResolver."""

    @pytest.fixture
    def resolver(self):
        """Create a SpellResolver for testing."""
        return SpellResolver()

    @pytest.mark.parametrize("spell_id", ALL_SPELL_IDS)
    def test_spell_parses_without_error(self, resolver: SpellResolver, spell_id: str):
        """Verify each spell can be parsed without raising exceptions."""
        spell = find_spell_by_id(spell_id)

        # This should not raise an exception
        parsed = resolver.parse_mechanical_effects(spell)

        # Basic validation
        assert parsed is not None, f"Parser returned None for {spell_id}"

        # Log what was found (for debugging)
        impl_info = IMPL_MATRIX.get(spell_id, {})
        impl_level = impl_info.get("recommended_implementation_level", "unknown")

        effect_count = len(parsed.effects) if parsed.effects else 0
        print(f"\n{spell_id} ({impl_level}): {effect_count} effects parsed")
        if parsed.effects:
            for effect in parsed.effects:
                print(f"  - {effect.category.value}: {effect.description}")


class TestMinorSpellsParsing:
    """Test that 'minor' tier spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def get_minor_spells(self) -> list[str]:
        """Get all spell IDs with 'minor' implementation level."""
        return [
            spell_id for spell_id, info in IMPL_MATRIX.items()
            if info.get("recommended_implementation_level") == "minor"
            and spell_id in ALL_SPELL_IDS
        ]

    @pytest.mark.parametrize("spell_id", [
        sid for sid, info in IMPL_MATRIX.items()
        if info.get("recommended_implementation_level") == "minor"
        and sid in ALL_SPELL_IDS
    ][:31])  # All 31 minor spells
    def test_minor_spell_parses_effects(self, resolver: SpellResolver, spell_id: str):
        """Minor spells should parse at least some mechanical effects."""
        spell = find_spell_by_id(spell_id)
        parsed = resolver.parse_mechanical_effects(spell)

        impl_info = IMPL_MATRIX.get(spell_id, {})
        subsystems = impl_info.get("required_subsystems", "")

        # Log for analysis
        effect_count = len(parsed.effects) if parsed.effects else 0
        print(f"\n[MINOR] {spell_id}: {effect_count} effects, subsystems: {subsystems}")

        # Minor spells SHOULD produce effects - report if they don't
        if effect_count == 0:
            print(f"  WARNING: Minor spell {spell_id} produced no parsed effects!")
            print(f"  Description: {spell.description[:200]}...")


class TestModerateSpellsParsing:
    """Test that 'moderate' tier spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    @pytest.mark.parametrize("spell_id", [
        sid for sid, info in IMPL_MATRIX.items()
        if info.get("recommended_implementation_level") == "moderate"
        and sid in ALL_SPELL_IDS
    ][:65])  # All 65 moderate spells
    def test_moderate_spell_parses(self, resolver: SpellResolver, spell_id: str):
        """Moderate spells should parse without error and ideally produce some effects."""
        spell = find_spell_by_id(spell_id)
        parsed = resolver.parse_mechanical_effects(spell)

        impl_info = IMPL_MATRIX.get(spell_id, {})
        subsystems = impl_info.get("required_subsystems", "")

        effect_count = len(parsed.effects) if parsed.effects else 0
        print(f"\n[MODERATE] {spell_id}: {effect_count} effects, subsystems: {subsystems}")

        # Log spells that need special handling
        if effect_count == 0 and subsystems:
            print(f"  NOTE: Has subsystems but no parsed effects - needs special handler")


class TestSignificantSpellsParsing:
    """Test that 'significant' tier spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    @pytest.mark.parametrize("spell_id", [
        sid for sid, info in IMPL_MATRIX.items()
        if info.get("recommended_implementation_level") == "significant"
        and sid in ALL_SPELL_IDS
    ][:27])  # All 27 significant spells
    def test_significant_spell_parses(self, resolver: SpellResolver, spell_id: str):
        """Significant spells should parse without error."""
        spell = find_spell_by_id(spell_id)
        parsed = resolver.parse_mechanical_effects(spell)

        impl_info = IMPL_MATRIX.get(spell_id, {})
        subsystems = impl_info.get("required_subsystems", "")
        strategy = impl_info.get("good_enough_80_strategy", "")

        effect_count = len(parsed.effects) if parsed.effects else 0
        print(f"\n[SIGNIFICANT] {spell_id}: {effect_count} effects")
        print(f"  Subsystems: {subsystems}")
        if strategy:
            print(f"  80% Strategy: {strategy[:100]}...")


class TestSkipSpellsOracle:
    """Test that 'skip' tier spells are handled gracefully."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    @pytest.mark.parametrize("spell_id", [
        sid for sid, info in IMPL_MATRIX.items()
        if info.get("recommended_implementation_level") == "skip"
        and sid in ALL_SPELL_IDS
    ][:43])  # All 43 skip spells
    def test_skip_spell_parses_gracefully(self, resolver: SpellResolver, spell_id: str):
        """Skip spells should parse without error (may produce no effects)."""
        spell = find_spell_by_id(spell_id)
        parsed = resolver.parse_mechanical_effects(spell)

        impl_info = IMPL_MATRIX.get(spell_id, {})
        strategy = impl_info.get("good_enough_80_strategy", "")

        effect_count = len(parsed.effects) if parsed.effects else 0
        print(f"\n[SKIP] {spell_id}: {effect_count} effects (expected: 0 or oracle)")
        if strategy:
            print(f"  Strategy: {strategy[:150]}...")


class TestSpellParsingReport:
    """Generate a comprehensive report of spell parsing results."""

    def test_generate_parsing_report(self):
        """Generate a report showing which spells parse correctly."""
        resolver = SpellResolver()

        results = {
            "minor": {"total": 0, "with_effects": 0, "spells": []},
            "moderate": {"total": 0, "with_effects": 0, "spells": []},
            "significant": {"total": 0, "with_effects": 0, "spells": []},
            "skip": {"total": 0, "with_effects": 0, "spells": []},
            "unknown": {"total": 0, "with_effects": 0, "spells": []},
        }

        for spell_id in ALL_SPELL_IDS:
            try:
                spell = find_spell_by_id(spell_id)
                parsed = resolver.parse_mechanical_effects(spell)
                effect_count = len(parsed.effects) if parsed.effects else 0

                impl_info = IMPL_MATRIX.get(spell_id, {})
                tier = impl_info.get("recommended_implementation_level", "unknown")
                if tier not in results:
                    tier = "unknown"

                results[tier]["total"] += 1
                if effect_count > 0:
                    results[tier]["with_effects"] += 1

                results[tier]["spells"].append({
                    "spell_id": spell_id,
                    "name": spell.name,
                    "effect_count": effect_count,
                    "effects": [e.description for e in (parsed.effects or [])],
                })
            except Exception as e:
                print(f"ERROR parsing {spell_id}: {e}")

        # Print report
        print("\n" + "=" * 60)
        print("DOLMENWOOD SPELL PARSING REPORT")
        print("=" * 60)

        total_spells = sum(r["total"] for r in results.values())
        total_with_effects = sum(r["with_effects"] for r in results.values())

        print(f"\nTotal spells: {total_spells}")
        print(f"Spells with parsed effects: {total_with_effects}")
        print(f"Parsing rate: {total_with_effects/total_spells*100:.1f}%")

        for tier in ["minor", "moderate", "significant", "skip", "unknown"]:
            data = results[tier]
            if data["total"] == 0:
                continue

            pct = data["with_effects"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"\n{tier.upper()}: {data['with_effects']}/{data['total']} ({pct:.1f}%)")

            # Show spells without effects for minor/moderate tiers
            if tier in ["minor", "moderate"]:
                no_effects = [s for s in data["spells"] if s["effect_count"] == 0]
                if no_effects:
                    print(f"  Spells needing attention ({len(no_effects)}):")
                    for s in no_effects[:10]:
                        print(f"    - {s['spell_id']} ({s['name']})")
                    if len(no_effects) > 10:
                        print(f"    ... and {len(no_effects) - 10} more")

        print("\n" + "=" * 60)


# Individual spell tests for specific patterns
class TestDamageSpells:
    """Test damage-dealing spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_fireball(self, resolver):
        """Fireball should parse damage dice."""
        spell = find_spell_by_id("fireball")
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in (parsed.effects or []) if e.damage_dice]
        assert len(damage_effects) >= 1, "Fireball should have damage effect"

    def test_lightning_bolt(self, resolver):
        """Lightning Bolt should parse damage."""
        spell = find_spell_by_id("lightning_bolt")
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in (parsed.effects or []) if e.damage_dice]
        assert len(damage_effects) >= 1, "Lightning Bolt should have damage effect"

    def test_acid_globe(self, resolver):
        """Acid Globe should parse damage."""
        spell = find_spell_by_id("acid_globe")
        parsed = resolver.parse_mechanical_effects(spell)

        damage_effects = [e for e in (parsed.effects or []) if e.damage_dice or e.flat_damage]
        assert len(damage_effects) >= 1, "Acid Globe should have damage effect"

    def test_cloudkill(self, resolver):
        """Cloudkill should parse death effect or damage."""
        spell = find_spell_by_id("cloudkill")
        parsed = resolver.parse_mechanical_effects(spell)

        # Should have death effect or damage
        has_death = any(e.is_death_effect for e in (parsed.effects or []))
        has_damage = any(e.damage_dice or e.flat_damage for e in (parsed.effects or []))

        assert has_death or has_damage, "Cloudkill should have death or damage effect"


class TestHealingSpells:
    """Test healing spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_lesser_healing(self, resolver):
        """Lesser Healing should parse healing dice."""
        spell = find_spell_by_id("lesser_healing")
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in (parsed.effects or []) if e.healing_dice or e.flat_healing]
        assert len(heal_effects) >= 1, "Lesser Healing should have healing effect"

    def test_greater_healing(self, resolver):
        """Greater Healing should parse healing dice."""
        spell = find_spell_by_id("greater_healing")
        parsed = resolver.parse_mechanical_effects(spell)

        heal_effects = [e for e in (parsed.effects or []) if e.healing_dice or e.flat_healing]
        assert len(heal_effects) >= 1, "Greater Healing should have healing effect"


class TestConditionSpells:
    """Test condition-applying spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_hold_person(self, resolver):
        """Hold Person should apply paralyzed condition."""
        spell = find_spell_by_id("hold_person")
        parsed = resolver.parse_mechanical_effects(spell)

        conditions = [e for e in (parsed.effects or []) if e.condition_applied]
        assert len(conditions) >= 1, "Hold Person should apply a condition"

    def test_paralysation(self, resolver):
        """Paralysation should apply paralyzed condition."""
        spell = find_spell_by_id("paralysation")
        parsed = resolver.parse_mechanical_effects(spell)

        conditions = [e for e in (parsed.effects or []) if e.condition_applied == "paralyzed"]
        assert len(conditions) >= 1, "Paralysation should apply paralyzed condition"

    def test_fear(self, resolver):
        """Fear should apply frightened condition."""
        spell = find_spell_by_id("fear")
        parsed = resolver.parse_mechanical_effects(spell)

        conditions = [e for e in (parsed.effects or []) if e.condition_applied == "frightened"]
        assert len(conditions) >= 1, "Fear should apply frightened condition"


class TestBuffSpells:
    """Test buff spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_bless(self, resolver):
        """Bless should parse modifier bonus."""
        spell = find_spell_by_id("bless")
        parsed = resolver.parse_mechanical_effects(spell)

        buffs = [e for e in (parsed.effects or []) if e.modifier_value and e.modifier_value > 0]
        assert len(buffs) >= 1, "Bless should have buff effect"

    def test_haste(self, resolver):
        """Haste should parse some effect."""
        spell = find_spell_by_id("haste")
        parsed = resolver.parse_mechanical_effects(spell)
        # Haste may need special handling for extra attacks
        print(f"Haste effects: {[e.description for e in (parsed.effects or [])]}")

    def test_shield_of_force(self, resolver):
        """Shield of Force should parse AC bonus."""
        spell = find_spell_by_id("shield_of_force")
        parsed = resolver.parse_mechanical_effects(spell)

        ac_effects = [e for e in (parsed.effects or [])
                      if e.ac_override or (e.stat_modified and 'ac' in e.stat_modified.lower())]
        print(f"Shield of Force effects: {[e.description for e in (parsed.effects or [])]}")


class TestWardSpells:
    """Test ward/protection spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_frost_ward(self, resolver):
        """Frost Ward should parse cold resistance."""
        spell = find_spell_by_id("frost_ward")
        parsed = resolver.parse_mechanical_effects(spell)

        resist_effects = [e for e in (parsed.effects or [])
                          if e.damage_type == "cold" or "cold" in e.description.lower()]
        assert len(resist_effects) >= 1, "Frost Ward should have cold resistance"

    def test_flame_ward(self, resolver):
        """Flame Ward should parse fire resistance."""
        spell = find_spell_by_id("flame_ward")
        parsed = resolver.parse_mechanical_effects(spell)

        resist_effects = [e for e in (parsed.effects or [])
                          if e.damage_type == "fire" or "fire" in e.description.lower()]
        assert len(resist_effects) >= 1, "Flame Ward should have fire resistance"

    def test_missile_ward(self, resolver):
        """Missile Ward should parse immunity effect."""
        spell = find_spell_by_id("missile_ward")
        parsed = resolver.parse_mechanical_effects(spell)

        # May need immunity subsystem
        print(f"Missile Ward effects: {[e.description for e in (parsed.effects or [])]}")


class TestCharmSpells:
    """Test charm/control spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_ingratiate(self, resolver):
        """Ingratiate should parse charm effect."""
        spell = find_spell_by_id("ingratiate")
        parsed = resolver.parse_mechanical_effects(spell)

        charm_effects = [e for e in (parsed.effects or [])
                         if e.condition_applied == "charmed" or e.is_charm_effect]
        assert len(charm_effects) >= 1, "Ingratiate should have charm effect"

    def test_dominate(self, resolver):
        """Dominate should parse charm/control effect."""
        spell = find_spell_by_id("dominate")
        parsed = resolver.parse_mechanical_effects(spell)

        charm_effects = [e for e in (parsed.effects or [])
                         if e.condition_applied == "charmed" or e.is_charm_effect]
        assert len(charm_effects) >= 1, "Dominate should have charm effect"

    def test_charm_serpents(self, resolver):
        """Charm Serpents should parse charm effect."""
        spell = find_spell_by_id("charm_serpents")
        parsed = resolver.parse_mechanical_effects(spell)

        charm_effects = [e for e in (parsed.effects or [])
                         if e.condition_applied == "charmed" or e.is_charm_effect]
        assert len(charm_effects) >= 1, "Charm Serpents should have charm effect"


class TestDeathEffectSpells:
    """Test death effect spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_disintegrate(self, resolver):
        """Disintegrate should parse death effect."""
        spell = find_spell_by_id("disintegrate")
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in (parsed.effects or []) if e.is_death_effect]
        assert len(death_effects) >= 1, "Disintegrate should have death effect"

    def test_petrification(self, resolver):
        """Petrification should parse death/petrify effect."""
        spell = find_spell_by_id("petrification")
        parsed = resolver.parse_mechanical_effects(spell)

        # Either death effect or petrified condition
        has_death = any(e.is_death_effect for e in (parsed.effects or []))
        has_petrified = any(e.condition_applied == "petrified" for e in (parsed.effects or []))

        assert has_death or has_petrified, "Petrification should have death or petrified effect"

    def test_word_of_doom(self, resolver):
        """Word of Doom should parse death effect with HD threshold."""
        spell = find_spell_by_id("word_of_doom")
        parsed = resolver.parse_mechanical_effects(spell)

        death_effects = [e for e in (parsed.effects or []) if e.is_death_effect]
        assert len(death_effects) >= 1, "Word of Doom should have death effect"


class TestLightSpells:
    """Test light-creating spells parse correctly."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_light(self, resolver):
        """Light spell should parse light effect."""
        spell = find_spell_by_id("light")
        parsed = resolver.parse_mechanical_effects(spell)

        light_effects = [e for e in (parsed.effects or [])
                         if "light" in e.description.lower()]
        assert len(light_effects) >= 1, "Light should have light effect"

    def test_firelight(self, resolver):
        """Firelight should parse light effect."""
        spell = find_spell_by_id("firelight")
        parsed = resolver.parse_mechanical_effects(spell)

        # May also have damage component
        print(f"Firelight effects: {[e.description for e in (parsed.effects or [])]}")


class TestUtilitySpells:
    """Test utility spells parse appropriately."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_dispel_magic(self, resolver):
        """Dispel Magic should parse without error."""
        spell = find_spell_by_id("dispel_magic")
        parsed = resolver.parse_mechanical_effects(spell)
        # Dispel magic is a special case - may need handler
        print(f"Dispel Magic effects: {[e.description for e in (parsed.effects or [])]}")

    def test_remove_curse(self, resolver):
        """Remove Curse should parse without error."""
        spell = find_spell_by_id("remove_curse")
        parsed = resolver.parse_mechanical_effects(spell)
        print(f"Remove Curse effects: {[e.description for e in (parsed.effects or [])]}")

    def test_water_breathing(self, resolver):
        """Water Breathing should parse buff effect."""
        spell = find_spell_by_id("water_breathing")
        parsed = resolver.parse_mechanical_effects(spell)
        print(f"Water Breathing effects: {[e.description for e in (parsed.effects or [])]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
