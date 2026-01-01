"""
Settlement Engine for Dolmenwood Virtual DM.

Implements settlement exploration per Dolmenwood rules (p160-161).
Handles settlement exploration, NPC interactions, and social encounters.
Manages services, shopping, rumors, and faction interactions.

Settlement Procedure Per Day (p160):
1. Weather: Referee determines day's weather
2. Decide actions: Players decide on actions (resting, shopping, researching)
3. Random encounters: Daytime encounter check (2-in-6 when active)
4. Description: Referee describes what happens
5. End of day: Update time, ongoing downtime activities
6. Random encounters: Nighttime check if active (1-in-6)

Settlement Sizes (p161):
- Hamlet: 20-49 inhabitants
- Village: 50-999 inhabitants
- Small town: 1,000-3,999 inhabitants
- Large town: 4,000-7,999 inhabitants
- City: 8,000+ inhabitants

Lifestyle Expenses (Optional Rule, p161):
- Wretched: Free, no healing
- Poor: 5sp/day, 15gp/month
- Common: 2gp/day, 60gp/month
- Fancy: 10gp/day, 300gp/month

Settlement exploration transitions:
- SETTLEMENT_EXPLORATION -> SOCIAL_INTERACTION (initiate_conversation)
- SETTLEMENT_EXPLORATION -> COMBAT (settlement_combat)
- SETTLEMENT_EXPLORATION -> WILDERNESS_TRAVEL (exit_settlement)
- SETTLEMENT_EXPLORATION -> DOWNTIME (begin_downtime)
- SETTLEMENT_EXPLORATION -> DUNGEON_EXPLORATION (enter_dungeon)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import logging
import re

from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.data_models import (
    DiceRoller,
    NPC,
    ReactionResult,
    interpret_reaction,
    LocationType,
    SourceReference,
    TimeOfDay,
)

# Import v2 content models (JSON-backed settlements)
from src.settlement.settlement_content_models import SettlementData
from src.settlement.settlement_registry import SettlementRegistry
from src.settlement.settlement_encounters import (
    SettlementEncounterTables,
    SettlementEncounterResult,
    tod_to_daynight,
)

# Import RunLog for settlement event logging
try:
    from src.observability.run_log import get_run_log
except ImportError:
    get_run_log = None  # type: ignore


logger = logging.getLogger(__name__)


def _log_settlement_event(event_type: str, details: dict) -> None:
    """Log a settlement event if RunLog is available."""
    if get_run_log is not None:
        try:
            get_run_log().log_custom(f"settlement:{event_type}", details)
        except Exception:
            pass  # Silently ignore logging failures


class SettlementSize(str, Enum):
    """
    Size categories for settlements per Dolmenwood rules (p161).

    Population ranges determine available services and encounter tables.
    """

    HAMLET = "hamlet"  # 20-49 inhabitants
    VILLAGE = "village"  # 50-999 inhabitants
    SMALL_TOWN = "small_town"  # 1,000-3,999 inhabitants
    LARGE_TOWN = "large_town"  # 4,000-7,999 inhabitants
    CITY = "city"  # 8,000+ inhabitants


class LifestyleType(str, Enum):
    """
    Lifestyle expense categories per Dolmenwood rules (p161).

    Optional rule for abstracting daily living expenses.
    Affects healing and costs during settlement stays.
    """

    WRETCHED = "wretched"  # Free, sleeping in alleys/begging - NO HEALING
    POOR = "poor"  # 5sp/day, 15gp/month - poor quality inns
    COMMON = "common"  # 2gp/day, 60gp/month - common quality inns
    FANCY = "fancy"  # 10gp/day, 300gp/month - fancy quality inns


# Lifestyle costs and effects per Dolmenwood rules (p161)
LIFESTYLE_DATA: dict[LifestyleType, dict[str, Any]] = {
    LifestyleType.WRETCHED: {
        "cost_per_day_sp": 0,
        "cost_per_month_gp": 0,
        "allows_healing": False,  # Wretched characters do not heal (p161)
        "description": "Sleeping in back alleys, begging, eating scraps",
    },
    LifestyleType.POOR: {
        "cost_per_day_sp": 5,
        "cost_per_month_gp": 15,
        "allows_healing": True,
        "description": "Poor quality inns or rented rooms in older part of town",
    },
    LifestyleType.COMMON: {
        "cost_per_day_sp": 20,  # 2gp = 20sp
        "cost_per_month_gp": 60,
        "allows_healing": True,
        "description": "Common quality inns or rented cottage in quiet part of town",
    },
    LifestyleType.FANCY: {
        "cost_per_day_sp": 100,  # 10gp = 100sp
        "cost_per_month_gp": 300,
        "allows_healing": True,
        "description": "Fancy quality inns or spacious rented house in nicest part of town",
    },
}


class ServiceType(str, Enum):
    """
    Types of services available in settlements per Dolmenwood rules (p161).

    Settlement services include common shops and specialists.
    """

    INN = "inn"
    TAVERN = "tavern"
    BLACKSMITH = "blacksmith"
    GENERAL_STORE = "general_store"
    TEMPLE = "temple"
    HEALER = "healer"
    SAGE = "sage"
    GUILD = "guild"
    MARKET = "market"
    STABLES = "stables"
    ARMORER = "armorer"
    WEAPONSMITH = "weaponsmith"
    # Dolmenwood-specific services (p161)
    APOTHECARY = "apothecary"  # Herbalist - identify 5gp, buy/sell at 50% (p161)
    MONEY_CHANGER = "money_changer"  # Banking - 3% exchange, storage, loans (p161)
    JEWELER = "jeweler"  # Gems/jewelry - sell at 100%, buy at 80% (p161)
    HIRELING_HALL = "hireling_hall"  # Find specialists/retainers (p160)


class BuildingType(str, Enum):
    """Types of buildings in settlements."""

    RESIDENCE = "residence"
    SHOP = "shop"
    TAVERN = "tavern"
    INN = "inn"
    TEMPLE = "temple"
    MANOR = "manor"
    GUILD_HALL = "guild_hall"
    WAREHOUSE = "warehouse"
    MILL = "mill"
    FORGE = "forge"


class ConversationTopic(str, Enum):
    """Topics for NPC conversations."""

    GREETING = "greeting"
    RUMORS = "rumors"
    LOCAL_INFO = "local_info"
    DIRECTIONS = "directions"
    SERVICES = "services"
    QUEST = "quest"
    TRADE = "trade"
    FACTION = "faction"
    HISTORY = "history"
    GOSSIP = "gossip"


@dataclass
class Building:
    """A building within a settlement."""

    building_id: str
    name: str
    building_type: BuildingType
    services: list[ServiceType] = field(default_factory=list)
    proprietor: Optional[str] = None  # NPC ID
    staff: list[str] = field(default_factory=list)  # NPC IDs
    description: str = ""
    open_hours: tuple[int, int] = (8, 20)  # 8am to 8pm
    prices_modifier: float = 1.0  # Multiplier for standard prices


@dataclass
class Settlement:
    """A settlement in Dolmenwood."""

    settlement_id: str
    name: str
    size: SettlementSize
    hex_id: str
    population: int
    description: str = ""
    ruler: Optional[str] = None  # NPC ID
    faction: Optional[str] = None
    buildings: list[Building] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)  # NPC IDs
    available_services: list[ServiceType] = field(default_factory=list)
    rumors: list[str] = field(default_factory=list)
    special_features: list[str] = field(default_factory=list)
    source: Optional[SourceReference] = None


@dataclass
class ConversationState:
    """State of an active conversation."""

    npc_id: str
    npc_name: str
    topics_discussed: list[ConversationTopic] = field(default_factory=list)
    disposition: int = 0  # -5 to +5
    secrets_revealed: list[str] = field(default_factory=list)
    trades_made: list[dict] = field(default_factory=list)
    turns_elapsed: int = 0


class SettlementEngine:
    """
    Engine for settlement exploration per Dolmenwood rules (p160-161).

    Manages:
    - Settlement exploration with daily procedure (p160)
    - Rest and healing (1 HP/night, 1d3 HP/full day rest)
    - Lifestyle expenses (optional rule, p161)
    - Earning money using class capabilities (3d6sp/day, p160)
    - NPC conversations and social interaction
    - Services: banking, jewelers, apothecaries, etc. (p161)
    - Random encounters (2-in-6 day, 1-in-6 night when active)
    - Rumors and information gathering
    """

    def __init__(self, controller: GlobalController):
        """
        Initialize the settlement engine.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Settlement data (procedural model)
        self._settlements: dict[str, Settlement] = {}
        self._current_settlement: Optional[str] = None

        # JSON-backed settlement registry (v2 content model)
        self._registry: Optional[SettlementRegistry] = None

        # Runtime state for v2 content navigation
        self._active_settlement_id: Optional[str] = None  # ID of settlement we're in (v2)
        self._current_location_number: Optional[int] = None  # Location number we're at
        self._visited_locations: set[int] = set()  # Locations visited in current settlement

        # NPC data
        self._npcs: dict[str, NPC] = {}

        # Active conversation
        self._conversation: Optional[ConversationState] = None

        # Lifestyle tracking per Dolmenwood rules (p161)
        self._current_lifestyle: LifestyleType = LifestyleType.COMMON
        self._days_in_settlement: int = 0

        # Callbacks
        self._dialogue_callback: Optional[Callable] = None
        self._description_callback: Optional[Callable] = None

    def register_dialogue_callback(self, callback: Callable) -> None:
        """Register callback for NPC dialogue generation."""
        self._dialogue_callback = callback

    def register_description_callback(self, callback: Callable) -> None:
        """Register callback for settlement descriptions."""
        self._description_callback = callback

    # =========================================================================
    # REGISTRY INTEGRATION (v2 JSON-backed content)
    # =========================================================================

    def set_registry(self, registry: SettlementRegistry) -> None:
        """
        Set the settlement registry for JSON-backed content.

        Args:
            registry: SettlementRegistry loaded from JSON files
        """
        self._registry = registry
        logger.info(f"Settlement registry set with {len(registry.list_ids())} settlements")

    def get_registry(self) -> Optional[SettlementRegistry]:
        """Get the settlement registry if loaded."""
        return self._registry

    def get_settlement_data(self, settlement_id: str) -> Optional[SettlementData]:
        """
        Get settlement data from registry by ID.

        Args:
            settlement_id: The settlement identifier

        Returns:
            SettlementData if found, None otherwise
        """
        if self._registry:
            return self._registry.get(settlement_id)
        return None

    def get_settlement_by_hex(self, hex_id: str) -> Optional[SettlementData]:
        """
        Find settlement data by hex ID.

        Args:
            hex_id: The hex identifier (e.g., "1604")

        Returns:
            SettlementData if a settlement exists at that hex, None otherwise
        """
        if self._registry:
            return self._registry.find_by_hex(hex_id)
        return None

    def list_settlement_ids(self) -> list[str]:
        """List all settlement IDs in the registry."""
        if self._registry:
            return self._registry.list_ids()
        return []

    # =========================================================================
    # V2 RUNTIME STATE MANAGEMENT
    # =========================================================================

    def get_active_settlement(self) -> Optional[SettlementData]:
        """Get the currently active settlement data (v2)."""
        if self._active_settlement_id and self._registry:
            return self._registry.get(self._active_settlement_id)
        return None

    def get_current_location(self) -> Optional["SettlementLocationData"]:
        """Get the current location within the active settlement."""
        from src.settlement.settlement_content_models import SettlementLocationData

        settlement = self.get_active_settlement()
        if settlement and self._current_location_number is not None:
            loc_map = settlement.location_by_number()
            return loc_map.get(self._current_location_number)
        return None

    def set_active_settlement(self, settlement_id: str) -> bool:
        """
        Set the active settlement for v2 navigation.

        Args:
            settlement_id: Settlement ID from registry

        Returns:
            True if settlement was found and set, False otherwise
        """
        if self._registry and self._registry.get(settlement_id):
            self._active_settlement_id = settlement_id
            self._current_location_number = None
            self._visited_locations = set()
            logger.info(f"Active settlement set to: {settlement_id}")
            return True
        logger.warning(f"Settlement not found in registry: {settlement_id}")
        return False

    def clear_active_settlement(self) -> None:
        """Clear the active settlement state (when leaving)."""
        self._active_settlement_id = None
        self._current_location_number = None
        self._visited_locations = set()

    # =========================================================================
    # PHASE 1: BRIDGE API (handle_player_action + execute_action)
    # =========================================================================

    def handle_player_action(self, text: str, character_id: Optional[str] = None) -> dict[str, Any]:
        """
        Bridge shim for freeform player input in settlement.

        This method provides conservative keyword routing to structured actions.
        It's designed to work with the existing ConversationFacade integration
        while gradually migrating to execute_action().

        Args:
            text: Freeform player input text
            character_id: Optional character performing the action

        Returns:
            Result dict with 'success', 'message', and optional data
        """
        text_lower = text.strip().lower()

        # Try to extract intent and route to structured action

        # "list locations" / "show locations" / "locations" / "where can i go"
        if any(kw in text_lower for kw in ["list location", "show location", "locations", "where can i go", "what's here", "look around"]):
            return self.execute_action("settlement:list_locations", {})

        # "visit <number>" / "go to <number>" / "enter <number>"
        visit_match = re.search(r"(?:visit|go to|enter|check out)\s+(?:location\s+)?(\d+)", text_lower)
        if visit_match:
            loc_num = int(visit_match.group(1))
            return self.execute_action("settlement:visit_location", {"location_number": loc_num})

        # "visit <name>" - try to match by location name
        visit_name_match = re.search(r"(?:visit|go to|enter|check out)\s+(?:the\s+)?(.+)", text_lower)
        if visit_name_match:
            name_query = visit_name_match.group(1).strip()
            settlement = self.get_active_settlement()
            if settlement:
                for loc in settlement.locations:
                    if name_query in loc.name.lower():
                        return self.execute_action("settlement:visit_location", {"location_number": loc.number})

        # "services" / "what services" / "list services"
        if any(kw in text_lower for kw in ["services", "what can i buy", "what's available"]):
            return self.execute_action("settlement:list_services", {})

        # "use <service>" / "buy <service>"
        use_match = re.search(r"(?:use|buy|get|order)\s+(.+)", text_lower)
        if use_match:
            service_query = use_match.group(1).strip()
            return self.execute_action("settlement:use_service", {"service_name": service_query})

        # "npcs" / "who's here" / "list npcs"
        if any(kw in text_lower for kw in ["npcs", "who's here", "who is here", "people", "locals"]):
            return self.execute_action("settlement:list_npcs", {})

        # "talk to <name>" / "speak with <name>"
        talk_match = re.search(r"(?:talk to|speak (?:to|with)|chat with)\s+(.+)", text_lower)
        if talk_match:
            npc_query = talk_match.group(1).strip()
            return self.execute_action("settlement:talk", {"npc_name": npc_query})

        # "directions" / "roads" / "how do i get to"
        if any(kw in text_lower for kw in ["directions", "roads", "way to", "path to", "route"]):
            return self.execute_action("settlement:ask_directions", {})

        # "rumors" / "gossip" / "what's the word"
        if any(kw in text_lower for kw in ["rumor", "gossip", "word on the street", "heard anything"]):
            return self.execute_action("settlement:ask_rumor", {})

        # "leave" / "exit" / "depart"
        if any(kw in text_lower for kw in ["leave", "exit", "depart", "go outside", "wilderness"]):
            return self.execute_action("settlement:leave", {})

        # Fallback - unrecognized input
        return {
            "success": False,
            "message": f"I don't understand '{text}'. Try: list locations, visit <number>, services, npcs, talk to <name>, or leave.",
            "action": None,
        }

    def execute_action(self, action_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a structured settlement action.

        This is the main router for settlement actions. Each action returns
        a result dict suitable for UI consumption.

        Args:
            action_id: The action identifier (e.g., "settlement:list_locations")
            params: Action parameters

        Returns:
            Result dict with 'success', 'message', and action-specific data
        """
        # Dispatch to action handlers
        handlers = {
            "settlement:list_locations": self._action_list_locations,
            "settlement:visit_location": self._action_visit_location,
            "settlement:list_services": self._action_list_services,
            "settlement:use_service": self._action_use_service,
            "settlement:list_npcs": self._action_list_npcs,
            "settlement:talk": self._action_talk_to_npc,
            "settlement:ask_directions": self._action_ask_directions,
            "settlement:ask_rumor": self._action_ask_rumor,
            "settlement:check_encounter": self._action_check_encounter,
            "settlement:leave": self._action_leave,
        }

        handler = handlers.get(action_id)
        if handler:
            try:
                return handler(params)
            except Exception as e:
                logger.exception(f"Error executing action {action_id}: {e}")
                return {
                    "success": False,
                    "message": f"Error executing action: {str(e)}",
                    "action": action_id,
                }

        return {
            "success": False,
            "message": f"Unknown action: {action_id}",
            "action": action_id,
        }

    # =========================================================================
    # ACTION HANDLERS (Phase 1: Core Navigation)
    # =========================================================================

    def _action_list_locations(self, params: dict[str, Any]) -> dict[str, Any]:
        """List all locations in the current settlement."""
        settlement = self.get_active_settlement()
        if not settlement:
            return {
                "success": False,
                "message": "Not currently in a settlement with location data.",
                "action": "settlement:list_locations",
            }

        locations = []
        for loc in sorted(settlement.locations, key=lambda x: x.number):
            loc_info = {
                "number": loc.number,
                "name": loc.name,
                "type": loc.location_type,
                "visited": loc.number in self._visited_locations,
                "is_locked": loc.is_locked,
                "key_holder": loc.key_holder if loc.is_locked else None,
            }
            # Add brief description excerpt
            if loc.description:
                loc_info["brief"] = loc.description[:100] + "..." if len(loc.description) > 100 else loc.description
            locations.append(loc_info)

        return {
            "success": True,
            "message": f"{settlement.name} has {len(locations)} notable locations:",
            "action": "settlement:list_locations",
            "settlement_id": settlement.settlement_id,
            "settlement_name": settlement.name,
            "locations": locations,
            "current_location": self._current_location_number,
        }

    def _action_visit_location(self, params: dict[str, Any]) -> dict[str, Any]:
        """Visit a specific location by number."""
        settlement = self.get_active_settlement()
        if not settlement:
            return {
                "success": False,
                "message": "Not currently in a settlement.",
                "action": "settlement:visit_location",
            }

        location_number = params.get("location_number")
        if location_number is None:
            return {
                "success": False,
                "message": "No location number specified.",
                "action": "settlement:visit_location",
            }

        loc_map = settlement.location_by_number()
        location = loc_map.get(location_number)
        if not location:
            return {
                "success": False,
                "message": f"Location {location_number} not found in {settlement.name}.",
                "action": "settlement:visit_location",
            }

        # Check if locked (Phase 4 will add proper enforcement)
        if location.is_locked:
            return {
                "success": False,
                "message": f"{location.name} is locked. Key holder: {location.key_holder or 'unknown'}",
                "action": "settlement:visit_location",
                "location_number": location_number,
                "is_locked": True,
                "key_holder": location.key_holder,
            }

        # Update state
        self._current_location_number = location_number
        self._visited_locations.add(location_number)

        # Log the visit event
        _log_settlement_event("visit_location", {
            "settlement_id": settlement.settlement_id,
            "settlement_name": settlement.name,
            "location_number": location_number,
            "location_name": location.name,
            "location_type": location.location_type,
        })

        # Build location details
        services = [{"name": s.name, "cost": s.cost, "description": s.description} for s in location.services]

        # Get NPCs - both from location.npcs and by matching npc.location_id
        npc_map = settlement.npc_by_id()
        npc_ids_set = set(location.npcs)
        # Also find NPCs whose location_id matches this location
        for npc in settlement.npcs:
            if npc.location_id and str(npc.location_id) == str(location_number):
                npc_ids_set.add(npc.npc_id)
        npcs = list(npc_ids_set)

        return {
            "success": True,
            "message": f"You arrive at {location.name}.",
            "action": "settlement:visit_location",
            "location": {
                "number": location.number,
                "name": location.name,
                "type": location.location_type,
                "description": location.description,
                "exterior": location.exterior,
                "interior": location.interior,
                "atmosphere": location.atmosphere,
                "populace": location.populace,
                "special_features": location.special_features,
            },
            "services": services,
            "npc_ids": npcs,
            "has_services": len(services) > 0,
            "has_npcs": len(npcs) > 0,
        }

    # =========================================================================
    # ACTION HANDLERS (Phase 2: Services + NPCs)
    # =========================================================================

    def _action_list_services(self, params: dict[str, Any]) -> dict[str, Any]:
        """List services at current location."""
        location = self.get_current_location()
        if not location:
            # If no specific location, list all services in settlement
            settlement = self.get_active_settlement()
            if not settlement:
                return {
                    "success": False,
                    "message": "Not in a settlement.",
                    "action": "settlement:list_services",
                }

            all_services = []
            for loc in settlement.locations:
                for svc in loc.services:
                    all_services.append({
                        "name": svc.name,
                        "cost": svc.cost,
                        "location": loc.name,
                        "location_number": loc.number,
                    })

            return {
                "success": True,
                "message": f"Services available in {settlement.name}:",
                "action": "settlement:list_services",
                "services": all_services,
            }

        # Services at current location
        services = [{"name": s.name, "cost": s.cost, "description": s.description, "notes": s.notes} for s in location.services]

        if not services:
            return {
                "success": True,
                "message": f"No services available at {location.name}.",
                "action": "settlement:list_services",
                "services": [],
            }

        return {
            "success": True,
            "message": f"Services at {location.name}:",
            "action": "settlement:list_services",
            "location_name": location.name,
            "services": services,
        }

    def _action_use_service(self, params: dict[str, Any]) -> dict[str, Any]:
        """Use a service at the current location."""
        from src.settlement.settlement_services import SettlementServiceExecutor, parse_cost_text

        service_name = params.get("service_name", "")
        location = self.get_current_location()
        settlement = self.get_active_settlement()

        if not location:
            return {
                "success": False,
                "message": "Visit a location first to use services.",
                "action": "settlement:use_service",
            }

        # Find matching service (try exact match first, then partial)
        matched = None
        for svc in location.services:
            if svc.name.lower() == service_name.lower():
                matched = svc
                break
        if not matched:
            for svc in location.services:
                if service_name.lower() in svc.name.lower():
                    matched = svc
                    break

        if not matched:
            available = [s.name for s in location.services]
            return {
                "success": False,
                "message": f"Service '{service_name}' not found at {location.name}.",
                "action": "settlement:use_service",
                "available_services": available,
            }

        # Execute service
        executor = SettlementServiceExecutor()
        result = executor.use(matched, params)

        # Log the service use event
        _log_settlement_event("use_service", {
            "settlement_id": settlement.settlement_id if settlement else None,
            "location_name": location.name,
            "location_number": location.number,
            "service_name": result.service_name,
            "cost_text": result.cost_text,
            "cost_estimate": result.cost_estimate.__dict__ if result.cost_estimate else None,
        })

        return {
            "success": True,
            "message": f"Using {result.service_name}...",
            "action": "settlement:use_service",
            "service_result": result.to_dict(),
            "location_name": location.name,
        }

    def _action_list_npcs(self, params: dict[str, Any]) -> dict[str, Any]:
        """List NPCs at current location or in settlement."""
        settlement = self.get_active_settlement()
        if not settlement:
            return {
                "success": False,
                "message": "Not in a settlement.",
                "action": "settlement:list_npcs",
            }

        location = self.get_current_location()
        npc_map = settlement.npc_by_id()

        if location:
            # Get NPCs at this location from both sources:
            # 1. location.npcs list
            # 2. NPCs whose location_id matches this location number
            seen_ids = set()
            npcs = []

            # From location.npcs
            for npc_id in location.npcs:
                if npc_id in seen_ids:
                    continue
                npc = npc_map.get(npc_id)
                if npc:
                    seen_ids.add(npc_id)
                    npcs.append({
                        "npc_id": npc.npc_id,
                        "name": npc.name,
                        "title": npc.title,
                        "kindred": npc.kindred,
                        "description": npc.description[:100] + "..." if len(npc.description) > 100 else npc.description,
                    })

            # From NPCs with matching location_id
            for npc in settlement.npcs:
                if npc.npc_id in seen_ids:
                    continue
                if npc.location_id and str(npc.location_id) == str(location.number):
                    seen_ids.add(npc.npc_id)
                    npcs.append({
                        "npc_id": npc.npc_id,
                        "name": npc.name,
                        "title": npc.title,
                        "kindred": npc.kindred,
                        "description": npc.description[:100] + "..." if len(npc.description) > 100 else npc.description,
                    })

            return {
                "success": True,
                "message": f"Notable people at {location.name}:" if npcs else f"No notable NPCs at {location.name}.",
                "action": "settlement:list_npcs",
                "location_name": location.name,
                "location_number": location.number,
                "npcs": npcs,
            }

        # All NPCs in settlement
        npcs = []
        for npc in settlement.npcs:
            # Try to find location name for this NPC
            loc_name = None
            if npc.location_id:
                loc_map = settlement.location_by_number()
                loc = loc_map.get(int(npc.location_id)) if npc.location_id.isdigit() else None
                loc_name = loc.name if loc else None

            npcs.append({
                "npc_id": npc.npc_id,
                "name": npc.name,
                "title": npc.title,
                "kindred": npc.kindred,
                "occupation": npc.occupation,
                "location_id": npc.location_id,
                "location_name": loc_name,
            })

        return {
            "success": True,
            "message": f"Notable people in {settlement.name}:",
            "action": "settlement:list_npcs",
            "settlement_name": settlement.name,
            "npcs": npcs,
        }

    def _action_talk_to_npc(self, params: dict[str, Any]) -> dict[str, Any]:
        """Talk to an NPC - provides NPC details for narration."""
        settlement = self.get_active_settlement()
        if not settlement:
            return {
                "success": False,
                "message": "Not in a settlement.",
                "action": "settlement:talk",
            }

        npc_name = params.get("npc_name", "")
        npc_id = params.get("npc_id")  # Allow lookup by ID too

        # Find NPC by ID first, then by name
        matched = None
        if npc_id:
            npc_map = settlement.npc_by_id()
            matched = npc_map.get(npc_id)

        if not matched:
            # Try exact name match first
            for npc in settlement.npcs:
                if npc.name.lower() == npc_name.lower():
                    matched = npc
                    break
            # Then try partial match
            if not matched:
                for npc in settlement.npcs:
                    if npc_name.lower() in npc.name.lower():
                        matched = npc
                        break

        if not matched:
            # Suggest available NPCs
            available = [npc.name for npc in settlement.npcs]
            return {
                "success": False,
                "message": f"Could not find '{npc_name}' in {settlement.name}.",
                "action": "settlement:talk",
                "available_npcs": available[:5],  # Limit suggestions
            }

        # Log the talk event
        _log_settlement_event("talk_to_npc", {
            "settlement_id": settlement.settlement_id,
            "npc_id": matched.npc_id,
            "npc_name": matched.name,
            "location_number": self._current_location_number,
        })

        # Get NPC's location name if available
        npc_location_name = None
        if matched.location_id:
            loc_map = settlement.location_by_number()
            loc = loc_map.get(int(matched.location_id)) if matched.location_id.isdigit() else None
            npc_location_name = loc.name if loc else None

        return {
            "success": True,
            "message": f"You approach {matched.name}.",
            "action": "settlement:talk",
            "npc": {
                "npc_id": matched.npc_id,
                "name": matched.name,
                "title": matched.title,
                "description": matched.description,
                "kindred": matched.kindred,
                "alignment": matched.alignment,
                "demeanor": matched.demeanor,
                "mannerisms": matched.mannerisms,
                "speech": matched.speech,
                "languages": matched.languages,
                "desires": matched.desires,
                "secrets": matched.secrets,
                "occupation": matched.occupation,
                "location_name": npc_location_name,
            },
        }

    def _action_ask_directions(self, params: dict[str, Any]) -> dict[str, Any]:
        """Ask for directions / roads out of settlement."""
        settlement = self.get_active_settlement()
        if not settlement:
            return {
                "success": False,
                "message": "Not in a settlement.",
                "action": "settlement:ask_directions",
            }

        return {
            "success": True,
            "message": f"Roads and connections from {settlement.name}:",
            "action": "settlement:ask_directions",
            "roads": settlement.roads,
            "connections": settlement.connections,
        }

    def _action_ask_rumor(self, params: dict[str, Any]) -> dict[str, Any]:
        """Ask about rumors (stub - needs rumor system)."""
        settlement = self.get_active_settlement()
        if not settlement:
            return {
                "success": False,
                "message": "Not in a settlement.",
                "action": "settlement:ask_rumor",
            }

        return {
            "success": True,
            "message": f"Rumors in {settlement.name}...",
            "action": "settlement:ask_rumor",
            "rumors_reference": settlement.rumors_reference,
            "current_events": settlement.current_events,
            "note": "Full rumor system to be implemented.",
        }

    def _action_leave(self, params: dict[str, Any]) -> dict[str, Any]:
        """Leave the settlement."""
        settlement = self.get_active_settlement()
        if not settlement:
            return {
                "success": False,
                "message": "Not in a settlement.",
                "action": "settlement:leave",
            }

        settlement_name = settlement.name
        hex_id = settlement.hex_id

        # Clear v2 state
        self.clear_active_settlement()

        return {
            "success": True,
            "message": f"You depart from {settlement_name}.",
            "action": "settlement:leave",
            "settlement_name": settlement_name,
            "hex_id": hex_id,
            "note": "Use exit_settlement() for full state transition to wilderness.",
        }

    # =========================================================================
    # ACTION HANDLERS (Phase 3: Encounters)
    # =========================================================================

    def _action_check_encounter(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Check for a random encounter in the settlement.

        Per Dolmenwood rules (p160):
        - Daytime: 2-in-6 chance when active
        - Nighttime: 1-in-6 chance when active

        Args:
            params: Optional parameters:
                - time_of_day: TimeOfDay enum or string (defaults to current time)
                - force_roll: If True, skip probability check and roll table directly
                - route_to_encounter_engine: If True, create EncounterState for EncounterEngine

        Returns:
            Result dict with encounter outcome
        """
        settlement = self.get_active_settlement()
        if not settlement:
            return {
                "success": False,
                "message": "Not in a settlement.",
                "action": "settlement:check_encounter",
            }

        # Get time of day
        time_of_day = params.get("time_of_day")
        if time_of_day is None:
            # Get from controller's time tracker
            try:
                time_of_day = self.controller.time_tracker.game_time.get_time_of_day()
            except Exception:
                time_of_day = TimeOfDay.MIDDAY  # Default to day
        elif isinstance(time_of_day, str):
            try:
                time_of_day = TimeOfDay(time_of_day)
            except ValueError:
                time_of_day = TimeOfDay.MIDDAY

        day_night = tod_to_daynight(time_of_day)

        # Roll probability check unless forced
        force_roll = params.get("force_roll", False)
        if not force_roll:
            # Day: 2-in-6, Night: 1-in-6
            threshold = 2 if day_night == "day" else 1
            prob_roll = self.dice.roll("1d6", reason=f"Settlement encounter check ({day_night})")

            if prob_roll.total > threshold:
                return {
                    "success": True,
                    "message": f"No encounter ({day_night}: rolled {prob_roll.total}, needed {threshold} or less).",
                    "action": "settlement:check_encounter",
                    "encounter_occurred": False,
                    "probability_roll": prob_roll.total,
                    "threshold": threshold,
                    "time_of_day": time_of_day.value,
                    "day_night": day_night,
                }

        # Roll on the encounter table
        encounter_result = self.check_settlement_encounter(time_of_day)

        if not encounter_result:
            return {
                "success": True,
                "message": f"No encounter table available for {settlement.name} ({day_night}).",
                "action": "settlement:check_encounter",
                "encounter_occurred": False,
                "time_of_day": time_of_day.value,
                "day_night": day_night,
            }

        # Log the encounter event
        _log_settlement_event("encounter", {
            "settlement_id": settlement.settlement_id,
            "settlement_name": settlement.name,
            "time_of_day": time_of_day.value,
            "day_night": day_night,
            "roll": encounter_result.roll,
            "description": encounter_result.description,
            "npcs_involved": encounter_result.npcs_involved,
            "monsters_involved": encounter_result.monsters_involved,
        })

        # Build response
        result = {
            "success": True,
            "message": f"Encounter! ({day_night}, rolled {encounter_result.roll})",
            "action": "settlement:check_encounter",
            "encounter_occurred": True,
            "time_of_day": time_of_day.value,
            "day_night": day_night,
            "encounter": {
                "roll": encounter_result.roll,
                "description": encounter_result.description,
                "npcs_involved": encounter_result.npcs_involved,
                "monsters_involved": encounter_result.monsters_involved,
                "notes": encounter_result.notes,
            },
        }

        # Optionally route to EncounterEngine
        route_to_engine = params.get("route_to_encounter_engine", False)
        if route_to_engine and (encounter_result.monsters_involved or encounter_result.npcs_involved):
            result["encounter_engine_data"] = self._prepare_encounter_for_engine(
                encounter_result, settlement, time_of_day
            )

        return result

    def check_settlement_encounter(
        self, time_of_day: Optional[TimeOfDay] = None
    ) -> Optional[SettlementEncounterResult]:
        """
        Roll on the settlement encounter table.

        This method rolls directly on the encounter table without checking
        the probability threshold. Use _action_check_encounter for full
        encounter check with probability.

        Args:
            time_of_day: The time of day (defaults to current time from controller)

        Returns:
            SettlementEncounterResult if encounter occurs, None otherwise
        """
        settlement = self.get_active_settlement()
        if not settlement:
            return None

        # Get time of day
        if time_of_day is None:
            try:
                time_of_day = self.controller.time_tracker.game_time.get_time_of_day()
            except Exception:
                time_of_day = TimeOfDay.MIDDAY

        # Create encounter tables wrapper and roll
        tables = SettlementEncounterTables(settlement)
        return tables.roll(self.dice, time_of_day)

    def _prepare_encounter_for_engine(
        self,
        encounter_result: SettlementEncounterResult,
        settlement: SettlementData,
        time_of_day: TimeOfDay,
    ) -> dict[str, Any]:
        """
        Prepare encounter data for routing to EncounterEngine.

        This creates the data needed to call EncounterEngine.start_encounter().
        The actual EncounterState creation should be done by the caller.

        Args:
            encounter_result: The settlement encounter result
            settlement: The settlement data
            time_of_day: The time of day

        Returns:
            Dict with data for EncounterEngine integration
        """
        from src.encounter.encounter_engine import EncounterOrigin

        # Determine encounter type based on what's involved
        has_monsters = bool(encounter_result.monsters_involved)
        has_npcs = bool(encounter_result.npcs_involved)

        return {
            "origin": EncounterOrigin.SETTLEMENT.value,
            "settlement_id": settlement.settlement_id,
            "settlement_name": settlement.name,
            "location_number": self._current_location_number,
            "time_of_day": time_of_day.value,
            "actors": encounter_result.monsters_involved + encounter_result.npcs_involved,
            "context": encounter_result.description,
            "has_monsters": has_monsters,
            "has_npcs": has_npcs,
            "notes": encounter_result.notes,
            "suggested_encounter_type": "monster" if has_monsters else "npc",
        }

    def check_encounter_on_time_advance(
        self, new_time_of_day: TimeOfDay, is_active: bool = True
    ) -> Optional[dict[str, Any]]:
        """
        Hook for checking encounters when time advances.

        This should be called by time-advancing actions (rest, waiting, etc.)
        to check for random encounters per Dolmenwood rules.

        Args:
            new_time_of_day: The time of day after advancement
            is_active: Whether the party is active (exploring, not hidden)

        Returns:
            Encounter result dict if encounter occurs, None otherwise
        """
        if not is_active:
            return None

        settlement = self.get_active_settlement()
        if not settlement:
            return None

        # Check using the action handler
        result = self._action_check_encounter({
            "time_of_day": new_time_of_day,
            "force_roll": False,
        })

        if result.get("encounter_occurred"):
            return result
        return None

    # =========================================================================
    # SETTLEMENT MANAGEMENT
    # =========================================================================

    def load_settlement(self, settlement: Settlement) -> None:
        """Load settlement data."""
        self._settlements[settlement.settlement_id] = settlement

    def load_npc(self, npc: NPC) -> None:
        """Load NPC data."""
        self._npcs[npc.npc_id] = npc

    def get_settlement(self, settlement_id: str) -> Optional[Settlement]:
        """Get settlement by ID."""
        return self._settlements.get(settlement_id)

    def get_npc(self, npc_id: str) -> Optional[NPC]:
        """Get NPC by ID."""
        return self._npcs.get(npc_id)

    # =========================================================================
    # SETTLEMENT EXPLORATION
    # =========================================================================

    def enter_settlement(
        self, settlement_id: str, settlement_data: Optional[Settlement] = None
    ) -> dict[str, Any]:
        """
        Enter a settlement.

        Args:
            settlement_id: Settlement identifier
            settlement_data: Pre-loaded settlement data (optional)

        Returns:
            Dictionary with entry results
        """
        # Validate state
        if self.controller.current_state != GameState.WILDERNESS_TRAVEL:
            return {"error": "Can only enter settlement from wilderness travel"}

        # Load or use provided data
        if settlement_data:
            self._settlements[settlement_id] = settlement_data

        settlement = self._settlements.get(settlement_id)
        if not settlement:
            # Create minimal settlement if not loaded
            settlement = Settlement(
                settlement_id=settlement_id,
                name=f"Settlement {settlement_id}",
                size=SettlementSize.VILLAGE,
                hex_id=str(self.controller.party_state.location.location_id),
                population=200,
            )
            self._settlements[settlement_id] = settlement

        self._current_settlement = settlement_id

        # Transition to settlement exploration
        self.controller.transition(
            "enter_settlement",
            context={
                "settlement_id": settlement_id,
                "settlement_name": settlement.name,
            },
        )

        # Update party location
        self.controller.set_party_location(LocationType.SETTLEMENT, settlement_id)

        result = {
            "settlement_id": settlement_id,
            "name": settlement.name,
            "size": settlement.size.value,
            "population": settlement.population,
            "available_services": [s.value for s in settlement.available_services],
            "buildings": len(settlement.buildings),
            "notable_npcs": len(settlement.npcs),
        }

        # Request description if callback registered
        if self._description_callback:
            self._description_callback(
                settlement_id=settlement_id,
                name=settlement.name,
                size=settlement.size.value,
                time_of_day=self.controller.time_tracker.game_time.get_time_of_day().value,
            )

        return result

    def exit_settlement(self) -> dict[str, Any]:
        """
        Exit the current settlement to wilderness.

        Returns:
            Dictionary with exit results
        """
        if self.controller.current_state != GameState.SETTLEMENT_EXPLORATION:
            return {"error": "Not in settlement exploration state"}

        settlement_id = self._current_settlement
        settlement = self._settlements.get(settlement_id) if settlement_id else None

        result = {
            "settlement_id": settlement_id,
            "settlement_name": settlement.name if settlement else "Unknown",
        }

        # Transition back to wilderness
        self.controller.transition("exit_settlement", context=result)

        self._current_settlement = None

        return result

    # =========================================================================
    # LIFESTYLE MANAGEMENT (p161)
    # =========================================================================

    def set_lifestyle(self, lifestyle: LifestyleType) -> dict[str, Any]:
        """
        Set the party's lifestyle for settlement stays (p161).

        Lifestyle affects daily costs and healing:
        - Wretched: Free, no healing
        - Poor: 5sp/day, 15gp/month
        - Common: 2gp/day, 60gp/month
        - Fancy: 10gp/day, 300gp/month

        Args:
            lifestyle: The lifestyle tier to use

        Returns:
            Dictionary with lifestyle info
        """
        self._current_lifestyle = lifestyle
        lifestyle_info = LIFESTYLE_DATA[lifestyle]

        return {
            "lifestyle": lifestyle.value,
            "cost_per_day_sp": lifestyle_info["cost_per_day_sp"],
            "cost_per_month_gp": lifestyle_info["cost_per_month_gp"],
            "allows_healing": lifestyle_info["allows_healing"],
            "description": lifestyle_info["description"],
        }

    def get_lifestyle_cost(self, days: int = 1) -> dict[str, Any]:
        """
        Calculate lifestyle expenses for a number of days (p161).

        Args:
            days: Number of days to calculate costs for

        Returns:
            Dictionary with cost breakdown
        """
        lifestyle_info = LIFESTYLE_DATA[self._current_lifestyle]
        daily_cost_sp = lifestyle_info["cost_per_day_sp"]

        # Monthly rate is cheaper - use if staying 30+ days
        if days >= 30:
            months = days // 30
            remaining_days = days % 30
            monthly_cost_gp = lifestyle_info["cost_per_month_gp"]
            total_cost_gp = (months * monthly_cost_gp) + (remaining_days * daily_cost_sp / 10)
        else:
            total_cost_gp = (days * daily_cost_sp) / 10  # Convert sp to gp

        return {
            "lifestyle": self._current_lifestyle.value,
            "days": days,
            "total_cost_gp": total_cost_gp,
            "allows_healing": lifestyle_info["allows_healing"],
        }

    # =========================================================================
    # EARNING MONEY (p160)
    # =========================================================================

    def earn_money_using_class(self, character_id: str, days: int = 1) -> dict[str, Any]:
        """
        Earn money using class capabilities per Dolmenwood rules (p160).

        Characters can earn 3d6sp per day using their class abilities:
        - Bards performing in taverns
        - Thieves picking pockets at markets
        - etc.

        Args:
            character_id: ID of character earning money
            days: Number of days spent earning

        Returns:
            Dictionary with earnings
        """
        total_sp = 0
        daily_earnings = []

        for day in range(days):
            roll = self.dice.roll("3d6", f"day {day + 1} earnings")
            total_sp += roll.total
            daily_earnings.append(roll.total)

        return {
            "character_id": character_id,
            "days_worked": days,
            "daily_earnings_sp": daily_earnings,
            "total_sp": total_sp,
            "total_gp": total_sp / 10,
        }

    # =========================================================================
    # DAILY SETTLEMENT LOOP (p160)
    # =========================================================================

    def process_settlement_day(
        self,
        planned_actions: list[str],
        active_at_night: bool = False,
        lifestyle: Optional[LifestyleType] = None,
    ) -> dict[str, Any]:
        """
        Execute one settlement day following Dolmenwood procedures (p160).

        Settlement Procedure Per Day:
        1. Weather: Determine day's weather
        2. Decide actions: Players choose activities
        3. Random encounters: Daytime check (2-in-6 when active)
        4. Description: Describe what happens
        5. End of day: Update time records, apply lifestyle costs
        6. Random encounters: Nighttime check if active (1-in-6)

        Args:
            planned_actions: List of planned activities
            active_at_night: Whether party is active at night
            lifestyle: Optional lifestyle override for the day

        Returns:
            Dictionary with day summary
        """
        if self.controller.current_state != GameState.SETTLEMENT_EXPLORATION:
            return {"error": "Not in settlement exploration state"}

        # Apply lifestyle if specified
        if lifestyle:
            self._current_lifestyle = lifestyle

        # 1. Weather (from world state)
        weather = self.controller.world_state.weather.value

        # 3. Daytime random encounter (2-in-6) - only when active
        is_just_resting = planned_actions == ["full_rest"]
        daytime_encounter = None
        if not is_just_resting:
            daytime_encounter = self._check_settlement_encounter(TimeOfDay.MIDDAY)

        # 5. End of day - advance time (144 turns = 1 day)
        time_result = self.controller.advance_time(144)
        self._days_in_settlement += 1

        # Apply lifestyle costs
        lifestyle_info = LIFESTYLE_DATA[self._current_lifestyle]
        lifestyle_cost = {
            "lifestyle": self._current_lifestyle.value,
            "cost_sp": lifestyle_info["cost_per_day_sp"],
        }

        # Apply rest healing (respects lifestyle healing rules)
        healing_info = self._apply_rest_healing(
            full_day_rest="full_rest" in planned_actions,
            nights=1,
            apply=True,
        )

        # 6. Nighttime random encounter (1-in-6) - only when active at night
        night_encounter = None
        if active_at_night:
            night_encounter = self._check_settlement_encounter(TimeOfDay.MIDNIGHT, night=True)

        summary = {
            "weather": weather,
            "planned_actions": planned_actions,
            "daytime_encounter": daytime_encounter,
            "nighttime_encounter": night_encounter,
            "healing": healing_info,
            "lifestyle": lifestyle_cost,
            "days_in_settlement": self._days_in_settlement,
            "time_advanced": time_result,
        }

        if self._description_callback:
            self._description_callback(
                settlement_id=self._current_settlement,
                name=self.get_current_settlement().name if self.get_current_settlement() else "",
                size=(
                    self.get_current_settlement().size.value
                    if self.get_current_settlement()
                    else ""
                ),
                time_of_day=self.controller.time_tracker.game_time.get_time_of_day().value,
            )

        return summary

    def _check_settlement_encounter(
        self, time_of_day: TimeOfDay, night: bool = False
    ) -> Optional[dict[str, Any]]:
        """
        Settlement random encounter check per Dolmenwood rules (p160).

        When PCs are active in a settlement (not just resting in an inn):
        - Daytime: 2-in-6 chance
        - Nighttime: 1-in-6 chance

        This is in addition to NPCs encountered at settlement locations.
        """
        chance = 1 if night else 2
        roll = self.dice.roll_d6(1, f"settlement encounter {time_of_day.value}")
        if roll.total <= chance:
            return {
                "time_of_day": time_of_day.value,
                "roll": roll.total,
                "encounter": "Random settlement encounter",
            }
        return None

    def _apply_rest_healing(
        self, full_day_rest: bool, nights: int = 1, apply: bool = False
    ) -> dict[str, Any]:
        """
        Apply rest healing while in settlement per Dolmenwood rules (p160).

        Healing overnight: 1 HP per night in settlement
        Full days of rest: 1d3 HP per day (precludes strenuous activity)

        Note: Wretched lifestyle prevents all healing (p161).
        """
        # Check if lifestyle allows healing (p161)
        lifestyle_info = LIFESTYLE_DATA[self._current_lifestyle]
        if not lifestyle_info["allows_healing"]:
            return {
                "full_day_rest": full_day_rest,
                "nights": nights,
                "healing_per_character": {},
                "lifestyle": self._current_lifestyle.value,
                "no_healing_reason": "Wretched lifestyle prevents healing",
            }

        healing_per_character: dict[str, int] = {}

        for _ in range(nights):
            heal_amount = self.dice.roll("1d3", "full day rest").total if full_day_rest else 1
            for character in self.controller.get_all_characters():
                healing_per_character.setdefault(character.character_id, 0)
                healing_per_character[character.character_id] += heal_amount
                if apply:
                    self.controller.heal_character(character.character_id, heal_amount)

        return {
            "full_day_rest": full_day_rest,
            "nights": nights,
            "healing_per_character": healing_per_character,
        }

    def visit_building(self, building_id: str) -> dict[str, Any]:
        """
        Visit a specific building in the settlement.

        Args:
            building_id: Building identifier

        Returns:
            Dictionary with building info
        """
        if not self._current_settlement:
            return {"error": "Not in a settlement"}

        settlement = self._settlements.get(self._current_settlement)
        if not settlement:
            return {"error": "Settlement data not found"}

        building = None
        for b in settlement.buildings:
            if b.building_id == building_id:
                building = b
                break

        if not building:
            return {"error": f"Building {building_id} not found"}

        # Check if building is open
        current_hour = self.controller.time_tracker.game_time.hour
        is_open = building.open_hours[0] <= current_hour < building.open_hours[1]

        result = {
            "building_id": building_id,
            "name": building.name,
            "type": building.building_type.value,
            "services": [s.value for s in building.services],
            "is_open": is_open,
            "description": building.description,
        }

        if building.proprietor:
            npc = self._npcs.get(building.proprietor)
            if npc:
                result["proprietor"] = {
                    "id": npc.npc_id,
                    "name": npc.name,
                    "title": npc.title,
                }

        # Update location
        self.controller.set_party_location(
            LocationType.BUILDING, building_id, sub_location=self._current_settlement
        )

        return result

    def get_available_services(self) -> dict[ServiceType, list[Building]]:
        """Get all available services in current settlement."""
        if not self._current_settlement:
            return {}

        settlement = self._settlements.get(self._current_settlement)
        if not settlement:
            return {}

        services: dict[ServiceType, list[Building]] = {}
        for building in settlement.buildings:
            for service in building.services:
                if service not in services:
                    services[service] = []
                services[service].append(building)

        return services

    # =========================================================================
    # SOCIAL INTERACTION
    # =========================================================================

    def initiate_conversation(self, npc_id: str) -> dict[str, Any]:
        """
        Start a conversation with an NPC.

        Args:
            npc_id: NPC identifier

        Returns:
            Dictionary with conversation initialization
        """
        if self.controller.current_state not in {
            GameState.SETTLEMENT_EXPLORATION,
            GameState.WILDERNESS_ENCOUNTER,
            GameState.DUNGEON_ENCOUNTER,
        }:
            return {"error": "Cannot initiate conversation from current state"}

        npc = self._npcs.get(npc_id)
        if not npc:
            return {"error": f"NPC {npc_id} not found"}

        # Roll initial reaction if first meeting
        initial_reaction = None
        if not npc.met_before:
            reaction_roll = self.dice.roll_2d6("initial reaction")
            initial_reaction = self._interpret_reaction(reaction_roll.total)
            npc.met_before = True
            npc.disposition = self._reaction_to_disposition(initial_reaction)

        # Initialize conversation state
        self._conversation = ConversationState(
            npc_id=npc_id,
            npc_name=npc.name,
            disposition=npc.disposition,
        )

        # Transition to social interaction
        self.controller.transition(
            "initiate_conversation",
            context={
                "npc_id": npc_id,
                "npc_name": npc.name,
            },
        )

        result = {
            "npc_id": npc_id,
            "npc_name": npc.name,
            "title": npc.title,
            "initial_reaction": initial_reaction.value if initial_reaction else None,
            "disposition": npc.disposition,
            "dialogue_hooks": npc.dialogue_hooks,
        }

        # Request initial dialogue if callback registered
        if self._dialogue_callback:
            self._dialogue_callback(
                npc_id=npc_id,
                npc_profile=npc,
                topic=ConversationTopic.GREETING,
                disposition=npc.disposition,
            )

        return result

    def continue_conversation(
        self, topic: ConversationTopic, player_approach: str = ""
    ) -> dict[str, Any]:
        """
        Continue an active conversation.

        Args:
            topic: The topic to discuss
            player_approach: How the player approaches the topic

        Returns:
            Dictionary with conversation results
        """
        if not self._conversation:
            return {"error": "No active conversation"}

        if self.controller.current_state != GameState.SOCIAL_INTERACTION:
            return {"error": "Not in social interaction state"}

        npc = self._npcs.get(self._conversation.npc_id)
        if not npc:
            return {"error": "NPC data not found"}

        # Advance time (conversation takes time)
        self.controller.advance_time(1)  # 10 minutes per topic
        self._conversation.turns_elapsed += 1

        # Track topic
        self._conversation.topics_discussed.append(topic)

        result = {
            "topic": topic.value,
            "success": True,
            "information": [],
            "disposition_change": 0,
        }

        # Handle different topics
        if topic == ConversationTopic.RUMORS:
            result["information"] = self._gather_rumors(npc)
        elif topic == ConversationTopic.LOCAL_INFO:
            result["information"] = self._get_local_info(npc)
        elif topic == ConversationTopic.DIRECTIONS:
            result["information"] = self._get_directions(npc)
        elif topic == ConversationTopic.QUEST:
            result["information"] = self._check_for_quest(npc)
        elif topic == ConversationTopic.TRADE:
            result["trade_available"] = self._check_trade_options(npc)
        elif topic == ConversationTopic.FACTION:
            result["information"] = self._get_faction_info(npc)

        # Check for disposition change based on approach
        if player_approach:
            disposition_change = self._evaluate_approach(player_approach, npc)
            self._conversation.disposition += disposition_change
            npc.disposition = self._conversation.disposition
            result["disposition_change"] = disposition_change

        # Check if secrets can be revealed (high disposition)
        if self._conversation.disposition >= 3 and npc.secrets:
            # May reveal a secret
            roll = self.dice.roll_d6(1, "secret reveal")
            if roll.total <= self._conversation.disposition - 2:
                secret = npc.secrets[0]  # First unrevealed secret
                if secret not in self._conversation.secrets_revealed:
                    self._conversation.secrets_revealed.append(secret)
                    result["secret_revealed"] = True

        # Request dialogue if callback registered
        if self._dialogue_callback:
            self._dialogue_callback(
                npc_id=self._conversation.npc_id,
                npc_profile=npc,
                topic=topic,
                disposition=self._conversation.disposition,
                player_approach=player_approach,
            )

        return result

    def end_conversation(self) -> dict[str, Any]:
        """
        End the current conversation.

        Returns:
            Dictionary with conversation summary
        """
        if not self._conversation:
            return {"error": "No active conversation"}

        npc = self._npcs.get(self._conversation.npc_id)

        result = {
            "npc_id": self._conversation.npc_id,
            "npc_name": self._conversation.npc_name,
            "topics_discussed": [t.value for t in self._conversation.topics_discussed],
            "final_disposition": self._conversation.disposition,
            "secrets_revealed": len(self._conversation.secrets_revealed),
            "turns_elapsed": self._conversation.turns_elapsed,
        }

        # Log interaction
        if npc:
            npc.interactions.append(
                {
                    "date": str(self.controller.world_state.current_date),
                    "topics": [t.value for t in self._conversation.topics_discussed],
                    "disposition_change": self._conversation.disposition - npc.disposition,
                }
            )

        # Determine return state
        if self._current_settlement:
            trigger = "conversation_end_settlement"
        elif self.controller.party_state.location.location_type == LocationType.DUNGEON_ROOM:
            trigger = "conversation_end_dungeon"
        else:
            trigger = "conversation_end_wilderness"

        self.controller.transition(trigger, context=result)
        self._conversation = None

        return result

    def _interpret_reaction(self, roll: int) -> ReactionResult:
        """Interpret 2d6 reaction roll using canonical function."""
        return interpret_reaction(roll)

    def _reaction_to_disposition(self, reaction: ReactionResult) -> int:
        """Convert reaction to disposition score."""
        mapping = {
            ReactionResult.ATTACKS: -3,
            ReactionResult.HOSTILE: -2,
            ReactionResult.UNCERTAIN: 0,
            ReactionResult.INDIFFERENT: 1,
            ReactionResult.FRIENDLY: 3,
        }
        return mapping.get(reaction, 0)

    def _gather_rumors(self, npc: NPC) -> list[str]:
        """Gather rumors from an NPC."""
        rumors = []

        # Check settlement rumors
        if self._current_settlement:
            settlement = self._settlements.get(self._current_settlement)
            if settlement and settlement.rumors:
                # NPC knows some settlement rumors
                num_rumors = min(2, len(settlement.rumors))
                roll = self.dice.roll_d6(1, "rumor knowledge")
                if roll.total >= 4:
                    rumors.append(settlement.rumors[roll.total % len(settlement.rumors)])

        # NPC-specific knowledge based on disposition
        if self._conversation and self._conversation.disposition >= 1:
            if npc.goals:
                rumors.append(f"{npc.name} seems interested in {npc.goals[0]}")

        return rumors

    def _get_local_info(self, npc: NPC) -> list[str]:
        """Get local information from NPC."""
        info = []

        if self._current_settlement:
            settlement = self._settlements.get(self._current_settlement)
            if settlement:
                info.append(f"{settlement.name} has about {settlement.population} inhabitants")
                if settlement.ruler:
                    ruler = self._npcs.get(settlement.ruler)
                    if ruler:
                        info.append(f"The settlement is led by {ruler.name}")
                if settlement.faction:
                    info.append(f"The settlement is aligned with {settlement.faction}")

        return info

    def _get_directions(self, npc: NPC) -> list[str]:
        """Get directions from NPC."""
        # Would integrate with hex data for actual directions
        return [f"{npc.name} can provide directions to nearby locations"]

    def _check_for_quest(self, npc: NPC) -> list[str]:
        """Check if NPC has a quest available."""
        quests = []

        # Check NPC goals for potential quests
        if npc.goals and self._conversation:
            if self._conversation.disposition >= 1:
                quests.append(f"{npc.name} might need help with: {npc.goals[0]}")

        return quests

    def _check_trade_options(self, npc: NPC) -> dict[str, Any]:
        """Check what trade options are available."""
        return {
            "can_trade": True,
            "npc_id": npc.npc_id,
            "disposition_modifier": self._conversation.disposition if self._conversation else 0,
        }

    def _get_faction_info(self, npc: NPC) -> list[str]:
        """Get faction information from NPC."""
        info = []

        if npc.faction:
            info.append(f"{npc.name} is associated with {npc.faction}")
            if self._conversation and self._conversation.disposition >= 2:
                info.append(f"The {npc.faction} faction has interests in this area")

        return info

    def _evaluate_approach(self, approach: str, npc: NPC) -> int:
        """
        Evaluate player's conversation approach for disposition change.

        This would ideally be informed by NPC personality and context.
        """
        # Simple implementation - could be expanded with personality matching
        roll = self.dice.roll_2d6("approach evaluation")

        if roll.total >= 10:
            return 1  # Positive impression
        elif roll.total <= 4:
            return -1  # Negative impression
        return 0  # Neutral

    # =========================================================================
    # SERVICES
    # =========================================================================

    def use_service(
        self,
        service_type: ServiceType,
        building_id: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Use a service in the settlement.

        Args:
            service_type: Type of service to use
            building_id: Specific building (optional)
            parameters: Service-specific parameters

        Returns:
            Dictionary with service results
        """
        parameters = parameters or {}

        if not self._current_settlement:
            return {"error": "Not in a settlement"}

        settlement = self._settlements.get(self._current_settlement)
        if not settlement:
            return {"error": "Settlement data not found"}

        # Find building with service
        building = None
        if building_id:
            for b in settlement.buildings:
                if b.building_id == building_id:
                    building = b
                    break
        else:
            for b in settlement.buildings:
                if service_type in b.services:
                    building = b
                    break

        if not building:
            return {"error": f"No {service_type.value} available"}

        # Handle different services
        handlers = {
            ServiceType.INN: self._use_inn,
            ServiceType.TAVERN: self._use_tavern,
            ServiceType.BLACKSMITH: self._use_blacksmith,
            ServiceType.GENERAL_STORE: self._use_general_store,
            ServiceType.TEMPLE: self._use_temple,
            ServiceType.HEALER: self._use_healer,
            ServiceType.STABLES: self._use_stables,
            ServiceType.HIRELING_HALL: self._use_hireling_hall,
            # Dolmenwood-specific services (p161)
            ServiceType.APOTHECARY: self._use_apothecary,
            ServiceType.MONEY_CHANGER: self._use_money_changer,
            ServiceType.JEWELER: self._use_jeweler,
        }

        handler = handlers.get(service_type, self._use_generic_service)
        return handler(building, parameters)

    def _use_inn(self, building: Building, params: dict) -> dict[str, Any]:
        """Use inn services (lodging)."""
        nights = params.get("nights", 1)
        room_type = params.get("room_type", "common")
        full_day_rest = params.get("full_day_rest", False)

        base_cost = {"common": 1, "private": 5, "suite": 20}
        cost = base_cost.get(room_type, 1) * nights * building.prices_modifier
        healing = self._apply_rest_healing(full_day_rest=full_day_rest, nights=nights, apply=True)

        return {
            "service": "lodging",
            "building": building.name,
            "nights": nights,
            "room_type": room_type,
            "cost_gp": cost,
            "includes_meals": room_type != "common",
            "healing": healing,
        }

    def _use_tavern(self, building: Building, params: dict) -> dict[str, Any]:
        """Use tavern services (food, drink, rumors)."""
        # Spending money in tavern can yield rumors
        spending = params.get("spending_gp", 1)

        rumors = []
        if spending >= 5:
            # Good chance of hearing something
            settlement = self._settlements.get(self._current_settlement)
            if settlement and settlement.rumors:
                roll = self.dice.roll_d6(1, "tavern rumor")
                if roll.total >= 3:
                    rumors.append(settlement.rumors[roll.total % len(settlement.rumors)])

        return {
            "service": "tavern",
            "building": building.name,
            "cost_gp": spending,
            "rumors_heard": rumors,
        }

    def _use_blacksmith(self, building: Building, params: dict) -> dict[str, Any]:
        """Use blacksmith services."""
        service = params.get("service", "repair")  # repair, forge, shoe_horse

        costs = {
            "repair": 5,
            "forge_weapon": 50,
            "forge_armor": 100,
            "shoe_horse": 2,
        }

        return {
            "service": service,
            "building": building.name,
            "cost_gp": costs.get(service, 10) * building.prices_modifier,
            "time_days": 1 if service == "repair" else 7,
        }

    def _use_general_store(self, building: Building, params: dict) -> dict[str, Any]:
        """
        Use general store services per Dolmenwood rules (p161).

        Buying and Selling Equipment:
        - Buying: Common adventuring gear at standard prices
        - Selling used equipment: 50% of normal value (if good condition)
        """
        service = params.get("service", "buy")
        item_value = params.get("item_value", 0)

        if service == "sell":
            # Sell used equipment at 50% value (p161)
            sell_value = item_value * 0.5
            return {
                "service": "sell",
                "building": building.name,
                "item_value": item_value,
                "sell_price_gp": sell_value,
                "sell_rate": "50%",
                "condition_required": "good condition",
            }

        return {
            "service": "shopping",
            "building": building.name,
            "prices_modifier": building.prices_modifier,
            "available_items": ["standard adventuring gear"],
            "sell_rate_for_used": "50%",
        }

    def _use_temple(self, building: Building, params: dict) -> dict[str, Any]:
        """Use temple services."""
        service = params.get("service", "blessing")

        costs = {
            "blessing": 1,
            "cure_disease": 100,
            "remove_curse": 250,
            "raise_dead": 1000,
        }

        return {
            "service": service,
            "building": building.name,
            "cost_gp": costs.get(service, 10),
            "donation_expected": True,
        }

    def _use_healer(self, building: Building, params: dict) -> dict[str, Any]:
        """Use healer services."""
        service = params.get("service", "treatment")

        return {
            "service": service,
            "building": building.name,
            "cost_gp": 5 * building.prices_modifier,
            "healing": "1d3 HP restored",
        }

    def _use_stables(self, building: Building, params: dict) -> dict[str, Any]:
        """Use stables services."""
        service = params.get("service", "stabling")  # stabling, buy_horse, buy_mule

        costs = {
            "stabling_day": 1,
            "buy_riding_horse": 75,
            "buy_war_horse": 200,
            "buy_mule": 30,
        }

        return {
            "service": service,
            "building": building.name,
            "cost_gp": costs.get(service, 1) * building.prices_modifier,
        }

    def _use_hireling_hall(self, building: Building, params: dict) -> dict[str, Any]:
        """
        Use hireling hall to find specialists or retainers (p160).

        Characters may ask around to find specialists or retainers for hire.
        """
        hireling_type = params.get("type", "porter")

        # Roll for availability
        roll = self.dice.roll_2d6("hireling availability")

        available = roll.total >= 6

        return {
            "service": "hire",
            "building": building.name,
            "hireling_type": hireling_type,
            "available": available,
            "daily_wage": 1 if hireling_type == "porter" else 2,
        }

    def _use_apothecary(self, building: Building, params: dict) -> dict[str, Any]:
        """
        Use apothecary/herbalist services per Dolmenwood rules (p161).

        Apothecaries and Herbalists:
        - Buying fungi/herbs: Standard prices
        - Identifying fungi/herbs: 5gp fee
        - Selling fungi/herbs: 50% of normal value (useful specimens only)
        """
        service = params.get("service", "identify")
        item_value = params.get("item_value", 0)  # For selling

        if service == "identify":
            return {
                "service": "identify",
                "building": building.name,
                "cost_gp": 5,  # 5gp fee per Dolmenwood rules (p161)
                "result": "Herbalist examines and identifies specimen",
            }
        elif service == "sell":
            # Herbalists buy at 50% value (p161)
            sell_value = item_value * 0.5
            return {
                "service": "sell",
                "building": building.name,
                "item_value": item_value,
                "sell_price_gp": sell_value,
                "sell_rate": "50%",
                "note": "Only useful (non-poisonous) specimens accepted",
            }
        elif service == "buy":
            return {
                "service": "buy",
                "building": building.name,
                "prices_modifier": building.prices_modifier,
                "available_items": ["common fungi", "common herbs"],
            }

        return {
            "service": service,
            "building": building.name,
        }

    def _use_money_changer(self, building: Building, params: dict) -> dict[str, Any]:
        """
        Use money changer/banking services per Dolmenwood rules (p161).

        Banking services (towns and cities):
        - Money changing: 3% fee
        - Safe storage: Free if 1+ month, 10% fee otherwise
        - Loans: 10% interest per month, requires deposit of double value
        """
        service = params.get("service", "exchange")
        amount = params.get("amount", 0)
        duration_months = params.get("duration_months", 0)

        if service == "exchange":
            # 3% fee for exchanging coinage (p161)
            fee = amount * 0.03
            return {
                "service": "exchange",
                "building": building.name,
                "amount_exchanged": amount,
                "fee_gp": fee,
                "fee_rate": "3%",
                "result": f"Exchanged {amount}gp worth of coins (fee: {fee}gp)",
            }
        elif service == "storage":
            # Free if 1+ month, 10% otherwise (p161)
            if duration_months >= 1:
                fee = 0
                fee_note = "Free (1+ month storage)"
            else:
                fee = amount * 0.10
                fee_note = "10% fee (less than 1 month)"
            return {
                "service": "storage",
                "building": building.name,
                "amount_stored": amount,
                "duration_months": duration_months,
                "fee_gp": fee,
                "fee_note": fee_note,
                "token_provided": True,
            }
        elif service == "loan":
            # 10% interest per month, double value deposit required (p161)
            interest_per_month = amount * 0.10
            deposit_required = amount * 2
            return {
                "service": "loan",
                "building": building.name,
                "loan_amount": amount,
                "interest_rate": "10% per month",
                "interest_per_month_gp": interest_per_month,
                "deposit_required_gp": deposit_required,
                "deposit_note": "Item of double loan value required",
                "reduced_rate_available": "For high-level characters with land",
            }

        return {
            "service": service,
            "building": building.name,
        }

    def _use_jeweler(self, building: Building, params: dict) -> dict[str, Any]:
        """
        Use jeweler services per Dolmenwood rules (p161).

        Jewelers (towns and cities):
        - Buying gems/jewelry: 100% value (full price)
        - Selling gems/jewelry: 80% value
        - Valuation (optional): 3% fee
        """
        service = params.get("service", "sell")
        item_value = params.get("item_value", 0)

        if service == "sell":
            # Jewelers buy at 80% (p161)
            sell_value = item_value * 0.8
            return {
                "service": "sell",
                "building": building.name,
                "item_value": item_value,
                "sell_price_gp": sell_value,
                "sell_rate": "80%",
            }
        elif service == "buy":
            # Jewelers sell at 100% (p161)
            return {
                "service": "buy",
                "building": building.name,
                "prices": "full value",
                "available_items": ["gems", "jewelry", "art objects"],
            }
        elif service == "valuation":
            # 3% fee for appraisal (p161)
            fee = item_value * 0.03
            return {
                "service": "valuation",
                "building": building.name,
                "item_value": item_value,
                "fee_gp": fee,
                "fee_rate": "3%",
                "note": "Optional - PCs may appraise items themselves",
            }

        return {
            "service": service,
            "building": building.name,
        }

    def _use_generic_service(self, building: Building, params: dict) -> dict[str, Any]:
        """Generic service handler."""
        return {
            "service": "generic",
            "building": building.name,
            "available": True,
        }

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def get_current_settlement(self) -> Optional[Settlement]:
        """Get current settlement."""
        if self._current_settlement:
            return self._settlements.get(self._current_settlement)
        return None

    def get_active_conversation(self) -> Optional[ConversationState]:
        """Get active conversation state."""
        return self._conversation

    def get_settlement_summary(self) -> dict[str, Any]:
        """
        Get summary of current settlement state per Dolmenwood rules (p160-161).

        Includes lifestyle tracking and days spent in settlement.
        """
        if not self._current_settlement:
            return {"in_settlement": False}

        settlement = self._settlements.get(self._current_settlement)
        if not settlement:
            return {"in_settlement": True, "error": "Settlement data not found"}

        lifestyle_info = LIFESTYLE_DATA[self._current_lifestyle]

        return {
            "in_settlement": True,
            "settlement_id": settlement.settlement_id,
            "name": settlement.name,
            "size": settlement.size.value,
            "population": settlement.population,
            "available_services": [s.value for s in settlement.available_services],
            "buildings_count": len(settlement.buildings),
            "known_npcs": len(settlement.npcs),
            "active_conversation": self._conversation is not None,
            # Dolmenwood-specific tracking (p161)
            "current_lifestyle": self._current_lifestyle.value,
            "lifestyle_cost_sp_per_day": lifestyle_info["cost_per_day_sp"],
            "lifestyle_allows_healing": lifestyle_info["allows_healing"],
            "days_in_settlement": self._days_in_settlement,
        }
