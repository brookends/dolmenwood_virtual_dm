# Dolmenwood Virtual DM — Patch Plan for Remaining Spells (Including “Skip”)

This patch plan targets **all spells that currently produce zero parsed mechanical effects** in `SpellResolver.parse_mechanical_effects()` and therefore have no reliable gameplay impact. It is designed to be **directly actionable for an LLM** that can edit the repository.

---

## Scope

- Implement the **43 remaining spells** that currently do not yield parsed mechanical effects:
  - **17 Moderate** (best solved via special handlers + small model extensions)
  - **5 Significant** (require subsystem integration, but many supporting data-model hooks already exist)
  - **21 Skip** (oracle-first execution with optional lightweight tags; no full mechanical parsing required)

Primary code touchpoints:
- `src/narrative/spell_resolver.py` (handlers + orchestration)
- `src/game_state/global_controller.py` (oracle adjudication, buffs, conditions, dispels)
- `src/data_models.py` (new/extended state models: doors/locks, area effects, stasis, soul receptacles, transformation templates)

---

## Definition of Done

A spell is considered “implemented” if **casting it** results in at least one of:
1. **State change** (condition, buff, item/resource creation, location/area effect, etc.)
2. **Tracked ongoing effect** (`ActiveSpellEffect` stored and visible via existing effect inspection)
3. **Oracle adjudication** executed and returned (for “skip” spells), with outcome captured in narration context

Add a test that asserts every spell in `data/content/spells/**.json` satisfies (1) or (2) or (3).

---

## Remaining Spell Inventory (43)

