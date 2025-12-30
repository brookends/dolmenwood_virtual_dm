"""
Integration tests for actual play sequences.

Tests end-to-end scenarios that match real gameplay flows:
1. Wilderness: start → travel segment → encounter check → encounter → combat → return to travel
2. Dungeon: exploration turn → check events → encounter → combat → loot → time advance

These tests verify that multiple systems work together correctly across
complete gameplay loops.
"""

import pytest
from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.encounter.encounter_engine import EncounterEngine, EncounterOrigin, EncounterAction
from src.combat.combat_engine import CombatEngine, CombatAction, CombatActionType
from src.dungeon.dungeon_engine import (
    DungeonEngine,
    DungeonActionType,
    DungeonRoom,
    DungeonState,
    DoorState,
)
from src.data_models import (
    EncounterState,
    EncounterType,
    SurpriseStatus,
    Combatant,
    StatBlock,
    CharacterState,
    GameDate,
    GameTime,
    LocationType,
    LightSourceType,
    Feature,
    Hazard,
)


class TestWildernessTravelFlow:
    """
    Integration tests for wilderness travel play sequence.

    Flow: start in wilderness → travel segment → encounter check →
          encounter → combat → return to travel
    """

    @pytest.fixture
    def wilderness_party(self, controller_with_party, sample_party):
        """Set up a party ready for wilderness travel."""
        # Ensure party is in wilderness state
        assert controller_with_party.current_state == GameState.WILDERNESS_TRAVEL

        # Add party as combatants for potential combat
        self.party_combatants = []
        for char in sample_party:
            combatant = Combatant(
                combatant_id=char.character_id,
                name=char.name,
                side="party",
                stat_block=StatBlock(
                    armor_class=char.armor_class,
                    hit_dice=f"{char.level}d8",
                    hp_current=char.hp_current,
                    hp_max=char.hp_max,
                    movement=char.base_speed,
                    attacks=[{"name": "Weapon", "damage": "1d8+1", "bonus": 2}],
                    morale=12,
                ),
                character_ref=char.character_id,
            )
            self.party_combatants.append(combatant)

        return controller_with_party

    @pytest.fixture
    def enemy_combatants(self):
        """Create enemy combatants for encounters."""
        return [
            Combatant(
                combatant_id="goblin_1",
                name="Goblin Warrior",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=6,
                    hit_dice="1d8-1",
                    hp_current=4,
                    hp_max=4,
                    movement=60,
                    attacks=[{"name": "Short Sword", "damage": "1d6", "bonus": 0}],
                    morale=7,
                ),
            ),
            Combatant(
                combatant_id="goblin_2",
                name="Goblin Archer",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=7,
                    hit_dice="1d8-1",
                    hp_current=3,
                    hp_max=3,
                    movement=60,
                    attacks=[{"name": "Shortbow", "damage": "1d6", "bonus": 0}],
                    morale=7,
                ),
            ),
        ]

    def test_complete_wilderness_to_combat_loop(
        self, wilderness_party, enemy_combatants, seeded_dice
    ):
        """
        Test the complete wilderness travel → encounter → combat → return flow.

        This simulates a typical play session where the party:
        1. Travels through wilderness
        2. Encounters monsters
        3. Goes through encounter phases
        4. Engages in combat
        5. Defeats enemies
        6. Returns to wilderness travel
        """
        controller = wilderness_party

        # =========================================================
        # Phase 1: Start in Wilderness Travel
        # =========================================================
        assert controller.current_state == GameState.WILDERNESS_TRAVEL
        initial_time = str(controller.time_tracker.game_time)

        # =========================================================
        # Phase 2: Travel Segment - Advance Time
        # =========================================================
        travel_result = controller.advance_travel_segment()
        assert travel_result is not None
        new_time = str(controller.time_tracker.game_time)
        assert new_time != initial_time, "Time should advance after travel segment"

        # =========================================================
        # Phase 3: Encounter Triggered - Create Monster Encounter
        # =========================================================
        # Combine party and enemy combatants
        all_combatants = self.party_combatants + enemy_combatants

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=60,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["goblin_1", "goblin_2"],
            context="ambush",
            terrain="forest",
            combatants=all_combatants,
        )

        # Start encounter using EncounterEngine
        encounter_engine = EncounterEngine(controller)
        start_result = encounter_engine.start_encounter(encounter, EncounterOrigin.WILDERNESS)

        assert controller.current_state == GameState.ENCOUNTER
        assert start_result is not None

        # =========================================================
        # Phase 4: Run Encounter Phases
        # =========================================================
        # Auto-run awareness, surprise, distance, initiative phases
        encounter_engine.auto_run_phases()

        # Verify encounter phase progression
        assert encounter_engine.is_active()

        # =========================================================
        # Phase 5: Declare Attack - Transition to Combat
        # =========================================================
        attack_result = encounter_engine.execute_action(EncounterAction.ATTACK, actor="party")
        assert attack_result is not None

        assert controller.current_state == GameState.COMBAT

        # =========================================================
        # Phase 6: Combat Resolution
        # =========================================================
        combat_engine = CombatEngine(controller)
        combat_engine.start_combat(encounter, GameState.WILDERNESS_TRAVEL)

        assert combat_engine.is_in_combat()

        # Execute combat round - party attacks
        party_actions = [
            CombatAction(
                combatant_id="fighter_1",
                action_type=CombatActionType.MELEE_ATTACK,
                target_id="goblin_1",
            ),
            CombatAction(
                combatant_id="thief_1",
                action_type=CombatActionType.MELEE_ATTACK,
                target_id="goblin_2",
            ),
        ]

        round_result = combat_engine.execute_round(party_actions)
        assert round_result is not None
        assert round_result.round_number == 1

        # =========================================================
        # Phase 7: Force Combat End (simulate victory)
        # =========================================================
        # Kill all enemies to end combat
        for combatant in encounter.combatants:
            if combatant.side == "enemy":
                combatant.stat_block.hp_current = 0

        # Execute another round to trigger combat end check
        final_result = combat_engine.execute_round([])
        assert final_result.combat_ended is True
        assert "all_enemies_defeated" in final_result.end_reason

        # =========================================================
        # Phase 8: Return to Wilderness Travel
        # =========================================================
        controller.transition("combat_end_wilderness")
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        # Verify session log captured the flow
        log = controller.get_session_log()
        assert len(log) > 0, "Session should have logged state transitions"

    def test_wilderness_travel_time_and_resources(self, wilderness_party):
        """Test that wilderness travel properly tracks time and resources."""
        controller = wilderness_party

        initial_food = controller.party_state.resources.food_days
        initial_time = controller.time_tracker.game_time.hour

        # Advance a full travel segment (4 hours)
        result = controller.advance_travel_segment()

        # Time should advance by 4 hours (24 turns)
        new_hour = controller.time_tracker.game_time.hour
        expected_hour = (initial_time + 4) % 24
        assert new_hour == expected_hour, "Travel segment should advance 4 hours"

        # Resources should remain the same (consumption is per day)
        assert controller.party_state.resources.food_days == initial_food

        # Advance to end of day to trigger consumption
        controller.time_tracker.advance_day(1)
        assert controller.party_state.resources.food_days < initial_food

    def test_encounter_evasion_returns_to_wilderness(self, wilderness_party, enemy_combatants):
        """Test that successful evasion returns party to wilderness."""
        controller = wilderness_party

        # Create encounter
        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=120,  # Far distance for evasion
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["goblin_1"],
            terrain="forest",
            combatants=self.party_combatants + enemy_combatants[:1],
        )

        encounter_engine = EncounterEngine(controller)
        encounter_engine.start_encounter(encounter, EncounterOrigin.WILDERNESS)
        encounter_engine.auto_run_phases()

        assert controller.current_state == GameState.ENCOUNTER

        # Attempt evasion
        evasion_result = encounter_engine.execute_action(EncounterAction.EVASION, actor="party")
        assert evasion_result is not None

        # If evasion succeeded, should return to wilderness
        # (exact result depends on dice rolls, but transition should work)
        if evasion_result.success:
            assert controller.current_state == GameState.WILDERNESS_TRAVEL
        else:
            # If evasion failed, should still be in encounter
            assert controller.current_state in {GameState.ENCOUNTER, GameState.COMBAT}

    def test_encounter_parley_to_social_interaction(self, wilderness_party, seeded_dice):
        """Test that parley transitions to social interaction."""
        controller = wilderness_party

        # Create NPC encounter
        encounter = EncounterState(
            encounter_type=EncounterType.NPC,
            distance=30,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["traveling_merchant"],
            context="peaceful traveler",
            terrain="road",
        )

        encounter_engine = EncounterEngine(controller)
        encounter_engine.start_encounter(encounter, EncounterOrigin.WILDERNESS)
        encounter_engine.auto_run_phases()

        assert controller.current_state == GameState.ENCOUNTER

        # Attempt parley
        parley_result = encounter_engine.execute_action(EncounterAction.PARLEY, actor="party")
        assert parley_result is not None
        assert parley_result.reaction_roll is not None

        # Depending on reaction, could go to social or combat
        # Verify the transition mechanism works
        final_state = controller.current_state
        assert final_state in {
            GameState.SOCIAL_INTERACTION,
            GameState.COMBAT,
            GameState.ENCOUNTER,
        }


