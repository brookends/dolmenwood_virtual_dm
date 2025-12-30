"""
Hazard Resolver for Dolmenwood Virtual DM.

Handles environmental hazards and physical challenges per Dolmenwood rules (p150-155):
- Climbing, Jumping, Swimming
- Doors (forcing, listening)
- Traps (triggering, searching)
- Environmental hazards (cold, darkness, falling, hunger, exhaustion)
- Finding food (foraging, fishing, hunting)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_models import CharacterState, DiceRoller, ArmorWeight

from src.narrative.intent_parser import ActionType, ResolutionType, CheckType, ParsedIntent
from src.tables.foraging_tables import (
    ForageableItem,
    ForageType,
    roll_forage_type,
    roll_foraged_item,
    roll_forage_quantity,
    is_fungi,
)
from src.tables.fishing_tables import (
    CatchableFish,
    roll_fish,
    roll_fish_rations,
    check_treasure_in_fish,
    check_monster_attracted,
    fish_requires_landing_check,
    fish_triggers_combat,
    fish_is_fairy,
)
from src.tables.hunting_tables import (
    GameAnimal,
    TerrainType as HuntingTerrainType,
    roll_game_animal,
    roll_number_appearing,
    roll_encounter_distance,
    calculate_rations_yield,
    get_hunting_terrain,
)
from src.narrative.sensory_details import (
    SensoryContext,
    TerrainContext,
    TimeOfDayContext,
    WeatherContext,
    get_foraging_scene,
    get_fishing_scene,
    get_hunting_scene,
    get_trap_scene,
    get_secret_door_scene,
    build_narrative_hints,
)


class HazardType(str, Enum):
    """Types of hazards per Dolmenwood rules."""

    # Physical challenges
    CLIMBING = "climbing"  # p150
    COLD = "cold"  # p150
    DARKNESS = "darkness"  # p150
    DIVING = "diving"  # Swimming underwater with breath tracking
    DOOR_STUCK = "door_stuck"  # p151
    DOOR_LOCKED = "door_locked"  # p151
    DOOR_LISTEN = "door_listen"  # p151
    EXHAUSTION = "exhaustion"  # p151
    FALLING = "falling"  # p151
    HUNGER = "hunger"  # p153
    THIRST = "thirst"  # p153
    JUMPING = "jumping"  # p153
    SWIMMING = "swimming"  # p154
    SUFFOCATION = "suffocation"  # p154
    TRAP = "trap"  # p155


class DarknessLevel(str, Enum):
    """Light levels affecting visibility."""

    BRIGHT = "bright"  # Normal vision
    LOW_LIGHT = "low_light"  # -2 Attack, half Speed
    PITCH_DARK = "pitch_dark"  # -4 Attack/AC/Saves, Speed 10


@dataclass
class HazardResult:
    """Result of resolving a hazard."""

    success: bool
    hazard_type: HazardType
    action_type: ActionType

    # What happened
    description: str = ""
    damage_dealt: int = 0
    damage_type: str = ""

    # Check details
    check_made: bool = False
    check_type: Optional[CheckType] = None
    check_target: Optional[int] = None
    check_result: Optional[int] = None
    check_modifier: int = 0

    # Time cost
    turns_spent: int = 0

    # State changes
    conditions_applied: list[str] = field(default_factory=list)
    penalties_applied: dict[str, int] = field(default_factory=dict)

    # Effects to apply to game state (target_id, value)
    apply_damage: list[tuple[str, int]] = field(default_factory=list)
    apply_conditions: list[tuple[str, str]] = field(default_factory=list)

    # For LLM narration
    narrative_hints: list[str] = field(default_factory=list)

    # Nested results (e.g., for traps that deal damage)
    nested_results: list["HazardResult"] = field(default_factory=list)

    # Diving-specific
    rounds_underwater: int = 0
    rounds_remaining: int = 0

    # Foraging-specific
    foraged_items: list[dict[str, Any]] = field(default_factory=list)
    rations_found: int = 0

    # Fishing-specific (Campaign Book p116-117)
    fish_caught: Optional[dict[str, Any]] = None  # The fish species caught
    landing_required: Optional[dict[str, Any]] = None  # Landing check needed
    catch_events: list[dict[str, Any]] = field(default_factory=list)  # Events during catch
    treasure_found: Optional[dict[str, Any]] = None  # Treasure in fish belly
    monster_attracted: bool = False  # Screaming jenny effect
    combat_triggered: bool = False  # Giant catfish
    blessing_offered: bool = False  # Queen's salmon

    # Hunting-specific (Campaign Book p120-121)
    game_animal: Optional[dict[str, Any]] = None  # The game animal found
    number_appearing: int = 0  # How many animals in the group
    encounter_distance: int = 0  # Starting distance in feet (1d4 × 30')
    party_has_surprise: bool = False  # Party always has surprise when hunting
    potential_rations: int = 0  # Rations if all animals killed


@dataclass
class DivingState:
    """
    Tracks diving/underwater exploration state for a character.

    Per Dolmenwood rules (p154):
    - A character can survive for up to 1 Round (10 seconds) per point of CON
      before suffocating to death
    - Swimming is at half speed
    - Armor imposes penalties on swimming checks
    """

    character_id: str
    rounds_underwater: int = 0
    max_rounds: int = 10  # Will be set from CON score

    # Diving status
    is_diving: bool = False
    depth_feet: int = 0

    # Swimming check results
    last_swim_check_success: bool = True

    def start_dive(self, con_score: int) -> None:
        """Start diving, calculating max breath time from CON."""
        self.is_diving = True
        self.rounds_underwater = 0
        self.max_rounds = con_score
        self.last_swim_check_success = True

    def advance_round(self) -> int:
        """
        Advance time by one round underwater.

        Returns:
            Rounds of breath remaining
        """
        if not self.is_diving:
            return self.max_rounds
        self.rounds_underwater += 1
        return max(0, self.max_rounds - self.rounds_underwater)

    def advance_turn(self) -> int:
        """
        Advance time by one turn (6 rounds) underwater.

        Returns:
            Rounds of breath remaining
        """
        for _ in range(6):
            remaining = self.advance_round()
            if remaining <= 0:
                return 0
        return max(0, self.max_rounds - self.rounds_underwater)

    def get_rounds_remaining(self) -> int:
        """Get rounds of breath remaining."""
        return max(0, self.max_rounds - self.rounds_underwater)

    def is_suffocating(self) -> bool:
        """Check if character has run out of breath."""
        return self.rounds_underwater >= self.max_rounds

    def surface(self) -> None:
        """Surface and reset diving state."""
        self.is_diving = False
        self.rounds_underwater = 0
        self.depth_feet = 0

    def get_warning_level(self) -> str:
        """Get warning level based on remaining breath."""
        remaining = self.get_rounds_remaining()
        if remaining <= 0:
            return "suffocating"
        elif remaining <= 3:
            return "critical"
        elif remaining <= self.max_rounds // 2:
            return "warning"
        return "safe"


# Hazard constants per Dolmenwood rules

# Darkness penalties (p150)
DARKNESS_PENALTIES = {
    DarknessLevel.BRIGHT: {"attack": 0, "ac": 0, "saves": 0, "speed_override": None},
    DarknessLevel.LOW_LIGHT: {"attack": -2, "ac": 0, "saves": 0, "speed_multiplier": 0.5},
    DarknessLevel.PITCH_DARK: {"attack": -4, "ac": -4, "saves": -4, "speed_override": 10},
}

# Cold damage (p150)
COLD_DAMAGE_PER_DAY = "1d4"

# Exhaustion penalties (p151)
EXHAUSTION_PENALTY_PER_SOURCE = -1
EXHAUSTION_MAX_PENALTY = -4

# Fall damage (p151)
FALL_DAMAGE_PER_10FT = "1d6"

# Hunger effects by day (p153)
HUNGER_EFFECTS_MORTAL = {
    1: {"attack": -1, "speed": 0},
    2: {"attack": -1, "speed": -10},
    3: {"attack": -2, "speed": -10},
    4: {"attack": -2, "speed": -20},
    5: {"attack": -3, "speed": -20},
    6: {"attack": -4, "speed": -30},
    7: {"attack": -4, "speed": -30, "con_loss": 1},  # -1 CON per day
}

# Jump distances (p153)
JUMP_TRIVIAL_LONG = 5  # feet with 20' run-up
JUMP_CHECK_LONG = 10  # feet with Strength Check
JUMP_TRIVIAL_HIGH = 3  # feet with 20' run-up
JUMP_CHECK_HIGH = 5  # feet with Strength Check

# Armor jump modifiers (p153)
JUMP_ARMOR_MODIFIERS = {
    "unarmoured": 0,
    "light": 0,
    "medium": -1,
    "heavy": -2,
}

# Swim armor modifiers (p154)
SWIM_ARMOR_MODIFIERS = {
    "unarmoured": 0,
    "light": 0,
    "medium": -2,
    "heavy": -4,
}

# Trap trigger chance (p155)
TRAP_TRIGGER_CHANCE = 2  # X-in-6

# Suffocation rules (p154)
# A character can survive for up to 1 Round (10 seconds) per point of Constitution
# before suffocating to death
SECONDS_PER_ROUND = 10  # 1 round = 10 seconds
ROUNDS_PER_TURN = 6  # 1 turn = 60 seconds = 6 rounds

# Foraging yields (p152)
FORAGING_YIELDS = {
    "fishing": "2d6",
    "foraging_normal": "1d6",
    "foraging_winter": "1d4",
    "foraging_autumn": "1d8",
}


class HazardResolver:
    """
    Resolves environmental hazards and physical challenges.

    Implements Dolmenwood rules from p150-155.
    """

    def __init__(self, dice_roller: Optional["DiceRoller"] = None):
        """
        Initialize the hazard resolver.

        Args:
            dice_roller: Optional dice roller (will create one if not provided)
        """
        from src.data_models import DiceRoller

        self.dice = dice_roller or DiceRoller()

    def resolve_hazard(
        self, hazard_type: HazardType, character: "CharacterState", **kwargs: Any
    ) -> HazardResult:
        """
        Resolve a hazard for a character.

        Args:
            hazard_type: Type of hazard
            character: The character facing the hazard
            **kwargs: Additional context (distance, armor, etc.)

        Returns:
            HazardResult with outcomes
        """
        handlers = {
            HazardType.CLIMBING: self._resolve_climbing,
            HazardType.COLD: self._resolve_cold,
            HazardType.DARKNESS: self._resolve_darkness,
            HazardType.DIVING: self._resolve_diving,
            HazardType.DOOR_STUCK: self._resolve_door_stuck,
            HazardType.DOOR_LOCKED: self._resolve_door_locked,
            HazardType.DOOR_LISTEN: self._resolve_door_listen,
            HazardType.EXHAUSTION: self._resolve_exhaustion,
            HazardType.FALLING: self._resolve_falling,
            HazardType.HUNGER: self._resolve_hunger,
            HazardType.JUMPING: self._resolve_jumping,
            HazardType.SWIMMING: self._resolve_swimming,
            HazardType.SUFFOCATION: self._resolve_suffocation,
            HazardType.TRAP: self._resolve_trap,
        }

        handler = handlers.get(hazard_type)
        if handler:
            return handler(character, **kwargs)

        return HazardResult(
            success=False,
            hazard_type=hazard_type,
            action_type=ActionType.UNKNOWN,
            description=f"Unknown hazard type: {hazard_type}",
        )

    def _resolve_climbing(
        self,
        character: "CharacterState",
        height_feet: int = 10,
        is_trivial: bool = False,
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve a climbing attempt (p150).

        Trivial climbs (lower tree branches, non-pressured) require no roll.
        Otherwise, DEX check; failure = fall at halfway point.
        """
        if is_trivial:
            return HazardResult(
                success=True,
                hazard_type=HazardType.CLIMBING,
                action_type=ActionType.CLIMB,
                description="Trivial climb completed without difficulty",
                narrative_hints=["character climbs easily"],
            )

        # Make DEX check
        dex_mod = character.get_ability_modifier("DEX")
        roll = self.dice.roll_d20("Climbing check")
        check_result = roll.total + dex_mod

        # Target is typically 10 for moderate difficulty
        target = kwargs.get("difficulty", 10)
        success = check_result >= target

        if success:
            return HazardResult(
                success=True,
                hazard_type=HazardType.CLIMBING,
                action_type=ActionType.CLIMB,
                description=f"Successfully climbed {height_feet} feet",
                check_made=True,
                check_type=CheckType.DEXTERITY,
                check_target=target,
                check_result=check_result,
                check_modifier=dex_mod,
                narrative_hints=["character finds handholds", "steady progress upward"],
            )
        else:
            # Fall at halfway point
            fall_height = height_feet // 2
            fall_result = self._resolve_falling(character, height_feet=fall_height)

            return HazardResult(
                success=False,
                hazard_type=HazardType.CLIMBING,
                action_type=ActionType.CLIMB,
                description=f"Failed to climb, fell {fall_height} feet",
                damage_dealt=fall_result.damage_dealt,
                damage_type="falling",
                check_made=True,
                check_type=CheckType.DEXTERITY,
                check_target=target,
                check_result=check_result,
                check_modifier=dex_mod,
                narrative_hints=["grip slips", "tumbles down"],
                nested_results=[fall_result],
            )

    def _resolve_cold(
        self, character: "CharacterState", has_protection: bool = False, **kwargs: Any
    ) -> HazardResult:
        """
        Resolve cold exposure (p150).

        Without adequate protection (winter cloak), lose 1d4 HP per day.
        """
        if has_protection:
            return HazardResult(
                success=True,
                hazard_type=HazardType.COLD,
                action_type=ActionType.NARRATIVE_ACTION,
                description="Protected from cold",
                narrative_hints=["winter cloak keeps character warm"],
            )

        damage_roll = self.dice.roll(COLD_DAMAGE_PER_DAY, "Cold damage")

        return HazardResult(
            success=False,
            hazard_type=HazardType.COLD,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"Suffered {damage_roll.total} cold damage",
            damage_dealt=damage_roll.total,
            damage_type="cold",
            narrative_hints=["fingers go numb", "shivering uncontrollably"],
        )

    def _resolve_darkness(
        self,
        character: "CharacterState",
        darkness_level: DarknessLevel = DarknessLevel.PITCH_DARK,
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve darkness penalties (p150).

        Low light: -2 Attack, half Speed
        Pitch dark: -4 Attack/AC/Saves, Speed 10
        """
        penalties = DARKNESS_PENALTIES[darkness_level]

        return HazardResult(
            success=True,  # Not a pass/fail, just applies penalties
            hazard_type=HazardType.DARKNESS,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"Operating in {darkness_level.value}",
            penalties_applied=penalties,
            narrative_hints=(
                ["can barely see", "stumbling in darkness"]
                if darkness_level != DarknessLevel.BRIGHT
                else []
            ),
        )

    def _resolve_diving(
        self,
        character: "CharacterState",
        diving_state: Optional[DivingState] = None,
        rounds_to_spend: int = 1,
        armor_weight: str = "unarmoured",
        action: str = "dive",  # "dive", "swim", "surface", "action"
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve diving/underwater exploration with breath tracking.

        Per Dolmenwood rules (p154):
        - A character can survive for 1 Round (10 seconds) per CON point
          before suffocating to death
        - Swimming is at half speed
        - Armor imposes penalties

        Args:
            character: The character diving
            diving_state: Current diving state (or None to start fresh)
            rounds_to_spend: How many rounds this action takes underwater
            armor_weight: Weight of armor worn
            action: "dive" to start, "swim" for movement, "surface" to return,
                   "action" for exploring/grabbing items

        Returns:
            HazardResult with diving outcomes
        """
        con_score = character.ability_scores.get("CON", 10)

        # Initialize or use existing diving state
        if diving_state is None:
            diving_state = DivingState(character_id=character.character_id)
            diving_state.start_dive(con_score)

        # Handle surfacing
        if action == "surface":
            diving_state.surface()
            return HazardResult(
                success=True,
                hazard_type=HazardType.DIVING,
                action_type=ActionType.SWIM,
                description="Surfaced successfully, catching breath",
                rounds_underwater=0,
                rounds_remaining=con_score,
                narrative_hints=["breaks the surface", "gasps for air", "breathes deeply"],
            )

        # Handle initial dive
        if action == "dive":
            diving_state.start_dive(con_score)

        # Advance time underwater
        for _ in range(rounds_to_spend):
            remaining = diving_state.advance_round()

            # Check for suffocation
            if remaining <= 0:
                return HazardResult(
                    success=False,
                    hazard_type=HazardType.DIVING,
                    action_type=ActionType.SWIM,
                    description="Ran out of breath and drowned!",
                    conditions_applied=["dead"],
                    rounds_underwater=diving_state.rounds_underwater,
                    rounds_remaining=0,
                    narrative_hints=[
                        "lungs burn",
                        "darkness closes in",
                        "cannot hold breath any longer",
                    ],
                )

        # Check swimming ability (for movement actions)
        swim_success = True
        swim_check_result = None
        if action in ("swim", "dive"):
            armor_mod = SWIM_ARMOR_MODIFIERS.get(armor_weight, 0)

            # Heavy/medium armor requires a check
            if armor_mod < 0:
                str_mod = character.get_ability_modifier("STR")
                total_mod = armor_mod + str_mod

                roll = self.dice.roll_d20("Swimming underwater")
                swim_check_result = roll.total + total_mod
                target = kwargs.get("difficulty", 10)
                swim_success = swim_check_result >= target

                if not swim_success:
                    # Failed swim check - sink and use extra round
                    diving_state.advance_round()
                    diving_state.last_swim_check_success = False

        rounds_remaining = diving_state.get_rounds_remaining()
        warning_level = diving_state.get_warning_level()

        # Build narrative hints based on warning level
        narrative_hints = []
        if warning_level == "critical":
            narrative_hints = ["lungs burning", "desperate for air", "vision blurring"]
        elif warning_level == "warning":
            narrative_hints = ["chest tightening", "need to surface soon"]
        else:
            narrative_hints = ["swimming underwater", "light filtering from above"]

        if not swim_success:
            narrative_hints.append("struggling against armor weight")

        result = HazardResult(
            success=swim_success,
            hazard_type=HazardType.DIVING,
            action_type=ActionType.SWIM,
            description=f"Underwater: {rounds_remaining} rounds of breath remaining",
            rounds_underwater=diving_state.rounds_underwater,
            rounds_remaining=rounds_remaining,
            penalties_applied={"speed_multiplier": 0.5},
            narrative_hints=narrative_hints,
        )

        if swim_check_result is not None:
            result.check_made = True
            result.check_type = CheckType.STRENGTH
            result.check_result = swim_check_result

        return result

    def create_diving_state(self, character: "CharacterState") -> DivingState:
        """
        Create a new diving state for a character.

        Args:
            character: The character to create state for

        Returns:
            New DivingState initialized with character's CON
        """
        con_score = character.ability_scores.get("CON", 10)
        state = DivingState(character_id=character.character_id)
        state.max_rounds = con_score
        return state

    def _resolve_door_stuck(
        self, character: "CharacterState", has_tools: bool = False, **kwargs: Any
    ) -> HazardResult:
        """
        Resolve forcing a stuck door (p151).

        Requires Strength Check. Takes 1 Turn.
        Failed attempt eliminates surprise possibility.
        """
        str_mod = character.get_ability_modifier("STR")
        tool_bonus = 2 if has_tools else 0

        roll = self.dice.roll_d20("Force stuck door")
        check_result = roll.total + str_mod + tool_bonus
        target = kwargs.get("difficulty", 10)

        success = check_result >= target

        result = HazardResult(
            success=success,
            hazard_type=HazardType.DOOR_STUCK,
            action_type=ActionType.FORCE_DOOR,
            description="Door forced open" if success else "Failed to force door",
            check_made=True,
            check_type=CheckType.STRENGTH,
            check_target=target,
            check_result=check_result,
            check_modifier=str_mod + tool_bonus,
            turns_spent=1,
            narrative_hints=[
                "door bursts open" if success else "door holds firm",
                "loud noise echoes" if not success else "",
            ],
        )

        if not success:
            result.narrative_hints.append("any creatures beyond are now alert")

        return result

    def _resolve_door_locked(
        self,
        character: "CharacterState",
        has_key: bool = False,
        can_pick: bool = False,
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve a locked door (p151).

        Can be opened with key, magic (Knock spell), or picked by thief.
        """
        if has_key:
            return HazardResult(
                success=True,
                hazard_type=HazardType.DOOR_LOCKED,
                action_type=ActionType.NARRATIVE_ACTION,
                description="Unlocked door with key",
                narrative_hints=["key turns smoothly in lock"],
            )

        if can_pick:
            # TODO: Thief pick lock skill check
            return HazardResult(
                success=True,
                hazard_type=HazardType.DOOR_LOCKED,
                action_type=ActionType.PICK_LOCK,
                description="Lock picked successfully",
                turns_spent=1,
                narrative_hints=["tumblers click into place"],
            )

        return HazardResult(
            success=False,
            hazard_type=HazardType.DOOR_LOCKED,
            action_type=ActionType.NARRATIVE_ACTION,
            description="Door is locked",
            narrative_hints=["lock holds fast", "need key or other means"],
        )

    def _resolve_door_listen(
        self,
        character: "CharacterState",
        monsters_present: bool = False,
        monsters_silent: bool = False,
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve listening at a door (p151).

        Takes 1 Turn. Referee rolls in secret.
        Silent monsters (undead) cannot be detected.
        """
        # Listen check - referee rolls secretly
        # For simulation, we'll make the roll here
        roll = self.dice.roll_d6(1, "Listen check")

        # Typically 1-2 on d6 to hear
        target = kwargs.get("listen_target", 2)
        success = roll.total <= target

        if monsters_silent:
            success = False
            description = "No sounds heard (monsters are silent)"
        elif not monsters_present:
            description = "No sounds heard (nothing beyond)"
        elif success:
            description = "Sounds detected beyond the door"
        else:
            description = "No sounds heard"

        return HazardResult(
            success=success and monsters_present,
            hazard_type=HazardType.DOOR_LISTEN,
            action_type=ActionType.LISTEN,
            description=description,
            check_made=True,
            check_type=CheckType.LISTEN,
            check_target=target,
            check_result=roll.total,
            turns_spent=1,
            narrative_hints=[
                "presses ear against door",
                "strains to hear" if not success else "hears something moving",
            ],
        )

    def _resolve_exhaustion(
        self, character: "CharacterState", exhaustion_sources: int = 1, **kwargs: Any
    ) -> HazardResult:
        """
        Resolve exhaustion effects (p151).

        -1 penalty to Attack and Damage per source, max -4.
        """
        penalty = min(exhaustion_sources * EXHAUSTION_PENALTY_PER_SOURCE, EXHAUSTION_MAX_PENALTY)

        return HazardResult(
            success=True,  # Just applies penalties
            hazard_type=HazardType.EXHAUSTION,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"Exhaustion penalty: {penalty}",
            penalties_applied={"attack": penalty, "damage": penalty},
            conditions_applied=["exhausted"],
            narrative_hints=["weary limbs", "struggling to focus"],
        )

    def _resolve_falling(
        self, character: "CharacterState", height_feet: int = 10, **kwargs: Any
    ) -> HazardResult:
        """
        Resolve falling damage (p151).

        1d6 damage per 10' fallen onto hard surface.
        """
        dice_count = max(1, height_feet // 10)
        damage_roll = self.dice.roll(f"{dice_count}d6", f"Falling {height_feet} feet")

        return HazardResult(
            success=False,
            hazard_type=HazardType.FALLING,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"Fell {height_feet} feet, took {damage_roll.total} damage",
            damage_dealt=damage_roll.total,
            damage_type="falling",
            narrative_hints=["crashes to the ground", "painful landing"],
        )

    def _resolve_hunger(
        self,
        character: "CharacterState",
        days_without_food: int = 1,
        is_fairy: bool = False,
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve hunger effects (p153).

        Mortals: Attack and Speed penalties, eventually CON loss.
        Fairies: Wisdom penalties, alignment shift.
        """
        if is_fairy:
            # Fairy hunger affects Wisdom
            wis_penalty = min(days_without_food * 2, 12)
            effects = {"wisdom": -wis_penalty}
            description = f"Fairy hunger: -{wis_penalty} Wisdom"
            hints = ["otherworldly hunger gnaws", "connection to Fairy weakens"]
        else:
            # Mortal hunger
            day_capped = min(days_without_food, 7)
            effects = HUNGER_EFFECTS_MORTAL.get(day_capped, HUNGER_EFFECTS_MORTAL[7])
            description = f"Day {days_without_food} without food"
            hints = ["stomach growls", "weakness sets in"]

            if day_capped >= 7:
                hints.append("body begins to waste away")

        return HazardResult(
            success=True,  # Just applies effects
            hazard_type=HazardType.HUNGER,
            action_type=ActionType.NARRATIVE_ACTION,
            description=description,
            penalties_applied=effects,
            conditions_applied=["hungry"] if days_without_food > 0 else [],
            narrative_hints=hints,
        )

    def _resolve_jumping(
        self,
        character: "CharacterState",
        distance_feet: int = 5,
        is_high_jump: bool = False,
        has_runup: bool = True,
        armor_weight: str = "unarmoured",
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve a jump attempt (p153).

        Long jump: 5' trivial with run-up, 10' with STR check
        High jump: 3' trivial with run-up, 5' with STR check
        Armor modifiers: -1 Medium, -2 Heavy
        """
        trivial_distance = JUMP_TRIVIAL_HIGH if is_high_jump else JUMP_TRIVIAL_LONG
        max_distance = JUMP_CHECK_HIGH if is_high_jump else JUMP_CHECK_LONG

        # Check if trivial
        if distance_feet <= trivial_distance and has_runup:
            return HazardResult(
                success=True,
                hazard_type=HazardType.JUMPING,
                action_type=ActionType.JUMP,
                description=f"Easily jumped {distance_feet} feet",
                narrative_hints=["clears the gap with ease"],
            )

        # Check if impossible
        if distance_feet > max_distance:
            return HazardResult(
                success=False,
                hazard_type=HazardType.JUMPING,
                action_type=ActionType.JUMP,
                description=f"Cannot jump {distance_feet} feet - too far",
                narrative_hints=["impossible distance"],
            )

        # Strength check required
        str_mod = character.get_ability_modifier("STR")
        armor_mod = JUMP_ARMOR_MODIFIERS.get(armor_weight, 0)
        total_mod = str_mod + armor_mod

        roll = self.dice.roll_d20("Jump check")
        check_result = roll.total + total_mod
        target = kwargs.get("difficulty", 10)

        success = check_result >= target

        return HazardResult(
            success=success,
            hazard_type=HazardType.JUMPING,
            action_type=ActionType.JUMP,
            description=f"{'Made' if success else 'Failed'} {distance_feet}' jump",
            check_made=True,
            check_type=CheckType.STRENGTH,
            check_target=target,
            check_result=check_result,
            check_modifier=total_mod,
            narrative_hints=[
                "leaps across" if success else "falls short",
                "lands safely" if success else "tumbles",
            ],
        )

    def _resolve_swimming(
        self,
        character: "CharacterState",
        armor_weight: str = "unarmoured",
        rough_waters: bool = False,
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve swimming (p154).

        Swim at half Speed. STR check to avoid going under in armor.
        Light: no modifier, Medium: -2, Heavy: -4
        Rough waters: -1 or -2 additional
        """
        armor_mod = SWIM_ARMOR_MODIFIERS.get(armor_weight, 0)
        water_mod = -2 if rough_waters else 0
        total_mod = armor_mod + water_mod

        # If unarmored in calm water, no check needed
        if armor_weight == "unarmoured" and not rough_waters:
            return HazardResult(
                success=True,
                hazard_type=HazardType.SWIMMING,
                action_type=ActionType.SWIM,
                description="Swimming at half speed",
                penalties_applied={"speed_multiplier": 0.5},
                narrative_hints=["strokes through the water"],
            )

        # STR check required
        str_mod = character.get_ability_modifier("STR")
        total_mod += str_mod

        roll = self.dice.roll_d20("Swimming check")
        check_result = roll.total + total_mod
        target = kwargs.get("difficulty", 10)

        success = check_result >= target

        if success:
            return HazardResult(
                success=True,
                hazard_type=HazardType.SWIMMING,
                action_type=ActionType.SWIM,
                description="Swimming successfully",
                penalties_applied={"speed_multiplier": 0.5},
                check_made=True,
                check_type=CheckType.STRENGTH,
                check_target=target,
                check_result=check_result,
                check_modifier=total_mod,
                narrative_hints=["struggles but stays afloat"],
            )
        else:
            return HazardResult(
                success=False,
                hazard_type=HazardType.SWIMMING,
                action_type=ActionType.SWIM,
                description="Going under!",
                check_made=True,
                check_type=CheckType.STRENGTH,
                check_target=target,
                check_result=check_result,
                check_modifier=total_mod,
                conditions_applied=["drowning"],
                narrative_hints=["sinks beneath the surface", "armor drags down"],
            )

    def _resolve_suffocation(
        self, character: "CharacterState", rounds_elapsed: int = 0, **kwargs: Any
    ) -> HazardResult:
        """
        Resolve suffocation (p154).

        Can survive 1 Round per CON point before death.
        """
        con_score = character.ability_scores.get("CON", 10)
        max_rounds = con_score
        rounds_remaining = max(0, max_rounds - rounds_elapsed)

        if rounds_remaining <= 0:
            return HazardResult(
                success=False,
                hazard_type=HazardType.SUFFOCATION,
                action_type=ActionType.NARRATIVE_ACTION,
                description="Suffocated to death",
                conditions_applied=["dead"],
                narrative_hints=["lungs burn", "darkness closes in"],
            )

        return HazardResult(
            success=True,
            hazard_type=HazardType.SUFFOCATION,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"{rounds_remaining} rounds of breath remaining",
            conditions_applied=["holding_breath"],
            narrative_hints=[
                f"can hold breath for {rounds_remaining} more rounds",
                "chest tightens" if rounds_remaining < 5 else "",
            ],
        )

    def _resolve_trap(
        self,
        character: "CharacterState",
        trap_type: str = "generic",
        trap_damage: str = "1d6",
        trigger_chance: int = TRAP_TRIGGER_CHANCE,
        trap: Optional[Any] = None,  # Trap object from trap_tables
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve triggering a trap per Campaign Book p102-103.

        Trap resolution procedure:
        1. Check trigger chance (2-in-6 standard, 3-4 for well-maintained)
        2. If triggered, resolve effect based on trap type:
           - Save-based effects: Character makes appropriate save
           - Attack-based effects: Trap makes attack roll(s)
           - Instant effects: Apply damage/condition immediately
        3. Apply conditions and track duration for ongoing effects

        Args:
            character: The character triggering the trap
            trap_type: Type of trap (for legacy compatibility)
            trap_damage: Damage dice (for legacy compatibility)
            trigger_chance: X-in-6 chance of triggering
            trap: Full Trap object from trap_tables (if available)

        Returns:
            HazardResult with detailed trap outcomes
        """
        from src.tables.trap_tables import Trap, TrapEffectType, TRAP_EFFECTS

        # Check if trap triggers
        trigger_roll = self.dice.roll_d6(1, "Trap trigger check")
        triggered = trigger_roll.total <= trigger_chance

        if not triggered:
            # Generate sensory scene for non-triggered trap
            sensory_scene = get_trap_scene(
                trigger_type="proximity",
                effect_type="generic",
                avoided=True,
                dice=self.dice,
            )
            base_hints = [
                "mechanism clicks but doesn't fire",
                "feels pressure plate shift slightly",
            ]
            hints_with_sensory = build_narrative_hints(base_hints, sensory_scene)

            return HazardResult(
                success=True,  # Avoided trap
                hazard_type=HazardType.TRAP,
                action_type=ActionType.NARRATIVE_ACTION,
                description="Trap failed to trigger",
                check_made=True,
                check_result=trigger_roll.total,
                check_target=trigger_chance,
                narrative_hints=hints_with_sensory,
            )

        # Get character ID for applying effects
        character_id = getattr(character, 'character_id', None)

        # If no trap object provided, use legacy behavior
        if trap is None:
            damage_roll = self.dice.roll(trap_damage, f"{trap_type} trap damage")
            apply_damage = []
            if damage_roll.total > 0 and character_id:
                apply_damage.append((character_id, damage_roll.total))

            # Generate sensory scene for legacy trap
            sensory_scene = get_trap_scene(
                trigger_type="touch",
                effect_type=trap_type,
                avoided=False,
                dice=self.dice,
            )
            base_hints = ["trap springs", f"{trap_type} strikes"]
            hints_with_sensory = build_narrative_hints(base_hints, sensory_scene)

            return HazardResult(
                success=False,
                hazard_type=HazardType.TRAP,
                action_type=ActionType.NARRATIVE_ACTION,
                description=f"Trap triggered! Took {damage_roll.total} damage",
                damage_dealt=damage_roll.total,
                damage_type=trap_type,
                apply_damage=apply_damage,
                check_made=True,
                check_result=trigger_roll.total,
                check_target=trigger_chance,
                narrative_hints=hints_with_sensory,
            )

        # Use full trap resolution with proper mechanics
        effect = trap.effect
        damage_dealt = 0
        conditions: list[str] = []
        save_made = False
        save_result = 0
        attack_hits: list[dict] = []
        narrative_hints = [trap.effect.description]

        # Handle different effect types
        if effect.save_type:
            # Effect requires a save
            save_result = self._roll_save(character, effect.save_type)
            save_target = kwargs.get("save_dc", 15)
            save_made = save_result >= save_target

            if save_made:
                if effect.save_negates:
                    # Save completely negates the effect
                    narrative_hints.append("barely avoided the effect!")
                elif effect.damage_on_save:
                    # Reduced damage on save
                    damage_roll = self.dice.roll(effect.damage_on_save, "trap damage (saved)")
                    damage_dealt = damage_roll.total
                    narrative_hints.append("partially avoided the worst")
            else:
                # Failed save
                if effect.damage:
                    damage_roll = self.dice.roll(effect.damage, "trap damage")
                    damage_dealt = damage_roll.total
                if effect.condition_applied:
                    conditions.append(effect.condition_applied)
                    narrative_hints.append(f"afflicted with {effect.condition_applied}")

        elif effect.attack_bonus is not None:
            # Effect makes attack rolls (arrow volley, spear wall, etc.)
            num_attacks = 1
            if effect.num_attacks:
                num_attacks = self.dice.roll(effect.num_attacks, "number of attacks").total

            for i in range(num_attacks):
                attack_roll = self.dice.roll_d20(f"trap attack {i + 1}")
                attack_total = attack_roll.total + effect.attack_bonus
                target_ac = character.armor_class if hasattr(character, 'armor_class') else 10

                if attack_total >= target_ac:
                    # Hit
                    damage_roll = self.dice.roll(effect.damage or "1d6", f"trap damage {i + 1}")
                    damage_dealt += damage_roll.total
                    attack_hits.append({
                        "attack": i + 1,
                        "roll": attack_total,
                        "damage": damage_roll.total,
                        "hit": True,
                    })
                else:
                    attack_hits.append({
                        "attack": i + 1,
                        "roll": attack_total,
                        "hit": False,
                    })

            if attack_hits:
                hits = sum(1 for a in attack_hits if a["hit"])
                narrative_hints.append(f"{hits} of {num_attacks} attacks hit")

        else:
            # Instant effect or special mechanic
            if effect.damage:
                damage_roll = self.dice.roll(effect.damage, "trap damage")
                damage_dealt = damage_roll.total
            if effect.condition_applied:
                conditions.append(effect.condition_applied)

        # Build description
        desc_parts = [f"{trap.name} triggered!"]
        if damage_dealt > 0:
            desc_parts.append(f"Took {damage_dealt} damage")
        if conditions:
            desc_parts.append(f"Conditions: {', '.join(conditions)}")

        # Include duration info if applicable
        if effect.duration_rounds:
            narrative_hints.append(f"effect lasts {effect.duration_rounds} rounds")
        elif effect.duration_turns:
            narrative_hints.append(f"effect lasts {effect.duration_turns} turns")

        # Include escape info if applicable
        if effect.escape_check and conditions:
            narrative_hints.append(
                f"Can attempt {effect.escape_check} check DC {effect.escape_dc} to escape"
            )

        # Build apply lists for game state updates
        apply_damage: list[tuple[str, int]] = []
        apply_conditions: list[tuple[str, str]] = []

        if character_id:
            if damage_dealt > 0:
                apply_damage.append((character_id, damage_dealt))
            for condition in conditions:
                apply_conditions.append((character_id, condition))

        # Generate sensory scene for triggered trap
        # Determine trigger type from trap mechanics
        trigger_type = "pressure_plate"  # default
        if trap.trigger:
            trigger_str = str(trap.trigger).lower()
            if "tripwire" in trigger_str or "wire" in trigger_str:
                trigger_type = "tripwire"
            elif "touch" in trigger_str:
                trigger_type = "touch"
            elif "proximity" in trigger_str or "rune" in trigger_str:
                trigger_type = "proximity"

        sensory_scene = get_trap_scene(
            trigger_type=trigger_type,
            effect_type=effect.effect_type.value,
            avoided=save_made and effect.save_negates,
            dice=self.dice,
        )
        narrative_hints = build_narrative_hints(narrative_hints, sensory_scene)

        return HazardResult(
            success=False,
            hazard_type=HazardType.TRAP,
            action_type=ActionType.NARRATIVE_ACTION,
            description=" ".join(desc_parts),
            damage_dealt=damage_dealt,
            damage_type=trap.effect.effect_type.value,
            conditions_applied=conditions,
            apply_damage=apply_damage,
            apply_conditions=apply_conditions,
            check_made=True,
            check_result=trigger_roll.total,
            check_target=trigger_chance,
            narrative_hints=narrative_hints,
        )

    def _roll_save(self, character: "CharacterState", save_type: str) -> int:
        """
        Roll a saving throw for a character.

        Args:
            character: The character making the save
            save_type: Type of save (doom, blast, ray, etc.)

        Returns:
            Total save result (d20 + modifier)
        """
        # Map save types to ability modifiers
        save_abilities = {
            "doom": "CON",
            "blast": "DEX",
            "ray": "DEX",
            "spell": "WIS",
            "wand": "WIS",
        }

        ability = save_abilities.get(save_type.lower(), "CON")
        modifier = character.get_ability_modifier(ability)
        roll = self.dice.roll_d20(f"Save vs {save_type}")
        return roll.total + modifier

    def resolve_foraging(
        self,
        character: "CharacterState",
        method: str = "foraging",
        season: str = "normal",
        full_day: bool = False,
        foraging_bonus: float = 1.0,
        active_unseason: Optional[str] = None,
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve finding food in the wild per Campaign Book (p118-119, p152).

        Procedure for foraging:
        1. Make a Survival check
        2. On success, roll d6: 1-3 = fungi, 4-6 = plants
        3. Roll d20 on appropriate table for specific species
        4. Roll 1d6 for rations found

        Fishing: 2d6 rations on success (uses generic fish, not foraging tables)
        Hunting: Triggers combat with game animals

        Colliggwyld Unseason: During Colliggwyld, fungi yields are doubled.
        This is handled by passing foraging_bonus=2.0 or active_unseason="colliggwyld".

        Args:
            character: The character foraging
            method: "foraging", "fishing", or "hunting"
            season: "normal", "winter", or "autumn"
            full_day: Whether spending a full day foraging (+2 bonus)
            foraging_bonus: Multiplier for fungi yields (default 1.0, 2.0 for Colliggwyld)
            active_unseason: Current unseason (used to auto-set foraging_bonus)

        Returns:
            HazardResult with foraged_items list containing ForageableItem dicts
            with effect metadata for later consumption.
        """
        # Auto-set foraging bonus for Colliggwyld if not explicitly provided
        if active_unseason == "colliggwyld" and foraging_bonus == 1.0:
            foraging_bonus = 2.0

        # Survival check
        # TODO: Get best Survival skill in party
        roll = self.dice.roll_d6(1, "Survival check")
        bonus = 2 if full_day else 0
        target = kwargs.get("difficulty", 4)  # 4+ on d6

        success = roll.total + bonus >= target

        if not success:
            return HazardResult(
                success=False,
                hazard_type=HazardType.HUNGER,  # Related to food
                action_type=ActionType.FORAGE if method != "hunting" else ActionType.HUNT,
                description=f"Failed to find food while {method}",
                check_made=True,
                check_result=roll.total + bonus,
                check_target=target,
                narrative_hints=["slim pickings", "nothing edible found"],
            )

        # Handle hunting using Campaign Book tables (p120-121)
        if method == "hunting":
            terrain = kwargs.pop("terrain", "forest")
            return self._resolve_hunting(
                character=character,
                survival_roll=roll.total,
                survival_bonus=bonus,
                survival_target=target,
                terrain=terrain,
                **kwargs,
            )

        # Handle fishing using Campaign Book tables (p116-117)
        if method == "fishing":
            return self._resolve_fishing(
                character=character,
                survival_roll=roll.total,
                survival_bonus=bonus,
                survival_target=target,
                has_pipe_music=kwargs.get("has_pipe_music", False),
                **kwargs,
            )

        # FORAGING: Use the Campaign Book tables (p118-119)
        # Step 1: Roll d6 for fungi (1-3) or plants (4-6)
        forage_type = roll_forage_type()

        # Step 2: Roll d20 on the appropriate table
        foraged_item = roll_foraged_item(forage_type)

        # Step 3: Roll 1d6 for quantity (rations)
        base_quantity = roll_forage_quantity()

        # Apply Colliggwyld bonus to fungi yields
        quantity = base_quantity
        colliggwyld_bonus_applied = False
        if is_fungi(foraged_item) and foraging_bonus > 1.0:
            quantity = int(base_quantity * foraging_bonus)
            colliggwyld_bonus_applied = True

        # Build item data with effect metadata for inventory
        foraged_item_data = foraged_item.to_dict()
        foraged_item_data["quantity"] = quantity
        foraged_item_data["colliggwyld_bonus_applied"] = colliggwyld_bonus_applied

        # Process any hex-specific foraging special yields (legacy support)
        foraging_special = kwargs.get("foraging_special", [])
        additional_items: list[dict[str, Any]] = []
        for special in foraging_special:
            special_result = self._parse_and_roll_special_yield(special, foraging_bonus)
            if special_result:
                additional_items.append(special_result)

        # Build description
        type_str = "fungi" if forage_type == ForageType.FUNGI else "plants"
        bonus_note = " (doubled by Colliggwyld!)" if colliggwyld_bonus_applied else ""
        base_desc = f"Found {quantity} rations of {foraged_item.name} ({type_str}){bonus_note}"

        if additional_items:
            additional_desc = ", ".join(
                f"{item['quantity']} {item['item']}"
                for item in additional_items
            )
            base_desc += f", plus {additional_desc}"

        # Build narrative hints using item descriptions
        hints = [
            foraged_item.description,
            f"smells {foraged_item.smell.lower()}" if foraged_item.smell else "",
        ]
        if colliggwyld_bonus_applied:
            hints.append("the Colliggwyld's blessing doubles the fungi harvest")

        # Filter empty hints
        hints = [h for h in hints if h]

        # Add sensory details for immersive narration
        terrain_context = kwargs.get("terrain", "forest")
        try:
            sensory_terrain = TerrainContext(terrain_context)
        except ValueError:
            sensory_terrain = TerrainContext.FOREST

        sensory_context = SensoryContext(
            terrain=sensory_terrain,
            season=season,
            unseason_active=active_unseason,
        )
        sensory_scene = get_foraging_scene(
            context=sensory_context,
            success=True,
            is_fungi=(forage_type == ForageType.FUNGI),
            dice=self.dice,
        )
        hints = build_narrative_hints(hints, sensory_scene)

        # Compile all foraged items
        all_foraged = [foraged_item_data]
        all_foraged.extend(additional_items)

        return HazardResult(
            success=True,
            hazard_type=HazardType.HUNGER,
            action_type=ActionType.FORAGE,
            description=base_desc,
            check_made=True,
            check_result=roll.total + bonus,
            check_target=target,
            rations_found=quantity,
            foraged_items=all_foraged,
            narrative_hints=hints,
        )

    # Common fungi/mushroom keywords for Colliggwyld bonus detection
    FUNGI_KEYWORDS = frozenset([
        "mushroom", "mushrooms", "fungus", "fungi", "toadstool", "toadstools",
        "morel", "morels", "puffball", "puffballs", "bracket", "truffle", "truffles",
        "cap", "caps", "shroom", "shrooms", "spore", "spores",
        # Specific Dolmenwood fungi
        "sage toe", "brainconk", "pook morel", "redslob", "mould",
    ])

    def _is_fungi_item(self, item_name: str) -> bool:
        """Check if an item is a fungi/mushroom type (for Colliggwyld bonus)."""
        name_lower = item_name.lower()
        return any(keyword in name_lower for keyword in self.FUNGI_KEYWORDS)

    def _parse_and_roll_special_yield(
        self,
        special_str: str,
        foraging_bonus: float = 1.0,
    ) -> Optional[dict[str, Any]]:
        """
        Parse a special foraging yield string and roll for quantity.

        Args:
            special_str: Format like "Sage Toe (1d3 portions)" or "Moonwort (2d4)"
            foraging_bonus: Multiplier for fungi yields (2.0 during Colliggwyld)

        Returns:
            Dict with item name, rolled quantity, and whether bonus was applied
        """
        import re

        # Match patterns like "Item Name (XdY portions)" or "Item Name (XdY)"
        match = re.match(r"(.+?)\s*\((\d+d\d+)(?:\s+\w+)?\)", special_str)
        if not match:
            # Simple format without dice, like "Rare Herb"
            item_name = special_str.strip()
            quantity = 1
            # Apply bonus if it's a fungi item
            bonus_applied = False
            if self._is_fungi_item(item_name) and foraging_bonus > 1.0:
                quantity = int(quantity * foraging_bonus)
                bonus_applied = True
            return {"item": item_name, "quantity": quantity, "bonus_applied": bonus_applied}

        item_name = match.group(1).strip()
        dice_expr = match.group(2)

        try:
            quantity_roll = self.dice.roll(dice_expr, f"special yield: {item_name}")
            quantity = quantity_roll.total

            # Apply Colliggwyld bonus to fungi items
            bonus_applied = False
            if self._is_fungi_item(item_name) and foraging_bonus > 1.0:
                quantity = int(quantity * foraging_bonus)
                bonus_applied = True

            return {"item": item_name, "quantity": quantity, "bonus_applied": bonus_applied}
        except Exception:
            return {"item": item_name, "quantity": 1, "bonus_applied": False}

    def _resolve_fishing(
        self,
        character: "CharacterState",
        survival_roll: int,
        survival_bonus: int,
        survival_target: int,
        has_pipe_music: bool = False,
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve fishing using Campaign Book tables (p116-117).

        Procedure:
        1. Roll 1d20 to determine fish species
        2. Check for landing requirements (DEX/STR checks for some fish)
        3. Check for catch events (danger, treasure, monster attraction)
        4. Roll for rations yield (varies by fish type)

        Args:
            character: The character fishing
            survival_roll: Result of survival check
            survival_bonus: Bonus applied to survival check
            survival_target: Target number for survival check
            has_pipe_music: Whether party has madcap pipe music (for Wraithfish)

        Returns:
            HazardResult with fish caught and any events
        """
        # Step 1: Roll d20 for fish species
        fish = roll_fish()
        fish_data = fish.to_dict()

        catch_events: list[dict[str, Any]] = []
        narrative_hints: list[str] = [fish.description]

        # Step 2: Check if this fish requires special landing
        landing_required = None
        if fish_requires_landing_check(fish):
            landing_required = fish.landing.to_dict()
            catch_events.append({
                "type": "landing_required",
                "check_type": fish.landing.landing_type.value,
                "num_characters": fish.landing.num_characters,
                "description": fish.landing.check_description,
            })
            narrative_hints.append(fish.landing.check_description)

        # Step 3: Check if this triggers combat
        combat_triggered = fish_triggers_combat(fish)
        if combat_triggered:
            catch_events.append({
                "type": "combat",
                "monster_id": fish.monster_id,
                "description": "This catch triggers a combat encounter!",
                "rations_per_hp": fish.rations_per_hp,
            })
            narrative_hints.append("A massive fish! This will be a fight!")

            return HazardResult(
                success=True,
                hazard_type=HazardType.HUNGER,
                action_type=ActionType.FISH,
                description=f"Hooked a {fish.name}! Combat required!",
                check_made=True,
                check_result=survival_roll + survival_bonus,
                check_target=survival_target,
                fish_caught=fish_data,
                catch_events=catch_events,
                combat_triggered=True,
                narrative_hints=narrative_hints,
            )

        # Step 4: Check for treasure in fish belly
        treasure = check_treasure_in_fish(fish)
        if treasure:
            catch_events.append({
                "type": "treasure",
                **treasure,
            })
            narrative_hints.append(treasure["description"])

        # Step 5: Check if fish attracts monsters (Screaming jenny)
        monster_attracted = check_monster_attracted(fish)
        if monster_attracted:
            catch_events.append({
                "type": "monster_attracted",
                "description": f"The {fish.name}'s shriek echoes through the area!",
            })
            narrative_hints.append("The shriek may have attracted something...")

        # Step 6: Check for fairy fish blessing
        blessing_offered = fish_is_fairy(fish)
        if blessing_offered:
            catch_events.append({
                "type": "blessing_offered",
                "bonus": fish.catch_effect.blessing_bonus,
                "description": fish.catch_effect.description,
            })
            narrative_hints.append(
                f"The {fish.name} speaks! It offers a blessing in exchange for its freedom."
            )

        # Step 7: Check for first-timer dangers (Gurney, Puffer)
        # These fish deal damage to inexperienced anglers who fail their save
        damage_dealt = 0
        conditions_applied: list[str] = []

        if fish.catch_effect.requires_experience:
            # Roll save (using the save type from the fish)
            save_type = fish.catch_effect.save_type or "doom"
            save_roll = self.dice.roll_d20(f"Save vs {save_type} ({fish.name})")

            # Get appropriate ability modifier for save
            save_ability = "CON" if save_type == "doom" else "DEX" if save_type == "blast" else "WIS"
            save_mod = character.get_ability_modifier(save_ability)
            save_total = save_roll.total + save_mod

            # Target is typically 15 for saves vs effects
            save_target = kwargs.get("save_difficulty", 15)
            save_success = save_total >= save_target

            if not save_success and fish.catch_effect.damage:
                # Roll the damage
                damage_roll = self.dice.roll(fish.catch_effect.damage, f"{fish.name} damage")
                damage_dealt = damage_roll.total
                catch_events.append({
                    "type": "first_timer_danger",
                    "save_type": save_type,
                    "save_roll": save_total,
                    "save_target": save_target,
                    "save_success": False,
                    "damage_dealt": damage_dealt,
                    "description": f"Save failed! {fish.catch_effect.description}",
                })
                narrative_hints.append(f"The {fish.name} caught you off guard!")
            else:
                catch_events.append({
                    "type": "first_timer_danger",
                    "save_type": save_type,
                    "save_roll": save_total,
                    "save_target": save_target,
                    "save_success": True,
                    "damage_dealt": 0,
                    "description": f"Avoided the danger! {fish.catch_effect.description}",
                })
                if not save_success:
                    narrative_hints.append(f"Careful handling avoided the {fish.name}'s danger")

        # Step 8: Roll for rations
        rations = roll_fish_rations(fish, has_pipe_music=has_pipe_music)

        # Build description
        if rations > 0:
            desc = f"Caught {fish.name}! ({rations} rations)"
        else:
            desc = f"Hooked a {fish.name}!"

        if fish.flavor_text:
            narrative_hints.append(fish.flavor_text)

        # Special condition notes
        if fish.special_condition and not has_pipe_music:
            narrative_hints.append(fish.special_condition)

        # Add sensory details for immersive narration
        fish_size = "large" if fish.rations_per_hp and fish.rations_per_hp >= 4 else (
            "small" if rations <= 2 else "medium"
        )
        is_magical = blessing_offered or fish_is_fairy(fish)

        sensory_context = SensoryContext(
            terrain=TerrainContext.RIVER,  # Default to river for fishing
        )
        sensory_scene = get_fishing_scene(
            context=sensory_context,
            fish_size=fish_size,
            is_magical=is_magical,
            dice=self.dice,
        )
        narrative_hints = build_narrative_hints(narrative_hints, sensory_scene)

        return HazardResult(
            success=True,
            hazard_type=HazardType.HUNGER,
            action_type=ActionType.FISH,
            description=desc,
            damage_dealt=damage_dealt,
            damage_type="fishing_hazard" if damage_dealt > 0 else "",
            check_made=True,
            check_result=survival_roll + survival_bonus,
            check_target=survival_target,
            rations_found=rations,
            fish_caught=fish_data,
            landing_required=landing_required,
            catch_events=catch_events,
            treasure_found=treasure,
            monster_attracted=monster_attracted,
            blessing_offered=blessing_offered,
            conditions_applied=conditions_applied,
            narrative_hints=narrative_hints,
        )

    def _resolve_hunting(
        self,
        character: "CharacterState",
        survival_roll: int,
        survival_bonus: int,
        survival_target: int,
        terrain: str = "forest",
        **kwargs: Any,
    ) -> HazardResult:
        """
        Resolve hunting using Campaign Book tables (p120-121).

        Hunting Procedure:
        1. Survival check already passed (done by caller)
        2. Roll d20 on terrain-specific Game Animals table
        3. Roll number appearing dice
        4. Set up combat encounter with party having surprise
        5. Starting distance is 1d4 × 30'
        6. Yield calculated after combat: 1/2/4 rations per HP based on size

        Args:
            character: The character hunting
            survival_roll: The survival check roll
            survival_bonus: Bonus applied to survival check
            survival_target: Target number for survival check
            terrain: Terrain type for animal selection

        Returns:
            HazardResult with game_animal data and encounter setup
        """
        narrative_hints: list[str] = []

        # Step 1: Determine terrain type for hunting table
        hunting_terrain = get_hunting_terrain(terrain)

        # Step 2: Roll on the terrain-specific game animal table
        animal = roll_game_animal(hunting_terrain)
        narrative_hints.append(f"Tracked {animal.name.lower()} in the {terrain}")

        # Step 3: Roll number appearing
        num_appearing = roll_number_appearing(animal)
        if num_appearing == 1:
            narrative_hints.append(f"A lone {animal.name.lower()}")
        else:
            narrative_hints.append(f"A group of {num_appearing} {animal.name.lower()}s")

        # Step 4: Roll encounter distance (1d4 × 30')
        distance = roll_encounter_distance()
        narrative_hints.append(f"Spotted {distance}' away")

        # Step 5: Calculate potential rations if all killed
        # This uses average HP from monster stats - actual yield depends on combat
        # For now we estimate based on hit dice (rough HP estimate)
        hp_per_animal = self._estimate_animal_hp(animal.monster_id)
        total_hp = hp_per_animal * num_appearing
        potential_rations = calculate_rations_yield(animal, total_hp)

        # Build animal data for result
        animal_data = animal.to_dict()
        animal_data["terrain_found"] = terrain
        animal_data["hunting_terrain"] = hunting_terrain.value

        # Build description
        if num_appearing == 1:
            desc = f"Stalked a {animal.name}! Combat encounter at {distance}'"
        else:
            desc = f"Stalked {num_appearing} {animal.name}s! Combat encounter at {distance}'"

        if animal.flavor_text:
            narrative_hints.append(animal.flavor_text)

        # Add sensory details for immersive narration
        try:
            sensory_terrain = TerrainContext(terrain)
        except ValueError:
            sensory_terrain = TerrainContext.FOREST

        sensory_context = SensoryContext(terrain=sensory_terrain)
        sensory_scene = get_hunting_scene(
            context=sensory_context,
            distance=distance,
            dice=self.dice,
        )
        narrative_hints = build_narrative_hints(narrative_hints, sensory_scene)

        return HazardResult(
            success=True,
            hazard_type=HazardType.HUNGER,
            action_type=ActionType.HUNT,
            description=desc,
            check_made=True,
            check_result=survival_roll + survival_bonus,
            check_target=survival_target,
            game_animal=animal_data,
            number_appearing=num_appearing,
            encounter_distance=distance,
            party_has_surprise=True,  # Party always has surprise when hunting
            potential_rations=potential_rations,
            combat_triggered=True,  # Hunting always triggers combat
            narrative_hints=narrative_hints,
        )

    def _estimate_animal_hp(self, monster_id: str) -> int:
        """
        Estimate average HP for a game animal.

        Uses known values from Monster Book - actual HP may vary in combat.
        """
        # Average HP values from Monster Book entries
        hp_estimates = {
            "boar": 13,
            "false_unicorn": 9,
            "gelatinous_ape": 9,
            "gobble": 2,
            "headhog": 2,
            "honey_badger": 4,
            "lurkey": 4,
            "merriman": 4,
            "moss_mole": 2,
            "puggle": 4,
            "red_deer": 13,
            "swamp_sloth": 4,
            "trotteling": 4,
            "woad": 4,
            "yegril": 18,
        }
        return hp_estimates.get(monster_id, 4)  # Default to 4 HP
