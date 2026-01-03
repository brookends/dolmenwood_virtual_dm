"""
Tests for combat aura effects.

These tests verify that creatures with auras (like Cold Aura)
deal automatic damage to nearby enemies at the start of each round.
"""

import pytest
from unittest.mock import MagicMock


class TestCombatAuraDataclass:
    """Tests for the CombatAura dataclass."""

    def test_parse_cold_aura(self):
        """Verify parsing of cold aura from special ability text."""
        from src.data_models import CombatAura, AuraType

        ability = "Cold Aura (creatures within 10 feet take 1 cold damage per round)"
        aura = CombatAura.parse_from_special_ability(ability)

        assert aura is not None
        assert aura.aura_type == AuraType.COLD
        assert aura.radius_feet == 10
        assert aura.damage_per_round == 1
        assert aura.damage_type == "cold"

    def test_parse_fire_aura(self):
        """Verify parsing of fire aura."""
        from src.data_models import CombatAura, AuraType

        ability = "Fire Aura (10ft radius, creatures take 2 fire damage)"
        aura = CombatAura.parse_from_special_ability(ability)

        assert aura is not None
        assert aura.aura_type == AuraType.FIRE
        assert aura.radius_feet == 10
        assert aura.damage_per_round == 2
        assert aura.damage_type == "fire"

    def test_parse_aura_with_dice_damage(self):
        """Verify parsing of aura with dice damage (uses average)."""
        from src.data_models import CombatAura

        ability = "Poison Aura (within 5 feet take 1d4 poison damage)"
        aura = CombatAura.parse_from_special_ability(ability)

        assert aura is not None
        assert aura.radius_feet == 5
        # 1d4 average = 2.5, rounded down = 2
        assert aura.damage_per_round == 2

    def test_parse_non_aura_ability(self):
        """Verify non-aura abilities return None."""
        from src.data_models import CombatAura

        ability = "Flight (60ft)"
        aura = CombatAura.parse_from_special_ability(ability)

        assert aura is None

    def test_parse_aura_with_save(self):
        """Verify parsing of aura with save requirement."""
        from src.data_models import CombatAura

        ability = "Fear Aura (10ft, Save vs Spell or frightened)"
        aura = CombatAura.parse_from_special_ability(ability)

        assert aura is not None
        assert aura.save_type == "spell"


class TestAuraTypeEnum:
    """Tests for AuraType enum."""

    def test_all_types_exist(self):
        """Verify all expected aura types exist."""
        from src.data_models import AuraType

        assert AuraType.COLD.value == "cold"
        assert AuraType.FIRE.value == "fire"
        assert AuraType.LIGHTNING.value == "lightning"
        assert AuraType.POISON.value == "poison"
        assert AuraType.FEAR.value == "fear"
        assert AuraType.CHARM.value == "charm"


