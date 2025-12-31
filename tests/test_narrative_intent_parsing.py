"""
Unit tests for narrative intent parsing (Upgrade A Extension).

Tests the NarrativeIntentSchema, NarrativeIntentOutput, and the
integration with ParsedIntent for the NarrativeResolver.
"""

import pytest
from dataclasses import asdict

from src.ai.prompt_schemas import (
    NarrativeIntentInputs,
    NarrativeIntentOutput,
    NarrativeIntentSchema,
    PromptSchemaType,
)
from src.narrative.intent_parser import (
    ParsedIntent,
    ActionCategory,
    ActionType,
    ResolutionType,
    CheckType,
)


class TestNarrativeIntentInputs:
    """Tests for NarrativeIntentInputs dataclass."""

    def test_minimal_inputs(self):
        """Test creation with only required fields."""
        inputs = NarrativeIntentInputs(
            player_input="I climb the wall",
            current_state="dungeon_exploration",
        )

        assert inputs.player_input == "I climb the wall"
        assert inputs.current_state == "dungeon_exploration"
        assert inputs.character_name == ""
        assert inputs.character_level == 1
        assert inputs.character_abilities == {}
        assert inputs.visible_features == []

    def test_full_inputs(self):
        """Test creation with all fields populated."""
        inputs = NarrativeIntentInputs(
            player_input="I cast sleep on the goblin",
            current_state="encounter",
            character_name="Aldric",
            character_class="Magic-User",
            character_level=3,
            character_abilities={"STR": 10, "INT": 16, "WIS": 12},
            location_type="dungeon",
            location_description="A dusty stone chamber",
            visible_features=["wooden door", "iron chest", "goblin"],
            in_combat=True,
            visible_enemies=["Goblin Scout"],
            recent_actions=["searched the room", "opened the door"],
            known_spell_names=["Sleep", "Charm Person", "Magic Missile"],
        )

        assert inputs.character_name == "Aldric"
        assert inputs.character_class == "Magic-User"
        assert inputs.in_combat is True
        assert "Sleep" in inputs.known_spell_names
        assert "goblin" in inputs.visible_features


class TestNarrativeIntentOutput:
    """Tests for NarrativeIntentOutput dataclass."""

    def test_minimal_output(self):
        """Test creation with only required fields."""
        output = NarrativeIntentOutput(
            action_category="hazard",
            action_type="climb",
            confidence=0.9,
        )

        assert output.action_category == "hazard"
        assert output.action_type == "climb"
        assert output.confidence == 0.9
        assert output.suggested_resolution == "check_required"
        assert output.is_adventurer_competency is False

    def test_spell_output(self):
        """Test output for a spell action."""
        output = NarrativeIntentOutput(
            action_category="spell",
            action_type="cast_spell",
            confidence=0.95,
            target_type="creature",
            target_description="the goblin",
            spell_name="Sleep",
            suggested_resolution="check_required",
            suggested_check="none",
            rule_reference="Player's Tome p.XX",
        )

        assert output.action_category == "spell"
        assert output.spell_name == "Sleep"
        assert output.target_description == "the goblin"

    def test_creative_solution_output(self):
        """Test output for a creative solution."""
        output = NarrativeIntentOutput(
            action_category="creative",
            action_type="creative_solution",
            confidence=0.8,
            proposed_approach="pour water on the floor to reveal hidden pits",
            suggested_resolution="auto_success",
            suggested_check="none",
            rule_reference="p155 - Creative Solutions",
            reasoning="This matches a known creative pattern from p155",
        )

        assert output.action_category == "creative"
        assert output.suggested_resolution == "auto_success"
        assert "pour water" in output.proposed_approach

    def test_adventurer_competency_output(self):
        """Test output for adventurer competency action."""
        output = NarrativeIntentOutput(
            action_category="survival",
            action_type="camp",
            confidence=0.95,
            suggested_resolution="auto_success",
            is_adventurer_competency=True,
            rule_reference="p150 - Adventurer Competencies",
        )

        assert output.is_adventurer_competency is True
        assert output.suggested_resolution == "auto_success"

    def test_clarification_needed(self):
        """Test output when clarification is needed."""
        output = NarrativeIntentOutput(
            action_category="unknown",
            action_type="unknown",
            confidence=0.3,
            requires_clarification=True,
            clarification_prompt="What exactly do you want to attack?",
        )

        assert output.requires_clarification is True
        assert "attack" in output.clarification_prompt


