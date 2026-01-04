"""
Tests for hex 0108 action resolution - the _resolve_hex_hazard_result helper.

This helper provides consistent narrative + encounter structure for hazard outcomes.
"""

import pytest
from pathlib import Path

from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import DiceRoller, GameDate


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0108 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0108_the_cabbage_plot.json"))
    assert result.success, f"Failed to load hex 0108: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0108_engine(pipeline):
    """Create a HexCrawlEngine with hex 0108 loaded."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=1, day=1)
    engine = HexCrawlEngine(controller)
    engine._hex_data["0108"] = pipeline.get_hex("0108")
    return engine


# =============================================================================
# _resolve_hex_hazard_result TESTS
# =============================================================================


class TestResolveHexHazardResult:
    """Test the _resolve_hex_hazard_result helper method."""

    def test_returns_stable_structure_when_not_triggered(self, hex_0108_engine):
        """When hazard not triggered, should return stable structure with suggestions."""
        hazard_result = {
            "triggered": False,
            "description": "Nothing unusual happens.",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)

        assert result["resolved"] is True
        assert result["hazard_triggered"] is False
        assert result["encounter"] is None
        assert result["narrative"] == "Nothing unusual happens."
        assert isinstance(result["suggested_actions"], list)
        assert len(result["suggested_actions"]) > 0

    def test_returns_stable_structure_when_triggered(self, hex_0108_engine):
        """When hazard triggered, should return stable structure with encounter info."""
        hazard_result = {
            "triggered": True,
            "description": "Murkin's Soldiers arrive!",
            "result": "murkins_soldiers_arrive",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert result["resolved"] is True
        assert result["hazard_triggered"] is True
        assert result["encounter"] is not None
        assert isinstance(result["narrative"], str)
        assert isinstance(result["suggested_actions"], list)
        assert isinstance(result["rolls_made"], list)

    def test_matches_npc_by_partial_id(self, hex_0108_engine):
        """Should match NPC when result contains npc_id (e.g., 'murkins_soldiers_arrive')."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers approach.",
            "result": "murkins_soldiers_arrive",  # Contains "murkins_soldiers"
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert result["encounter"]["type"] == "npc_arrival"
        assert result["encounter"]["npc_id"] == "murkins_soldiers"
        assert result["encounter"]["is_combatant"] is True

    def test_rolls_group_size_for_group_npc(self, hex_0108_engine):
        """Should roll group size when NPC has group_count."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "3-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert result["npc_group"] is not None
        assert result["npc_group"]["is_group"] is True
        assert result["npc_group"]["total_count"] > 0

        # Should have group_size roll recorded
        group_rolls = [r for r in result["rolls_made"] if r["type"] == "group_size"]
        assert len(group_rolls) == 1
        assert group_rolls[0]["expression"] == "1d4+1d4"

    def test_records_hazard_trigger_roll(self, hex_0108_engine):
        """Should record the hazard trigger roll in rolls_made."""
        hazard_result = {
            "triggered": True,
            "description": "Event occurs.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        trigger_rolls = [r for r in result["rolls_made"] if r["type"] == "hazard_trigger"]
        assert len(trigger_rolls) == 1
        assert trigger_rolls[0]["chance"] == "2-in-6"
        assert trigger_rolls[0]["succeeded"] is True

    def test_provides_combat_suggestions_for_combatant_npc(self, hex_0108_engine):
        """Should provide combat-appropriate suggestions for combatant NPCs."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert "Prepare for combat" in result["suggested_actions"]
        assert "Attempt to negotiate" in result["suggested_actions"]

    def test_handles_unknown_result_as_event(self, hex_0108_engine):
        """When result doesn't match an NPC, should treat as narrative event."""
        hazard_result = {
            "triggered": True,
            "description": "Strange sounds echo.",
            "result": "unknown_event_id",
            "chance": "1-in-6",
        }
        context = {"hex_id": "0108"}

        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)

        assert result["encounter"]["type"] == "event"
        assert result["encounter"]["event_id"] == "unknown_event_id"
        assert "Investigate further" in result["suggested_actions"]

    def test_deterministic_with_seeded_dice(self, hex_0108_engine):
        """Results should be deterministic with same seed."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(12345)
        result1 = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)

        DiceRoller.set_seed(12345)
        result2 = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)

        DiceRoller._seed = None

        assert result1["npc_group"]["total_count"] == result2["npc_group"]["total_count"]


class TestIntegrationWithHazardChecks:
    """Test _resolve_hex_hazard_result integrates with hazard check methods."""

    def test_resolves_investigation_hazard_result(self, hex_0108_engine):
        """Should properly resolve output from check_investigation_hazard."""
        # Force hazard to trigger
        DiceRoller.set_seed(0)  # Low roll triggers 2-in-6

        hazard_result = hex_0108_engine.check_investigation_hazard(
            "0108", "investigate_cabbages"
        )

        if hazard_result["triggered"]:
            resolution = hex_0108_engine._resolve_hex_hazard_result(
                hazard_result, {"hex_id": "0108", "trigger_type": "investigation"}
            )
            assert resolution["resolved"] is True
            assert resolution["encounter"] is not None

        DiceRoller._seed = None

    def test_resolves_evening_hazard_result(self, hex_0108_engine):
        """Should properly resolve output from check_evening_hazard."""
        # Force hazard to trigger
        DiceRoller.set_seed(0)  # Low roll triggers 3-in-6

        hazard_result = hex_0108_engine.check_evening_hazard(
            "0108", "The Crimson Bath"
        )

        if hazard_result["triggered"]:
            resolution = hex_0108_engine._resolve_hex_hazard_result(
                hazard_result, {"hex_id": "0108", "trigger_type": "evening_stay"}
            )
            assert resolution["resolved"] is True
            assert resolution["encounter"] is not None

        DiceRoller._seed = None


# =============================================================================
# WILDERNESS:INVESTIGATE ACTION TESTS
# =============================================================================


class TestWildernessInvestigateAction:
    """Test the wilderness:investigate action in the action registry."""

    def test_action_registered(self):
        """wilderness:investigate should be registered in the action registry."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")
        assert spec is not None
        assert spec.id == "wilderness:investigate"
        assert spec.label == "Investigate the area"

    def test_action_executor_returns_no_hazard_for_wrong_trigger(self, hex_0108_engine):
        """Executor should return no hazard for non-matching trigger."""
        from unittest.mock import MagicMock

        # Create mock VirtualDM with hex_crawl pointing to our engine
        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        params = {"hex_id": "0108", "trigger": "investigate_trees"}
        result = spec.executor(mock_dm, params)

        assert result["success"] is True
        assert result["hazard_triggered"] is False
        assert "message" in result

    def test_action_executor_returns_hazard_when_triggered(self, hex_0108_engine):
        """Executor should return encounter info when hazard triggers."""
        from unittest.mock import MagicMock, patch

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        # Force hazard to trigger
        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            DiceRoller.set_seed(42)
            params = {"hex_id": "0108", "trigger": "investigate_cabbages"}
            result = spec.executor(mock_dm, params)
            DiceRoller._seed = None

        assert result["success"] is True
        assert result["hazard_triggered"] is True
        assert result["encounter"] is not None
        assert "message" in result

    def test_action_executor_includes_group_info(self, hex_0108_engine):
        """Executor should include NPC group info when hazard triggers NPC arrival."""
        from unittest.mock import MagicMock, patch

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            DiceRoller.set_seed(42)
            params = {"hex_id": "0108", "trigger": "investigate_cabbages"}
            result = spec.executor(mock_dm, params)
            DiceRoller._seed = None

        assert result.get("npc_group") is not None
        assert result["npc_group"]["is_group"] is True
        assert result["npc_group"]["total_count"] > 0

    def test_action_executor_includes_suggested_actions(self, hex_0108_engine):
        """Executor should include suggested follow-up actions."""
        from unittest.mock import MagicMock, patch

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            DiceRoller.set_seed(42)
            params = {"hex_id": "0108", "trigger": "investigate_cabbages"}
            result = spec.executor(mock_dm, params)
            DiceRoller._seed = None

        assert "suggested_actions" in result
        assert isinstance(result["suggested_actions"], list)
        assert len(result["suggested_actions"]) > 0


