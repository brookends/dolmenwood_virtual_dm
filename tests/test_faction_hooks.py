"""
Tests for faction_hooks.py - Faction integration hooks.

Tests hex-faction lookups, service cost modifiers, and encounter modifiers.
"""

import pytest
from unittest.mock import MagicMock

from src.factions.faction_hooks import (
    FactionModifiers,
    HexFactionLookup,
    calculate_modifiers,
    get_service_cost_multiplier,
    get_encounter_modifier,
    apply_cost_modifier,
)
from src.factions.faction_models import (
    FactionRules,
    FactionDefinition,
    FactionTurnState,
    Territory,
    PartyFactionState,
)
from src.factions.faction_engine import FactionEngine


@pytest.fixture
def basic_rules():
    """Create basic faction rules."""
    return FactionRules(schema_version=1)


@pytest.fixture
def faction_with_territory():
    """Create a faction with territory claims."""
    return FactionDefinition(
        faction_id="house_brackenwold",
        name="House Brackenwold",
        tags=["human_nobility"],
    )


@pytest.fixture
def faction_engine(basic_rules, faction_with_territory):
    """Create a faction engine with territory claims."""
    engine = FactionEngine(
        rules=basic_rules,
        definitions={"house_brackenwold": faction_with_territory},
    )

    # Set up territory
    state = engine.faction_states["house_brackenwold"]
    state.territory.hexes.add("0604")
    state.territory.hexes.add("0605")
    state.territory.settlements.add("prigwort")

    # Set up party state
    engine.set_party_state(PartyFactionState())

    return engine


# =============================================================================
# FactionModifiers Tests
# =============================================================================


class TestFactionModifiers:
    """Tests for FactionModifiers dataclass."""

    def test_default_values(self):
        """Test default modifier values."""
        mods = FactionModifiers()
        assert mods.cost_multiplier == 1.0
        assert mods.encounter_modifier == 0
        assert mods.faction_id is None
        assert mods.standing == 0

    def test_cost_percent_change_discount(self):
        """Test cost percent change for discounts."""
        mods = FactionModifiers(cost_multiplier=0.75)
        assert mods.cost_percent_change == -25

    def test_cost_percent_change_markup(self):
        """Test cost percent change for markups."""
        mods = FactionModifiers(cost_multiplier=1.50)
        assert mods.cost_percent_change == 50


# =============================================================================
# calculate_modifiers Tests
# =============================================================================


