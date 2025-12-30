"""
Unit tests for MonsterRegistry.

Tests monster loading, lookup, StatBlock conversion, and NPC generation.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.content_loader.monster_registry import (
    MonsterRegistry,
    MonsterLookupResult,
    StatBlockResult,
    NPCStatRequest,
    get_monster_registry,
    reset_monster_registry,
)
from src.data_models import (
    Monster,
    StatBlock,
    Combatant,
    DiceRoller,
)


# Sample monster data for testing
SAMPLE_MONSTER_DATA = {
    "_metadata": {
        "source_file": "test_monsters.pdf",
        "pages": [1, 2],
        "content_type": "monsters",
        "item_count": 2,
    },
    "items": [
        {
            "name": "Test Goblin",
            "monster_id": "test_goblin",
            "armor_class": 12,
            "hit_dice": "2d8",
            "hp": 9,
            "level": 2,
            "movement": "40'",
            "speed": 40,
            "attacks": ["Shortsword (+1, 1d6)"],
            "damage": ["1d6"],
            "save_doom": 12,
            "save_ray": 13,
            "save_hold": 14,
            "save_blast": 15,
            "save_spell": 16,
            "morale": 7,
            "size": "Small",
            "monster_type": "Fairy",
            "sentience": "Sentient",
            "alignment": "Chaotic",
            "special_abilities": ["Cold iron vulnerability"],
            "vulnerabilities": ["cold iron"],
            "number_appearing": "2d6",
            "xp_value": 35,
        },
        {
            "name": "Test Skeleton",
            "monster_id": "test_skeleton",
            "armor_class": 13,
            "hit_dice": "1d8",
            "hp": 4,
            "level": 1,
            "movement": "30'",
            "speed": 30,
            "attacks": ["Rusty Sword (+0, 1d6)"],
            "damage": ["1d6"],
            "save_doom": 14,
            "save_ray": 15,
            "save_hold": 16,
            "save_blast": 17,
            "save_spell": 18,
            "morale": 12,
            "size": "Medium",
            "monster_type": "Undead",
            "sentience": "Non-Sentient",
            "alignment": "Chaotic",
            "special_abilities": ["Undead immunities"],
            "immunities": ["poison", "disease"],
            "xp_value": 10,
        },
    ],
}


@pytest.fixture
def temp_monster_dir():
    """Create a temporary directory with test monster JSON files."""
    with TemporaryDirectory() as tmpdir:
        # Write sample monster file
        monster_file = Path(tmpdir) / "test_monsters.json"
        with open(monster_file, "w") as f:
            json.dump(SAMPLE_MONSTER_DATA, f)

        yield Path(tmpdir)


@pytest.fixture
def loaded_registry(temp_monster_dir):
    """Create a MonsterRegistry loaded with test data."""
    registry = MonsterRegistry()
    registry.load_from_directory(temp_monster_dir)
    return registry


class TestMonsterRegistryLoading:
    """Tests for loading monsters into the registry."""

    def test_load_from_directory(self, temp_monster_dir):
        """Test loading monsters from a directory."""
        registry = MonsterRegistry()
        stats = registry.load_from_directory(temp_monster_dir)

        assert stats["files_loaded"] == 1
        assert stats["monsters_loaded"] == 2
        assert len(stats["errors"]) == 0

    def test_load_nonexistent_directory(self):
        """Test loading from a directory that doesn't exist."""
        registry = MonsterRegistry()
        stats = registry.load_from_directory(Path("/nonexistent/path"))

        assert stats["files_loaded"] == 0
        assert stats["monsters_loaded"] == 0
        assert len(stats["errors"]) > 0

    def test_registry_length(self, loaded_registry):
        """Test that __len__ returns correct count."""
        assert len(loaded_registry) == 2

    def test_registry_contains(self, loaded_registry):
        """Test that __contains__ works for monster IDs."""
        assert "test_goblin" in loaded_registry
        assert "test_skeleton" in loaded_registry
        assert "nonexistent" not in loaded_registry


