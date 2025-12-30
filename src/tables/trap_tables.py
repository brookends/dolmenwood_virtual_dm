"""
Trap tables and data for Dolmenwood Virtual DM.

Implements the trap system per Campaign Book p102-103:
- 4 trap categories (Pit, Architectural, Mechanism, Magical)
- 9 trigger types
- 20 trap effects with specific mechanics
- Category-based disarm rules
- Exploration clues for detection
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.data_models import DiceRoller


class TrapCategory(str, Enum):
    """
    Trap categories per Campaign Book p102.

    Each category has different properties:
    - PIT: Open or concealed holes, always passable if party crosses safely
    - ARCHITECTURAL: Wall/ceiling/floor attacks (spears, arrows, deadfalls)
    - MECHANISM: Spring-loaded contraptions with blades, gas, etc.
    - MAGICAL: Curses, symbols, trapped souls
    """

    PIT = "pit"
    ARCHITECTURAL = "architectural"
    MECHANISM = "mechanism"
    MAGICAL = "magical"


class TrapTrigger(str, Enum):
    """
    Trap trigger types per Campaign Book p102.

    9 distinct trigger mechanisms that activate traps.
    """

    PRESSURE_PLATE = "pressure_plate"  # Weight-activated floor plate
    SCALES = "scales"  # Removes item triggers trap (like idol on altar)
    TRIPWIRE = "tripwire"  # Physical wire at ankle height
    LOCK = "lock"  # Triggered when lock is picked or forced
    OPENING = "opening"  # Triggered when lid/door is opened
    DETECTION = "detection"  # Light, body heat, motion, or sound sensors
    PROXIMITY = "proximity"  # Magical detection of nearby creatures
    SPEECH = "speech"  # Triggered by spoken word/password
    TOUCH = "touch"  # Direct contact with object


class TrapEffectType(str, Enum):
    """
    Trap effect types per Campaign Book p103.

    20 distinct trap effects with specific mechanics.
    """

    # Damage effects
    ACID_SPRAY = "acid_spray"
    ARROW_VOLLEY = "arrow_volley"
    CRUSHING_CEILING = "crushing_ceiling"
    PIT_FALL = "pit"
    SPEAR_WALL = "spear_wall"
    SPIKES = "spikes"

    # Gas effects (save vs Doom)
    GAS_CONFUSION = "gas_confusion"
    GAS_MEMORY = "gas_memory"
    GAS_PARALYSIS = "gas_paralysis"
    GAS_SLEEP = "gas_sleep"
    GAS_POISON = "gas_poison"

    # Physical constraint effects
    NET = "net"
    PORTCULLIS = "portcullis"

    # Magic effects
    MAGIC_ALARM = "magic_alarm"
    MAGIC_CAGE = "magic_cage"
    MAGIC_DARKNESS = "magic_darkness"
    MAGIC_LIGHT_BLAST = "magic_light_blast"
    MAGIC_POLYMORPH = "magic_polymorph"
    MAGIC_SYMBOL = "magic_symbol"
    MAGIC_TELEPORT = "magic_teleport"


@dataclass
class TrapEffect:
    """
    Detailed trap effect with mechanics per Campaign Book p103.

    Attributes:
        effect_type: The type of effect
        description: Narrative description of the effect
        save_type: Type of save required (doom, blast, ray, etc.) or None
        save_negates: Whether save completely negates the effect
        damage: Damage dice expression or None
        damage_on_save: Damage if save succeeds (usually half or none)
        attack_bonus: Attack bonus if trap makes attack roll
        num_attacks: Number of attacks (e.g., arrow volley)
        duration_rounds: Duration in rounds (None = instant)
        duration_turns: Duration in turns (None = instant)
        condition_applied: Condition applied on failed save
        escape_check: Check type to escape (STR, DEX, etc.)
        escape_dc: DC for escape check
        special_mechanic: Any special mechanics
        clues: Exploration clues that might reveal this trap
    """

    effect_type: TrapEffectType
    description: str
    save_type: Optional[str] = None
    save_negates: bool = False
    damage: Optional[str] = None
    damage_on_save: Optional[str] = None
    attack_bonus: Optional[int] = None
    num_attacks: Optional[str] = None  # Dice expression like "1d4"
    duration_rounds: Optional[int] = None
    duration_turns: Optional[int] = None
    condition_applied: Optional[str] = None
    escape_check: Optional[str] = None
    escape_dc: Optional[int] = None
    special_mechanic: Optional[str] = None
    clues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "effect_type": self.effect_type.value,
            "description": self.description,
            "save_type": self.save_type,
            "save_negates": self.save_negates,
            "damage": self.damage,
            "damage_on_save": self.damage_on_save,
            "attack_bonus": self.attack_bonus,
            "num_attacks": self.num_attacks,
            "duration_rounds": self.duration_rounds,
            "duration_turns": self.duration_turns,
            "condition_applied": self.condition_applied,
            "escape_check": self.escape_check,
            "escape_dc": self.escape_dc,
            "special_mechanic": self.special_mechanic,
            "clues": self.clues,
        }


@dataclass
class Trap:
    """
    Complete trap definition per Campaign Book p102-103.

    Attributes:
        trap_id: Unique identifier
        name: Display name
        category: Trap category (determines disarm rules)
        trigger: Trigger mechanism
        effect: The trap's effect when triggered
        trigger_chance: X-in-6 chance of triggering (default 2, well-maintained 3-4)
        detection_dc: DC to detect during search (None = auto-found on search)
        is_concealed: Whether the trap is hidden
        can_be_bypassed: Whether the trap can be safely bypassed
        bypass_description: How to bypass the trap
        password: Password to disable (for magical traps)
    """

    trap_id: str
    name: str
    category: TrapCategory
    trigger: TrapTrigger
    effect: TrapEffect
    trigger_chance: int = 2  # X-in-6
    detection_dc: Optional[int] = None
    is_concealed: bool = True
    can_be_bypassed: bool = True
    bypass_description: Optional[str] = None
    password: Optional[str] = None  # For magical traps

    def can_be_disarmed(self) -> bool:
        """Check if this trap can be disarmed (not bypassed)."""
        return self.category in (TrapCategory.MECHANISM, TrapCategory.MAGICAL)

    def requires_thief(self) -> bool:
        """Check if this trap requires a thief to disarm."""
        return self.category == TrapCategory.MECHANISM

    def requires_magic(self) -> bool:
        """Check if this trap requires magic to disarm."""
        return self.category == TrapCategory.MAGICAL

    def get_disarm_method(self) -> str:
        """Get the method required to disarm this trap."""
        if self.category == TrapCategory.PIT:
            return "Pit traps cannot be disarmed, only bypassed"
        elif self.category == TrapCategory.ARCHITECTURAL:
            return "Architectural traps cannot be disarmed, only bypassed"
        elif self.category == TrapCategory.MECHANISM:
            return "Requires thief with Disarm Mechanism ability"
        else:  # MAGICAL
            if self.password:
                return "Requires Dispel Magic spell or speaking the password"
            return "Requires Dispel Magic spell"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trap_id": self.trap_id,
            "name": self.name,
            "category": self.category.value,
            "trigger": self.trigger.value,
            "effect": self.effect.to_dict(),
            "trigger_chance": self.trigger_chance,
            "detection_dc": self.detection_dc,
            "is_concealed": self.is_concealed,
            "can_be_bypassed": self.can_be_bypassed,
            "bypass_description": self.bypass_description,
            "disarm_method": self.get_disarm_method(),
            "requires_thief": self.requires_thief(),
            "requires_magic": self.requires_magic(),
        }


# =============================================================================
# TRAP EFFECTS TABLE (p103)
# =============================================================================

# Define all 20 trap effects from Campaign Book p103

TRAP_EFFECTS: dict[TrapEffectType, TrapEffect] = {
    TrapEffectType.ACID_SPRAY: TrapEffect(
        effect_type=TrapEffectType.ACID_SPRAY,
        description="A spray of acid shoots from the wall, floor, or ceiling",
        save_type="blast",
        save_negates=False,
        damage="3d6",
        damage_on_save="0",  # Avoid entirely
        clues=[
            "Discolored stains on the floor",
            "Pitted stone surface nearby",
            "Faint chemical smell",
        ],
    ),
    TrapEffectType.ARROW_VOLLEY: TrapEffect(
        effect_type=TrapEffectType.ARROW_VOLLEY,
        description="Multiple arrows fire from hidden slots in the wall",
        attack_bonus=8,
        num_attacks="1d4",
        damage="1d6",  # Per arrow
        clues=[
            "Small holes in the wall",
            "Feathers or broken arrow shafts nearby",
            "Click sounds when testing surfaces",
        ],
    ),
    TrapEffectType.CRUSHING_CEILING: TrapEffect(
        effect_type=TrapEffectType.CRUSHING_CEILING,
        description="The ceiling begins to descend, crushing all beneath after 3 rounds",
        damage="10d6",
        duration_rounds=3,  # Takes 3 rounds to crush
        escape_check="STR",  # Hold it up or escape
        escape_dc=15,
        special_mechanic="Party has 3 rounds to escape or prop ceiling. STR check to hold it temporarily.",
        clues=[
            "Ceiling sits lower than adjacent areas",
            "Grooves in the walls",
            "Ancient dried bloodstains",
        ],
    ),
    TrapEffectType.GAS_CONFUSION: TrapEffect(
        effect_type=TrapEffectType.GAS_CONFUSION,
        description="Confusion gas fills the area",
        save_type="doom",
        save_negates=True,
        condition_applied="confused",
        duration_rounds=12,  # 2 minutes
        special_mechanic="Affected creatures act randomly per Confusion spell",
        clues=[
            "Strange smell in the air",
            "Yellowish residue on surfaces",
            "Ventilation holes in ceiling",
        ],
    ),
    TrapEffectType.GAS_MEMORY: TrapEffect(
        effect_type=TrapEffectType.GAS_MEMORY,
        description="Memory-erasing gas fills the area",
        save_type="doom",
        save_negates=True,
        condition_applied="memory_erased",
        special_mechanic="On failed save, lose all memory of the last 1d6 hours",
        clues=[
            "Faint sweet smell",
            "Pink residue on walls",
            "Notes left by previous victims",
        ],
    ),
    TrapEffectType.GAS_PARALYSIS: TrapEffect(
        effect_type=TrapEffectType.GAS_PARALYSIS,
        description="Paralytic gas fills the area",
        save_type="doom",
        save_negates=True,
        condition_applied="paralyzed",
        duration_turns=1,  # 10 minutes
        clues=[
            "Greenish tinge in the air",
            "Rigid corpse nearby",
            "Unusual stillness in the area",
        ],
    ),
    TrapEffectType.GAS_POISON: TrapEffect(
        effect_type=TrapEffectType.GAS_POISON,
        description="Poisonous gas fills the area",
        save_type="doom",
        save_negates=False,
        damage="3d6",
        damage_on_save="0",  # Avoided on save
        special_mechanic="On failed save, take 3d6 damage",
        clues=[
            "Dead insects and rodents nearby",
            "Withered plants",
            "Acrid smell",
        ],
    ),
    TrapEffectType.GAS_SLEEP: TrapEffect(
        effect_type=TrapEffectType.GAS_SLEEP,
        description="Sleep gas fills the area",
        save_type="doom",
        save_negates=True,
        condition_applied="asleep",
        duration_turns=3,  # 30 minutes
        special_mechanic="Affected creatures fall asleep and cannot be woken for duration",
        clues=[
            "Sweet floral scent",
            "Sleeping creature nearby",
            "Soft hissing sound from walls",
        ],
    ),
    TrapEffectType.MAGIC_ALARM: TrapEffect(
        effect_type=TrapEffectType.MAGIC_ALARM,
        description="A magical alarm sounds, alerting nearby creatures",
        special_mechanic="Loud magical alarm sounds. All wandering monster checks in dungeon succeed for next turn.",
        clues=[
            "Faint magical aura",
            "Runes inscribed on surface",
            "Tingling sensation when approaching",
        ],
    ),
    TrapEffectType.MAGIC_CAGE: TrapEffect(
        effect_type=TrapEffectType.MAGIC_CAGE,
        description="A magical iron cage springs up around the victim",
        condition_applied="caged",
        duration_turns=1,  # 10 minutes
        escape_check="STR",
        escape_dc=20,  # Very hard to break
        special_mechanic="Cage has AC 18 and 50 HP. Dispel Magic ends it instantly.",
        clues=[
            "Iron filings on floor",
            "Scorch marks in circular pattern",
            "Previous cage marks on floor",
        ],
    ),
    TrapEffectType.MAGIC_DARKNESS: TrapEffect(
        effect_type=TrapEffectType.MAGIC_DARKNESS,
        description="Magical darkness fills the area",
        condition_applied="in_darkness",
        duration_turns=1,  # 10 minutes
        special_mechanic="15' radius magical darkness. Light sources don't function within.",
        clues=[
            "Darkened stone surfaces",
            "Cold spots in the area",
            "Light seems dimmer near trigger",
        ],
    ),
    TrapEffectType.MAGIC_LIGHT_BLAST: TrapEffect(
        effect_type=TrapEffectType.MAGIC_LIGHT_BLAST,
        description="A blinding flash of light erupts",
        condition_applied="blinded",
        duration_rounds=6,  # 1 minute
        special_mechanic="No save. All creatures in 30' radius blinded for 1d6 rounds.",
        clues=[
            "Reflective surfaces positioned oddly",
            "Crystal or gem in unusual location",
            "Faint glow from trigger point",
        ],
    ),
    TrapEffectType.MAGIC_POLYMORPH: TrapEffect(
        effect_type=TrapEffectType.MAGIC_POLYMORPH,
        description="The victim is polymorphed into a small creature",
        save_type="ray",
        save_negates=True,
        condition_applied="polymorphed",
        special_mechanic="Polymorphed into a frog, mouse, or similar. Dispel Magic to reverse.",
        clues=[
            "Small animals nearby that behave strangely",
            "Discarded equipment with no owner",
            "Magical residue on surfaces",
        ],
    ),
    TrapEffectType.MAGIC_SYMBOL: TrapEffect(
        effect_type=TrapEffectType.MAGIC_SYMBOL,
        description="A magical symbol activates with devastating effect",
        save_type="doom",
        save_negates=False,
        damage="4d6",
        damage_on_save="2d6",
        special_mechanic="Symbol explodes. Affects all within 30'. Various effects possible.",
        clues=[
            "Glowing rune visible on surface",
            "Warning inscriptions nearby",
            "Magical aura detectable",
        ],
    ),
    TrapEffectType.MAGIC_TELEPORT: TrapEffect(
        effect_type=TrapEffectType.MAGIC_TELEPORT,
        description="The victim is teleported to a random location in the dungeon",
        save_type="ray",
        save_negates=True,
        condition_applied="teleported",
        special_mechanic="Teleported 1d6 rooms away to a random location. Equipment goes too.",
        clues=[
            "Shimmer in the air",
            "Disoriented person nearby who doesn't remember arriving",
            "Portal residue on floor",
        ],
    ),
    TrapEffectType.NET: TrapEffect(
        effect_type=TrapEffectType.NET,
        description="A weighted net drops from above",
        save_type="blast",
        save_negates=True,
        condition_applied="restrained",
        escape_check="STR",
        escape_dc=12,
        special_mechanic="Net can be cut (AC 10, 5 HP) or escaped with STR check",
        clues=[
            "Holes in ceiling above",
            "Rope fibers on floor",
            "Slight sag in ceiling",
        ],
    ),
    TrapEffectType.PIT_FALL: TrapEffect(
        effect_type=TrapEffectType.PIT_FALL,
        description="The floor gives way, dropping victims into a pit",
        save_type="blast",
        save_negates=True,
        damage="1d6",  # Per 10 feet, typically 10-30 feet
        special_mechanic="Pit depth varies (10-30 feet). Some contain spikes (+1d6) or water.",
        clues=[
            "Floor sounds hollow when tapped",
            "Slight depression or discoloration",
            "Draft from below",
        ],
    ),
    TrapEffectType.PORTCULLIS: TrapEffect(
        effect_type=TrapEffectType.PORTCULLIS,
        description="Heavy iron portcullis drops, trapping or separating the party",
        save_type="blast",
        save_negates=True,
        damage="2d6",  # If caught under it
        escape_check="STR",
        escape_dc=18,
        special_mechanic="Splits party. Requires STR check DC 18 to lift, or mechanism to raise.",
        clues=[
            "Grooves in walls and floor",
            "Portcullis visible in ceiling",
            "Winch mechanism nearby",
        ],
    ),
    TrapEffectType.SPEAR_WALL: TrapEffect(
        effect_type=TrapEffectType.SPEAR_WALL,
        description="Spears thrust out from the wall",
        attack_bonus=6,
        num_attacks="1d6",  # Number of spears
        damage="1d8",  # Per spear
        clues=[
            "Slots in the wall",
            "Bloodstains at waist height",
            "Broken spear tips on floor",
        ],
    ),
    TrapEffectType.SPIKES: TrapEffect(
        effect_type=TrapEffectType.SPIKES,
        description="Hidden spikes spring up from the floor or shoot from walls",
        save_type="blast",
        save_negates=False,
        damage="2d6",
        damage_on_save="1d6",
        special_mechanic="Spikes may be poisoned (additional Save vs Doom or extra 1d6 damage)",
        clues=[
            "Small holes in floor",
            "Dark stains between floor tiles",
            "Previous victims impaled nearby",
        ],
    ),
}


# =============================================================================
# TRAP GENERATION
# =============================================================================

def generate_random_trap(dice: Optional[DiceRoller] = None) -> Trap:
    """
    Generate a random trap using d20 tables per Campaign Book p102-103.

    Rolls:
    - d4 for category
    - d10 for trigger type (adapted from 9 types)
    - d20 for effect type

    Args:
        dice: Optional dice roller

    Returns:
        A randomly generated Trap
    """
    dice = dice or DiceRoller()

    # Roll category (d4)
    cat_roll = dice.roll("1d4", "trap category").total
    categories = [TrapCategory.PIT, TrapCategory.ARCHITECTURAL,
                  TrapCategory.MECHANISM, TrapCategory.MAGICAL]
    category = categories[cat_roll - 1]

    # Roll trigger (d10, mapped to 9 types)
    trig_roll = dice.roll("1d10", "trap trigger").total
    triggers = [
        TrapTrigger.PRESSURE_PLATE,  # 1
        TrapTrigger.SCALES,  # 2
        TrapTrigger.TRIPWIRE,  # 3
        TrapTrigger.LOCK,  # 4
        TrapTrigger.OPENING,  # 5
        TrapTrigger.DETECTION,  # 6
        TrapTrigger.PROXIMITY,  # 7
        TrapTrigger.SPEECH,  # 8
        TrapTrigger.TOUCH,  # 9
        TrapTrigger.PRESSURE_PLATE,  # 10 (repeat)
    ]
    trigger = triggers[trig_roll - 1]

    # Roll effect (d20)
    effect_roll = dice.roll("1d20", "trap effect").total
    effect_types = list(TrapEffectType)
    effect_type = effect_types[effect_roll % len(effect_types)]
    effect = TRAP_EFFECTS[effect_type]

    # Generate trap name
    trap_id = f"trap_{category.value}_{effect_type.value}"
    name = f"{category.value.title()} {effect_type.value.replace('_', ' ').title()}"

    return Trap(
        trap_id=trap_id,
        name=name,
        category=category,
        trigger=trigger,
        effect=effect,
    )


def get_trap_by_effect(effect_type: TrapEffectType, category: TrapCategory,
                       trigger: TrapTrigger = TrapTrigger.PRESSURE_PLATE) -> Trap:
    """
    Create a trap with a specific effect type.

    Args:
        effect_type: The effect when triggered
        category: The trap category
        trigger: The trigger mechanism

    Returns:
        A Trap with the specified configuration
    """
    effect = TRAP_EFFECTS[effect_type]

    trap_id = f"trap_{category.value}_{effect_type.value}"
    name = f"{category.value.title()} {effect_type.value.replace('_', ' ').title()}"

    return Trap(
        trap_id=trap_id,
        name=name,
        category=category,
        trigger=trigger,
        effect=effect,
    )


# =============================================================================
# EXPLORATION CLUES
# =============================================================================

def get_exploration_clues(trap: Trap) -> list[str]:
    """
    Get exploration clues that might reveal this trap.

    These clues are what the referee might describe during exploration
    to hint at the trap's presence.

    Args:
        trap: The trap to get clues for

    Returns:
        List of clue descriptions
    """
    clues = list(trap.effect.clues)

    # Add trigger-specific clues
    trigger_clues = {
        TrapTrigger.PRESSURE_PLATE: [
            "A section of floor sits slightly lower",
            "The stone here feels different underfoot",
        ],
        TrapTrigger.SCALES: [
            "The object sits on an oddly designed pedestal",
            "You notice a slight mechanism beneath the item",
        ],
        TrapTrigger.TRIPWIRE: [
            "A thin glint at ankle height",
            "The dust pattern is disturbed in a line",
        ],
        TrapTrigger.LOCK: [
            "The lock mechanism looks unusually complex",
            "Scratch marks around the keyhole",
        ],
        TrapTrigger.OPENING: [
            "The hinges look strangely reinforced",
            "A faint click when you touch the handle",
        ],
        TrapTrigger.DETECTION: [
            "Strange crystals embedded in the walls",
            "The air feels charged with energy",
        ],
        TrapTrigger.PROXIMITY: [
            "Runes glow faintly as you approach",
            "A tingling sensation near the area",
        ],
        TrapTrigger.SPEECH: [
            "An inscription reads 'Speak friend and enter'",
            "The walls seem to be listening",
        ],
        TrapTrigger.TOUCH: [
            "The surface looks suspiciously pristine",
            "A faint magical aura on the object",
        ],
    }

    clues.extend(trigger_clues.get(trap.trigger, []))
    return clues


def get_bypass_options(trap: Trap) -> list[dict[str, Any]]:
    """
    Get options to bypass (not disarm) a trap.

    Per p155, these are creative solutions that avoid triggering the trap
    rather than disarming it.

    Args:
        trap: The trap to bypass

    Returns:
        List of bypass options with resolution method
    """
    options = []

    # Category-specific bypasses
    if trap.category == TrapCategory.PIT:
        options.extend([
            {
                "method": "Jump across",
                "check": "STR",
                "dc": 10,
                "description": "Jump over the pit",
            },
            {
                "method": "Use plank or ladder",
                "check": None,  # Auto-success with equipment
                "description": "Bridge the gap with equipment",
            },
            {
                "method": "Climb around",
                "check": "DEX",
                "dc": 12,
                "description": "Edge around the pit on the walls",
            },
        ])

    # Trigger-specific bypasses
    if trap.trigger == TrapTrigger.PRESSURE_PLATE:
        options.append({
            "method": "Throw weight to trigger",
            "check": None,
            "description": "Throw a heavy object to trigger from safety",
        })
        options.append({
            "method": "Step around",
            "check": "DEX",
            "dc": 10,
            "description": "Carefully step around the pressure plate",
        })

    if trap.trigger == TrapTrigger.TRIPWIRE:
        options.append({
            "method": "Step over",
            "check": "DEX",
            "dc": 8,
            "description": "Step carefully over the tripwire",
        })
        options.append({
            "method": "Probe ahead with pole",
            "check": None,
            "description": "Use a 10-foot pole to trigger from safety",
        })

    if trap.trigger == TrapTrigger.SCALES:
        options.append({
            "method": "Replace with equal weight",
            "check": "DEX",
            "dc": 12,
            "description": "Swap the item with something of equal weight",
        })

    if trap.trigger == TrapTrigger.LOCK:
        options.append({
            "method": "Force the lock",
            "check": "STR",
            "dc": 15,
            "description": "Smash the lock, possibly destroying a delicate trap",
        })

    # Universal bypasses
    options.append({
        "method": "Avoid entirely",
        "check": None,
        "description": "Simply don't interact with the trapped area",
    })

    return options


# =============================================================================
# DISARM RULES
# =============================================================================

@dataclass
class DisarmAttempt:
    """Result of a trap disarm attempt."""

    success: bool
    method_used: str
    trap_triggered: bool = False
    message: str = ""
    thief_ability_used: bool = False
    magic_used: bool = False
    password_used: bool = False


def can_attempt_disarm(trap: Trap, character_class: str,
                       has_dispel_magic: bool = False,
                       knows_password: bool = False) -> tuple[bool, str]:
    """
    Check if a character can attempt to disarm a trap.

    Per Campaign Book p102-103:
    - Mechanism traps: Require thief with Disarm Mechanism ability
    - Magical traps: Require Dispel Magic or knowing the password
    - Pit/Architectural: Cannot be disarmed, only bypassed

    Args:
        trap: The trap to disarm
        character_class: Character's class (lowercase)
        has_dispel_magic: Whether character can cast Dispel Magic
        knows_password: Whether character knows the password

    Returns:
        Tuple of (can_disarm, reason)
    """
    if trap.category == TrapCategory.PIT:
        return False, "Pit traps cannot be disarmed. Try jumping over or bridging it."

    if trap.category == TrapCategory.ARCHITECTURAL:
        return False, "Architectural traps cannot be disarmed. Try jamming the mechanism or avoiding it."

    if trap.category == TrapCategory.MECHANISM:
        if character_class.lower() == "thief":
            return True, "Thief can attempt Disarm Mechanism check"
        return False, "Only a thief can disarm mechanism traps using their Disarm Mechanism ability"

    if trap.category == TrapCategory.MAGICAL:
        if has_dispel_magic:
            return True, "Can attempt to dispel the magical trap"
        if knows_password and trap.password:
            return True, "Speaking the password will disable the trap"
        return False, "Magical traps require Dispel Magic spell or knowing the password"

    return False, "Unknown trap category"


def attempt_disarm(trap: Trap, character_class: str, disarm_chance: int,
                   dice: Optional[DiceRoller] = None,
                   has_dispel_magic: bool = False,
                   dispel_check: Optional[int] = None,
                   knows_password: bool = False) -> DisarmAttempt:
    """
    Attempt to disarm a trap.

    Args:
        trap: The trap to disarm
        character_class: Character's class
        disarm_chance: Thief's Disarm Mechanism percentage
        dice: Optional dice roller
        has_dispel_magic: Whether using Dispel Magic
        dispel_check: Caster level for dispel check
        knows_password: Whether using the password

    Returns:
        DisarmAttempt result
    """
    dice = dice or DiceRoller()

    # Check if disarm is possible
    can_disarm, reason = can_attempt_disarm(trap, character_class, has_dispel_magic, knows_password)

    if not can_disarm:
        return DisarmAttempt(
            success=False,
            method_used="none",
            message=reason,
        )

    # Password bypass (auto-success)
    if knows_password and trap.password:
        return DisarmAttempt(
            success=True,
            method_used="password",
            password_used=True,
            message=f"Speaking '{trap.password}' disables the trap",
        )

    # Dispel Magic
    if has_dispel_magic and trap.category == TrapCategory.MAGICAL:
        # Dispel check: d20 + caster level vs DC 11 + trap level (assume level 5)
        dispel_roll = dice.roll("1d20", "dispel check").total
        dc = 11 + 5  # Assume trap level 5
        success = (dispel_roll + (dispel_check or 0)) >= dc

        if success:
            return DisarmAttempt(
                success=True,
                method_used="dispel_magic",
                magic_used=True,
                message="The magical trap's enchantment is dispelled",
            )
        else:
            return DisarmAttempt(
                success=False,
                method_used="dispel_magic",
                magic_used=True,
                message="The dispel attempt fails to overcome the trap's magic",
            )

    # Thief Disarm Mechanism
    if character_class.lower() == "thief" and trap.category == TrapCategory.MECHANISM:
        roll = dice.roll_percentile("disarm mechanism")

        if roll.total <= disarm_chance:
            return DisarmAttempt(
                success=True,
                method_used="disarm_mechanism",
                thief_ability_used=True,
                message="The trap's mechanism is carefully disabled",
            )
        else:
            # Failed attempt - chance to trigger
            trigger_roll = dice.roll("1d6", "failed disarm trigger").total
            triggered = trigger_roll == 1

            return DisarmAttempt(
                success=False,
                method_used="disarm_mechanism",
                thief_ability_used=True,
                trap_triggered=triggered,
                message="The disarm attempt fails!" + (
                    " The trap springs!" if triggered else ""
                ),
            )

    return DisarmAttempt(
        success=False,
        method_used="none",
        message="No valid disarm method available",
    )
