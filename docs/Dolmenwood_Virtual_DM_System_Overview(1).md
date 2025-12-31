# Dolmenwood Virtual DM — System Overview (LLM-Oriented)

This document is written as a **fast on-ramp for an LLM (or human) with direct code access**. It explains what exists, how it fits together, and where the real gaps/blockers are.

## Repository snapshot

- Poetry project: `pyproject.toml` (package name `dolmenwood-virtual-dm`, version `0.1.0`)
- Python modules: 162 total (`src/` = 116, `tests/` = 46)
- Test status in this repo: **1972 passed, 1 skipped** (`pytest -q`)

## Mental model

**Design rule:** mechanics are authoritative in Python, narration is advisory via LLM.

At runtime, the system behaves like:

1. `VirtualDM` (in `src/main.py`) constructs:
   - a `GlobalController` (authoritative game state façade)
   - engines (`HexCrawlEngine`, `DungeonEngine`, `EncounterEngine`, `CombatEngine`, `SettlementEngine`, `DowntimeEngine`)
   - optional `DMAgent` narration seams (callbacks)
   - a `SessionManager` (save/load deltas)

2. The player interacts either via:
   - CLI loop in `src/main.py`, or
   - chat-first wrapper (`ConversationFacade`) that emits `TurnResponse` + **suggested actions**.

3. Engines mutate state through `GlobalController` (characters, party resources, conditions, time, location, encounter/combat state).

## “Start here” reading order

- `src/main.py` — `VirtualDM` façade + CLI + narration seams
- `src/game_state/state_machine.py` — `GameState`, transitions, validation
- `src/game_state/global_controller.py` — authoritative state façade (party, characters, time, conditions, charms, glyphs, traps)
- `src/data_models.py` — the big domain model (HexLocation/POI, EncounterState, Combat state, items, conditions, spells types, etc.)
- `src/hex_crawl/hex_crawl_engine.py` — wilderness travel procedure, lost checks, encounter triggering, POI discovery flow
- `src/encounter/encounter_engine.py` + `src/tables/encounter_roller.py` + `src/encounter/encounter_factory.py` — encounter generation + encounter sequence
- `src/combat/combat_engine.py` — OSE/BX-ish combat sequence + spell casting hooks
- `src/dungeon/dungeon_engine.py` — dungeon turns, doors/traps/search, room movement
- `src/settlement/settlement_engine.py` — settlement procedure, services, rumors/shopping/social
- `src/downtime/downtime_engine.py` — long-term actions, rests, travel recovery
- `src/ai/dm_agent.py` + `src/ai/prompt_schemas.py` — advisory narration and prompt contracts
- `src/conversation/*` — chat-first adapter, suggestion builder, (currently duplicated) action dispatch/registry
- `src/game_state/session_manager.py` — save/load and delta application (expects base content loaded)

## Key subsystems and responsibilities

- `root` — Top-level glue (`main.py`), shared domain models (`data_models.py`), and small utilities.
- `game_state` — State machine + `GlobalController` + session persistence. Owns authoritative mutable state.
- `hex_crawl` — Wilderness travel procedure, lost/maze logic, encounter triggering, POI discovery scaffolding.
- `encounter` — Encounter sequence (parley/evade/flee) and building EncounterState objects (factory).
- `combat` — Combat loop, initiative, morale, attack resolution, and spell casting in combat.
- `dungeon` — Dungeon exploration turns, rooms, doors/traps, hazards, and navigation.
- `settlement` — Settlement exploration and services (shopping, rumors, lodging), NPC conversation entrypoints.
- `downtime` — Resting, recovery, and downtime activities.
- `tables` — Canonical Dolmenwood tables implemented as Python data + resolvers (encounters, traps, weather, fishing, treasure, etc.).
- `narrative` — Mechanical resolvers that produce `NarrationContext`s (hazards, spells, charms, glyphs, area effects).
- `content_loader` — Load/validate/import hexes/monsters/spells/items; multi-source content manager (SQLite) + optional vector index.
- `ai` — LLM provider adapters, prompt schemas, lore search, and the advisory-only `DMAgent`.
- `conversation` — Chat-first TurnResponse types + suggestion ranking + action routing façade (for UI/Foundry later).
- `integrations` — Seams for external UIs (Foundry bridge, state export).
- `observability` — Run/dice/session logging and replay helpers.

## Core runtime objects

