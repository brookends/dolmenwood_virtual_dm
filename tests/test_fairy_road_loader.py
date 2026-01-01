from pathlib import Path

from src.content_loader.fairy_road_loader import FairyRoadDataLoader


def test_fairy_road_loader_loads_common_and_roads(tmp_path: Path):
    # Create a minimal common file
    common = {
        "content_type": "fairy_roads_common",
        "tables": {
            "fairy_road_encounters_d20": {"die": "1d20", "entries": [{"roll": 1, "name": "Goblin", "count": "2d6"}]},
            "time_passed_in_mortal_world_2d6": {"die": "2d6", "entries": [{"roll": 2, "time": "1d6 minutes"}]},
        },
        "rules": {"travel_procedure": {"rolls_per_day_max": 3}},
    }
    (tmp_path / "fairy_roads_common.json").write_text(__import__("json").dumps(common), encoding="utf-8")

    # Create a minimal road file
    road = {
        "content_type": "fairy_road",
        "id": "test_road",
        "name": "Test Road",
        "length_miles": 12,
        "doors": [{"hex_id": "0000", "name": "Test Door", "direction": "endpoint"}],
        "tables": {
            "locations_d8": {
                "die": "1d8",
                "entries": [{"roll": 1, "summary": "A thing happens.", "effects": [{"type": "heal", "amount": "1d4"}]}],
            }
        },
    }
    (tmp_path / "fairy_road_test.json").write_text(__import__("json").dumps(road), encoding="utf-8")

    loader = FairyRoadDataLoader()
    result = loader.load_directory(tmp_path)

    assert result.files_processed == 2
    assert result.total_roads_loaded == 1
    assert result.common is not None
    assert result.common.encounter_table.entries[0].name == "Goblin"
    assert result.all_roads[0].road_id == "test_road"
    assert result.all_roads[0].locations.entries[0].effects[0].type == "heal"
