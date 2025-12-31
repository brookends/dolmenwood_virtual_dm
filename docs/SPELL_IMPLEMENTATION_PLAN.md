# Dolmenwood Spell Implementation Plan

## Executive Summary

This plan covers implementation of **166 spells** across 6 magic types (Arcane, Divine, Glamours, Runes, Knacks). Based on the Implementation Matrix and Guide, the work is organized into **5 phases** with clear dependencies and priorities.

### Spell Count by Implementation Level
| Level | Count | Description |
|-------|-------|-------------|
| Minor | 31 | Parser fixes, wiring existing mechanics |
| Moderate | 65 | Contained subsystem or special handler |
| Significant | 27 | New world/combat/state machinery |
| Skip | 43 | Oracle fallback with minimal state tags |

---

## Phase 0: Pre-flight Fixes (Foundation Work)

Before implementing individual spells, these infrastructure improvements unlock multiple spells at once.

### 0.1 Spell Loader & Registry
**Priority: CRITICAL**

Create `src/content_loader/spell_loader.py`:
- Iterate `data/content/spells/*.json` and create `SpellData` instances
- Parse raw duration/range/description into structured fields
- Register into `SpellResolver` via `register_spell()`
- Call during startup in `NarrativeResolver.__init__()`

**Unlocks:** All 166 spells become loadable

### 0.2 AC Override Support
**Priority: HIGH**

Fix inconsistency in `StatModifier`:
- Add `mode: Literal["add", "set"] = "add"` to `StatModifier`
- Update `CharacterState.get_effective_ac()` to handle set/override modifiers
- Update `GlobalController.apply_buff()` to accept override semantics
- Remove/align `is_override` usage in `SpellResolver`

**Unlocks:** Shield of Force, Missile Ward, AC-modifying spells

### 0.3 Visibility State System
**Priority: HIGH**

Add visibility tracking to `CharacterState`:
```python
class VisibilityState(str, Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    INVISIBLE = "invisible"
    REVEALED = "revealed"
```

Combat targeting integration:
- Targeting penalties for INVISIBLE targets
- Break invisibility on hostile action
- "See invisible" effect bypasses penalties

**Unlocks:** Invisibility (12 spells), Fairy Dust, Vanishing, Rune of Invisibility

### 0.4 Charm/Control Condition System
**Priority: HIGH**

Extend condition system for charm tracking:
- Add `source_spell_id` and `caster_id` to `Condition` dataclass
- Implement `saves:daily` recurring save system in `SpellResolver.tick_effects()`
- Add "is_hostile_to(caster)" helper for charmed creature behavior

**Unlocks:** Ingratiate, Dominate, Sway the Mind, charm-type spells (8+ spells)

### 0.5 Area Effect Enhancement
**Priority: MEDIUM**

Extend `AreaEffect` system:
- Add `blocks_movement`, `blocks_sound`, `blocks_magic` flags
- Add `entry_damage`, `per_turn_damage`, `save_type` fields
- Add `escape_mechanism` for entangle-type effects

**Unlocks:** Web, Silence, Wall spells, terrain manipulation (15+ spells)

---

## Phase 1: Minor Spells (31 spells)

These require parser fixes and wiring existing mechanics. Target: 1-2 days each.

### 1.1 Damage Spells (Direct Resolution)
Already mostly work - ensure parsers catch all patterns:

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Ignite/Extinguish | Arcane | 1 | Flat damage parser needed |
| Fireball | Arcane | 3 | Works, verify AoE |
| Lightning Bolt | Arcane | 3 | Works, verify line |
| Acid Globe | Arcane | 4 | Works, verify splash |
| Dweomerfire | Arcane | 6 | Standard damage |
| Cannibalise | Arcane | 3 | Damage + healing |
| Ice Storm | Rune (Greater) | - | 3d8 AoE damage |
| Eternal Slumber | Rune (Mighty) | - | Sleep + death effect |

**Parser Enhancement:** Add `spell_parser:flat_damage` support:
```python
# Match: "1 damage per round", "2 points of damage"
pattern = r"(\d+)\s+(?:points?\s+of\s+)?damage"
```

