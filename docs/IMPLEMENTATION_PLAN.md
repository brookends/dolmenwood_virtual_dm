# Dolmenwood Virtual DM — Conversation-First Refactor Implementation Plan

**Generated:** 2025-12-31
**Based on:** Refactor Blueprint (2025-12-30)
**Target:** Transform command-driven CLI into conversation-first solo DM with suggested actions

---

## Executive Summary

This plan transforms the existing command-driven CLI into a **conversation-first interface** with system-generated suggested actions. The refactor leverages significant existing infrastructure:

- **Existing callback infrastructure** in all 6 engines (ready to wire)
- **Existing intent parser** with ActionCategory/ActionType enums (foundation for ActionRegistry)
- **Existing RunLog** with subscription model (foundation for UI event bus)
- **Existing NarrativeResolver** switchboard (can route to new handlers)

**Estimated scope:** 8 implementation phases, ~15-20 new files, ~30-40 surgical edits to existing files.

---

## Gap Analysis: Blueprint vs. Current Code

### What Exists (Reusable)

| Blueprint Requirement | Existing Code | Reuse Strategy |
|----------------------|---------------|----------------|
| Engine action types | `DungeonActionType`, `EncounterAction` enums | Map to ActionRegistry IDs |
| Intent classification | `src/narrative/intent_parser.py` (ActionCategory, ActionType) | Extend with action_id mapping |
| Narration callbacks | `register_description_callback()` in 5 engines | Wire to DMAgent in VirtualDM.__init__ |
| Event logging | `src/observability/run_log.py` with subscribe() | Add UI event adapter |
| State machine hooks | `state_machine.register_callback()` | Use for suggestion refresh |
| Oracle subsystem | `src/oracle/` fully implemented | Wire to SpellResolver Tier-4 |

### What's Missing (Must Build)

| Blueprint Requirement | Gap | Priority |
|----------------------|-----|----------|
| `src/conversation/` package | Does not exist | P0 |
| ActionRegistry | No unified action ID system | P0 |
| SuggestionBuilder | No context-aware suggestions | P0 |
| ConversationFacade | No chat orchestrator | P0 |
| ChatCLI | Only command-based CLI exists | P1 |
| state_export.py | No stable JSON export | P1 |
| Engine context accessors | Partial (spell_context exists) | P2 |
| UI event bus adapter | RunLog exists but no UI layer | P2 |

---

## Implementation Phases

### Phase 1: Wire Narration Callbacks (Low Risk, High Impact)

**Goal:** Close narration gaps documented in `docs/NARRATION_GAP_ASSESSMENT.md`

**Files to modify:**
- `src/main.py` — VirtualDM.__init__()

**Changes:**
```python
# In VirtualDM.__init__, after engine creation:
self.hex_crawl.register_description_callback(self._handle_hex_description)
self.dungeon.register_description_callback(self._handle_dungeon_description)
self.settlement.register_description_callback(self._handle_settlement_description)
self.settlement.register_dialogue_callback(self._handle_dialogue)
self.combat.register_narration_callback(self._handle_combat_narration)
self.encounter.register_narration_callback(self._handle_encounter_narration)
self.downtime.register_event_callback(self._handle_downtime_event)
```

**New methods to add in VirtualDM:**
- `_handle_hex_description(context: dict) -> Optional[str]`
- `_handle_dungeon_description(context: dict) -> Optional[str]`
- `_handle_settlement_description(context: dict) -> Optional[str]`
- `_handle_dialogue(context: dict) -> Optional[str]`
- `_handle_combat_narration(context: dict) -> Optional[str]`
- `_handle_encounter_narration(context: dict) -> Optional[str]`
- `_handle_downtime_event(context: dict) -> Optional[str]`

**Validation:** Run existing tests, manually verify narration flows.

---

### Phase 2: Create Conversation Package Foundation

**Goal:** Establish `src/conversation/` with core types

**New files:**

