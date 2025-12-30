"""
Sensory Details Generator for Dolmenwood Virtual DM.

Provides atmospheric and sensory narrative elements for game systems:
- Foraging: Discovery scenes, terrain atmosphere
- Fishing: Waterside ambiance, catch moments
- Hunting: Stalking tension, pursuit atmosphere
- Traps: Trigger moments, aftermath scenes
- Secret Doors: Discovery tension, mechanism interaction

These details are used to enhance LLM narration with Dolmenwood-appropriate
flavor and immersive sensory descriptions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.data_models import DiceRoller


class TimeOfDayContext(str, Enum):
    """Time context affecting sensory details."""

    DAWN = "dawn"
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    NIGHT = "night"


class WeatherContext(str, Enum):
    """Weather context affecting sensory details."""

    CLEAR = "clear"
    OVERCAST = "overcast"
    RAIN = "rain"
    MIST = "mist"
    SNOW = "snow"
    STORM = "storm"


class TerrainContext(str, Enum):
    """Terrain context for location-specific details."""

    FOREST = "forest"
    MARSH = "marsh"
    RIVER = "river"
    LAKE = "lake"
    HILLS = "hills"
    RUINS = "ruins"
    DUNGEON = "dungeon"
    FAIRY_REALM = "fairy_realm"


@dataclass
class SensoryContext:
    """
    Context for generating appropriate sensory details.

    Combines time, weather, terrain, and other factors to generate
    atmospheric descriptions appropriate to the current scene.
    """

    terrain: TerrainContext = TerrainContext.FOREST
    time_of_day: TimeOfDayContext = TimeOfDayContext.MORNING
    weather: WeatherContext = WeatherContext.CLEAR
    is_underground: bool = False
    light_level: str = "normal"  # bright, dim, dark
    season: str = "normal"  # normal, winter, autumn
    unseason_active: Optional[str] = None  # hitching, colliggwyld, chame, vague


# =============================================================================
# FORAGING SENSORY DETAILS
# =============================================================================

FORAGING_DISCOVERY_SCENES: dict[str, list[str]] = {
    "forest": [
        "Pushing through the underbrush, your eyes catch a familiar shape",
        "The dappled light reveals a hidden bounty beneath the leaves",
        "Following an animal trail leads you to an unexpected find",
        "The earthy scent guides you to a patch of growth",
        "Parting the ferns, you discover what you've been searching for",
    ],
    "marsh": [
        "Careful steps through the soggy ground reveal something promising",
        "Among the reeds and cattails, you spot an edible treasure",
        "The brackish air carries hints of something useful nearby",
        "Balancing on a tussock, you reach for your discovery",
        "The squelching mud gives way to a fortunate find",
    ],
    "hills": [
        "Scanning the rocky outcrop, a splash of color catches your eye",
        "The wind-swept grass parts to reveal hidden sustenance",
        "In the shelter of a boulder, something edible grows",
        "The thin highland soil nurtures a hardy specimen",
        "Cresting a rise, you spot what you've been seeking",
    ],
}

FORAGING_FAILURE_SCENES: list[str] = [
    "After hours of searching, nothing edible presents itself",
    "The forest yields only inedible roots and bitter leaves",
    "Every promising lead turns out to be a disappointment",
    "The land seems barren of anything nourishing today",
    "Wildlife has already claimed anything worth eating",
    "Your knowledge fails you - everything looks the same",
]

FORAGING_SEASONAL_DETAILS: dict[str, list[str]] = {
    "autumn": [
        "Fallen leaves crunch underfoot as you search",
        "The autumn colors guide you to ripe specimens",
        "The musty smell of decay mingles with earthy richness",
    ],
    "winter": [
        "Frost clings to every surface, hiding potential finds",
        "Your breath mists in the cold as you search",
        "Snow-covered ground makes foraging treacherous",
    ],
    "normal": [
        "Birdsong accompanies your search",
        "The warm air carries the scent of growing things",
        "Insects buzz around as you carefully forage",
    ],
}

FUNGI_DISCOVERY_DETAILS: list[str] = [
    "The distinctive cap emerges from the forest floor",
    "Clusters of fungi cling to a rotting log",
    "The earthy smell of mushrooms fills your nostrils",
    "Delicate spore-laden caps await careful harvesting",
    "The damp conditions have produced a fine specimen",
]

PLANT_DISCOVERY_DETAILS: list[str] = [
    "Leaves catch the light, revealing their edible nature",
    "Roots emerge from the disturbed soil",
    "The distinctive pattern confirms your identification",
    "Berries hang heavy on the stems",
    "The plant's unique aroma identifies it immediately",
]


# =============================================================================
# FISHING SENSORY DETAILS
# =============================================================================

FISHING_SCENE_SETTING: dict[str, list[str]] = {
    "river": [
        "The river's current whispers secrets as you cast your line",
        "Water rushes over mossy stones, creating perfect fishing spots",
        "The sound of the river masks all other forest sounds",
        "Sunlight dances on the rippling surface",
        "The cold spray from nearby rapids refreshes you",
    ],
    "lake": [
        "The still water mirrors the sky like polished silver",
        "Mist clings to the lake's surface in the early hours",
        "Ripples spread outward from your bobber",
        "The lake's depths hide countless secrets",
        "Reeds sway gently at the water's edge",
    ],
    "marsh": [
        "The brackish water holds strange creatures",
        "Bubbles rise from the murky depths",
        "The smell of peat mingles with the water's surface",
        "Lily pads provide cover for wary fish",
        "The still water reflects twisted trees",
    ],
}

FISHING_CATCH_MOMENTS: dict[str, list[str]] = {
    "small": [
        "A quick tug and the line goes taut",
        "The rod bends slightly with a light catch",
        "Something small but feisty takes the bait",
        "A flash of silver breaks the surface",
    ],
    "medium": [
        "The line pulls with sudden force",
        "Your rod bends dramatically as something takes hold",
        "A strong fish fights against your grip",
        "The water churns as you battle your catch",
    ],
    "large": [
        "The rod nearly flies from your hands",
        "Something massive pulls from the depths",
        "The line screams as it's dragged through the water",
        "You brace yourself against an immense force",
        "The water explodes as a huge shape surfaces",
    ],
    "magical": [
        "The water begins to glow with an otherworldly light",
        "The air crackles with fairy magic",
        "Something ancient and powerful tests your line",
        "Whispers in an unknown tongue accompany the catch",
    ],
}

FISHING_TIME_DETAILS: dict[str, list[str]] = {
    "dawn": [
        "The early light barely penetrates the mist",
        "Fish rise to feed in the quiet hours",
        "Dew clings to your fishing line",
    ],
    "dusk": [
        "The fading light turns the water to gold",
        "Evening insects draw fish to the surface",
        "Shadows lengthen across the water",
    ],
    "night": [
        "Moonlight reflects off the dark water",
        "The night sounds surround your vigil",
        "Strange things move in the depths after dark",
    ],
}


# =============================================================================
# HUNTING SENSORY DETAILS
# =============================================================================

HUNTING_TRACKING_SCENES: dict[str, list[str]] = {
    "forest": [
        "Fresh tracks indent the soft forest floor",
        "Broken twigs mark the animal's passage",
        "The musky scent of game hangs in the air",
        "Droppings indicate recent activity in the area",
        "Displaced leaves reveal a clear trail",
    ],
    "marsh": [
        "Prints pressed into the soft mud show the way",
        "Disturbed reeds point to the quarry's path",
        "Splashes in the distance betray movement",
        "The marshy ground holds tracks well",
    ],
    "hills": [
        "Disturbed scree marks the animal's passage",
        "Cropped grass indicates grazing activity",
        "A silhouette moves against the skyline",
        "Wind carries the scent of your quarry",
    ],
}

HUNTING_STALKING_SCENES: list[str] = [
    "You move carefully, testing each footfall for noise",
    "The wind is in your favor, carrying your scent away",
    "Time seems to slow as you close the distance",
    "Your heart pounds as you creep ever closer",
    "Every rustle of leaves sounds deafening to your ears",
    "You freeze as the animal pauses, sensing something",
]

HUNTING_SPOTTING_SCENES: dict[str, list[str]] = {
    "close": [
        "There! Just ahead, unaware of your presence",
        "The animal stands in a small clearing, perfectly positioned",
        "You've closed to striking distance without detection",
    ],
    "medium": [
        "Movement catches your eye through the trees",
        "The animal grazes, occasionally raising its head to listen",
        "You'll need to close the distance carefully",
    ],
    "far": [
        "A distant shape moves at the edge of visibility",
        "The quarry is far but visible - this will require patience",
        "The hunt begins in earnest with a distant sighting",
    ],
}

HUNTING_AFTERMATH_SCENES: list[str] = [
    "The hunt complete, you set to work preparing your kill",
    "Fresh game means the party will eat well tonight",
    "You offer a silent thanks for the forest's bounty",
    "The work of butchering begins under watchful eyes",
]


# =============================================================================
# TRAP SENSORY DETAILS
# =============================================================================

TRAP_TRIGGER_SCENES: dict[str, list[str]] = {
    "pressure_plate": [
        "The floor stone sinks with an ominous click",
        "Too late, you feel the tile depress beneath your foot",
        "A grinding sound echoes as the mechanism activates",
    ],
    "tripwire": [
        "Your ankle catches something taut and invisible",
        "A sharp twang announces the wire snapping",
        "The subtle line you missed now seals your fate",
    ],
    "touch": [
        "The moment your fingers make contact, something shifts",
        "The object feels wrong - and then you know why",
        "A tingling sensation precedes the trap's activation",
    ],
    "proximity": [
        "Runes flare to life as you step too close",
        "The air crackles with awakening magic",
        "An invisible barrier shatters, triggering ancient wards",
    ],
}

TRAP_DAMAGE_SCENES: dict[str, list[str]] = {
    "acid_spray": [
        "Caustic liquid sprays from hidden nozzles",
        "The hiss of dissolving stone accompanies your cry",
        "Acrid smoke rises from where the acid lands",
    ],
    "arrow_volley": [
        "Missiles streak from the darkness",
        "The whistle of arrows fills the air",
        "Thunk after thunk as arrows find their marks",
    ],
    "crushing_ceiling": [
        "The ceiling groans as it begins its descent",
        "Dust rains down as the trap engages",
        "The grinding of stone on stone fills the chamber",
    ],
    "spikes": [
        "Sharp metal springs from concealed ports",
        "Blood wells from a dozen sudden wounds",
        "The trap's teeth bite deep",
    ],
    "gas": [
        "A strange vapor hisses into the room",
        "The air grows thick with an otherworldly mist",
        "You gasp as the gas reaches your lungs",
    ],
    "pit": [
        "The floor gives way beneath you",
        "Darkness swallows you as you fall",
        "You tumble into the hungry darkness below",
    ],
    "magic": [
        "Arcane energies crackle through the air",
        "Reality warps as the spell takes hold",
        "The trap's magical payload discharges",
    ],
}

TRAP_AFTERMATH_SCENES: list[str] = [
    "The trap falls silent, its work done",
    "Dust settles in the trap's wake",
    "The mechanism's echo fades into silence",
    "A moment of stillness follows the chaos",
    "The smell of danger lingers in the air",
]

TRAP_NARROWLY_AVOIDED_SCENES: list[str] = [
    "You throw yourself aside at the last moment",
    "Instinct saves you where caution failed",
    "A desperate leap carries you to safety",
    "The trap's payload whistles past your ear",
    "You tumble clear as death claims the space you occupied",
]


# =============================================================================
# SECRET DOOR SENSORY DETAILS
# =============================================================================

SECRET_DOOR_DISCOVERY_SCENES: dict[str, list[str]] = {
    "searching": [
        "Your fingers trace an almost imperceptible seam",
        "Something about this wall doesn't feel right",
        "A hollow sound rewards your patient tapping",
        "Draft of cold air seeps from a hairline crack",
        "Years of dust fail to hide the telltale signs",
    ],
    "found_hidden_door": [
        "There! A door cleverly concealed from casual observation",
        "What appeared solid proves to be cunningly disguised",
        "The secret entrance reveals itself to your keen eye",
        "Hidden for ages, the door now stands exposed",
    ],
    "found_mechanism": [
        "A subtle click as you find the trigger",
        "The mechanism's purpose becomes clear",
        "Your probing reveals the door's secret",
        "The way to open this door finally presents itself",
    ],
}

SECRET_DOOR_MECHANISM_SCENES: dict[str, list[str]] = {
    "mechanical": [
        "Gears grind as the mechanism engages",
        "A counterweight drops somewhere in the walls",
        "Chains rattle behind the stonework",
        "The satisfying click of a well-made mechanism",
        "Hidden machinery springs to life",
    ],
    "magical": [
        "Runes flare briefly with eldritch light",
        "The air shimmers as the magic activates",
        "A whisper of power courses through the stone",
        "Ancient enchantments recognize your action",
        "The barrier of magic dissolves like morning mist",
    ],
    "password": [
        "The spoken word echoes with unexpected power",
        "The door seems to listen, then respond",
        "Ancient magic recognizes the command",
        "Your voice unlocks what hands could not",
    ],
}

SECRET_DOOR_OPENING_SCENES: list[str] = [
    "With a groan of ancient hinges, the door swings wide",
    "The wall pivots smoothly despite its apparent age",
    "Dust cascades as the hidden portal opens",
    "A rush of stale air greets you from the darkness beyond",
    "The secret passage yawns open before you",
    "Stone grinds against stone as the way opens",
]

SECRET_DOOR_CLUE_SCENES: list[str] = [
    "Something about this area demands closer inspection",
    "Your instincts whisper that not all is as it seems",
    "A detail catches your eye - worth investigating",
    "The evidence of passage ends here... or does it?",
    "Years of experience suggest a hidden truth",
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_foraging_scene(
    context: SensoryContext,
    success: bool,
    is_fungi: bool,
    dice: Optional[DiceRoller] = None,
) -> dict[str, Any]:
    """
    Generate sensory details for a foraging scene.

    Args:
        context: Current environmental context
        success: Whether foraging was successful
        is_fungi: Whether fungi or plants were found
        dice: Optional dice roller for randomization

    Returns:
        Dictionary with narrative elements:
        - discovery_scene: The moment of finding (or not finding)
        - sensory_details: Smell, sight, sound, touch details
        - seasonal_context: Season-appropriate details
        - atmosphere: General mood/atmosphere
    """
    dice = dice or DiceRoller()
    terrain = context.terrain.value

    result: dict[str, Any] = {
        "discovery_scene": "",
        "sensory_details": [],
        "seasonal_context": "",
        "atmosphere": "",
    }

    if success:
        # Get terrain-specific discovery scene
        scenes = FORAGING_DISCOVERY_SCENES.get(terrain, FORAGING_DISCOVERY_SCENES["forest"])
        idx = dice.roll(f"1d{len(scenes)}", "discovery scene").total - 1
        result["discovery_scene"] = scenes[idx]

        # Add type-specific details
        type_scenes = FUNGI_DISCOVERY_DETAILS if is_fungi else PLANT_DISCOVERY_DETAILS
        type_idx = dice.roll(f"1d{len(type_scenes)}", "type detail").total - 1
        result["sensory_details"].append(type_scenes[type_idx])

    else:
        # Failed foraging scene
        idx = dice.roll(f"1d{len(FORAGING_FAILURE_SCENES)}", "failure scene").total - 1
        result["discovery_scene"] = FORAGING_FAILURE_SCENES[idx]

    # Add seasonal context
    season_key = context.season if context.season in FORAGING_SEASONAL_DETAILS else "normal"
    seasonal = FORAGING_SEASONAL_DETAILS[season_key]
    season_idx = dice.roll(f"1d{len(seasonal)}", "seasonal detail").total - 1
    result["seasonal_context"] = seasonal[season_idx]

    return result


def get_fishing_scene(
    context: SensoryContext,
    fish_size: str = "medium",
    is_magical: bool = False,
    dice: Optional[DiceRoller] = None,
) -> dict[str, Any]:
    """
    Generate sensory details for a fishing scene.

    Args:
        context: Current environmental context
        fish_size: "small", "medium", or "large"
        is_magical: Whether the fish is magical/fairy
        dice: Optional dice roller

    Returns:
        Dictionary with narrative elements
    """
    dice = dice or DiceRoller()
    terrain = context.terrain.value
    time = context.time_of_day.value

    result: dict[str, Any] = {
        "scene_setting": "",
        "catch_moment": "",
        "time_atmosphere": "",
    }

    # Scene setting based on terrain
    water_type = terrain if terrain in FISHING_SCENE_SETTING else "river"
    scenes = FISHING_SCENE_SETTING[water_type]
    idx = dice.roll(f"1d{len(scenes)}", "scene setting").total - 1
    result["scene_setting"] = scenes[idx]

    # Catch moment based on size
    size_key = "magical" if is_magical else fish_size
    if size_key not in FISHING_CATCH_MOMENTS:
        size_key = "medium"
    catch_scenes = FISHING_CATCH_MOMENTS[size_key]
    catch_idx = dice.roll(f"1d{len(catch_scenes)}", "catch moment").total - 1
    result["catch_moment"] = catch_scenes[catch_idx]

    # Time of day atmosphere
    time_key = "dawn" if time in ["dawn", "morning"] else "dusk" if time in ["dusk", "afternoon"] else "night"
    if time_key in FISHING_TIME_DETAILS:
        time_scenes = FISHING_TIME_DETAILS[time_key]
        time_idx = dice.roll(f"1d{len(time_scenes)}", "time detail").total - 1
        result["time_atmosphere"] = time_scenes[time_idx]

    return result


def get_hunting_scene(
    context: SensoryContext,
    distance: int,
    dice: Optional[DiceRoller] = None,
) -> dict[str, Any]:
    """
    Generate sensory details for a hunting scene.

    Args:
        context: Current environmental context
        distance: Distance to quarry in feet
        dice: Optional dice roller

    Returns:
        Dictionary with narrative elements
    """
    dice = dice or DiceRoller()
    terrain = context.terrain.value

    result: dict[str, Any] = {
        "tracking_scene": "",
        "stalking_scene": "",
        "spotting_scene": "",
    }

    # Tracking scene
    terrain_key = terrain if terrain in HUNTING_TRACKING_SCENES else "forest"
    tracks = HUNTING_TRACKING_SCENES[terrain_key]
    track_idx = dice.roll(f"1d{len(tracks)}", "tracking scene").total - 1
    result["tracking_scene"] = tracks[track_idx]

    # Stalking scene
    stalk_idx = dice.roll(f"1d{len(HUNTING_STALKING_SCENES)}", "stalking scene").total - 1
    result["stalking_scene"] = HUNTING_STALKING_SCENES[stalk_idx]

    # Spotting scene based on distance
    if distance <= 30:
        distance_key = "close"
    elif distance <= 60:
        distance_key = "medium"
    else:
        distance_key = "far"
    spots = HUNTING_SPOTTING_SCENES[distance_key]
    spot_idx = dice.roll(f"1d{len(spots)}", "spotting scene").total - 1
    result["spotting_scene"] = spots[spot_idx]

    return result


def get_trap_scene(
    trigger_type: str,
    effect_type: str,
    avoided: bool = False,
    dice: Optional[DiceRoller] = None,
) -> dict[str, Any]:
    """
    Generate sensory details for a trap triggering.

    Args:
        trigger_type: Type of trigger (pressure_plate, tripwire, etc.)
        effect_type: Type of effect (acid_spray, arrows, etc.)
        avoided: Whether the trap was avoided/saved against
        dice: Optional dice roller

    Returns:
        Dictionary with narrative elements
    """
    dice = dice or DiceRoller()

    result: dict[str, Any] = {
        "trigger_scene": "",
        "effect_scene": "",
        "aftermath_scene": "",
    }

    # Trigger scene
    trigger_key = trigger_type if trigger_type in TRAP_TRIGGER_SCENES else "touch"
    triggers = TRAP_TRIGGER_SCENES[trigger_key]
    trig_idx = dice.roll(f"1d{len(triggers)}", "trigger scene").total - 1
    result["trigger_scene"] = triggers[trig_idx]

    # Effect scene (or avoided scene)
    if avoided:
        avoid_idx = dice.roll(f"1d{len(TRAP_NARROWLY_AVOIDED_SCENES)}", "avoid scene").total - 1
        result["effect_scene"] = TRAP_NARROWLY_AVOIDED_SCENES[avoid_idx]
    else:
        # Map effect types to categories
        effect_category = "magic"  # default
        if "acid" in effect_type.lower():
            effect_category = "acid_spray"
        elif "arrow" in effect_type.lower() or "spear" in effect_type.lower():
            effect_category = "arrow_volley"
        elif "crush" in effect_type.lower() or "ceiling" in effect_type.lower():
            effect_category = "crushing_ceiling"
        elif "spike" in effect_type.lower():
            effect_category = "spikes"
        elif "gas" in effect_type.lower():
            effect_category = "gas"
        elif "pit" in effect_type.lower():
            effect_category = "pit"

        effects = TRAP_DAMAGE_SCENES.get(effect_category, TRAP_DAMAGE_SCENES["magic"])
        effect_idx = dice.roll(f"1d{len(effects)}", "effect scene").total - 1
        result["effect_scene"] = effects[effect_idx]

    # Aftermath
    after_idx = dice.roll(f"1d{len(TRAP_AFTERMATH_SCENES)}", "aftermath").total - 1
    result["aftermath_scene"] = TRAP_AFTERMATH_SCENES[after_idx]

    return result


def get_secret_door_scene(
    phase: str,
    mechanism_type: Optional[str] = None,
    dice: Optional[DiceRoller] = None,
) -> dict[str, Any]:
    """
    Generate sensory details for secret door interaction.

    Args:
        phase: "searching", "found_hidden_door", "found_mechanism", "opening"
        mechanism_type: "mechanical", "magical", or "password" (for opening phase)
        dice: Optional dice roller

    Returns:
        Dictionary with narrative elements
    """
    dice = dice or DiceRoller()

    result: dict[str, Any] = {
        "scene": "",
        "atmosphere": "",
    }

    if phase in SECRET_DOOR_DISCOVERY_SCENES:
        scenes = SECRET_DOOR_DISCOVERY_SCENES[phase]
        idx = dice.roll(f"1d{len(scenes)}", f"{phase} scene").total - 1
        result["scene"] = scenes[idx]

    elif phase == "opening":
        # Mechanism-specific opening scene
        if mechanism_type and mechanism_type in SECRET_DOOR_MECHANISM_SCENES:
            mechs = SECRET_DOOR_MECHANISM_SCENES[mechanism_type]
            mech_idx = dice.roll(f"1d{len(mechs)}", "mechanism scene").total - 1
            result["scene"] = mechs[mech_idx]

        # Add opening scene
        open_idx = dice.roll(f"1d{len(SECRET_DOOR_OPENING_SCENES)}", "opening scene").total - 1
        result["atmosphere"] = SECRET_DOOR_OPENING_SCENES[open_idx]

    elif phase == "clue":
        clue_idx = dice.roll(f"1d{len(SECRET_DOOR_CLUE_SCENES)}", "clue scene").total - 1
        result["scene"] = SECRET_DOOR_CLUE_SCENES[clue_idx]

    return result


def build_narrative_hints(
    base_hints: list[str],
    sensory_scene: dict[str, Any],
) -> list[str]:
    """
    Combine base narrative hints with sensory scene details.

    Args:
        base_hints: Existing narrative hints from the resolver
        sensory_scene: Sensory details from get_*_scene functions

    Returns:
        Enhanced list of narrative hints for LLM
    """
    hints = list(base_hints)

    # Add all non-empty sensory elements
    for key, value in sensory_scene.items():
        if isinstance(value, str) and value:
            hints.append(value)
        elif isinstance(value, list):
            hints.extend([v for v in value if v])

    return hints
