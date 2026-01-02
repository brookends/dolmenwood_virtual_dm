"""
Tests for faction oracle integration.

Tests the Mythic GME oracle integration with the faction system:
- DiceRngAdapter for deterministic MythicGME
- FactionOracle with state and event types
- Complication random events in faction turns
- Contested territory oracle adjudication
- Party work extreme roll twists
"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_models import DiceRoller
from src.oracle.dice_rng_adapter import DiceRngAdapter
from src.oracle.mythic_gme import Likelihood
from src.factions.faction_oracle import (
    FactionOracle,
    FactionOracleConfig,
    FactionOracleState,
    OracleEvent,
    OracleEventKind,
    create_faction_oracle,
)
from src.factions.faction_models import (
    FactionDefinition,
    FactionRules,
    FactionTurnState,
    PartyFactionState,
    ActionTemplate,
    Territory,
)
from src.factions.faction_engine import FactionEngine


# =============================================================================
# DiceRngAdapter Tests
# =============================================================================


class TestDiceRngAdapter:
    """Tests for DiceRngAdapter."""

    def test_randint_calls_dice_roller(self):
        """Test that randint calls DiceRoller.randint."""
        mock_roller = MagicMock()
        mock_roller.randint.return_value = 42

        adapter = DiceRngAdapter(reason_prefix="Test", dice_roller=mock_roller)
        result = adapter.randint(1, 100)

        assert result == 42
        mock_roller.randint.assert_called_once()
        call_args = mock_roller.randint.call_args
        assert call_args[0][0] == 1  # a
        assert call_args[0][1] == 100  # b
        assert "d100" in call_args[0][2]  # reason contains d100

    def test_choice_calls_dice_roller(self):
        """Test that choice calls DiceRoller.choice."""
        mock_roller = MagicMock()
        mock_roller.choice.return_value = "selected"

        adapter = DiceRngAdapter(reason_prefix="Test", dice_roller=mock_roller)
        result = adapter.choice(["a", "b", "c"])

        assert result == "selected"
        mock_roller.choice.assert_called_once()

    def test_choice_empty_sequence_raises(self):
        """Test that choice raises IndexError for empty sequence."""
        adapter = DiceRngAdapter()
        with pytest.raises(IndexError, match="Cannot choose from an empty sequence"):
            adapter.choice([])

    def test_roll_count_increments(self):
        """Test that roll count increments with each call."""
        mock_roller = MagicMock()
        mock_roller.randint.return_value = 50
        mock_roller.choice.return_value = "x"

        adapter = DiceRngAdapter(dice_roller=mock_roller)
        assert adapter.roll_count == 0

        adapter.randint(1, 100)
        assert adapter.roll_count == 1

        adapter.choice(["a", "b"])
        assert adapter.roll_count == 2

        adapter.reset_count()
        assert adapter.roll_count == 0

    def test_deterministic_with_mocked_roller(self):
        """Test that adapter produces deterministic results with consistent roller."""
        # Use mocks to simulate deterministic behavior
        mock_roller = MagicMock()
        mock_roller.randint.side_effect = [10, 20, 30, 40, 50]

        adapter = DiceRngAdapter(dice_roller=mock_roller)

        results = [adapter.randint(1, 100) for _ in range(5)]

        assert results == [10, 20, 30, 40, 50]
        assert mock_roller.randint.call_count == 5


# =============================================================================
# FactionOracleConfig Tests
# =============================================================================


class TestFactionOracleConfig:
    """Tests for FactionOracleConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = FactionOracleConfig()
        assert config.enabled is True
        assert config.default_chaos_factor == 5
        assert config.auto_random_event_on_complication is True
        assert config.contested_territory_enabled is True
        assert config.party_work_twists_enabled is True
        assert config.party_work_twist_on_extremes is True

    def test_from_dict_empty(self):
        """Test from_dict with empty/None data."""
        config = FactionOracleConfig.from_dict(None)
        assert config.enabled is True

        config = FactionOracleConfig.from_dict({})
        assert config.enabled is True

    def test_from_dict_with_values(self):
        """Test from_dict with actual values."""
        data = {
            "enabled": False,
            "default_chaos_factor": 7,
            "auto_random_event_on_complication": False,
            "contested_territory": {"enabled": False},
            "party_work_twists": {"enabled": True, "on_extremes": False},
        }

        config = FactionOracleConfig.from_dict(data)
        assert config.enabled is False
        assert config.default_chaos_factor == 7
        assert config.auto_random_event_on_complication is False
        assert config.contested_territory_enabled is False
        assert config.party_work_twists_enabled is True
        assert config.party_work_twist_on_extremes is False


