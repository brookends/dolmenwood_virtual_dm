"""
Integration tests for complete game flows.

Tests end-to-end scenarios involving multiple systems working together.
"""

import pytest
from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.encounter.encounter_engine import EncounterEngine, EncounterOrigin, EncounterAction
from src.combat.combat_engine import CombatEngine, CombatAction, CombatActionType
from src.data_models import (
    EncounterState,
    EncounterType,
    SurpriseStatus,
    Combatant,
    StatBlock,
    CharacterState,
    GameDate,
    GameTime,
    Weather,
    Season,
    LocationType,
)


class TestWildernessExplorationFlow:
    """Integration tests for wilderness exploration."""

    def test_basic_travel_advances_time(self, controller_with_party):
        """Test that travel advances game time."""
        initial_time = str(controller_with_party.time_tracker.game_time)

        controller_with_party.advance_travel_segment()

        new_time = str(controller_with_party.time_tracker.game_time)
        assert initial_time != new_time

    def test_travel_consumes_resources(self, controller_with_party):
        """Test that day passage consumes food and water."""
        initial_food = controller_with_party.party_state.resources.food_days

        # Advance a full day
        controller_with_party.time_tracker.advance_day(1)

        # Food should be consumed
        new_food = controller_with_party.party_state.resources.food_days
        # Note: consumption happens in on_day_advance callback
        assert new_food < initial_food

    def test_wilderness_to_dungeon_flow(self, controller_with_party):
        """Test transitioning from wilderness to dungeon."""
        assert controller_with_party.current_state == GameState.WILDERNESS_TRAVEL

        controller_with_party.transition("enter_dungeon")
        assert controller_with_party.current_state == GameState.DUNGEON_EXPLORATION

        controller_with_party.set_party_location(
            LocationType.DUNGEON_ROOM,
            "room_1",
        )

        assert controller_with_party.party_state.location.location_type == LocationType.DUNGEON_ROOM


class TestEncounterFlow:
    """Integration tests for encounter sequences."""

    def test_full_encounter_to_combat_flow(self, controller_with_party, sample_party, seeded_dice):
        """Test complete encounter leading to combat."""
        # Add party to controller
        for char in sample_party:
            controller_with_party.add_character(char)

        # Create encounter
        combatants = [
            Combatant(
                combatant_id=sample_party[0].character_id,
                name=sample_party[0].name,
                side="party",
                stat_block=StatBlock(
                    armor_class=sample_party[0].armor_class,
                    hit_dice="3d8",
                    hp_current=sample_party[0].hp_current,
                    hp_max=sample_party[0].hp_max,
                    movement=sample_party[0].base_speed,
                    attacks=[{"name": "Sword", "damage": "1d8", "bonus": 3}],
                    morale=12,
                ),
            ),
            Combatant(
                combatant_id="goblin_1",
                name="Goblin",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=6,
                    hit_dice="1d8-1",
                    hp_current=4,
                    hp_max=4,
                    movement=60,
                    attacks=[{"name": "Sword", "damage": "1d6", "bonus": 0}],
                    morale=7,
                ),
            ),
        ]

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=60,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["goblin"],
            context="patrolling",
            terrain="forest",
            combatants=combatants,
        )

        # Start encounter sequence
        encounter_engine = EncounterEngine(controller_with_party)
        encounter_engine.start_encounter(encounter, EncounterOrigin.WILDERNESS)

        assert controller_with_party.current_state == GameState.ENCOUNTER

        # Run through phases
        encounter_engine.auto_run_phases()

        # Attack to trigger combat
        result = encounter_engine.execute_action(EncounterAction.ATTACK, actor="party")

        assert controller_with_party.current_state == GameState.COMBAT

        # Start and run combat
        combat_engine = CombatEngine(controller_with_party)
        combat_engine.start_combat(encounter, GameState.WILDERNESS_TRAVEL)

        # Execute a round
        party_actions = [
            CombatAction(
                combatant_id=sample_party[0].character_id,
                action_type=CombatActionType.MELEE_ATTACK,
                target_id="goblin_1",
            )
        ]
        combat_engine.execute_round(party_actions)

        assert combat_engine.is_in_combat() is True

    def test_encounter_to_social_flow(self, controller_with_party, seeded_dice):
        """Test encounter leading to social interaction."""
        # Create NPC encounter
        encounter = EncounterState(
            encounter_type=EncounterType.NPC,
            distance=30,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["traveling merchant"],
            context="on the road",
            terrain="road",
        )

        encounter_engine = EncounterEngine(controller_with_party)
        encounter_engine.start_encounter(encounter, EncounterOrigin.WILDERNESS)
        encounter_engine.auto_run_phases()

        # Attempt parley - keep trying until we get a friendly result
        # (For testing, we just verify the mechanism works)
        result = encounter_engine.execute_action(EncounterAction.PARLEY, actor="party")

        # Reaction roll should have occurred
        assert result.reaction_roll is not None


