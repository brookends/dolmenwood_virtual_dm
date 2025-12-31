# Unimplemented Spells Summary

This document provides a comprehensive analysis of all Dolmenwood spells that currently do not produce parsed mechanical effects from the `SpellResolver.parse_mechanical_effects()` method. For each spell, it describes what systems or code changes would be needed for implementation.

## Overview

| Tier | Unimplemented | Total | Notes |
|------|---------------|-------|-------|
| Moderate | 17 | 65 | Should work with parser improvements or special handlers |
| Significant | 5 | 27 | Require new subsystems |
| Skip | 21 | 43 | Oracle-only, no mechanical parsing expected |

---

## Moderate Spells (17 unimplemented)

These spells are expected to work with parser improvements or special handlers.

### 1. Air Sphere
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

### 2. Animal Growth
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

### 3. Arcane Cypher
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

### 4. Awe
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

### 5. Create Food
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

### 6. Create Water
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

### 7. Deathly Blossom
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

### 8. Detect Disguise
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

### 9. Dispel Magic
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

### 10. En Croute
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

### 11. Fool's Gold
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

### 12. Ginger Snap
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

### 13. Lock Singer
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

### 14. Serpent Glyph
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

### 15. Through the Keyhole
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

### 16. Trap the Soul
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

### 17. Ventriloquism
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

## Significant Spells (5 unimplemented)

These spells require new subsystems to implement properly.

### 1. Holy Quest
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

### 2. Levitate
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

### 3. Passwall
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

### 4. Polymorph
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

### 5. Telekinesis
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
