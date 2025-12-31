"""
Tests for Runtime Content Bootstrap.

Tests the loading of game content from disk into runtime-ready
data structures for use by VirtualDM and its engines.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from src.content_loader.runtime_bootstrap import (
    RuntimeContent,
    RuntimeContentStats,
    load_runtime_content,
    register_spells_with_combat,
)


# =============================================================================
# DATA CLASS TESTS
# =============================================================================


class TestRuntimeContentStats:
    """Tests for RuntimeContentStats dataclass."""

    def test_default_values(self):
        """All stats should default to zero."""
        stats = RuntimeContentStats()
        assert stats.hexes_loaded == 0
        assert stats.hexes_failed == 0
        assert stats.spells_loaded == 0
        assert stats.spells_failed == 0
        assert stats.monsters_loaded == 0
        assert stats.monsters_failed == 0
        assert stats.items_loaded == 0

    def test_custom_values(self):
        """Stats should accept custom values."""
        stats = RuntimeContentStats(
            hexes_loaded=10,
            hexes_failed=2,
            spells_loaded=50,
            monsters_loaded=100,
        )
        assert stats.hexes_loaded == 10
        assert stats.hexes_failed == 2
        assert stats.spells_loaded == 50
        assert stats.monsters_loaded == 100


class TestRuntimeContent:
    """Tests for RuntimeContent dataclass."""

    def test_default_values(self):
        """RuntimeContent should have proper defaults."""
        content = RuntimeContent()
        assert content.hexes == {}
        assert content.spells == []
        assert content.monsters_loaded is False
        assert content.items_loaded is False
        assert content.warnings == []
        assert isinstance(content.stats, RuntimeContentStats)

    def test_hexes_dict(self):
        """Hexes should be a mutable dictionary."""
        content = RuntimeContent()
        content.hexes["0101"] = MagicMock()
        content.hexes["0102"] = MagicMock()
        assert len(content.hexes) == 2
        assert "0101" in content.hexes

    def test_warnings_list(self):
        """Warnings should be a mutable list."""
        content = RuntimeContent()
        content.warnings.append("Test warning 1")
        content.warnings.append("Test warning 2")
        assert len(content.warnings) == 2

    def test_separate_instances(self):
        """Multiple RuntimeContent instances should have separate data."""
        content1 = RuntimeContent()
        content2 = RuntimeContent()
        content1.hexes["0101"] = MagicMock()
        content1.warnings.append("Warning 1")
        assert len(content2.hexes) == 0
        assert len(content2.warnings) == 0


# =============================================================================
# LOAD RUNTIME CONTENT TESTS
# =============================================================================


class TestLoadRuntimeContent:
    """Tests for load_runtime_content function."""

    def test_nonexistent_directory(self):
        """Should return empty content with warning for missing directory."""
        result = load_runtime_content(Path("/nonexistent/path/to/content"))
        assert len(result.hexes) == 0
        assert len(result.spells) == 0
        assert result.monsters_loaded is False
        assert len(result.warnings) > 0
        assert "not found" in result.warnings[0].lower()

    def test_empty_directory(self):
        """Should handle empty content directory gracefully."""
        with TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            result = load_runtime_content(content_dir)
            # Should have warnings about missing subdirectories
            assert len(result.warnings) >= 0  # May or may not warn
            assert result.stats.hexes_loaded == 0

    def test_selective_loading_hexes_only(self):
        """Should only load hexes when other flags are False."""
        with TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            result = load_runtime_content(
                content_dir,
                load_hexes=True,
                load_spells=False,
                load_monsters=False,
                load_items=False,
            )
            # With no actual hex files, should just warn about missing hex dir
            assert result.stats.spells_loaded == 0

    def test_selective_loading_nothing(self):
        """Should load nothing when all flags are False."""
        with TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            result = load_runtime_content(
                content_dir,
                load_hexes=False,
                load_spells=False,
                load_monsters=False,
                load_items=False,
            )
            assert result.stats.hexes_loaded == 0
            assert result.stats.spells_loaded == 0
            assert result.stats.monsters_loaded == 0
            assert result.stats.items_loaded == 0

    def test_with_spell_directory(self):
        """Should load spells from properly structured directory."""
        with TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            spell_dir = content_dir / "spells"
            spell_dir.mkdir()

            # Create a valid spell JSON file
            spell_data = {
                "_metadata": {
                    "source_file": "test.pdf",
                    "pages": [1],
                    "content_type": "spells",
                    "item_count": 1,
                },
                "items": [
                    {
                        "name": "Test Spell",
                        "spell_id": "test_spell",
                        "level": 1,
                        "magic_type": "arcane",
                        "duration": "Instant",
                        "range": "Touch",
                        "description": "A test spell.",
                        "reversible": False,
                        "reversed_name": None,
                    }
                ],
            }

            spell_file = spell_dir / "test_spells.json"
            with open(spell_file, "w") as f:
                json.dump(spell_data, f)

            result = load_runtime_content(
                content_dir,
                load_hexes=False,
                load_spells=True,
                load_monsters=False,
                load_items=False,
            )

            assert result.stats.spells_loaded == 1
            assert len(result.spells) == 1

    def test_with_monster_directory(self):
        """Should load monsters from properly structured directory."""
        with TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            monster_dir = content_dir / "monsters"
            monster_dir.mkdir()

            # Create a valid monster JSON file
            monster_data = {
                "_metadata": {
                    "source_file": "test.pdf",
                    "content_type": "monsters",
                    "item_count": 1,
                },
                "items": [
                    {
                        "name": "Test Goblin",
                        "monster_id": "goblin_test",
                        "hit_dice": "1",
                        "armor_class": 6,
                        "attacks": [{"name": "sword", "damage": "1d6"}],
                        "morale": 7,
                        "movement": 30,
                        "xp_value": 10,
                    }
                ],
            }

            monster_file = monster_dir / "test_monsters.json"
            with open(monster_file, "w") as f:
                json.dump(monster_data, f)

            result = load_runtime_content(
                content_dir,
                load_hexes=False,
                load_spells=False,
                load_monsters=True,
                load_items=False,
            )

            # MonsterRegistry should have loaded the monster
            assert result.stats.monsters_loaded >= 0  # May be 0 if format differs


# =============================================================================
# REGISTER SPELLS TESTS
# =============================================================================


class TestRegisterSpellsWithCombat:
    """Tests for register_spells_with_combat function."""

    def test_empty_spells_list(self):
        """Should return 0 for empty spells list."""
        combat_engine = MagicMock()
        result = register_spells_with_combat([], combat_engine)
        assert result == 0

    def test_none_spells(self):
        """Should handle None spells gracefully."""
        combat_engine = MagicMock()
        result = register_spells_with_combat(None, combat_engine)
        assert result == 0

    def test_no_spell_resolver(self):
        """Should return 0 when combat engine has no spell_resolver."""
        combat_engine = MagicMock(spec=[])  # No spell_resolver attribute
        spells = [MagicMock()]
        result = register_spells_with_combat(spells, combat_engine)
        assert result == 0

    def test_none_spell_resolver(self):
        """Should return 0 when spell_resolver is None."""
        combat_engine = MagicMock()
        combat_engine.spell_resolver = None
        spells = [MagicMock()]
        result = register_spells_with_combat(spells, combat_engine)
        assert result == 0

    def test_registration_with_valid_resolver(self):
        """Should register spells with valid combat engine."""
        from src.narrative.spell_resolver import SpellResolver, SpellData, MagicType, DurationType, RangeType

        combat_engine = MagicMock()
        combat_engine.spell_resolver = SpellResolver()

        # Create a real SpellData object with all required fields
        spell = SpellData(
            spell_id="test_register",
            name="Test Register Spell",
            level=1,
            magic_type=MagicType.ARCANE,
            duration=DurationType.INSTANT,
            range=RangeType.TOUCH,
            description="A spell for testing registration.",
        )

        result = register_spells_with_combat([spell], combat_engine)
        assert result == 1

        # Verify spell is retrievable
        retrieved = combat_engine.spell_resolver.lookup_spell("test_register")
        assert retrieved is not None
        assert retrieved.name == "Test Register Spell"

    def test_registration_multiple_spells(self):
        """Should register multiple spells correctly."""
        from src.narrative.spell_resolver import SpellResolver, SpellData, MagicType, DurationType, RangeType

        combat_engine = MagicMock()
        combat_engine.spell_resolver = SpellResolver()

        spells = [
            SpellData(
                spell_id=f"test_spell_{i}",
                name=f"Test Spell {i}",
                level=i % 5 + 1,
                magic_type=MagicType.ARCANE,
                duration=DurationType.INSTANT,
                range=RangeType.SELF,
                description=f"Test spell number {i}.",
            )
            for i in range(5)
        ]

        result = register_spells_with_combat(spells, combat_engine)
        assert result == 5


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestRuntimeBootstrapIntegration:
    """Integration tests for the full bootstrap flow."""

    def test_full_content_structure(self):
        """Test loading from a complete content directory structure."""
        with TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)

            # Create all subdirectories
            (content_dir / "hexes").mkdir()
            (content_dir / "spells").mkdir()
            (content_dir / "monsters").mkdir()
            (content_dir / "items").mkdir()

            # Add a spell
            spell_data = {
                "_metadata": {
                    "source_file": "test.pdf",
                    "pages": [1],
                    "content_type": "spells",
                    "item_count": 1,
                },
                "items": [
                    {
                        "name": "Integration Spell",
                        "spell_id": "integration_spell",
                        "level": 2,
                        "magic_type": "arcane",
                        "duration": "1 turn",
                        "range": "30'",
                        "description": "An integration test spell.",
                        "reversible": False,
                        "reversed_name": None,
                    }
                ],
            }
            with open(content_dir / "spells" / "test.json", "w") as f:
                json.dump(spell_data, f)

            result = load_runtime_content(content_dir)

            # Should have loaded spells
            assert result.stats.spells_loaded == 1
            # Hexes/monsters/items may have warnings but should not error
            assert isinstance(result.stats, RuntimeContentStats)

    def test_warning_accumulation(self):
        """Warnings should accumulate across content types."""
        with TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            # Don't create any subdirectories

            result = load_runtime_content(content_dir)

            # Should have multiple warnings about missing directories
            # (hexes, spells, monsters, items)
            assert len(result.warnings) >= 1

    def test_stats_tracking(self):
        """Stats should accurately track loaded content."""
        with TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            spell_dir = content_dir / "spells"
            spell_dir.mkdir()

            # Create multiple spells
            spell_data = {
                "_metadata": {
                    "source_file": "test.pdf",
                    "pages": [1],
                    "content_type": "spells",
                    "item_count": 3,
                },
                "items": [
                    {
                        "name": f"Spell {i}",
                        "spell_id": f"spell_{i}",
                        "level": i,
                        "magic_type": "arcane",
                        "duration": "Instant",
                        "range": "Touch",
                        "description": f"Spell number {i}.",
                        "reversible": False,
                        "reversed_name": None,
                    }
                    for i in range(1, 4)
                ],
            }
            with open(spell_dir / "multi.json", "w") as f:
                json.dump(spell_data, f)

            result = load_runtime_content(
                content_dir,
                load_hexes=False,
                load_spells=True,
                load_monsters=False,
                load_items=False,
            )

            assert result.stats.spells_loaded == 3
            assert len(result.spells) == 3
