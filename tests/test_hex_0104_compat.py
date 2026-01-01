"""
Compatibility tests for HEX 0104 - The Phantom Lighthouse.

Tests that hex data loads correctly and game engine can interact with:
- Terrain and procedural data
- POI (Lighthouse in the Bog)
- NPC (The Dredger) with combat stats
- Item (Crystal Of Sepulture)
- Special features (time-of-day dependent)
"""

import pytest
from pathlib import Path

from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import DiceRoller


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def hex_pipeline():
    """Create a content pipeline with hex 0104 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0104_the_phantom_lighthouse.json"))
    assert result.success, f"Failed to load hex: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0104(hex_pipeline):
    """Get the loaded HexLocation for hex 0104."""
    hex_data = hex_pipeline.get_hex("0104")
    assert hex_data is not None, "Hex 0104 not found in pipeline"
    return hex_data


@pytest.fixture
def hex_engine(hex_0104):
    """Create a HexCrawlEngine with hex 0104 loaded."""
    controller = GlobalController()
    engine = HexCrawlEngine(controller)
    engine._hex_data["0104"] = hex_0104
    return engine


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


# =============================================================================
# BASIC LOADING TESTS
# =============================================================================


class TestHex0104Loading:
    """Test that hex 0104 loads correctly."""

    def test_hex_loads_successfully(self, hex_0104):
        """Hex 0104 should load without errors."""
        assert hex_0104.hex_id == "0104"
        assert hex_0104.name == "The Phantom Lighthouse"

    def test_terrain_type(self, hex_0104):
        """Hex should have correct terrain type."""
        assert hex_0104.terrain_type == "bog"
        assert hex_0104.terrain_difficulty == 3

    def test_region(self, hex_0104):
        """Hex should be in correct region."""
        assert hex_0104.region == "Northern Scratch"

    def test_procedural_data(self, hex_0104):
        """Procedural data should be loaded."""
        proc = hex_0104.procedural
        assert proc is not None
        assert proc.lost_chance == "2-in-6"
        assert proc.encounter_chance == "2-in-6"


# =============================================================================
# POI TESTS
# =============================================================================


class TestHex0104POIs:
    """Test POI loading."""

    def test_poi_count(self, hex_0104):
        """Should have exactly 1 POI."""
        assert len(hex_0104.points_of_interest) == 1

    def test_lighthouse_poi(self, hex_0104):
        """Lighthouse in the Bog should be loaded correctly."""
        poi = hex_0104.points_of_interest[0]
        assert poi.name == "Lighthouse in the Bog"
        assert poi.poi_type == "lighthouse"
        assert poi.is_dungeon is False
        assert poi.hidden is False  # Visible POI

    def test_lighthouse_has_dredger_npc(self, hex_0104):
        """Lighthouse POI should reference the Dredger NPC."""
        poi = hex_0104.points_of_interest[0]
        assert "the_dredger" in poi.npcs

    def test_lighthouse_special_features(self, hex_0104):
        """Lighthouse should have 5 special features."""
        poi = hex_0104.points_of_interest[0]
        assert len(poi.special_features) == 5

    def test_lighthouse_time_dependent_interior(self, hex_0104):
        """Interior description mentions time-of-day variations."""
        poi = hex_0104.points_of_interest[0]
        assert "daytime" in poi.interior.lower() or "nighttime" in poi.interior.lower()

    def test_lighthouse_inhabitants(self, hex_0104):
        """Inhabitants field should mention the Dredger."""
        poi = hex_0104.points_of_interest[0]
        assert "Dredger" in poi.inhabitants


# =============================================================================
# NPC TESTS
# =============================================================================


class TestHex0104NPCs:
    """Test NPC loading."""

    def test_npc_count(self, hex_0104):
        """Should have 1 NPC (The Dredger)."""
        assert len(hex_0104.npcs) == 1

    def test_dredger_npc(self, hex_0104):
        """The Dredger should be loaded with correct data."""
        dredger = hex_0104.npcs[0]
        assert dredger.npc_id == "the_dredger"
        assert dredger.name == "The Dredger"
        assert dredger.kindred == "Monstrosity"
        assert dredger.is_combatant is True

    def test_dredger_stat_reference(self, hex_0104):
        """The Dredger should have stat reference."""
        dredger = hex_0104.npcs[0]
        assert dredger.stat_reference is not None
        assert "Level 7" in dredger.stat_reference
        assert "AC 14" in dredger.stat_reference
        assert "HP 45" in dredger.stat_reference

    def test_dredger_location(self, hex_0104):
        """The Dredger should have location specified."""
        dredger = hex_0104.npcs[0]
        assert "lantern room" in dredger.location.lower()
        assert "nighttime" in dredger.location.lower()


# =============================================================================
# ITEM TESTS
# =============================================================================


class TestHex0104Items:
    """Test item loading."""

    def test_item_count(self, hex_0104):
        """Should have 1 item (Crystal Of Sepulture)."""
        assert len(hex_0104.items) == 1

    def test_crystal_item(self, hex_0104):
        """Crystal Of Sepulture should be loaded correctly."""
        crystal = hex_0104.items[0]
        assert crystal["name"] == "Crystal Of Sepulture"
        assert crystal["magical"] is True
        assert crystal["item_id"] == "0104:item:crystal-of-sepulture"

    def test_crystal_acquisition_condition(self, hex_0104):
        """Crystal should have acquisition condition."""
        crystal = hex_0104.items[0]
        assert "acquisition_condition" in crystal
        assert "Dredger" in crystal["acquisition_condition"]


# =============================================================================
# ENGINE INTERACTION TESTS
# =============================================================================


class TestHex0104EngineInteraction:
    """Test HexCrawlEngine interactions with hex 0104."""

    def test_hex_loaded_in_engine(self, hex_engine):
        """Hex 0104 should be loaded in the engine."""
        assert "0104" in hex_engine._hex_data
        hex_data = hex_engine._hex_data["0104"]
        assert hex_data.name == "The Phantom Lighthouse"

    def test_poi_accessible_from_engine(self, hex_engine):
        """POI data should be accessible from engine."""
        hex_data = hex_engine._hex_data["0104"]
        poi = hex_data.points_of_interest[0]
        assert poi.name == "Lighthouse in the Bog"
        assert "the_dredger" in poi.npcs


# =============================================================================
# NPC COMBAT ENGAGEMENT TESTS
# =============================================================================


class TestDredgerCombatEngagement:
    """Test engaging the Dredger in combat."""

    def test_engage_dredger_requires_poi(self, hex_engine):
        """Cannot engage NPC without being at a POI."""
        hex_engine._current_poi = None
        result = hex_engine.engage_poi_npc("0104", "the_dredger")
        assert result["success"] is False
        assert "Not at a POI" in result["error"]

    def test_engage_dredger_at_lighthouse(self, hex_engine):
        """Can engage the Dredger when at the lighthouse POI."""
        hex_engine._current_poi = "Lighthouse in the Bog"
        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is True
        assert result["combatant"]["name"] == "The Dredger"
        assert result["combatant"]["ac"] == 14
        assert result["combatant"]["hp"] == 45
        assert result["combatant"]["attacks"] == 6

    def test_engage_wrong_npc_at_poi(self, hex_engine):
        """Cannot engage NPC that isn't at current POI."""
        hex_engine._current_poi = "Lighthouse in the Bog"
        result = hex_engine.engage_poi_npc("0104", "nonexistent_npc")
        assert result["success"] is False
        assert "not at this POI" in result["error"]

    def test_stat_reference_parser(self):
        """Test inline stat block parser directly."""
        from src.content_loader.monster_registry import get_monster_registry

        registry = get_monster_registry()
        stat_ref = "Level 5 AC 16 HP 30 Morale 8 Speed 30 Att 2 claws (+4, 1d6)"

        result = registry.parse_inline_stat_block(stat_ref)
        assert result.success is True
        assert result.stat_block.armor_class == 16
        assert result.stat_block.hp_max == 30
        assert result.stat_block.morale == 8
        assert len(result.stat_block.attacks) == 2

    def test_combatant_creation_from_hex_npc(self, hex_0104):
        """Test creating combatant from HexNPC."""
        from src.content_loader.monster_registry import get_monster_registry

        registry = get_monster_registry()
        dredger = hex_0104.npcs[0]

        combatant = registry.create_combatant_from_hex_npc(
            npc=dredger,
            combatant_id="test_dredger",
            side="enemy",
        )

        assert combatant is not None
        assert combatant.name == "The Dredger"
        assert combatant.side == "enemy"
        assert combatant.stat_block.armor_class == 14
        assert combatant.stat_block.hp_max == 45