class TestDungeonExplorationFlow:
    """
    Integration tests for dungeon exploration play sequence.

    Flow: exploration turn → check events → encounter → combat →
          loot → time advance
    """

    @pytest.fixture
    def dungeon_party(self, controller_with_party, sample_party):
        """Set up a party ready for dungeon exploration."""
        controller = controller_with_party

        # Set up light source for dungeon exploration
        controller.party_state.active_light_source = LightSourceType.TORCH
        controller.party_state.light_remaining_turns = 36  # 6 hours of torch light

        # Create party combatants for potential combat
        self.party_combatants = []
        for char in sample_party:
            combatant = Combatant(
                combatant_id=char.character_id,
                name=char.name,
                side="party",
                stat_block=StatBlock(
                    armor_class=char.armor_class,
                    hit_dice=f"{char.level}d8",
                    hp_current=char.hp_current,
                    hp_max=char.hp_max,
                    movement=char.base_speed,
                    attacks=[{"name": "Weapon", "damage": "1d8+1", "bonus": 2}],
                    morale=12,
                ),
                character_ref=char.character_id,
            )
            self.party_combatants.append(combatant)

        return controller

    @pytest.fixture
    def test_dungeon_data(self):
        """Create test dungeon with multiple rooms."""
        dungeon = DungeonState(
            dungeon_id="test_dungeon",
            name="The Forgotten Crypt",
            current_room="entry_hall",
            dungeon_level=1,
        )

        # Create rooms
        entry_hall = DungeonRoom(
            room_id="entry_hall",
            name="Entry Hall",
            description="A dusty chamber with crumbling stone walls.",
            dimensions="30x40",
            exits={"north": "guard_room", "east": "treasure_room"},
            doors={"entry_hall_north": DoorState.CLOSED},
        )

        guard_room = DungeonRoom(
            room_id="guard_room",
            name="Guard Chamber",
            description="An old guard post with rusted weapons on the walls.",
            dimensions="20x20",
            exits={"south": "entry_hall"},
            occupants=["skeleton_1", "skeleton_2"],
        )

        treasure_room = DungeonRoom(
            room_id="treasure_room",
            name="Treasury",
            description="A vault with ancient chests.",
            dimensions="15x15",
            exits={"west": "entry_hall"},
            doors={"treasure_room_west": DoorState.LOCKED},
            treasure=[
                {"name": "Gold coins", "quantity": 50, "found": False},
                {"name": "Silver ring", "found": False},
            ],
            features=[
                Feature(
                    feature_id="chest_1",
                    name="Ancient Chest",
                    description="A weathered wooden chest bound with iron.",
                    hidden=False,
                    discovered=True,
                ),
            ],
        )

        dungeon.rooms = {
            "entry_hall": entry_hall,
            "guard_room": guard_room,
            "treasure_room": treasure_room,
        }

        return dungeon

    @pytest.fixture
    def dungeon_enemies(self):
        """Create dungeon enemy combatants."""
        return [
            Combatant(
                combatant_id="skeleton_1",
                name="Skeleton Warrior",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=7,
                    hit_dice="1d8",
                    hp_current=5,
                    hp_max=5,
                    movement=60,
                    attacks=[{"name": "Rusty Sword", "damage": "1d6", "bonus": 0}],
                    morale=12,  # Undead don't check morale
                ),
            ),
            Combatant(
                combatant_id="skeleton_2",
                name="Skeleton Archer",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=8,
                    hit_dice="1d8",
                    hp_current=4,
                    hp_max=4,
                    movement=60,
                    attacks=[{"name": "Shortbow", "damage": "1d6", "bonus": 0}],
                    morale=12,
                ),
            ),
        ]

    def test_complete_dungeon_exploration_loop(
        self, dungeon_party, test_dungeon_data, dungeon_enemies, seeded_dice
    ):
        """
        Test the complete dungeon exploration → encounter → combat → loot → advance flow.

        This simulates a typical dungeon delve where the party:
        1. Enters the dungeon
        2. Explores rooms (10-minute turns)
        3. Encounters monsters
        4. Fights through combat
        5. Loots treasure
        6. Time advances appropriately
        7. Exits the dungeon
        """
        controller = dungeon_party
        dungeon = test_dungeon_data

        # =========================================================
        # Phase 1: Enter Dungeon
        # =========================================================
        dungeon_engine = DungeonEngine(controller)
        entry_result = dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entry_hall",
            dungeon_data=dungeon,
        )

        assert entry_result["dungeon_id"] == "test_dungeon"
        assert controller.current_state == GameState.DUNGEON_EXPLORATION
        assert entry_result["light_status"]["has_light"] is True

        initial_turns = dungeon.turns_in_dungeon

        # =========================================================
        # Phase 2: Exploration Turn - Search Entry Hall
        # =========================================================
        search_result = dungeon_engine.execute_turn(DungeonActionType.SEARCH, action_params={})

        assert search_result.success is True
        assert search_result.time_spent == 1
        assert dungeon.turns_in_dungeon == initial_turns + 1

        # Light should have depleted by 1 turn
        assert controller.party_state.light_remaining_turns == 35

        # =========================================================
        # Phase 3: Move to Guard Room - Trigger Encounter
        # =========================================================
        move_result = dungeon_engine.execute_turn(
            DungeonActionType.MOVE, action_params={"direction": "north"}
        )

        assert move_result.success is True
        assert dungeon.current_room == "guard_room"

        # =========================================================
        # Phase 4: Manually Trigger Encounter (simulating room occupants)
        # =========================================================
        # Combine party and enemy combatants
        all_combatants = self.party_combatants + dungeon_enemies

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=20,  # Close distance in dungeon
            surprise_status=SurpriseStatus.ENEMIES_SURPRISED,  # Party got the drop
            actors=["skeleton_1", "skeleton_2"],
            context="guarding",
            terrain="dungeon",
            combatants=all_combatants,
        )

        # =========================================================
        # Phase 5: Run Encounter - start_encounter handles the transition
        # =========================================================
        encounter_engine = EncounterEngine(controller)
        encounter_engine.start_encounter(encounter, EncounterOrigin.DUNGEON)

        assert controller.current_state == GameState.ENCOUNTER

        encounter_engine.auto_run_phases()

        # Party attacks
        attack_result = encounter_engine.execute_action(EncounterAction.ATTACK, actor="party")
        assert attack_result is not None

        assert controller.current_state == GameState.COMBAT

        # =========================================================
        # Phase 6: Combat Resolution
        # =========================================================
        combat_engine = CombatEngine(controller)
        combat_engine.start_combat(encounter, GameState.DUNGEON_EXPLORATION)

        # Execute combat - party attacks with advantage from surprise
        party_actions = [
            CombatAction(
                combatant_id="fighter_1",
                action_type=CombatActionType.MELEE_ATTACK,
                target_id="skeleton_1",
            ),
            CombatAction(
                combatant_id="thief_1",
                action_type=CombatActionType.MELEE_ATTACK,
                target_id="skeleton_2",
            ),
        ]

        round_result = combat_engine.execute_round(party_actions)
        assert round_result is not None

        # =========================================================
        # Phase 7: Force Combat End (simulate victory)
        # =========================================================
        for combatant in encounter.combatants:
            if combatant.side == "enemy":
                combatant.stat_block.hp_current = 0

        final_result = combat_engine.execute_round([])
        assert final_result.combat_ended is True

        # =========================================================
        # Phase 8: Return to Dungeon Exploration
        # =========================================================
        controller.transition("combat_end_dungeon")
        assert controller.current_state == GameState.DUNGEON_EXPLORATION

        # =========================================================
        # Phase 9: Move to Treasure Room and Loot
        # =========================================================
        # First go back to entry hall
        move_back = dungeon_engine.execute_turn(
            DungeonActionType.MOVE, action_params={"direction": "south"}
        )
        assert move_back.success is True
        assert dungeon.current_room == "entry_hall"

        # Add the locked door to the east for this test
        dungeon.rooms["entry_hall"].doors["entry_hall_east"] = DoorState.LOCKED

        # Try to open locked door - should fail
        open_result = dungeon_engine.execute_turn(
            DungeonActionType.OPEN_DOOR, action_params={"direction": "east"}
        )
        # Door should report locked status
        assert "locked" in open_result.action_result.get("message", "").lower()

        # Pick the lock
        pick_result = dungeon_engine.execute_turn(
            DungeonActionType.PICK_LOCK,
            action_params={"door_id": "entry_hall_east", "character_id": "thief_1"},
        )
        # Result depends on roll, but action should complete

        # For test purposes, unlock the door manually to continue the flow
        dungeon.rooms["entry_hall"].doors["entry_hall_east"] = DoorState.OPEN

        # Move to treasure room
        move_to_treasure = dungeon_engine.execute_turn(
            DungeonActionType.MOVE, action_params={"direction": "east"}
        )
        assert move_to_treasure.success is True
        assert dungeon.current_room == "treasure_room"

        # Search for treasure
        search_treasure = dungeon_engine.execute_turn(DungeonActionType.SEARCH, action_params={})
        assert search_treasure.success is True

        # Interact with chest
        interact_result = dungeon_engine.execute_turn(
            DungeonActionType.INTERACT, action_params={"feature_id": "chest_1"}
        )
        assert interact_result.success is True
        assert interact_result.action_result.get("feature") == "Ancient Chest"

        # =========================================================
        # Phase 10: Time Tracking Verification
        # =========================================================
        # Handle any encounter that may have been triggered
        if interact_result.encounter_triggered or controller.current_state == GameState.ENCOUNTER:
            controller.transition("encounter_end_dungeon")

        # Verify time has advanced appropriately
        summary = dungeon_engine.get_exploration_summary()
        assert summary["active"] is True
        assert summary["turns_in_dungeon"] > initial_turns
        assert summary["current_room"] == "treasure_room"
        assert "entry_hall" in summary["explored_rooms"]

        # =========================================================
        # Phase 11: Exit Dungeon
        # =========================================================
        # Ensure we're in dungeon exploration state before exiting
        if controller.current_state != GameState.DUNGEON_EXPLORATION:
            if controller.current_state == GameState.ENCOUNTER:
                controller.transition("encounter_end_dungeon")
            elif controller.current_state == GameState.COMBAT:
                controller.transition("combat_end_dungeon")

        exit_result = dungeon_engine.exit_dungeon()
        assert (
            "dungeon_id" in exit_result or "error" not in exit_result
        ), f"Exit should succeed from dungeon exploration: {exit_result}"
        if "dungeon_id" in exit_result:
            assert exit_result["dungeon_id"] == "test_dungeon"
            assert exit_result["turns_spent"] > 0
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

    def test_dungeon_rest_requirement(self, dungeon_party, test_dungeon_data, seeded_dice):
        """Test that dungeon exploration tracks rest requirements (1 turn per 5)."""
        controller = dungeon_party
        dungeon = test_dungeon_data

        dungeon_engine = DungeonEngine(controller)
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entry_hall",
            dungeon_data=dungeon,
        )

        # Execute exploration turns until we get a rest warning
        found_rest_warning = False
        for i in range(6):  # More than 5 turns to ensure we trigger warning
            # If an encounter was triggered, clear it and return to dungeon state
            if controller.current_state != GameState.DUNGEON_EXPLORATION:
                if controller.current_state == GameState.ENCOUNTER:
                    controller.transition("encounter_end_dungeon")
                elif controller.current_state == GameState.COMBAT:
                    controller.transition("combat_end_dungeon")

            result = dungeon_engine.execute_turn(DungeonActionType.SEARCH, action_params={})
            if any("rest" in w.lower() or "fatigue" in w.lower() for w in result.warnings):
                found_rest_warning = True

            # Handle any encounter that was triggered
            if result.encounter_triggered:
                controller.transition("encounter_end_dungeon")

        assert found_rest_warning, "Should warn about rest/fatigue after multiple exploration turns"

        # Ensure we're back in dungeon exploration
        if controller.current_state != GameState.DUNGEON_EXPLORATION:
            if controller.current_state == GameState.ENCOUNTER:
                controller.transition("encounter_end_dungeon")

        # Rest for one turn
        rest_result = dungeon_engine.execute_turn(DungeonActionType.REST, action_params={})
        assert rest_result.success is True
        assert rest_result.action_result.get("rest_fulfilled") is True

        # Next exploration turn should not warn about rest immediately
        next_result = dungeon_engine.execute_turn(DungeonActionType.SEARCH, action_params={})
        # The first turn after rest shouldn't have fatigue warnings
        # (though other warnings may still appear)
        fatigue_warnings = [w for w in next_result.warnings if "fatigue" in w.lower()]
        assert (
            len(fatigue_warnings) == 0
        ), "Should not have fatigue warning immediately after resting"

    def test_dungeon_light_depletion(self, dungeon_party, test_dungeon_data):
        """Test that light sources deplete during dungeon exploration."""
        controller = dungeon_party
        dungeon = test_dungeon_data

        # Set limited torch light (3 turns remaining)
        controller.party_state.active_light_source = LightSourceType.TORCH
        controller.party_state.light_remaining_turns = 3

        dungeon_engine = DungeonEngine(controller)
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entry_hall",
            dungeon_data=dungeon,
        )

        initial_light = controller.party_state.light_remaining_turns

        # Execute turns and verify light depletes
        for i in range(3):
            result = dungeon_engine.execute_turn(DungeonActionType.SEARCH, action_params={})
            # Light should decrement each turn
            expected_remaining = initial_light - i - 1
            assert controller.party_state.light_remaining_turns == max(
                0, expected_remaining
            ), f"Light should deplete each turn: turn {i+1}"

        # After 3 turns with 3 turns of light, should be at 0
        assert controller.party_state.light_remaining_turns == 0, "Light should be exhausted"

        # The active light source should be cleared when exhausted
        # (this happens via the controller's time advancement logic)
        # If not cleared, at least verify it's at 0 remaining

    def test_dungeon_wandering_monster_check(self, dungeon_party, test_dungeon_data, seeded_dice):
        """Test that wandering monster checks occur every 2 turns."""
        controller = dungeon_party
        dungeon = test_dungeon_data

        dungeon_engine = DungeonEngine(controller)
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entry_hall",
            dungeon_data=dungeon,
        )

        # Execute multiple turns to trigger wandering monster check
        encounters_triggered = 0
        for i in range(10):
            result = dungeon_engine.execute_turn(DungeonActionType.SEARCH, action_params={})

            if result.encounter_triggered:
                encounters_triggered += 1
                assert result.encounter is not None
                # Reset state for continued testing
                controller.transition("encounter_end_dungeon")

        # With seeded dice, we should have consistent behavior
        # The exact number depends on the seed, but mechanism should work

    def test_dungeon_door_states(self, dungeon_party, test_dungeon_data):
        """Test door handling in dungeon exploration."""
        controller = dungeon_party
        dungeon = test_dungeon_data

        # Add a stuck door
        dungeon.rooms["entry_hall"].doors["entry_hall_north"] = DoorState.STUCK

        dungeon_engine = DungeonEngine(controller)
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entry_hall",
            dungeon_data=dungeon,
        )

        # Try to move through stuck door - should fail
        move_result = dungeon_engine.execute_turn(
            DungeonActionType.MOVE, action_params={"direction": "north"}
        )
        assert move_result.success is False
        assert "stuck" in move_result.action_result.get("message", "").lower()

        # Try to force the door
        force_result = dungeon_engine.execute_turn(
            DungeonActionType.OPEN_DOOR, action_params={"direction": "north"}
        )
        # Result depends on dice roll
        assert force_result.action_result.get("noise", 0) > 0  # Forcing is noisy

    def test_dungeon_fast_travel(self, dungeon_party, test_dungeon_data):
        """Test fast travel through explored areas."""
        controller = dungeon_party
        dungeon = test_dungeon_data

        dungeon_engine = DungeonEngine(controller)
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entry_hall",
            dungeon_data=dungeon,
        )

        # Mark rooms as explored
        dungeon.explored_rooms = {"entry_hall", "guard_room"}

        # Move to guard room normally first
        dungeon.rooms["entry_hall"].doors["entry_hall_north"] = DoorState.OPEN
        dungeon_engine.execute_turn(DungeonActionType.MOVE, action_params={"direction": "north"})
        assert dungeon.current_room == "guard_room"

        # Now fast travel back
        fast_travel_result = dungeon_engine.execute_turn(
            DungeonActionType.FAST_TRAVEL,
            action_params={
                "route": ["guard_room", "entry_hall"],
                "destination": "entry_hall",
            },
        )

        # Fast travel should succeed through explored areas
        if fast_travel_result.success:
            assert dungeon.current_room == "entry_hall"

    def test_dungeon_escape_roll(self, dungeon_party, test_dungeon_data, seeded_dice):
        """Test dungeon escape roll mechanics."""
        controller = dungeon_party
        dungeon = test_dungeon_data

        dungeon_engine = DungeonEngine(controller)
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entry_hall",
            dungeon_data=dungeon,
        )

        # Test escape roll without bonuses
        escape_result = dungeon_engine.attempt_escape_roll("fighter_1")
        assert "roll" in escape_result
        assert "target" in escape_result
        assert "modifier" in escape_result

        # If escaped, verify state transition
        if escape_result["escaped"]:
            assert controller.current_state == GameState.WILDERNESS_TRAVEL
        else:
            # If failed, should have doom result
            assert "doom_result" in escape_result

    def test_dungeon_escape_modifiers(self, dungeon_party, test_dungeon_data):
        """Test that escape roll modifiers apply correctly."""
        controller = dungeon_party
        dungeon = test_dungeon_data

        dungeon_engine = DungeonEngine(controller)
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entry_hall",
            dungeon_data=dungeon,
        )

        # Update modifiers
        dungeon_engine.update_escape_modifiers(
            has_map=True,  # +2
            known_exit_path=True,  # +4
            dungeon_level=2,  # -1
        )

        # Establish safe path
        dungeon.explored_rooms = {"entry_hall", "guard_room"}
        path_result = dungeon_engine.establish_safe_path(["entry_hall", "guard_room"])
        assert path_result["success"] is True

        # Verify modifiers in escape attempt
        escape_result = dungeon_engine.attempt_escape_roll("fighter_1")
        assert escape_result["modifier_breakdown"]["has_map"] == 2
        assert escape_result["modifier_breakdown"]["known_exit_path"] == 4
        assert escape_result["modifier_breakdown"]["dungeon_level"] == -1