### 1.2 Healing Spells
| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Lesser Healing | Divine | 1 | Works |
| Greater Healing | Divine | 4 | Works |
| Light | Divine | 1 | Utility only |
| Rally | Divine | 1 | Morale bonus |
| Frost Ward | Divine | 1 | Resistance buff |
| Flame Ward | Divine | 2 | Resistance buff |
| Bless | Divine | 2 | +1 attack/damage buff |
| Bless Weapon | Divine | 3 | Weapon enhancement |
| Gingerbread Charm | Arcane | 1 | Healing item creation |

### 1.3 Death Effect Spells
Add `spell_resolution:death_effects` support:
- Extend `MechanicalEffect` with `is_death_effect`, `death_on_failed_save`
- In `_apply_mechanical_effects()`: set HP to 0 on failed save

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Cloudkill | Arcane | 5 | Death save + damage |
| Disintegrate | Arcane | 6 | Save vs Doom or die |
| Petrification | Arcane | 6 | Save or petrified |
| Word of Doom | Arcane | 6 | HD budget targeting |
| Rune of Death | Rune (Mighty) | - | HD budget targeting |

### 1.4 Simple Buff/Condition Spells
| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Crystal Resonance | Arcane | 1 | Already implemented |
| Decipher | Arcane | 1 | Already implemented |
| Ioun Shard | Arcane | 1 | Auto-hit damage |
| Shield of Force | Arcane | 1 | AC override (after 0.2) |
| Vapours of Dream | Arcane | 1 | Sleep condition |
| Flaming Spirit | Arcane | 2 | DoT effect |
| Paralysation | Arcane | 3 | Paralysis condition |
| Hold Person | Divine | 2 | Paralysis condition |
| Mantle of Protection | Divine | 1 | AC/save buff |
| Circle of Protection | Divine | 4 | AoE buff |
| Purify Food and Drink | Divine | 1 | Already implemented |
| Charm Serpents | Divine | 2 | Charm effect |
| Decay | Arcane | 1 | Object destruction |

---

## Phase 2: Moderate Spells (65 spells)

These require contained subsystems or special handlers. Target: 2-4 days each.

### 2.1 Charm/Control Spells (After Phase 0.4)
| Spell | Magic Type | Level | Required System |
|-------|------------|-------|-----------------|
| Ingratiate | Arcane | 1 | control:charm, saves:daily |
| Dominate | Arcane | 4 | control:charm, saves:daily, ai:command_interface |
| Sway the Mortal Mind | Rune (Lesser) | - | Same as Ingratiate |
| Sway the Mind | Rune (Greater) | - | Same as Dominate |
| Command | Divine | 1 | One-word command |
| Awe | Glamour | - | Morale check |
| Forgetting | Glamour | - | Memory manipulation |

### 2.2 Door/Lock/Glyph System
Create `world:doors_locks` and `world:glyphs` subsystems:
- Model doors as stateful objects: LOCKED/BARRED/SEALED/MAGICAL_LOCK
- Glyphs stored on doors with trigger conditions

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Glyph of Sealing | Arcane | 1 | Temp lock (2d6 turns) |
| Glyph of Locking | Arcane | 2 | Permanent lock + password |
| Knock | Arcane | 2 | Unlock + dispel glyphs |
| Serpent Glyph | Arcane | 3 | Trap glyph |
| Through the Keyhole | Glamour | - | See through doors |
| Lock Singer | Knack | - | Open locks musically |

### 2.3 Combat Modifier Spells
| Spell | Magic Type | Level | Required System |
|-------|------------|-------|-----------------|
| Mirror Image | Arcane | 2 | combat:mirror_images (1d4 images) |
| Haste | Arcane | 3 | combat:extra_actions, buffs:multi_target |
| Confusion | Arcane | 4 | combat:behavior_table, conditions:confusion |
| Fear | Arcane | 3 | Morale/flee effect |
| Ginger Snap | Arcane | 3 | Attack modifier |