# =============================================================================
# CREATIVE APPROACH TESTS
# =============================================================================


class TestCreativeApproach:
    """Test creative, non-combat approaches to the Dredger."""

    def test_creative_approach_requires_poi(self, hex_engine):
        """Cannot attempt creative approach without being at POI."""
        hex_engine._current_poi = None
        result = hex_engine.attempt_creative_approach(
            "0104", "the_dredger", "Lure it away with magic"
        )
        assert result["success"] is False
        assert "Not at a POI" in result["error"]

    def test_creative_approach_returns_oracle_result(self, hex_engine):
        """Creative approach should return oracle outcome."""
        hex_engine._current_poi = "Lighthouse in the Bog"
        result = hex_engine.attempt_creative_approach(
            "0104", "the_dredger", "Distract the Dredger"
        )

        # Should have oracle details regardless of success
        assert "oracle" in result
        assert "question" in result["oracle"]
        assert "likelihood" in result["oracle"]
        assert "roll" in result["oracle"]
        assert "result" in result["oracle"]

    def test_magic_bait_increases_likelihood(self, hex_engine):
        """Using magical items should increase likelihood for magic-hungry creatures."""
        hex_engine._current_poi = "Lighthouse in the Bog"

        # Get Dredger NPC
        hex_data = hex_engine._hex_data["0104"]
        dredger = hex_data.npcs[0]

        # Verify Dredger desires magic
        assert "Feed on magical energy" in dredger.desires

        # Test likelihood evaluation
        from src.oracle import Likelihood

        likelihood_with_magic = hex_engine._evaluate_approach_likelihood(
            dredger, "Lure with magical bait", ["enchanted wand"]
        )
        likelihood_without = hex_engine._evaluate_approach_likelihood(
            dredger, "Lure with regular bait", []
        )

        # Magic should give better odds
        assert likelihood_with_magic.value >= likelihood_without.value

    def test_approach_formulates_correct_question(self, hex_engine):
        """Different approaches should generate appropriate oracle questions."""
        hex_data = hex_engine._hex_data["0104"]
        dredger = hex_data.npcs[0]

        q1 = hex_engine._formulate_approach_question(dredger, "Lure it away")
        assert "lured away" in q1

        q2 = hex_engine._formulate_approach_question(dredger, "Distract the creature")
        assert "distracted" in q2

        q3 = hex_engine._formulate_approach_question(dredger, "Sneak past it")
        assert "bypass" in q3

    def test_creative_approach_provides_follow_up_options(self, hex_engine):
        """Result should include follow-up action options."""
        hex_engine._current_poi = "Lighthouse in the Bog"
        result = hex_engine.attempt_creative_approach(
            "0104", "the_dredger", "Distract the Dredger"
        )

        assert "follow_up_options" in result
        assert len(result["follow_up_options"]) > 0

    def test_creative_approach_includes_narrative_hints(self, hex_engine):
        """Result should include narrative hints for LLM."""
        hex_engine._current_poi = "Lighthouse in the Bog"
        result = hex_engine.attempt_creative_approach(
            "0104", "the_dredger", "Lure the Dredger with magic"
        )

        assert "narrative_hints" in result
        assert len(result["narrative_hints"]) > 0


