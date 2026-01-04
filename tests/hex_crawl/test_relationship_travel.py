"""
Tests for cross-hex relationship travel suggestions (Task 11).

This test suite validates:
- Travel suggestions appear for NPC relationships with hex_id
- Lady Borrid suggests travel to hex 0208 (Lord Murkin) and 0108 (Timilda)
- Snidebleat suggests travel to hex 0208 (Lord Murkin) and 0311 (Red Gwen)
- Suggestions exclude relationships in the same hex
"""

import pytest
from unittest.mock import MagicMock, PropertyMock


# =============================================================================
# RELATIONSHIP STRUCTURE TESTS
# =============================================================================


class TestRelationshipStructure:
    """Test that relationship data is correctly structured."""

    def test_lady_borrid_has_cross_hex_relationships(self):
        """Lady Borrid should have relationships with hex_id."""
        from pathlib import Path
        from src.content_loader.content_pipeline import ContentPipeline
        from src.content_loader.hex_loader import HexDataLoader

        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)
        result = loader.load_file(
            Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
        )
        assert result.success

        hex_data = pipeline.get_hex("0109")

        # Find Lady Borrid
        lady_borrid = None
        for npc in hex_data.npcs:
            npc_id = getattr(npc, "npc_id", None) or (npc.get("npc_id") if isinstance(npc, dict) else None)
            if npc_id == "lady_amonie_borrid":
                lady_borrid = npc
                break

        assert lady_borrid is not None, "Lady Borrid should exist as NPC"

        # Check relationships
        relationships = getattr(lady_borrid, "relationships", [])
        assert len(relationships) >= 2, "Lady Borrid should have at least 2 relationships"

        # Check for cross-hex connections
        cross_hex = [r for r in relationships if r.get("hex_id") and r.get("hex_id") != "0109"]
        assert len(cross_hex) >= 2, "Lady Borrid should have cross-hex connections"

        # Verify specific relationships
        hex_ids = [r.get("hex_id") for r in cross_hex]
        assert "0208" in hex_ids, "Lady Borrid should have relationship to hex 0208 (Lord Murkin)"
        assert "0108" in hex_ids, "Lady Borrid should have relationship to hex 0108 (Timilda)"

    def test_snidebleat_has_cross_hex_relationships(self):
        """Snidebleat should have relationships with hex_id."""
        from pathlib import Path
        from src.content_loader.content_pipeline import ContentPipeline
        from src.content_loader.hex_loader import HexDataLoader

        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)
        result = loader.load_file(
            Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
        )
        assert result.success

        hex_data = pipeline.get_hex("0109")

        # Find Snidebleat
        snidebleat = None
        for npc in hex_data.npcs:
            npc_id = getattr(npc, "npc_id", None) or (npc.get("npc_id") if isinstance(npc, dict) else None)
            if npc_id == "sergeant_crewwin_snidebleat":
                snidebleat = npc
                break

        assert snidebleat is not None, "Snidebleat should exist as NPC"

        # Check relationships
        relationships = getattr(snidebleat, "relationships", [])
        assert len(relationships) >= 2, "Snidebleat should have at least 2 relationships"

        # Check for cross-hex connections
        cross_hex = [r for r in relationships if r.get("hex_id") and r.get("hex_id") != "0109"]
        assert len(cross_hex) >= 2, "Snidebleat should have cross-hex connections"

        # Verify specific relationships
        hex_ids = [r.get("hex_id") for r in cross_hex]
        assert "0208" in hex_ids, "Snidebleat should have relationship to hex 0208 (Lord Murkin)"
        assert "0311" in hex_ids, "Snidebleat should have relationship to hex 0311 (Red Gwen)"


# =============================================================================
# SUGGESTION BUILDER TESTS
# =============================================================================


