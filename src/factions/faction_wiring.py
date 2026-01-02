"""
Faction system wiring for VirtualDM integration.

This module provides helper functions to:
- Initialize and wire the FactionEngine to VirtualDM
- Handle save/load of faction state via session custom_data
- Generate faction status summaries for the offline surface

Usage in VirtualDM:
    from src.factions.faction_wiring import (
        init_faction_engine,
        save_faction_state,
        load_faction_state,
        get_factions_summary,
    )

    # In __init__:
    self.factions = init_faction_engine(self, content_dir)

    # In save_game:
    save_faction_state(self.factions, session.custom_data)

    # In load_game:
    load_faction_state(self.factions, session.custom_data)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.main import VirtualDM

from src.factions.faction_engine import FactionEngine
from src.factions.faction_loader import FactionLoader
from src.factions.faction_relations import FactionRelationsLoader
from src.factions.faction_adventurers import FactionAdventurerProfilesLoader
from src.factions.faction_models import PartyFactionState
from src.factions.faction_party import FactionPartyManager

logger = logging.getLogger(__name__)


def init_faction_engine(
    dm: "VirtualDM",
    content_dir: Path,
    *,
    register_time_callback: bool = True,
) -> Optional[FactionEngine]:
    """
    Initialize and wire the faction engine to VirtualDM.

    Args:
        dm: The VirtualDM instance
        content_dir: Path to the content directory
        register_time_callback: Whether to register the day advancement callback

    Returns:
        FactionEngine instance or None if initialization failed
    """
    factions_dir = content_dir / "factions"

    if not factions_dir.exists():
        logger.info("Factions directory not found, skipping faction engine initialization")
        return None

    try:
        # Load faction definitions and rules
        loader = FactionLoader(content_dir)
        load_result = loader.load_all()

        if not loader.definitions:
            logger.warning("No faction definitions found")
            return None

        if load_result.errors:
            for err in load_result.errors[:3]:
                logger.warning(f"Faction load error: {err}")

        # Load faction relations
        relations_loader = FactionRelationsLoader(content_dir)
        relations = relations_loader.load(loader.definitions)

        if relations_loader.load_result and relations_loader.load_result.errors:
            for err in relations_loader.load_result.errors[:3]:
                logger.warning(f"Relations load error: {err}")

        # Load adventurer profiles (optional)
        profiles_loader = FactionAdventurerProfilesLoader(content_dir)
        profiles = profiles_loader.load()
        if profiles_loader.load_result and profiles_loader.load_result.errors:
            for err in profiles_loader.load_result.errors[:3]:
                logger.warning(f"Profiles load error: {err}")

        # Create the engine
        engine = FactionEngine(
            rules=loader.rules,
            definitions=loader.definitions,
            relations=relations,
        )

        # Store profiles on engine for party manager access
        engine._adventurer_profiles = profiles

        # Initialize party faction state
        engine.set_party_state(PartyFactionState())

        # Register time callback
        if register_time_callback:
            _register_time_callback(dm, engine)

        logger.info(
            f"Faction engine initialized with {len(loader.definitions)} factions, "
            f"{relations.relations.__len__() if relations else 0} relations"
        )

        return engine

    except Exception as e:
        logger.error(f"Failed to initialize faction engine: {e}", exc_info=True)
        return None


def _register_time_callback(dm: "VirtualDM", engine: FactionEngine) -> None:
    """
    Register the faction engine's day callback with TimeTracker.

    Args:
        dm: The VirtualDM instance
        engine: The FactionEngine instance
    """
    try:
        time_tracker = dm.controller.time_tracker

        def on_days_advanced(days: int) -> None:
            """Handle day advancement - may trigger faction cycle."""
            # Update current date in engine
            game_date = time_tracker.game_date
            engine.set_current_date(f"{game_date.year}-{game_date.month}-{game_date.day}")

            # Advance and check for cycle
            result = engine.on_days_advanced(days)
            if result:
                logger.info(
                    f"Faction cycle {result.cycle_number} completed: "
                    f"{len(result.faction_results)} factions processed"
                )

        time_tracker.register_day_callback(on_days_advanced)
        logger.debug("Faction engine day callback registered with TimeTracker")

    except Exception as e:
        logger.warning(f"Failed to register faction time callback: {e}")


def save_faction_state(
    engine: Optional[FactionEngine],
    custom_data: dict[str, Any],
) -> None:
    """
    Save faction engine state to session custom_data.

    Args:
        engine: The FactionEngine instance (or None)
        custom_data: The session's custom_data dict to update
    """
    if not engine:
        return

    try:
        custom_data["faction_state"] = engine.to_dict()
        logger.debug("Faction state saved to custom_data")
    except Exception as e:
        logger.error(f"Failed to save faction state: {e}")


def load_faction_state(
    engine: Optional[FactionEngine],
    custom_data: dict[str, Any],
) -> bool:
    """
    Load faction engine state from session custom_data.

    Args:
        engine: The FactionEngine instance (or None)
        custom_data: The session's custom_data dict

    Returns:
        True if state was loaded successfully
    """
    if not engine:
        return False

    if "faction_state" not in custom_data:
        return False

    try:
        engine.from_dict(custom_data["faction_state"])
        logger.debug("Faction state loaded from custom_data")
        return True
    except Exception as e:
        logger.error(f"Failed to load faction state: {e}")
        return False


def get_factions_summary(engine: Optional[FactionEngine]) -> str:
    """
    Get a formatted summary of all factions for display.

    This is the offline surface - shows faction status without LLM.

    Args:
        engine: The FactionEngine instance (or None)

    Returns:
        Formatted string with faction summaries
    """
    if not engine:
        return "Faction system not initialized."

    lines = []
    lines.append("=== FACTION STATUS ===")
    lines.append(f"Cycles completed: {engine.cycles_completed}")
    lines.append(f"Days until next cycle: {engine.rules.turn_cadence_days - engine.days_accumulated}")
    lines.append("")

    summaries = engine.get_all_factions_summary()
    if not summaries:
        lines.append("No active factions.")
        return "\n".join(lines)

    for summary in summaries:
        lines.append(f"--- {summary['name']} (Level {summary['level']}) ---")
        lines.append(f"  Territory Points: {summary['territory_points']}")

        # Territory breakdown
        territory = summary.get("territory", {})
        parts = []
        if territory.get("hexes"):
            parts.append(f"{territory['hexes']} hex(es)")
        if territory.get("settlements"):
            parts.append(f"{territory['settlements']} settlement(s)")
        if territory.get("strongholds"):
            parts.append(f"{territory['strongholds']} stronghold(s)")
        if territory.get("domains"):
            parts.append(f"{territory['domains']} domain(s)")
        if parts:
            lines.append(f"  Holdings: {', '.join(parts)}")

        # Active actions
        actions = summary.get("actions", [])
        if actions:
            lines.append("  Active Actions:")
            for action in actions:
                progress_bar = _progress_bar(action["progress"], action["segments"])
                status = " [COMPLETE]" if action["complete"] else ""
                lines.append(f"    - {action['action_id']}: {progress_bar}{status}")

        # Recent news
        news = summary.get("recent_news", [])
        if news:
            lines.append("  Recent News:")
            for item in news[-3:]:
                lines.append(f"    * {item}")

        lines.append("")

    return "\n".join(lines)


def get_party_faction_summary(engine: Optional[FactionEngine]) -> str:
    """
    Get a formatted summary of party faction relationships.

    Args:
        engine: The FactionEngine instance (or None)

    Returns:
        Formatted string with party faction state
    """
    if not engine or not engine.party_state:
        return "No party faction relationships."

    party_state = engine.party_state
    lines = []
    lines.append("=== PARTY FACTION STANDING ===")

    # Standing
    if party_state.standing_by_id:
        lines.append("Standing:")
        for faction_id, standing in sorted(party_state.standing_by_id.items()):
            sign = "+" if standing > 0 else ""
            lines.append(f"  {faction_id}: {sign}{standing}")
    else:
        lines.append("No faction standings recorded.")

    # Affiliations
    if party_state.affiliations:
        lines.append("\nAffiliations:")
        for aff in party_state.affiliations:
            lines.append(f"  - {aff.faction_or_group}: {aff.kind} (rank {aff.rank})")

    # Active jobs
    if party_state.active_jobs:
        lines.append("\nActive Jobs:")
        for job_id, job in party_state.active_jobs.items():
            lines.append(f"  - {job.title} (from {job.faction_id}): {job.status}")

    return "\n".join(lines)


def get_party_manager(engine: Optional[FactionEngine]) -> Optional[FactionPartyManager]:
    """
    Get a FactionPartyManager for the engine.

    Args:
        engine: The FactionEngine instance (or None)

    Returns:
        FactionPartyManager or None if engine not available
    """
    if not engine:
        return None

    profiles = getattr(engine, "_adventurer_profiles", None)
    return FactionPartyManager(engine, profiles=profiles)


def _progress_bar(progress: int, segments: int, width: int = 10) -> str:
    """Create a simple ASCII progress bar."""
    if segments <= 0:
        return "[??????????]"

    filled = int((progress / segments) * width)
    filled = min(width, filled)
    empty = width - filled

    return f"[{'#' * filled}{'.' * empty}] {progress}/{segments}"
