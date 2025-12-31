"""
Tests for the Spell Context Provider system.

Tests cover:
- Tier 1: Querying existing game state (DetectMagic, DetectEvil)
- Tier 2: Lazy history generation with persistence
- Tier 3: SpellRevelation to LLM schema integration
"""

import pytest
from dataclasses import dataclass, field
from typing import Any

from src.narrative.spell_context import (
    SpellContextRegistry,
    SpellRevelation,
    Revelation,
    RevelationType,
    HistoryGenerator,
    ItemHistory,
    CreatureHistory,
    DetectMagicProvider,
    DetectEvilProvider,
    WoodKenningProvider,
    CrystalResonanceProvider,
)


# =============================================================================
# TIER 2: HISTORY GENERATOR TESTS
# =============================================================================


class TestHistoryGenerator:
    """Tests for deterministic history generation."""

    def test_same_item_same_history(self):
        """Same item ID always generates same history."""
        gen1 = HistoryGenerator(world_seed=12345)
        gen2 = HistoryGenerator(world_seed=12345)

        history1 = gen1.get_or_generate_item_history("wooden_box_001")
        history2 = gen2.get_or_generate_item_history("wooden_box_001")

        assert history1.creator_name == history2.creator_name
        assert history1.absorbed_emotion == history2.absorbed_emotion
        assert history1.age_category == history2.age_category

    def test_different_items_different_history(self):
        """Different item IDs generate different histories."""
        gen = HistoryGenerator(world_seed=12345)

        history1 = gen.get_or_generate_item_history("item_001")
        history2 = gen.get_or_generate_item_history("item_002")

        # Very unlikely to be identical
        assert not (
            history1.creator_name == history2.creator_name
            and history1.absorbed_emotion == history2.absorbed_emotion
            and history1.age_category == history2.age_category
        )

    def test_different_seeds_different_history(self):
        """Different world seeds produce different histories."""
        gen1 = HistoryGenerator(world_seed=11111)
        gen2 = HistoryGenerator(world_seed=22222)

        history1 = gen1.get_or_generate_item_history("same_item")
        history2 = gen2.get_or_generate_item_history("same_item")

        # Should be different (extremely unlikely to match)
        assert history1.creator_name != history2.creator_name

    def test_magical_items_get_true_names(self):
        """Magical items receive true names."""
        gen = HistoryGenerator(world_seed=42)

        magical = gen.get_or_generate_item_history("wand_001", is_magical=True)
        mundane = gen.get_or_generate_item_history("stick_001", is_magical=False)

        assert magical.true_name is not None
        assert mundane.true_name is None

    def test_ancient_items_have_events(self):
        """Ancient items have notable events."""
        gen = HistoryGenerator(world_seed=42)

        # Generate enough to find an ancient one
        ancient_found = False
        for i in range(50):
            history = gen.get_or_generate_item_history(f"item_{i:03d}")
            if history.age_category in ("ancient", "primordial"):
                assert len(history.notable_events) > 0
                ancient_found = True
                break

        # Should find at least one ancient item in 50 tries
        assert ancient_found, "No ancient items generated in 50 attempts"

    def test_creature_history_generation(self):
        """Creature history is generated correctly."""
        gen = HistoryGenerator(world_seed=42)

        history = gen.get_or_generate_creature_history(
            "goblin_001",
            is_fairy=False,
        )

        assert history.creature_id == "goblin_001"
        assert history.origin_location is not None
        assert history.dominant_emotion is not None
        assert history.secret_fear is not None
        assert history.hidden_desire is not None
        assert history.true_name is None  # Not fairy

    def test_fairy_creatures_get_true_names(self):
        """Fairy creatures receive true names."""
        gen = HistoryGenerator(world_seed=42)

        fairy = gen.get_or_generate_creature_history("sprite_001", is_fairy=True)
        mortal = gen.get_or_generate_creature_history("human_001", is_fairy=False)

        assert fairy.true_name is not None
        assert mortal.true_name is None

    def test_cache_persistence(self):
        """Cache can be exported and imported."""
        gen1 = HistoryGenerator(world_seed=42)

        # Generate some history
        gen1.get_or_generate_item_history("item_001")
        gen1.get_or_generate_creature_history("creature_001")

        # Export
        cache_data = gen1.export_cache()

        # Import into new generator
        gen2 = HistoryGenerator(world_seed=999)  # Different seed
        gen2.import_cache(cache_data)

        # Should get same cached values
        history1 = gen1.get_or_generate_item_history("item_001")
        history2 = gen2.get_or_generate_item_history("item_001")

        assert history1.creator_name == history2.creator_name


# =============================================================================
# SPELL REVELATION TESTS
# =============================================================================


