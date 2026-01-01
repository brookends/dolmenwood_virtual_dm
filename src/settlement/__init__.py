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
]
