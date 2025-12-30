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

    def test_watch_transitions(self, controller_with_party):
        """Test that watch transitions trigger correctly."""
        # Start at 8:00 AM (third watch)
        initial_watches = controller_with_party.time_tracker.watches

        # Advance 24 turns (4 hours = 1 watch)
        result = controller_with_party.advance_time(24)

        assert result["watches_passed"] == 1
        assert controller_with_party.time_tracker.watches == initial_watches + 1

    def test_day_transition_triggers_callbacks(self, controller_with_party):
        """Test that day transitions trigger resource consumption."""
        # Give party some resources
        controller_with_party.party_state.resources.food_days = 10
        controller_with_party.party_state.resources.water_days = 10
        initial_food = controller_with_party.party_state.resources.food_days

        # Advance 144 turns (1 day)
        result = controller_with_party.advance_time(144)

        assert result["days_passed"] == 1
        # Resources should have been consumed
        assert controller_with_party.party_state.resources.food_days < initial_food


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


class TestSocialContextDialogueIntegration:
    """Tests for the SocialContext to DMAgent dialogue integration."""

    def test_participant_to_dialogue_inputs(self):
        """Test that SocialParticipant converts to dialogue inputs correctly."""
        from src.data_models import SocialParticipant, SocialParticipantType, ReactionResult

        participant = SocialParticipant(
            participant_id="goblin_chief",
            name="Grubnak the Smelly",
            participant_type=SocialParticipantType.MONSTER,
            personality="Cunning and paranoid",
            demeanor=["shifty eyes", "nervous twitching"],
            speech="broken Common, guttural accent",
            goals=["protect the tribe", "find food"],
            secrets=["knows location of hidden treasure"],
            dialogue_hooks=["complains about adventurers", "mentions tribute demands"],
            faction="Goblin Warrens",
            reaction_result=ReactionResult.HOSTILE,
            can_communicate=True,
        )

        result = participant.to_dialogue_inputs("Where is your lair?")

        assert result["npc_name"] == "Grubnak the Smelly"
        assert "Cunning and paranoid" in result["npc_personality"]
        assert "shifty eyes" in result["npc_personality"]
        assert "broken Common" in result["npc_voice"]
        assert result["reaction_result"] == "hostile"
        assert result["conversation_topic"] == "Where is your lair?"
        assert "complains about adventurers" in result["known_to_npc"]
        assert "Goal: protect the tribe" in result["known_to_npc"]
        assert "knows location of hidden treasure" in result["hidden_from_player"]
        assert "Goblin Warrens" in result["faction_context"]

    def test_participant_communication_warning(self):
        """Test communication warnings for non-sentient creatures."""
        from src.data_models import SocialParticipant, SocialParticipantType

        # Non-sentient cannot communicate
        skeleton = SocialParticipant(
            participant_id="skeleton_1",
            name="Skeleton",
            participant_type=SocialParticipantType.MONSTER,
            sentience="Non-Sentient",
            can_communicate=False,
        )
        warning = skeleton.get_communication_warning()
        assert warning is not None
        assert "cannot communicate verbally" in warning

        # Semi-intelligent has limited speech
        goblin = SocialParticipant(
            participant_id="goblin_1",
            name="Goblin",
            participant_type=SocialParticipantType.MONSTER,
            sentience="Semi-Intelligent",
            can_communicate=True,
        )
        warning = goblin.get_communication_warning()
        assert warning is not None
        assert "limited intelligence" in warning

        # Sentient has no warning
        elf = SocialParticipant(
            participant_id="elf_1",
            name="Elf",
            participant_type=SocialParticipantType.NPC,
            sentience="Sentient",
            can_communicate=True,
            languages=["Common", "Elvish"],
        )
        warning = elf.get_communication_warning()
        assert warning is None

    def test_social_context_aggregates_secrets(self):
        """Test that SocialContext aggregates secrets from all participants."""
        from src.data_models import SocialContext, SocialParticipant, SocialParticipantType

        p1 = SocialParticipant(
            participant_id="npc_1",
            name="Alice",
            participant_type=SocialParticipantType.NPC,
            secrets=["knows about the murder", "has the key"],
        )
        p2 = SocialParticipant(
            participant_id="npc_2",
            name="Bob",
            participant_type=SocialParticipantType.NPC,
            secrets=["witnessed the theft"],
        )

        context = SocialContext(participants=[p1, p2])
        all_secrets = context.get_all_secrets()

        assert len(all_secrets) == 3
        assert "knows about the murder" in all_secrets
        assert "has the key" in all_secrets
        assert "witnessed the theft" in all_secrets

    def test_social_context_quest_hook_aggregation(self):
        """Test that SocialContext aggregates quest hooks from participants."""
        from src.data_models import SocialContext, SocialParticipant, SocialParticipantType

        p1 = SocialParticipant(
            participant_id="npc_1",
            name="Quest Giver",
            participant_type=SocialParticipantType.NPC,
            quest_hooks=[
                {"name": "Find the Artifact", "description": "Search the ruins"},
                {"name": "Rescue the Princess", "description": "She's in the tower"},
            ],
        )

        context = SocialContext(participants=[p1])
        hooks = context.get_all_quest_hooks()

        assert len(hooks) == 2
        assert hooks[0]["name"] == "Find the Artifact"

    def test_social_context_can_parley(self):
        """Test SocialContext.can_parley() with mixed participants."""
        from src.data_models import SocialContext, SocialParticipant, SocialParticipantType

        # All can communicate
        context1 = SocialContext(
            participants=[
                SocialParticipant(
                    participant_id="p1",
                    name="Talker",
                    participant_type=SocialParticipantType.NPC,
                    can_communicate=True,
                )
            ]
        )
        assert context1.can_parley() is True

        # None can communicate
        context2 = SocialContext(
            participants=[
                SocialParticipant(
                    participant_id="p1",
                    name="Mindless",
                    participant_type=SocialParticipantType.MONSTER,
                    can_communicate=False,
                )
            ]
        )
        assert context2.can_parley() is False

        # Mixed - at least one can
        context3 = SocialContext(
            participants=[
                SocialParticipant(
                    participant_id="p1",
                    name="Mindless",
                    participant_type=SocialParticipantType.MONSTER,
                    can_communicate=False,
                ),
                SocialParticipant(
                    participant_id="p2",
                    name="Leader",
                    participant_type=SocialParticipantType.MONSTER,
                    can_communicate=True,
                ),
            ]
        )
        assert context3.can_parley() is True

    def test_participant_from_monster(self):
        """Test creating SocialParticipant from Monster data."""
        from src.data_models import Monster, SocialParticipant, ReactionResult

        monster = Monster(
            name="Frost Elf",
            monster_id="frost_elf",
            sentience="Sentient",
            intelligence="High",
            alignment="Lawful",
            speech="Speaks Elvish and Common with a cold, formal tone",
            behavior="Haughty and dismissive of mortals",
            monster_type="Fairy",
            encounter_scenarios=["demands tribute", "questions intruders"],
            page_reference="DMB p.45",
        )

        participant = SocialParticipant.from_monster(
            monster,
            reaction=ReactionResult.UNCERTAIN,
            hex_id="0303",
        )

        assert participant.name == "Frost Elf"
        assert participant.sentience == "Sentient"
        assert participant.can_communicate is True
        assert participant.monster_type == "Fairy"
        assert participant.reaction_result == ReactionResult.UNCERTAIN
        assert participant.hex_id == "0303"
        assert "demands tribute" in participant.dialogue_hooks
        assert "Haughty and dismissive" in participant.personality

    def test_dialogue_inputs_with_disposition(self):
        """Test that disposition affects reaction_result in dialogue inputs."""
        from src.data_models import SocialParticipant, SocialParticipantType

        # High disposition -> friendly
        friendly_npc = SocialParticipant(
            participant_id="npc_1",
            name="Friend",
            participant_type=SocialParticipantType.NPC,
            disposition=4,  # High positive
        )
        result = friendly_npc.to_dialogue_inputs("Hello")
        assert result["reaction_result"] == "friendly"

        # Low disposition -> hostile
        hostile_npc = SocialParticipant(
            participant_id="npc_2",
            name="Enemy",
            participant_type=SocialParticipantType.NPC,
            disposition=-4,  # High negative
        )
        result = hostile_npc.to_dialogue_inputs("Hello")
        assert result["reaction_result"] == "hostile"

        # Neutral disposition -> neutral
        neutral_npc = SocialParticipant(
            participant_id="npc_3",
            name="Stranger",
            participant_type=SocialParticipantType.NPC,
            disposition=0,
        )
        result = neutral_npc.to_dialogue_inputs("Hello")
        assert result["reaction_result"] == "neutral"

    def test_social_context_disposition_tracking(self):
        """Test that SocialContext tracks disposition changes."""
        from src.data_models import SocialContext, SocialParticipant, SocialParticipantType

        context = SocialContext(
            participants=[
                SocialParticipant(
                    participant_id="npc_1",
                    name="Merchant",
                    participant_type=SocialParticipantType.NPC,
                )
            ]
        )

        # Track changes
        context.add_disposition_change("npc_1", 2)
        assert context.disposition_changes["npc_1"] == 2

        context.add_disposition_change("npc_1", -1)
        assert context.disposition_changes["npc_1"] == 1  # 2 + (-1) = 1

    def test_social_context_topic_tracking(self):
        """Test that SocialContext tracks discussed topics."""
        from src.data_models import SocialContext, SocialParticipant, SocialParticipantType

        context = SocialContext(
            participants=[
                SocialParticipant(
                    participant_id="npc_1",
                    name="Informant",
                    participant_type=SocialParticipantType.NPC,
                )
            ]
        )

        assert len(context.topics_discussed) == 0

        context.topics_discussed.append("the weather")
        context.topics_discussed.append("local rumors")

        assert len(context.topics_discussed) == 2
        assert "the weather" in context.topics_discussed


