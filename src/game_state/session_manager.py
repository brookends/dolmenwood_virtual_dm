"""
Session Manager for Dolmenwood Virtual DM.

Handles saving and loading game sessions while keeping base content data immutable.
Only session-specific changes (deltas) are persisted.

Architecture:
- Base Data Layer: Immutable hex/NPC/item definitions loaded from content files
- Session State: Mutable changes that occur during gameplay
- Deltas: Track only what changed from the base state

This ensures base content can be updated without breaking existing saves,
and saves remain small by only storing differences from defaults.
"""

from dataclasses import dataclass, field, asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json
import logging
import uuid

from src.data_models import (
    GameDate,
    GameTime,
    Season,
    Weather,
    Location,
    LocationType,
    CharacterState,
    PartyResources,
    Condition,
    ConditionType,
    LightSourceType,
    Item,
    Spell,
    EncumbranceSystem,
    ArmorWeight,
)

logger = logging.getLogger(__name__)


# =============================================================================
# STATE DELTA CLASSES
# These track changes to base data without modifying the originals
# =============================================================================


@dataclass
class POIStateDelta:
    """
    Tracks changes to a POI's mutable state.

    Only stores what changed from the base POI definition.
    """
    poi_name: str
    hex_id: str

    # Discovery state
    discovered: Optional[bool] = None  # None = unchanged from base

    # Alert state: {alert_index: triggered}
    triggered_alerts: dict[int, bool] = field(default_factory=dict)

    # Concealed items found: {item_index: found}
    found_concealed_items: dict[int, bool] = field(default_factory=dict)

    # Variable inhabitants roll result (cached for consistency)
    variable_inhabitants_roll: Optional[int] = None

    # Items taken from this POI
    items_taken: list[str] = field(default_factory=list)

    # Roll table entries found: {table_name: [roll_values found]}
    # For unique-item tables where entries can only be found once
    found_roll_table_entries: dict[str, list[int]] = field(default_factory=dict)

    # Custom state changes
    custom_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "poi_name": self.poi_name,
            "hex_id": self.hex_id,
            "discovered": self.discovered,
            "triggered_alerts": self.triggered_alerts,
            "found_concealed_items": self.found_concealed_items,
            "variable_inhabitants_roll": self.variable_inhabitants_roll,
            "items_taken": self.items_taken,
            "found_roll_table_entries": self.found_roll_table_entries,
            "custom_state": self.custom_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "POIStateDelta":
        """Deserialize from dictionary."""
        return cls(
            poi_name=data["poi_name"],
            hex_id=data["hex_id"],
            discovered=data.get("discovered"),
            triggered_alerts={int(k): v for k, v in data.get("triggered_alerts", {}).items()},
            found_concealed_items={int(k): v for k, v in data.get("found_concealed_items", {}).items()},
            variable_inhabitants_roll=data.get("variable_inhabitants_roll"),
            items_taken=data.get("items_taken", []),
            found_roll_table_entries=data.get("found_roll_table_entries", {}),
            custom_state=data.get("custom_state", {}),
        )


@dataclass
class NPCStateDelta:
    """
    Tracks changes to an NPC's state during the session.
    """
    npc_id: str
    hex_id: str

    # Relationship with party
    disposition: Optional[str] = None  # friendly, neutral, hostile

    # State changes
    is_dead: bool = False
    is_hostile: bool = False

    # Quest state
    quests_given: list[str] = field(default_factory=list)
    quests_completed: list[str] = field(default_factory=list)

    # Conversation flags
    topics_discussed: list[str] = field(default_factory=list)
    secrets_revealed: list[str] = field(default_factory=list)

    # Custom state
    custom_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "npc_id": self.npc_id,
            "hex_id": self.hex_id,
            "disposition": self.disposition,
            "is_dead": self.is_dead,
            "is_hostile": self.is_hostile,
            "quests_given": self.quests_given,
            "quests_completed": self.quests_completed,
            "topics_discussed": self.topics_discussed,
            "secrets_revealed": self.secrets_revealed,
            "custom_state": self.custom_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NPCStateDelta":
        return cls(
            npc_id=data["npc_id"],
            hex_id=data["hex_id"],
            disposition=data.get("disposition"),
            is_dead=data.get("is_dead", False),
            is_hostile=data.get("is_hostile", False),
            quests_given=data.get("quests_given", []),
            quests_completed=data.get("quests_completed", []),
            topics_discussed=data.get("topics_discussed", []),
            secrets_revealed=data.get("secrets_revealed", []),
            custom_state=data.get("custom_state", {}),
        )


@dataclass
class HexStateDelta:
    """
    Tracks changes to a hex's state during the session.
    """
    hex_id: str

    # Exploration state
    explored: bool = False

    # POI deltas
    poi_deltas: dict[str, POIStateDelta] = field(default_factory=dict)

    # NPC deltas
    npc_deltas: dict[str, NPCStateDelta] = field(default_factory=dict)

    # Discovered secrets in this hex
    discovered_secrets: list[str] = field(default_factory=list)

    # Items taken from hex-level (not POI-specific)
    items_taken: list[str] = field(default_factory=list)

    # Encounters that have occurred (to prevent re-triggering one-time encounters)
    triggered_encounters: list[str] = field(default_factory=list)

    # Custom hex state
    custom_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hex_id": self.hex_id,
            "explored": self.explored,
            "poi_deltas": {k: v.to_dict() for k, v in self.poi_deltas.items()},
            "npc_deltas": {k: v.to_dict() for k, v in self.npc_deltas.items()},
            "discovered_secrets": self.discovered_secrets,
            "items_taken": self.items_taken,
            "triggered_encounters": self.triggered_encounters,
            "custom_state": self.custom_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HexStateDelta":
        return cls(
            hex_id=data["hex_id"],
            explored=data.get("explored", False),
            poi_deltas={
                k: POIStateDelta.from_dict(v)
                for k, v in data.get("poi_deltas", {}).items()
            },
            npc_deltas={
                k: NPCStateDelta.from_dict(v)
                for k, v in data.get("npc_deltas", {}).items()
            },
            discovered_secrets=data.get("discovered_secrets", []),
            items_taken=data.get("items_taken", []),
            triggered_encounters=data.get("triggered_encounters", []),
            custom_state=data.get("custom_state", {}),
        )


# =============================================================================
# SERIALIZABLE STATE CLASSES
# =============================================================================


