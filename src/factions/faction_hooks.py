"""
Faction hooks for settlement services and encounter systems.

Provides integration points for:
- Service cost modifiers based on party standing
- Encounter probability modifiers based on hex/settlement faction control
- Hex-to-faction lookups

This module is the bridge between the faction engine and other game systems.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.factions.faction_engine import FactionEngine
    from src.factions.faction_models import PartyFactionState

logger = logging.getLogger(__name__)


@dataclass
class FactionModifiers:
    """Calculated modifiers based on faction standing."""
    cost_multiplier: float = 1.0
    encounter_modifier: int = 0
    faction_id: Optional[str] = None
    standing: int = 0

    @property
    def cost_percent_change(self) -> int:
        """Return the cost change as a percentage (-20, +50, etc.)."""
        return int((self.cost_multiplier - 1.0) * 100)


class HexFactionLookup:
    """
    Maps hexes and settlements to controlling factions.

    Builds a reverse index from faction territory data to enable
    quick lookups of which faction controls a given hex or settlement.
    """

    def __init__(self, engine: Optional["FactionEngine"] = None):
        """
        Initialize the lookup.

        Args:
            engine: The FactionEngine instance (or None for no faction effects)
        """
        self._engine = engine
        self._hex_to_faction: dict[str, str] = {}
        self._settlement_to_faction: dict[str, str] = {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild the hex/settlement to faction mappings from engine state."""
        self._hex_to_faction.clear()
        self._settlement_to_faction.clear()

        if not self._engine:
            return

        for faction_id, state in self._engine.faction_states.items():
            territory = state.territory

            # Map hexes to faction
            for hex_id in territory.hexes:
                # First faction to claim wins (could extend to track conflicts)
                if hex_id not in self._hex_to_faction:
                    self._hex_to_faction[hex_id] = faction_id

            # Map settlements to faction
            for settlement_id in territory.settlements:
                if settlement_id not in self._settlement_to_faction:
                    self._settlement_to_faction[settlement_id] = faction_id

    def refresh(self) -> None:
        """Refresh the index after territory changes."""
        self._rebuild_index()

    def get_faction_for_hex(self, hex_id: str) -> Optional[str]:
        """
        Get the faction controlling a hex.

        Args:
            hex_id: The hex identifier (e.g., "0604")

        Returns:
            Faction ID or None if hex is unclaimed
        """
        return self._hex_to_faction.get(hex_id)

    def get_faction_for_settlement(self, settlement_id: str) -> Optional[str]:
        """
        Get the faction controlling a settlement.

        Args:
            settlement_id: The settlement identifier

        Returns:
            Faction ID or None if settlement is unclaimed
        """
        return self._settlement_to_faction.get(settlement_id)

    def get_standing_for_hex(
        self,
        hex_id: str,
        party_state: Optional["PartyFactionState"] = None,
    ) -> int:
        """
        Get party standing with the faction controlling a hex.

        Args:
            hex_id: The hex identifier
            party_state: Party faction state (uses engine's if not provided)

        Returns:
            Standing value (0 if hex unclaimed or no party state)
        """
        faction_id = self.get_faction_for_hex(hex_id)
        if not faction_id:
            return 0

        state = party_state or (self._engine.party_state if self._engine else None)
        if not state:
            return 0

        return state.get_standing(faction_id)

    def get_standing_for_settlement(
        self,
        settlement_id: str,
        party_state: Optional["PartyFactionState"] = None,
    ) -> int:
        """
        Get party standing with the faction controlling a settlement.

        Args:
            settlement_id: The settlement identifier
            party_state: Party faction state (uses engine's if not provided)

        Returns:
            Standing value (0 if settlement unclaimed or no party state)
        """
        faction_id = self.get_faction_for_settlement(settlement_id)
        if not faction_id:
            return 0

        state = party_state or (self._engine.party_state if self._engine else None)
        if not state:
            return 0

        return state.get_standing(faction_id)


def calculate_modifiers(
    standing: int,
    faction_id: Optional[str] = None,
) -> FactionModifiers:
    """
    Calculate faction-based modifiers from standing value.

    Standing effects:
    - Allied (+8 or more): -25% cost, -2 encounter chance
    - Friendly (+5 to +7): -15% cost, -1 encounter chance
    - Favorable (+2 to +4): -5% cost, no encounter change
    - Neutral (-1 to +1): no change
    - Unfavorable (-2 to -4): +10% cost, +1 encounter chance
    - Hostile (-5 to -7): +25% cost, +1 encounter chance
    - Enemy (-8 or less): +50% cost, +2 encounter chance

    Args:
        standing: Party standing with the faction
        faction_id: Optional faction ID for reference

    Returns:
        FactionModifiers with calculated values
    """
    if standing >= 8:
        # Allied
        return FactionModifiers(
            cost_multiplier=0.75,
            encounter_modifier=-2,
            faction_id=faction_id,
            standing=standing,
        )
    elif standing >= 5:
        # Friendly
        return FactionModifiers(
            cost_multiplier=0.85,
            encounter_modifier=-1,
            faction_id=faction_id,
            standing=standing,
        )
    elif standing >= 2:
        # Favorable
        return FactionModifiers(
            cost_multiplier=0.95,
            encounter_modifier=0,
            faction_id=faction_id,
            standing=standing,
        )
    elif standing >= -1:
        # Neutral
        return FactionModifiers(
            cost_multiplier=1.0,
            encounter_modifier=0,
            faction_id=faction_id,
            standing=standing,
        )
    elif standing >= -4:
        # Unfavorable
        return FactionModifiers(
            cost_multiplier=1.10,
            encounter_modifier=1,
            faction_id=faction_id,
            standing=standing,
        )
    elif standing >= -7:
        # Hostile
        return FactionModifiers(
            cost_multiplier=1.25,
            encounter_modifier=1,
            faction_id=faction_id,
            standing=standing,
        )
    else:
        # Enemy
        return FactionModifiers(
            cost_multiplier=1.50,
            encounter_modifier=2,
            faction_id=faction_id,
            standing=standing,
        )


def get_service_cost_multiplier(
    standing: int,
) -> float:
    """
    Get service cost multiplier based on faction standing.

    Convenience function for settlement service pricing.

    Args:
        standing: Party standing with the controlling faction

    Returns:
        Cost multiplier (e.g., 0.85 for 15% discount, 1.25 for 25% markup)
    """
    return calculate_modifiers(standing).cost_multiplier


def get_encounter_modifier(
    standing: int,
) -> int:
    """
    Get encounter probability modifier based on faction standing.

    Convenience function for encounter checks.

    Args:
        standing: Party standing with the controlling faction

    Returns:
        Modifier to add to encounter chance (-2 to +2)
    """
    return calculate_modifiers(standing).encounter_modifier


def apply_cost_modifier(
    base_cost: int,
    standing: int,
    round_to: int = 1,
) -> int:
    """
    Apply faction standing modifier to a base cost.

    Args:
        base_cost: Original cost in coins
        standing: Party standing with the faction
        round_to: Round result to nearest multiple (default 1)

    Returns:
        Modified cost
    """
    multiplier = get_service_cost_multiplier(standing)
    modified = int(base_cost * multiplier)

    if round_to > 1:
        modified = round(modified / round_to) * round_to

    return max(1, modified)  # Minimum 1 coin
