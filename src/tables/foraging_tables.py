"""
Dolmenwood Foraging Tables.

Implements the foraging tables from the Campaign Book (p118-119).
Contains 20 Edible Fungi and 20 Edible Plants with their descriptions
and special effects metadata (applied upon consumption, not discovery).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.data_models import DiceRoller


class ForageType(Enum):
    """Type of foraged item."""
    FUNGI = "fungi"
    PLANT = "plant"


class EffectType(Enum):
    """Types of effects that can apply when consuming foraged items."""
    NONE = "none"
    DOUBLE_NOURISHMENT = "double_nourishment"  # Counts as 2 rations
    SAVE_PENALTY = "save_penalty"  # Penalty to saving throws
    PSYCHEDELIA = "psychedelia"  # Hallucinogenic effects
    VALUABLE = "valuable"  # Can be sold for gold
    HEALING = "healing"  # Restores HP
    POISON_RESISTANCE = "poison_resistance"  # Bonus vs poison
    INTOXICATION = "intoxication"  # Drunk-like effects
    ENERGY = "energy"  # Temporary stamina boost
    NAUSEA = "nausea"  # Sickness if overconsumed
    VISION = "vision"  # Enhanced sight or visions
    SLEEP = "sleep"  # Induces drowsiness
    WARMTH = "warmth"  # Resistance to cold
    COURAGE = "courage"  # Bonus vs fear


@dataclass
class ConsumptionEffect:
    """
    Effect metadata for when a foraged item is consumed.

    These effects are stored with the inventory item and applied
    only when the character consumes the item.
    """
    effect_type: EffectType = EffectType.NONE
    description: str = ""
    # Mechanical values (interpretation depends on effect_type)
    modifier: int = 0  # e.g., -2 for save penalty, +1 for bonus
    duration_hours: int = 0  # How long effect lasts (0 = instant/permanent)
    gold_value: str = ""  # Dice expression for valuable items (e.g., "1d6")
    save_type: str = ""  # Which save is affected (e.g., "magic", "poison")
    condition: str = ""  # Condition for effect (e.g., "after dark", "if 3+ consumed")

    def to_dict(self) -> dict[str, Any]:
        """Serialize effect to dictionary."""
        return {
            "effect_type": self.effect_type.value,
            "description": self.description,
            "modifier": self.modifier,
            "duration_hours": self.duration_hours,
            "gold_value": self.gold_value,
            "save_type": self.save_type,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConsumptionEffect":
        """Deserialize from dictionary."""
        return cls(
            effect_type=EffectType(data.get("effect_type", "none")),
            description=data.get("description", ""),
            modifier=data.get("modifier", 0),
            duration_hours=data.get("duration_hours", 0),
            gold_value=data.get("gold_value", ""),
            save_type=data.get("save_type", ""),
            condition=data.get("condition", ""),
        )


@dataclass
class ForageableItem:
    """
    A forageable item with full description and effect metadata.

    Attributes:
        name: Common name of the item
        forage_type: Whether this is fungi or plant
        description: Physical description of the item
        smell: What it smells like
        taste: What it tastes like
        effect: Consumption effect metadata (applied when eaten)
    """
    name: str
    forage_type: ForageType
    description: str
    smell: str
    taste: str
    effect: ConsumptionEffect = field(default_factory=ConsumptionEffect)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for inventory storage."""
        return {
            "name": self.name,
            "forage_type": self.forage_type.value,
            "description": self.description,
            "smell": self.smell,
            "taste": self.taste,
            "effect": self.effect.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ForageableItem":
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            forage_type=ForageType(data.get("forage_type", "plant")),
            description=data.get("description", ""),
            smell=data.get("smell", ""),
            taste=data.get("taste", ""),
            effect=ConsumptionEffect.from_dict(data.get("effect", {})),
        )


# =============================================================================
# EDIBLE FUNGI TABLE (d20) - Campaign Book p118
# =============================================================================

