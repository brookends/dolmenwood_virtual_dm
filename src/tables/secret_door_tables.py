"""
Secret Door tables and data for Dolmenwood Virtual DM.

Implements the secret door system per Campaign Book p104:
- 3 secret door types (Hidden, Hidden Mechanism, Doubly Hidden)
- 20 secret door locations (d20 table)
- 20 mechanical opening mechanisms (d20 table)
- 20 magical opening mechanisms (d20 table)
- Clue system (visual, functional, symbolic)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.data_models import DiceRoller


class SecretDoorType(str, Enum):
    """
    Secret door types per Campaign Book p104.

    Three distinct types with different discovery requirements:
    - HIDDEN_DOOR: Door itself is hidden, once found it can be opened normally
    - HIDDEN_MECHANISM: Door is visible but requires hidden mechanism to open
    - DOUBLY_HIDDEN: Both the door AND the mechanism are hidden
    """

    HIDDEN_DOOR = "hidden_door"
    HIDDEN_MECHANISM = "hidden_mechanism"
    DOUBLY_HIDDEN = "doubly_hidden"


class MechanismType(str, Enum):
    """
    Opening mechanism types per Campaign Book p104.

    - NONE: No special mechanism needed (for simple hidden doors)
    - MECHANICAL: Physical mechanism (lever, button, pressure plate, etc.)
    - MAGICAL: Magical mechanism (password, riddle, gesture, etc.)
    """

    NONE = "none"
    MECHANICAL = "mechanical"
    MAGICAL = "magical"


class SecretDoorLocation(str, Enum):
    """
    Secret door locations per Campaign Book p104 (d20 table).

    Where the secret door is concealed.
    """

    POOL_BASE = "pool_base"  # 1: At base of pool
    BEHIND_DOOR = "behind_door"  # 2: Behind large open door
    BEHIND_MIRROR = "behind_mirror"  # 3: Behind mirror
    BEHIND_PICTURE = "behind_picture"  # 4: Behind picture frame
    BEHIND_TAPESTRY = "behind_tapestry"  # 5: Behind tapestry
    BENEATH_STATUE = "beneath_statue"  # 6: Beneath large statue
    BENEATH_RUG = "beneath_rug"  # 7: Beneath rug
    CONCEALED_SLIME = "concealed_slime"  # 8: Concealed by slime
    FALSE_CLOSET = "false_closet"  # 9: False closet back
    FALSE_COFFER = "false_coffer"  # 10: False coffer base
    STATUE_MOUTH = "statue_mouth"  # 11: In giant statue's mouth
    MOSAIC_SECTION = "mosaic_section"  # 12: Mosaic section
    MURAL_SECTION = "mural_section"  # 13: Mural section
    OVERGROWN_LICHEN = "overgrown_lichen"  # 14: Overgrown with lichen
    OVERGROWN_MOSS = "overgrown_moss"  # 15: Overgrown with moss
    OVERGROWN_ROOTS = "overgrown_roots"  # 16: Overgrown with roots
    PIVOTING_BOOKSHELF = "pivoting_bookshelf"  # 17: Pivoting bookshelf
    PIVOTING_CHIMNEY = "pivoting_chimney"  # 18: Pivoting chimney back
    SEAMLESS_PILLAR = "seamless_pillar"  # 19: Seamless pillar section
    SEAMLESS_WALL = "seamless_wall"  # 20: Seamless wall section


class MechanicalMechanism(str, Enum):
    """
    Mechanical opening mechanisms per Campaign Book p104 (d20 table).
    """

    FILL_DRAIN_BASIN = "fill_drain_basin"  # 1: Fill or drain basin
    OPEN_STATUE_MOUTH = "open_statue_mouth"  # 2: Open statue's mouth
    PIVOT_STATUE_ARM = "pivot_statue_arm"  # 3: Pivot statue's arm
    PLACE_ITEM_ALTAR = "place_item_altar"  # 4: Place item on altar
    PLACE_ITEM_LEDGE = "place_item_ledge"  # 5: Place item on ledge
    POKE_SLOT = "poke_slot"  # 6: Poke thin object in slot
    PRESS_MOSAIC_BUTTON = "press_mosaic_button"  # 7: Press button in mosaic
    PRESS_WALL_BUTTON = "press_wall_button"  # 8: Press button in wall
    PRESS_BRICK = "press_brick"  # 9: Press jutting wall brick
    PRESS_CEILING_SLAB = "press_ceiling_slab"  # 10: Press slab in ceiling
    PULL_LEVER_GRATE = "pull_lever_grate"  # 11: Pull lever in grate
    PULL_FINGER_HOLE = "pull_finger_hole"  # 12: Pull on finger hole
    PULL_ROPE_BRICK = "pull_rope_brick"  # 13: Pull rope behind brick
    PULL_TORCH_SCONCE = "pull_torch_sconce"  # 14: Pull torch sconce
    PUT_COIN_SLOT = "put_coin_slot"  # 15: Put coin in slot
    REMOVE_ITEM_ALTAR = "remove_item_altar"  # 16: Remove item from altar
    STEP_CORNER_SLAB = "step_corner_slab"  # 17: Step on corner slab
    STEP_DAIS_TILE = "step_dais_tile"  # 18: Step on dais tile
    TURN_STATUE = "turn_statue"  # 19: Turn statue
    WEIGHT_PRESSURE_PLATE = "weight_pressure_plate"  # 20: Weight pressure plate


class MagicalMechanism(str, Enum):
    """
    Magical opening mechanisms per Campaign Book p104 (d20 table).
    """

    ANSWER_RIDDLE = "answer_riddle"  # 1: Answer riddle
    ARRANGE_ALTAR_ITEMS = "arrange_altar_items"  # 2: Arrange items on altar
    BOW_BEFORE_DOOR = "bow_before_door"  # 3: Bow before door
    COPY_MURAL_MOTIONS = "copy_mural_motions"  # 4: Copy motions in mural
    COVER_MIRROR = "cover_mirror"  # 5: Cover mirror
    DRINK_CHALICE = "drink_chalice"  # 6: Drink liquid in chalice
    DRIP_BLOOD_ALTAR = "drip_blood_altar"  # 7: Drip blood on altar
    FEED_STATUE_BEER = "feed_statue_beer"  # 8: Feed beer to statue
    INSCRIBE_CHALK_ARROW = "inscribe_chalk_arrow"  # 9: Inscribe chalk arrow
    KISS_STATUE = "kiss_statue"  # 10: Kiss statue or painting
    LAY_DOWN_ARMS = "lay_down_arms"  # 11: Lay down arms
    LIGHT_ALTAR_CANDLE = "light_altar_candle"  # 12: Light candle on altar
    MAKE_GESTURE = "make_gesture"  # 13: Make certain gesture
    PLAY_PIANO = "play_piano"  # 14: Play on nearby piano
    PUT_GEM_STATUE_EYE = "put_gem_statue_eye"  # 15: Put gem in statue's eye
    PUT_GOLD_STATUE_PALM = "put_gold_statue_palm"  # 16: Put gold in statue's palm
    RECITE_INSCRIPTION = "recite_inscription"  # 17: Recite inscription
    RING_BELL = "ring_bell"  # 18: Ring nearby bell
    SINGING = "singing"  # 19: Singing
    SPEAK_COMMAND_WORD = "speak_command_word"  # 20: Speak command word


class ClueType(str, Enum):
    """
    Types of clues that can hint at secret doors per Campaign Book p104.
    """

    VISUAL = "visual"  # Scuff marks, footprints, sounds, stains, roots
    FUNCTIONAL = "functional"  # Guards/patrols suggest presence
    SYMBOLIC = "symbolic"  # Inscriptions, murals, statues hint at opening


class PortalType(str, Enum):
    """
    Types of secret portals beyond standard doors per Campaign Book p104.
    """

    DOOR = "door"  # Standard wall door
    TRAPDOOR_FLOOR = "trapdoor_floor"  # Trapdoor in floor
    TRAPDOOR_CEILING = "trapdoor_ceiling"  # Trapdoor in ceiling
    HATCH = "hatch"  # Small hatch
    SPYHOLE = "spyhole"  # Observation hole
    PIPE = "pipe"  # Crawlspace/pipe
    CLOSET = "closet"  # Hidden closet/compartment


# =============================================================================
# LOCATION DESCRIPTIONS
# =============================================================================

LOCATION_DESCRIPTIONS: dict[SecretDoorLocation, dict[str, Any]] = {
    SecretDoorLocation.POOL_BASE: {
        "name": "At base of pool",
        "description": "A secret passage hidden beneath the murky waters of a pool",
        "discovery_hint": "The pool seems deeper than expected in one corner",
        "requires_diving": True,
    },
    SecretDoorLocation.BEHIND_DOOR: {
        "name": "Behind large open door",
        "description": "A secret door concealed behind an ordinary door when it's open",
        "discovery_hint": "The wall behind the open door has unusual markings",
        "requires_door_open": True,
    },
    SecretDoorLocation.BEHIND_MIRROR: {
        "name": "Behind mirror",
        "description": "A secret passage hidden behind an ornate mirror",
        "discovery_hint": "The mirror seems to reflect light oddly at the edges",
    },
    SecretDoorLocation.BEHIND_PICTURE: {
        "name": "Behind picture frame",
        "description": "A secret door concealed behind a large painting or portrait",
        "discovery_hint": "The painting hangs slightly crooked despite its heavy frame",
    },
    SecretDoorLocation.BEHIND_TAPESTRY: {
        "name": "Behind tapestry",
        "description": "A secret passage hidden behind a hanging tapestry",
        "discovery_hint": "A draft stirs the bottom of the tapestry",
    },
    SecretDoorLocation.BENEATH_STATUE: {
        "name": "Beneath large statue",
        "description": "A trapdoor or passage hidden beneath a large statue",
        "discovery_hint": "The floor around the statue shows wear in an odd pattern",
        "portal_type": PortalType.TRAPDOOR_FLOOR,
    },
    SecretDoorLocation.BENEATH_RUG: {
        "name": "Beneath rug",
        "description": "A trapdoor hidden beneath a large rug or carpet",
        "discovery_hint": "The rug lies perfectly flat despite the uneven floor",
        "portal_type": PortalType.TRAPDOOR_FLOOR,
    },
    SecretDoorLocation.CONCEALED_SLIME: {
        "name": "Concealed by slime",
        "description": "A door hidden behind a layer of dungeon slime and mold",
        "discovery_hint": "The slime growth seems unnaturally regular in one area",
    },
    SecretDoorLocation.FALSE_CLOSET: {
        "name": "False closet back",
        "description": "The back wall of a closet that swings open",
        "discovery_hint": "The closet seems shallower than the wall thickness suggests",
        "portal_type": PortalType.CLOSET,
    },
    SecretDoorLocation.FALSE_COFFER: {
        "name": "False coffer base",
        "description": "A hidden compartment beneath a large chest or coffer",
        "discovery_hint": "The chest seems heavier than its contents would suggest",
        "portal_type": PortalType.HATCH,
    },
    SecretDoorLocation.STATUE_MOUTH: {
        "name": "In giant statue's mouth",
        "description": "A passage accessed through a large statue's open mouth",
        "discovery_hint": "The statue's mouth is large enough to crawl through",
    },
    SecretDoorLocation.MOSAIC_SECTION: {
        "name": "Mosaic section",
        "description": "A section of decorative floor mosaic that lifts away",
        "discovery_hint": "One section of the mosaic has slightly different grout",
        "portal_type": PortalType.TRAPDOOR_FLOOR,
    },
    SecretDoorLocation.MURAL_SECTION: {
        "name": "Mural section",
        "description": "Part of a wall mural that conceals a hidden door",
        "discovery_hint": "The paint in one section of the mural is less faded",
    },
    SecretDoorLocation.OVERGROWN_LICHEN: {
        "name": "Overgrown with lichen",
        "description": "A door hidden behind years of lichen growth",
        "discovery_hint": "The lichen grows in an unusually rectangular pattern",
    },
    SecretDoorLocation.OVERGROWN_MOSS: {
        "name": "Overgrown with moss",
        "description": "A door concealed by thick moss growth",
        "discovery_hint": "The moss here is damper than elsewhere, fed by a draft",
    },
    SecretDoorLocation.OVERGROWN_ROOTS: {
        "name": "Overgrown with roots",
        "description": "A passage hidden behind a curtain of hanging roots",
        "discovery_hint": "The roots part more easily in one spot",
    },
    SecretDoorLocation.PIVOTING_BOOKSHELF: {
        "name": "Pivoting bookshelf",
        "description": "A classic bookshelf that swings open to reveal a passage",
        "discovery_hint": "One book seems fixed in place, unable to be removed",
    },
    SecretDoorLocation.PIVOTING_CHIMNEY: {
        "name": "Pivoting chimney back",
        "description": "The back wall of a fireplace that rotates open",
        "discovery_hint": "The soot patterns suggest something moves in the hearth",
    },
    SecretDoorLocation.SEAMLESS_PILLAR: {
        "name": "Seamless pillar section",
        "description": "A section of a pillar that opens to reveal a hidden space",
        "discovery_hint": "One pillar sounds hollow when tapped",
        "portal_type": PortalType.CLOSET,
    },
    SecretDoorLocation.SEAMLESS_WALL: {
        "name": "Seamless wall section",
        "description": "A perfectly concealed door in an apparently solid wall",
        "discovery_hint": "Faint air currents emanate from a hairline crack",
    },
}


# =============================================================================
# MECHANISM DESCRIPTIONS
# =============================================================================

MECHANICAL_MECHANISM_DESCRIPTIONS: dict[MechanicalMechanism, dict[str, Any]] = {
    MechanicalMechanism.FILL_DRAIN_BASIN: {
        "name": "Fill or drain basin",
        "description": "A basin that must be filled with water or drained to trigger the mechanism",
        "action_required": "Fill the basin with water or pull the drain plug",
        "clue": "The basin has a drain hole and water stains at a specific level",
    },
    MechanicalMechanism.OPEN_STATUE_MOUTH: {
        "name": "Open statue's mouth",
        "description": "A statue whose hinged jaw opens the secret door",
        "action_required": "Pull down on the statue's jaw to open its mouth",
        "clue": "The statue's jaw seems slightly loose",
    },
    MechanicalMechanism.PIVOT_STATUE_ARM: {
        "name": "Pivot statue's arm",
        "description": "A statue with a moveable arm that activates the door",
        "action_required": "Rotate or pull the statue's arm",
        "clue": "The statue's arm is worn smooth from handling",
    },
    MechanicalMechanism.PLACE_ITEM_ALTAR: {
        "name": "Place item on altar",
        "description": "An altar that requires a specific item to be placed upon it",
        "action_required": "Place the correct item on the altar",
        "clue": "A depression in the altar matches a specific shape",
        "requires_item": True,
    },
    MechanicalMechanism.PLACE_ITEM_LEDGE: {
        "name": "Place item on ledge",
        "description": "A ledge with a pressure mechanism requiring weight",
        "action_required": "Place a heavy enough item on the ledge",
        "clue": "A small ledge juts out with scratch marks from objects",
        "requires_item": True,
    },
    MechanicalMechanism.POKE_SLOT: {
        "name": "Poke thin object in slot",
        "description": "A narrow slot that requires a thin object to trigger",
        "action_required": "Insert a thin object (dagger, key, wire) into the slot",
        "clue": "A narrow slot in the wall is just wide enough for a blade",
        "requires_item": True,
    },
    MechanicalMechanism.PRESS_MOSAIC_BUTTON: {
        "name": "Press button in mosaic",
        "description": "A disguised button hidden within a mosaic pattern",
        "action_required": "Press the specific tile in the mosaic",
        "clue": "One tile in the mosaic is slightly raised and a different color",
    },
    MechanicalMechanism.PRESS_WALL_BUTTON: {
        "name": "Press button in wall",
        "description": "A stone button disguised as part of the wall",
        "action_required": "Press the protruding stone in the wall",
        "clue": "One stone protrudes slightly and is worn smooth",
    },
    MechanicalMechanism.PRESS_BRICK: {
        "name": "Press jutting wall brick",
        "description": "A brick that depresses to open the door",
        "action_required": "Push in the loose brick",
        "clue": "One brick sits slightly proud of the others",
    },
    MechanicalMechanism.PRESS_CEILING_SLAB: {
        "name": "Press slab in ceiling",
        "description": "A ceiling tile that must be pushed up",
        "action_required": "Use a pole or jump to press the ceiling slab",
        "clue": "One ceiling tile has finger marks at its edges",
        "requires_reach": True,
    },
    MechanicalMechanism.PULL_LEVER_GRATE: {
        "name": "Pull lever in grate",
        "description": "A lever hidden within a floor grate",
        "action_required": "Reach into the grate and pull the lever",
        "clue": "A floor grate has something metallic visible within",
    },
    MechanicalMechanism.PULL_FINGER_HOLE: {
        "name": "Pull on finger hole",
        "description": "A small hole that serves as a grip to pull the door",
        "action_required": "Insert finger and pull",
        "clue": "A small hole in the stone is worn smooth inside",
    },
    MechanicalMechanism.PULL_ROPE_BRICK: {
        "name": "Pull rope behind brick",
        "description": "A rope hidden behind a removable brick",
        "action_required": "Remove the brick and pull the rope behind it",
        "clue": "One brick can be wiggled loose",
    },
    MechanicalMechanism.PULL_TORCH_SCONCE: {
        "name": "Pull torch sconce",
        "description": "A torch holder that acts as a lever",
        "action_required": "Pull down on the torch sconce",
        "clue": "The torch sconce is more ornate than others and sits at an angle",
    },
    MechanicalMechanism.PUT_COIN_SLOT: {
        "name": "Put coin in slot",
        "description": "A coin slot that triggers the mechanism when paid",
        "action_required": "Insert a coin into the slot",
        "clue": "A narrow slot is sized exactly for a coin",
        "requires_item": True,
        "item_type": "coin",
    },
    MechanicalMechanism.REMOVE_ITEM_ALTAR: {
        "name": "Remove item from altar",
        "description": "An altar where removing an item opens the door",
        "action_required": "Remove the item from the altar",
        "clue": "An item rests on the altar with visible mechanism beneath",
    },
    MechanicalMechanism.STEP_CORNER_SLAB: {
        "name": "Step on corner slab",
        "description": "A floor slab in the corner that acts as a pressure plate",
        "action_required": "Step on or place weight on the corner slab",
        "clue": "A floor slab in the corner is slightly raised",
    },
    MechanicalMechanism.STEP_DAIS_TILE: {
        "name": "Step on dais tile",
        "description": "A specific tile on a raised platform that triggers the door",
        "action_required": "Step on the correct dais tile",
        "clue": "One tile on the dais is worn more than the others",
    },
    MechanicalMechanism.TURN_STATUE: {
        "name": "Turn statue",
        "description": "A statue on a rotating base",
        "action_required": "Rotate the statue on its base",
        "clue": "Circular scratches on the floor around the statue's base",
    },
    MechanicalMechanism.WEIGHT_PRESSURE_PLATE: {
        "name": "Weight pressure plate",
        "description": "A pressure plate requiring sufficient weight",
        "action_required": "Place enough weight on the pressure plate",
        "clue": "A section of floor sits slightly higher than the rest",
    },
}


MAGICAL_MECHANISM_DESCRIPTIONS: dict[MagicalMechanism, dict[str, Any]] = {
    MagicalMechanism.ANSWER_RIDDLE: {
        "name": "Answer riddle",
        "description": "A magical guardian that poses a riddle",
        "action_required": "Speak the answer to the riddle aloud",
        "clue": "An inscription poses a cryptic question",
        "requires_answer": True,
    },
    MagicalMechanism.ARRANGE_ALTAR_ITEMS: {
        "name": "Arrange items on altar",
        "description": "Items on an altar must be arranged in a specific pattern",
        "action_required": "Arrange the items in the correct order or pattern",
        "clue": "Items on the altar seem deliberately misarranged",
    },
    MagicalMechanism.BOW_BEFORE_DOOR: {
        "name": "Bow before door",
        "description": "The door requires a gesture of respect to open",
        "action_required": "Bow or kneel before the door",
        "clue": "Worn patches on the floor suggest where people have knelt",
    },
    MagicalMechanism.COPY_MURAL_MOTIONS: {
        "name": "Copy motions in mural",
        "description": "A mural depicting figures in specific poses that must be mimicked",
        "action_required": "Mimic the poses shown in the mural",
        "clue": "A mural shows figures in a sequence of unusual poses",
    },
    MagicalMechanism.COVER_MIRROR: {
        "name": "Cover mirror",
        "description": "A mirror that must be covered or obscured",
        "action_required": "Cover the mirror with cloth or block its reflection",
        "clue": "A mirror seems to watch you, and cloth lies nearby",
    },
    MagicalMechanism.DRINK_CHALICE: {
        "name": "Drink liquid in chalice",
        "description": "A chalice containing liquid that must be drunk",
        "action_required": "Drink from the chalice",
        "clue": "A chalice contains liquid that never evaporates",
        "may_be_dangerous": True,
    },
    MagicalMechanism.DRIP_BLOOD_ALTAR: {
        "name": "Drip blood on altar",
        "description": "An altar requiring a blood offering",
        "action_required": "Drip blood onto the altar",
        "clue": "The altar has a groove leading to a dark stain",
        "requires_sacrifice": True,
    },
    MagicalMechanism.FEED_STATUE_BEER: {
        "name": "Feed beer to statue",
        "description": "A statue that must be given an offering of beer or ale",
        "action_required": "Pour beer into the statue's mouth or offering bowl",
        "clue": "The statue holds an empty cup and smells faintly of hops",
        "requires_item": True,
        "item_type": "beer",
    },
    MagicalMechanism.INSCRIBE_CHALK_ARROW: {
        "name": "Inscribe chalk arrow",
        "description": "Drawing a specific symbol activates the door",
        "action_required": "Draw a chalk arrow pointing at the door",
        "clue": "Faint chalk marks and dust suggest previous drawings",
        "requires_item": True,
        "item_type": "chalk",
    },
    MagicalMechanism.KISS_STATUE: {
        "name": "Kiss statue or painting",
        "description": "A statue or painting that responds to a kiss",
        "action_required": "Kiss the statue or painting",
        "clue": "The statue's lips or a figure in the painting are worn smooth",
    },
    MagicalMechanism.LAY_DOWN_ARMS: {
        "name": "Lay down arms",
        "description": "The door only opens for those who disarm",
        "action_required": "Set down all weapons before the door",
        "clue": "An inscription reads 'Enter in peace' or similar",
    },
    MagicalMechanism.LIGHT_ALTAR_CANDLE: {
        "name": "Light candle on altar",
        "description": "A candle on an altar that must be lit",
        "action_required": "Light the candle on the altar",
        "clue": "An unlit candle sits on the altar with matches nearby",
        "requires_fire": True,
    },
    MagicalMechanism.MAKE_GESTURE: {
        "name": "Make certain gesture",
        "description": "A specific hand gesture opens the door",
        "action_required": "Make the correct gesture",
        "clue": "A carving shows a hand in an unusual position",
    },
    MagicalMechanism.PLAY_PIANO: {
        "name": "Play on nearby piano",
        "description": "A piano or musical instrument that must be played",
        "action_required": "Play a specific tune or any music on the instrument",
        "clue": "A dusty piano sits nearby with one key more worn than others",
    },
    MagicalMechanism.PUT_GEM_STATUE_EYE: {
        "name": "Put gem in statue's eye",
        "description": "A statue with an empty eye socket",
        "action_required": "Place a gem in the statue's empty eye socket",
        "clue": "The statue has one eye missing, the socket sized for a gem",
        "requires_item": True,
        "item_type": "gem",
    },
    MagicalMechanism.PUT_GOLD_STATUE_PALM: {
        "name": "Put gold in statue's palm",
        "description": "A statue with an outstretched palm awaiting tribute",
        "action_required": "Place gold in the statue's hand",
        "clue": "The statue's palm is outstretched and has gold residue",
        "requires_item": True,
        "item_type": "gold",
    },
    MagicalMechanism.RECITE_INSCRIPTION: {
        "name": "Recite inscription",
        "description": "Words inscribed nearby that must be spoken aloud",
        "action_required": "Read the inscription aloud",
        "clue": "An inscription in an ancient language adorns the wall",
    },
    MagicalMechanism.RING_BELL: {
        "name": "Ring nearby bell",
        "description": "A bell that must be rung to open the door",
        "action_required": "Ring the bell",
        "clue": "A small bell hangs nearby, its clapper worn",
    },
    MagicalMechanism.SINGING: {
        "name": "Singing",
        "description": "The door responds to song",
        "action_required": "Sing a song, hymn, or specific tune",
        "clue": "Musical notes are carved around the doorframe",
    },
    MagicalMechanism.SPEAK_COMMAND_WORD: {
        "name": "Speak command word",
        "description": "A password that must be spoken",
        "action_required": "Speak the command word",
        "clue": "Faint magical runes glow when approached",
        "requires_password": True,
    },
}


# =============================================================================
# CLUE GENERATION
# =============================================================================

VISUAL_CLUES: list[str] = [
    "Scuff marks on the floor lead to the wall",
    "Footprints in the dust end abruptly at the wall",
    "Faint sounds can be heard from beyond the wall",
    "A draft of air comes from a hairline crack",
    "Roots or vines cross what appears to be a threshold",
    "The stone here is a slightly different color",
    "Cobwebs are broken in a doorway-shaped pattern",
    "The dust on the floor is disturbed in a rectangular area",
    "Moisture seeps from an invisible crack",
    "The wall sounds hollow when tapped",
]

FUNCTIONAL_CLUES: list[str] = [
    "Guards patrol this area more frequently than seems necessary",
    "A creature was seen disappearing into this wall",
    "The room layout suggests a space behind this wall",
    "Enemies seem to appear from nowhere in this area",
    "The architecture doesn't match the building's exterior",
    "This dead-end seems too short for the building's size",
]

SYMBOLIC_CLUES: list[str] = [
    "An inscription nearby reads 'The way opens to those who seek'",
    "A mural depicts figures walking through a solid wall",
    "A statue points toward a section of wall",
    "Carved arrows on the floor point to the wall",
    "A riddle inscribed on a plaque hints at a hidden path",
    "The symbol on the wall matches one on a key you found",
]


# =============================================================================
# SECRET DOOR DATA CLASS
# =============================================================================

@dataclass
class SecretDoor:
    """
    Complete secret door definition per Campaign Book p104.

    Tracks both the door and its opening mechanism, supporting all three
    secret door types: hidden door, hidden mechanism, and doubly hidden.
    """

    door_id: str
    name: str
    door_type: SecretDoorType
    location: SecretDoorLocation
    portal_type: PortalType = PortalType.DOOR

    # Mechanism details
    mechanism_type: MechanismType = MechanismType.NONE
    mechanism: Optional[str] = None  # Enum value as string
    mechanism_details: dict[str, Any] = field(default_factory=dict)

    # For magical mechanisms that need specific answers
    password: Optional[str] = None
    riddle_answer: Optional[str] = None

    # Discovery state
    door_discovered: bool = False
    mechanism_discovered: bool = False
    door_opened: bool = False

    # Clues available to players
    visual_clues: list[str] = field(default_factory=list)
    functional_clues: list[str] = field(default_factory=list)
    symbolic_clues: list[str] = field(default_factory=list)

    # What room this leads to
    destination_room: Optional[str] = None
    direction: Optional[str] = None  # north, south, etc. for wall doors

    def is_fully_discovered(self) -> bool:
        """Check if both door and mechanism (if any) are discovered."""
        if self.door_type == SecretDoorType.HIDDEN_DOOR:
            return self.door_discovered
        elif self.door_type == SecretDoorType.HIDDEN_MECHANISM:
            return self.mechanism_discovered
        else:  # DOUBLY_HIDDEN
            return self.door_discovered and self.mechanism_discovered

    def can_be_opened(self) -> bool:
        """Check if the door can currently be opened."""
        if self.door_opened:
            return True
        if not self.is_fully_discovered():
            return False
        if self.mechanism_type == MechanismType.NONE:
            return True
        # For mechanism doors, discovery allows interaction but not auto-open
        return self.mechanism_discovered

    def get_required_action(self) -> Optional[str]:
        """Get the action required to open this door."""
        if self.mechanism_type == MechanismType.NONE:
            return None
        if self.mechanism_type == MechanismType.MECHANICAL:
            mech = MechanicalMechanism(self.mechanism)
            return MECHANICAL_MECHANISM_DESCRIPTIONS[mech].get("action_required")
        else:  # MAGICAL
            mech = MagicalMechanism(self.mechanism)
            return MAGICAL_MECHANISM_DESCRIPTIONS[mech].get("action_required")

    def get_mechanism_clue(self) -> Optional[str]:
        """Get the clue for discovering the mechanism."""
        if self.mechanism_type == MechanismType.NONE:
            return None
        if self.mechanism_type == MechanismType.MECHANICAL:
            mech = MechanicalMechanism(self.mechanism)
            return MECHANICAL_MECHANISM_DESCRIPTIONS[mech].get("clue")
        else:  # MAGICAL
            mech = MagicalMechanism(self.mechanism)
            return MAGICAL_MECHANISM_DESCRIPTIONS[mech].get("clue")

    def requires_item(self) -> Optional[str]:
        """Check if opening requires a specific item type."""
        if self.mechanism_type == MechanismType.NONE:
            return None

        details = self.mechanism_details
        if details.get("requires_item"):
            return details.get("item_type", "item")
        return None

    def get_all_clues(self) -> list[dict[str, Any]]:
        """Get all available clues for this secret door."""
        clues = []
        for clue in self.visual_clues:
            clues.append({"type": ClueType.VISUAL.value, "clue": clue})
        for clue in self.functional_clues:
            clues.append({"type": ClueType.FUNCTIONAL.value, "clue": clue})
        for clue in self.symbolic_clues:
            clues.append({"type": ClueType.SYMBOLIC.value, "clue": clue})
        return clues

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "door_id": self.door_id,
            "name": self.name,
            "door_type": self.door_type.value,
            "location": self.location.value,
            "portal_type": self.portal_type.value,
            "mechanism_type": self.mechanism_type.value,
            "mechanism": self.mechanism,
            "mechanism_details": self.mechanism_details,
            "door_discovered": self.door_discovered,
            "mechanism_discovered": self.mechanism_discovered,
            "door_opened": self.door_opened,
            "destination_room": self.destination_room,
            "direction": self.direction,
            "clues": self.get_all_clues(),
            "can_be_opened": self.can_be_opened(),
            "required_action": self.get_required_action(),
        }


# =============================================================================
# GENERATION FUNCTIONS
# =============================================================================

def roll_secret_door_type(dice: Optional[DiceRoller] = None) -> SecretDoorType:
    """
    Roll for secret door type.

    Distribution:
    - 1-3: Hidden door (50%)
    - 4-5: Hidden mechanism (33%)
    - 6: Doubly hidden (17%)
    """
    dice = dice or DiceRoller()
    roll = dice.roll_d6(1, "secret door type").total

    if roll <= 3:
        return SecretDoorType.HIDDEN_DOOR
    elif roll <= 5:
        return SecretDoorType.HIDDEN_MECHANISM
    else:
        return SecretDoorType.DOUBLY_HIDDEN


def roll_location(dice: Optional[DiceRoller] = None) -> SecretDoorLocation:
    """Roll for secret door location (d20)."""
    dice = dice or DiceRoller()
    roll = dice.roll("1d20", "secret door location").total

    locations = list(SecretDoorLocation)
    return locations[roll - 1]


def roll_mechanism_type(door_type: SecretDoorType,
                        dice: Optional[DiceRoller] = None) -> MechanismType:
    """
    Roll for mechanism type based on door type.

    Hidden doors usually have no mechanism.
    Hidden mechanism and doubly hidden always have a mechanism.
    """
    dice = dice or DiceRoller()

    if door_type == SecretDoorType.HIDDEN_DOOR:
        # 1-4: No mechanism, 5-6: Has mechanism
        roll = dice.roll_d6(1, "hidden door mechanism").total
        if roll <= 4:
            return MechanismType.NONE
        else:
            # 50/50 mechanical vs magical
            mech_roll = dice.roll_d6(1, "mechanism type").total
            return MechanismType.MECHANICAL if mech_roll <= 3 else MechanismType.MAGICAL
    else:
        # Must have mechanism
        roll = dice.roll_d6(1, "mechanism type").total
        return MechanismType.MECHANICAL if roll <= 4 else MechanismType.MAGICAL


def roll_mechanical_mechanism(dice: Optional[DiceRoller] = None) -> MechanicalMechanism:
    """Roll for mechanical mechanism (d20)."""
    dice = dice or DiceRoller()
    roll = dice.roll("1d20", "mechanical mechanism").total

    mechanisms = list(MechanicalMechanism)
    return mechanisms[roll - 1]


def roll_magical_mechanism(dice: Optional[DiceRoller] = None) -> MagicalMechanism:
    """Roll for magical mechanism (d20)."""
    dice = dice or DiceRoller()
    roll = dice.roll("1d20", "magical mechanism").total

    mechanisms = list(MagicalMechanism)
    return mechanisms[roll - 1]


def generate_clues(location: SecretDoorLocation,
                   mechanism_type: MechanismType,
                   mechanism: Optional[str],
                   dice: Optional[DiceRoller] = None) -> dict[str, list[str]]:
    """
    Generate clues for a secret door.

    Returns visual, functional, and symbolic clues based on the door's
    location and mechanism.
    """
    dice = dice or DiceRoller()
    clues: dict[str, list[str]] = {
        "visual": [],
        "functional": [],
        "symbolic": [],
    }

    # Add location-specific visual clue
    loc_info = LOCATION_DESCRIPTIONS.get(location, {})
    if "discovery_hint" in loc_info:
        clues["visual"].append(loc_info["discovery_hint"])

    # Add 1-2 random visual clues
    num_visual = dice.roll("1d2", "num visual clues").total
    for _ in range(num_visual):
        roll = dice.roll(f"1d{len(VISUAL_CLUES)}", "visual clue").total
        clue = VISUAL_CLUES[roll - 1]
        if clue not in clues["visual"]:
            clues["visual"].append(clue)

    # 50% chance of functional clue
    if dice.roll_d6(1, "functional clue").total <= 3:
        roll = dice.roll(f"1d{len(FUNCTIONAL_CLUES)}", "functional clue").total
        clues["functional"].append(FUNCTIONAL_CLUES[roll - 1])

    # Add mechanism-specific symbolic clue if there's a mechanism
    if mechanism_type != MechanismType.NONE and mechanism:
        if mechanism_type == MechanismType.MECHANICAL:
            mech_enum = MechanicalMechanism(mechanism)
            mech_clue = MECHANICAL_MECHANISM_DESCRIPTIONS[mech_enum].get("clue")
        else:
            mech_enum = MagicalMechanism(mechanism)
            mech_clue = MAGICAL_MECHANISM_DESCRIPTIONS[mech_enum].get("clue")

        if mech_clue:
            clues["symbolic"].append(mech_clue)

    # Add random symbolic clue
    if dice.roll_d6(1, "symbolic clue").total <= 2:
        roll = dice.roll(f"1d{len(SYMBOLIC_CLUES)}", "symbolic clue").total
        clues["symbolic"].append(SYMBOLIC_CLUES[roll - 1])

    return clues


def generate_secret_door(
    door_id: Optional[str] = None,
    destination_room: Optional[str] = None,
    direction: Optional[str] = None,
    dice: Optional[DiceRoller] = None,
    # Optional overrides
    door_type: Optional[SecretDoorType] = None,
    location: Optional[SecretDoorLocation] = None,
    mechanism_type: Optional[MechanismType] = None,
) -> SecretDoor:
    """
    Generate a complete secret door with all properties.

    Args:
        door_id: Unique identifier (auto-generated if not provided)
        destination_room: Room ID this door leads to
        direction: Direction from current room (north, south, etc.)
        dice: Optional dice roller
        door_type: Override random door type
        location: Override random location
        mechanism_type: Override random mechanism type

    Returns:
        A fully configured SecretDoor
    """
    dice = dice or DiceRoller()

    # Generate or use provided values
    if door_type is None:
        door_type = roll_secret_door_type(dice)

    if location is None:
        location = roll_location(dice)

    if mechanism_type is None:
        mechanism_type = roll_mechanism_type(door_type, dice)

    # Get location info
    loc_info = LOCATION_DESCRIPTIONS.get(location, {})
    portal_type = PortalType(loc_info.get("portal_type", PortalType.DOOR))

    # Generate mechanism if needed
    mechanism: Optional[str] = None
    mechanism_details: dict[str, Any] = {}
    password: Optional[str] = None
    riddle_answer: Optional[str] = None

    if mechanism_type == MechanismType.MECHANICAL:
        mech_enum = roll_mechanical_mechanism(dice)
        mechanism = mech_enum.value
        mechanism_details = dict(MECHANICAL_MECHANISM_DESCRIPTIONS[mech_enum])

    elif mechanism_type == MechanismType.MAGICAL:
        mech_enum = roll_magical_mechanism(dice)
        mechanism = mech_enum.value
        mechanism_details = dict(MAGICAL_MECHANISM_DESCRIPTIONS[mech_enum])

        # Generate password/answer if needed
        if mechanism_details.get("requires_password"):
            password = _generate_password(dice)
        if mechanism_details.get("requires_answer"):
            riddle_answer = _generate_riddle_answer(dice)

    # Generate clues
    clues = generate_clues(location, mechanism_type, mechanism, dice)

    # Create door ID if not provided
    if door_id is None:
        door_id = f"secret_door_{location.value}"
        if direction:
            door_id = f"{door_id}_{direction}"

    # Build name
    name = f"Secret {portal_type.value.replace('_', ' ').title()}"
    if loc_info.get("name"):
        name = f"{name} ({loc_info['name']})"

    return SecretDoor(
        door_id=door_id,
        name=name,
        door_type=door_type,
        location=location,
        portal_type=portal_type,
        mechanism_type=mechanism_type,
        mechanism=mechanism,
        mechanism_details=mechanism_details,
        password=password,
        riddle_answer=riddle_answer,
        visual_clues=clues["visual"],
        functional_clues=clues["functional"],
        symbolic_clues=clues["symbolic"],
        destination_room=destination_room,
        direction=direction,
    )


def _generate_password(dice: DiceRoller) -> str:
    """Generate a random password/command word."""
    prefixes = ["Mel", "Zar", "Vor", "Keth", "Dra", "Fel", "Gor", "Ith", "Nex", "Pha"]
    suffixes = ["orn", "ax", "un", "eth", "or", "ix", "al", "um", "is", "ar"]

    p_roll = dice.roll(f"1d{len(prefixes)}", "password prefix").total
    s_roll = dice.roll(f"1d{len(suffixes)}", "password suffix").total

    return prefixes[p_roll - 1] + suffixes[s_roll - 1]


def _generate_riddle_answer(dice: DiceRoller) -> str:
    """Generate a simple riddle answer."""
    answers = [
        "shadow", "time", "echo", "silence", "darkness",
        "moon", "star", "wind", "flame", "water",
        "death", "life", "truth", "dream", "memory",
    ]
    roll = dice.roll(f"1d{len(answers)}", "riddle answer").total
    return answers[roll - 1]


# =============================================================================
# INTERACTION RESOLUTION
# =============================================================================

@dataclass
class SecretDoorInteraction:
    """Result of interacting with a secret door mechanism."""

    success: bool
    door_opened: bool = False
    message: str = ""
    mechanism_triggered: bool = False
    item_consumed: bool = False
    item_required: Optional[str] = None
    damage_taken: int = 0  # For dangerous mechanisms


def attempt_open_mechanism(
    door: SecretDoor,
    action: str,
    item_used: Optional[str] = None,
    spoken_word: Optional[str] = None,
    dice: Optional[DiceRoller] = None,
) -> SecretDoorInteraction:
    """
    Attempt to open a secret door via its mechanism.

    Args:
        door: The secret door to open
        action: Description of what the player is doing
        item_used: Item being used (if any)
        spoken_word: Word being spoken (if any)
        dice: Optional dice roller

    Returns:
        SecretDoorInteraction with results
    """
    dice = dice or DiceRoller()

    # Check if door is already open
    if door.door_opened:
        return SecretDoorInteraction(
            success=True,
            door_opened=True,
            message="The secret door is already open.",
        )

    # Check if mechanism is discovered
    if door.mechanism_type != MechanismType.NONE and not door.mechanism_discovered:
        return SecretDoorInteraction(
            success=False,
            message="You haven't discovered how to open this door yet.",
        )

    # No mechanism needed - just open
    if door.mechanism_type == MechanismType.NONE:
        door.door_opened = True
        return SecretDoorInteraction(
            success=True,
            door_opened=True,
            message="The secret door swings open.",
        )

    # Get mechanism details
    if door.mechanism_type == MechanismType.MECHANICAL:
        mech_enum = MechanicalMechanism(door.mechanism)
        mech_info = MECHANICAL_MECHANISM_DESCRIPTIONS[mech_enum]
    else:
        mech_enum = MagicalMechanism(door.mechanism)
        mech_info = MAGICAL_MECHANISM_DESCRIPTIONS[mech_enum]

    # Check for required items
    if mech_info.get("requires_item"):
        required_type = mech_info.get("item_type", "item")
        if item_used is None:
            return SecretDoorInteraction(
                success=False,
                message=f"This mechanism requires a {required_type}.",
                item_required=required_type,
            )
        # Check if correct item type (simplified check)
        if required_type.lower() not in item_used.lower():
            return SecretDoorInteraction(
                success=False,
                message=f"The mechanism doesn't respond to the {item_used}.",
                item_required=required_type,
            )

    # Check for password/command word
    if mech_info.get("requires_password"):
        if spoken_word is None:
            return SecretDoorInteraction(
                success=False,
                message="This door requires a command word to open.",
            )
        if spoken_word.lower() != door.password.lower():
            return SecretDoorInteraction(
                success=False,
                message="Nothing happens. Perhaps that's not the right word.",
            )

    # Check for riddle answer
    if mech_info.get("requires_answer"):
        if spoken_word is None:
            return SecretDoorInteraction(
                success=False,
                message="The door poses a riddle that must be answered.",
            )
        if spoken_word.lower() != door.riddle_answer.lower():
            return SecretDoorInteraction(
                success=False,
                message="The riddle remains unsolved. The door stays shut.",
            )

    # Check for dangerous mechanisms
    damage = 0
    if mech_info.get("may_be_dangerous"):
        # 1-in-6 chance of taking damage
        danger_roll = dice.roll_d6(1, "dangerous mechanism").total
        if danger_roll == 1:
            damage = dice.roll("1d6", "mechanism damage").total

    # Success! Open the door
    door.door_opened = True
    door.mechanism_discovered = True

    return SecretDoorInteraction(
        success=True,
        door_opened=True,
        message=f"The mechanism activates and the secret door opens!",
        mechanism_triggered=True,
        item_consumed=mech_info.get("requires_item", False),
        damage_taken=damage,
    )


def search_for_secret_door(
    door: SecretDoor,
    searcher_class: str = "",
    search_bonus: int = 0,
    dice: Optional[DiceRoller] = None,
) -> dict[str, Any]:
    """
    Attempt to find a secret door through searching.

    Per Campaign Book:
    - Base 2-in-6 chance to find secret doors
    - Thieves get improved chances at higher levels

    Args:
        door: The secret door being searched for
        searcher_class: Class of the searching character
        search_bonus: Bonus to search roll (from class abilities)
        dice: Optional dice roller

    Returns:
        Dictionary with search results
    """
    dice = dice or DiceRoller()

    result: dict[str, Any] = {
        "door_found": False,
        "mechanism_found": False,
        "clues_found": [],
        "message": "",
    }

    # Already fully discovered
    if door.is_fully_discovered():
        result["message"] = "This area has already been thoroughly searched."
        result["door_found"] = door.door_discovered
        result["mechanism_found"] = door.mechanism_discovered
        return result

    # Calculate success threshold (2-in-6 base)
    threshold = 2 + search_bonus

    # Search for door if not found
    if not door.door_discovered:
        if door.door_type in (SecretDoorType.HIDDEN_DOOR, SecretDoorType.DOUBLY_HIDDEN):
            roll = dice.roll_d6(1, "find secret door").total
            if roll <= threshold:
                door.door_discovered = True
                result["door_found"] = True
                loc_info = LOCATION_DESCRIPTIONS.get(door.location, {})
                result["message"] = f"You discover a {loc_info.get('name', 'secret door')}!"
            else:
                # Partial success - provide a clue
                if roll <= 4 and door.visual_clues:
                    clue_idx = dice.roll(f"1d{len(door.visual_clues)}", "clue").total - 1
                    result["clues_found"].append({
                        "type": "visual",
                        "clue": door.visual_clues[clue_idx],
                    })
                    result["message"] = "Something catches your attention..."
        else:
            # HIDDEN_MECHANISM type - door is already visible
            door.door_discovered = True
            result["door_found"] = True

    # Search for mechanism if door found but mechanism not
    if door.door_discovered and not door.mechanism_discovered:
        if door.mechanism_type != MechanismType.NONE:
            roll = dice.roll_d6(1, "find mechanism").total
            if roll <= threshold:
                door.mechanism_discovered = True
                result["mechanism_found"] = True
                mech_clue = door.get_mechanism_clue()
                if mech_clue:
                    result["message"] += f" You notice: {mech_clue}"
            else:
                # Provide symbolic clue about mechanism
                if roll <= 4 and door.symbolic_clues:
                    clue_idx = dice.roll(f"1d{len(door.symbolic_clues)}", "clue").total - 1
                    result["clues_found"].append({
                        "type": "symbolic",
                        "clue": door.symbolic_clues[clue_idx],
                    })

    if not result["message"]:
        if result["clues_found"]:
            result["message"] = "Your search reveals some clues..."
        else:
            result["message"] = "You find nothing of interest."

    return result
