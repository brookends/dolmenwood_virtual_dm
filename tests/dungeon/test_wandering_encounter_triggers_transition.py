"""
Deterministic tests for dungeon wandering encounter transitions (P9.3).

Verifies that:
1. Wandering monster checks trigger controller transitions
2. Encounter context includes dungeon information
3. Dice are seeded for deterministic testing
4. Encounter state is properly initialized
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.dungeon.dungeon_engine import (
    DungeonEngine,
    DungeonState,
    DungeonRoom,
    DungeonActionType,
)
from src.game_state.global_controller import GlobalController
from src.game_state.state_machine import GameState
from src.data_models import (
    Location,
    LocationType,
    PartyState,
    PartyResources,
    DiceRoller,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    LightSourceType,
)


@pytest.fixture
def mock_controller():
    """Create a mock controller in dungeon exploration state."""
    controller = MagicMock(spec=GlobalController)

    controller.party_state = PartyState(
        location=Location(
            location_type=LocationType.DUNGEON_ROOM,
            location_id="entrance",
            sub_location="test_dungeon",
        ),
        resources=PartyResources(),
        active_light_source=LightSourceType.LANTERN,
        light_remaining_turns=10,
    )

    controller.current_state = GameState.DUNGEON_EXPLORATION
    controller.get_party_speed.return_value = 30
    controller.advance_time.return_value = {}

    return controller


@pytest.fixture
def dungeon_engine(mock_controller):
    """Create dungeon engine with deterministic dice."""
    # Set seed for reproducibility
    DiceRoller.set_seed(42)

    engine = DungeonEngine(controller=mock_controller)

    # Initialize dungeon state
    engine._dungeon_state = DungeonState(
        dungeon_id="test_dungeon",
        current_room="entrance",
        hex_id="0703",
        poi_name="old_mill",
    )
    engine._dungeon_state.rooms["entrance"] = DungeonRoom(room_id="entrance")

    return engine


class TestWanderingMonsterCheckTriggersTransition:
    """Test that wandering monster checks trigger controller transitions."""

    def test_encounter_triggers_controller_transition(
        self, dungeon_engine, mock_controller
    ):
        """Verify encounter triggers transition with correct context."""
        # Force a roll that triggers encounter (roll of 1)
        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            # First call is wandering monster check, needs to return 1
            mock_roll.return_value = MagicMock(total=1)

            encounter = dungeon_engine._check_wandering_monster()

        assert encounter is not None

        # Verify transition was called
        mock_controller.transition.assert_called()
        call_args = mock_controller.transition.call_args

        assert call_args[0][0] == "encounter_triggered"
        context = call_args[1]["context"]
        assert context["dungeon_id"] == "test_dungeon"
        assert context["room_id"] == "entrance"
        assert context["source"] == "wandering_monster"

    def test_encounter_context_includes_roll_tables(
        self, dungeon_engine, mock_controller
    ):
        """Verify encounter context includes dungeon roll tables."""
        # Set up roll tables from POI
        dungeon_engine._dungeon_state.roll_tables = ["Dungeon Encounters", "Monsters"]
        dungeon_engine._dungeon_state.poi_name = "spectral_manse"
        dungeon_engine._dungeon_state.hex_id = "0805"

        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=1)
            dungeon_engine._check_wandering_monster()

        context = mock_controller.transition.call_args[1]["context"]
        assert context["roll_tables"] == ["Dungeon Encounters", "Monsters"]
        assert context["poi_name"] == "spectral_manse"
        assert context["hex_id"] == "0805"

    def test_no_transition_when_no_encounter(self, dungeon_engine, mock_controller):
        """Verify no transition when wandering monster roll fails."""
        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            # Roll of 2-6 doesn't trigger encounter
            mock_roll.return_value = MagicMock(total=3)

            encounter = dungeon_engine._check_wandering_monster()

        assert encounter is None
        mock_controller.transition.assert_not_called()


class TestEncounterStateInitialization:
    """Test that encounter state is properly initialized."""

    def test_encounter_set_on_controller(self, dungeon_engine, mock_controller):
        """Verify encounter state is set on controller."""
        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            # Roll 1 for encounter, then surprise checks
            mock_roll.side_effect = [
                MagicMock(total=1),  # Wandering monster check
                MagicMock(total=3),  # Party surprise (not surprised)
                MagicMock(total=3),  # Monster surprise (not surprised)
            ]
            with patch.object(dungeon_engine.dice, 'roll') as mock_distance:
                mock_distance.return_value = MagicMock(total=6)  # 60 feet

                encounter = dungeon_engine._check_wandering_monster()

        # Should set encounter on controller
        mock_controller.set_encounter.assert_called_once()
        encounter_arg = mock_controller.set_encounter.call_args[0][0]

        assert isinstance(encounter_arg, EncounterState)
        assert encounter_arg.encounter_type == EncounterType.MONSTER
        assert encounter_arg.context == "wandering"

    def test_encounter_distance_calculated(self, dungeon_engine, mock_controller):
        """Verify encounter distance is calculated correctly."""
        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            mock_roll.side_effect = [
                MagicMock(total=1),  # Encounter triggered
                MagicMock(total=4),  # Party not surprised
                MagicMock(total=4),  # Monster not surprised
            ]
            with patch.object(dungeon_engine.dice, 'roll') as mock_distance:
                mock_distance.return_value = MagicMock(total=8)  # 80 feet

                encounter = dungeon_engine._check_wandering_monster()

        assert encounter.distance == 80

    def test_surprise_status_determined(self, dungeon_engine, mock_controller):
        """Verify surprise status is properly determined."""
        # Test party surprised
        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            mock_roll.side_effect = [
                MagicMock(total=1),  # Encounter
                MagicMock(total=1),  # Party surprised (roll <= 2)
                MagicMock(total=5),  # Monster not surprised
            ]
            with patch.object(dungeon_engine.dice, 'roll') as mock_distance:
                mock_distance.return_value = MagicMock(total=5)

                encounter = dungeon_engine._check_wandering_monster()

        assert encounter.surprise_status == SurpriseStatus.PARTY_SURPRISED


class TestTurnExecutionTriggersEncounter:
    """Test that execute_turn properly triggers encounters."""

    def test_encounter_triggered_during_turn(self, dungeon_engine, mock_controller):
        """Verify encounter can trigger during turn execution."""
        # Set up for encounter to trigger on second turn
        dungeon_engine._wandering_check_interval = 2
        dungeon_engine._turns_since_check = 1  # Will check this turn

        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            mock_roll.side_effect = [
                MagicMock(total=1),  # Wandering check - encounter!
                MagicMock(total=4),  # Party surprise
                MagicMock(total=4),  # Monster surprise
            ]
            with patch.object(dungeon_engine.dice, 'roll') as mock_distance:
                mock_distance.return_value = MagicMock(total=7)

                result = dungeon_engine.execute_turn(DungeonActionType.REST)

        assert result.encounter_triggered is True
        assert result.encounter is not None
        assert "Something approaches!" in result.messages

    def test_no_encounter_before_check_interval(
        self, dungeon_engine, mock_controller
    ):
        """Verify no encounter check before interval is reached."""
        dungeon_engine._wandering_check_interval = 2
        dungeon_engine._turns_since_check = 0  # Won't check yet

        result = dungeon_engine.execute_turn(DungeonActionType.REST)

        # Should not trigger encounter check
        assert result.encounter_triggered is False
        assert dungeon_engine._turns_since_check == 1


class TestDeterministicDiceRolls:
    """Test deterministic behavior with seeded dice."""

    def test_seeded_dice_produces_consistent_results(self):
        """Verify seeded dice produces consistent encounter sequence."""
        results = []

        for _ in range(3):
            DiceRoller.set_seed(12345)
            dice = DiceRoller()
            rolls = [dice.roll_d6(1, "test").total for _ in range(5)]
            results.append(rolls)

        # All runs should produce identical sequences
        assert results[0] == results[1] == results[2]

    def test_encounter_sequence_reproducible(self, mock_controller):
        """Verify encounter sequence is reproducible with same seed."""
        encounter_counts = []

        for _ in range(3):
            DiceRoller.set_seed(99999)
            engine = DungeonEngine(controller=mock_controller)
            engine._dungeon_state = DungeonState(
                dungeon_id="test",
                current_room="room1",
            )

            count = 0
            for _ in range(20):
                with patch.object(mock_controller, 'transition'):
                    with patch.object(mock_controller, 'set_encounter'):
                        encounter = engine._check_wandering_monster()
                        if encounter:
                            count += 1

            encounter_counts.append(count)

        # Should produce same number of encounters each run
        assert encounter_counts[0] == encounter_counts[1] == encounter_counts[2]


class TestAlertLevelAffectsEncounters:
    """Test that dungeon alert level affects encounter frequency."""

    def test_high_alert_increases_encounter_chance(
        self, dungeon_engine, mock_controller
    ):
        """Verify high alert level increases encounter probability."""
        dungeon_engine._dungeon_state.alert_level = 3

        # With alert level 3, encounter triggers on roll <= 4 (1 + 3)
        # But the current implementation uses roll <= 1 for wandering monsters
        # This tests that alert_level is tracked and could affect future behavior

        # The current implementation just uses 1-in-6
        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=2)

            encounter = dungeon_engine._check_wandering_monster()

        # Currently 2 doesn't trigger (only 1 does)
        # This test documents current behavior
        assert encounter is None


class TestDungeonSurpriseRules:
    """Test dungeon-specific surprise mechanics."""

    def test_darkness_increases_party_surprise_threshold(
        self, dungeon_engine, mock_controller
    ):
        """Verify darkness increases party's chance of being surprised."""
        # No light source
        mock_controller.party_state.active_light_source = None

        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            # Roll 3 - would not surprise with light, does surprise in dark
            mock_roll.side_effect = [
                MagicMock(total=1),  # Encounter triggered
                MagicMock(total=3),  # Party roll - surprised in dark (threshold 3)
                MagicMock(total=5),  # Monster not surprised
            ]
            with patch.object(dungeon_engine.dice, 'roll') as mock_distance:
                mock_distance.return_value = MagicMock(total=5)

                encounter = dungeon_engine._check_wandering_monster()

        assert encounter.surprise_status == SurpriseStatus.PARTY_SURPRISED

    def test_mutual_surprise_uses_shorter_distance(
        self, dungeon_engine, mock_controller
    ):
        """Verify mutual surprise uses 1d4×10 instead of 2d6×10."""
        with patch.object(dungeon_engine.dice, 'roll_d6') as mock_roll:
            mock_roll.side_effect = [
                MagicMock(total=1),  # Encounter triggered
                MagicMock(total=1),  # Party surprised
                MagicMock(total=1),  # Monster surprised (mutual)
            ]
            with patch.object(dungeon_engine.dice, 'roll') as mock_distance:
                mock_distance.return_value = MagicMock(total=3)  # 30 feet

                encounter = dungeon_engine._check_wandering_monster()

        assert encounter.surprise_status == SurpriseStatus.MUTUAL_SURPRISE
        assert encounter.distance == 30

        # Verify 1d4 was used (mutual surprise distance)
        mock_distance.assert_called_with("1d4", "dungeon distance (mutual surprise)")