@dataclass
class SerializableCharacter:
    """
    Serializable version of character state.

    Properly handles Item serialization with all unique item fields.
    """
    character_id: str
    name: str
    character_class: str
    level: int
    hp_max: int
    hp_current: int
    armor_class: int
    base_speed: int = 40  # Base Speed in feet (p146)

    # Abilities (stored as dict for compatibility with CharacterState)
    ability_scores: dict[str, int] = field(default_factory=lambda: {
        "STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10
    })

    # Equipment and resources - Items serialized with all fields
    inventory: list[dict[str, Any]] = field(default_factory=list)

    # Spells
    spells: list[dict[str, Any]] = field(default_factory=list)

    # Conditions (with extended fields for dreamlessness, etc.)
    conditions: list[dict[str, Any]] = field(default_factory=list)

    # Retainer info
    morale: Optional[int] = None
    is_retainer: bool = False
    employer_id: Optional[str] = None

    # Encumbrance settings
    encumbrance_system: str = "weight"
    armor_weight: str = "unarmoured"

    # Kindred (race) information
    kindred: str = "human"
    gender: Optional[str] = None
    age: int = 0
    height_inches: int = 0
    weight_lbs: int = 0

    # Kindred aspects (background, trinket, head, demeanour, etc.)
    aspects: dict[str, str] = field(default_factory=dict)

    # Active kindred ability IDs
    kindred_abilities: list[str] = field(default_factory=list)

    # Languages known
    languages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SerializableCharacter":
        # Handle legacy format with individual ability scores
        if "strength" in data and "ability_scores" not in data:
            data["ability_scores"] = {
                "STR": data.pop("strength", 10),
                "DEX": data.pop("dexterity", 10),
                "CON": data.pop("constitution", 10),
                "INT": data.pop("intelligence", 10),
                "WIS": data.pop("wisdom", 10),
                "CHA": data.pop("charisma", 10),
            }
        # Remove any legacy fields not in dataclass
        known_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)

    @classmethod
    def from_character_state(cls, char: CharacterState) -> "SerializableCharacter":
        """Convert from CharacterState to serializable form."""
        # Serialize inventory items using Item.to_dict()
        serialized_inventory = []
        for item in char.inventory:
            if hasattr(item, 'to_dict'):
                serialized_inventory.append(item.to_dict())
            elif hasattr(item, '__dataclass_fields__'):
                serialized_inventory.append(asdict(item))
            else:
                serialized_inventory.append(item)

        # Serialize spells
        serialized_spells = []
        for spell in char.spells:
            if hasattr(spell, '__dataclass_fields__'):
                serialized_spells.append(asdict(spell))
            else:
                serialized_spells.append(spell)

        # Serialize conditions with all extended fields
        serialized_conditions = []
        for c in char.conditions:
            cond_dict = {
                "condition_type": c.condition_type.value,
                "duration_turns": c.duration_turns,
                "source": c.source,
                "severity": c.severity,
                "duration_days": c.duration_days,
                "days_elapsed": c.days_elapsed,
                "periodic_effect": c.periodic_effect,
                "recovery_condition": c.recovery_condition,
                "recovery_rate": c.recovery_rate,
                "spell_effects": c.spell_effects,
                "threshold_effect": c.threshold_effect,
            }
            serialized_conditions.append(cond_dict)

        return cls(
            character_id=char.character_id,
            name=char.name,
            character_class=char.character_class,
            level=char.level,
            hp_max=char.hp_max,
            hp_current=char.hp_current,
            armor_class=char.armor_class,
            base_speed=char.base_speed,
            ability_scores=char.ability_scores.copy(),
            inventory=serialized_inventory,
            spells=serialized_spells,
            conditions=serialized_conditions,
            morale=char.morale,
            is_retainer=char.is_retainer,
            employer_id=char.employer_id,
            encumbrance_system=char.encumbrance_system.value if hasattr(char.encumbrance_system, 'value') else str(char.encumbrance_system),
            armor_weight=char.armor_weight.value if hasattr(char.armor_weight, 'value') else str(char.armor_weight),
            # Kindred fields
            kindred=char.kindred,
            gender=char.gender,
            age=char.age,
            height_inches=char.height_inches,
            weight_lbs=char.weight_lbs,
            aspects=char.aspects.copy() if char.aspects else {},
            kindred_abilities=list(char.kindred_abilities) if char.kindred_abilities else [],
            languages=list(char.languages) if char.languages else [],
        )

    def to_character_state(self) -> CharacterState:
        """Convert back to CharacterState with proper Item objects."""
        # Deserialize inventory items using Item.from_dict()
        inventory_items = []
        for item_data in self.inventory:
            if isinstance(item_data, dict):
                inventory_items.append(Item.from_dict(item_data))
            else:
                inventory_items.append(item_data)

        # Deserialize spells
        spell_objects = []
        for spell_data in self.spells:
            if isinstance(spell_data, dict):
                spell_objects.append(Spell(
                    spell_id=spell_data.get("spell_id", ""),
                    name=spell_data.get("name", ""),
                    level=spell_data.get("level", 1),
                    prepared=spell_data.get("prepared", True),
                    cast_today=spell_data.get("cast_today", False),
                ))
            else:
                spell_objects.append(spell_data)

        # Deserialize conditions with extended fields
        condition_objects = []
        for c in self.conditions:
            if isinstance(c, dict):
                condition_objects.append(Condition(
                    condition_type=ConditionType(c.get("condition_type", c.get("type", "exhausted"))),
                    duration_turns=c.get("duration_turns", c.get("duration")),
                    source=c.get("source", ""),
                    severity=c.get("severity", 1),
                    duration_days=c.get("duration_days"),
                    days_elapsed=c.get("days_elapsed", 0),
                    periodic_effect=c.get("periodic_effect"),
                    recovery_condition=c.get("recovery_condition"),
                    recovery_rate=c.get("recovery_rate"),
                    spell_effects=c.get("spell_effects"),
                    threshold_effect=c.get("threshold_effect"),
                ))
            else:
                condition_objects.append(c)

        # Parse encumbrance system
        try:
            enc_system = EncumbranceSystem(self.encumbrance_system)
        except (ValueError, KeyError):
            enc_system = EncumbranceSystem.WEIGHT

        # Parse armor weight
        try:
            arm_weight = ArmorWeight(self.armor_weight)
        except (ValueError, KeyError):
            arm_weight = ArmorWeight.UNARMOURED

        return CharacterState(
            character_id=self.character_id,
            name=self.name,
            character_class=self.character_class,
            level=self.level,
            hp_max=self.hp_max,
            hp_current=self.hp_current,
            armor_class=self.armor_class,
            base_speed=self.base_speed,
            ability_scores=self.ability_scores.copy(),
            inventory=inventory_items,
            spells=spell_objects,
            conditions=condition_objects,
            morale=self.morale,
            is_retainer=self.is_retainer,
            employer_id=self.employer_id,
            encumbrance_system=enc_system,
            armor_weight=arm_weight,
            # Kindred fields
            kindred=self.kindred,
            gender=self.gender,
            age=self.age,
            height_inches=self.height_inches,
            weight_lbs=self.weight_lbs,
            aspects=self.aspects.copy() if self.aspects else {},
            kindred_abilities=list(self.kindred_abilities) if self.kindred_abilities else [],
            languages=list(self.languages) if self.languages else [],
        )


