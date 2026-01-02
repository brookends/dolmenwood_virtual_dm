"""
Run Log system for comprehensive game event tracking.

Captures all deterministic events (dice rolls, table lookups, state transitions,
time changes) to enable observability and deterministic replay.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Callable
import json
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events that can be logged."""

    ROLL = "roll"  # Dice roll
    TRANSITION = "transition"  # State machine transition
    TABLE_LOOKUP = "table_lookup"  # Table roll/lookup
    TIME_STEP = "time_step"  # Game time advancement
    ACTION = "action"  # Player/NPC action
    ENCOUNTER = "encounter"  # Encounter generation/resolution
    CUSTOM = "custom"  # Custom event

    # Phase 4.1: New observability event types
    ORACLE = "oracle"  # Mythic GME fate checks, meaning rolls
    SPELL_ADJUDICATION = "spell_adjudication"  # Spell adjudication outcomes
    LLM_CALL = "llm_call"  # DM agent / LLM call metadata


@dataclass
class LogEvent:
    """Base class for all logged events."""

    # Note: event_type has a default to allow subclass fields with defaults
    # Subclasses set the correct value in __post_init__
    event_type: EventType = EventType.CUSTOM
    timestamp: datetime = field(default_factory=datetime.now)
    sequence_number: int = 0
    game_time: Optional[str] = None  # In-game time as string
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "sequence_number": self.sequence_number,
            "game_time": self.game_time,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogEvent":
        """Create from dictionary."""
        return cls(
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
        )


@dataclass
class RollEvent(LogEvent):
    """A dice roll event."""

    notation: str = ""  # e.g., "2d6", "1d20+5"
    rolls: list[int] = field(default_factory=list)  # Individual die results
    modifier: int = 0
    total: int = 0
    reason: str = ""  # Why this roll was made

    def __post_init__(self):
        self.event_type = EventType.ROLL

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "notation": self.notation,
                "rolls": self.rolls,
                "modifier": self.modifier,
                "total": self.total,
                "reason": self.reason,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RollEvent":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
            notation=data.get("notation", ""),
            rolls=data.get("rolls", []),
            modifier=data.get("modifier", 0),
            total=data.get("total", 0),
            reason=data.get("reason", ""),
        )

    def __str__(self) -> str:
        if self.modifier > 0:
            return f"[{self.sequence_number}] ROLL {self.notation}: {self.rolls} + {self.modifier} = {self.total} ({self.reason})"
        elif self.modifier < 0:
            return f"[{self.sequence_number}] ROLL {self.notation}: {self.rolls} - {abs(self.modifier)} = {self.total} ({self.reason})"
        return f"[{self.sequence_number}] ROLL {self.notation}: {self.rolls} = {self.total} ({self.reason})"


@dataclass
class TransitionEvent(LogEvent):
    """A state machine transition event."""

    from_state: str = ""
    to_state: str = ""
    trigger: str = ""

    def __post_init__(self):
        self.event_type = EventType.TRANSITION

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "from_state": self.from_state,
                "to_state": self.to_state,
                "trigger": self.trigger,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransitionEvent":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
            from_state=data.get("from_state", ""),
            to_state=data.get("to_state", ""),
            trigger=data.get("trigger", ""),
        )

    def __str__(self) -> str:
        return f"[{self.sequence_number}] TRANSITION {self.from_state} -> {self.to_state} (trigger: {self.trigger})"


@dataclass
class TableLookupEvent(LogEvent):
    """A table lookup/roll event."""

    table_id: str = ""
    table_name: str = ""
    roll_total: int = 0
    result_text: str = ""
    modifier_applied: int = 0

    def __post_init__(self):
        self.event_type = EventType.TABLE_LOOKUP

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "table_id": self.table_id,
                "table_name": self.table_name,
                "roll_total": self.roll_total,
                "result_text": self.result_text,
                "modifier_applied": self.modifier_applied,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableLookupEvent":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
            table_id=data.get("table_id", ""),
            table_name=data.get("table_name", ""),
            roll_total=data.get("roll_total", 0),
            result_text=data.get("result_text", ""),
            modifier_applied=data.get("modifier_applied", 0),
        )

    def __str__(self) -> str:
        mod_str = f" (mod: {self.modifier_applied:+d})" if self.modifier_applied else ""
        return f"[{self.sequence_number}] TABLE {self.table_name} [{self.roll_total}{mod_str}]: {self.result_text}"