| tier | name | spell_id | level | magic_type | duration | range | source_file | required_subsystems | good_enough_80_strategy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| moderate | Detect Disguise | detect_disguise | 1 | divine | Instant | 60′ | hidden_spells.json |  |  |
| moderate | Ventriloquism | ventriloquism | 1 | arcane | 2 Turns | 60' | arcane_level_1_2.json |  |  |
| moderate | Arcane Cypher | arcane_cypher | 2 | arcane | Permanent | 5' | arcane_level_2_1.json |  |  |
| moderate | En Croute | en_croute | 2 | arcane | Special | 20′ | hidden_spells.json |  |  |
| moderate | Animal Growth | animal_growth | 3 | divine | 12 Turns | 120' | holy_level_3.json |  |  |
| moderate | Dispel Magic | dispel_magic | 3 | arcane | Instant | 120' | arcane_level_3_1.json |  |  |
| moderate | Ginger Snap | ginger_snap | 3 | arcane | 1d6 Rounds | 30′ | hidden_spells.json |  |  |
| moderate | Serpent Glyph | serpent_glyph | 3 | arcane | Permanent until triggered | Touch | arcane_level_3_2.json | conditions:stasis;traps:glyphs;world:doors_locks;world:glyphs |  |
| moderate | Create Water | create_water | 4 | divine | Permanent | Touch | holy_level_4.json |  |  |
| moderate | Air Sphere | air_sphere | 5 | arcane | 1 Turn per Level | 10′ around the caster | arcane_level_5_1.json |  |  |
| moderate | Create Food | create_food | 5 | divine | Permanent | Appears in the caster's presence | holy_level_5.json |  |  |
| moderate | Trap the Soul | trap_the_soul | 6 | arcane | Instant | 20′ | hidden_spells.json |  |  |
| moderate | Deathly Blossom | deathly_blossom | lesser | rune | 1 Turn or until used | Appears in caster's hand | lesser_runes.json |  | Implement as bounded tags + time costs; narrate with oracle checks for ambiguous outcomes; avoid full spatial simulation. |
| moderate | Awe | awe |  | fairy_glamour | 1d4 Rounds | 30' | glamours.json | morale:checks | Implement as bounded tags + time costs; narrate with oracle checks for ambiguous outcomes; avoid full spatial simulation. |
| moderate | Fool's Gold | fools_gold |  | fairy_glamour | 1d6 minutes | Coins touched | glamours.json | deception:illusions;saves:spell | Implement as bounded tags + time costs; narrate with oracle checks for ambiguous outcomes; avoid full spatial simulation. |
| moderate | Lock Singer | lock_singer |  | knack |  |  | knacks.json |  | Implement as bounded tags + time costs; narrate with oracle checks for ambiguous outcomes; avoid full spatial simulation. |
| moderate | Through the Keyhole | through_the_keyhole |  | fairy_glamour | Instant | Door touched | glamours.json | world:doors_locks | Model doors/locks/glyphs as stateful objects on exits/POI gates (LOCKED/BARRED/SEALED). Avoid geometry; treat barriers as blocking a connection with optional save/damage on passing. |
| significant | Levitate | levitate | 2 | arcane | 6 Turns +1 per Level | The caster | arcane_level_2_2.json | movement:flight_state;movement:verticality | Implement as bounded tags + time costs; narrate with oracle checks for ambiguous outcomes; avoid full spatial simulation. |
| significant | Polymorph | polymorph | 4 | arcane | 1d6 Turns + 1 Turn per Level or permanent | 60′ | arcane_level_4_2.json | transformation:form_templates | Use curated form templates with fixed movement/attacks/senses; swap combat stats only; keep identity/inventory; end effect restores prior sheet snapshot. |
| significant | Holy Quest | holy_quest | 5 | divine | Until quest is completed | 30′ | holy_level_5.json | compulsion:oath_clock;penalties:escalation | Track a compulsion object (goal + violation triggers + escalation clock). On violation apply bounded penalties (attack/save penalty, HP loss, exhaustion) at intervals; oracle handles nuanced edge cases. |
| significant | Passwall | passwall | 5 | arcane | 3 Turns | 30' | arcane_level_5_2.json | world:temporary_passage | Implement as bounded tags + time costs; narrate with oracle checks for ambiguous outcomes; avoid full spatial simulation. |
| significant | Telekinesis | telekinesis | 5 | arcane | Concentration (up to 6 Rounds) | 120' | arcane_level_5_2.json | interaction:telekinesis | Implement as bounded tags + time costs; narrate with oracle checks for ambiguous outcomes; avoid full spatial simulation. |
| skip | Detect Evil | detect_evil | 1 | divine | 6 Turns | 120' | holy_level_1.json |  | Use existing providers (if any) to supply factual context to the narrator; resolve uncertainty with Mythic fate checks; avoid committing new world facts without explicit player confirmation. |
| skip | Detect Magic | detect_magic | 1 | divine | 2 Turns | 60' | holy_level_1.json |  | Use existing providers (if any) to supply factual context to the narrator; resolve uncertainty with Mythic fate checks; avoid committing new world facts without explicit player confirmation. |
| skip | Dweomerlight | dweomerlight | 2 | arcane | 6 Turns | 30' | arcane_level_2_1.json |  | Use existing providers (if any) to supply factual context to the narrator; resolve uncertainty with Mythic fate checks; avoid committing new world facts without explicit player confirmation. |
| skip | Find Traps | find_traps | 2 | divine | 2 Turns | 30' | holy_level_2.json |  | Use existing providers (if any) to supply factual context to the narrator; resolve uncertainty with Mythic fate checks; avoid committing new world facts without explicit player confirmation. |
| skip | Mind Crystal | mind_crystal | 2 | arcane | 12 Turns | 60′ | arcane_level_2_2.json |  | Use existing providers (if any) to supply factual context to the narrator; resolve uncertainty with Mythic fate checks; avoid committing new world facts without explicit player confirmation. |
| skip | Reveal Alignment | reveal_alignment | 2 | divine | Instant | 30' | holy_level_2.json |  | Use existing providers (if any) to supply factual context to the narrator; resolve uncertainty with Mythic fate checks; avoid committing new world facts without explicit player confirmation. |
| skip | Fabricate | fabricate | 5 | arcane | Permanent | 60′ | arcane_level_5_1.json |  | Handle via oracle/LLM adjudication + bounded EffectCommands (add/remove condition, damage/heal, spawn generic NPC/creature, item create/remove). Require player to state intent + limits. |
| skip | Move Terrain | move_terrain | 6 | arcane | 6 Turns | 240' | arcane_level_6_2.json | world:terrain_tags | Handle via oracle/LLM adjudication + bounded EffectCommands (add/remove condition, damage/heal, spawn generic NPC/creature, item create/remove). Require player to state intent + limits. |
| skip | Oracle | oracle | 6 | arcane | 1d6 Turns | The caster | arcane_level_6_2.json |  | Handle via oracle/LLM adjudication + bounded EffectCommands (add/remove condition, damage/heal, spawn generic NPC/creature, item create/remove). Require player to state intent + limits. |
| skip | Fairy Steed | fairy_steed | greater | rune | Until dawn | Appears in the caster's presence | greater_runes.json |  | Use existing providers (if any) to supply factual context to the narrator; resolve uncertainty with Mythic fate checks; avoid committing new world facts without explicit player confirmation. |
| skip | Rune of Wishing | rune_of_wishing | mighty | rune | Permanent | Unlimited | mighty_runes.json |  | Handle via oracle/LLM adjudication + bounded EffectCommands (add/remove condition, damage/heal, spawn generic NPC/creature, item create/remove). Require player to state intent + limits. |
| skip | Summon Wild Hunt | summon_wild_hunt | mighty | rune | 1d6 hours or until successful | Appears in the caster's presence | mighty_runes.json |  | Handle via oracle/LLM adjudication + bounded EffectCommands (add/remove condition, damage/heal, spawn generic NPC/creature, item create/remove). Require player to state intent + limits. |
| skip | Beguilement | beguilement |  | fairy_glamour | 1d4 Rounds | 30' | glamours.json |  | Narrate effect; optionally apply a small mechanical tag/bonus (advantage/disadvantage, reaction modifier) for 1 scene/turn; use oracle for edge cases. |
| skip | Bird Friend | bird_friend |  | knack |  |  | knacks.json |  | Treat as narrative ability; expose a limited menu of mechanical tags when relevant (e.g., morale modifier, fainted condition) and otherwise narrate. |
| skip | Dancing Flame | dancing_flame |  | fairy_glamour | Concentration (up to 2d6 Rounds) | 60' | glamours.json |  | Narrate effect; optionally apply a small mechanical tag/bonus (advantage/disadvantage, reaction modifier) for 1 scene/turn; use oracle for edge cases. |
| skip | Disguise Object | disguise_object |  | fairy_glamour | Until touched by another | Object touched | glamours.json |  | Narrate effect; optionally apply a small mechanical tag/bonus (advantage/disadvantage, reaction modifier) for 1 scene/turn; use oracle for edge cases. |
| skip | Mirth and Malice | mirth_and_malice |  | fairy_glamour | 1 Turn | 30' | glamours.json |  | Narrate effect; optionally apply a small mechanical tag/bonus (advantage/disadvantage, reaction modifier) for 1 scene/turn; use oracle for edge cases. |
| skip | Root Friend | root_friend |  | knack |  |  | knacks.json |  | Treat as narrative ability; expose a limited menu of mechanical tags when relevant (e.g., morale modifier, fainted condition) and otherwise narrate. |
| skip | Thread Whistling | thread_whistling |  | knack |  | 30' | knacks.json |  | Treat as narrative ability; expose a limited menu of mechanical tags when relevant (e.g., morale modifier, fainted condition) and otherwise narrate. |
| skip | Wood Kenning | wood_kenning |  | knack | 1 Turn |  | knacks.json |  | Use existing providers (if any) to supply factual context to the narrator; resolve uncertainty with Mythic fate checks; avoid committing new world facts without explicit player confirmation. |
| skip | Yeast Master | yeast_master |  | knack |  |  | knacks.json |  | Treat as narrative ability; expose a limited menu of mechanical tags when relevant (e.g., morale modifier, fainted condition) and otherwise narrate. |