@dataclass
class SerializablePartyState:
    """Serializable version of party state."""
    # Location
    location_type: str
    location_id: str
    location_name: Optional[str] = None

    # Party composition
    marching_order: list[str] = field(default_factory=list)

    # Resources
    food_days: float = 0.0
    water_days: float = 0.0
    torches: int = 0
    lantern_oil_flasks: int = 0
    ammunition: dict[str, int] = field(default_factory=dict)

    # Light
    active_light_source: Optional[str] = None
    light_remaining_turns: int = 0

    # Conditions affecting whole party
    party_conditions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SerializablePartyState":
        return cls(**data)


@dataclass
class SerializableWorldState:
    """Serializable version of world state."""
    # Time
    year: int
    month: int
    day: int
    hour: int
    minute: int

    # Environment
    season: str
    weather: str

    # Global flags
    global_flags: dict[str, Any] = field(default_factory=dict)

    # Cleared locations
    cleared_locations: list[str] = field(default_factory=list)

    # Active adventure/campaign state
    active_adventure: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SerializableWorldState":
        return cls(**data)


@dataclass
class SerializableScheduledEvent:
    """Serializable version of a scheduled event."""
    event_id: str
    event_type: str

    # When created
    created_year: int
    created_month: int
    created_day: int

    # Source
    source_hex_id: Optional[str] = None
    source_poi_name: Optional[str] = None

    # Trigger
    trigger_condition: Optional[str] = None
    trigger_year: Optional[int] = None
    trigger_month: Optional[int] = None
    trigger_day: Optional[int] = None

    # Details
    title: str = ""
    description: str = ""
    player_message: str = ""
    effect_type: str = ""
    effect_details: dict[str, Any] = field(default_factory=dict)

    # State
    triggered: bool = False
    expired: bool = False
    character_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SerializableScheduledEvent":
        return cls(**data)


@dataclass
class SerializableGrantedAbility:
    """Serializable version of a granted ability."""
    grant_id: str
    character_id: str
    ability_name: str
    ability_type: str
    description: str

    # Source
    source_hex_id: str = ""
    source_poi_name: Optional[str] = None

    # Duration
    duration: str = "permanent"
    uses_remaining: Optional[int] = None

    # Granted date
    granted_year: int = 1
    granted_month: int = 1
    granted_day: int = 1

    # State
    is_active: bool = True
    used: bool = False

    # Spell details (if applicable)
    spell_level: Optional[int] = None
    spell_school: Optional[str] = None
    spell_data: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SerializableGrantedAbility":
        return cls(**data)


@dataclass
class SerializableWorldChange:
    """Serializable version of a world state change."""
    change_id: str
    hex_id: str
    poi_name: Optional[str]

    trigger_action: str
    trigger_details: dict[str, Any]
    change_type: str

    before_state: dict[str, Any]
    after_state: dict[str, Any]
    narrative_description: str

    # When it occurred
    occurred_year: int
    occurred_month: int
    occurred_day: int

    reversible: bool = False
    reverse_condition: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SerializableWorldChange":
        return cls(**data)


# =============================================================================
# MAIN GAME SESSION CLASS
# =============================================================================