#### 2.1 `src/conversation/__init__.py`
```python
"""Conversation-first interface for Dolmenwood Virtual DM."""
from .types import TurnResponse, SuggestedAction, ClarificationRequest
from .action_registry import ActionRegistry, ActionHandler
from .suggestion_builder import SuggestionBuilder
from .conversation_facade import ConversationFacade
```

#### 2.2 `src/conversation/types.py`
```python
@dataclass
class SuggestedAction:
    action_id: str           # e.g., "dungeon.search"
    display_text: str        # "Search the room"
    params: dict[str, Any]   # Pre-filled parameters
    shortcut: Optional[str]  # Keyboard shortcut (1-9)
    category: str            # For grouping in UI
    enabled: bool = True
    reason_disabled: Optional[str] = None

@dataclass
class ClarificationRequest:
    question: str
    options: list[str]
    context: dict[str, Any]
    required: bool = True

@dataclass
class ResolvedActionSummary:
    action_id: str
    success: bool
    partial_success: bool = False
    dice_results: list[dict] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    state_changes: dict[str, Any] = field(default_factory=dict)
    time_spent: int = 0  # Turns
    resources_consumed: dict[str, int] = field(default_factory=dict)

@dataclass
class TurnResponse:
    narration: str
    mechanical_summary: ResolvedActionSummary
    suggested_actions: list[SuggestedAction]
    clarification: Optional[ClarificationRequest] = None
    warnings: list[str] = field(default_factory=list)
    state_snapshot: Optional[dict] = None  # For Foundry
```

#### 2.3 `src/conversation/state_export.py`
```python
SCHEMA_VERSION = "0.1.0"

def export_public_state(controller: GlobalController) -> dict:
    """Export player-visible state (no secrets)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "game_state": controller.current_state.value,
        "time": controller.time_tracker.get_time_summary(),
        "party": _export_party_state(controller),
        "location": _export_location_state(controller),
        "encounter": _export_encounter_state(controller) if controller.current_encounter else None,
    }

def export_gm_state(controller: GlobalController) -> dict:
    """Export full state including secrets (for debugging)."""
    # Include hidden information
```

---

### Phase 3: Build ActionRegistry

**Goal:** Create unified action ID system mapping to engine methods

**New file:** `src/conversation/action_registry.py`

```python
@dataclass
class ActionDefinition:
    action_id: str
    display_name: str
    category: str  # wilderness, dungeon, encounter, combat, settlement, downtime
    param_schema: dict[str, Any]  # JSON schema for params
    valid_states: list[GameState]
    handler: Callable[[GlobalController, dict], dict]

class ActionRegistry:
    def __init__(self):
        self._actions: dict[str, ActionDefinition] = {}
        self._register_core_actions()

    def register(self, action: ActionDefinition) -> None: ...
    def get(self, action_id: str) -> Optional[ActionDefinition]: ...
    def get_valid_actions(self, state: GameState) -> list[ActionDefinition]: ...
    def execute(self, action_id: str, controller: GlobalController,
                params: dict) -> dict: ...

    def _register_core_actions(self):
        # Wilderness actions
        self.register(ActionDefinition(
            action_id="wilderness.travel",
            display_name="Travel to hex",
            category="wilderness",
            param_schema={"hex_id": {"type": "string", "required": True}},
            valid_states=[GameState.WILDERNESS_TRAVEL],
            handler=self._handle_wilderness_travel,
        ))
        # ... register 20-30 core actions
```

**Action ID mapping (from blueprint Section 4):**