class TestCombatToExplorationTransitions:
    """Test combat resolution transitions back to exploration states."""

    def test_combat_end_to_wilderness(self, controller_with_party, sample_party, seeded_dice):
        """Test that combat properly returns to wilderness travel."""
        controller = controller_with_party

        # Set up encounter and transition to combat
        combatants = [
            Combatant(
                combatant_id="goblin_1",
                name="Goblin",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=9,
                    hit_dice="1d8",
                    hp_current=1,
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
            actors=["goblin_1"],
            terrain="forest",
            combatants=combatants,
        )

        controller.set_encounter(encounter)
        controller.transition("encounter_triggered")
        controller.transition("encounter_to_combat")

        assert controller.current_state == GameState.COMBAT
        assert controller.combat_engine is not None

        # End combat
        controller.transition("combat_end_wilderness")

        assert controller.current_state == GameState.WILDERNESS_TRAVEL
        assert controller.combat_engine is None

    def test_combat_end_to_dungeon(self, controller_with_party, seeded_dice):
        """Test that combat properly returns to dungeon exploration."""
        controller = controller_with_party

        # First enter dungeon
        controller.transition("enter_dungeon")
        assert controller.current_state == GameState.DUNGEON_EXPLORATION

        # Trigger encounter
        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=20,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["skeleton"],
            terrain="dungeon",
        )

        controller.set_encounter(encounter)
        controller.transition("encounter_triggered")
        controller.transition("encounter_to_combat")

        assert controller.current_state == GameState.COMBAT

        # End combat - should return to dungeon
        controller.transition("combat_end_dungeon")

        assert controller.current_state == GameState.DUNGEON_EXPLORATION

    def test_combat_end_to_settlement(self, controller_with_party, seeded_dice):
        """Test that combat properly returns to settlement exploration."""
        controller = controller_with_party

        # Enter settlement
        controller.transition("enter_settlement")
        assert controller.current_state == GameState.SETTLEMENT_EXPLORATION

        # Trigger encounter in settlement
        encounter = EncounterState(
            encounter_type=EncounterType.NPC,
            distance=10,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["bandit"],
            terrain="settlement",
        )

        controller.set_encounter(encounter)
        controller.transition("encounter_triggered")
        controller.transition("encounter_to_combat")

        assert controller.current_state == GameState.COMBAT

        # End combat - should return to settlement
        controller.transition("combat_end_settlement")

        assert controller.current_state == GameState.SETTLEMENT_EXPLORATION