### `VirtualDM` (`src/main.py`)
**Role:** A façade and composition root. It owns the controller, engines, session manager, and DM agent wiring.

High-value APIs:
- **State & save/load:** `get_full_state()`, `get_valid_actions()`, `save_game()`, `load_game()`, `list_saves()`
- **Character/party setup:** `create_character()`, `add_character()`, `get_character()`, `get_party()`, `set_party_resources()`
- **Primary procedures:** `travel_to_hex()`, `enter_dungeon()`, `enter_settlement()`, `rest()`
- **Narration seam methods:** `narrate_*` family (all return `Optional[str]` and should never mutate mechanics)

> Implementation note: The config flag `load_content` exists, but in the current codebase it is not wired to actually load base content into runtime engines. See Patch Plan.

### `GlobalController` (`src/game_state/global_controller.py`)
**Role:** The authoritative “single mutable source of truth” for game state.
It wraps:
- State machine transitions (`controller.transition(...)`)
- Party state (resources, location, encumbrance, movement)
- World state (date/time, weather/season, light)
- Character roster and HP/conditions/charm/glyph effects
- Encounter and combat state holders

**Rule:** engines should prefer controller methods over direct mutation.

### `GameState` / `StateMachine` (`src/game_state/state_machine.py`)
**Role:** Finite-state procedure gate. Examples:
- `WILDERNESS_TRAVEL`, `DUNGEON_EXPLORATION`, `ENCOUNTER`, `COMBAT`, `SETTLEMENT`, `DOWNTIME`
Engines and actions should check state before executing.

### `SessionManager` (`src/game_state/session_manager.py`)
**Role:** Save/load session state as deltas against immutable base content.
It **expects** that base hex/NPC definitions exist in memory when applying deltas (POI discovery, triggered alerts, etc.).

## Data model center of gravity: `src/data_models.py`
This file is intentionally broad and contains:
- **World/time:** `GameDate`, `TimeOfDay`, `TimeTracker`
- **Locations:** `HexLocation`, `PointOfInterest`, room/door/trap models
- **Party/characters:** `PartyState`, `CharacterState`, inventory/encumbrance helpers
- **Encounters/combat:** `EncounterState`, `CombatState`, combatant models
- **Conditions/effects:** `ConditionType`, charm/glyph systems, area effects
- **Spell system types:** `SpellData` + parsed mechanical fields, effect trackers

When making changes, treat `data_models.py` as the **shared contract layer** between all engines.

## Engine flow and interdependencies

### Wilderness travel: `HexCrawlEngine`
- Owns daily travel points, lost checks, and “wandering encounter” trigger.
- Depends on `GlobalController` for:
  - current state (`WILDERNESS_TRAVEL`)
  - party location updates
  - storing the active `EncounterState` when an encounter triggers
- **Needs content:** meaningful hex travel requires hex definitions (terrain, POIs, region) loaded into `self._hex_data`.

Current gaps:
- Standard encounter generation does not use `EncounterRoller` + `EncounterFactory` (it builds a mostly-empty `EncounterState`).
- Session deltas (`SessionManager.apply_*_deltas_to_hex`) are not consistently applied because base hexes are not loaded at runtime.

### Encounters: `EncounterEngine`
- Runs the non-combat encounter procedure (surprise, distance, reaction/parley, evasion, flee/pursuit).
- Uses `MovementCalculator` and party/actor speeds (some TODOs still use constants).
- Interacts with combat by transitioning to `COMBAT` and calling `CombatEngine.start_combat(...)` (depending on caller flow).

### Combat: `CombatEngine`
- Resolves initiative, attacks, damage, morale, and round structure.
- Has a `SpellResolver` hook, but **VirtualDM does not load spell data** or inject a controller-aware resolver by default.

### Dungeon: `DungeonEngine`
- Handles dungeon exploration turns, doors/traps/search mechanics, and room movement.
- One explicit TODO: if an interaction consumes an item, it does not yet remove it from inventory.

### Settlement/Downtime engines
- Implement generic procedures, but are not currently driven by imported settlement data (no settlement JSON in this repo).

## Conversation-first adapter (`src/conversation`)
This is the “UI seam”:
- `TurnResponse` carries messages + suggested actions + a public-state snapshot.
- `SuggestionBuilder` generates ranked action suggestions by current `GameState`.
- Two competing action-routing implementations exist:
  - `ConversationFacade.handle_action(...)` uses a manual `if action_id == ...` dispatch
  - `ActionRegistry` defines canonical actions with param schemas and executors