| Action ID | Engine Method | Valid States |
|-----------|--------------|--------------|
| `wilderness.travel` | `HexCrawlEngine.travel_to_hex(hex_id)` | WILDERNESS_TRAVEL |
| `wilderness.search_hex` | `HexCrawlEngine.search_hex()` | WILDERNESS_TRAVEL |
| `wilderness.make_camp` | `DowntimeEngine.setup_camp()` | WILDERNESS_TRAVEL |
| `dungeon.move` | `DungeonEngine.execute_turn(MOVE, {dest})` | DUNGEON_EXPLORATION |
| `dungeon.search` | `DungeonEngine.execute_turn(SEARCH, {area})` | DUNGEON_EXPLORATION |
| `dungeon.listen` | `DungeonEngine.execute_turn(LISTEN, {door})` | DUNGEON_EXPLORATION |
| `dungeon.open_door` | `DungeonEngine.execute_turn(OPEN_DOOR, {door})` | DUNGEON_EXPLORATION |
| `dungeon.rest` | `DungeonEngine.execute_turn(REST, {})` | DUNGEON_EXPLORATION |
| `encounter.parley` | `EncounterEngine.execute_action(PARLEY)` | ENCOUNTER |
| `encounter.evade` | `EncounterEngine.execute_action(EVADE)` | ENCOUNTER |
| `encounter.attack` | `EncounterEngine.execute_action(ATTACK)` | ENCOUNTER |
| `combat.attack` | `CombatEngine.resolve_attack(...)` | COMBAT |
| `combat.cast_spell` | `SpellResolver` routing | COMBAT |
| `combat.flee` | `CombatEngine.attempt_flee(...)` | COMBAT |
| `settlement.talk` | `SettlementEngine.initiate_conversation(npc)` | SETTLEMENT_EXPLORATION |
| `settlement.end_talk` | `SettlementEngine.end_conversation()` | SOCIAL_INTERACTION |
| `downtime.rest` | `DowntimeEngine.rest(type)` | DOWNTIME |
| `oracle.fate_check` | `MythicGME.fate_check(...)` | ANY |

---

### Phase 4: Build SuggestionBuilder

**Goal:** Generate context-aware suggested actions per state

**New file:** `src/conversation/suggestion_builder.py`

```python
class SuggestionBuilder:
    def __init__(self, registry: ActionRegistry):
        self.registry = registry
        self._state_builders: dict[GameState, Callable] = {
            GameState.WILDERNESS_TRAVEL: self._build_wilderness_suggestions,
            GameState.DUNGEON_EXPLORATION: self._build_dungeon_suggestions,
            GameState.ENCOUNTER: self._build_encounter_suggestions,
            GameState.COMBAT: self._build_combat_suggestions,
            GameState.SETTLEMENT_EXPLORATION: self._build_settlement_suggestions,
            GameState.SOCIAL_INTERACTION: self._build_social_suggestions,
            GameState.DOWNTIME: self._build_downtime_suggestions,
        }

    def build(self, controller: GlobalController,
              engines: dict) -> list[SuggestedAction]:
        """Build suggestions for current state."""
        state = controller.current_state
        builder = self._state_builders.get(state)
        if builder:
            return builder(controller, engines)
        return []

    def _build_dungeon_suggestions(self, controller, engines) -> list[SuggestedAction]:
        """Build dungeon exploration suggestions."""
        suggestions = []
        dungeon = engines.get('dungeon')
        if not dungeon:
            return suggestions

        # Get current room context
        room = dungeon.get_current_room()
        if room:
            # Add movement options for each exit
            for direction, dest in room.exits.items():
                suggestions.append(SuggestedAction(
                    action_id="dungeon.move",
                    display_text=f"Go {direction}",
                    params={"direction": direction, "destination": dest},
                    category="movement",
                ))

            # Add search if not searched
            if not room.searched:
                suggestions.append(SuggestedAction(
                    action_id="dungeon.search",
                    display_text="Search the room",
                    params={"area": room.room_id},
                    category="exploration",
                ))

            # Add door interactions
            for door_id, state in room.doors.items():
                if state == DoorState.CLOSED:
                    suggestions.append(SuggestedAction(
                        action_id="dungeon.listen",
                        display_text=f"Listen at {door_id}",
                        params={"door_id": door_id},
                        category="exploration",
                    ))

        # Always offer rest if needed
        if dungeon.state and dungeon.state.turns_since_rest >= 5:
            suggestions.append(SuggestedAction(
                action_id="dungeon.rest",
                display_text="Rest (required)",
                params={},
                category="survival",
            ))

        return suggestions[:12]  # Cap at 12 suggestions
```