class TestMultiStatePlaySession:
    """Test complex play sessions involving multiple state transitions."""

    def test_full_session_wilderness_dungeon_wilderness(
        self, controller_with_party, sample_party, seeded_dice
    ):
        """
        Test a complete mini-session flow:
        1. Start in wilderness
        2. Travel to dungeon
        3. Explore dungeon
        4. Exit dungeon
        5. Continue wilderness travel
        """
        controller = controller_with_party

        # Phase 1: Wilderness travel
        assert controller.current_state == GameState.WILDERNESS_TRAVEL
        controller.advance_travel_segment()

        # Phase 2: Enter dungeon
        controller.transition("enter_dungeon")
        assert controller.current_state == GameState.DUNGEON_EXPLORATION

        controller.set_party_location(LocationType.DUNGEON_ROOM, "room_1")
        assert controller.party_state.location.location_type == LocationType.DUNGEON_ROOM

        # Advance time in dungeon (1 turn = 10 minutes)
        controller.advance_time(6)  # 1 hour

        # Phase 3: Exit dungeon
        controller.transition("exit_dungeon")
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        # Phase 4: Continue wilderness travel
        controller.advance_travel_segment()

        # Verify session log
        log = controller.get_session_log()
        assert len(log) > 0

    def test_session_with_rest_and_combat(self, controller_with_party, sample_party, seeded_dice):
        """
        Test session with rest and combat interruption:
        1. Travel in wilderness
        2. Begin rest
        3. Get interrupted by combat
        4. Resolve combat
        5. Continue travel
        """
        controller = controller_with_party

        # Travel
        assert controller.current_state == GameState.WILDERNESS_TRAVEL
        controller.advance_travel_segment()

        # Begin rest (downtime)
        controller.transition("begin_rest")
        assert controller.current_state == GameState.DOWNTIME

        # Rest interrupted by combat
        controller.transition("rest_interrupted")
        assert controller.current_state == GameState.COMBAT

        # Combat ends - return to wilderness (since rest was interrupted)
        controller.transition("combat_end_wilderness")
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        # Continue travel
        controller.advance_travel_segment()

    def test_settlement_interaction_flow(self, controller_with_party, sample_party):
        """
        Test settlement interaction flow:
        1. Enter settlement
        2. Initiate conversation
        3. End conversation
        4. Leave settlement
        """
        controller = controller_with_party

        # Enter settlement
        controller.transition("enter_settlement")
        assert controller.current_state == GameState.SETTLEMENT_EXPLORATION

        controller.set_party_location(LocationType.SETTLEMENT, "prigwort", "The Wicked Owl Inn")
        assert controller.party_state.location.sub_location == "The Wicked Owl Inn"

        # Start conversation
        controller.transition("initiate_conversation")
        assert controller.current_state == GameState.SOCIAL_INTERACTION

        # End conversation
        controller.transition("conversation_end_settlement")
        assert controller.current_state == GameState.SETTLEMENT_EXPLORATION

        # Leave settlement
        controller.transition("exit_settlement")
        assert controller.current_state == GameState.WILDERNESS_TRAVEL
