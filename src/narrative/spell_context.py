"""
Spell Context Provider for Dolmenwood Virtual DM.

Provides context for NARRATIVE and HYBRID spells by:
- Tier 1: Querying existing game state (creatures, items, effects)
- Tier 2: Lazy-generating persistent metadata (history, emotions, names)
- Tier 3: Packaging context for constrained LLM narration

The key principle: The LLM describes the EXPERIENCE of magic,
but the Python system determines what INFORMATION exists.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, TYPE_CHECKING
import hashlib
import json
import random

if TYPE_CHECKING:
    from src.game_state.global_controller import GlobalController


# =============================================================================
# CONTEXT DATA STRUCTURES
# =============================================================================


class RevelationType(str, Enum):
    """Types of information a spell can reveal."""

    MAGICAL_AURA = "magical_aura"
    EVIL_INTENT = "evil_intent"
    HIDDEN_OBJECT = "hidden_object"
    CREATURE_PRESENCE = "creature_presence"
    ITEM_HISTORY = "item_history"
    EMOTIONAL_RESIDUE = "emotional_residue"
    TRUE_NAME = "true_name"
    SENSORY_IMPRINT = "sensory_imprint"
    LANGUAGE_CONTENT = "language_content"
    LOCATION_FEATURE = "location_feature"


@dataclass
class Revelation:
    """A single piece of information revealed by a spell."""

    revelation_type: RevelationType
    source_id: str  # ID of creature/item/location
    source_name: str  # Display name
    description: str  # What is revealed
    intensity: str = "moderate"  # faint, moderate, strong, overwhelming
    additional_data: dict[str, Any] = field(default_factory=dict)

    def to_narrative_context(self) -> str:
        """Format for LLM consumption."""
        return f"{self.source_name}: {self.description} ({self.intensity})"


@dataclass
class SpellRevelation:
    """
    Complete context for a divination/detection spell.

    This is what gets passed to the LLM - it can ONLY narrate
    what's contained in this structure.
    """

    spell_id: str
    spell_name: str
    caster_id: str
    revelations: list[Revelation] = field(default_factory=list)
    nothing_detected: bool = False
    detection_range: int = 60  # feet
    duration_remaining: Optional[int] = None

    # Narrative guidance
    sensory_mode: str = "sight"  # sight, sound, smell, touch, intuition
    aesthetic_notes: list[str] = field(default_factory=list)

    def has_revelations(self) -> bool:
        return len(self.revelations) > 0

    def to_llm_context(self) -> dict[str, Any]:
        """Package for LLM prompt."""
        return {
            "spell_name": self.spell_name,
            "sensory_mode": self.sensory_mode,
            "detection_range": f"{self.detection_range} feet",
            "nothing_detected": self.nothing_detected,
            "revelations": [r.to_narrative_context() for r in self.revelations],
            "aesthetic_notes": self.aesthetic_notes,
        }


# =============================================================================
# WRITTEN TEXT (For Decipher and similar spells)
# =============================================================================


@dataclass
class WrittenText:
    """
    Represents written text on an item or surface.

    Used by Decipher and similar translation spells.
    The content field contains the actual meaning - Decipher reveals this
    by "translating" from the original_language to Woldish.
    """

    text_id: str  # Unique identifier for this text
    original_language: str  # "elvish", "dwarvish", "ancient", "coded", "runic", etc.
    content: str  # The actual meaning/translation
    surface: str = "surface"  # Where text appears: "scroll", "wall", "ring inscription", etc.
    script_style: str = "common"  # Visual style: "elegant", "crude", "ornate", "faded"
    is_magical: bool = False  # True if the text itself is magical (e.g., spell scrolls)
    is_coded: bool = False  # True if intentionally encrypted/encoded

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_id": self.text_id,
            "original_language": self.original_language,
            "content": self.content,
            "surface": self.surface,
            "script_style": self.script_style,
            "is_magical": self.is_magical,
            "is_coded": self.is_coded,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WrittenText":
        return cls(**data)


# =============================================================================
# LAZY-GENERATED HISTORY (Tier 2)
# =============================================================================


@dataclass
class ItemHistory:
    """
    Procedurally generated history for an item.
    Generated once on first query, persisted forever.
    """

    item_id: str
    creator_name: Optional[str] = None
    creator_profession: Optional[str] = None
    creation_location: Optional[str] = None
    last_touched_by: Optional[str] = None
    absorbed_emotion: Optional[str] = None  # grief, joy, rage, fear, love
    age_category: str = "old"  # new, old, ancient, primordial
    notable_events: list[str] = field(default_factory=list)
    true_name: Optional[str] = None  # For magical items

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "creator_name": self.creator_name,
            "creator_profession": self.creator_profession,
            "creation_location": self.creation_location,
            "last_touched_by": self.last_touched_by,
            "absorbed_emotion": self.absorbed_emotion,
            "age_category": self.age_category,
            "notable_events": self.notable_events,
            "true_name": self.true_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemHistory":
        return cls(**data)


@dataclass
class CreatureHistory:
    """
    Procedurally generated background for a creature.
    For NPCs and monsters encountered.
    """

    creature_id: str
    true_name: Optional[str] = None
    origin_location: Optional[str] = None
    dominant_emotion: Optional[str] = None
    secret_fear: Optional[str] = None
    hidden_desire: Optional[str] = None
    notable_deeds: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creature_id": self.creature_id,
            "true_name": self.true_name,
            "origin_location": self.origin_location,
            "dominant_emotion": self.dominant_emotion,
            "secret_fear": self.secret_fear,
            "hidden_desire": self.hidden_desire,
            "notable_deeds": self.notable_deeds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CreatureHistory":
        return cls(**data)


class HistoryGenerator:
    """
    Generates persistent history/metadata for items and creatures.

    Uses deterministic seeding so the same item always gets
    the same history, even across sessions.
    """

    # Dolmenwood-appropriate name components
    FIRST_NAMES = [
        "Aldric", "Bramwell", "Cedric", "Dunstan", "Edric", "Fenwick",
        "Godwin", "Hengist", "Isolde", "Jocelyn", "Keir", "Leofric",
        "Morwen", "Nest", "Osric", "Peredur", "Quenby", "Rhosyn",
        "Silas", "Tamsyn", "Ulric", "Vivianne", "Wulfric", "Yseult",
    ]

    PROFESSIONS = [
        "blacksmith", "woodcarver", "weaver", "herbalist", "chandler",
        "cooper", "tinker", "scribe", "hedge wizard", "cunning woman",
        "friar", "forester", "charcoal burner", "miller", "cobbler",
    ]

    LOCATIONS = [
        "Lankshorn", "Prigwort", "Dreg", "Shantywood Isle", "Orbswallow",
        "Castle Brackenwold", "the High Wold", "the Nagwood",
        "a forgotten village", "the depths of the wood", "beyond the Hag's Addle",
    ]

    EMOTIONS = ["grief", "joy", "rage", "fear", "love", "envy", "hope", "despair"]

    FEARS = [
        "fire", "drowning", "the dark", "being forgotten", "betrayal",
        "the Cold Prince", "iron", "true names spoken aloud",
    ]

    DESIRES = [
        "freedom", "revenge", "acceptance", "power", "love",
        "to return home", "to find their true name", "peace",
    ]

    def __init__(self, world_seed: int = 42):
        """
        Initialize with a world seed for deterministic generation.

        Args:
            world_seed: Base seed for the world. Combined with item/creature
                       IDs to produce unique but reproducible results.
        """
        self.world_seed = world_seed
        self._cache: dict[str, Any] = {}

    def _get_seeded_random(self, entity_id: str) -> random.Random:
        """Get a deterministic random generator for an entity."""
        # Combine world seed with entity ID for unique but reproducible seed
        combined = f"{self.world_seed}:{entity_id}"
        seed = int(hashlib.md5(combined.encode()).hexdigest()[:8], 16)
        return random.Random(seed)

    def get_or_generate_item_history(
        self,
        item_id: str,
        item_name: str = "",
        item_type: str = "",
        is_magical: bool = False,
    ) -> ItemHistory:
        """
        Get existing history or generate new one.

        Generated history is deterministic based on item_id,
        so the same item always gets the same history.
        """
        cache_key = f"item:{item_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        rng = self._get_seeded_random(item_id)

        history = ItemHistory(
            item_id=item_id,
            creator_name=rng.choice(self.FIRST_NAMES),
            creator_profession=rng.choice(self.PROFESSIONS),
            creation_location=rng.choice(self.LOCATIONS),
            last_touched_by=rng.choice(self.FIRST_NAMES) if rng.random() > 0.3 else None,
            absorbed_emotion=rng.choice(self.EMOTIONS) if rng.random() > 0.5 else None,
            age_category=rng.choice(["new", "old", "old", "ancient", "ancient", "primordial"]),
            true_name=self._generate_true_name(rng) if is_magical else None,
        )

        # Add notable events based on age
        if history.age_category in ("ancient", "primordial"):
            num_events = rng.randint(1, 3)
            events = [
                "witnessed a great battle",
                "was blessed by a saint",
                "was cursed by a dying witch",
                "passed through fairy hands",
                "was lost for a century",
                "was used in a dark ritual",
            ]
            history.notable_events = rng.sample(events, min(num_events, len(events)))

        self._cache[cache_key] = history
        return history

    def get_or_generate_creature_history(
        self,
        creature_id: str,
        creature_name: str = "",
        creature_type: str = "",
        is_fairy: bool = False,
    ) -> CreatureHistory:
        """Generate persistent background for a creature."""
        cache_key = f"creature:{creature_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        rng = self._get_seeded_random(creature_id)

        history = CreatureHistory(
            creature_id=creature_id,
            true_name=self._generate_true_name(rng) if is_fairy else None,
            origin_location=rng.choice(self.LOCATIONS),
            dominant_emotion=rng.choice(self.EMOTIONS),
            secret_fear=rng.choice(self.FEARS),
            hidden_desire=rng.choice(self.DESIRES),
        )

        self._cache[cache_key] = history
        return history

    def _generate_true_name(self, rng: random.Random) -> str:
        """Generate a fairy-style true name."""
        prefixes = ["Ash", "Thorn", "Moon", "Star", "Oak", "Frost", "Shadow", "Silver"]
        suffixes = ["whisper", "song", "dream", "tear", "heart", "wind", "light", "dance"]
        return f"{rng.choice(prefixes)}{rng.choice(suffixes)}"

    def export_cache(self) -> dict[str, Any]:
        """Export cache for persistence."""
        return {
            key: val.to_dict() if hasattr(val, 'to_dict') else val
            for key, val in self._cache.items()
        }

    def import_cache(self, data: dict[str, Any]) -> None:
        """Import persisted cache."""
        for key, val in data.items():
            if key.startswith("item:"):
                self._cache[key] = ItemHistory.from_dict(val)
            elif key.startswith("creature:"):
                self._cache[key] = CreatureHistory.from_dict(val)


# =============================================================================
# CONTEXT PROVIDER INTERFACE
# =============================================================================


class SpellContextProvider(ABC):
    """
    Abstract base for spell context providers.

    Each divination/detection spell type has a provider that:
    1. Queries game state for relevant information
    2. Generates missing metadata as needed
    3. Packages everything into a SpellRevelation
    """

    @abstractmethod
    def get_context(
        self,
        caster_id: str,
        location_id: str,
        target_id: Optional[str] = None,
        **kwargs,
    ) -> SpellRevelation:
        """
        Gather context for spell resolution.

        Args:
            caster_id: Who is casting
            location_id: Where they are
            target_id: Specific target (if any)
            **kwargs: Spell-specific parameters

        Returns:
            SpellRevelation with all detected information
        """
        pass


# =============================================================================
# TIER 1: DETECT MAGIC
# =============================================================================


class DetectMagicProvider(SpellContextProvider):
    """
    Context provider for Detect Magic and similar spells.

    Queries game state for:
    - Magical items in range
    - Active spell effects
    - Creatures with innate magic
    - Enchanted locations
    """

    def __init__(
        self,
        controller: Optional["GlobalController"] = None,
        history_generator: Optional[HistoryGenerator] = None,
    ):
        self._controller = controller
        self._history = history_generator or HistoryGenerator()

    def get_context(
        self,
        caster_id: str,
        location_id: str,
        target_id: Optional[str] = None,
        range_feet: int = 60,
        **kwargs,
    ) -> SpellRevelation:
        """Detect magical auras in range."""
        revelation = SpellRevelation(
            spell_id="detect_magic",
            spell_name="Detect Magic",
            caster_id=caster_id,
            detection_range=range_feet,
            sensory_mode="sight",
            aesthetic_notes=[
                "Magical auras appear as shimmering halos",
                "Stronger magic glows more intensely",
                "Different magic types have distinct colors",
            ],
        )

        if not self._controller:
            # No game state - return empty
            revelation.nothing_detected = True
            return revelation

        # Query magical items
        # TODO: Wire to actual item registry when available
        magical_items = self._get_magical_items_in_range(location_id, range_feet)
        for item in magical_items:
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.MAGICAL_AURA,
                source_id=item.get("id", "unknown"),
                source_name=item.get("name", "an object"),
                description=f"radiates {item.get('magic_strength', 'faint')} magical energy",
                intensity=item.get("magic_strength", "faint"),
                additional_data={"magic_type": item.get("magic_type", "unknown")},
            ))

        # Query active spell effects
        active_effects = self._get_active_effects_in_range(location_id, range_feet)
        for effect in active_effects:
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.MAGICAL_AURA,
                source_id=effect.get("id", "unknown"),
                source_name=effect.get("target_name", "a creature"),
                description=f"is affected by {effect.get('spell_name', 'magic')}",
                intensity="moderate",
            ))

        if not revelation.has_revelations():
            revelation.nothing_detected = True

        return revelation

    def _get_magical_items_in_range(
        self, location_id: str, range_feet: int
    ) -> list[dict[str, Any]]:
        """Query magical items from game state."""
        # TODO: Implement when item registry is available
        # For now, return empty - will be wired later
        return []

    def _get_active_effects_in_range(
        self, location_id: str, range_feet: int
    ) -> list[dict[str, Any]]:
        """Query active spell effects from game state."""
        # TODO: Wire to spell_resolver.get_active_effects
        return []


# =============================================================================
# TIER 1: DETECT EVIL
# =============================================================================


class DetectEvilProvider(SpellContextProvider):
    """
    Context provider for Detect Evil.

    Detects:
    - Creatures with evil intent (NOT just chaotic alignment)
    - Cursed items
    - Evil enchantments
    """

    def __init__(
        self,
        controller: Optional["GlobalController"] = None,
    ):
        self._controller = controller

    def get_context(
        self,
        caster_id: str,
        location_id: str,
        target_id: Optional[str] = None,
        range_feet: int = 120,
        **kwargs,
    ) -> SpellRevelation:
        """Detect evil intent and enchantments."""
        revelation = SpellRevelation(
            spell_id="detect_evil",
            spell_name="Detect Evil",
            caster_id=caster_id,
            detection_range=range_feet,
            sensory_mode="sight",
            aesthetic_notes=[
                "Evil appears as flickering spirits with wicked grins",
                "Cursed objects are wreathed in dark wisps",
                "The caster sees intent, not alignment",
            ],
        )

        # Query creatures with evil intent
        # NOTE: This requires creatures to have an "intent" or "hostile" flag
        # Chaotic creatures are NOT automatically evil
        evil_creatures = self._get_creatures_with_evil_intent(location_id, range_feet)
        for creature in evil_creatures:
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.EVIL_INTENT,
                source_id=creature.get("id", "unknown"),
                source_name=creature.get("name", "a figure"),
                description="harbors malevolent intent",
                intensity=creature.get("hostility_level", "moderate"),
            ))

        # Query cursed items
        cursed_items = self._get_cursed_items_in_range(location_id, range_feet)
        for item in cursed_items:
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.EVIL_INTENT,
                source_id=item.get("id", "unknown"),
                source_name=item.get("name", "an object"),
                description="bears a wicked enchantment",
                intensity="strong",
            ))

        if not revelation.has_revelations():
            revelation.nothing_detected = True

        return revelation

    def _get_creatures_with_evil_intent(
        self, location_id: str, range_feet: int
    ) -> list[dict[str, Any]]:
        """Query creatures with evil intent (not just chaotic alignment)."""
        # TODO: Wire to encounter/NPC system
        return []

    def _get_cursed_items_in_range(
        self, location_id: str, range_feet: int
    ) -> list[dict[str, Any]]:
        """Query cursed items."""
        # TODO: Wire to item registry
        return []


# =============================================================================
# TIER 2: WOOD KENNING (Mossling Knack)
# =============================================================================


class WoodKenningProvider(SpellContextProvider):
    """
    Context provider for the Mossling Wood Kenning knack.

    Reveals:
    - Level 1: Creator's name or last person to touch
    - Level 3: Most recent strong emotion absorbed
    - Level 5: What's on the other side of wooden barrier
    - Level 7: Tree's true name

    Uses Tier 2 lazy generation for history that doesn't exist.
    """

    def __init__(
        self,
        controller: Optional["GlobalController"] = None,
        history_generator: Optional[HistoryGenerator] = None,
    ):
        self._controller = controller
        self._history = history_generator or HistoryGenerator()

    def get_context(
        self,
        caster_id: str,
        location_id: str,
        target_id: Optional[str] = None,
        caster_level: int = 1,
        target_type: str = "item",  # "item", "tree", "barrier"
        **kwargs,
    ) -> SpellRevelation:
        """
        Commune with wood to learn its secrets.

        Args:
            caster_level: Determines which abilities are available
            target_type: What kind of wooden thing is being touched
        """
        revelation = SpellRevelation(
            spell_id="wood_kenning",
            spell_name="Wood Kenning",
            caster_id=caster_id,
            detection_range=0,  # Touch only
            sensory_mode="touch",
            aesthetic_notes=[
                "Knowledge flows through fingertips pressed to wood",
                "Vibrations carry whispered secrets",
                "Ancient wood remembers more than young",
            ],
        )

        if not target_id:
            revelation.nothing_detected = True
            return revelation

        # Get or generate item history
        history = self._history.get_or_generate_item_history(
            item_id=target_id,
            item_type="wooden",
        )

        # Level 1: Sense History - creator or last toucher
        if caster_level >= 1:
            name_to_reveal = history.last_touched_by or history.creator_name
            if name_to_reveal:
                revelation.revelations.append(Revelation(
                    revelation_type=RevelationType.ITEM_HISTORY,
                    source_id=target_id,
                    source_name="the wood",
                    description=f"remembers the touch of {name_to_reveal}",
                    intensity="faint",
                ))

        # Level 3: Sense Emotions
        if caster_level >= 3 and history.absorbed_emotion:
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.EMOTIONAL_RESIDUE,
                source_id=target_id,
                source_name="the wood",
                description=f"has absorbed deep {history.absorbed_emotion}",
                intensity="moderate",
            ))

        # Level 5: See Beyond (barrier only)
        if caster_level >= 5 and target_type == "barrier":
            # This would need actual location data
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.LOCATION_FEATURE,
                source_id=target_id,
                source_name="beyond the barrier",
                description="[query location data for adjacent room]",
                intensity="moderate",
            ))

        # Level 7: True Name (tree only)
        if caster_level >= 7 and target_type == "tree":
            true_name = history.true_name or self._history._generate_true_name(
                self._history._get_seeded_random(target_id)
            )
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.TRUE_NAME,
                source_id=target_id,
                source_name="the tree",
                description=f"whispers its true name: {true_name}",
                intensity="strong",
            ))

        if not revelation.has_revelations():
            revelation.nothing_detected = True

        return revelation


# =============================================================================
# TIER 2: CRYSTAL RESONANCE
# =============================================================================


class CrystalResonanceProvider(SpellContextProvider):
    """
    Context provider for Crystal Resonance.

    This spell captures environmental energy (light, sound, image, temperature)
    for later playback. The context provider packages what's available
    to capture at the current location.
    """

    def __init__(
        self,
        controller: Optional["GlobalController"] = None,
    ):
        self._controller = controller

    def get_context(
        self,
        caster_id: str,
        location_id: str,
        target_id: Optional[str] = None,
        energy_type: str = "image",  # light, image, sound, temperature
        **kwargs,
    ) -> SpellRevelation:
        """
        Gather what environmental energy is available to imprint.
        """
        revelation = SpellRevelation(
            spell_id="crystal_resonance",
            spell_name="Crystal Resonance",
            caster_id=caster_id,
            detection_range=10,
            sensory_mode=self._energy_to_sense(energy_type),
            aesthetic_notes=[
                "The crystal hums as it attunes to ambient energy",
                "Light refracts through the gem in prismatic patterns",
                "Captured energy swirls within the crystal's heart",
            ],
        )

        # Package current environmental state for capture
        env_state = self._get_environment_state(location_id)

        if energy_type == "light":
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.SENSORY_IMPRINT,
                source_id=location_id,
                source_name="the ambient light",
                description=env_state.get("lighting", "dim forest light"),
                intensity=env_state.get("light_intensity", "moderate"),
            ))

        elif energy_type == "image":
            # Capture visible scene
            visible_elements = env_state.get("visible_elements", [])
            for element in visible_elements[:5]:  # Limit to 5 elements
                revelation.revelations.append(Revelation(
                    revelation_type=RevelationType.SENSORY_IMPRINT,
                    source_id=location_id,
                    source_name=element.get("name", "something"),
                    description=element.get("appearance", "is present"),
                    intensity="moderate",
                ))

        elif energy_type == "sound":
            sounds = env_state.get("ambient_sounds", ["silence"])
            for sound in sounds[:3]:
                revelation.revelations.append(Revelation(
                    revelation_type=RevelationType.SENSORY_IMPRINT,
                    source_id=location_id,
                    source_name="the air",
                    description=f"carries the sound of {sound}",
                    intensity="faint",
                ))

        elif energy_type == "temperature":
            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.SENSORY_IMPRINT,
                source_id=location_id,
                source_name="the air",
                description=env_state.get("temperature", "cool forest air"),
                intensity="moderate",
            ))

        return revelation

    def _energy_to_sense(self, energy_type: str) -> str:
        return {
            "light": "sight",
            "image": "sight",
            "sound": "hearing",
            "temperature": "touch",
        }.get(energy_type, "intuition")

    def _get_environment_state(self, location_id: str) -> dict[str, Any]:
        """Query current environmental state from game."""
        # TODO: Wire to location manager
        return {
            "lighting": "dappled forest light filtering through leaves",
            "light_intensity": "moderate",
            "temperature": "cool and damp",
            "ambient_sounds": ["bird calls", "rustling leaves", "distant stream"],
            "visible_elements": [],
        }


# =============================================================================
# DECIPHER PROVIDER
# =============================================================================


class DecipherProvider(SpellContextProvider):
    """
    Context provider for Decipher spell.

    Decipher transforms written text in any language (including coded messages
    and symbols) into readable Woldish for 2 turns. The text writhes, glows,
    and temporarily displays its meaning.

    This provider queries:
    - Items with inscriptions within 5' range
    - Location features with written text (signs, plaques, graffiti)
    - Environmental text (carved runes, wall writings)
    """

    def __init__(
        self,
        controller: Optional["GlobalController"] = None,
    ):
        self._controller = controller

    def get_context(
        self,
        caster_id: str,
        location_id: str,
        target_id: Optional[str] = None,
        range_feet: int = 5,
        **kwargs,
    ) -> SpellRevelation:
        """
        Gather all written text within range for deciphering.

        Args:
            caster_id: Who is casting
            location_id: Current location
            target_id: Specific item/surface to decipher (optional)
            range_feet: Range of the spell (default 5')

        Returns:
            SpellRevelation with all decipherable text
        """
        revelation = SpellRevelation(
            spell_id="decipher",
            spell_name="Decipher",
            caster_id=caster_id,
            detection_range=range_feet,
            sensory_mode="sight",
            aesthetic_notes=[
                "The script writhes and glows with arcane light",
                "Strange characters shift and reform into familiar Woldish text",
                "The transformation is temporary - text will revert after 2 turns",
            ],
        )

        # Collect all written text from various sources
        written_texts: list[tuple[str, WrittenText]] = []

        # 1. Check items in caster's inventory and nearby
        item_texts = self._get_item_inscriptions(caster_id, target_id)
        written_texts.extend(item_texts)

        # 2. Check location for environmental text
        location_texts = self._get_location_text(location_id)
        written_texts.extend(location_texts)

        # Create revelations for each text found
        for source_name, text in written_texts:
            intensity = self._determine_intensity(text)
            description = self._format_translation(text)

            revelation.revelations.append(Revelation(
                revelation_type=RevelationType.LANGUAGE_CONTENT,
                source_id=text.text_id,
                source_name=source_name,
                description=description,
                intensity=intensity,
                additional_data={
                    "original_language": text.original_language,
                    "content": text.content,
                    "surface": text.surface,
                    "script_style": text.script_style,
                    "is_magical": text.is_magical,
                    "is_coded": text.is_coded,
                },
            ))

        if not revelation.has_revelations():
            revelation.nothing_detected = True
            revelation.aesthetic_notes.append(
                "No written text is visible within range"
            )

        return revelation

    def _get_item_inscriptions(
        self,
        caster_id: str,
        target_id: Optional[str] = None,
    ) -> list[tuple[str, WrittenText]]:
        """
        Get inscriptions from items.

        Returns list of (item_name, WrittenText) tuples.
        """
        results: list[tuple[str, WrittenText]] = []

        if not self._controller:
            return results

        # Get caster's character
        caster = self._controller.get_character(caster_id)
        if not caster:
            return results

        # Check caster's inventory
        for item in caster.inventory:
            # If target_id specified, only check that item
            if target_id and item.item_id != target_id:
                continue

            # Check if item has inscriptions
            inscriptions = getattr(item, "inscriptions", None)
            if inscriptions:
                for inscription in inscriptions:
                    if isinstance(inscription, dict):
                        text = WrittenText.from_dict(inscription)
                    elif isinstance(inscription, WrittenText):
                        text = inscription
                    else:
                        continue
                    results.append((item.name, text))

        return results

    def _get_location_text(
        self,
        location_id: str,
    ) -> list[tuple[str, WrittenText]]:
        """
        Get written text from current location.

        Returns list of (surface_description, WrittenText) tuples.
        """
        results: list[tuple[str, WrittenText]] = []

        if not self._controller:
            return results

        # TODO: Wire to location/dungeon manager for environmental text
        # This would query:
        # - Dungeon room features (carved inscriptions, wall writings)
        # - POI descriptions with text elements
        # - Signs, plaques, tombstones, etc.

        return results

    def _determine_intensity(self, text: WrittenText) -> str:
        """Determine revelation intensity based on text properties."""
        if text.is_magical:
            return "strong"
        if text.is_coded:
            return "moderate"
        if text.script_style == "faded":
            return "faint"
        if text.script_style == "ornate":
            return "strong"
        return "moderate"

    def _format_translation(self, text: WrittenText) -> str:
        """Format the translation for narrative display."""
        language_desc = text.original_language.title()

        if text.is_coded:
            prefix = f"decodes from {language_desc} cipher"
        elif text.is_magical:
            prefix = f"reveals magical script in {language_desc}"
        else:
            prefix = f"translates from {language_desc}"

        # Include surface context
        surface_desc = text.surface
        if surface_desc != "surface":
            return f"({surface_desc}) {prefix}: '{text.content}'"
        return f"{prefix}: '{text.content}'"


# =============================================================================
# PROVIDER REGISTRY
# =============================================================================


class SpellContextRegistry:
    """
    Registry of context providers for different spell types.

    Usage:
        registry = SpellContextRegistry(controller)
        context = registry.get_context("detect_magic", caster_id, location_id)
    """

    def __init__(
        self,
        controller: Optional["GlobalController"] = None,
        world_seed: int = 42,
    ):
        self._controller = controller
        self._history = HistoryGenerator(world_seed)

        # Register providers
        self._providers: dict[str, SpellContextProvider] = {
            "detect_magic": DetectMagicProvider(controller, self._history),
            "detect_evil": DetectEvilProvider(controller),
            "wood_kenning": WoodKenningProvider(controller, self._history),
            "crystal_resonance": CrystalResonanceProvider(controller),
            "decipher": DecipherProvider(controller),
        }

    def get_context(
        self,
        spell_id: str,
        caster_id: str,
        location_id: str,
        **kwargs,
    ) -> Optional[SpellRevelation]:
        """
        Get context for a spell, if a provider exists.

        Returns None if no provider is registered for this spell.
        """
        provider = self._providers.get(spell_id)
        if provider:
            return provider.get_context(caster_id, location_id, **kwargs)
        return None

    def register_provider(self, spell_id: str, provider: SpellContextProvider) -> None:
        """Register a custom provider for a spell."""
        self._providers[spell_id] = provider

    def has_provider(self, spell_id: str) -> bool:
        """Check if a provider exists for a spell."""
        return spell_id in self._providers

    def export_history_cache(self) -> dict[str, Any]:
        """Export generated history for save file."""
        return self._history.export_cache()

    def import_history_cache(self, data: dict[str, Any]) -> None:
        """Import history from save file."""
        self._history.import_cache(data)
