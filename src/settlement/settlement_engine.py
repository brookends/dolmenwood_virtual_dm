"""
Settlement Engine for Dolmenwood Virtual DM.

Handles settlement exploration, NPC interactions, and social encounters.
Manages services, shopping, rumors, and faction interactions.

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

from ..game_state.state_machine import GameState
from ..game_state.global_controller import GlobalController
from ..data_models import (
    DiceRoller,
    NPC,
    ReactionResult,
    LocationType,
    SourceReference,
)


logger = logging.getLogger(__name__)


class SettlementSize(str, Enum):
    """Size categories for settlements."""
    HAMLET = "hamlet"       # 50-200 inhabitants
    VILLAGE = "village"     # 200-1000 inhabitants
    TOWN = "town"           # 1000-5000 inhabitants
    CITY = "city"           # 5000+ inhabitants


class ServiceType(str, Enum):
    """Types of services available in settlements."""
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
    APOTHECARY = "apothecary"
    MONEYLENDER = "moneylender"
    HIRELING_HALL = "hireling_hall"


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
    Engine for settlement exploration and social interaction.

    Manages:
    - Settlement exploration
    - NPC conversations
    - Services and shopping
    - Rumors and information gathering
    - Faction interactions
    """

    def __init__(self, controller: GlobalController):
        """
        Initialize the settlement engine.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Settlement data
        self._settlements: dict[str, Settlement] = {}
        self._current_settlement: Optional[str] = None

        # NPC data
        self._npcs: dict[str, NPC] = {}

        # Active conversation
        self._conversation: Optional[ConversationState] = None

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
        self,
        settlement_id: str,
        settlement_data: Optional[Settlement] = None
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
        self.controller.transition("enter_settlement", context={
            "settlement_id": settlement_id,
            "settlement_name": settlement.name,
        })

        # Update party location
        self.controller.set_party_location(
            LocationType.SETTLEMENT,
            settlement_id
        )

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
            LocationType.BUILDING,
            building_id,
            sub_location=self._current_settlement
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
        self.controller.transition("initiate_conversation", context={
            "npc_id": npc_id,
            "npc_name": npc.name,
        })

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
        self,
        topic: ConversationTopic,
        player_approach: str = ""
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
            npc.interactions.append({
                "date": str(self.controller.world_state.current_date),
                "topics": [t.value for t in self._conversation.topics_discussed],
                "disposition_change": self._conversation.disposition - npc.disposition,
            })

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
        """Interpret 2d6 reaction roll."""
        if roll <= 2:
            return ReactionResult.HOSTILE
        elif roll <= 5:
            return ReactionResult.UNFRIENDLY
        elif roll <= 8:
            return ReactionResult.NEUTRAL
        elif roll <= 11:
            return ReactionResult.FRIENDLY
        else:
            return ReactionResult.HELPFUL

    def _reaction_to_disposition(self, reaction: ReactionResult) -> int:
        """Convert reaction to disposition score."""
        mapping = {
            ReactionResult.HOSTILE: -3,
            ReactionResult.UNFRIENDLY: -1,
            ReactionResult.NEUTRAL: 0,
            ReactionResult.FRIENDLY: 1,
            ReactionResult.HELPFUL: 3,
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
        parameters: Optional[dict[str, Any]] = None
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
        }

        handler = handlers.get(service_type, self._use_generic_service)
        return handler(building, parameters)

    def _use_inn(self, building: Building, params: dict) -> dict[str, Any]:
        """Use inn services (lodging)."""
        nights = params.get("nights", 1)
        room_type = params.get("room_type", "common")

        base_cost = {"common": 1, "private": 5, "suite": 20}
        cost = base_cost.get(room_type, 1) * nights * building.prices_modifier

        return {
            "service": "lodging",
            "building": building.name,
            "nights": nights,
            "room_type": room_type,
            "cost_gp": cost,
            "includes_meals": room_type != "common",
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
        """Use general store services."""
        return {
            "service": "shopping",
            "building": building.name,
            "prices_modifier": building.prices_modifier,
            "available_items": ["standard adventuring gear"],
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
        """Use hireling hall to find hirelings."""
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
        """Get summary of current settlement state."""
        if not self._current_settlement:
            return {"in_settlement": False}

        settlement = self._settlements.get(self._current_settlement)
        if not settlement:
            return {"in_settlement": True, "error": "Settlement data not found"}

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
        }
