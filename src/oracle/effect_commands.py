"""
Effect Command System for Dolmenwood Virtual DM.

Provides a structured way to translate spell interpretations
into discrete game state changes that can be validated and executed.

This bridges the gap between:
- Mythic GME oracle results ("Waste + Energy")
- LLM/Human interpretation ("Lord Malbrook loses 2 CON")
- Actual game state changes (controller.modify_stat())

The key principle: Interpretations produce EffectCommands,
which are validated, then executed against the game state.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from src.game_state.global_controller import GlobalController
    from src.data_models import DiceRoller


# =============================================================================
# EFFECT TYPES
# =============================================================================


class EffectType(str, Enum):
    """
    Valid effect types the system can execute.

    Each type maps to a specific game state modification.
    New effect types require corresponding handler methods.
    """

    # Condition management
    ADD_CONDITION = "add_condition"
    REMOVE_CONDITION = "remove_condition"
    TRANSFER_CONDITION = "transfer_condition"

    # Stat modification
    MODIFY_STAT = "modify_stat"  # Permanent change (CON, STR, etc.)
    APPLY_MODIFIER = "apply_modifier"  # Temporary buff/debuff
    REMOVE_MODIFIER = "remove_modifier"

    # Hit points / resources
    DAMAGE = "damage"
    HEAL = "heal"

    # Spell resources
    RESTORE_SPELL_SLOT = "restore_slot"
    EXPEND_SPELL_SLOT = "expend_slot"

    # Inventory
    ADD_ITEM = "add_item"
    REMOVE_ITEM = "remove_item"
    TRANSFORM_ITEM = "transform_item"

    # Entity management
    SUMMON_CREATURE = "summon"
    BANISH_CREATURE = "banish"
    TRANSFORM_CREATURE = "transform"

    # Time/duration
    APPLY_EXHAUSTION = "exhaustion"
    AGE = "age"
    EXTEND_CONDITION_DURATION = "extend_condition_duration"

    # Context flags and disposition
    SET_FLAG = "set_flag"  # Set a context flag for this interaction
    MODIFY_DISPOSITION = "modify_disposition"  # Change NPC disposition

    # Meta
    CUSTOM = "custom"  # For referee-adjudicated effects


# =============================================================================
# EFFECT COMMAND
# =============================================================================


@dataclass
class EffectCommand:
    """
    A discrete, validated game state change.

    Effect commands are the atomic units of game state modification.
    They can be created from:
    - Direct spell mechanical effects
    - LLM interpretation of Mythic results
    - Human player choices

    All commands are validated before execution.
    """

    effect_type: EffectType
    target_id: str  # Entity ID (character, NPC, item, location)
    parameters: dict[str, Any] = field(default_factory=dict)

    # Source tracking
    source: str = ""  # What caused this effect (spell name, etc.)
    source_id: str = ""  # Unique ID of source

    # For dice expressions (resolved at execution time)
    dice_expressions: dict[str, str] = field(default_factory=dict)
    resolved_values: dict[str, int] = field(default_factory=dict)

    # Validation state
    validated: bool = False
    validation_errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        params = ", ".join(f"{k}={v}" for k, v in self.parameters.items())
        return f"{self.effect_type.value}({self.target_id}, {params})"


@dataclass
class EffectResult:
    """Result of executing an effect command."""

    success: bool
    command: EffectCommand
    description: str = ""
    error: str = ""

    # What actually changed
    changes: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.success:
            return f"Success: {self.description}"
        return f"Failed: {self.error}"


@dataclass
class EffectBatch:
    """A collection of effects to apply together."""

    effects: list[EffectCommand] = field(default_factory=list)
    source: str = ""
    description: str = ""

    # Results after execution
    results: list[EffectResult] = field(default_factory=list)
    all_succeeded: bool = False

    def add(self, effect: EffectCommand) -> None:
        """Add an effect to the batch."""
        self.effects.append(effect)

    def __len__(self) -> int:
        return len(self.effects)


# =============================================================================
# EFFECT COMMAND BUILDER
# =============================================================================


class EffectCommandBuilder:
    """
    Factory for creating validated effect commands.

    Provides convenience methods for common effect types
    and handles dice expression parsing.
    """

    @staticmethod
    def remove_condition(
        target_id: str,
        condition: str,
        source: str = "",
    ) -> EffectCommand:
        """Create a command to remove a condition."""
        return EffectCommand(
            effect_type=EffectType.REMOVE_CONDITION,
            target_id=target_id,
            parameters={"condition": condition},
            source=source,
        )

    @staticmethod
    def add_condition(
        target_id: str,
        condition: str,
        duration: Optional[str] = None,
        source: str = "",
    ) -> EffectCommand:
        """Create a command to add a condition."""
        params = {"condition": condition}
        if duration:
            params["duration"] = duration
        return EffectCommand(
            effect_type=EffectType.ADD_CONDITION,
            target_id=target_id,
            parameters=params,
            source=source,
        )

    @staticmethod
    def modify_stat(
        target_id: str,
        stat: str,
        value: int | str,  # Can be int or dice expression like "-1d3"
        source: str = "",
    ) -> EffectCommand:
        """Create a command to permanently modify a stat."""
        cmd = EffectCommand(
            effect_type=EffectType.MODIFY_STAT,
            target_id=target_id,
            parameters={"stat": stat.upper()},
            source=source,
        )

        # Handle dice expressions
        if isinstance(value, str) and 'd' in value.lower():
            cmd.dice_expressions["value"] = value
            cmd.parameters["value_expr"] = value
        else:
            cmd.parameters["value"] = int(value)

        return cmd

    @staticmethod
    def damage(
        target_id: str,
        amount: int | str,
        damage_type: str = "magic",
        source: str = "",
    ) -> EffectCommand:
        """Create a command to deal damage."""
        cmd = EffectCommand(
            effect_type=EffectType.DAMAGE,
            target_id=target_id,
            parameters={"damage_type": damage_type},
            source=source,
        )

        if isinstance(amount, str) and 'd' in amount.lower():
            cmd.dice_expressions["amount"] = amount
            cmd.parameters["amount_expr"] = amount
        else:
            cmd.parameters["amount"] = int(amount)

        return cmd

    @staticmethod
    def heal(
        target_id: str,
        amount: int | str,
        source: str = "",
    ) -> EffectCommand:
        """Create a command to heal."""
        cmd = EffectCommand(
            effect_type=EffectType.HEAL,
            target_id=target_id,
            parameters={},
            source=source,
        )

        if isinstance(amount, str) and 'd' in amount.lower():
            cmd.dice_expressions["amount"] = amount
            cmd.parameters["amount_expr"] = amount
        else:
            cmd.parameters["amount"] = int(amount)

        return cmd

    @staticmethod
    def apply_exhaustion(
        target_id: str,
        duration_days: int | str,
        effect: str = "cannot cast spells",
        source: str = "",
    ) -> EffectCommand:
        """Create a command to apply exhaustion."""
        cmd = EffectCommand(
            effect_type=EffectType.APPLY_EXHAUSTION,
            target_id=target_id,
            parameters={"effect": effect},
            source=source,
        )

        if isinstance(duration_days, str) and 'd' in duration_days.lower():
            cmd.dice_expressions["duration"] = duration_days
            cmd.parameters["duration_expr"] = duration_days
        else:
            cmd.parameters["duration_days"] = int(duration_days)

        return cmd

    @staticmethod
    def age(
        target_id: str,
        years: int | str,
        source: str = "",
    ) -> EffectCommand:
        """Create a command to age a character."""
        cmd = EffectCommand(
            effect_type=EffectType.AGE,
            target_id=target_id,
            parameters={},
            source=source,
        )

        if isinstance(years, str) and 'd' in years.lower():
            cmd.dice_expressions["years"] = years
            cmd.parameters["years_expr"] = years
        else:
            cmd.parameters["years"] = int(years)

        return cmd

    @staticmethod
    def transfer_condition(
        from_target: str,
        to_target: str,
        condition: str,
        source: str = "",
    ) -> EffectCommand:
        """Create a command to transfer a condition between entities."""
        return EffectCommand(
            effect_type=EffectType.TRANSFER_CONDITION,
            target_id=from_target,
            parameters={
                "condition": condition,
                "to_target": to_target,
            },
            source=source,
        )

    @staticmethod
    def summon_creature(
        location_id: str,
        creature_type: str,
        duration: Optional[str] = None,
        loyalty: str = "obedient",
        source: str = "",
    ) -> EffectCommand:
        """Create a command to summon a creature."""
        params = {
            "creature_type": creature_type,
            "loyalty": loyalty,
        }
        if duration:
            params["duration"] = duration

        return EffectCommand(
            effect_type=EffectType.SUMMON_CREATURE,
            target_id=location_id,
            parameters=params,
            source=source,
        )

    @staticmethod
    def custom(
        target_id: str,
        description: str,
        source: str = "",
    ) -> EffectCommand:
        """Create a custom effect that requires manual adjudication."""
        return EffectCommand(
            effect_type=EffectType.CUSTOM,
            target_id=target_id,
            parameters={"description": description},
            source=source,
        )

    @staticmethod
    def extend_condition_duration(
        target_id: str,
        condition: str,
        turns: int = 0,
        minutes: int = 0,
        hours: int = 0,
        source: str = "",
    ) -> EffectCommand:
        """Create a command to extend the duration of an existing condition."""
        return EffectCommand(
            effect_type=EffectType.EXTEND_CONDITION_DURATION,
            target_id=target_id,
            parameters={
                "condition": condition,
                "extend_turns": turns,
                "extend_minutes": minutes,
                "extend_hours": hours,
            },
            source=source,
        )

    @staticmethod
    def set_flag(
        target_id: str,
        flag_name: str,
        flag_value: bool | str | int = True,
        scope: str = "interaction",  # "interaction", "scene", "session"
        source: str = "",
    ) -> EffectCommand:
        """Create a command to set a context flag."""
        return EffectCommand(
            effect_type=EffectType.SET_FLAG,
            target_id=target_id,
            parameters={
                "flag_name": flag_name,
                "flag_value": flag_value,
                "scope": scope,
            },
            source=source,
        )

    @staticmethod
    def modify_disposition(
        target_id: str,
        delta: int,
        reason: str = "",
        source: str = "",
    ) -> EffectCommand:
        """
        Create a command to modify NPC disposition.

        Args:
            target_id: NPC to modify
            delta: Change in disposition (-2 hostile, -1 wary, +1 friendly, +2 helpful)
            reason: Why disposition changed
            source: What caused it
        """
        return EffectCommand(
            effect_type=EffectType.MODIFY_DISPOSITION,
            target_id=target_id,
            parameters={
                "delta": delta,
                "reason": reason,
            },
            source=source,
        )


# =============================================================================
# EFFECT VALIDATOR
# =============================================================================


class EffectValidator:
    """
    Validates effect commands before execution.

    Checks:
    - Target exists
    - Effect type is valid for target type
    - Parameters are valid
    - Conditions/stats referenced exist
    """

    # Valid conditions that can be added/removed
    VALID_CONDITIONS = {
        "cursed", "charmed", "paralyzed", "poisoned", "frightened",
        "invisible", "blinded", "deafened", "stunned", "unconscious",
        "exhausted", "prone", "restrained", "petrified", "incapacitated",
        "sleeping", "confused", "diseased", "dying", "dead",
        "transformed", "suspicious", "displaced",  # Reality warp / charm conditions
    }

    # Valid stats that can be modified
    VALID_STATS = {
        "STR", "DEX", "CON", "INT", "WIS", "CHA",
        "HP", "MAX_HP", "AC", "LEVEL", "XP",
    }

    # P10.4: Special target identifiers that don't require entity lookup
    SPECIAL_TARGETS = {"party", "all", "self", "caster", "location", "area", "hex"}

    def __init__(self, controller: Optional["GlobalController"] = None):
        self._controller = controller

    def validate(self, command: EffectCommand) -> EffectCommand:
        """
        Validate an effect command.

        Returns the command with validated=True if valid,
        or with validation_errors populated if invalid.
        """
        errors = []

        # Check target exists (if we have a controller)
        if self._controller:
            exists, reason = self._entity_exists_with_reason(command.target_id)
            if not exists:
                errors.append(f"Target '{command.target_id}' not found: {reason}")

        # Validate based on effect type
        validator_method = getattr(
            self,
            f"_validate_{command.effect_type.value}",
            None
        )
        if validator_method:
            type_errors = validator_method(command)
            errors.extend(type_errors)

        # Validate dice expressions
        for key, expr in command.dice_expressions.items():
            if not self._is_valid_dice_expr(expr):
                errors.append(f"Invalid dice expression '{expr}' for {key}")

        command.validation_errors = errors
        command.validated = len(errors) == 0

        return command

    def validate_batch(self, batch: EffectBatch) -> EffectBatch:
        """Validate all effects in a batch."""
        for effect in batch.effects:
            self.validate(effect)
        return batch

    def _entity_exists_with_reason(self, entity_id: str) -> tuple[bool, str]:
        """
        P10.4: Check if an entity exists with detailed reason.

        Returns:
            Tuple of (exists: bool, reason: str)
            When no controller is available, returns (True, "validation skipped")
            to allow simulated mode to work.
        """
        if not self._controller:
            # No controller - skip validation for simulated mode
            # Note: The executor will still run in simulated mode
            return True, "validation skipped (no controller)"

        # Check special target identifiers
        if entity_id.lower() in self.SPECIAL_TARGETS:
            return True, "special target"

        # Check party members and registered NPCs
        if self._controller.get_character(entity_id):
            return True, "found in characters/NPCs"

        # Check registered NPCs specifically
        if self._controller.get_npc(entity_id):
            return True, "found in NPCs"

        # Check combatants in active combat
        if hasattr(self._controller, 'combat_engine') and self._controller.combat_engine:
            combat_engine = self._controller.combat_engine
            if hasattr(combat_engine, 'get_combatant') and combat_engine.get_combatant(entity_id):
                return True, "found in active combat"
            if hasattr(combat_engine, '_combat_state') and combat_engine._combat_state:
                for combatant in combat_engine._combat_state.combatants:
                    if combatant.combatant_id == entity_id:
                        return True, "found in combat combatants"

        # P10.4: Entity not found - return explicit error
        return False, "not found in party, NPCs, or combat"

    def _entity_exists(self, entity_id: str) -> bool:
        """Check if an entity exists in game state."""
        exists, _ = self._entity_exists_with_reason(entity_id)
        return exists

    def _is_valid_dice_expr(self, expr: str) -> bool:
        """Check if a string is a valid dice expression."""
        # Matches patterns like: 1d6, 2d8+2, -1d3, 3d6-1
        pattern = r'^[+-]?\d*d\d+([+-]\d+)?$'
        return bool(re.match(pattern, expr.lower().replace(' ', '')))

    def _validate_add_condition(self, cmd: EffectCommand) -> list[str]:
        errors = []
        condition = cmd.parameters.get("condition", "").lower()
        if condition and condition not in self.VALID_CONDITIONS:
            errors.append(f"Unknown condition '{condition}'")
        return errors

    def _validate_remove_condition(self, cmd: EffectCommand) -> list[str]:
        return self._validate_add_condition(cmd)

    def _validate_modify_stat(self, cmd: EffectCommand) -> list[str]:
        errors = []
        stat = cmd.parameters.get("stat", "").upper()
        if stat and stat not in self.VALID_STATS:
            errors.append(f"Unknown stat '{stat}'")
        if "value" not in cmd.parameters and "value_expr" not in cmd.parameters:
            errors.append("modify_stat requires 'value' or 'value_expr'")
        return errors

    def _validate_damage(self, cmd: EffectCommand) -> list[str]:
        errors = []
        if "amount" not in cmd.parameters and "amount_expr" not in cmd.parameters:
            errors.append("damage requires 'amount' or 'amount_expr'")
        return errors

    def _validate_heal(self, cmd: EffectCommand) -> list[str]:
        return self._validate_damage(cmd)


# =============================================================================
# EFFECT EXECUTOR
# =============================================================================


class EffectExecutor:
    """
    Executes validated effect commands against the game state.

    Each effect type has a handler method that performs
    the actual game state modification.
    """

    def __init__(
        self,
        controller: Optional["GlobalController"] = None,
        dice_roller: Optional["DiceRoller"] = None,
    ):
        self._controller = controller
        self._dice = dice_roller
        self._validator = EffectValidator(controller)

    def execute(self, command: EffectCommand) -> EffectResult:
        """
        Execute a single effect command.

        Validates first if not already validated,
        resolves dice expressions, then applies the effect.
        """
        # Validate if needed
        if not command.validated:
            self._validator.validate(command)

        if not command.validated:
            return EffectResult(
                success=False,
                command=command,
                error=f"Validation failed: {', '.join(command.validation_errors)}",
            )

        # Resolve dice expressions
        self._resolve_dice(command)

        # Get handler for this effect type
        handler = getattr(self, f"_execute_{command.effect_type.value}", None)
        if not handler:
            return EffectResult(
                success=False,
                command=command,
                error=f"No handler for effect type: {command.effect_type.value}",
            )

        # Execute
        try:
            return handler(command)
        except Exception as e:
            return EffectResult(
                success=False,
                command=command,
                error=f"Execution error: {str(e)}",
            )

    def execute_batch(self, batch: EffectBatch) -> EffectBatch:
        """Execute all effects in a batch."""
        batch.results = []
        all_success = True

        for effect in batch.effects:
            result = self.execute(effect)
            batch.results.append(result)
            if not result.success:
                all_success = False

        batch.all_succeeded = all_success
        return batch

    def _entity_exists(self, entity_id: str) -> bool:
        """
        P10.4: Check if an entity exists in game state.

        Delegates to the validator's comprehensive entity lookup.
        """
        return self._validator._entity_exists(entity_id)

    def _entity_exists_with_reason(self, entity_id: str) -> tuple[bool, str]:
        """P10.4: Check if entity exists with detailed reason."""
        return self._validator._entity_exists_with_reason(entity_id)

    def _resolve_dice(self, command: EffectCommand) -> None:
        """Resolve any dice expressions in the command."""
        if not self._dice:
            # No dice roller - can't resolve
            return

        for key, expr in command.dice_expressions.items():
            roll_result = self._dice.roll(expr, f"{command.source} - {key}")
            command.resolved_values[key] = roll_result.total

            # Also update parameters with resolved value
            if f"{key}_expr" in command.parameters:
                command.parameters[key] = roll_result.total

    # =========================================================================
    # EFFECT HANDLERS
    # =========================================================================

    def _execute_remove_condition(self, cmd: EffectCommand) -> EffectResult:
        """Remove a condition from a target."""
        condition = cmd.parameters.get("condition")

        if not condition:
            return EffectResult(
                success=False,
                command=cmd,
                description="No condition specified to remove",
                changes={},
            )

        if self._controller:
            # P10.4: Verify target exists with detailed reason
            exists, reason = self._entity_exists_with_reason(cmd.target_id)
            if not exists:
                return EffectResult(
                    success=False,
                    command=cmd,
                    error=f"Invalid target '{cmd.target_id}': {reason}",
                    changes={},
                )

            # Wire to actual controller method
            result = self._controller.remove_condition(cmd.target_id, condition)
            if result.get("error"):
                return EffectResult(
                    success=False,
                    command=cmd,
                    description=result["error"],
                    changes={},
                )

            return EffectResult(
                success=True,
                command=cmd,
                description=f"Removed '{condition}' from {cmd.target_id}",
                changes={"removed_condition": condition, "was_present": result.get("removed", False)},
            )

        # No controller - report as success but no actual change
        return EffectResult(
            success=True,
            command=cmd,
            description=f"[No controller] Would remove '{condition}' from {cmd.target_id}",
            changes={"removed_condition": condition, "simulated": True},
        )

    def _execute_add_condition(self, cmd: EffectCommand) -> EffectResult:
        """Add a condition to a target."""
        condition = cmd.parameters.get("condition")
        duration = cmd.parameters.get("duration")
        source = cmd.parameters.get("source", "spell_effect")

        if not condition:
            return EffectResult(
                success=False,
                command=cmd,
                description="No condition specified to add",
                changes={},
            )

        if self._controller:
            # P10.4: Verify target exists with detailed reason
            exists, reason = self._entity_exists_with_reason(cmd.target_id)
            if not exists:
                return EffectResult(
                    success=False,
                    command=cmd,
                    error=f"Invalid target '{cmd.target_id}': {reason}",
                    changes={},
                )

            # Wire to actual controller method
            result = self._controller.apply_condition(cmd.target_id, condition, source=source)
            if result.get("error"):
                return EffectResult(
                    success=False,
                    command=cmd,
                    description=result["error"],
                    changes={},
                )

            desc = f"Applied '{condition}' to {cmd.target_id}"
            if duration:
                desc += f" for {duration}"

            return EffectResult(
                success=True,
                command=cmd,
                description=desc,
                changes={"added_condition": condition, "duration": duration, "applied": True},
            )

        # No controller - report as success but no actual change
        desc = f"[No controller] Would apply '{condition}' to {cmd.target_id}"
        if duration:
            desc += f" for {duration}"

        return EffectResult(
            success=True,
            command=cmd,
            description=desc,
            changes={"added_condition": condition, "duration": duration, "simulated": True},
        )

    def _execute_modify_stat(self, cmd: EffectCommand) -> EffectResult:
        """Permanently modify a stat (ability score)."""
        stat = cmd.parameters.get("stat")
        value = cmd.resolved_values.get("value") or cmd.parameters.get("value", 0)

        if not stat:
            return EffectResult(
                success=False,
                command=cmd,
                description="No stat specified to modify",
                changes={},
            )

        # Normalize stat name to uppercase
        stat_upper = stat.upper()
        valid_stats = {"STR", "INT", "WIS", "DEX", "CON", "CHA"}
        if stat_upper not in valid_stats:
            return EffectResult(
                success=False,
                command=cmd,
                description=f"Unknown stat: {stat}. Valid: {', '.join(valid_stats)}",
                changes={},
            )

        if self._controller:
            # P10.4: Verify target exists with detailed reason
            exists, reason = self._entity_exists_with_reason(cmd.target_id)
            if not exists:
                return EffectResult(
                    success=False,
                    command=cmd,
                    error=f"Invalid target '{cmd.target_id}': {reason}",
                    changes={},
                )

            # Get character and modify stat
            character = self._controller.get_character(cmd.target_id)
            if not character:
                return EffectResult(
                    success=False,
                    command=cmd,
                    description=f"Character {cmd.target_id} not found",
                    changes={},
                )

            old_val = character.ability_scores.get(stat_upper, 10)
            new_val = max(1, old_val + value)  # Stats can't go below 1
            character.ability_scores[stat_upper] = new_val

            return EffectResult(
                success=True,
                command=cmd,
                description=f"Modified {cmd.target_id}'s {stat_upper}: {old_val} → {new_val} ({value:+d})",
                changes={"stat": stat_upper, "old_value": old_val, "new_value": new_val, "delta": value},
            )

        # No controller - report as simulated
        return EffectResult(
            success=True,
            command=cmd,
            description=f"[No controller] Would modify {cmd.target_id}'s {stat_upper} by {value:+d}",
            changes={"stat": stat_upper, "delta": value, "simulated": True},
        )

    def _execute_damage(self, cmd: EffectCommand) -> EffectResult:
        """Deal damage to a target."""
        amount = cmd.resolved_values.get("amount") or cmd.parameters.get("amount", 0)
        damage_type = cmd.parameters.get("damage_type", "magic")

        if amount <= 0:
            return EffectResult(
                success=False,
                command=cmd,
                description=f"Invalid damage amount: {amount}",
                changes={},
            )

        if self._controller:
            # P10.4: Verify target exists with detailed reason
            exists, reason = self._entity_exists_with_reason(cmd.target_id)
            if not exists:
                return EffectResult(
                    success=False,
                    command=cmd,
                    error=f"Invalid target '{cmd.target_id}': {reason}",
                    changes={},
                )

            # Wire to actual controller method
            result = self._controller.apply_damage(cmd.target_id, amount, damage_type)
            if result.get("error"):
                return EffectResult(
                    success=False,
                    command=cmd,
                    description=result["error"],
                    changes={},
                )

            changes = {
                "damage": result.get("damage_dealt", amount),
                "type": damage_type,
                "hp_remaining": result.get("hp_remaining"),
            }
            if result.get("unconscious"):
                changes["unconscious"] = True
            if result.get("dead"):
                changes["dead"] = True

            return EffectResult(
                success=True,
                command=cmd,
                description=f"Dealt {result.get('damage_dealt', amount)} {damage_type} damage to {cmd.target_id}",
                changes=changes,
            )

        # No controller - report as simulated
        return EffectResult(
            success=True,
            command=cmd,
            description=f"[No controller] Would deal {amount} {damage_type} damage to {cmd.target_id}",
            changes={"damage": amount, "type": damage_type, "simulated": True},
        )

    def _execute_heal(self, cmd: EffectCommand) -> EffectResult:
        """Heal a target."""
        amount = cmd.resolved_values.get("amount") or cmd.parameters.get("amount", 0)

        if amount <= 0:
            return EffectResult(
                success=False,
                command=cmd,
                description=f"Invalid healing amount: {amount}",
                changes={},
            )

        if self._controller:
            # P10.4: Verify target exists with detailed reason
            exists, reason = self._entity_exists_with_reason(cmd.target_id)
            if not exists:
                return EffectResult(
                    success=False,
                    command=cmd,
                    error=f"Invalid target '{cmd.target_id}': {reason}",
                    changes={},
                )

            # Wire to actual controller method
            result = self._controller.heal_character(cmd.target_id, amount)
            if result.get("error"):
                return EffectResult(
                    success=False,
                    command=cmd,
                    description=result["error"],
                    changes={},
                )

            return EffectResult(
                success=True,
                command=cmd,
                description=f"Healed {cmd.target_id} for {result.get('healing', amount)} HP (now {result.get('hp_current')}/{result.get('hp_max')})",
                changes={
                    "healing": result.get("healing", amount),
                    "hp_current": result.get("hp_current"),
                    "hp_max": result.get("hp_max"),
                },
            )

        # No controller - report as simulated
        return EffectResult(
            success=True,
            command=cmd,
            description=f"[No controller] Would heal {cmd.target_id} for {amount} HP",
            changes={"healing": amount, "simulated": True},
        )

    def _execute_exhaustion(self, cmd: EffectCommand) -> EffectResult:
        """Apply exhaustion to a target."""
        duration = cmd.resolved_values.get("duration") or cmd.parameters.get("duration_days", 1)
        effect = cmd.parameters.get("effect", "exhausted")

        return EffectResult(
            success=True,
            command=cmd,
            description=f"Applied exhaustion to {cmd.target_id} for {duration} days: {effect}",
            changes={"exhaustion_days": duration, "effect": effect},
        )

    def _execute_age(self, cmd: EffectCommand) -> EffectResult:
        """Age a character."""
        years = cmd.resolved_values.get("years") or cmd.parameters.get("years", 0)

        return EffectResult(
            success=True,
            command=cmd,
            description=f"Aged {cmd.target_id} by {years} years",
            changes={"years_aged": years},
        )

    def _execute_transfer_condition(self, cmd: EffectCommand) -> EffectResult:
        """Transfer a condition from one target to another."""
        condition = cmd.parameters.get("condition")
        to_target = cmd.parameters.get("to_target")

        return EffectResult(
            success=True,
            command=cmd,
            description=f"Transferred '{condition}' from {cmd.target_id} to {to_target}",
            changes={
                "removed_from": cmd.target_id,
                "added_to": to_target,
                "condition": condition,
            },
        )

    def _execute_summon(self, cmd: EffectCommand) -> EffectResult:
        """Summon a creature."""
        creature_type = cmd.parameters.get("creature_type")
        duration = cmd.parameters.get("duration")
        loyalty = cmd.parameters.get("loyalty", "obedient")

        return EffectResult(
            success=True,
            command=cmd,
            description=f"Summoned {creature_type} at {cmd.target_id} ({loyalty})",
            changes={
                "summoned": creature_type,
                "location": cmd.target_id,
                "duration": duration,
                "loyalty": loyalty,
            },
        )

    def _execute_custom(self, cmd: EffectCommand) -> EffectResult:
        """Handle custom effects that require manual adjudication."""
        description = cmd.parameters.get("description", "Unknown custom effect")

        return EffectResult(
            success=True,
            command=cmd,
            description=f"Custom effect: {description}",
            changes={"custom": description, "requires_adjudication": True},
        )

    def _execute_extend_condition_duration(self, cmd: EffectCommand) -> EffectResult:
        """Extend the duration of an existing condition."""
        condition = cmd.parameters.get("condition")
        extend_turns = cmd.parameters.get("extend_turns", 0)
        extend_minutes = cmd.parameters.get("extend_minutes", 0)
        extend_hours = cmd.parameters.get("extend_hours", 0)

        if not condition:
            return EffectResult(
                success=False,
                command=cmd,
                error="No condition specified to extend",
            )

        if self._controller:
            # Wire to controller's extend_condition_duration if available
            if hasattr(self._controller, 'extend_condition_duration'):
                result = self._controller.extend_condition_duration(
                    cmd.target_id, condition,
                    turns=extend_turns, minutes=extend_minutes, hours=extend_hours
                )
                if result.get("error"):
                    return EffectResult(
                        success=False,
                        command=cmd,
                        error=result["error"],
                    )
                return EffectResult(
                    success=True,
                    command=cmd,
                    description=f"Extended '{condition}' duration on {cmd.target_id}",
                    changes={
                        "condition": condition,
                        "extended_turns": extend_turns,
                        "extended_minutes": extend_minutes,
                        "extended_hours": extend_hours,
                    },
                )

        # No controller or method - report as simulated
        desc_parts = []
        if extend_turns:
            desc_parts.append(f"{extend_turns} turns")
        if extend_minutes:
            desc_parts.append(f"{extend_minutes} minutes")
        if extend_hours:
            desc_parts.append(f"{extend_hours} hours")
        duration_str = " + ".join(desc_parts) or "0"

        return EffectResult(
            success=True,
            command=cmd,
            description=f"[Simulated] Extend '{condition}' on {cmd.target_id} by {duration_str}",
            changes={
                "condition": condition,
                "extended_turns": extend_turns,
                "extended_minutes": extend_minutes,
                "extended_hours": extend_hours,
                "simulated": True,
            },
        )

    def _execute_set_flag(self, cmd: EffectCommand) -> EffectResult:
        """Set a context flag for this interaction."""
        flag_name = cmd.parameters.get("flag_name")
        flag_value = cmd.parameters.get("flag_value", True)
        scope = cmd.parameters.get("scope", "interaction")

        if not flag_name:
            return EffectResult(
                success=False,
                command=cmd,
                error="No flag_name specified",
            )

        if self._controller:
            # Wire to controller's set_context_flag if available
            if hasattr(self._controller, 'set_context_flag'):
                self._controller.set_context_flag(flag_name, flag_value, scope=scope)

        return EffectResult(
            success=True,
            command=cmd,
            description=f"Set flag '{flag_name}' = {flag_value} (scope: {scope})",
            changes={
                "flag_name": flag_name,
                "flag_value": flag_value,
                "scope": scope,
            },
        )

    def _execute_modify_disposition(self, cmd: EffectCommand) -> EffectResult:
        """Modify NPC disposition."""
        delta = cmd.parameters.get("delta", 0)
        reason = cmd.parameters.get("reason", "")

        if self._controller:
            # Wire to controller's modify_disposition if available
            if hasattr(self._controller, 'modify_npc_disposition'):
                result = self._controller.modify_npc_disposition(
                    cmd.target_id, delta, reason=reason
                )
                if result.get("error"):
                    return EffectResult(
                        success=False,
                        command=cmd,
                        error=result["error"],
                    )
                return EffectResult(
                    success=True,
                    command=cmd,
                    description=f"Modified disposition of {cmd.target_id} by {delta:+d}",
                    changes={
                        "npc_id": cmd.target_id,
                        "delta": delta,
                        "new_disposition": result.get("new_disposition"),
                    },
                )

        # No controller - report as simulated
        return EffectResult(
            success=True,
            command=cmd,
            description=f"[Simulated] Modify disposition of {cmd.target_id} by {delta:+d}",
            changes={
                "npc_id": cmd.target_id,
                "delta": delta,
                "reason": reason,
                "simulated": True,
            },
        )
