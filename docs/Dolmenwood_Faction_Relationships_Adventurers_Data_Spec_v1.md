# Faction Relationships + Adventurer Profiles — Data Spec (v1)

This is a *content-layer* spec for two new JSON files:

- `faction_relationships.json`
- `faction_adventurer_profiles.json`

Companion examples (generated from `output.pdf`) are included in the workspace:
- `faction_relationships.example.json`
- `faction_adventurer_profiles.example.json`

---

## 1) `faction_relationships.json`

### 1.1 Goals
- Represent major faction attitudes toward each other.
- Support relationships between *groups* (e.g., “human_nobility”) and individual factions.

### 1.2 Shape

```json
{
  "schema_version": 1,
  "score_range": [-100, 100],
  "groups": {
    "human_nobility": {"match_tags_any": ["human_nobility"]},
    "longhorn_nobility": {"match_tags_any": ["longhorn_nobility", "longhorn", "high_wold"]}
  },
  "pairs": [
    {"a":"pluritine_church","b":"drune","score":-90,"sentiment":"hate","notes":"..."},
    {"a":"witches","b":"human_nobility","score":30,"sentiment":"loosely_allied","notes":"..."}
  ]
}
```

### 1.3 Resolution rules
When asking for the relationship between A and B:

1) Exact faction_id pair exists? Use it.
2) Else, expand A into `[A] + matched group_ids` (by tags), same for B.
3) Search for any pair among expanded sets.
4) If multiple matches exist, prefer:
   - exact faction_id over group,
   - then highest absolute score.
5) If still nothing, score=0 (neutral).

### 1.4 Sentiment-to-score suggestion table
(Use as authoring guidance; the engine uses `score` for mechanics.)

- allied: +60
- loosely_allied: +30
- pact: +20
- tolerates: +10
- neutral/ignores/dismisses_as_legend: 0
- distrusts/disdains: -20..-30
- fears: -40..-60
- hates: -70..-90
- seeks_eradication: -90..-100

---

## 2) `faction_adventurer_profiles.json`

### 2.1 Goals
- Encode what factions *mechanically* offer/permit for adventurers:
  - affiliation/fealty (who can join)
  - rewards
  - quest/job templates
  - trade hooks
  - risk notes (e.g. audience danger)

### 2.2 Shape

```json
{
  "schema_version": 1,
  "profiles": {
    "pluritine_church": {
      "pc_join_policy": {
        "allow_affiliation": true,
        "fully_initiable": true,
        "allowed_alignments": ["Lawful", "Neutral"],
        "join_summary": "..."
      },
      "rewards": ["gold", "holy magic"],
      "quest_templates": [
        {"id":"church_procure_relics", "title":"Procure relics", "tags":["recovery"], "summary":"...", "default_effects":[...]}
      ]
    }
  }
}
```

### 2.3 “NPC-only initiation” flag
Some factions (e.g., Drune and Witches) are treated as NPC-only for full initiation.
Encode that as:

```json
"fully_initiable": false
```

The engine should:
- allow a “working relationship” (jobs/trade) without full initiation
- prevent “join as PC class/faction member” mechanics unless later supplements add rules

### 2.4 Effects list
Quest templates should include a small list of deterministic effect descriptors, e.g.:

```json
{"type":"party_reputation","faction":"witches","delta":1}
```

The interaction resolver applies these effects; narration may summarize them.

---

## 3) Authoring guidance
- Prefer stable IDs:
  - Use `faction_id` from each faction JSON where available.
  - For umbrella concepts in the PDF (“Human Nobility”, “Longhorn Nobility”), use group ids and tag matchers.
- Keep text fields short; narration can elaborate.

