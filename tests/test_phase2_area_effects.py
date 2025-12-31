"""
Tests for Phase 2.4: Area/Zone Effect Spells.

Tests Web, Silence, Darkness, Fog Cloud, and other area effect spells.
"""

import pytest
from unittest.mock import MagicMock

from src.data_models import (
    AreaEffect,
    AreaEffectType,
    CharacterState,
    LocationState,
    LocationType,
)
from src.narrative.spell_resolver import (
    MagicType,
    MechanicalEffect,
    MechanicalEffectCategory,
    SpellData,
    SpellResolver,
)


def create_spell(
    spell_id: str,
    name: str,
    level: int,
    magic_type: MagicType,
    description: str,
    duration: str = "Instant",
    range_: str = "30'",
    **kwargs
) -> SpellData:
    """Helper to create SpellData with required fields."""
    return SpellData(
        spell_id=spell_id,
        name=name,
        level=level,
        magic_type=magic_type,
        duration=duration,
        range=range_,
        description=description,
        **kwargs
    )


# =============================================================================
# AREA EFFECT DATA MODEL TESTS
# =============================================================================


class TestAreaEffectDataModel:
    """Tests for AreaEffect dataclass."""

    def test_area_effect_creation_web(self):
        """Create a web area effect."""
        effect = AreaEffect(
            effect_type=AreaEffectType.WEB,
            name="Web",
            description="Sticky webs",
            location_id="room_1",
            duration_turns=48,
            blocks_movement=True,
        )

        assert effect.effect_type == AreaEffectType.WEB
        assert effect.name == "Web"
        assert effect.blocks_movement is True
        assert effect.is_active is True

    def test_area_effect_creation_silence(self):
        """Create a silence area effect."""
        effect = AreaEffect(
            effect_type=AreaEffectType.SILENCE,
            name="Silence",
            description="Zone of silence",
            location_id="room_2",
            duration_turns=12,
            blocks_sound=True,
            blocks_magic=True,
        )

        assert effect.effect_type == AreaEffectType.SILENCE
        assert effect.blocks_sound is True
        assert effect.blocks_magic is True

    def test_area_effect_creation_darkness(self):
        """Create a darkness area effect."""
        effect = AreaEffect(
            effect_type=AreaEffectType.DARKNESS,
            name="Darkness",
            description="Magical darkness",
            location_id="room_3",
            duration_turns=6,
            blocks_vision=True,
        )

        assert effect.effect_type == AreaEffectType.DARKNESS
        assert effect.blocks_vision is True

    def test_area_effect_tick_expiry(self):
        """Test effect expiry on tick."""
        effect = AreaEffect(
            effect_type=AreaEffectType.FOG,
            name="Fog",
            duration_turns=2,
            location_id="room_4",
        )

        assert effect.is_active is True
        assert effect.tick() is False  # Not expired yet
        assert effect.duration_turns == 1
        assert effect.tick() is True  # Now expired
        assert effect.is_active is False

    def test_area_effect_permanent(self):
        """Test permanent effect doesn't expire."""
        effect = AreaEffect(
            effect_type=AreaEffectType.LIGHT,
            name="Light",
            duration_turns=None,
            is_permanent=True,
            location_id="room_5",
        )

        for _ in range(10):
            assert effect.tick() is False  # Never expires
        assert effect.is_active is True

    def test_area_effect_trapping(self):
        """Test trapping characters in effects like Web."""
        effect = AreaEffect(
            effect_type=AreaEffectType.WEB,
            name="Web",
            location_id="room_6",
            blocks_movement=True,
            escape_mechanism={"method": "strength_check", "dc": 0},
        )

        assert effect.is_character_trapped("char_1") is False

        effect.trap_character("char_1")
        assert effect.is_character_trapped("char_1") is True
        assert "char_1" in effect.trapped_characters

        effect.free_character("char_1")
        assert effect.is_character_trapped("char_1") is False


# =============================================================================
# GLOBAL CONTROLLER AREA SPELL TESTS
# =============================================================================


