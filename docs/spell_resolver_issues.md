# Spell Resolver Issues and Solutions

**Generated:** 2025-12-31
**Status:** Implementation gaps identified for "easy" spells

---

## Executive Summary

After testing the spells claimed to "work with current resolver," I found:

| Category | Count |
|----------|-------|
| Actually Works | 7 |
| False Positives (wrong parsing) | 5 |
| Missing Parsing | 4 |
| Need Special Handlers | 6 |

---

## Spells That Actually Work

These spells parse correctly and should work with the current resolver:

| Spell | Parsed Correctly |
|-------|------------------|
| **Ioun Shard** | 1d6+1 damage + level scaling (1 per 3 levels) |
| **Flaming Spirit** | 1d6 damage |
| **Bless** | +1 modifier |
| **Hold Person** | Paralyzed condition |
| **Paralysation** | Paralyzed condition |
| **Vapours of Dream** | Unconscious condition + duration scaling |
| **Ice Storm** | 3d8 damage |

---

## Issue 1: False Positives (Parser Finds Wrong Things)

### 1.1 Frost Ward / Flame Ward - Damage Reduction Misparse

**Problem:** The parser finds "4d6 damage" in the text "4d6 damage is reduced by 4" and interprets it as the spell DEALING 4d6 damage.

**Actual Effect:** The spell REDUCES incoming damage by 1 per die.

**Current Regex:**
```python
damage_pattern = r"(\d+d\d+(?:\s*\+\s*\d+)?)\s*(?:points?\s+of\s+)?(?:damage|hp|hit\s+points?)"
```

**Solution:** Add negative lookbehind for "reduced" context:
```python
# Skip if this is about damage reduction, not damage dealt
if "reduced" in context or "reduce" in context:
    continue
```

**Or better:** Check surrounding context before adding effect:
```python
# Get 50 chars before the match to check context
start_pos = max(0, match.start() - 50)
context = description[start_pos:match.start()].lower()
if "reduce" in context or "less" in context:
    continue  # This is damage reduction, not damage dealt
```

---

### 1.2 Lesser/Greater Healing - Healing Parsed as Damage

**Problem:** "Restores 1d6+1 Hit Points" is parsed as BOTH:
- DAMAGE effect (regex: `\d+d\d+.*hit\s+points?`)
- HEALING effect (regex: `restores?\s*\d+d\d+`)

**Solution:** Make damage regex more specific - require "damage" word, not "hit points" for healing context:
```python
# Only match damage if explicitly says "damage", not "Hit Points"
damage_pattern = r"(\d+d\d+(?:\s*\+\s*\d+)?)\s*(?:points?\s+of\s+)?damage"
# NOT: damage|hp|hit\s+points  <- This causes false positive
```

---

### 1.3 Lesser Healing - Curing Parsed as Applying

**Problem:** "Curing paralysis" triggers the paralysis condition parser, but the spell CURES paralysis, not applies it.

**Current Check:**
```python
if f"remove {keyword}" in description or f"cure {keyword}" in description:
    continue
```

**Issue:** The check is looking for "cure paralysis" but the spell says "Curing paralysis" (with capital C and -ing form).

**Solution:** Case-insensitive and variant matching:
```python
desc_lower = description.lower()
# Check for cure/remove/nullify/end context
removal_patterns = [
    f"cure {keyword}", f"cures {keyword}", f"curing {keyword}",
    f"remove {keyword}", f"removes {keyword}", f"removing {keyword}",
    f"negat {keyword}", f"end {keyword}", f"ends {keyword}",
]
if any(pattern in desc_lower for pattern in removal_patterns):
    continue
```

---

### 1.4 Shield of Force - "Invisible" False Positive

**Problem:** "Conjures an invisible barrier" triggers the invisibility condition parser.

**Actual Effect:** The BARRIER is invisible (descriptive), not the caster.

**Solution:** Check that "invisible" applies to a creature, not an object:
```python
# Check context - invisible should apply to creature/subject/caster
invisible_creature_patterns = [
    "creature.*invisible", "invisible.*creature",
    "subject.*invisible", "invisible.*subject",
    "caster.*invisible", "invisible.*caster",
    "rendered invisible", "become invisible", "becomes invisible",
    "disappear", "shimmers and disappears",
]
if keyword == "invisible":
    if not any(pattern in desc_lower for pattern in invisible_creature_patterns):
        continue  # Probably describing an invisible object, not condition
```