class TestSpellRevelation:
    """Tests for SpellRevelation data structure."""

    def test_empty_revelation_reports_nothing_detected(self):
        """Empty revelations with flag reports nothing detected."""
        revelation = SpellRevelation(
            spell_id="detect_magic",
            spell_name="Detect Magic",
            caster_id="wizard_001",
            nothing_detected=True,
        )

        assert revelation.nothing_detected
        assert not revelation.has_revelations()

    def test_revelations_to_llm_context(self):
        """Revelations convert to LLM context format."""
        revelation = SpellRevelation(
            spell_id="detect_magic",
            spell_name="Detect Magic",
            caster_id="wizard_001",
            sensory_mode="sight",
            detection_range=60,
        )
        revelation.revelations.append(Revelation(
            revelation_type=RevelationType.MAGICAL_AURA,
            source_id="sword_001",
            source_name="a gleaming sword",
            description="radiates strong magical energy",
            intensity="strong",
        ))

        context = revelation.to_llm_context()

        assert context["spell_name"] == "Detect Magic"
        assert context["sensory_mode"] == "sight"
        assert len(context["revelations"]) == 1
        assert "gleaming sword" in context["revelations"][0]


# =============================================================================
# CONTEXT PROVIDER TESTS
# =============================================================================


class TestDetectMagicProvider:
    """Tests for Detect Magic context provider."""

    def test_no_controller_returns_empty(self):
        """Without controller, returns nothing detected."""
        provider = DetectMagicProvider(controller=None)

        result = provider.get_context(
            caster_id="wizard_001",
            location_id="room_001",
        )

        assert result.nothing_detected
        assert result.spell_name == "Detect Magic"
        assert result.sensory_mode == "sight"

    def test_aesthetic_notes_included(self):
        """Aesthetic guidance is provided."""
        provider = DetectMagicProvider(controller=None)

        result = provider.get_context(
            caster_id="wizard_001",
            location_id="room_001",
        )

        assert len(result.aesthetic_notes) > 0
        assert any("aura" in note.lower() for note in result.aesthetic_notes)


class TestWoodKenningProvider:
    """Tests for Mossling Wood Kenning knack."""

    def test_level_1_reveals_history(self):
        """Level 1 reveals creator or last toucher."""
        history_gen = HistoryGenerator(world_seed=42)
        provider = WoodKenningProvider(
            controller=None,
            history_generator=history_gen,
        )

        result = provider.get_context(
            caster_id="mossling_001",
            location_id="forest_001",
            target_id="wooden_door_001",
            caster_level=1,
            target_type="item",
        )

        assert result.sensory_mode == "touch"
        assert result.has_revelations()

        # Should have history revelation
        history_revelation = [
            r for r in result.revelations
            if r.revelation_type == RevelationType.ITEM_HISTORY
        ]
        assert len(history_revelation) > 0

    def test_level_3_reveals_emotion(self):
        """Level 3 reveals absorbed emotions."""
        history_gen = HistoryGenerator(world_seed=42)
        provider = WoodKenningProvider(
            controller=None,
            history_generator=history_gen,
        )

        # Generate multiple items to find one with emotion
        for i in range(20):
            result = provider.get_context(
                caster_id="mossling_001",
                location_id="forest_001",
                target_id=f"wood_item_{i:03d}",
                caster_level=3,
                target_type="item",
            )

            emotion_revelations = [
                r for r in result.revelations
                if r.revelation_type == RevelationType.EMOTIONAL_RESIDUE
            ]
            if emotion_revelations:
                assert "absorbed" in emotion_revelations[0].description
                break

    def test_level_7_reveals_true_name(self):
        """Level 7 reveals tree's true name."""
        history_gen = HistoryGenerator(world_seed=42)
        provider = WoodKenningProvider(
            controller=None,
            history_generator=history_gen,
        )

        result = provider.get_context(
            caster_id="mossling_001",
            location_id="forest_001",
            target_id="ancient_oak_001",
            caster_level=7,
            target_type="tree",
        )

        true_name_revelations = [
            r for r in result.revelations
            if r.revelation_type == RevelationType.TRUE_NAME
        ]
        assert len(true_name_revelations) > 0
        assert "true name" in true_name_revelations[0].description.lower()


