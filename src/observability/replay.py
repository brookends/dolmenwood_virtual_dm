"""
Replay system for deterministic game replay.

Allows replaying a game session by providing recorded roll results
instead of generating new random numbers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class ReplayMode(str, Enum):
    """Replay mode settings."""

    DISABLED = "disabled"  # Normal operation, generate random rolls
    REPLAYING = "replaying"  # Use recorded rolls from stream
    RECORDING = "recording"  # Normal operation, but recording for later replay


@dataclass
class ReplaySession:
    """
    Manages a replay session.

    In replay mode, provides pre-recorded roll results instead of
    generating new random numbers, allowing deterministic replay.
    """

    seed: int
    roll_stream: list[dict[str, Any]] = field(default_factory=list)
    mode: ReplayMode = ReplayMode.DISABLED
    _position: int = 0
    _overruns: int = 0

    def __post_init__(self):
        self._position = 0
        self._overruns = 0

    @classmethod
    def from_run_log(cls, log_data: dict[str, Any]) -> "ReplaySession":
        """
        Create a replay session from saved run log data.

        Args:
            log_data: Dictionary from RunLog.to_dict() or loaded JSON

        Returns:
            ReplaySession configured for replay
        """
        seed = log_data.get("seed", 0)
        roll_stream = []

        for event in log_data.get("events", []):
            if event.get("event_type") == "roll":
                roll_stream.append(
                    {
                        "notation": event.get("notation", ""),
                        "rolls": event.get("rolls", []),
                        "modifier": event.get("modifier", 0),
                        "total": event.get("total", 0),
                        "reason": event.get("reason", ""),
                    }
                )

        session = cls(seed=seed, roll_stream=roll_stream)
        session.mode = ReplayMode.REPLAYING
        return session

    @classmethod
    def load(cls, filepath: str) -> "ReplaySession":
        """Load a replay session from a file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle both ReplaySession.save() format and RunLog.to_dict() format
        if "roll_stream" in data:
            # Direct ReplaySession save format
            session = cls(
                seed=data.get("seed", 0),
                roll_stream=data.get("roll_stream", []),
            )
            session.mode = ReplayMode.REPLAYING
            return session
        else:
            # RunLog.to_dict() format - extract rolls from events
            return cls.from_run_log(data)

    def save(self, filepath: str) -> None:
        """Save the replay session to a file."""
        data = {
            "seed": self.seed,
            "roll_stream": self.roll_stream,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"ReplaySession saved to {filepath}")

    def start_replay(self) -> None:
        """Start replaying from the beginning."""
        self.mode = ReplayMode.REPLAYING
        self._position = 0
        self._overruns = 0
        logger.info(f"Replay started with {len(self.roll_stream)} recorded rolls")

    def stop_replay(self) -> None:
        """Stop replay mode."""
        self.mode = ReplayMode.DISABLED
        logger.info(f"Replay stopped at position {self._position}/{len(self.roll_stream)}")

    def is_replaying(self) -> bool:
        """Check if currently in replay mode."""
        return self.mode == ReplayMode.REPLAYING

    def has_next_roll(self) -> bool:
        """Check if there are more recorded rolls available."""
        return self._position < len(self.roll_stream)

    def get_next_roll(self) -> Optional[dict[str, Any]]:
        """
        Get the next recorded roll.

        Returns:
            Dict with {notation, rolls, modifier, total, reason}
            or None if no more rolls available
        """
        if not self.is_replaying():
            return None

        if self._position >= len(self.roll_stream):
            self._overruns += 1
            logger.warning(
                f"Replay overrun #{self._overruns}: no more recorded rolls at position {self._position}"
            )
            return None

        roll = self.roll_stream[self._position]
        self._position += 1
        return roll

    def peek_next_roll(self) -> Optional[dict[str, Any]]:
        """Peek at the next roll without advancing position."""
        if self._position < len(self.roll_stream):
            return self.roll_stream[self._position]
        return None

    def get_position(self) -> int:
        """Get current position in the roll stream."""
        return self._position

    def get_total_rolls(self) -> int:
        """Get total number of recorded rolls."""
        return len(self.roll_stream)

    def get_remaining_rolls(self) -> int:
        """Get number of remaining rolls in the stream."""
        return max(0, len(self.roll_stream) - self._position)

    def get_overrun_count(self) -> int:
        """Get number of times replay ran out of recorded rolls."""
        return self._overruns

    def reset(self) -> None:
        """Reset to the beginning of the roll stream."""
        self._position = 0
        self._overruns = 0

    def add_roll(
        self,
        notation: str,
        rolls: list[int],
        modifier: int,
        total: int,
        reason: str = "",
    ) -> None:
        """
        Add a roll to the stream (for recording mode).

        Args:
            notation: Dice notation (e.g., "2d6")
            rolls: Individual die results
            modifier: Modifier applied
            total: Final total
            reason: Why the roll was made
        """
        self.roll_stream.append(
            {
                "notation": notation,
                "rolls": rolls,
                "modifier": modifier,
                "total": total,
                "reason": reason,
            }
        )

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the replay session."""
        return {
            "seed": self.seed,
            "mode": self.mode.value,
            "total_rolls": len(self.roll_stream),
            "current_position": self._position,
            "remaining_rolls": self.get_remaining_rolls(),
            "overruns": self._overruns,
        }

    def __repr__(self) -> str:
        return (
            f"ReplaySession(seed={self.seed}, "
            f"mode={self.mode.value}, "
            f"position={self._position}/{len(self.roll_stream)})"
        )