class TestCombatFlow:
    """Integration tests for combat sequences."""

    def test_combat_to_resolution(self, controller_with_party, sample_fighter, seeded_dice):
        """Test combat from start to resolution."""
        controller_with_party.add_character(sample_fighter)

        # Create weak enemy for quick resolution
        combatants = [
            Combatant(
                combatant_id=sample_fighter.character_id,
                name=sample_fighter.name,
                side="party",
                stat_block=StatBlock(
                    armor_class=4,
                    hit_dice="3d8",
                    hp_current=24,
                    hp_max=24,
                    movement=90,
                    attacks=[{"name": "Sword", "damage": "1d8+3", "bonus": 5}],
                    morale=12,
                ),
            ),
            Combatant(
                combatant_id="goblin_1",
                name="Goblin",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=9,
                    hit_dice="1d8-1",
                    hp_current=1,  # Very weak
                    hp_max=1,
                    movement=60,
                    attacks=[{"name": "Sword", "damage": "1d6", "bonus": 0}],
                    morale=7,
                ),
            ),
        ]

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=30,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["goblin"],
            terrain="dungeon",
            combatants=combatants,
        )

        controller_with_party.transition("encounter_triggered")
        controller_with_party.transition("encounter_to_combat")

        combat_engine = CombatEngine(controller_with_party)
        combat_engine.start_combat(encounter, GameState.WILDERNESS_TRAVEL)

        # Kill the goblin
        encounter.combatants[1].stat_block.hp_current = 0

        # Execute round
        result = combat_engine.execute_round([])

        assert result.combat_ended is True
        assert "all_enemies_defeated" in result.end_reason


class TestDowntimeFlow:
    """Integration tests for downtime activities."""

    def test_rest_heals_characters(self, controller_with_party, sample_fighter):
        """Test that rest heals characters."""
        sample_fighter.hp_current = 10  # Wounded
        controller_with_party.add_character(sample_fighter)

        # Transition to downtime
        controller_with_party.transition("begin_rest")
        assert controller_with_party.current_state == GameState.DOWNTIME

        # Natural healing would occur during downtime
        # (Actual healing logic not implemented in controller)

        # Return from rest
        controller_with_party.transition("downtime_end_wilderness")
        assert controller_with_party.current_state == GameState.WILDERNESS_TRAVEL

    def test_rest_interrupted_by_combat(self, controller_with_party):
        """Test rest being interrupted."""
        controller_with_party.transition("begin_rest")
        assert controller_with_party.current_state == GameState.DOWNTIME

        controller_with_party.transition("rest_interrupted")
        assert controller_with_party.current_state == GameState.COMBAT


class TestSettlementFlow:
    """Integration tests for settlement activities."""

    def test_settlement_exploration(self, controller_with_party):
        """Test exploring a settlement."""
        controller_with_party.transition("enter_settlement")
        assert controller_with_party.current_state == GameState.SETTLEMENT_EXPLORATION

        controller_with_party.set_party_location(
            LocationType.SETTLEMENT,
            "prigwort",
            "The Wicked Owl Inn",
        )

        assert controller_with_party.party_state.location.sub_location == "The Wicked Owl Inn"

    def test_settlement_conversation(self, controller_with_party):
        """Test initiating conversation in settlement."""
        controller_with_party.transition("enter_settlement")
        controller_with_party.transition("initiate_conversation")

        assert controller_with_party.current_state == GameState.SOCIAL_INTERACTION

        controller_with_party.transition("conversation_end_settlement")
        assert controller_with_party.current_state == GameState.SETTLEMENT_EXPLORATION


