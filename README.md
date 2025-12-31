# Dolmenwood Virtual DM

A Python-based companion tool for solo TTRPG play in Dolmenwood. Designed for use with Mythic Game Master Emulator 2e.

## Overview

The Virtual DM acts as a procedural referee and world simulator, enforcing OSR procedures with mechanical precision. An optional LLM layer adds atmospheric description.

**Design Principle**: Mechanics are authoritative in Python; narration is advisory via LLM.

## Requirements

- Python 3.11+
- Poetry (for dependency management)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd dolmenwood_virtual_dm

# Install dependencies
poetry install

# Install with optional features
poetry install --extras "all"        # All optional dependencies
poetry install --extras "llm"        # LLM providers (Anthropic + OpenAI)
poetry install --extras "vector"     # Vector DB for lore search
poetry install --extras "pdf"        # PDF parsing for content import
```

## Running

```bash
# Run the CLI
poetry run dolmenwood-dm

# Or with Python directly
poetry run python -m src.main

# With content loading
poetry run dolmenwood-dm --load-content

# With LLM narration (requires API key)
poetry run dolmenwood-dm --llm-provider anthropic
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_combat.py

# Run with coverage (if pytest-cov installed)
poetry run pytest --cov=src
```

## Project Structure

- `src/` - Main source code (116 modules)
  - `main.py` - VirtualDM facade and CLI entry point
  - `game_state/` - State machine, GlobalController, session management
  - `hex_crawl/` - Wilderness travel procedures
  - `dungeon/` - Dungeon exploration
  - `combat/` - Combat resolution
  - `encounter/` - Encounter sequence handling
  - `settlement/` - Settlement exploration
  - `downtime/` - Rest and downtime activities
  - `tables/` - Dolmenwood random tables
  - `narrative/` - Spell/hazard resolvers
  - `content_loader/` - Content import pipeline
  - `ai/` - LLM integration (advisory narration)
  - `conversation/` - Chat-first interface adapter
- `tests/` - Test suite (46 modules, 1972+ tests)
- `data/content/` - Game content (hexes, monsters, spells, items)
- `docs/` - Documentation

## Key Components

| Component | Purpose |
|-----------|---------|
| `VirtualDM` | Main facade coordinating all subsystems |
| `GlobalController` | Authoritative game state management |
| `StateMachine` | Game state transitions (wilderness, dungeon, combat, etc.) |
| `HexCrawlEngine` | Wilderness travel with encounter/lost checks |
| `CombatEngine` | OSE/BX-style combat resolution |
| `DMAgent` | Optional LLM-powered narrative descriptions |

## Content

Base game content should be placed in `data/content/`:
- `hexes/` - Hex location JSON files
- `monsters/` - Monster stat blocks
- `spells/` - Spell definitions
- `items/` - Item catalog

Use `--load-content` flag to load content at startup.

## License

See LICENSE file for details.