**Gap:** unify around `ActionRegistry` so the UI has a single source of truth.

## Content system (`src/content_loader`)
The repo already contains a fairly complete content architecture:
- Multi-source content manager using SQLite (`ContentManager`)
- ContentPipeline for validation + storage + optional vector indexing
- Loaders for hexes, monsters, spells, and items in `data/content/**`

**Gap:** runtime engines do not call this during startup, so most play procedures operate on placeholder data.

## Package/module index (core packages)

### `root`
- `__init__.py`
- `data_models.py` | classes: Season, Weather, LocationType, TerrainType, EncounterType, SurpriseStatus… | functions: interpret_reaction, get_dolmenwood_year_length
- `main.py` | classes: GameConfig, VirtualDM, DolmenwoodCLI | functions: setup_logging, create_demo_session, test_hex_exploration_loop, test_encounter_loop, test_dungeon_exploration_loop, test_combat_loop…

### `game_state`
- `game_state/__init__.py`
- `game_state/global_controller.py` | classes: TimeTracker, GlobalController
- `game_state/session_manager.py` | classes: POIStateDelta, NPCStateDelta, HexStateDelta, SerializableCharacter, SerializablePartyState, SerializableWorldState…
- `game_state/state_machine.py` | classes: GameState, StateTransition, InvalidTransitionError, StateMachine

### `hex_crawl`
- `hex_crawl/__init__.py`
- `hex_crawl/hex_crawl_engine.py` | classes: POIExplorationState, POIVisit, SecretCheck, HexMagicalEffects, HexOverview, RouteType…

### `encounter`
- `encounter/__init__.py`
- `encounter/encounter_engine.py` | classes: EncounterPhase, EncounterOrigin, EncounterAction, AwarenessResult, SurpriseResult, DistanceResult…
- `encounter/encounter_factory.py` | classes: EncounterFactoryResult, EncounterFactory | functions: get_encounter_factory, reset_encounter_factory, create_encounter_from_roll, create_wilderness_encounter, start_wilderness_encounter, start_dungeon_encounter…

### `combat`
- `combat/__init__.py`
- `combat/combat_engine.py` | classes: CombatActionType, MoraleCheckTrigger, MissileRange, CoverType, CombatAction, CombatantStatus…

### `dungeon`
- `dungeon/__init__.py`
- `dungeon/dungeon_engine.py` | classes: DungeonActionType, DungeonDoomResult, DoorState, LightLevel, DungeonRoom, DungeonTurnResult…

### `settlement`
- `settlement/__init__.py`
- `settlement/settlement_engine.py` | classes: SettlementSize, LifestyleType, ServiceType, BuildingType, ConversationTopic, Building…

### `downtime`
- `downtime/__init__.py`
- `downtime/downtime_engine.py` | classes: DowntimeActivity, RestType, SleepDifficulty, BeddingType, CampState, FactionStanding…

### `narrative`
- `narrative/__init__.py`
- `narrative/creative_resolver.py` | classes: CreativeSolutionCategory, CreativeSolution, CreativeResolutionResult, CreativeSolutionResolver
- `narrative/hazard_resolver.py` | classes: HazardType, DarknessLevel, HazardResult, DivingState, HazardResolver
- `narrative/intent_parser.py` | classes: ActionCategory, ActionType, ResolutionType, CheckType, SaveType, ParsedIntent… | functions: get_hazard_rule, is_adventurer_competency
- `narrative/narrative_resolver.py` | classes: NarrationContext, ResolutionResult, NarrativeResolver
- `narrative/sensory_details.py` | classes: TimeOfDayContext, WeatherContext, TerrainContext, SensoryContext | functions: get_foraging_scene, get_fishing_scene, get_hunting_scene, get_trap_scene, get_secret_door_scene, build_narrative_hints
- `narrative/spell_context.py` | classes: RevelationType, Revelation, SpellRevelation, WrittenText, ItemHistory, CreatureHistory…
- `narrative/spell_resolver.py` | classes: DurationType, RangeType, SpellEffectType, MagicType, RuneMagnitude, UsageFrequency…