class TestMonsterLookup:
    """Tests for looking up monsters."""

    def test_get_monster_by_id(self, loaded_registry):
        """Test looking up a monster by ID."""
        result = loaded_registry.get_monster("test_goblin")

        assert result.found is True
        assert result.monster is not None
        assert result.monster.name == "Test Goblin"
        assert result.monster.armor_class == 12
        assert result.error is None

    def test_get_monster_not_found(self, loaded_registry):
        """Test looking up a nonexistent monster."""
        result = loaded_registry.get_monster("nonexistent")

        assert result.found is False
        assert result.monster is None
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_get_monster_by_name(self, loaded_registry):
        """Test looking up a monster by name."""
        result = loaded_registry.get_monster_by_name("Test Skeleton")

        assert result.found is True
        assert result.monster is not None
        assert result.monster.monster_id == "test_skeleton"

    def test_get_monster_by_name_case_insensitive(self, loaded_registry):
        """Test that name lookup is case-insensitive."""
        result = loaded_registry.get_monster_by_name("TEST GOBLIN")

        assert result.found is True
        assert result.monster.monster_id == "test_goblin"

    def test_search_monsters(self, loaded_registry):
        """Test searching for monsters."""
        results = loaded_registry.search_monsters("test")

        assert len(results) == 2

    def test_search_monsters_partial_match(self, loaded_registry):
        """Test searching with partial match."""
        results = loaded_registry.search_monsters("goblin")

        assert len(results) == 1
        assert results[0].monster_id == "test_goblin"

    def test_get_monsters_by_type(self, loaded_registry):
        """Test filtering monsters by type."""
        undead = loaded_registry.get_monsters_by_type("Undead")
        fairy = loaded_registry.get_monsters_by_type("Fairy")

        assert len(undead) == 1
        assert undead[0].monster_id == "test_skeleton"
        assert len(fairy) == 1
        assert fairy[0].monster_id == "test_goblin"

    def test_get_monsters_by_level(self, loaded_registry):
        """Test filtering monsters by level."""
        level_1 = loaded_registry.get_monsters_by_level(1)
        level_2 = loaded_registry.get_monsters_by_level(2)

        assert len(level_1) == 1
        assert level_1[0].monster_id == "test_skeleton"
        assert len(level_2) == 1
        assert level_2[0].monster_id == "test_goblin"

    def test_get_all_monster_ids(self, loaded_registry):
        """Test getting all monster IDs."""
        ids = loaded_registry.get_all_monster_ids()

        assert "test_goblin" in ids
        assert "test_skeleton" in ids
        assert len(ids) == 2


class TestStatBlockConversion:
    """Tests for converting monsters to StatBlocks."""

    def test_get_stat_block(self, loaded_registry):
        """Test getting a StatBlock for a monster."""
        result = loaded_registry.get_stat_block("test_goblin")

        assert result.success is True
        assert result.stat_block is not None
        assert result.source_type == "monster"
        assert result.source_id == "test_goblin"

    def test_stat_block_values(self, loaded_registry):
        """Test that StatBlock has correct values."""
        result = loaded_registry.get_stat_block("test_goblin")
        stat_block = result.stat_block

        assert stat_block.armor_class == 12
        assert stat_block.hit_dice == "2d8"
        assert stat_block.movement == 40
        assert stat_block.morale == 7
        assert len(stat_block.attacks) == 1
        assert stat_block.attacks[0]["damage"] == "1d6"

    def test_stat_block_hp_is_rolled(self, loaded_registry):
        """Test that HP is rolled from hit dice."""
        # Get multiple stat blocks and verify HP varies or is within dice range
        hp_values = set()
        for _ in range(10):
            result = loaded_registry.get_stat_block("test_goblin")
            hp_values.add(result.stat_block.hp_current)

        # 2d8 gives 2-16, so all values should be in this range
        for hp in hp_values:
            assert 2 <= hp <= 16

    def test_stat_block_not_found(self, loaded_registry):
        """Test getting StatBlock for nonexistent monster."""
        result = loaded_registry.get_stat_block("nonexistent")

        assert result.success is False
        assert result.stat_block is None
        assert result.error is not None