# =============================================================================
# SMOKE TEST - PARSE ALL HEXES
# =============================================================================


class TestAllHexesParse:
    """Quick smoke test that hex files parse without error."""

    def test_hex_0104_parses_cleanly(self):
        """Hex 0104 should parse without errors."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        result = loader.load_file(Path("data/content/hexes/0104_the_phantom_lighthouse.json"))
        assert result.success, f"Hex 0104 parsing errors: {result.errors}"

    def test_hex_0103_still_parses(self):
        """Hex 0103 should still parse (regression check)."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        result = loader.load_file(Path("data/content/hexes/0103_the_golden_goose.json"))
        assert result.success, f"Hex 0103 parsing errors: {result.errors}"

    def test_hex_0102_still_parses(self):
        """Hex 0102 should still parse (regression check)."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        result = loader.load_file(Path("data/content/hexes/0102_reedwall.json"))
        assert result.success, f"Hex 0102 parsing errors: {result.errors}"


# =============================================================================
# ENVIRONMENTAL CREATIVE RESOLVER TESTS
# =============================================================================


@pytest.fixture
def hex_0102_engine():
    """Create engine with hex 0102 (Reedwall) loaded for environmental tests."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0102_reedwall.json"))
    assert result.success

    controller = GlobalController()
    engine = HexCrawlEngine(controller)
    engine._hex_data["0102"] = pipeline.get_hex("0102")
    return engine


