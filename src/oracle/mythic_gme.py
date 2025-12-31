"""
Mythic GME 2e Integration for Dolmenwood Virtual DM.

Implements the core Mythic Game Master Emulator mechanics:
- Fate Check: Yes/No oracle with probability gradients
- Random Events: Unexpected occurrences triggered by dice
- Meaning Tables: Word pairs for interpretation
- Chaos Factor: Escalating unpredictability

This module provides the oracle layer for Tier 4 spell resolution,
answering uncertain questions that require "referee discretion."

Reference: Mythic Game Master Emulator 2nd Edition by Tana Pigeon
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Optional, Callable
import random


# =============================================================================
# ENUMS
# =============================================================================


class Likelihood(IntEnum):
    """
    Probability modifiers for Fate Check.

    Values represent the column index in the Fate Chart.
    Higher values = more likely to be YES.
    """
    IMPOSSIBLE = 0
    NO_WAY = 1
    VERY_UNLIKELY = 2
    UNLIKELY = 3
    FIFTY_FIFTY = 4
    LIKELY = 5
    VERY_LIKELY = 6
    NEAR_SURE_THING = 7
    A_SURE_THING = 8
    HAS_TO_BE = 9


class FateResult(str, Enum):
    """Possible outcomes of a Fate Check."""
    EXCEPTIONAL_YES = "exceptional_yes"
    YES = "yes"
    NO = "no"
    EXCEPTIONAL_NO = "exceptional_no"


class RandomEventFocus(str, Enum):
    """What a Random Event relates to."""
    REMOTE_EVENT = "remote_event"
    AMBIGUOUS_EVENT = "ambiguous_event"
    NEW_NPC = "new_npc"
    NPC_ACTION = "npc_action"
    NPC_NEGATIVE = "npc_negative"
    NPC_POSITIVE = "npc_positive"
    MOVE_TOWARD_THREAD = "move_toward_thread"
    MOVE_AWAY_FROM_THREAD = "move_away_from_thread"
    CLOSE_THREAD = "close_thread"
    PC_NEGATIVE = "pc_negative"
    PC_POSITIVE = "pc_positive"


# =============================================================================
# FATE CHART (Mythic GME 2e)
# =============================================================================

# The Fate Chart: rows = Chaos Factor (1-9), columns = Likelihood (0-9)
# Each cell contains (exceptional_yes_threshold, yes_threshold, no_threshold, exceptional_no_threshold)
# Roll d100: <= exceptional_yes = Exceptional Yes, <= yes = Yes, > no = No, > exceptional_no = Exceptional No

FATE_CHART = {
    # Chaos Factor 1 (very stable)
    1: {
        Likelihood.IMPOSSIBLE: (0, 0, 77, 100),
        Likelihood.NO_WAY: (0, 5, 82, 100),
        Likelihood.VERY_UNLIKELY: (1, 10, 87, 100),
        Likelihood.UNLIKELY: (2, 15, 92, 100),
        Likelihood.FIFTY_FIFTY: (3, 25, 97, 100),
        Likelihood.LIKELY: (5, 35, 100, 100),
        Likelihood.VERY_LIKELY: (7, 45, 100, 100),
        Likelihood.NEAR_SURE_THING: (10, 55, 100, 100),
        Likelihood.A_SURE_THING: (15, 65, 100, 100),
        Likelihood.HAS_TO_BE: (20, 85, 100, 100),
    },
    # Chaos Factor 2
    2: {
        Likelihood.IMPOSSIBLE: (0, 0, 73, 100),
        Likelihood.NO_WAY: (0, 5, 78, 100),
        Likelihood.VERY_UNLIKELY: (1, 10, 83, 100),
        Likelihood.UNLIKELY: (2, 20, 88, 100),
        Likelihood.FIFTY_FIFTY: (4, 30, 93, 100),
        Likelihood.LIKELY: (6, 40, 98, 100),
        Likelihood.VERY_LIKELY: (8, 50, 100, 100),
        Likelihood.NEAR_SURE_THING: (11, 60, 100, 100),
        Likelihood.A_SURE_THING: (16, 70, 100, 100),
        Likelihood.HAS_TO_BE: (21, 90, 100, 100),
    },
    # Chaos Factor 3
    3: {
        Likelihood.IMPOSSIBLE: (0, 0, 69, 97),
        Likelihood.NO_WAY: (0, 5, 74, 98),
        Likelihood.VERY_UNLIKELY: (2, 10, 79, 99),
        Likelihood.UNLIKELY: (3, 20, 84, 100),
        Likelihood.FIFTY_FIFTY: (5, 35, 89, 100),
        Likelihood.LIKELY: (7, 45, 94, 100),
        Likelihood.VERY_LIKELY: (9, 55, 99, 100),
        Likelihood.NEAR_SURE_THING: (12, 65, 100, 100),
        Likelihood.A_SURE_THING: (17, 75, 100, 100),
        Likelihood.HAS_TO_BE: (22, 95, 100, 100),
    },
    # Chaos Factor 4
    4: {
        Likelihood.IMPOSSIBLE: (0, 0, 65, 93),
        Likelihood.NO_WAY: (1, 5, 70, 95),
        Likelihood.VERY_UNLIKELY: (2, 15, 75, 97),
        Likelihood.UNLIKELY: (4, 25, 80, 99),
        Likelihood.FIFTY_FIFTY: (6, 40, 85, 100),
        Likelihood.LIKELY: (8, 50, 90, 100),
        Likelihood.VERY_LIKELY: (10, 60, 95, 100),
        Likelihood.NEAR_SURE_THING: (13, 70, 100, 100),
        Likelihood.A_SURE_THING: (18, 80, 100, 100),
        Likelihood.HAS_TO_BE: (23, 100, 100, 100),
    },
    # Chaos Factor 5 (default/balanced)
    5: {
        Likelihood.IMPOSSIBLE: (0, 2, 62, 90),
        Likelihood.NO_WAY: (1, 7, 67, 92),
        Likelihood.VERY_UNLIKELY: (3, 17, 72, 95),
        Likelihood.UNLIKELY: (5, 27, 77, 97),
        Likelihood.FIFTY_FIFTY: (7, 42, 82, 99),
        Likelihood.LIKELY: (9, 52, 87, 100),
        Likelihood.VERY_LIKELY: (11, 62, 92, 100),
        Likelihood.NEAR_SURE_THING: (14, 72, 97, 100),
        Likelihood.A_SURE_THING: (19, 82, 100, 100),
        Likelihood.HAS_TO_BE: (24, 100, 100, 100),
    },
    # Chaos Factor 6
    6: {
        Likelihood.IMPOSSIBLE: (0, 4, 58, 86),
        Likelihood.NO_WAY: (2, 9, 63, 89),
        Likelihood.VERY_UNLIKELY: (4, 19, 68, 92),
        Likelihood.UNLIKELY: (6, 29, 73, 95),
        Likelihood.FIFTY_FIFTY: (8, 44, 78, 98),
        Likelihood.LIKELY: (10, 54, 83, 100),
        Likelihood.VERY_LIKELY: (12, 64, 88, 100),
        Likelihood.NEAR_SURE_THING: (15, 74, 93, 100),
        Likelihood.A_SURE_THING: (20, 84, 98, 100),
        Likelihood.HAS_TO_BE: (25, 100, 100, 100),
    },
    # Chaos Factor 7
    7: {
        Likelihood.IMPOSSIBLE: (1, 6, 54, 82),
        Likelihood.NO_WAY: (3, 11, 59, 86),
        Likelihood.VERY_UNLIKELY: (5, 21, 64, 89),
        Likelihood.UNLIKELY: (7, 31, 69, 93),
        Likelihood.FIFTY_FIFTY: (9, 46, 74, 96),
        Likelihood.LIKELY: (11, 56, 79, 99),
        Likelihood.VERY_LIKELY: (13, 66, 84, 100),
        Likelihood.NEAR_SURE_THING: (16, 76, 89, 100),
        Likelihood.A_SURE_THING: (21, 86, 94, 100),
        Likelihood.HAS_TO_BE: (26, 100, 100, 100),
    },
    # Chaos Factor 8
    8: {
        Likelihood.IMPOSSIBLE: (2, 8, 50, 78),
        Likelihood.NO_WAY: (4, 13, 55, 83),
        Likelihood.VERY_UNLIKELY: (6, 23, 60, 86),
        Likelihood.UNLIKELY: (8, 33, 65, 91),
        Likelihood.FIFTY_FIFTY: (10, 48, 70, 94),
        Likelihood.LIKELY: (12, 58, 75, 97),
        Likelihood.VERY_LIKELY: (14, 68, 80, 100),
        Likelihood.NEAR_SURE_THING: (17, 78, 85, 100),
        Likelihood.A_SURE_THING: (22, 88, 90, 100),
        Likelihood.HAS_TO_BE: (27, 100, 100, 100),
    },
    # Chaos Factor 9 (maximum chaos)
    9: {
        Likelihood.IMPOSSIBLE: (3, 10, 46, 74),
        Likelihood.NO_WAY: (5, 15, 51, 79),
        Likelihood.VERY_UNLIKELY: (7, 25, 56, 83),
        Likelihood.UNLIKELY: (9, 35, 61, 88),
        Likelihood.FIFTY_FIFTY: (11, 50, 66, 92),
        Likelihood.LIKELY: (13, 60, 71, 95),
        Likelihood.VERY_LIKELY: (15, 70, 76, 98),
        Likelihood.NEAR_SURE_THING: (18, 80, 81, 100),
        Likelihood.A_SURE_THING: (23, 90, 86, 100),
        Likelihood.HAS_TO_BE: (28, 100, 100, 100),
    },
}


# =============================================================================
# MEANING TABLES
# =============================================================================

# Action meanings (verbs/actions) - used for "what is happening"
ACTION_MEANINGS = [
    "Attainment", "Starting", "Neglect", "Fight", "Recruit",
    "Triumph", "Violate", "Oppose", "Malice", "Communicate",
    "Persecute", "Increase", "Decrease", "Abandon", "Gratify",
    "Inquire", "Antagonize", "Move", "Waste", "Truce",
    "Release", "Befriend", "Judge", "Desert", "Dominate",
    "Procrastinate", "Praise", "Separate", "Take", "Break",
    "Heal", "Delay", "Stop", "Lie", "Return",
    "Immitate", "Struggle", "Inform", "Bestow", "Postpone",
    "Expose", "Haggle", "Imprison", "Release", "Celebrate",
    "Develop", "Travel", "Block", "Harm", "Debase",
    "Overindulge", "Adjourn", "Adversity", "Kill", "Disrupt",
    "Usurp", "Create", "Betray", "Agree", "Abuse",
    "Oppress", "Inspect", "Ambush", "Spy", "Attach",
    "Carry", "Open", "Carelessness", "Ruin", "Extravagance",
    "Trick", "Arrive", "Propose", "Divide", "Refuse",
    "Mistrust", "Deceive", "Cruelty", "Intolerance", "Trust",
    "Excitement", "Activity", "Assist", "Care", "Negligence",
    "Passion", "Work", "Control", "Attract", "Failure",
    "Pursue", "Vengeance", "Proceedings", "Dispute", "Punish",
    "Guide", "Transform", "Overthrow", "Oppress", "Change",
]

# Subject meanings (nouns/concepts) - used for "what is it about"
SUBJECT_MEANINGS = [
    "Goals", "Dreams", "Environment", "Outside", "Inside",
    "Reality", "Allies", "Enemies", "Evil", "Good",
    "Emotions", "Opposition", "War", "Peace", "The innocent",
    "Love", "The spiritual", "The intellectual", "New ideas", "Joy",
    "Messages", "Energy", "Balance", "Tension", "Friendship",
    "The physical", "A project", "Pleasures", "Pain", "Possessions",
    "Benefits", "Plans", "Lies", "Expectations", "Legal matters",
    "Bureaucracy", "Business", "A path", "News", "Exterior factors",
    "Advice", "A plot", "Competition", "Prison", "Illness",
    "Food", "Attention", "Success", "Failure", "Travel",
    "Jealousy", "Dispute", "Home", "Investment", "Suffering",
    "Wishes", "Tactics", "Stalemate", "Randomness", "Misfortune",
    "Death", "Disruption", "Power", "A burden", "Intrigues",
    "Fears", "Ambush", "Rumor", "Wounds", "Extravagance",
    "A representative", "Adversities", "Opulence", "Liberty", "Military",
    "The mundane", "Trials", "Masses", "Vehicle", "Art",
    "Victory", "Dispute", "Riches", "Status quo", "Technology",
    "Hope", "Magic", "Illusions", "Portals", "Danger",
    "Weapons", "Animals", "Weather", "Elements", "Nature",
    "The public", "Leadership", "Fame", "Anger", "Information",
]

# Random Event Focus table (d100)
RANDOM_EVENT_FOCUS_TABLE = [
    (1, 7, RandomEventFocus.REMOTE_EVENT),
    (8, 28, RandomEventFocus.NPC_ACTION),
    (29, 35, RandomEventFocus.NEW_NPC),
    (36, 45, RandomEventFocus.MOVE_TOWARD_THREAD),
    (46, 52, RandomEventFocus.MOVE_AWAY_FROM_THREAD),
    (53, 55, RandomEventFocus.CLOSE_THREAD),
    (56, 67, RandomEventFocus.PC_NEGATIVE),
    (68, 75, RandomEventFocus.PC_POSITIVE),
    (76, 83, RandomEventFocus.AMBIGUOUS_EVENT),
    (84, 90, RandomEventFocus.NPC_NEGATIVE),
    (91, 100, RandomEventFocus.NPC_POSITIVE),
]


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class FateCheckResult:
    """Result of a Fate Check."""

    question: str
    likelihood: Likelihood
    chaos_factor: int
    roll: int
    result: FateResult

    # Thresholds used
    exceptional_yes_threshold: int = 0
    yes_threshold: int = 0
    no_threshold: int = 0
    exceptional_no_threshold: int = 0

    # Random event (if triggered)
    random_event_triggered: bool = False
    random_event: Optional["RandomEvent"] = None

    def __str__(self) -> str:
        result_str = self.result.value.replace("_", " ").title()
        s = f"Fate Check: '{self.question}' ({self.likelihood.name}) = {result_str} (rolled {self.roll})"
        if self.random_event_triggered:
            s += f" [Random Event: {self.random_event}]"
        return s


@dataclass
class RandomEvent:
    """A randomly triggered event."""

    focus: RandomEventFocus
    action: str
    subject: str
    focus_roll: int = 0
    action_roll: int = 0
    subject_roll: int = 0

    def __str__(self) -> str:
        return f"{self.focus.value}: {self.action} + {self.subject}"

    @property
    def meaning_pair(self) -> str:
        """Return the action + subject as a meaning pair."""
        return f"{self.action} {self.subject}"


@dataclass
class MeaningRoll:
    """Result of a Meaning Table roll."""

    action: str
    subject: str
    action_roll: int
    subject_roll: int

    def __str__(self) -> str:
        return f"{self.action} + {self.subject}"


@dataclass
class ChaosFactorState:
    """Tracks the current Chaos Factor and modifiers."""

    value: int = 5  # Default balanced chaos
    min_value: int = 1
    max_value: int = 9

    # Track what caused changes
    history: list[tuple[int, str]] = field(default_factory=list)

    def increase(self, reason: str = "") -> int:
        """Increase chaos (things got out of control)."""
        old = self.value
        self.value = min(self.value + 1, self.max_value)
        if old != self.value:
            self.history.append((self.value, f"Increased: {reason}"))
        return self.value

    def decrease(self, reason: str = "") -> int:
        """Decrease chaos (things are under control)."""
        old = self.value
        self.value = max(self.value - 1, self.min_value)
        if old != self.value:
            self.history.append((self.value, f"Decreased: {reason}"))
        return self.value

    def set(self, value: int, reason: str = "") -> int:
        """Set chaos to specific value."""
        old = self.value
        self.value = max(self.min_value, min(value, self.max_value))
        if old != self.value:
            self.history.append((self.value, f"Set: {reason}"))
        return self.value


# =============================================================================
# MYTHIC GME ENGINE
# =============================================================================


class MythicGME:
    """
    Core Mythic Game Master Emulator engine.

    Provides oracle functionality for uncertain questions:
    - Fate Checks for Yes/No questions
    - Random Events for complications
    - Meaning Tables for interpretation
    - Chaos Factor management

    Usage:
        mythic = MythicGME()
        result = mythic.fate_check("Does the spell succeed?", Likelihood.LIKELY)
        if result.random_event_triggered:
            # Handle complication
            meaning = result.random_event.meaning_pair
    """

    def __init__(
        self,
        chaos_factor: int = 5,
        rng: Optional[random.Random] = None,
    ):
        """
        Initialize the Mythic GME engine.

        Args:
            chaos_factor: Starting chaos factor (1-9)
            rng: Optional random number generator for reproducibility
        """
        self.chaos = ChaosFactorState(value=chaos_factor)
        self._rng = rng or random.Random()

    def fate_check(
        self,
        question: str,
        likelihood: Likelihood = Likelihood.FIFTY_FIFTY,
        check_for_event: bool = True,
    ) -> FateCheckResult:
        """
        Perform a Fate Check to answer a Yes/No question.

        Args:
            question: The yes/no question being asked
            likelihood: How likely is a "yes" answer?
            check_for_event: Whether to check for random events

        Returns:
            FateCheckResult with the outcome
        """
        # Get thresholds from Fate Chart
        thresholds = FATE_CHART[self.chaos.value][likelihood]
        ex_yes, yes, no, ex_no = thresholds

        # Roll d100 (1-100)
        roll = self._rng.randint(1, 100)

        # Determine result
        if roll <= ex_yes:
            result = FateResult.EXCEPTIONAL_YES
        elif roll <= yes:
            result = FateResult.YES
        elif roll > ex_no:
            result = FateResult.EXCEPTIONAL_NO
        elif roll > no:
            result = FateResult.NO
        else:
            # Between yes and no thresholds - this is the "gray zone"
            # In some versions this is a weak yes, we'll call it YES
            result = FateResult.YES

        fate_result = FateCheckResult(
            question=question,
            likelihood=likelihood,
            chaos_factor=self.chaos.value,
            roll=roll,
            result=result,
            exceptional_yes_threshold=ex_yes,
            yes_threshold=yes,
            no_threshold=no,
            exceptional_no_threshold=ex_no,
        )

        # Check for random event
        if check_for_event:
            event = self._check_random_event(roll)
            if event:
                fate_result.random_event_triggered = True
                fate_result.random_event = event

        return fate_result

    def _check_random_event(self, roll: int) -> Optional[RandomEvent]:
        """
        Check if a roll triggers a random event.

        Random events trigger on doubles (11, 22, 33, etc.)
        when the doubles value is <= chaos factor.
        """
        # Check for doubles
        tens = roll // 10
        ones = roll % 10

        # Handle roll of 100 (treat as 10 and 0, not doubles)
        if roll == 100:
            return None

        # Check if doubles
        if tens != ones:
            return None

        # Doubles! Check if <= chaos factor
        # For roll 11, tens = 1; for roll 99, tens = 9
        if tens > self.chaos.value:
            return None

        # Random event triggered!
        return self.generate_random_event()

    def generate_random_event(self) -> RandomEvent:
        """Generate a random event using focus and meaning tables."""
        # Roll for focus
        focus_roll = self._rng.randint(1, 100)
        focus = self._lookup_focus(focus_roll)

        # Roll for meaning
        meaning = self.roll_meaning()

        return RandomEvent(
            focus=focus,
            action=meaning.action,
            subject=meaning.subject,
            focus_roll=focus_roll,
            action_roll=meaning.action_roll,
            subject_roll=meaning.subject_roll,
        )

    def _lookup_focus(self, roll: int) -> RandomEventFocus:
        """Look up random event focus from roll."""
        for low, high, focus in RANDOM_EVENT_FOCUS_TABLE:
            if low <= roll <= high:
                return focus
        return RandomEventFocus.AMBIGUOUS_EVENT

    def roll_meaning(self) -> MeaningRoll:
        """Roll on the meaning tables for Action + Subject."""
        action_roll = self._rng.randint(1, 100)
        subject_roll = self._rng.randint(1, 100)

        # Tables are 1-indexed, lists are 0-indexed
        action_idx = (action_roll - 1) % len(ACTION_MEANINGS)
        subject_idx = (subject_roll - 1) % len(SUBJECT_MEANINGS)

        return MeaningRoll(
            action=ACTION_MEANINGS[action_idx],
            subject=SUBJECT_MEANINGS[subject_idx],
            action_roll=action_roll,
            subject_roll=subject_roll,
        )

    def detail_check(self) -> MeaningRoll:
        """
        Roll for details about something.

        Use when you need to know "what kind" or "how" rather than yes/no.
        """
        return self.roll_meaning()

    def adjust_chaos_for_scene(self, scene_was_controlled: bool) -> int:
        """
        Adjust chaos at scene end per Mythic rules.

        Args:
            scene_was_controlled: Did the players maintain control?

        Returns:
            New chaos factor value
        """
        if scene_was_controlled:
            return self.chaos.decrease("Scene ended under player control")
        else:
            return self.chaos.increase("Scene ended out of player control")

    def get_chaos_factor(self) -> int:
        """Get current chaos factor."""
        return self.chaos.value

    def set_chaos_factor(self, value: int, reason: str = "") -> int:
        """Set chaos factor directly."""
        return self.chaos.set(value, reason)

    # =========================================================================
    # CONVENIENCE METHODS FOR COMMON QUESTIONS
    # =========================================================================

    def is_it_likely(self, question: str) -> FateCheckResult:
        """Ask a question with LIKELY odds."""
        return self.fate_check(question, Likelihood.LIKELY)

    def is_it_unlikely(self, question: str) -> FateCheckResult:
        """Ask a question with UNLIKELY odds."""
        return self.fate_check(question, Likelihood.UNLIKELY)

    def fifty_fifty(self, question: str) -> FateCheckResult:
        """Ask a 50/50 question."""
        return self.fate_check(question, Likelihood.FIFTY_FIFTY)

    def is_yes(self, result: FateCheckResult) -> bool:
        """Check if result is any form of yes."""
        return result.result in (FateResult.YES, FateResult.EXCEPTIONAL_YES)

    def is_exceptional(self, result: FateCheckResult) -> bool:
        """Check if result is exceptional (either yes or no)."""
        return result.result in (FateResult.EXCEPTIONAL_YES, FateResult.EXCEPTIONAL_NO)

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Export state for persistence."""
        return {
            "chaos_factor": self.chaos.value,
            "chaos_history": self.chaos.history,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """Import state from persistence."""
        self.chaos.value = data.get("chaos_factor", 5)
        self.chaos.history = data.get("chaos_history", [])