class TestCrossHexTravelSuggestions:
    """Test that travel suggestions are generated from relationships."""

    def _create_mock_dm_with_participant(self, relationships, current_hex="0109"):
        """Create a mock DM with social context."""
        dm = MagicMock()

        # Create participant with relationships
        participant = MagicMock()
        participant.name = "Test NPC"
        participant.hex_id = current_hex
        participant.relationships = relationships
        participant.secret_info = []

        # Set up social context
        social_context = MagicMock()
        social_context.participants = [participant]
        social_context.hex_id = current_hex

        # Set up controller
        controller = MagicMock()
        type(controller).social_context = PropertyMock(return_value=social_context)
        controller.party_state = MagicMock()
        controller.party_state.gold_gp = 0

        dm.controller = controller

        return dm

    def test_travel_suggestions_from_relationships(self):
        """Travel suggestions should appear for cross-hex relationships."""
        from src.conversation.suggestion_builder import _social_suggestions

        relationships = [
            {
                "npc_id": "lord_murkin",
                "relationship_type": "family",
                "description": "Cousin who rules hex 0208",
                "hex_id": "0208",
            },
            {
                "npc_id": "timilda_brumble",
                "relationship_type": "secret_ally",
                "description": "Ally in the rebellion",
                "hex_id": "0108",
            },
        ]

        dm = self._create_mock_dm_with_participant(relationships)

        suggestions = _social_suggestions(dm, "char_1")

        # Find travel suggestions
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        assert len(travel_suggestions) == 2, "Should have 2 travel suggestions"

        # Check hex IDs
        hex_ids = [s.action.params.get("hex_id") for s in travel_suggestions]
        assert "0208" in hex_ids, "Should suggest travel to 0208"
        assert "0108" in hex_ids, "Should suggest travel to 0108"

    def test_travel_suggestion_labels_include_relationship_type(self):
        """Travel suggestion labels should describe the relationship."""
        from src.conversation.suggestion_builder import _social_suggestions

        relationships = [
            {
                "npc_id": "lord_murkin",
                "relationship_type": "family",
                "description": "Family connection",
                "hex_id": "0208",
            },
        ]

        dm = self._create_mock_dm_with_participant(relationships)

        suggestions = _social_suggestions(dm, "char_1")
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        assert len(travel_suggestions) == 1
        label = travel_suggestions[0].action.label

        assert "0208" in label, "Label should include hex ID"
        assert "lord_murkin" in label, "Label should include NPC name"
        assert "family" in label, "Label should include relationship type"

    def test_no_suggestion_for_same_hex(self):
        """Should not suggest travel to the current hex."""
        from src.conversation.suggestion_builder import _social_suggestions

        relationships = [
            {
                "npc_id": "brynne_giant_weasel",
                "relationship_type": "animal_companion",
                "description": "Loyal companion",
                "hex_id": "0109",  # Same hex
            },
            {
                "npc_id": "lord_murkin",
                "relationship_type": "family",
                "description": "Cousin",
                "hex_id": "0208",
            },
        ]

        dm = self._create_mock_dm_with_participant(relationships, current_hex="0109")

        suggestions = _social_suggestions(dm, "char_1")
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        # Should only have one suggestion (to 0208, not 0109)
        assert len(travel_suggestions) == 1
        assert travel_suggestions[0].action.params.get("hex_id") == "0208"

    def test_employer_relationship_label(self):
        """Employer relationships should have appropriate label."""
        from src.conversation.suggestion_builder import _social_suggestions

        relationships = [
            {
                "npc_id": "lord_murkin",
                "relationship_type": "employer",
                "description": "Serves as knight",
                "hex_id": "0208",
            },
        ]

        dm = self._create_mock_dm_with_participant(relationships)

        suggestions = _social_suggestions(dm, "char_1")
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        assert len(travel_suggestions) == 1
        assert "employer" in travel_suggestions[0].action.label

    def test_secret_correspondent_relationship_label(self):
        """Secret correspondent relationships should have appropriate label."""
        from src.conversation.suggestion_builder import _social_suggestions

        relationships = [
            {
                "npc_id": "red_gwen",
                "relationship_type": "secret_correspondent",
                "description": "Secret correspondence about alliance",
                "hex_id": "0311",
            },
        ]

        dm = self._create_mock_dm_with_participant(relationships)

        suggestions = _social_suggestions(dm, "char_1")
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        assert len(travel_suggestions) == 1
        assert "correspondent" in travel_suggestions[0].action.label

    def test_limit_to_three_suggestions(self):
        """Should limit travel suggestions to 3."""
        from src.conversation.suggestion_builder import _social_suggestions

        relationships = [
            {"npc_id": "npc_1", "relationship_type": "ally", "hex_id": "0101"},
            {"npc_id": "npc_2", "relationship_type": "ally", "hex_id": "0102"},
            {"npc_id": "npc_3", "relationship_type": "ally", "hex_id": "0103"},
            {"npc_id": "npc_4", "relationship_type": "ally", "hex_id": "0104"},
            {"npc_id": "npc_5", "relationship_type": "ally", "hex_id": "0105"},
        ]

        dm = self._create_mock_dm_with_participant(relationships)

        suggestions = _social_suggestions(dm, "char_1")
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        assert len(travel_suggestions) == 3, "Should limit to 3 travel suggestions"

    def test_help_text_uses_description(self):
        """Help text should use relationship description."""
        from src.conversation.suggestion_builder import _social_suggestions

        relationships = [
            {
                "npc_id": "lord_murkin",
                "relationship_type": "family",
                "description": "Maternal cousin who rules hex 0208",
                "hex_id": "0208",
            },
        ]

        dm = self._create_mock_dm_with_participant(relationships)

        suggestions = _social_suggestions(dm, "char_1")
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        assert len(travel_suggestions) == 1
        help_text = travel_suggestions[0].action.help
        assert "Maternal cousin" in help_text

    def test_no_suggestions_without_social_context(self):
        """Should handle missing social context gracefully."""
        from src.conversation.suggestion_builder import _social_suggestions

        dm = MagicMock()
        dm.controller.social_context = None

        suggestions = _social_suggestions(dm, "char_1")

        # Should still return standard social suggestions
        assert len(suggestions) > 0
        # But no travel suggestions
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]
        assert len(travel_suggestions) == 0


