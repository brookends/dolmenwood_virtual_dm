"""
Action registry and execution helpers.

The first iteration keeps this intentionally small:
- stable IDs so UI can reference actions deterministically
- thin adapters that call existing VirtualDM / engine methods
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.main import VirtualDM  # existing entrypoint module

ActionExecutor = Callable[[VirtualDM, dict[str, Any]], dict[str, Any]]

@dataclass(frozen=True)
class ActionSpec:
    id: str
    label: str
    params_schema: dict[str, Any]
    executor: ActionExecutor
    safe_to_execute: bool = True
    help: Optional[str] = None


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> None:
        self._actions[spec.id] = spec

    def get(self, action_id: str) -> Optional[ActionSpec]:
        return self._actions.get(action_id)

    def all(self) -> list[ActionSpec]:
        return list(self._actions.values())

    def execute(self, dm: VirtualDM, action_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        spec = self.get(action_id)
        if not spec:
            return {"success": False, "message": f"Unknown action_id: {action_id}"}
        return spec.executor(dm, params or {})