@dataclass
class TimeStepEvent(LogEvent):
    """A game time advancement event."""

    old_time: str = ""  # Previous game time
    new_time: str = ""  # New game time
    turns_advanced: int = 0
    minutes_advanced: int = 0
    reason: str = ""

    def __post_init__(self):
        self.event_type = EventType.TIME_STEP

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "old_time": self.old_time,
                "new_time": self.new_time,
                "turns_advanced": self.turns_advanced,
                "minutes_advanced": self.minutes_advanced,
                "reason": self.reason,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeStepEvent":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
            old_time=data.get("old_time", ""),
            new_time=data.get("new_time", ""),
            turns_advanced=data.get("turns_advanced", 0),
            minutes_advanced=data.get("minutes_advanced", 0),
            reason=data.get("reason", ""),
        )

    def __str__(self) -> str:
        return f"[{self.sequence_number}] TIME {self.old_time} -> {self.new_time} (+{self.turns_advanced} turns, {self.reason})"


# =============================================================================
# Phase 4.1: New Event Types for Observability
# =============================================================================


@dataclass
class OracleEvent(LogEvent):
    """An oracle (Mythic GME) event - fate checks, meaning rolls, etc."""

    oracle_type: str = ""  # "fate_check", "meaning_roll", "random_event"
    question: str = ""  # For fate checks
    likelihood: str = ""  # For fate checks (e.g., "likely", "fifty_fifty")
    roll: int = 0  # The dice roll
    result: str = ""  # "yes", "no", "exceptional_yes", "exceptional_no"
    chaos_factor: int = 5
    meaning_action: str = ""  # For meaning rolls
    meaning_subject: str = ""  # For meaning rolls
    random_event_triggered: bool = False

    def __post_init__(self):
        self.event_type = EventType.ORACLE

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "oracle_type": self.oracle_type,
                "question": self.question,
                "likelihood": self.likelihood,
                "roll": self.roll,
                "result": self.result,
                "chaos_factor": self.chaos_factor,
                "meaning_action": self.meaning_action,
                "meaning_subject": self.meaning_subject,
                "random_event_triggered": self.random_event_triggered,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OracleEvent":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
            oracle_type=data.get("oracle_type", ""),
            question=data.get("question", ""),
            likelihood=data.get("likelihood", ""),
            roll=data.get("roll", 0),
            result=data.get("result", ""),
            chaos_factor=data.get("chaos_factor", 5),
            meaning_action=data.get("meaning_action", ""),
            meaning_subject=data.get("meaning_subject", ""),
            random_event_triggered=data.get("random_event_triggered", False),
        )

    def __str__(self) -> str:
        if self.oracle_type == "fate_check":
            event_str = " [EVENT!]" if self.random_event_triggered else ""
            return (
                f"[{self.sequence_number}] ORACLE fate_check: \"{self.question}\" "
                f"({self.likelihood}, CF={self.chaos_factor}) -> {self.result.upper()} "
                f"(roll: {self.roll}){event_str}"
            )
        elif self.oracle_type == "meaning_roll":
            return (
                f"[{self.sequence_number}] ORACLE meaning: "
                f"{self.meaning_action} + {self.meaning_subject}"
            )
        return f"[{self.sequence_number}] ORACLE {self.oracle_type}: {self.result}"