class TestCombatantCreation:
    """Tests for creating Combatants from monsters."""

    def test_create_combatant(self, loaded_registry):
        """Test creating a Combatant from a monster."""
        combatant = loaded_registry.create_combatant(
            monster_id="test_goblin", combatant_id="enemy_1", side="enemy"
        )

        assert combatant is not None
        assert combatant.combatant_id == "enemy_1"
        assert combatant.name == "Test Goblin"
        assert combatant.side == "enemy"
        assert combatant.stat_block is not None

    def test_create_combatant_with_name_override(self, loaded_registry):
        """Test creating a Combatant with custom name."""
        combatant = loaded_registry.create_combatant(
            monster_id="test_goblin",
            combatant_id="enemy_1",
            side="enemy",
            name_override="Goblin Chief",
        )

        assert combatant.name == "Goblin Chief"

    def test_create_combatant_not_found(self, loaded_registry):
        """Test creating a Combatant from nonexistent monster."""
        combatant = loaded_registry.create_combatant(
            monster_id="nonexistent", combatant_id="enemy_1", side="enemy"
        )

        assert combatant is None


class TestNumberAppearing:
    """Tests for rolling number appearing."""

    def test_roll_number_appearing(self, loaded_registry):
        """Test rolling number appearing for a monster."""
        # Goblin has number_appearing: "2d6"
        for _ in range(10):
            count = loaded_registry.roll_number_appearing("test_goblin")
            assert 2 <= count <= 12  # 2d6 range

    def test_roll_number_appearing_no_dice(self, loaded_registry):
        """Test rolling for monster without number_appearing."""
        # Skeleton has no number_appearing
        count = loaded_registry.roll_number_appearing("test_skeleton")
        assert count == 1

    def test_roll_number_appearing_not_found(self, loaded_registry):
        """Test rolling for nonexistent monster."""
        count = loaded_registry.roll_number_appearing("nonexistent")
        assert count == 1


class TestNPCStatGeneration:
    """Tests for generating NPC stats from descriptions."""

    def test_get_npc_stat_block_fighter(self, loaded_registry):
        """Test generating stats for a fighter NPC."""
        request = NPCStatRequest(description="level 4 human fighter", name="Guard Captain")
        result = loaded_registry.get_npc_stat_block(request)

        assert result.success is True
        assert result.stat_block is not None
        assert result.source_type == "npc_generated"
        assert result.stat_block.hp_max > 0

    def test_get_npc_stat_block_cleric(self, loaded_registry):
        """Test generating stats for a cleric NPC."""
        request = NPCStatRequest(description="level 3 cleric", name="Brother Marcus")
        result = loaded_registry.get_npc_stat_block(request)

        assert result.success is True
        assert result.stat_block is not None
        # Cleric should have mace attack
        assert any("Mace" in atk["name"] for atk in result.stat_block.attacks)

    def test_get_npc_stat_block_with_overrides(self, loaded_registry):
        """Test generating NPC stats with manual overrides."""
        request = NPCStatRequest(
            description="level 2 fighter",
            name="Tough Guard",
            hp_override=25,
            ac_override=16,
            morale_override=10,
        )
        result = loaded_registry.get_npc_stat_block(request)

        assert result.success is True
        assert result.stat_block.hp_current == 25
        assert result.stat_block.armor_class == 16
        assert result.stat_block.morale == 10

    def test_get_npc_stat_block_invalid_description(self, loaded_registry):
        """Test generating stats from invalid description."""
        request = NPCStatRequest(description="some random text without level or class")
        result = loaded_registry.get_npc_stat_block(request)

        assert result.success is False
        assert result.error is not None

    def test_create_combatant_from_npc(self, loaded_registry):
        """Test creating a Combatant from NPC description."""
        request = NPCStatRequest(description="level 5 thief", name="Shadow")
        combatant = loaded_registry.create_combatant_from_npc(
            request=request, combatant_id="npc_1", side="enemy"
        )

        assert combatant is not None
        assert combatant.combatant_id == "npc_1"
        assert combatant.name == "Shadow"
        assert combatant.stat_block is not None


class TestMonsterToStatBlock:
    """Tests for Monster.to_stat_block() method."""

    def test_monster_to_stat_block(self):
        """Test converting a Monster directly to StatBlock."""
        monster = Monster(
            name="Test Monster",
            monster_id="test_monster",
            armor_class=14,
            hit_dice="3d8",
            hp=13,
            level=3,
            speed=40,
            attacks=["Claw (+2, 1d6)", "Bite (+2, 1d8)"],
            damage=["1d6", "1d8"],
            morale=8,
            special_abilities=["Dark vision", "Pack tactics"],
        )

        stat_block = monster.to_stat_block()

        assert stat_block.armor_class == 14
        assert stat_block.hit_dice == "3d8"
        assert stat_block.hp_current == 13
        assert stat_block.hp_max == 13
        assert stat_block.movement == 40
        assert stat_block.morale == 8
        assert len(stat_block.attacks) == 2
        assert len(stat_block.special_abilities) == 2


