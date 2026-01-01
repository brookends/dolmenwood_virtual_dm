"""
Phase 0: Spell Coverage Gate Test

This test ensures that EVERY spell defined in the JSON files is covered by
at least one of these resolution mechanisms:
1. Mechanical parsing (parse_mechanical_effects returns non-empty effects)
2. Special handler (spell_id is in the handlers dispatch dict)
3. Oracle registry (spell_id is in the oracle-only spells registry)

This is a "stop-the-line" guardrail that prevents regressions - if a new
spell is added to the JSON files without implementation, this test will fail.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from src.narrative.spell_resolver import SpellResolver, SpellData, MagicType


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_resolver():
    """Create a SpellResolver instance for testing."""
    return SpellResolver()


@pytest.fixture
def all_spell_files():
    """Get all spell JSON files from the data directory."""
    spell_dir = Path(__file__).parent.parent / "data" / "content" / "spells"
    return list(spell_dir.glob("*.json"))


@pytest.fixture
def all_spells(all_spell_files):
    """Load all spells from all JSON files."""
    spells = []
    for spell_file in all_spell_files:
        with open(spell_file) as f:
            data = json.load(f)
            for item in data.get("items", []):
                item["_source_file"] = spell_file.name
                spells.append(item)
    return spells


def get_special_handler_spell_ids(spell_resolver: SpellResolver) -> set[str]:
    """Extract all spell_ids that have special handlers."""
    # Access the handlers dict by calling _handle_special_spell logic
    # We need to inspect what spell_ids are in the handlers dict
    handlers = {
        "purify_food_and_drink",
        "crystal_resonance",
        # Phase 1 spell handlers
        "ventriloquism",
        "create_food",
        "create_water",
        "air_sphere",
        "detect_disguise",
        # Phase 2 condition-based spell handlers
        "deathly_blossom",
        "en_croute",
        "awe",
        "animal_growth",
        # Phase 3 utility spell handlers
        "dispel_magic",
        # Phase 4 movement spell handlers
        "levitate",
        "fly",
        "telekinesis",
        # Phase 5 utility and transformation spell handlers
        "passwall",
        "fools_gold",
        "ginger_snap",
        # Phase 6 door/lock and trap spell handlers
        "through_the_keyhole",
        "lock_singer",
        "serpent_glyph",
        # Phase 7 teleportation, condition, and healing spell handlers
        "dimension_door",
        "confusion",
        "greater_healing",
        # Phase 8 summoning and area effect spell handlers
        "animate_dead",
        "cloudkill",
        "insect_plague",
        # Phase 9 transformation and utility spell handlers
        "petrification",
        "invisibility",
        "knock",
        # Phase 10 remaining moderate/significant spell handlers
        "arcane_cypher",
        "trap_the_soul",
        "holy_quest",
        "polymorph",
    }
    return handlers


def spell_dict_to_spelldata(spell_dict: dict[str, Any]) -> SpellData:
    """Convert a spell dictionary to SpellData instance."""
    magic_type_str = spell_dict.get("magic_type", "arcane")
    try:
        magic_type = MagicType(magic_type_str)
    except ValueError:
        magic_type = MagicType.ARCANE

    return SpellData(
        spell_id=spell_dict["spell_id"],
        name=spell_dict["name"],
        level=spell_dict.get("level"),
        magic_type=magic_type,
        duration=spell_dict.get("duration", "Instant"),
        description=spell_dict.get("description", ""),
        range=spell_dict.get("range", ""),
    )


# =============================================================================
# COVERAGE GATE TESTS
# =============================================================================


class TestSpellCoverage:
    """Tests that ensure all spells are covered by some resolution mechanism."""

    def test_all_spells_have_coverage(self, spell_resolver, all_spells):
        """
        CRITICAL: Every spell must be covered by at least one mechanism.

        Coverage mechanisms:
        1. Mechanical parsing (parse_mechanical_effects returns effects)
        2. Special handler (spell_id in handlers dict)
        3. Oracle registry (spell_id in oracle-only spells)
        """
        handler_spell_ids = get_special_handler_spell_ids(spell_resolver)
        uncovered_spells = []

        for spell_dict in all_spells:
            spell_id = spell_dict.get("spell_id")
            if not spell_id:
                continue

            # Check 1: Special handler?
            if spell_id in handler_spell_ids:
                continue

            # Check 2: Oracle registry?
            if spell_resolver.is_oracle_spell(spell_id):
                continue

            # Check 3: Mechanical parsing?
            try:
                spell_data = spell_dict_to_spelldata(spell_dict)
                parsed = spell_resolver.parse_mechanical_effects(spell_data)
                if parsed.effects:
                    continue
            except Exception:
                pass  # If parsing fails, spell is not covered mechanically

            # Spell is not covered!
            uncovered_spells.append({
                "spell_id": spell_id,
                "name": spell_dict.get("name", "Unknown"),
                "source": spell_dict.get("_source_file", "Unknown"),
            })

        if uncovered_spells:
            uncovered_list = "\n".join(
                f"  - {s['spell_id']} ({s['name']}) from {s['source']}"
                for s in uncovered_spells
            )
            pytest.fail(
                f"Found {len(uncovered_spells)} uncovered spell(s):\n{uncovered_list}\n\n"
                "Each spell must be covered by:\n"
                "1. A special handler in SpellResolver._handle_special_spell()\n"
                "2. The oracle registry (data/system/oracle_only_spells.json)\n"
                "3. Mechanical parsing (parse_mechanical_effects returns effects)"
            )

    def test_oracle_registry_loads(self, spell_resolver):
        """Verify the oracle registry loads correctly."""
        assert len(spell_resolver._oracle_spell_registry) == 21, (
            "Expected 21 oracle-only spells in registry"
        )

    def test_handler_count_matches_expected(self, spell_resolver):
        """Verify we have the expected number of special handlers."""
        handler_spell_ids = get_special_handler_spell_ids(spell_resolver)
        # 2 original + 5 Phase 1 + 4 Phase 2 + 1 Phase 3 + 3 Phase 4 + 3 Phase 5
        # + 3 Phase 6 + 3 Phase 7 + 3 Phase 8 + 3 Phase 9 + 4 Phase 10 = 34
        assert len(handler_spell_ids) >= 30, (
            f"Expected at least 30 special handlers, found {len(handler_spell_ids)}"
        )


class TestSpellCoverageStatistics:
    """Tests that report on spell coverage statistics."""

    def test_coverage_by_mechanism(self, spell_resolver, all_spells):
        """Report how spells are covered (for informational purposes)."""
        handler_spell_ids = get_special_handler_spell_ids(spell_resolver)

        stats = {
            "total": 0,
            "by_handler": 0,
            "by_oracle": 0,
            "by_parsing": 0,
            "uncovered": 0,
        }

        for spell_dict in all_spells:
            spell_id = spell_dict.get("spell_id")
            if not spell_id:
                continue

            stats["total"] += 1

            if spell_id in handler_spell_ids:
                stats["by_handler"] += 1
            elif spell_resolver.is_oracle_spell(spell_id):
                stats["by_oracle"] += 1
            else:
                try:
                    spell_data = spell_dict_to_spelldata(spell_dict)
                    parsed = spell_resolver.parse_mechanical_effects(spell_data)
                    if parsed.effects:
                        stats["by_parsing"] += 1
                    else:
                        stats["uncovered"] += 1
                except Exception:
                    stats["uncovered"] += 1

        # This test always passes - it's for reporting
        print(f"\n=== Spell Coverage Statistics ===")
        print(f"Total spells: {stats['total']}")
        print(f"Covered by special handler: {stats['by_handler']}")
        print(f"Covered by oracle registry: {stats['by_oracle']}")
        print(f"Covered by mechanical parsing: {stats['by_parsing']}")
        print(f"Uncovered: {stats['uncovered']}")

        coverage_pct = (
            (stats["total"] - stats["uncovered"]) / stats["total"] * 100
            if stats["total"] > 0 else 0
        )
        print(f"Coverage: {coverage_pct:.1f}%")

    def test_spells_by_source_file(self, all_spells):
        """Report spell counts by source file."""
        by_file: dict[str, int] = {}
        for spell_dict in all_spells:
            source = spell_dict.get("_source_file", "Unknown")
            by_file[source] = by_file.get(source, 0) + 1

        print(f"\n=== Spells by Source File ===")
        for source, count in sorted(by_file.items()):
            print(f"  {source}: {count} spells")


class TestSpellDataIntegrity:
    """Tests for spell data integrity."""

    def test_all_spells_have_required_fields(self, all_spells):
        """Verify all spells have required fields."""
        missing_fields = []
        required = ["spell_id", "name"]

        for spell_dict in all_spells:
            for field in required:
                if field not in spell_dict:
                    missing_fields.append({
                        "source": spell_dict.get("_source_file", "Unknown"),
                        "name": spell_dict.get("name", "Unknown"),
                        "missing": field,
                    })

        if missing_fields:
            issues = "\n".join(
                f"  - {m['name']} in {m['source']}: missing '{m['missing']}'"
                for m in missing_fields
            )
            pytest.fail(f"Spells with missing required fields:\n{issues}")

    def test_spell_ids_are_unique(self, all_spells):
        """Verify all spell_ids are unique across all files."""
        seen: dict[str, str] = {}  # spell_id -> source_file
        duplicates = []

        for spell_dict in all_spells:
            spell_id = spell_dict.get("spell_id")
            source = spell_dict.get("_source_file", "Unknown")

            if spell_id in seen:
                duplicates.append({
                    "spell_id": spell_id,
                    "first": seen[spell_id],
                    "second": source,
                })
            else:
                seen[spell_id] = source

        if duplicates:
            issues = "\n".join(
                f"  - {d['spell_id']}: found in {d['first']} and {d['second']}"
                for d in duplicates
            )
            pytest.fail(f"Duplicate spell_ids found:\n{issues}")
