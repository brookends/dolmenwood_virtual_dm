# NPC Conversational Richness Enrichment Prompt

You are enriching NPC data for a Dolmenwood TTRPG virtual game master system. Your task is to add structured conversational and mechanical data to NPCs based on their existing descriptions, enabling dynamic conversations, creative problem-solving, and faction manipulation mechanics.

## Your Task

Given an NPC's existing data (name, description, demeanor, desires, secrets, etc.), generate the following enrichment fields:

---

## Field Specifications

### 1. `vulnerabilities` (array of strings)

Weaknesses that increase the likelihood of creative approaches succeeding against this NPC. These are exploitable traits, fears, or desires.

**Guidelines:**
- Derive from the NPC's description, desires, and personality
- Use lowercase_snake_case identifiers
- Include emotional vulnerabilities (fear, love, guilt)
- Include practical vulnerabilities (bribery, flattery, specific items)
- For fairies: always include `cold_iron` if applicable

**Examples:**
```json
"vulnerabilities": ["cold_iron", "shiny_objects", "mention_of_thorn_rosy"]
"vulnerabilities": ["flattery", "appeal_to_nobility", "promise_of_glory"]
"vulnerabilities": ["better_payment", "threat_of_violence"]
"vulnerabilities": ["mention_of_ygraine", "promise_of_freedom", "musical_appreciation"]
```

---

### 2. `known_topics` (array of topic objects)

Conversation topics the NPC will discuss. These drive the conversation system and provide information to players.

**Topic Object Schema:**
```json
{
  "topic_id": "unique_snake_case_id",
  "content": "The actual dialogue or description of what the NPC says/does when this topic comes up. Write in present tense, as if narrating the moment.",
  "keywords": ["array", "of", "trigger", "words", "that", "activate", "this", "topic"],
  "required_disposition": -5,  // Minimum disposition needed (-5 = hostile will share, 5 = requires trusted friend)
  "category": "quest|personal|location|npc|lore|situation|revelation|interaction",
  "shared": false,  // Has this been shared with the party yet?
  "priority": 10,   // Higher = more likely to come up (1-10)
  "requires_ungagged": true  // Optional: only for gagged/silenced NPCs
}
```

**Category Definitions:**
- `quest`: Information about quests, hunts, missions
- `personal`: NPC's own history, feelings, relationships
- `location`: Information about places
- `npc`: Information about other NPCs
- `lore`: World lore, history, legends
- `situation`: Current circumstances, recent events
- `revelation`: Dramatic information that changes understanding
- `interaction`: Behavioral responses (for non-speaking creatures)

**Guidelines:**
- Create 2-5 topics per NPC based on their knowledge and role
- Write `content` as actual dialogue in quotes or narrative description
- Include 5-10 keywords that players might naturally use
- Set `required_disposition` based on how guarded the information is
- Higher priority topics come up more readily in conversation

---

### 3. `secret_info` (array of secret objects)

Hidden information the NPC knows but won't easily share. Requires trust, disposition, or bribery.

**Secret Object Schema:**
```json
{
  "secret_id": "unique_snake_case_id",
  "content": "The actual secret information, written as if the NPC is revealing it.",
  "hint": "Observable clue that suggests this secret exists. What might a perceptive player notice?",
  "keywords": ["trigger", "words", "that", "might", "prompt", "this", "secret"],
  "required_disposition": 2,  // Minimum disposition (usually 1-3)
  "required_trust": 1,        // Minimum trust level (0-3)
  "can_be_bribed": true,      // Can money loosen their tongue?
  "bribe_amount": 20          // GP required if bribable
}
```

**Guidelines:**
- Derive secrets from the NPC's `secrets` field if present
- Create 1-3 secrets per NPC
- `hint` should be something observable without the secret being revealed
- Set `can_be_bribed` based on NPC's alignment and personality
- Chaotic/mercenary NPCs are more bribable; Lawful/principled less so
- `bribe_amount` should reflect the secret's value and NPC's wealth level

---

### 4. `relationships` (array of relationship objects)

Connections to other NPCs, enabling faction play and information networks.

**Relationship Object Schema:**
```json
{
  "npc_id": "other_npc_snake_case_id",
  "relationship_type": "employer|employee|ally|enemy|kin|former_master|captor|prisoner|rival|friend|lover",
  "description": "Brief description of the relationship and its current state.",
  "hex_id": "0103",  // Where the other NPC is located, if known. null if external reference.
  "notes": "Optional notes, often book page references for external NPCs"
}
```

**Common Relationship Types:**
- `employer` / `employee`: Work relationships
- `ally` / `enemy`: Factional alignment
- `kin` / `distant_kin`: Family connections
- `former_master` / `former_servant`: Past service relationships
- `captor` / `prisoner`: Imprisonment
- `rival`: Competition or antagonism
- `friend` / `lover`: Personal bonds

---

### 5. `binding` (object, for imprisoned/captive NPCs only)

Structured captivity information for NPCs who are bound, imprisoned, or restrained.

**Binding Object Schema:**
```json
{
  "bound_by": "npc_id_of_captor",
  "bound_with": "silver_chain|rope|magical_bonds|iron_shackles",
  "binding_value_gp": 100,  // Value of physical restraints if applicable
  "gagged": true,
  "gag_description": "cloth gag",
  "release_conditions": [
    "defeat_captor",
    "steal_prisoner",
    "specific_creative_action"
  ],
  "on_ungag": "Description of what happens when ungagged, if gagged"
}
```