EDIBLE_FUNGI: list[ForageableItem] = [
    # 1. Amethyst orb
    ForageableItem(
        name="Amethyst orb",
        forage_type=ForageType.FUNGI,
        description="A round, purple-hued mushroom with a crystalline sheen on its cap",
        smell="Faintly floral, like dried lavender",
        taste="Earthy with a hint of grape",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="A nourishing mushroom with no special effects",
        ),
    ),
    # 2. Brainconk
    ForageableItem(
        name="Brainconk",
        forage_type=ForageType.FUNGI,
        description="A wrinkled, brain-shaped bracket fungus that grows on dead oaks",
        smell="Musty and slightly metallic",
        taste="Chewy with a nutty undertone",
        effect=ConsumptionEffect(
            effect_type=EffectType.VISION,
            description="Grants vivid dreams if eaten before sleep",
            duration_hours=8,
            condition="eaten before sleep",
        ),
    ),
    # 3. Chanctonslip
    ForageableItem(
        name="Chanctonslip",
        forage_type=ForageType.FUNGI,
        description="Slender, pale mushrooms with a slippery texture",
        smell="Fresh and clean, like morning dew",
        taste="Mild and slightly sweet",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="A pleasant, easily digestible mushroom",
        ),
    ),
    # 4. Deathcap mimic
    ForageableItem(
        name="Deathcap mimic",
        forage_type=ForageType.FUNGI,
        description="Resembles the deadly deathcap but with subtle orange flecks on the cap",
        smell="Slightly acrid, causing hesitation",
        taste="Surprisingly rich and savory",
        effect=ConsumptionEffect(
            effect_type=EffectType.COURAGE,
            description="Grants +1 to saves vs fear for eating something that looks deadly",
            modifier=1,
            duration_hours=4,
            save_type="fear",
        ),
    ),
    # 5. Devil's fingers
    ForageableItem(
        name="Devil's fingers",
        forage_type=ForageType.FUNGI,
        description="Red, tentacle-like protrusions emerging from a white egg sac",
        smell="Strong carrion stench that fades when cooked",
        taste="Meaty and peppery when prepared properly",
        effect=ConsumptionEffect(
            effect_type=EffectType.WARMTH,
            description="Provides warmth, granting resistance to natural cold",
            duration_hours=6,
        ),
    ),
    # 6. Elf-cup
    ForageableItem(
        name="Elf-cup",
        forage_type=ForageType.FUNGI,
        description="Bright scarlet, cup-shaped fungi found on rotting branches",
        smell="Sweet and inviting",
        taste="Delicate, like honeyed berries",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="A favorite of the fey, considered good luck to find",
        ),
    ),
    # 7. Green-finger morel
    ForageableItem(
        name="Green-finger morel",
        forage_type=ForageType.FUNGI,
        description="Honeycomb-textured cap with a distinctive greenish tinge",
        smell="Woody and aromatic",
        taste="Rich, earthy, and prized by gourmands",
        effect=ConsumptionEffect(
            effect_type=EffectType.VALUABLE,
            description="Highly prized by cooks; can be sold to taverns",
            gold_value="1d4",
        ),
    ),
    # 8. Hell horns
    ForageableItem(
        name="Hell horns",
        forage_type=ForageType.FUNGI,
        description="Black, horn-shaped mushrooms with ridged surfaces",
        smell="Smoky, like charred wood",
        taste="Intensely savory with an almost meaty quality",
        effect=ConsumptionEffect(
            effect_type=EffectType.DOUBLE_NOURISHMENT,
            description="Exceptionally filling; counts as 2 rations worth of food",
        ),
    ),
    # 9. Hogback truffle
    ForageableItem(
        name="Hogback truffle",
        forage_type=ForageType.FUNGI,
        description="Lumpy, dark brown truffle found just beneath the soil",
        smell="Pungent and earthy, irresistible to pigs",
        taste="Complex, with notes of garlic and hazelnut",
        effect=ConsumptionEffect(
            effect_type=EffectType.VALUABLE,
            description="A delicacy; can be sold to wealthy buyers",
            gold_value="2d6",
        ),
    ),
    # 10. King oyster
    ForageableItem(
        name="King oyster",
        forage_type=ForageType.FUNGI,
        description="Large, trumpet-shaped white mushroom with a thick stem",
        smell="Subtle, almost odorless",
        taste="Firm and slightly sweet, excellent grilled",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="A hearty, filling mushroom favored by travelers",
        ),
    ),
    # 11. Moonchook
    ForageableItem(
        name="Moonchook",
        forage_type=ForageType.FUNGI,
        description="Luminescent pale blue mushrooms that glow faintly in darkness",
        smell="Cool and ethereal, like moonlit mist",
        taste="Light and refreshing with a minty finish",
        effect=ConsumptionEffect(
            effect_type=EffectType.VALUABLE,
            description="Prized for their magical glow; alchemists pay well",
            gold_value="1d6",
        ),
    ),
    # 12. Pook morel
    ForageableItem(
        name="Pook morel",
        forage_type=ForageType.FUNGI,
        description="Small, spongy morels with a distinctive pook-face pattern",
        smell="Mildly fungal with grassy notes",
        taste="Buttery when sautéed",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Named for their resemblance to pook faces; harmless",
        ),
    ),
    # 13. Redslob
    ForageableItem(
        name="Redslob",
        forage_type=ForageType.FUNGI,
        description="Crimson, gelatinous mass that quivers when touched",
        smell="Faintly sour, like vinegar",
        taste="Tangy and surprisingly refreshing",
        effect=ConsumptionEffect(
            effect_type=EffectType.HEALING,
            description="Mildly restorative; heals 1 HP if eaten fresh",
            modifier=1,
        ),
    ),
    # 14. Sage toe
    ForageableItem(
        name="Sage toe",
        forage_type=ForageType.FUNGI,
        description="Gnarled, toe-shaped mushroom with a wrinkled grey cap",
        smell="Herbal and medicinal, like dried sage",
        taste="Bitter but wholesome",
        effect=ConsumptionEffect(
            effect_type=EffectType.POISON_RESISTANCE,
            description="Grants +1 to saves vs poison for 4 hours",
            modifier=1,
            duration_hours=4,
            save_type="poison",
        ),
    ),
    # 15. Shrieker spawn
    ForageableItem(
        name="Shrieker spawn",
        forage_type=ForageType.FUNGI,
        description="Tiny purple mushrooms that emit a faint squeak when picked",
        smell="Sharp and acidic",
        taste="Sour with an unpleasant aftertaste",
        effect=ConsumptionEffect(
            effect_type=EffectType.NAUSEA,
            description="Causes mild nausea if more than 3 are consumed",
            condition="if 3+ consumed",
        ),
    ),
    # 16. Stinkhorn
    ForageableItem(
        name="Stinkhorn",
        forage_type=ForageType.FUNGI,
        description="Phallic mushroom covered in dark green slime",
        smell="Revolting carrion stench",
        taste="Once cleaned, surprisingly mild and pleasant",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="The smell is far worse than the taste",
        ),
    ),
    # 17. Treasure chanterelle
    ForageableItem(
        name="Treasure chanterelle",
        forage_type=ForageType.FUNGI,
        description="Golden, vase-shaped mushroom with forked ridges",
        smell="Fruity and apricot-like",
        taste="Delicately peppery with fruity notes",
        effect=ConsumptionEffect(
            effect_type=EffectType.VALUABLE,
            description="Highly sought after by fine dining establishments",
            gold_value="1d4",
        ),
    ),
    # 18. Velvet shank
    ForageableItem(
        name="Velvet shank",
        forage_type=ForageType.FUNGI,
        description="Orange-brown caps with dark, velvety stems",
        smell="Mild and woodsy",
        taste="Tender with a slightly gelatinous texture",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Can survive frost, found even in winter",
        ),
    ),
    # 19. Witch's butter
    ForageableItem(
        name="Witch's butter",
        forage_type=ForageType.FUNGI,
        description="Bright yellow-orange gelatinous blobs on dead wood",
        smell="Neutral, almost odorless",
        taste="Bland but fills the belly",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Said to appear where witches have passed",
        ),
    ),
    # 20. Wood ear
    ForageableItem(
        name="Wood ear",
        forage_type=ForageType.FUNGI,
        description="Brown, ear-shaped jelly fungus on elder branches",
        smell="Earthy and damp",
        taste="Crunchy and absorbent, takes on other flavors well",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Popular in soups and stews throughout Dolmenwood",
        ),
    ),
]


