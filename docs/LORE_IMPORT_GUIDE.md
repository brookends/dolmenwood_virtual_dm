# Lore Import Guide

This guide explains how to import lore information (factions, history, NPCs, hexes, monsters, etc.) into the Dolmenwood Virtual DM databases for use by the DM Agent's lore enrichment feature.

## Overview

The system uses two complementary storage systems:

1. **Structured Storage (SQLite)**: Stores content as structured data for game mechanics
2. **Vector Database (ChromaDB)**: Stores embeddings for semantic search/retrieval

Content flows through the **ContentPipeline** which handles validation, storage, and indexing automatically.

## Prerequisites

### Optional Dependencies

For full vector database functionality, install the optional dependencies:

```bash
# Install LLM provider dependencies (includes vector DB support)
pip install -e ".[llm]"

# Or install just the vector DB dependencies
pip install chromadb sentence-transformers
```

For PDF parsing capabilities:

```bash
pip install PyMuPDF  # or pdfplumber
```

The system works without these dependencies - it gracefully falls back to simpler search when unavailable.

## Import Methods

### Method 1: JSON Files (Recommended)

The preferred method for importing structured lore. Create JSON files following the expected schemas.

#### Hex Data

Create a JSON file with hex information:

```json
{
  "hexes": [
    {
      "hex_id": "0709",
      "name": "The Witch's Knoll",
      "terrain": "forest",
      "description": "A dark, tangled forest where ancient oaks grow...",
      "features": [
        {
          "name": "Standing Stone",
          "description": "A moss-covered menhir humming with eldritch energy"
        }
      ],
      "fairy_influence": "Strong - glamours common",
      "drune_presence": true
    }
  ]
}
```

Import using the TextParser:

```python
from src.content_loader.pdf_parser import TextParser
from pathlib import Path

parser = TextParser()
hexes = parser.parse_hex_file(Path("data/hexes.json"))
```

#### NPC Data

```json
{
  "npcs": [
    {
      "npc_id": "lady_harrowmoor",
      "name": "Lady Harrowmoor",
      "title": "Baroness of Harrowmoor",
      "location": "Castle Harrowmoor",
      "faction": "High Wold Nobility",
      "personality": "Cold and calculating, speaks with measured precision",
      "goals": [
        "Expand territorial influence",
        "Uncover the fate of her missing heir"
      ],
      "secrets": [
        "Is actually a changeling who replaced the real baroness decades ago"
      ],
      "dialogue_hooks": [
        "Speaks often of 'the old ways' and the 'time before the wood grew dark'"
      ],
      "relationships": {
        "Lord Blackwood": "Bitter rival",
        "The Drune": "Uneasy truce"
      }
    }
  ]
}
```

#### Faction/Lore Data

For general lore (factions, history, religion, etc.), use the direct indexing API:

```python
from src.vector_db.rules_retriever import RulesRetriever, ContentCategory

retriever = RulesRetriever(persist_directory=Path("data/vector_db"))

# Index faction lore
retriever.index_lore(
    lore_id="drune_history",
    lore_text="""
    The Drune are an ancient order of sorcerer-priests who have ruled
    Dolmenwood through fear and dark magic for centuries. They trace their
    lineage to the Cold Prince, a powerful fey lord who was banished to
    the mortal realm. Their stone circles dot the forest, serving as both
    temples and sources of arcane power.
    """,
    topic="faction_drune"
)

# Index historical lore
retriever.index_lore(
    lore_id="war_of_winter",
    lore_text="""
    The War of Winter (Year 923-928) pitted the mortal lords of Dolmenwood
    against the Court of Winter. The conflict ended with the Pact of Frost,
    which established the current boundary between the Otherworld and the
    mortal realm.
    """,
    topic="history"
)
```

### Method 2: Using ContentPipeline (Unified Interface)

The ContentPipeline provides a unified interface with automatic validation and indexing:

