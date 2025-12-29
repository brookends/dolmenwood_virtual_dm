"""
Kindred manager for Dolmenwood.

Central registry for all kindred definitions. Provides access to kindred
data for character generation and gameplay.
"""

import logging
from typing import Optional

from src.kindred.kindred_data import KindredDefinition, KindredAbility

logger = logging.getLogger(__name__)


class KindredManager:
    """
    Central registry and manager for all kindred definitions.

    Provides access to kindred data by ID and handles loading
    of kindred definitions from their respective modules.
    """

    _instance: Optional["KindredManager"] = None
    _kindreds: dict[str, KindredDefinition] = {}
    _initialized: bool = False

    def __new__(cls) -> "KindredManager":
        """Singleton pattern to ensure one global registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the manager (only runs once due to singleton)."""
        if not KindredManager._initialized:
            self._load_all_kindreds()
            KindredManager._initialized = True

    def _load_all_kindreds(self) -> None:
        """Load all kindred definitions from their modules."""
        # Import and register each kindred
        try:
            from src.kindred.breggle import BREGGLE_DEFINITION
            self.register(BREGGLE_DEFINITION)
            logger.info(f"Loaded kindred: {BREGGLE_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Breggle kindred: {e}")

        try:
            from src.kindred.elf import ELF_DEFINITION
            self.register(ELF_DEFINITION)
            logger.info(f"Loaded kindred: {ELF_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Elf kindred: {e}")

        try:
            from src.kindred.grimalkin import GRIMALKIN_DEFINITION
            self.register(GRIMALKIN_DEFINITION)
            logger.info(f"Loaded kindred: {GRIMALKIN_DEFINITION.name}")
        except ImportError as e:
            logger.warning(f"Failed to load Grimalkin kindred: {e}")

        # Future kindreds will be loaded here:
        # from src.kindred.human import HUMAN_DEFINITION
        # from src.kindred.mossling import MOSSLING_DEFINITION
        # from src.kindred.woodgrue import WOODGRUE_DEFINITION

    def register(self, kindred: KindredDefinition) -> None:
        """
        Register a kindred definition.

        Args:
            kindred: The kindred definition to register
        """
        KindredManager._kindreds[kindred.kindred_id.lower()] = kindred

    def get(self, kindred_id: str) -> Optional[KindredDefinition]:
        """
        Get a kindred definition by ID.

        Args:
            kindred_id: The kindred identifier (e.g., "breggle", "human")

        Returns:
            KindredDefinition or None if not found
        """
        return KindredManager._kindreds.get(kindred_id.lower())

    def get_all(self) -> list[KindredDefinition]:
        """Get all registered kindred definitions."""
        return list(KindredManager._kindreds.values())

    def get_all_ids(self) -> list[str]:
        """Get all registered kindred IDs."""
        return list(KindredManager._kindreds.keys())

    def is_valid_kindred(self, kindred_id: str) -> bool:
        """Check if a kindred ID is valid/registered."""
        return kindred_id.lower() in KindredManager._kindreds

    def get_ability(self, kindred_id: str, ability_id: str) -> Optional[KindredAbility]:
        """
        Get a specific ability for a kindred.

        Args:
            kindred_id: The kindred identifier
            ability_id: The ability identifier

        Returns:
            KindredAbility or None if not found
        """
        kindred = self.get(kindred_id)
        if kindred:
            return kindred.get_ability(ability_id)
        return None

    def get_abilities_for_level(
        self, kindred_id: str, level: int
    ) -> list[KindredAbility]:
        """
        Get all abilities available to a kindred at a given level.

        Args:
            kindred_id: The kindred identifier
            level: Character level

        Returns:
            List of available KindredAbility objects
        """
        kindred = self.get(kindred_id)
        if not kindred:
            return []

        available = []
        for ability in kindred.abilities:
            if level >= ability.min_level:
                available.append(ability)
        return available


# Global instance for convenience
def get_kindred_manager() -> KindredManager:
    """Get the global KindredManager instance."""
    return KindredManager()
