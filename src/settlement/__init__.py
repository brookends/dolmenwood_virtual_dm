"""Settlement exploration and social interaction engine module."""

from src.settlement.settlement_engine import SettlementEngine
from src.settlement.settlement_content_models import (
    SettlementData,
    SettlementLocationData,
    SettlementNPCData,
    SettlementServiceData,
    SettlementEncounterTable,
    SettlementEncounterEntry,
    SettlementEquipmentAvailability,
)
from src.settlement.settlement_registry import SettlementRegistry
from src.settlement.settlement_services import (
    SettlementServiceExecutor,
    ServiceUseResult,
    CostEstimate,
    parse_cost_text,
)
from src.settlement.settlement_encounters import (
    SettlementEncounterTables,
    SettlementEncounterResult,
    tod_to_daynight,
)
from src.settlement.settlement_actions import (
    SETTLEMENT_ACTIONS,
    Suggestion,
    build_settlement_suggestions,
)
from src.settlement.settlement_state_export import (
    SettlementEvent,
    SettlementEventBuffer,
    build_settlement_snapshot,
)
from src.settlement.settlement_encounter_adapter import (
    SettlementActorParser,
    SettlementEncounterAdapter,
    SettlementActorType,
    ParsedActor,
    SettlementEncounterConversion,
    SETTLEMENT_ACTOR_MAP,
    parse_settlement_actor,
    convert_settlement_encounter,
    get_settlement_encounter_adapter,
    get_settlement_actor_parser,
)
from src.settlement.carousing import (
    CarousingEngine,
    CarousingResult,
    CarousingOutcome,
    CarousingMishap,
    CarousingBonus,
    MishapSeverity,
    MAJOR_MISHAPS,
    MINOR_MISHAPS,
    CAROUSING_BONUSES,
    get_carousing_engine,
    reset_carousing_engine,
)

__all__ = [
    "SettlementEngine",
    # Content models
    "SettlementData",
    "SettlementLocationData",
    "SettlementNPCData",
    "SettlementServiceData",
    "SettlementEncounterTable",
    "SettlementEncounterEntry",
    "SettlementEquipmentAvailability",
    # Registry
    "SettlementRegistry",
    # Services
    "SettlementServiceExecutor",
    "ServiceUseResult",
    "CostEstimate",
    "parse_cost_text",
    # Encounters
    "SettlementEncounterTables",
    "SettlementEncounterResult",
    "tod_to_daynight",
    # Actions
    "SETTLEMENT_ACTIONS",
    "Suggestion",
    "build_settlement_suggestions",
    # State export
    "SettlementEvent",
    "SettlementEventBuffer",
    "build_settlement_snapshot",
    # Encounter adapter
    "SettlementActorParser",
    "SettlementEncounterAdapter",
    "SettlementActorType",
    "ParsedActor",
    "SettlementEncounterConversion",
    "SETTLEMENT_ACTOR_MAP",
    "parse_settlement_actor",
    "convert_settlement_encounter",
    "get_settlement_encounter_adapter",
    "get_settlement_actor_parser",
    # Carousing
    "CarousingEngine",
    "CarousingResult",
    "CarousingOutcome",
    "CarousingMishap",
    "CarousingBonus",
    "MishapSeverity",
    "MAJOR_MISHAPS",
    "MINOR_MISHAPS",
    "CAROUSING_BONUSES",
    "get_carousing_engine",
    "reset_carousing_engine",
]