**Engine context accessors needed:**

| Engine | Method to Add | Returns |
|--------|---------------|---------|
| DungeonEngine | `get_current_room()` | DungeonRoom or None |
| DungeonEngine | `get_dungeon_context()` | dict with state summary |
| HexCrawlEngine | `get_adjacent_hexes()` | list of accessible hex_ids |
| HexCrawlEngine | `get_hex_context()` | dict with current hex info |
| EncounterEngine | `get_encounter_context()` | dict with phase, distance, foes |
| CombatEngine | `get_combat_context()` | dict with combatants, initiative |
| SettlementEngine | `get_settlement_context()` | dict with NPCs, services |

---

### Phase 5: Build ConversationFacade

**Goal:** Create the chat orchestrator

**New file:** `src/conversation/conversation_facade.py`

```python
class ConversationFacade:
    """
    Single orchestrator for conversation-first UI.

    Handles:
    - Natural language input → action resolution
    - Direct action execution (button clicks)
    - State export for UI rendering
    - Suggestion generation
    """

    def __init__(
        self,
        controller: GlobalController,
        engines: dict,
        dm_agent: Optional[DMAgent] = None,
    ):
        self.controller = controller
        self.engines = engines
        self.dm_agent = dm_agent
        self.registry = ActionRegistry()
        self.suggestion_builder = SuggestionBuilder(self.registry)
        self.intent_interpreter = IntentInterpreter(self.registry)

    def handle_chat(self, text: str, actor_id: str = "player") -> TurnResponse:
        """
        Process natural language input.

        Flow:
        1. Interpret text → proposed action
        2. Validate action is legal in current state
        3. Execute via ActionRegistry
        4. Collect deterministic summary
        5. Generate narration via DMAgent
        6. Build next suggestions
        """
        # 1. Interpret intent
        interpretation = self.intent_interpreter.interpret(
            text=text,
            current_state=self.controller.current_state,
            state_context=export_public_state(self.controller),
        )

        # 2. Check for clarification needed
        if interpretation.requires_clarification:
            return TurnResponse(
                narration="",
                mechanical_summary=None,
                suggested_actions=self._build_suggestions(),
                clarification=ClarificationRequest(
                    question=interpretation.clarification_question,
                    options=interpretation.alternatives,
                    context={"original_input": text},
                ),
            )

        # 3. Execute the action
        return self.execute_action(
            action_id=interpretation.action_id,
            params=interpretation.params,
            actor_id=actor_id,
        )

    def execute_action(
        self,
        action_id: str,
        params: dict,
        actor_id: str = "player"
    ) -> TurnResponse:
        """Execute a specific action (from button click or interpreted chat)."""
        # Validate
        action_def = self.registry.get(action_id)
        if not action_def:
            return self._error_response(f"Unknown action: {action_id}")

        if self.controller.current_state not in action_def.valid_states:
            return self._error_response(
                f"Cannot {action_def.display_name} in {self.controller.current_state.value}"
            )

        # Execute
        result = self.registry.execute(action_id, self.controller, params)

        # Build summary
        summary = ResolvedActionSummary(
            action_id=action_id,
            success=result.get("success", True),
            partial_success=result.get("partial_success", False),
            dice_results=result.get("dice_results", []),
            effects=result.get("effects", []),
            state_changes=result.get("state_changes", {}),
            time_spent=result.get("time_spent", 0),
            resources_consumed=result.get("resources_consumed", {}),
        )

        # Generate narration
        narration = ""
        if self.dm_agent:
            narration = self._generate_narration(action_def, result, summary)

        # Build suggestions for new state
        suggestions = self._build_suggestions()

        return TurnResponse(
            narration=narration,
            mechanical_summary=summary,
            suggested_actions=suggestions,
            state_snapshot=export_public_state(self.controller),
        )

    def get_current_suggestions(self) -> list[SuggestedAction]:
        """Get suggestions for current state without executing anything."""
        return self._build_suggestions()

    def get_state(self) -> dict:
        """Get current public state for UI."""
        return export_public_state(self.controller)

    def _build_suggestions(self) -> list[SuggestedAction]:
        return self.suggestion_builder.build(self.controller, self.engines)

    def _generate_narration(self, action_def, result, summary) -> str:
        # Call appropriate DMAgent method based on action category
        ...
```