class TestCrystalResonanceProvider:
    """Tests for Crystal Resonance spell."""

    def test_light_capture(self):
        """Light energy can be captured."""
        provider = CrystalResonanceProvider(controller=None)

        result = provider.get_context(
            caster_id="wizard_001",
            location_id="forest_glade",
            energy_type="light",
        )

        assert result.sensory_mode == "sight"
        assert result.has_revelations()
        assert result.revelations[0].revelation_type == RevelationType.SENSORY_IMPRINT

    def test_sound_capture(self):
        """Sound energy can be captured."""
        provider = CrystalResonanceProvider(controller=None)

        result = provider.get_context(
            caster_id="wizard_001",
            location_id="forest_glade",
            energy_type="sound",
        )

        assert result.sensory_mode == "hearing"

    def test_temperature_capture(self):
        """Temperature can be captured."""
        provider = CrystalResonanceProvider(controller=None)

        result = provider.get_context(
            caster_id="wizard_001",
            location_id="forest_glade",
            energy_type="temperature",
        )

        assert result.sensory_mode == "touch"


# =============================================================================
# REGISTRY TESTS
# =============================================================================


class TestSpellContextRegistry:
    """Tests for the spell context registry."""

    def test_registered_spells_have_providers(self):
        """Default spells are registered."""
        registry = SpellContextRegistry()

        assert registry.has_provider("detect_magic")
        assert registry.has_provider("detect_evil")
        assert registry.has_provider("wood_kenning")
        assert registry.has_provider("crystal_resonance")

    def test_unregistered_spell_returns_none(self):
        """Unknown spells return None."""
        registry = SpellContextRegistry()

        result = registry.get_context(
            spell_id="unknown_spell",
            caster_id="wizard_001",
            location_id="room_001",
        )

        assert result is None

    def test_history_cache_persistence(self):
        """Registry's history cache can be persisted."""
        registry = SpellContextRegistry(world_seed=42)

        # Generate some history via Wood Kenning
        registry.get_context(
            spell_id="wood_kenning",
            caster_id="mossling_001",
            location_id="forest_001",
            target_id="door_001",
            caster_level=1,
        )

        # Export and verify non-empty
        cache = registry.export_history_cache()
        assert len(cache) > 0


# =============================================================================
# SCHEMA INTEGRATION TESTS
# =============================================================================


class TestSpellRevelationSchema:
    """Tests for the SpellRevelationSchema."""

    def test_schema_creation(self):
        """Schema can be created with required inputs."""
        from src.ai.prompt_schemas import SpellRevelationInputs, SpellRevelationSchema

        inputs = SpellRevelationInputs(
            spell_name="Detect Magic",
            caster_name="Merlin",
            sensory_mode="sight",
            revelations=["a gleaming sword: radiates magical energy"],
        )

        schema = SpellRevelationSchema(inputs)
        assert schema.typed_inputs.spell_name == "Detect Magic"

    def test_schema_prompt_includes_revelations(self):
        """Prompt includes all revelations."""
        from src.ai.prompt_schemas import SpellRevelationInputs, SpellRevelationSchema

        inputs = SpellRevelationInputs(
            spell_name="Detect Magic",
            caster_name="Merlin",
            sensory_mode="sight",
            revelations=[
                "a gleaming sword: radiates strong magical energy",
                "a ring: pulses with faint enchantment",
            ],
        )

        schema = SpellRevelationSchema(inputs)
        prompt = schema.build_prompt()

        assert "gleaming sword" in prompt
        assert "ring" in prompt
        assert "ONLY" in prompt  # Constraint language

    def test_nothing_detected_prompt(self):
        """Nothing detected produces appropriate prompt."""
        from src.ai.prompt_schemas import SpellRevelationInputs, SpellRevelationSchema

        inputs = SpellRevelationInputs(
            spell_name="Detect Evil",
            caster_name="Cleric",
            sensory_mode="sight",
            revelations=[],
            nothing_detected=True,
        )

        schema = SpellRevelationSchema(inputs)
        prompt = schema.build_prompt()

        assert "Nothing detected" in prompt

    def test_system_prompt_includes_constraints(self):
        """System prompt emphasizes constraints."""
        from src.ai.prompt_schemas import SpellRevelationInputs, SpellRevelationSchema

        inputs = SpellRevelationInputs(
            spell_name="Detect Magic",
            caster_name="Merlin",
            sensory_mode="sight",
            revelations=["something magical"],
        )

        schema = SpellRevelationSchema(inputs)
        system = schema.get_system_prompt()

        assert "ONLY describe the revelations" in system
        assert "do not invent" in system.lower()

    def test_factory_creates_revelation_schema(self):
        """Factory function creates correct schema type."""
        from src.ai.prompt_schemas import (
            create_schema,
            PromptSchemaType,
            SpellRevelationSchema,
        )

        inputs = {
            "spell_name": "Detect Magic",
            "caster_name": "Wizard",
            "sensory_mode": "sight",
            "revelations": ["a magical aura"],
        }

        schema = create_schema(PromptSchemaType.SPELL_REVELATION, inputs)
        assert isinstance(schema, SpellRevelationSchema)