### `content_loader`
- `content_loader/__init__.py`
- `content_loader/content_manager.py` | classes: ContentType, ContentEntry, ConflictResolution, ContentManager
- `content_loader/content_pipeline.py` | classes: ValidationError, ExtractionError, ValidationResult, ImportResult, BatchImportResult, ContentValidator…
- `content_loader/hex_loader.py` | classes: HexFileMetadata, HexFileLoadResult, HexDirectoryLoadResult, HexDataLoader | functions: load_all_hexes, create_sample_hex_json
- `content_loader/monster_loader.py` | classes: MonsterFileMetadata, MonsterFileLoadResult, MonsterDirectoryLoadResult, MonsterDataLoader | functions: load_all_monsters
- `content_loader/monster_registry.py` | classes: MonsterLookupResult, StatBlockResult, NPCStatRequest, MonsterRegistry | functions: get_monster_registry, reset_monster_registry
- `content_loader/pdf_parser.py` | classes: BookType, ParsedPage, ParsedSection, ParseResult, PDFParser, TextParser
- `content_loader/spell_loader.py` | classes: SpellFileMetadata, SpellFileLoadResult, SpellDirectoryLoadResult, SpellParser, SpellDataLoader | functions: load_all_spells, register_spells_with_resolver
- `content_loader/spell_registry.py` | classes: SpellLookupResult, SpellListResult, SpellRegistry | functions: get_spell_registry, reset_spell_registry

### `ai`
- `ai/__init__.py`
- `ai/dm_agent.py` | classes: DMAgentConfig, DescriptionResult, DMAgent | functions: get_dm_agent, reset_dm_agent
- `ai/llm_provider.py` | classes: LLMProvider, LLMRole, LLMMessage, LLMResponse, LLMConfig, BaseLLMClient… | functions: get_llm_manager
- `ai/lore_search.py` | classes: LoreCategory, LoreSearchResult, LoreSearchQuery, LoreSearchInterface, NullLoreSearch, VectorLoreSearch… | functions: create_lore_search
- `ai/prompt_schemas.py` | classes: PromptSchemaType, PromptSchema, ExplorationDescriptionInputs, ExplorationDescriptionOutput, ExplorationDescriptionSchema, EncounterFramingInputs… | functions: create_schema

### `conversation`
- `conversation/__init__.py`
- `conversation/action_registry.py` | classes: ActionCategory, ActionSpec, ActionRegistry | functions: _create_default_registry, get_default_registry, reset_registry
- `conversation/conversation_facade.py` | classes: ConversationConfig, ConversationFacade
- `conversation/oracle_enhancement.py` | classes: AmbiguityType, AmbiguityDetection, OracleResolution, OracleEnhancement | functions: create_oracle_enhancement
- `conversation/state_export.py` | classes: EventStream | functions: export_public_state
- `conversation/suggestion_builder.py` | classes: _Candidate | functions: _clamp, _default_character_id, _current_hex_id, _has_light, build_suggestions, _dungeon_suggestions…
- `conversation/types.py` | classes: ChatMessage, SuggestedAction, TurnResponse

### `tables`
- `tables/__init__.py`
- `tables/action_resolver.py` | classes: ResolutionType, FailureSeverity, FailureConsequence, SuccessEffect, ActionContext, ActionResolution… | functions: prepare_skill_check, quick_skill_check
- `tables/character_tables.py` | classes: CharacterTableManager | functions: get_character_table_manager
- `tables/dolmenwood_tables.py` | classes: DolmenwoodTables | functions: get_dolmenwood_tables
- `tables/encounter_roller.py` | classes: EncounterEntryType, RolledEncounter, EncounterContext, LairCheckResult, EncounterRoller | functions: _roll_number_appearing, get_encounter_roller, roll_wilderness_encounter
- `tables/encounter_tables.py` | classes: EncounterTableManager | functions: get_encounter_table_manager
- `tables/fishing_tables.py` | classes: FishEffectType, LandingType, LandingRequirement, CatchEffect, CatchableFish | functions: roll_fish, roll_fish_rations, get_fish_by_name, get_all_fish, check_treasure_in_fish, check_first_timer_danger…
- `tables/foraging_tables.py` | classes: ForageType, EffectType, ConsumptionEffect, ForageableItem | functions: roll_forage_type, roll_foraged_item, roll_forage_quantity, get_foraged_item_by_name, get_all_fungi, get_all_plants…
- `tables/hunting_tables.py` | classes: TerrainType, AnimalSize, GameAnimal | functions: get_game_animal, get_game_animal_by_name, roll_game_animal, roll_number_appearing, roll_encounter_distance, calculate_rations_yield…
- `tables/procedure_triggers.py`
- `tables/secret_door_tables.py` | classes: SecretDoorType, MechanismType, SecretDoorLocation, MechanicalMechanism, MagicalMechanism, ClueType… | functions: roll_secret_door_type, roll_location, roll_mechanism_type, roll_mechanical_mechanism, roll_magical_mechanism, generate_clues…
- `tables/table_manager.py` | classes: TableManager | functions: get_table_manager
- `tables/table_types.py` | classes: Kindred, NameColumn, CharacterAspectType, EncounterLocationType, EncounterTimeOfDay, EncounterSeason… | functions: _infer_hex_table_category, parse_hex_roll_tables, convert_hex_tables_to_roll_tables
- `tables/trap_tables.py` | classes: TrapCategory, TrapTrigger, TrapEffectType, TrapEffect, Trap, DisarmAttempt | functions: generate_random_trap, get_trap_by_effect, get_exploration_clues, get_bypass_options, can_attempt_disarm, attempt_disarm
- `tables/treasure_tables.py` | classes: TreasureTableManager | functions: get_treasure_table_manager
- `tables/wilderness_encounter_tables.py` | classes: TimeOfDay, LocationType, EncounterCategory, EncounterEntry | functions: E, get_encounter_type_table, get_common_table, get_regional_table, get_unseason_table, get_all_regions