---

### Phase 6: Build IntentInterpreter

**Goal:** Map natural language to action IDs

**New file:** `src/conversation/intent_interpreter.py`

```python
@dataclass
class InterpretationResult:
    action_id: str
    params: dict[str, Any]
    confidence: float
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    alternatives: list[str] = field(default_factory=list)

class IntentInterpreter:
    """
    Interprets natural language into ActionRegistry action IDs.

    Uses:
    1. Quick pattern matching for common actions
    2. Existing ParsedIntent from intent_parser.py
    3. LLM fallback for ambiguous cases
    """

    def __init__(self, registry: ActionRegistry):
        self.registry = registry
        self._quick_patterns = self._build_quick_patterns()

    def interpret(
        self,
        text: str,
        current_state: GameState,
        state_context: dict,
        last_suggestions: Optional[list[SuggestedAction]] = None,
    ) -> InterpretationResult:
        """Interpret player text into an action."""
        text_lower = text.lower().strip()

        # 1. Check for numeric selection of last suggestions
        if text_lower.isdigit() and last_suggestions:
            idx = int(text_lower) - 1
            if 0 <= idx < len(last_suggestions):
                action = last_suggestions[idx]
                return InterpretationResult(
                    action_id=action.action_id,
                    params=action.params,
                    confidence=1.0,
                )

        # 2. Quick pattern matching
        for pattern, (action_id, param_extractor) in self._quick_patterns.items():
            if pattern in text_lower:
                params = param_extractor(text) if param_extractor else {}
                return InterpretationResult(
                    action_id=action_id,
                    params=params,
                    confidence=0.9,
                )

        # 3. Use existing ParsedIntent system
        from src.narrative.intent_parser import ParsedIntent, ActionCategory, ActionType
        # Map ParsedIntent to action_id
        parsed = self._parse_with_existing_system(text, current_state)
        action_id = self._map_parsed_to_action_id(parsed, current_state)

        if action_id:
            return InterpretationResult(
                action_id=action_id,
                params=self._extract_params(parsed),
                confidence=parsed.confidence,
            )

        # 4. Request clarification
        valid_actions = self.registry.get_valid_actions(current_state)
        return InterpretationResult(
            action_id="",
            params={},
            confidence=0.0,
            requires_clarification=True,
            clarification_question=f"I'm not sure what you mean. Did you want to:",
            alternatives=[a.display_name for a in valid_actions[:5]],
        )

    def _build_quick_patterns(self) -> dict:
        return {
            "search": ("dungeon.search", None),
            "listen": ("dungeon.listen", None),
            "rest": ("downtime.rest", None),
            "attack": ("combat.attack", self._extract_attack_target),
            "flee": ("combat.flee", None),
            "parley": ("encounter.parley", None),
            "talk to": ("settlement.talk", self._extract_npc_target),
            "travel to": ("wilderness.travel", self._extract_hex_id),
            "go ": ("dungeon.move", self._extract_direction),
        }
```

---

### Phase 7: Build ChatCLI

**Goal:** Add conversation-mode CLI alongside existing command CLI

**File to modify:** `src/main.py`

