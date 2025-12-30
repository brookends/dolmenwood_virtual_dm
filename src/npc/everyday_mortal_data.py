"""
Everyday Mortal data definitions for Dolmenwood.

Contains type definitions, roll tables, and special mechanics for
non-adventuring NPCs encountered in the wilds.

All Everyday Mortals share the same stat block:
- Level 1, AC 10, HP 1d4 (2), Saves D12 R13 H14 B15 S16
- Attack: Weapon (-1), Speed 40, Morale 6, XP 10
- Weapons: Club (d4), dagger (d4), or staff (d4)
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# =============================================================================
# SHARED STAT BLOCK
# =============================================================================

EVERYDAY_MORTAL_STATS = {
    "level": 1,
    "armor_class": 10,
    "hp_dice": "1d4",
    "hp_average": 2,
    "saves": {
        "doom": 12,
        "ray": 13,
        "hold": 14,
        "blast": 15,
        "spell": 16,
    },
    "attack_bonus": -1,
    "speed": 40,
    "morale": 6,
    "xp": 10,
    "weapons": ["Club (1d4)", "Dagger (1d4)", "Staff (1d4)"],
}


# =============================================================================
# BASIC DETAILS TABLES (Optional for any everyday mortal)
# =============================================================================

BASIC_DETAILS = {
    "sex": {
        "die": "d4",
        "entries": {
            1: "Female",
            2: "Female",
            3: "Male",
            4: "Male",
        }
    },
    "age": {
        "die": "d6",
        "entries": {
            1: "Child",
            2: "Youth",
            3: "Adult",
            4: "Mature",
            5: "Old",
            6: "Decrepit",
        }
    },
    "dress": {
        "die": "d8",
        "entries": {
            1: "Drab",
            2: "Elaborate",
            3: "Formal",
            4: "Messy",
            5: "Pristine",
            6: "Scant",
            7: "Tatty",
            8: "Uniform",
        }
    },
    "feature": {
        "die": "d10",
        "entries": {
            1: "Bald",
            2: "Beautiful",
            3: "Hairy",
            4: "Lost limb",
            5: "Muscular",
            6: "Obese",
            7: "Scrawny",
            8: "Short",
            9: "Tall",
            10: "Ugly",
        }
    },
    "kindred": {
        "die": "d12",
        "entries": {
            1: "Breggle",
            2: "Breggle",
            3: "Breggle",
            4: "Human",
            5: "Human",
            6: "Human",
            7: "Human",
            8: "Human",
            9: "Human",
            10: "Human",
            11: "Mossling",
            12: "Mossling",
        }
    },
}


# =============================================================================
# EVERYDAY MORTAL TYPES
# =============================================================================

EVERYDAY_MORTAL_TYPES = {
    "angler": {
        "name": "Angler",
        "description": "Fisherfolk bearing nets, rods, tackle, bait boxes, and buckets. If encountered on water, anglers are afloat on rafts or rowing boats.",
        "kindred_preference": ["human"],
        "special_mechanics": [
            {
                "name": "Fresh Fish",
                "chance": "3-in-6",
                "effect": "Carrying 2d6 rations of fresh fish (1gp per ration)",
            }
        ],
        "roll_tables": {},
    },

    "crier": {
        "name": "Crier",
        "description": "Flamboyantly dressed officials carrying news to local settlements. Sometimes accompanied by fanfare-blowers.",
        "kindred_preference": ["human", "breggle"],
        "special_mechanics": [],
        "roll_tables": {
            "news": {
                "die": "d6",
                "entries": {
                    1: "25% taxation of the mercantile and adventuring classes.",
                    2: "A noble is missing, 2,000gp reward.",
                    3: "Berryld Ramius to wed the victor of Ramius' tourney.",
                    4: "Lady Zoemina (duke's daughter) to marry Lord Ramius.",
                    5: "Strong youths to be trained for impending war.",
                    6: "Upcoming 2 week religious festival, travel banned.",
                }
            }
        },
    },

    "fortune_teller": {
        "name": "Fortune-Teller",
        "description": "Minor oracles and seers—some genuine, some deluded, and some charlatans. Wander from settlement to settlement, consulting the fates in return for a small consideration.",
        "kindred_preference": ["human"],
        "special_mechanics": [
            {
                "name": "Consultation Fee",
                "effect": "1d10gp (traditionally paid in silver)",
            }
        ],
        "roll_tables": {
            "result": {
                "die": "d6",
                "entries": {
                    1: "Weal. The proposed course of action ends well.",
                    2: "Weal. The proposed course of action ends well.",
                    3: "Woe. The proposed course of action ends in ruin.",
                    4: "Woe. The proposed course of action ends in ruin.",
                    5: "Truth. Weal or woe, per the Referee's judgement of the likely outcome. Alternatively, a cryptic message or riddle.",
                    6: "Truth. Weal or woe, per the Referee's judgement of the likely outcome. Alternatively, a cryptic message or riddle.",
                }
            },
            "method": {
                "die": "d12",
                "entries": {
                    1: "Astrology",
                    2: "Card reading",
                    3: "Casting bones",
                    4: "Crystal ball",
                    5: "Fire gazing",
                    6: "Ley line dowsing",
                    7: "Melting wax",
                    8: "Oracular vision",
                    9: "Palm reading",
                    10: "Sparrow entrails",
                    11: "Spirit board",
                    12: "Tea leaves",
                }
            },
        },
    },

    "lost_soul": {
        "name": "Lost Soul",
        "description": "Befuddled individuals utterly unaware of their current whereabouts, trying to find their way back home.",
        "kindred_preference": ["human"],
        "special_mechanics": [],
        "roll_tables": {
            "fate": {
                "die": "d6",
                "entries": {
                    1: "Escaped from the realms of the dead.",
                    2: "Kidnapped by fairies as a child, recently expelled.",
                    3: "Lost in the wilds, starving and ragged.",
                    4: "Slept for 1d100 years, recently awoke.",
                    5: "Teleported by ley line discharge, now lost.",
                    6: "Wandered in Fairy for 2d100 years.",
                }
            },
            "home": {
                "die": "d10",
                "entries": {
                    1: "Castle Brackenwold (Hex 1508)",
                    2: "Dreg (Hex 1110)",
                    3: "Drigbolton (Hex 0702)",
                    4: "Fort Vulgar (Hex 0604)",
                    5: "Lankshorn (Hex 0710)",
                    6: "Meagre's Reach (Hex 1703)",
                    7: "Odd (Hex 1403)",
                    8: "Prigwort (Hex 1106)",
                    9: "Woodcutters' Encampment (Hex 1109)",
                    10: "Servant at noble estate (roll 1d4: 1. Bogwitt Manor hex 1210, 2. Hall of Sleep hex 1304, 3. Harrowmoor Keep hex 1105, 4. Nodding Castle hex 0210)",
                }
            },
        },
    },

    "merchant": {
        "name": "Merchant",
        "description": "Organised traders who travel between settlements in well-armed convoys, buying and selling trade goods.",
        "kindred_preference": ["human", "breggle"],
        "special_mechanics": [
            {
                "name": "Wagons",
                "effect": "1 wagon per merchant encountered",
            },
            {
                "name": "Guards",
                "effect": "Number of guards determined by wealth roll",
            },
        ],
        "roll_tables": {
            "wealth_and_guards": {
                "die": "d6",
                "entries": {
                    1: {
                        "wealth": "1d100gp",
                        "guards": "2 soldiers per wagon",
                    },
                    2: {
                        "wealth": "1d100x2gp",
                        "guards": "3 soldiers per wagon",
                    },
                    3: {
                        "wealth": "1d100x3gp, 1 gem",
                        "guards": "4 soldiers per wagon, 1 lieutenant per 5 wagons",
                    },
                    4: {
                        "wealth": "1d100x4gp, 1d3 gems",
                        "guards": "5 soldiers per wagon, 2 lieutenants per 5 wagons",
                    },
                    5: {
                        "wealth": "1d100x5gp, 1d4 gems, 1 art object",
                        "guards": "6 soldiers per wagon, 2 lieutenants per 4 wagons, 1 captain",
                    },
                    6: {
                        "wealth": "1d100x6gp, 2d4 gems, 1d4 art objects",
                        "guards": "7 soldiers per wagon, 2 lieutenants per 3 wagons, 1 captain",
                    },
                }
            },
        },
    },

    "pedlar": {
        "name": "Pedlar",
        "description": "Roving vendors of all manner of items, both quotidian and singular.",
        "kindred_preference": ["human"],
        "special_mechanics": [
            {
                "name": "Trade Goods",
                "effect": "Roll on mundane or herbal trade goods tables (DCB)",
            }
        ],
        "roll_tables": {},
    },

    "pilgrim": {
        "name": "Pilgrim",
        "description": "Zealous adherents of the Pluritine Church heading to a site of religious significance.",
        "kindred_preference": ["human", "breggle"],
        "special_mechanics": [
            {
                "name": "Flagellants",
                "chance": "2-in-6",
                "effect": "Pilgrims are flagellants",
            }
        ],
        "roll_tables": {
            "destination": {
                "die": "d6",
                "entries": {
                    1: "Church of St Pastery (Lankshorn)",
                    2: "Church of St Waylaine (Prigwort)",
                    3: "Lost shrine (in the correct location)",
                    4: "Lost shrine (in an incorrect location)",
                    5: "The Cathedral of St Signis (Castle Brackenwold)",
                    6: "Three Martyrs Minster (High-Hankle)",
                }
            },
        },
    },

    "priest": {
        "name": "Priest",
        "description": "Non-adventuring clergy of the Pluritine Church travelling from one settlement to another.",
        "kindred_preference": ["human", "breggle"],
        "special_mechanics": [],
        "roll_tables": {
            "function": {
                "die": "d12",
                "entries": {
                    1: "Administrator",
                    2: "Alms collector",
                    3: "Cantor",
                    4: "Confessor",
                    5: "Evangelist",
                    6: "Herbalist",
                    7: "Lichward",
                    8: "Mendicant",
                    9: "Preacher",
                    10: "Scholar",
                    11: "Scribe",
                    12: "Tithe collector",
                }
            },
        },
    },

    "villager": {
        "name": "Villager",
        "description": "Common folk going about their day-to-day business, seldom venturing far from their home.",
        "kindred_preference": ["human"],
        "special_mechanics": [],
        "roll_tables": {
            "activity": {
                "die": "d12",
                "entries": {
                    1: "Calling for a lost child",
                    2: "Chasing errant swine",
                    3: "Collecting eggs",
                    4: "Cutting wood",
                    5: "Fetching water",
                    6: "Foraging",
                    7: "Hanging corn dollies",
                    8: "Hunting fowl",
                    9: "Masked capering",
                    10: "Praying to a saint",
                    11: "Trysting",
                    12: "Whittling",
                }
            },
        },
    },
}


# =============================================================================
# CREATURE ACTIVITY TABLE (Optional - applies to any encounter)
# =============================================================================

CREATURE_ACTIVITY = {
    "die": "d20",
    "entries": {
        1: "Celebrating",
        2: "Chasing ?",  # Roll another encounter for the other creature
        3: "Constructing",
        4: "Defecating",
        5: "Dying / wounded",
        6: "Fleeing from ?",  # Roll another encounter
        7: "Hallucinating",
        8: "Hunting / foraging",
        9: "In combat with ?",  # Roll another encounter
        10: "Journey / pilgrimage",
        11: "Lost / exploring",
        12: "Marking territory",
        13: "Mating / courting",
        14: "Negotiating with ?",  # Roll another encounter
        15: "Patrolling / guarding",
        16: "Resting / camping",
        17: "Ritual / magic",
        18: "Sleeping",
        19: "Trapped / imprisoned",
        20: "Washing",
    },
    "note": "Question mark (?) means roll another encounter to determine the other creature involved.",
}


@dataclass
class EverydayMortalType:
    """Definition of an everyday mortal type."""
    type_id: str
    name: str
    description: str
    kindred_preference: list[str]
    special_mechanics: list[dict]
    roll_tables: dict[str, dict]


def get_mortal_type(type_id: str) -> Optional[EverydayMortalType]:
    """Get an everyday mortal type definition by ID."""
    data = EVERYDAY_MORTAL_TYPES.get(type_id)
    if not data:
        return None

    return EverydayMortalType(
        type_id=type_id,
        name=data["name"],
        description=data["description"],
        kindred_preference=data["kindred_preference"],
        special_mechanics=data["special_mechanics"],
        roll_tables=data["roll_tables"],
    )


def get_all_mortal_types() -> list[str]:
    """Get list of all everyday mortal type IDs."""
    return list(EVERYDAY_MORTAL_TYPES.keys())
