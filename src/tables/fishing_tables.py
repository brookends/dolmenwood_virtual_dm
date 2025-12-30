"""
Dolmenwood Fishing Tables.

Implements the fishing tables from the Campaign Book (p116-117).
Contains 20 Edible Fish with their descriptions, special effects,
landing requirements, and yield modifiers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.data_models import DiceRoller


class FishEffectType(Enum):
    """Types of effects that occur when catching or consuming fish."""
    NONE = "none"
    # Catching effects
    HYPNOTIC = "hypnotic"  # Lowest WIS saves or fall in water
    SLIPPERY = "slippery"  # Requires DEX check to land
    VICIOUS = "vicious"  # Requires STR check to land
    COMBAT = "combat"  # Triggers combat encounter
    SHRIEK = "shriek"  # May attract wandering monster
    EXPLOSIVE = "explosive"  # May explode if mishandled
    DANGEROUS = "dangerous"  # Has spiny teeth, may cause damage
    INCORPOREAL = "incorporeal"  # Can turn incorporeal
    # Treasure effects
    TREASURE_TRINKET = "treasure_trinket"  # May contain trinket
    TREASURE_GEM = "treasure_gem"  # May contain gem
    # Special effects
    FAIRY = "fairy"  # Fairy fish, can grant blessing
    SINGING = "singing"  # Sings wistful melodies
    BLEATING = "bleating"  # Makes goat-like sounds
    SIGHING = "sighing"  # Sighs when landed
    RESEMBLANCE = "resemblance"  # Face resembles family member


class LandingType(Enum):
    """Type of check required to successfully land the fish."""
    NONE = "none"  # No special requirement
    DEX_CHECK = "dex_check"  # Dexterity check
    STR_CHECK = "str_check"  # Strength check
    COMBAT = "combat"  # Must defeat in combat


@dataclass
class LandingRequirement:
    """
    Requirements to successfully land a caught fish.

    Some fish are slippery (DEX) or strong (STR) and require
    multiple party members to successfully land.
    """
    landing_type: LandingType = LandingType.NONE
    num_characters: int = 1  # How many characters need to succeed
    check_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "landing_type": self.landing_type.value,
            "num_characters": self.num_characters,
            "check_description": self.check_description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LandingRequirement":
        return cls(
            landing_type=LandingType(data.get("landing_type", "none")),
            num_characters=data.get("num_characters", 1),
            check_description=data.get("check_description", ""),
        )


@dataclass
class CatchEffect:
    """
    Effect that occurs when catching or handling the fish.

    These effects happen during the fishing process, not consumption.
    """
    effect_type: FishEffectType = FishEffectType.NONE
    description: str = ""
    # Mechanical values
    save_type: str = ""  # "hold", "doom", "blast"
    damage: str = ""  # Dice expression for damage
    chance: str = ""  # X-in-6 chance (e.g., "2-in-6", "3-in-6")
    treasure_value: str = ""  # Dice expression for treasure value
    condition: str = ""  # Condition for effect (e.g., "first time catching")
    # Special flags
    requires_experience: bool = False  # Effect only hits first-timers
    attracts_monster: bool = False  # May attract wandering monster
    triggers_combat: bool = False  # Requires combat encounter
    blessing_if_released: bool = False  # Grants blessing if released
    blessing_bonus: int = 0  # Save bonus granted by blessing

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_type": self.effect_type.value,
            "description": self.description,
            "save_type": self.save_type,
            "damage": self.damage,
            "chance": self.chance,
            "treasure_value": self.treasure_value,
            "condition": self.condition,
            "requires_experience": self.requires_experience,
            "attracts_monster": self.attracts_monster,
            "triggers_combat": self.triggers_combat,
            "blessing_if_released": self.blessing_if_released,
            "blessing_bonus": self.blessing_bonus,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatchEffect":
        return cls(
            effect_type=FishEffectType(data.get("effect_type", "none")),
            description=data.get("description", ""),
            save_type=data.get("save_type", ""),
            damage=data.get("damage", ""),
            chance=data.get("chance", ""),
            treasure_value=data.get("treasure_value", ""),
            condition=data.get("condition", ""),
            requires_experience=data.get("requires_experience", False),
            attracts_monster=data.get("attracts_monster", False),
            triggers_combat=data.get("triggers_combat", False),
            blessing_if_released=data.get("blessing_if_released", False),
            blessing_bonus=data.get("blessing_bonus", 0),
        )


@dataclass
class CatchableFish:
    """
    A fish that can be caught with full description and effect metadata.

    Attributes:
        name: Common name of the fish
        description: Physical description of the fish
        flavor_text: Culinary or folklore notes
        rations_yield: Dice expression for rations (default "2d6")
        landing: Requirements to land the fish
        catch_effect: Effect when catching/handling
        rations_per_hp: For combat fish, rations per HP of damage dealt
        special_condition: Any special condition for full yield
    """
    name: str
    description: str
    flavor_text: str = ""
    rations_yield: str = "2d6"  # Default yield per Campaign Book
    landing: LandingRequirement = field(default_factory=LandingRequirement)
    catch_effect: CatchEffect = field(default_factory=CatchEffect)
    rations_per_hp: int = 0  # For combat fish like Giant Catfish
    special_condition: str = ""  # Condition for full yield
    monster_id: str = ""  # Reference to monster stats if combat fish

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "name": self.name,
            "description": self.description,
            "flavor_text": self.flavor_text,
            "rations_yield": self.rations_yield,
            "landing": self.landing.to_dict(),
            "catch_effect": self.catch_effect.to_dict(),
            "rations_per_hp": self.rations_per_hp,
            "special_condition": self.special_condition,
            "monster_id": self.monster_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatchableFish":
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            flavor_text=data.get("flavor_text", ""),
            rations_yield=data.get("rations_yield", "2d6"),
            landing=LandingRequirement.from_dict(data.get("landing", {})),
            catch_effect=CatchEffect.from_dict(data.get("catch_effect", {})),
            rations_per_hp=data.get("rations_per_hp", 0),
            special_condition=data.get("special_condition", ""),
            monster_id=data.get("monster_id", ""),
        )


# =============================================================================
# EDIBLE FISH TABLE (d20) - Campaign Book p116-117
# =============================================================================

EDIBLE_FISH: list[CatchableFish] = [
    # 1. Bally-tom
    CatchableFish(
        name="Bally-tom",
        description="Rotund, slow-swimming fish with silver scales and bulbous green eyes",
        flavor_text="When threatened, their eyes flash hypnotically. Lone anglers have been known to drown as a result.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.HYPNOTIC,
            description="Lowest WIS party member must Save Versus Hold or be dazzled and fall into the water",
            save_type="hold",
            condition="lowest WIS party member",
        ),
    ),

    # 2. Braithgilly
    CatchableFish(
        name="Braithgilly",
        description="Lithe, white-scaled trout with adorable pink eyes",
        flavor_text="When unafraid, braithgillies poke their heads above the surface and sing beautiful, wistful melodies. Their songs sometimes contain snippets of well-known folk-melodies and passages that sound almost like words. According to folklore, braithgillies willingly leap into the net of a maiden who sings to them under the light of the moon.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.SINGING,
            description="Sings wistful melodies; maidens singing under moonlight have advantage",
        ),
    ),

    # 3. Butter-eel
    CatchableFish(
        name="Butter-eel",
        description="3′-long, buttery-brown eels with startled, gaping mouths and a tendency to writhe vigorously when caught",
        flavor_text="Butter-eels are coated with a fatty slime, making them difficult to land.",
        landing=LandingRequirement(
            landing_type=LandingType.DEX_CHECK,
            num_characters=2,
            check_description="At least two PCs must make a successful Dexterity Check to land",
        ),
        catch_effect=CatchEffect(
            effect_type=FishEffectType.SLIPPERY,
            description="Coated in fatty slime; requires 2 PCs to make DEX checks to land",
        ),
    ),

    # 4. Gaffer
    CatchableFish(
        name="Gaffer",
        description="Foot-long catfish with tufts of coarse white fur around their face and gills, often formed into a goat-like beard upon the chin",
        flavor_text="Bleat when dragged from the water. Their flesh is tough but has a palatable sweet-sour note.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.BLEATING,
            description="Makes goat-like bleating sounds when caught",
        ),
    ),

    # 5. Giant catfish
    CatchableFish(
        name="Giant catfish",
        description="A real monster! Predatory fish 9–14′ long that attack anything nearby when hungry",
        flavor_text="Spawn in the deeps of the Groaning Loch, but sometimes swim in other lakes and rivers.",
        rations_yield="0",  # Calculated from HP
        rations_per_hp=4,  # 4 rations per Hit Point of the fish
        monster_id="giant_catfish",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.COMBAT,
            description="Handle as a normal combat encounter. If killed, provides 4 rations per Hit Point.",
            triggers_combat=True,
        ),
    ),

    # 6. Groper
    CatchableFish(
        name="Groper",
        description="Flat-bodied, green-skinned bottom feeders with gaping mouths and spacious gullets",
        flavor_text="Known for swallowing interesting objects that sink to the riverbed.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.TREASURE_TRINKET,
            description="2-in-6 chance of finding a random human trinket in the fish's belly",
            chance="2-in-6",
            treasure_value="trinket",
        ),
    ),

    # 7. Gurney
    CatchableFish(
        name="Gurney",
        description="Big, ball-shaped fish with beady eyes, misshapen faces, and wide, flapping mouths",
        flavor_text="Known among anglers for their habit of suddenly snapping with their concealed rows of vicious, spiny teeth.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.DANGEROUS,
            description="Characters who have not caught gurneys before must Save Versus Doom or suffer 1 point of damage",
            save_type="doom",
            damage="1",
            requires_experience=True,
            condition="first time catching gurneys",
        ),
    ),

    # 8. Hameth sprat
    CatchableFish(
        name="Hameth sprat",
        description="Little black-scaled fish with long, ribbon tails",
        flavor_text="Flit around in great swarms, especially numerous in the River Hameth. Eaten whole (bones and all), typically fried in batter.",
        rations_yield="2d4",  # Reduced yield
    ),

    # 9. Lardfish
    CatchableFish(
        name="Lardfish",
        description="Head-sized, translucent cream jellyfish with tangled tentacles dotted with clusters of grape-like nodules",
        flavor_text="The body of a lardfish is tough and somewhat fatty, but its tentacles are sweet and succulent.",
    ),

    # 10. Maid-o'-the-lake
    CatchableFish(
        name="Maid-o'-the-lake",
        description="Thigh-sized, pink, translucent squids renowned as a Dolmenwood delicacy",
        flavor_text="Their flesh is succulent and has a mildly fruity flavour. According to folklore, feasting beneath the moon on these squids fried in garlic butter is a sure way to summon the attentions of a witch, who will visit in the dead of night.",
    ),

    # 11. Mummer
    CatchableFish(
        name="Mummer",
        description="Sluggish, puffy fish with mud-brown scales, pink, ribbon-like fins, and bulbous, yellow faces of an unnervingly human-like cast",
        flavor_text="Known for their disturbing resemblance to human faces.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.RESEMBLANCE,
            description="3-in-6 chance that one of the caught fish has an uncanny resemblance to a family member of someone in the party",
            chance="3-in-6",
        ),
    ),

    # 12. Nag-pike
    CatchableFish(
        name="Nag-pike",
        description="Muscular, 3′-long, snaggle-toothed pikes with nine crooked horns upon their heads",
        flavor_text="Nag-pikes are vicious and tenacious, making them tricky to catch. When sliced and fried, their flesh is deliciously gamy.",
        landing=LandingRequirement(
            landing_type=LandingType.STR_CHECK,
            num_characters=2,
            check_description="The catch is only landed if at least two PCs make a successful Strength Check",
        ),
        catch_effect=CatchEffect(
            effect_type=FishEffectType.VICIOUS,
            description="Vicious and tenacious; requires 2 PCs to make STR checks to land",
        ),
    ),

    # 13. Orbling
    CatchableFish(
        name="Orbling",
        description="Silvery, spherical jellyfish that hide in weeds during the day and only emerge after sundown",
        flavor_text="In shaded waters, they bob near the surface, resembling reflected moonlight. Their outer skin is rubbery, but their insides are soft and taste of toffee. They are typically eaten like boiled eggs, by slicing off the top and scooping out the insides with a spoon.",
    ),

    # 14. Pilgrim crab
    CatchableFish(
        name="Pilgrim crab",
        description="Chunky violet crabs with long, delicate pincers and creamy-white underbellies",
        flavor_text="Their shells are graven with lines that look curiously like a religious script of some kind. (These are sometimes used as a means of fortune-telling.) If cooked alive, pilgrim crabs emit a shrill tone reminiscent of choirboys at practice.",
    ),

    # 15. Puffer
    CatchableFish(
        name="Puffer",
        description="2′-round, near-spherical fish covered with hard scales and spines",
        flavor_text="Puffers are slow moving and easy to catch. Killing and preparing them is the tricky part: they have a gas-filled organ that explodes if not handled correctly.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.EXPLOSIVE,
            description="Characters who have not caught puffers before must Save Versus Blast or suffer 1d3 damage when the fish explode",
            save_type="blast",
            damage="1d3",
            requires_experience=True,
            condition="first time catching puffers",
        ),
    ),

    # 16. Queen's salmon
    CatchableFish(
        name="Queen's salmon",
        description="Iridescent-scaled salmon that dart and leap playfully",
        flavor_text="Queen's salmon are fairy fish that visit Dolmenwood to spawn. They speak Sylvan and basic Woldish, and address anglers in squeaking little voices when caught. In return for their lives, a catch of these fish offer to place their blessing upon the noble anglers.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.FAIRY,
            description="Fairy fish that speak Sylvan and Woldish. If released, each party member gains +4 bonus to next Saving Throw vs deadly effect (death, petrification, poison, etc.)",
            blessing_if_released=True,
            blessing_bonus=4,
            condition="if released",
        ),
    ),

    # 17. Screaming jenny
    CatchableFish(
        name="Screaming jenny",
        description="Long, slender fish with frilly purple fins and tails",
        flavor_text="When pulled from the water, they emit a startling shriek.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.SHRIEK,
            description="Emits a startling shriek when landed; 3-in-6 chance of attracting a wandering monster",
            chance="3-in-6",
            attracts_monster=True,
        ),
    ),

    # 18. Smuggler-fish
    CatchableFish(
        name="Smuggler-fish",
        description="Puffed up, putrid green fish with lemon yellow bellies and wide, astonished eyes",
        flavor_text="Sigh plaintively then give up the ghost when landed.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.TREASURE_GEM,
            description="2-in-6 chance of finding a small gem (1d20 × 10gp) in the belly of one of the caught fish",
            chance="2-in-6",
            treasure_value="1d20*10",  # gp value
        ),
    ),

    # 19. Twine-eel
    CatchableFish(
        name="Twine-eel",
        description="3′-long, twisty, finger-thick eels with scales of purple or burnished pink",
        flavor_text="Swim in great schools and voraciously attack small prey and tempting morsels of bait. Preparing them is fiddly work, due to all the fine bones, but their delectably sweet flesh makes it worthwhile.",
    ),

    # 20. Wraithfish
    CatchableFish(
        name="Wraithfish",
        description="Lazy weed-browsers with near-transparent, jelly-like, white flesh",
        flavor_text="Wraithfish can turn incorporeal for brief periods, a trick they invariably perform when yanked out of the water by anglers. Madcap pipe music stymies this ability, and woodgrues are expert wraithfish catchers.",
        rations_yield="1d6",  # Reduced yield without music
        special_condition="Parties fishing without madcap pipe music only land fish sufficient for 1d6 rations. With pipe music, normal 2d6 yield.",
        catch_effect=CatchEffect(
            effect_type=FishEffectType.INCORPOREAL,
            description="Can turn incorporeal when caught; pipe music prevents this. Without music, only 1d6 rations.",
            condition="without pipe music",
        ),
    ),
]


# =============================================================================
# FISHING FUNCTIONS
# =============================================================================

def roll_fish() -> CatchableFish:
    """
    Roll for a specific fish on the d20 table.

    Per Campaign Book p116: Roll 1d20 to see what is caught.

    Returns:
        The CatchableFish caught
    """
    roll = DiceRoller.roll("1d20", "Fishing table").total
    # d20 roll of 1-20 maps to index 0-19
    index = roll - 1
    return EDIBLE_FISH[index]


def roll_fish_rations(fish: CatchableFish, has_pipe_music: bool = False) -> int:
    """
    Roll for the quantity of rations from a caught fish.

    Most fish yield 2d6 rations, but some have special yields:
    - Hameth sprat: 2d4
    - Wraithfish: 1d6 without pipe music, 2d6 with
    - Giant catfish: 4 per HP (calculated separately)

    Args:
        fish: The fish that was caught
        has_pipe_music: Whether party has madcap pipe music (for wraithfish)

    Returns:
        Number of rations (0 for combat fish)
    """
    # Combat fish don't give rations directly
    if fish.rations_per_hp > 0:
        return 0

    # Handle wraithfish special case
    if fish.name == "Wraithfish":
        if has_pipe_music:
            yield_expr = "2d6"
        else:
            yield_expr = "1d6"
    else:
        yield_expr = fish.rations_yield

    return DiceRoller.roll(yield_expr, f"{fish.name} rations yield").total


def get_fish_by_name(name: str) -> Optional[CatchableFish]:
    """
    Look up a fish by name.

    Args:
        name: Name of the fish (case-insensitive)

    Returns:
        The CatchableFish if found, None otherwise
    """
    name_lower = name.lower()

    for fish in EDIBLE_FISH:
        if fish.name.lower() == name_lower:
            return fish

    return None


def get_all_fish() -> list[CatchableFish]:
    """Return all catchable fish."""
    return EDIBLE_FISH.copy()


def check_treasure_in_fish(fish: CatchableFish) -> Optional[dict[str, Any]]:
    """
    Check if a fish contains treasure.

    Args:
        fish: The fish to check

    Returns:
        Dict with treasure info if found, None otherwise
    """
    effect = fish.catch_effect

    if effect.effect_type not in (FishEffectType.TREASURE_TRINKET, FishEffectType.TREASURE_GEM):
        return None

    if not effect.chance:
        return None

    # Parse X-in-6 chance
    parts = effect.chance.split("-in-")
    if len(parts) != 2:
        return None

    target = int(parts[0])
    roll = DiceRoller.roll("1d6", f"{fish.name} treasure check").total

    if roll > target:
        return None  # No treasure

    # Treasure found!
    if effect.effect_type == FishEffectType.TREASURE_TRINKET:
        return {
            "type": "trinket",
            "description": "Random human trinket found in fish's belly",
            "table": "human_trinket",
        }
    else:  # GEM
        # Parse treasure value expression (e.g., "1d20*10")
        if "*" in effect.treasure_value:
            dice, multiplier = effect.treasure_value.split("*")
            base_roll = DiceRoller.roll(dice, f"{fish.name} gem value").total
            value = base_roll * int(multiplier)
        else:
            value = DiceRoller.roll(effect.treasure_value, f"{fish.name} gem value").total

        return {
            "type": "gem",
            "value_gp": value,
            "description": f"Small gem worth {value}gp found in fish's belly",
        }


def check_first_timer_danger(fish: CatchableFish, has_experience: bool) -> Optional[dict[str, Any]]:
    """
    Check if an inexperienced angler suffers from a dangerous fish.

    Args:
        fish: The fish being handled
        has_experience: Whether the character has caught this fish before

    Returns:
        Dict with danger info if triggered, None otherwise
    """
    effect = fish.catch_effect

    if not effect.requires_experience:
        return None

    if has_experience:
        return None  # Experienced anglers know to be careful

    return {
        "fish_name": fish.name,
        "save_type": effect.save_type,
        "damage": effect.damage,
        "description": effect.description,
    }


def check_monster_attracted(fish: CatchableFish) -> bool:
    """
    Check if catching this fish attracts a wandering monster.

    Args:
        fish: The fish that was caught

    Returns:
        True if a monster is attracted, False otherwise
    """
    effect = fish.catch_effect

    if not effect.attracts_monster:
        return False

    if not effect.chance:
        return True  # Always attracts if no chance specified

    # Parse X-in-6 chance
    parts = effect.chance.split("-in-")
    if len(parts) != 2:
        return False

    target = int(parts[0])
    roll = DiceRoller.roll("1d6", f"{fish.name} monster attraction check").total

    return roll <= target


def fish_requires_landing_check(fish: CatchableFish) -> bool:
    """Check if this fish requires a special landing check."""
    return fish.landing.landing_type != LandingType.NONE


def fish_triggers_combat(fish: CatchableFish) -> bool:
    """Check if this fish triggers a combat encounter."""
    return fish.catch_effect.triggers_combat


def fish_is_fairy(fish: CatchableFish) -> bool:
    """Check if this is a fairy fish that can grant blessings."""
    return fish.catch_effect.blessing_if_released


def fish_to_inventory_item(
    fish: CatchableFish,
    quantity: int = 1,
    source_hex: Optional[str] = None,
) -> "Item":
    """
    Convert a CatchableFish to an Item for character inventory.

    This creates an Item instance that can be stored in character inventory
    as fresh rations from fishing.

    Args:
        fish: The CatchableFish from fishing tables
        quantity: Number of rations caught
        source_hex: Optional hex where fish was caught

    Returns:
        Item instance ready for inventory storage
    """
    from src.data_models import Item

    # Generate a unique item_id based on name
    item_id = fish.name.lower().replace(" ", "_").replace("'", "").replace("-", "_")

    return Item(
        item_id=item_id,
        name=fish.name,
        weight=4,  # Standard weight for rations
        quantity=quantity,
        item_type="consumable",
        slot_size=0,
        description=fish.description,
        consumption_effect={
            "effect_type": "rations",
            "description": f"Fresh {fish.name} - provides sustenance",
            "flavor_text": fish.flavor_text,
        },
        source_hex=source_hex,
    )
