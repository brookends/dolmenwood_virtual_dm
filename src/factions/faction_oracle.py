"""
Faction-scoped Mythic GME oracle integration.

Provides structured oracle functionality for the faction system:
- Random events for action complications
- Fate checks for contested territory
- Detail checks for party work twists

Oracle results are structured data, not invented facts. The LLM narrator
(if enabled) interprets the meaning pairs into narrative context.

Key principle: Oracle generates prompts/twists, not canonical world facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.oracle.dice_rng_adapter import DiceRngAdapter
from src.oracle.mythic_gme import (
    MythicGME,
    Likelihood,
    FateResult,
    RandomEventFocus,
)


class OracleEventKind(str, Enum):
    """Types of oracle events."""
    RANDOM_EVENT = "random_event"
    FATE_CHECK = "fate_check"
    DETAIL_CHECK = "detail_check"


@dataclass
class OracleEvent:
    """
    Structured record of an oracle outcome.

    This is stored data that can be surfaced offline. It contains
    tokens for interpretation, not invented narrative facts.
    """
    kind: OracleEventKind
    date: str  # ISO date or game date string
    tag: str  # Context tag (e.g., "action_complication", "contested_territory")

    # Optional context
    faction_id: Optional[str] = None
    question: Optional[str] = None  # For fate checks

    # Fate check results
    result: Optional[str] = None  # yes/no/exceptional_yes/exceptional_no
    likelihood: Optional[str] = None  # Likelihood enum value
    roll: Optional[int] = None  # The d100 roll

    # Random/detail event results
    focus: Optional[str] = None  # RandomEventFocus value
    action: Optional[str] = None  # Action meaning word
    subject: Optional[str] = None  # Subject meaning word

    # State at time of event
    chaos_factor: int = 5

    def to_dict(self) -> dict[str, Any]:
        """Serialize for persistence."""
        return {
            "kind": self.kind.value,
            "date": self.date,
            "tag": self.tag,
            "faction_id": self.faction_id,
            "question": self.question,
            "result": self.result,
            "likelihood": self.likelihood,
            "roll": self.roll,
            "focus": self.focus,
            "action": self.action,
            "subject": self.subject,
            "chaos_factor": self.chaos_factor,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OracleEvent":
        """Deserialize from persistence."""
        return cls(
            kind=OracleEventKind(data.get("kind", "random_event")),
            date=data.get("date", ""),
            tag=data.get("tag", ""),
            faction_id=data.get("faction_id"),
            question=data.get("question"),
            result=data.get("result"),
            likelihood=data.get("likelihood"),
            roll=data.get("roll"),
            focus=data.get("focus"),
            action=data.get("action"),
            subject=data.get("subject"),
            chaos_factor=data.get("chaos_factor", 5),
        )

    @property
    def meaning_pair(self) -> str:
        """Get the action/subject meaning pair as a string."""
        if self.action and self.subject:
            return f"{self.action} {self.subject}"
        return ""

    def as_rumor_text(self) -> str:
        """Format as a rumor/news item for offline display."""
        if self.kind == OracleEventKind.RANDOM_EVENT:
            focus_str = self.focus.replace("_", " ").title() if self.focus else "Event"
            return f"Mythic Event ({focus_str}): {self.meaning_pair} (interpretation needed)"
        elif self.kind == OracleEventKind.FATE_CHECK:
            result_str = self.result.replace("_", " ").title() if self.result else "Unknown"
            return f"Mythic Fate ({self.tag}): {result_str} - {self.question or 'Contested outcome'}"
        elif self.kind == OracleEventKind.DETAIL_CHECK:
            return f"Mythic Twist ({self.tag}): {self.meaning_pair} (interpretation needed)"
        return f"Oracle: {self.tag}"


@dataclass
class FactionOracleState:
    """
    Persisted oracle state for the faction system.

    Tracks chaos factor and event history across sessions.
    """
    chaos_factor: int = 5
    events_this_cycle: int = 0
    total_events: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize for persistence."""
        return {
            "chaos_factor": self.chaos_factor,
            "events_this_cycle": self.events_this_cycle,
            "total_events": self.total_events,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FactionOracleState":
        """Deserialize from persistence."""
        return cls(
            chaos_factor=data.get("chaos_factor", 5),
            events_this_cycle=data.get("events_this_cycle", 0),
            total_events=data.get("total_events", 0),
        )


@dataclass
class FactionOracleConfig:
    """Configuration for faction oracle behavior."""
    enabled: bool = True
    default_chaos_factor: int = 5
    auto_random_event_on_complication: bool = True
    contested_territory_enabled: bool = True
    party_work_twists_enabled: bool = True
    party_work_twist_on_extremes: bool = True  # Trigger on 2 or 12

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "FactionOracleConfig":
        """Create config from faction_rules.json oracle block."""
        if not data:
            return cls()  # Defaults

        contested = data.get("contested_territory", {})
        party_work = data.get("party_work_twists", {})

        return cls(
            enabled=data.get("enabled", True),
            default_chaos_factor=data.get("default_chaos_factor", 5),
            auto_random_event_on_complication=data.get(
                "auto_random_event_on_complication", True
            ),
            contested_territory_enabled=contested.get("enabled", True),
            party_work_twists_enabled=party_work.get("enabled", True),
            party_work_twist_on_extremes=party_work.get("on_extremes", True),
        )


class FactionOracle:
    """
    Faction-scoped oracle wrapper for MythicGME.

    Provides methods tailored to faction system needs while ensuring
    all randomness goes through the deterministic DiceRoller.

    Usage:
        oracle = FactionOracle()
        event = oracle.random_event(
            date="1420-05-15",
            faction_id="nag_lord",
            tag="action_complication"
        )
        print(event.meaning_pair)  # e.g., "Pursue Knowledge"
    """

    def __init__(
        self,
        config: Optional[FactionOracleConfig] = None,
        state: Optional[FactionOracleState] = None,
    ):
        """
        Initialize the faction oracle.

        Args:
            config: Optional configuration (defaults apply if None)
            state: Optional persisted state to restore
        """
        self.config = config or FactionOracleConfig()
        self.state = state or FactionOracleState(
            chaos_factor=self.config.default_chaos_factor
        )

        # Create deterministic MythicGME with DiceRoller adapter
        self._rng_adapter = DiceRngAdapter(reason_prefix="FactionOracle")
        self._mythic = MythicGME(
            chaos_factor=self.state.chaos_factor,
            rng=self._rng_adapter,
        )

        # Event log for current session (not persisted, just for reference)
        self._session_events: list[OracleEvent] = []

    @property
    def chaos_factor(self) -> int:
        """Get current chaos factor."""
        return self._mythic.get_chaos_factor()

    def set_chaos_factor(self, value: int, reason: str = "") -> int:
        """Set chaos factor directly."""
        new_value = self._mythic.set_chaos_factor(value, reason)
        self.state.chaos_factor = new_value
        return new_value

    def increase_chaos(self, reason: str = "") -> int:
        """Increase chaos factor by 1."""
        new_value = self._mythic.chaos.increase(reason)
        self.state.chaos_factor = new_value
        return new_value

    def decrease_chaos(self, reason: str = "") -> int:
        """Decrease chaos factor by 1."""
        new_value = self._mythic.chaos.decrease(reason)
        self.state.chaos_factor = new_value
        return new_value

    def random_event(
        self,
        date: str,
        faction_id: Optional[str] = None,
        tag: str = "random_event",
    ) -> OracleEvent:
        """
        Generate a random event with focus and meaning pair.

        Use for action complications or other unexpected twists.

        Args:
            date: Current game date for the event record
            faction_id: Optional faction context
            tag: Event category (e.g., "action_complication")

        Returns:
            OracleEvent with focus and action/subject meanings
        """
        if not self.config.enabled:
            # Return a minimal event when disabled
            return OracleEvent(
                kind=OracleEventKind.RANDOM_EVENT,
                date=date,
                tag=tag,
                faction_id=faction_id,
                chaos_factor=self.chaos_factor,
                focus="disabled",
                action="oracle",
                subject="disabled",
            )

        event = self._mythic.generate_random_event()

        oracle_event = OracleEvent(
            kind=OracleEventKind.RANDOM_EVENT,
            date=date,
            tag=tag,
            faction_id=faction_id,
            chaos_factor=self.chaos_factor,
            focus=event.focus.value,
            action=event.action,
            subject=event.subject,
        )

        self._record_event(oracle_event)
        return oracle_event

    def detail_check(
        self,
        date: str,
        faction_id: Optional[str] = None,
        tag: str = "detail_check",
    ) -> OracleEvent:
        """
        Roll for detail meanings (action/subject pair).

        Use when you need "what kind" or "how" rather than yes/no.
        Good for party work twists and other narrative details.

        Args:
            date: Current game date
            faction_id: Optional faction context
            tag: Event category (e.g., "party_work_twist")

        Returns:
            OracleEvent with action/subject meanings
        """
        if not self.config.enabled:
            return OracleEvent(
                kind=OracleEventKind.DETAIL_CHECK,
                date=date,
                tag=tag,
                faction_id=faction_id,
                chaos_factor=self.chaos_factor,
                action="oracle",
                subject="disabled",
            )

        meaning = self._mythic.detail_check()

        oracle_event = OracleEvent(
            kind=OracleEventKind.DETAIL_CHECK,
            date=date,
            tag=tag,
            faction_id=faction_id,
            chaos_factor=self.chaos_factor,
            action=meaning.action,
            subject=meaning.subject,
        )

        self._record_event(oracle_event)
        return oracle_event

    def fate_check(
        self,
        question: str,
        likelihood: Likelihood,
        date: str,
        faction_id: Optional[str] = None,
        tag: str = "fate_check",
    ) -> OracleEvent:
        """
        Perform a Yes/No fate check.

        Use for contested territory claims and other binary decisions.

        Args:
            question: The yes/no question being asked
            likelihood: How likely is "yes"?
            date: Current game date
            faction_id: Optional faction context
            tag: Event category (e.g., "contested_territory")

        Returns:
            OracleEvent with result (yes/no/exceptional variants)
        """
        if not self.config.enabled:
            return OracleEvent(
                kind=OracleEventKind.FATE_CHECK,
                date=date,
                tag=tag,
                faction_id=faction_id,
                question=question,
                result="no",  # Default to no when disabled
                likelihood=likelihood.name,
                chaos_factor=self.chaos_factor,
            )

        result = self._mythic.fate_check(question, likelihood, check_for_event=False)

        oracle_event = OracleEvent(
            kind=OracleEventKind.FATE_CHECK,
            date=date,
            tag=tag,
            faction_id=faction_id,
            question=question,
            result=result.result.value,
            likelihood=likelihood.name,
            roll=result.roll,
            chaos_factor=self.chaos_factor,
        )

        self._record_event(oracle_event)
        return oracle_event

    def _record_event(self, event: OracleEvent) -> None:
        """Record an event in session log and update counters."""
        self._session_events.append(event)
        self.state.events_this_cycle += 1
        self.state.total_events += 1

    def reset_cycle_counter(self) -> None:
        """Reset the events_this_cycle counter (call at cycle start)."""
        self.state.events_this_cycle = 0

    def get_session_events(self) -> list[OracleEvent]:
        """Get all events from current session."""
        return list(self._session_events)

    def clear_session_events(self) -> None:
        """Clear session event log."""
        self._session_events.clear()

    # =========================================================================
    # FACTION-SPECIFIC HELPERS
    # =========================================================================

    def determine_contest_likelihood(
        self,
        attacker_level: int,
        defender_level: int,
        relationship_score: int,
    ) -> Likelihood:
        """
        Determine likelihood for contested territory fate check.

        Based on level difference and relationship:
        - Higher level attacker = more likely to succeed
        - Negative relationship = more likely (they're enemies)
        - Positive relationship = less likely (they're allies)

        Args:
            attacker_level: Attacking faction's level (1-4)
            defender_level: Defending faction's level (1-4)
            relationship_score: From FactionRelations (-100 to +100)

        Returns:
            Likelihood enum for the fate check
        """
        # Level difference: +1 per level advantage
        level_diff = attacker_level - defender_level

        # Relationship: negative = hostile = easier to attack
        # Scale from -100..+100 to -2..+2
        rel_modifier = -relationship_score // 50  # -100 -> +2, +100 -> -2

        # Combined modifier
        total_modifier = level_diff + rel_modifier

        # Map to likelihood
        if total_modifier >= 3:
            return Likelihood.VERY_LIKELY
        elif total_modifier >= 1:
            return Likelihood.LIKELY
        elif total_modifier >= -1:
            return Likelihood.FIFTY_FIFTY
        elif total_modifier >= -2:
            return Likelihood.UNLIKELY
        else:
            return Likelihood.VERY_UNLIKELY

    def is_yes(self, event: OracleEvent) -> bool:
        """Check if a fate check event resulted in yes."""
        return event.result in ("yes", "exceptional_yes")

    def is_exceptional(self, event: OracleEvent) -> bool:
        """Check if a fate check event was exceptional."""
        return event.result in ("exceptional_yes", "exceptional_no")

    def is_exceptional_yes(self, event: OracleEvent) -> bool:
        """Check if result was exceptional yes."""
        return event.result == "exceptional_yes"

    def is_exceptional_no(self, event: OracleEvent) -> bool:
        """Check if result was exceptional no."""
        return event.result == "exceptional_no"

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for persistence."""
        return {
            "state": self.state.to_dict(),
            "mythic": self._mythic.to_dict(),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """Restore state from persistence."""
        if "state" in data:
            self.state = FactionOracleState.from_dict(data["state"])
        if "mythic" in data:
            self._mythic.from_dict(data["mythic"])
            self.state.chaos_factor = self._mythic.get_chaos_factor()


# Convenience function for creating oracle with config
def create_faction_oracle(
    config_data: Optional[dict[str, Any]] = None,
    state_data: Optional[dict[str, Any]] = None,
) -> FactionOracle:
    """
    Create a FactionOracle from config and state dicts.

    Args:
        config_data: Oracle config from faction_rules.json
        state_data: Persisted oracle state

    Returns:
        Configured FactionOracle instance
    """
    config = FactionOracleConfig.from_dict(config_data)
    state = FactionOracleState.from_dict(state_data) if state_data else None
    return FactionOracle(config=config, state=state)