---

### 1.5 Missile Ward - "Splinter" → "Stone" → Petrified

**Problem:** The word "splinter" in "missiles...shatter or splinter" is matching the "stone" keyword for petrification.

**Investigation:** The word "stone" appears in "spl**int**er" - wait, that's not it. Let me check...

Actually the issue is the condition_keywords has `"stone": "petrified"` and "stone" appears in the description somewhere. The description says "1″ away from the subject's flesh" - the word "stone" must appear elsewhere.

Looking at full description: "providing complete protection from normal missiles, which shatter or splinter 1″ away..."

Actually there's no "stone" - let me re-check. The regex must be matching something else.

**Real Issue:** The word ordering - need to investigate further. For now, require more context for petrification:
```python
if keyword == "stone":
    # Only apply if context suggests petrification, not just "stone" material
    if "turn to stone" not in desc_lower and "flesh to stone" not in desc_lower:
        continue
```

---

## Issue 2: Missing Parsing (Should Find But Doesn't)

### 2.1 Fireball/Lightning Bolt/Acid Globe - Level Scaling for Damage

**Problem:** "1d6 damage per Level of the caster" is parsed as only "1d6 damage" - the level scaling is lost.

**Current State:**
- Damage regex finds: `1d6`
- Level scaling regex looks for: `"X per Level"` patterns for projectiles/targets
- Missing: Damage dice scaling with level

**Impact:** A Level 5 caster's Fireball would do 1d6 instead of 5d6!

**Solution:** Add damage scaling parser:
```python
# Pattern: "Xd6 damage per Level"
damage_per_level_pattern = r"(\d+d\d+)\s+damage\s+per\s+level"
matches = re.findall(damage_per_level_pattern, description, re.IGNORECASE)
for match in matches:
    effect = MechanicalEffect(
        category=MechanicalEffectCategory.DAMAGE,
        damage_dice=match,
        level_multiplier=True,  # NEW FIELD: multiply dice by caster level
        description=f"Deals {match} × caster level damage",
    )
    parsed.add_effect(effect)
```

**Also need:** Update `_apply_mechanical_effects` to multiply damage dice by caster level when `level_multiplier=True`.

---

### 2.2 Ignite/Extinguish - Flat Damage Not Parsed

**Problem:** "suffer 1 damage per stream of sparks" uses flat "1 damage" not dice notation.

**Solution:** Add flat damage pattern:
```python
# Pattern: "suffer X damage" (flat, no dice)
flat_damage_pattern = r"suffer\s+(\d+)\s+damage"
matches = re.findall(flat_damage_pattern, description, re.IGNORECASE)
for match in matches:
    effect = MechanicalEffect(
        category=MechanicalEffectCategory.DAMAGE,
        damage_dice=match,  # Store as string "1" not "1d1"
        damage_type="fire",  # From context
    )
    parsed.add_effect(effect)
```

**Note:** This spell also has level scaling ("one stream per Level") which IS parsed correctly.

---

### 2.3 Mantle of Protection - Modifier Pattern Not Matching

**Problem:** "+1 Armour Class and Saving Throw bonus" doesn't match the current pattern.

**Current Pattern:**
```python
stat_pattern = r"([+-]\d+)\s*(?:bonus|penalty)?\s*(?:to\s+)?(?:attack|ac|armor class|saving throw)"
```

**Issue:** The text says "Armour Class" (British spelling) and "bonus" comes AFTER the stats, not before.

**Solution:** Expand pattern:
```python
stat_patterns = [
    # Original: +1 bonus to attack
    r"([+-]\d+)\s*(?:bonus|penalty)?\s*(?:to\s+)?(?:attack|ac|armou?r\s+class|saving\s+throws?)",
    # Reversed: +1 Armour Class...bonus
    r"([+-]\d+)\s+(?:armou?r\s+class|ac|saving\s+throws?|attack).*?bonus",
    # Bonus of +1
    r"bonus\s+of\s+([+-]?\d+)",
]
```

---

### 2.4 Shield of Force - AC Setting Not Parsed

**Problem:** "grants the caster AC 17" sets AC to a specific value, not a modifier.

**Current Parser:** Only looks for +/- modifiers.