class TestAttackBonusParsing:
    """Tests for parsing attack bonuses from attack strings."""

    def test_parse_positive_bonus(self, loaded_registry):
        """Test parsing positive attack bonus."""
        bonus = loaded_registry._parse_attack_bonus("Claw (+3, 1d6)", 2)
        assert bonus == 3

    def test_parse_zero_bonus(self, loaded_registry):
        """Test parsing zero attack bonus."""
        bonus = loaded_registry._parse_attack_bonus("Rusty Sword (+0, 1d6)", 1)
        assert bonus == 0

    def test_parse_no_bonus_in_string(self, loaded_registry):
        """Test fallback to level when no bonus in string."""
        bonus = loaded_registry._parse_attack_bonus("Claw", 4)
        assert bonus == 4


class TestDefaultRegistry:
    """Tests for the module-level singleton registry."""

    def test_get_monster_registry(self):
        """Test getting the default registry singleton."""
        reset_monster_registry()  # Clear any existing instance

        registry1 = get_monster_registry()
        registry2 = get_monster_registry()

        # Should return the same instance
        assert registry1 is registry2

    def test_reset_monster_registry(self):
        """Test resetting the default registry."""
        registry1 = get_monster_registry()
        reset_monster_registry()
        registry2 = get_monster_registry()

        # After reset, should be a new instance
        assert registry1 is not registry2


class TestMonsterProperties:
    """Tests for accessing Monster properties."""

    def test_monster_get_saves(self, loaded_registry):
        """Test getting MonsterSaves from a Monster."""
        result = loaded_registry.get_monster("test_goblin")
        saves = result.monster.get_saves()

        assert saves.doom == 12
        assert saves.ray == 13
        assert saves.hold == 14
        assert saves.blast == 15
        assert saves.spell == 16

    def test_monster_get_attack_bonus(self, loaded_registry):
        """Test getting attack bonus from a Monster."""
        result = loaded_registry.get_monster("test_goblin")
        bonus = result.monster.get_attack_bonus()

        assert bonus == 2  # Level 2 goblin


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_directory(self):
        """Test loading from an empty directory."""
        with TemporaryDirectory() as tmpdir:
            registry = MonsterRegistry()
            stats = registry.load_from_directory(Path(tmpdir))

            assert stats["files_loaded"] == 0
            assert stats["monsters_loaded"] == 0

    def test_invalid_json_file(self):
        """Test handling of invalid JSON files."""
        with TemporaryDirectory() as tmpdir:
            # Write invalid JSON
            bad_file = Path(tmpdir) / "bad.json"
            with open(bad_file, "w") as f:
                f.write("{ invalid json }")

            registry = MonsterRegistry()
            stats = registry.load_from_directory(Path(tmpdir))

            assert stats["files_loaded"] == 0
            assert len(stats["errors"]) > 0

    def test_json_without_items(self):
        """Test handling of JSON file without items array."""
        with TemporaryDirectory() as tmpdir:
            empty_file = Path(tmpdir) / "empty.json"
            with open(empty_file, "w") as f:
                json.dump({"_metadata": {}}, f)

            registry = MonsterRegistry()
            stats = registry.load_from_directory(Path(tmpdir))

            assert stats["monsters_loaded"] == 0

    def test_duplicate_monster_ids(self):
        """Test handling of duplicate monster IDs."""
        with TemporaryDirectory() as tmpdir:
            # First file
            file1 = Path(tmpdir) / "monsters1.json"
            with open(file1, "w") as f:
                json.dump({"items": [{"name": "Goblin V1", "monster_id": "goblin"}]}, f)

            # Second file with same monster_id
            file2 = Path(tmpdir) / "monsters2.json"
            with open(file2, "w") as f:
                json.dump({"items": [{"name": "Goblin V2", "monster_id": "goblin"}]}, f)

            registry = MonsterRegistry()
            registry.load_from_directory(Path(tmpdir))

            # Should have loaded (later file wins)
            result = registry.get_monster("goblin")
            assert result.found is True
            # The second file's version should be loaded
            assert result.monster.name == "Goblin V2"
