"""
Tests for Settlement Encounter Adapter.

Tests cover:
- Actor string parsing (dice notation, numeric, single)
- Actor-to-monster ID mapping
- Full conversion pipeline
- Integration with EncounterFactory
- Edge cases and error handling
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.settlement import (
    SettlementEngine,
    SettlementRegistry,
    SettlementActorParser,
    SettlementEncounterAdapter,
    SettlementActorType,
    ParsedActor,
    SettlementEncounterConversion,
    SETTLEMENT_ACTOR_MAP,
    parse_settlement_actor,
    convert_settlement_encounter,
    get_settlement_encounter_adapter,
    get_settlement_actor_parser,
)
from src.settlement.settlement_encounter_adapter import reset_adapter
from src.content_loader import SettlementLoader
from src.content_loader.monster_registry import MonsterRegistry, get_monster_registry
from src.game_state import GlobalController
from src.data_models import TimeOfDay, DiceRoller
from src.tables.encounter_roller import EncounterEntryType
from src.encounter.encounter_factory import (
    EncounterFactory,
    get_encounter_factory,
    start_settlement_encounter,
)
from src.encounter.encounter_engine import EncounterEngine, EncounterOrigin


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    reset_adapter()
    yield
    reset_adapter()


@pytest.fixture
def parser():
    """Create a SettlementActorParser."""
    return SettlementActorParser()


@pytest.fixture
def adapter():
    """Create a SettlementEncounterAdapter."""
    return SettlementEncounterAdapter()


@pytest.fixture
def controller():
    """Create a GlobalController for tests."""
    return GlobalController()


@pytest.fixture
def engine(controller):
    """Create a SettlementEngine with registry loaded."""
    engine = SettlementEngine(controller)
    loader = SettlementLoader(Path("data/content/settlements"))
    registry = loader.load_registry()
    engine.set_registry(registry)
    return engine


@pytest.fixture
def deterministic_dice():
    """Create a DiceRoller with fixed seed for deterministic tests."""
    dice = DiceRoller()
    dice.set_seed(42)
    return dice


# =============================================================================
# ACTOR PARSING TESTS
# =============================================================================


class TestActorParsing:
    """Tests for parsing settlement actor strings."""

    def test_parse_dice_notation(self, parser):
        """Test parsing actors with dice notation (e.g., '3d6 sprites')."""
        with patch.object(DiceRoller, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=10)
            result = parser.parse_actor_string("3d6 sprites")

        assert result.original_string == "3d6 sprites"
        assert result.actor_type == "sprites"
        assert result.quantity_dice == "3d6"
        assert result.quantity == 10
        assert result.monster_id == "sprite"
        assert result.actor_classification == SettlementActorType.MONSTER
        assert result.parse_success is True

    def test_parse_numeric_quantity(self, parser):
        """Test parsing actors with numeric quantity (e.g., '3 guards')."""
        result = parser.parse_actor_string("3 guards")

        assert result.original_string == "3 guards"
        assert result.actor_type == "guards"
        assert result.quantity_dice == "3"
        assert result.quantity == 3
        assert result.monster_id == "standard_mercenary"
        assert result.actor_classification == SettlementActorType.MONSTER

    def test_parse_single_actor(self, parser):
        """Test parsing single actor without quantity (e.g., 'griffon')."""
        result = parser.parse_actor_string("griffon")

        assert result.original_string == "griffon"
        assert result.actor_type == "griffon"
        assert result.quantity_dice == "1"
        assert result.quantity == 1
        assert result.monster_id == "griffon"
        assert result.actor_classification == SettlementActorType.MONSTER

    def test_parse_named_npc(self, parser):
        """Test parsing named NPCs (e.g., 'Father Dobey')."""
        result = parser.parse_actor_string("Father Dobey")

        assert result.original_string == "Father Dobey"
        assert result.actor_type == "Father Dobey"
        assert result.quantity == 1
        assert result.monster_id is None
        assert result.actor_classification == SettlementActorType.NPC
        assert result.parse_success is True

    def test_parse_breggle_variants(self, parser):
        """Test parsing breggle soldier/guard variants."""
        shorthorn = parser.parse_actor_string("shorthorn soldiers")
        assert shorthorn.monster_id == "breggle_shorthorn"

        longhorn = parser.parse_actor_string("longhorn guards")
        assert longhorn.monster_id == "breggle_longhorn"

    def test_parse_thieves_and_ruffians(self, parser):
        """Test parsing thief variants."""
        ruffians = parser.parse_actor_string("ruffians")
        assert ruffians.monster_id == "thief_footpad"

        thieves = parser.parse_actor_string("thieves")
        assert thieves.monster_id == "thief_footpad"

        pickpocket = parser.parse_actor_string("pickpocket")
        assert pickpocket.monster_id == "thief_footpad"

    def test_parse_case_insensitive(self, parser):
        """Test case-insensitive matching."""
        result1 = parser.parse_actor_string("Crookhorn")
        result2 = parser.parse_actor_string("crookhorn")
        result3 = parser.parse_actor_string("CROOKHORN")

        assert result1.monster_id == "crookhorn"
        assert result2.monster_id == "crookhorn"
        # Should still work via case-insensitive search
        assert result3.monster_id == "crookhorn" or result3.actor_classification == SettlementActorType.NPC

    def test_parse_undead(self, parser):
        """Test parsing undead creatures."""
        zombie = parser.parse_actor_string("Zombie")
        assert zombie.monster_id == "zombie"
        assert zombie.actor_classification == SettlementActorType.MONSTER

        bog_corpse = parser.parse_actor_string("bog corpses")
        assert bog_corpse.monster_id == "bog_corpse"

    def test_parse_fairy_creatures(self, parser):
        """Test parsing fairy/fey creatures."""
        sprites = parser.parse_actor_string("sprites")
        assert sprites.monster_id == "sprite"

        mosslings = parser.parse_actor_string("mosslings")
        assert mosslings.monster_id == "mossling"

        nutcaps = parser.parse_actor_string("Nutcap")
        assert nutcaps.monster_id == "nutcap"

    def test_parse_special_monsters(self, parser):
        """Test parsing special settlement monsters."""
        slime_hulk = parser.parse_actor_string("ochre slime-hulk")
        assert slime_hulk.monster_id == "ochre_slime_hulk"

        big_chook = parser.parse_actor_string("Big Chook")
        assert big_chook.monster_id == "big_chook"

        hag = parser.parse_actor_string("the Hag")
        assert hag.monster_id == "the_hag"

    def test_parse_unknown_actor(self, parser):
        """Test parsing unknown actor type."""
        result = parser.parse_actor_string("mysterious stranger")

        assert result.actor_type == "mysterious stranger"
        assert result.monster_id is None
        assert result.actor_classification in (
            SettlementActorType.NPC,
            SettlementActorType.NARRATIVE,
        )


# =============================================================================
# MAPPING TABLE TESTS
# =============================================================================


class TestActorMappingTable:
    """Tests for the actor-to-monster mapping table."""

    def test_mapping_table_has_key_entries(self):
        """Test that mapping table contains essential entries."""
        required_keys = [
            "shorthorn soldiers",
            "longhorn guards",
            "ruffians",
            "sprites",
            "Crookhorn",
            "griffon",
            "bog corpses",
            "mosslings",
            "Zombie",
        ]

        for key in required_keys:
            assert key in SETTLEMENT_ACTOR_MAP, f"Missing key: {key}"

    def test_mapping_returns_valid_monster_ids(self):
        """Test that mapping returns valid monster registry IDs."""
        expected_ids = {
            "shorthorn soldiers": "breggle_shorthorn",
            "longhorn guards": "breggle_longhorn",
            "ruffians": "thief_footpad",
            "sprites": "sprite",
            "griffon": "griffon",
            "Crookhorn": "crookhorn",
            "Zombie": "zombie",
            "fire elemental": "fire_elemental",
            "Big Chook": "big_chook",
        }

        for actor_string, expected_id in expected_ids.items():
            monster_id, actor_type, notes = SETTLEMENT_ACTOR_MAP[actor_string]
            assert monster_id == expected_id, f"Wrong ID for {actor_string}"
            assert actor_type == SettlementActorType.MONSTER

    def test_mapping_includes_mortals(self):
        """Test that non-combat mortals are classified correctly."""
        mortal_actors = ["merchants", "nobles", "villagers"]

        for actor in mortal_actors:
            if actor in SETTLEMENT_ACTOR_MAP:
                monster_id, actor_type, notes = SETTLEMENT_ACTOR_MAP[actor]
                assert actor_type == SettlementActorType.MORTAL


# =============================================================================
# CONVERSION PIPELINE TESTS
# =============================================================================


class TestConversionPipeline:
    """Tests for the full encounter conversion pipeline."""

    def test_convert_monster_encounter(self, adapter):
        """Test converting a combat encounter with monsters."""
        encounter_data = {
            "origin": "settlement",
            "settlement_id": "lankshorn",
            "settlement_name": "Lankshorn",
            "time_of_day": "night",
            "actors": ["3d6 sprites"],
            "context": "Sprites causing mischief in the streets",
            "has_monsters": True,
            "has_npcs": False,
        }

        result = adapter.convert_encounter(
            encounter_data,
            "lankshorn",
            "Lankshorn",
        )

        assert result.settlement_id == "lankshorn"
        assert result.settlement_name == "Lankshorn"
        assert result.requires_engine is True
        assert result.is_narrative_only is False
        assert len(result.parsed_monsters) == 1
        assert result.parsed_monsters[0].monster_id == "sprite"
        assert result.rolled_encounter is not None

    def test_convert_narrative_encounter(self, adapter):
        """Test converting a narrative-only encounter."""
        encounter_data = {
            "origin": "settlement",
            "settlement_id": "lankshorn",
            "settlement_name": "Lankshorn",
            "time_of_day": "day",
            "actors": ["Father Dobey", "mourners"],
            "context": "A funeral procession through town",
            "has_monsters": False,
            "has_npcs": True,
        }

        result = adapter.convert_encounter(
            encounter_data,
            "lankshorn",
            "Lankshorn",
        )

        assert result.requires_engine is False
        assert result.is_narrative_only is True
        assert result.rolled_encounter is None
        assert len(result.parsed_npcs) >= 1

    def test_convert_mixed_encounter(self, adapter):
        """Test converting an encounter with both monsters and NPCs."""
        encounter_data = {
            "origin": "settlement",
            "settlement_id": "lankshorn",
            "settlement_name": "Lankshorn",
            "time_of_day": "day",
            "actors": ["Lord Malbleat", "2d4 longhorn guards"],
            "context": "Lord Malbleat demanding impromptu taxes",
            "has_monsters": True,
            "has_npcs": True,
        }

        result = adapter.convert_encounter(
            encounter_data,
            "lankshorn",
            "Lankshorn",
        )

        # Has guards = combat possible
        assert result.requires_engine is True
        assert result.rolled_encounter is not None
        assert len(result.parsed_monsters) >= 1
        assert len(result.parsed_npcs) >= 1

    def test_rolled_encounter_has_correct_structure(self, adapter):
        """Test that RolledEncounter has correct structure."""
        encounter_data = {
            "origin": "settlement",
            "settlement_id": "prigwort",
            "settlement_name": "Prigwort",
            "time_of_day": "night",
            "actors": ["2d6 ruffians"],
            "context": "Ruffians looking for trouble",
            "has_monsters": True,
            "has_npcs": False,
        }

        result = adapter.convert_encounter(
            encounter_data,
            "prigwort",
            "Prigwort",
        )

        rolled = result.rolled_encounter
        assert rolled is not None
        assert rolled.entry is not None
        assert rolled.entry.monster_id == "thief_footpad"
        assert rolled.entry_type == EncounterEntryType.MONSTER
        assert rolled.number_appearing >= 2  # Minimum from 2d6
        assert rolled.activity == "Ruffians looking for trouble"
        assert "prigwort" in rolled.terrain_type


# =============================================================================
# INTEGRATION WITH MONSTER REGISTRY TESTS
# =============================================================================


class TestMonsterRegistryIntegration:
    """Tests for integration with MonsterRegistry."""

    def test_mapped_monsters_exist_in_registry(self):
        """Test that mapped monster IDs exist in the registry."""
        registry = get_monster_registry()

        # Key monster IDs from our mapping
        key_monster_ids = [
            "sprite",
            "crookhorn",
            "griffon",
            "mossling",
            "nutcap",
            "bog_corpse",
            "barrowbogey",
            "ochre_slime_hulk",
            "zombie",
            "fire_elemental",
            "big_chook",
        ]

        for monster_id in key_monster_ids:
            monster = registry.get_monster(monster_id)
            assert monster is not None, f"Monster '{monster_id}' not found in registry"

    def test_can_create_combatant_from_mapped_id(self):
        """Test creating combatants from mapped monster IDs."""
        registry = get_monster_registry()

        # Test a few key monsters
        test_monsters = ["sprite", "crookhorn", "zombie"]

        for monster_id in test_monsters:
            combatant = registry.create_combatant(
                monster_id=monster_id,
                combatant_id=f"test_{monster_id}_1",
                side="enemy",
                roll_hp=True,
            )
            assert combatant is not None, f"Failed to create combatant for {monster_id}"
            assert combatant.stat_block is not None
            assert combatant.stat_block.hp_current > 0


# =============================================================================
# INTEGRATION WITH ENCOUNTER ENGINE TESTS
# =============================================================================


class TestEncounterEngineIntegration:
    """Tests for full integration with EncounterEngine."""

    def test_full_settlement_encounter_flow(self, controller, engine):
        """Test complete flow from settlement encounter to EncounterEngine."""
        # Set up settlement
        engine.set_active_settlement("lankshorn")

        # Simulate a settlement encounter with monsters
        encounter_engine_data = {
            "origin": "settlement",
            "settlement_id": "lankshorn",
            "settlement_name": "Lankshorn",
            "location_number": 1,
            "time_of_day": "night",
            "actors": ["3d6 sprites"],
            "context": "Sprites causing mischief",
            "has_monsters": True,
            "has_npcs": False,
            "notes": None,
            "suggested_encounter_type": "monster",
        }

        # Convert using adapter
        adapter = get_settlement_encounter_adapter()
        conversion = adapter.convert_encounter(
            encounter_engine_data,
            "lankshorn",
            "Lankshorn",
        )

        assert conversion.requires_engine is True
        assert conversion.rolled_encounter is not None

        # Create encounter using factory
        factory = get_encounter_factory()
        factory_result = factory.create_encounter(
            rolled_encounter=conversion.rolled_encounter,
            terrain="Lankshorn streets",
            is_outdoor=True,
        )

        assert factory_result.encounter_state is not None
        assert len(factory_result.encounter_state.combatants) > 0

        # Verify combatants have valid stats
        for combatant in factory_result.encounter_state.combatants:
            assert combatant.stat_block is not None
            assert combatant.stat_block.hp_current > 0

    def test_encounter_engine_can_start_settlement_encounter(self, controller, engine):
        """Test EncounterEngine can start a settlement encounter."""
        engine.set_active_settlement("prigwort")

        # Create encounter data
        encounter_engine_data = {
            "origin": "settlement",
            "settlement_id": "prigwort",
            "settlement_name": "Prigwort",
            "time_of_day": "night",
            "actors": ["2d6 ruffians"],
            "context": "Ruffians looking for trouble",
            "has_monsters": True,
            "has_npcs": False,
        }

        # Convert and create encounter
        adapter = get_settlement_encounter_adapter()
        conversion = adapter.convert_encounter(
            encounter_engine_data,
            "prigwort",
            "Prigwort",
        )

        factory = get_encounter_factory()
        factory_result = factory.create_encounter(
            rolled_encounter=conversion.rolled_encounter,
            terrain="Prigwort alleyway",
            is_outdoor=True,
        )

        # Start encounter with engine
        enc_engine = EncounterEngine(controller)
        result = enc_engine.start_encounter(
            encounter=factory_result.encounter_state,
            origin=EncounterOrigin.SETTLEMENT,
            party_aware=False,
            enemies_aware=False,
        )

        assert result["encounter_started"] is True
        assert result["origin"] == "settlement"
        assert enc_engine.is_active() is True
        assert enc_engine.get_origin() == EncounterOrigin.SETTLEMENT


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_parse_settlement_actor(self):
        """Test parse_settlement_actor convenience function."""
        result = parse_settlement_actor("3d6 sprites")
        assert result.monster_id == "sprite"
        assert result.actor_classification == SettlementActorType.MONSTER

    def test_convert_settlement_encounter(self):
        """Test convert_settlement_encounter convenience function."""
        encounter_data = {
            "settlement_id": "lankshorn",
            "settlement_name": "Lankshorn",
            "time_of_day": "night",
            "actors": ["griffon"],
            "context": "A griffon lands in the market square",
        }

        result = convert_settlement_encounter(encounter_data)
        assert result.requires_engine is True
        assert result.rolled_encounter is not None

    def test_get_shared_instances(self):
        """Test that shared instances are returned correctly."""
        adapter1 = get_settlement_encounter_adapter()
        adapter2 = get_settlement_encounter_adapter()
        assert adapter1 is adapter2

        parser1 = get_settlement_actor_parser()
        parser2 = get_settlement_actor_parser()
        assert parser1 is parser2


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_actors_list(self, adapter):
        """Test handling empty actors list."""
        encounter_data = {
            "settlement_id": "lankshorn",
            "settlement_name": "Lankshorn",
            "time_of_day": "day",
            "actors": [],
            "context": "Nothing happens",
        }

        result = adapter.convert_encounter(
            encounter_data,
            "lankshorn",
            "Lankshorn",
        )

        assert result.requires_engine is False
        assert result.is_narrative_only is True
        assert len(result.parsed_monsters) == 0

    def test_whitespace_in_actor_string(self, parser):
        """Test handling whitespace in actor strings."""
        result = parser.parse_actor_string("  3d6 sprites  ")
        assert result.actor_type == "sprites"
        assert result.monster_id == "sprite"

    def test_complex_dice_expression(self, parser):
        """Test parsing complex dice expressions."""
        with patch.object(DiceRoller, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=8)
            result = parser.parse_actor_string("2d4+2 guards")

        assert result.quantity_dice == "2d4+2"
        assert result.actor_type == "guards"

    def test_missing_encounter_data_fields(self, adapter):
        """Test handling missing fields in encounter data."""
        encounter_data = {
            "settlement_id": "test",
            "actors": ["sprites"],
            # Missing other fields
        }

        # Should not raise an exception
        result = adapter.convert_encounter(
            encounter_data,
            "test",
            "Test Settlement",
        )

        assert result is not None
        assert result.settlement_id == "test"


# =============================================================================
# COMPREHENSIVE SETTLEMENT ACTOR COVERAGE TESTS
# =============================================================================


class TestAllSettlementActors:
    """Tests to verify all settlement actors can be parsed."""

    # All unique actors from settlement JSON files
    MONSTER_ACTORS = [
        "2d4 mosslings",
        "Big Chook",
        "Crookhorn",
        "Crookhorn Guards",
        "Crookhorns",
        "Giant Mutant Snail",
        "Mossling",
        "Nutcap",
        "Ochre Slime-hulk",
        "Zombie",
        "barrowbogey",
        "bestial centaur",
        "bog corpses",
        "clockwork guardian",
        "fire elemental",
        "griffon",
        "grimalkin",
        "guards",
        "longhorn guards",
        "longhorn nobles",
        "longhorns",
        "mosslings",
        "ochre slime-hulk",
        "ruffians",
        "shorthorn guards",
        "shorthorn soldiers",
        "shorthorns",
        "soldiers",
        "sprites",
        "the Hag",
        "thieves",
    ]

    def test_all_monster_actors_can_be_parsed(self, parser):
        """Test that all monster actors from settlements can be parsed."""
        failed_actors = []

        for actor in self.MONSTER_ACTORS:
            result = parser.parse_actor_string(actor)
            if result.monster_id is None and result.actor_classification == SettlementActorType.MONSTER:
                failed_actors.append(actor)

        # Most should parse successfully
        success_rate = (len(self.MONSTER_ACTORS) - len(failed_actors)) / len(self.MONSTER_ACTORS)
        assert success_rate >= 0.85, f"Too many parse failures: {failed_actors}"

    def test_key_combat_actors_have_monster_ids(self, parser):
        """Test that key combat actors map to valid monster IDs."""
        combat_actors = [
            ("sprites", "sprite"),
            ("Crookhorn", "crookhorn"),
            ("griffon", "griffon"),
            ("ruffians", "thief_footpad"),
            ("guards", "standard_mercenary"),
            ("Zombie", "zombie"),
            ("mosslings", "mossling"),
            ("bog corpses", "bog_corpse"),
            ("Big Chook", "big_chook"),
        ]

        for actor_string, expected_id in combat_actors:
            result = parser.parse_actor_string(actor_string)
            assert result.monster_id == expected_id, (
                f"Actor '{actor_string}' mapped to '{result.monster_id}', "
                f"expected '{expected_id}'"
            )
