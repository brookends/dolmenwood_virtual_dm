# Dolmenwood Virtual DM — Spell Implementation Guide (LLM Coder Edition)

**Purpose:** A practical, code-oriented playbook for implementing the spells listed in:
- `Dolmenwood_Spell_Implementation_Matrix.csv` (authoritative implementation tier + subsystem tags)
- `Dolmenwood_Spell_Implementation_Matrix.json` (same data, easier for tooling)

This guide assumes you are editing the **latest repo** extracted at:
- `/mnt/data/dolmenwood_virtual_dm-main5_extracted/dolmenwood_virtual_dm-main`

It is written to be consumed by another LLM (or an engineer) that will implement spells *systematically*, while staying consistent with the existing architecture.

---

## 0) Where spells live and how they currently resolve

### Spell content (data)
Spell definitions are stored as JSON files under:

- `data/content/spells/*.json`

Each file has:
- `_metadata` (source info)
- `items[]` containing: `name`, `spell_id`, `level`, `magic_type`, `duration`, `range`, `description`, `reversible`, `reversed_name`

Example: `data/content/spells/arcane_level_1_1.json`.

### Spell runtime pipeline (code)
The current runtime pipeline for spells is:

1. **Player action → Narrative resolver**
   - `src/narrative/narrative_resolver.py`
   - `resolve_action()` → `_resolve_spell_action()` → `self.spell_resolver.resolve_spell(...)`

2. **Spell resolution**
   - `src/narrative/spell_resolver.py`
   - `resolve_spell()` performs:
     - resource checks & spend
     - per-target saving throws
     - `_apply_mechanical_effects()` (damage/heal/conditions/buffs/debuffs)
     - creates `ActiveSpellEffect` (duration/concentration tracking)
     - merges any `_handle_special_spell()` results into the `narrative_context`

3. **Game-state mutation**
   - via `GlobalController` methods (if `SpellResolver._controller` is set):
     - `apply_damage()`
     - `heal_character()`
     - `apply_condition()` / `remove_condition()`
     - `apply_buff()` / `remove_buff()` / `tick_character_modifiers_*()`
   - `src/game_state/global_controller.py`

4. **Ongoing duration ticking**
   - `GlobalController.tick_spell_effects()` → `NarrativeResolver.tick_effects()` → `SpellResolver.tick_effects()`

### Two other “spell adjacent” subsystems you can leverage
- **Area effects** (`Web`, `Silence`, etc.)
  - `AreaEffect` / `AreaEffectType` in `src/data_models.py`
  - stored on `LocationState.area_effects`
  - created/managed through `GlobalController.add_area_effect()` and `LocationState.add_area_effect()`

- **Oracle adjudication + effect command plan (Tier-4 style)**
  - `src/oracle/spell_adjudicator.py`
  - `src/oracle/effect_commands.py`
  - This is ideal for “80% good enough” handling of spells that are too complex to fully mechanize.

---

## 1) How to use the Spell Implementation Matrix

The matrix is the **source of truth** for implementation strategy. Each row gives you:

- `spell_id`, `name`, `level`, `magic_type`
- `recommended_implementation_level`: `minor | moderate | significant | skip`
- `required_subsystems`: semicolon-delimited subsystem tags
- `good_enough_80_strategy`: suggested fallback when full implementation isn’t worth it
- `source_file`: which spell JSON contains the spell

**Current counts (from matrix):**
- minor: 31
- moderate: 65
- significant: 27
- skip: 43

### “What to do” mapping by tier
- **minor**: extend parsers / wire already-existing mechanics correctly (fast, low risk)
- **moderate**: add a contained subsystem or a special handler (still deterministic)
- **significant**: requires new world/combat/state machinery; prefer “80%” unless this is a top priority
- **skip**: don’t fully mechanize; implement a clean fallback path (oracle plan + minimal state tags)

---

## 2) Pre-flight fixes (recommended before implementing many spells)

These are high-leverage fixes that prevent repeated work later.

### 2.1 Fix: AC “override” support is inconsistent
`SpellResolver._apply_mechanical_effects()` tries to call:

- `GlobalController.apply_buff(..., is_override=True)`

…but `GlobalController.apply_buff()` **does not** accept `is_override`, and `StatModifier` only supports additive `value`.