```python
class ChatCLI:
    """
    Conversation-first CLI interface.

    Displays:
    - DM narration
    - Numbered suggested actions
    - Accepts free text or number selection
    """

    def __init__(self, virtual_dm: VirtualDM):
        self.vdm = virtual_dm
        self.facade = ConversationFacade(
            controller=virtual_dm.controller,
            engines={
                'hex_crawl': virtual_dm.hex_crawl,
                'dungeon': virtual_dm.dungeon,
                'combat': virtual_dm.combat,
                'encounter': virtual_dm.encounter,
                'settlement': virtual_dm.settlement,
                'downtime': virtual_dm.downtime,
            },
            dm_agent=virtual_dm._dm_agent,
        )
        self.last_suggestions: list[SuggestedAction] = []

    def run(self):
        """Main chat loop."""
        print("=== Dolmenwood Virtual DM (Conversation Mode) ===")
        print("Type naturally or select a numbered action. Type 'quit' to exit.\n")

        # Initial state display
        self._display_state()
        self._display_suggestions()

        while True:
            try:
                user_input = input("\n> ").strip()
                if user_input.lower() in ('quit', 'exit', 'q'):
                    break
                if not user_input:
                    continue

                # Process input
                response = self.facade.handle_chat(
                    text=user_input,
                    actor_id="player",
                )

                # Display response
                self._display_response(response)

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")

    def _display_response(self, response: TurnResponse):
        """Display a turn response."""
        # Clarification needed?
        if response.clarification:
            print(f"\n{response.clarification.question}")
            for i, opt in enumerate(response.clarification.options, 1):
                print(f"  {i}. {opt}")
            return

        # Mechanical results
        if response.mechanical_summary:
            summary = response.mechanical_summary
            status = "SUCCESS" if summary.success else "FAILED"
            if summary.partial_success:
                status = "PARTIAL"
            print(f"\n[{status}]", end="")
            if summary.dice_results:
                dice_str = ", ".join(
                    f"{d.get('notation', '?')}: {d.get('total', '?')}"
                    for d in summary.dice_results
                )
                print(f" Dice: {dice_str}", end="")
            print()

        # Narration
        if response.narration:
            print(f"\n{response.narration}")

        # Warnings
        for warning in response.warnings:
            print(f"⚠ {warning}")

        # Update and display suggestions
        self.last_suggestions = response.suggested_actions
        self._display_suggestions()

    def _display_suggestions(self):
        """Display numbered action suggestions."""
        if not self.last_suggestions:
            return

        print("\n--- Actions ---")
        for i, action in enumerate(self.last_suggestions, 1):
            status = "" if action.enabled else f" (disabled: {action.reason_disabled})"
            print(f"  {i}. {action.display_text}{status}")

    def _display_state(self):
        """Display current game state summary."""
        state = self.facade.get_state()
        print(f"State: {state.get('game_state', 'unknown')}")
        time_info = state.get('time', {})
        print(f"Time: {time_info.get('date', '?')} {time_info.get('time', '?')}")
```

**CLI entry point modification:**
```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['command', 'chat'], default='chat')
    # ... other args

    args = parser.parse_args()
    vdm = VirtualDM(config)

    if args.mode == 'chat':
        cli = ChatCLI(vdm)
    else:
        cli = DolmenwoodCLI(vdm)

    cli.run()
```

---

### Phase 8: Integrate Mythic Oracle into SpellResolver

**Goal:** Wire Tier-4 spell adjudication for open-ended spells

**File to modify:** `src/narrative/spell_resolver.py`

```python
# Add to SpellResolver class

def resolve_cast(self, spell_data: SpellData, context: dict) -> ResolutionResult:
    """Resolve spell casting."""
    tier = self._determine_tier(spell_data)

    if tier <= 3:
        return self._resolve_mechanical_spell(spell_data, context)
    else:
        return self._resolve_tier4_spell(spell_data, context)

def _resolve_tier4_spell(self, spell_data: SpellData, context: dict) -> ResolutionResult:
    """Resolve open-ended spell via Mythic oracle."""
    from src.oracle import MythicGME, MythicSpellAdjudicator
    from src.oracle.effect_commands import EffectCommandBuilder, EffectValidator, EffectExecutor

    # Get oracle from controller
    oracle = self.controller.get_oracle()
    adjudicator = MythicSpellAdjudicator(oracle)

    # Build adjudication context
    adj_context = AdjudicationContext(
        spell_id=spell_data.spell_id,
        spell_name=spell_data.name,
        caster_id=context.get('caster_id'),
        target_description=context.get('target_description'),
        situation=context.get('situation_description'),
        chaos_factor=oracle.chaos_factor,
    )

    # Adjudicate via oracle
    result = adjudicator.adjudicate(adj_context)

    # If LLM interpretation available, use it
    if self._llm_interpreter:
        interpretation = self._llm_interpreter.interpret(result)
        effects = EffectCommandBuilder.build_from_interpretation(interpretation)

        # Validate effects
        validator = EffectValidator(self.controller)
        validated = validator.validate(effects)

        if validated.is_valid:
            # Execute effects
            executor = EffectExecutor(self.controller)
            executor.execute(validated.commands)

    return ResolutionResult(
        success=result.success_level in [SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS],
        adjudication_result=result,
        # ... other fields
    )
```