@dataclass
class GameSession:
    """
    Complete game session state.

    This captures everything needed to save and restore a game,
    while keeping base content data immutable.
    """
    # Session metadata
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_name: str = "Untitled Session"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_saved_at: Optional[str] = None
    version: str = "1.0.0"

    # World state
    world_state: Optional[SerializableWorldState] = None

    # Party state
    party_state: Optional[SerializablePartyState] = None

    # Characters
    characters: list[SerializableCharacter] = field(default_factory=list)

    # Hex exploration deltas (changes from base data)
    hex_deltas: dict[str, HexStateDelta] = field(default_factory=dict)

    # Global exploration state
    explored_hexes: list[str] = field(default_factory=list)
    discovered_secrets: list[str] = field(default_factory=list)
    met_npcs: list[str] = field(default_factory=list)

    # Scheduled events
    scheduled_events: list[SerializableScheduledEvent] = field(default_factory=list)

    # Granted abilities
    granted_abilities: list[SerializableGrantedAbility] = field(default_factory=list)

    # World changes (permanent mutations)
    world_changes: list[SerializableWorldChange] = field(default_factory=list)

    # Completed quests
    completed_quests: list[str] = field(default_factory=list)

    # POI visit tracking
    poi_visits: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Unique item registry - tracks unique items acquired to prevent duplicates
    # Format: {unique_item_id: {name, acquired_by, acquired_at_hex, acquired_at_poi, acquired_date}}
    unique_items_acquired: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Materialized item properties - stores generated random properties for template magic items
    # Format: {unique_item_id: {enchantment_type, special_powers, oddities, appearance, ...}}
    # When a template item is first encountered, its random properties are rolled and stored here
    # to ensure consistency if the same item is encountered again (e.g., after save/load)
    materialized_items: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Custom session data (for extensions)
    custom_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize entire session to dictionary."""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "created_at": self.created_at,
            "last_saved_at": self.last_saved_at,
            "version": self.version,
            "world_state": self.world_state.to_dict() if self.world_state else None,
            "party_state": self.party_state.to_dict() if self.party_state else None,
            "characters": [c.to_dict() for c in self.characters],
            "hex_deltas": {k: v.to_dict() for k, v in self.hex_deltas.items()},
            "explored_hexes": self.explored_hexes,
            "discovered_secrets": self.discovered_secrets,
            "met_npcs": self.met_npcs,
            "scheduled_events": [e.to_dict() for e in self.scheduled_events],
            "granted_abilities": [a.to_dict() for a in self.granted_abilities],
            "world_changes": [c.to_dict() for c in self.world_changes],
            "completed_quests": self.completed_quests,
            "poi_visits": self.poi_visits,
            "unique_items_acquired": self.unique_items_acquired,
            "materialized_items": self.materialized_items,
            "custom_data": self.custom_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameSession":
        """Deserialize from dictionary."""
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            session_name=data.get("session_name", "Untitled Session"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_saved_at=data.get("last_saved_at"),
            version=data.get("version", "1.0.0"),
            world_state=SerializableWorldState.from_dict(data["world_state"]) if data.get("world_state") else None,
            party_state=SerializablePartyState.from_dict(data["party_state"]) if data.get("party_state") else None,
            characters=[SerializableCharacter.from_dict(c) for c in data.get("characters", [])],
            hex_deltas={k: HexStateDelta.from_dict(v) for k, v in data.get("hex_deltas", {}).items()},
            explored_hexes=data.get("explored_hexes", []),
            discovered_secrets=data.get("discovered_secrets", []),
            met_npcs=data.get("met_npcs", []),
            scheduled_events=[SerializableScheduledEvent.from_dict(e) for e in data.get("scheduled_events", [])],
            granted_abilities=[SerializableGrantedAbility.from_dict(a) for a in data.get("granted_abilities", [])],
            world_changes=[SerializableWorldChange.from_dict(c) for c in data.get("world_changes", [])],
            completed_quests=data.get("completed_quests", []),
            poi_visits=data.get("poi_visits", {}),
            unique_items_acquired=data.get("unique_items_acquired", {}),
            materialized_items=data.get("materialized_items", {}),
            custom_data=data.get("custom_data", {}),
        )

    def get_materialized_properties(self, unique_item_id: str) -> Optional[dict[str, Any]]:
        """
        Get previously materialized properties for an item.

        Args:
            unique_item_id: The unique identifier for the item

        Returns:
            Dict of materialized properties, or None if not yet materialized
        """
        return self.materialized_items.get(unique_item_id)

    def store_materialized_properties(
        self,
        unique_item_id: str,
        properties: dict[str, Any],
    ) -> None:
        """
        Store materialized properties for an item.

        Args:
            unique_item_id: The unique identifier for the item
            properties: The generated properties to store
        """
        self.materialized_items[unique_item_id] = properties

    def is_item_materialized(self, unique_item_id: str) -> bool:
        """Check if an item has already been materialized."""
        return unique_item_id in self.materialized_items


# =============================================================================
# SESSION MANAGER
# =============================================================================


class SessionManager:
    """
    Manages game session save/load operations.

    Handles:
    - Saving sessions to JSON files
    - Loading sessions from JSON files
    - Listing available sessions
    - Applying session deltas to base data
    - Extracting session state from running game
    """

    def __init__(self, save_directory: Optional[Path] = None):
        """
        Initialize the session manager.

        Args:
            save_directory: Directory for save files. Defaults to ./saves/
        """
        self.save_directory = save_directory or Path("./saves")
        self.save_directory.mkdir(parents=True, exist_ok=True)
        self._current_session: Optional[GameSession] = None

    @property
    def current_session(self) -> Optional[GameSession]:
        """Get the currently loaded session."""
        return self._current_session

    def new_session(self, session_name: str = "New Adventure") -> GameSession:
        """
        Create a new game session.

        Args:
            session_name: Name for the session

        Returns:
            New GameSession instance
        """
        session = GameSession(session_name=session_name)
        self._current_session = session
        logger.info(f"Created new session: {session.session_id}")
        return session

    def save_session(
        self,
        session: Optional[GameSession] = None,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Save a session to a JSON file.

        Args:
            session: Session to save (defaults to current session)
            filename: Custom filename (defaults to session_id.json)

        Returns:
            Path to the saved file
        """
        session = session or self._current_session
        if not session:
            raise ValueError("No session to save")

        # Update last saved timestamp
        session.last_saved_at = datetime.now().isoformat()

        # Determine filename
        if filename is None:
            # Sanitize session name for filename
            safe_name = "".join(c for c in session.session_name if c.isalnum() or c in " -_")
            filename = f"{safe_name}_{session.session_id[:8]}.json"

        filepath = self.save_directory / filename

        # Serialize and save
        data = session.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved session to: {filepath}")
        return filepath

    def load_session(self, filepath: Path | str) -> GameSession:
        """
        Load a session from a JSON file.

        Args:
            filepath: Path to the save file

        Returns:
            Loaded GameSession
        """
        filepath = Path(filepath)
        if not filepath.exists():
            # Try relative to save directory
            filepath = self.save_directory / filepath

        if not filepath.exists():
            raise FileNotFoundError(f"Save file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        session = GameSession.from_dict(data)
        self._current_session = session

        logger.info(f"Loaded session: {session.session_name} ({session.session_id})")
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all available save files.

        Returns:
            List of session metadata dictionaries
        """
        sessions = []

        for filepath in self.save_directory.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                sessions.append({
                    "filepath": str(filepath),
                    "filename": filepath.name,
                    "session_id": data.get("session_id", "unknown"),
                    "session_name": data.get("session_name", "Untitled"),
                    "created_at": data.get("created_at"),
                    "last_saved_at": data.get("last_saved_at"),
                    "version": data.get("version", "unknown"),
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Could not read save file {filepath}: {e}")

        # Sort by last saved date, most recent first
        sessions.sort(
            key=lambda s: s.get("last_saved_at") or s.get("created_at") or "",
            reverse=True
        )

        return sessions

    def delete_session(self, filepath: Path | str) -> bool:
        """
        Delete a save file.

        Args:
            filepath: Path to the save file

        Returns:
            True if deleted successfully
        """
        filepath = Path(filepath)
        if not filepath.exists():
            filepath = self.save_directory / filepath

        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted save file: {filepath}")
            return True
        return False

    def get_hex_delta(self, hex_id: str) -> HexStateDelta:
        """
        Get or create a hex state delta.

        Args:
            hex_id: The hex ID

        Returns:
            HexStateDelta for this hex
        """
        if not self._current_session:
            raise ValueError("No active session")

        if hex_id not in self._current_session.hex_deltas:
            self._current_session.hex_deltas[hex_id] = HexStateDelta(hex_id=hex_id)

        return self._current_session.hex_deltas[hex_id]

    def get_poi_delta(self, hex_id: str, poi_name: str) -> POIStateDelta:
        """
        Get or create a POI state delta.

        Args:
            hex_id: The hex ID
            poi_name: The POI name

        Returns:
            POIStateDelta for this POI
        """
        hex_delta = self.get_hex_delta(hex_id)

        if poi_name not in hex_delta.poi_deltas:
            hex_delta.poi_deltas[poi_name] = POIStateDelta(
                poi_name=poi_name,
                hex_id=hex_id,
            )

        return hex_delta.poi_deltas[poi_name]

    def get_npc_delta(self, hex_id: str, npc_id: str) -> NPCStateDelta:
        """
        Get or create an NPC state delta.

        Args:
            hex_id: The hex ID
            npc_id: The NPC ID

        Returns:
            NPCStateDelta for this NPC
        """
        hex_delta = self.get_hex_delta(hex_id)

        if npc_id not in hex_delta.npc_deltas:
            hex_delta.npc_deltas[npc_id] = NPCStateDelta(
                npc_id=npc_id,
                hex_id=hex_id,
            )

        return hex_delta.npc_deltas[npc_id]

    def mark_poi_discovered(self, hex_id: str, poi_name: str) -> None:
        """Mark a POI as discovered."""
        delta = self.get_poi_delta(hex_id, poi_name)
        delta.discovered = True

    def mark_alert_triggered(self, hex_id: str, poi_name: str, alert_index: int) -> None:
        """Mark an alert as triggered."""
        delta = self.get_poi_delta(hex_id, poi_name)
        delta.triggered_alerts[alert_index] = True

    def mark_concealed_item_found(self, hex_id: str, poi_name: str, item_index: int) -> None:
        """Mark a concealed item as found."""
        delta = self.get_poi_delta(hex_id, poi_name)
        delta.found_concealed_items[item_index] = True

    def add_item_taken(self, hex_id: str, poi_name: str, item_name: str) -> None:
        """Record that an item was taken from a POI."""
        delta = self.get_poi_delta(hex_id, poi_name)
        if item_name not in delta.items_taken:
            delta.items_taken.append(item_name)

    def get_items_taken_from_poi(self, hex_id: str, poi_name: str) -> list[str]:
        """
        Get list of items that have been taken from a POI.

        Args:
            hex_id: The hex ID
            poi_name: The POI name

        Returns:
            List of item names that have been taken
        """
        if not self._current_session:
            return []

        hex_delta = self._current_session.hex_deltas.get(hex_id)
        if not hex_delta:
            return []

        poi_delta = hex_delta.poi_deltas.get(poi_name)
        if not poi_delta:
            return []

        return poi_delta.items_taken.copy()

    def is_item_taken_from_poi(
        self,
        hex_id: str,
        poi_name: str,
        item_name: str,
    ) -> bool:
        """
        Check if a specific item has been taken from a POI.

        Args:
            hex_id: The hex ID
            poi_name: The POI name
            item_name: Name of the item to check

        Returns:
            True if the item has been taken
        """
        taken_items = self.get_items_taken_from_poi(hex_id, poi_name)
        return item_name in taken_items

    def mark_roll_table_entry_found(
        self,
        hex_id: str,
        poi_name: str,
        table_name: str,
        roll_value: int,
    ) -> None:
        """
        Mark a roll table entry as found (for unique-item tables).

        Args:
            hex_id: The hex ID
            poi_name: The POI name
            table_name: Name of the roll table
            roll_value: The roll value that was found
        """
        delta = self.get_poi_delta(hex_id, poi_name)
        if table_name not in delta.found_roll_table_entries:
            delta.found_roll_table_entries[table_name] = []
        if roll_value not in delta.found_roll_table_entries[table_name]:
            delta.found_roll_table_entries[table_name].append(roll_value)

    def is_roll_table_entry_found(
        self,
        hex_id: str,
        poi_name: str,
        table_name: str,
        roll_value: int,
    ) -> bool:
        """
        Check if a roll table entry has been found.

        Args:
            hex_id: The hex ID
            poi_name: The POI name
            table_name: Name of the roll table
            roll_value: The roll value to check

        Returns:
            True if this entry has been found, False otherwise
        """
        if not self._current_session:
            return False

        hex_delta = self._current_session.hex_deltas.get(hex_id)
        if not hex_delta:
            return False

        poi_delta = hex_delta.poi_deltas.get(poi_name)
        if not poi_delta:
            return False

        found_entries = poi_delta.found_roll_table_entries.get(table_name, [])
        return roll_value in found_entries

    def get_unfound_roll_table_entries(
        self,
        hex_id: str,
        poi_name: str,
        table_name: str,
        all_roll_values: list[int],
    ) -> list[int]:
        """
        Get roll values that haven't been found yet.

        Args:
            hex_id: The hex ID
            poi_name: The POI name
            table_name: Name of the roll table
            all_roll_values: All possible roll values in the table

        Returns:
            List of roll values not yet found
        """
        if not self._current_session:
            return all_roll_values

        hex_delta = self._current_session.hex_deltas.get(hex_id)
        if not hex_delta:
            return all_roll_values

        poi_delta = hex_delta.poi_deltas.get(poi_name)
        if not poi_delta:
            return all_roll_values

        found_entries = poi_delta.found_roll_table_entries.get(table_name, [])
        return [v for v in all_roll_values if v not in found_entries]

    def mark_hex_explored(self, hex_id: str) -> None:
        """Mark a hex as explored."""
        if not self._current_session:
            return

        delta = self.get_hex_delta(hex_id)
        delta.explored = True

        if hex_id not in self._current_session.explored_hexes:
            self._current_session.explored_hexes.append(hex_id)

    def add_discovered_secret(self, secret_id: str, hex_id: Optional[str] = None) -> None:
        """Record a discovered secret."""
        if not self._current_session:
            return

        if secret_id not in self._current_session.discovered_secrets:
            self._current_session.discovered_secrets.append(secret_id)

        if hex_id:
            delta = self.get_hex_delta(hex_id)
            if secret_id not in delta.discovered_secrets:
                delta.discovered_secrets.append(secret_id)

    def mark_npc_met(self, npc_id: str) -> None:
        """Record that an NPC has been met."""
        if not self._current_session:
            return

        if npc_id not in self._current_session.met_npcs:
            self._current_session.met_npcs.append(npc_id)

    def complete_quest(self, quest_id: str) -> None:
        """Mark a quest as completed."""
        if not self._current_session:
            return

        if quest_id not in self._current_session.completed_quests:
            self._current_session.completed_quests.append(quest_id)

    # =========================================================================
    # UNIQUE ITEM REGISTRY
    # =========================================================================

    def is_unique_item_acquired(self, unique_item_id: str) -> bool:
        """
        Check if a unique item has already been acquired.

        Args:
            unique_item_id: The unique identifier for the item

        Returns:
            True if the item has been acquired, False otherwise
        """
        if not self._current_session:
            return False
        return unique_item_id in self._current_session.unique_items_acquired

    def register_unique_item(
        self,
        unique_item_id: str,
        item_name: str,
        acquired_by: str,
        hex_id: Optional[str] = None,
        poi_name: Optional[str] = None,
    ) -> bool:
        """
        Register a unique item as acquired.

        Args:
            unique_item_id: The unique identifier for the item
            item_name: Display name of the item
            acquired_by: Character ID who acquired the item
            hex_id: Hex where item was acquired
            poi_name: POI where item was acquired

        Returns:
            True if registration succeeded, False if item was already acquired
        """
        if not self._current_session:
            return False

        if unique_item_id in self._current_session.unique_items_acquired:
            return False  # Already acquired

        self._current_session.unique_items_acquired[unique_item_id] = {
            "name": item_name,
            "acquired_by": acquired_by,
            "acquired_at_hex": hex_id,
            "acquired_at_poi": poi_name,
            "acquired_date": datetime.now().isoformat(),
        }
        return True

    def get_unique_item_info(self, unique_item_id: str) -> Optional[dict[str, Any]]:
        """
        Get information about an acquired unique item.

        Args:
            unique_item_id: The unique identifier for the item

        Returns:
            Dictionary with item info or None if not acquired
        """
        if not self._current_session:
            return None
        return self._current_session.unique_items_acquired.get(unique_item_id)

    def get_unique_item_owner(self, unique_item_id: str) -> Optional[str]:
        """
        Get the character ID of who owns a unique item.

        Args:
            unique_item_id: The unique identifier for the item

        Returns:
            Character ID or None if item not acquired
        """
        info = self.get_unique_item_info(unique_item_id)
        return info.get("acquired_by") if info else None

    def transfer_unique_item(
        self,
        unique_item_id: str,
        new_owner: str,
    ) -> bool:
        """
        Transfer ownership of a unique item to another character.

        Args:
            unique_item_id: The unique identifier for the item
            new_owner: Character ID of new owner

        Returns:
            True if transfer succeeded, False if item not found
        """
        if not self._current_session:
            return False

        if unique_item_id not in self._current_session.unique_items_acquired:
            return False

        self._current_session.unique_items_acquired[unique_item_id]["acquired_by"] = new_owner
        return True

    def remove_unique_item_from_world(self, unique_item_id: str) -> bool:
        """
        Remove a unique item from the registry (e.g., if destroyed or consumed).

        Note: This allows the item to potentially be found again if it respawns.
        For permanent removal, keep it in the registry with a "destroyed" flag.

        Args:
            unique_item_id: The unique identifier for the item

        Returns:
            True if removal succeeded, False if item not found
        """
        if not self._current_session:
            return False

        if unique_item_id in self._current_session.unique_items_acquired:
            del self._current_session.unique_items_acquired[unique_item_id]
            return True
        return False

    def get_all_unique_items(self) -> dict[str, dict[str, Any]]:
        """
        Get all acquired unique items.

        Returns:
            Dictionary mapping unique_item_id to item info
        """
        if not self._current_session:
            return {}
        return self._current_session.unique_items_acquired.copy()

    def get_unique_items_by_owner(self, character_id: str) -> list[str]:
        """
        Get all unique items owned by a specific character.

        Args:
            character_id: The character's ID

        Returns:
            List of unique_item_ids owned by the character
        """
        if not self._current_session:
            return []

        return [
            uid for uid, info in self._current_session.unique_items_acquired.items()
            if info.get("acquired_by") == character_id
        ]

    # =========================================================================
    # STATE EXTRACTION (from running game)
    # =========================================================================

    def extract_world_state(self, world_state: Any) -> SerializableWorldState:
        """
        Extract world state from a WorldState object.

        Args:
            world_state: WorldState from the game

        Returns:
            Serializable world state
        """
        return SerializableWorldState(
            year=world_state.current_date.year,
            month=world_state.current_date.month,
            day=world_state.current_date.day,
            hour=world_state.current_time.hour,
            minute=world_state.current_time.minute,
            season=world_state.season.value,
            weather=world_state.weather.value if hasattr(world_state.weather, 'value') else str(world_state.weather),
            global_flags=world_state.global_flags.copy(),
            cleared_locations=list(world_state.cleared_locations),
            active_adventure=world_state.active_adventure,
        )

    def extract_party_state(self, party_state: Any) -> SerializablePartyState:
        """
        Extract party state from a PartyState object.

        Args:
            party_state: PartyState from the game

        Returns:
            Serializable party state
        """
        return SerializablePartyState(
            location_type=party_state.location.location_type.value,
            location_id=party_state.location.location_id,
            location_name=party_state.location.name,
            marching_order=party_state.marching_order.copy(),
            food_days=party_state.resources.food_days,
            water_days=party_state.resources.water_days,
            torches=party_state.resources.torches,
            lantern_oil_flasks=party_state.resources.lantern_oil_flasks,
            ammunition=party_state.resources.ammunition.copy(),
            active_light_source=party_state.active_light_source.value if party_state.active_light_source else None,
            light_remaining_turns=party_state.light_remaining_turns,
            party_conditions=[
                {"type": c.condition_type.value, "duration": c.duration_remaining}
                for c in party_state.active_conditions
            ],
        )

    def extract_characters(self, characters: list) -> list[SerializableCharacter]:
        """
        Extract character states.

        Args:
            characters: List of CharacterState objects

        Returns:
            List of serializable characters
        """
        return [SerializableCharacter.from_character_state(c) for c in characters]

    def extract_hex_crawl_state(self, engine: Any) -> None:
        """
        Extract state from the HexCrawlEngine.

        Args:
            engine: HexCrawlEngine instance
        """
        if not self._current_session:
            return

        # Explored hexes
        self._current_session.explored_hexes = list(engine._explored_hexes)

        # Discovered secrets
        self._current_session.discovered_secrets = list(engine._discovered_secrets)

        # Met NPCs
        self._current_session.met_npcs = list(engine._met_npcs)

        # POI visits
        for key, visit in engine._poi_visits.items():
            self._current_session.poi_visits[key] = {
                "poi_name": visit.poi_name,
                "entered": visit.entered,
                "items_taken": visit.items_taken.copy(),
                "rooms_explored": visit.rooms_explored.copy(),
            }

        # World changes
        for change in engine._world_state_changes.changes:
            serialized = SerializableWorldChange(
                change_id=change.change_id,
                hex_id=change.hex_id,
                poi_name=change.poi_name,
                trigger_action=change.trigger_action,
                trigger_details=change.trigger_details.copy(),
                change_type=change.change_type,
                before_state=change.before_state.copy(),
                after_state=change.after_state.copy(),
                narrative_description=change.narrative_description,
                occurred_year=change.occurred_at.year if change.occurred_at else 1,
                occurred_month=change.occurred_at.month if change.occurred_at else 1,
                occurred_day=change.occurred_at.day if change.occurred_at else 1,
                reversible=change.reversible,
                reverse_condition=change.reverse_condition,
            )
            self._current_session.world_changes.append(serialized)

        # Scheduled events
        for event in engine._event_scheduler.events:
            serialized = SerializableScheduledEvent(
                event_id=event.event_id,
                event_type=event.event_type.value,
                created_year=event.created_at.year if event.created_at else 1,
                created_month=event.created_at.month if event.created_at else 1,
                created_day=event.created_at.day if event.created_at else 1,
                source_hex_id=event.source_hex_id,
                source_poi_name=event.source_poi_name,
                trigger_condition=event.trigger_condition,
                trigger_year=event.trigger_date.year if event.trigger_date else None,
                trigger_month=event.trigger_date.month if event.trigger_date else None,
                trigger_day=event.trigger_date.day if event.trigger_date else None,
                title=event.title,
                description=event.description,
                player_message=event.player_message,
                effect_type=event.effect_type,
                effect_details=event.effect_details.copy(),
                triggered=event.triggered,
                expired=event.expired,
                character_ids=event.character_ids.copy(),
            )
            self._current_session.scheduled_events.append(serialized)

        # Granted abilities
        for ability in engine._ability_tracker.granted_abilities:
            serialized = SerializableGrantedAbility(
                grant_id=ability.grant_id,
                character_id=ability.character_id,
                ability_name=ability.ability_name,
                ability_type=ability.ability_type.value,
                description=ability.description,
                source_hex_id=ability.source_hex_id,
                source_poi_name=ability.source_poi_name,
                duration=ability.duration,
                uses_remaining=ability.uses_remaining,
                granted_year=ability.granted_at.year if ability.granted_at else 1,
                granted_month=ability.granted_at.month if ability.granted_at else 1,
                granted_day=ability.granted_at.day if ability.granted_at else 1,
                is_active=ability.is_active,
                used=ability.used,
                spell_level=ability.spell_level,
                spell_school=ability.spell_school,
                spell_data=ability.spell_data,
            )
            self._current_session.granted_abilities.append(serialized)

    def extract_full_state(
        self,
        controller: Any,
        hex_engine: Any,
        characters: list,
    ) -> GameSession:
        """
        Extract complete game state from all components.

        Args:
            controller: GlobalController instance
            hex_engine: HexCrawlEngine instance
            characters: List of CharacterState objects

        Returns:
            Complete GameSession with all state
        """
        if not self._current_session:
            self.new_session()

        # World state
        if controller.get_world_state():
            self._current_session.world_state = self.extract_world_state(
                controller.get_world_state()
            )

        # Party state
        if controller.get_party_state():
            self._current_session.party_state = self.extract_party_state(
                controller.get_party_state()
            )

        # Characters
        self._current_session.characters = self.extract_characters(characters)

        # HexCrawl state
        self.extract_hex_crawl_state(hex_engine)

        return self._current_session

    # =========================================================================
    # STATE APPLICATION (to running game)
    # =========================================================================

    def apply_world_state(self, world_state: Any) -> None:
        """
        Apply saved world state to a WorldState object.

        Args:
            world_state: WorldState to update
        """
        if not self._current_session or not self._current_session.world_state:
            return

        saved = self._current_session.world_state

        world_state.current_date = GameDate(
            year=saved.year,
            month=saved.month,
            day=saved.day,
        )
        world_state.current_time = GameTime(
            hour=saved.hour,
            minute=saved.minute,
        )
        world_state.season = Season(saved.season)
        world_state.weather = Weather(saved.weather) if saved.weather else Weather.CLEAR
        world_state.global_flags = saved.global_flags.copy()
        world_state.cleared_locations = set(saved.cleared_locations)
        world_state.active_adventure = saved.active_adventure

    def apply_party_state(self, party_state: Any) -> None:
        """
        Apply saved party state to a PartyState object.

        Args:
            party_state: PartyState to update
        """
        if not self._current_session or not self._current_session.party_state:
            return

        saved = self._current_session.party_state

        party_state.location = Location(
            location_type=LocationType(saved.location_type),
            location_id=saved.location_id,
            name=saved.location_name,
        )
        party_state.marching_order = saved.marching_order.copy()
        party_state.resources.food_days = saved.food_days
        party_state.resources.water_days = saved.water_days
        party_state.resources.torches = saved.torches
        party_state.resources.lantern_oil_flasks = saved.lantern_oil_flasks
        party_state.resources.ammunition = saved.ammunition.copy()
        party_state.active_light_source = LightSourceType(saved.active_light_source) if saved.active_light_source else None
        party_state.light_remaining_turns = saved.light_remaining_turns

        # Restore party conditions
        party_state.active_conditions = [
            Condition(
                condition_type=ConditionType(c["type"]),
                duration_remaining=c.get("duration", -1),
            )
            for c in saved.party_conditions
        ]

    def get_characters(self) -> list[CharacterState]:
        """
        Get restored character states.

        Returns:
            List of CharacterState objects
        """
        if not self._current_session:
            return []

        return [c.to_character_state() for c in self._current_session.characters]

    def apply_to_hex_engine(self, engine: Any) -> None:
        """
        Apply saved state to HexCrawlEngine.

        Args:
            engine: HexCrawlEngine to update
        """
        if not self._current_session:
            return

        # Explored hexes
        engine._explored_hexes = set(self._current_session.explored_hexes)

        # Discovered secrets
        engine._discovered_secrets = set(self._current_session.discovered_secrets)

        # Met NPCs
        engine._met_npcs = set(self._current_session.met_npcs)

        # POI visits - need to import POIVisit
        from src.hex_crawl.hex_crawl_engine import POIVisit
        for key, visit_data in self._current_session.poi_visits.items():
            engine._poi_visits[key] = POIVisit(
                poi_name=visit_data["poi_name"],
                entered=visit_data.get("entered", False),
                items_taken=visit_data.get("items_taken", []),
                rooms_explored=visit_data.get("rooms_explored", []),
            )

        # World changes
        from src.data_models import HexStateChange, WorldStateChanges
        engine._world_state_changes = WorldStateChanges()
        for saved in self._current_session.world_changes:
            change = HexStateChange(
                change_id=saved.change_id,
                hex_id=saved.hex_id,
                poi_name=saved.poi_name,
                trigger_action=saved.trigger_action,
                trigger_details=saved.trigger_details,
                change_type=saved.change_type,
                before_state=saved.before_state,
                after_state=saved.after_state,
                narrative_description=saved.narrative_description,
                occurred_at=GameDate(
                    year=saved.occurred_year,
                    month=saved.occurred_month,
                    day=saved.occurred_day,
                ),
                reversible=saved.reversible,
                reverse_condition=saved.reverse_condition,
            )
            engine._world_state_changes.add_change(change)

        # Scheduled events
        from src.data_models import ScheduledEvent, EventType, EventScheduler
        engine._event_scheduler = EventScheduler()
        for saved in self._current_session.scheduled_events:
            event = ScheduledEvent(
                event_id=saved.event_id,
                event_type=EventType(saved.event_type),
                created_at=GameDate(
                    year=saved.created_year,
                    month=saved.created_month,
                    day=saved.created_day,
                ),
                source_hex_id=saved.source_hex_id,
                source_poi_name=saved.source_poi_name,
                trigger_condition=saved.trigger_condition,
                trigger_date=GameDate(
                    year=saved.trigger_year,
                    month=saved.trigger_month,
                    day=saved.trigger_day,
                ) if saved.trigger_year else None,
                title=saved.title,
                description=saved.description,
                player_message=saved.player_message,
                effect_type=saved.effect_type,
                effect_details=saved.effect_details,
                triggered=saved.triggered,
                expired=saved.expired,
                character_ids=saved.character_ids,
            )
            engine._event_scheduler.add_event(event)

        # Granted abilities
        from src.data_models import GrantedAbility, AbilityType, AbilityGrantTracker
        engine._ability_tracker = AbilityGrantTracker()
        for saved in self._current_session.granted_abilities:
            ability = GrantedAbility(
                grant_id=saved.grant_id,
                character_id=saved.character_id,
                ability_name=saved.ability_name,
                ability_type=AbilityType(saved.ability_type),
                description=saved.description,
                source_hex_id=saved.source_hex_id,
                source_poi_name=saved.source_poi_name,
                duration=saved.duration,
                uses_remaining=saved.uses_remaining,
                granted_at=GameDate(
                    year=saved.granted_year,
                    month=saved.granted_month,
                    day=saved.granted_day,
                ),
                is_active=saved.is_active,
                used=saved.used,
                spell_level=saved.spell_level,
                spell_school=saved.spell_school,
                spell_data=saved.spell_data,
            )
            engine._ability_tracker.granted_abilities.append(ability)

            # Rebuild the grants_issued set
            source_key = f"{saved.source_hex_id}:{saved.source_poi_name}"
            grant_key = (saved.character_id, source_key, saved.ability_name)
            engine._ability_tracker._grants_issued.add(grant_key)

    def apply_poi_deltas_to_hex(self, hex_data: Any, hex_id: str) -> None:
        """
        Apply POI deltas to a loaded hex's POIs.

        This modifies the POI objects to reflect session state
        without changing the base data files.

        Args:
            hex_data: HexLocation object with POIs
            hex_id: The hex ID
        """
        if not self._current_session:
            return

        hex_delta = self._current_session.hex_deltas.get(hex_id)
        if not hex_delta:
            return

        for poi in hex_data.points_of_interest:
            poi_delta = hex_delta.poi_deltas.get(poi.name)
            if not poi_delta:
                continue

            # Apply discovery state
            if poi_delta.discovered is not None:
                poi.discovered = poi_delta.discovered

            # Apply triggered alerts
            for alert_idx, triggered in poi_delta.triggered_alerts.items():
                if 0 <= alert_idx < len(poi.alerts):
                    poi.alerts[alert_idx]["triggered"] = triggered

            # Apply found concealed items
            for item_idx, found in poi_delta.found_concealed_items.items():
                if 0 <= item_idx < len(poi.concealed_items):
                    poi.concealed_items[item_idx]["found"] = found

    def apply_npc_deltas_to_hex(self, hex_data: Any, hex_id: str) -> None:
        """
        Apply NPC deltas to a loaded hex's NPCs.

        Args:
            hex_data: HexLocation object with NPCs
            hex_id: The hex ID
        """
        if not self._current_session:
            return

        hex_delta = self._current_session.hex_deltas.get(hex_id)
        if not hex_delta:
            return

        # Note: Base HexNPC doesn't have disposition/is_dead fields
        # These deltas would be used by the game logic to check state
        # rather than modifying the base NPC object

    def is_npc_dead(self, hex_id: str, npc_id: str) -> bool:
        """Check if an NPC is dead in this session."""
        if not self._current_session:
            return False

        hex_delta = self._current_session.hex_deltas.get(hex_id)
        if not hex_delta:
            return False

        npc_delta = hex_delta.npc_deltas.get(npc_id)
        return npc_delta.is_dead if npc_delta else False

    def get_npc_disposition(self, hex_id: str, npc_id: str) -> Optional[str]:
        """Get an NPC's disposition toward the party."""
        if not self._current_session:
            return None

        hex_delta = self._current_session.hex_deltas.get(hex_id)
        if not hex_delta:
            return None

        npc_delta = hex_delta.npc_deltas.get(npc_id)
        return npc_delta.disposition if npc_delta else None

    def is_quest_completed(self, quest_id: str) -> bool:
        """Check if a quest has been completed."""
        if not self._current_session:
            return False
        return quest_id in self._current_session.completed_quests