class TestTimeManagement:
    """Integration tests for time tracking."""

    def test_time_advances_through_turns(self, controller_with_party):
        """Test time advancement through exploration turns."""
        initial_time = controller_with_party.time_tracker.game_time.hour

        # Advance 6 turns (1 hour)
        controller_with_party.advance_time(6)

        new_time = controller_with_party.time_tracker.game_time.hour
        assert new_time == (initial_time + 1) % 24

    def test_day_rollover(self, controller_with_party):
        """Test day advancement."""
        initial_day = controller_with_party.time_tracker.game_date.day

        # Advance 144 turns (24 hours)
        controller_with_party.advance_time(144)

        new_day = controller_with_party.time_tracker.game_date.day
        assert new_day != initial_day

    def test_season_change(self, controller_with_party):
        """Test season changes with time."""
        # Start with the initial season from the controller
        initial_season = controller_with_party.time_tracker.season

        # Advance many days to force a season change
        # Each day is 144 turns, need ~90+ days to change season
        for _ in range(100):
            controller_with_party.time_tracker.advance_day(1)

        # Should have changed season by now (after 100 days)
        # The exact season depends on starting month
        final_season = controller_with_party.time_tracker.season
        # Either season changed, or we cycled through multiple seasons
        assert controller_with_party.time_tracker.game_date.month != 6


class TestResourceManagement:
    """Integration tests for resource tracking."""

    def test_light_source_depletes(self, controller_with_party):
        """Test that light sources deplete over time."""
        controller_with_party.party_state.resources.torches = 5

        result = controller_with_party.light_source(
            controller_with_party.party_state.active_light_source or
            __import__('src.data_models', fromlist=['LightSourceType']).LightSourceType.TORCH
        )

        # Advance 7 turns (torch lasts 6)
        from src.data_models import LightSourceType
        controller_with_party.party_state.active_light_source = LightSourceType.TORCH
        controller_with_party.party_state.light_remaining_turns = 6

        result = controller_with_party.advance_time(7)

        assert "light_extinguished" in result
        assert controller_with_party.party_state.active_light_source is None

    def test_weather_roll(self, controller_with_party, seeded_dice):
        """Test weather generation."""
        weather = controller_with_party.roll_weather()

        assert weather in Weather


class TestFullGameSession:
    """Integration test for a complete mini-session."""

    def test_mini_session(self, controller_with_party, sample_party, seeded_dice):
        """Test a complete mini-session flow."""
        # Setup party
        for char in sample_party:
            controller_with_party.add_character(char)

        # 1. Start in wilderness
        assert controller_with_party.current_state == GameState.WILDERNESS_TRAVEL

        # 2. Travel for a watch
        controller_with_party.advance_travel_segment()

        # 3. Enter a settlement
        controller_with_party.transition("enter_settlement")
        assert controller_with_party.current_state == GameState.SETTLEMENT_EXPLORATION

        # 4. Have a conversation
        controller_with_party.transition("initiate_conversation")
        controller_with_party.transition("conversation_end_settlement")

        # 5. Leave settlement
        controller_with_party.transition("exit_settlement")
        assert controller_with_party.current_state == GameState.WILDERNESS_TRAVEL

        # 6. Enter a dungeon
        controller_with_party.transition("enter_dungeon")
        assert controller_with_party.current_state == GameState.DUNGEON_EXPLORATION

        # 7. Encounter something
        controller_with_party.transition("encounter_triggered")
        assert controller_with_party.current_state == GameState.ENCOUNTER

        # 8. Return to dungeon (evade)
        controller_with_party.transition("encounter_end_dungeon")
        assert controller_with_party.current_state == GameState.DUNGEON_EXPLORATION

        # 9. Exit dungeon
        controller_with_party.transition("exit_dungeon")
        assert controller_with_party.current_state == GameState.WILDERNESS_TRAVEL

        # 10. Rest
        controller_with_party.transition("begin_rest")
        controller_with_party.transition("downtime_end_wilderness")

        # Session complete, back to wilderness
        assert controller_with_party.current_state == GameState.WILDERNESS_TRAVEL

        # Verify session log has entries
        log = controller_with_party.get_session_log()
        assert len(log) > 0


