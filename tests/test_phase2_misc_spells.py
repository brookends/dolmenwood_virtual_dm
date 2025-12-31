"""
Tests for Phase 2.8: Miscellaneous Moderate Spells.

Tests teleportation, divination, movement, invisibility, illusion, and protection spells.
"""

import pytest
from unittest.mock import MagicMock

from src.data_models import (
    CharacterState,
    LocationState,
    LocationType,
    ConditionType,
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
# TELEPORTATION SPELL PARSING TESTS
# =============================================================================


class TestTeleportSpellParsing:
    """Tests for parsing teleportation spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_teleport(self, resolver):
        """Parse Teleport spell."""
        spell = create_spell(
            spell_id="teleport",
            name="Teleport",
            magic_type=MagicType.ARCANE,
            level=5,
            description="Teleport instantly to a known location with up to 3 other creatures.",
            duration="Instant",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        teleport_effects = [e for e in parsed.effects if e.is_teleport_effect]
        assert len(teleport_effects) >= 1

        effect = teleport_effects[0]
        assert effect.teleport_type == "long"
        assert effect.allows_passengers is True
        assert effect.max_passengers == 3

    def test_parse_dimension_door(self, resolver):
        """Parse Dimension Door spell."""
        spell = create_spell(
            spell_id="dimension_door",
            name="Dimension Door",
            magic_type=MagicType.ARCANE,
            level=4,
            description="Open a dimension door to travel 360 feet instantly.",
            duration="Instant",
            range_="Self",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        teleport_effects = [e for e in parsed.effects if e.is_teleport_effect]
        assert len(teleport_effects) >= 1

        effect = teleport_effects[0]
        assert effect.teleport_type == "short"
        assert effect.teleport_range == 360

    def test_parse_plane_shift(self, resolver):
        """Parse Plane Shift spell."""
        spell = create_spell(
            spell_id="plane_shift",
            name="Plane Shift",
            magic_type=MagicType.DIVINE,
            level=5,
            description="Plane shift to another plane of existence.",
            duration="Instant",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        teleport_effects = [e for e in parsed.effects if e.is_teleport_effect]
        assert len(teleport_effects) >= 1

        effect = teleport_effects[0]
        assert effect.teleport_type == "planar"


# =============================================================================
# DIVINATION SPELL PARSING TESTS
# =============================================================================


class TestDivinationSpellParsing:
    """Tests for parsing divination spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_detect_magic(self, resolver):
        """Parse Detect Magic spell."""
        spell = create_spell(
            spell_id="detect_magic",
            name="Detect Magic",
            magic_type=MagicType.ARCANE,
            level=1,
            description="Detect magic within 60' for 2 turns.",
            duration="2 Turns",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        div_effects = [e for e in parsed.effects if e.is_divination_effect]
        assert len(div_effects) >= 1

        effect = div_effects[0]
        assert effect.divination_type == "detect"
        assert effect.detects_what == "magic"
        assert effect.divination_range == 60

    def test_parse_detect_evil(self, resolver):
        """Parse Detect Evil spell."""
        spell = create_spell(
            spell_id="detect_evil",
            name="Detect Evil",
            magic_type=MagicType.DIVINE,
            level=1,
            description="Detect evil within 120 feet.",
            duration="6 Turns",
            range_="120'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        div_effects = [e for e in parsed.effects if e.is_divination_effect]
        assert len(div_effects) >= 1

        effect = div_effects[0]
        assert effect.divination_type == "detect"
        assert effect.detects_what == "evil"

    def test_parse_locate_object(self, resolver):
        """Parse Locate Object spell."""
        spell = create_spell(
            spell_id="locate_object",
            name="Locate Object",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Locate object within 360 feet if familiar.",
            duration="Concentration",
            range_="360'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        div_effects = [e for e in parsed.effects if e.is_divination_effect]
        assert len(div_effects) >= 1

        effect = div_effects[0]
        assert effect.divination_type == "locate"
        assert effect.detects_what == "object"

    def test_parse_esp(self, resolver):
        """Parse ESP spell."""
        spell = create_spell(
            spell_id="esp",
            name="ESP",
            magic_type=MagicType.ARCANE,
            level=2,
            description="ESP allows reading thoughts of creatures.",
            duration="12 Turns",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        div_effects = [e for e in parsed.effects if e.is_divination_effect]
        assert len(div_effects) >= 1

        effect = div_effects[0]
        assert effect.divination_type == "detect"
        assert effect.detects_what == "thoughts"


# =============================================================================
# MOVEMENT SPELL PARSING TESTS
# =============================================================================


class TestMovementSpellParsing:
    """Tests for parsing movement enhancement spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_fly(self, resolver):
        """Parse Fly spell."""
        spell = create_spell(
            spell_id="fly",
            name="Fly",
            magic_type=MagicType.ARCANE,
            level=3,
            description="Target can fly at 120' per turn.",
            duration="1 Turn per level",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        move_effects = [e for e in parsed.effects if e.grants_movement]
        assert len(move_effects) >= 1

        effect = move_effects[0]
        assert effect.movement_type == "fly"
        assert effect.movement_speed == 120

    def test_parse_levitate(self, resolver):
        """Parse Levitate spell."""
        spell = create_spell(
            spell_id="levitate",
            name="Levitate",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Levitation allows vertical movement only.",
            duration="1 Turn per level",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        move_effects = [e for e in parsed.effects if e.grants_movement]
        assert len(move_effects) >= 1

        effect = move_effects[0]
        assert effect.movement_type == "levitate"

    def test_parse_water_walk(self, resolver):
        """Parse Water Walk spell."""
        spell = create_spell(
            spell_id="water_walk",
            name="Water Walk",
            magic_type=MagicType.DIVINE,
            level=3,
            description="Walk on water as if it were solid ground. Water walking lasts 1 hour.",
            duration="1 Hour",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        move_effects = [e for e in parsed.effects if e.grants_movement]
        assert len(move_effects) >= 1

        effect = move_effects[0]
        assert effect.movement_type == "water_walk"

    def test_parse_spider_climb(self, resolver):
        """Parse Spider Climb spell."""
        spell = create_spell(
            spell_id="spider_climb",
            name="Spider Climb",
            magic_type=MagicType.ARCANE,
            level=1,
            description="Spider climb allows walking on walls and ceilings at 60' per turn.",
            duration="1 Turn per level",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        move_effects = [e for e in parsed.effects if e.grants_movement]
        assert len(move_effects) >= 1

        effect = move_effects[0]
        assert effect.movement_type == "climb"


# =============================================================================
# INVISIBILITY/ILLUSION SPELL PARSING TESTS
# =============================================================================


class TestInvisibilitySpellParsing:
    """Tests for parsing invisibility spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_invisibility(self, resolver):
        """Parse Invisibility spell."""
        spell = create_spell(
            spell_id="invisibility",
            name="Invisibility",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Target becomes invisible until they attack.",
            duration="Until attack",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        inv_effects = [e for e in parsed.effects if e.is_invisibility_effect]
        assert len(inv_effects) >= 1

        effect = inv_effects[0]
        assert effect.invisibility_type == "normal"

    def test_parse_improved_invisibility(self, resolver):
        """Parse Improved Invisibility spell."""
        spell = create_spell(
            spell_id="improved_invisibility",
            name="Improved Invisibility",
            magic_type=MagicType.ARCANE,
            level=4,
            description="Improved invisibility persists even while attacking.",
            duration="1 Turn per level",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        inv_effects = [e for e in parsed.effects if e.is_invisibility_effect]
        assert len(inv_effects) >= 1

        effect = inv_effects[0]
        assert effect.invisibility_type == "improved"


class TestIllusionSpellParsing:
    """Tests for parsing illusion spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_phantasmal_force(self, resolver):
        """Parse Phantasmal Force spell."""
        spell = create_spell(
            spell_id="phantasmal_force",
            name="Phantasmal Force",
            magic_type=MagicType.ARCANE,
            level=2,
            description="Create a phantasmal illusion that seems real.",
            duration="Concentration",
            range_="240'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        ill_effects = [e for e in parsed.effects if e.is_illusion_effect]
        assert len(ill_effects) >= 1

        effect = ill_effects[0]
        assert effect.illusion_type == "phantasm"

    def test_parse_silent_image(self, resolver):
        """Parse Silent Image spell."""
        spell = create_spell(
            spell_id="silent_image",
            name="Silent Image",
            magic_type=MagicType.ARCANE,
            level=1,
            description="Create a silent image of an object or creature.",
            duration="Concentration",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        ill_effects = [e for e in parsed.effects if e.is_illusion_effect]
        assert len(ill_effects) >= 1

        effect = ill_effects[0]
        assert effect.illusion_type == "visual"


# =============================================================================
# PROTECTION SPELL PARSING TESTS
# =============================================================================


class TestProtectionSpellParsing:
    """Tests for parsing protection spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_protection_from_evil(self, resolver):
        """Parse Protection from Evil spell."""
        spell = create_spell(
            spell_id="protection_from_evil",
            name="Protection from Evil",
            magic_type=MagicType.DIVINE,
            level=1,
            description="Protection from evil grants +1 to AC and saves vs evil creatures.",
            duration="6 Turns",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        prot_effects = [e for e in parsed.effects if e.is_protection_effect]
        assert len(prot_effects) >= 1

        effect = prot_effects[0]
        assert effect.protection_type == "evil"
        assert effect.protection_bonus == 1

    def test_parse_magic_circle(self, resolver):
        """Parse Magic Circle spell."""
        spell = create_spell(
            spell_id="magic_circle",
            name="Magic Circle Against Evil",
            magic_type=MagicType.DIVINE,
            level=3,
            description="Create a magic circle that protects all within.",
            duration="12 Turns",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        prot_effects = [e for e in parsed.effects if e.is_protection_effect]
        assert len(prot_effects) >= 1

        effect = prot_effects[0]
        assert effect.protection_type == "evil"


# =============================================================================
# CONTROLLER METHOD TESTS
# =============================================================================


class TestControllerMiscMethods:
    """Tests for GlobalController misc spell methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add locations
        room1 = LocationState(
            location_id="room_1",
            name="Starting Room",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="dungeon",
        )
        controller._locations["room_1"] = room1

        room2 = LocationState(
            location_id="room_2",
            name="Destination Room",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="dungeon",
        )
        controller._locations["room_2"] = room2

        # Add wizard
        wizard = CharacterState(
            character_id="wizard",
            name="Test Wizard",
            character_class="Magician",
            level=9,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 18, "WIS": 12, "CHA": 11},
            hp_current=25,
            hp_max=30,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["wizard"] = wizard

        # Add fighter
        fighter = CharacterState(
            character_id="fighter",
            name="Test Fighter",
            character_class="Fighter",
            level=7,
            ability_scores={"STR": 18, "DEX": 14, "CON": 16, "INT": 10, "WIS": 12, "CHA": 13},
            hp_current=45,
            hp_max=50,
            armor_class=17,
            base_speed=40,
        )
        controller._characters["fighter"] = fighter

        return controller

    def test_teleport_character(self, controller):
        """Test teleporting a character."""
        result = controller.teleport_character(
            caster_id="wizard",
            target_id="wizard",
            destination_location_id="room_2",
            passengers=["fighter"],
        )

        assert result["success"] is True
        assert result["destination"] == "room_2"
        assert result["total_teleported"] == 2
        assert "wizard" in result["teleported"]
        assert "fighter" in result["teleported"]

    def test_teleport_invalid_destination(self, controller):
        """Test teleporting to invalid destination."""
        result = controller.teleport_character(
            caster_id="wizard",
            target_id="wizard",
            destination_location_id="nonexistent",
        )

        assert "error" in result

    def test_cast_detect_magic(self, controller):
        """Test casting Detect Magic."""
        result = controller.cast_detect_magic(
            caster_id="wizard",
            location_id="room_1",
        )

        assert result["success"] is True
        assert result["spell"] == "Detect Magic"
        assert "magical_auras_detected" in result

    def test_grant_flight(self, controller):
        """Test granting flight."""
        result = controller.grant_flight(
            caster_id="wizard",
            target_id="fighter",
            speed=120,
            duration_turns=6,
        )

        assert result["success"] is True
        assert result["spell"] == "Fly"
        assert result["speed"] == 120

        # Verify stat modifier was added
        fighter = controller._characters["fighter"]
        assert fighter.get_stat_modifier_total("movement_fly") == 120

    def test_grant_invisibility(self, controller):
        """Test granting invisibility."""
        result = controller.grant_invisibility(
            caster_id="wizard",
            target_id="fighter",
            invisibility_type="normal",
        )

        assert result["success"] is True
        assert result["spell"] == "Invisibility"

        # Verify condition was added
        fighter = controller._characters["fighter"]
        inv_conditions = [c for c in fighter.conditions if c.condition_type == ConditionType.INVISIBLE]
        assert len(inv_conditions) == 1

    def test_cast_protection_from_evil(self, controller):
        """Test Protection from Evil."""
        result = controller.cast_protection_from_evil(
            caster_id="wizard",
            target_id="fighter",
        )

        assert result["success"] is True
        assert result["ac_bonus"] == 1
        assert result["save_bonus"] == 1

        # Verify stat modifiers were added
        fighter = controller._characters["fighter"]
        assert len(fighter.stat_modifiers) >= 2


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestMiscSpellIntegration:
    """Integration tests for miscellaneous spells."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Locations
        for i in range(3):
            loc = LocationState(
                location_id=f"room_{i}",
                name=f"Room {i}",
                location_type=LocationType.DUNGEON_ROOM,
                terrain="dungeon",
            )
            controller._locations[f"room_{i}"] = loc

        # Party
        wizard = CharacterState(
            character_id="wizard",
            name="Party Wizard",
            character_class="Magician",
            level=9,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 18, "WIS": 12, "CHA": 11},
            hp_current=25,
            hp_max=30,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["wizard"] = wizard

        cleric = CharacterState(
            character_id="cleric",
            name="Party Cleric",
            character_class="Cleric",
            level=7,
            ability_scores={"STR": 14, "DEX": 10, "CON": 14, "INT": 10, "WIS": 17, "CHA": 12},
            hp_current=35,
            hp_max=40,
            armor_class=16,
            base_speed=40,
        )
        controller._characters["cleric"] = cleric

        return controller

    def test_buff_and_teleport_workflow(self, controller):
        """Test buffing party and teleporting."""
        # Cleric casts Protection from Evil on wizard
        prot_result = controller.cast_protection_from_evil(
            caster_id="cleric",
            target_id="wizard",
        )
        assert prot_result["success"] is True

        # Wizard makes self invisible
        inv_result = controller.grant_invisibility(
            caster_id="wizard",
            target_id="wizard",
        )
        assert inv_result["success"] is True

        # Wizard teleports party
        teleport_result = controller.teleport_character(
            caster_id="wizard",
            target_id="wizard",
            destination_location_id="room_2",
            passengers=["cleric"],
        )
        assert teleport_result["success"] is True
        assert teleport_result["total_teleported"] == 2

        # Verify wizard has protection and invisibility
        wizard = controller._characters["wizard"]
        assert len(wizard.stat_modifiers) >= 2
        assert any(c.condition_type == ConditionType.INVISIBLE for c in wizard.conditions)

    def test_flight_and_detection_workflow(self, controller):
        """Test flying and detecting magic."""
        # Wizard casts fly on self
        fly_result = controller.grant_flight(
            caster_id="wizard",
            target_id="wizard",
            speed=120,
        )
        assert fly_result["success"] is True

        # Wizard detects magic
        detect_result = controller.cast_detect_magic(
            caster_id="wizard",
            location_id="room_0",
        )
        assert detect_result["success"] is True

        # Verify wizard can fly
        wizard = controller._characters["wizard"]
        assert wizard.get_stat_modifier_total("movement_fly") == 120