class TestCalculateModifiers:
    """Tests for calculate_modifiers function."""

    def test_allied_standing(self):
        """Test Allied tier (+8 or more)."""
        mods = calculate_modifiers(8, "test_faction")
        assert mods.cost_multiplier == 0.75
        assert mods.encounter_modifier == -2
        assert mods.faction_id == "test_faction"
        assert mods.standing == 8

    def test_friendly_standing(self):
        """Test Friendly tier (+5 to +7)."""
        mods = calculate_modifiers(5)
        assert mods.cost_multiplier == 0.85
        assert mods.encounter_modifier == -1

        mods = calculate_modifiers(7)
        assert mods.cost_multiplier == 0.85

    def test_favorable_standing(self):
        """Test Favorable tier (+2 to +4)."""
        mods = calculate_modifiers(2)
        assert mods.cost_multiplier == 0.95
        assert mods.encounter_modifier == 0

        mods = calculate_modifiers(4)
        assert mods.cost_multiplier == 0.95

    def test_neutral_standing(self):
        """Test Neutral tier (-1 to +1)."""
        mods = calculate_modifiers(0)
        assert mods.cost_multiplier == 1.0
        assert mods.encounter_modifier == 0

        mods = calculate_modifiers(-1)
        assert mods.cost_multiplier == 1.0

        mods = calculate_modifiers(1)
        assert mods.cost_multiplier == 1.0

    def test_unfavorable_standing(self):
        """Test Unfavorable tier (-2 to -4)."""
        mods = calculate_modifiers(-2)
        assert mods.cost_multiplier == 1.10
        assert mods.encounter_modifier == 1

        mods = calculate_modifiers(-4)
        assert mods.cost_multiplier == 1.10

    def test_hostile_standing(self):
        """Test Hostile tier (-5 to -7)."""
        mods = calculate_modifiers(-5)
        assert mods.cost_multiplier == 1.25
        assert mods.encounter_modifier == 1

        mods = calculate_modifiers(-7)
        assert mods.cost_multiplier == 1.25

    def test_enemy_standing(self):
        """Test Enemy tier (-8 or less)."""
        mods = calculate_modifiers(-8)
        assert mods.cost_multiplier == 1.50
        assert mods.encounter_modifier == 2

        mods = calculate_modifiers(-10)
        assert mods.cost_multiplier == 1.50


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_service_cost_multiplier(self):
        """Test get_service_cost_multiplier function."""
        assert get_service_cost_multiplier(8) == 0.75
        assert get_service_cost_multiplier(0) == 1.0
        assert get_service_cost_multiplier(-8) == 1.50

    def test_get_encounter_modifier(self):
        """Test get_encounter_modifier function."""
        assert get_encounter_modifier(8) == -2
        assert get_encounter_modifier(5) == -1
        assert get_encounter_modifier(0) == 0
        assert get_encounter_modifier(-5) == 1
        assert get_encounter_modifier(-8) == 2

    def test_apply_cost_modifier_discount(self):
        """Test apply_cost_modifier with discount."""
        # 25% discount on 100gp
        result = apply_cost_modifier(100, 8)
        assert result == 75

    def test_apply_cost_modifier_markup(self):
        """Test apply_cost_modifier with markup."""
        # 50% markup on 100gp
        result = apply_cost_modifier(100, -8)
        assert result == 150

    def test_apply_cost_modifier_minimum(self):
        """Test apply_cost_modifier minimum of 1."""
        # 25% discount on 1gp should still be 1
        result = apply_cost_modifier(1, 8)
        assert result >= 1

    def test_apply_cost_modifier_rounding(self):
        """Test apply_cost_modifier with rounding."""
        # Round to nearest 5
        result = apply_cost_modifier(97, 0, round_to=5)
        assert result % 5 == 0


# =============================================================================
# HexFactionLookup Tests
# =============================================================================


class TestHexFactionLookup:
    """Tests for HexFactionLookup class."""

    def test_init_no_engine(self):
        """Test initialization with no engine."""
        lookup = HexFactionLookup(None)
        assert lookup.get_faction_for_hex("0604") is None
        assert lookup.get_faction_for_settlement("prigwort") is None

    def test_get_faction_for_hex(self, faction_engine):
        """Test getting faction for a claimed hex."""
        lookup = HexFactionLookup(faction_engine)
        assert lookup.get_faction_for_hex("0604") == "house_brackenwold"
        assert lookup.get_faction_for_hex("0605") == "house_brackenwold"

    def test_get_faction_for_hex_unclaimed(self, faction_engine):
        """Test getting faction for an unclaimed hex."""
        lookup = HexFactionLookup(faction_engine)
        assert lookup.get_faction_for_hex("9999") is None

    def test_get_faction_for_settlement(self, faction_engine):
        """Test getting faction for a claimed settlement."""
        lookup = HexFactionLookup(faction_engine)
        assert lookup.get_faction_for_settlement("prigwort") == "house_brackenwold"

    def test_get_faction_for_settlement_unclaimed(self, faction_engine):
        """Test getting faction for an unclaimed settlement."""
        lookup = HexFactionLookup(faction_engine)
        assert lookup.get_faction_for_settlement("unknown_town") is None

    def test_get_standing_for_hex(self, faction_engine):
        """Test getting party standing for a hex."""
        # Set party standing with house_brackenwold
        faction_engine.party_state.adjust_standing("house_brackenwold", 5)

        lookup = HexFactionLookup(faction_engine)
        standing = lookup.get_standing_for_hex("0604")
        assert standing == 5

    def test_get_standing_for_hex_unclaimed(self, faction_engine):
        """Test standing for unclaimed hex is 0."""
        lookup = HexFactionLookup(faction_engine)
        standing = lookup.get_standing_for_hex("9999")
        assert standing == 0

    def test_get_standing_for_hex_no_party_state(self, basic_rules, faction_with_territory):
        """Test standing when no party state exists."""
        engine = FactionEngine(
            rules=basic_rules,
            definitions={"house_brackenwold": faction_with_territory},
        )
        engine.faction_states["house_brackenwold"].territory.hexes.add("0604")
        # Don't set party state

        lookup = HexFactionLookup(engine)
        standing = lookup.get_standing_for_hex("0604")
        assert standing == 0

    def test_get_standing_for_settlement(self, faction_engine):
        """Test getting party standing for a settlement."""
        faction_engine.party_state.adjust_standing("house_brackenwold", -3)

        lookup = HexFactionLookup(faction_engine)
        standing = lookup.get_standing_for_settlement("prigwort")
        assert standing == -3

    def test_refresh_after_territory_change(self, faction_engine):
        """Test refresh updates the index."""
        lookup = HexFactionLookup(faction_engine)

        # Initially hex 1001 is unclaimed
        assert lookup.get_faction_for_hex("1001") is None

        # Add hex to territory
        faction_engine.faction_states["house_brackenwold"].territory.hexes.add("1001")

        # Still unclaimed until refresh
        assert lookup.get_faction_for_hex("1001") is None

        # Refresh updates index
        lookup.refresh()
        assert lookup.get_faction_for_hex("1001") == "house_brackenwold"