**Mirror Image Implementation:**
```python
# Add to CharacterState
mirror_image_count: int = 0

# On attack resolution
def resolve_attack_vs_mirror_image(target: CharacterState) -> bool:
    """Returns True if image absorbs hit."""
    if target.mirror_image_count > 0:
        # Roll to see if image is hit
        roll = dice_roller.roll_d6()
        if roll <= target.mirror_image_count:
            target.mirror_image_count -= 1
            return True  # Image hit, attack negated
    return False
```

### 2.4 Area/Zone Spells (After Phase 0.5)
| Spell | Magic Type | Level | Area Type |
|-------|------------|-------|-----------|
| Web | Arcane | 2 | zones:terrain_web, conditions:entangle |
| Silence | Divine | 2 | zones:silence, spellcasting:verbal_lockout |
| Darkness (via spells) | Various | - | zones:darkness |
| Fog Cloud | Rune (Lesser) | - | zones:obscurement |
| Gust of Wind | Rune (Lesser) | - | zones:push |
| Deathly Blossom | Rune (Lesser) | - | zones:hazards |

### 2.5 Buff Enhancement Spells
| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Missile Ward | Arcane | 3 | buffs:immunity (normal missiles) |
| Water Breathing | Arcane | 3 | buffs:immunity (drowning) |
| Air Sphere | Arcane | 5 | buffs:immunity (gas) |
| Dark Sight | Arcane | 3 | Vision enhancement |
| Feeblemind | Arcane | 5 | buffs:stat_override (INT=3) |
| Dispel Magic | Arcane | 3 | Remove active spell effects |
| Remove Curse | Divine | 3 | curses:tracking removal |
| Cure Affliction | Divine | 3 | Condition removal |
| Remove Poison | Divine | 4 | Poison removal |

### 2.6 Summon/Control Spells
| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Serpent Transformation | Divine | 4 | Create 2d8 adders |
| Animal Growth | Divine | 3 | Size increase |
| Summon Shadow | Arcane | 5 | Shadow creature |
| Insect Plague | Divine | 5 | Swarm creation |

### 2.7 Curse/Hex System
Create `curses:tracking` subsystem:
```python
@dataclass
class CurseState:
    curse_id: str
    source: str  # Who/what placed the curse
    curse_type: str  # Specific curse category
    severity: str  # minor, normal, powerful, legendary
    effects: list[EffectCommand]
    removal_conditions: list[str]
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Hex Weaving | Arcane | 4 | Place or remove curses |
| Remove Curse | Divine | 3 | Remove curses |

### 2.8 Miscellaneous Moderate Spells
| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Arcane Cypher | Arcane | 2 | Encode text |
| Ventriloquism | Arcane | 1 | Sound projection |
| Speak with Dead | Arcane | 3 | NPC interaction |
| Transparency | Arcane | 2 | Object transparency |
| En Croute | Arcane | 2 | Food preservation |
| Yeast Growth | Arcane | 1 | Baking magic |
| Control Weather | Arcane | 6 | Weather manipulation |
| Wave of Force | Arcane | 6 | Push/knockback |
| Holy Light | Divine | 3 | Light + damage vs undead |
| Holy Fire | Divine | 5 | Fire damage vs evil |
| Create Water | Divine | 4 | Resource creation |
| Create Food | Divine | 5 | Resource creation |
| Raise Dead | Divine | 5 | Resurrection |

---

## Phase 3: Significant Spells (27 spells)

These require new world/combat/state machinery. Target: 3-7 days each.

### 3.1 Visibility System Spells (After Phase 0.3)
| Spell | Magic Type | Level | Complexity |
|-------|------------|-------|------------|
| Invisibility | Arcane | 2 | Single target |
| Perceive the Invisible | Arcane | 2 | Detection |
| Circle of Invisibility | Arcane | 3 | Mobile zone |
| Fairy Dust | Glamour | - | Multi-target |
| Vanishing | Glamour | - | Self + objects |
| Subtle Sight | Glamour | - | See invisible |
| Rune of Vanishing | Rune (Lesser) | - | Item/self |
| Rune of Invisibility | Rune (Greater) | - | Duration-based |

### 3.2 Movement/Verticality System
Create `movement:flight_state` and `movement:verticality`:
```python
class FlightState(str, Enum):
    GROUNDED = "grounded"
    HOVERING = "hovering"
    FLYING = "flying"
    FALLING = "falling"