# =============================================================================
# OracleEvent Tests
# =============================================================================


class TestOracleEvent:
    """Tests for OracleEvent dataclass."""

    def test_meaning_pair(self):
        """Test meaning_pair property."""
        event = OracleEvent(
            kind=OracleEventKind.RANDOM_EVENT,
            date="1420-05-15",
            tag="test",
            action="Pursue",
            subject="Knowledge",
        )
        assert event.meaning_pair == "Pursue Knowledge"

    def test_meaning_pair_empty(self):
        """Test meaning_pair when action/subject missing."""
        event = OracleEvent(
            kind=OracleEventKind.FATE_CHECK,
            date="1420-05-15",
            tag="test",
        )
        assert event.meaning_pair == ""

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        event = OracleEvent(
            kind=OracleEventKind.RANDOM_EVENT,
            date="1420-05-15",
            tag="action_complication",
            faction_id="nag_lord",
            focus="npc_action",
            action="Pursue",
            subject="Knowledge",
            chaos_factor=6,
        )

        data = event.to_dict()
        restored = OracleEvent.from_dict(data)

        assert restored.kind == event.kind
        assert restored.date == event.date
        assert restored.tag == event.tag
        assert restored.faction_id == event.faction_id
        assert restored.focus == event.focus
        assert restored.action == event.action
        assert restored.subject == event.subject
        assert restored.chaos_factor == event.chaos_factor

    def test_as_rumor_text_random_event(self):
        """Test rumor text for random event."""
        event = OracleEvent(
            kind=OracleEventKind.RANDOM_EVENT,
            date="1420-05-15",
            tag="test",
            focus="npc_action",
            action="Pursue",
            subject="Knowledge",
        )
        text = event.as_rumor_text()
        assert "Npc Action" in text
        assert "Pursue Knowledge" in text

    def test_as_rumor_text_fate_check(self):
        """Test rumor text for fate check."""
        event = OracleEvent(
            kind=OracleEventKind.FATE_CHECK,
            date="1420-05-15",
            tag="contested_territory",
            question="Does faction A claim hex?",
            result="yes",
        )
        text = event.as_rumor_text()
        assert "Yes" in text
        assert "contested_territory" in text


# =============================================================================
# FactionOracle Tests
# =============================================================================