# =============================================================================
# INTEGRATION TESTS WITH HEX DATA
# =============================================================================


class TestLadyBorridTravelSuggestions:
    """Integration test with actual Lady Borrid data."""

    def test_lady_borrid_produces_travel_suggestions(self):
        """Talking to Lady Borrid should produce travel suggestions."""
        from pathlib import Path
        from src.content_loader.content_pipeline import ContentPipeline
        from src.content_loader.hex_loader import HexDataLoader
        from src.conversation.suggestion_builder import _social_suggestions

        # Load hex data
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)
        result = loader.load_file(
            Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
        )
        assert result.success

        hex_data = pipeline.get_hex("0109")

        # Find Lady Borrid
        lady_borrid = None
        for npc in hex_data.npcs:
            npc_id = getattr(npc, "npc_id", None) or (npc.get("npc_id") if isinstance(npc, dict) else None)
            if npc_id == "lady_amonie_borrid":
                lady_borrid = npc
                break

        assert lady_borrid is not None

        # Create mock DM with Lady Borrid's actual relationships
        relationships = getattr(lady_borrid, "relationships", [])

        dm = MagicMock()
        participant = MagicMock()
        participant.name = "Lady Amonie Borrid"
        participant.hex_id = "0109"
        participant.relationships = relationships
        participant.secret_info = []

        social_context = MagicMock()
        social_context.participants = [participant]
        social_context.hex_id = "0109"

        type(dm.controller).social_context = PropertyMock(return_value=social_context)
        dm.controller.party_state = MagicMock()
        dm.controller.party_state.gold_gp = 0

        suggestions = _social_suggestions(dm, "char_1")
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        # Lady Borrid has relationships to 0208 and 0108
        assert len(travel_suggestions) >= 2

        hex_ids = [s.action.params.get("hex_id") for s in travel_suggestions]
        assert "0208" in hex_ids, "Should suggest travel to Lord Murkin's hex"
        assert "0108" in hex_ids, "Should suggest travel to Timilda's hex"


class TestSnidebleatTravelSuggestions:
    """Integration test with actual Snidebleat data."""

    def test_snidebleat_produces_travel_suggestions(self):
        """Talking to Snidebleat should produce travel suggestions."""
        from pathlib import Path
        from src.content_loader.content_pipeline import ContentPipeline
        from src.content_loader.hex_loader import HexDataLoader
        from src.conversation.suggestion_builder import _social_suggestions

        # Load hex data
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)
        result = loader.load_file(
            Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
        )
        assert result.success

        hex_data = pipeline.get_hex("0109")

        # Find Snidebleat
        snidebleat = None
        for npc in hex_data.npcs:
            npc_id = getattr(npc, "npc_id", None) or (npc.get("npc_id") if isinstance(npc, dict) else None)
            if npc_id == "sergeant_crewwin_snidebleat":
                snidebleat = npc
                break

        assert snidebleat is not None

        # Create mock DM with Snidebleat's actual relationships
        relationships = getattr(snidebleat, "relationships", [])

        dm = MagicMock()
        participant = MagicMock()
        participant.name = "Sergeant Crewwin Snidebleat"
        participant.hex_id = "0109"
        participant.relationships = relationships
        participant.secret_info = []

        social_context = MagicMock()
        social_context.participants = [participant]
        social_context.hex_id = "0109"

        type(dm.controller).social_context = PropertyMock(return_value=social_context)
        dm.controller.party_state = MagicMock()
        dm.controller.party_state.gold_gp = 0

        suggestions = _social_suggestions(dm, "char_1")
        travel_suggestions = [s for s in suggestions if s.action.id == "wilderness:travel"]

        # Snidebleat has relationships to 0208 and 0311
        assert len(travel_suggestions) >= 2

        hex_ids = [s.action.params.get("hex_id") for s in travel_suggestions]
        assert "0208" in hex_ids, "Should suggest travel to Lord Murkin's hex"
        assert "0311" in hex_ids, "Should suggest travel to Red Gwen's hex"