class TestEnvironmentalCreativeResolver:
    """Test environmental hazard creative solutions."""

    def test_environmental_patterns_exist(self, hex_0102_engine):
        """Engine should have environmental pattern definitions."""
        assert hasattr(hex_0102_engine, "ENVIRONMENTAL_PATTERNS")
        patterns = hex_0102_engine.ENVIRONMENTAL_PATTERNS
        assert "avoid_sleep" in patterns
        assert "navigate_maze" in patterns
        assert "magical_protection" in patterns

    def test_attempt_environmental_solution_night_hazard(self, hex_0102_engine):
        """Should be able to attempt solution for night hazard."""
        result = hex_0102_engine.attempt_environmental_solution(
            "0102", "night_hazard", "Set up a protective ward before sleeping"
        )

        assert "success" in result
        # Environmental solutions use pattern_used, check, or oracle resolution
        assert "pattern_used" in result or "check" in result or "oracle" in result
        assert "hazard_type" in result
        assert result["hazard_type"] == "night_hazard"

    def test_attempt_environmental_solution_maze(self, hex_0102_engine):
        """Should be able to attempt solution for maze lost behavior."""
        result = hex_0102_engine.attempt_environmental_solution(
            "0102", "lost", "Use rope and stakes to mark the path"
        )

        assert "success" in result
        # Environmental solutions use pattern_used, check, or oracle resolution
        assert "pattern_used" in result or "check" in result or "oracle" in result
        assert "hazard_type" in result

    def test_environmental_solution_returns_narrative_hints(self, hex_0102_engine):
        """Environmental solution should provide narrative hints."""
        result = hex_0102_engine.attempt_environmental_solution(
            "0102", "night_hazard", "Stay awake taking shifts"
        )

        # Should have narrative hints for storytelling
        assert "narrative_hints" in result
        # And mechanical effects for game mechanics
        assert "mechanical_effects" in result


# =============================================================================
# FACTION RELATIONSHIP TESTS
# =============================================================================


