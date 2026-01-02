"""
Settlement service execution scaffolding.

This module targets an "80% good enough" first pass:
- preserve authored cost text
- parse simple coin amounts when possible
- return structured results the engine can log and (optionally) apply

Later: integrate party currency tracking + item purchases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import re

from src.settlement.settlement_content_models import SettlementServiceData


@dataclass
class CostEstimate:
    gp: int = 0
    sp: int = 0
    cp: int = 0
    notes: str = ""

    def apply_multiplier(self, multiplier: float) -> "CostEstimate":
        """Return a new CostEstimate with costs scaled by multiplier."""
        return CostEstimate(
            gp=max(0, int(self.gp * multiplier)),
            sp=max(0, int(self.sp * multiplier)),
            cp=max(0, int(self.cp * multiplier)),
            notes=self.notes,
        )


_SIMPLE_COIN_RE = re.compile(r"(?P<num>\d+)\s*(?P<denom>gp|sp|cp)\b", flags=re.I)


def parse_cost_text(cost: str) -> Optional[CostEstimate]:
    """
    Best-effort parser for simple patterns like:
    - "15cp per stein"
    - "25gp per item"
    - "1gp per person per night"

    Returns None if parsing fails or no numeric coin amounts are present.
    """
    if not cost:
        return None
    gp = sp = cp = 0
    found = False
    for m in _SIMPLE_COIN_RE.finditer(cost):
        found = True
        num = int(m.group("num"))
        denom = m.group("denom").lower()
        if denom == "gp":
            gp += num
        elif denom == "sp":
            sp += num
        elif denom == "cp":
            cp += num
    if not found:
        return None
    return CostEstimate(gp=gp, sp=sp, cp=cp, notes="parsed simple coin amounts")


@dataclass
class ServiceUseResult:
    service_name: str
    description: str
    cost_text: str
    cost_estimate: Optional[CostEstimate]
    notes: str = ""
    effects: list[dict] = field(default_factory=list)  # future EffectCommands
    faction_modifier_applied: bool = False
    faction_cost_percent: int = 0  # e.g., -15 for 15% discount, +25 for markup

    def to_dict(self) -> dict:
        return {
            "service_name": self.service_name,
            "description": self.description,
            "cost_text": self.cost_text,
            "cost_estimate": (self.cost_estimate.__dict__ if self.cost_estimate else None),
            "notes": self.notes,
            "effects": self.effects or [],
            "faction_modifier_applied": self.faction_modifier_applied,
            "faction_cost_percent": self.faction_cost_percent,
        }


class SettlementServiceExecutor:
    """
    A thin dispatcher that recognizes a few common service categories.

    In the first pass, most services are "generic" and only return structured text.
    Later passes can add real effects (healing, room/rest, hirelings, spellcasting, etc.).
    """

    def use(
        self,
        service: SettlementServiceData,
        params: Optional[dict] = None,
        faction_standing: int = 0,
    ) -> ServiceUseResult:
        """
        Execute a service and return structured results.

        Args:
            service: The service data
            params: Optional parameters for the service
            faction_standing: Party standing with the settlement's controlling faction.
                Positive values give discounts, negative values add markups.

        Returns:
            ServiceUseResult with cost estimates and effects
        """
        params = params or {}
        cost_est = parse_cost_text(service.cost or "")

        # Apply faction standing modifier to costs
        faction_modifier_applied = False
        faction_cost_percent = 0
        if cost_est and faction_standing != 0:
            from src.factions.faction_hooks import get_service_cost_multiplier
            multiplier = get_service_cost_multiplier(faction_standing)
            if multiplier != 1.0:
                cost_est = cost_est.apply_multiplier(multiplier)
                faction_modifier_applied = True
                faction_cost_percent = int((multiplier - 1.0) * 100)

        lname = (service.name or "").lower()

        # Lodging/rest keywords
        if any(k in lname for k in ("lodg", "room", "sleep", "suite")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Lodging",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes="TODO: integrate with SettlementEngine lifestyle + rest healing and/or DowntimeEngine.",
                faction_modifier_applied=faction_modifier_applied,
                faction_cost_percent=faction_cost_percent,
            )

        # Food/drink
        if any(k in lname for k in ("food", "drink", "ale", "wine", "meal", "supper", "breakfast")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Food/drink",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes=service.notes or "",
                faction_modifier_applied=faction_modifier_applied,
                faction_cost_percent=faction_cost_percent,
            )

        # Healing
        if any(k in lname for k in ("heal", "leech", "apothec", "physic", "surgeon")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Healing service",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes="TODO: integrate with CharacterState healing/conditions + downtime/rest rules.",
                faction_modifier_applied=faction_modifier_applied,
                faction_cost_percent=faction_cost_percent,
            )

        # Prayer/blessing
        if any(k in lname for k in ("prayer", "blessing", "benediction")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Prayer/blessing",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes="TODO: integrate with blessing effects and/or condition removal (rules-driven).",
                faction_modifier_applied=faction_modifier_applied,
                faction_cost_percent=faction_cost_percent,
            )

        # Stabling/transport
        if any(k in lname for k in ("stabl", "ferry", "boat", "barge", "passage")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Transport/stabling",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes=service.notes or "",
                faction_modifier_applied=faction_modifier_applied,
                faction_cost_percent=faction_cost_percent,
            )

        # Default: generic service/purchase
        return ServiceUseResult(
            service_name=service.name,
            description=service.description or "",
            cost_text=service.cost or "",
            cost_estimate=cost_est,
            notes=service.notes or "",
            faction_modifier_applied=faction_modifier_applied,
            faction_cost_percent=faction_cost_percent,
        )
