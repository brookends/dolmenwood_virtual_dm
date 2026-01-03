"""
Snapshot validation tests for save/load functionality.

Tests that game state is preserved correctly through save/load cycles:
- Party state (location, resources, marching order)
- Time state (date, time, season, weather)
- Character state (HP, conditions, inventory, spells)
- Combat state (ongoing combat)
- Encounter state (ongoing encounter)
- Hex exploration deltas
"""

import pytest
import tempfile
from pathlib import Path
import shutil

from src.main import VirtualDM, GameConfig, create_demo_session
from src.data_models import (
    GameDate,
    GameTime,
    CharacterState,
    ConditionType,
    Condition,
    LocationType,
    Item,
    Spell,
    EncounterState,
    EncounterType,
    Combatant,
    StatBlock,
    SurpriseStatus,
)
from src.game_state import GameState


@pytest.fixture
def temp_save_dir():
    """Create a temporary directory for saves."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def dm_with_state(temp_save_dir):
    """Create a VirtualDM with a rich game state for testing."""
    config = GameConfig(
        save_dir=temp_save_dir,
        campaign_name="Test Campaign",
        enable_narration=False,
        use_vector_db=False,
    )
    dm = VirtualDM(
        config=config,
        initial_state=GameState.WILDERNESS_TRAVEL,
        game_date=GameDate(year=1, month=6, day=15),
        game_time=GameTime(hour=14, minute=30),
    )

    # Add a character with conditions and items
    char = CharacterState(
        character_id="test_fighter",
        name="Aldric the Bold",
        character_class="Fighter",
        level=3,
        hp_max=24,
        hp_current=18,
        armor_class=16,
        base_speed=40,
        ability_scores={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 11, "CHA": 13},
        inventory=[
            Item(
                item_id="sword_01",
                name="Longsword",
                weight=4.0,
                value_gp=15,
                equipped=True,
            ),
            Item(
                item_id="potion_01",
                name="Healing Potion",
                weight=0.5,
                value_gp=50,
            ),
        ],
        conditions=[
            Condition(
                condition_type=ConditionType.EXHAUSTED,
                duration_turns=10,
                source="forced march",
            ),
        ],
    )
    dm.add_character(char)

    # Add a second character
    char2 = CharacterState(
        character_id="test_mage",
        name="Elara the Wise",
        character_class="Magic-User",
        level=2,
        hp_max=8,
        hp_current=8,
        armor_class=10,
        base_speed=40,
        ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 17, "WIS": 13, "CHA": 12},
        spells=[
            Spell(
                spell_id="magic_missile",
                name="Magic Missile",
                level=1,
                prepared=True,
                cast_today=False,
            ),
            Spell(
                spell_id="sleep",
                name="Sleep",
                level=1,
                prepared=True,
                cast_today=True,
            ),
        ],
    )
    dm.add_character(char2)

    # Set party resources
    dm.set_party_resources(
        food_days=5.5,
        water_days=7.0,
        torches=8,
        lantern_oil=3,
    )

    # Set location
    dm.controller.set_party_location(LocationType.HEX, "0709")

    # Mark some exploration
    dm.hex_crawl._explored_hexes.add("0709")
    dm.hex_crawl._explored_hexes.add("0710")
    dm.hex_crawl._met_npcs.add("blackwood_elder")

    return dm


class TestBasicSaveLoad:
    """Test basic save/load round-trip."""

    def test_save_creates_file(self, dm_with_state, temp_save_dir):
        """Saving creates a slot file."""
        filepath = dm_with_state.save_game(slot=1)
        assert filepath.exists()
        assert filepath.name == "slot_1.json"

    def test_save_load_round_trip(self, dm_with_state, temp_save_dir):
        """Save and load preserves state."""
        # Save
        dm_with_state.save_game(slot=1)

        # Create a new VirtualDM and load
        config = GameConfig(
            save_dir=temp_save_dir,
            campaign_name="Fresh Load",
            enable_narration=False,
            use_vector_db=False,
        )
        dm2 = VirtualDM(config=config)

        success = dm2.load_game(slot=1)
        assert success is True

    def test_list_saves(self, dm_with_state, temp_save_dir):
        """list_saves shows saved slots."""
        dm_with_state.save_game(slot=1)
        dm_with_state.save_game(slot=3)

        saves = dm_with_state.list_saves()
        assert len(saves) == 9  # All 9 slots

        slot1 = next(s for s in saves if s["slot"] == 1)
        assert slot1["session_name"] != "(empty)"
        assert slot1["last_saved"] is not None

        slot2 = next(s for s in saves if s["slot"] == 2)
        assert slot2["session_name"] == "(empty)"

        slot3 = next(s for s in saves if s["slot"] == 3)
        assert slot3["session_name"] != "(empty)"


class TestCharacterStatePreservation:
    """Test character state is preserved through save/load."""

    def test_character_hp_preserved(self, dm_with_state, temp_save_dir):
        """Character HP is preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        char = dm2.get_character("test_fighter")
        assert char is not None
        assert char.hp_current == 18
        assert char.hp_max == 24

    def test_character_conditions_preserved(self, dm_with_state, temp_save_dir):
        """Character conditions are preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        char = dm2.get_character("test_fighter")
        assert len(char.conditions) == 1
        assert char.conditions[0].condition_type == ConditionType.EXHAUSTED
        assert char.conditions[0].source == "forced march"

    def test_character_inventory_preserved(self, dm_with_state, temp_save_dir):
        """Character inventory is preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        char = dm2.get_character("test_fighter")
        assert len(char.inventory) == 2
        sword = next(i for i in char.inventory if i.item_id == "sword_01")
        assert sword.name == "Longsword"
        assert sword.equipped is True

    def test_character_spells_preserved(self, dm_with_state, temp_save_dir):
        """Character spells are preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        char = dm2.get_character("test_mage")
        assert len(char.spells) == 2

        mm = next(s for s in char.spells if s.spell_id == "magic_missile")
        assert mm.cast_today is False

        sleep = next(s for s in char.spells if s.spell_id == "sleep")
        assert sleep.cast_today is True

    def test_ability_scores_preserved(self, dm_with_state, temp_save_dir):
        """Character ability scores are preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        char = dm2.get_character("test_fighter")
        assert char.ability_scores["STR"] == 16
        assert char.ability_scores["INT"] == 10