# Add to CharacterState
altitude: int = 0  # Relative height level
flight_state: FlightState = FlightState.GROUNDED
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Levitate | Arcane | 2 | Vertical movement only |
| Fly | Arcane | 3 | Full 3D movement |

### 3.3 Teleportation System
Create `travel:familiarity` and `travel:mishap_table`:
```python
class LocationFamiliarity(str, Enum):
    INTIMATELY_KNOWN = "intimately_known"
    WELL_KNOWN = "well_known"
    VISITED = "visited"
    DESCRIBED = "described"
    UNKNOWN = "unknown"

# Mishap table per familiarity level
TELEPORT_MISHAP_TABLE = {
    "intimately_known": {"success": 95, "off_target": 4, "mishap": 1},
    # ...
}
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Dimension Door | Arcane | 4 | Short range, visual |
| Teleport | Arcane | 5 | Long range, familiarity-based |

### 3.4 Transformation System
Create `transformation:form_templates`:
```python
@dataclass
class FormTemplate:
    form_id: str
    name: str
    movement_speed: int
    attacks: list[Attack]
    special_abilities: list[str]
    size: str
    # Original stats preserved for restoration
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Polymorph | Arcane | 4 | Curated form templates |

### 3.5 Summoning/Control System
Create `summoning:creatures` and `summoning:control_rules`:
```python
@dataclass
class SummonedCreature:
    creature_id: str
    summoner_id: str
    creature_type: str  # undead, elemental, fairy, etc.
    loyalty: str  # obedient, reluctant, hostile
    duration_remaining: int
    control_condition: Optional[str]  # concentration, ritual, etc.
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Animate Dead | Arcane | 5 | summoning:undead_control |
| Conjure Elemental | Arcane | 5 | concentration:loss_rules |

### 3.6 Compulsion/Geas System
Create `compulsion:oath_clock` and `penalties:escalation`:
```python
@dataclass
class CompulsionState:
    compulsion_id: str
    goal: str
    violation_triggers: list[str]
    current_penalty_level: int  # Escalates on violation
    penalty_effects: list[EffectCommand]  # Per level
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Geas | Arcane | 6 | Quest compulsion |
| Holy Quest | Divine | 5 | Same system |

### 3.7 Barrier/Wall Spells
Create `world:barriers` subsystem:
```python
@dataclass
class BarrierEffect:
    barrier_id: str
    barrier_type: str  # fire, ice, stone, force
    blocks_movement: bool
    blocks_vision: bool
    entry_damage: Optional[str]  # Dice expression
    save_type: Optional[str]
    duration_remaining: int
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Wall of Fire | Arcane | 4 | zones:hazards |
| Wall of Ice | Arcane | 4 | world:barriers |
| Wall of Stone | Arcane | 5 | world:barriers |
| Passwall | Arcane | 5 | world:temporary_passage |

### 3.8 Terrain Manipulation
Create `world:terrain_tags`:
| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Plant Growth | Arcane | 4 | Terrain enhancement |
| Mire | Arcane | 5 | Terrain obstacle |

### 3.9 Anti-Magic System
Create `spellcasting:interception`:
```python
def check_spell_interception(spell: SpellData, target: str) -> bool:
    """Check if a ward blocks this spell."""
    # Check for active wards on target/area
    # Compare spell rank vs ward level
    return False  # Spell proceeds
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Anti-Magic Ward | Arcane | 6 | Blocks rank 1-3 spells |

