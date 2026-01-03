"""
Tests for hex 0107 (The Weeping Woman) hazard mechanics.

These tests verify that full moon triggers, enchantment chains,
and fairy magic hazards work correctly for hex 0107's specific gameplay.
"""

import pytest
from unittest.mock import MagicMock


class TestFullMoonTrigger:
    """Tests for full moon night hazard triggers."""

    def test_full_moon_trigger_only_fires_on_full_moon(self):
        """Verify full_moon trigger only fires when is_full_moon is True."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)  # NOT full moon
        engine._is_winter = MagicMock(return_value=False)
        engine.dice = MagicMock()

        # Create mock hex with full_moon trigger hazard (from hex 0107)
        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {
                "trigger": "full_moon",
                "save_type": "spell",
                "description": "The moon's light draws you to dance",
                "on_fail": {"condition": "moon_dance_compulsion"},
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Should NOT trigger when not full moon
        results = engine.process_night_hazards("0107")
        assert len(results) == 0

    def test_full_moon_trigger_fires_on_full_moon(self):
        """Verify full_moon trigger fires when is_full_moon is True."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=10)
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.character_id = "test_char"
        char.name = "Test Character"
        char.make_saving_throw = MagicMock(return_value=(5, False))  # Failed save

        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = [char]
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=True)  # Full moon!
        engine._is_winter = MagicMock(return_value=False)

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {
                "trigger": "full_moon",
                "save_type": "spell",
                "description": "The moon's light draws you to dance",
                "on_fail": {"condition": "compelled"},
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Should trigger on full moon
        results = engine.process_night_hazards("0107")
        assert len(results) == 1
        assert results[0]["character_id"] == "test_char"

    def test_full_moon_trigger_requires_night(self):
        """Verify full_moon trigger requires it to be night."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []
        engine._is_night = MagicMock(return_value=False)  # NOT night (daytime)
        engine._is_full_moon = MagicMock(return_value=True)  # Full moon
        engine._is_winter = MagicMock(return_value=False)
        engine.dice = MagicMock()

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {
                "trigger": "full_moon",
                "save_type": "spell",
                "on_fail": {"condition": "compelled"},
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Should NOT trigger during day even on full moon
        results = engine.process_night_hazards("0107")
        assert len(results) == 0

    def test_full_moon_excluded_from_generic_night_trigger(self):
        """Verify full_moon hazard does NOT fire on regular night triggers."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)  # Regular night
        engine._is_winter = MagicMock(return_value=False)
        engine.dice = MagicMock()

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            # Regular night hazard
            {
                "trigger": "night",
                "save_type": "spell",
                "description": "Night whispers",
                "on_fail": {"condition": "frightened"},
            },
            # Full moon only hazard
            {
                "trigger": "full_moon",
                "save_type": "spell",
                "description": "Moon compulsion",
                "on_fail": {"condition": "compelled"},
            },
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Mock _resolve_hazard to track which hazards are called
        resolved_triggers = []

        def track_resolve(hazard, char, apply_effects=True):
            resolved_triggers.append(hazard.get("trigger"))
            return MagicMock(
                success=True,
                conditions_applied=[],
                damage_taken=0,
                apply_damage=[],
                apply_conditions=[],
            )

        # Add a mock character
        char = MagicMock()
        char.character_id = "test"
        char.name = "Test"
        engine.controller.get_all_characters.return_value = [char]
        engine._resolve_hazard = track_resolve

        results = engine.process_night_hazards("0107")

        # Only "night" trigger should fire, not "full_moon"
        assert "night" in resolved_triggers
        assert "full_moon" not in resolved_triggers


class TestHex0107NightNearWeepingWoman:
    """Tests for night_near_weeping_woman trigger."""

    def test_night_near_weeping_woman_triggers_at_night(self):
        """Verify night_near_weeping_woman trigger works at night."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=10)
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.character_id = "test_char"
        char.name = "Test Character"
        char.make_saving_throw = MagicMock(return_value=(5, False))

        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = [char]
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)
        engine._is_winter = MagicMock(return_value=False)
        engine._hex_has_feature = MagicMock(return_value=True)  # Near weeping woman

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {
                "trigger": "sleep_near_weeping_woman",
                "save_type": "spell",
                "description": "Dreams of the fairy woman haunt your sleep",
                "on_fail": {"condition": "enchanted_reverie"},
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Should trigger when sleeping near the feature
        results = engine.process_night_hazards("0107", activity="sleeping")
        assert len(results) == 1