class TestFactionOracle:
    """Tests for FactionOracle."""

    def test_default_chaos_factor(self):
        """Test default chaos factor initialization."""
        oracle = FactionOracle()
        assert oracle.chaos_factor == 5

    def test_custom_chaos_factor(self):
        """Test custom chaos factor via config."""
        config = FactionOracleConfig(default_chaos_factor=7)
        oracle = FactionOracle(config=config)
        assert oracle.chaos_factor == 7

    def test_set_chaos_factor(self):
        """Test setting chaos factor."""
        oracle = FactionOracle()
        new_value = oracle.set_chaos_factor(3, "test reason")
        assert new_value == 3
        assert oracle.chaos_factor == 3
        assert oracle.state.chaos_factor == 3

    def test_increase_decrease_chaos(self):
        """Test increasing and decreasing chaos."""
        oracle = FactionOracle()

        oracle.increase_chaos("went poorly")
        assert oracle.chaos_factor == 6

        oracle.decrease_chaos("went well")
        assert oracle.chaos_factor == 5

    def test_random_event_disabled(self):
        """Test random_event when oracle is disabled."""
        config = FactionOracleConfig(enabled=False)
        oracle = FactionOracle(config=config)

        event = oracle.random_event(date="1420-05-15", faction_id="test")

        assert event.kind == OracleEventKind.RANDOM_EVENT
        assert event.focus == "disabled"
        assert event.action == "oracle"
        assert event.subject == "disabled"

    def test_random_event_generates_event(self):
        """Test random_event generates proper event."""
        oracle = FactionOracle()
        event = oracle.random_event(
            date="1420-05-15",
            faction_id="nag_lord",
            tag="action_complication",
        )

        assert event.kind == OracleEventKind.RANDOM_EVENT
        assert event.date == "1420-05-15"
        assert event.faction_id == "nag_lord"
        assert event.tag == "action_complication"
        assert event.focus is not None
        assert event.action is not None
        assert event.subject is not None

    def test_detail_check_generates_event(self):
        """Test detail_check generates event with meaning pair."""
        oracle = FactionOracle()
        event = oracle.detail_check(
            date="1420-05-15",
            faction_id="test",
            tag="party_work_twist",
        )

        assert event.kind == OracleEventKind.DETAIL_CHECK
        assert event.action is not None
        assert event.subject is not None
        assert event.meaning_pair != ""

    def test_fate_check_generates_event(self):
        """Test fate_check generates proper event."""
        oracle = FactionOracle()
        event = oracle.fate_check(
            question="Does faction A succeed?",
            likelihood=Likelihood.FIFTY_FIFTY,
            date="1420-05-15",
            faction_id="faction_a",
            tag="contested_territory",
        )

        assert event.kind == OracleEventKind.FATE_CHECK
        assert event.question == "Does faction A succeed?"
        assert event.result in ("yes", "no", "exceptional_yes", "exceptional_no")
        assert event.likelihood == "FIFTY_FIFTY"
        assert event.roll is not None

    def test_fate_check_result_helpers(self):
        """Test is_yes, is_exceptional helpers."""
        oracle = FactionOracle()

        # Create events for each result type
        yes_event = OracleEvent(
            kind=OracleEventKind.FATE_CHECK,
            date="test",
            tag="test",
            result="yes",
        )
        no_event = OracleEvent(
            kind=OracleEventKind.FATE_CHECK,
            date="test",
            tag="test",
            result="no",
        )
        exc_yes_event = OracleEvent(
            kind=OracleEventKind.FATE_CHECK,
            date="test",
            tag="test",
            result="exceptional_yes",
        )
        exc_no_event = OracleEvent(
            kind=OracleEventKind.FATE_CHECK,
            date="test",
            tag="test",
            result="exceptional_no",
        )

        assert oracle.is_yes(yes_event) is True
        assert oracle.is_yes(no_event) is False
        assert oracle.is_yes(exc_yes_event) is True
        assert oracle.is_yes(exc_no_event) is False

        assert oracle.is_exceptional(yes_event) is False
        assert oracle.is_exceptional(exc_yes_event) is True
        assert oracle.is_exceptional(exc_no_event) is True

    def test_determine_contest_likelihood_equal_factions(self):
        """Test likelihood for equal factions with neutral relationship."""
        oracle = FactionOracle()
        likelihood = oracle.determine_contest_likelihood(
            attacker_level=2,
            defender_level=2,
            relationship_score=0,
        )
        assert likelihood == Likelihood.FIFTY_FIFTY

    def test_determine_contest_likelihood_stronger_attacker(self):
        """Test likelihood for stronger attacker."""
        oracle = FactionOracle()
        likelihood = oracle.determine_contest_likelihood(
            attacker_level=4,
            defender_level=2,
            relationship_score=0,
        )
        # +2 level diff -> LIKELY
        assert likelihood == Likelihood.LIKELY

    def test_determine_contest_likelihood_hostile_relationship(self):
        """Test likelihood with hostile relationship (easier to attack)."""
        oracle = FactionOracle()
        likelihood = oracle.determine_contest_likelihood(
            attacker_level=2,
            defender_level=2,
            relationship_score=-100,  # Very hostile
        )
        # Hostile relationship makes attack easier
        assert likelihood in (Likelihood.LIKELY, Likelihood.VERY_LIKELY)

    def test_determine_contest_likelihood_allied_relationship(self):
        """Test likelihood with allied relationship (harder to attack)."""
        oracle = FactionOracle()
        likelihood = oracle.determine_contest_likelihood(
            attacker_level=2,
            defender_level=2,
            relationship_score=100,  # Very allied
        )
        # Allied relationship makes attack harder
        assert likelihood in (Likelihood.UNLIKELY, Likelihood.VERY_UNLIKELY)

    def test_session_events_tracking(self):
        """Test that events are tracked in session."""
        oracle = FactionOracle()

        assert len(oracle.get_session_events()) == 0

        oracle.random_event(date="test", tag="test")
        oracle.detail_check(date="test", tag="test")

        events = oracle.get_session_events()
        assert len(events) == 2

        oracle.clear_session_events()
        assert len(oracle.get_session_events()) == 0

    def test_cycle_counter(self):
        """Test cycle event counter."""
        oracle = FactionOracle()

        assert oracle.state.events_this_cycle == 0

        oracle.random_event(date="test", tag="test")
        assert oracle.state.events_this_cycle == 1
        assert oracle.state.total_events == 1

        oracle.reset_cycle_counter()
        assert oracle.state.events_this_cycle == 0
        assert oracle.state.total_events == 1

    def test_serialization(self):
        """Test oracle state serialization."""
        oracle = FactionOracle()
        oracle.set_chaos_factor(7, "test")
        oracle.random_event(date="test", tag="test")

        data = oracle.to_dict()

        # Create new oracle and restore
        oracle2 = FactionOracle()
        oracle2.from_dict(data)

        assert oracle2.chaos_factor == 7
        assert oracle2.state.total_events == 1


