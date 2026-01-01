"""
Phase 8 Spell Handler Tests

Tests for summoning and area effect spell handlers:
- Animate Dead (arcane level 5) - raises corpses as undead minions
- Cloudkill (arcane level 5) - deadly poison fog
- Insect Plague (divine level 5) - swarm of biting insects
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.narrative.spell_resolver import SpellResolver, DurationType, SpellEffectType


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_resolver():
    """Create a SpellResolver instance for testing."""
    return SpellResolver()


@pytest.fixture
def mock_caster():
    """Create a mock caster character."""
    caster = MagicMock()
    caster.character_id = "test_caster"
    caster.level = 7
    return caster


@pytest.fixture
def mock_corpses():
    """Create a list of mock corpse target IDs."""
    return ["corpse_goblin_1", "corpse_goblin_2", "skeleton_ancient", "corpse_bandit"]


@pytest.fixture
def mock_creatures():
    """Create a list of mock creature target IDs."""
    return ["goblin_1", "goblin_2", "orc_warrior", "kobold_scout", "troll_guard"]


@pytest.fixture
def fixed_dice_roller():
    """Create a dice roller that returns predictable values."""
    roller = MagicMock()
    roller.roll = MagicMock(side_effect=lambda expr: {
        "1d20": 10,
        "1d6": 4,
    }.get(expr, 10))
    return roller


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


# =============================================================================
# ANIMATE DEAD TESTS
# =============================================================================


class TestAnimateDeadHandler:
    """Tests for the Animate Dead spell handler."""

    def test_basic_animation_succeeds(self, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller):
        """Test basic undead animation."""
        result = spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        assert result["spell_id"] == "animate_dead"
        assert result["spell_name"] == "Animate Dead"
        assert result["success"] is True

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7

    def test_animates_one_per_level(self, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller):
        """Test that undead count equals caster level."""
        result = spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        assert result["max_undead"] == 7
        # Limited by corpses available (4)
        assert result["undead_created"] == 4

    def test_limited_by_available_corpses(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that animation is limited by available corpses."""
        # Only 2 corpses for a level 7 caster
        result = spell_resolver._handle_animate_dead(
            mock_caster, ["corpse_1", "corpse_2"], fixed_dice_roller
        )

        assert result["max_undead"] == 7
        assert result["corpses_available"] == 2
        assert result["undead_created"] == 2

    def test_high_level_caster_many_undead(self, spell_resolver, fixed_dice_roller):
        """Test that high level caster can animate many undead."""
        caster = MagicMock()
        caster.character_id = "necromancer"
        caster.level = 12

        corpses = [f"corpse_{i}" for i in range(15)]
        result = spell_resolver._handle_animate_dead(caster, corpses, fixed_dice_roller)

        assert result["max_undead"] == 12
        assert result["undead_created"] == 12

    def test_undead_stats_are_standard(self, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller):
        """Test that created undead use standard stats."""
        result = spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        stats = result["undead_stats"]
        assert stats["hit_dice"] == 1
        assert stats["armor_class"] == 7
        assert stats["morale"] == 12  # Undead don't flee
        assert stats["special_abilities"] == []

    def test_tracks_animated_corpses(self, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller):
        """Test that each animated corpse is tracked."""
        result = spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        assert len(result["animated_corpses"]) == 4
        assert result["animated_corpses"][0]["corpse_id"] == "corpse_goblin_1"
        assert result["animated_corpses"][2]["corpse_id"] == "skeleton_ancient"

    def test_detects_skeleton_type(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that skeletons are detected from corpse ID."""
        corpses = ["skeleton_warrior", "corpse_farmer"]
        result = spell_resolver._handle_animate_dead(mock_caster, corpses, fixed_dice_roller)

        assert result["animated_corpses"][0]["undead_type"] == "skeleton"
        assert result["animated_corpses"][1]["undead_type"] == "zombie"

    def test_creates_permanent_effect(self, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller):
        """Test that permanent effect is created."""
        initial_effects = len(spell_resolver._active_effects)

        spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        assert len(spell_resolver._active_effects) == initial_effects + 1
        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "animate_dead"
        assert effect.duration_type == DurationType.PERMANENT

    def test_effect_tracks_undead_group(self, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller):
        """Test that effect data tracks undead group."""
        spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["summoned_creatures"] is True
        assert effect.mechanical_effects["creature_type"] == "undead"
        assert effect.mechanical_effects["obeys_caster"] is True
        assert effect.mechanical_effects["dispellable"] is True

    def test_narrative_context(self, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller):
        """Test narrative context is provided."""
        result = spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("dark energy" in hint for hint in hints)
        assert any("dead rise" in hint for hint in hints)

    def test_empty_targets_uses_max(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that empty targets assumes max available corpses."""
        result = spell_resolver._handle_animate_dead(
            mock_caster, [], fixed_dice_roller
        )

        # With no corpses specified, uses caster level as available
        assert result["corpses_available"] == 7
        assert result["undead_created"] == 7


# =============================================================================
# CLOUDKILL TESTS
# =============================================================================


class TestCloudkillHandler:
    """Tests for the Cloudkill spell handler."""

    def test_basic_cloudkill_succeeds(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test basic cloudkill casting."""
        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert result["spell_id"] == "cloudkill"
        assert result["spell_name"] == "Cloudkill"
        assert result["success"] is True

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7

    def test_cloud_parameters(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test cloud dimensions and parameters."""
        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert result["cloud_diameter"] == 30
        assert result["duration_turns"] == 6
        assert result["cloud_speed"] == 10
        assert result["damage_per_round"] == 1

    def test_low_level_creatures_must_save(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that low level creatures must Save vs Doom."""
        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        # All creatures default to level 1, must save
        for creature in result["affected_creatures"]:
            assert creature["must_save_vs_death"] is True

    def test_high_level_creatures_no_death_save(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that high level creatures don't need death save."""
        # Set up controller with level 6 creature
        controller = MagicMock()
        target_char = MagicMock()
        target_char.level = 6
        controller.get_character = MagicMock(return_value=target_char)
        spell_resolver._controller = controller

        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        for creature in result["affected_creatures"]:
            assert creature["must_save_vs_death"] is False

    def test_failed_save_causes_death(self, spell_resolver, mock_caster, mock_creatures):
        """Test that failed save causes death."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Low roll fails

        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, roller
        )

        # With low roll, creatures die
        deaths = sum(1 for c in result["affected_creatures"] if c.get("died"))
        assert deaths > 0

    def test_successful_save_survives(self, spell_resolver, mock_caster, mock_creatures):
        """Test that successful save means survival."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=18)  # High roll succeeds

        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, roller
        )

        # With high roll, all creatures survive
        for creature in result["affected_creatures"]:
            assert creature["died"] is False

    def test_all_creatures_take_damage(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that all creatures take 1 damage per round."""
        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        for creature in result["affected_creatures"]:
            assert creature["damage_taken"] == 1

    def test_creates_area_effect(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that area effect is created."""
        initial_effects = len(spell_resolver._active_effects)

        spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert len(spell_resolver._active_effects) == initial_effects + 1
        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "cloudkill"
        assert effect.duration_type == DurationType.TURNS
        assert effect.duration_remaining == 6

    def test_effect_tracks_cloud_mechanics(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that effect tracks cloud movement mechanics."""
        spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["area_effect"] is True
        assert effect.mechanical_effects["sinks_to_lowest"] is True
        assert effect.mechanical_effects["cloud_speed"] == 10

    def test_narrative_describes_deaths(self, spell_resolver, mock_caster, mock_creatures):
        """Test that narrative describes creature deaths."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Low roll, creatures die

        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("collapse" in hint for hint in hints)

    def test_empty_targets_no_casualties(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test cloudkill with no targets."""
        result = spell_resolver._handle_cloudkill(
            mock_caster, [], fixed_dice_roller
        )

        assert len(result["affected_creatures"]) == 0


# =============================================================================
# INSECT PLAGUE TESTS
# =============================================================================


class TestInsectPlagueHandler:
    """Tests for the Insect Plague spell handler."""

    def test_basic_insect_plague_succeeds(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test basic insect plague casting."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert result["spell_id"] == "insect_plague"
        assert result["spell_name"] == "Insect Plague"
        assert result["success"] is True

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7

    def test_swarm_parameters(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test swarm dimensions and parameters."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert result["swarm_diameter"] == 60
        assert result["damage_per_round"] == 1
        assert result["vision_limit"] == 30
        assert result["flee_distance"] == 240

    def test_duration_scales_with_level(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that duration is 1 Turn per level."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert result["duration_turns"] == 7

    def test_low_level_creatures_flee(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that level 1-2 creatures flee in horror."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        # All creatures default to level 1, must flee
        for creature in result["affected_creatures"]:
            assert creature["must_flee"] is True
            assert creature["flee_distance"] == 240

    def test_high_level_creatures_dont_flee(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that level 3+ creatures don't flee."""
        controller = MagicMock()
        target_char = MagicMock()
        target_char.level = 4
        controller.get_character = MagicMock(return_value=target_char)
        spell_resolver._controller = controller

        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        for creature in result["affected_creatures"]:
            assert creature["must_flee"] is False

    def test_all_creatures_take_damage(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that all creatures take 1 damage per round."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        for creature in result["affected_creatures"]:
            assert creature["damage_taken"] == 1

    def test_creates_area_effect(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that area effect is created."""
        initial_effects = len(spell_resolver._active_effects)

        spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        assert len(spell_resolver._active_effects) == initial_effects + 1
        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "insect_plague"
        assert effect.duration_type == DurationType.TURNS

    def test_effect_tracks_swarm_as_stationary(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that effect marks swarm as stationary."""
        spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["stationary"] is True
        assert effect.mechanical_effects["swarm_diameter"] == 60

    def test_narrative_mentions_vision_limit(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that narrative mentions vision limitation."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("30'" in hint and "vision" in hint for hint in hints)

    def test_narrative_mentions_fleeing_creatures(self, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller):
        """Test that narrative mentions fleeing creatures."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("flee" in hint for hint in hints)

    def test_empty_targets_no_fleeing(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test insect plague with no targets."""
        result = spell_resolver._handle_insect_plague(
            mock_caster, [], fixed_dice_roller
        )

        assert len(result["affected_creatures"]) == 0


# =============================================================================
# INTEGRATION TESTS WITH SPELL DATA
# =============================================================================


class TestPhase8SpellDataIntegration:
    """Integration tests that verify handlers against actual spell JSON data."""

    def test_animate_dead_matches_source(self, spell_data_loader):
        """Verify Animate Dead matches arcane_level_5_1.json."""
        spell = spell_data_loader("arcane_level_5_1.json", "animate_dead")

        assert spell["level"] == 5
        assert spell["magic_type"] == "arcane"
        assert "Permanent" in spell["duration"]
        assert spell["range"] == "60′"

    def test_animate_dead_description_validation(self, spell_data_loader):
        """Verify Animate Dead description contains key mechanics."""
        spell = spell_data_loader("arcane_level_5_1.json", "animate_dead")

        # Verify description contains key mechanics from source
        assert "corpses or skeletons" in spell["description"]
        assert "1 corpse or skeleton per Level" in spell["description"]
        assert "undead under the caster's command" in spell["description"]
        assert "dispelled" in spell["description"]

    def test_animate_dead_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_corpses, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_5_1.json", "animate_dead")

        result = spell_resolver._handle_animate_dead(
            mock_caster, mock_corpses, fixed_dice_roller
        )

        # Verify permanent duration from source
        effect = spell_resolver._active_effects[-1]
        assert effect.duration_type == DurationType.PERMANENT
        # Verify 1 per level from source
        assert result["max_undead"] == mock_caster.level

    def test_cloudkill_matches_source(self, spell_data_loader):
        """Verify Cloudkill matches arcane_level_5_1.json."""
        spell = spell_data_loader("arcane_level_5_1.json", "cloudkill")

        assert spell["level"] == 5
        assert spell["magic_type"] == "arcane"
        assert spell["duration"] == "6 Turns"
        assert spell["range"] == "30′"

    def test_cloudkill_description_validation(self, spell_data_loader):
        """Verify Cloudkill description contains key mechanics."""
        spell = spell_data_loader("arcane_level_5_1.json", "cloudkill")

        # Verify description contains key mechanics from source
        assert "poisonous fog" in spell["description"]
        assert "30′ diameter" in spell["description"]
        assert "Speed 10" in spell["description"]
        assert "sinks" in spell["description"].lower()
        assert "1 damage per Round" in spell["description"]
        assert "Level 4 or lower" in spell["description"]
        assert "Save Versus Doom" in spell["description"]

    def test_cloudkill_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_5_1.json", "cloudkill")

        result = spell_resolver._handle_cloudkill(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        # Verify 6 Turns duration from source
        assert result["duration_turns"] == 6
        # Verify 30' diameter from source
        assert result["cloud_diameter"] == 30
        # Verify Level 4 or lower death threshold from source
        assert result["instant_death_level_threshold"] == 4
        # Verify Speed 10 from source
        assert result["cloud_speed"] == 10

    def test_insect_plague_matches_source(self, spell_data_loader):
        """Verify Insect Plague matches holy_level_5.json."""
        spell = spell_data_loader("holy_level_5.json", "insect_plague")

        assert spell["level"] == 5
        assert spell["magic_type"] == "divine"
        assert "1 Turn per Level" in spell["duration"]
        assert spell["range"] == "360′"

    def test_insect_plague_description_validation(self, spell_data_loader):
        """Verify Insect Plague description contains key mechanics."""
        spell = spell_data_loader("holy_level_5.json", "insect_plague")

        # Verify description contains key mechanics from source
        assert "60′ diameter" in spell["description"]
        assert "biting insects" in spell["description"]
        assert "30′" in spell["description"]  # Vision limit
        assert "1 damage per Round" in spell["description"]
        assert "Level 1–2" in spell["description"] or "Level 1-2" in spell["description"]
        assert "240′" in spell["description"]  # Flee distance

    def test_insect_plague_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_creatures, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("holy_level_5.json", "insect_plague")

        result = spell_resolver._handle_insect_plague(
            mock_caster, mock_creatures, fixed_dice_roller
        )

        # Verify 60' diameter from source
        assert result["swarm_diameter"] == 60
        # Verify 30' vision limit from source
        assert result["vision_limit"] == 30
        # Verify Level 1-2 flee from source
        assert result["flee_level_threshold"] == 2
        # Verify 240' flee distance from source
        assert result["flee_distance"] == 240


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestPhase8EdgeCases:
    """Edge case tests for Phase 8 handlers."""

    def test_level_1_caster_animate_dead(self, spell_resolver, fixed_dice_roller):
        """Test Animate Dead with level 1 caster."""
        caster = MagicMock()
        caster.character_id = "apprentice"
        caster.level = 1

        result = spell_resolver._handle_animate_dead(
            caster, ["corpse_1"], fixed_dice_roller
        )

        assert result["max_undead"] == 1
        assert result["undead_created"] == 1

    def test_cloudkill_mixed_levels(self, spell_resolver, mock_caster):
        """Test Cloudkill with mixed creature levels."""
        controller = MagicMock()

        def get_char(target_id):
            char = MagicMock(spec=["level"])  # Only allow level attribute
            if "strong" in target_id:
                char.level = 8  # Won't die from poison
            else:
                char.level = 2  # Must save or die
            return char

        controller.get_character = get_char
        spell_resolver._controller = controller

        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Failed save

        targets = ["goblin_weak", "troll_strong", "kobold_weak"]
        result = spell_resolver._handle_cloudkill(mock_caster, targets, roller)

        # Strong creature doesn't need to save
        strong = next(c for c in result["affected_creatures"] if "strong" in c["target_id"])
        weak = [c for c in result["affected_creatures"] if "weak" in c["target_id"]]

        assert strong["must_save_vs_death"] is False
        assert all(c["must_save_vs_death"] is True for c in weak)

    def test_insect_plague_level_2_boundary(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test Insect Plague at the level 2 boundary."""
        controller = MagicMock()

        def get_char(target_id):
            char = MagicMock()
            if "strong" in target_id:
                char.level = 3  # Doesn't flee
            else:
                char.level = 2  # Flees
            return char

        controller.get_character = get_char
        spell_resolver._controller = controller

        targets = ["goblin_weak", "orc_strong"]
        result = spell_resolver._handle_insect_plague(mock_caster, targets, fixed_dice_roller)

        weak = next(c for c in result["affected_creatures"] if "weak" in c["target_id"])
        strong = next(c for c in result["affected_creatures"] if "strong" in c["target_id"])

        assert weak["must_flee"] is True
        assert strong["must_flee"] is False

    def test_high_level_caster_insect_plague_duration(self, spell_resolver, fixed_dice_roller):
        """Test Insect Plague duration with high level caster."""
        caster = MagicMock()
        caster.character_id = "high_priest"
        caster.level = 12

        result = spell_resolver._handle_insect_plague(
            caster, ["target"], fixed_dice_roller
        )

        assert result["duration_turns"] == 12

    def test_animate_dead_skeleton_detection(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that skeleton detection is case-insensitive."""
        corpses = ["SKELETON_king", "Skeleton_Warrior", "corpse_normal"]
        result = spell_resolver._handle_animate_dead(mock_caster, corpses, fixed_dice_roller)

        assert result["animated_corpses"][0]["undead_type"] == "skeleton"
        assert result["animated_corpses"][1]["undead_type"] == "skeleton"
        assert result["animated_corpses"][2]["undead_type"] == "zombie"

    def test_cloudkill_exact_level_threshold(self, spell_resolver, mock_caster):
        """Test Cloudkill at exact level 4 threshold."""
        controller = MagicMock()
        target_char = MagicMock(spec=["level"])  # Only allow level attribute
        target_char.level = 4  # Exactly at threshold
        controller.get_character = MagicMock(return_value=target_char)
        spell_resolver._controller = controller

        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)

        result = spell_resolver._handle_cloudkill(
            mock_caster, ["creature"], roller
        )

        # Level 4 is at or below threshold, must save
        assert result["affected_creatures"][0]["must_save_vs_death"] is True

    def test_all_handlers_work_with_no_controller(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test all Phase 8 handlers work without controller."""
        spell_resolver._controller = None

        # All should succeed without controller
        result1 = spell_resolver._handle_animate_dead(
            mock_caster, ["corpse"], fixed_dice_roller
        )
        assert result1["success"] is True

        result2 = spell_resolver._handle_cloudkill(
            mock_caster, ["creature"], fixed_dice_roller
        )
        assert result2["success"] is True

        result3 = spell_resolver._handle_insect_plague(
            mock_caster, ["creature"], fixed_dice_roller
        )
        assert result3["success"] is True