# =============================================================================
# EDIBLE PLANTS TABLE (d20) - Campaign Book p119
# =============================================================================

EDIBLE_PLANTS: list[ForageableItem] = [
    # 1. Barb cone
    ForageableItem(
        name="Barb cone",
        forage_type=ForageType.PLANT,
        description="Spiky pine cone with edible seeds hidden within",
        smell="Fresh pine and resin",
        taste="Nutty and slightly resinous",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Requires patience to extract the seeds",
        ),
    ),
    # 2. Bent leek
    ForageableItem(
        name="Bent leek",
        forage_type=ForageType.PLANT,
        description="Wild leek with a characteristic curved stem",
        smell="Pungent onion and garlic",
        taste="Sharp and savory, excellent in cooking",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="A staple wild vegetable in Dolmenwood cuisine",
        ),
    ),
    # 3. Bitter chestnut
    ForageableItem(
        name="Bitter chestnut",
        forage_type=ForageType.PLANT,
        description="Small, dark chestnuts in spiny husks",
        smell="Mild and nutty",
        taste="Bitter raw, sweet when roasted",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Must be roasted to remove bitterness",
        ),
    ),
    # 4. Crake berries
    ForageableItem(
        name="Crake berries",
        forage_type=ForageType.PLANT,
        description="Clusters of small black berries on thorny bushes",
        smell="Sweet and slightly fermented",
        taste="Tart and juicy with many seeds",
        effect=ConsumptionEffect(
            effect_type=EffectType.INTOXICATION,
            description="Mildly intoxicating if eaten in large quantities",
            condition="if large quantity consumed",
        ),
    ),
    # 5. Cuckoo sorrel
    ForageableItem(
        name="Cuckoo sorrel",
        forage_type=ForageType.PLANT,
        description="Clover-like leaves with a distinctive arrow shape",
        smell="Fresh and green",
        taste="Pleasantly sour, refreshing",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Popular as a thirst-quenching trail snack",
        ),
    ),
    # 6. Drude root
    ForageableItem(
        name="Drude root",
        forage_type=ForageType.PLANT,
        description="Gnarled root with bark-like skin",
        smell="Earthy and slightly sweet",
        taste="Starchy and filling, like potato",
        effect=ConsumptionEffect(
            effect_type=EffectType.ENERGY,
            description="Provides sustained energy; no fatigue for 4 hours",
            duration_hours=4,
        ),
    ),
    # 7. Fairy thimble
    ForageableItem(
        name="Fairy thimble",
        forage_type=ForageType.PLANT,
        description="Tiny purple bell-shaped flowers on tall stalks",
        smell="Intensely sweet and floral",
        taste="Honey-like nectar",
        effect=ConsumptionEffect(
            effect_type=EffectType.PSYCHEDELIA,
            description="May cause fey visions after dark",
            condition="after dark",
        ),
    ),
    # 8. Fen pepper
    ForageableItem(
        name="Fen pepper",
        forage_type=ForageType.PLANT,
        description="Small red pods growing in marshy areas",
        smell="Sharp and spicy",
        taste="Intensely hot, used sparingly as seasoning",
        effect=ConsumptionEffect(
            effect_type=EffectType.WARMTH,
            description="Causes intense warmth; resistance to cold for 2 hours",
            duration_hours=2,
        ),
    ),
    # 9. Gorger bean
    ForageableItem(
        name="Gorger bean",
        forage_type=ForageType.PLANT,
        description="Large, meaty beans in twisted pods",
        smell="Earthy and substantial",
        taste="Rich and filling, almost meaty",
        effect=ConsumptionEffect(
            effect_type=EffectType.DOUBLE_NOURISHMENT,
            description="Very filling; counts as 2 rations worth of food",
        ),
    ),
    # 10. Hob nut
    ForageableItem(
        name="Hob nut",
        forage_type=ForageType.PLANT,
        description="Small hazelnuts with an iridescent sheen",
        smell="Sweet and nutty with a strange undertone",
        taste="Delicious but leaves an odd tingling sensation",
        effect=ConsumptionEffect(
            effect_type=EffectType.SAVE_PENALTY,
            description="Grants -2 to saves vs magic for 8 hours",
            modifier=-2,
            duration_hours=8,
            save_type="magic",
        ),
    ),
    # 11. Jellycup
    ForageableItem(
        name="Jellycup",
        forage_type=ForageType.PLANT,
        description="Translucent, cup-shaped flowers filled with sweet gel",
        smell="Honey and citrus",
        taste="Sweet and tangy jelly",
        effect=ConsumptionEffect(
            effect_type=EffectType.PSYCHEDELIA,
            description="Causes vivid hallucinations after dark",
            condition="after dark",
        ),
    ),
    # 12. Moon carrot
    ForageableItem(
        name="Moon carrot",
        forage_type=ForageType.PLANT,
        description="Pale white root vegetable that glows faintly",
        smell="Sweet and carroty",
        taste="Crisp and sweet, sweeter than normal carrots",
        effect=ConsumptionEffect(
            effect_type=EffectType.VISION,
            description="Grants improved night vision for 4 hours",
            duration_hours=4,
        ),
    ),
    # 13. Nettlecress
    ForageableItem(
        name="Nettlecress",
        forage_type=ForageType.PLANT,
        description="Stinging nettles with edible cress-like leaves",
        smell="Sharp and peppery",
        taste="Peppery and nutritious when cooked",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Must be cooked to remove stinging properties",
        ),
    ),
    # 14. Pigwort
    ForageableItem(
        name="Pigwort",
        forage_type=ForageType.PLANT,
        description="Broad, fleshy leaves often found near pig trails",
        smell="Green and slightly musky",
        taste="Bland but filling",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Named because pigs love to root for it",
        ),
    ),
    # 15. Ramp
    ForageableItem(
        name="Ramp",
        forage_type=ForageType.PLANT,
        description="Broad-leaved wild onion with a red-tinged stem",
        smell="Strong garlic-onion combination",
        taste="Pungent and flavorful, prized in cooking",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="A spring delicacy throughout the Wood",
        ),
    ),
    # 16. Sloe berry
    ForageableItem(
        name="Sloe berry",
        forage_type=ForageType.PLANT,
        description="Small, dark blue berries with a dusty bloom",
        smell="Faintly sweet",
        taste="Extremely tart, mouth-puckering",
        effect=ConsumptionEffect(
            effect_type=EffectType.VALUABLE,
            description="Used to make sloe gin; taverns will buy them",
            gold_value="1d4",
        ),
    ),
    # 17. Sweetmoss
    ForageableItem(
        name="Sweetmoss",
        forage_type=ForageType.PLANT,
        description="Soft, verdant moss with a sugary coating",
        smell="Fresh rain and honey",
        taste="Sweet and refreshing, melts on the tongue",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="A favorite treat of woodland sprites",
        ),
    ),
    # 18. Wanderer's friend
    ForageableItem(
        name="Wanderer's friend",
        forage_type=ForageType.PLANT,
        description="Hardy green herb that grows along forest paths",
        smell="Clean and medicinal",
        taste="Bitter but restorative",
        effect=ConsumptionEffect(
            effect_type=EffectType.HEALING,
            description="Heals 1 HP when chewed fresh",
            modifier=1,
        ),
    ),
    # 19. Wild garlic
    ForageableItem(
        name="Wild garlic",
        forage_type=ForageType.PLANT,
        description="Broad leaves and white star-shaped flowers",
        smell="Powerful garlic scent that fills the air",
        taste="Mild garlic flavor, less pungent than cultivated",
        effect=ConsumptionEffect(
            effect_type=EffectType.NONE,
            description="Common but always welcome for cooking",
        ),
    ),
    # 20. Wood apple
    ForageableItem(
        name="Wood apple",
        forage_type=ForageType.PLANT,
        description="Small, gnarled crabapple with mottled skin",
        smell="Tart apple with woody notes",
        taste="Sour and astringent, better when cooked",
        effect=ConsumptionEffect(
            effect_type=EffectType.SLEEP,
            description="Mildly sedative; may cause drowsiness",
            duration_hours=4,
        ),
    ),
]


