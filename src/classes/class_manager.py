"""
Class manager for Dolmenwood character classes.

Provides a singleton registry for class definitions with lazy loading.
Follows the same pattern as KindredManager.
"""

import logging
from typing import Optional

from src.classes.class_data import ClassDefinition

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
        return [
            c for c in self._classes.values()
            if c.can_be_kindred(kindred_id)
        ]

    def get_spellcasting_classes(self) -> list[ClassDefinition]:
        """Get all classes that can cast spells."""
        from src.classes.class_data import MagicType
        return [
            c for c in self._classes.values()
            if c.magic_type != MagicType.NONE
        ]

    def can_kindred_be_class(self, kindred_id: str, class_id: str) -> bool:
        """Check if a kindred can be a specific class."""
        class_def = self.get(class_id)
        if not class_def:
            return False
        return class_def.can_be_kindred(kindred_id)

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
