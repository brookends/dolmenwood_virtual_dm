"""
Tests for Phase 2.2: Door/Lock/Glyph System.

Tests glyph data model, controller methods, and spell parsing for
Glyph of Sealing, Glyph of Locking, Knock, and Serpent Glyph.
"""

import pytest
from src.data_models import Glyph, GlyphType, CharacterState
from src.game_state.global_controller import GlobalController
from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    MagicType,
    MechanicalEffectCategory,
)


# =============================================================================
# FIXTURES
# =============================================================================


def make_spell(
    spell_id: str,
    name: str,
    level: int,
    magic_type: MagicType,
    description: str,
    duration: str = "2d6 Turns",
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


@pytest.fixture
def resolver():
    """Create a SpellResolver instance."""
    return SpellResolver()


@pytest.fixture
def magic_user():
    """Create a magic-user character."""
    return CharacterState(
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


@pytest.fixture
def low_level_caster():
    """Create a low-level magic-user."""
    return CharacterState(
        character_id="apprentice_1",
        name="Novice",
        character_class="Magic-User",
        level=1,
        ability_scores={"STR": 8, "DEX": 12, "CON": 10, "INT": 14, "WIS": 10, "CHA": 10},
        hp_current=4,
        hp_max=4,
        armor_class=10,
        base_speed=40,
    )


@pytest.fixture
def high_level_caster():
    """Create a high-level magic-user."""
    return CharacterState(
        character_id="archmage_1",
        name="Archmage",
        character_class="Magic-User",
        level=10,
        ability_scores={"STR": 8, "DEX": 14, "CON": 12, "INT": 18, "WIS": 14, "CHA": 14},
        hp_current=20,
        hp_max=20,
        armor_class=14,
        base_speed=40,
    )


@pytest.fixture
def controller_with_caster(magic_user):
    """Create a GlobalController with a magic-user."""
    controller = GlobalController()
    controller.add_character(magic_user)
    return controller, magic_user


# =============================================================================
# GLYPH DATA MODEL TESTS
# =============================================================================


class TestGlyphDataModel:
    """Tests for the Glyph dataclass."""

    def test_glyph_creation_sealing(self):
        """Create a basic sealing glyph."""
        glyph = Glyph(
            glyph_type=GlyphType.SEALING,
            name="Glyph of Sealing",
            source_spell_id="glyph_of_sealing",
            caster_id="mage_1",
            caster_level=5,
            target_type="door",
            target_id="door_001",
            duration_turns=10,
            turns_remaining=10,
        )

        assert glyph.glyph_type == GlyphType.SEALING
        assert glyph.caster_level == 5
        assert glyph.is_active(0) is True
        assert glyph.is_visible is True

    def test_glyph_creation_locking(self):
        """Create a locking glyph with password."""
        glyph = Glyph(
            glyph_type=GlyphType.LOCKING,
            name="Glyph of Locking",
            source_spell_id="glyph_of_locking",
            caster_id="mage_1",
            caster_level=5,
            target_type="door",
            target_id="door_001",
            password="opensesame",
            can_be_bypassed_by_level=3,
        )

        assert glyph.glyph_type == GlyphType.LOCKING
        assert glyph.password == "opensesame"
        assert glyph.can_be_bypassed_by_level == 3

    def test_glyph_creation_trap(self):
        """Create a trap glyph."""
        glyph = Glyph(
            glyph_type=GlyphType.TRAP,
            name="Serpent Glyph",
            source_spell_id="serpent_glyph",
            caster_id="mage_1",
            caster_level=5,
            target_type="door",
            target_id="door_001",
            trigger_condition="touch",
            trap_effect="summon_adders",
            trap_save_type="spell",
        )

        assert glyph.glyph_type == GlyphType.TRAP
        assert glyph.trigger_condition == "touch"
        assert glyph.trap_effect == "summon_adders"

    def test_glyph_is_active_duration(self):
        """Glyph becomes inactive when duration expires."""
        glyph = Glyph(
            glyph_type=GlyphType.SEALING,
            duration_turns=5,
            turns_remaining=0,
        )

        assert glyph.is_active(0) is False

    def test_glyph_is_active_disabled(self):
        """Glyph becomes inactive when temporarily disabled."""
        glyph = Glyph(
            glyph_type=GlyphType.LOCKING,
            disabled_until_turn=10,
        )

        assert glyph.is_active(5) is False  # Before disable ends
        assert glyph.is_active(15) is True  # After disable ends

    def test_glyph_bypass_caster(self):
        """Caster can always bypass their own glyph."""
        glyph = Glyph(
            glyph_type=GlyphType.LOCKING,
            caster_id="mage_1",
            caster_level=5,
        )

        can_bypass, reason = glyph.check_bypass("mage_1")
        assert can_bypass is True
        assert reason == "caster_control"

    def test_glyph_bypass_password(self):
        """Correct password bypasses locking glyph."""
        glyph = Glyph(
            glyph_type=GlyphType.LOCKING,
            caster_id="mage_1",
            caster_level=5,
            password="secret",
        )

        can_bypass, reason = glyph.check_bypass(
            "other_person", password_given="secret"
        )
        assert can_bypass is True
        assert reason == "correct_password"

    def test_glyph_bypass_wrong_password(self):
        """Wrong password doesn't bypass locking glyph."""
        glyph = Glyph(
            glyph_type=GlyphType.LOCKING,
            caster_id="mage_1",
            caster_level=5,
            password="secret",
        )

        can_bypass, reason = glyph.check_bypass(
            "other_person", password_given="wrong"
        )
        assert can_bypass is False

    def test_glyph_bypass_higher_level(self):
        """Higher-level caster can bypass glyph."""
        glyph = Glyph(
            glyph_type=GlyphType.LOCKING,
            caster_id="mage_1",
            caster_level=5,
            can_be_bypassed_by_level=3,  # Need 5+3 = level 8+
        )

        can_bypass, reason = glyph.check_bypass(
            "archmage", character_level=10
        )
        assert can_bypass is True
        assert "level_10" in reason

    def test_glyph_trigger_trap(self):
        """Trigger a trap glyph."""
        glyph = Glyph(
            glyph_type=GlyphType.TRAP,
            name="Serpent Glyph",
            trap_effect="summon_adders",
            trap_damage="2d6",
            trap_save_type="spell",
        )

        result = glyph.trigger_trap()

        assert result["triggered"] is True
        assert result["effect"] == "summon_adders"
        assert result["damage"] == "2d6"
        assert glyph.triggered is True

    def test_glyph_trigger_trap_only_once(self):
        """Trap glyph can only trigger once."""
        glyph = Glyph(
            glyph_type=GlyphType.TRAP,
            trap_effect="summon_adders",
        )

        glyph.trigger_trap()
        result = glyph.trigger_trap()

        assert result["triggered"] is False
        assert result["reason"] == "already_triggered"

    def test_glyph_dispel(self):
        """Dispel a glyph."""
        glyph = Glyph(
            glyph_type=GlyphType.SEALING,
            duration_turns=10,
            turns_remaining=10,
        )

        result = glyph.dispel()

        assert result is True
        assert glyph.turns_remaining == 0
        assert glyph.is_active(0) is False

    def test_glyph_tick_turn(self):
        """Glyph duration decreases each turn."""
        glyph = Glyph(
            glyph_type=GlyphType.SEALING,
            duration_turns=5,
            turns_remaining=5,
        )

        glyph.tick_turn()
        assert glyph.turns_remaining == 4

        glyph.tick_turn()
        glyph.tick_turn()
        glyph.tick_turn()
        glyph.tick_turn()
        assert glyph.is_active(0) is False


# =============================================================================
# CONTROLLER GLYPH TESTS
# =============================================================================


class TestControllerGlyphMethods:
    """Tests for GlobalController glyph management."""

    def test_place_glyph_sealing(self, controller_with_caster):
        """Place a sealing glyph via controller."""
        controller, caster = controller_with_caster

        result = controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.SEALING,
            source_spell_id="glyph_of_sealing",
            name="Glyph of Sealing",
            duration_turns=10,
        )

        assert result["placed"] is True
        assert result["glyph_type"] == "sealing"
        assert result["target_id"] == "door_001"
        assert result["caster_level"] == caster.level

    def test_place_glyph_locking_with_password(self, controller_with_caster):
        """Place a locking glyph with password."""
        controller, caster = controller_with_caster

        result = controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.LOCKING,
            source_spell_id="glyph_of_locking",
            password="mysecret",
        )

        assert result["placed"] is True
        assert result["has_password"] is True

    def test_get_glyphs_on_target(self, controller_with_caster):
        """Get all glyphs on a target."""
        controller, caster = controller_with_caster

        controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.SEALING,
            source_spell_id="glyph_of_sealing",
        )
        controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.LOCKING,
            source_spell_id="glyph_of_locking",
        )

        glyphs = controller.get_glyphs_on_target("door_001")

        assert len(glyphs) == 2

    def test_dispel_glyph(self, controller_with_caster):
        """Dispel a glyph via controller."""
        controller, caster = controller_with_caster

        result = controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.SEALING,
            source_spell_id="glyph_of_sealing",
        )
        glyph_id = result["glyph_id"]

        dispel_result = controller.dispel_glyph(glyph_id, caster.character_id, "Knock spell")

        assert dispel_result["dispelled"] is True
        assert dispel_result["glyph_type"] == "sealing"

    def test_disable_glyph_temporarily(self, controller_with_caster):
        """Temporarily disable a glyph."""
        controller, caster = controller_with_caster

        result = controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.LOCKING,
            source_spell_id="glyph_of_locking",
        )
        glyph_id = result["glyph_id"]

        disable_result = controller.disable_glyph_temporarily(glyph_id, 1)

        assert disable_result["disabled"] is True
        assert disable_result["disabled_until_turn"] is not None

    def test_check_glyph_bypass_blocked(self, controller_with_caster, low_level_caster):
        """Check bypass when blocked by glyph."""
        controller, caster = controller_with_caster
        controller.add_character(low_level_caster)

        controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.LOCKING,
            source_spell_id="glyph_of_locking",
        )

        result = controller.check_glyph_bypass(
            target_id="door_001",
            character_id=low_level_caster.character_id,
        )

        assert result["can_bypass"] is False
        assert len(result["blocking_glyphs"]) == 1

    def test_check_glyph_bypass_allowed(self, controller_with_caster):
        """Check bypass when caster approaches their own glyph."""
        controller, caster = controller_with_caster

        controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.LOCKING,
            source_spell_id="glyph_of_locking",
        )

        result = controller.check_glyph_bypass(
            target_id="door_001",
            character_id=caster.character_id,
        )

        assert result["can_bypass"] is True
        assert len(result["bypassed_glyphs"]) == 1

    def test_trigger_trap_glyph(self, controller_with_caster, low_level_caster):
        """Trigger a trap glyph."""
        controller, caster = controller_with_caster
        controller.add_character(low_level_caster)

        result = controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.TRAP,
            source_spell_id="serpent_glyph",
            name="Serpent Glyph",
            trap_effect="summon_adders",
            trap_damage="2d6",
        )
        glyph_id = result["glyph_id"]

        trigger_result = controller.trigger_trap_glyph(
            glyph_id=glyph_id,
            triggerer_id=low_level_caster.character_id,
        )

        assert trigger_result["triggered"] is True
        assert trigger_result["effect"] == "summon_adders"
        assert trigger_result["triggerer_id"] == low_level_caster.character_id

    def test_cast_knock(self, controller_with_caster, low_level_caster):
        """Cast Knock on a door with glyphs."""
        controller, caster = controller_with_caster
        controller.add_character(low_level_caster)

        # Place a sealing glyph (should be dispelled)
        controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.SEALING,
            source_spell_id="glyph_of_sealing",
            name="Glyph of Sealing",
        )

        # Place a locking glyph (should be disabled)
        controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.LOCKING,
            source_spell_id="glyph_of_locking",
            name="Glyph of Locking",
        )

        result = controller.cast_knock(
            caster_id=low_level_caster.character_id,
            target_id="door_001",
        )

        assert len(result["glyphs_dispelled"]) == 1
        assert result["glyphs_dispelled"][0]["name"] == "Glyph of Sealing"
        assert len(result["glyphs_disabled"]) == 1
        assert result["glyphs_disabled"][0]["name"] == "Glyph of Locking"


