"""
Enhanced Oracle Integration (Upgrade D).

This module provides oracle-based adjudication for ambiguous situations:
1. Detects ambiguous player input
2. Offers oracle options when clarification is needed
3. Provides hooks for spell adjudication (Tier-4 spells)
4. Integrates Mythic GME for uncertainty resolution

The goal is to gracefully handle uncertainty in a solo/co-op play context
where there's no human referee to make judgment calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
import re

from src.oracle.mythic_gme import MythicGME, Likelihood, FateResult

if TYPE_CHECKING:
    from src.main import VirtualDM


class AmbiguityType(str, Enum):
    """Types of ambiguity detected in player input."""
    UNCLEAR_TARGET = "unclear_target"  # Who/what is the target?
    UNCLEAR_METHOD = "unclear_method"  # How do you want to do this?
    UNCLEAR_INTENT = "unclear_intent"  # What are you trying to achieve?
    MULTIPLE_OPTIONS = "multiple_options"  # Several valid interpretations
    NEEDS_DICE = "needs_dice"  # Outcome requires randomization
    NEEDS_REFEREE = "needs_referee"  # Requires judgment call
    CREATIVE_ACTION = "creative_action"  # Novel action not covered by rules


@dataclass
class AmbiguityDetection:
    """Result of detecting ambiguity in player input."""
    is_ambiguous: bool
    ambiguity_type: Optional[AmbiguityType]
    confidence: float  # 0.0 to 1.0
    clarification_prompt: str
    oracle_suggestions: list[str]  # Suggested oracle questions


@dataclass
class OracleResolution:
    """Result of oracle-based resolution."""
    resolved: bool
    outcome: str  # "yes", "no", "exceptional_yes", "exceptional_no"
    interpretation: str  # Human-readable interpretation
    random_event: Optional[str]  # If a random event was triggered
    meaning_pair: Optional[tuple[str, str]]  # Action/subject pair if generated


class OracleEnhancement:
    """
    Enhanced oracle integration for ambiguity resolution.

    This class provides:
    - Ambiguity detection in player input
    - Oracle-based resolution suggestions
    - Integration with Mythic GME
    - Hooks for spell adjudication
    """

    def __init__(self, mythic: MythicGME):
        self.mythic = mythic

        # Keywords that suggest ambiguity
        self._uncertainty_keywords = {
            "maybe", "perhaps", "possibly", "might", "could",
            "try to", "attempt to", "see if", "check if",
            "is it", "are they", "does it", "can i", "would",
        }

        # Keywords that suggest creative/unusual actions
        self._creative_keywords = {
            "use the", "combine", "trick", "pretend", "convince",
            "negotiate", "bribe", "intimidate", "distract",
            "improvise", "create", "modify",
        }

    def detect_ambiguity(
        self,
        player_input: str,
        game_state: str,
        context: Optional[dict[str, Any]] = None
    ) -> AmbiguityDetection:
        """
        Analyze player input for ambiguity.

        Returns detection result with suggested clarifications.
        """
        input_lower = player_input.lower().strip()

        # Check for question format (player is already asking something)
        is_question = input_lower.endswith("?") or input_lower.startswith(
            ("is ", "are ", "does ", "do ", "can ", "will ", "would ", "could ")
        )

        if is_question:
            # Player is asking a question - suggest oracle
            return AmbiguityDetection(
                is_ambiguous=True,
                ambiguity_type=AmbiguityType.NEEDS_DICE,
                confidence=0.9,
                clarification_prompt="This sounds like a question for the Oracle.",
                oracle_suggestions=[
                    f"Ask the Oracle: {player_input}",
                    "Use Mythic Fate Check with appropriate likelihood",
                ]
            )

        # Check for uncertainty keywords
        has_uncertainty = any(kw in input_lower for kw in self._uncertainty_keywords)

        if has_uncertainty:
            return AmbiguityDetection(
                is_ambiguous=True,
                ambiguity_type=AmbiguityType.UNCLEAR_INTENT,
                confidence=0.7,
                clarification_prompt="Your action seems uncertain. Would you like to consult the Oracle?",
                oracle_suggestions=[
                    "Fate Check: Is the action successful?",
                    "Detail Check: What happens next?",
                ]
            )

        # Check for creative actions
        has_creative = any(kw in input_lower for kw in self._creative_keywords)

        if has_creative and game_state in ("encounter", "dungeon_exploration"):
            return AmbiguityDetection(
                is_ambiguous=True,
                ambiguity_type=AmbiguityType.CREATIVE_ACTION,
                confidence=0.6,
                clarification_prompt="This is a creative action. The Oracle can help determine the outcome.",
                oracle_suggestions=[
                    "Fate Check: Does the creative approach work?",
                    "Detail Check: What unexpected twist occurs?",
                ]
            )

        # Check for vague targets in encounter/combat
        if game_state in ("encounter", "combat"):
            vague_targets = ["them", "it", "one of them", "someone", "something"]
            if any(vt in input_lower for vt in vague_targets):
                return AmbiguityDetection(
                    is_ambiguous=True,
                    ambiguity_type=AmbiguityType.UNCLEAR_TARGET,
                    confidence=0.8,
                    clarification_prompt="Who or what specifically are you targeting?",
                    oracle_suggestions=[]
                )

        # No ambiguity detected
        return AmbiguityDetection(
            is_ambiguous=False,
            ambiguity_type=None,
            confidence=1.0,
            clarification_prompt="",
            oracle_suggestions=[]
        )

    def resolve_with_oracle(
        self,
        question: str,
        likelihood: Likelihood = Likelihood.FIFTY_FIFTY
    ) -> OracleResolution:
        """
        Resolve an ambiguous situation using the oracle.

        Converts the oracle result into an actionable resolution.
        """
        result = self.mythic.fate_check(question, likelihood)

        # Build interpretation
        if result.result == FateResult.EXCEPTIONAL_YES:
            interpretation = f"Exceptional Yes! {question.rstrip('?')} - absolutely, and even better than expected."
        elif result.result == FateResult.YES:
            interpretation = f"Yes. {question.rstrip('?')}."
        elif result.result == FateResult.NO:
            interpretation = f"No. {question.rstrip('?')} does not happen."
        else:  # EXCEPTIONAL_NO
            interpretation = f"Exceptional No! Not only does it fail, but there may be consequences."

        # Check for random event
        random_event_desc = None
        if result.random_event_triggered and result.random_event:
            ev = result.random_event
            random_event_desc = f"Random Event triggered: {ev.focus.value} - {ev.action}/{ev.subject}"

        return OracleResolution(
            resolved=True,
            outcome=result.result.value,
            interpretation=interpretation,
            random_event=random_event_desc,
            meaning_pair=None
        )

    def generate_detail(self) -> OracleResolution:
        """
        Generate a meaning word pair for creative interpretation.

        Useful for open-ended situations that need inspiration.
        """
        meaning = self.mythic.generate_meaning()

        return OracleResolution(
            resolved=True,
            outcome="detail",
            interpretation=f"The oracle suggests: {meaning.action} / {meaning.subject}",
            random_event=None,
            meaning_pair=(meaning.action, meaning.subject)
        )

    def suggest_likelihood(
        self,
        situation: str,
        modifiers: Optional[dict[str, Any]] = None
    ) -> Likelihood:
        """
        Suggest an appropriate likelihood for a fate check.

        Analyzes the situation and any modifiers to recommend
        the right Mythic likelihood level.
        """
        modifiers = modifiers or {}

        # Start at 50/50
        base_score = 50

        # Adjust for situational keywords
        situation_lower = situation.lower()

        if any(w in situation_lower for w in ["easy", "simple", "obvious", "guaranteed"]):
            base_score += 25
        elif any(w in situation_lower for w in ["hard", "difficult", "unlikely", "rare"]):
            base_score -= 25
        elif any(w in situation_lower for w in ["impossible", "never", "no way"]):
            base_score -= 40
        elif any(w in situation_lower for w in ["certain", "definitely", "always"]):
            base_score += 40

        # Adjust for skill/level
        if modifiers.get("character_level", 0) > 10:
            base_score += 10
        if modifiers.get("has_relevant_skill", False):
            base_score += 15
        if modifiers.get("favorable_conditions", False):
            base_score += 10
        if modifiers.get("unfavorable_conditions", False):
            base_score -= 10

        # Map score to likelihood
        if base_score >= 95:
            return Likelihood.HAS_TO_BE
        elif base_score >= 85:
            return Likelihood.A_SURE_THING
        elif base_score >= 75:
            return Likelihood.NEAR_SURE_THING
        elif base_score >= 65:
            return Likelihood.VERY_LIKELY
        elif base_score >= 55:
            return Likelihood.LIKELY
        elif base_score >= 45:
            return Likelihood.FIFTY_FIFTY
        elif base_score >= 35:
            return Likelihood.UNLIKELY
        elif base_score >= 25:
            return Likelihood.VERY_UNLIKELY
        else:
            return Likelihood.IMPOSSIBLE

    def format_oracle_options(
        self,
        detection: AmbiguityDetection
    ) -> list[dict[str, Any]]:
        """
        Format oracle suggestions as action options.

        Returns list of suggested actions with oracle integration.
        """
        options = []

        for i, suggestion in enumerate(detection.oracle_suggestions):
            if "Fate Check" in suggestion:
                options.append({
                    "id": f"oracle:fate_check",
                    "label": suggestion,
                    "params": {
                        "question": suggestion.replace("Fate Check: ", ""),
                    }
                })
            elif "Detail Check" in suggestion:
                options.append({
                    "id": "oracle:detail_check",
                    "label": suggestion,
                    "params": {}
                })
            elif "Random Event" in suggestion:
                options.append({
                    "id": "oracle:random_event",
                    "label": suggestion,
                    "params": {}
                })

        return options


def create_oracle_enhancement(mythic: Optional[MythicGME] = None) -> OracleEnhancement:
    """Create an OracleEnhancement with the given or new Mythic GME."""
    import random
    if mythic is None:
        mythic = MythicGME(rng=random.Random())
    return OracleEnhancement(mythic)
