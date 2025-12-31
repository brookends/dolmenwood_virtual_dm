"""
Conversation-first + Suggested Actions types.

These types are deliberately UI-agnostic:
- CLI can render suggested_actions as numbered choices
- Foundry (later) can render them as clickable buttons
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Literal

Role = Literal["player", "dm", "system"]

@dataclass
class ChatMessage:
    role: Role
    content: str

@dataclass
class SuggestedAction:
    """
    A stable, UI-clickable action suggestion.

    - id: stable action identifier (used by CLI index mapping and future Foundry buttons)
    - params_schema: lightweight JSON-schema-ish description for tool-guided edits
    - params: concrete params for immediate execution (when safe_to_execute=True)
    """
    id: str
    label: str
    params_schema: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    safe_to_execute: bool = True
    help: Optional[str] = None

@dataclass
class TurnResponse:
    """
    Result of one chat turn OR one clicked action.
    """
    messages: list[ChatMessage] = field(default_factory=list)
    suggested_actions: list[SuggestedAction] = field(default_factory=list)

    # Optional: payloads for integrations
    public_state: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    # Optional: clarification loop support
    requires_clarification: bool = False
    clarification_prompt: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": [m.__dict__ for m in self.messages],
            "suggested_actions": [
                {
                    "id": a.id,
                    "label": a.label,
                    "params_schema": a.params_schema,
                    "params": a.params,
                    "safe_to_execute": a.safe_to_execute,
                    "help": a.help,
                }
                for a in self.suggested_actions
            ],
            "public_state": self.public_state,
            "events": self.events,
            "requires_clarification": self.requires_clarification,
            "clarification_prompt": self.clarification_prompt,
        }