**Solution:** Add AC setting pattern:
```python
# Pattern: "AC 17", "grants AC 15", etc.
ac_set_pattern = r"(?:grants?|provides?|gives?)\s+(?:the\s+caster\s+)?ac\s+(\d+)"
matches = re.findall(ac_set_pattern, description, re.IGNORECASE)
for match in matches:
    effect = MechanicalEffect(
        category=MechanicalEffectCategory.BUFF,
        ac_override=int(match),  # NEW FIELD: Override AC to this value
        description=f"Sets AC to {match}",
    )
    parsed.add_effect(effect)
```

**Note:** Shield of Force has conditional AC (17 vs missiles, 15 vs other). This requires condition context:
```python
# Check for conditional context
if "missile" in nearby_text:
    effect.condition_context = "vs_missiles"
elif "other" in nearby_text:
    effect.condition_context = "vs_other"
```

---

## Issue 3: Spells Needing Special Handlers

These spells cannot be parsed mechanically and need custom handlers:

| Spell | Effect Type | Proposed Handler |
|-------|-------------|------------------|
| **Disintegrate** | Save vs Doom or destroyed | `_handle_disintegrate()` - death effect |
| **Word of Doom** | 4d8 levels die | `_handle_word_of_doom()` - mass death by HD |
| **Cloudkill** | 1 damage + Level 4 or lower die | `_handle_cloudkill()` - ongoing + death |
| **Anti-Magic Ward** | Block spells Ranks 1-3 | Special flag on caster state |
| **Silence** | No sound/spells in area | Area effect on location |
| **Feeblemind** | INT=3, no spells | `_handle_feeblemind()` - stat override |

### Recommended Approach

For death effects (Disintegrate, Word of Doom, Cloudkill):
```python
def _handle_death_spell(self, spell, caster, targets, dice_roller):
    """Handle spells that cause instant death on failed save."""
    results = {"kills": [], "survivors": []}

    for target_id in targets:
        # Check if target already made save
        if target_id in self._targets_saved:
            results["survivors"].append(target_id)
            continue

        # Death effect
        if self._controller:
            self._controller.kill_character(target_id, cause=spell.name)
        results["kills"].append(target_id)

    return {"narrative_context": results}
```

---

## Recommended Fix Priority

### Phase 1: Critical Fixes (Prevents Wrong Behavior)

1. **Fix false positive for damage reduction** (Frost/Flame Ward)
   - Currently applies 4d6 damage instead of reducing it!

2. **Fix healing parsed as damage** (Lesser/Greater Healing)
   - Currently damages AND heals the target

3. **Add level scaling for damage** (Fireball, Lightning Bolt, Acid Globe)
   - Currently Fireball does 1d6 instead of Nd6 where N=level

### Phase 2: Missing Features

4. **Fix condition application context** (cure vs apply)
5. **Add AC override parsing** (Shield of Force)
6. **Add flat damage parsing** (Ignite/Extinguish)
7. **Fix modifier pattern** (Mantle of Protection)

### Phase 3: Special Handlers

8. **Implement death effect handlers** (Disintegrate, Word of Doom)
9. **Implement area denial handlers** (Silence, Cloudkill)
10. **Implement stat override handlers** (Feeblemind)

---

## Appendix: Test Script

```python
# Run this to verify fixes
import sys
sys.path.insert(0, 'src')
from narrative.spell_resolver import SpellResolver, SpellData, MagicType

resolver = SpellResolver()

# Test cases that should pass after fixes
test_cases = [
    ("Fireball", "suffer 1d6 damage per Level",
     lambda p: any(e.level_multiplier for e in p.effects)),

    ("Frost Ward", "4d6 damage is reduced by 4",
     lambda p: not any(e.category.value == "damage" for e in p.effects)),

    ("Lesser Healing", "Restores 1d6+1 Hit Points",
     lambda p: (
         any(e.category.value == "healing" for e in p.effects) and
         not any(e.category.value == "damage" for e in p.effects)
     )),
]

for name, desc, check in test_cases:
    spell = SpellData(
        spell_id=name.lower().replace(" ", "_"),
        name=name,
        level=3,
        magic_type=MagicType.ARCANE,
        duration="Instant",
        range="120'",
        description=desc,
    )
    parsed = resolver.parse_mechanical_effects(spell)
    status = "PASS" if check(parsed) else "FAIL"
    print(f"{status}: {name}")
```