class TestWorldStatePreservation:
    """Test world state is preserved through save/load."""

    def test_time_preserved(self, dm_with_state, temp_save_dir):
        """Game time is preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        world = dm2.controller.world_state
        assert world.current_date.year == 1
        assert world.current_date.month == 6
        assert world.current_date.day == 15
        assert world.current_time.hour == 14
        assert world.current_time.minute == 30

    def test_location_preserved(self, dm_with_state, temp_save_dir):
        """Party location is preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        party = dm2.controller.party_state
        assert party.location.location_type == LocationType.HEX
        assert party.location.location_id == "0709"

    def test_resources_preserved(self, dm_with_state, temp_save_dir):
        """Party resources are preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        res = dm2.get_resources()
        assert res.food_days == 5.5
        assert res.water_days == 7.0
        assert res.torches == 8
        assert res.lantern_oil_flasks == 3

    def test_game_state_preserved(self, dm_with_state, temp_save_dir):
        """Current game state is preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        assert dm2.current_state == GameState.WILDERNESS_TRAVEL


class TestExplorationPreservation:
    """Test exploration state is preserved through save/load."""

    def test_explored_hexes_preserved(self, dm_with_state, temp_save_dir):
        """Explored hexes are preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        assert "0709" in dm2.hex_crawl._explored_hexes
        assert "0710" in dm2.hex_crawl._explored_hexes

    def test_met_npcs_preserved(self, dm_with_state, temp_save_dir):
        """Met NPCs are preserved."""
        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        assert "blackwood_elder" in dm2.hex_crawl._met_npcs


class TestCombatStatePreservation:
    """Test combat state is preserved through save/load."""

    def test_ongoing_combat_preserved(self, dm_with_state, temp_save_dir):
        """Ongoing combat is preserved."""
        from src.combat.combat_engine import CombatState, CombatantStatus

        # Set up a mock combat state with correct Combatant structure
        enemy = Combatant(
            combatant_id="goblin_1",
            name="Goblin",
            side="enemy",
            stat_block=StatBlock(
                armor_class=13,
                hit_dice="1d8",
                hp_current=5,
                hp_max=7,
                movement=30,
                attacks=["dagger (1d4)"],
                morale=7,
                save_as="F1",
            ),
        )

        encounter = EncounterState(
            encounter_id="test_combat",
            combatants=[enemy],
        )

        dm_with_state.combat._combat_state = CombatState(
            encounter=encounter,
            round_number=2,
            party_initiative=15,
            enemy_initiative=10,
        )
        dm_with_state.combat._combat_state.is_solo_creature = False
        dm_with_state.combat._combat_state.enemy_starting_count = 1
        dm_with_state.combat._combat_state.enemy_casualties = 0
        dm_with_state.combat._combat_state.combatant_status["goblin_1"] = CombatantStatus(
            combatant_id="goblin_1",
            successful_morale_checks=1,
            is_fleeing=False,
        )
        dm_with_state.combat._return_state = GameState.WILDERNESS_TRAVEL

        # Save
        dm_with_state.save_game(slot=1)

        # Load into new DM
        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        # Verify combat state
        assert dm2.combat._combat_state is not None
        cs = dm2.combat._combat_state
        assert cs.round_number == 2
        assert cs.party_initiative == 15
        assert cs.enemy_initiative == 10
        assert len(cs.encounter.combatants) == 1
        assert cs.encounter.combatants[0].name == "Goblin"
        assert cs.encounter.combatants[0].stat_block.hp_current == 5
        assert "goblin_1" in cs.combatant_status
        assert cs.combatant_status["goblin_1"].successful_morale_checks == 1


class TestEncounterStatePreservation:
    """Test encounter state is preserved through save/load."""

    def test_ongoing_encounter_preserved(self, dm_with_state, temp_save_dir):
        """Ongoing encounter is preserved."""
        from src.encounter.encounter_engine import (
            EncounterEngineState,
            EncounterPhase,
            EncounterOrigin,
        )

        # Set up a mock encounter state with correct Combatant structure
        enemy = Combatant(
            combatant_id="bandit_1",
            name="Bandit",
            side="enemy",
            stat_block=StatBlock(
                armor_class=12,
                hit_dice="1d8",
                hp_current=8,
                hp_max=8,
                movement=30,
                attacks=["sword (1d6)"],
                morale=8,
                save_as="F1",
            ),
        )

        encounter = EncounterState(
            encounter_id="test_encounter",
            encounter_type=EncounterType.MONSTER,
            distance=60,
            party_initiative=12,
            enemy_initiative=8,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            combatants=[enemy],
        )

        dm_with_state.encounter._state = EncounterEngineState(
            encounter=encounter,
            origin=EncounterOrigin.WILDERNESS,
            current_phase=EncounterPhase.INITIATIVE,
        )
        dm_with_state.encounter._state.reaction_attempted = True

        # Save
        dm_with_state.save_game(slot=1)

        # Load into new DM
        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        # Verify encounter state
        assert dm2.encounter._state is not None
        es = dm2.encounter._state
        assert es.current_phase == EncounterPhase.INITIATIVE
        assert es.origin == EncounterOrigin.WILDERNESS
        assert es.reaction_attempted is True
        assert es.encounter.distance == 60
        assert es.encounter.party_initiative == 12
        assert es.encounter.surprise_status == SurpriseStatus.NO_SURPRISE


class TestMultipleSlots:
    """Test saving to and loading from multiple slots."""

    def test_different_slots_independent(self, temp_save_dir):
        """Different slots contain independent saves."""
        # Save to slot 1 with 2 characters
        config1 = GameConfig(
            save_dir=temp_save_dir,
            campaign_name="Campaign A",
            enable_narration=False,
            use_vector_db=False,
        )
        dm1 = VirtualDM(config=config1, game_date=GameDate(year=1, month=1, day=1))
        dm1.create_character("char_a1", "Alice", "Fighter", 1, {}, 10)
        dm1.create_character("char_a2", "Bob", "Thief", 1, {}, 8)
        dm1.save_game(slot=1)

        # Save to slot 2 with 1 character
        config2 = GameConfig(
            save_dir=temp_save_dir,
            campaign_name="Campaign B",
            enable_narration=False,
            use_vector_db=False,
        )
        dm2 = VirtualDM(config=config2, game_date=GameDate(year=5, month=7, day=20))
        dm2.create_character("char_b1", "Charlie", "Magic-User", 3, {}, 12)
        dm2.save_game(slot=2)

        # Load slot 1 - should have 2 characters from year 1
        dm_load1 = VirtualDM(
            config=GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        )
        dm_load1.load_game(slot=1)
        assert len(dm_load1.get_party()) == 2
        assert dm_load1.controller.world_state.current_date.year == 1

        # Load slot 2 - should have 1 character from year 5
        dm_load2 = VirtualDM(
            config=GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        )
        dm_load2.load_game(slot=2)
        assert len(dm_load2.get_party()) == 1
        assert dm_load2.get_character("char_b1").name == "Charlie"
        assert dm_load2.controller.world_state.current_date.year == 5


class TestEdgeCases:
    """Test edge cases for save/load."""

    def test_load_nonexistent_slot_returns_false(self, temp_save_dir):
        """Loading from empty slot returns False."""
        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm = VirtualDM(config=config)
        success = dm.load_game(slot=5)
        assert success is False

    def test_invalid_slot_raises(self, dm_with_state):
        """Invalid slot numbers raise ValueError."""
        with pytest.raises(ValueError):
            dm_with_state.save_game(slot=0)

        with pytest.raises(ValueError):
            dm_with_state.save_game(slot=10)

        with pytest.raises(ValueError):
            dm_with_state.load_game(slot=0)

    def test_overwrite_save(self, dm_with_state, temp_save_dir):
        """Saving to same slot overwrites."""
        # Save with 2 chars
        dm_with_state.save_game(slot=1)

        # Add another character and save again
        dm_with_state.create_character("char3", "Third", "Cleric", 1, {}, 10)
        dm_with_state.save_game(slot=1)

        # Load - should have 3 characters
        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)
        assert len(dm2.get_party()) == 3


class TestGameStateRestoration:
    """
    Test that game state (GameState enum) is properly restored.

    P0-1: These tests verify the fix for save/load state restoration
    where the game state wasn't being properly restored to the state machine.
    """

    def test_game_state_preserved_default(self, dm_with_state, temp_save_dir):
        """Default WILDERNESS_TRAVEL state is preserved."""
        # dm_with_state starts in WILDERNESS_TRAVEL
        assert dm_with_state.current_state == GameState.WILDERNESS_TRAVEL

        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        assert dm2.current_state == GameState.WILDERNESS_TRAVEL

    def test_dungeon_state_preserved(self, dm_with_state, temp_save_dir):
        """DUNGEON_EXPLORATION state is properly restored."""
        # Transition to dungeon state
        dm_with_state.controller.state_machine.force_state(
            GameState.DUNGEON_EXPLORATION,
            reason="test setup",
        )
        assert dm_with_state.current_state == GameState.DUNGEON_EXPLORATION

        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        # Should restore to DUNGEON_EXPLORATION
        assert dm2.current_state == GameState.DUNGEON_EXPLORATION

    def test_encounter_state_with_encounter_restored(self, dm_with_state, temp_save_dir):
        """ENCOUNTER state restores controller.current_encounter."""
        from src.encounter.encounter_engine import (
            EncounterEngineState,
            EncounterPhase,
            EncounterOrigin,
        )

        # Set up encounter
        enemy = Combatant(
            combatant_id="orc_1",
            name="Orc",
            side="enemy",
            stat_block=StatBlock(
                armor_class=13,
                hit_dice="1d8",
                hp_current=7,
                hp_max=7,
                movement=30,
                attacks=["axe (1d8)"],
                morale=8,
                save_as="F1",
            ),
        )

        encounter = EncounterState(
            encounter_id="test_enc",
            encounter_type=EncounterType.MONSTER,
            distance=60,
            party_initiative=10,
            enemy_initiative=8,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            combatants=[enemy],
        )

        dm_with_state.encounter._state = EncounterEngineState(
            encounter=encounter,
            origin=EncounterOrigin.WILDERNESS,
            current_phase=EncounterPhase.INITIATIVE,
        )

        # Force state to ENCOUNTER
        dm_with_state.controller.set_encounter(encounter)
        dm_with_state.controller.state_machine.force_state(
            GameState.ENCOUNTER,
            reason="test setup",
        )

        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        # Should restore ENCOUNTER state
        assert dm2.current_state == GameState.ENCOUNTER
        # Controller should have the encounter set
        assert dm2.controller.get_encounter() is not None
        assert dm2.controller.get_encounter().encounter_id == "test_enc"

    def test_combat_state_restored_with_encounter(self, dm_with_state, temp_save_dir):
        """COMBAT state restores with controller.current_encounter set."""
        from src.combat.combat_engine import CombatState, CombatantStatus

        # Set up combat
        enemy = Combatant(
            combatant_id="troll_1",
            name="Troll",
            side="enemy",
            stat_block=StatBlock(
                armor_class=15,
                hit_dice="6d8",
                hp_current=30,
                hp_max=36,
                movement=40,
                attacks=["claw (1d6)", "claw (1d6)", "bite (1d10)"],
                morale=10,
                save_as="F6",
            ),
        )

        encounter = EncounterState(
            encounter_id="combat_test",
            encounter_type=EncounterType.MONSTER,
            combatants=[enemy],
        )

        dm_with_state.combat._combat_state = CombatState(
            encounter=encounter,
            round_number=3,
            party_initiative=12,
            enemy_initiative=8,
        )
        dm_with_state.combat._return_state = GameState.WILDERNESS_TRAVEL

        # Force state to COMBAT
        dm_with_state.controller.set_encounter(encounter)
        dm_with_state.controller.state_machine.force_state(
            GameState.COMBAT,
            reason="test setup",
        )

        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        # Should restore COMBAT state
        assert dm2.current_state == GameState.COMBAT
        # Controller should have encounter set
        assert dm2.controller.get_encounter() is not None

    def test_previous_state_restored(self, dm_with_state, temp_save_dir):
        """Previous state is preserved for return_to_previous."""
        # Transition to dungeon, then to encounter
        dm_with_state.controller.state_machine.force_state(
            GameState.DUNGEON_EXPLORATION,
            reason="test setup",
        )
        # Set a previous state
        dm_with_state.controller.state_machine._previous_state = GameState.WILDERNESS_TRAVEL

        dm_with_state.save_game(slot=1)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm2 = VirtualDM(config=config)
        dm2.load_game(slot=1)

        assert dm2.current_state == GameState.DUNGEON_EXPLORATION
        assert dm2.controller.state_machine._previous_state == GameState.WILDERNESS_TRAVEL

    def test_combat_without_encounter_downgrades_gracefully(self, temp_save_dir):
        """Loading COMBAT without encounter data downgrades to safe state."""
        # Create a save file manually that has COMBAT but no encounter
        import json

        save_path = temp_save_dir / "slot_1.json"
        save_data = {
            "session_name": "Test",
            "last_saved_at": "2024-01-01",
            "world_state": {},
            "party_state": {},
            "characters": [],
            "hex_exploration": {},
            "custom_data": {
                "current_game_state": "combat",
                # No combat_state or encounter_state
            },
        }
        with open(save_path, "w") as f:
            json.dump(save_data, f)

        config = GameConfig(save_dir=temp_save_dir, enable_narration=False, use_vector_db=False)
        dm = VirtualDM(config=config)
        dm.load_game(slot=1)

        # Should downgrade to WILDERNESS_TRAVEL (not crash)
        assert dm.current_state == GameState.WILDERNESS_TRAVEL
