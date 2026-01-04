"""
Content validation tests for hex 0107 (The Weeping Woman).

These tests verify that:
- All hazard conditions in the JSON are valid ConditionType enum values
- The condition schema is consistent (uses on_fail.condition pattern)
- Special fields like ends_at_time_of_day are properly set
"""

import json
import pytest
from pathlib import Path

from src.data_models import ConditionType


class TestHex0107ConditionValidation:
    """Tests verifying all conditions in hex 0107 are valid ConditionType values."""

    @pytest.fixture
    def hex_data(self):
        """Load the hex 0107 JSON data."""
        hex_path = Path("data/content/hexes/0107_the_weeping_woman.json")
        with open(hex_path) as f:
            return json.load(f)

    def get_valid_condition_values(self):
        """Get set of all valid ConditionType values."""
        return {ct.value for ct in ConditionType}

    def test_night_hazards_have_valid_conditions(self, hex_data):
        """Verify all night hazard conditions are valid ConditionType values."""
        valid_conditions = self.get_valid_condition_values()
        night_hazards = hex_data.get("procedural", {}).get("night_hazards", [])

        for hazard in night_hazards:
            on_fail = hazard.get("on_fail", {})
            condition = on_fail.get("condition")

            if condition:
                assert condition in valid_conditions, (
                    f"Night hazard condition '{condition}' is not a valid ConditionType. "
                    f"Valid values: {sorted(valid_conditions)}"
                )

    def test_poi_hazards_have_valid_conditions(self, hex_data):
        """Verify all POI hazard conditions are valid ConditionType values."""
        valid_conditions = self.get_valid_condition_values()
        pois = hex_data.get("points_of_interest", [])

        for poi in pois:
            hazards = poi.get("hazards", [])
            for hazard in hazards:
                # Check on_fail.condition
                on_fail = hazard.get("on_fail", {})
                condition = on_fail.get("condition")
                if condition:
                    assert condition in valid_conditions, (
                        f"POI hazard on_fail condition '{condition}' in '{poi.get('name')}' "
                        f"is not a valid ConditionType."
                    )

                # Check effect.condition
                effect = hazard.get("effect", {})
                condition = effect.get("condition")
                if condition:
                    assert condition in valid_conditions, (
                        f"POI hazard effect condition '{condition}' in '{poi.get('name')}' "
                        f"is not a valid ConditionType."
                    )

                # Check condition_required (must also be valid)
                condition_required = hazard.get("condition_required")
                if condition_required:
                    assert condition_required in valid_conditions, (
                        f"POI hazard condition_required '{condition_required}' "
                        f"in '{poi.get('name')}' is not a valid ConditionType."
                    )

    def test_no_legacy_condition_ids_in_night_hazards(self, hex_data):
        """Verify legacy condition IDs have been replaced in night hazards."""
        legacy_conditions = {
            "hear_music",
            "enchanted_reverie",
            "moon_dance_compulsion",
            "neveryon_dreams",
        }
        night_hazards = hex_data.get("procedural", {}).get("night_hazards", [])

        for hazard in night_hazards:
            on_fail = hazard.get("on_fail", {})
            condition = on_fail.get("condition")

            if condition:
                assert condition not in legacy_conditions, (
                    f"Night hazard still uses legacy condition ID '{condition}'. "
                    f"Should be replaced with valid ConditionType."
                )

    def test_no_legacy_condition_ids_in_poi_hazards(self, hex_data):
        """Verify legacy condition IDs have been replaced in POI hazards."""
        legacy_conditions = {
            "hear_music",
            "enchanted_reverie",
            "moon_dance_compulsion",
            "neveryon_dreams",
        }
        pois = hex_data.get("points_of_interest", [])

        for poi in pois:
            hazards = poi.get("hazards", [])
            for hazard in hazards:
                # Check all condition fields
                for field_path in ["on_fail.condition", "effect.condition", "condition_required"]:
                    parts = field_path.split(".")
                    value = hazard
                    for part in parts:
                        if isinstance(value, dict):
                            value = value.get(part)
                        else:
                            value = None
                            break

                    if value:
                        assert value not in legacy_conditions, (
                            f"POI hazard still uses legacy condition ID '{value}' "
                            f"in field '{field_path}'. Should be replaced with valid ConditionType."
                        )