@dataclass
class SpellAdjudicationEvent(LogEvent):
    """A spell adjudication event."""

    spell_name: str = ""
    caster_id: str = ""
    adjudication_type: str = ""  # "wish", "curse_break", "divination", etc.
    success_level: str = ""  # "success", "failure", "exceptional_success", etc.
    summary: str = ""
    effects_executed: list[str] = field(default_factory=list)
    has_complication: bool = False
    meaning_pair: str = ""  # If meaning roll was involved

    def __post_init__(self):
        self.event_type = EventType.SPELL_ADJUDICATION

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "spell_name": self.spell_name,
                "caster_id": self.caster_id,
                "adjudication_type": self.adjudication_type,
                "success_level": self.success_level,
                "summary": self.summary,
                "effects_executed": self.effects_executed,
                "has_complication": self.has_complication,
                "meaning_pair": self.meaning_pair,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpellAdjudicationEvent":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
            spell_name=data.get("spell_name", ""),
            caster_id=data.get("caster_id", ""),
            adjudication_type=data.get("adjudication_type", ""),
            success_level=data.get("success_level", ""),
            summary=data.get("summary", ""),
            effects_executed=data.get("effects_executed", []),
            has_complication=data.get("has_complication", False),
            meaning_pair=data.get("meaning_pair", ""),
        )

    def __str__(self) -> str:
        complication = " [COMPLICATION]" if self.has_complication else ""
        effects = f" effects: {len(self.effects_executed)}" if self.effects_executed else ""
        return (
            f"[{self.sequence_number}] SPELL {self.spell_name} ({self.adjudication_type}): "
            f"{self.success_level}{complication}{effects}"
        )


@dataclass
class EncounterEvent(LogEvent):
    """An encounter-related event (generation, resolution, transition)."""

    encounter_type: str = ""  # "start", "resolution", "flee", "combat_start"
    encounter_id: str = ""
    creatures: list[str] = field(default_factory=list)
    outcome: str = ""  # "party_victory", "parley_success", "fled", etc.
    resolution_method: str = ""  # "combat", "parley", "flee", "evasion"

    def __post_init__(self):
        self.event_type = EventType.ENCOUNTER

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "encounter_type": self.encounter_type,
                "encounter_id": self.encounter_id,
                "creatures": self.creatures,
                "outcome": self.outcome,
                "resolution_method": self.resolution_method,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EncounterEvent":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
            encounter_type=data.get("encounter_type", ""),
            encounter_id=data.get("encounter_id", ""),
            creatures=data.get("creatures", []),
            outcome=data.get("outcome", ""),
            resolution_method=data.get("resolution_method", ""),
        )

    def __str__(self) -> str:
        creature_str = f" ({', '.join(self.creatures[:3])})" if self.creatures else ""
        outcome_str = f" -> {self.outcome}" if self.outcome else ""
        return (
            f"[{self.sequence_number}] ENCOUNTER {self.encounter_type}{creature_str}{outcome_str}"
        )


@dataclass
class LLMCallEvent(LogEvent):
    """An LLM/DM agent call event (metadata only, no secrets)."""

    call_type: str = ""  # "dialogue", "narration", "spell_interpretation", etc.
    schema_name: str = ""  # Which prompt schema was used
    success: bool = True
    latency_ms: Optional[int] = None  # Response time if available
    error_message: str = ""  # If failed
    input_summary: str = ""  # Brief summary of input (no secrets)
    output_summary: str = ""  # Brief summary of output (truncated)

    def __post_init__(self):
        self.event_type = EventType.LLM_CALL

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "call_type": self.call_type,
                "schema_name": self.schema_name,
                "success": self.success,
                "latency_ms": self.latency_ms,
                "error_message": self.error_message,
                "input_summary": self.input_summary,
                "output_summary": self.output_summary,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMCallEvent":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data.get("sequence_number", 0),
            game_time=data.get("game_time"),
            context=data.get("context", {}),
            call_type=data.get("call_type", ""),
            schema_name=data.get("schema_name", ""),
            success=data.get("success", True),
            latency_ms=data.get("latency_ms"),
            error_message=data.get("error_message", ""),
            input_summary=data.get("input_summary", ""),
            output_summary=data.get("output_summary", ""),
        )

    def __str__(self) -> str:
        status = "OK" if self.success else f"FAILED: {self.error_message[:50]}"
        latency = f" ({self.latency_ms}ms)" if self.latency_ms else ""
        return f"[{self.sequence_number}] LLM {self.call_type} [{self.schema_name}]: {status}{latency}"


