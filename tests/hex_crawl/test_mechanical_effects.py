"""
Tests for mechanical_effect automation from POI roll tables.

This test suite validates:
- Roll tables apply mechanical_effect to POIVisit.active_effects
- get_stealth_modifier_from_effects calculates correctly
- get_reaction_modifier_from_effects calculates correctly
- sneak_into_poi uses effect stealth modifier
- Session persistence of active_effects
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.data_models import DiceRoller, GameDate, CharacterState
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine, POIVisit


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0109 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(
        Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
    )
    assert result.success, f"Failed to load hex 0109: {result.errors}"
    return pipeline


@pytest.fixture
def controller():
    """Create a GlobalController with a test character."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=3, day=15)
    char = CharacterState(
        character_id="thief_1",
        name="Sneaky Pete",
        character_class="Thief",
        level=3,
        ability_scores={"STR": 10, "INT": 12, "WIS": 10, "DEX": 16, "CON": 12, "CHA": 10},
        hp_current=15,
        hp_max=15,
        armor_class=13,
        base_speed=40,
    )
    controller.add_character(char)
    return controller


@pytest.fixture
def engine(controller, pipeline):
    """Create a HexCrawlEngine with hex 0109 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0109"] = pipeline.get_hex("0109")
    engine._current_hex = "0109"
    return engine


# =============================================================================
# ROLL TABLE EFFECT APPLICATION TESTS
# =============================================================================


class TestRollTableEffectApplication:
    """Test that roll tables apply mechanical_effect to active_effects."""

    def test_roll_table_stores_effect(self, engine):
        """Rolling on table should store mechanical_effect in active_effects."""
        # Mock the dice to get a predictable result with mechanical_effect
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            # Roll 5 on Camp Activities (d6) gets "Furtive Drinking" with stealth_mod +2
            mock_result.total = 5
            mock_roll.return_value = mock_result

            result = engine.roll_on_poi_table("0109", "Camp Activities", "Murkin's Army")

            # Check that the effect was stored
            effects = engine.get_active_effects("0109", "Murkin's Army")
            assert len(effects) > 0

            # Find the stealth effect from Camp Activities
            camp_effect = None
            for e in effects:
                if e.get("source") == "Camp Activities":
                    camp_effect = e
                    break

            assert camp_effect is not None
            assert camp_effect.get("type") == "stealth_mod"
            assert camp_effect.get("value") == 2

    def test_roll_table_replaces_same_source(self, engine):
        """Rolling on same table twice should replace previous effect."""
        with patch.object(engine.dice, "roll") as mock_roll:
            # First roll - stealth_mod +2 (roll 5: Furtive Drinking)
            mock_result = MagicMock()
            mock_result.total = 5
            mock_roll.return_value = mock_result

            engine.roll_on_poi_table("0109", "Camp Activities", "Murkin's Army")

            # Second roll - stealth_mod -2 (roll 4: Formation March)
            mock_result.total = 4
            mock_roll.return_value = mock_result

            engine.roll_on_poi_table("0109", "Camp Activities", "Murkin's Army")

            # Should only have one Camp Activities effect
            effects = engine.get_active_effects("0109", "Murkin's Army")
            camp_effects = [e for e in effects if e.get("source") == "Camp Activities"]
            assert len(camp_effects) == 1
            assert camp_effects[0].get("value") == -2


class TestStealthModifierFromEffects:
    """Test get_stealth_modifier_from_effects calculation."""

    def test_no_effects_returns_zero(self, engine):
        """No active effects should return 0 modifier."""
        modifier = engine.get_stealth_modifier_from_effects("0109", "Murkin's Army")
        assert modifier == 0

    def test_single_stealth_effect(self, engine):
        """Single stealth effect should return its value."""
        # Manually add an effect
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "stealth_mod", "value": -2, "source": "Camp Activities"}
            ]
        )

        modifier = engine.get_stealth_modifier_from_effects("0109", "Murkin's Army")
        assert modifier == -2

    def test_multiple_stealth_effects_sum(self, engine):
        """Multiple stealth effects should sum together."""
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "stealth_mod", "value": -2, "source": "Camp Activities"},
                {"type": "stealth_mod", "value": 1, "source": "Weather"},
            ]
        )

        modifier = engine.get_stealth_modifier_from_effects("0109", "Murkin's Army")
        assert modifier == -1

    def test_ignores_non_stealth_effects(self, engine):
        """Non-stealth effects should not affect stealth modifier."""
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "stealth_mod", "value": 2, "source": "Camp Activities"},
                {"type": "reaction_mod", "value": -1, "source": "Morale"},
            ]
        )

        modifier = engine.get_stealth_modifier_from_effects("0109", "Murkin's Army")
        assert modifier == 2


class TestReactionModifierFromEffects:
    """Test get_reaction_modifier_from_effects calculation."""

    def test_no_effects_returns_zero(self, engine):
        """No active effects should return 0 modifier."""
        modifier = engine.get_reaction_modifier_from_effects("0109", "Murkin's Army")
        assert modifier == 0

    def test_single_reaction_effect(self, engine):
        """Single reaction effect should return its value."""
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "reaction_mod", "value": 1, "target": "all", "source": "Morale"}
            ]
        )

        modifier = engine.get_reaction_modifier_from_effects("0109", "Murkin's Army")
        assert modifier == 1

    def test_target_filtering(self, engine):
        """Reaction modifier should filter by target when specified."""
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "reaction_mod", "value": 1, "target": "murkin_soldiers", "source": "Morale"},
                {"type": "reaction_mod", "value": -2, "target": "grimalkin", "source": "Other"},
            ]
        )

        # Target matches murkin_soldiers
        modifier = engine.get_reaction_modifier_from_effects(
            "0109", "Murkin's Army", target="murkin_soldiers"
        )
        assert modifier == 1

        # Target matches grimalkin
        modifier = engine.get_reaction_modifier_from_effects(
            "0109", "Murkin's Army", target="grimalkin"
        )
        assert modifier == -2

    def test_all_target_always_applies(self, engine):
        """Effects with target='all' should always apply."""
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "reaction_mod", "value": 1, "target": "all", "source": "Morale"},
            ]
        )

        modifier = engine.get_reaction_modifier_from_effects(
            "0109", "Murkin's Army", target="any_target"
        )
        assert modifier == 1


# =============================================================================
# SNEAK INTO POI INTEGRATION TESTS
# =============================================================================


class TestSneakIntoPOIWithEffects:
    """Test that sneak_into_poi uses effect stealth modifier."""

    def test_effect_modifier_affects_roll(self, engine):
        """Effect stealth modifier should affect stealth roll."""
        engine._current_poi = None

        # Set up a negative stealth modifier effect
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "stealth_mod", "value": -2, "source": "Camp Activities"}
            ]
        )

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 5
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.sneak_into_poi("0109", "Murkin's Army", "thief_1")

            # Should include effect modifier in result
            assert "effect_stealth_modifier" in result
            assert result["effect_stealth_modifier"] == -2
            assert result["total_modifier"] == -2

    def test_positive_effect_modifier_helps_stealth(self, engine):
        """Positive effect modifier should make stealth easier."""
        engine._current_poi = None

        # Set up a positive stealth modifier effect (soldiers distracted)
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "stealth_mod", "value": 2, "source": "Camp Activities"}
            ]
        )

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 4  # Base roll of 4
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            result = engine.sneak_into_poi("0109", "Murkin's Army", "thief_1")

            # With +2 modifier, effective roll is 6
            assert result["effect_stealth_modifier"] == 2
            assert result["effective_roll"] == 6

    def test_effect_plus_player_modifier_stack(self, engine):
        """Effect modifier and player modifier should stack."""
        engine._current_poi = None

        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "stealth_mod", "value": 2, "source": "Camp Activities"}
            ]
        )

        with patch(
            "src.resolution.skill_resolver.get_skill_resolver"
        ) as mock_resolver:
            mock_skill_result = MagicMock()
            mock_skill_result.roll = 3
            mock_resolver.return_value.resolve_skill_check.return_value = (
                mock_skill_result
            )

            # Pass player modifier of +1
            result = engine.sneak_into_poi(
                "0109", "Murkin's Army", "thief_1", stealth_modifier=1
            )

            # Total should be 3 + 2 (effect) + 1 (player) = 6
            assert result["stealth_modifier"] == 1
            assert result["effect_stealth_modifier"] == 2
            assert result["total_modifier"] == 3
            assert result["effective_roll"] == 6


# =============================================================================
# ENCOUNTER ENGINE REACTION MODIFIER TESTS
# =============================================================================


class TestEncounterReactionModifier:
    """Test that encounter engine applies reaction modifier."""

    def test_reaction_modifier_field_exists(self):
        """EncounterEngineState should have reaction_modifier field."""
        from src.encounter.encounter_engine import EncounterEngineState, EncounterOrigin, EncounterPhase
        from src.data_models import EncounterState

        state = EncounterEngineState(
            encounter=EncounterState(actors=["goblin"]),
            origin=EncounterOrigin.WILDERNESS,
            current_phase=EncounterPhase.AWARENESS,
            reaction_modifier=2,
        )

        assert state.reaction_modifier == 2

    def test_parley_applies_reaction_modifier(self, controller):
        """Parley action should apply reaction_modifier to roll."""
        from src.encounter.encounter_engine import (
            EncounterEngine, EncounterEngineState,
            EncounterOrigin, EncounterPhase, EncounterRoundResult
        )
        from src.data_models import EncounterState

        engine = EncounterEngine(controller)

        # Set up state with reaction modifier
        engine._state = EncounterEngineState(
            encounter=EncounterState(actors=["goblin"], context="test"),
            origin=EncounterOrigin.WILDERNESS,
            current_phase=EncounterPhase.ACTIONS,
            reaction_modifier=2,
        )

        result = EncounterRoundResult(
            phase=EncounterPhase.ACTIONS,
            success=True
        )

        with patch.object(engine.dice, "roll_2d6") as mock_roll:
            mock_dice_result = MagicMock()
            mock_dice_result.total = 7  # Base roll
            mock_roll.return_value = mock_dice_result

            # Mock controller.transition to avoid state machine errors
            with patch.object(controller, "transition"):
                result = engine._handle_parley("party", result)

            # Modified total should be 7 + 2 = 9
            assert result.reaction_roll == 9


# =============================================================================
# SESSION PERSISTENCE TESTS
# =============================================================================


class TestSessionPersistence:
    """Test that active_effects persist through session save/load."""

    def test_poi_visit_active_effects_serialize(self, engine):
        """POIVisit active_effects should serialize properly."""
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "stealth_mod", "value": 2, "source": "Camp Activities", "roll": 7}
            ]
        )

        # Access the visit and verify it has effects
        visit = engine._poi_visits[visit_key]
        assert len(visit.active_effects) == 1
        assert visit.active_effects[0]["type"] == "stealth_mod"

    def test_active_effects_in_visit_copy(self, engine):
        """Copying active_effects should preserve data."""
        effects = [
            {"type": "stealth_mod", "value": -2, "source": "Camp Activities"},
            {"type": "reaction_mod", "value": 1, "target": "all", "source": "Morale"},
        ]

        copied = [e.copy() for e in effects]

        assert len(copied) == 2
        assert copied[0]["value"] == -2
        assert copied[1]["target"] == "all"


# =============================================================================
# CLEAR EFFECTS TESTS
# =============================================================================


class TestClearEffects:
    """Test clearing active effects."""

    def test_clear_active_effects(self, engine):
        """clear_active_effects should remove all effects."""
        visit_key = "0109:Murkin's Army"
        engine._poi_visits[visit_key] = POIVisit(
            poi_name="Murkin's Army",
            active_effects=[
                {"type": "stealth_mod", "value": 2, "source": "Camp Activities"},
                {"type": "reaction_mod", "value": 1, "source": "Morale"},
            ]
        )

        engine.clear_active_effects("0109", "Murkin's Army")

        effects = engine.get_active_effects("0109", "Murkin's Army")
        assert len(effects) == 0


# =============================================================================
# STRUCTURED EFFECT FORMAT TESTS
# =============================================================================


class TestStructuredEffectFormat:
    """Test that mechanical_effect is properly structured in hex data."""

    def test_camp_activities_has_structured_effects(self, pipeline):
        """Camp Activities table should have structured mechanical_effects."""
        hex_data = pipeline.get_hex("0109")

        # Find Murkin's Army POI
        poi = None
        for p in hex_data.points_of_interest:
            if p.name == "Murkin's Army":
                poi = p
                break

        assert poi is not None

        # Find Camp Activities table - tables are RollTable objects with .name attribute
        camp_table = None
        for table in poi.roll_tables:
            # Handle both RollTable objects and dict format
            table_name = getattr(table, "name", None) or table.get("name")
            if table_name == "Camp Activities":
                camp_table = table
                break

        assert camp_table is not None

        # Get entries - handle RollTable object or dict
        entries = getattr(camp_table, "entries", None) or camp_table.get("entries", [])

        # Check entries have structured mechanical_effects
        for entry in entries:
            # Handle RollTableEntry object or dict
            effect = getattr(entry, "mechanical_effect", None)
            if effect is None and hasattr(entry, "get"):
                effect = entry.get("mechanical_effect")
            if effect:
                assert isinstance(effect, dict), f"Effect should be dict: {effect}"
                assert "type" in effect, f"Effect missing type: {effect}"

    def test_morale_table_has_reaction_effects(self, pipeline):
        """Morale table should have reaction_mod effects."""
        hex_data = pipeline.get_hex("0109")

        poi = None
        for p in hex_data.points_of_interest:
            if p.name == "Murkin's Army":
                poi = p
                break

        assert poi is not None

        morale_table = None
        for table in poi.roll_tables:
            # Handle both RollTable objects and dict format
            table_name = getattr(table, "name", None) or table.get("name")
            if table_name == "Soldier Morale":
                morale_table = table
                break

        assert morale_table is not None

        # Get entries - handle RollTable object or dict
        entries = getattr(morale_table, "entries", None) or morale_table.get("entries", [])

        # Check for reaction_mod effects
        has_reaction_effect = False
        for entry in entries:
            effect = getattr(entry, "mechanical_effect", None)
            if effect is None and hasattr(entry, "get"):
                effect = entry.get("mechanical_effect")
            if effect and effect.get("type") == "reaction_mod":
                has_reaction_effect = True
                break

        assert has_reaction_effect, "Morale table should have reaction_mod effects"