# =============================================================================
# Settlement Service Integration Tests
# =============================================================================


class TestSettlementServiceIntegration:
    """Tests for settlement service cost modifier integration."""

    def test_cost_estimate_apply_multiplier(self):
        """Test CostEstimate.apply_multiplier method."""
        from src.settlement.settlement_services import CostEstimate

        cost = CostEstimate(gp=100, sp=50, cp=25)
        modified = cost.apply_multiplier(0.75)

        assert modified.gp == 75
        assert modified.sp == 37
        assert modified.cp == 18

    def test_cost_estimate_apply_multiplier_markup(self):
        """Test CostEstimate.apply_multiplier with markup."""
        from src.settlement.settlement_services import CostEstimate

        cost = CostEstimate(gp=100, sp=50, cp=25)
        modified = cost.apply_multiplier(1.50)

        assert modified.gp == 150
        assert modified.sp == 75
        assert modified.cp == 37

    def test_service_executor_with_faction_standing(self):
        """Test SettlementServiceExecutor applies faction modifiers."""
        from src.settlement.settlement_services import SettlementServiceExecutor
        from src.settlement.settlement_content_models import SettlementServiceData

        service = SettlementServiceData(
            name="Lodging",
            description="A room for the night",
            cost="10gp",
        )

        executor = SettlementServiceExecutor()

        # Without faction standing
        result = executor.use(service)
        assert result.cost_estimate.gp == 10
        assert result.faction_modifier_applied is False

        # With positive standing (Allied = -25%)
        result = executor.use(service, faction_standing=8)
        assert result.cost_estimate.gp == 7  # 10 * 0.75 = 7.5 -> 7
        assert result.faction_modifier_applied is True
        assert result.faction_cost_percent == -25

        # With negative standing (Enemy = +50%)
        result = executor.use(service, faction_standing=-8)
        assert result.cost_estimate.gp == 15  # 10 * 1.50 = 15
        assert result.faction_modifier_applied is True
        assert result.faction_cost_percent == 50

    def test_service_executor_neutral_standing(self):
        """Test SettlementServiceExecutor with neutral standing."""
        from src.settlement.settlement_services import SettlementServiceExecutor
        from src.settlement.settlement_content_models import SettlementServiceData

        service = SettlementServiceData(
            name="Meal",
            cost="5sp",
        )

        executor = SettlementServiceExecutor()

        # Neutral standing should not apply modifier
        result = executor.use(service, faction_standing=0)
        assert result.cost_estimate.sp == 5
        assert result.faction_modifier_applied is False


# =============================================================================
# HexCrawlEngine Encounter Integration Tests
# =============================================================================