class TestNarrativeIntentSchema:
    """Tests for NarrativeIntentSchema."""

    def test_schema_type(self):
        """Test that schema has correct type."""
        inputs = NarrativeIntentInputs(
            player_input="I search the room",
            current_state="dungeon_exploration",
        )
        schema = NarrativeIntentSchema(inputs)

        assert schema.schema_type == PromptSchemaType.NARRATIVE_INTENT_PARSE

    def test_required_inputs(self):
        """Test required inputs are specified."""
        inputs = NarrativeIntentInputs(
            player_input="test",
            current_state="test",
        )
        schema = NarrativeIntentSchema(inputs)

        required = schema.get_required_inputs()
        assert "player_input" in required
        assert "current_state" in required

    def test_system_prompt_contains_rules(self):
        """Test system prompt includes Dolmenwood rules."""
        inputs = NarrativeIntentInputs(
            player_input="test",
            current_state="test",
        )
        schema = NarrativeIntentSchema(inputs)

        system_prompt = schema.get_system_prompt()

        # Should contain action categories
        assert "ACTION CATEGORIES" in system_prompt
        assert "spell" in system_prompt
        assert "hazard" in system_prompt
        assert "exploration" in system_prompt

        # Should contain resolution types
        assert "RESOLUTION TYPES" in system_prompt
        assert "auto_success" in system_prompt
        assert "check_required" in system_prompt

        # Should contain Dolmenwood-specific rules
        assert "ADVENTURER COMPETENCIES" in system_prompt
        assert "p150" in system_prompt
        assert "DOLMENWOOD HAZARD RULES" in system_prompt
        assert "CREATIVE SOLUTIONS" in system_prompt

    def test_build_prompt_basic(self):
        """Test basic prompt building."""
        inputs = NarrativeIntentInputs(
            player_input="I climb the wall",
            current_state="dungeon_exploration",
        )
        schema = NarrativeIntentSchema(inputs)

        prompt = schema.build_prompt()

        assert "I climb the wall" in prompt
        assert "dungeon_exploration" in prompt
        assert "PLAYER INPUT" in prompt
        assert "GAME STATE" in prompt

    def test_build_prompt_with_character(self):
        """Test prompt building with character context."""
        inputs = NarrativeIntentInputs(
            player_input="I cast sleep",
            current_state="encounter",
            character_name="Aldric",
            character_class="Magic-User",
            character_level=5,
            character_abilities={"STR": 10, "INT": 16},
        )
        schema = NarrativeIntentSchema(inputs)

        prompt = schema.build_prompt()

        assert "Aldric" in prompt
        assert "Magic-User" in prompt
        assert "Level: 5" in prompt
        assert "CHARACTER:" in prompt

    def test_build_prompt_with_location(self):
        """Test prompt building with location context."""
        inputs = NarrativeIntentInputs(
            player_input="I search the room",
            current_state="dungeon_exploration",
            location_type="dungeon",
            location_description="A dusty chamber with cobwebs",
            visible_features=["wooden door", "iron chest", "skeleton"],
        )
        schema = NarrativeIntentSchema(inputs)

        prompt = schema.build_prompt()

        assert "LOCATION:" in prompt
        assert "dungeon" in prompt
        assert "dusty chamber" in prompt
        assert "wooden door" in prompt

    def test_build_prompt_with_combat(self):
        """Test prompt building in combat context."""
        inputs = NarrativeIntentInputs(
            player_input="I attack the goblin",
            current_state="combat",
            in_combat=True,
            visible_enemies=["Goblin Scout", "Goblin Archer"],
        )
        schema = NarrativeIntentSchema(inputs)

        prompt = schema.build_prompt()

        assert "COMBAT: In progress" in prompt
        assert "Goblin Scout" in prompt
        assert "Goblin Archer" in prompt

    def test_build_prompt_with_spells(self):
        """Test prompt building with known spells."""
        inputs = NarrativeIntentInputs(
            player_input="I cast a spell",
            current_state="encounter",
            known_spell_names=["Sleep", "Charm Person", "Magic Missile", "Web"],
        )
        schema = NarrativeIntentSchema(inputs)

        prompt = schema.build_prompt()

        assert "KNOWN SPELLS:" in prompt
        assert "Sleep" in prompt
        assert "Magic Missile" in prompt

    def test_build_prompt_with_recent_actions(self):
        """Test prompt building with recent actions."""
        inputs = NarrativeIntentInputs(
            player_input="I try again",
            current_state="dungeon_exploration",
            recent_actions=["searched the chest", "found nothing", "heard a noise"],
        )
        schema = NarrativeIntentSchema(inputs)

        prompt = schema.build_prompt()

        assert "RECENT ACTIONS:" in prompt
        assert "searched the chest" in prompt


