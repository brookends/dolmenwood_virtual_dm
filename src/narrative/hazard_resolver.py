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

from src.narrative.intent_parser import (
    ActionType, ResolutionType, CheckType, ParsedIntent
)


class HazardType(str, Enum):
    """Types of hazards per Dolmenwood rules."""
    # Physical challenges
    CLIMBING = "climbing"           # p150
    COLD = "cold"                   # p150
    DARKNESS = "darkness"           # p150
    DIVING = "diving"               # Swimming underwater with breath tracking
    DOOR_STUCK = "door_stuck"       # p151
    DOOR_LOCKED = "door_locked"     # p151
    DOOR_LISTEN = "door_listen"     # p151
    EXHAUSTION = "exhaustion"       # p151
    FALLING = "falling"             # p151
    HUNGER = "hunger"               # p153
    THIRST = "thirst"               # p153
    JUMPING = "jumping"             # p153
    SWIMMING = "swimming"           # p154
    SUFFOCATION = "suffocation"     # p154
    TRAP = "trap"                   # p155


class DarknessLevel(str, Enum):
    """Light levels affecting visibility."""
    BRIGHT = "bright"               # Normal vision
    LOW_LIGHT = "low_light"         # -2 Attack, half Speed
    PITCH_DARK = "pitch_dark"       # -4 Attack/AC/Saves, Speed 10


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

    # For LLM narration
    narrative_hints: list[str] = field(default_factory=list)

    # Nested results (e.g., for traps that deal damage)
    nested_results: list["HazardResult"] = field(default_factory=list)

    # Diving-specific
    rounds_underwater: int = 0
    rounds_remaining: int = 0


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
JUMP_TRIVIAL_LONG = 5   # feet with 20' run-up
JUMP_CHECK_LONG = 10    # feet with Strength Check
JUMP_TRIVIAL_HIGH = 3   # feet with 20' run-up
JUMP_CHECK_HIGH = 5     # feet with Strength Check

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
ROUNDS_PER_TURN = 6     # 1 turn = 60 seconds = 6 rounds

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
        self,
        hazard_type: HazardType,
        character: "CharacterState",
        **kwargs: Any
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
            description=f"Unknown hazard type: {hazard_type}"
        )

    def _resolve_climbing(
        self,
        character: "CharacterState",
        height_feet: int = 10,
        is_trivial: bool = False,
        **kwargs: Any
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
                narrative_hints=["character climbs easily"]
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
                narrative_hints=["character finds handholds", "steady progress upward"]
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
                nested_results=[fall_result]
            )

    def _resolve_cold(
        self,
        character: "CharacterState",
        has_protection: bool = False,
        **kwargs: Any
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
                narrative_hints=["winter cloak keeps character warm"]
            )

        damage_roll = self.dice.roll(COLD_DAMAGE_PER_DAY, "Cold damage")

        return HazardResult(
            success=False,
            hazard_type=HazardType.COLD,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"Suffered {damage_roll.total} cold damage",
            damage_dealt=damage_roll.total,
            damage_type="cold",
            narrative_hints=["fingers go numb", "shivering uncontrollably"]
        )

    def _resolve_darkness(
        self,
        character: "CharacterState",
        darkness_level: DarknessLevel = DarknessLevel.PITCH_DARK,
        **kwargs: Any
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
            narrative_hints=[
                "can barely see",
                "stumbling in darkness"
            ] if darkness_level != DarknessLevel.BRIGHT else []
        )

    def _resolve_diving(
        self,
        character: "CharacterState",
        diving_state: Optional[DivingState] = None,
        rounds_to_spend: int = 1,
        armor_weight: str = "unarmoured",
        action: str = "dive",  # "dive", "swim", "surface", "action"
        **kwargs: Any
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
                narrative_hints=["breaks the surface", "gasps for air", "breathes deeply"]
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
                    narrative_hints=["lungs burn", "darkness closes in", "cannot hold breath any longer"]
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
        self,
        character: "CharacterState",
        has_tools: bool = False,
        **kwargs: Any
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
                "loud noise echoes" if not success else ""
            ]
        )

        if not success:
            result.narrative_hints.append("any creatures beyond are now alert")

        return result

    def _resolve_door_locked(
        self,
        character: "CharacterState",
        has_key: bool = False,
        can_pick: bool = False,
        **kwargs: Any
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
                narrative_hints=["key turns smoothly in lock"]
            )

        if can_pick:
            # TODO: Thief pick lock skill check
            return HazardResult(
                success=True,
                hazard_type=HazardType.DOOR_LOCKED,
                action_type=ActionType.PICK_LOCK,
                description="Lock picked successfully",
                turns_spent=1,
                narrative_hints=["tumblers click into place"]
            )

        return HazardResult(
            success=False,
            hazard_type=HazardType.DOOR_LOCKED,
            action_type=ActionType.NARRATIVE_ACTION,
            description="Door is locked",
            narrative_hints=["lock holds fast", "need key or other means"]
        )

    def _resolve_door_listen(
        self,
        character: "CharacterState",
        monsters_present: bool = False,
        monsters_silent: bool = False,
        **kwargs: Any
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
                "strains to hear" if not success else "hears something moving"
            ]
        )

    def _resolve_exhaustion(
        self,
        character: "CharacterState",
        exhaustion_sources: int = 1,
        **kwargs: Any
    ) -> HazardResult:
        """
        Resolve exhaustion effects (p151).

        -1 penalty to Attack and Damage per source, max -4.
        """
        penalty = min(
            exhaustion_sources * EXHAUSTION_PENALTY_PER_SOURCE,
            EXHAUSTION_MAX_PENALTY
        )

        return HazardResult(
            success=True,  # Just applies penalties
            hazard_type=HazardType.EXHAUSTION,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"Exhaustion penalty: {penalty}",
            penalties_applied={"attack": penalty, "damage": penalty},
            conditions_applied=["exhausted"],
            narrative_hints=["weary limbs", "struggling to focus"]
        )

    def _resolve_falling(
        self,
        character: "CharacterState",
        height_feet: int = 10,
        **kwargs: Any
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
            narrative_hints=[
                "crashes to the ground",
                "painful landing"
            ]
        )

    def _resolve_hunger(
        self,
        character: "CharacterState",
        days_without_food: int = 1,
        is_fairy: bool = False,
        **kwargs: Any
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
            narrative_hints=hints
        )

    def _resolve_jumping(
        self,
        character: "CharacterState",
        distance_feet: int = 5,
        is_high_jump: bool = False,
        has_runup: bool = True,
        armor_weight: str = "unarmoured",
        **kwargs: Any
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
                narrative_hints=["clears the gap with ease"]
            )

        # Check if impossible
        if distance_feet > max_distance:
            return HazardResult(
                success=False,
                hazard_type=HazardType.JUMPING,
                action_type=ActionType.JUMP,
                description=f"Cannot jump {distance_feet} feet - too far",
                narrative_hints=["impossible distance"]
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
                "lands safely" if success else "tumbles"
            ]
        )

    def _resolve_swimming(
        self,
        character: "CharacterState",
        armor_weight: str = "unarmoured",
        rough_waters: bool = False,
        **kwargs: Any
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
                narrative_hints=["strokes through the water"]
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
                narrative_hints=["struggles but stays afloat"]
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
                narrative_hints=["sinks beneath the surface", "armor drags down"]
            )

    def _resolve_suffocation(
        self,
        character: "CharacterState",
        rounds_elapsed: int = 0,
        **kwargs: Any
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
                narrative_hints=["lungs burn", "darkness closes in"]
            )

        return HazardResult(
            success=True,
            hazard_type=HazardType.SUFFOCATION,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"{rounds_remaining} rounds of breath remaining",
            conditions_applied=["holding_breath"],
            narrative_hints=[
                f"can hold breath for {rounds_remaining} more rounds",
                "chest tightens" if rounds_remaining < 5 else ""
            ]
        )

    def _resolve_trap(
        self,
        character: "CharacterState",
        trap_type: str = "generic",
        trap_damage: str = "1d6",
        trigger_chance: int = TRAP_TRIGGER_CHANCE,
        **kwargs: Any
    ) -> HazardResult:
        """
        Resolve triggering a trap (p155).

        2-in-6 chance of trap springing (or higher for well-maintained).
        """
        # Check if trap triggers
        trigger_roll = self.dice.roll_d6(1, "Trap trigger check")
        triggered = trigger_roll.total <= trigger_chance

        if not triggered:
            return HazardResult(
                success=True,  # Avoided trap
                hazard_type=HazardType.TRAP,
                action_type=ActionType.NARRATIVE_ACTION,
                description="Trap failed to trigger",
                check_made=True,
                check_result=trigger_roll.total,
                check_target=trigger_chance,
                narrative_hints=[
                    "mechanism clicks but doesn't fire",
                    "feels pressure plate shift slightly"
                ]
            )

        # Trap triggered - apply effects
        damage_roll = self.dice.roll(trap_damage, f"{trap_type} trap damage")

        return HazardResult(
            success=False,
            hazard_type=HazardType.TRAP,
            action_type=ActionType.NARRATIVE_ACTION,
            description=f"Trap triggered! Took {damage_roll.total} damage",
            damage_dealt=damage_roll.total,
            damage_type=trap_type,
            check_made=True,
            check_result=trigger_roll.total,
            check_target=trigger_chance,
            narrative_hints=[
                "trap springs",
                f"{trap_type} strikes"
            ]
        )

    def resolve_foraging(
        self,
        character: "CharacterState",
        method: str = "foraging",
        season: str = "normal",
        full_day: bool = False,
        **kwargs: Any
    ) -> HazardResult:
        """
        Resolve finding food in the wild (p152).

        Fishing: 2d6 rations on success
        Foraging: 1d6 (1d4 winter, 1d8 autumn)
        Hunting: Triggers combat with game animals
        """
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
                narrative_hints=["slim pickings", "nothing edible found"]
            )

        # Determine yield
        if method == "fishing":
            yield_dice = FORAGING_YIELDS["fishing"]
        elif method == "foraging":
            if season == "winter":
                yield_dice = FORAGING_YIELDS["foraging_winter"]
            elif season == "autumn":
                yield_dice = FORAGING_YIELDS["foraging_autumn"]
            else:
                yield_dice = FORAGING_YIELDS["foraging_normal"]
        else:
            # Hunting requires combat
            return HazardResult(
                success=True,
                hazard_type=HazardType.HUNGER,
                action_type=ActionType.HUNT,
                description="Found game animals - combat required",
                check_made=True,
                check_result=roll.total + bonus,
                check_target=target,
                narrative_hints=["tracks lead to quarry", "game spotted ahead"]
            )

        yield_roll = self.dice.roll(yield_dice, f"{method} yield")

        return HazardResult(
            success=True,
            hazard_type=HazardType.HUNGER,
            action_type=ActionType.FORAGE if method != "fishing" else ActionType.FISH,
            description=f"Found {yield_roll.total} rations while {method}",
            check_made=True,
            check_result=roll.total + bonus,
            check_target=target,
            narrative_hints=[
                f"gathered {yield_roll.total} fresh rations",
                "basket fills with edibles" if method == "foraging" else "fish on the line"
            ]
        )
