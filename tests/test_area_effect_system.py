"""
Tests for the Enhanced Area Effect System.

Tests area effects with blocking, damage, trapping, and escape mechanics.
"""

import pytest
from src.data_models import (
    AreaEffect,
    AreaEffectType,
    LocationState,
    LocationType,
    CharacterState,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def basic_effect():
    """Create a basic area effect."""
    return AreaEffect(
        effect_id="effect_1",
        effect_type=AreaEffectType.CUSTOM,
        name="Test Effect",
        description="A test area effect",
    )


@pytest.fixture
def web_effect():
    """Create a Web-like effect that traps and can be escaped."""
    return AreaEffect(
        effect_id="web_1",
        effect_type=AreaEffectType.WEB,
        name="Web",
        description="Sticky webs that trap creatures",
        blocks_movement=True,
        blocks_vision=False,
        escape_mechanism={
            "method": "strength_check",
            "dc": 14,
            "requires_action": True,
        },
    )


@pytest.fixture
def fire_effect():
    """Create a damaging fire effect."""
    return AreaEffect(
        effect_id="fire_1",
        effect_type=AreaEffectType.CUSTOM,
        name="Wall of Fire",
        description="A wall of searing flames",
        entry_damage="2d6",
        entry_damage_type="fire",
        entry_save_avoids=False,
        damage_per_turn="1d6",
        damage_type="fire",
        save_type="blast",
        save_halves_damage=True,
    )


@pytest.fixture
def silence_effect():
    """Create a Silence effect that blocks sound and magic."""
    return AreaEffect(
        effect_id="silence_1",
        effect_type=AreaEffectType.SILENCE,
        name="Silence",
        description="An area of magical silence",
        blocks_sound=True,
        blocks_magic=False,  # Only blocks verbal spells, handled separately
        duration_turns=10,
    )


@pytest.fixture
def location():
    """Create a test location."""
    return LocationState(
        location_id="room_1",
        name="Test Room",
        location_type=LocationType.DUNGEON_ROOM,
        terrain="stone",
    )


@pytest.fixture
def fighter():
    """Create a test fighter character."""
    return CharacterState(
        character_id="fighter_1",
        name="Torben",
        character_class="Fighter",
        level=3,
        ability_scores={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        hp_current=20,
        hp_max=20,
        armor_class=16,
        base_speed=40,
    )


# =============================================================================
# BASIC AREA EFFECT TESTS
# =============================================================================


class TestBasicAreaEffect:
    """Tests for basic AreaEffect functionality."""

    def test_create_basic_effect(self, basic_effect):
        """Test creating a basic area effect."""
        assert basic_effect.effect_id == "effect_1"
        assert basic_effect.name == "Test Effect"
        assert basic_effect.is_active is True

    def test_default_no_blocking(self, basic_effect):
        """Test that effects don't block by default."""
        assert basic_effect.blocks_movement is False
        assert basic_effect.blocks_vision is False
        assert basic_effect.blocks_sound is False
        assert basic_effect.blocks_magic is False

    def test_effect_with_duration(self):
        """Test effect with duration tracking."""
        effect = AreaEffect(
            name="Timed Effect",
            duration_turns=5,
        )
        assert effect.duration_turns == 5
        assert effect.is_permanent is False

    def test_permanent_effect(self):
        """Test permanent effect."""
        effect = AreaEffect(
            name="Permanent Effect",
            is_permanent=True,
        )
        assert effect.is_permanent is True

    def test_tick_reduces_duration(self):
        """Test that tick reduces duration."""
        effect = AreaEffect(
            name="Timed Effect",
            duration_turns=3,
        )
        assert effect.tick() is False  # Not expired
        assert effect.duration_turns == 2
        assert effect.tick() is False
        assert effect.duration_turns == 1
        assert effect.tick() is True  # Expired
        assert effect.is_active is False

    def test_tick_permanent_no_expire(self):
        """Test that permanent effects don't expire on tick."""
        effect = AreaEffect(
            name="Permanent Effect",
            is_permanent=True,
        )
        for _ in range(10):
            assert effect.tick() is False
        assert effect.is_active is True

    def test_dismiss_effect(self, basic_effect):
        """Test dismissing an effect."""
        assert basic_effect.dismiss() is True
        assert basic_effect.is_active is False
        assert basic_effect.dismissed is True
        # Can't dismiss again
        assert basic_effect.dismiss() is False


# =============================================================================
# BLOCKING TESTS
# =============================================================================


class TestBlocking:
    """Tests for effect blocking mechanics."""

    def test_blocks_movement(self, web_effect):
        """Test movement blocking."""
        assert web_effect.blocks_movement is True
        assert web_effect.blocks("movement") is True

    def test_blocks_sound(self, silence_effect):
        """Test sound blocking."""
        assert silence_effect.blocks_sound is True
        assert silence_effect.blocks("sound") is True

    def test_blocks_invalid_type(self, basic_effect):
        """Test blocking with invalid type."""
        assert basic_effect.blocks("invalid") is False

    def test_get_all_blocks_empty(self, basic_effect):
        """Test getting empty blocks list."""
        assert basic_effect.get_all_blocks() == []

    def test_get_all_blocks_multiple(self):
        """Test getting multiple blocks."""
        effect = AreaEffect(
            name="Full Block",
            blocks_movement=True,
            blocks_vision=True,
            blocks_sound=True,
            blocks_magic=True,
        )
        blocks = effect.get_all_blocks()
        assert "movement" in blocks
        assert "vision" in blocks
        assert "sound" in blocks
        assert "magic" in blocks
        assert len(blocks) == 4


# =============================================================================
# DAMAGE TESTS
# =============================================================================


class TestDamage:
    """Tests for area effect damage mechanics."""

    def test_has_entry_damage(self, fire_effect):
        """Test entry damage check."""
        assert fire_effect.has_entry_damage() is True

    def test_no_entry_damage(self, web_effect):
        """Test no entry damage."""
        assert web_effect.has_entry_damage() is False

    def test_has_per_turn_damage(self, fire_effect):
        """Test per-turn damage check."""
        assert fire_effect.has_per_turn_damage() is True

    def test_no_per_turn_damage(self, web_effect):
        """Test no per-turn damage."""
        assert web_effect.has_per_turn_damage() is False

    def test_get_damage_info(self, fire_effect):
        """Test getting damage info."""
        info = fire_effect.get_damage_info()
        assert info["entry_damage"] == "2d6"
        assert info["entry_damage_type"] == "fire"
        assert info["per_turn_damage"] == "1d6"
        assert info["per_turn_damage_type"] == "fire"
        assert info["save_type"] == "blast"
        assert info["save_halves"] is True

    def test_get_damage_info_no_damage(self, basic_effect):
        """Test getting damage info with no damage."""
        info = basic_effect.get_damage_info()
        assert info["entry_damage"] is None
        assert info["per_turn_damage"] is None


# =============================================================================
# ESCAPE MECHANISM TESTS
# =============================================================================


class TestEscapeMechanism:
    """Tests for escape mechanism functionality."""

    def test_can_be_escaped(self, web_effect):
        """Test escape check."""
        assert web_effect.can_be_escaped is True

    def test_cannot_be_escaped(self, fire_effect):
        """Test effect without escape."""
        assert fire_effect.can_be_escaped is False

    def test_get_escape_method(self, web_effect):
        """Test getting escape method."""
        assert web_effect.get_escape_method() == "strength_check"

    def test_get_escape_dc(self, web_effect):
        """Test getting escape DC."""
        assert web_effect.get_escape_dc() == 14

    def test_escape_requires_action(self, web_effect):
        """Test escape action requirement."""
        assert web_effect.escape_requires_action() is True

    def test_escape_free_action(self):
        """Test escape that doesn't require action."""
        effect = AreaEffect(
            name="Easy Escape",
            escape_mechanism={
                "method": "dexterity_check",
                "dc": 10,
                "requires_action": False,
            },
        )
        assert effect.escape_requires_action() is False

    def test_no_escape_method_returns_none(self, basic_effect):
        """Test no escape mechanism returns None."""
        assert basic_effect.get_escape_method() is None
        assert basic_effect.get_escape_dc() is None


# =============================================================================
# TRAPPED CHARACTER TESTS
# =============================================================================


class TestTrappedCharacters:
    """Tests for trapped character management."""

    def test_trap_character(self, web_effect):
        """Test trapping a character."""
        result = web_effect.trap_character("fighter_1")
        assert result is True
        assert web_effect.is_character_trapped("fighter_1") is True

    def test_trap_already_trapped(self, web_effect):
        """Test trapping already trapped character."""
        web_effect.trap_character("fighter_1")
        result = web_effect.trap_character("fighter_1")
        assert result is False  # Already trapped

    def test_free_character(self, web_effect):
        """Test freeing a character."""
        web_effect.trap_character("fighter_1")
        result = web_effect.free_character("fighter_1")
        assert result is True
        assert web_effect.is_character_trapped("fighter_1") is False

    def test_free_not_trapped(self, web_effect):
        """Test freeing a character that isn't trapped."""
        result = web_effect.free_character("fighter_1")
        assert result is False

    def test_get_trapped_count(self, web_effect):
        """Test getting trapped count."""
        assert web_effect.get_trapped_count() == 0
        web_effect.trap_character("fighter_1")
        assert web_effect.get_trapped_count() == 1
        web_effect.trap_character("mage_1")
        assert web_effect.get_trapped_count() == 2

    def test_multiple_trapped(self, web_effect):
        """Test multiple trapped characters."""
        web_effect.trap_character("fighter_1")
        web_effect.trap_character("mage_1")
        web_effect.trap_character("cleric_1")

        assert web_effect.is_character_trapped("fighter_1") is True
        assert web_effect.is_character_trapped("mage_1") is True
        assert web_effect.is_character_trapped("cleric_1") is True
        assert web_effect.is_character_trapped("rogue_1") is False


# =============================================================================
# LOCATION STATE TESTS
# =============================================================================


class TestLocationAreaEffects:
    """Tests for location-based area effect management."""

    def test_add_area_effect_to_location(self, location, web_effect):
        """Test adding effect to location."""
        location.add_area_effect(web_effect)
        assert len(location.area_effects) == 1
        assert web_effect.location_id == location.location_id

    def test_remove_area_effect(self, location, web_effect):
        """Test removing effect from location."""
        location.add_area_effect(web_effect)
        removed = location.remove_area_effect(web_effect.effect_id)
        assert removed is not None
        assert len(location.area_effects) == 0

    def test_remove_nonexistent_effect(self, location):
        """Test removing effect that doesn't exist."""
        removed = location.remove_area_effect("nonexistent")
        assert removed is None

    def test_get_active_effects(self, location, web_effect, fire_effect):
        """Test getting active effects."""
        location.add_area_effect(web_effect)
        location.add_area_effect(fire_effect)
        fire_effect.dismiss()

        active = location.get_active_effects()
        assert len(active) == 1
        assert active[0].effect_id == web_effect.effect_id

    def test_tick_effects_expiration(self, location):
        """Test ticking effects and expiration."""
        effect = AreaEffect(
            name="Short Effect",
            duration_turns=2,
        )
        location.add_area_effect(effect)

        expired = location.tick_effects()
        assert len(expired) == 0
        assert len(location.area_effects) == 1

        expired = location.tick_effects()
        assert len(expired) == 1
        assert len(location.area_effects) == 0

    def test_has_blocking_effect(self, location, silence_effect):
        """Test checking for blocking effects."""
        assert location.has_blocking_effect("sound") is False
        location.add_area_effect(silence_effect)
        assert location.has_blocking_effect("sound") is True


# =============================================================================
# GLOBAL CONTROLLER TESTS
# =============================================================================


class TestGlobalControllerAreaEffects:
    """Tests for GlobalController area effect management."""

    @pytest.fixture
    def controller_setup(self, location, fighter):
        """Create controller with location and character."""
        from src.game_state.global_controller import GlobalController

        controller = GlobalController()
        controller._locations[location.location_id] = location
        controller.add_character(fighter)
        return controller, location, fighter

    def test_add_area_effect(self, controller_setup):
        """Test adding area effect via controller."""
        controller, location, _ = controller_setup
        effect = AreaEffect(
            name="Test Effect",
            effect_type=AreaEffectType.CUSTOM,
        )
        result = controller.add_area_effect(location.location_id, effect)
        assert "error" not in result
        assert result["effect_id"] == effect.effect_id

    def test_remove_area_effect(self, controller_setup):
        """Test removing area effect via controller."""
        controller, location, _ = controller_setup
        effect = AreaEffect(name="Test Effect")
        controller.add_area_effect(location.location_id, effect)

        result = controller.remove_area_effect(location.location_id, effect.effect_id)
        assert "error" not in result
        assert result["effect_id"] == effect.effect_id

    def test_get_area_effect(self, controller_setup):
        """Test getting area effect details."""
        controller, location, _ = controller_setup
        effect = AreaEffect(
            name="Web",
            effect_type=AreaEffectType.WEB,
            blocks_movement=True,
            escape_mechanism={"method": "strength_check", "dc": 14},
        )
        controller.add_area_effect(location.location_id, effect)

        result = controller.get_area_effect(location.location_id, effect.effect_id)
        assert "error" not in result
        assert result["name"] == "Web"
        assert result["can_be_escaped"] is True
        assert result["escape_dc"] == 14
        assert "movement" in result["blocks"]

    def test_get_area_effect_not_found(self, controller_setup):
        """Test getting nonexistent effect."""
        controller, location, _ = controller_setup
        result = controller.get_area_effect(location.location_id, "nonexistent")
        assert "error" in result

    def test_process_area_entry_trapping(self, controller_setup):
        """Test processing entry into trapping effect."""
        controller, location, fighter = controller_setup
        effect = AreaEffect(
            name="Web",
            blocks_movement=True,
            escape_mechanism={"method": "strength_check", "dc": 14},
        )
        controller.add_area_effect(location.location_id, effect)

        result = controller.process_area_entry(
            fighter.character_id,
            location.location_id,
            effect.effect_id,
        )
        assert "error" not in result
        assert result["trapped"] is True
        assert "trapped" in result["effects_applied"]

    def test_process_area_entry_damage(self, controller_setup):
        """Test processing entry with damage."""
        controller, location, fighter = controller_setup
        effect = AreaEffect(
            name="Fire Wall",
            entry_damage="2d6",
            entry_damage_type="fire",
            save_type="blast",
        )
        controller.add_area_effect(location.location_id, effect)

        result = controller.process_area_entry(
            fighter.character_id,
            location.location_id,
            effect.effect_id,
        )
        assert "error" not in result
        assert result["entry_damage"]["damage_dice"] == "2d6"
        assert "entry_damage" in result["effects_applied"]

    def test_attempt_escape_success(self, controller_setup):
        """Test successful escape attempt."""
        controller, location, fighter = controller_setup
        effect = AreaEffect(
            name="Web",
            blocks_movement=True,
            escape_mechanism={"method": "strength_check", "dc": 14},
        )
        controller.add_area_effect(location.location_id, effect)
        effect.trap_character(fighter.character_id)

        result = controller.attempt_escape(
            fighter.character_id,
            location.location_id,
            effect.effect_id,
            roll_result=16,  # Beats DC 14
        )
        assert "error" not in result
        assert result["escaped"] is True
        assert not effect.is_character_trapped(fighter.character_id)

    def test_attempt_escape_failure(self, controller_setup):
        """Test failed escape attempt."""
        controller, location, fighter = controller_setup
        effect = AreaEffect(
            name="Web",
            blocks_movement=True,
            escape_mechanism={"method": "strength_check", "dc": 14},
        )
        controller.add_area_effect(location.location_id, effect)
        effect.trap_character(fighter.character_id)

        result = controller.attempt_escape(
            fighter.character_id,
            location.location_id,
            effect.effect_id,
            roll_result=10,  # Below DC 14
        )
        assert "error" not in result
        assert result["escaped"] is False
        assert effect.is_character_trapped(fighter.character_id)

    def test_attempt_escape_not_trapped(self, controller_setup):
        """Test escape when not trapped."""
        controller, location, fighter = controller_setup
        effect = AreaEffect(
            name="Web",
            blocks_movement=True,
            escape_mechanism={"method": "strength_check", "dc": 14},
        )
        controller.add_area_effect(location.location_id, effect)

        result = controller.attempt_escape(
            fighter.character_id,
            location.location_id,
            effect.effect_id,
        )
        assert "error" in result

    def test_get_trapped_in_effect(self, controller_setup):
        """Test checking if character is trapped."""
        controller, location, fighter = controller_setup
        effect = AreaEffect(
            name="Web",
            effect_type=AreaEffectType.WEB,
            blocks_movement=True,
            escape_mechanism={"method": "strength_check", "dc": 14},
        )
        controller.add_area_effect(location.location_id, effect)
        effect.trap_character(fighter.character_id)

        result = controller.get_trapped_in_effect(
            fighter.character_id,
            location.location_id,
        )
        assert result["is_trapped"] is True
        assert len(result["trapping_effects"]) == 1
        assert result["trapping_effects"][0]["name"] == "Web"

    def test_get_trapped_not_trapped(self, controller_setup):
        """Test checking when not trapped."""
        controller, location, fighter = controller_setup

        result = controller.get_trapped_in_effect(
            fighter.character_id,
            location.location_id,
        )
        assert result["is_trapped"] is False
        assert len(result["trapping_effects"]) == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestAreaEffectIntegration:
    """Integration tests for area effect system."""

    def test_full_web_lifecycle(self):
        """Test complete web spell lifecycle."""
        from src.game_state.global_controller import GlobalController

        controller = GlobalController()

        # Create location
        location = LocationState(
            location_id="dungeon_room",
            name="Spider Lair",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="stone",
        )
        controller._locations[location.location_id] = location

        # Create characters
        mage = CharacterState(
            character_id="mage_1",
            name="Elara",
            character_class="Magic-User",
            level=5,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 17, "WIS": 12, "CHA": 12},
            hp_current=12,
            hp_max=12,
            armor_class=12,
            base_speed=40,
        )
        fighter = CharacterState(
            character_id="fighter_1",
            name="Torben",
            character_class="Fighter",
            level=3,
            ability_scores={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=16,
            base_speed=40,
        )
        controller.add_character(mage)
        controller.add_character(fighter)

        # Mage casts Web
        web = AreaEffect(
            effect_type=AreaEffectType.WEB,
            name="Web",
            description="Magical sticky webs fill the area",
            source_spell_id="web_spell",
            caster_id=mage.character_id,
            blocks_movement=True,
            blocks_vision=False,
            duration_turns=10,
            escape_mechanism={
                "method": "strength_check",
                "dc": 14,
                "requires_action": True,
            },
        )
        controller.add_area_effect(location.location_id, web)

        # Fighter enters web
        entry_result = controller.process_area_entry(
            fighter.character_id,
            location.location_id,
            web.effect_id,
        )
        assert entry_result["trapped"] is True

        # Fighter tries to escape (fails)
        escape_result = controller.attempt_escape(
            fighter.character_id,
            location.location_id,
            web.effect_id,
            roll_result=12,
        )
        assert escape_result["escaped"] is False

        # Fighter tries again (succeeds)
        escape_result = controller.attempt_escape(
            fighter.character_id,
            location.location_id,
            web.effect_id,
            roll_result=16,
        )
        assert escape_result["escaped"] is True

        # Verify fighter is free
        trap_check = controller.get_trapped_in_effect(
            fighter.character_id,
            location.location_id,
        )
        assert trap_check["is_trapped"] is False

    def test_damaging_effect_with_save(self):
        """Test damaging area effect with save mechanics."""
        fire_wall = AreaEffect(
            effect_type=AreaEffectType.CUSTOM,
            name="Wall of Fire",
            entry_damage="4d6",
            entry_damage_type="fire",
            entry_save_avoids=False,
            damage_per_turn="2d6",
            damage_type="fire",
            save_type="blast",
            save_halves_damage=True,
            duration_turns=5,
        )

        # Verify damage info
        damage_info = fire_wall.get_damage_info()
        assert damage_info["entry_damage"] == "4d6"
        assert damage_info["per_turn_damage"] == "2d6"
        assert damage_info["save_halves"] is True

        # Verify blocking (fire wall might block movement)
        fire_wall.blocks_movement = True
        assert "movement" in fire_wall.get_all_blocks()

    def test_silence_blocks_verbal_spells(self):
        """Test silence effect mechanics."""
        silence = AreaEffect(
            effect_type=AreaEffectType.SILENCE,
            name="Silence 15' Radius",
            description="No sound can occur within this area",
            blocks_sound=True,
            area_radius_feet=15,
            duration_turns=20,
        )

        # Silence blocks sound
        assert silence.blocks("sound") is True
        # But doesn't block movement or vision
        assert silence.blocks("movement") is False
        assert silence.blocks("vision") is False

        # No entry damage
        assert silence.has_entry_damage() is False
        # Can't be escaped (just leave the area)
        assert silence.can_be_escaped is False
