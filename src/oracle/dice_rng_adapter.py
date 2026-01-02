"""
Deterministic RNG adapter for MythicGME integration.

This adapter wraps the project's DiceRoller to provide the same interface
that MythicGME expects from random.Random, ensuring all oracle rolls go
through the centralized dice system for:
- Reproducibility via seeding
- Logging for observability
- Replay mode support
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Sequence

if TYPE_CHECKING:
    from src.data_models import DiceRoller


class DiceRngAdapter:
    """
    Adapter that makes DiceRoller compatible with random.Random interface.

    MythicGME expects an RNG with randint(a, b) and choice(seq) methods.
    This adapter wraps DiceRoller to provide that interface while ensuring
    all rolls are deterministic and logged.

    Usage:
        from src.data_models import DiceRoller
        from src.oracle.dice_rng_adapter import DiceRngAdapter
        from src.oracle.mythic_gme import MythicGME

        adapter = DiceRngAdapter(reason_prefix="FactionOracle")
        mythic = MythicGME(rng=adapter)
    """

    def __init__(
        self,
        reason_prefix: str = "Oracle",
        dice_roller: Optional["DiceRoller"] = None,
    ):
        """
        Initialize the adapter.

        Args:
            reason_prefix: Prefix for roll reason logging (e.g., "FactionOracle")
            dice_roller: Optional DiceRoller instance. If None, uses singleton.
        """
        self._reason_prefix = reason_prefix
        self._dice_roller = dice_roller
        self._roll_count = 0

    def _get_dice_roller(self) -> "DiceRoller":
        """Get the DiceRoller instance (lazy import to avoid circular deps)."""
        if self._dice_roller is not None:
            return self._dice_roller
        from src.data_models import DiceRoller
        return DiceRoller()

    def _make_reason(self, context: str) -> str:
        """Create a reason string for logging."""
        self._roll_count += 1
        return f"{self._reason_prefix}: {context} (roll #{self._roll_count})"

    def randint(self, a: int, b: int) -> int:
        """
        Return random integer in range [a, b], inclusive.

        This is the main method used by MythicGME for d100 rolls.

        Args:
            a: Minimum value (inclusive)
            b: Maximum value (inclusive)

        Returns:
            Random integer in the specified range
        """
        dice = self._get_dice_roller()
        reason = self._make_reason(f"d{b - a + 1}" if a == 1 else f"range({a}-{b})")
        return dice.randint(a, b, reason)

    def choice(self, seq: Sequence[Any]) -> Any:
        """
        Choose a random element from a non-empty sequence.

        Used by MythicGME for table lookups.

        Args:
            seq: Non-empty sequence to choose from

        Returns:
            Randomly selected element

        Raises:
            IndexError: If sequence is empty
        """
        if not seq:
            raise IndexError("Cannot choose from an empty sequence")

        dice = self._get_dice_roller()
        reason = self._make_reason(f"choice from {len(seq)} options")
        return dice.choice(list(seq), reason)

    def random(self) -> float:
        """
        Return a random float in [0.0, 1.0).

        Not typically used by MythicGME but included for completeness.
        Simulates by rolling d10000 and dividing.
        """
        dice = self._get_dice_roller()
        reason = self._make_reason("random float")
        roll = dice.randint(0, 9999, reason)
        return roll / 10000.0

    def shuffle(self, x: list) -> None:
        """
        Shuffle list x in place.

        Implemented using Fisher-Yates shuffle with DiceRoller.
        Not typically used by MythicGME but included for completeness.
        """
        dice = self._get_dice_roller()
        for i in range(len(x) - 1, 0, -1):
            reason = self._make_reason(f"shuffle position {i}")
            j = dice.randint(0, i, reason)
            x[i], x[j] = x[j], x[i]

    @property
    def roll_count(self) -> int:
        """Get the number of rolls made through this adapter."""
        return self._roll_count

    def reset_count(self) -> None:
        """Reset the roll counter."""
        self._roll_count = 0
