"""
Tests for Phase 3: Significant Spell Systems.

Tests flight/verticality, barriers/walls, geas/compulsion, and teleportation mishaps.
"""

import pytest

from src.data_models import (
    CharacterState,
    LocationState,
    LocationType,
    FlightState,
    LocationFamiliarity,
    BarrierType,
    BarrierEffect,
    CompulsionState,
)
from src.narrative.spell_resolver import (
    MagicType,
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
# FLIGHT STATE TESTS
# =============================================================================


class TestFlightState:
    """Tests for FlightState enum and properties."""

    def test_flight_state_values(self):
        """Test FlightState enum values exist."""
        assert FlightState.GROUNDED == "grounded"
        assert FlightState.HOVERING == "hovering"
        assert FlightState.FLYING == "flying"
        assert FlightState.FALLING == "falling"

    def test_can_be_melee_attacked(self):
        """Test melee attack reach property."""
        assert FlightState.GROUNDED.can_be_melee_attacked is True
        assert FlightState.FLYING.can_be_melee_attacked is False
        assert FlightState.HOVERING.can_be_melee_attacked is False

    def test_requires_concentration(self):
        """Test concentration property."""
        assert FlightState.FLYING.requires_concentration is True
        assert FlightState.HOVERING.requires_concentration is True
        assert FlightState.GROUNDED.requires_concentration is False


class TestCharacterFlightMethods:
    """Tests for CharacterState flight methods."""

    @pytest.fixture
    def character(self):
        """Create a test character."""
        return CharacterState(
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

    def test_grant_flight(self, character):
        """Test granting flight to a character."""
        character.grant_flight(speed=120, source="Fly spell")

        assert character.flight_state == FlightState.FLYING
        assert character.flight_speed == 120
        assert character.flight_source == "Fly spell"
        assert character.is_flying is True

    def test_remove_flight_while_airborne(self, character):
        """Test removing flight while flying causes falling."""
        character.grant_flight(speed=120, source="Fly spell")
        character.altitude = 60

        was_airborne = character.remove_flight()

        assert was_airborne is True
        assert character.is_falling is True
        assert character.flight_speed is None

    def test_land(self, character):
        """Test voluntary landing."""
        character.grant_flight(speed=120, source="Fly spell")
        character.altitude = 30

        character.land()

        assert character.flight_state == FlightState.GROUNDED
        assert character.altitude == 0

    def test_fall_damage_calculation(self, character):
        """Test fall damage calculation."""
        character.altitude = 50  # 50 feet

        dice_count, dice_expr = character.calculate_fall_damage()

        assert dice_count == 5  # 1d6 per 10 feet
        assert dice_expr == "5d6"

    def test_fall_damage_cap(self, character):
        """Test fall damage caps at 20d6."""
        character.altitude = 500  # Very high

        dice_count, dice_expr = character.calculate_fall_damage()

        assert dice_count == 20  # Capped
        assert dice_expr == "20d6"


# =============================================================================
# LOCATION FAMILIARITY TESTS
# =============================================================================


class TestLocationFamiliarity:
    """Tests for LocationFamiliarity enum."""

    def test_success_chances(self):
        """Test success chance percentages."""
        assert LocationFamiliarity.INTIMATELY_KNOWN.success_chance == 95
        assert LocationFamiliarity.WELL_KNOWN.success_chance == 85
        assert LocationFamiliarity.VISITED.success_chance == 70
        assert LocationFamiliarity.DESCRIBED.success_chance == 50
        assert LocationFamiliarity.UNKNOWN.success_chance == 25

    def test_mishap_chances(self):
        """Test mishap chance percentages."""
        assert LocationFamiliarity.INTIMATELY_KNOWN.mishap_chance == 1
        assert LocationFamiliarity.WELL_KNOWN.mishap_chance == 3
        assert LocationFamiliarity.VISITED.mishap_chance == 8
        assert LocationFamiliarity.DESCRIBED.mishap_chance == 15
        assert LocationFamiliarity.UNKNOWN.mishap_chance == 30


# =============================================================================
# BARRIER EFFECT TESTS
# =============================================================================


class TestBarrierEffect:
    """Tests for BarrierEffect dataclass."""

    def test_create_wall_of_fire(self):
        """Test creating a Wall of Fire barrier."""
        barrier = BarrierEffect(
            barrier_type=BarrierType.FIRE,
            name="Wall of Fire",
            caster_id="wizard",
            location_id="corridor",
            length_feet=40,
            height_feet=20,
            duration_turns=12,
            contact_damage="2d6",
            damage_type="fire",
        )

        assert barrier.barrier_type == BarrierType.FIRE
        assert barrier.blocks_movement is True
        assert barrier.contact_damage == "2d6"
        assert barrier.is_active is True

    def test_barrier_tick(self):
        """Test barrier duration ticking."""
        barrier = BarrierEffect(
            barrier_type=BarrierType.STONE,
            duration_turns=3,
        )

        assert barrier.tick() is False  # Still active
        assert barrier.duration_turns == 2
        assert barrier.tick() is False
        assert barrier.tick() is True  # Expired
        assert barrier.is_active is False

    def test_breakable_barrier(self):
        """Test barrier damage and destruction."""
        barrier = BarrierEffect(
            barrier_type=BarrierType.ICE,
            hp=20,
            hp_max=20,
            can_be_broken=True,
        )

        assert barrier.take_damage(15) is False
        assert barrier.hp == 5

        assert barrier.take_damage(10) is True
        assert barrier.is_active is False


# =============================================================================
# COMPULSION STATE TESTS
# =============================================================================


class TestCompulsionState:
    """Tests for CompulsionState (Geas) dataclass."""

    def test_create_geas(self):
        """Test creating a geas compulsion."""
        geas = CompulsionState(
            target_id="knight",
            caster_id="wizard",
            goal="Slay the dragon",
            forbidden_actions=["flee", "hide from dragon", "give up"],
        )

        assert geas.goal == "Slay the dragon"
        assert geas.is_active is True
        assert geas.current_penalty_level == 0

    def test_violation_check(self):
        """Test checking for violations."""
        geas = CompulsionState(
            target_id="knight",
            caster_id="wizard",
            goal="Slay the dragon",
            forbidden_actions=["flee", "hide"],
        )

        assert geas.check_violation("I attack the dragon") is False
        assert geas.check_violation("I flee from the dragon") is True
        assert geas.check_violation("I hide behind a rock") is True

    def test_violation_escalation(self):
        """Test penalty escalation on violation."""
        geas = CompulsionState(
            target_id="knight",
            caster_id="wizard",
            goal="Slay the dragon",
        )

        result1 = geas.register_violation()
        assert result1["penalty_level"] == 1
        assert result1["penalty_modifier"] == -1
        assert result1["is_lethal"] is False

        result2 = geas.register_violation()
        assert result2["penalty_level"] == 2
        assert result2["penalty_modifier"] == -2

    def test_lethal_violation(self):
        """Test that max violations are lethal."""
        geas = CompulsionState(
            target_id="knight",
            caster_id="wizard",
            goal="Slay the dragon",
        )

        # Violate until lethal
        for _ in range(5):
            result = geas.register_violation()

        assert result["is_lethal"] is True
        assert result["penalty_level"] == 5

    def test_complete_geas(self):
        """Test completing a geas."""
        geas = CompulsionState(
            target_id="knight",
            caster_id="wizard",
            goal="Slay the dragon",
        )

        result = geas.complete()

        assert result["completed"] is True
        assert geas.is_active is False
        assert geas.completed is True


class TestCharacterCompulsionMethods:
    """Tests for CharacterState compulsion methods."""

    @pytest.fixture
    def character(self):
        """Create a test character."""
        return CharacterState(
            character_id="knight",
            name="Sir Test",
            character_class="Fighter",
            level=5,
            ability_scores={"STR": 17, "DEX": 12, "CON": 14, "INT": 10, "WIS": 11, "CHA": 13},
            hp_current=35,
            hp_max=40,
            armor_class=17,
            base_speed=40,
        )

    def test_add_compulsion(self, character):
        """Test adding a compulsion to a character."""
        geas = CompulsionState(
            target_id=character.character_id,
            caster_id="wizard",
            goal="Rescue the princess",
        )

        character.add_compulsion(geas)

        assert len(character.compulsions) == 1
        assert len(character.get_active_compulsions()) == 1

    def test_check_compulsion_violation(self, character):
        """Test checking violations against character's compulsions."""
        geas = CompulsionState(
            target_id=character.character_id,
            caster_id="wizard",
            goal="Rescue the princess",
            forbidden_actions=["abandon", "ignore princess"],
        )
        character.add_compulsion(geas)

        violations = character.check_compulsion_violation("I abandon the quest")

        assert len(violations) == 1
        assert violations[0]["violation"] is True

    def test_compulsion_penalty(self, character):
        """Test getting penalty from compulsions."""
        geas = CompulsionState(
            target_id=character.character_id,
            caster_id="wizard",
            goal="Complete the quest",
        )
        geas.current_penalty_level = 2
        character.add_compulsion(geas)

        penalty = character.get_compulsion_penalty()

        assert penalty == -2


# =============================================================================
# BARRIER SPELL PARSING TESTS
# =============================================================================


class TestBarrierSpellParsing:
    """Tests for parsing barrier/wall spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_wall_of_fire(self, resolver):
        """Parse Wall of Fire spell."""
        spell = create_spell(
            spell_id="wall_of_fire",
            name="Wall of Fire",
            magic_type=MagicType.ARCANE,
            level=4,
            description="Create a wall of fire that deals 2d6 damage to those passing through.",
            duration="Concentration",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        barrier_effects = [e for e in parsed.effects if e.is_barrier_effect]
        assert len(barrier_effects) >= 1

        effect = barrier_effects[0]
        assert effect.barrier_type == "fire"
        assert effect.barrier_damage == "2d6"

    def test_parse_wall_of_ice(self, resolver):
        """Parse Wall of Ice spell."""
        spell = create_spell(
            spell_id="wall_of_ice",
            name="Wall of Ice",
            magic_type=MagicType.ARCANE,
            level=4,
            description="Create a wall of ice blocking movement and vision.",
            duration="12 Turns",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        barrier_effects = [e for e in parsed.effects if e.is_barrier_effect]
        assert len(barrier_effects) >= 1

        effect = barrier_effects[0]
        assert effect.barrier_type == "ice"
        assert effect.barrier_blocks_vision is True

    def test_parse_wall_of_stone(self, resolver):
        """Parse Wall of Stone spell."""
        spell = create_spell(
            spell_id="wall_of_stone",
            name="Wall of Stone",
            magic_type=MagicType.ARCANE,
            level=5,
            description="Create a permanent wall of stone.",
            duration="Permanent",
            range_="60'",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        barrier_effects = [e for e in parsed.effects if e.is_barrier_effect]
        assert len(barrier_effects) >= 1

        effect = barrier_effects[0]
        assert effect.barrier_type == "stone"


# =============================================================================
# GEAS SPELL PARSING TESTS
# =============================================================================


class TestGeasSpellParsing:
    """Tests for parsing geas/compulsion spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_geas(self, resolver):
        """Parse Geas spell."""
        spell = create_spell(
            spell_id="geas",
            name="Geas",
            magic_type=MagicType.ARCANE,
            level=6,
            description="Place a geas upon the target, compelling them to complete a quest.",
            duration="Until completed",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        compulsion_effects = [e for e in parsed.effects if e.is_compulsion_effect]
        assert len(compulsion_effects) >= 1

        effect = compulsion_effects[0]
        assert effect.compulsion_type == "geas"

    def test_parse_holy_quest(self, resolver):
        """Parse Holy Quest spell."""
        spell = create_spell(
            spell_id="holy_quest",
            name="Holy Quest",
            magic_type=MagicType.DIVINE,
            level=5,
            description="The target must obey and complete a holy quest.",
            duration="Until completed",
            range_="Touch",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        compulsion_effects = [e for e in parsed.effects if e.is_compulsion_effect]
        assert len(compulsion_effects) >= 1


# =============================================================================
# ANTIMAGIC SPELL PARSING TESTS
# =============================================================================


class TestAntimagicSpellParsing:
    """Tests for parsing anti-magic spells."""

    @pytest.fixture
    def resolver(self):
        """Create a test resolver."""
        return SpellResolver()

    def test_parse_antimagic_shell(self, resolver):
        """Parse Anti-Magic Shell spell."""
        spell = create_spell(
            spell_id="antimagic_shell",
            name="Anti-Magic Shell",
            magic_type=MagicType.ARCANE,
            level=6,
            description="Create an anti-magic shell in a 10 foot radius that nullifies magic.",
            duration="12 Turns",
            range_="Self",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        am_effects = [e for e in parsed.effects if e.is_antimagic_effect]
        assert len(am_effects) >= 1

        effect = am_effects[0]
        assert effect.antimagic_type == "nullify"
        assert effect.antimagic_radius == 10


# =============================================================================
# CONTROLLER METHOD TESTS
# =============================================================================


class TestControllerBarrierMethods:
    """Tests for GlobalController barrier methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add location
        corridor = LocationState(
            location_id="corridor",
            name="Long Corridor",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="dungeon",
        )
        controller._locations["corridor"] = corridor

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

        return controller

    def test_create_barrier(self, controller):
        """Test creating a barrier."""
        result = controller.create_barrier(
            caster_id="wizard",
            location_id="corridor",
            barrier_type="fire",
            contact_damage="2d6",
            damage_type="fire",
        )

        assert result["success"] is True
        assert result["barrier_type"] == "fire"
        assert result["contact_damage"] == "2d6"
        assert result["blocks_movement"] is True


class TestControllerGeasMethods:
    """Tests for GlobalController geas methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add wizard
        wizard = CharacterState(
            character_id="wizard",
            name="Test Wizard",
            character_class="Magician",
            level=12,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 18, "WIS": 12, "CHA": 11},
            hp_current=30,
            hp_max=35,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["wizard"] = wizard

        # Add knight
        knight = CharacterState(
            character_id="knight",
            name="Sir Test",
            character_class="Fighter",
            level=8,
            ability_scores={"STR": 18, "DEX": 12, "CON": 16, "INT": 10, "WIS": 11, "CHA": 14},
            hp_current=50,
            hp_max=55,
            armor_class=18,
            base_speed=40,
        )
        controller._characters["knight"] = knight

        return controller

    def test_apply_geas(self, controller):
        """Test applying a geas."""
        result = controller.apply_geas(
            caster_id="wizard",
            target_id="knight",
            goal="Retrieve the Holy Grail",
            forbidden_actions=["abandon", "give up"],
        )

        assert result["success"] is True
        assert result["goal"] == "Retrieve the Holy Grail"
        assert len(result["forbidden_actions"]) == 2

        # Verify geas was added
        knight = controller._characters["knight"]
        assert len(knight.compulsions) == 1

    def test_check_geas_violation(self, controller):
        """Test checking for geas violation."""
        # Apply geas
        controller.apply_geas(
            caster_id="wizard",
            target_id="knight",
            goal="Complete the quest",
            forbidden_actions=["abandon", "flee"],
        )

        # Check for violation
        result = controller.check_geas_violation(
            character_id="knight",
            action="I abandon the quest",
        )

        assert result["violated"] is True
        assert len(result["violations"]) == 1

    def test_complete_geas(self, controller):
        """Test completing a geas."""
        # Apply geas
        apply_result = controller.apply_geas(
            caster_id="wizard",
            target_id="knight",
            goal="Slay the beast",
        )

        # Complete it
        complete_result = controller.complete_geas(
            character_id="knight",
            compulsion_id=apply_result["compulsion_id"],
        )

        assert complete_result["completed"] is True


class TestControllerTeleportMethods:
    """Tests for GlobalController teleport methods."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add locations
        for name in ["home", "castle", "dungeon"]:
            loc = LocationState(
                location_id=name,
                name=name.title(),
                location_type=LocationType.DUNGEON_ROOM,
                terrain="dungeon",
            )
            controller._locations[name] = loc

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

        return controller

    def test_teleport_with_familiarity(self, controller):
        """Test teleporting with familiarity system."""
        result = controller.teleport_with_familiarity(
            caster_id="wizard",
            target_ids=["wizard"],
            destination_id="home",
            familiarity="intimately_known",
        )

        assert "success" in result
        assert result["familiarity"] == "intimately_known"
        assert result["success_threshold"] == 95


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestPhase3Integration:
    """Integration tests for Phase 3 systems."""

    @pytest.fixture
    def controller(self):
        """Create a controller with test data."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()

        # Add location
        battlefield = LocationState(
            location_id="battlefield",
            name="Battlefield",
            location_type=LocationType.DUNGEON_ROOM,
            terrain="open",
        )
        controller._locations["battlefield"] = battlefield

        # Add flying wizard
        wizard = CharacterState(
            character_id="wizard",
            name="Flying Wizard",
            character_class="Magician",
            level=12,
            ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 18, "WIS": 12, "CHA": 11},
            hp_current=30,
            hp_max=35,
            armor_class=10,
            base_speed=40,
        )
        controller._characters["wizard"] = wizard

        # Add enemy
        enemy = CharacterState(
            character_id="enemy",
            name="Ground Fighter",
            character_class="Fighter",
            level=8,
            ability_scores={"STR": 18, "DEX": 12, "CON": 16, "INT": 10, "WIS": 11, "CHA": 10},
            hp_current=50,
            hp_max=55,
            armor_class=16,
            base_speed=40,
        )
        controller._characters["enemy"] = enemy

        return controller

    def test_flight_and_barrier_combo(self, controller):
        """Test using flight and barriers together."""
        wizard = controller._characters["wizard"]

        # Wizard flies up
        wizard.grant_flight(speed=120, source="Fly spell")
        wizard.altitude = 30

        assert wizard.is_flying is True
        assert wizard.altitude == 30

        # Create wall of fire below
        barrier_result = controller.create_barrier(
            caster_id="wizard",
            location_id="battlefield",
            barrier_type="fire",
            contact_damage="2d6",
        )

        assert barrier_result["success"] is True

        # Enemy can't reach flying wizard with melee
        assert FlightState.FLYING.can_be_melee_attacked is False

    def test_geas_workflow(self, controller):
        """Test complete geas workflow."""
        wizard = controller._characters["wizard"]
        enemy = controller._characters["enemy"]

        # Apply geas to enemy
        geas_result = controller.apply_geas(
            caster_id="wizard",
            target_id="enemy",
            goal="Serve the wizard for one year",
            forbidden_actions=["attack wizard", "disobey"],
        )

        assert geas_result["success"] is True

        # Check violation
        violation_result = controller.check_geas_violation(
            character_id="enemy",
            action="I attack wizard with my sword",
        )

        assert violation_result["violated"] is True
        assert violation_result["penalty"] < 0  # Has penalty now

        # Complete the geas after time passes
        complete_result = controller.complete_geas(
            character_id="enemy",
            compulsion_id=geas_result["compulsion_id"],
        )

        assert complete_result["completed"] is True