class TestOutputConversion:
    """Tests for converting NarrativeIntentOutput to ParsedIntent."""

    def test_convert_hazard_action(self):
        """Test converting a hazard action output."""
        output = NarrativeIntentOutput(
            action_category="hazard",
            action_type="climb",
            confidence=0.9,
            target_type="object",
            target_description="the stone wall",
            suggested_resolution="check_required",
            suggested_check="dexterity",
            rule_reference="p150 - Climbing",
        )

        # Simulate the conversion logic from main.py
        try:
            action_category = ActionCategory(output.action_category)
        except ValueError:
            action_category = ActionCategory.UNKNOWN

        try:
            action_type = ActionType(output.action_type)
        except ValueError:
            action_type = ActionType.UNKNOWN

        try:
            resolution_type = ResolutionType(output.suggested_resolution)
        except ValueError:
            resolution_type = ResolutionType.CHECK_REQUIRED

        try:
            check_type = CheckType(output.suggested_check)
        except ValueError:
            check_type = CheckType.NONE

        parsed = ParsedIntent(
            action_category=action_category,
            action_type=action_type,
            confidence=output.confidence,
            raw_input="I climb the wall",
            target_type=output.target_type,
            target_description=output.target_description,
            applicable_rule=output.rule_reference,
            suggested_resolution=resolution_type,
            suggested_check=check_type,
        )

        assert parsed.action_category == ActionCategory.HAZARD
        assert parsed.action_type == ActionType.CLIMB
        assert parsed.suggested_check == CheckType.DEXTERITY
        assert parsed.applicable_rule == "p150 - Climbing"

    def test_convert_spell_action(self):
        """Test converting a spell action output."""
        output = NarrativeIntentOutput(
            action_category="spell",
            action_type="cast_spell",
            confidence=0.95,
            spell_name="Sleep",
            target_description="the goblin",
        )

        action_category = ActionCategory(output.action_category)
        action_type = ActionType(output.action_type)

        parsed = ParsedIntent(
            action_category=action_category,
            action_type=action_type,
            confidence=output.confidence,
            raw_input="I cast sleep on the goblin",
            spell_name=output.spell_name,
            target_description=output.target_description,
        )

        assert parsed.action_category == ActionCategory.SPELL
        assert parsed.action_type == ActionType.CAST_SPELL
        assert parsed.spell_name == "Sleep"

    def test_convert_unknown_values(self):
        """Test handling unknown enum values gracefully."""
        output = NarrativeIntentOutput(
            action_category="invalid_category",
            action_type="invalid_type",
            confidence=0.5,
        )

        try:
            action_category = ActionCategory(output.action_category)
        except ValueError:
            action_category = ActionCategory.UNKNOWN

        try:
            action_type = ActionType(output.action_type)
        except ValueError:
            action_type = ActionType.UNKNOWN

        assert action_category == ActionCategory.UNKNOWN
        assert action_type == ActionType.UNKNOWN


class TestSchemaValidation:
    """Tests for schema input validation."""

    def test_validate_minimal_inputs(self):
        """Test validation passes with minimal inputs."""
        inputs = NarrativeIntentInputs(
            player_input="test action",
            current_state="wilderness_travel",
        )
        schema = NarrativeIntentSchema(inputs)

        errors = schema.validate_inputs()
        assert errors == []

    def test_schema_inputs_dict(self):
        """Test that schema inputs are properly converted to dict."""
        inputs = NarrativeIntentInputs(
            player_input="I search",
            current_state="dungeon_exploration",
            character_name="Test",
        )
        schema = NarrativeIntentSchema(inputs)

        # The inputs should be available as a dict
        assert schema.inputs["player_input"] == "I search"
        assert schema.inputs["current_state"] == "dungeon_exploration"
        assert schema.inputs["character_name"] == "Test"