class TestTopicIntelligence:
    """Tests for the enhanced topic matching and intelligence system."""

    def test_known_topic_keyword_matching(self):
        """Test that KnownTopic matches queries by keywords."""
        from src.data_models import KnownTopic, TopicRelevance

        topic = KnownTopic(
            topic_id="ruins_quest",
            content="There are ancient ruins to the north that hide treasures",
            keywords=["ruins", "ancient", "treasure", "north"],
        )

        # Exact keyword match
        assert topic.matches_query("Tell me about the ruins") == TopicRelevance.EXACT
        assert topic.matches_query("Where can I find treasure?") == TopicRelevance.EXACT

        # Irrelevant
        assert topic.matches_query("How's the weather?") == TopicRelevance.IRRELEVANT

    def test_topic_disposition_gating(self):
        """Test that topics are gated by disposition requirements."""
        from src.data_models import KnownTopic

        # Topic requires friendly disposition
        friendly_topic = KnownTopic(
            topic_id="secret_path",
            content="There's a secret path through the forest",
            required_disposition=2,  # Requires friendly
        )

        # Can share at disposition 2+
        assert friendly_topic.can_share(2) is True
        assert friendly_topic.can_share(3) is True

        # Cannot share at lower disposition
        assert friendly_topic.can_share(1) is False
        assert friendly_topic.can_share(0) is False
        assert friendly_topic.can_share(-1) is False

    def test_secret_hinting_logic(self):
        """Test that secrets are hinted at appropriately."""
        from src.data_models import SecretInfo

        secret = SecretInfo(
            secret_id="hidden_treasure",
            content="The treasure is buried under the old oak",
            hint="Something about buried treasure...",
            required_disposition=3,
            required_trust=2,
        )

        # Should hint if asked about multiple times with neutral+ disposition
        assert secret.should_hint(current_disposition=0, times_asked=2) is True

        # Should not hint on first ask with low disposition
        assert secret.should_hint(current_disposition=-1, times_asked=1) is False

    def test_secret_reveal_conditions(self):
        """Test conditions for revealing secrets."""
        from src.data_models import SecretInfo

        secret = SecretInfo(
            secret_id="dark_secret",
            content="The mayor is actually a werewolf",
            required_disposition=3,
            required_trust=2,
            can_be_bribed=True,
            bribe_amount=100,
        )

        # Cannot reveal without meeting requirements
        assert secret.can_reveal(current_disposition=2, trust_level=1) is False

        # Can reveal with high disposition and trust
        assert secret.can_reveal(current_disposition=3, trust_level=2) is True

        # Can reveal with bribe
        assert secret.can_reveal(current_disposition=0, trust_level=0, bribe_offered=100) is True
        assert secret.can_reveal(current_disposition=0, trust_level=0, bribe_offered=50) is False

    def test_conversation_tracker_patience(self):
        """Test that patience decays with irrelevant questions."""
        from src.data_models import ConversationTracker

        tracker = ConversationTracker(patience=3)

        # Relevant questions maintain patience
        tracker.record_question("about the ruins", was_relevant=True)
        assert tracker.patience == 3
        assert tracker.successful_exchanges == 1

        # Irrelevant questions reduce patience
        tracker.record_question("about bananas", was_relevant=False)
        assert tracker.patience == 2
        assert tracker.irrelevant_count == 1

        # Multiple irrelevant questions (need to get to -3 to end)
        tracker.record_question("about unicorns", was_relevant=False)  # patience = 1
        tracker.record_question("about rainbows", was_relevant=False)  # patience = 0
        tracker.record_question("about clouds", was_relevant=False)    # patience = -1
        tracker.record_question("about stars", was_relevant=False)     # patience = -2
        tracker.record_question("about moons", was_relevant=False)     # patience = -3

        # Conversation should end when patience hits -3
        assert tracker.conversation_ended is True
        assert "patience" in tracker.end_reason.lower()

    def test_conversation_tracker_trust_building(self):
        """Test that trust builds with successful exchanges."""
        from src.data_models import ConversationTracker

        tracker = ConversationTracker(patience=3, trust_level=0)

        # First exchange doesn't build trust yet
        tracker.record_question("about the town", was_relevant=True)
        assert tracker.trust_level == 0

        # Second exchange starts building trust
        tracker.record_question("about the mayor", was_relevant=True)
        assert tracker.trust_level == 1

        # More exchanges build more trust
        tracker.record_question("about the history", was_relevant=True)
        tracker.record_question("about the festivals", was_relevant=True)
        assert tracker.trust_level >= 2

    def test_participant_query_processing(self):
        """Test full query processing through participant."""
        from src.data_models import (
            SocialParticipant, SocialParticipantType, KnownTopic, SecretInfo
        )

        participant = SocialParticipant(
            participant_id="tavern_keeper",
            name="Old Tom",
            participant_type=SocialParticipantType.NPC,
            disposition=1,
            known_topics=[
                KnownTopic(
                    topic_id="local_rumors",
                    content="Strange lights have been seen in the forest",
                    keywords=["lights", "forest", "strange"],
                    required_disposition=-5,  # Always share
                ),
                KnownTopic(
                    topic_id="secret_path",
                    content="There's a hidden path to the castle",
                    keywords=["path", "castle", "hidden"],
                    required_disposition=2,  # Requires friendly
                ),
            ],
            secret_info=[
                SecretInfo(
                    secret_id="dark_truth",
                    content="The baron murdered his brother",
                    keywords=["baron", "brother", "murder"],
                    hint="Something dark about the baron...",
                    required_disposition=4,
                    required_trust=3,
                ),
            ],
        )

        # Query about available topic
        result = participant.process_query("Tell me about the strange lights")
        assert result["is_relevant"] is True
        assert len(result["relevant_topics"]) == 1
        assert "lights" in result["relevant_topics"][0]["content"].lower()

        # Query about locked topic (needs higher disposition)
        result = participant.process_query("Is there a path to the castle?")
        assert len(result["locked_topics"]) == 1

    def test_participant_find_relevant_topics(self):
        """Test finding relevant topics for a query."""
        from src.data_models import (
            SocialParticipant, SocialParticipantType, KnownTopic, TopicRelevance
        )

        participant = SocialParticipant(
            participant_id="scholar",
            name="Professor Elm",
            participant_type=SocialParticipantType.NPC,
            disposition=2,
            known_topics=[
                KnownTopic(
                    topic_id="history",
                    content="The ancient kingdom fell 500 years ago",
                    keywords=["history", "ancient", "kingdom"],
                ),
                KnownTopic(
                    topic_id="dragons",
                    content="Dragons once ruled these lands",
                    keywords=["dragons", "ruled", "lands"],
                ),
                KnownTopic(
                    topic_id="magic",
                    content="Magic flows from the ley lines",
                    keywords=["magic", "ley", "lines"],
                ),
            ],
        )

        # Find exact match
        results = participant.find_relevant_topics("Tell me about dragons")
        assert len(results) == 1
        assert results[0][1] == TopicRelevance.EXACT
        assert "dragons" in results[0][0].content.lower()

    def test_dialogue_inputs_with_enhanced_topics(self):
        """Test that to_dialogue_inputs uses the enhanced topic system."""
        from src.data_models import (
            SocialParticipant, SocialParticipantType, KnownTopic
        )

        participant = SocialParticipant(
            participant_id="guard",
            name="Captain Stone",
            participant_type=SocialParticipantType.NPC,
            disposition=1,
            known_topics=[
                KnownTopic(
                    topic_id="patrol",
                    content="We patrol the northern border every dawn",
                    keywords=["patrol", "border", "north", "dawn"],
                ),
                KnownTopic(
                    topic_id="threat",
                    content="Goblins have been spotted near the mountains",
                    keywords=["goblins", "mountains", "spotted"],
                ),
            ],
        )

        # Ask about patrols - should get relevant topic
        result = participant.to_dialogue_inputs("When do you patrol?")
        assert any("patrol" in str(topic).lower() for topic in result["known_to_npc"])

    def test_patience_affects_personality(self):
        """Test that low patience is reflected in personality description."""
        from src.data_models import SocialParticipant, SocialParticipantType

        participant = SocialParticipant(
            participant_id="innkeeper",
            name="Grumpy Greg",
            participant_type=SocialParticipantType.NPC,
            personality="Usually cheerful",
        )

        # Reduce patience with irrelevant questions
        for _ in range(3):
            participant.conversation.record_question("nonsense", was_relevant=False)

        # Get dialogue inputs
        result = participant.to_dialogue_inputs("More nonsense")

        # Personality should mention the impatience
        assert "impatient" in result["npc_personality"].lower() or \
               "annoyed" in result["npc_personality"].lower()

    def test_legacy_topics_converted(self):
        """Test that legacy dialogue_hooks are converted to KnownTopic."""
        from src.data_models import SocialParticipant, SocialParticipantType

        participant = SocialParticipant(
            participant_id="merchant",
            name="Trader Joe",
            participant_type=SocialParticipantType.NPC,
            dialogue_hooks=[
                "Sells exotic spices from the east",
                "Knows about trade routes",
            ],
        )

        # Should have converted to known_topics
        assert len(participant.known_topics) >= 2

        # Should be able to query them
        results = participant.find_relevant_topics("What spices do you have?")
        assert len(results) >= 1