### 3.10 HD-Budget Targeting
Create `targeting:hd_budget`:
```python
def select_hd_budget_targets(
    budget_dice: str,  # e.g., "4d8"
    available_targets: list[CreatureInfo],
    dice_roller: DiceRoller,
) -> list[str]:
    """Select lowest-HD targets until budget exhausted."""
    budget = dice_roller.roll(budget_dice).total
    sorted_targets = sorted(available_targets, key=lambda t: t.hit_dice)
    selected = []
    for target in sorted_targets:
        if target.hit_dice <= budget:
            selected.append(target.id)
            budget -= target.hit_dice
    return selected
```

| Spell | Magic Type | Level | Notes |
|-------|------------|-------|-------|
| Word of Doom | Arcane | 6 | 4d8 HD budget |
| Rune of Death | Rune (Mighty) | - | 4d8 HD budget |

---

## Phase 4: Skip Spells (43 spells) - Oracle Fallback

These spells are handled via oracle adjudication with minimal state tags.

### 4.1 Divination/Detection Spells
Handle via `MythicSpellAdjudicator.adjudicate_divination()`:
| Spell | Magic Type | Level |
|-------|------------|-------|
| Detect Evil | Divine | 1 |
| Detect Magic | Divine | 1 |
| Detect Disguise | Divine | 1 |
| Find Traps | Divine | 2 |
| Reveal Alignment | Divine | 2 |
| Locate Object | Divine | 3 |
| Crystal Vision | Arcane | 3 |
| Arcane Eye | Arcane | 4 |
| Communion | Divine | 5 |

### 4.2 Communication/Summoning Spells
Handle via narrative + oracle:
| Spell | Magic Type | Level |
|-------|------------|-------|
| Fairy Servant | Arcane | 1 |
| Dweomerlight | Arcane | 2 |
| Mind Crystal | Arcane | 2 |
| Phantasm | Arcane | 2 |
| Sending | Arcane | 5 |
| Speak with Animals | Divine | 2 |
| Speak with Plants | Divine | 4 |
| Silver Tongue | Glamour | - |

### 4.3 Reality-Warping Spells
Handle via `MythicSpellAdjudicator.adjudicate_wish()`:
| Spell | Magic Type | Level |
|-------|------------|-------|
| Fabricate | Arcane | 5 |
| Oracle | Arcane | 6 |
| Invisible Stalker | Arcane | 6 |
| Move Terrain | Arcane | 6 |
| Project Image | Arcane | 6 |
| Hallucinatory Terrain | Arcane | 4 |
| Woodland Veil | Arcane | 4 |
| Rune of Wishing | Rune (Mighty) | - |
| Dream Ship | Rune (Mighty) | - |
| Summon Wild Hunt | Rune (Mighty) | - |

### 4.4 Glamours (Narrative-First)
Most glamours are narrative effects with optional small mechanical tags:
| Spell | Notes |
|-------|-------|
| Beguilement | Narrative + optional reaction modifier |
| Breath of the Wind | Narrative only |
| Cloak of Darkness | Narrative + stealth bonus |
| Conjure Treats | Narrative only |
| Dancing Flame | Narrative only |
| Disguise Object | Narrative + deception |
| Flame Charm | Narrative only |
| Masquerade | Narrative + disguise |
| Mirth and Malice | Narrative + mood effect |
| Moon Sight | Narrative + vision |
| Seeming | Narrative + disguise |
| Walk in Shadows | 2-in-6 check for shadow door |
| Fool's Gold | Deception + save |

### 4.5 Knacks (Narrative Abilities)
Treat as narrative abilities with limited mechanical tags:
| Knack | Notes |
|-------|-------|
| Bird Friend | Narrative + optional morale modifier |
| Root Friend | Narrative only |
| Thread Whistling | Narrative only |
| Wood Kenning | Narrative + knowledge check |
| Yeast Master | Narrative only |

### 4.6 Runes (Oracle-Assisted)
| Spell | Notes |
|-------|-------|
| Fairy Steed | Narrative + mount stats |
| Arcane Unbinding | Dispel + oracle for complex cases |
| Fairy Gold | Deception + duration |
| Proof Against Deadly Harm | Death save protection |
| Unravel Death | Resurrection + oracle |

---

## Implementation Timeline

