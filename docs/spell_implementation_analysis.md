# Dolmenwood Spell Implementation Analysis

**Generated:** 2025-12-31
**Last Updated:** 2025-12-31
**Total Spells Analyzed:** 103 spells across 22 JSON files

---

## Table of Contents

1. [Overview](#overview)
2. [Recent Fixes](#recent-fixes)
3. [Works With Current Resolver](#works-with-current-resolver)
4. [Needs Parser Enhancements](#needs-parser-enhancements)
5. [Needs Special Handler](#needs-special-handler)
6. [Narrative-Only Spells](#narrative-only-spells)
7. [Significant Implementation Gaps](#significant-implementation-gaps)
8. [Problematic / Not Worth Implementing](#problematic--not-worth-implementing)
9. [Glamours Analysis](#glamours-analysis)
10. [Knacks Analysis](#knacks-analysis)
11. [Runes Analysis](#runes-analysis)
12. [Recommended Priorities](#recommended-priorities)

---

## Overview

This document analyzes all spells in the Dolmenwood Virtual DM system to identify:
- Spells that work with the current spell resolver
- Spells that need custom Python handlers
- Spells best left to LLM narration
- Implementation gaps and missing systems
- Recommended development priorities

### Spell Counts by Type

| Category | Count |
|----------|-------|
| Arcane Spells (Levels 1-6) | 48 |
| Holy Spells (Levels 1-5) | 34 |
| Glamours | 20 |
| Lesser Runes | 6 |
| Greater Runes | 6 |
| Mighty Runes | 6 |
| Knacks (6 types × ~4 abilities) | ~24 |

---

## Recent Fixes

The following issues were fixed in the spell resolver on 2025-12-31:

### Fix 1: Level-Scaled Damage
**Issue:** Spells like Fireball ("1d6 damage per Level") only parsed as 1d6.
**Solution:** Added `level_multiplier` field to `MechanicalEffect`. Parser now detects "per level" pattern and multiplies damage by caster level.
**Spells Fixed:** Fireball, Lightning Bolt, Acid Globe

### Fix 2: Damage Reduction False Positive
**Issue:** Frost Ward/Flame Ward description "4d6 damage is reduced by 2 points" was parsed as dealing 4d6 damage.
**Solution:** Parser now checks context after damage dice match; skips if followed by "reduced", "reduction", or "less".
**Spells Fixed:** Frost Ward, Flame Ward

### Fix 3: Healing Not Parsed as Damage
**Issue:** Lesser Healing's "1d6+1" was parsed as both healing AND damage.
**Solution:** Healing patterns now parsed first, with dice tracked to skip in damage parser.
**Spells Fixed:** Lesser Healing, Greater Healing

### Fix 4: Condition Cure vs Apply
**Issue:** "Curing paralysis" was incorrectly parsed as APPLYING paralysis condition.
**Solution:** Expanded removal detection patterns to include "curing", "negat", "nullif", etc.
**Spells Fixed:** Neutralize Poison, Lesser Healing (paralysis cure)

### Fix 5: AC Override Parsing
**Issue:** Shield of Force "grants AC 17 against missiles" was not being parsed.
**Solution:** Added `ac_override` field and pattern to detect "grants AC [number]" with optional condition context.
**Spells Fixed:** Shield of Force

---

## Works With Current Resolver

These spells have clear mechanical effects that the existing `SpellResolver` correctly parses and applies.

### Damage Spells (Verified Working)

| Spell | Level | Type | Mechanics | Status |
|-------|-------|------|-----------|--------|
| Ioun Shard | 1 | Arcane | 1d6+1 auto-hit, scales with level | ✅ Working |
| Flaming Spirit | 2 | Arcane | 1d6/round, Save vs Ray | ✅ Working |
| Fireball | 3 | Arcane | 1d6 × caster level AoE, Save vs Blast for half | ✅ Fixed (level scaling) |
| Lightning Bolt | 3 | Arcane | 1d6 × caster level line, Save vs Ray for half | ✅ Fixed (level scaling) |
| Acid Globe | 4 | Arcane | 1d4 × caster level + splash, Save vs Blast | ✅ Fixed (level scaling) |
| Ice Storm | Greater Rune | Rune | 3d8 AoE damage | ✅ Working |

### Healing Spells (Verified Working)

| Spell | Level | Type | Mechanics | Status |
|-------|-------|------|-----------|--------|
| Lesser Healing | 1 | Holy | 1d6+1 HP or cure paralysis | ✅ Fixed (healing only) |
| Greater Healing | 4 | Holy | 2d6+2 HP | ✅ Fixed (healing only) |

### Buff Spells (Verified Working)

| Spell | Level | Type | Mechanics | Status |
|-------|-------|------|-----------|--------|
| Bless | 2 | Holy | +1 Attack/Damage in 20'×20' | ✅ Working |
| Frost Ward | 1 | Holy | +2 save vs cold, reduce cold damage | ✅ Fixed (not parsed as damage) |
| Flame Ward | 2 | Holy | +2 save vs fire, reduce fire damage | ✅ Fixed (not parsed as damage) |
| Shield of Force | 1 | Arcane | AC 17 vs missiles, AC 15 vs other | ✅ Fixed (AC override) |
| Mantle of Protection | 1 | Holy | +1 AC/saves vs Chaotic creatures | ✅ Working |
| Circle of Protection | 4 | Holy | 10' radius Mantle of Protection | ✅ Working |

### Condition Spells (Verified Working)

| Spell | Level | Type | Mechanics | Status |
|-------|-------|------|-----------|--------|
| Hold Person | 2 | Holy | Save vs Hold, paralysis | ⚠️ Partial (immunity not parsed) |
| Paralysation | 3 | Arcane | Save vs Hold, 2× caster level in HD | ✅ Working |
| Vapours of Dream | 1 | Arcane | Level 4 or lower, Save vs Spell or sleep | ✅ Working |
| Neutralize Poison | 3 | Holy | Cures poison condition | ✅ Fixed (cure context) |

---

## Needs Parser Enhancements

These spells have mechanical effects that CANNOT be parsed by the current resolver and need additional parsing logic.

### Flat Damage (No Dice Notation)

| Spell | Level | Type | Issue | What's Needed |
|-------|-------|------|-------|---------------|
| Ignite/Extinguish | 1 | Arcane | "1 damage per spark" | Parse flat damage numbers |
| Cloudkill | 5 | Arcane | "1 damage per round" | Parse flat damage numbers |

**Solution:** Add regex pattern for `(\d+)\s+(?:points?\s+of\s+)?damage` without dice notation.

### Death Effects (Save-or-Die)

| Spell | Level | Type | Issue | What's Needed |
|-------|-------|------|-------|---------------|
| Cloudkill | 5 | Arcane | "Save vs Doom or die" | Death effect handler |
| Disintegrate | 6 | Arcane | "Save vs Doom or destroyed" | Death effect handler |
| Word of Doom | 6 | Arcane | "Save vs Doom or die" (lowest HD first) | Death effect + HD targeting |
| Rune of Death | Mighty | Rune | "Save vs Doom or die" (4d8 HD) | Death effect + HD targeting |

**Solution:** Add `is_death_effect: bool` field to `MechanicalEffect`, detect "or die", "or destroyed", "instant death" patterns.

### HD-Based Targeting

| Spell | Level | Type | Issue | What's Needed |
|-------|-------|------|-------|---------------|
| Word of Doom | 6 | Arcane | Targets lowest HD first up to 4d8 total | HD-based target selection |
| Rune of Death | Mighty | Rune | Targets lowest HD first up to 4d8 total | HD-based target selection |

**Solution:** This requires special handling logic, not just parsing. Needs `_handle_mass_death_effect()` method.

### Immunity Effects

| Spell | Level | Type | Issue | What's Needed |
|-------|-------|------|-------|---------------|
| Missile Ward | 3 | Arcane | "Immune to normal missiles" | Immunity buff system |
| Hold Person | 2 | Holy | "Summoned creatures immune" | Target filtering |

**Solution:** Add immunity tracking to buff system with source/condition.

### Spell Blocking

| Spell | Level | Type | Issue | What's Needed |
|-------|-------|------|-------|---------------|
| Anti-Magic Ward | 6 | Arcane | "Blocks spells of Rank 1-3" | Spell interception system |

**Solution:** Requires pre-cast hook to check for blocking effects on target.

### Silence/Sound Effects

| Spell | Level | Type | Issue | What's Needed |
|-------|-------|------|-------|---------------|
| Silence | 2 | Holy | "Cannot speak or cast spells" | Sound suppression zone |

**Solution:** Add area effect with spellcasting prevention flag.

### Stat Reduction

| Spell | Level | Type | Issue | What's Needed |
|-------|-------|------|-------|---------------|
| Feeblemind | 5 | Arcane | "INT reduced to 3" | Stat override/reduction system |

**Solution:** Extend buff system to support stat overrides (not just modifiers).

---

## Needs Special Handler

These spells require custom Python code beyond the standard resolver.

### Already Implemented

| Spell | Level | Type | Handler |
|-------|-------|------|---------|
| Crystal Resonance | 1 | Arcane | `_handle_crystal_resonance()` + `CrystalResonanceProvider` |
| Decipher | 1 | Arcane | `DecipherProvider` |
| Purify Food and Drink | 1 | Holy | `_handle_purify_food_and_drink()` |

### Needs Implementation - Medium Complexity

| Spell | Level | Type | What's Needed | Effort |
|-------|-------|------|---------------|--------|
| Ingratiate | 1 | Arcane | Enchanted item tracking, daily save system for charm | Medium |
| Dominate | 4 | Arcane | Charm tracking with daily saves, command system | Medium |
| Sway the Mortal Mind | Lesser Rune | Rune | Same charm system as Dominate | Medium |
| Sway the Mind | Greater Rune | Rune | Same charm system, affects any creature | Medium |
| Glyph of Sealing | 1 | Arcane | Door/portal state tracking, 2d6 turn duration | Medium |
| Glyph of Locking | 2 | Arcane | Permanent door locks, password system | Medium |
| Knock | 2 | Arcane | Interaction with locked doors and glyphs | Medium |
| Mirror Image | 2 | Arcane | Image count (1d4), attack absorption tracking | Medium |
| Web | 2 | Arcane | Entanglement state, strength-based escape time | Medium |
| Haste | 3 | Arcane | Double movement/attacks for up to 24 creatures | Low |
| Confusion | 4 | Arcane | Behavior table rolls each round for affected | Medium |
| Hex Weaving | 4 | Arcane | Curse system (remove or place curses) | Medium |
| Serpent Transformation | 4 | Holy | Create 2d8 adder creatures from sticks | Medium |
| Serpent Glyph | 3 | Arcane | Trap glyph with temporal stasis effect | Medium |

### Needs Implementation - High Complexity

| Spell | Level | Type | What's Needed | Effort |
|-------|-------|------|---------------|--------|
| Invisibility | 2 | Arcane | Visibility state tracking, break on attack/cast | High |
| Circle of Invisibility | 3 | Arcane | Mobile 10' radius invisibility zone | High |
| Polymorph | 4 | Arcane | Complete form transformation system | High |
| Animate Dead | 5 | Arcane | Undead creature creation and control | High |
| Conjure Elemental | 5 | Arcane | Elemental stats + concentration loss = hostile | High |
| Teleport | 5 | Arcane | Destination familiarity table + mishap system | High |
| Geas | 6 | Arcane | Compulsion with escalating penalties | High |
| Holy Quest | 5 | Holy | Same compulsion system as Geas | High |

---

## Narrative-Only Spells

These spells are best handled by LLM narration with appropriate context providers. The Python system should provide the *information* but let the LLM describe the *experience*.

### Detection/Divination Spells

| Spell | Level | Type | Context Needed |
|-------|-------|------|----------------|
| Detect Magic | 1 | Holy | Magic items/effects in range (has `DetectMagicProvider`) |
| Detect Evil | 1 | Holy | Evil intent/cursed items (has `DetectEvilProvider`) |
| Dweomerlight | 2 | Arcane | Same as Detect Magic but visible glow |
| Mind Crystal | 2 | Arcane | Creature thoughts in direction |
| Crystal Vision | 3 | Arcane | See through creature's eyes |
| Arcane Eye | 4 | Arcane | Remote invisible eye viewing |
| Oracle | 6 | Arcane | 3 cryptic questions, 1-in-6 false |
| Communion | 5 | Holy | 3 yes/no questions from saints |
| Locate Object | 3 | Holy | Direction to object class or specific item |
| Find Traps | 2 | Holy | Reveal trap locations |
| Reveal Alignment | 2 | Holy | Show creature/object alignment |
| Wood Kenning | Knack | Knack | History/emotions from wood (has `WoodKenningProvider`) |

### Communication Spells

| Spell | Level | Type | Context Needed |
|-------|-------|------|----------------|
| Speak with Animals | 2 | Holy | Animal species communication |
| Speak with Plants | 4 | Holy | Plant communication |
| Sending | 5 | Arcane | 25-word mental message to anyone |
| Silver Tongue | Glamour | Glamour | Communicate in any language |

### Illusion/Deception Spells

| Spell | Level | Type | Notes |
|-------|-------|------|-------|
| Phantasm | 2 | Arcane | Complex illusion: scene, attack, or monster |
| Hallucinatory Terrain | 4 | Arcane | Terrain feature illusion |
| Project Image | 6 | Arcane | Illusory duplicate of caster |
| Woodland Veil | 4 | Arcane | 100 creatures appear as trees |

### Summoning/Creation Spells

| Spell | Level | Type | Notes |
|-------|-------|------|-------|
| Fairy Servant | 1 | Arcane | Invisible sprite performs tasks |
| Invisible Stalker | 6 | Arcane | Extra-dimensional hunter on mission |
| Dream Ship | Mighty Rune | Rune | Phantasmagoric ship for travel |
| Summon Wild Hunt | Mighty Rune | Rune | Massive fairy hunting host |
| Fairy Steed | Greater Rune | Rune | Charming fairy horse mount |

---

## Significant Implementation Gaps

These spells reveal missing systems in the codebase.

### Missing: Visibility State System

**Affected Spells:**
- Invisibility (Arcane 2)
- Circle of Invisibility (Arcane 3)
- Perceive the Invisible (Arcane 2)
- Rune of Vanishing (Lesser Rune)
- Rune of Invisibility (Greater Rune)
- Vanishing (Glamour)
- Subtle Sight (Glamour)
- Fairy Dust (Glamour)

**What's Needed:**
- Character/creature visibility state (visible, invisible, partially visible)
- Tracking what can see invisible (Perceive the Invisible, Subtle Sight)
- Break conditions (attacking, casting spells)
- Attack penalties vs invisible targets

### Missing: 3D Position/Movement System

**Affected Spells:**
- Levitate (Arcane 2) - vertical movement only
- Fly (Arcane 3) - full 3D movement
- Dimension Door (Arcane 4) - teleport with coordinate offsets
- Teleport (Arcane 5) - long-range teleport
- Telekinesis (Arcane 5) - move objects/creatures

**What's Needed:**
- Z-coordinate or height tracking
- Falling/landing mechanics
- Coordinate-based destination specification

### Missing: Wall/Barrier System

**Affected Spells:**
- Wall of Fire (Arcane 4)
- Wall of Ice (Arcane 4)
- Wall of Stone (Arcane 5)
- Web (Arcane 2)

**What's Needed:**
- Barrier creation in location
- Blocking movement/line of sight
- Breaking/destroying barriers
- Effects on creatures passing through

### Missing: Terrain Modification System

**Affected Spells:**
- Plant Growth (Arcane 4) - dense thicket
- Mire (Arcane 5) - mud terrain
- Move Terrain (Arcane 6) - relocate terrain features
- Passwall (Arcane 5) - temporary hole in stone

**What's Needed:**
- Terrain state modifications
- Movement speed effects by terrain
- Temporary vs permanent changes

### Missing: Charm/Compulsion Tracking

**Affected Spells:**
- Ingratiate (Arcane 1)
- Dominate (Arcane 4)
- Sway the Mortal Mind (Lesser Rune)
- Sway the Mind (Greater Rune)
- Geas (Arcane 6)
- Holy Quest (Holy 5)
- Eternal Slumber (Mighty Rune)

**What's Needed:**
- Charmed creature tracking
- Daily save attempts
- Command/resist logic
- Penalty escalation for Geas/Quest

### Missing: Curse System

**Affected Spells:**
- Hex Weaving (Arcane 4)
- Remove Curse (Holy 3)

**What's Needed:**
- Curse tracking (type, severity, source)
- Curse effects (save penalties, attack penalties, stat reductions)
- Curse removal conditions

---

## Problematic / Not Worth Implementing

These spells should be handled purely by LLM narration. Mechanical implementation would be extremely complex with minimal gameplay benefit.

| Spell | Level | Type | Reason |
|-------|-------|------|--------|
| Rune of Wishing | Mighty Rune | Rune | "Alter reality in any conceivable way" - undefined scope |
| Fabricate | 5 | Arcane | Create arbitrary objects from materials - too open-ended |
| Invisible Stalker | 6 | Arcane | Autonomous NPC with complex mission logic |
| Dream Ship | Mighty Rune | Rune | Teleportation via dream narrative |
| Summon Wild Hunt | Mighty Rune | Rune | Army of 100+ creatures |
| Move Terrain | 6 | Arcane | Physically relocate terrain features |
| Oracle | 6 | Arcane | Cryptic answers with false chance - pure LLM |
| Communion | 5 | Holy | Yes/no from saints - pure LLM |

---

## Glamours Analysis

### 20 Glamours Total

Glamours are fairy magic usable by Elves, Grimalkin, and Woodgrue. Most have usage frequency limits (once per turn, once per day, once per day per subject).

### Should Implement Mechanically

| Glamour | Mechanics | Why Implement |
|---------|-----------|---------------|
| Awe | Morale check, affects levels up to caster | Combat trigger |
| Fairy Dust | Reveal invisible for 1 round | Counters invisibility |
| Fool's Gold | Save vs Spell to detect | Deception with clear save |
| Forgetting | Save vs Spell, forget last round | Memory modification with save |
| Vanishing | 1d3 rounds invisible to one creature | Targeted invisibility |
| Through the Keyhole | Pass through door with keyhole | Door bypass |
| Walk in Shadows | 2-in-6 chance to find shadow door | Teleportation with random element |

### Let LLM Handle

| Glamour | Reason |
|---------|--------|
| Beguilement | Short-term belief in words - roleplay |
| Breath of the Wind | Stealth effect - narrative |
| Cloak of Darkness | Hide while motionless - narrative |
| Conjure Treats | Improve disposition - roleplay |
| Dancing Flame | Move flame - narrative |
| Disguise Object | Illusion - narrative |
| Flame Charm | Ignite/extinguish - narrative |
| Masquerade | Facial disguise - narrative |
| Mirth and Malice | Emotion manipulation - roleplay |
| Moon Sight | Darkvision - passive ability |
| Seeming | Clothing illusion - narrative |
| Silver Tongue | Universal communication - narrative |
| Subtle Sight | 3-in-6 spot invisible - passive check |

---

## Knacks Analysis

### 6 Knacks (Mossling-only, level-scaled abilities)

Each knack has 4 abilities unlocked at levels 1, 3, 5, and 7.

### Bird Friend
| Level | Ability | Implementation |
|-------|---------|----------------|
| 1 | Bird speech | LLM handles conversation |
| 3 | Bird companion (Save vs Spell) | Needs charm tracking |
| 5 | Twittering message (10 words, 12 mph) | LLM handles |
| 7 | Summon flock (1d4 turns) | Narrative + duration |

### Lock Singer
| Level | Ability | Implementation |
|-------|---------|----------------|
| 1 | Open simple locks (2-in-6/turn) | Skill check |
| 3 | Locate key | LLM describes location |
| 5 | Snap shut (locks in 30') | Area effect |
| 7 | Open any lock (2-in-6, 1-in-6 backfire) | Skill check + risk |

### Root Friend
| Level | Ability | Implementation |
|-------|---------|----------------|
| 1 | Root question (1d6 words) | LLM answers |
| 3 | Summon roots (1d4 rations) | Create items |
| 5 | Root respite (hide 1 hour) | State tracking |
| 7 | Summon root thing (creature) | Creature creation |

### Thread Whistling
| Level | Ability | Implementation |
|-------|---------|----------------|
| 1 | Thread mastery (tie/untie) | LLM narrative |
| 3 | Animate threads (5'/round) | Movement tracking |
| 5 | Rope mastery | LLM narrative |
| 7 | Animate rope (attack) | Combat creature |

### Wood Kenning
| Level | Ability | Implementation |
|-------|---------|----------------|
| 1 | Sense history | ✅ Has `WoodKenningProvider` |
| 3 | Sense emotions | ✅ Has `WoodKenningProvider` |
| 5 | See beyond | ✅ Has `WoodKenningProvider` |
| 7 | True name | ✅ Has `WoodKenningProvider` |

### Yeast Master
| Level | Ability | Implementation |
|-------|---------|----------------|
| 1 | Ferment (1 pint/turn, 2-in-6 palatable) | Item transformation |
| 3 | Commune with yeast (reveal name) | LLM narrative |
| 5 | Yeasty belch (Save vs Blast, faint 1d6 rounds) | Combat ability |
| 7 | Yeast feast (1d6 rations) | Create items |

---

## Runes Analysis

### Lesser Runes (6 spells, available at level 1+)

| Rune | Mechanics | Implementation |
|------|-----------|----------------|
| Deathly Blossom | Save vs Doom or appear dead 1d6 turns | Condition + save |
| Fog Cloud | 20' radius blocks vision | Area effect |
| Gust of Wind | Extinguish flames, push creatures (Save vs Hold) | Area effect + save |
| Proof Against Deadly Harm | Immune to one weapon type | Damage immunity |
| Rune of Vanishing | Invisible to mortals/animals 1 turn | Visibility state |
| Sway the Mortal Mind | Charm mortal (Save vs Spell) | Charm tracking |

### Greater Runes (6 spells, available at level 5+)

| Rune | Mechanics | Implementation |
|------|-----------|----------------|
| Arcane Unbinding | Dispel arcane/fairy magic 20' cube | Dispel mechanic |
| Fairy Gold | Conjure 2d100 gold for 1d6 hours | Temporary items |
| Fairy Steed | Summon fairy horse | Creature creation |
| Ice Storm | 3d8 damage, icy surface | ✅ Working (damage parsed) |
| Rune of Invisibility | Invisible to all beings 1 day | Visibility state |
| Sway the Mind | Charm any creature (fairies +4 save) | Charm tracking |

### Mighty Runes (6 spells, available at level 9+)

| Rune | Mechanics | Implementation |
|------|-----------|----------------|
| Dream Ship | Transport to any Dolmenwood location | Pure narrative |
| Eternal Slumber | Permanent sleep, custom wake condition | State + condition |
| Rune of Death | 4d8 levels, Save vs Doom or die | ⚠️ Needs death effect handler |
| Rune of Wishing | Alter reality, costs 1d3 CON | Pure narrative |
| Summon Wild Hunt | 4d6 hounds + 4d20×2 elves + 1d6 goblins | Pure narrative |
| Unravel Death | Resurrect dead ≤7 days | Resurrection mechanic |

---

## Recommended Priorities

### Phase 0: Quick Parser Fixes (1-2 hours)

These can be fixed with small additions to the parser:

1. **Flat Damage Parsing**
   - Covers: Ignite/Extinguish, Cloudkill
   - Effort: ~30 minutes
   - Add pattern for "N damage" without dice

2. **Death Effect Parsing**
   - Covers: Cloudkill, Disintegrate, Word of Doom, Rune of Death
   - Effort: ~1 hour
   - Add `is_death_effect` field, detect "or die" patterns

3. **Stat Override Parsing**
   - Covers: Feeblemind
   - Effort: ~30 minutes
   - Extend buff system for stat overrides

### Phase 1: High Value / Low Effort

These provide significant gameplay value with minimal development effort.

1. **Charm/Domination Daily Save System**
   - Covers: Ingratiate, Dominate, Sway the Mortal Mind, Sway the Mind
   - Effort: ~2-3 hours
   - Impact: 4+ spells work correctly

2. **Door/Lock State System**
   - Covers: Glyph of Sealing, Glyph of Locking, Knock, Through the Keyhole
   - Effort: ~3-4 hours
   - Impact: Lock puzzles work mechanically

3. **Mirror Image Tracking**
   - Covers: Mirror Image
   - Effort: ~1-2 hours
   - Impact: Popular defensive spell works

4. **Haste Buff Tracking**
   - Covers: Haste
   - Effort: ~1 hour
   - Impact: Important combat buff works

### Phase 2: High Value / Medium Effort

These require more work but unlock significant gameplay.

1. **Invisibility State System**
   - Covers: Invisibility, Circle of Invisibility, Perceive the Invisible, all invisibility runes/glamours
   - Effort: ~6-8 hours
   - Impact: Major gameplay mechanic

2. **Wall/Barrier System**
   - Covers: Wall of Fire, Wall of Ice, Wall of Stone, Web
   - Effort: ~4-6 hours
   - Impact: Battlefield control spells work

3. **Curse System**
   - Covers: Hex Weaving, Remove Curse, Geas (partial), Holy Quest (partial)
   - Effort: ~3-4 hours
   - Impact: Important narrative mechanic

### Phase 3: Defer / LLM Handles

These should NOT be prioritized for mechanical implementation:

- All summoning spells (let LLM describe creatures and actions)
- All scrying/divination beyond existing providers
- All terrain modification
- All complex illusions
- Reality-altering effects (Wish, Fabricate)

---

## Appendix: Spell Counts by Implementation Status

| Status | Count | Percentage |
|--------|-------|------------|
| Works with current resolver | ~12 | 12% |
| Works after recent fixes | 6 | 6% |
| Already implemented (special handler) | 3 | 3% |
| Needs parser enhancements | 10 | 10% |
| Needs special handler (medium) | ~14 | 14% |
| Needs special handler (high complexity) | ~8 | 8% |
| Narrative-only (context provider exists) | 4 | 4% |
| Narrative-only (needs context provider) | ~12 | 12% |
| Narrative-only (pure LLM) | ~20 | 19% |
| Problematic / skip | ~8 | 8% |
| Glamours (mostly narrative) | 20 | - |
| Knacks (mix) | ~24 abilities | - |

---

*Document generated by Dolmenwood Virtual DM spell analysis system*
*Last updated: 2025-12-31 after spell resolver parser fixes*