---

### 6. `faction` and `loyalty` (strings, for faction-aligned NPCs)

For NPCs who serve another NPC or faction.

**Faction:** The `npc_id` or faction name they serve
**Loyalty Types:**
- `loyal`: Ideologically committed, very hard to turn
- `coerced`: Serving under duress, can be freed/turned
- `bought`: Payment-based, can be outbid
- `bound`: Magically or contractually bound

```json
"faction": "sidney_tew",
"loyalty": "bought"
```

---

## Example: Full NPC Enrichment

**Input NPC:**
```json
{
  "npc_id": "crocus",
  "name": "Crocus",
  "description": "A 10' tall ogre-like fairy. She has no skin, just exposed muscle and patches of scab-like scales. Her lipless mouth is set in a permanent smile. Her fingers are tipped by teeth instead of nails. Until recently, avoiding her betrayed mistress Thorn-Rosy was her highest priority. Having finally grown too bored of hiding in a cave and eating wildlife, she now deliberately allows travellers to sight the goose, attracting greedy mortals to feed upon.",
  "kindred": "Fairy",
  "alignment": "Chaotic",
  "demeanor": ["Crude and brutish"],
  "desires": ["To feed and be amused", "to avoid the wrath of Thorn-Rosy", "and to be surrounded by shiny things"]
}
```

**Output Enrichment:**
```json
{
  "vulnerabilities": ["cold_iron", "shiny_objects", "mention_of_thorn_rosy"],
  "known_topics": [
    {
      "topic_id": "shiny_distraction",
      "content": "Crocus's eyes fix on any shiny object presented to her. She reaches for it with grasping, tooth-tipped fingers, momentarily forgetting her hunger.",
      "keywords": ["shiny", "gold", "treasure", "jewel", "sparkle", "glitter"],
      "required_disposition": -5,
      "category": "interaction",
      "shared": false,
      "priority": 8
    }
  ],
  "secret_info": [
    {
      "secret_id": "thorn_rosy_fear",
      "content": "Crocus stole the Golden Goose from her mistress, the Hag Thorn-Rosy. She lives in constant fear of discovery and punishment. Mentioning Thorn-Rosy's name causes her to flinch and glance nervously at shadows.",
      "hint": "When fairy matters are discussed, her permanent smile seems to tighten, and she glances toward the cave entrance.",
      "keywords": ["thorn", "rosy", "mistress", "fairy", "stole", "theft", "fear", "hiding"],
      "required_disposition": 0,
      "required_trust": 0,
      "can_be_bribed": false,
      "bribe_amount": 0
    },
    {
      "secret_id": "deliberate_lure",
      "content": "Crocus deliberately allows travelers to sight the goose, using it as bait to attract greedy mortals she can feed upon. The whole 'hunt' is her trap.",
      "hint": "The ease with which the golden egg was found seems almost... too convenient.",
      "keywords": ["trap", "bait", "lure", "deliberate", "purpose", "why", "feed"],
      "required_disposition": 1,
      "required_trust": 1,
      "can_be_bribed": false,
      "bribe_amount": 0
    }
  ],
  "relationships": [
    {
      "npc_id": "thorn_rosy",
      "relationship_type": "former_master",
      "description": "Fled from Thorn-Rosy after stealing the Golden Goose. Lives in terror of her wrath.",
      "hex_id": null,
      "notes": "Thorn-Rosy is referenced on p32 of the Campaign Book"
    },
    {
      "npc_id": "the_golden_goose",
      "relationship_type": "captor",
      "description": "Keeps the goose chained and gagged as both treasure and bait for prey.",
      "hex_id": "0103",
      "notes": null
    }
  ]
}
```

---

## Processing Instructions

When given NPC data to enrich:

1. **Analyze the source material**: Read description, demeanor, desires, secrets, and any contextual information carefully.

2. **Identify vulnerabilities**: What could be exploited? What do they fear, want, or respond to?

3. **Create conversation topics**: What would this NPC talk about? What do they know? Write as actual dialogue or behavioral description.

4. **Extract secrets**: What do they know that they wouldn't freely share? What would it take to learn it?

5. **Map relationships**: Who do they know? Who do they serve, fear, love, or hate?

6. **Handle special cases**:
   - Imprisoned NPCs: Add `binding` structure
   - Faction members: Add `faction` and `loyalty`
   - Non-speaking creatures: Use `interaction` category for behavioral topics
   - Group NPCs (e.g., "4 ruffians"): Create collective topics and secrets

7. **Maintain consistency**: Use existing `npc_id` values for relationships. Reference page numbers for external NPCs when available.

8. **Output format**: Return only the enrichment fields as valid JSON that can be merged into the existing NPC object.

---

## Special Considerations

### For Monsters/Beasts
- May have no `known_topics` if non-intelligent
- `vulnerabilities` focus on combat/tactical weaknesses
- `relationships` may include territorial or predatory connections

### For Group NPCs (e.g., "4 ruffians", "minor nobles")
- Topics represent what any member might say
- Secrets apply to the group's collective knowledge
- Consider group dynamics (leader, dissent, shared loyalty)

### For Captive/Bound NPCs
- Always include `binding` structure
- Consider `on_ungag` behavior if gagged
- `known_topics` may require `requires_ungagged: true`

### For Fairies
- Always include `cold_iron` vulnerability
- Consider fairy nature (oaths, bargains, weaknesses)
- Reference the fairy's court or master if applicable