### Sprint 1: Foundation (Weeks 1-2)
- [ ] Phase 0.1: Spell Loader & Registry
- [ ] Phase 0.2: AC Override Support
- [ ] Phase 0.3: Visibility State System (partial)
- [ ] Phase 1.1-1.2: Damage and Healing spells (13 spells)

### Sprint 2: Combat Core (Weeks 3-4)
- [ ] Phase 0.4: Charm/Control System
- [ ] Phase 1.3-1.4: Death effects and simple buffs (18 spells)
- [ ] Phase 2.1: Charm spells (7 spells)
- [ ] Phase 2.3: Combat modifier spells (5 spells)

### Sprint 3: World Interaction (Weeks 5-6)
- [ ] Phase 0.5: Area Effect Enhancement
- [ ] Phase 2.2: Door/Lock/Glyph system (6 spells)
- [ ] Phase 2.4: Area/Zone spells (6 spells)
- [ ] Phase 2.5: Buff enhancement spells (9 spells)

### Sprint 4: Advanced Systems (Weeks 7-8)
- [ ] Phase 2.6-2.7: Summon/Control and Curse systems (7 spells)
- [ ] Phase 3.1: Visibility system spells (8 spells)
- [ ] Phase 3.2: Movement/Verticality (2 spells)

### Sprint 5: Complex Magic (Weeks 9-10)
- [ ] Phase 3.3: Teleportation (2 spells)
- [ ] Phase 3.4: Transformation (1 spell)
- [ ] Phase 3.5-3.6: Summoning and Compulsion (4 spells)

### Sprint 6: World Shaping (Weeks 11-12)
- [ ] Phase 3.7-3.10: Barriers, terrain, anti-magic, targeting (9 spells)
- [ ] Phase 4: Oracle fallback integration for skip spells (43 spells)

---

## Testing Strategy

### Unit Tests
For each spell implementation:
1. **Parser tests**: Verify mechanical effects are parsed correctly
2. **State mutation tests**: Verify conditions/buffs/damage applied correctly
3. **Duration tests**: Verify tick_effects handles expiration
4. **Save tests**: Verify saving throws work correctly

### Integration Tests
1. **Spell casting flow**: End-to-end from cast to effect
2. **Combat integration**: Spells in combat context
3. **Duration ticking**: Effects over multiple rounds/turns
4. **Concentration**: Breaking concentration ends effects

### Regression Tests
1. **Existing spell tests** must continue passing
2. **New subsystems** must not break existing functionality

---

## Files to Modify

### Core Files
- `src/narrative/spell_resolver.py` - Main spell resolution
- `src/narrative/narrative_resolver.py` - Spell casting entry point
- `src/game_state/global_controller.py` - State mutations
- `src/data_models.py` - Data structures (conditions, modifiers, visibility)

### New Files
- `src/content_loader/spell_loader.py` - Spell loading from JSON
- `src/spells/visibility_system.py` - Visibility state management
- `src/spells/charm_system.py` - Charm/control tracking
- `src/spells/glyph_system.py` - Door/lock/glyph management
- `src/spells/summoning_system.py` - Summoned creature management
- `src/spells/barrier_system.py` - Wall/barrier management
- `src/spells/compulsion_system.py` - Geas/quest tracking

### Oracle Integration
- `src/oracle/spell_adjudicator.py` - Already exists, extend for more spell types
- `src/oracle/effect_commands.py` - Already exists, wire to controller

### Tests
- `tests/test_spell_resolver.py` - Extend with new spell tests
- `tests/test_spell_loader.py` - New
- `tests/test_visibility_system.py` - New
- `tests/test_charm_system.py` - New
- `tests/test_spell_integration.py` - End-to-end tests

---

## Success Criteria

1. **All 166 spells** have a defined resolution path (mechanical, oracle, or hybrid)
2. **Minor spells** (31) resolve fully mechanically
3. **Moderate spells** (65) resolve with contained subsystems
4. **Significant spells** (27) have functional subsystems
5. **Skip spells** (43) resolve via oracle with appropriate context
6. **Test coverage** > 80% for new spell code
7. **No regressions** in existing 975+ tests
