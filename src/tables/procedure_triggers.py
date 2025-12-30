"""
Procedure trigger system - DEPRECATED.

This module previously contained an event-driven ProcedureManager system
designed to automatically fire game procedures (encounter checks, resource
depletion, etc.) based on game events.

DESIGN DECISION (P1.2):
The ProcedureManager was never integrated with the game engines. Instead,
HexCrawlEngine and DungeonEngine implement procedures internally where they
have direct access to engine state (travel points, turns, alert levels, etc.).

The engine-internal approach is simpler and more maintainable because:
1. Procedures are tightly coupled to engine state
2. No need to pass complex context dicts through an event system
3. Engines maintain direct control over procedure timing

If a unified procedure system is needed in the future, it should be designed
to work with the existing engine architecture rather than as a parallel system.

For procedure implementations, see:
- src/hex_crawl/hex_crawl_engine.py (wilderness procedures)
- src/dungeon/dungeon_engine.py (dungeon procedures)
- src/downtime/downtime_engine.py (rest/camping procedures)
"""

# This module is intentionally empty.
# Keeping it to preserve import compatibility if needed.
