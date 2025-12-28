"""
Item catalog and management system for Dolmenwood.

This module provides:
- ItemCatalog: Loads and manages common items from JSON catalog files
- ItemMaterializer: Generates random properties for template magic items
"""

from src.items.item_catalog import ItemCatalog
from src.items.item_materializer import ItemMaterializer

__all__ = ["ItemCatalog", "ItemMaterializer"]