```python
from src.content_loader.content_pipeline import ContentPipeline, ContentType
from src.data_models import SourceReference, ContentSource, SourceType
from pathlib import Path
from datetime import datetime

# Initialize pipeline (creates both SQLite and ChromaDB storage)
pipeline = ContentPipeline(
    db_path=Path("data/content.db"),
    vector_path=Path("data/vector_db"),
    auto_index=True  # Automatically index for search
)

# Register a content source
source = ContentSource(
    source_id="campaign_book_v1",
    source_type=SourceType.CORE_RULEBOOK,
    book_name="Dolmenwood Campaign Book",
    book_code="DCB",
    version="1.0",
    imported_at=datetime.now(),
)
pipeline.register_source(source)

# Create source reference for individual content
source_ref = SourceReference(
    source_id="campaign_book_v1",
    book_code="DCB",
    page=42
)

# Add lore content
result = pipeline.add_rule(
    rule_id="fairy_magic_rules",
    title="Fairy Magic and Glamours",
    text="""
    Fairy magic operates on different principles than mortal sorcery.
    Glamours can create illusions that fool all five senses. Cold iron
    disrupts fairy magic, causing 1d6 extra damage to fey creatures.
    """,
    source=source_ref,
    category="magic"
)

print(f"Import successful: {result.success}, indexed: {result.indexed}")
```

### Method 3: PDF Import

For importing directly from Dolmenwood rulebooks:

```python
from src.content_loader.pdf_parser import PDFParser, BookType
from pathlib import Path

parser = PDFParser()

# Parse the Campaign Book
result = parser.parse_pdf(
    file_path=Path("books/Dolmenwood_Campaign_Book.pdf"),
    book_type=BookType.CAMPAIGN_BOOK,
    version="1.0"
)

if result.success:
    print(f"Extracted {len(result.hexes)} hexes")
    print(f"Extracted {len(result.npcs)} NPCs")
    print(f"Extracted {len(result.sections)} sections")
else:
    print(f"Parse failed: {result.errors}")
```

Note: PDF parsing requires PyMuPDF or pdfplumber installed.

### Method 4: Direct Vector DB Indexing

For maximum control, use the RulesRetriever directly:

```python
from src.vector_db.rules_retriever import RulesRetriever, ContentCategory
from pathlib import Path

# Initialize with persistence
retriever = RulesRetriever(
    persist_directory=Path("data/vector_db"),
    collection_name="dolmenwood_content",
    embedding_model="all-MiniLM-L6-v2"  # Sentence transformer model
)

# Index different content types
retriever.index_document(
    doc_id="faction_drune",
    category=ContentCategory.FACTION,
    text="The Drune are ancient sorcerer-priests who rule through dark magic...",
    metadata={
        "faction_name": "The Drune",
        "alignment": "Lawful Evil",
        "territory": "Stone circles throughout Dolmenwood"
    }
)

retriever.index_document(
    doc_id="history_cold_prince",
    category=ContentCategory.LORE,
    text="The Cold Prince was banished from the Otherworld in the Age of Frost...",
    metadata={
        "topic": "history",
        "era": "Age of Frost"
    }
)
```

## Content Categories

The system supports these content categories for lore:

| Category | Use For |
|----------|---------|
| `RULES` | Game mechanics, procedures, combat rules |
| `LORE` | History, legends, general world information |
| `HEX` | Hex locations and descriptions |
| `NPC` | Non-player character profiles |
| `MONSTER` | Creature statistics and descriptions |
| `FACTION` | Organizations, cults, noble houses |
| `SETTLEMENT` | Towns, villages, cities |
| `DUNGEON` | Dungeon descriptions and features |
| `SPELL` | Spell descriptions and effects |
| `ITEM` | Magic items and equipment |
| `ENCOUNTER` | Encounter tables and scenarios |

## Searching Lore

Once indexed, the DM Agent can search lore during narration:

```python
from src.ai.dm_agent import DMAgent, DMAgentConfig, LLMProvider
from src.ai.lore_search import create_lore_search, LoreCategory

# Create lore search with vector DB
lore_search = create_lore_search(use_vector_db=True)

# Initialize agent with lore search
config = DMAgentConfig(llm_provider=LLMProvider.ANTHROPIC)
agent = DMAgent(config, lore_search=lore_search)

# Retrieve lore for context enrichment
results = agent.retrieve_lore(
    query="What do the Drune believe about fairy magic?",
    category=LoreCategory.FACTION,
    max_results=3
)

for result in results:
    print(f"[{result.source}] {result.content[:100]}...")
```

## Bulk Import Script Example

Here's a complete script for bulk importing lore:

