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

    def to_dict(self) -> dict:
        return {
            "service_name": self.service_name,
            "description": self.description,
            "cost_text": self.cost_text,
            "cost_estimate": (self.cost_estimate.__dict__ if self.cost_estimate else None),
            "notes": self.notes,
            "effects": self.effects or [],
        }


class SettlementServiceExecutor:
    """
    A thin dispatcher that recognizes a few common service categories.

    In the first pass, most services are "generic" and only return structured text.
    Later passes can add real effects (healing, room/rest, hirelings, spellcasting, etc.).
    """

    def use(self, service: SettlementServiceData, params: Optional[dict] = None) -> ServiceUseResult:
        params = params or {}
        cost_est = parse_cost_text(service.cost or "")

        lname = (service.name or "").lower()

        # Lodging/rest keywords
        if any(k in lname for k in ("lodg", "room", "sleep", "suite")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Lodging",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes="TODO: integrate with SettlementEngine lifestyle + rest healing and/or DowntimeEngine.",
            )

        # Food/drink
        if any(k in lname for k in ("food", "drink", "ale", "wine", "meal", "supper", "breakfast")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Food/drink",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes=service.notes or "",
            )

        # Healing
        if any(k in lname for k in ("heal", "leech", "apothec", "physic", "surgeon")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Healing service",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes="TODO: integrate with CharacterState healing/conditions + downtime/rest rules.",
            )

        # Prayer/blessing
        if any(k in lname for k in ("prayer", "blessing", "benediction")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Prayer/blessing",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes="TODO: integrate with blessing effects and/or condition removal (rules-driven).",
            )

        # Stabling/transport
        if any(k in lname for k in ("stabl", "ferry", "boat", "barge", "passage")):
            return ServiceUseResult(
                service_name=service.name,
                description=service.description or "Transport/stabling",
                cost_text=service.cost or "",
                cost_estimate=cost_est,
                notes=service.notes or "",
            )

        # Default: generic service/purchase
        return ServiceUseResult(
            service_name=service.name,
            description=service.description or "",
            cost_text=service.cost or "",
            cost_estimate=cost_est,
            notes=service.notes or "",
        )
