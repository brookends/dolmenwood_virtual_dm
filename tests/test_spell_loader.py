"""
Tests for the Spell Loader and Registry.

Tests the loading of spell data from JSON files, parsing of
raw text fields into structured components, and spell registry
lookup functionality.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.content_loader.spell_loader import (
    SpellDataLoader,
    SpellParser,
    load_all_spells,
    register_spells_with_resolver,
)
from src.content_loader.spell_registry import (
    SpellRegistry,
    get_spell_registry,
    reset_spell_registry,
)
from src.narrative.spell_resolver import (
    SpellData,
    SpellResolver,
    DurationType,
    RangeType,
    MagicType,
    RuneMagnitude,
    UsageFrequency,
    LevelScalingType,
)
from src.narrative.intent_parser import SaveType


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_parser():
    """Create a SpellParser instance."""
    return SpellParser()


@pytest.fixture
def spell_loader():
    """Create a SpellDataLoader instance."""
    return SpellDataLoader()


@pytest.fixture
def spell_registry():
    """Create a fresh SpellRegistry instance."""
    reset_spell_registry()
    registry = get_spell_registry()
    yield registry
    reset_spell_registry()


@pytest.fixture
def sample_spell_json():
    """Sample spell JSON data for testing."""
    return {
        "_metadata": {
            "source_file": "test_source.pdf",
            "pages": [42],
            "content_type": "spells",
            "item_count": 3
        },
        "items": [
            {
                "name": "Test Fireball",
                "spell_id": "test_fireball",
                "level": 3,
                "magic_type": "arcane",
                "duration": "Instant",
                "range": "150'",
                "description": "A ball of fire explodes, dealing 1d6 damage per caster level. "
                              "All creatures in a 20' radius must Save Versus Blast for half damage.",
                "reversible": False,
                "reversed_name": None
            },
            {
                "name": "Test Charm",
                "spell_id": "test_charm",
                "level": 1,
                "magic_type": "arcane",
                "duration": "Until dispelled",
                "range": "60'",
                "description": "The target must Save Versus Spell or be charmed. "
                              "Affects creatures of Level 4 or lower only. "
                              "The target may save again daily.",
                "reversible": False,
                "reversed_name": None
            },
            {
                "name": "Test Glamour",
                "spell_id": "test_glamour",
                "level": None,
                "magic_type": "fairy_glamour",
                "duration": "1 Turn per Level",
                "range": "Touch",
                "description": "A fairy enchantment that can be used once per day per subject.",
                "reversible": False,
                "reversed_name": None
            }
        ]
    }


@pytest.fixture
def temp_spell_directory(sample_spell_json):
    """Create a temporary directory with spell JSON files."""
    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Write sample spell file
        with open(tmppath / "test_spells.json", "w") as f:
            json.dump(sample_spell_json, f)

        # Write a rune spell file
        rune_data = {
            "_metadata": {"content_type": "spells"},
            "items": [
                {
                    "name": "Test Rune",
                    "spell_id": "test_rune",
                    "level": "lesser",
                    "magic_type": "rune",
                    "duration": "6 Turns",
                    "range": "Self",
                    "description": "A lesser fairy rune.",
                    "reversible": False,
                    "reversed_name": None
                }
            ]
        }
        with open(tmppath / "test_runes.json", "w") as f:
            json.dump(rune_data, f)

        yield tmppath


# =============================================================================
# SPELL PARSER TESTS
# =============================================================================


class TestSpellParserDuration:
    """Tests for duration parsing."""

    def test_parse_turns(self, spell_parser):
        """Test parsing turn-based durations."""
        dtype, value, per_level = spell_parser.parse_duration("6 Turns")
        assert dtype == DurationType.TURNS
        assert value == "6"
        assert not per_level

    def test_parse_rounds(self, spell_parser):
        """Test parsing round-based durations."""
        dtype, value, per_level = spell_parser.parse_duration("3 Rounds")
        assert dtype == DurationType.ROUNDS
        assert value == "3"

    def test_parse_turns_per_level(self, spell_parser):
        """Test parsing duration with per-level scaling."""
        dtype, value, per_level = spell_parser.parse_duration("1 Turn per Level")
        assert dtype == DurationType.TURNS
        assert per_level is True

    def test_parse_concentration(self, spell_parser):
        """Test parsing concentration duration."""
        dtype, value, per_level = spell_parser.parse_duration("Concentration")
        assert dtype == DurationType.CONCENTRATION

    def test_parse_permanent(self, spell_parser):
        """Test parsing permanent duration."""
        dtype, value, per_level = spell_parser.parse_duration("Until dispelled")
        assert dtype == DurationType.PERMANENT

    def test_parse_instant(self, spell_parser):
        """Test parsing instant duration."""
        dtype, value, per_level = spell_parser.parse_duration("Instant")
        assert dtype == DurationType.INSTANT

    def test_parse_special(self, spell_parser):
        """Test parsing special duration."""
        dtype, value, per_level = spell_parser.parse_duration("Special")
        assert dtype == DurationType.SPECIAL

    def test_parse_dice_duration(self, spell_parser):
        """Test parsing dice-based duration."""
        dtype, value, per_level = spell_parser.parse_duration("1d6 Turns")
        assert dtype == DurationType.TURNS
        assert value == "1d6"


class TestSpellParserRange:
    """Tests for range parsing."""

    def test_parse_self(self, spell_parser):
        """Test parsing self range."""
        rtype, feet = spell_parser.parse_range("The caster")
        assert rtype == RangeType.SELF
        assert feet is None

    def test_parse_touch(self, spell_parser):
        """Test parsing touch range."""
        rtype, feet = spell_parser.parse_range("Touch")
        assert rtype == RangeType.TOUCH
        assert feet is None

    def test_parse_feet_with_apostrophe(self, spell_parser):
        """Test parsing feet with apostrophe notation."""
        rtype, feet = spell_parser.parse_range("60'")
        assert rtype == RangeType.RANGED
        assert feet == 60

    def test_parse_feet_with_word(self, spell_parser):
        """Test parsing feet with word."""
        rtype, feet = spell_parser.parse_range("100 feet")
        assert rtype == RangeType.RANGED
        assert feet == 100


class TestSpellParserSave:
    """Tests for save type parsing."""

    def test_parse_save_vs_spell(self, spell_parser):
        """Test parsing Save vs Spell."""
        save_type, negates = spell_parser.parse_save_type(
            "The target must Save Versus Spell or be charmed."
        )
        assert save_type == SaveType.SPELL

    def test_parse_save_vs_blast(self, spell_parser):
        """Test parsing Save vs Blast."""
        save_type, negates = spell_parser.parse_save_type(
            "Save Versus Blast for half damage."
        )
        assert save_type == SaveType.BLAST

    def test_parse_save_vs_doom(self, spell_parser):
        """Test parsing Save vs Doom."""
        save_type, negates = spell_parser.parse_save_type(
            "The target must Save Versus Doom or die."
        )
        assert save_type == SaveType.DOOM

    def test_parse_no_save(self, spell_parser):
        """Test spell with no save."""
        save_type, negates = spell_parser.parse_save_type(
            "This spell has no saving throw."
        )
        assert save_type is None


class TestSpellParserLevelScaling:
    """Tests for level scaling parsing."""

    def test_parse_per_level_duration(self, spell_parser):
        """Test parsing per-level duration scaling."""
        scalings = spell_parser.parse_level_scaling("1 Turn per Level")
        assert len(scalings) >= 1
        assert any(s.scaling_type == LevelScalingType.DURATION for s in scalings)

    def test_parse_per_level_damage(self, spell_parser):
        """Test parsing per-level damage scaling."""
        scalings = spell_parser.parse_level_scaling("1d6 per Level damage")
        assert len(scalings) >= 1
        assert any(s.scaling_type == LevelScalingType.DAMAGE for s in scalings)


class TestSpellParserUsageFrequency:
    """Tests for usage frequency parsing."""

    def test_parse_once_per_day(self, spell_parser):
        """Test parsing once per day."""
        freq = spell_parser.parse_usage_frequency("Can be used once per day.")
        assert freq == UsageFrequency.ONCE_PER_DAY

    def test_parse_once_per_day_per_subject(self, spell_parser):
        """Test parsing once per day per subject."""
        freq = spell_parser.parse_usage_frequency("Once per day per subject.")
        assert freq == UsageFrequency.ONCE_PER_DAY_PER_SUBJECT

    def test_parse_at_will(self, spell_parser):
        """Test parsing at will."""
        freq = spell_parser.parse_usage_frequency("Can be used at will.")
        assert freq == UsageFrequency.AT_WILL


class TestSpellParserTargetRestrictions:
    """Tests for target restriction parsing."""

    def test_parse_level_restriction(self, spell_parser):
        """Test parsing level restriction."""
        restrictions = spell_parser.parse_target_restrictions(
            "Affects creatures of Level 4 or lower."
        )
        assert restrictions["max_target_level"] == 4

    def test_parse_hd_restriction(self, spell_parser):
        """Test parsing HD restriction."""
        restrictions = spell_parser.parse_target_restrictions(
            "Only affects creatures with 6 HD or fewer."
        )
        assert restrictions["max_target_hd"] == 6

    def test_parse_living_only(self, spell_parser):
        """Test parsing living creatures only."""
        restrictions = spell_parser.parse_target_restrictions(
            "Only affects living creatures only."
        )
        assert restrictions["affects_living_only"] is True


# =============================================================================
# SPELL LOADER TESTS
# =============================================================================


class TestSpellDataLoader:
    """Tests for SpellDataLoader."""

    def test_load_file(self, spell_loader, temp_spell_directory):
        """Test loading a single spell file."""
        result = spell_loader.load_file(temp_spell_directory / "test_spells.json")

        assert result.success
        assert result.spells_loaded == 3
        assert len(result.loaded_spells) == 3
        assert result.metadata is not None
        assert result.metadata.source_file == "test_source.pdf"

    def test_load_directory(self, spell_loader, temp_spell_directory):
        """Test loading all spells from a directory."""
        result = spell_loader.load_directory(temp_spell_directory)

        assert result.files_processed == 2
        assert result.total_spells_loaded == 4
        assert len(result.all_spells) == 4

    def test_parse_arcane_spell(self, spell_loader, temp_spell_directory):
        """Test parsing an arcane spell."""
        result = spell_loader.load_file(temp_spell_directory / "test_spells.json")

        fireball = next(s for s in result.loaded_spells if s.spell_id == "test_fireball")
        assert fireball.name == "Test Fireball"
        assert fireball.level == 3
        assert fireball.magic_type == MagicType.ARCANE
        assert fireball.range_feet == 150
        assert fireball.save_type == SaveType.BLAST

    def test_parse_glamour_spell(self, spell_loader, temp_spell_directory):
        """Test parsing a glamour spell."""
        result = spell_loader.load_file(temp_spell_directory / "test_spells.json")

        glamour = next(s for s in result.loaded_spells if s.spell_id == "test_glamour")
        assert glamour.name == "Test Glamour"
        assert glamour.level is None
        assert glamour.magic_type == MagicType.FAIRY_GLAMOUR
        assert glamour.range_type == RangeType.TOUCH
        assert glamour.duration_per_level is True

    def test_parse_rune_magnitude(self, spell_loader, temp_spell_directory):
        """Test parsing rune magnitude from level field."""
        result = spell_loader.load_file(temp_spell_directory / "test_runes.json")

        rune = result.loaded_spells[0]
        assert rune.spell_id == "test_rune"
        assert rune.magic_type == MagicType.RUNE
        assert rune.rune_magnitude == RuneMagnitude.LESSER
        assert rune.level is None

    def test_load_nonexistent_file(self, spell_loader):
        """Test loading a non-existent file."""
        result = spell_loader.load_file(Path("/nonexistent/path.json"))

        assert not result.success
        assert len(result.errors) > 0


# =============================================================================
# SPELL REGISTRY TESTS
# =============================================================================


class TestSpellRegistry:
    """Tests for SpellRegistry."""

    def test_register_and_get_by_id(self, spell_registry):
        """Test registering and retrieving a spell by ID."""
        spell = SpellData(
            spell_id="test_spell",
            name="Test Spell",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="60'",
            description="A test spell."
        )
        spell_registry.register(spell)

        result = spell_registry.get_by_id("test_spell")
        assert result.found
        assert result.spell.name == "Test Spell"

    def test_get_by_name_case_insensitive(self, spell_registry):
        """Test case-insensitive name lookup."""
        spell = SpellData(
            spell_id="magic_missile",
            name="Magic Missile",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="150'",
            description="Unerring bolts of force."
        )
        spell_registry.register(spell)

        result = spell_registry.get_by_name("MAGIC MISSILE")
        assert result.found
        assert result.spell.spell_id == "magic_missile"

    def test_get_by_level(self, spell_registry):
        """Test getting spells by level."""
        spell1 = SpellData(
            spell_id="level1_spell",
            name="Level 1 Spell",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="60'",
            description="Test"
        )
        spell2 = SpellData(
            spell_id="level2_spell",
            name="Level 2 Spell",
            level=2,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="60'",
            description="Test"
        )
        spell_registry.register(spell1)
        spell_registry.register(spell2)

        result = spell_registry.get_by_level(1, MagicType.ARCANE)
        assert result.count == 1
        assert result.spells[0].spell_id == "level1_spell"

    def test_get_by_magic_type(self, spell_registry):
        """Test getting spells by magic type."""
        arcane = SpellData(
            spell_id="arcane_spell",
            name="Arcane Spell",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="60'",
            description="Test"
        )
        divine = SpellData(
            spell_id="divine_spell",
            name="Divine Spell",
            level=1,
            magic_type=MagicType.DIVINE,
            duration="Instant",
            range="60'",
            description="Test"
        )
        spell_registry.register(arcane)
        spell_registry.register(divine)

        result = spell_registry.get_by_magic_type(MagicType.DIVINE)
        assert result.count == 1
        assert result.spells[0].spell_id == "divine_spell"

    def test_get_by_rune_magnitude(self, spell_registry):
        """Test getting runes by magnitude."""
        lesser = SpellData(
            spell_id="lesser_rune",
            name="Lesser Rune",
            level=None,
            magic_type=MagicType.RUNE,
            duration="1 Turn",
            range="Self",
            description="Test",
            rune_magnitude=RuneMagnitude.LESSER
        )
        greater = SpellData(
            spell_id="greater_rune",
            name="Greater Rune",
            level=None,
            magic_type=MagicType.RUNE,
            duration="1 Turn",
            range="Self",
            description="Test",
            rune_magnitude=RuneMagnitude.GREATER
        )
        spell_registry.register(lesser)
        spell_registry.register(greater)

        result = spell_registry.get_by_rune_magnitude(RuneMagnitude.LESSER)
        assert result.count == 1
        assert result.spells[0].spell_id == "lesser_rune"

    def test_search_by_name(self, spell_registry):
        """Test searching spells by name substring."""
        spell1 = SpellData(
            spell_id="fireball",
            name="Fireball",
            level=3,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="150'",
            description="Fire damage"
        )
        spell2 = SpellData(
            spell_id="firelight",
            name="Firelight",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="6 Turns",
            range="Self",
            description="Creates light"
        )
        spell3 = SpellData(
            spell_id="lightning",
            name="Lightning Bolt",
            level=3,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="180'",
            description="Lightning damage"
        )
        spell_registry.register(spell1)
        spell_registry.register(spell2)
        spell_registry.register(spell3)

        result = spell_registry.search(name_contains="fire")
        assert result.count == 2
        assert all("fire" in s.name.lower() for s in result.spells)

    def test_load_from_directory(self, spell_registry, temp_spell_directory):
        """Test loading spells from a directory into the registry."""
        count = spell_registry.load_from_directory(temp_spell_directory)

        assert count == 4
        assert spell_registry.spell_count == 4
        assert spell_registry.is_loaded

    def test_register_with_resolver(self, spell_registry, temp_spell_directory):
        """Test registering spells with a SpellResolver."""
        spell_registry.load_from_directory(temp_spell_directory)

        resolver = SpellResolver()
        count = spell_registry.register_with_resolver(resolver)

        assert count == 4
        assert resolver.lookup_spell("test_fireball") is not None
        assert resolver.lookup_spell("test_rune") is not None


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_load_all_spells(self, temp_spell_directory):
        """Test the load_all_spells convenience function."""
        result = load_all_spells(temp_spell_directory)

        assert result.total_spells_loaded == 4
        assert len(result.all_spells) == 4

    def test_register_spells_with_resolver(self, temp_spell_directory):
        """Test the register_spells_with_resolver convenience function."""
        result = load_all_spells(temp_spell_directory)
        resolver = SpellResolver()

        count = register_spells_with_resolver(result.all_spells, resolver)

        assert count == 4
        assert resolver.lookup_spell("test_fireball") is not None


# =============================================================================
# INTEGRATION WITH REAL SPELL DATA
# =============================================================================


class TestRealSpellData:
    """Integration tests with real spell data files."""

    @pytest.fixture
    def real_spell_directory(self):
        """Get the path to real spell data."""
        path = Path(__file__).parent.parent / "data" / "content" / "spells"
        if not path.exists():
            pytest.skip("Real spell data not available")
        return path

    def test_load_real_spells(self, real_spell_directory, spell_loader):
        """Test loading real spell data files."""
        result = spell_loader.load_directory(real_spell_directory)

        # Should load many spells with minimal errors
        assert result.total_spells_loaded > 100
        # Allow some parse failures for edge cases in real data
        assert result.total_spells_failed < 10

        # Basic validation of loaded spells
        for spell in result.all_spells:
            assert spell.spell_id
            assert spell.name
            assert spell.magic_type in MagicType

    def test_real_spell_registry(self, real_spell_directory):
        """Test registering real spells in the registry."""
        reset_spell_registry()
        registry = get_spell_registry()

        count = registry.load_from_directory(real_spell_directory)

        assert count > 0
        assert registry.is_loaded

        # Test some known spells exist
        fireball = registry.get_by_name("Fireball")
        if fireball.found:
            assert fireball.spell.level == 3
            assert fireball.spell.magic_type == MagicType.ARCANE

        reset_spell_registry()