**File to modify:** `src/game_state/global_controller.py`

```python
# Add oracle accessor

def get_oracle(self) -> "MythicGME":
    """Get or create the Mythic GME oracle instance."""
    if not hasattr(self, '_oracle'):
        from src.oracle import MythicGME
        self._oracle = MythicGME(chaos_factor=5)  # Default chaos
    return self._oracle

def set_chaos_factor(self, factor: int) -> None:
    """Set the Mythic chaos factor (1-9)."""
    self.get_oracle().chaos_factor = max(1, min(9, factor))
```

---

## Implementation Sequence (Dependency Order)

```
Phase 1: Wire Narration Callbacks
    ↓ (no dependencies)
Phase 2: Create Conversation Package Foundation (types.py, state_export.py)
    ↓
Phase 3: Build ActionRegistry
    ↓ (depends on Phase 2 types)
Phase 4: Build SuggestionBuilder
    ↓ (depends on Phase 3 registry)
    ↓ (parallel) Add engine context accessors
Phase 5: Build ConversationFacade
    ↓ (depends on Phases 3, 4)
Phase 6: Build IntentInterpreter
    ↓ (depends on Phase 3 registry)
Phase 7: Build ChatCLI
    ↓ (depends on Phase 5 facade)
Phase 8: Integrate Mythic Oracle
    (independent, can run in parallel with 3-7)
```

---

## Engine Context Accessors (Phase 4 Parallel Work)

### DungeonEngine additions (`src/dungeon/dungeon_engine.py`)

```python
def get_current_room(self) -> Optional[DungeonRoom]:
    """Get the current room the party is in."""
    if not self.state or not self.state.current_room:
        return None
    return self.state.rooms.get(self.state.current_room)

def get_dungeon_context(self) -> dict[str, Any]:
    """Get dungeon exploration context for suggestions."""
    room = self.get_current_room()
    return {
        "current_room_id": self.state.current_room if self.state else None,
        "exits": room.exits if room else {},
        "doors": room.doors if room else {},
        "searched": room.searched if room else False,
        "light_remaining": self._get_light_remaining(),
        "turns_since_rest": self.state.turns_since_rest if self.state else 0,
        "noise_level": self.state.noise_accumulator if self.state else 0,
        "has_map": self.state.has_map if self.state else False,
    }
```

### HexCrawlEngine additions (`src/hex_crawl/hex_crawl_engine.py`)

```python
def get_adjacent_hexes(self) -> list[str]:
    """Get IDs of hexes adjacent to current location."""
    current = self.controller.party_state.current_hex
    if not current:
        return []
    return self._calculate_adjacent_hexes(current)

def get_hex_context(self) -> dict[str, Any]:
    """Get wilderness context for suggestions."""
    return {
        "current_hex": self.controller.party_state.current_hex,
        "adjacent_hexes": self.get_adjacent_hexes(),
        "travel_points_remaining": self._get_remaining_travel_points(),
        "known_pois": self._get_known_pois(),
        "current_poi_state": self._get_current_poi_state(),
        "weather": self.controller.world_state.weather.value,
        "time_of_day": self.controller.time_tracker.game_time.get_time_of_day().value,
    }
```

