# Character Conditions Reference

This document catalogs all conditions that can affect characters in the Dolmenwood Virtual DM system. Conditions represent temporary or ongoing effects that modify a character's abilities, impose penalties, or restrict actions.

## Integration Status Legend

- **Integrated**: Fully implemented in the game engine with mechanical effects
- **Partial**: Condition exists but not all mechanics are implemented
- **Pending**: Condition is defined but not yet wired to game mechanics
- **Planned**: Condition is referenced in code but not yet in ConditionType enum

---

## Core Conditions (ConditionType Enum)

These conditions are defined in `src/data_models.py` and can be applied via the `GlobalController.apply_condition()` method.

### Physical/Health Conditions

| Condition | Description | Duration | Mechanical Effects | Integration Status |
|-----------|-------------|----------|-------------------|-------------------|
| **POISONED** | Affected by a toxin | Varies | -2 to attack rolls and ability checks until cured | Integrated |
| **DISEASED** | Affected by illness | Varies | Effect varies by disease type | Partial |
| **EXHAUSTED** | Physically drained | Until rest | Cumulative penalties: -1 per level to attack/damage | Integrated |
| **STUNNED** | Cannot act | 1+ rounds | Cannot move or take actions, auto-fail DEX saves | Partial |
| **PRONE** | Knocked down | Until stood | -4 to melee attacks, +4 to be hit by melee, -4 to be hit by ranged | Partial |
| **UNCONSCIOUS** | Knocked out | Until healed/rested | Cannot act, unaware of surroundings, auto-fail saves | Integrated |
| **DEAD** | Killed | Permanent | Character is deceased | Integrated |
| **INCAPACITATED** | Cannot take actions | Varies | Cannot take actions or reactions | Pending |

### Sensory Conditions

| Condition | Description | Duration | Mechanical Effects | Integration Status |
|-----------|-------------|----------|-------------------|-------------------|
| **BLINDED** | Cannot see | Varies | Auto-fail sight-based checks, -4 to attack, enemies have +4 to hit | Partial |
| **DEAFENED** | Cannot hear | Varies | Auto-fail hearing-based checks, -2 to initiative | Pending |

### Mental/Magical Conditions

| Condition | Description | Duration | Mechanical Effects | Integration Status |
|-----------|-------------|----------|-------------------|-------------------|
| **CHARMED** | Magically influenced | Varies | Cannot attack charmer, charmer has advantage on social checks | Pending |
| **FRIGHTENED** | Terrified | Varies | Cannot willingly move toward source, -2 to attacks/checks while source visible | Partial |
| **CURSED** | Under a curse | Until removed | Effect varies by curse type | Partial |
| **DREAMLESS** | Cannot dream | Until cured | Periodic Wisdom loss, spell memorization penalty | Pending |

### Transformation Conditions

| Condition | Description | Duration | Mechanical Effects | Integration Status |
|-----------|-------------|----------|-------------------|-------------------|
| **PETRIFIED** | Turned to stone | Until cured | Completely immobile, unconscious, weight x10, immune to damage | Pending |
| **INVISIBLE** | Cannot be seen | Varies | Cannot be targeted by sight, +4 to hit, enemies -4 to hit | Pending |

### Movement/Physical Restriction Conditions

| Condition | Description | Duration | Mechanical Effects | Integration Status |
|-----------|-------------|----------|-------------------|-------------------|
| **PARALYZED** | Cannot move | 1+ turns | Cannot move or act, auto-fail STR/DEX saves, melee attacks auto-hit | Partial |
| **RESTRAINED** | Movement restricted | Until escaped | Speed 0, -2 to attack, +2 to be hit, disadvantage on DEX saves | Partial |
| **ENCUMBERED** | Carrying too much | Until items dropped | Reduced movement speed based on encumbrance level | Integrated |

### Survival Conditions

| Condition | Description | Duration | Mechanical Effects | Integration Status |
|-----------|-------------|----------|-------------------|-------------------|
| **HUNGRY** | Missing food | Until fed | Warning state before starvation | Integrated |
| **STARVING** | No food for days | Until fed | -1 HP per day, cannot heal naturally | Integrated |
| **DEHYDRATED** | Insufficient water | Until hydrated | Cumulative penalties, eventual death | Partial |
| **DROWNING** | Out of breath underwater | Immediate | Must surface or die | Integrated |
| **HOLDING_BREATH** | Underwater with air | CON rounds | Limited time before drowning | Integrated |

### Navigation Conditions

| Condition | Description | Duration | Mechanical Effects | Integration Status |
|-----------|-------------|----------|-------------------|-------------------|
| **LOST** | Disoriented in wilderness | Until found | Random movement direction, doubled travel time | Partial |

---

## Trap-Specific Conditions (Planned)

These conditions are used by trap effects in `src/tables/trap_tables.py` but are not yet in the ConditionType enum. They need to be added and integrated.