class TestInvestigateSuggestion:
    """Test that wilderness:investigate appears in suggestions for hex 0108."""

    def test_suggestion_appears_for_hex_with_investigation_hazard(self, hex_0108_engine):
        """Suggestion should appear for hex with investigation_hazard."""
        from unittest.mock import MagicMock
        from src.conversation.suggestion_builder import build_suggestions
        from src.game_state.state_machine import GameState

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.current_state = GameState.WILDERNESS_TRAVEL
        mock_dm.controller.party_state.location.location_id = "0108"
        mock_dm.controller.get_active_characters.return_value = []
        mock_dm.controller.get_all_characters.return_value = []

        # get_valid_actions returns empty list
        mock_dm.get_valid_actions.return_value = []

        suggestions = build_suggestions(mock_dm, limit=15)
        action_ids = [s.id for s in suggestions]

        assert "wilderness:investigate" in action_ids

    def test_suggestion_has_correct_trigger(self, hex_0108_engine):
        """Suggestion should have the trigger from the hazard definition."""
        from unittest.mock import MagicMock
        from src.conversation.suggestion_builder import build_suggestions
        from src.game_state.state_machine import GameState

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.current_state = GameState.WILDERNESS_TRAVEL
        mock_dm.controller.party_state.location.location_id = "0108"
        mock_dm.controller.get_active_characters.return_value = []
        mock_dm.controller.get_all_characters.return_value = []
        mock_dm.get_valid_actions.return_value = []

        suggestions = build_suggestions(mock_dm, limit=15)
        investigate_suggestion = next(
            (s for s in suggestions if s.id == "wilderness:investigate"), None
        )

        assert investigate_suggestion is not None
        assert investigate_suggestion.params.get("trigger") == "investigate_cabbages"


# =============================================================================
# CUSTOM ENCOUNTER TABLE TESTS (Task 3)
# =============================================================================