# =============================================================================
# FORAGING FUNCTIONS
# =============================================================================

def roll_forage_type() -> ForageType:
    """
    Roll to determine whether fungi or plants are found.

    Per Campaign Book p118: Roll d6
    - 1-3: Fungi
    - 4-6: Plants

    Returns:
        ForageType indicating fungi or plant
    """
    roll = DiceRoller.roll("1d6", "Forage type (1-3=fungi, 4-6=plants)").total
    return ForageType.FUNGI if roll <= 3 else ForageType.PLANT


def roll_foraged_item(forage_type: Optional[ForageType] = None) -> ForageableItem:
    """
    Roll for a specific foraged item.

    Args:
        forage_type: Optional type to roll on. If None, rolls for type first.

    Returns:
        The ForageableItem found
    """
    if forage_type is None:
        forage_type = roll_forage_type()

    table = EDIBLE_FUNGI if forage_type == ForageType.FUNGI else EDIBLE_PLANTS
    table_name = "Edible Fungi" if forage_type == ForageType.FUNGI else "Edible Plants"

    roll = DiceRoller.roll("1d20", f"{table_name} table").total
    # d20 roll of 1-20 maps to index 0-19
    index = roll - 1

    return table[index]


def roll_forage_quantity() -> int:
    """
    Roll for the quantity of rations found.

    Per Campaign Book p118: 1d6 rations found on successful forage.

    Returns:
        Number of rations (1-6)
    """
    return DiceRoller.roll("1d6", "Foraging yield (rations)").total


def get_foraged_item_by_name(name: str) -> Optional[ForageableItem]:
    """
    Look up a forageable item by name.

    Args:
        name: Name of the item (case-insensitive)

    Returns:
        The ForageableItem if found, None otherwise
    """
    name_lower = name.lower()

    for item in EDIBLE_FUNGI:
        if item.name.lower() == name_lower:
            return item

    for item in EDIBLE_PLANTS:
        if item.name.lower() == name_lower:
            return item

    return None


def get_all_fungi() -> list[ForageableItem]:
    """Return all edible fungi items."""
    return EDIBLE_FUNGI.copy()


def get_all_plants() -> list[ForageableItem]:
    """Return all edible plant items."""
    return EDIBLE_PLANTS.copy()


def is_fungi(item: ForageableItem) -> bool:
    """Check if an item is fungi (for Colliggwyld bonus)."""
    return item.forage_type == ForageType.FUNGI