class TestEncounterIntegration:
    """Tests for encounter modifier integration with HexCrawlEngine."""

    def test_faction_modifier_reduces_encounter_chance(self):
        """Test that good standing reduces encounter chance."""
        # Allied standing (-2 modifier) should reduce chance
        modifier = get_encounter_modifier(8)
        assert modifier == -2

        # If base chance is 2, modified chance would be 0
        base_chance = 2
        modified_chance = max(0, min(6, base_chance + modifier))
        assert modified_chance == 0

    def test_faction_modifier_increases_encounter_chance(self):
        """Test that bad standing increases encounter chance."""
        # Enemy standing (+2 modifier) should increase chance
        modifier = get_encounter_modifier(-8)
        assert modifier == 2

        # If base chance is 2, modified chance would be 4
        base_chance = 2
        modified_chance = max(0, min(6, base_chance + modifier))
        assert modified_chance == 4

    def test_encounter_chance_clamped(self):
        """Test that encounter chance is clamped to 0-6."""
        # Even with -2 modifier, can't go below 0
        modifier = get_encounter_modifier(8)
        base_chance = 1
        modified_chance = max(0, min(6, base_chance + modifier))
        assert modified_chance == 0

        # Even with +2 modifier, can't go above 6
        modifier = get_encounter_modifier(-8)
        base_chance = 5
        modified_chance = max(0, min(6, base_chance + modifier))
        assert modified_chance == 6


# =============================================================================
# Multiple Faction Territory Tests
# =============================================================================


class TestMultipleFactionTerritory:
    """Tests with multiple factions claiming territory."""

    @pytest.fixture
    def multi_faction_engine(self, basic_rules):
        """Create engine with multiple factions."""
        definitions = {
            "house_brackenwold": FactionDefinition(
                faction_id="house_brackenwold",
                name="House Brackenwold",
            ),
            "nag_lord": FactionDefinition(
                faction_id="nag_lord",
                name="Nag-Lord Atanuwe",
            ),
        }

        engine = FactionEngine(rules=basic_rules, definitions=definitions)

        # Set up territories
        engine.faction_states["house_brackenwold"].territory.hexes.add("0604")
        engine.faction_states["house_brackenwold"].territory.settlements.add("prigwort")

        engine.faction_states["nag_lord"].territory.hexes.add("0807")
        engine.faction_states["nag_lord"].territory.settlements.add("dreg")

        engine.set_party_state(PartyFactionState())

        return engine

    def test_lookup_multiple_factions(self, multi_faction_engine):
        """Test looking up different faction territories."""
        lookup = HexFactionLookup(multi_faction_engine)

        assert lookup.get_faction_for_hex("0604") == "house_brackenwold"
        assert lookup.get_faction_for_hex("0807") == "nag_lord"
        assert lookup.get_faction_for_settlement("prigwort") == "house_brackenwold"
        assert lookup.get_faction_for_settlement("dreg") == "nag_lord"

    def test_standing_varies_by_faction(self, multi_faction_engine):
        """Test that standing varies by controlling faction."""
        multi_faction_engine.party_state.adjust_standing("house_brackenwold", 5)
        multi_faction_engine.party_state.adjust_standing("nag_lord", -3)

        lookup = HexFactionLookup(multi_faction_engine)

        # Hex 0604 controlled by house_brackenwold - good standing
        assert lookup.get_standing_for_hex("0604") == 5

        # Hex 0807 controlled by nag_lord - bad standing
        assert lookup.get_standing_for_hex("0807") == -3

    def test_different_modifiers_by_location(self, multi_faction_engine):
        """Test different modifiers based on location."""
        multi_faction_engine.party_state.adjust_standing("house_brackenwold", 8)
        multi_faction_engine.party_state.adjust_standing("nag_lord", -5)

        lookup = HexFactionLookup(multi_faction_engine)

        # In friendly territory - discount
        standing = lookup.get_standing_for_hex("0604")
        assert get_service_cost_multiplier(standing) == 0.75

        # In hostile territory - markup
        standing = lookup.get_standing_for_hex("0807")
        assert get_service_cost_multiplier(standing) == 1.25