### Similar additions for:
- `EncounterEngine.get_encounter_context()`
- `CombatEngine.get_combat_context()`
- `SettlementEngine.get_settlement_context()`

---

## Testing Strategy

### Unit Tests (per phase)

| Phase | Test File | Key Tests |
|-------|-----------|-----------|
| 2 | `tests/test_conversation_types.py` | TurnResponse serialization, SuggestedAction validation |
| 3 | `tests/test_action_registry.py` | Action registration, execution, state validation |
| 4 | `tests/test_suggestion_builder.py` | Suggestions per state, context-awareness |
| 5 | `tests/test_conversation_facade.py` | Full chat flow, action execution |
| 6 | `tests/test_intent_interpreter.py` | Pattern matching, ambiguity handling |
| 7 | `tests/test_chat_cli.py` | CLI integration (mock input/output) |

### Integration Tests

```python
# tests/test_conversation_integration.py

def test_full_dungeon_turn_flow():
    """Test complete dungeon exploration via conversation."""
    vdm = VirtualDM(initial_state=GameState.DUNGEON_EXPLORATION)
    facade = ConversationFacade(vdm.controller, {...})

    # Natural language
    response = facade.handle_chat("I want to search this room")
    assert response.mechanical_summary.action_id == "dungeon.search"
    assert len(response.suggested_actions) > 0

    # Numbered selection
    response2 = facade.handle_chat("1")  # Select first suggestion
    assert response2.mechanical_summary is not None

def test_state_transitions_update_suggestions():
    """Verify suggestions change when state transitions."""
    # Start in wilderness
    # Trigger encounter
    # Verify suggestions now show encounter actions
```

---

## Definition of Done

Per blueprint Section 8:

- [ ] Player can type natural language
- [ ] System returns DM response + 5-12 suggested actions
- [ ] Player can choose suggestion with a number
- [ ] All outcomes deterministic given RNG seed and RunLog
- [ ] No LLM output directly mutates state

### Verification Checklist

```
[ ] ChatCLI launches without errors
[ ] Natural language "search the room" resolves to dungeon.search
[ ] Typing "1" selects first suggested action
[ ] Suggestions update after state transitions
[ ] RunLog captures all dice rolls and transitions
[ ] Replay with same seed produces identical results
[ ] LLM narration is generated but doesn't affect mechanics
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ActionRegistry bloat | Medium | Low | Start with 20 core actions, add incrementally |
| Intent interpreter false positives | High | Medium | Conservative matching, clarification fallback |
| Engine context accessor gaps | Medium | Medium | Add accessors incrementally as needed |
| Narration callback type mismatches | Low | Low | Type hints and tests |
| State export schema drift | Medium | High | Version field, breaking change policy |

---

## Appendix: File Checklist

### New Files to Create

```
src/conversation/
├── __init__.py
├── types.py
├── state_export.py
├── action_registry.py
├── suggestion_builder.py
├── conversation_facade.py
├── intent_interpreter.py
└── ui_events.py (Phase 8 / Foundry prep)

tests/
├── test_conversation_types.py
├── test_action_registry.py
├── test_suggestion_builder.py
├── test_conversation_facade.py
├── test_intent_interpreter.py
└── test_conversation_integration.py
```

### Files to Modify

```
src/main.py
  - Add ChatCLI class
  - Wire narration callbacks in VirtualDM.__init__
  - Add --mode argument to main()

src/game_state/global_controller.py
  - Add get_oracle() method
  - Add set_chaos_factor() method

src/dungeon/dungeon_engine.py
  - Add get_current_room()
  - Add get_dungeon_context()

src/hex_crawl/hex_crawl_engine.py
  - Add get_adjacent_hexes()
  - Add get_hex_context()

src/encounter/encounter_engine.py
  - Add get_encounter_context()

src/combat/combat_engine.py
  - Add get_combat_context()

src/settlement/settlement_engine.py
  - Add get_settlement_context()

src/narrative/spell_resolver.py
  - Add Tier-4 oracle integration
  - Add _resolve_tier4_spell() method
```
