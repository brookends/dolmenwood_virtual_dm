"""
Tests for the Visibility State System.

Tests visibility states (VISIBLE, HIDDEN, INVISIBLE, REVEALED),
targeting penalties, and the break/reveal mechanics for invisibility.
"""

import pytest
from src.data_models import (
    VisibilityState,
    CharacterState,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def fighter():
    """Create a basic fighter character."""
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


# =============================================================================
# VISIBILITY STATE ENUM TESTS
# =============================================================================


class TestVisibilityStateEnum:
    """Tests for the VisibilityState enum."""

    def test_visible_is_detectable(self):
        """Visible state is detectable."""
        assert VisibilityState.VISIBLE.is_detectable is True

    def test_revealed_is_detectable(self):
        """Revealed state is detectable."""
        assert VisibilityState.REVEALED.is_detectable is True

    def test_invisible_not_detectable(self):
        """Invisible state is not detectable."""
        assert VisibilityState.INVISIBLE.is_detectable is False

    def test_hidden_not_detectable(self):
        """Hidden state is not detectable."""
        assert VisibilityState.HIDDEN.is_detectable is False

    def test_visible_no_targeting_penalty(self):
        """Visible targets have no targeting penalty."""
        assert VisibilityState.VISIBLE.targeting_penalty == 0

    def test_invisible_targeting_penalty(self):
        """Invisible targets have -4 targeting penalty."""
        assert VisibilityState.INVISIBLE.targeting_penalty == -4

    def test_hidden_targeting_penalty(self):
        """Hidden targets have -2 targeting penalty."""
        assert VisibilityState.HIDDEN.targeting_penalty == -2

    def test_revealed_targeting_penalty(self):
        """Revealed targets have -1 targeting penalty."""
        assert VisibilityState.REVEALED.targeting_penalty == -1


# =============================================================================
# CHARACTER VISIBILITY STATE TESTS
# =============================================================================


class TestCharacterVisibilityState:
    """Tests for CharacterState visibility tracking."""

    def test_default_visibility_is_visible(self, fighter):
        """Characters default to visible state."""
        assert fighter.visibility_state == VisibilityState.VISIBLE
        assert fighter.is_visible is True
        assert fighter.is_invisible is False
        assert fighter.is_hidden is False

    def test_make_invisible(self, fighter):
        """Test making a character invisible."""
        fighter.make_invisible("invisibility_spell_123")

        assert fighter.visibility_state == VisibilityState.INVISIBLE
        assert fighter.is_invisible is True
        assert fighter.is_visible is False
        assert fighter.invisibility_source == "invisibility_spell_123"

    def test_break_invisibility(self, fighter):
        """Test breaking invisibility on hostile action."""
        fighter.make_invisible("invisibility_spell_123")
        assert fighter.is_invisible is True

        result = fighter.break_invisibility("attacked enemy")

        assert result is True
        assert fighter.is_visible is True
        assert fighter.is_invisible is False
        assert fighter.invisibility_source is None

    def test_break_invisibility_when_not_invisible(self, fighter):
        """Breaking invisibility on visible character returns False."""
        result = fighter.break_invisibility("no reason")

        assert result is False
        assert fighter.is_visible is True

    def test_reveal_invisible(self, fighter):
        """Test revealing an invisible character (dust, mud, etc.)."""
        fighter.make_invisible("invisibility_spell_123")

        result = fighter.reveal_invisible("covered in dust")

        assert result is True
        assert fighter.visibility_state == VisibilityState.REVEALED
        assert fighter.is_invisible is False
        # Source preserved since magic is still active
        assert fighter.invisibility_source == "invisibility_spell_123"

    def test_hide(self, fighter):
        """Test hiding (non-magical concealment)."""
        fighter.hide()

        assert fighter.visibility_state == VisibilityState.HIDDEN
        assert fighter.is_hidden is True
        assert fighter.is_visible is False
        assert fighter.is_invisible is False

    def test_set_visibility_to_visible_clears_source(self, fighter):
        """Setting visibility to VISIBLE clears invisibility source."""
        fighter.make_invisible("spell_123")
        fighter.set_visibility(VisibilityState.VISIBLE)

        assert fighter.is_visible is True
        assert fighter.invisibility_source is None


# =============================================================================
# SEE INVISIBLE TESTS
# =============================================================================


class TestSeeInvisible:
    """Tests for the see invisible ability."""

    def test_default_cannot_see_invisible(self, fighter):
        """Characters cannot see invisible by default."""
        assert fighter.can_see_invisible is False
        assert fighter.see_invisible_source is None

    def test_grant_see_invisible(self, fighter):
        """Test granting see invisible ability."""
        fighter.grant_see_invisible("perceive_invisible_spell")

        assert fighter.can_see_invisible is True
        assert fighter.see_invisible_source == "perceive_invisible_spell"

    def test_remove_see_invisible(self, fighter):
        """Test removing see invisible ability."""
        fighter.grant_see_invisible("perceive_invisible_spell")
        fighter.remove_see_invisible()

        assert fighter.can_see_invisible is False
        assert fighter.see_invisible_source is None


# =============================================================================
# PERCEPTION AND TARGETING TESTS
# =============================================================================


class TestPerceptionAndTargeting:
    """Tests for can_perceive and targeting penalty calculations."""

    def test_can_perceive_visible_target(self, fighter, magic_user):
        """Can always perceive visible targets."""
        assert fighter.can_perceive(magic_user) is True

    def test_cannot_perceive_invisible_target(self, fighter, magic_user):
        """Cannot perceive invisible targets normally."""
        magic_user.make_invisible("spell")

        assert fighter.can_perceive(magic_user) is False

    def test_can_perceive_invisible_with_see_invisible(self, fighter, magic_user):
        """Can perceive invisible targets with see invisible ability."""
        magic_user.make_invisible("spell")
        fighter.grant_see_invisible("detection_spell")

        assert fighter.can_perceive(magic_user) is True

    def test_can_perceive_revealed_target(self, fighter, magic_user):
        """Can perceive revealed targets."""
        magic_user.make_invisible("spell")
        magic_user.reveal_invisible("dust cloud")

        assert fighter.can_perceive(magic_user) is True

    def test_cannot_perceive_hidden_target(self, fighter, magic_user):
        """Cannot perceive hidden targets without perception check."""
        magic_user.hide()

        assert fighter.can_perceive(magic_user) is False

    def test_targeting_penalty_visible(self, fighter, magic_user):
        """No penalty when targeting visible."""
        penalty = fighter.get_targeting_penalty_against(magic_user)
        assert penalty == 0

    def test_targeting_penalty_invisible(self, fighter, magic_user):
        """Heavy penalty when targeting invisible."""
        magic_user.make_invisible("spell")

        penalty = fighter.get_targeting_penalty_against(magic_user)
        assert penalty == -4

    def test_targeting_penalty_hidden(self, fighter, magic_user):
        """Moderate penalty when targeting hidden."""
        magic_user.hide()

        penalty = fighter.get_targeting_penalty_against(magic_user)
        assert penalty == -2

    def test_targeting_penalty_revealed(self, fighter, magic_user):
        """Minor penalty when targeting revealed."""
        magic_user.make_invisible("spell")
        magic_user.reveal_invisible("flour")

        penalty = fighter.get_targeting_penalty_against(magic_user)
        assert penalty == -1

    def test_targeting_invisible_with_see_invisible(self, fighter, magic_user):
        """No penalty for invisible targets if attacker can see invisible."""
        magic_user.make_invisible("spell")
        fighter.grant_see_invisible("true_sight")

        penalty = fighter.get_targeting_penalty_against(magic_user)
        assert penalty == 0


# =============================================================================
# GLOBAL CONTROLLER VISIBILITY TESTS
# =============================================================================


class TestGlobalControllerVisibility:
    """Tests for GlobalController visibility management."""

    @pytest.fixture
    def controller_with_character(self, fighter):
        """Create a controller with a registered character."""
        from src.game_state.global_controller import GlobalController

        controller = GlobalController()
        controller.add_character(fighter)
        return controller, fighter

    def test_make_invisible_via_controller(self, controller_with_character):
        """Test making character invisible through controller."""
        controller, fighter = controller_with_character

        result = controller.make_invisible(fighter.character_id, "invisibility_spell")

        assert "error" not in result
        assert result["visibility_state"] == "invisible"
        assert fighter.is_invisible is True

    def test_break_invisibility_via_controller(self, controller_with_character):
        """Test breaking invisibility through controller."""
        controller, fighter = controller_with_character
        controller.make_invisible(fighter.character_id, "spell")

        result = controller.break_invisibility(fighter.character_id, "attacked enemy")

        assert "error" not in result
        assert result["was_invisible"] is True
        assert fighter.is_visible is True

    def test_grant_see_invisible_via_controller(self, controller_with_character):
        """Test granting see invisible through controller."""
        controller, fighter = controller_with_character

        result = controller.grant_see_invisible(fighter.character_id, "perceive_invisible")

        assert "error" not in result
        assert result["can_see_invisible"] is True
        assert fighter.can_see_invisible is True

    def test_remove_see_invisible_via_controller(self, controller_with_character):
        """Test removing see invisible through controller."""
        controller, fighter = controller_with_character
        controller.grant_see_invisible(fighter.character_id, "perceive_invisible")

        result = controller.remove_see_invisible(fighter.character_id)

        assert "error" not in result
        assert result["can_see_invisible"] is False
        assert fighter.can_see_invisible is False

    def test_visibility_operations_on_missing_character(self):
        """Test visibility operations on non-existent character."""
        from src.game_state.global_controller import GlobalController

        controller = GlobalController()

        assert "error" in controller.make_invisible("missing", "spell")
        assert "error" in controller.break_invisibility("missing", "reason")
        assert "error" in controller.grant_see_invisible("missing", "spell")
        assert "error" in controller.remove_see_invisible("missing")