```python
#!/usr/bin/env python3
"""Bulk import lore into Dolmenwood Virtual DM."""

from pathlib import Path
from datetime import datetime
import json

from src.content_loader.content_pipeline import ContentPipeline
from src.data_models import ContentSource, SourceReference, SourceType
from src.vector_db.rules_retriever import RulesRetriever, ContentCategory


def import_lore_files(lore_dir: Path, pipeline: ContentPipeline):
    """Import all lore JSON files from a directory."""
    source = ContentSource(
        source_id="custom_lore",
        source_type=SourceType.HOMEBREW,
        book_name="Custom Campaign Lore",
        book_code="CCL",
        version="1.0",
        imported_at=datetime.now(),
    )
    pipeline.register_source(source)

    source_ref = SourceReference(source_id="custom_lore", book_code="CCL")

    # Import faction files
    for faction_file in lore_dir.glob("factions/*.json"):
        with open(faction_file) as f:
            data = json.load(f)

        for faction in data.get("factions", []):
            pipeline.add_content(
                content_id=faction["faction_id"],
                content_type=ContentType.FACTION,
                data=faction,
                source=source_ref,
                tags=["faction", faction.get("type", "unknown")]
            )
            print(f"Imported faction: {faction['name']}")

    # Import history files
    for history_file in lore_dir.glob("history/*.json"):
        with open(history_file) as f:
            data = json.load(f)

        for entry in data.get("history", []):
            pipeline.add_rule(
                rule_id=entry["history_id"],
                title=entry["title"],
                text=entry["text"],
                source=source_ref,
                category="history"
            )
            print(f"Imported history: {entry['title']}")


def main():
    pipeline = ContentPipeline(
        db_path=Path("data/content.db"),
        vector_path=Path("data/vector_db"),
    )

    import_lore_files(Path("data/lore"), pipeline)

    stats = pipeline.get_statistics()
    print(f"\nImport complete!")
    print(f"Structured storage: {stats['structured_storage']}")
    print(f"Vector storage: {stats['vector_storage']}")


if __name__ == "__main__":
    main()
```

## JSON Schema Examples

### Faction Schema

```json
{
  "factions": [
    {
      "faction_id": "drune",
      "name": "The Drune",
      "type": "religious_order",
      "description": "Ancient sorcerer-priests who rule through dark magic",
      "headquarters": "Various stone circles",
      "territory": ["Deep forest hexes", "Stone circle locations"],
      "goals": [
        "Maintain control over Dolmenwood",
        "Prevent fairy incursion"
      ],
      "allies": ["Certain noble houses"],
      "enemies": ["The Fairy Courts", "The Church of St. Oswulf"],
      "resources": ["Dark magic", "Fear", "Ancient knowledge"],
      "notable_members": [
        {
          "name": "The Nagath",
          "role": "High Priest",
          "description": "The leader of all Drune"
        }
      ]
    }
  ]
}
```

### History Schema

```json
{
  "history": [
    {
      "history_id": "founding_of_lankshorn",
      "title": "The Founding of Lankshorn",
      "era": "Age of Settlement",
      "year": "Year 412",
      "text": "Lankshorn was founded by settlers from the western kingdoms who sought refuge from the Wars of Consolidation...",
      "key_figures": ["Lord Lank", "The First Bishop"],
      "locations_involved": ["Hex 0709", "The River Lank"],
      "consequences": ["Established human presence in eastern Dolmenwood"]
    }
  ]
}
```

## Verification

After importing, verify the content is searchable:

```python
from src.vector_db.rules_retriever import RulesRetriever

retriever = RulesRetriever(persist_directory=Path("data/vector_db"))

# Check statistics
stats = retriever.get_statistics()
print(f"Total indexed documents: {stats['total_documents']}")

# Test a search
results = retriever.get_faction_info("Drune")
for result in results:
    print(f"Found: {result.content_id} (score: {result.score:.2f})")
    print(f"  {result.text[:100]}...")
```

## Troubleshooting

### "chromadb or sentence-transformers not installed"

Install the optional dependencies:
```bash
pip install chromadb sentence-transformers
```

### "No PDF library available"

Install PyMuPDF:
```bash
pip install PyMuPDF
```

### Content not appearing in searches

1. Check that `auto_index=True` in ContentPipeline
2. Verify content was indexed: check `result.indexed` after import
3. Use `pipeline.reindex_all()` to rebuild the search index

### Empty search results

- Lower the `min_relevance` threshold in LoreSearchQuery
- Try broader search terms
- Verify the content category matches your query