class TestCustomEncounterTableGeneration:
    """Test that hex 0108's encounter table influences encounter generation."""

    def test_try_custom_encounter_table_returns_encounter_for_npc_result(
        self, hex_0108_engine
    ):
        """When table roll hits NPC entry, should create NPC encounter."""
        from src.data_models import TerrainType, SurpriseStatus

        # Seed dice to roll 1 (which maps to murkins_soldiers)
        DiceRoller.set_seed(0)  # Will produce low roll

        hex_data = hex_0108_engine._hex_data.get("0108")
        result = hex_0108_engine._try_custom_encounter_table(
            hex_id="0108",
            hex_data=hex_data,
            terrain=TerrainType.FARMLAND,
            distance=60,
            surprise=SurpriseStatus.NO_SURPRISE,
        )

        DiceRoller._seed = None

        # The result depends on actual dice roll - if roll=1, should get NPC encounter
        if result is not None:
            assert result.context is not None
            assert "hex_encounter_table" in result.contextual_data.get("source", "")

    def test_try_custom_encounter_table_returns_none_for_standard_result(
        self, hex_0108_engine
    ):
        """When table roll hits 'standard', should return None to use default tables."""
        from src.data_models import TerrainType, SurpriseStatus
        from unittest.mock import patch

        hex_data = hex_0108_engine._hex_data.get("0108")

        # Mock roll_hex_encounter_table to return "standard"
        with patch.object(
            hex_0108_engine,
            "roll_hex_encounter_table",
            return_value={
                "has_table": True,
                "roll": 3,
                "result": "standard",
                "description": "Roll on standard regional table.",
                "table_name": "Hex 0108 Encounters",
            },
        ):
            result = hex_0108_engine._try_custom_encounter_table(
                hex_id="0108",
                hex_data=hex_data,
                terrain=TerrainType.FARMLAND,
                distance=60,
                surprise=SurpriseStatus.NO_SURPRISE,
            )

        assert result is None

    def test_create_npc_encounter_creates_group_combatants(self, hex_0108_engine):
        """NPC encounter should create correct number of combatants for groups."""
        from src.data_models import TerrainType, SurpriseStatus

        hex_data = hex_0108_engine._hex_data.get("0108")

        # Find murkins_soldiers NPC
        soldiers_npc = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers_npc = npc
                break

        assert soldiers_npc is not None

        # Create encounter with seeded dice for deterministic group size
        DiceRoller.set_seed(42)
        encounter = hex_0108_engine._create_npc_encounter(
            hex_id="0108",
            npc=soldiers_npc,
            terrain=TerrainType.FARMLAND,
            distance=60,
            surprise=SurpriseStatus.NO_SURPRISE,
            description="A gang of soldiers approach.",
        )
        DiceRoller._seed = None

        # Should have combatants (group NPC)
        assert len(encounter.combatants) > 0
        assert encounter.contextual_data.get("is_group") is True
        assert encounter.contextual_data.get("npc_id") == "murkins_soldiers"

    def test_create_npc_encounter_stores_faction_info(self, hex_0108_engine):
        """NPC encounter should store faction information for later use."""
        from src.data_models import TerrainType, SurpriseStatus

        hex_data = hex_0108_engine._hex_data.get("0108")

        # Find murkins_soldiers NPC
        soldiers_npc = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers_npc = npc
                break

        DiceRoller.set_seed(42)
        encounter = hex_0108_engine._create_npc_encounter(
            hex_id="0108",
            npc=soldiers_npc,
            terrain=TerrainType.FARMLAND,
            distance=60,
            surprise=SurpriseStatus.NO_SURPRISE,
            description="Soldiers approach.",
        )
        DiceRoller._seed = None

        assert encounter.contextual_data.get("faction") == "house_murkin"

    def test_find_npc_by_id_finds_exact_match(self, hex_0108_engine):
        """Should find NPC by exact ID match."""
        hex_data = hex_0108_engine._hex_data.get("0108")

        npc = hex_0108_engine._find_npc_by_id(hex_data, "murkins_soldiers")

        assert npc is not None
        assert npc.npc_id == "murkins_soldiers"

    def test_find_npc_by_id_finds_partial_match(self, hex_0108_engine):
        """Should find NPC by partial ID match."""
        hex_data = hex_0108_engine._hex_data.get("0108")

        # "murkins" should match "murkins_soldiers"
        npc = hex_0108_engine._find_npc_by_id(hex_data, "murkins")

        assert npc is not None
        assert "murkins" in npc.npc_id

    def test_find_npc_by_id_returns_none_for_unknown(self, hex_0108_engine):
        """Should return None for unknown NPC ID."""
        hex_data = hex_0108_engine._hex_data.get("0108")

        npc = hex_0108_engine._find_npc_by_id(hex_data, "unknown_npc_12345")

        assert npc is None

    def test_create_narrative_encounter_sets_contextual_data(self, hex_0108_engine):
        """Narrative encounters should have proper contextual data."""
        from src.data_models import TerrainType, SurpriseStatus

        encounter = hex_0108_engine._create_narrative_encounter(
            result_id="mysterious_event",
            description="Something strange happens.",
            terrain=TerrainType.FARMLAND,
            distance=60,
            surprise=SurpriseStatus.NO_SURPRISE,
        )

        assert encounter.contextual_data.get("source") == "hex_encounter_table"
        assert encounter.contextual_data.get("event_id") == "mysterious_event"
        assert encounter.contextual_data.get("is_narrative") is True

    def test_custom_table_used_before_standard_factory(self, hex_0108_engine):
        """When hex has custom table and roll=1, should use custom table result."""
        from src.data_models import TerrainType
        from unittest.mock import patch, MagicMock

        # Mock dice to always roll 1 (Murkin's Soldiers on hex 0108 table)
        with patch.object(hex_0108_engine.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 1
            mock_roll.return_value = mock_result

            # Also need to mock the group size roll
            DiceRoller.set_seed(42)

            encounter = hex_0108_engine._generate_encounter("0108", TerrainType.FARMLAND)

            DiceRoller._seed = None

        # Should have used custom table (indicated by contextual_data.source)
        assert encounter is not None
        if encounter.contextual_data:
            assert encounter.contextual_data.get("source") == "hex_encounter_table"
            assert encounter.contextual_data.get("npc_id") == "murkins_soldiers"


# =============================================================================
# MULTI-ACTOR GROUP ENCOUNTER TESTS (Task 4)
# =============================================================================


class TestMultiActorGroupEncounters:
    """Test that group NPCs spawn multiple actors/combatants."""

    def test_resolve_hex_hazard_creates_combatants_when_requested(self, hex_0108_engine):
        """_resolve_hex_hazard_result should create combatants when create_combatants=True."""
        from unittest.mock import patch

        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {
            "hex_id": "0108",
            "trigger_type": "investigation",
            "create_combatants": True,
        }

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert "combatants" in result
        assert isinstance(result["combatants"], list)
        assert len(result["combatants"]) > 0  # Group NPC creates multiple

    def test_each_combatant_has_unique_id(self, hex_0108_engine):
        """Each combatant in a group should have a unique ID."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {
            "hex_id": "0108",
            "trigger_type": "investigation",
            "create_combatants": True,
        }

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        combatants = result.get("combatants", [])
        combatant_ids = [c.combatant_id for c in combatants]

        # All IDs should be unique
        assert len(combatant_ids) == len(set(combatant_ids))

        # IDs should follow pattern like "murkins_soldiers_1", "murkins_soldiers_2"
        for i, cid in enumerate(combatant_ids):
            assert "murkins_soldiers" in cid
            assert str(i + 1) in cid

    def test_combatant_count_matches_group_size(self, hex_0108_engine):
        """Number of combatants should match the rolled group size."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {
            "hex_id": "0108",
            "trigger_type": "investigation",
            "create_combatants": True,
        }

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        combatants = result.get("combatants", [])
        npc_group = result.get("npc_group", {})

        # Combatant count should match group size
        assert len(combatants) == npc_group.get("total_count", 1)

    def test_create_combatants_for_hazard_npc_creates_group(self, hex_0108_engine):
        """_create_combatants_for_hazard_npc should create correct number of combatants."""
        hex_data = hex_0108_engine._hex_data.get("0108")
        soldiers_npc = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers_npc = npc
                break

        assert soldiers_npc is not None

        # Roll group size
        DiceRoller.set_seed(42)
        group_info = hex_0108_engine.get_npc_group_size("0108", "murkins_soldiers")
        combatants = hex_0108_engine._create_combatants_for_hazard_npc(
            soldiers_npc, "0108", group_info
        )
        DiceRoller._seed = None

        assert len(combatants) == group_info["total_count"]
        assert all(c.side == "enemy" for c in combatants)

    def test_investigate_action_returns_combatants(self, hex_0108_engine):
        """wilderness:investigate action should return combatants when hazard triggers."""
        from unittest.mock import MagicMock, patch
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            DiceRoller.set_seed(42)
            params = {"hex_id": "0108", "trigger": "investigate_cabbages"}
            result = spec.executor(mock_dm, params)
            DiceRoller._seed = None

        assert result["hazard_triggered"] is True
        assert "combatants" in result
        assert result["combatant_count"] > 0
        assert len(result["combatants"]) == result["combatant_count"]

    def test_evening_stay_action_returns_combatants(self, hex_0108_engine):
        """wilderness:evening_stay action should return combatants when hazard triggers."""
        from unittest.mock import MagicMock, patch
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        registry = get_default_registry()
        spec = registry.get("wilderness:evening_stay")

        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            DiceRoller.set_seed(42)
            params = {"hex_id": "0108", "poi_name": "The Crimson Bath"}
            result = spec.executor(mock_dm, params)
            DiceRoller._seed = None

        assert result["hazard_triggered"] is True
        assert "combatants" in result
        assert result["combatant_count"] > 0

    def test_create_encounter_from_hazard_creates_multi_actor_encounter(
        self, hex_0108_engine
    ):
        """create_encounter_from_hazard should create EncounterState with multiple combatants."""
        from unittest.mock import patch

        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108", "trigger_type": "investigation"}

        DiceRoller.set_seed(42)
        encounter = hex_0108_engine.create_encounter_from_hazard(hazard_result, context)
        DiceRoller._seed = None

        assert encounter is not None
        assert len(encounter.combatants) > 0
        assert encounter.contextual_data.get("is_group") is True

    def test_group_encounter_combatants_are_combat_ready(self, hex_0108_engine):
        """Combatants in group encounter should have stat blocks for combat."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {
            "hex_id": "0108",
            "trigger_type": "investigation",
            "create_combatants": True,
        }

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        for combatant in result.get("combatants", []):
            assert combatant.stat_block is not None
            assert combatant.stat_block.armor_class > 0
            assert combatant.stat_block.hp_max > 0


# =============================================================================
# Task 5: NPC Intelligence in Social Context
# =============================================================================


class TestNPCIntelligenceSerialization:
    """Test _serialize_npc_intelligence method for social context."""

    def test_serialize_npc_intelligence_includes_known_topics(self, hex_0108_engine):
        """Should serialize known_topics from HexNPC."""
        hex_data = hex_0108_engine._hex_data["0108"]
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break

        assert timilda is not None, "Timilda should exist in hex 0108"
        intel = hex_0108_engine._serialize_npc_intelligence(timilda)

        assert "known_topics" in intel
        assert len(intel["known_topics"]) > 0
        # Check topic structure
        for topic in intel["known_topics"]:
            assert "topic_id" in topic
            assert "content" in topic
            assert "keywords" in topic

    def test_serialize_npc_intelligence_includes_secret_info(self, hex_0108_engine):
        """Should serialize secret_info with bribery data from HexNPC."""
        hex_data = hex_0108_engine._hex_data["0108"]
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break

        assert soldiers is not None, "Murkin's soldiers should exist"
        intel = hex_0108_engine._serialize_npc_intelligence(soldiers)

        assert "secret_info" in intel
        # Check for bribery fields
        bribable_secrets = [s for s in intel["secret_info"] if s.get("can_be_bribed")]
        assert len(bribable_secrets) > 0, "Should have bribable secrets"

    def test_serialize_npc_intelligence_includes_faction_profile(self, hex_0108_engine):
        """Should serialize faction_profile for faction NPCs."""
        hex_data = hex_0108_engine._hex_data["0108"]
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break

        assert soldiers is not None
        intel = hex_0108_engine._serialize_npc_intelligence(soldiers)

        assert "faction" in intel
        assert intel["faction"] == "house_murkin"
        assert "faction_profile" in intel
        assert intel["faction_profile"]["role"] == "enforcers"

    def test_serialize_npc_intelligence_includes_relationships(self, hex_0108_engine):
        """Should serialize relationships for NPCs with connections."""
        hex_data = hex_0108_engine._hex_data["0108"]
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break

        assert timilda is not None
        intel = hex_0108_engine._serialize_npc_intelligence(timilda)

        assert "relationships" in intel
        assert len(intel["relationships"]) > 0

    def test_serialize_npc_intelligence_includes_vulnerabilities(self, hex_0108_engine):
        """Should serialize vulnerabilities for NPC manipulation hints."""
        hex_data = hex_0108_engine._hex_data["0108"]
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break

        assert timilda is not None
        intel = hex_0108_engine._serialize_npc_intelligence(timilda)

        assert "vulnerabilities" in intel
        assert len(intel["vulnerabilities"]) > 0


class TestNPCIntelligenceInSocialContext:
    """Test that NPC intelligence flows into social context participants."""

    def test_interact_with_npc_includes_intelligence_in_context(self, hex_0108_engine):
        """interact_with_npc should include npc_intelligence in transition context."""
        # Setup engine state
        hex_0108_engine._current_hex = "0108"
        hex_0108_engine._current_poi = "The Crimson Bath"

        # Capture the context passed to transition
        captured_context = {}

        def capture_transition(trigger, context=None):
            captured_context.update(context or {})

        hex_0108_engine.controller.transition = capture_transition

        # Call interact_with_npc
        result = hex_0108_engine.interact_with_npc("0108", "timilda_brumble")

        assert result["success"] is True
        assert "npc_intelligence" in captured_context
        intel = captured_context["npc_intelligence"]

        # Verify intelligence structure
        assert intel["npc_id"] == "timilda_brumble"
        assert "known_topics" in intel
        assert "secret_info" in intel

    def test_build_participant_from_intelligence_creates_rich_participant(
        self, hex_0108_engine
    ):
        """_build_participant_from_intelligence should create participant with full intelligence."""
        from src.game_state.global_controller import GlobalController

        # Get intelligence data
        hex_data = hex_0108_engine._hex_data["0108"]
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break

        intel = hex_0108_engine._serialize_npc_intelligence(timilda)

        # Build participant
        controller = GlobalController()
        participant = controller._build_participant_from_intelligence(
            npc_id="timilda_brumble",
            npc_name="Timilda Brumble",
            npc_intel=intel,
            context={"hex_id": "0108", "poi_name": "The Crimson Bath", "disposition": 0},
        )

        # Verify participant has intelligence
        assert participant.participant_id == "timilda_brumble"
        assert participant.name == "Timilda Brumble"
        assert len(participant.known_topics) > 0
        assert len(participant.secret_info) > 0
        assert participant.hex_id == "0108"

    def test_participant_known_topics_are_structured(self, hex_0108_engine):
        """Participant's known_topics should be KnownTopic objects with proper fields."""
        from src.game_state.global_controller import GlobalController
        from src.data_models import KnownTopic

        hex_data = hex_0108_engine._hex_data["0108"]
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break

        intel = hex_0108_engine._serialize_npc_intelligence(timilda)
        controller = GlobalController()
        participant = controller._build_participant_from_intelligence(
            npc_id="timilda_brumble",
            npc_name="Timilda Brumble",
            npc_intel=intel,
            context={"hex_id": "0108", "disposition": 0},
        )

        # Verify topics are proper KnownTopic objects
        for topic in participant.known_topics:
            assert isinstance(topic, KnownTopic)
            assert topic.topic_id != ""
            assert topic.content != ""

    def test_participant_secret_info_includes_bribery(self, hex_0108_engine):
        """Participant's secret_info should include bribery hints from source NPC."""
        from src.game_state.global_controller import GlobalController
        from src.data_models import SecretInfo

        hex_data = hex_0108_engine._hex_data["0108"]
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break

        intel = hex_0108_engine._serialize_npc_intelligence(soldiers)
        controller = GlobalController()
        participant = controller._build_participant_from_intelligence(
            npc_id="murkins_soldiers",
            npc_name="Murkin's Soldiers",
            npc_intel=intel,
            context={"hex_id": "0108", "disposition": 0},
        )

        # Check for bribable secrets
        bribable = [s for s in participant.secret_info if s.can_be_bribed]
        assert len(bribable) > 0, "Should have bribable secrets"
        for secret in bribable:
            assert isinstance(secret, SecretInfo)
            assert secret.bribe_amount >= 0

    def test_participant_faction_profile_in_personality(self, hex_0108_engine):
        """Participant's personality should include faction profile info."""
        from src.game_state.global_controller import GlobalController

        hex_data = hex_0108_engine._hex_data["0108"]
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break

        intel = hex_0108_engine._serialize_npc_intelligence(soldiers)
        controller = GlobalController()
        participant = controller._build_participant_from_intelligence(
            npc_id="murkins_soldiers",
            npc_name="Murkin's Soldiers",
            npc_intel=intel,
            context={"hex_id": "0108", "disposition": 0},
        )

        # Faction profile should be reflected in personality
        assert participant.faction == "house_murkin"
        assert "enforcer" in participant.personality.lower()

    def test_participant_vulnerabilities_in_secrets(self, hex_0108_engine):
        """Participant's secrets list should include vulnerability hints."""
        from src.game_state.global_controller import GlobalController

        hex_data = hex_0108_engine._hex_data["0108"]
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break

        intel = hex_0108_engine._serialize_npc_intelligence(timilda)
        controller = GlobalController()
        participant = controller._build_participant_from_intelligence(
            npc_id="timilda_brumble",
            npc_name="Timilda Brumble",
            npc_intel=intel,
            context={"hex_id": "0108", "disposition": 0},
        )

        # Vulnerabilities should be in secrets list
        vuln_secrets = [s for s in participant.secrets if "Vulnerable to:" in s]
        assert len(vuln_secrets) > 0, "Should have vulnerability hints in secrets"

    def test_participant_relationships_preserved(self, hex_0108_engine):
        """Participant's relationships should be preserved from source NPC."""
        from src.game_state.global_controller import GlobalController

        hex_data = hex_0108_engine._hex_data["0108"]
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break

        intel = hex_0108_engine._serialize_npc_intelligence(timilda)
        controller = GlobalController()
        participant = controller._build_participant_from_intelligence(
            npc_id="timilda_brumble",
            npc_name="Timilda Brumble",
            npc_intel=intel,
            context={"hex_id": "0108", "disposition": 0},
        )

        assert len(participant.relationships) > 0
        # Check relationship structure
        for rel in participant.relationships:
            assert isinstance(rel, dict)
            assert "npc_id" in rel or "relationship_type" in rel