**Recommended approach:**
- Extend `StatModifier` to support **override semantics**, e.g.:
  - add `mode: Literal["add","set"] = "add"` or `is_override: bool = False`
- Update `CharacterState.get_effective_ac()` to:
  - collect all AC modifiers in context
  - if any “set” modifiers exist, use the **best/most-relevant set value**, then add additive bonuses

Files:
- `src/data_models.py` (`StatModifier`, `CharacterState.get_effective_ac`)
- `src/game_state/global_controller.py` (`apply_buff` signature + storage)
- `src/narrative/spell_resolver.py` (remove/align `is_override` usage)

This single fix unlocks correct behavior for many “AC becomes X” spells.

### 2.2 Add a real spell loader + registration step
Right now, tests construct `SpellData` manually; the game does not have a single obvious “load all spells” step.

**Create a new loader module** (recommended location):
- `src/content_loader/spell_loader.py`

Responsibilities:
- iterate `data/content/spells/*.json`
- create `SpellData` instances
- parse raw fields (`duration`, `range`, `description`) into:
  - `duration_type`, `duration_value`, `duration_per_level`
  - `range_type`, `range_feet` (and possibly `area_radius`)
  - `save_type`, `save_negates`, `save_halves` (if you add halves)
  - `effect_type` heuristic (or keep default HYBRID)
- register spells into `SpellResolver` via `register_spell(spell: SpellData)`

Then call it during startup, e.g. in:
- `NarrativeResolver.__init__()` (after `self.spell_resolver` is created)
  - or `GlobalController.__init__()` right after resolver initialization

### 2.3 Decide: “mechanics-first” vs “oracle-first” for complex spells
You already have an oracle adjudication stack. For **significant/skip** spells, prefer:
- deterministic **state tags** (conditions, area effects, buffs)
- plus oracle plan + narration for the rest

This prevents the engine from becoming an unbounded physics simulator.

---

## 3) A repeatable implementation workflow per spell

For each spell row in the matrix:

1. **Locate the spell data**
   - open `data/content/spells/{source_file}` and find `items[]` entry for the `spell_id`

2. **Ensure the spell loads into the spell registry**
   - `SpellResolver.register_spell(SpellData)`
   - confirm `SpellResolver.get_spell(spell_id)` returns it

3. **Choose the implementation pattern**
   - parser-only (minor)
   - special handler (moderate)
   - new subsystem module (moderate/significant)
   - oracle fallback (skip)

4. **Add/extend mechanics**
   - parser enhancements: `SpellResolver.parse_mechanical_effects()`, `parse_level_scaling()`, `parse_target_restrictions()`
   - effect application: `SpellResolver._apply_mechanical_effects()`
   - world/area effects: `AreaEffect` + `GlobalController.add_area_effect()`
   - durations: `ActiveSpellEffect` + `SpellResolver.tick_effects()` hooks

5. **Add tests**
   - parser tests: `tests/test_spell_resolver.py`
   - state mutation tests: create a minimal `GlobalController` + characters, then call `resolve_spell()`
   - duration ticking tests: call `GlobalController.tick_spell_effects()` and assert expiration / recurring saves

6. **Update suggested-action UI hooks (optional but recommended)**
   - whenever a spell creates an effect you can track, generate a suggested action such as:
     - “Dismiss effect”
     - “Apply concentration break”
     - “Roll recurring save”
     - “Apply area effect entry damage”
   - This will later map cleanly to Foundry/VTT UI.

---

## 4) Implementation patterns (copy/paste mental models)

### Pattern A — Pure mechanical (damage/heal/condition/buff)
Use when `required_subsystems` is empty or only parser-related.

Touchpoints:
- `SpellResolver.parse_mechanical_effects()`
- `SpellResolver._apply_mechanical_effects()`

Ensure:
- saving throw text sets `effect.save_type`, `effect.save_negates`, `effect.save_halves`
- state mutation goes through `GlobalController` (not directly editing character objects)

### Pattern B — Special handler (one-off bespoke)
Use when the spell interacts with inventory, doors, inscriptions, etc.

Touchpoints:
- `SpellResolver._handle_special_spell()` handler map
- implement `_handle_<spell_id>()` near the bottom of `spell_resolver.py` or in a dedicated helper

Rule of thumb:
- **Keep special handlers side-effectful but reversible**, with explicit output in `narrative_context`.