---

## Phase 0 — Add a Coverage Gate (prevents regressions)

### 0.1 Add a spell coverage test
Create `tests/test_spell_coverage.py`:

- Load all spell JSONs from `data/content/spells/`
- For each spell:
  - Call `SpellResolver.parse_mechanical_effects(spell)`
  - If it returns effects: OK
  - Else if spell_id is handled by special handler: OK
  - Else if spell_id is in ORACLE registry: OK
  - Else: **fail** with “spell not implemented”

This test is your new “stop-the-line” guardrail.

### 0.2 Add a developer script (optional but useful)
Add `scripts/spells/report_spell_coverage.py` that prints:
- counts by tier
- list of missing spell_ids

---

## Phase 1 — Plumbing Upgrades (enables the hardest 10% of cases)

### 1.1 Multiplier-style stat modifiers (needed for Animal Growth and future spells)
**Problem:** current buffs are additive/override (e.g., `AC becomes 17`), but some spells require **multipliers** (e.g., “double damage”).

**Patch:**
- Extend `StatModifier` (in `src/data_models.py`) with:
  - `mode: Literal["add","set","mul"] = "add"`
  - `multiplier: float = 1.0` (used when mode=="mul")
- Extend `GlobalController.apply_buff(...)` to accept `mode` and `multiplier`
- Extend the parts of combat and checks that compute:
  - damage (apply any active `damage` multipliers)
  - carry capacity / encumbrance (apply multipliers for `carry_capacity`, if used)

**Good-enough 80% implementation:**
- Only implement multipliers for:
  - `damage`
  - `carry_capacity`

### 1.2 Oracle-first spell execution path (implements all “skip” spells cleanly)
Add an explicit oracle registry (either as a dict in code, or as a JSON file under `data/system/`):

- `data/system/oracle_only_spells.json` (recommended)

At runtime:
- In `SpellResolver._handle_special_spell(...)`, add:
  - If `spell.spell_id` in oracle registry:
    - call `self._controller.adjudicate_oracle_spell(...)`
    - include result in `narrative_context["oracle_adjudication"]`
    - optionally create an `ActiveSpellEffect` if duration is non-instant

### 1.3 Door/lock state hooks (needed for Through the Keyhole, Lock Singer, Passwall adjacencies)
Confirm/extend door objects in `LocationState` (in `src/data_models.py`):
- add fields where missing:
  - `has_keyhole: bool`
  - `is_magically_sealed: bool`
  - `lock_dc: Optional[int]`
  - `magic_seal_save: Optional[str]` (default “Spell”)

Add helper in `GlobalController`:
- `find_door(location_id, door_id_or_direction) -> DoorState`
- `unlock_door(...)`, `bypass_door(...)`

### 1.4 Temporal stasis condition (needed for Serpent Glyph)
Add new condition type:
- `ConditionType.TEMPORAL_STASIS`

Behavior hooks:
- Combat: targets in temporal stasis **skip turns**, cannot be targeted by mundane attacks, and ignore ongoing damage.
- Exploration: they cannot act; timers tick down.

Represent invulnerability as a combat check in `CombatEngine.resolve_attack(...)`:
- If target has `TEMPORAL_STASIS`: auto-miss / no-effect

### 1.5 Soul receptacle model (needed for Trap the Soul)
Add:
- `SoulState` (on CharacterState): `has_soul: bool`, `soul_container_item_id: Optional[str]`
- `SoulReceptacle` (as an Item property / type): stores trapped soul identity + date trapped

Add controller helpers:
- `trap_soul(target_id, receptacle_item_id, caster_id, duration_days=30)`
- `release_soul(receptacle_item_id, target_id)`

---

## Phase 2 — Implement Moderate + Significant Spells (22 handlers)

**Rule of thumb:** Use *spell-id keyed special handlers* for anything that is:
- environmental/world-interaction heavy, or
- requires new state, or
- is primarily narrative but should still be “executable”

