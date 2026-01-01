Fairy Road Loader + Schema Stub (drop-in)

Files included:
  - src/fairy_roads/models.py
  - src/content_loader/fairy_road_loader.py
  - src/content_loader/fairy_road_registry.py
  - tests/test_fairy_road_loader.py

Minimal integration steps in your repo:
  1) Copy the src/* files into your repository.
  2) Optionally export the registry/loader symbols from src/content_loader/__init__.py
     similar to how spell_loader/spell_registry are exported.
  3) Place fairy road JSON content under: data/content/fairy_roads/
  4) Load at startup:
       from src.content_loader.fairy_road_registry import get_fairy_road_registry
       get_fairy_road_registry().load_from_directory()

This stub intentionally does not implement the FairyRoadEngine.