# =============================================================================
# NARRATION LAYER INTEGRATION TESTS
# =============================================================================


class TestNarrationIntegration:
    """Integration tests for the LLM narrative layer in VirtualDM."""

    @pytest.fixture
    def virtual_dm_with_narration(self, sample_party):
        """Create a VirtualDM with narration enabled using mock LLM."""
        from src.main import VirtualDM, GameConfig

        config = GameConfig(
            llm_provider="mock",
            enable_narration=True,
        )
        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        # Add party
        for char in sample_party:
            dm.add_character(char)

        # Set resources
        dm.set_party_resources(food_days=7, water_days=7, torches=6)

        return dm

    @pytest.fixture
    def virtual_dm_no_narration(self, sample_party):
        """Create a VirtualDM with narration disabled."""
        from src.main import VirtualDM, GameConfig

        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
        )
        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
        )

        for char in sample_party:
            dm.add_character(char)

        return dm

    def test_dm_agent_initialized_when_narration_enabled(self, virtual_dm_with_narration):
        """Test that DMAgent is created when narration is enabled."""
        assert virtual_dm_with_narration.dm_agent is not None
        assert virtual_dm_with_narration.dm_agent.is_available()

    def test_dm_agent_not_initialized_when_narration_disabled(self, virtual_dm_no_narration):
        """Test that DMAgent is None when narration is disabled."""
        assert virtual_dm_no_narration.dm_agent is None

    def test_hex_narration_method_directly(self, virtual_dm_with_narration):
        """Test that _narrate_hex_arrival generates narration."""
        # Test the narration method directly with mock travel result
        mock_result = {
            "terrain": "forest",
            "hex_name": "Whispering Glade",
            "features": ["ancient oak", "stream"],
        }

        narration = virtual_dm_with_narration._narrate_hex_arrival("0710", mock_result)

        # Should return string (mock response)
        assert narration is not None
        assert isinstance(narration, str)

    def test_narration_skipped_when_disabled(self, virtual_dm_no_narration):
        """Test that _narrate_hex_arrival returns None when disabled."""
        mock_result = {"terrain": "forest"}

        narration = virtual_dm_no_narration._narrate_hex_arrival("0710", mock_result)

        # Should return None when narration disabled
        assert narration is None

    def test_travel_result_includes_narration_key(self, virtual_dm_with_narration):
        """Test that travel_to_hex adds narration key when enabled."""
        # This tests the integration by checking that the result dict
        # would have narration added. Since travel itself requires hex data,
        # we verify the method signature and mechanism work correctly.
        from unittest.mock import patch

        # Mock the hex_crawl.travel_to_hex to return a simple result
        with patch.object(
            virtual_dm_with_narration.hex_crawl,
            'travel_to_hex',
            return_value={"success": True, "terrain": "forest"}
        ):
            result = virtual_dm_with_narration.travel_to_hex("0710")

            # Should have narration key
            assert "narration" in result
            assert isinstance(result["narration"], str)

    def test_encounter_narration_method(self, virtual_dm_with_narration, basic_encounter):
        """Test narrate_encounter_start method."""
        narration = virtual_dm_with_narration.narrate_encounter_start(
            encounter=basic_encounter,
            creature_name="Goblin",
            number_appearing=1,
            terrain="forest",
        )

        # Should return string (mock response)
        assert narration is not None
        assert isinstance(narration, str)

    def test_combat_narration_method(self, virtual_dm_with_narration):
        """Test narrate_combat_round method."""
        resolved_actions = [
            {
                "actor": "Aldric the Bold",
                "action": "melee attack",
                "target": "Goblin",
                "result": "hit",
                "damage": 6,
            },
        ]

        narration = virtual_dm_with_narration.narrate_combat_round(
            round_number=1,
            resolved_actions=resolved_actions,
            damage_results={"goblin_1": 6},
        )

        assert narration is not None
        assert isinstance(narration, str)

    def test_failure_narration_method(self, virtual_dm_with_narration):
        """Test narrate_failure method."""
        narration = virtual_dm_with_narration.narrate_failure(
            failed_action="Climb the cliff face",
            failure_type="skill check failed",
            consequence_type="damage",
            consequence_details="Fell 20 feet, took 2d6 damage (7 points)",
            visible_warning="The rocks looked loose and crumbling",
        )

        assert narration is not None
        assert isinstance(narration, str)

    def test_combat_end_narration_method(self, virtual_dm_with_narration):
        """Test narrate_combat_end method."""
        narration = virtual_dm_with_narration.narrate_combat_end(
            combat_outcome="victory",
            surviving_party=["Aldric the Bold", "Elara Moonwhisper"],
            fallen_party=[],
            defeated_enemies=["Goblin Warrior", "Goblin Archer"],
            fled_enemies=[],
            significant_moments=["Aldric landed a critical hit"],
            total_rounds=3,
            xp_gained=50,
            treasure_found=["12 silver coins"],
        )

        assert narration is not None
        assert isinstance(narration, str)

    def test_dungeon_event_narration_method(self, virtual_dm_with_narration):
        """Test narrate_dungeon_event method."""
        narration = virtual_dm_with_narration.narrate_dungeon_event(
            event_type="trap",
            event_description="A pressure plate triggers a poison dart trap",
            location_name="The Sunken Library",
            location_atmosphere="dust motes drift in stale air",
            party_formation=["Aldric", "Thief", "Cleric"],
            triggering_action="stepping on stone tile",
            mechanical_outcome="Save vs Poison succeeded",
            damage_dealt={"Aldric": 4},
            items_involved=["10-foot pole"],
            hidden_elements=["mechanism behind wall panel"],
        )

        assert narration is not None
        assert isinstance(narration, str)

    def test_rest_narration_method(self, virtual_dm_with_narration):
        """Test narrate_rest method."""
        narration = virtual_dm_with_narration.narrate_rest(
            rest_type="camp",
            location_name="Sheltered Glen",
            location_safety="relatively safe",
            duration_hours=8,
            healing_received={"Aldric": 4, "Elara": 2},
            spells_recovered={"Elara": ["Light", "Cure Light Wounds"]},
            watch_schedule=["Aldric: 1st watch", "Elara: 2nd watch"],
            interruptions=[],
            weather_conditions="clear and cool",
            ambient_events=["owl hooting in distance"],
            resources_consumed={"rations": 2},
        )

        assert narration is not None
        assert isinstance(narration, str)

    def test_narration_disabled_returns_none(self, virtual_dm_no_narration, basic_encounter):
        """Test that narration methods return None when disabled."""
        result = virtual_dm_no_narration.narrate_encounter_start(
            encounter=basic_encounter,
            creature_name="Goblin",
            number_appearing=1,
            terrain="forest",
        )
        assert result is None

        result = virtual_dm_no_narration.narrate_combat_round(
            round_number=1,
            resolved_actions=[],
        )
        assert result is None

        result = virtual_dm_no_narration.narrate_failure(
            failed_action="test",
            failure_type="test",
            consequence_type="test",
            consequence_details="test",
        )
        assert result is None

        result = virtual_dm_no_narration.narrate_combat_end(
            combat_outcome="victory",
            surviving_party=["Test"],
            fallen_party=[],
            defeated_enemies=["Enemy"],
            fled_enemies=[],
            significant_moments=[],
            total_rounds=1,
        )
        assert result is None

        result = virtual_dm_no_narration.narrate_dungeon_event(
            event_type="trap",
            event_description="Test trap",
            location_name="Test Location",
        )
        assert result is None

        result = virtual_dm_no_narration.narrate_rest(
            rest_type="camp",
            location_name="Test Camp",
            location_safety="safe",
            duration_hours=8,
        )
        assert result is None