@pytest.fixture
def hex_0103_engine():
    """Create engine with hex 0103 (Golden Goose) loaded for faction tests."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0103_the_golden_goose.json"))
    assert result.success

    controller = GlobalController()
    engine = HexCrawlEngine(controller)
    engine._hex_data["0103"] = pipeline.get_hex("0103")
    return engine


class TestFactionRelationshipTracking:
    """Test faction relationship tracking for NPCs."""

    def test_ruffians_have_faction_data(self, hex_0103_engine):
        """Ruffians should have faction and loyalty data loaded."""
        hex_data = hex_0103_engine._hex_data["0103"]
        ruffians = None
        for npc in hex_data.npcs:
            if npc.npc_id == "ruffians":
                ruffians = npc
                break

        assert ruffians is not None
        assert ruffians.faction == "sidney_tew"
        # "bought" means payment-based loyalty
        assert ruffians.loyalty == "bought"

    def test_ruffians_have_vulnerability(self, hex_0103_engine):
        """Ruffians should have better_payment vulnerability."""
        hex_data = hex_0103_engine._hex_data["0103"]
        ruffians = None
        for npc in hex_data.npcs:
            if npc.npc_id == "ruffians":
                ruffians = npc
                break

        assert ruffians is not None
        assert "better_payment" in ruffians.vulnerabilities

    def test_minor_nobles_have_faction_data(self, hex_0103_engine):
        """Minor nobles should have faction and loyalty data."""
        hex_data = hex_0103_engine._hex_data["0103"]
        nobles = None
        for npc in hex_data.npcs:
            if npc.npc_id == "minor_nobles":
                nobles = npc
                break

        assert nobles is not None
        assert nobles.faction == "sidney_tew"
        # "loyal" means ideologically aligned
        assert nobles.loyalty == "loyal"

    def test_get_turnable_npcs(self, hex_0103_engine):
        """Should be able to get NPCs that can be turned."""
        hex_0103_engine._current_poi = "Sidney's Company"

        # get_faction_state creates and initializes the faction state
        hex_0103_engine.get_faction_state("0103")

        turnable = hex_0103_engine.get_turnable_npcs("0103", "sidney_tew")

        # Ruffians should be turnable (payment-based loyalty)
        # get_turnable_npcs returns list of dicts, not HexNPC objects
        assert any(npc["npc_id"] == "ruffians" for npc in turnable)

    def test_attempt_turn_npc(self, hex_0103_engine):
        """Should be able to attempt to turn an NPC against employer."""
        hex_0103_engine._current_poi = "Sidney's Company"

        result = hex_0103_engine.attempt_turn_npc(
            "0103",
            "ruffians",
            "sidney_tew",
            "Offer double their current payment",
            incentive="50gp",
        )

        assert "success" in result
        assert "oracle" in result
        # The result uses "npc_id" and "target", not "target_npc" and "against"
        assert result["npc_id"] == "ruffians"
        assert result["target"] == "sidney_tew"


# =============================================================================
# VULNERABILITY-BASED LIKELIHOOD TESTS
# =============================================================================


class TestVulnerabilityBasedLikelihood:
    """Test that vulnerabilities affect creative approach likelihood."""

    def test_crocus_has_cold_iron_vulnerability(self, hex_0103_engine):
        """Crocus should have cold_iron vulnerability."""
        hex_data = hex_0103_engine._hex_data["0103"]
        crocus = None
        for npc in hex_data.npcs:
            if npc.npc_id == "crocus":
                crocus = npc
                break

        assert crocus is not None
        assert "cold_iron" in crocus.vulnerabilities

    def test_cold_iron_increases_likelihood(self, hex_0103_engine):
        """Using cold iron should increase approach likelihood against Crocus."""
        hex_data = hex_0103_engine._hex_data["0103"]
        crocus = None
        for npc in hex_data.npcs:
            if npc.npc_id == "crocus":
                crocus = npc
                break

        assert crocus is not None

        # Test likelihood with and without cold iron
        likelihood_with = hex_0103_engine._evaluate_approach_likelihood(
            crocus, "Threaten with cold iron weapon", ["cold_iron_sword"]
        )
        likelihood_without = hex_0103_engine._evaluate_approach_likelihood(
            crocus, "Threaten with regular weapon", ["steel_sword"]
        )

        # Cold iron should give better odds
        assert likelihood_with.value >= likelihood_without.value

    def test_better_payment_increases_likelihood_for_ruffians(self, hex_0103_engine):
        """Offering better payment should increase likelihood with ruffians."""
        hex_data = hex_0103_engine._hex_data["0103"]
        ruffians = None
        for npc in hex_data.npcs:
            if npc.npc_id == "ruffians":
                ruffians = npc
                break

        assert ruffians is not None

        likelihood_with_money = hex_0103_engine._evaluate_approach_likelihood(
            ruffians, "Offer them better payment to switch sides", ["gold_coins"]
        )
        likelihood_without = hex_0103_engine._evaluate_approach_likelihood(
            ruffians, "Ask them nicely to switch sides", []
        )

        # Money should help with payment-loyal ruffians
        assert likelihood_with_money.value >= likelihood_without.value