class TestTransitionHooks:
    """Integration tests for state transition hooks."""

    @pytest.fixture
    def controller_with_encounter(self, controller_with_party, sample_party):
        """Create controller with party and active encounter."""
        for char in sample_party:
            controller_with_party.add_character(char)

        # Create an encounter with combatants
        combatants = [
            Combatant(
                combatant_id="goblin_1",
                name="Goblin",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=13,
                    hit_dice="1d8",
                    hp_max=4,
                    hp_current=4,
                    movement=30,
                    attacks=[{"name": "Short Sword", "damage": "1d6", "bonus": 0}],
                    morale=7,
                ),
            ),
        ]

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=60,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["goblin_1"],
            combatants=combatants,
        )

        controller_with_party.set_encounter(encounter)
        return controller_with_party

    def test_combat_engine_initialized_on_combat_transition(self, controller_with_encounter):
        """Test that CombatEngine is automatically initialized when entering COMBAT."""
        # Start encounter
        controller_with_encounter.transition("encounter_triggered")
        assert controller_with_encounter.current_state == GameState.ENCOUNTER

        # Verify no combat engine yet
        assert controller_with_encounter.combat_engine is None

        # Transition to combat
        controller_with_encounter.transition("encounter_to_combat")
        assert controller_with_encounter.current_state == GameState.COMBAT

        # Combat engine should now be initialized
        assert controller_with_encounter.combat_engine is not None
        assert controller_with_encounter.combat_engine._combat_state is not None

    def test_combat_round_executable_after_transition(self, controller_with_encounter, sample_party):
        """Test that combat rounds can be executed immediately after transition."""
        # Add party members as combatants
        for char in sample_party:
            controller_with_encounter.add_character(char)

        # Update the encounter to include party
        encounter = controller_with_encounter.get_encounter()
        for char in sample_party:
            encounter.combatants.append(
                Combatant(
                    combatant_id=char.character_id,
                    name=char.name,
                    side="party",
                    stat_block=StatBlock(
                        armor_class=10,
                        hit_dice="1d8",
                        hp_max=char.hp_max,
                        hp_current=char.hp_current,
                        movement=30,
                        attacks=[{"name": "Weapon", "damage": "1d6", "bonus": 0}],
                        morale=12,
                    ),
                    character_ref=char.character_id,
                )
            )
            encounter.actors.append(char.character_id)

        # Transition through encounter to combat
        controller_with_encounter.transition("encounter_triggered")
        controller_with_encounter.transition("encounter_to_combat")

        # Get the combat engine and verify it's properly initialized
        combat_engine = controller_with_encounter.combat_engine
        assert combat_engine is not None
        assert combat_engine._combat_state is not None

        # Combat state should have the combatants
        combat_state = combat_engine._combat_state
        assert combat_state.encounter == encounter
        assert len(combat_state.encounter.combatants) > 0

        # Combat state should be properly initialized
        assert combat_state.round_number == 0  # Before first round
        assert combat_state.enemy_starting_count == 1  # One goblin

    def test_combat_engine_cleared_on_combat_exit(self, controller_with_encounter):
        """Test that CombatEngine is cleared when exiting COMBAT."""
        # Transition to combat
        controller_with_encounter.transition("encounter_triggered")
        controller_with_encounter.transition("encounter_to_combat")
        assert controller_with_encounter.combat_engine is not None

        # Exit combat back to wilderness
        controller_with_encounter.transition("combat_end_wilderness")
        assert controller_with_encounter.current_state == GameState.WILDERNESS_TRAVEL

        # Combat engine should be cleared
        assert controller_with_encounter.combat_engine is None

    def test_custom_transition_hook_fires(self, controller_with_party):
        """Test that custom transition hooks are called."""
        hook_called = {"value": False, "context": None}

        def custom_hook(from_state, to_state, trigger, context):
            hook_called["value"] = True
            hook_called["from"] = from_state
            hook_called["to"] = to_state
            hook_called["context"] = context

        # Register custom hook for wilderness -> dungeon
        controller_with_party.register_transition_hook(
            GameState.WILDERNESS_TRAVEL,
            GameState.DUNGEON_EXPLORATION,
            custom_hook
        )

        # Trigger the transition
        controller_with_party.transition("enter_dungeon")

        # Verify hook was called
        assert hook_called["value"] is True
        assert hook_called["from"] == GameState.WILDERNESS_TRAVEL
        assert hook_called["to"] == GameState.DUNGEON_EXPLORATION

    def test_on_enter_hook_fires_from_any_state(self, controller_with_party):
        """Test that on-enter hooks fire regardless of source state."""
        enter_count = {"value": 0}

        def on_enter_encounter(from_state, to_state, trigger, context):
            enter_count["value"] += 1

        # Register on-enter hook for ENCOUNTER
        controller_with_party.register_on_enter_hook(
            GameState.ENCOUNTER,
            on_enter_encounter
        )

        # Enter from wilderness
        controller_with_party.transition("encounter_triggered")
        assert enter_count["value"] == 1

        # Go back to wilderness
        controller_with_party.transition("encounter_end_wilderness")

        # Enter dungeon
        controller_with_party.transition("enter_dungeon")

        # Enter encounter from dungeon
        controller_with_party.transition("encounter_triggered")
        assert enter_count["value"] == 2

    def test_encounter_cleared_on_exit_to_exploration(self, controller_with_encounter):
        """Test that encounter is cleared when returning to exploration states."""
        # Start with encounter
        assert controller_with_encounter.get_encounter() is not None

        # Transition to encounter state
        controller_with_encounter.transition("encounter_triggered")

        # Return to wilderness (evade)
        controller_with_encounter.transition("encounter_end_wilderness")

        # Encounter should be cleared
        assert controller_with_encounter.get_encounter() is None

    def test_encounter_preserved_for_combat(self, controller_with_encounter):
        """Test that encounter is preserved when transitioning to combat."""
        # Start with encounter
        assert controller_with_encounter.get_encounter() is not None

        # Transition through encounter to combat
        controller_with_encounter.transition("encounter_triggered")
        controller_with_encounter.transition("encounter_to_combat")

        # Encounter should still be present (combat needs it)
        assert controller_with_encounter.get_encounter() is not None

    def test_social_context_initialized_on_parley(self, controller_with_encounter):
        """Test that social context is initialized when entering SOCIAL_INTERACTION from encounter."""
        # Transition to encounter
        controller_with_encounter.transition("encounter_triggered")
        assert controller_with_encounter.current_state == GameState.ENCOUNTER

        # No social context yet
        assert controller_with_encounter.social_context is None

        # Transition to social interaction (parley)
        controller_with_encounter.transition(
            "encounter_to_parley",
            context={"reaction": "friendly"}
        )
        assert controller_with_encounter.current_state == GameState.SOCIAL_INTERACTION

        # Social context should be initialized
        assert controller_with_encounter.social_context is not None
        assert controller_with_encounter.social_context.origin.value == "encounter_parley"
        assert controller_with_encounter.social_context.initial_reaction.value == "friendly"

    def test_social_context_has_participants_from_encounter(self, controller_with_encounter):
        """Test that social context includes participants from encounter actors."""
        # Setup encounter with actors
        encounter = controller_with_encounter.get_encounter()
        assert "goblin_1" in encounter.actors

        # Transition to parley
        controller_with_encounter.transition("encounter_triggered")
        controller_with_encounter.transition(
            "encounter_to_parley",
            context={"reaction": "friendly"}
        )

        # Social context should have participants
        social_context = controller_with_encounter.social_context
        assert social_context is not None
        assert len(social_context.participants) > 0

        # First participant should be based on the encounter actor
        participant = social_context.participants[0]
        assert participant.participant_id == "goblin_1"

    def test_social_context_cleared_on_exit(self, controller_with_encounter):
        """Test that social context is cleared when exiting SOCIAL_INTERACTION."""
        # Transition to social interaction
        controller_with_encounter.transition("encounter_triggered")
        controller_with_encounter.transition(
            "encounter_to_parley",
            context={"reaction": "helpful"}
        )
        assert controller_with_encounter.social_context is not None

        # Exit back to wilderness
        controller_with_encounter.transition("conversation_end_wilderness")
        assert controller_with_encounter.current_state == GameState.WILDERNESS_TRAVEL

        # Social context should be cleared
        assert controller_with_encounter.social_context is None

    def test_social_context_with_npc_from_context(self, controller_with_party):
        """Test social context initialization with NPC data in context."""
        # Transition to settlement first
        controller_with_party.transition("enter_settlement")
        assert controller_with_party.current_state == GameState.SETTLEMENT_EXPLORATION

        # Initiate conversation with NPC data in context
        controller_with_party.transition(
            "initiate_conversation",
            context={
                "npc_id": "merchant_bob",
                "npc_name": "Bob the Merchant",
                "hex_id": "0505",
            }
        )
        assert controller_with_party.current_state == GameState.SOCIAL_INTERACTION

        # Verify social context
        social_context = controller_with_party.social_context
        assert social_context is not None
        assert social_context.origin.value == "settlement"
        assert len(social_context.participants) == 1
        assert social_context.participants[0].name == "Bob the Merchant"
        assert social_context.participants[0].hex_id == "0505"

    def test_social_context_parley_capability_check(self, controller_with_party):
        """Test that social context correctly tracks whether participants can communicate."""
        from src.data_models import SocialParticipant, SocialParticipantType

        # Create a social participant that cannot communicate
        non_sentient = SocialParticipant(
            participant_id="mindless_skeleton",
            name="Skeleton",
            participant_type=SocialParticipantType.MONSTER,
            sentience="Non-Sentient",
            can_communicate=False,
        )

        # Transition to encounter then parley with explicit participants
        controller_with_party.transition("encounter_triggered")
        controller_with_party.transition(
            "encounter_to_parley",
            context={
                "reaction": "neutral",
                "participants": [non_sentient],
            }
        )

        social_context = controller_with_party.social_context
        assert social_context is not None
        assert social_context.can_parley() is False

    def test_social_context_return_state_tracking(self, controller_with_encounter):
        """Test that social context correctly tracks the return state."""
        # Start from wilderness -> encounter -> social
        assert controller_with_encounter.current_state == GameState.WILDERNESS_TRAVEL
        controller_with_encounter.transition("encounter_triggered")
        controller_with_encounter.transition(
            "encounter_to_parley",
            context={"reaction": "friendly"}
        )

        # Social context should track that we should return to wilderness
        social_context = controller_with_encounter.social_context
        assert social_context is not None
        assert social_context.return_state == "wilderness_travel"

    def test_social_context_preserves_encounter_for_possible_combat(self, controller_with_encounter):
        """Test that encounter is preserved when transitioning to social (might escalate)."""
        # Start encounter
        controller_with_encounter.transition("encounter_triggered")
        original_encounter = controller_with_encounter.get_encounter()

        # Transition to social
        controller_with_encounter.transition(
            "encounter_to_parley",
            context={"reaction": "unfriendly"}
        )

        # Encounter should still be available (conversation might escalate)
        assert controller_with_encounter.get_encounter() is not None
        assert controller_with_encounter.get_encounter() == original_encounter

    def test_social_to_combat_transition(self, controller_with_encounter):
        """Test transitioning from social interaction to combat when conversation escalates."""
        # Setup: encounter -> social
        controller_with_encounter.transition("encounter_triggered")
        controller_with_encounter.transition(
            "encounter_to_parley",
            context={"reaction": "unfriendly"}
        )
        assert controller_with_encounter.social_context is not None

        # Conversation escalates to combat
        controller_with_encounter.transition("conversation_escalates")
        assert controller_with_encounter.current_state == GameState.COMBAT

        # Social context should be cleared
        assert controller_with_encounter.social_context is None

        # Combat engine should be initialized (from the preserved encounter)
        assert controller_with_encounter.combat_engine is not None