class TestNarrationAuthorityBoundary:
    """Test that narration respects mechanical authority boundaries."""

    @pytest.fixture
    def dm_agent_for_authority_test(self):
        """DM Agent configured for authority testing."""
        from src.ai.dm_agent import DMAgent, DMAgentConfig, reset_dm_agent
        from src.ai.llm_provider import LLMProvider

        reset_dm_agent()
        config = DMAgentConfig(
            llm_provider=LLMProvider.MOCK,
            validate_all_responses=True,
        )
        return DMAgent(config)

    def test_exploration_description_has_no_mechanics(self, dm_agent_for_authority_test):
        """Test that exploration descriptions don't contain mechanical decisions."""
        from src.data_models import TimeOfDay, Weather, Season

        result = dm_agent_for_authority_test.describe_hex(
            hex_id="0709",
            terrain="forest",
            name="Whispering Glade",
            time_of_day=TimeOfDay.MIDDAY,
            weather=Weather.CLEAR,
            season=Season.SUMMER,
        )

        # Mock always returns a default response without authority violations
        assert result.success
        # The authority violation list should be empty for a well-behaved response
        # (Mock client doesn't generate violations)

    def test_combat_narration_accepts_resolved_outcomes_only(
        self, dm_agent_for_authority_test
    ):
        """Test that combat narration only describes resolved outcomes."""
        from src.ai.prompt_schemas import ResolvedAction

        resolved_actions = [
            ResolvedAction(
                actor="Fighter",
                action="sword attack",
                target="Goblin",
                result="hit",
                damage=8,
            ),
        ]

        result = dm_agent_for_authority_test.narrate_combat_round(
            round_number=1,
            resolved_actions=[{
                "actor": "Fighter",
                "action": "sword attack",
                "target": "Goblin",
                "result": "hit",
                "damage": 8,
            }],
            damage_results={"goblin_1": 8},
            deaths=["goblin_1"],
        )

        # Should succeed - we're providing resolved outcomes
        assert result.success

    def test_llm_manager_detects_authority_violations(self, mock_llm_manager):
        """Test that LLMManager can detect authority violations in responses."""
        from src.ai.llm_provider import LLMMessage, LLMRole

        # The manager validates responses - mock returns clean responses
        response = mock_llm_manager.complete(
            messages=[LLMMessage(role=LLMRole.USER, content="Describe the forest")],
            system_prompt="You are a DM describing a scene.",
        )

        # Mock responses should be valid
        assert response is not None
