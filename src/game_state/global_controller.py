"""
Global Controller for Dolmenwood Virtual DM.

Manages global game state including time tracking, world state, and party state.
This is the central coordinator that ties together all game systems.

Implements Section 5.1 Global Loop Invariants and Section 6.6 TimeTracker.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
import logging

from src.game_state.state_machine import GameState, StateMachine
from src.data_models import (
    WorldState,
    PartyState,
    CharacterState,
    LocationState,
    EncounterState,
    GameDate,
    GameTime,
    Season,
    Weather,
    Location,
    LocationType,
    PartyResources,
    DiceRoller,
    Condition,
    ConditionType,
    LightSourceType,
    AreaEffect,
    PolymorphOverlay,
)

# Import NarrativeResolver (optional, may not be initialized yet)
try:
    from src.narrative import NarrativeResolver, ActiveSpellEffect
    NARRATIVE_AVAILABLE = True
except ImportError:
    NARRATIVE_AVAILABLE = False
    NarrativeResolver = None
    ActiveSpellEffect = None

# Import XPManager for advancement tracking
try:
    from src.advancement import XPManager
    XP_MANAGER_AVAILABLE = True
except ImportError:
    XP_MANAGER_AVAILABLE = False
    XPManager = None


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class TimeTracker:
    """
    Tracks game time at multiple scales.
    From Section 6.6 of the specification.

    Time scales:
    - Exploration turns: 10 minutes (dungeon time)
    - Watches: 4 hours (travel/rest time)
    - Days: 24 hours
    - Seasons: Quarterly

    All time advancement flows through this class to ensure consistency.
    """
    exploration_turns: int = 0
    watches: int = 0
    days: int = 0
    game_date: GameDate = field(default_factory=lambda: GameDate(year=1, month=1, day=1))
    game_time: GameTime = field(default_factory=lambda: GameTime(hour=8, minute=0))
    season: Season = field(default_factory=lambda: Season.SPRING)

    # Callbacks for time-based triggers
    _turn_callbacks: list[Callable] = field(default_factory=list)
    _watch_callbacks: list[Callable] = field(default_factory=list)
    _day_callbacks: list[Callable] = field(default_factory=list)
    _season_callbacks: list[Callable] = field(default_factory=list)

    def advance_turn(self, turns: int = 1) -> dict[str, Any]:
        """
        Advance time by exploration turns (10 minutes each).

        This is the base unit of dungeon time.

        Args:
            turns: Number of turns to advance

        Returns:
            Dictionary with time changes and triggered thresholds
        """
        self.exploration_turns += turns

        new_time, days_passed = self.game_time.advance_turns(turns)
        self.game_time = new_time

        result = {
            "turns_advanced": turns,
            "new_time": str(self.game_time),
            "watches_passed": 0,
            "days_passed": 0,
            "season_changed": False,
        }

        # Check watch threshold (24 turns = 4 hours)
        watches_from_turns = self.exploration_turns // 24
        if watches_from_turns > self.watches:
            watch_diff = watches_from_turns - self.watches
            self.watches = watches_from_turns
            result["watches_passed"] = watch_diff
            for callback in self._watch_callbacks:
                callback(watch_diff)

        # Handle days passed
        if days_passed > 0:
            self.days += days_passed
            self.game_date = self.game_date.advance_days(days_passed)
            result["days_passed"] = days_passed
            result["new_date"] = str(self.game_date)
            for callback in self._day_callbacks:
                callback(days_passed)

            # Check season change
            new_season = self.game_date.get_season()
            if new_season != self.season:
                old_season = self.season
                self.season = new_season
                result["season_changed"] = True
                result["old_season"] = old_season.value
                result["new_season"] = new_season.value
                for callback in self._season_callbacks:
                    callback(old_season, new_season)

        # Run turn callbacks
        for callback in self._turn_callbacks:
            callback(turns)

        return result

    def advance_watch(self, watches: int = 1) -> dict[str, Any]:
        """
        Advance time by watches (4 hours each).

        Args:
            watches: Number of watches to advance

        Returns:
            Dictionary with time changes
        """
        # Each watch is 24 turns
        return self.advance_turn(watches * 24)

    def advance_day(self, days: int = 1) -> dict[str, Any]:
        """
        Advance time by full days.

        Args:
            days: Number of days to advance

        Returns:
            Dictionary with time changes
        """
        # Each day is 6 watches = 144 turns
        return self.advance_turn(days * 144)

    def advance_hours(self, hours: int) -> dict[str, Any]:
        """
        Advance time by hours.

        Args:
            hours: Number of hours to advance

        Returns:
            Dictionary with time changes
        """
        # Each hour is 6 turns
        return self.advance_turn(hours * 6)

    def check_seasonal_threshold(self) -> bool:
        """
        Check if we've crossed a seasonal boundary.

        Returns:
            True if season changed since last check
        """
        current_season = self.game_date.get_season()
        return current_season != self.season

    def register_turn_callback(self, callback: Callable[[int], None]) -> None:
        """Register callback for turn advancement."""
        self._turn_callbacks.append(callback)

    def register_watch_callback(self, callback: Callable[[int], None]) -> None:
        """Register callback for watch advancement."""
        self._watch_callbacks.append(callback)

    def register_day_callback(self, callback: Callable[[int], None]) -> None:
        """Register callback for day advancement."""
        self._day_callbacks.append(callback)

    def register_season_callback(self, callback: Callable[[Season, Season], None]) -> None:
        """Register callback for season changes."""
        self._season_callbacks.append(callback)

    def get_time_summary(self) -> dict[str, Any]:
        """Get a summary of current time state."""
        return {
            "date": str(self.game_date),
            "time": str(self.game_time),
            "time_of_day": self.game_time.get_time_of_day().value,
            "watch": self.game_time.get_current_watch().value,
            "season": self.season.value,
            "is_daylight": self.game_time.is_daylight(),
            "total_turns": self.exploration_turns,
            "total_days": self.days,
        }


class GlobalController:
    """
    Central game controller that coordinates all subsystems.

    This class is the authoritative source for:
    - Game state management via StateMachine
    - Time tracking via TimeTracker
    - World state persistence
    - Party state management
    - Character roster

    Implements Section 5.1 Global Loop Invariants:
    1. Validate current state
    2. Load shared state (World, Party, Location)
    3. Enforce procedure ordering
    4. Log all state mutations
    5. Disallow LLM authority over outcomes
    """

    def __init__(
        self,
        initial_state: GameState = GameState.WILDERNESS_TRAVEL,
        game_date: Optional[GameDate] = None,
        game_time: Optional[GameTime] = None,
    ):
        """
        Initialize the global controller.

        Args:
            initial_state: Starting game state
            game_date: Starting date (default: Year 1, Month 1, Day 1)
            game_time: Starting time (default: 08:00)
        """
        # Core subsystems
        self.state_machine = StateMachine(initial_state)
        self.time_tracker = TimeTracker(
            game_date=game_date or GameDate(year=1, month=1, day=1),
            game_time=game_time or GameTime(hour=8, minute=0),
        )
        self.dice_roller = DiceRoller()

        # Game state storage
        self.world_state = WorldState(
            current_date=self.time_tracker.game_date,
            current_time=self.time_tracker.game_time,
            season=self.time_tracker.season,
            weather=Weather.CLEAR,
        )

        self.party_state = PartyState(
            location=Location(LocationType.HEX, "0101"),
            resources=PartyResources(),
        )

        # Character roster
        self._characters: dict[str, CharacterState] = {}

        # Location cache
        self._locations: dict[str, LocationState] = {}

        # Current encounter (if any)
        self._current_encounter: Optional[EncounterState] = None

        # Narrative resolver for effect tracking (optional)
        self._narrative_resolver: Optional["NarrativeResolver"] = None
        if NARRATIVE_AVAILABLE:
            self._narrative_resolver = NarrativeResolver(controller=self)

        # XP Manager for advancement tracking (optional)
        self._xp_manager: Optional["XPManager"] = None
        if XP_MANAGER_AVAILABLE:
            self._xp_manager = XPManager(controller=self)

        # Session log
        self._session_log: list[dict[str, Any]] = []

        # Register state machine hooks
        self.state_machine.register_post_hook(self._on_state_transition)

        # Register time callbacks
        self.time_tracker.register_turn_callback(self._on_turn_advance)
        self.time_tracker.register_watch_callback(self._on_watch_advance)
        self.time_tracker.register_day_callback(self._on_day_advance)
        self.time_tracker.register_season_callback(self._on_season_change)

        logger.info(f"GlobalController initialized in state: {initial_state.value}")

    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================

    @property
    def current_state(self) -> GameState:
        """Get current game state."""
        return self.state_machine.current_state

    @property
    def xp_manager(self) -> Optional["XPManager"]:
        """Get the XP manager for advancement tracking."""
        return self._xp_manager

    def transition(self, trigger: str, context: Optional[dict[str, Any]] = None) -> GameState:
        """
        Transition to a new game state.

        Args:
            trigger: The trigger causing the transition
            context: Optional context data

        Returns:
            The new game state
        """
        return self.state_machine.transition(trigger, context)

    def can_transition(self, trigger: str) -> bool:
        """Check if a transition is valid from current state."""
        return self.state_machine.can_transition(trigger)

    def get_valid_actions(self) -> list[str]:
        """Get valid triggers/actions from current state."""
        return self.state_machine.get_valid_triggers()

    # =========================================================================
    # TIME MANAGEMENT
    # =========================================================================

    def advance_time(self, turns: int = 1) -> dict[str, Any]:
        """
        Advance game time and trigger any time-based effects.

        Args:
            turns: Number of 10-minute turns to advance

        Returns:
            Dictionary with time changes and effects
        """
        result = self.time_tracker.advance_turn(turns)

        # Sync world state with time tracker
        self.world_state.current_time = self.time_tracker.game_time
        self.world_state.current_date = self.time_tracker.game_date
        self.world_state.season = self.time_tracker.season

        # Deplete light sources
        if self.party_state.active_light_source:
            self.party_state.light_remaining_turns -= turns
            if self.party_state.light_remaining_turns <= 0:
                result["light_extinguished"] = True
                result["light_source"] = self.party_state.active_light_source.value
                self.party_state.active_light_source = None
                self.party_state.light_remaining_turns = 0

        # Tick conditions on all characters
        expired_conditions = self._tick_conditions(turns)
        if expired_conditions:
            result["expired_conditions"] = expired_conditions

        self._log_event("time_advance", result)
        return result

    def advance_travel_segment(self, terrain_modifier: float = 1.0) -> dict[str, Any]:
        """
        Advance time for a travel segment.

        A standard travel segment is 4 hours (1 watch) in clear terrain.

        Args:
            terrain_modifier: Multiplier for difficult terrain (>1 = slower)

        Returns:
            Dictionary with travel results
        """
        base_hours = 4
        actual_hours = int(base_hours * terrain_modifier)
        return self.advance_time(actual_hours * 6)  # 6 turns per hour

    # =========================================================================
    # CHARACTER MANAGEMENT
    # =========================================================================

    def add_character(self, character: CharacterState) -> None:
        """Add a character to the roster."""
        self._characters[character.character_id] = character
        if character.character_id not in self.party_state.marching_order:
            self.party_state.marching_order.append(character.character_id)
        self._log_event("character_added", {"character_id": character.character_id})

    def get_character(self, character_id: str) -> Optional[CharacterState]:
        """Get a character by ID."""
        return self._characters.get(character_id)

    def get_all_characters(self) -> list[CharacterState]:
        """Get all characters in the party."""
        return list(self._characters.values())

    def get_active_characters(self) -> list[CharacterState]:
        """Get all conscious, active characters."""
        return [c for c in self._characters.values() if c.is_conscious()]

    def get_party_speed(self) -> int:
        """
        Get party movement speed per Dolmenwood rules (p146, p148-149).

        Party speed is determined by the slowest member's encumbered speed.

        Returns:
            Party movement speed (slowest member's encumbered speed)
        """
        characters = self.get_active_characters()
        if not characters:
            return 40  # Default unencumbered speed

        # Update party state with current member speeds
        self.party_state.update_member_speeds(characters)

        return self.party_state.get_movement_rate()

    def update_party_encumbrance(self) -> dict[str, Any]:
        """
        Update party encumbrance state from all characters.

        Call this after any inventory changes.

        Returns:
            Dictionary with encumbrance status for each character
        """
        characters = self.get_all_characters()
        self.party_state.update_member_speeds(characters)

        result = {
            "party_speed": self.party_state.get_movement_rate(),
            "total_weight": self.party_state.encumbrance_total,
            "members": {}
        }

        for char in characters:
            enc_state = char.get_encumbrance_state()
            result["members"][char.character_id] = {
                "name": char.name,
                "speed": char.get_encumbered_speed(),
                "weight": enc_state.total_weight,
                "equipped_slots": enc_state.equipped_slots,
                "stowed_slots": enc_state.stowed_slots,
                "over_capacity": char.is_over_capacity()
            }

        return result

    def is_party_over_capacity(self) -> bool:
        """
        Check if any party member is over carrying capacity.

        Returns:
            True if any member is over capacity
        """
        return self.party_state.any_over_capacity(self.get_all_characters())

    def remove_character(self, character_id: str) -> Optional[CharacterState]:
        """Remove a character from the roster."""
        character = self._characters.pop(character_id, None)
        if character and character_id in self.party_state.marching_order:
            self.party_state.marching_order.remove(character_id)
        return character

    def apply_damage(
        self,
        character_id: str,
        damage: int,
        damage_type: str = "physical"
    ) -> dict[str, Any]:
        """
        Apply damage to a character.

        Automatically breaks concentration per Dolmenwood rules.

        Args:
            character_id: The character to damage
            damage: Amount of damage
            damage_type: Type of damage for resistance checks

        Returns:
            Dictionary with damage results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        old_hp = character.hp_current
        character.hp_current = max(0, character.hp_current - damage)
        actual_damage = old_hp - character.hp_current

        result = {
            "character_id": character_id,
            "damage_dealt": actual_damage,
            "hp_remaining": character.hp_current,
            "hp_max": character.hp_max,
        }

        # Break concentration on damage (per Dolmenwood rules)
        if actual_damage > 0 and self._narrative_resolver:
            broken_effects = self._narrative_resolver.break_concentration(character_id)
            if broken_effects:
                result["concentration_broken"] = [
                    effect.spell_name for effect in broken_effects
                ]

        if character.hp_current <= 0:
            character.conditions.append(
                Condition(ConditionType.UNCONSCIOUS, source="damage")
            )
            result["unconscious"] = True

            # Check for death at -10 or negative equal to max HP
            if character.hp_current <= -10 or character.hp_current <= -character.hp_max:
                character.conditions.append(
                    Condition(ConditionType.DEAD, source="damage")
                )
                result["dead"] = True

        self._log_event("damage_applied", result)
        return result

    def heal_character(
        self,
        character_id: str,
        healing: int
    ) -> dict[str, Any]:
        """
        Heal a character.

        Args:
            character_id: The character to heal
            healing: Amount of healing

        Returns:
            Dictionary with healing results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        old_hp = character.hp_current
        character.hp_current = min(character.hp_max, character.hp_current + healing)
        actual_healing = character.hp_current - old_hp

        # Remove unconscious if healed above 0
        if old_hp <= 0 and character.hp_current > 0:
            character.conditions = [
                c for c in character.conditions
                if c.condition_type != ConditionType.UNCONSCIOUS
            ]

        result = {
            "character_id": character_id,
            "healing_received": actual_healing,
            "hp_current": character.hp_current,
            "hp_max": character.hp_max,
        }

        self._log_event("healing_applied", result)
        return result

    # =========================================================================
    # LOCATION MANAGEMENT
    # =========================================================================

    def set_party_location(
        self,
        location_type: LocationType,
        location_id: str,
        sub_location: Optional[str] = None
    ) -> None:
        """Set the party's current location."""
        self.party_state.location = Location(
            location_type=location_type,
            location_id=location_id,
            sub_location=sub_location
        )
        self._log_event("location_changed", {
            "location": str(self.party_state.location)
        })

    def get_location_state(self, location_id: str) -> Optional[LocationState]:
        """Get state for a specific location."""
        return self._locations.get(location_id)

    def set_location_state(self, location_id: str, state: LocationState) -> None:
        """Set state for a location."""
        self._locations[location_id] = state

    # =========================================================================
    # ENCOUNTER MANAGEMENT
    # =========================================================================

    def set_encounter(self, encounter: EncounterState) -> None:
        """Set the current encounter."""
        self._current_encounter = encounter
        self._log_event("encounter_started", {
            "encounter_id": encounter.encounter_id,
            "encounter_type": encounter.encounter_type.value,
        })

    def get_encounter(self) -> Optional[EncounterState]:
        """Get the current encounter."""
        return self._current_encounter

    def clear_encounter(self) -> None:
        """Clear the current encounter."""
        if self._current_encounter:
            self._log_event("encounter_ended", {
                "encounter_id": self._current_encounter.encounter_id,
            })
        self._current_encounter = None

    # =========================================================================
    # RESOURCE MANAGEMENT
    # =========================================================================

    def consume_resources(
        self,
        food_days: float = 0,
        water_days: float = 0,
        torches: int = 0,
        oil_flasks: int = 0
    ) -> dict[str, Any]:
        """
        Consume party resources.

        Returns:
            Dictionary with consumption results and warnings
        """
        party_size = len(self.get_active_characters())
        result = {"consumed": {}, "warnings": []}

        if food_days > 0:
            sufficient = self.party_state.resources.consume_food(food_days, party_size)
            result["consumed"]["food"] = food_days * party_size
            if not sufficient:
                result["warnings"].append("Party is out of food!")

        if water_days > 0:
            sufficient = self.party_state.resources.consume_water(water_days, party_size)
            result["consumed"]["water"] = water_days * party_size
            if not sufficient:
                result["warnings"].append("Party is out of water!")

        if torches > 0:
            self.party_state.resources.torches -= torches
            result["consumed"]["torches"] = torches
            if self.party_state.resources.torches < 0:
                self.party_state.resources.torches = 0
                result["warnings"].append("No more torches!")

        if oil_flasks > 0:
            self.party_state.resources.lantern_oil_flasks -= oil_flasks
            result["consumed"]["oil_flasks"] = oil_flasks
            if self.party_state.resources.lantern_oil_flasks < 0:
                self.party_state.resources.lantern_oil_flasks = 0
                result["warnings"].append("No more lantern oil!")

        if result["consumed"]:
            self._log_event("resources_consumed", result)

        return result

    def light_source(self, source_type: LightSourceType) -> dict[str, Any]:
        """
        Activate a light source.

        Returns:
            Dictionary with light source status
        """
        duration_map = {
            LightSourceType.TORCH: 6,  # 1 hour
            LightSourceType.LANTERN: 24,  # 4 hours
            LightSourceType.CANDLE: 12,  # 2 hours
            LightSourceType.MAGICAL: 144,  # 24 hours
        }

        if source_type == LightSourceType.TORCH:
            if self.party_state.resources.torches <= 0:
                return {"error": "No torches available"}
            self.party_state.resources.torches -= 1

        elif source_type == LightSourceType.LANTERN:
            if self.party_state.resources.lantern_oil_flasks <= 0:
                return {"error": "No lantern oil available"}
            self.party_state.resources.lantern_oil_flasks -= 1

        self.party_state.active_light_source = source_type
        self.party_state.light_remaining_turns = duration_map.get(source_type, 6)

        result = {
            "light_source": source_type.value,
            "duration_turns": self.party_state.light_remaining_turns,
        }
        self._log_event("light_activated", result)
        return result

    # =========================================================================
    # WEATHER AND ENVIRONMENT
    # =========================================================================

    def set_weather(self, weather: Weather) -> None:
        """Set current weather."""
        old_weather = self.world_state.weather
        self.world_state.weather = weather
        self._log_event("weather_changed", {
            "old_weather": old_weather.value,
            "new_weather": weather.value,
        })

    def roll_weather(self) -> Weather:
        """
        Roll for random weather appropriate to season.

        Returns:
            The new weather condition
        """
        season = self.world_state.season
        roll = self.dice_roller.roll_2d6("weather").total

        # Simplified weather table by season
        if season == Season.WINTER:
            weather_table = {
                2: Weather.BLIZZARD,
                3: Weather.BLIZZARD,
                4: Weather.SNOW,
                5: Weather.SNOW,
                6: Weather.OVERCAST,
                7: Weather.OVERCAST,
                8: Weather.OVERCAST,
                9: Weather.FOG,
                10: Weather.CLEAR,
                11: Weather.CLEAR,
                12: Weather.CLEAR,
            }
        elif season == Season.SPRING:
            weather_table = {
                2: Weather.STORM,
                3: Weather.RAIN,
                4: Weather.RAIN,
                5: Weather.RAIN,
                6: Weather.OVERCAST,
                7: Weather.OVERCAST,
                8: Weather.FOG,
                9: Weather.CLEAR,
                10: Weather.CLEAR,
                11: Weather.CLEAR,
                12: Weather.CLEAR,
            }
        elif season == Season.SUMMER:
            weather_table = {
                2: Weather.STORM,
                3: Weather.RAIN,
                4: Weather.OVERCAST,
                5: Weather.OVERCAST,
                6: Weather.CLEAR,
                7: Weather.CLEAR,
                8: Weather.CLEAR,
                9: Weather.CLEAR,
                10: Weather.CLEAR,
                11: Weather.CLEAR,
                12: Weather.CLEAR,
            }
        else:  # Autumn
            weather_table = {
                2: Weather.STORM,
                3: Weather.RAIN,
                4: Weather.RAIN,
                5: Weather.FOG,
                6: Weather.FOG,
                7: Weather.OVERCAST,
                8: Weather.OVERCAST,
                9: Weather.OVERCAST,
                10: Weather.CLEAR,
                11: Weather.CLEAR,
                12: Weather.CLEAR,
            }

        new_weather = weather_table.get(roll, Weather.CLEAR)
        self.set_weather(new_weather)
        return new_weather

    # =========================================================================
    # EFFECT MANAGEMENT
    # =========================================================================

    def get_narrative_resolver(self) -> Optional["NarrativeResolver"]:
        """Get the narrative resolver for effect tracking."""
        return self._narrative_resolver

    def tick_spell_effects(self, time_unit: str = "turns") -> list[dict[str, Any]]:
        """
        Tick all spell effects and return expired ones.

        Args:
            time_unit: "rounds" or "turns"

        Returns:
            List of expired effect info
        """
        if not self._narrative_resolver:
            return []

        expired_effects = self._narrative_resolver.tick_effects(time_unit)

        return [
            {
                "effect_id": e.effect_id,
                "spell_name": e.spell_name,
                "caster_id": e.caster_id,
                "target_id": e.target_id,
            }
            for e in expired_effects
        ]

    def tick_location_effects(self, location_id: str) -> list[dict[str, Any]]:
        """
        Tick all area effects at a location and return expired ones.

        Args:
            location_id: The location to tick effects for

        Returns:
            List of expired effect info
        """
        location = self._locations.get(location_id)
        if not location:
            return []

        expired_effects = location.tick_effects()

        return [
            {
                "effect_id": e.effect_id,
                "name": e.name,
                "effect_type": e.effect_type.value,
            }
            for e in expired_effects
        ]

    def tick_polymorph_effects(self) -> list[dict[str, Any]]:
        """
        Tick all polymorph overlays and return expired ones.

        Returns:
            List of expired polymorph info
        """
        expired = []

        for character in self._characters.values():
            if character.polymorph_overlay and character.polymorph_overlay.is_active:
                if character.polymorph_overlay.tick():
                    expired.append({
                        "character_id": character.character_id,
                        "character_name": character.name,
                        "form_name": character.polymorph_overlay.form_name,
                    })
                    character.polymorph_overlay = None

        return expired

    def add_area_effect(
        self,
        location_id: str,
        effect: AreaEffect
    ) -> dict[str, Any]:
        """
        Add an area effect to a location.

        Args:
            location_id: The location to add the effect to
            effect: The area effect to add

        Returns:
            Result of adding the effect
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        location.add_area_effect(effect)

        result = {
            "effect_id": effect.effect_id,
            "name": effect.name,
            "location_id": location_id,
            "duration_turns": effect.duration_turns,
        }

        self._log_event("area_effect_added", result)
        return result

    def remove_area_effect(
        self,
        location_id: str,
        effect_id: str
    ) -> dict[str, Any]:
        """
        Remove an area effect from a location.

        Args:
            location_id: The location to remove the effect from
            effect_id: The effect ID to remove

        Returns:
            Result of removing the effect
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        effect = location.remove_area_effect(effect_id)
        if not effect:
            return {"error": f"Effect {effect_id} not found"}

        result = {
            "effect_id": effect_id,
            "name": effect.name,
            "location_id": location_id,
        }

        self._log_event("area_effect_removed", result)
        return result

    def apply_polymorph(
        self,
        character_id: str,
        overlay: PolymorphOverlay
    ) -> dict[str, Any]:
        """
        Apply a polymorph transformation to a character.

        Args:
            character_id: The character to transform
            overlay: The polymorph overlay to apply

        Returns:
            Result of applying the transformation
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        # Remove existing polymorph if any
        old_form = None
        if character.polymorph_overlay:
            old_form = character.polymorph_overlay.form_name

        character.apply_polymorph(overlay)

        result = {
            "character_id": character_id,
            "character_name": character.name,
            "new_form": overlay.form_name,
            "previous_form": old_form,
            "duration_turns": overlay.duration_turns,
        }

        self._log_event("polymorph_applied", result)
        return result

    def remove_polymorph(self, character_id: str) -> dict[str, Any]:
        """
        Remove a polymorph transformation from a character.

        Args:
            character_id: The character to restore

        Returns:
            Result of removing the transformation
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        overlay = character.remove_polymorph()
        if not overlay:
            return {"error": f"Character {character_id} is not polymorphed"}

        result = {
            "character_id": character_id,
            "character_name": character.name,
            "restored_from": overlay.form_name,
        }

        self._log_event("polymorph_removed", result)
        return result

    def get_active_effects_on_character(
        self,
        character_id: str
    ) -> dict[str, Any]:
        """
        Get all active effects on a character.

        Args:
            character_id: The character to check

        Returns:
            Dictionary with all active effects
        """
        result = {
            "character_id": character_id,
            "spell_effects": [],
            "polymorph": None,
            "conditions": [],
        }

        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        # Spell effects from narrative resolver
        if self._narrative_resolver:
            spell_effects = self._narrative_resolver.get_active_effects(character_id)
            result["spell_effects"] = [
                {
                    "effect_id": e.effect_id,
                    "spell_name": e.spell_name,
                    "duration_remaining": e.duration_remaining,
                    "requires_concentration": e.requires_concentration,
                }
                for e in spell_effects
            ]

        # Polymorph overlay
        if character.polymorph_overlay and character.polymorph_overlay.is_active:
            result["polymorph"] = {
                "form_name": character.polymorph_overlay.form_name,
                "duration_remaining": character.polymorph_overlay.duration_turns,
            }

        # Conditions
        result["conditions"] = [
            {
                "type": c.condition_type.value,
                "duration": c.duration_turns,
                "source": c.source,
            }
            for c in character.conditions
        ]

        return result

    def get_location_effects(self, location_id: str) -> dict[str, Any]:
        """
        Get all area effects at a location.

        Args:
            location_id: The location to check

        Returns:
            Dictionary with all active area effects
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        return {
            "location_id": location_id,
            "effects": [
                {
                    "effect_id": e.effect_id,
                    "name": e.name,
                    "effect_type": e.effect_type.value,
                    "duration_remaining": e.duration_turns,
                    "blocks_movement": e.blocks_movement,
                    "blocks_vision": e.blocks_vision,
                    "blocks_sound": e.blocks_sound,
                }
                for e in location.get_active_effects()
            ],
            "has_blocking_movement": location.has_blocking_effect("movement"),
            "has_blocking_vision": location.has_blocking_effect("vision"),
            "has_blocking_sound": location.has_blocking_effect("sound"),
        }

    # =========================================================================
    # INTERNAL CALLBACKS
    # =========================================================================

    def _on_state_transition(
        self,
        old_state: GameState,
        new_state: GameState,
        trigger: str,
        context: dict[str, Any]
    ) -> None:
        """Called after any state transition."""
        self._log_event("state_transition", {
            "from": old_state.value,
            "to": new_state.value,
            "trigger": trigger,
            "context": context,
        })

    def _on_turn_advance(self, turns: int) -> None:
        """Called when exploration turns advance."""
        # Tick spell effects
        for _ in range(turns):
            self.tick_spell_effects("turns")
            self.tick_polymorph_effects()

            # Tick area effects at current location
            if self.party_state.location:
                self.tick_location_effects(self.party_state.location.location_id)

    def _on_watch_advance(self, watches: int) -> None:
        """Called when watches advance."""
        pass  # Override in subclasses if needed

    def _on_day_advance(self, days: int) -> None:
        """Called when days advance."""
        # Consume daily resources
        self.consume_resources(food_days=days, water_days=days)

    def _on_season_change(self, old_season: Season, new_season: Season) -> None:
        """Called when season changes."""
        self._log_event("season_changed", {
            "old_season": old_season.value,
            "new_season": new_season.value,
        })

    def _tick_conditions(self, turns: int) -> list[dict[str, Any]]:
        """Tick all conditions and return expired ones."""
        expired = []

        for character in self._characters.values():
            still_active = []
            for condition in character.conditions:
                for _ in range(turns):
                    if condition.tick():
                        expired.append({
                            "character_id": character.character_id,
                            "condition": condition.condition_type.value,
                        })
                        break
                else:
                    still_active.append(condition)
            character.conditions = still_active

        return expired

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log an event to the session log."""
        self._session_log.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "game_time": str(self.time_tracker.game_time),
            "game_date": str(self.time_tracker.game_date),
            "data": data,
        })
        logger.debug(f"Event: {event_type} - {data}")

    # =========================================================================
    # STATE PERSISTENCE
    # =========================================================================

    def get_full_state(self) -> dict[str, Any]:
        """
        Get complete game state for persistence or display.

        Returns:
            Dictionary with all game state
        """
        return {
            "state_machine": self.state_machine.get_state_info(),
            "time": self.time_tracker.get_time_summary(),
            "world": {
                "date": str(self.world_state.current_date),
                "time": str(self.world_state.current_time),
                "season": self.world_state.season.value,
                "weather": self.world_state.weather.value,
                "global_flags": self.world_state.global_flags,
                "cleared_locations": list(self.world_state.cleared_locations),
            },
            "party": {
                "location": str(self.party_state.location),
                "marching_order": self.party_state.marching_order,
                "resources": {
                    "food_days": self.party_state.resources.food_days,
                    "water_days": self.party_state.resources.water_days,
                    "torches": self.party_state.resources.torches,
                    "oil_flasks": self.party_state.resources.lantern_oil_flasks,
                },
                "light_source": self.party_state.active_light_source.value if self.party_state.active_light_source else None,
                "light_remaining": self.party_state.light_remaining_turns,
            },
            "characters": {
                cid: {
                    "name": c.name,
                    "class": c.character_class,
                    "level": c.level,
                    "hp": f"{c.hp_current}/{c.hp_max}",
                    "conditions": [cond.condition_type.value for cond in c.conditions],
                }
                for cid, c in self._characters.items()
            },
            "encounter": {
                "active": self._current_encounter is not None,
                "type": self._current_encounter.encounter_type.value if self._current_encounter else None,
            },
        }

    def get_session_log(self) -> list[dict[str, Any]]:
        """Get the session log."""
        return self._session_log.copy()

    def clear_session_log(self) -> None:
        """Clear the session log."""
        self._session_log = []
