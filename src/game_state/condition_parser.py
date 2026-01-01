"""
Acquisition Condition Parser

This module provides extensible parsing and evaluation of item acquisition conditions.
Conditions can reference NPCs, locations, items, or other game state to determine
if an item can be acquired.

Supported condition patterns:
- "[NPC_NAME] must be killed or removed" - NPC death or removal
- "[NPC_NAME] must be defeated" - NPC death only
- "[NPC_NAME] must be gone" - NPC removed only
- "[ITEM_NAME] must be obtained" - Item in party inventory
- Custom conditions via extension
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Protocol


class ConditionType(Enum):
    """Types of acquisition conditions."""
    NPC_DEAD_OR_REMOVED = "npc_dead_or_removed"
    NPC_DEAD = "npc_dead"
    NPC_REMOVED = "npc_removed"
    ITEM_OBTAINED = "item_obtained"
    CUSTOM = "custom"


@dataclass
class ParsedCondition:
    """A parsed acquisition condition."""
    condition_type: ConditionType
    target_name: str  # NPC name, item name, etc.
    original_text: str
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ConditionEvaluator(Protocol):
    """Protocol for condition evaluation functions."""
    def __call__(
        self,
        condition: ParsedCondition,
        hex_id: str,
        session_manager: Any,
    ) -> tuple[bool, str]:
        """
        Evaluate if a condition is satisfied.

        Returns:
            Tuple of (is_satisfied, reason_message)
        """
        ...


class AcquisitionConditionParser:
    """
    Extensible parser for item acquisition conditions.

    Parses natural language conditions from hex data and evaluates them
    against the current game state.
    """

    # Pattern definitions for parsing conditions
    PATTERNS = [
        # "[Name] must be killed or removed"
        (
            re.compile(r"^(.+?)\s+must\s+be\s+(?:killed|slain)\s+or\s+removed$", re.IGNORECASE),
            ConditionType.NPC_DEAD_OR_REMOVED,
        ),
        # "[Name] must be defeated/killed/slain"
        (
            re.compile(r"^(.+?)\s+must\s+be\s+(?:defeated|killed|slain)$", re.IGNORECASE),
            ConditionType.NPC_DEAD,
        ),
        # "[Name] must be removed/gone/banished"
        (
            re.compile(r"^(.+?)\s+must\s+be\s+(?:removed|gone|banished)$", re.IGNORECASE),
            ConditionType.NPC_REMOVED,
        ),
        # "[Item] must be obtained/acquired"
        (
            re.compile(r"^(.+?)\s+must\s+be\s+(?:obtained|acquired)$", re.IGNORECASE),
            ConditionType.ITEM_OBTAINED,
        ),
    ]

    def __init__(self):
        """Initialize the condition parser."""
        self._custom_patterns: list[tuple[re.Pattern, ConditionType, dict]] = []
        self._custom_evaluators: dict[str, ConditionEvaluator] = {}

    def register_pattern(
        self,
        pattern: re.Pattern,
        condition_type: ConditionType,
        metadata: dict[str, Any] = None,
    ) -> None:
        """
        Register a custom pattern for condition parsing.

        Args:
            pattern: Regex pattern with capture group for target name
            condition_type: The type of condition this pattern represents
            metadata: Optional metadata to attach to parsed conditions
        """
        self._custom_patterns.append((pattern, condition_type, metadata or {}))

    def register_evaluator(
        self,
        name: str,
        evaluator: ConditionEvaluator,
    ) -> None:
        """
        Register a custom condition evaluator.

        Args:
            name: Unique name for the evaluator
            evaluator: Function that evaluates conditions
        """
        self._custom_evaluators[name] = evaluator

    def parse(self, condition_text: str) -> Optional[ParsedCondition]:
        """
        Parse a condition string into a structured condition.

        Args:
            condition_text: The raw condition text from hex data

        Returns:
            ParsedCondition if successfully parsed, None otherwise
        """
        if not condition_text:
            return None

        condition_text = condition_text.strip()

        # Try custom patterns first
        for pattern, cond_type, metadata in self._custom_patterns:
            match = pattern.match(condition_text)
            if match:
                return ParsedCondition(
                    condition_type=cond_type,
                    target_name=match.group(1).strip(),
                    original_text=condition_text,
                    metadata=metadata.copy(),
                )

        # Try built-in patterns
        for pattern, cond_type in self.PATTERNS:
            match = pattern.match(condition_text)
            if match:
                return ParsedCondition(
                    condition_type=cond_type,
                    target_name=match.group(1).strip(),
                    original_text=condition_text,
                )

        # Fallback: treat as custom condition
        return ParsedCondition(
            condition_type=ConditionType.CUSTOM,
            target_name=condition_text,
            original_text=condition_text,
        )

    def evaluate(
        self,
        condition: ParsedCondition,
        hex_id: str,
        session_manager: Any,
        controller: Any = None,
    ) -> tuple[bool, str]:
        """
        Evaluate if a parsed condition is satisfied.

        Args:
            condition: The parsed condition to evaluate
            hex_id: Current hex ID
            session_manager: SessionManager instance for state queries
            controller: Optional GlobalController for additional queries

        Returns:
            Tuple of (is_satisfied, reason_message)
        """
        if condition.condition_type == ConditionType.NPC_DEAD_OR_REMOVED:
            return self._evaluate_npc_dead_or_removed(
                condition, hex_id, session_manager
            )

        elif condition.condition_type == ConditionType.NPC_DEAD:
            return self._evaluate_npc_dead(
                condition, hex_id, session_manager
            )

        elif condition.condition_type == ConditionType.NPC_REMOVED:
            return self._evaluate_npc_removed(
                condition, hex_id, session_manager
            )

        elif condition.condition_type == ConditionType.ITEM_OBTAINED:
            return self._evaluate_item_obtained(
                condition, controller
            )

        elif condition.condition_type == ConditionType.CUSTOM:
            # Check for registered custom evaluators
            for name, evaluator in self._custom_evaluators.items():
                try:
                    result = evaluator(condition, hex_id, session_manager)
                    if result[0]:  # If satisfied
                        return result
                except Exception:
                    continue

            # Custom conditions default to not satisfied
            return (
                False,
                f"Condition not met: {condition.original_text}"
            )

        return (False, f"Unknown condition type: {condition.condition_type}")

    def _normalize_npc_id(self, name: str) -> str:
        """Convert NPC name to ID format."""
        return name.lower().replace(" ", "_").replace("the_", "")

    def _evaluate_npc_dead_or_removed(
        self,
        condition: ParsedCondition,
        hex_id: str,
        session_manager: Any,
    ) -> tuple[bool, str]:
        """Evaluate NPC dead or removed condition."""
        npc_id = self._normalize_npc_id(condition.target_name)

        # Check if NPC is dead or removed
        is_dead = session_manager.is_npc_dead(hex_id, npc_id)
        is_removed = session_manager.is_npc_removed(hex_id, npc_id)

        if is_dead:
            return (True, f"The {condition.target_name} has been slain.")
        elif is_removed:
            return (True, f"The {condition.target_name} has been driven away.")
        else:
            return (
                False,
                f"The {condition.target_name} still blocks access to this item."
            )

    def _evaluate_npc_dead(
        self,
        condition: ParsedCondition,
        hex_id: str,
        session_manager: Any,
    ) -> tuple[bool, str]:
        """Evaluate NPC must be dead condition."""
        npc_id = self._normalize_npc_id(condition.target_name)

        if session_manager.is_npc_dead(hex_id, npc_id):
            return (True, f"The {condition.target_name} has been defeated.")
        else:
            return (
                False,
                f"The {condition.target_name} must be defeated first."
            )

    def _evaluate_npc_removed(
        self,
        condition: ParsedCondition,
        hex_id: str,
        session_manager: Any,
    ) -> tuple[bool, str]:
        """Evaluate NPC must be removed condition."""
        npc_id = self._normalize_npc_id(condition.target_name)

        if session_manager.is_npc_removed(hex_id, npc_id):
            return (True, f"The {condition.target_name} is no longer here.")
        else:
            return (
                False,
                f"The {condition.target_name} is still present."
            )

    def _evaluate_item_obtained(
        self,
        condition: ParsedCondition,
        controller: Any,
    ) -> tuple[bool, str]:
        """Evaluate item must be obtained condition."""
        if not controller:
            return (False, "Cannot check inventory without controller.")

        item_name = condition.target_name.lower()

        # Check all party member inventories
        for character in controller.party.members:
            for item in character.inventory:
                if item.name.lower() == item_name:
                    return (True, f"You have the {condition.target_name}.")

        return (
            False,
            f"You must first obtain the {condition.target_name}."
        )


# Singleton instance for convenience
_default_parser: Optional[AcquisitionConditionParser] = None


def get_condition_parser() -> AcquisitionConditionParser:
    """Get the default condition parser instance."""
    global _default_parser
    if _default_parser is None:
        _default_parser = AcquisitionConditionParser()
    return _default_parser


def check_acquisition_condition(
    condition_text: str,
    hex_id: str,
    session_manager: Any,
    controller: Any = None,
) -> tuple[bool, str]:
    """
    Convenience function to check if an acquisition condition is met.

    Args:
        condition_text: Raw condition text from item data
        hex_id: Current hex ID
        session_manager: SessionManager instance
        controller: Optional GlobalController

    Returns:
        Tuple of (is_satisfied, reason_message)
    """
    parser = get_condition_parser()
    condition = parser.parse(condition_text)

    if condition is None:
        return (True, "No condition to check.")

    return parser.evaluate(condition, hex_id, session_manager, controller)