class TestHex0107HazardSchemaConsistency:
    """Tests verifying consistent hazard schema in hex 0107."""

    @pytest.fixture
    def hex_data(self):
        """Load the hex 0107 JSON data."""
        hex_path = Path("data/content/hexes/0107_the_weeping_woman.json")
        with open(hex_path) as f:
            return json.load(f)

    def test_dancing_conditions_have_ends_at_dawn(self, hex_data):
        """Verify compelled_dancing conditions have ends_at_time_of_day=dawn."""
        night_hazards = hex_data.get("procedural", {}).get("night_hazards", [])

        for hazard in night_hazards:
            on_fail = hazard.get("on_fail", {})
            condition = on_fail.get("condition")

            if condition == "compelled_dancing":
                ends_at = on_fail.get("ends_at_time_of_day")
                assert ends_at == "dawn", (
                    f"compelled_dancing condition should have ends_at_time_of_day='dawn', "
                    f"got '{ends_at}'"
                )

    def test_poi_dancing_conditions_have_ends_at_dawn(self, hex_data):
        """Verify POI compelled_dancing conditions have ends_at_time_of_day=dawn."""
        pois = hex_data.get("points_of_interest", [])

        for poi in pois:
            hazards = poi.get("hazards", [])
            for hazard in hazards:
                effect = hazard.get("effect", {})
                condition = effect.get("condition")

                if condition == "compelled_dancing":
                    ends_at = effect.get("ends_at_time_of_day")
                    assert ends_at == "dawn", (
                        f"compelled_dancing in '{hazard.get('name')}' should have "
                        f"ends_at_time_of_day='dawn', got '{ends_at}'"
                    )

    def test_enchanted_hearing_leads_to_compelled_dancing(self, hex_data):
        """Verify enchanted_hearing condition properly leads to compelled_dancing."""
        pois = hex_data.get("points_of_interest", [])

        for poi in pois:
            hazards = poi.get("hazards", [])
            for hazard in hazards:
                on_fail = hazard.get("on_fail", {})
                condition = on_fail.get("condition")

                if condition == "enchanted_hearing":
                    leads_to = on_fail.get("leads_to")
                    assert leads_to == "compelled_dancing", (
                        f"enchanted_hearing should lead to 'compelled_dancing', "
                        f"got '{leads_to}'"
                    )

    def test_fairy_marked_has_source(self, hex_data):
        """Verify fairy_marked condition has source field for specificity."""
        pois = hex_data.get("points_of_interest", [])

        for poi in pois:
            hazards = poi.get("hazards", [])
            for hazard in hazards:
                effect = hazard.get("effect", {})
                condition = effect.get("condition")

                if condition == "fairy_marked":
                    source = effect.get("source")
                    assert source is not None, (
                        f"fairy_marked condition in '{hazard.get('name')}' should have "
                        f"a 'source' field to identify the fairy entity"
                    )


class TestConditionTypeEnumCompleteness:
    """Tests verifying ConditionType enum has required fairy conditions."""

    def test_enchanted_hearing_exists(self):
        """Verify ENCHANTED_HEARING exists in ConditionType."""
        assert hasattr(ConditionType, "ENCHANTED_HEARING")
        assert ConditionType.ENCHANTED_HEARING.value == "enchanted_hearing"

    def test_compelled_dancing_exists(self):
        """Verify COMPELLED_DANCING exists in ConditionType."""
        assert hasattr(ConditionType, "COMPELLED_DANCING")
        assert ConditionType.COMPELLED_DANCING.value == "compelled_dancing"

    def test_magical_sleep_exists(self):
        """Verify MAGICAL_SLEEP exists in ConditionType."""
        assert hasattr(ConditionType, "MAGICAL_SLEEP")
        assert ConditionType.MAGICAL_SLEEP.value == "magical_sleep"

    def test_fairy_marked_exists(self):
        """Verify FAIRY_MARKED exists in ConditionType."""
        assert hasattr(ConditionType, "FAIRY_MARKED")
        assert ConditionType.FAIRY_MARKED.value == "fairy_marked"