### Pattern C — Persistent effect (duration / concentration)
Use when effects last beyond the cast moment.

Touchpoints:
- Create `ActiveSpellEffect` in `resolve_spell()`
- Extend `SpellResolver.tick_effects()` to:
  - apply per-turn/per-round ongoing mechanics (damage over time)
  - run recurring saves (daily/hourly/per-turn)
  - end effect cleanly (remove buffs/conditions, dismiss area effects)

### Pattern D — Area effect (location-based)
Use for `zones:*` and many `world:*` tags.

Touchpoints:
- `AreaEffect` in `src/data_models.py`
- `LocationState.add_area_effect()`
- `GlobalController.add_area_effect()` / `tick_location_effects()`

Recommendation:
- Prefer `AreaEffect` over inventing new “zone” primitives.

### Pattern E — Oracle fallback (“80% good enough”)
Use for **skip** spells or **significant** spells with high complexity.

Touchpoints:
- `src/oracle/spell_adjudicator.py`
- `src/oracle/effect_commands.py`

Approach:
- Ask the oracle/LLM to return **EffectCommands** (apply_condition, apply_area_effect, apply_damage, etc.)
- Execute only the commands you can validate + safely apply
- Narrate everything else

---

## 5) Subsystem tag playbooks (required_subsystems)

Below are the subsystem tags used in the matrix and what to implement for each.
Treat this as a checklist: implement the subsystem once, then many spells “unlock”.

### A) Parser / resolution tags

#### `spell_parser:flat_damage`
Some spells say “1 damage per round” (no dice notation).

Add to `SpellResolver.parse_mechanical_effects()`:
- regex for flat damage like: `r"(\d+)\s+(?:points?\s+of\s+)?damage(?:\s+per\s+(round|turn))?"`
Store as:
- either `damage_dice = "1"` (not ideal), or add a new `flat_damage: Optional[int]`
Recommended: extend `MechanicalEffect` with `flat_damage: Optional[int]` to avoid abusing dice strings.

Also update `_apply_mechanical_effects()` to apply flat damage.

#### `spell_resolution:death_effects`
Save-or-die (“save vs doom or die/destroyed”).

Implementation:
- extend `MechanicalEffect` with `is_death_effect: bool` and/or `death_on_failed_save: bool`
- in `_apply_mechanical_effects()`, if failed save:
  - set HP to 0 via `GlobalController.apply_damage(target_id, huge_number, ...)` or add `kill_character()`
  - record in `SpellCastResult` (e.g., `instant_deaths: [target_id]`)

#### `saves:spell`
This tag just indicates “Save vs Spell” (already supported). Ensure the save parser catches the exact “Save Versus Spell” wording used in descriptions.

#### `saves:daily`
Used for charm-like spells where the target can save again each day.

Implementation:
- Use `ActiveSpellEffect` fields:
  - `recurring_save_type = "spell"` (or doom)
  - `recurring_save_frequency = "daily"`
  - `recurring_save_ends_effect = True`
- Extend `SpellResolver.tick_effects()`:
  - read `controller.time_tracker.days`
  - if day advanced since `last_save_check_day`, roll save
  - on success: end effect and remove any applied conditions/buffs

### B) Targeting tags

#### `targeting:filters`
Enforce “living only”, “level X or lower”, “HD X or fewer”.

You already have:
- `SpellResolver.parse_target_restrictions()`
- `SpellResolver.filter_valid_targets()`

Hook it earlier:
- before saving throws, filter `all_targets` using a `get_target_info` callback from controller.

#### `targeting:hd_budget`
“Lowest HD first up to total budget (e.g., 4d8 HD).”

Implementation (best as a helper in `SpellResolver`):
- compute HD budget: roll dice via `dice_roller`
- obtain target HDs via `get_target_info()`
- sort ascending by HD
- select until budget exhausted
- only then proceed with saves/effects

### C) Buff / modifier tags

#### `buffs:multi_target`
Spells that apply buffs to many targets (e.g., Bless-like, Haste-like).

Implementation:
- ensure `resolve_spell()` supports `target_ids` lists properly (it does)
- for convenience, add a helper to auto-expand targets in an encounter:
  - `GlobalController.get_encounter_participants(side="allies"|"enemies")`

#### `buffs:immunity`
“Immune to normal missiles”, “summoned creatures immune”, etc.

