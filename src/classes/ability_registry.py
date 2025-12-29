"""
Class Ability Registry for Dolmenwood Virtual DM.

Provides a centralized registry of class abilities with categorization
by effect type and integration hooks for game systems (combat, skills,
encounters, etc.).

This registry enables the combat engine, encounter engine, and skill
resolution systems to query which abilities apply to specific situations.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_models import CharacterState
    from src.classes.class_data import ClassAbility


class AbilityEffectType(str, Enum):
    """Categories of ability effects for system integration."""
    # Combat effects
    COMBAT_ATTACK = "combat_attack"       # Modifies attack rolls
    COMBAT_DAMAGE = "combat_damage"       # Modifies damage
    COMBAT_AC = "combat_ac"               # Modifies armor class
    COMBAT_SPECIAL = "combat_special"     # Special combat action (backstab)
    COMBAT_TRIGGERED = "combat_triggered" # Triggered by combat event (cleave)

    # Skill effects
    SKILL_CHECK = "skill_check"           # d6 skill check
    SKILL_BONUS = "skill_bonus"           # Bonus to existing skill

    # Encounter effects
    ENCOUNTER_ACTION = "encounter_action" # Special encounter action
    ENCOUNTER_MODIFIER = "encounter_modifier"  # Modifies encounter rolls

    # Save effects
    SAVE_BONUS = "save_bonus"             # Bonus to saving throws
    SAVE_PENALTY_INFLICT = "save_penalty_inflict"  # Penalty to enemy saves

    # Magic effects
    MAGIC_CASTING = "magic_casting"       # Enables spellcasting
    MAGIC_DETECTION = "magic_detection"   # Detects magic

    # Healing effects
    HEALING_ACTIVE = "healing_active"     # Active healing ability

    # Passive effects
    PASSIVE_LANGUAGE = "passive_language" # Language ability
    PASSIVE_MOVEMENT = "passive_movement" # Movement modifier
    PASSIVE_RESISTANCE = "passive_resistance"  # Damage resistance

    # Companion/summon effects
    COMPANION = "companion"               # Animal companion or summon


@dataclass
class AbilityIntegration:
    """
    Defines how a class ability integrates with game systems.

    This structure allows game engines to query for applicable abilities
    and apply their effects.
    """
    ability_id: str
    class_id: str
    effect_types: list[AbilityEffectType]

    # Combat integration
    attack_bonus: int = 0
    damage_bonus: int = 0
    damage_dice: Optional[str] = None
    ac_modifier: int = 0

    # Conditions for the ability to apply
    requires_position: Optional[str] = None  # "behind", "flanking"
    requires_awareness: bool = False         # Target must be unaware
    requires_weapon: Optional[str] = None    # "dagger", "two-handed"
    requires_enemy_type: Optional[str] = None  # "undead", "arcane_caster"
    requires_activation: bool = False        # Must be explicitly activated

    # Skill integration
    skill_names: list[str] = field(default_factory=list)
    skill_targets_by_level: dict[int, dict[str, int]] = field(default_factory=dict)

    # Save integration
    save_bonus: int = 0
    save_type: Optional[str] = None  # "doom", "spell", "arcane"
    inflicts_save_penalty: int = 0
    inflicts_penalty_to: Optional[str] = None  # "arcane_casters"

    # Encounter integration
    encounter_action_name: Optional[str] = None
    encounter_action_roll: Optional[str] = None  # "2d6"
    encounter_action_range: int = 0

    # Healing integration
    healing_amount: Optional[str] = None  # "1 HP per level"
    healing_uses_per_day: int = 0

    # Triggered effects
    trigger_condition: Optional[str] = None  # "killing_blow", "first_hit"
    triggered_effect: Optional[str] = None

    # Resource costs
    uses_per_day: Optional[int] = None
    uses_per_combat: Optional[int] = None

    # Extra data for complex abilities
    extra_data: dict[str, Any] = field(default_factory=dict)


class AbilityRegistry:
    """
    Central registry for class ability integration.

    Provides lookup methods for game systems to find and apply
    relevant class abilities.
    """
    _instance: Optional["AbilityRegistry"] = None
    _initialized: bool = False

    def __new__(cls) -> "AbilityRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if AbilityRegistry._initialized:
            return

        self._abilities: dict[str, AbilityIntegration] = {}
        self._by_class: dict[str, list[str]] = {}
        self._by_effect_type: dict[AbilityEffectType, list[str]] = {}

        self._register_all_abilities()
        AbilityRegistry._initialized = True

    def _register_all_abilities(self) -> None:
        """Register all class abilities with their integration data."""
        # =================================================================
        # FIGHTER ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="fighter_combat_talents",
            class_id="fighter",
            effect_types=[
                AbilityEffectType.COMBAT_ATTACK,
                AbilityEffectType.COMBAT_DAMAGE,
                AbilityEffectType.COMBAT_AC,
                AbilityEffectType.COMBAT_TRIGGERED,
            ],
            requires_activation=True,  # Talents must be selected/activated
            extra_data={
                "talent_levels": [2, 6, 10, 14],
                "available_talents": [
                    "battle_rage", "cleave", "defender", "last_stand",
                    "leader", "main_gauche", "slayer", "weapon_specialist"
                ],
            },
        ))

        # =================================================================
        # THIEF ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="thief_backstab",
            class_id="thief",
            effect_types=[
                AbilityEffectType.COMBAT_SPECIAL,
                AbilityEffectType.COMBAT_ATTACK,
                AbilityEffectType.COMBAT_DAMAGE,
            ],
            attack_bonus=4,
            damage_dice="3d4",
            requires_position="behind",
            requires_awareness=True,
            requires_weapon="dagger",
            extra_data={
                "valid_targets": "Mortals, fairies, or demi-fey of Small or Medium size",
                "natural_1_effect": "Save vs Doom or be noticed",
            },
        ))

        self._register(AbilityIntegration(
            ability_id="thief_skills",
            class_id="thief",
            effect_types=[AbilityEffectType.SKILL_CHECK],
            skill_names=[
                "climb_wall", "decipher_document", "disarm_mechanism",
                "legerdemain", "pick_lock", "listen", "search", "stealth"
            ],
            skill_targets_by_level={
                1:  {"climb_wall": 4, "decipher_document": 6, "disarm_mechanism": 6, "legerdemain": 6, "pick_lock": 6, "listen": 5, "search": 6, "stealth": 5},
                2:  {"climb_wall": 4, "decipher_document": 6, "disarm_mechanism": 5, "legerdemain": 6, "pick_lock": 6, "listen": 5, "search": 5, "stealth": 5},
                3:  {"climb_wall": 4, "decipher_document": 6, "disarm_mechanism": 5, "legerdemain": 5, "pick_lock": 5, "listen": 5, "search": 5, "stealth": 5},
                4:  {"climb_wall": 3, "decipher_document": 5, "disarm_mechanism": 5, "legerdemain": 5, "pick_lock": 5, "listen": 5, "search": 5, "stealth": 5},
                5:  {"climb_wall": 3, "decipher_document": 5, "disarm_mechanism": 5, "legerdemain": 5, "pick_lock": 5, "listen": 4, "search": 5, "stealth": 4},
                6:  {"climb_wall": 3, "decipher_document": 5, "disarm_mechanism": 4, "legerdemain": 5, "pick_lock": 5, "listen": 4, "search": 4, "stealth": 4},
                7:  {"climb_wall": 3, "decipher_document": 5, "disarm_mechanism": 4, "legerdemain": 4, "pick_lock": 4, "listen": 4, "search": 4, "stealth": 4},
                8:  {"climb_wall": 2, "decipher_document": 4, "disarm_mechanism": 4, "legerdemain": 4, "pick_lock": 4, "listen": 4, "search": 4, "stealth": 4},
                9:  {"climb_wall": 2, "decipher_document": 4, "disarm_mechanism": 4, "legerdemain": 4, "pick_lock": 4, "listen": 3, "search": 4, "stealth": 3},
                10: {"climb_wall": 2, "decipher_document": 4, "disarm_mechanism": 3, "legerdemain": 4, "pick_lock": 4, "listen": 3, "search": 3, "stealth": 3},
                11: {"climb_wall": 2, "decipher_document": 4, "disarm_mechanism": 3, "legerdemain": 3, "pick_lock": 3, "listen": 3, "search": 3, "stealth": 3},
                12: {"climb_wall": 2, "decipher_document": 3, "disarm_mechanism": 3, "legerdemain": 3, "pick_lock": 3, "listen": 2, "search": 3, "stealth": 3},
                13: {"climb_wall": 2, "decipher_document": 3, "disarm_mechanism": 3, "legerdemain": 3, "pick_lock": 3, "listen": 2, "search": 2, "stealth": 2},
                14: {"climb_wall": 2, "decipher_document": 3, "disarm_mechanism": 2, "legerdemain": 3, "pick_lock": 2, "listen": 2, "search": 2, "stealth": 2},
                15: {"climb_wall": 2, "decipher_document": 2, "disarm_mechanism": 2, "legerdemain": 2, "pick_lock": 2, "listen": 2, "search": 2, "stealth": 2},
            },
        ))

        self._register(AbilityIntegration(
            ability_id="thief_thieves_cant",
            class_id="thief",
            effect_types=[AbilityEffectType.PASSIVE_LANGUAGE],
            extra_data={
                "language_type": "secret",
                "components": ["gestures", "code words"],
            },
        ))

        # =================================================================
        # CLERIC ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="cleric_turn_undead",
            class_id="cleric",
            effect_types=[AbilityEffectType.ENCOUNTER_ACTION],
            encounter_action_name="Turn Undead",
            encounter_action_roll="2d6",
            encounter_action_range=30,
            requires_enemy_type="undead",
            extra_data={
                "results": {
                    "4_or_lower": "unaffected",
                    "5_to_6": "2d4 stunned for 1 Round",
                    "7_to_12": "2d4 flee for 1 Turn",
                    "13_or_higher": "2d4 destroyed",
                },
                "level_modifiers": {
                    "lower_level_undead": "+2 per Level difference (max +6)",
                    "higher_level_undead": "-2 per Level difference (max -6)",
                },
            },
        ))

        self._register(AbilityIntegration(
            ability_id="cleric_holy_magic",
            class_id="cleric",
            effect_types=[AbilityEffectType.MAGIC_CASTING],
            extra_data={
                "spell_type": "holy",
                "max_spell_rank": 5,
                "min_level": 2,
            },
        ))

        self._register(AbilityIntegration(
            ability_id="cleric_detect_holy_magic",
            class_id="cleric",
            effect_types=[AbilityEffectType.MAGIC_DETECTION],
            extra_data={
                "requires": "touch object, concentrate",
                "time": "1 Turn",
            },
        ))

        # Holy Order abilities (Order of St Faxis)
        self._register(AbilityIntegration(
            ability_id="cleric_order_st_faxis",
            class_id="cleric",
            effect_types=[
                AbilityEffectType.SAVE_BONUS,
                AbilityEffectType.SAVE_PENALTY_INFLICT,
            ],
            save_bonus=2,
            save_type="arcane",
            inflicts_save_penalty=-2,
            inflicts_penalty_to="arcane_casters",
            extra_data={
                "order_name": "Order of St Faxis",
                "min_level": 2,
            },
        ))

        # Holy Order abilities (Order of St Sedge)
        self._register(AbilityIntegration(
            ability_id="cleric_order_st_sedge",
            class_id="cleric",
            effect_types=[AbilityEffectType.HEALING_ACTIVE],
            healing_amount="1 HP per Level",
            healing_uses_per_day=1,
            extra_data={
                "order_name": "Order of St Sedge",
                "min_level": 2,
                "ability_name": "Laying on Hands",
            },
        ))

        # Holy Order abilities (Order of St Signis)
        self._register(AbilityIntegration(
            ability_id="cleric_order_st_signis",
            class_id="cleric",
            effect_types=[AbilityEffectType.COMBAT_ATTACK],
            attack_bonus=1,
            requires_enemy_type="undead",
            extra_data={
                "order_name": "Order of St Signis",
                "min_level": 2,
                "ability_name": "Undead Slayer",
                "bypasses_resistance": True,
            },
        ))

        self._register(AbilityIntegration(
            ability_id="cleric_languages",
            class_id="cleric",
            effect_types=[AbilityEffectType.PASSIVE_LANGUAGE],
            extra_data={"bonus_languages": ["Liturgic"]},
        ))

        # =================================================================
        # FRIAR ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="friar_turn_undead",
            class_id="friar",
            effect_types=[AbilityEffectType.ENCOUNTER_ACTION],
            encounter_action_name="Turn Undead",
            encounter_action_roll="2d6",
            encounter_action_range=30,
            requires_enemy_type="undead",
            extra_data={
                "results": {
                    "4_or_lower": "unaffected",
                    "5_to_6": "2d4 stunned for 1 Round",
                    "7_to_12": "2d4 flee for 1 Turn",
                    "13_or_higher": "2d4 destroyed",
                },
            },
        ))

        self._register(AbilityIntegration(
            ability_id="friar_unarmoured_defence",
            class_id="friar",
            effect_types=[AbilityEffectType.COMBAT_AC],
            ac_modifier=3,  # Base AC 13 unarmoured
            extra_data={
                "base_ac": 13,
                "condition": "not wearing armour",
            },
        ))

        self._register(AbilityIntegration(
            ability_id="friar_holy_magic",
            class_id="friar",
            effect_types=[AbilityEffectType.MAGIC_CASTING],
            extra_data={
                "spell_type": "holy",
                "max_spell_rank": 5,
            },
        ))

        # =================================================================
        # KNIGHT ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="knight_combat_prowess",
            class_id="knight",
            effect_types=[
                AbilityEffectType.COMBAT_ATTACK,
                AbilityEffectType.COMBAT_DAMAGE,
            ],
            attack_bonus=1,
            damage_bonus=1,
            extra_data={
                "condition": "mounted or on foot",
                "applies_always": True,
            },
        ))

        self._register(AbilityIntegration(
            ability_id="knight_horsemanship",
            class_id="knight",
            effect_types=[AbilityEffectType.SKILL_CHECK],
            skill_names=["riding"],
            extra_data={
                "riding_checks": "automatic success",
                "mounted_combat": "no penalties",
            },
        ))

        self._register(AbilityIntegration(
            ability_id="knight_mounted_charge",
            class_id="knight",
            effect_types=[
                AbilityEffectType.COMBAT_ATTACK,
                AbilityEffectType.COMBAT_DAMAGE,
            ],
            attack_bonus=2,  # +2 in addition to normal charge +2
            damage_dice="2x",  # Double damage on mounted charge
            extra_data={
                "condition": "mounted charge with lance",
                "total_charge_bonus": "+4 Attack, double damage",
            },
        ))

        # =================================================================
        # HUNTER ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="hunter_skills",
            class_id="hunter",
            effect_types=[AbilityEffectType.SKILL_CHECK],
            skill_names=["listen", "search", "stealth", "track"],
            skill_targets_by_level={
                1:  {"listen": 5, "search": 5, "stealth": 5, "track": 5},
                2:  {"listen": 5, "search": 5, "stealth": 5, "track": 5},
                3:  {"listen": 4, "search": 5, "stealth": 5, "track": 5},
                4:  {"listen": 4, "search": 4, "stealth": 4, "track": 5},
                5:  {"listen": 4, "search": 4, "stealth": 4, "track": 4},
                6:  {"listen": 4, "search": 4, "stealth": 4, "track": 4},
                7:  {"listen": 3, "search": 3, "stealth": 3, "track": 4},
                8:  {"listen": 3, "search": 3, "stealth": 3, "track": 3},
                9:  {"listen": 3, "search": 3, "stealth": 3, "track": 3},
                10: {"listen": 2, "search": 2, "stealth": 2, "track": 3},
                11: {"listen": 2, "search": 2, "stealth": 2, "track": 2},
                12: {"listen": 2, "search": 2, "stealth": 2, "track": 2},
                13: {"listen": 2, "search": 2, "stealth": 2, "track": 2},
                14: {"listen": 2, "search": 2, "stealth": 2, "track": 2},
                15: {"listen": 2, "search": 2, "stealth": 2, "track": 2},
            },
        ))

        self._register(AbilityIntegration(
            ability_id="hunter_animal_companion",
            class_id="hunter",
            effect_types=[AbilityEffectType.COMPANION],
            extra_data={
                "companion_types": ["dog", "hawk", "ferret"],
                "levels_together": "companion levels with hunter",
            },
        ))

        self._register(AbilityIntegration(
            ability_id="hunter_wayfinding",
            class_id="hunter",
            effect_types=[AbilityEffectType.ENCOUNTER_MODIFIER],
            extra_data={
                "effect": "Party cannot become lost in wilderness",
                "condition": "hunter conscious and guiding",
            },
        ))

        self._register(AbilityIntegration(
            ability_id="hunter_trophy_bonus",
            class_id="hunter",
            effect_types=[
                AbilityEffectType.COMBAT_ATTACK,
                AbilityEffectType.SAVE_BONUS,
            ],
            extra_data={
                "attack_bonus_per_trophy": 1,
                "save_bonus_per_trophy": 1,
                "condition": "fighting creature type matching trophy",
                "max_trophies": 3,
            },
        ))

        # =================================================================
        # BARD ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="bard_enchantment",
            class_id="bard",
            effect_types=[AbilityEffectType.ENCOUNTER_ACTION],
            encounter_action_name="Enchantment",
            encounter_action_roll="2d6",
            encounter_action_range=60,
            extra_data={
                "effect": "charm_like",
                "targets": "mortals, fairies, demi-fey, beasts",
                "save": "Spell",
                "uses_per_day_by_level": {1: 1, 4: 2, 8: 3, 12: 4},
            },
        ))

        self._register(AbilityIntegration(
            ability_id="bard_lore",
            class_id="bard",
            effect_types=[AbilityEffectType.SKILL_CHECK],
            skill_names=["lore"],
            extra_data={
                "base_chance": "2-in-6",
                "scaling": "+1 per 3 levels",
            },
        ))

        self._register(AbilityIntegration(
            ability_id="bard_performance",
            class_id="bard",
            effect_types=[AbilityEffectType.ENCOUNTER_MODIFIER],
            extra_data={
                "effect": "+1 reaction roll when performing",
                "uses": "unlimited during social encounters",
            },
        ))

        # =================================================================
        # MAGICIAN ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="magician_arcane_magic",
            class_id="magician",
            effect_types=[AbilityEffectType.MAGIC_CASTING],
            extra_data={
                "spell_type": "arcane",
                "max_spell_rank": 6,
            },
        ))

        self._register(AbilityIntegration(
            ability_id="magician_detect_magic",
            class_id="magician",
            effect_types=[
                AbilityEffectType.MAGIC_DETECTION,
                AbilityEffectType.SKILL_CHECK,
            ],
            skill_names=["detect_magic"],
            skill_targets_by_level={
                1: {"detect_magic": 6},
                3: {"detect_magic": 5},
                5: {"detect_magic": 5},
                7: {"detect_magic": 4},
                9: {"detect_magic": 4},
                11: {"detect_magic": 3},
                13: {"detect_magic": 3},
                15: {"detect_magic": 3},
            },
        ))

        # =================================================================
        # ENCHANTER ABILITIES
        # =================================================================
        self._register(AbilityIntegration(
            ability_id="enchanter_glamour_magic",
            class_id="enchanter",
            effect_types=[AbilityEffectType.MAGIC_CASTING],
            extra_data={
                "spell_type": "glamour",
                "max_spell_rank": 5,
            },
        ))

        self._register(AbilityIntegration(
            ability_id="enchanter_rune_magic",
            class_id="enchanter",
            effect_types=[AbilityEffectType.MAGIC_CASTING],
            extra_data={
                "spell_type": "rune",
                "rune_types": ["lesser", "greater", "mighty"],
                "runes_per_day_by_level": {1: 1, 3: 2, 5: 3, 7: 4},
            },
        ))

        self._register(AbilityIntegration(
            ability_id="enchanter_fairy_tongue",
            class_id="enchanter",
            effect_types=[AbilityEffectType.PASSIVE_LANGUAGE],
            extra_data={
                "bonus_languages": ["Sylvan"],
            },
        ))

    def _register(self, integration: AbilityIntegration) -> None:
        """Register an ability integration."""
        self._abilities[integration.ability_id] = integration

        # Index by class
        if integration.class_id not in self._by_class:
            self._by_class[integration.class_id] = []
        self._by_class[integration.class_id].append(integration.ability_id)

        # Index by effect type
        for effect_type in integration.effect_types:
            if effect_type not in self._by_effect_type:
                self._by_effect_type[effect_type] = []
            self._by_effect_type[effect_type].append(integration.ability_id)

    # =========================================================================
    # LOOKUP METHODS
    # =========================================================================

    def get(self, ability_id: str) -> Optional[AbilityIntegration]:
        """Get an ability integration by ID."""
        return self._abilities.get(ability_id)

    def get_by_class(self, class_id: str) -> list[AbilityIntegration]:
        """Get all abilities for a class."""
        ability_ids = self._by_class.get(class_id.lower(), [])
        return [self._abilities[aid] for aid in ability_ids]

    def get_by_effect_type(
        self,
        effect_type: AbilityEffectType
    ) -> list[AbilityIntegration]:
        """Get all abilities with a specific effect type."""
        ability_ids = self._by_effect_type.get(effect_type, [])
        return [self._abilities[aid] for aid in ability_ids]

    # =========================================================================
    # COMBAT INTEGRATION
    # =========================================================================

    def get_combat_modifiers(
        self,
        character: "CharacterState",
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Get combat modifiers from character's class abilities.

        Args:
            character: The character state
            context: Combat context with keys like:
                - target_type: Enemy type (undead, etc.)
                - position: Attack position (behind, flanking)
                - target_aware: Whether target is aware
                - weapon: Weapon being used
                - is_mounted: Whether attacker is mounted
                - talents: Selected combat talents

        Returns:
            Dictionary with:
                - attack_bonus: Total attack modifier
                - damage_bonus: Total damage modifier
                - damage_dice: Override damage dice (for backstab)
                - ac_modifier: AC modifier
                - special_effects: List of triggered effects
        """
        result = {
            "attack_bonus": 0,
            "damage_bonus": 0,
            "damage_dice": None,
            "ac_modifier": 0,
            "special_effects": [],
        }

        class_id = character.character_class.lower()
        abilities = self.get_by_class(class_id)

        for ability in abilities:
            # Check combat effect types
            if AbilityEffectType.COMBAT_ATTACK not in ability.effect_types:
                if AbilityEffectType.COMBAT_SPECIAL not in ability.effect_types:
                    if AbilityEffectType.COMBAT_AC not in ability.effect_types:
                        continue

            # Check conditions
            if ability.requires_enemy_type:
                if context.get("target_type") != ability.requires_enemy_type:
                    continue

            if ability.requires_position:
                if context.get("position") != ability.requires_position:
                    continue

            if ability.requires_awareness:
                if context.get("target_aware", True):
                    continue

            if ability.requires_weapon:
                if ability.requires_weapon not in str(context.get("weapon", "")):
                    continue

            # Apply bonuses
            result["attack_bonus"] += ability.attack_bonus
            result["damage_bonus"] += ability.damage_bonus
            result["ac_modifier"] += ability.ac_modifier

            if ability.damage_dice:
                result["damage_dice"] = ability.damage_dice

            # Record special effects
            if ability.ability_id:
                result["special_effects"].append({
                    "ability_id": ability.ability_id,
                    "attack_bonus": ability.attack_bonus,
                    "damage_bonus": ability.damage_bonus,
                })

        return result

    def get_backstab_data(
        self,
        character: "CharacterState"
    ) -> Optional[dict[str, Any]]:
        """
        Get backstab ability data for a character.

        Returns:
            Backstab data if character has backstab, None otherwise
        """
        ability = self.get("thief_backstab")
        if not ability:
            return None

        if character.character_class.lower() != "thief":
            return None

        return {
            "attack_bonus": ability.attack_bonus,
            "damage_dice": ability.damage_dice,
            "requires_position": ability.requires_position,
            "requires_awareness": ability.requires_awareness,
            "requires_weapon": ability.requires_weapon,
            "extra_data": ability.extra_data,
        }

    # =========================================================================
    # SKILL INTEGRATION
    # =========================================================================

    def get_skill_target(
        self,
        character: "CharacterState",
        skill_name: str,
    ) -> Optional[int]:
        """
        Get the skill check target number for a character.

        Args:
            character: The character state
            skill_name: Name of the skill (e.g., "pick_lock", "stealth")

        Returns:
            Target number (roll d6 >= target), or None if not a class skill
        """
        class_id = character.character_class.lower()
        abilities = self.get_by_class(class_id)

        for ability in abilities:
            if AbilityEffectType.SKILL_CHECK not in ability.effect_types:
                continue

            if skill_name not in ability.skill_names:
                continue

            # Look up target by level
            level_targets = ability.skill_targets_by_level.get(character.level)
            if level_targets and skill_name in level_targets:
                return level_targets[skill_name]

            # Fallback: find nearest lower level
            for lvl in sorted(ability.skill_targets_by_level.keys(), reverse=True):
                if lvl <= character.level:
                    return ability.skill_targets_by_level[lvl].get(skill_name)

        return None

    def get_class_skills(self, class_id: str) -> list[str]:
        """Get all skill names available to a class."""
        skills = set()
        abilities = self.get_by_class(class_id)

        for ability in abilities:
            if AbilityEffectType.SKILL_CHECK in ability.effect_types:
                skills.update(ability.skill_names)

        return list(skills)

    # =========================================================================
    # ENCOUNTER INTEGRATION
    # =========================================================================

    def get_encounter_actions(
        self,
        character: "CharacterState",
    ) -> list[dict[str, Any]]:
        """
        Get special encounter actions available to a character.

        Returns:
            List of encounter action definitions
        """
        result = []
        class_id = character.character_class.lower()
        abilities = self.get_by_class(class_id)

        for ability in abilities:
            if AbilityEffectType.ENCOUNTER_ACTION not in ability.effect_types:
                continue

            action = {
                "ability_id": ability.ability_id,
                "name": ability.encounter_action_name,
                "roll": ability.encounter_action_roll,
                "range": ability.encounter_action_range,
                "requires_enemy_type": ability.requires_enemy_type,
                "extra_data": ability.extra_data,
            }
            result.append(action)

        return result

    def get_turn_undead_data(
        self,
        character: "CharacterState",
    ) -> Optional[dict[str, Any]]:
        """
        Get Turn Undead ability data for a character.

        Returns:
            Turn Undead data if character has the ability, None otherwise
        """
        class_id = character.character_class.lower()

        if class_id == "cleric":
            ability = self.get("cleric_turn_undead")
        elif class_id == "friar":
            ability = self.get("friar_turn_undead")
        else:
            return None

        if not ability:
            return None

        return {
            "roll": ability.encounter_action_roll,
            "range": ability.encounter_action_range,
            "level": character.level,
            "results": ability.extra_data.get("results", {}),
            "level_modifiers": ability.extra_data.get("level_modifiers", {}),
        }

    # =========================================================================
    # SAVE INTEGRATION
    # =========================================================================

    def get_save_modifiers(
        self,
        character: "CharacterState",
        save_type: str,
        context: dict[str, Any],
    ) -> int:
        """
        Get save modifiers from character's class abilities.

        Args:
            character: The character state
            save_type: Type of save (doom, ray, hold, blast, spell)
            context: Context with keys like:
                - source_type: Source of effect (arcane, holy, etc.)

        Returns:
            Total save modifier
        """
        modifier = 0
        class_id = character.character_class.lower()
        abilities = self.get_by_class(class_id)

        for ability in abilities:
            if AbilityEffectType.SAVE_BONUS not in ability.effect_types:
                continue

            # Check if this save type matches
            if ability.save_type:
                # Check for specific save type match
                if ability.save_type == save_type:
                    modifier += ability.save_bonus
                # Check for source type match (e.g., "arcane" for Order of St Faxis)
                elif ability.save_type == context.get("source_type"):
                    modifier += ability.save_bonus

        return modifier

    # =========================================================================
    # HEALING INTEGRATION
    # =========================================================================

    def get_healing_abilities(
        self,
        character: "CharacterState",
    ) -> list[dict[str, Any]]:
        """
        Get healing abilities available to a character.

        Returns:
            List of healing ability definitions
        """
        result = []
        class_id = character.character_class.lower()
        abilities = self.get_by_class(class_id)

        for ability in abilities:
            if AbilityEffectType.HEALING_ACTIVE not in ability.effect_types:
                continue

            healing = {
                "ability_id": ability.ability_id,
                "amount": ability.healing_amount,
                "uses_per_day": ability.healing_uses_per_day,
                "extra_data": ability.extra_data,
            }
            result.append(healing)

        return result

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None
        cls._initialized = False


# Module-level singleton accessor
_registry: Optional[AbilityRegistry] = None


def get_ability_registry() -> AbilityRegistry:
    """Get the global ability registry instance."""
    global _registry
    if _registry is None:
        _registry = AbilityRegistry()
    return _registry