# =============================================================================
# Complication Oracle Event Integration Tests
# =============================================================================


class TestComplicationOracleIntegration:
    """Tests for oracle events on faction action complications."""

    @pytest.fixture
    def faction_with_oracle(self):
        """Create faction engine with oracle enabled."""
        rules = FactionRules(
            schema_version=1,
            complication_on_rolls=(1,),
        )
        definition = FactionDefinition(
            faction_id="test_faction",
            name="Test Faction",
            action_library=[
                ActionTemplate(
                    action_id="test_action",
                    name="Test Action",
                    scope="mission",
                ),
            ],
            starting_actions=["test_action"],
        )

        oracle = FactionOracle()
        engine = FactionEngine(
            rules=rules,
            definitions={"test_faction": definition},
            oracle=oracle,
        )
        engine.set_current_date("1420-05-15")
        return engine

    def test_complication_triggers_oracle_event(self, faction_with_oracle):
        """Test that roll of 1 triggers oracle random event."""
        engine = faction_with_oracle

        # Mock the dice roller to return 1 (complication)
        with patch.object(DiceRoller, 'roll_d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=1)
            result = engine.run_cycle()

        # Check that oracle event was generated
        action_result = result.faction_results[0].actions[0]
        assert action_result.complication is True
        assert action_result.oracle_event is not None
        assert action_result.oracle_event.kind == OracleEventKind.RANDOM_EVENT
        assert action_result.oracle_event.tag == "action_complication"
        assert action_result.oracle_event.faction_id == "test_faction"

        # Check that oracle event was collected in cycle result
        assert len(result.oracle_events) == 1
        assert result.oracle_events[0] == action_result.oracle_event

    def test_no_complication_no_oracle_event(self, faction_with_oracle):
        """Test that non-complication rolls don't trigger oracle events."""
        engine = faction_with_oracle

        # Mock the dice roller to return 4 (no complication)
        with patch.object(DiceRoller, 'roll_d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=4)
            result = engine.run_cycle()

        action_result = result.faction_results[0].actions[0]
        assert action_result.complication is False
        assert action_result.oracle_event is None
        assert len(result.oracle_events) == 0

    def test_disabled_oracle_no_event_on_complication(self):
        """Test that disabled oracle doesn't generate events."""
        rules = FactionRules(
            schema_version=1,
            complication_on_rolls=(1,),
        )
        definition = FactionDefinition(
            faction_id="test_faction",
            name="Test Faction",
            action_library=[
                ActionTemplate(action_id="test_action", name="Test", scope="task"),
            ],
            starting_actions=["test_action"],
        )

        config = FactionOracleConfig(auto_random_event_on_complication=False)
        oracle = FactionOracle(config=config)
        engine = FactionEngine(
            rules=rules,
            definitions={"test_faction": definition},
            oracle=oracle,
        )

        with patch.object(DiceRoller, 'roll_d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=1)
            result = engine.run_cycle()

        action_result = result.faction_results[0].actions[0]
        assert action_result.complication is True
        assert action_result.oracle_event is None


# =============================================================================
# Contested Territory Oracle Integration Tests
# =============================================================================


class TestContestedTerritoryOracle:
    """Tests for oracle adjudication of contested territory."""

    @pytest.fixture
    def two_faction_engine(self):
        """Create engine with two factions, one holding territory."""
        rules = FactionRules(schema_version=1)

        attacker = FactionDefinition(
            faction_id="attacker",
            name="Attacker Faction",
            action_library=[],
        )
        defender = FactionDefinition(
            faction_id="defender",
            name="Defender Faction",
            action_library=[],
        )

        oracle = FactionOracle()
        engine = FactionEngine(
            rules=rules,
            definitions={"attacker": attacker, "defender": defender},
            oracle=oracle,
        )

        # Give defender some territory
        engine.faction_states["defender"].territory.hexes.add("0604")
        engine.faction_states["defender"].territory.settlements.add("prigwort")

        engine.set_current_date("1420-05-15")
        return engine

    def test_uncontested_claim_succeeds(self, two_faction_engine):
        """Test that uncontested territory claim always succeeds."""
        engine = two_faction_engine
        attacker_state = engine.faction_states["attacker"]

        from src.factions.faction_effects import FactionEffectsInterpreter
        from src.factions.faction_models import EffectCommand

        effects = FactionEffectsInterpreter()
        effect = EffectCommand(type="claim_territory", data={"hex": "1001"})

        context = {
            "date": "1420-05-15",
            "faction_id": "attacker",
            "oracle": engine.oracle,
            "all_faction_states": engine.faction_states,
            "rules": engine.rules,
        }

        result = effects.apply_effect(effect, attacker_state, None, context)

        assert result.success is True
        assert "1001" in attacker_state.territory.hexes
        assert "oracle_events" not in result.changes  # No contest

    def test_contested_claim_uses_oracle(self, two_faction_engine):
        """Test that contested territory claim uses oracle."""
        engine = two_faction_engine
        attacker_state = engine.faction_states["attacker"]

        from src.factions.faction_effects import FactionEffectsInterpreter
        from src.factions.faction_models import EffectCommand

        effects = FactionEffectsInterpreter()
        # Try to claim hex 0604 which defender holds
        effect = EffectCommand(type="claim_territory", data={"hex": "0604"})

        context = {
            "date": "1420-05-15",
            "faction_id": "attacker",
            "oracle": engine.oracle,
            "all_faction_states": engine.faction_states,
            "rules": engine.rules,
        }

        result = effects.apply_effect(effect, attacker_state, None, context)

        # Oracle was used
        assert result.success is True
        assert "oracle_events" in result.changes
        assert len(result.changes["oracle_events"]) == 1

        oracle_event = result.changes["oracle_events"][0]
        assert oracle_event["kind"] == "fate_check"
        assert oracle_event["tag"] == "contested_territory"

    def test_contested_claim_winner_gets_territory(self, two_faction_engine):
        """Test that contest winner gets territory."""
        engine = two_faction_engine
        attacker_state = engine.faction_states["attacker"]
        defender_state = engine.faction_states["defender"]

        from src.factions.faction_effects import FactionEffectsInterpreter
        from src.factions.faction_models import EffectCommand

        effects = FactionEffectsInterpreter()
        effect = EffectCommand(type="claim_territory", data={"hex": "0604"})

        # Force oracle to return yes (attacker wins)
        with patch.object(engine.oracle, 'fate_check') as mock_fate:
            mock_event = OracleEvent(
                kind=OracleEventKind.FATE_CHECK,
                date="1420-05-15",
                tag="contested_territory",
                result="yes",
            )
            mock_fate.return_value = mock_event

            context = {
                "date": "1420-05-15",
                "faction_id": "attacker",
                "oracle": engine.oracle,
                "all_faction_states": engine.faction_states,
                "rules": engine.rules,
            }

            result = effects.apply_effect(effect, attacker_state, None, context)

        # Attacker got the hex
        assert "0604" in attacker_state.territory.hexes
        # Defender lost the hex
        assert "0604" not in defender_state.territory.hexes

    def test_contested_claim_loser_keeps_territory(self, two_faction_engine):
        """Test that contest loser keeps territory when attacker loses."""
        engine = two_faction_engine
        attacker_state = engine.faction_states["attacker"]
        defender_state = engine.faction_states["defender"]

        from src.factions.faction_effects import FactionEffectsInterpreter
        from src.factions.faction_models import EffectCommand

        effects = FactionEffectsInterpreter()
        effect = EffectCommand(type="claim_territory", data={"hex": "0604"})

        # Force oracle to return no (defender wins)
        with patch.object(engine.oracle, 'fate_check') as mock_fate:
            mock_event = OracleEvent(
                kind=OracleEventKind.FATE_CHECK,
                date="1420-05-15",
                tag="contested_territory",
                result="no",
            )
            mock_fate.return_value = mock_event

            context = {
                "date": "1420-05-15",
                "faction_id": "attacker",
                "oracle": engine.oracle,
                "all_faction_states": engine.faction_states,
                "rules": engine.rules,
            }

            result = effects.apply_effect(effect, attacker_state, None, context)

        # Attacker didn't get the hex
        assert "0604" not in attacker_state.territory.hexes
        # Defender kept the hex
        assert "0604" in defender_state.territory.hexes
        # Description mentions failure
        assert "failed to claim" in result.description


# =============================================================================
# Party Work Oracle Twist Tests
# =============================================================================


class TestPartyWorkOracleTwists:
    """Tests for oracle twists on party faction work."""

    @pytest.fixture
    def party_manager_with_oracle(self):
        """Create party manager with oracle enabled."""
        from src.factions.faction_party import FactionPartyManager

        rules = FactionRules(schema_version=1)
        definition = FactionDefinition(
            faction_id="test_faction",
            name="Test Faction",
        )

        oracle = FactionOracle()
        engine = FactionEngine(
            rules=rules,
            definitions={"test_faction": definition},
            oracle=oracle,
        )
        engine.set_party_state(PartyFactionState())

        return FactionPartyManager(engine)

    def test_normal_roll_no_twist(self, party_manager_with_oracle):
        """Test that normal rolls don't generate oracle twists."""
        manager = party_manager_with_oracle

        # Mock roll to return 7 (normal, not extreme)
        with patch.object(DiceRoller, 'roll_2d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=7)
            result = manager.perform_faction_work("test_faction", days=3)

        assert result.roll_total == 7
        assert result.oracle_twist is None

    def test_roll_12_generates_exceptional_twist(self, party_manager_with_oracle):
        """Test that roll of 12 generates exceptional oracle twist."""
        manager = party_manager_with_oracle

        with patch.object(DiceRoller, 'roll_2d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=12)
            result = manager.perform_faction_work(
                "test_faction", days=3, current_date="1420-05-15"
            )

        assert result.roll_total == 12
        assert result.oracle_twist is not None
        assert result.oracle_twist.tag == "party_work_exceptional"
        assert result.success is True  # 12 always succeeds

    def test_roll_2_generates_catastrophe_twist(self, party_manager_with_oracle):
        """Test that roll of 2 generates catastrophe oracle twist."""
        manager = party_manager_with_oracle

        with patch.object(DiceRoller, 'roll_2d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=2)
            result = manager.perform_faction_work(
                "test_faction", days=3, current_date="1420-05-15"
            )

        assert result.roll_total == 2
        assert result.oracle_twist is not None
        assert result.oracle_twist.tag == "party_work_catastrophe"
        assert result.success is False  # 2 always fails

    def test_roll_2_extra_penalty(self, party_manager_with_oracle):
        """Test that roll of 2 gives extra standing penalty."""
        manager = party_manager_with_oracle

        initial_standing = manager.get_standing("test_faction")

        with patch.object(DiceRoller, 'roll_2d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=2)
            result = manager.perform_faction_work("test_faction", days=3)

        # Standing should decrease by more than 1 (base penalty + catastrophe)
        final_standing = manager.get_standing("test_faction")
        assert result.standing_delta <= -2  # At least -2 penalty

    def test_roll_12_extra_bonus(self, party_manager_with_oracle):
        """Test that roll of 12 gives extra standing bonus."""
        manager = party_manager_with_oracle

        with patch.object(DiceRoller, 'roll_2d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=12)
            result = manager.perform_faction_work("test_faction", days=3)

        # Standing should increase by more than normal success
        assert result.standing_delta >= 2  # Base + exceptional bonus

    def test_disabled_twists_no_oracle_event(self):
        """Test that disabled twists don't generate oracle events."""
        from src.factions.faction_party import FactionPartyManager

        rules = FactionRules(schema_version=1)
        definition = FactionDefinition(
            faction_id="test_faction",
            name="Test Faction",
        )

        config = FactionOracleConfig(party_work_twists_enabled=False)
        oracle = FactionOracle(config=config)
        engine = FactionEngine(
            rules=rules,
            definitions={"test_faction": definition},
            oracle=oracle,
        )
        engine.set_party_state(PartyFactionState())

        manager = FactionPartyManager(engine)

        with patch.object(DiceRoller, 'roll_2d6') as mock_roll:
            mock_roll.return_value = MagicMock(total=12)
            result = manager.perform_faction_work("test_faction", days=3)

        assert result.roll_total == 12
        assert result.oracle_twist is None  # Disabled


# =============================================================================
# Oracle Persistence Tests
# =============================================================================


class TestOraclePersistence:
    """Tests for oracle state persistence through engine."""

    def test_oracle_state_persisted_in_engine(self):
        """Test that oracle state is saved with engine state."""
        rules = FactionRules(schema_version=1)
        definition = FactionDefinition(faction_id="test", name="Test")

        oracle = FactionOracle()
        oracle.set_chaos_factor(7, "test")
        oracle.random_event(date="test", tag="test")

        engine = FactionEngine(
            rules=rules,
            definitions={"test": definition},
            oracle=oracle,
        )

        # Serialize
        data = engine.to_dict()

        assert "oracle_state" in data
        assert data["oracle_state"]["state"]["chaos_factor"] == 7
        assert data["oracle_state"]["state"]["total_events"] == 1

    def test_oracle_state_restored_from_engine(self):
        """Test that oracle state is restored when loading engine state."""
        rules = FactionRules(schema_version=1)
        definition = FactionDefinition(faction_id="test", name="Test")

        # Create initial engine with oracle events
        oracle1 = FactionOracle()
        oracle1.set_chaos_factor(8, "test")
        engine1 = FactionEngine(
            rules=rules,
            definitions={"test": definition},
            oracle=oracle1,
        )

        data = engine1.to_dict()

        # Create new engine and restore
        oracle2 = FactionOracle()  # Fresh oracle with default chaos
        engine2 = FactionEngine(
            rules=rules,
            definitions={"test": definition},
            oracle=oracle2,
        )
        engine2.from_dict(data)

        # Oracle state should be restored
        assert oracle2.chaos_factor == 8


# =============================================================================
# create_faction_oracle Helper Tests
# =============================================================================


class TestCreateFactionOracle:
    """Tests for create_faction_oracle helper function."""

    def test_create_with_defaults(self):
        """Test creating oracle with default config."""
        oracle = create_faction_oracle()
        assert oracle.config.enabled is True
        assert oracle.chaos_factor == 5

    def test_create_with_config(self):
        """Test creating oracle with custom config."""
        config_data = {
            "enabled": True,
            "default_chaos_factor": 7,
        }
        oracle = create_faction_oracle(config_data=config_data)
        assert oracle.chaos_factor == 7

    def test_create_with_state(self):
        """Test creating oracle with persisted state."""
        state_data = {
            "chaos_factor": 3,
            "events_this_cycle": 5,
            "total_events": 42,
        }
        oracle = create_faction_oracle(state_data=state_data)

        assert oracle.state.chaos_factor == 3
        assert oracle.state.events_this_cycle == 5
        assert oracle.state.total_events == 42