class RunLog:
    """
    Central run log for all game events.

    Singleton pattern - use get_run_log() to access.
    Captures rolls, state transitions, table lookups, and time changes.
    """

    _instance: Optional["RunLog"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._events: list[LogEvent] = []
        self._sequence: int = 0
        self._seed: Optional[int] = None
        self._session_start: datetime = datetime.now()
        self._game_time_provider: Optional[Callable[[], str]] = None
        self._subscribers: list[Callable[[LogEvent], None]] = []
        self._paused: bool = False

    def reset(self) -> None:
        """Reset the log for a new session."""
        self._events = []
        self._sequence = 0
        self._session_start = datetime.now()
        logger.info("RunLog reset")

    def set_seed(self, seed: int) -> None:
        """Record the RNG seed used for this session."""
        self._seed = seed
        logger.info(f"RunLog seed set: {seed}")

    def get_seed(self) -> Optional[int]:
        """Get the RNG seed for this session."""
        return self._seed

    def set_game_time_provider(self, provider: Callable[[], str]) -> None:
        """
        Set a callback to get current game time.

        The provider should return a string like "Year 1, Month 6, Day 15, 14:30".
        """
        self._game_time_provider = provider

    def pause(self) -> None:
        """Pause logging (e.g., during replay)."""
        self._paused = True

    def resume(self) -> None:
        """Resume logging."""
        self._paused = False

    def is_paused(self) -> bool:
        """Check if logging is paused."""
        return self._paused

    def subscribe(self, callback: Callable[[LogEvent], None]) -> None:
        """Subscribe to receive events as they are logged."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[LogEvent], None]) -> None:
        """Unsubscribe from events."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _get_game_time(self) -> Optional[str]:
        """Get current game time if provider is set."""
        if self._game_time_provider:
            try:
                return self._game_time_provider()
            except Exception:
                return None
        return None

    def _log_event(self, event: LogEvent) -> None:
        """Internal method to log an event."""
        if self._paused:
            return

        self._sequence += 1
        event.sequence_number = self._sequence
        event.game_time = self._get_game_time()
        self._events.append(event)

        # Notify subscribers
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception as e:
                logger.warning(f"Subscriber error: {e}")

    def log_roll(
        self,
        notation: str,
        rolls: list[int],
        modifier: int,
        total: int,
        reason: str = "",
        context: Optional[dict[str, Any]] = None,
    ) -> RollEvent:
        """Log a dice roll."""
        event = RollEvent(
            notation=notation,
            rolls=rolls,
            modifier=modifier,
            total=total,
            reason=reason,
            context=context or {},
        )
        self._log_event(event)
        return event

    def log_transition(
        self,
        from_state: str,
        to_state: str,
        trigger: str,
        context: Optional[dict[str, Any]] = None,
    ) -> TransitionEvent:
        """Log a state transition."""
        event = TransitionEvent(
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            context=context or {},
        )
        self._log_event(event)
        return event

    def log_table_lookup(
        self,
        table_id: str,
        table_name: str,
        roll_total: int,
        result_text: str,
        modifier_applied: int = 0,
        context: Optional[dict[str, Any]] = None,
    ) -> TableLookupEvent:
        """Log a table lookup."""
        event = TableLookupEvent(
            table_id=table_id,
            table_name=table_name,
            roll_total=roll_total,
            result_text=result_text,
            modifier_applied=modifier_applied,
            context=context or {},
        )
        self._log_event(event)
        return event

    def log_time_step(
        self,
        old_time: str,
        new_time: str,
        turns_advanced: int = 0,
        minutes_advanced: int = 0,
        reason: str = "",
        context: Optional[dict[str, Any]] = None,
    ) -> TimeStepEvent:
        """Log a time advancement."""
        event = TimeStepEvent(
            old_time=old_time,
            new_time=new_time,
            turns_advanced=turns_advanced,
            minutes_advanced=minutes_advanced,
            reason=reason,
            context=context or {},
        )
        self._log_event(event)
        return event

    def log_custom(
        self,
        event_name: str,
        details: dict[str, Any],
    ) -> LogEvent:
        """Log a custom event."""
        event = LogEvent(
            event_type=EventType.CUSTOM,
            context={"event_name": event_name, **details},
        )
        self._log_event(event)
        return event

    # -------------------------------------------------------------------------
    # Phase 4.1: New Observability Logging Methods
    # -------------------------------------------------------------------------

    def log_oracle(
        self,
        oracle_type: str,
        question: str = "",
        likelihood: str = "",
        roll: int = 0,
        result: str = "",
        chaos_factor: int = 5,
        meaning_action: str = "",
        meaning_subject: str = "",
        random_event_triggered: bool = False,
        context: Optional[dict[str, Any]] = None,
    ) -> OracleEvent:
        """Log an oracle (Mythic GME) event."""
        event = OracleEvent(
            oracle_type=oracle_type,
            question=question,
            likelihood=likelihood,
            roll=roll,
            result=result,
            chaos_factor=chaos_factor,
            meaning_action=meaning_action,
            meaning_subject=meaning_subject,
            random_event_triggered=random_event_triggered,
            context=context or {},
        )
        self._log_event(event)
        return event

    def log_spell_adjudication(
        self,
        spell_name: str,
        caster_id: str,
        adjudication_type: str,
        success_level: str,
        summary: str = "",
        effects_executed: Optional[list[str]] = None,
        has_complication: bool = False,
        meaning_pair: str = "",
        context: Optional[dict[str, Any]] = None,
    ) -> SpellAdjudicationEvent:
        """Log a spell adjudication event."""
        event = SpellAdjudicationEvent(
            spell_name=spell_name,
            caster_id=caster_id,
            adjudication_type=adjudication_type,
            success_level=success_level,
            summary=summary,
            effects_executed=effects_executed or [],
            has_complication=has_complication,
            meaning_pair=meaning_pair,
            context=context or {},
        )
        self._log_event(event)
        return event

    def log_encounter(
        self,
        encounter_type: str,
        encounter_id: str = "",
        creatures: Optional[list[str]] = None,
        outcome: str = "",
        resolution_method: str = "",
        context: Optional[dict[str, Any]] = None,
    ) -> EncounterEvent:
        """Log an encounter event."""
        event = EncounterEvent(
            encounter_type=encounter_type,
            encounter_id=encounter_id,
            creatures=creatures or [],
            outcome=outcome,
            resolution_method=resolution_method,
            context=context or {},
        )
        self._log_event(event)
        return event

    def log_llm_call(
        self,
        call_type: str,
        schema_name: str = "",
        success: bool = True,
        latency_ms: Optional[int] = None,
        error_message: str = "",
        input_summary: str = "",
        output_summary: str = "",
        context: Optional[dict[str, Any]] = None,
    ) -> LLMCallEvent:
        """Log an LLM/DM agent call event."""
        event = LLMCallEvent(
            call_type=call_type,
            schema_name=schema_name,
            success=success,
            latency_ms=latency_ms,
            error_message=error_message,
            input_summary=input_summary,
            output_summary=output_summary,
            context=context or {},
        )
        self._log_event(event)
        return event

    def get_events(
        self,
        event_type: Optional[EventType] = None,
        since_sequence: int = 0,
    ) -> list[LogEvent]:
        """
        Get logged events.

        Args:
            event_type: Filter by event type (None = all)
            since_sequence: Only events after this sequence number

        Returns:
            List of events
        """
        events = [e for e in self._events if e.sequence_number > since_sequence]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    def get_rolls(self) -> list[RollEvent]:
        """Get all roll events."""
        return [e for e in self._events if isinstance(e, RollEvent)]

    def get_transitions(self) -> list[TransitionEvent]:
        """Get all transition events."""
        return [e for e in self._events if isinstance(e, TransitionEvent)]

    def get_table_lookups(self) -> list[TableLookupEvent]:
        """Get all table lookup events."""
        return [e for e in self._events if isinstance(e, TableLookupEvent)]

    def get_time_steps(self) -> list[TimeStepEvent]:
        """Get all time step events."""
        return [e for e in self._events if isinstance(e, TimeStepEvent)]

    def get_oracle_events(self) -> list[OracleEvent]:
        """Get all oracle events."""
        return [e for e in self._events if isinstance(e, OracleEvent)]

    def get_spell_adjudications(self) -> list[SpellAdjudicationEvent]:
        """Get all spell adjudication events."""
        return [e for e in self._events if isinstance(e, SpellAdjudicationEvent)]

    def get_encounter_events(self) -> list[EncounterEvent]:
        """Get all encounter events."""
        return [e for e in self._events if isinstance(e, EncounterEvent)]

    def get_llm_calls(self) -> list[LLMCallEvent]:
        """Get all LLM call events."""
        return [e for e in self._events if isinstance(e, LLMCallEvent)]

    def get_roll_stream(self) -> list[dict[str, Any]]:
        """
        Get the roll stream for replay.

        Returns a list of {notation, rolls, modifier, total} for each roll.
        This can be used to replay the exact sequence of rolls.
        """
        return [
            {
                "notation": e.notation,
                "rolls": e.rolls,
                "modifier": e.modifier,
                "total": e.total,
                "reason": e.reason,
            }
            for e in self.get_rolls()
        ]

    def get_event_count(self) -> int:
        """Get total number of logged events."""
        return len(self._events)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the run log."""
        return {
            "session_start": self._session_start.isoformat(),
            "seed": self._seed,
            "total_events": len(self._events),
            "rolls": len(self.get_rolls()),
            "transitions": len(self.get_transitions()),
            "table_lookups": len(self.get_table_lookups()),
            "time_steps": len(self.get_time_steps()),
            # Phase 4.1: New event counts
            "oracle_events": len(self.get_oracle_events()),
            "spell_adjudications": len(self.get_spell_adjudications()),
            "encounter_events": len(self.get_encounter_events()),
            "llm_calls": len(self.get_llm_calls()),
            "last_sequence": self._sequence,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire log to a dictionary."""
        return {
            "session_start": self._session_start.isoformat(),
            "seed": self._seed,
            "sequence": self._sequence,
            "events": [e.to_dict() for e in self._events],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the log to JSON."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def save(self, filepath: str) -> None:
        """Save the log to a file."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        logger.info(f"RunLog saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> "RunLog":
        """Load a log from a file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        log = get_run_log()
        log.reset()
        log._session_start = datetime.fromisoformat(data["session_start"])
        log._seed = data.get("seed")
        log._sequence = data.get("sequence", 0)

        # Reconstruct events
        for event_data in data.get("events", []):
            event_type = EventType(event_data["event_type"])
            event: LogEvent
            if event_type == EventType.ROLL:
                event = RollEvent.from_dict(event_data)
            elif event_type == EventType.TRANSITION:
                event = TransitionEvent.from_dict(event_data)
            elif event_type == EventType.TABLE_LOOKUP:
                event = TableLookupEvent.from_dict(event_data)
            elif event_type == EventType.TIME_STEP:
                event = TimeStepEvent.from_dict(event_data)
            elif event_type == EventType.ORACLE:
                event = OracleEvent.from_dict(event_data)
            elif event_type == EventType.SPELL_ADJUDICATION:
                event = SpellAdjudicationEvent.from_dict(event_data)
            elif event_type == EventType.ENCOUNTER:
                event = EncounterEvent.from_dict(event_data)
            elif event_type == EventType.LLM_CALL:
                event = LLMCallEvent.from_dict(event_data)
            else:
                event = LogEvent.from_dict(event_data)
            log._events.append(event)

        logger.info(f"RunLog loaded from {filepath}: {len(log._events)} events")
        return log

    def format_log(
        self,
        event_types: Optional[list[EventType]] = None,
        max_events: Optional[int] = None,
    ) -> str:
        """
        Format the log as a human-readable string.

        Args:
            event_types: Filter by event types (None = all)
            max_events: Maximum number of events to include

        Returns:
            Formatted log string
        """
        lines = [
            f"=== Run Log ===",
            f"Session: {self._session_start.isoformat()}",
            f"Seed: {self._seed or 'not set'}",
            f"Total Events: {len(self._events)}",
            "",
        ]

        events = self._events
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        if max_events:
            events = events[-max_events:]

        for event in events:
            lines.append(str(event))

        return "\n".join(lines)

    def print_log(
        self,
        event_types: Optional[list[EventType]] = None,
        max_events: int = 50,
    ) -> None:
        """Print a formatted log to stdout."""
        print(self.format_log(event_types, max_events))


# Singleton access
_run_log: Optional[RunLog] = None


def get_run_log() -> RunLog:
    """Get the global RunLog instance."""
    global _run_log
    if _run_log is None:
        _run_log = RunLog()
    return _run_log


def reset_run_log() -> RunLog:
    """Reset and return the global RunLog instance."""
    log = get_run_log()
    log.reset()
    return log