# =============================================================================
# Task 6: Roll Hex Encounter Table Action
# =============================================================================


class TestRollHexEncounterTableAction:
    """Test the wilderness:roll_hex_encounter_table action."""

    def test_action_registered(self):
        """wilderness:roll_hex_encounter_table should be registered."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:roll_hex_encounter_table")
        assert spec is not None
        assert spec.id == "wilderness:roll_hex_encounter_table"
        assert spec.label == "Roll hex encounter table"

    def test_action_returns_table_result_for_hex_with_table(self, hex_0108_engine):
        """Action should return table result for hex with custom table."""
        from unittest.mock import MagicMock
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        registry = get_default_registry()
        spec = registry.get("wilderness:roll_hex_encounter_table")

        DiceRoller.set_seed(42)
        params = {"hex_id": "0108"}
        result = spec.executor(mock_dm, params)
        DiceRoller._seed = None

        assert result["success"] is True
        assert result["has_table"] is True
        assert "roll" in result
        assert "result" in result
        assert "table_name" in result
        assert "message" in result

    def test_action_returns_no_table_for_hex_without_table(self, hex_0108_engine):
        """Action should indicate no table for hex without custom table."""
        from unittest.mock import MagicMock
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        registry = get_default_registry()
        spec = registry.get("wilderness:roll_hex_encounter_table")

        # Hex 0100 doesn't exist in our fixture
        params = {"hex_id": "0100"}
        result = spec.executor(mock_dm, params)

        assert result["success"] is True
        assert result["has_table"] is False
        assert "no custom encounter table" in result["message"].lower()

    def test_action_suggests_encounter_for_npc_result(self, hex_0108_engine):
        """When result is NPC, should suggest start encounter action."""
        from unittest.mock import MagicMock, patch
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        registry = get_default_registry()
        spec = registry.get("wilderness:roll_hex_encounter_table")

        # Mock roll_hex_encounter_table to return NPC result
        with patch.object(
            hex_0108_engine,
            "roll_hex_encounter_table",
            return_value={
                "has_table": True,
                "roll": 1,
                "result": "murkins_soldiers",
                "description": "A gang of Murkin's soldiers approach.",
                "table_name": "Hex 0108 Encounters",
            },
        ):
            params = {"hex_id": "0108"}
            result = spec.executor(mock_dm, params)

        assert result["success"] is True
        assert result["result"] == "murkins_soldiers"
        assert "suggested_actions" in result
        # Should suggest start encounter for combatant NPC
        action_ids = [a["id"] for a in result["suggested_actions"]]
        assert "wilderness:start_encounter" in action_ids

    def test_action_suggests_talk_for_npc_result(self, hex_0108_engine):
        """When result is NPC, should suggest talk action."""
        from unittest.mock import MagicMock, patch
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        registry = get_default_registry()
        spec = registry.get("wilderness:roll_hex_encounter_table")

        # Mock roll_hex_encounter_table to return NPC result
        with patch.object(
            hex_0108_engine,
            "roll_hex_encounter_table",
            return_value={
                "has_table": True,
                "roll": 1,
                "result": "murkins_soldiers",
                "description": "A gang of Murkin's soldiers approach.",
                "table_name": "Hex 0108 Encounters",
            },
        ):
            params = {"hex_id": "0108"}
            result = spec.executor(mock_dm, params)

        # Should suggest talk action for any NPC
        action_ids = [a["id"] for a in result["suggested_actions"]]
        assert "wilderness:talk_npc" in action_ids

    def test_action_no_suggestions_for_standard_result(self, hex_0108_engine):
        """When result is 'standard', should have no NPC suggestions."""
        from unittest.mock import MagicMock, patch
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        registry = get_default_registry()
        spec = registry.get("wilderness:roll_hex_encounter_table")

        # Mock roll_hex_encounter_table to return standard result
        with patch.object(
            hex_0108_engine,
            "roll_hex_encounter_table",
            return_value={
                "has_table": True,
                "roll": 3,
                "result": "standard",
                "description": "Roll on standard regional table.",
                "table_name": "Hex 0108 Encounters",
            },
        ):
            params = {"hex_id": "0108"}
            result = spec.executor(mock_dm, params)

        assert result["success"] is True
        assert result["result"] == "standard"
        # No NPC-related suggestions for standard
        assert len(result.get("suggested_actions", [])) == 0


class TestRollHexEncounterTableSuggestion:
    """Test that roll_hex_encounter_table appears in suggestions."""

    def test_suggestion_appears_for_hex_with_encounter_table(self, hex_0108_engine):
        """Suggestion should appear for hex with custom encounter table."""
        from unittest.mock import MagicMock
        from src.conversation.suggestion_builder import build_suggestions
        from src.game_state.state_machine import GameState

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.current_state = GameState.WILDERNESS_TRAVEL
        mock_dm.controller.party_state.location.location_id = "0108"
        mock_dm.controller.get_active_characters.return_value = []
        mock_dm.controller.get_all_characters.return_value = []
        mock_dm.get_valid_actions.return_value = []

        suggestions = build_suggestions(mock_dm, limit=20)
        action_ids = [s.id for s in suggestions]

        assert "wilderness:roll_hex_encounter_table" in action_ids

    def test_suggestion_has_table_name_in_label(self, hex_0108_engine):
        """Suggestion label should include the table name."""
        from unittest.mock import MagicMock
        from src.conversation.suggestion_builder import build_suggestions
        from src.game_state.state_machine import GameState

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.current_state = GameState.WILDERNESS_TRAVEL
        mock_dm.controller.party_state.location.location_id = "0108"
        mock_dm.controller.get_active_characters.return_value = []
        mock_dm.controller.get_all_characters.return_value = []
        mock_dm.get_valid_actions.return_value = []

        suggestions = build_suggestions(mock_dm, limit=20)
        encounter_suggestion = next(
            (s for s in suggestions if s.id == "wilderness:roll_hex_encounter_table"),
            None,
        )

        assert encounter_suggestion is not None
        # Label should contain "Roll" and some table reference
        assert "Roll" in encounter_suggestion.label


# =============================================================================
# Task 7: Sleep at POI (Inn Rest) Action
# =============================================================================


class TestSleepAtPOI:
    """Test the sleep_at_poi method for inn rest mechanics."""

    def test_sleep_at_poi_returns_success_for_valid_poi(self, hex_0108_engine):
        """sleep_at_poi should return success for a valid POI."""
        # Set a seed to make hazard check deterministic (no hazard)
        DiceRoller.set_seed(100)
        result = hex_0108_engine.sleep_at_poi("0108", "The Crimson Bath")
        DiceRoller._seed = None

        assert result["success"] is True
        assert result["poi_name"] == "The Crimson Bath"
        assert result["hex_id"] == "0108"
        assert result["time_advanced"] == 8

    def test_sleep_at_poi_returns_error_for_invalid_hex(self, hex_0108_engine):
        """sleep_at_poi should return error for nonexistent hex."""
        result = hex_0108_engine.sleep_at_poi("9999", "Some Inn")

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_sleep_at_poi_returns_error_for_invalid_poi(self, hex_0108_engine):
        """sleep_at_poi should return error for nonexistent POI."""
        result = hex_0108_engine.sleep_at_poi("0108", "Nonexistent Tavern")

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_sleep_at_poi_checks_evening_hazard(self, hex_0108_engine):
        """sleep_at_poi should check for evening hazards."""
        # Seed to trigger hazard (3-in-6 for Crimson Bath)
        DiceRoller.set_seed(1)  # Roll 1 triggers hazard
        result = hex_0108_engine.sleep_at_poi("0108", "The Crimson Bath")
        DiceRoller._seed = None

        # Hazard should be recorded in result
        assert "evening_hazard" in result

    def test_sleep_at_poi_heals_characters(self, hex_0108_engine):
        """sleep_at_poi should heal characters who can recover HP."""
        from src.data_models import CharacterState

        # Create a test character with reduced HP
        char = CharacterState(
            character_id="test_char",
            name="Test Fighter",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=5,
            hp_max=10,
            armor_class=14,
            base_speed=40,
        )
        hex_0108_engine.controller._characters["test_char"] = char

        # Use high seed to avoid evening hazard triggering
        DiceRoller.set_seed(100)
        result = hex_0108_engine.sleep_at_poi("0108", "The Crimson Bath", ["test_char"])
        DiceRoller._seed = None

        assert result["success"] is True
        assert len(result["rest_results"]) == 1
        char_result = result["rest_results"][0]
        assert char_result["character_id"] == "test_char"
        assert char_result["hp_recovered"] == 1  # 1 HP per Dolmenwood rules

    def test_sleep_at_poi_respects_restless_sleep_condition(self, hex_0108_engine):
        """sleep_at_poi should not heal characters with restless_sleep condition."""
        from src.data_models import CharacterState, Condition, ConditionType

        # Create a character with restless_sleep
        char = CharacterState(
            character_id="restless_char",
            name="Restless Sleeper",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=5,
            hp_max=10,
            armor_class=14,
            base_speed=40,
        )
        restless = Condition(
            condition_type=ConditionType.RESTLESS_SLEEP,
            source="hex_effect",
        )
        char.conditions.append(restless)
        hex_0108_engine.controller._characters["restless_char"] = char

        # Use high seed to avoid evening hazard
        DiceRoller.set_seed(100)
        result = hex_0108_engine.sleep_at_poi("0108", "The Crimson Bath", ["restless_char"])
        DiceRoller._seed = None

        assert result["success"] is True
        char_result = result["rest_results"][0]
        assert char_result["hp_recovered"] == 0
        assert "restless_sleep" in char_result["conditions_blocking"]

    def test_sleep_at_poi_advances_time(self, hex_0108_engine):
        """sleep_at_poi should advance game time by 8 hours."""
        from unittest.mock import MagicMock
        from src.data_models import CharacterState

        # Create a test character so rest proceeds
        char = CharacterState(
            character_id="time_test_char",
            name="Time Tester",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=14,
            base_speed=40,
        )
        hex_0108_engine.controller._characters["time_test_char"] = char

        # Mock advance_time to capture call
        hex_0108_engine.controller.advance_time = MagicMock()

        DiceRoller.set_seed(100)
        hex_0108_engine.sleep_at_poi("0108", "The Crimson Bath", ["time_test_char"])
        DiceRoller._seed = None

        # 48 turns = 8 hours (6 turns per hour)
        hex_0108_engine.controller.advance_time.assert_called_with(48)


class TestSleepAtPOIAction:
    """Test the wilderness:sleep_at_poi action registration."""

    def test_action_registered(self):
        """wilderness:sleep_at_poi should be registered."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:sleep_at_poi")
        assert spec is not None
        assert spec.id == "wilderness:sleep_at_poi"
        assert "Sleep" in spec.label or "sleep" in spec.label.lower()

    def test_action_requires_poi_name(self, hex_0108_engine):
        """Action should require poi_name parameter."""
        from unittest.mock import MagicMock
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.hex_crawl.current_hex_id = "0108"
        mock_dm.hex_crawl._current_poi = None  # No current POI

        registry = get_default_registry()
        spec = registry.get("wilderness:sleep_at_poi")

        result = spec.executor(mock_dm, {})  # No poi_name

        assert result["success"] is False
        assert "poi_name" in result["message"].lower() or "no poi" in result["message"].lower()

    def test_action_calls_sleep_at_poi_engine_method(self, hex_0108_engine):
        """Action should call engine's sleep_at_poi method."""
        from unittest.mock import MagicMock
        from src.conversation.action_registry import get_default_registry

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.hex_crawl.current_hex_id = "0108"

        registry = get_default_registry()
        spec = registry.get("wilderness:sleep_at_poi")

        DiceRoller.set_seed(100)
        result = spec.executor(mock_dm, {"hex_id": "0108", "poi_name": "The Crimson Bath"})
        DiceRoller._seed = None

        assert result["success"] is True
        assert result["poi_name"] == "The Crimson Bath"