Implementation pattern:
1. Add a handler method: `_handle_<spell_id>(...)`
2. Register it inside `_handle_special_spell` (spell_id dispatch)
3. Mutate controller/state where appropriate
4. Return a dict merged into `SpellCastResult.narrative_context`

### 2.1 Handler stubs to create in `src/narrative/spell_resolver.py`
Create handlers for these spell_ids:

**Moderate (17):**
`air_sphere`, `animal_growth`, `arcane_cypher`, `awe`, `create_food`, `create_water`,
`deathly_blossom`, `detect_disguise`, `dispel_magic`, `en_croute`, `fools_gold`,
`ginger_snap`, `lock_singer`, `serpent_glyph`, `through_the_keyhole`, `trap_the_soul`,
`ventriloquism`

**Significant (5):**
`holy_quest`, `levitate`, `passwall`, `polymorph`, `telekinesis`

Below is the per-spell requirements distilled from your gap summary (keep these requirements as your “acceptance tests” for each handler).

#### Air Sphere
**Level:** 5 (Arcane)
**Source:** `arcane_level_5_1.json`

**Description:** When immersed in water, the caster is surrounded by a 10' radius sphere of breathable air that moves with them.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Add special handler `_handle_air_sphere()`
- **Changes needed:**
  1. Create a buff effect with `condition_context="underwater_breathing"`
  2. Track as `ActiveSpellEffect` with mobile area (10' radius centered on caster)
  3. No combat mechanics needed - purely environmental buff

**Code pattern:** Pattern C (Persistent effect with duration tracking)

---
#### Animal Growth
**Level:** 3 (Divine)
**Source:** `holy_level_3.json`

**Description:** Doubles an animal's size, damage, and carrying capacity.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Add special handler `_handle_animal_growth()`
- **Changes needed:**
  1. Add parser pattern for "double the damage" → `modifier_value=2, modifier_type="multiplier"`
  2. Add `damage_multiplier` field to `MechanicalEffect`
  3. Track as buff on target creature
  4. Add targeting restriction: "normal or giant animals only"

**Code pattern:** Pattern B (Special handler for stat modification)

---
#### Arcane Cypher
**Level:** 2 (Arcane)
**Source:** `arcane_level_2_1.json`

**Description:** Transforms text into incomprehensible arcane sigils readable only by the caster.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Pure narrative effect with oracle assistance
- **Changes needed:**
  1. Add special handler that marks target text as "encrypted"
  2. Track encryption state in world/item data
  3. Pair with Decipher spell handler for decryption

**Code pattern:** Pattern E (Oracle fallback) - mostly narrative

---
#### Awe
**Level:** N/A (Fairy Glamour)
**Source:** `glamours.json`
**Subsystems:** `morale:checks`

**Description:** Triggers a Morale Check; affected creatures flee for 1d4 Rounds.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`, `src/game_state/global_controller.py`
- **Approach:** Integrate with morale system
- **Changes needed:**
  1. Add parser pattern for "morale check" → triggers morale subsystem
  2. Implement `GlobalController.trigger_morale_check(target_ids, modifier)`
  3. Apply "fleeing" condition on failed morale
  4. Add HD-budget targeting: "creatures whose Levels total up to caster's Level"

**Code pattern:** Pattern B (Special handler) + morale subsystem

---
#### Create Food
**Level:** 5 (Divine)
**Source:** `holy_level_5.json`

**Description:** Conjures food sufficient for 12 people and 12 mounts for one day.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Resource creation handler
- **Changes needed:**
  1. Add special handler `_handle_create_food()`
  2. Add items to party inventory via `GlobalController`
  3. Scale with caster level (additional 12 people/mounts per level above 9)
  4. Create "rations" or "food" item type

**Code pattern:** Pattern B (Special handler for item creation)

---
#### Create Water
**Level:** 4 (Divine)
**Source:** `holy_level_4.json`

**Description:** Creates approximately 50 gallons of pure water, enough for 12 people and 12 mounts.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Resource creation handler (similar to Create Food)
- **Changes needed:**
  1. Add special handler `_handle_create_water()`
  2. Add water/provisions to party inventory
  3. Scale with caster level

**Code pattern:** Pattern B (Special handler for item creation)

---
#### Deathly Blossom
**Level:** Lesser Rune
**Source:** `lesser_runes.json`

**Description:** Conjures a rose that causes those who smell it to fall into a death-like faint for 1d6 Turns.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Add parser patterns + special handler
- **Changes needed:**
  1. Add parser pattern for "fall into a deep faint" → `condition_applied="unconscious"`
  2. Parse "appearing dead" as special unconscious variant
  3. Add "Save Versus Doom" detection
  4. Track conjured item (rose) with 1 Turn duration or single-use

**Code pattern:** Pattern A (Pure mechanical) + Pattern C (Duration tracking)

---
#### Detect Disguise
**Level:** 1 (Divine)
**Source:** `hidden_spells.json`

**Description:** Reveals whether a target is disguised by mundane means.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Detection spell with oracle integration
- **Changes needed:**
  1. Add special handler for detection spells
  2. Query world state or oracle for disguise status
  3. Implement save resistance (Save Versus Spell)
  4. Return binary result ("be wary" or "be sure")

**Code pattern:** Pattern E (Oracle fallback for world knowledge)

---
#### Dispel Magic
**Level:** 3 (Arcane)
**Source:** `arcane_level_3_1.json`

**Description:** Unravels all spell effects in a 20' cube within range.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`, `src/game_state/global_controller.py`
- **Approach:** Critical utility spell requiring dedicated handler
- **Changes needed:**
  1. Add special handler `_handle_dispel_magic()`
  2. Query all `ActiveSpellEffect` entries in target area
  3. Calculate dispel chance based on caster level difference (5% per level)
  4. Call `SpellResolver.end_spell_effect()` for each dispelled effect
  5. Remove associated buffs, conditions, and area effects

**Code pattern:** Pattern B (Special handler) - high priority utility

---
#### En Croute
**Level:** 2 (Arcane)
**Source:** `hidden_spells.json`

**Description:** Encases target in pastry crust, immobilizing them with escape time based on Strength.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Restraint effect with Strength-based escape
- **Changes needed:**
  1. Add parser pattern for "immobilised" → `condition_applied="restrained"`
  2. Add `escape:strength_check` subsystem support
  3. Create escape time lookup table based on STR score
  4. Track remaining escape time on condition

**Code pattern:** Pattern B (Special handler) + `conditions:restrained`

---
#### Fool's Gold
**Level:** N/A (Fairy Glamour)
**Source:** `glamours.json`
**Subsystems:** `deception:illusions;saves:spell`

**Description:** Makes copper coins appear as gold; viewers may Save Versus Spell to see through it.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Illusion effect with per-viewer saves
- **Changes needed:**
  1. Track "glamoured" state on item objects
  2. Implement per-viewer save tracking
  3. Add usage limit: 20 coins per Level per day
  4. Duration tracking until touched or examined closely

**Code pattern:** Pattern E (Oracle for illusion detection) + item state tracking

---
#### Ginger Snap
**Level:** 3 (Arcane)
**Source:** `hidden_spells.json`

**Description:** Transforms target's limbs into gingerbread; smashed parts are permanently destroyed.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Transformation with body part tracking
- **Changes needed:**
  1. Add special handler `_handle_ginger_snap()`
  2. Track transformed body parts (1 per 3 caster levels)
  3. Implement "smash" attack mechanic against gingerbread parts
  4. Head transformation at level 14 = death if smashed
  5. Permanent limb loss on smashed parts

**Code pattern:** Pattern B (Complex special handler)

---
#### Lock Singer
**Level:** N/A (Knack)
**Source:** `knacks.json`

**Description:** Mossling ability to charm locks with songs.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Lock/door interaction ability
- **Changes needed:**
  1. Integrate with `world:doors_locks` subsystem
  2. Add ability check or automatic success for mundane locks
  3. Oracle fallback for magical locks
  4. Track usage (daily limit?)

**Code pattern:** Pattern E (Oracle) + world state interaction

---
#### Serpent Glyph
**Level:** 3 (Arcane)
**Source:** `arcane_level_3_2.json`
**Subsystems:** `conditions:stasis;traps:glyphs;world:doors_locks;world:glyphs`

**Description:** Creates a trap glyph that freezes triggering creatures in temporal stasis.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`, `src/data_models.py`
- **Approach:** Glyph trap system
- **Changes needed:**
  1. Extend glyph system for trap glyphs
  2. Create `GlyphTrap` model with trigger conditions
  3. Implement attack roll for serpent form
  4. Add "temporal stasis" condition (cannot move/perceive/act, invulnerable)
  5. Duration: 1d4 days or until dispelled

**Code pattern:** Pattern B (Special handler) + new subsystem `traps:glyphs`

---
#### Through the Keyhole
**Level:** N/A (Fairy Glamour)
**Source:** `glamours.json`
**Subsystems:** `world:doors_locks`

**Description:** Step through any door with a keyhole/aperture, bypassing it entirely.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Door bypass ability
- **Changes needed:**
  1. Integrate with door state system
  2. Check for magical sealing (requires Save Versus Spell)
  3. Track per-door daily usage limit
  4. Instant teleport to other side

**Code pattern:** Pattern B (Special handler) + door state system

---
#### Trap the Soul
**Level:** 6 (Arcane)
**Source:** `hidden_spells.json`

**Description:** Traps or releases a creature's life force in a prepared gem/crystal.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Complex two-mode spell with soul tracking
- **Changes needed:**
  1. Add special handler `_handle_trap_the_soul()`
  2. Create `SoulReceptacle` item type with name engraving
  3. Implement trap mode: Save Versus Doom or soul trapped, body comatose
  4. Implement release mode: restore soul to body or transfer
  5. Track 30-day death timer on soulless bodies
  6. Allow conversation with trapped souls

**Code pattern:** Pattern B (Complex special handler) - significant implementation

---
#### Ventriloquism
**Level:** 1 (Arcane)
**Source:** `arcane_level_1_2.json`

**Description:** Caster's voice emanates from any point within range.

**Implementation Requirements:**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Pure narrative utility
- **Changes needed:**
  1. Add as utility effect with `category=UTILITY`
  2. No mechanical effects needed
  3. Narration-only with duration tracking

**Code pattern:** Pattern E (Pure narrative/oracle)

---
#### Holy Quest
**Level:** 5 (Divine)
**Source:** `holy_level_5.json`
**Subsystems:** `compulsion:oath_clock;penalties:escalation`

**Description:** Commands subject to perform a quest; refusal causes -2 to attacks and saves.

**Implementation Requirements:**

**New Subsystem: Compulsion/Oath Tracking**
- **File:** `src/data_models.py`
- **New class:** `CompulsionEffect`
  ```python
  @dataclass
  class CompulsionEffect:
      goal: str  # Quest description
      source_spell_id: str
      caster_id: str
      target_id: str
      violation_triggers: list[str]  # Conditions that trigger penalty
      escalation_clock: int  # Days/turns until escalation
      current_penalties: dict[str, int]  # {stat: penalty}
      is_active: bool = True
  ```

**Changes needed:**
1. Create compulsion tracking in `GlobalController`
2. Implement penalty application on violation
3. Add quest completion detection (oracle-assisted)
4. Save Versus Spell resistance

**Code pattern:** Pattern B (Special handler) + new compulsion subsystem

---
#### Levitate
**Level:** 2 (Arcane)
**Source:** `arcane_level_2_2.json`
**Subsystems:** `movement:flight_state;movement:verticality`

**Description:** Caster can move up/down through air at 20'/round.

**Implementation Requirements:**

**New Subsystem: Movement States**
- **File:** `src/data_models.py`
- **Changes to `CharacterState`:**
  ```python
  movement_mode: Optional[str] = None  # "walking", "flying", "levitating", "swimming"
  altitude: int = 0  # Feet above ground
  vertical_movement_rate: int = 0  # Feet per round vertical
  ```

**Changes needed:**
1. Add `movement_mode` and `altitude` tracking to `CharacterState`
2. Update combat targeting to account for altitude differences
3. Implement "levitating" as special movement that requires pushing off solid objects for horizontal movement
4. Duration: spell duration (concentration?)

**Code pattern:** Pattern C (Persistent effect) + movement subsystem

---
#### Passwall
**Level:** 5 (Arcane)
**Source:** `arcane_level_5_2.json`
**Subsystems:** `world:temporary_passage`

**Description:** Opens a 5' diameter, 10' deep hole in solid rock/stone temporarily.

**Implementation Requirements:**

**New Subsystem: Temporary Passages**
- **File:** `src/data_models.py`, `src/game_state/location_state.py`
- **New class or extension:**
  ```python
  @dataclass
  class TemporaryPassage:
      location_id: str
      direction: str  # Which wall/surface
      diameter: int = 5
      depth: int = 10
      duration_remaining: int  # Turns
      created_by: str  # caster_id
  ```

**Changes needed:**
1. Add `temporary_passages` list to `LocationState`
2. Create passage creation/removal methods
3. Integrate with movement/exploration to allow traversal
4. Duration tracking and expiration

**Code pattern:** Pattern D (Area/location effect) + world state

---
#### Polymorph
**Level:** 4 (Arcane)
**Source:** `arcane_level_4_2.json`
**Subsystems:** `transformation:form_templates`

**Description:** Transforms caster or subject into another creature form.

**Implementation Requirements:**

**New Subsystem: Form Templates**
- **File:** `src/data_models.py`, new file `src/content/form_templates.py`
- **New structures:**
  ```python
  @dataclass
  class FormTemplate:
      form_id: str
      name: str
      level: int  # For level restriction checks
      movement_modes: dict[str, int]  # {"walk": 40, "fly": 60, "swim": 30}
      natural_attacks: list[Attack]
      special_abilities: list[str]
      senses: list[str]  # "darkvision", "tremorsense"
      size: str

  @dataclass
  class PolymorphState:
      original_state_snapshot: dict  # Full character state backup
      current_form: FormTemplate
      preserves_hp: bool = True
      preserves_saves: bool = True  # Only for self-cast
      preserves_attack: bool = True  # Only for self-cast
      duration_remaining: Optional[int] = None  # None = permanent (other target)
  ```

**Changes needed:**
1. Create curated form template library (common animals, monsters)
2. Store original character state for reversion
3. Apply form template stats while preserving HP/identity/inventory
4. Different rules for self-cast vs other-cast
5. Reversion on death

**Code pattern:** Pattern B (Complex handler) + transformation subsystem - **major implementation**

---
#### Telekinesis
**Level:** 5 (Arcane)
**Source:** `arcane_level_5_2.json`
**Subsystems:** `interaction:telekinesis`

**Description:** Move objects/creatures by thought; 200 coins weight per caster level.

**Implementation Requirements:**

**New Subsystem: Telekinesis Interaction**
- **File:** `src/narrative/spell_resolver.py`
- **Approach:** Concentration-based manipulation

**Changes needed:**
1. Add special handler `_handle_telekinesis()`
2. Calculate weight limit (200 coins × caster level)
3. Track concentration state (ends if harmed or takes action)
4. Movement rate: 20'/round in any direction
5. Save Versus Hold for unwilling creatures or held items
6. Integrate with object/creature interaction system

**Code pattern:** Pattern C (Concentration tracking) + interaction subsystem

---

---

## Phase 3 — Implement “Skip” Spells via Oracle Registry (21 spells)

### 3.1 Recommended implementation approach
- Treat these as **oracle-adjudicated** spells.
- Do **not** attempt full mechanical parsing.
- Apply only the smallest safe mechanical tags (optional).
- Store the adjudication result in `SpellCastResult.narrative_context` so the narration layer can present it.

### 3.2 Oracle registry (drop-in JSON)
Create: `data/system/oracle_only_spells.json`

```json
{
  "oracle_only_spells": [
    {
      "spell_id": "beguilement",
      "adjudication_type": "illusion_belief",
      "default_question_template": "Beguilement: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "bird_friend",
      "adjudication_type": "summoning_control",
      "default_question_template": "Bird Friend: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "dancing_flame",
      "adjudication_type": "generic",
      "default_question_template": "Dancing Flame: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "detect_evil",
      "adjudication_type": "divination",
      "default_question_template": "Detect Evil: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "detect_magic",
      "adjudication_type": "divination",
      "default_question_template": "Detect Magic: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "disguise_object",
      "adjudication_type": "illusion_belief",
      "default_question_template": "Disguise Object: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "dweomerlight",
      "adjudication_type": "divination",
      "default_question_template": "Dweomerlight: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "fabricate",
      "adjudication_type": "generic",
      "default_question_template": "Fabricate: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "fairy_steed",
      "adjudication_type": "summoning_control",
      "default_question_template": "Fairy Steed: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "find_traps",
      "adjudication_type": "divination",
      "default_question_template": "Find Traps: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "mind_crystal",
      "adjudication_type": "divination",
      "default_question_template": "Mind Crystal: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "mirth_and_malice",
      "adjudication_type": "illusion_belief",
      "default_question_template": "Mirth and Malice: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "move_terrain",
      "adjudication_type": "generic",
      "default_question_template": "Move Terrain: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "oracle",
      "adjudication_type": "divination",
      "default_question_template": "Oracle: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "reveal_alignment",
      "adjudication_type": "divination",
      "default_question_template": "Reveal Alignment: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "root_friend",
      "adjudication_type": "summoning_control",
      "default_question_template": "Root Friend: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "rune_of_wishing",
      "adjudication_type": "wish",
      "default_question_template": "Rune of Wishing: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "summon_wild_hunt",
      "adjudication_type": "summoning_control",
      "default_question_template": "Summon Wild Hunt: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "thread_whistling",
      "adjudication_type": "generic",
      "default_question_template": "Thread Whistling: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "wood_kenning",
      "adjudication_type": "divination",
      "default_question_template": "Wood Kenning: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    },
    {
      "spell_id": "yeast_master",
      "adjudication_type": "generic",
      "default_question_template": "Yeast Master: Based on the current scene, what happens if the caster uses this spell as described? Provide a concrete, bounded outcome consistent with established facts.",
      "minimal_tags": []
    }
  ]
}
```

### 3.3 Generic handler flow (pseudocode)

```python
def _handle_oracle_only_spell(self, spell, caster, targets, context):
    spec = ORACLE_REGISTRY[spell.spell_id]
    oracle = self._controller.adjudicate_oracle_spell(
        spell_id=spell.spell_id,
        adjudication_type=spec["adjudication_type"],
        context=spec["default_question_template"],
        caster_id=caster.id,
        target_ids=[t.id for t in targets],
        additional_context={"spell_text": spell.description}
    )
    # Optionally apply minimal tags as conditions or area effects
    return {
        "oracle_adjudication": oracle,
        "oracle_type": spec["adjudication_type"],
        "oracle_question": spec["default_question_template"],
    }
```

### 3.4 Skip spell strategy reference (from your summary)
## Skip Spells (21 unimplemented)

These spells are intentionally not mechanically parsed. They should be handled via oracle/LLM adjudication with minimal mechanical tags.

### Detection/Divination Spells (Oracle-Fallback)

| Spell | Strategy |
|-------|----------|
| **Detect Evil** | Query oracle for evil intent/enchantment; return boolean result |
| **Detect Magic** | Query oracle or world state for magical auras; list enchanted items |
| **Dweomerlight** | Narrative reveal of magic items and spell-casting; no mechanics |
| **Find Traps** | Query oracle/world state for trap locations; reveal without disarm |
| **Mind Crystal** | Oracle provides detected thoughts; requires concentration turns |
| **Reveal Alignment** | Query oracle for character/object alignment |
| **Wood Kenning** | Oracle provides information about plants/wood |

**Implementation Strategy:**
- Use `src/oracle/spell_adjudicator.py` for world knowledge queries
- Return narrative descriptions rather than mechanical effects
- Optionally integrate with lore providers for consistent world facts

---

### Illusion/Deception Spells (Narrative + Tags)

| Spell | Strategy |
|-------|----------|
| **Beguilement** | Apply "deceived" tag; oracle determines what target believes |
| **Disguise Object** | Track "glamoured" state on item; duration until touched |
| **Mirth and Malice** | Apply emotional state tags; oracle determines expression |

**Implementation Strategy:**
- Apply simple condition tags ("deceived", "glamoured", "emotional")
- Use oracle for determining specific outcomes and reactions
- Duration: typically 1 scene/turn or until specific trigger

---

### Summoning/Companion Spells (Entity Spawning)

| Spell | Strategy |
|-------|----------|
| **Fairy Steed** | Spawn creature with basic statblock; command interface |
| **Summon Wild Hunt** | Spawn powerful entity; oracle handles behavior |

**Implementation Strategy:**
- Use existing creature spawning if available
- Create simplified "summon" statblocks
- Track allegiance and command acceptance
- Oracle handles complex interactions

---

### Creation/Fabrication Spells (Bounded Commands)

| Spell | Strategy |
|-------|----------|
| **Fabricate** | Oracle determines what can be made; issue item creation commands |
| **Move Terrain** | Oracle narrates terrain movement; update location tags |
| **Rune of Wishing** | Full oracle adjudication with bounded effect commands |

**Implementation Strategy:**
- Use `src/oracle/effect_commands.py` for bounded effects:
  - `ItemCreateCommand`
  - `TerrainModifyCommand`
  - `ConditionApplyCommand`
- Require player to state intent and limits
- Oracle validates and executes bounded commands

---

### Narrative Abilities (Mossling Knacks)

| Spell | Strategy |
|-------|----------|
| **Bird Friend** | Narrative communication with birds; oracle roleplay |
| **Root Friend** | Narrative interaction with plant roots |
| **Thread Whistling** | Narrative thread manipulation |
| **Yeast Master** | Narrative yeast/baking control |

**Implementation Strategy:**
- Treat as pure narrative abilities
- No mechanical parsing needed
- Oracle handles contextual applications
- Optionally expose mechanical tags when combat-relevant:
  - Morale modifiers for animal companions
  - Advantage/disadvantage for related checks

---

### Complex Oracle Spells

| Spell | Strategy |
|-------|----------|
| **Oracle (spell)** | Full oracle integration; 3 questions with 1-in-6 false chance |
| **Dancing Flame** | Narrative light manipulation; concentration tracking |

**Implementation Strategy:**
- Direct pass-through to oracle system
- Track concentration states if applicable
- Log oracle responses for consistency

---

## Implementation Priority Recommendations

### High Priority (Core Functionality)
1. **Dispel Magic** - Critical utility for all spell users
2. **Polymorph** - Popular transformation spell requiring form templates
3. **Levitate** - Common movement spell needing altitude tracking

### Medium Priority (Common Use)
4. **Animal Growth** - Simple stat multiplier
5. **Create Food/Water** - Resource management
6. **Deathly Blossom** - Simple condition application
7. **Telekinesis** - Concentration-based utility

### Lower Priority (Situational)
8. **Serpent Glyph** - Requires trap subsystem
9. **Holy Quest** - Requires compulsion subsystem
10. **En Croute** - Niche restraint effect
11. **Trap the Soul** - Complex edge case

### Defer to Oracle (Skip Tier)
- All detection/divination spells
- All narrative-only abilities
- All complex creation spells

---

## Subsystem Development Roadmap

Based on the spells needing implementation, these new subsystems would unlock multiple spells:

1. **Movement States** (`movement:flight_state`, `movement:verticality`)
   - Unlocks: Levitate, Fly, Air Sphere
   - Add: `movement_mode`, `altitude` to CharacterState

2. **Form Templates** (`transformation:form_templates`)
   - Unlocks: Polymorph
   - Add: FormTemplate library, PolymorphState tracking

3. **Compulsion Tracking** (`compulsion:oath_clock`, `penalties:escalation`)
   - Unlocks: Holy Quest, Geas
   - Add: CompulsionEffect tracking with violation detection

4. **Trap Glyphs** (`traps:glyphs`)
   - Unlocks: Serpent Glyph
   - Extend existing glyph system with trigger mechanics

5. **Morale Integration** (`morale:checks`)
   - Unlocks: Awe
   - Add: GlobalController.trigger_morale_check()

6. **Item Creation** (no tag, but needed)
   - Unlocks: Create Food, Create Water, Fabricate
   - Add: Item spawning through GlobalController

---

## Phase 4 — Integration Tests (high leverage)

Add a minimal set of “golden path” tests for the hardest spells:

- `test_dispel_magic_removes_buffs_and_conditions`
- `test_polymorph_applies_overlay_and_reverts`
- `test_trap_the_soul_traps_and_releases`
- `test_serpent_glyph_applies_temporal_stasis`
- `test_oracle_only_spell_returns_adjudication_payload`

Each test should:
- create a tiny in-memory game state
- invoke `SpellResolver.resolve_spell(...)`
- assert on state deltas + `SpellCastResult.narrative_context`

---

## Suggested Implementation Order (fastest to stable)

1. Phase 0 (coverage gate)
2. Phase 3 (oracle-only registry + generic handler) → immediately “implements” 21 spells
3. Phase 1.3 (doors/locks) → unlocks multiple moderate spells
4. Phase 2: implement remaining moderate spells
5. Phase 1.4 (stasis) + Serpent Glyph
6. Phase 1.5 (soul) + Trap the Soul
7. Significant spells last: Polymorph, Telekinesis, Holy Quest (these touch the most state)

---

## Notes for the LLM Implementer

- Prefer **special handlers** over brittle regex parsing when the spell’s intent is complex or world-interaction heavy.
- Keep state additions small, serializable, and reversible.
- Any “edge case” you can’t mechanize safely should be routed through the **oracle adjudicator** rather than silently inventing world facts.
