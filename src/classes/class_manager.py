"""
Class manager for Dolmenwood character classes.

Provides a singleton registry for class definitions with lazy loading.
Follows the same pattern as KindredManager.

Also provides integration with CharacterState for initializing class-specific
data like saving throws, attack bonus, spell slots, and skill targets.
"""

import logging
from typing import Any, Optional, TYPE_CHECKING

from src.classes.class_data import ClassDefinition, MagicType

if TYPE_CHECKING:
    from src.data_models import CharacterState, SpellSlotState, ClassSpecificData

logger = logging.getLogger(__name__)


class ClassManager:
    """
    Singleton manager for character class definitions.

    Provides centralized access to all class definitions with lazy loading.
    """

    _instance: Optional["ClassManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "ClassManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if ClassManager._initialized:
            return
        self._classes: dict[str, ClassDefinition] = {}
        self._load_classes()
        ClassManager._initialized = True

    def _load_classes(self) -> None:
        """Load all class definitions."""
        # Import and register each class definition
        try:
            from src.classes.fighter import FIGHTER_DEFINITION

            self.register(FIGHTER_DEFINITION)
            logger.info(f"Loaded class: {FIGHTER_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Fighter class: {e}")

        try:
            from src.classes.thief import THIEF_DEFINITION

            self.register(THIEF_DEFINITION)
            logger.info(f"Loaded class: {THIEF_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Thief class: {e}")

        try:
            from src.classes.magician import MAGICIAN_DEFINITION

            self.register(MAGICIAN_DEFINITION)
            logger.info(f"Loaded class: {MAGICIAN_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Magician class: {e}")

        try:
            from src.classes.cleric import CLERIC_DEFINITION

            self.register(CLERIC_DEFINITION)
            logger.info(f"Loaded class: {CLERIC_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Cleric class: {e}")

        try:
            from src.classes.friar import FRIAR_DEFINITION

            self.register(FRIAR_DEFINITION)
            logger.info(f"Loaded class: {FRIAR_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Friar class: {e}")

        try:
            from src.classes.knight import KNIGHT_DEFINITION

            self.register(KNIGHT_DEFINITION)
            logger.info(f"Loaded class: {KNIGHT_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Knight class: {e}")

        try:
            from src.classes.hunter import HUNTER_DEFINITION

            self.register(HUNTER_DEFINITION)
            logger.info(f"Loaded class: {HUNTER_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Hunter class: {e}")

        try:
            from src.classes.bard import BARD_DEFINITION

            self.register(BARD_DEFINITION)
            logger.info(f"Loaded class: {BARD_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Bard class: {e}")

        try:
            from src.classes.enchanter import ENCHANTER_DEFINITION

            self.register(ENCHANTER_DEFINITION)
            logger.info(f"Loaded class: {ENCHANTER_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Enchanter class: {e}")

        logger.info(f"Loaded {len(self._classes)} character classes")

    def register(self, class_def: ClassDefinition) -> None:
        """Register a class definition."""
        self._classes[class_def.class_id.lower()] = class_def

    def get(self, class_id: str) -> Optional[ClassDefinition]:
        """Get a class definition by ID."""
        return self._classes.get(class_id.lower())

    def get_all(self) -> list[ClassDefinition]:
        """Get all registered class definitions."""
        return list(self._classes.values())

    def get_all_ids(self) -> list[str]:
        """Get all registered class IDs."""
        return list(self._classes.keys())

    def get_classes_for_kindred(self, kindred_id: str) -> list[ClassDefinition]:
        """Get all classes available to a specific kindred."""
        return [c for c in self._classes.values() if c.can_be_kindred(kindred_id)]

    def get_spellcasting_classes(self) -> list[ClassDefinition]:
        """Get all classes that can cast spells."""
        from src.classes.class_data import MagicType

        return [c for c in self._classes.values() if c.magic_type != MagicType.NONE]

    def can_kindred_be_class(self, kindred_id: str, class_id: str) -> bool:
        """Check if a kindred can be a specific class."""
        class_def = self.get(class_id)
        if not class_def:
            return False
        return class_def.can_be_kindred(kindred_id)

    # =========================================================================
    # CHARACTER STATE INTEGRATION
    # =========================================================================

    def initialize_character_class_data(
        self, character: "CharacterState", class_id: str, level: int = 1
    ) -> bool:
        """
        Initialize a character's class-specific data.

        Sets up saving throws, attack bonus, spell slots, and class abilities
        based on the class definition and level.

        Args:
            character: The CharacterState to initialize
            class_id: The class ID to use
            level: The character's level

        Returns:
            True if initialization succeeded
        """
        from src.data_models import SpellSlotState, ClassSpecificData

        class_def = self.get(class_id)
        if not class_def:
            logger.warning(f"Unknown class: {class_id}")
            return False

        # Set the character class
        character.character_class = class_id

        # Set attack bonus
        character.attack_bonus = class_def.get_attack_bonus(level)

        # Set saving throws
        saves = class_def.get_saving_throws(level)
        character.saving_throws = {
            "doom": saves.doom,
            "ray": saves.ray,
            "hold": saves.hold,
            "blast": saves.blast,
            "spell": saves.spell,
        }

        # Set class abilities
        character.class_abilities = [
            ability.ability_id for ability in class_def.get_abilities_at_level(level)
        ]

        # Initialize spell slots for spellcasters
        if class_def.magic_type in (MagicType.ARCANE, MagicType.HOLY):
            spell_slots = class_def.get_spell_slots(level)
            if spell_slots:
                character.spell_slots = SpellSlotState(
                    max_slots=spell_slots.copy(), current_slots=spell_slots.copy()
                )

        # Initialize class-specific data
        if not character.class_data:
            character.class_data = ClassSpecificData()

        return True

    def update_character_for_level(self, character: "CharacterState", new_level: int) -> bool:
        """
        Update a character's class data for a new level.

        Called when a character levels up.

        Args:
            character: The CharacterState to update
            new_level: The new level

        Returns:
            True if update succeeded
        """
        class_def = self.get(character.character_class)
        if not class_def:
            return False

        # Update attack bonus
        character.attack_bonus = class_def.get_attack_bonus(new_level)

        # Update saving throws
        saves = class_def.get_saving_throws(new_level)
        character.saving_throws = {
            "doom": saves.doom,
            "ray": saves.ray,
            "hold": saves.hold,
            "blast": saves.blast,
            "spell": saves.spell,
        }

        # Update class abilities
        character.class_abilities = [
            ability.ability_id for ability in class_def.get_abilities_at_level(new_level)
        ]

        # Update spell slots for spellcasters
        if class_def.magic_type in (MagicType.ARCANE, MagicType.HOLY):
            spell_slots = class_def.get_spell_slots(new_level)
            if spell_slots and character.spell_slots:
                character.spell_slots.max_slots = spell_slots.copy()
                # Keep current slots but don't exceed new max
                for rank, max_count in spell_slots.items():
                    current = character.spell_slots.current_slots.get(rank, 0)
                    character.spell_slots.current_slots[rank] = min(current, max_count)

        return True

    def get_skill_target_for_character(
        self, character: "CharacterState", skill_name: str
    ) -> Optional[int]:
        """
        Get a skill target for a character based on class and level.

        Args:
            character: The character to check
            skill_name: Name of the skill

        Returns:
            The target number (roll d6 >= target), or None if not a class skill
        """
        class_def = self.get(character.character_class)
        if not class_def:
            return None

        # Look for skill ability in class
        for ability in class_def.abilities:
            extra_data = ability.extra_data or {}
            skill_targets = extra_data.get("skill_targets", {})

            # Check if this ability has skill targets by level
            if skill_targets:
                level_targets = skill_targets.get(character.level)
                if level_targets and skill_name in level_targets:
                    return level_targets[skill_name]

        return None

    def can_character_cast_spell_type(self, character: "CharacterState", spell_type: str) -> bool:
        """
        Check if a character can cast a specific spell type.

        Args:
            character: The character to check
            spell_type: Type of spell (arcane, holy, glamour, rune)

        Returns:
            True if the character's class can cast this spell type
        """
        class_def = self.get(character.character_class)
        if not class_def:
            return False
        return class_def.can_cast_spell_type(spell_type)

    def get_character_magic_type(self, character: "CharacterState") -> Optional[MagicType]:
        """
        Get the magic type for a character's class.

        Args:
            character: The character to check

        Returns:
            The MagicType for the character's class, or None if unknown
        """
        class_def = self.get(character.character_class)
        if not class_def:
            return None
        return class_def.magic_type

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None
        cls._initialized = False


# Module-level singleton accessor
_manager: Optional[ClassManager] = None


def get_class_manager() -> ClassManager:
    """Get the global class manager instance."""
    global _manager
    if _manager is None:
        _manager = ClassManager()
    return _manager