class TestSleepAtPOISuggestion:
    """Test that sleep_at_poi appears in suggestions."""

    def test_suggestion_appears_when_at_poi(self, hex_0108_engine):
        """Suggestion should appear when party is at a POI."""
        from unittest.mock import MagicMock
        from src.conversation.suggestion_builder import build_suggestions
        from src.game_state.state_machine import GameState

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.hex_crawl._current_poi = "The Crimson Bath"
        mock_dm.current_state = GameState.WILDERNESS_TRAVEL
        mock_dm.controller.party_state.location.location_id = "0108"
        mock_dm.controller.get_active_characters.return_value = []
        mock_dm.controller.get_all_characters.return_value = []
        mock_dm.get_valid_actions.return_value = []

        # Set up POI state
        def mock_get_poi_state(hex_id):
            return {
                "at_poi": True,
                "poi_name": "The Crimson Bath",
                "can_enter": True,
                "requires_hazard_resolution": False,
            }
        mock_dm.hex_crawl.get_poi_state = mock_get_poi_state

        suggestions = build_suggestions(mock_dm, limit=30)
        action_ids = [s.id for s in suggestions]

        assert "wilderness:sleep_at_poi" in action_ids

    def test_suggestion_includes_poi_name(self, hex_0108_engine):
        """Suggestion should include the POI name in the label."""
        from unittest.mock import MagicMock
        from src.conversation.suggestion_builder import build_suggestions
        from src.game_state.state_machine import GameState

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.hex_crawl._current_poi = "The Crimson Bath"
        mock_dm.current_state = GameState.WILDERNESS_TRAVEL
        mock_dm.controller.party_state.location.location_id = "0108"
        mock_dm.controller.get_active_characters.return_value = []
        mock_dm.controller.get_all_characters.return_value = []
        mock_dm.get_valid_actions.return_value = []

        def mock_get_poi_state(hex_id):
            return {
                "at_poi": True,
                "poi_name": "The Crimson Bath",
                "can_enter": True,
                "requires_hazard_resolution": False,
            }
        mock_dm.hex_crawl.get_poi_state = mock_get_poi_state

        suggestions = build_suggestions(mock_dm, limit=30)
        sleep_suggestion = next(
            (s for s in suggestions if s.id == "wilderness:sleep_at_poi"),
            None,
        )

        assert sleep_suggestion is not None
        assert "Crimson Bath" in sleep_suggestion.label