# =============================================================================
# SPELL PARSING TESTS
# =============================================================================


class TestGlyphSpellParsing:
    """Tests for parsing glyph spells."""

    def test_parse_glyph_of_sealing(self, resolver):
        """Parse Glyph of Sealing spell."""
        spell = make_spell(
            spell_id="glyph_of_sealing",
            name="Glyph of Sealing",
            level=1,
            magic_type=MagicType.ARCANE,
            description="""A glowing rune appears on a single closed door, gate, lid,
            or similar portal of the caster's choosing, magically preventing it from
            being opened. Opening by magic: A Knock spell opens the sealed portal
            instantly, dispelling the Glyph of Sealing. Opening by force: Creatures
            3 Levels or more above the caster can open the sealed portal with 1
            Round of effort.""",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        glyph_effects = [e for e in parsed.effects if e.is_glyph_effect]
        assert len(glyph_effects) >= 1

        effect = glyph_effects[0]
        assert effect.glyph_type == "sealing"
        assert effect.can_bypass_level_diff == 3

    def test_parse_glyph_of_locking(self, resolver):
        """Parse Glyph of Locking spell."""
        spell = make_spell(
            spell_id="glyph_of_locking",
            name="Glyph of Locking",
            level=2,
            magic_type=MagicType.ARCANE,
            description="""A glowing rune appears on a single closed door, gate, lid,
            or similar portal of the caster's choosing, magically locking it.
            Password: The caster may specify a password, allowing others to pass
            through the locked portal. Higher-Level casters: Arcane spell-casters
            3 or more Levels higher than the caster of the Glyph of Locking may
            pass through. Knock spells: Disable the Glyph of Locking for 1 Turn.""",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        glyph_effects = [e for e in parsed.effects if e.is_glyph_effect]
        assert len(glyph_effects) >= 1

        effect = glyph_effects[0]
        assert effect.glyph_type == "locking"
        assert effect.has_password is True
        assert effect.can_bypass_level_diff == 3

    def test_parse_knock(self, resolver):
        """Parse Knock spell."""
        spell = make_spell(
            spell_id="knock",
            name="Knock",
            level=2,
            magic_type=MagicType.ARCANE,
            description="""The caster knocks on a single closed door, gate, lid,
            or similar portal with their hand or a staff. The portal groans, grumbles,
            and magically opens. Locks and bars: Are unlocked or removed.
            Magical seals: Glyphs of Sealing are dispelled. Other magical seals
            (e.g. Glyphs of Locking) are disabled for 1 Turn.""",
            duration="Instant",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        unlock_effects = [e for e in parsed.effects if e.is_unlock_effect]
        assert len(unlock_effects) >= 1

        effect = unlock_effects[0]
        assert effect.dispels_sealing is True
        assert effect.disables_locking is True

    def test_parse_serpent_glyph(self, resolver):
        """Parse Serpent Glyph spell."""
        spell = make_spell(
            spell_id="serpent_glyph",
            name="Serpent Glyph",
            level=3,
            magic_type=MagicType.ARCANE,
            description="""The caster inscribes a serpent glyph onto an object or
            surface (up to 10' × 10' in size). Trigger: The glyph activates when
            touched by a creature other than the caster. Effect: 1d4+1 adders are
            summoned and attack the creature that triggered the glyph.""",
        )

        parsed = resolver.parse_mechanical_effects(spell)

        glyph_effects = [e for e in parsed.effects if e.is_glyph_effect]
        assert len(glyph_effects) >= 1

        effect = glyph_effects[0]
        assert effect.glyph_type == "trap"
        assert effect.is_trap_glyph is True
        assert effect.trap_trigger == "touch"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestGlyphIntegration:
    """Integration tests for the glyph system."""

    def test_full_glyph_workflow(self, controller_with_caster, high_level_caster):
        """Full workflow: place glyph, attempt bypass, cast knock."""
        controller, caster = controller_with_caster
        controller.add_character(high_level_caster)

        # 1. Place Glyph of Locking
        place_result = controller.place_glyph(
            caster_id=caster.character_id,
            target_id="door_001",
            glyph_type=GlyphType.LOCKING,
            source_spell_id="glyph_of_locking",
            name="Glyph of Locking",
            password="sesame",
            can_be_bypassed_by_level=3,
        )
        assert place_result["placed"] is True

        # 2. High-level caster should be able to bypass (level 10 vs. level 5+3=8)
        bypass_result = controller.check_glyph_bypass(
            target_id="door_001",
            character_id=high_level_caster.character_id,
        )
        assert bypass_result["can_bypass"] is True

        # 3. Cast Knock to disable it
        knock_result = controller.cast_knock(
            caster_id=caster.character_id,
            target_id="door_001",
        )
        assert len(knock_result["glyphs_disabled"]) == 1

        # 4. Glyph should now be temporarily disabled
        glyphs = controller.get_glyphs_on_target("door_001", active_only=True)
        assert len(glyphs) == 0  # No active glyphs (disabled)
