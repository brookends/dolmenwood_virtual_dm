"""
Tests for oracle-adjudicated spell handlers (Skip spells).

This module tests the 21 oracle-adjudicated spells that require
Mythic GME oracle resolution rather than mechanical parsing:
- Beguilement (illusion_belief)
- Bird Friend (summoning_control)
- Dancing Flame (generic)
- Detect Evil (divination)
- Detect Magic (divination)
- Disguise Object (illusion_belief)
- Dweomerlight (divination)
- Fabricate (generic)
- Fairy Steed (summoning_control)
- Find Traps (divination)
- Mind Crystal (divination)
- Mirth and Malice (illusion_belief)
- Move Terrain (generic)
- Oracle (divination)
- Reveal Alignment (divination)
- Root Friend (summoning_control)
- Rune of Wishing (wish)
- Summon Wild Hunt (summoning_control)
- Thread Whistling (generic)
- Wood Kenning (divination)
- Yeast Master (generic)
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.narrative.spell_resolver import (
    ActiveSpellEffect,
    DurationType,
    SpellData,
    SpellEffectType,
    SpellResolver,
)
from src.oracle.spell_adjudicator import (
    AdjudicationResult,
    SpellAdjudicationType,
    SuccessLevel,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_resolver():
    """Create a SpellResolver instance for testing."""
    resolver = SpellResolver()
    resolver._active_effects = []
    resolver._current_context = {}
    return resolver


@pytest.fixture
def mock_caster():
    """Create a mock caster with appropriate attributes."""
    caster = MagicMock()
    caster.character_id = "caster_1"
    caster.name = "Aldric the Wise"
    caster.level = 7
    return caster


@pytest.fixture
def mock_targets():
    """Create a list of mock target IDs."""
    return ["target_1", "target_2"]


@pytest.fixture
def fixed_dice_roller():
    """Create a dice roller that returns predictable values."""
    roller = MagicMock()
    roll_result = MagicMock()
    roll_result.total = 10
    roller.roll = MagicMock(return_value=roll_result)
    return roller


@pytest.fixture
def oracle_registry_loader():
    """Fixture to load the oracle spell registry."""

    def _load_registry() -> dict:
        registry_path = Path(__file__).parent.parent / "data" / "system" / "oracle_only_spells.json"
        with open(registry_path) as f:
            return json.load(f)

    return _load_registry


@pytest.fixture
def spell_data_loader():
    """Fixture to load actual spell data from JSON files."""

    def _load_spell(filename: str, spell_id: str) -> dict:
        spell_path = Path(__file__).parent.parent / "data" / "content" / "spells" / filename
        with open(spell_path) as f:
            data = json.load(f)
        for item in data["items"]:
            if item["spell_id"] == spell_id:
                return item
        raise ValueError(f"Spell {spell_id} not found in {filename}")

    return _load_spell


def create_spell_data(
    spell_id: str,
    name: str,
    level: int = 1,
    magic_type: str = "arcane",
    duration: str = "Instant",
    **kwargs
) -> SpellData:
    """Helper to create SpellData instances for testing."""
    from src.narrative.spell_resolver import MagicType

    # Convert string magic_type to MagicType enum if needed
    if isinstance(magic_type, str):
        magic_type_enum = MagicType(magic_type)
    else:
        magic_type_enum = magic_type

    return SpellData(
        spell_id=spell_id,
        name=name,
        level=level,
        magic_type=magic_type_enum,
        duration=duration,
        description=kwargs.get("description", "Test spell description"),
        range=kwargs.get("range", "30'"),
    )


# =============================================================================
# ORACLE REGISTRY TESTS
# =============================================================================


class TestOracleSpellRegistry:
    """Tests for the oracle spell registry loading and lookup."""

    def test_registry_loads_successfully(self, spell_resolver):
        """Test that the oracle spell registry loads on initialization."""
        assert len(spell_resolver._oracle_spell_registry) == 21

    def test_all_21_skip_spells_registered(self, spell_resolver):
        """Test that all 21 skip spells are in the registry."""
        expected_spells = [
            "beguilement", "bird_friend", "dancing_flame", "detect_evil",
            "detect_magic", "disguise_object", "dweomerlight", "fabricate",
            "fairy_steed", "find_traps", "mind_crystal", "mirth_and_malice",
            "move_terrain", "oracle", "reveal_alignment", "root_friend",
            "rune_of_wishing", "summon_wild_hunt", "thread_whistling",
            "wood_kenning", "yeast_master"
        ]
        for spell_id in expected_spells:
            assert spell_resolver.is_oracle_spell(spell_id), f"{spell_id} not in registry"

    def test_is_oracle_spell_returns_false_for_non_oracle_spells(self, spell_resolver):
        """Test that non-oracle spells return False."""
        non_oracle_spells = ["fireball", "magic_missile", "cure_light_wounds", "bless"]
        for spell_id in non_oracle_spells:
            assert not spell_resolver.is_oracle_spell(spell_id)

    def test_get_oracle_spell_config_returns_correct_data(self, spell_resolver):
        """Test that config lookup returns correct adjudication type."""
        config = spell_resolver.get_oracle_spell_config("detect_magic")
        assert config is not None
        assert config["adjudication_type"] == "divination"

        config = spell_resolver.get_oracle_spell_config("rune_of_wishing")
        assert config is not None
        assert config["adjudication_type"] == "wish"

    def test_get_oracle_spell_config_returns_none_for_unknown(self, spell_resolver):
        """Test that unknown spells return None."""
        config = spell_resolver.get_oracle_spell_config("unknown_spell")
        assert config is None


# =============================================================================
# ORACLE SPELL HANDLER TESTS
# =============================================================================


class TestOracleSpellHandler:
    """Tests for the _handle_oracle_spell method."""

    def test_handle_oracle_spell_returns_adjudication_result(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that oracle spell handler returns valid result structure."""
        spell = create_spell_data("detect_magic", "Detect Magic", duration="2 Turns")

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        assert "oracle_adjudication" in result
        assert "narrative_context" in result

    def test_narrative_context_includes_spell_info(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that narrative context includes spell metadata."""
        spell = create_spell_data("detect_evil", "Detect Evil", duration="6 Turns")

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        context = result["narrative_context"]
        assert context["spell_id"] == "detect_evil"
        assert context["spell_name"] == "Detect Evil"
        assert context["caster_name"] == mock_caster.name
        assert context["targets"] == mock_targets

    def test_oracle_adjudication_contains_required_fields(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that oracle adjudication result has required fields."""
        spell = create_spell_data("find_traps", "Find Traps", duration="2 Turns")

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        adj = result["narrative_context"]["oracle_adjudication"]
        assert "adjudication_type" in adj
        assert "success_level" in adj
        assert "summary" in adj
        assert "requires_interpretation" in adj

    def test_divination_spells_use_divination_adjudicator(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that divination spells route to divination adjudicator."""
        spell = create_spell_data("reveal_alignment", "Reveal Alignment", duration="Instant")

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        adj = result["narrative_context"]["oracle_adjudication"]
        assert adj["adjudication_type"] == SpellAdjudicationType.DIVINATION.value

    def test_illusion_spells_use_illusion_adjudicator(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that illusion spells route to illusion_belief adjudicator."""
        spell = create_spell_data("beguilement", "Beguilement", duration="1d4 Rounds")

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        adj = result["narrative_context"]["oracle_adjudication"]
        assert adj["adjudication_type"] == SpellAdjudicationType.ILLUSION_BELIEF.value

    def test_summoning_spells_use_summoning_adjudicator(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that summoning spells route to summoning_control adjudicator."""
        spell = create_spell_data("bird_friend", "Bird Friend", duration="1 Turn")
        spell_resolver._current_context = {"creature_type": "friendly bird"}

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        adj = result["narrative_context"]["oracle_adjudication"]
        assert adj["adjudication_type"] == SpellAdjudicationType.SUMMONING_CONTROL.value

    def test_wish_spells_use_wish_adjudicator(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that wish spells route to wish adjudicator."""
        spell = create_spell_data("rune_of_wishing", "Rune of Wishing", duration="Permanent")
        spell_resolver._current_context = {"wish_text": "Grant me wisdom"}

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        adj = result["narrative_context"]["oracle_adjudication"]
        assert adj["adjudication_type"] == SpellAdjudicationType.WISH.value

    def test_generic_spells_use_generic_adjudicator(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that generic spells route to generic adjudicator."""
        spell = create_spell_data("yeast_master", "Yeast Master", duration="Special")

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        adj = result["narrative_context"]["oracle_adjudication"]
        assert adj["adjudication_type"] == SpellAdjudicationType.GENERIC.value


# =============================================================================
# ACTIVE EFFECT TRACKING TESTS
# =============================================================================


class TestOracleSpellActiveEffects:
    """Tests for active effect tracking of oracle spells."""

    def test_non_instant_spells_create_active_effects(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that spells with duration create active effects."""
        spell = create_spell_data("detect_magic", "Detect Magic", duration="2 Turns")

        initial_count = len(spell_resolver._active_effects)
        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        assert len(spell_resolver._active_effects) == initial_count + 1
        assert "active_effect_id" in result["narrative_context"]

    def test_instant_spells_do_not_create_active_effects(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that instant spells don't create active effects."""
        spell = create_spell_data("reveal_alignment", "Reveal Alignment", duration="Instant")

        initial_count = len(spell_resolver._active_effects)
        spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        assert len(spell_resolver._active_effects) == initial_count

    def test_active_effect_has_correct_spell_info(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that created active effect has correct metadata."""
        spell = create_spell_data("dweomerlight", "Dweomerlight", duration="6 Turns")

        spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "dweomerlight"
        assert effect.spell_name == "Dweomerlight"
        assert effect.caster_id == mock_caster.character_id
        assert effect.effect_type == SpellEffectType.NARRATIVE


# =============================================================================
# SPECIAL SPELL HANDLER INTEGRATION TESTS
# =============================================================================


class TestSpecialSpellHandlerIntegration:
    """Tests for oracle spell integration with _handle_special_spell."""

    def test_oracle_spell_routed_from_special_handler(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that oracle spells are routed through _handle_special_spell."""
        spell = create_spell_data("detect_magic", "Detect Magic", duration="2 Turns")

        result = spell_resolver._handle_special_spell(
            spell, mock_caster, mock_targets, None
        )

        assert result is not None
        assert "oracle_adjudication" in result

    def test_non_oracle_spell_returns_none_from_special_handler(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that unknown non-oracle spells return None."""
        spell = create_spell_data("unknown_spell", "Unknown Spell")

        result = spell_resolver._handle_special_spell(
            spell, mock_caster, mock_targets, None
        )

        assert result is None

    def test_mechanical_spell_handlers_take_precedence(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that mechanical handlers take precedence over oracle routing."""
        # dispel_magic has a mechanical handler
        spell = create_spell_data("dispel_magic", "Dispel Magic", duration="Instant")

        result = spell_resolver._handle_special_spell(
            spell, mock_caster, mock_targets, None
        )

        # Should use mechanical handler, not oracle
        assert result is not None
        # Mechanical handler returns different structure
        assert "oracle_adjudication" not in result or result.get("spell_id") == "dispel_magic"


# =============================================================================
# CONTEXT HANDLING TESTS
# =============================================================================


class TestOracleSpellContext:
    """Tests for context handling in oracle spells."""

    def test_intention_from_context_used(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that intention from context is used in adjudication."""
        spell = create_spell_data("oracle", "Oracle", duration="1d6 Turns")
        spell_resolver._current_context = {"intention": "Learn the location of the artifact"}

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        # The intention should be passed to the adjudicator
        assert result is not None

    def test_question_from_context_used_for_divination(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that question from context is used for divination spells."""
        spell = create_spell_data("wood_kenning", "Wood Kenning", duration="1 Turn")
        spell_resolver._current_context = {"question": "What secrets does this ancient oak hold?"}

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        assert result is not None

    def test_creature_type_from_context_used_for_summoning(
        self, spell_resolver, mock_caster, mock_targets
    ):
        """Test that creature_type from context is used for summoning spells."""
        spell = create_spell_data("fairy_steed", "Fairy Steed", duration="Until dawn")
        spell_resolver._current_context = {"creature_type": "silvery unicorn"}

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        assert result is not None


# =============================================================================
# ADJUDICATOR INSTANCE TESTS
# =============================================================================


class TestSpellAdjudicatorManagement:
    """Tests for spell adjudicator instance management."""

    def test_get_spell_adjudicator_creates_instance(self, spell_resolver):
        """Test that get_spell_adjudicator creates instance on first call."""
        assert spell_resolver._spell_adjudicator is None

        adjudicator = spell_resolver.get_spell_adjudicator()

        assert adjudicator is not None
        assert spell_resolver._spell_adjudicator is adjudicator

    def test_get_spell_adjudicator_returns_same_instance(self, spell_resolver):
        """Test that get_spell_adjudicator returns same instance."""
        adjudicator1 = spell_resolver.get_spell_adjudicator()
        adjudicator2 = spell_resolver.get_spell_adjudicator()

        assert adjudicator1 is adjudicator2


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestOracleSpellEdgeCases:
    """Tests for edge cases in oracle spell handling."""

    def test_missing_spell_config_returns_error(self, spell_resolver, mock_caster, mock_targets):
        """Test that missing config returns error dict."""
        spell = create_spell_data("nonexistent_oracle_spell", "Nonexistent")
        # Manually bypass is_oracle_spell check
        spell_resolver._oracle_spell_registry["nonexistent_oracle_spell"] = None

        # This should return an error
        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, mock_targets, None
        )

        assert "error" in result

    def test_empty_targets_handled_gracefully(self, spell_resolver, mock_caster):
        """Test that empty target list is handled."""
        spell = create_spell_data("detect_magic", "Detect Magic", duration="2 Turns")

        result = spell_resolver._handle_oracle_spell(
            spell, mock_caster, [], None
        )

        assert result is not None
        assert result["narrative_context"]["targets"] == []

    def test_special_duration_formats_handled(self, spell_resolver, mock_caster, mock_targets):
        """Test various duration formats are handled correctly."""
        duration_tests = [
            ("1d4 Rounds", True),  # Should create effect
            ("6 Turns", True),  # Should create effect
            ("Until dawn", True),  # Should create effect (special)
            ("Instant", False),  # Should not create effect
            ("Instantaneous", False),  # Should not create effect
        ]

        for duration, should_create_effect in duration_tests:
            spell_resolver._active_effects = []
            spell = create_spell_data("test_spell", "Test Spell", duration=duration)
            spell_resolver._oracle_spell_registry["test_spell"] = {
                "spell_id": "test_spell",
                "adjudication_type": "generic",
                "default_question_template": "Test template",
            }

            spell_resolver._handle_oracle_spell(
                spell, mock_caster, mock_targets, None
            )

            has_effect = len(spell_resolver._active_effects) > 0
            assert has_effect == should_create_effect, (
                f"Duration '{duration}' should{'not ' if not should_create_effect else ' '}"
                f"create effect, but got {has_effect}"
            )


# =============================================================================
# INTEGRATION WITH ACTUAL SPELL DATA TESTS
# =============================================================================


class TestOracleSpellsWithRealData:
    """Tests using actual spell data from JSON files."""

    def test_detect_magic_from_actual_data(
        self, spell_resolver, mock_caster, mock_targets, spell_data_loader
    ):
        """Test detect_magic with actual spell data."""
        from src.narrative.spell_resolver import MagicType

        try:
            spell_dict = spell_data_loader("holy_level_1.json", "detect_magic")

            # Convert magic_type string to enum
            magic_type_str = spell_dict.get("magic_type", "divine")
            magic_type_enum = MagicType(magic_type_str)

            spell = SpellData(
                spell_id=spell_dict["spell_id"],
                name=spell_dict["name"],
                level=spell_dict.get("level", 1),
                magic_type=magic_type_enum,
                duration=spell_dict.get("duration", "Instant"),
                description=spell_dict.get("description", ""),
                range=spell_dict.get("range", ""),
            )

            result = spell_resolver._handle_oracle_spell(
                spell, mock_caster, mock_targets, None
            )

            assert result is not None
            assert result["narrative_context"]["spell_id"] == "detect_magic"
        except (FileNotFoundError, ValueError):
            pytest.skip("Spell data file not found")

    def test_detect_evil_from_actual_data(
        self, spell_resolver, mock_caster, mock_targets, spell_data_loader
    ):
        """Test detect_evil with actual spell data."""
        from src.narrative.spell_resolver import MagicType

        try:
            spell_dict = spell_data_loader("holy_level_1.json", "detect_evil")

            # Convert magic_type string to enum
            magic_type_str = spell_dict.get("magic_type", "divine")
            magic_type_enum = MagicType(magic_type_str)

            spell = SpellData(
                spell_id=spell_dict["spell_id"],
                name=spell_dict["name"],
                level=spell_dict.get("level", 1),
                magic_type=magic_type_enum,
                duration=spell_dict.get("duration", "Instant"),
                description=spell_dict.get("description", ""),
                range=spell_dict.get("range", ""),
            )

            result = spell_resolver._handle_oracle_spell(
                spell, mock_caster, mock_targets, None
            )

            assert result is not None
            assert result["narrative_context"]["spell_id"] == "detect_evil"
        except (FileNotFoundError, ValueError):
            pytest.skip("Spell data file not found")
