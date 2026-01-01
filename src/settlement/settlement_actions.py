"""
Settlement action IDs and suggestion scaffolding.

This is designed to plug into the "chat-first + suggested actions" layer.

Key principle:
- Suggestions MUST map to executable actions (`SettlementEngine.execute_action`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


# Stable action IDs (string-based for UI safety)
SETTLEMENT_ACTIONS = {
    "settlement:list_locations",
    "settlement:visit_location",
    "settlement:list_services",
    "settlement:use_service",
    "settlement:list_npcs",
    "settlement:talk",
    "settlement:ask_rumor",
    "settlement:ask_directions",
    "settlement:ask_local_info",
    "settlement:check_encounter",
    "settlement:leave",
}


@dataclass
class Suggestion:
    id: str
    label: str
    params: dict[str, Any] = None
    priority: float = 0.0
    safe_to_execute: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "params": self.params or {},
            "priority": self.priority,
            "safe_to_execute": self.safe_to_execute,
        }


def build_settlement_suggestions(
    *,
    location_summaries: list[dict[str, Any]],
    has_unvisited: bool,
    has_services: bool,
    has_npcs: bool,
    can_leave: bool = True,
) -> list[Suggestion]:
    """
    Minimal suggestion set.
    The engine/conversation layer should add more context-aware suggestions over time.
    """
    sug: list[Suggestion] = []
    sug.append(Suggestion(id="settlement:list_locations", label="Browse locations", priority=0.9))
    if has_unvisited:
        # suggest visiting the first unvisited location if summaries include it
        first = next((l for l in location_summaries if not l.get("visited")), None)
        if first:
            sug.append(Suggestion(
                id="settlement:visit_location",
                label=f"Visit: {first.get('name','(unknown)')}",
                params={"location_number": first.get("number")},
                priority=0.85,
            ))
    if has_services:
        sug.append(Suggestion(id="settlement:list_services", label="See available services here", priority=0.75))
    if has_npcs:
        sug.append(Suggestion(id="settlement:list_npcs", label="See notable locals here", priority=0.7))
    sug.append(Suggestion(id="settlement:ask_rumor", label="Ask around for rumors", priority=0.6))
    sug.append(Suggestion(id="settlement:ask_directions", label="Ask for directions / roads", priority=0.5))
    if can_leave:
        sug.append(Suggestion(id="settlement:leave", label="Leave settlement", priority=0.2))
    return sorted(sug, key=lambda s: s.priority, reverse=True)