Implementation options:
1) Add an `immunities: list[str]` list to `CharacterState` (simple)
2) Or implement as a typed condition: `ConditionType.IMMUNE_MISSILES`
3) Or implement as a stat modifier with special `stat="immunity"` and structured payload (less clean)

Prefer (1) or (2). Then ensure:
- combat damage application checks immunities.

#### `buffs:stat_override`
Feeblemind-style “INT becomes 3”.

Implementation:
- extend `StatModifier` as described (set/override mode)
- extend `CharacterState.get_effective_ability()` to apply overrides for STR/DEX/CON/INT/WIS/CHA
- wire SpellResolver to apply a “set INT = 3” modifier

### D) Conditions / control tags

#### `control:charm`
Needs a “charmed” condition with behavioral consequences.

Minimum viable:
- Apply `Condition(condition_type="charmed", ...)` via controller
- Store `source_spell_id` + `caster_id` on the condition (add fields if missing)
- Provide helper “is_hostile_to(caster)” checks in combat AI (later)

Paired with `saves:daily`, this becomes durable.

#### `conditions:confusion`
Confusion requires per-round behavior rolls.

Implementation:
- represent confusion as a condition
- add a combat hook at round start:
  - roll 1d6 / table and emit a “forced action” suggestion
- simplest place: `CombatEngine` or wherever rounds advance (search for round loop)

#### `conditions:entangle`
Used by Web/Entangle.

Implementation:
- can be a condition on a target PLUS an area effect in the location
- escape uses `escape:strength_check`

#### `conditions:stasis`
“Cannot act/move; maybe invulnerable”.

Implementation:
- apply condition
- in combat engine, skip actions
- if invulnerable, add an immunity tag during stasis

### E) Combat-structure tags

#### `combat:mirror_images`
Mirror Image needs a per-attack “image absorbs hit” mechanic.

Implementation:
- store `mirror_images_count` on the target (new field on `CharacterState` or a condition payload)
- when target is attacked:
  - roll to see if an image is hit
  - if yes: decrement count, negate damage
- add suggested actions in CLI: “Resolve mirror image hit check”

#### `combat:extra_actions`
Haste-like “extra attack / double movement”.

Implementation:
- simplest: buff that modifies effective attacks list or grants “extra_action” token per round
- integrate at combat action generation layer (the place that builds suggested actions)

#### `combat:behavior_table`
Confusion/fear/compulsion tables. Implement a single generic “behavior table resolver” and reuse it.

#### `morale:checks`
If spells trigger morale saves, integrate with existing morale system for retainers/monsters.

### F) Concentration + casting restriction tags

#### `concentration:loss_rules`
If the engine doesn’t currently break concentration on damage:
- hook `GlobalController.apply_damage()` to notify `SpellResolver.break_concentration(caster_id)`
- then remove any associated buffs/area effects

#### `zones:silence` and `spellcasting:verbal_lockout`
Silence should block spells with verbal components.

Implementation:
- represent Silence as an `AreaEffect(effect_type=SILENCE, blocks_sound=True)`
- when casting, check:
  - is caster inside a silence effect?
  - does the spell require speech? (you may need a field on `SpellData`, or assume most do and allow overrides)
- if blocked, `can_cast_spell()` returns False with reason

#### `spellcasting:interception`
Anti-magic ward that blocks spells of certain ranks.

Implementation:
- before resolving a spell, query active `AreaEffect.blocks_magic` or `ActiveSpellEffect` on target/area
- if blocked, cancel spell and narrate “ward intercepts”

### G) World / location tags

#### `world:doors_locks`, `world:glyphs`, `traps:glyphs`
Use `LocationState.doors` (currently dicts) and extend door records to include:
- `lock_type`, `is_magical_lock`, `glyphs: [glyph_id]`, `password`, etc.

Prefer adding a small dataclass wrapper (optional) but keep JSON-serializable.

Knock/Glyph spells then:
- locate door by direction/id
- mutate door record

#### `world:barriers`, `world:temporary_passage`
Create area effects that block movement (barrier) or create temporary traversal rules (passage).

#### `world:terrain_tags`, `zones:hazards`, `zones:terrain_web`, `zones:mobile_radius`
Implement these as:
- `AreaEffect` entries with:
  - `blocks_movement`, `damage_per_turn`, `save_type`, etc.