### `integrations`
- `integrations/foundry/__init__.py`
- `integrations/foundry/foundry_bridge.py` | classes: FoundryExportMode, FoundryEventType, FoundryEvent, FoundryStateExport, FoundryBridge

### `observability`
- `observability/__init__.py`
- `observability/replay.py` | classes: ReplayMode, ReplaySession
- `observability/run_log.py` | classes: EventType, LogEvent, RollEvent, TransitionEvent, TableLookupEvent, TimeStepEvent… | functions: get_run_log, reset_run_log


## Package dependency graph (package → imported packages)

- `advancement` → `game_state`, `root`
- `ai` → `root`, `vector_db`
- `classes` → `root`
- `combat` → `classes`, `game_state`, `narrative`, `root`
- `content_loader` → `game_state`, `narrative`, `npc`, `root`, `vector_db`
- `conversation` → `dungeon`, `encounter`, `game_state`, `observability`, `oracle`, `root`
- `downtime` → `game_state`, `root`
- `dungeon` → `game_state`, `narrative`, `root`, `tables`
- `encounter` → `classes`, `content_loader`, `game_state`, `npc`, `root`, `tables`
- `game_state` → `combat`, `hex_crawl`, `observability`, `oracle`, `root`
- `hex_crawl` → `content_loader`, `game_state`, `narrative`, `root`, `tables`
- `integrations` → `root`
- `items` → `root`, `tables`
- `kindred` → `root`
- `narrative` → `ai`, `classes`, `game_state`, `root`, `tables`
- `npc` → `classes`, `kindred`, `root`
- `oracle` → `game_state`, `root`
- `resolution` → `classes`, `root`
- `root` → `ai`, `combat`, `conversation`, `downtime`, `encounter`, `narrative`, `observability`, `tables`
- `settlement` → `game_state`, `root`
- `tables` → `content_loader`, `npc`, `observability`, `root`
- `vector_db` → `game_state`, `root`
- `weather` → `root`, `tables`

## Implementation gaps (high signal)

### Blockers (prevent “real play”)
1. **Base content is not loaded into runtime engines.** (`--load-content` exists but doesn’t populate `HexCrawlEngine`, `MonsterRegistry`, `SpellResolver`, etc.)
2. **Hex travel encounter generation is not wired to encounter tables.** `EncounterRoller` + `EncounterFactory` exist but aren’t used in `HexCrawlEngine` standard encounters.
3. **Save/load delta architecture depends on base content being present.** Without base hex/POI objects, POI deltas cannot apply meaningfully.
4. **Conversation action routing is duplicated.** Registry exists but façade uses manual dispatch; IDs must remain stable.

### Important but not blocking
- Item consumption in dungeon interactions not wired to inventory removal.
- Encounter evasion uses constant movement rates instead of party/actor movement.
- Hazard resolver has a TODO for thief lock-picking checks.
- Several conditions are documented as partial/pending; enforcement is inconsistent.
- Optional DB-backed table loading is stubbed (tables are hardcoded today).

---

For an actionable step-by-step implementation plan, see **`Dolmenwood_Virtual_DM_Patch_Plan.md`**.