class TestControllerAreaSpells:
    """Tests for GlobalController area spell methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with a location."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add a test location
        location = LocationState(
            location_id="test_room",
            name="Test Room",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="dungeon",
        )
        controller._locations["test_room"] = location

        return controller

    def test_cast_web(self, controller):
        """Test casting Web spell."""
        result = controller.cast_web(
            location_id="test_room",
            caster_id="wizard_1",
            duration_turns=48,
        )

        assert "error" not in result
        assert result["spell"] == "Web"
        assert result["effect_type"] == "web"
        assert result["location_id"] == "test_room"

        # Verify effect was added to location
        location = controller._locations["test_room"]
        assert len(location.area_effects) == 1
        effect = location.area_effects[0]
        assert effect.effect_type == AreaEffectType.WEB
        assert effect.blocks_movement is True

    def test_cast_silence(self, controller):
        """Test casting Silence spell."""
        result = controller.cast_silence(
            location_id="test_room",
            caster_id="cleric_1",
            duration_turns=12,
        )

        assert "error" not in result
        assert result["spell"] == "Silence"
        assert result["blocks_verbal_spells"] is True

        location = controller._locations["test_room"]
        effect = location.area_effects[0]
        assert effect.effect_type == AreaEffectType.SILENCE
        assert effect.blocks_sound is True
        assert effect.blocks_magic is True

    def test_cast_darkness(self, controller):
        """Test casting Darkness spell."""
        result = controller.cast_darkness(
            location_id="test_room",
            caster_id="wizard_1",
            duration_turns=6,
        )

        assert "error" not in result
        assert result["spell"] == "Darkness"

        location = controller._locations["test_room"]
        effect = location.area_effects[0]
        assert effect.effect_type == AreaEffectType.DARKNESS
        assert effect.blocks_vision is True

    def test_cast_fog_cloud(self, controller):
        """Test casting Fog Cloud."""
        result = controller.cast_fog_cloud(
            location_id="test_room",
            caster_id="druid_1",
            duration_turns=6,
        )

        assert "error" not in result
        assert result["spell"] == "Fog Cloud"

        location = controller._locations["test_room"]
        effect = location.area_effects[0]
        assert effect.effect_type == AreaEffectType.FOG
        assert effect.blocks_vision is True

    def test_cast_stinking_cloud(self, controller):
        """Test casting Stinking Cloud."""
        result = controller.cast_stinking_cloud(
            location_id="test_room",
            caster_id="wizard_1",
        )

        assert "error" not in result
        assert result["spell"] == "Stinking Cloud"
        assert result["save_required"] == "poison"

        location = controller._locations["test_room"]
        effect = location.area_effects[0]
        assert effect.effect_type == AreaEffectType.STINKING_CLOUD
        assert effect.save_type == "spell"

    def test_cast_entangle(self, controller):
        """Test casting Entangle."""
        result = controller.cast_entangle(
            location_id="test_room",
            caster_id="druid_1",
            duration_turns=6,
        )

        assert "error" not in result
        assert result["spell"] == "Entangle"

        location = controller._locations["test_room"]
        effect = location.area_effects[0]
        assert effect.effect_type == AreaEffectType.ENTANGLE
        assert effect.blocks_movement is True

    def test_cast_spell_location_not_found(self, controller):
        """Test casting spell on nonexistent location."""
        result = controller.cast_web(
            location_id="nonexistent",
            caster_id="wizard_1",
        )

        assert "error" in result


# =============================================================================
# SPELL PARSING TESTS
# =============================================================================


class TestAreaSpellParsing:
    """Tests for parsing area effect spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_web(self, resolver):
        """Parse Web spell."""
        spell = create_spell(
            spell_id="web",
            name="Web",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Creates a mass of sticky webs that fill the area. Creatures must save or be trapped.",
            duration="8 hours",
            range_="10'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        web_effects = [e for e in parsed.effects if e.is_area_effect and e.area_effect_type == "web"]
        assert len(web_effects) >= 1

        effect = web_effects[0]
        assert effect.blocks_movement is True
        assert effect.entangles is True

    def test_parse_silence(self, resolver):
        """Parse Silence spell."""
        spell = create_spell(
            spell_id="silence",
            name="Silence",
            magic_type=MagicType.DIVINE,
            level=2,
            description="Creates a zone of silence. No sound can be made or heard within the area.",
            duration="12 Turns",
            range_="180'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        silence_effects = [e for e in parsed.effects if e.is_area_effect and e.area_effect_type == "silence"]
        assert len(silence_effects) >= 1

        effect = silence_effects[0]
        assert effect.blocks_sound is True
        assert effect.blocks_spellcasting is True

    def test_parse_darkness(self, resolver):
        """Parse Darkness spell."""
        spell = create_spell(
            spell_id="darkness",
            name="Darkness",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Creates magical darkness that blocks all light. Normal light cannot penetrate.",
            duration="6 Turns",
            range_="120'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        darkness_effects = [e for e in parsed.effects if e.is_area_effect and e.area_effect_type == "darkness"]
        assert len(darkness_effects) >= 1

        effect = darkness_effects[0]
        assert effect.blocks_vision is True

    def test_parse_fog_cloud(self, resolver):
        """Parse Fog Cloud spell."""
        spell = create_spell(
            spell_id="fog_cloud",
            name="Fog Cloud",
            magic_type=MagicType.RUNE,
            level=1,
            description="A thick fog obscures vision in the area.",
            duration="1 Turn per level",
            range_="30'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        fog_effects = [e for e in parsed.effects if e.is_area_effect and e.area_effect_type == "fog"]
        assert len(fog_effects) >= 1

        effect = fog_effects[0]
        assert effect.blocks_vision is True

    def test_parse_gust_of_wind(self, resolver):
        """Parse Gust of Wind spell."""
        spell = create_spell(
            spell_id="gust_of_wind",
            name="Gust of Wind",
            magic_type=MagicType.RUNE,
            level=2,
            description="A powerful wind blows creatures back. Save to resist being pushed away.",
            duration="1 Round",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        wind_effects = [e for e in parsed.effects if e.is_area_effect and e.area_effect_type == "wind"]
        assert len(wind_effects) >= 1

        effect = wind_effects[0]
        assert effect.save_type == "spell"

    def test_parse_stinking_cloud(self, resolver):
        """Parse Stinking Cloud spell."""
        spell = create_spell(
            spell_id="stinking_cloud",
            name="Stinking Cloud",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Creates a nauseating cloud of gas. Save or be helpless.",
            duration="1 Turn",
            range_="30'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        hazard_effects = [e for e in parsed.effects if e.is_area_effect and e.area_effect_type == "hazard"]
        assert len(hazard_effects) >= 1

        effect = hazard_effects[0]
        assert effect.creates_hazard is True

    def test_parse_entangle(self, resolver):
        """Parse Entangle spell."""
        spell = create_spell(
            spell_id="entangle",
            name="Entangle",
            magic_type=MagicType.DIVINE,
            level=1,
            description="Vines and roots wrap around creatures. Save to avoid being restrained.",
            duration="1 Turn per level",
            range_="80'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        entangle_effects = [e for e in parsed.effects if e.is_area_effect and e.area_effect_type == "entangle"]
        assert len(entangle_effects) >= 1

        effect = entangle_effects[0]
        assert effect.blocks_movement is True
        assert effect.entangles is True


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestAreaEffectIntegration:
    """Integration tests for area effect workflow."""

    @pytest.fixture
    def controller(self):
        """Create a controller with location and characters."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add dungeon room
        room = LocationState(
            location_id="dungeon_corridor",
            name="Dark Corridor",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="dungeon",
        )
        controller._locations["dungeon_corridor"] = room

        # Add wizard character
        wizard = CharacterState(
            character_id="wizard",
            name="Test Wizard",
            character_class="Magician",
            level=5,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 17, "WIS": 12, "CHA": 11},
            hp_current=15,
            hp_max=18,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["wizard"] = wizard

        return controller

    def test_web_workflow(self, controller):
        """Test complete Web spell workflow."""
        # Cast web
        result = controller.cast_web(
            location_id="dungeon_corridor",
            caster_id="wizard",
            duration_turns=48,
        )
        assert "error" not in result
        effect_id = result["effect_id"]

        # Verify effect exists
        location = controller._locations["dungeon_corridor"]
        assert len(location.area_effects) == 1

        # Get effect details
        details = controller.get_area_effect("dungeon_corridor", effect_id)
        assert details["effect_type"] == "web"
        assert details["is_active"] is True

        # Remove effect
        remove_result = controller.remove_area_effect("dungeon_corridor", effect_id)
        assert "error" not in remove_result
        assert len(location.area_effects) == 0

    def test_multiple_effects(self, controller):
        """Test multiple area effects in same location."""
        # Cast web and darkness in same room
        web_result = controller.cast_web("dungeon_corridor", "wizard")
        darkness_result = controller.cast_darkness("dungeon_corridor", "wizard")

        location = controller._locations["dungeon_corridor"]
        assert len(location.area_effects) == 2

        # Verify both effects exist
        effect_types = [e.effect_type.value for e in location.area_effects]
        assert "web" in effect_types
        assert "darkness" in effect_types

    def test_silence_blocks_verbal_spells(self, controller):
        """Test that silence zone is properly configured."""
        result = controller.cast_silence(
            location_id="dungeon_corridor",
            caster_id="wizard",
        )

        location = controller._locations["dungeon_corridor"]
        effect = location.area_effects[0]

        # Verify the effect blocks verbal spellcasting
        assert effect.blocks_sound is True
        assert effect.blocks_magic is True  # Used to indicate verbal component block