- plus lightweight terrain tags on `LocationState` (e.g., `terrain_tags: set[str]` or use `discovery_flags`)

### H) Summoning tags

#### `summoning:creatures`, `summoning:elemental`, `summoning:undead_control`, `summoning:control_rules`
Summons are best implemented as:
- create new `MonsterState`/NPC records (or simplified “Summon” objects)
- add them to the encounter participants
- store `summoner_id` and a duration effect to auto-dismiss

Control rules:
- treat as a “pet AI” with command suggestions
- for undead control, include a daily/turn check for rebellion if required

### I) Movement tags

#### `movement:flight_state`, `movement:verticality`
Minimum viable:
- add `movement_modes` to `CharacterState` (or reuse polymorph overlay’s fields without needing polymorph)
- store `altitude` as a simple int or enum
- update targeting rules to respect “out of reach” when airborne

### J) Illusion / deception tags

#### `deception:illusions`
Best implemented as:
- `AreaEffect(effect_type=ILLUSION, ...)` + narrative payload
- optionally: a “disbelief save” when a creature interacts with it

### K) Travel tags

#### `travel:familiarity`, `travel:mishap_table`, `travel:shadow_doors`
These are campaign-scale mechanics; implement as oracle-first unless they are central.

Minimum:
- add travel state flags to `WorldState` or `PartyState`
- use oracle to generate route outcomes & mishaps
- store results as journal entries + tags on visited locations

---

## 6) Test plan templates

### Parser tests
File: `tests/test_spell_resolver.py`

Add new tests for each added parsing rule:
- flat damage
- death phrases (“or die”, “or destroyed”)
- “Save Versus <type>” variants
- AC override w/ context (“vs missiles”)

### State mutation tests
Create a tiny harness:
- make `GlobalController()`
- add two `CharacterState` entries (caster + target)
- create `SpellData` for the spell under test
- call `controller.get_narrative_resolver().spell_resolver.resolve_spell(...)`
- assert:
  - HP changed
  - conditions/buffs applied
  - active effect created when appropriate

### Duration ticking tests
- cast a duration spell
- call `controller.tick_spell_effects("turns")` N times
- assert expiration removes buffs/conditions if you implement cleanup
- for `saves:daily`, advance day and assert recurring saves run

---

## 7) Practical “phase plan” for implementing lots of spells quickly

1) **Loader + parsing baseline** (unblocks real play)
2) **Buff override + immunity** (Feeblemind, wards, etc.)
3) **Area effects** (Web, Silence, fog/darkness)
4) **Charm + recurring saves** (Ingratiate/Dominate/etc.)
5) **Combat hooks** (Mirror Image, Confusion)
6) **Summoning** (only if you truly need it)
7) Everything else via oracle fallback

---

## 8) Files you will touch most often

- `src/narrative/spell_resolver.py`
- `src/narrative/narrative_resolver.py`
- `src/game_state/global_controller.py`
- `src/data_models.py`
- `src/oracle/spell_adjudicator.py`
- `src/oracle/effect_commands.py`
- `data/content/spells/*.json`
- `tests/test_spell_resolver.py`

---

## 9) Appendix: Subsystem tags list (from matrix)

- ai:command_interface
- buffs:immunity
- buffs:multi_target
- buffs:stat_override
- combat:behavior_table
- combat:extra_actions
- combat:mirror_images
- compulsion:oath_clock
- concentration:loss_rules
- conditions:confusion
- conditions:entangle
- conditions:stasis
- control:charm
- curses:tracking
- deception:illusions
- escape:strength_check
- interaction:telekinesis
- memory:last_round_state
- morale:checks
- movement:flight_state
- movement:verticality
- penalties:escalation
- random:2in6_checks
- saves:daily
- saves:spell
- spell_parser:flat_damage
- spell_resolution:death_effects
- spellcasting:interception
- spellcasting:verbal_lockout
- summoning:control_rules
- summoning:creatures
- summoning:elemental
- summoning:undead_control
- targeting:filters
- targeting:hd_budget
- transformation:form_templates
- traps:glyphs
- travel:familiarity
- travel:mishap_table
- travel:shadow_doors
- visibility:states
- world:barriers
- world:doors_locks
- world:glyphs
- world:temporary_passage
- world:terrain_tags
- zones:hazards
- zones:mobile_radius
- zones:silence
- zones:terrain_web