class TestCombatEngineAuraProcessing:
    """Tests for combat engine aura processing."""

    def _create_mock_combat_state(
        self,
        enemy_abilities: list[str] = None,
        party_hp: int = 20,
        enemy_hp: int = 50,
    ):
        """Create a mock combat state for testing."""
        from src.data_models import (
            EncounterState,
            Combatant,
            StatBlock,
            EncounterType,
            SurpriseStatus,
        )
        from src.combat.combat_engine import CombatState

        # Create party combatant
        party_stat_block = StatBlock(
            armor_class=14,
            hit_dice="1d8",
            hp_current=party_hp,
            hp_max=party_hp,
            movement=30,
            attacks=[{"name": "Sword", "damage": "1d8", "bonus": 1}],
            morale=10,
            special_abilities=[],
        )

        party_combatant = Combatant(
            combatant_id="fighter1",
            name="Fighter",
            side="party",
            stat_block=party_stat_block,
        )

        # Create enemy combatant with aura
        enemy_stat_block = StatBlock(
            armor_class=16,
            hit_dice="8d8",
            hp_current=enemy_hp,
            hp_max=enemy_hp,
            movement=40,
            attacks=[{"name": "Claw", "damage": "2d6", "bonus": 3}],
            morale=9,
            special_abilities=enemy_abilities or [],
        )

        enemy_combatant = Combatant(
            combatant_id="frore_gryphus",
            name="Frore Gryphus",
            side="enemy",
            stat_block=enemy_stat_block,
        )

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            combatants=[party_combatant, enemy_combatant],
        )

        combat_state = CombatState(
            encounter=encounter,
            enemy_starting_count=1,
        )

        return combat_state

    def test_cold_aura_deals_damage(self):
        """Verify cold aura deals damage to party members."""
        from src.combat.combat_engine import CombatEngine

        controller = MagicMock()
        engine = CombatEngine(controller)

        # Set up combat with cold aura enemy
        engine._combat_state = self._create_mock_combat_state(
            enemy_abilities=[
                "Cold Aura (creatures within 10 feet take 1 cold damage per round)"
            ],
            party_hp=20,
        )

        # Process aura damage
        messages = engine._process_aura_damage()

        # Verify damage was dealt
        assert len(messages) > 0
        assert "cold aura" in messages[0].lower()
        assert "1" in messages[0]

        # Check HP was reduced
        party_combatant = engine._combat_state.encounter.combatants[0]
        assert party_combatant.stat_block.hp_current == 19  # 20 - 1

    def test_aura_targets_enemies_only(self):
        """Verify aura only targets enemies, not allies."""
        from src.combat.combat_engine import CombatEngine
        from src.data_models import Combatant, StatBlock

        controller = MagicMock()
        engine = CombatEngine(controller)

        engine._combat_state = self._create_mock_combat_state(
            enemy_abilities=[
                "Cold Aura (creatures within 10 feet take 1 cold damage per round)"
            ],
            enemy_hp=50,
        )

        # Add another enemy (should not be damaged by ally's aura)
        ally_stat_block = StatBlock(
            armor_class=12,
            hit_dice="2d8",
            hp_current=10,
            hp_max=10,
            movement=30,
            attacks=[],
            morale=7,
            special_abilities=[],
        )
        ally = Combatant(
            combatant_id="gryphling1",
            name="Gryphling",
            side="enemy",  # Same side as aura source
            stat_block=ally_stat_block,
        )
        engine._combat_state.encounter.combatants.append(ally)

        # Process aura damage
        engine._process_aura_damage()

        # Ally should not be damaged
        assert ally.stat_block.hp_current == 10

    def test_dead_combatants_dont_have_auras(self):
        """Verify dead combatants don't emit aura damage."""
        from src.combat.combat_engine import CombatEngine

        controller = MagicMock()
        engine = CombatEngine(controller)

        engine._combat_state = self._create_mock_combat_state(
            enemy_abilities=[
                "Cold Aura (creatures within 10 feet take 1 cold damage per round)"
            ],
            party_hp=20,
            enemy_hp=0,  # Enemy is dead
        )

        # Process aura damage
        messages = engine._process_aura_damage()

        # No damage should be dealt
        assert len(messages) == 0

        # Party HP unchanged
        party_combatant = engine._combat_state.encounter.combatants[0]
        assert party_combatant.stat_block.hp_current == 20

    def test_no_aura_no_damage(self):
        """Verify combatants without auras don't deal aura damage."""
        from src.combat.combat_engine import CombatEngine

        controller = MagicMock()
        engine = CombatEngine(controller)

        engine._combat_state = self._create_mock_combat_state(
            enemy_abilities=["Flight (60ft)"],  # Not an aura
            party_hp=20,
        )

        # Process aura damage
        messages = engine._process_aura_damage()

        # No damage should be dealt
        assert len(messages) == 0
        party_combatant = engine._combat_state.encounter.combatants[0]
        assert party_combatant.stat_block.hp_current == 20

    def test_get_combatant_auras(self):
        """Verify get_combatant_auras returns correct auras."""
        from src.combat.combat_engine import CombatEngine
        from src.data_models import AuraType

        controller = MagicMock()
        engine = CombatEngine(controller)

        engine._combat_state = self._create_mock_combat_state(
            enemy_abilities=[
                "Cold Aura (creatures within 10 feet take 1 cold damage per round)",
                "Flight (60ft)",  # Not an aura
            ],
        )

        auras = engine.get_combatant_auras("frore_gryphus")

        assert len(auras) == 1
        assert auras[0].aura_type == AuraType.COLD


class TestFroreGryphusIntegration:
    """Integration tests for Frore Gryphus cold aura."""

    def test_frore_gryphus_ability_text(self):
        """Verify Frore Gryphus ability text parses correctly."""
        from src.data_models import CombatAura, AuraType

        # The actual ability text from hex 0105
        ability = "Cold Aura (creatures within 10 feet take 1 cold damage per round)"

        aura = CombatAura.parse_from_special_ability(ability)

        assert aura is not None
        assert aura.aura_type == AuraType.COLD
        assert aura.radius_feet == 10
        assert aura.damage_per_round == 1
        assert aura.damage_type == "cold"