| Condition | Source | Description | Duration | Escape Method | Integration Status |
|-----------|--------|-------------|----------|---------------|-------------------|
| **confused** | Gas Trap | Act randomly per Confusion spell | 12 rounds (2 min) | Save vs Doom | Planned |
| **memory_erased** | Gas Trap | Lose memory of last 1d6 hours | Permanent | Magic only | Planned |
| **asleep** | Gas Trap | Unconscious, cannot be woken | 3 turns (30 min) | Save vs Doom | Planned |
| **caged** | Magic Trap | Trapped in magical iron cage | 1 turn (10 min) | STR DC 20 or Dispel Magic | Planned |
| **in_darkness** | Magic Trap | Surrounded by magical darkness | 1 turn (10 min) | Dispel Magic | Planned |
| **polymorphed** | Magic Trap | Transformed into small creature | Until dispelled | Dispel Magic | Planned |
| **teleported** | Magic Trap | Moved to random location | Instant | N/A (one-time effect) | Planned |

---

## Condition Integration Checklist

### Priority 1: Combat-Critical Conditions

These conditions directly affect combat and should be integrated first:

- [ ] `STUNNED`: Implement full action denial and auto-fail saves
- [ ] `PARALYZED`: Implement auto-hit melee attacks, action denial
- [ ] `BLINDED`: Implement attack penalties and advantage/disadvantage
- [ ] `PRONE`: Implement attack modifiers for melee vs ranged
- [ ] `RESTRAINED`: Implement speed reduction and attack modifiers
- [ ] `INCAPACITATED`: Implement action and reaction denial

### Priority 2: Trap Conditions

These conditions are generated by the trap system:

- [ ] Add `CONFUSED` to ConditionType enum
- [ ] Add `MEMORY_ERASED` to ConditionType enum
- [ ] Add `ASLEEP` to ConditionType enum (differs from unconscious)
- [ ] Add `CAGED` to ConditionType enum
- [ ] Add `IN_DARKNESS` to ConditionType enum
- [ ] Add `POLYMORPHED` to ConditionType enum
- [ ] Add `TELEPORTED` to ConditionType enum (or handle as instant effect)

### Priority 3: Magical Conditions

These conditions typically come from spells:

- [ ] `CHARMED`: Implement social interaction modifiers
- [ ] `INVISIBLE`: Implement visibility checks and attack modifiers
- [ ] `PETRIFIED`: Implement transformation mechanics
- [ ] `DREAMLESS`: Implement Wisdom loss and spell penalties

### Priority 4: Environmental Conditions

These conditions come from wilderness/dungeon hazards:

- [ ] `DEAFENED`: Implement initiative penalties
- [ ] `LOST`: Implement navigation effects
- [ ] `DEHYDRATED`: Implement cumulative effects

---

## Condition Application Flow

```
Source (Trap/Spell/Hazard/Combat)
        │
        ▼
┌──────────────────┐
│ HazardResult     │
│ - apply_damage   │
│ - apply_conditions│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Engine Layer     │
│ (Dungeon/HexCrawl)│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ GlobalController │
│ apply_condition()│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ CharacterState   │
│ conditions: []   │
└──────────────────┘
```

---

## Condition Mechanics Reference

### Save Types for Condition Application

| Save Type | Typical Conditions |
|-----------|-------------------|
| **Doom** | Poison, disease, death effects, gas traps |
| **Blast** | Area effects, falling damage avoidance |
| **Ray** | Targeted magical effects (polymorph, petrify) |
| **Charm** | Mind-affecting effects (charm, fear, confusion) |
| **Polymorph** | Physical transformation effects |

### Duration Types

| Duration | Description |
|----------|-------------|
| **Instant** | Effect applied immediately, no ongoing condition |
| **Rounds** | Lasts for X combat rounds (6 seconds each) |
| **Turns** | Lasts for X exploration turns (10 minutes each) |
| **Hours/Days** | Extended duration for curses, diseases |
| **Until Cured** | Requires specific intervention (spell, rest, cure) |
| **Permanent** | Only removed by Dispel Magic, Remove Curse, or death |

### Escape Mechanics

Some conditions allow escape attempts:

| Check Type | Examples |
|-----------|----------|
| **STR check** | Break free from net, lift portcullis, escape cage |
| **DEX check** | Wiggle free from restraints, avoid ongoing effect |
| **CON check** | Resist poison/disease progression |
| **Magic** | Dispel Magic required for magical conditions |

---

## Implementation Notes

### Adding New Conditions

1. Add enum value to `ConditionType` in `src/data_models.py`
2. Add mapping in `GlobalController.apply_condition()` condition_map
3. Add mapping in `GlobalController.remove_condition()` condition_map
4. Implement mechanical effects in relevant engines:
   - Combat effects: `src/combat/combat_engine.py`
   - Movement effects: `src/hex_crawl/hex_crawl_engine.py`, `src/dungeon/dungeon_engine.py`
   - Spell effects: `src/narrative/spell_resolver.py`
5. Add tests in `tests/test_conditions.py` (to be created)

### Condition Stacking

- Same condition from multiple sources: Duration refreshed, doesn't stack
- Different conditions: All apply simultaneously
- Exhaustion: Levels stack (1-6), increasing penalties

### Condition Removal

Conditions can be removed by:
- Duration expiring
- Successful escape check
- Appropriate spell (Remove Curse, Cure Disease, Dispel Magic)
- Rest (for exhaustion)
- Death (removes all conditions except DEAD)
