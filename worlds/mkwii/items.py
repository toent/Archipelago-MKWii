"""
Items for Mario Kart Wii Archipelago World (PAL Version)

All 8 cups have per-CC unlock items. Two random starting cups are granted
during world generation (one for 50cc, one for 100cc). All other cup/CC
combinations must be received as AP items.

Star/Special/Leaf/Lightning cups also have save-file unlock bits.
Mushroom/Flower/Shell/Banana cups have no save bits and are blocked
at runtime via RaceConfig memory overwrites.

Characters and vehicles split into two tiers:
  - CHARACTER_ITEMS/KART_ITEMS/BIKE_ITEMS: have real save-file unlock bits.
    Always in the pool.
  - DEFAULT_CHARACTER_ITEMS/DEFAULT_KART_ITEMS/DEFAULT_BIKE_ITEMS: unlocked
    in vanilla, no save bits. Only added to the pool when the matching
    lock_default_* option is on, and blocked at runtime via RaceConfig
    menu-scenario overwrites, same mechanism as the base cups.
"""
from typing import NamedTuple, Dict
from BaseClasses import Item


class MKWiiItem(Item):
    game: str = "Mario Kart Wii"


class ItemData(NamedTuple):
    code: int
    classification: str = "progression"


# Base code offset
BASE_ID = 0x4D4B0000  # MKW in hex + offset


# Cup/CC unlock items
# All 8 cups, all 4 CCs. Base cups (Mushroom, Flower, Shell, Banana) are
# new additions that are blocked via RaceConfig redirect on the client side.
CUP_CC_ITEMS = {
    # 50cc
    "Mushroom Cup 50cc":    ItemData(BASE_ID + 4),
    "Flower Cup 50cc":      ItemData(BASE_ID + 5),
    "Star Cup 50cc":        ItemData(BASE_ID + 0),
    "Special Cup 50cc":     ItemData(BASE_ID + 1),
    "Shell Cup 50cc":       ItemData(BASE_ID + 6),
    "Banana Cup 50cc":      ItemData(BASE_ID + 7),
    "Leaf Cup 50cc":        ItemData(BASE_ID + 3),
    "Lightning Cup 50cc":   ItemData(BASE_ID + 2),

    # 100cc
    "Mushroom Cup 100cc":    ItemData(BASE_ID + 14),
    "Flower Cup 100cc":      ItemData(BASE_ID + 15),
    "Star Cup 100cc":        ItemData(BASE_ID + 12),
    "Special Cup 100cc":     ItemData(BASE_ID + 13),
    "Shell Cup 100cc":       ItemData(BASE_ID + 18),
    "Banana Cup 100cc":      ItemData(BASE_ID + 19),
    "Leaf Cup 100cc":        ItemData(BASE_ID + 16),
    "Lightning Cup 100cc":   ItemData(BASE_ID + 17),

    # 150cc
    "Mushroom Cup 150cc":    ItemData(BASE_ID + 24),
    "Flower Cup 150cc":      ItemData(BASE_ID + 25),
    "Star Cup 150cc":        ItemData(BASE_ID + 22),
    "Special Cup 150cc":     ItemData(BASE_ID + 23),
    "Shell Cup 150cc":       ItemData(BASE_ID + 28),
    "Banana Cup 150cc":      ItemData(BASE_ID + 29),
    "Leaf Cup 150cc":        ItemData(BASE_ID + 26),
    "Lightning Cup 150cc":   ItemData(BASE_ID + 27),

    # Mirror
    "Mushroom Cup Mirror":    ItemData(BASE_ID + 34),
    "Flower Cup Mirror":      ItemData(BASE_ID + 35),
    "Star Cup Mirror":        ItemData(BASE_ID + 32),
    "Special Cup Mirror":     ItemData(BASE_ID + 33),
    "Shell Cup Mirror":       ItemData(BASE_ID + 38),
    "Banana Cup Mirror":      ItemData(BASE_ID + 39),
    "Leaf Cup Mirror":        ItemData(BASE_ID + 36),
    "Lightning Cup Mirror":   ItemData(BASE_ID + 37),
}


# Mode unlock items
MODE_ITEMS = {
    "50cc Karts/Bikes": ItemData(BASE_ID + 40),     # 0x0038 bit 6 (0x40)
    "100cc Karts/Bikes": ItemData(BASE_ID + 41),     # 0x0038 bit 7 (0x80)
}


# Character unlocks (save-file bits)
CHARACTER_ITEMS = {
    "Character: Baby Daisy": ItemData(BASE_ID + 100),
    "Character: Baby Luigi": ItemData(BASE_ID + 101),
    "Character: Dry Bones": ItemData(BASE_ID + 102),
    "Character: Bowser Jr.": ItemData(BASE_ID + 103),
    "Character: Toadette": ItemData(BASE_ID + 104),
    "Character: King Boo": ItemData(BASE_ID + 105),
    "Character: Dry Bowser": ItemData(BASE_ID + 106),
    "Character: Funky Kong": ItemData(BASE_ID + 107),
    "Character: Rosalina": ItemData(BASE_ID + 108),
    "Character: Diddy Kong": ItemData(BASE_ID + 109),
    "Character: Daisy": ItemData(BASE_ID + 110),
    "Character: Birdo": ItemData(BASE_ID + 111),
    "Character: Mii Outfit A": ItemData(BASE_ID + 112),
    "Character: Mii Outfit B": ItemData(BASE_ID + 113),
}


# Default character unlocks (no save bits, blocked via RaceConfig redirect).
# Only added to the pool when lock_default_characters is on.
DEFAULT_CHARACTER_ITEMS = {
    "Character: Mario": ItemData(BASE_ID + 120),
    "Character: Luigi": ItemData(BASE_ID + 121),
    "Character: Peach": ItemData(BASE_ID + 122),
    "Character: Yoshi": ItemData(BASE_ID + 123),
    "Character: Toad": ItemData(BASE_ID + 124),
    "Character: Koopa Troopa": ItemData(BASE_ID + 125),
    "Character: Bowser": ItemData(BASE_ID + 126),
    "Character: Donkey Kong": ItemData(BASE_ID + 127),
    "Character: Wario": ItemData(BASE_ID + 128),
    "Character: Waluigi": ItemData(BASE_ID + 129),
    "Character: Baby Mario": ItemData(BASE_ID + 130),
    "Character: Baby Peach": ItemData(BASE_ID + 131),
}


# Kart unlocks (save-file bits)
KART_ITEMS = {
    "Kart: Turbo Blooper": ItemData(BASE_ID + 200),
    "Kart: Cheep Charger": ItemData(BASE_ID + 201),
    "Kart: Royal Racer": ItemData(BASE_ID + 202),
    "Kart: Blue Falcon": ItemData(BASE_ID + 203),
    "Kart: Rally Romper": ItemData(BASE_ID + 204),
    "Kart: B. Dasher Mk 2": ItemData(BASE_ID + 205),
    "Kart: Dragonetti": ItemData(BASE_ID + 206),
    "Kart: Aero Glider": ItemData(BASE_ID + 207),
    "Kart: Piranha Prowler": ItemData(BASE_ID + 208),
}


# Default kart unlocks (no save bits). Only added when lock_default_vehicles is on.
DEFAULT_KART_ITEMS = {
    "Kart: Standard Kart S": ItemData(BASE_ID + 220),
    "Kart: Standard Kart M": ItemData(BASE_ID + 221),
    "Kart: Standard Kart L": ItemData(BASE_ID + 222),
    "Kart: Baby Booster": ItemData(BASE_ID + 223),
    "Kart: Nostalgia 1": ItemData(BASE_ID + 224),
    "Kart: Concerto": ItemData(BASE_ID + 225),
    "Kart: Wild Wing": ItemData(BASE_ID + 226),
    "Kart: Offroader": ItemData(BASE_ID + 227),
    "Kart: Flame Flyer": ItemData(BASE_ID + 228),
}


# Bike unlocks (save-file bits)
BIKE_ITEMS = {
    "Bike: Magicruiser": ItemData(BASE_ID + 300),
    "Bike: Twinkle Star": ItemData(BASE_ID + 301),
    "Bike: Rapide": ItemData(BASE_ID + 302),
    "Bike: Nitrocycle": ItemData(BASE_ID + 303),
    "Bike: Quacker": ItemData(BASE_ID + 304),
    "Bike: Dolphin Dasher": ItemData(BASE_ID + 305),
    "Bike: Bubble Bike": ItemData(BASE_ID + 306),
    "Bike: Phantom": ItemData(BASE_ID + 307),
    "Bike: Torpedo": ItemData(BASE_ID + 308),
}


# Default bike unlocks (no save bits). Only added when lock_default_vehicles is on.
DEFAULT_BIKE_ITEMS = {
    "Bike: Standard Bike S": ItemData(BASE_ID + 320),
    "Bike: Standard Bike M": ItemData(BASE_ID + 321),
    "Bike: Standard Bike L": ItemData(BASE_ID + 322),
    "Bike: Bullet Bike": ItemData(BASE_ID + 323),
    "Bike: Nanobike": ItemData(BASE_ID + 324),
    "Bike: Bon Bon": ItemData(BASE_ID + 325),
    "Bike: Mach Bike": ItemData(BASE_ID + 326),
    "Bike: Bowser Bike": ItemData(BASE_ID + 327),
    "Bike: Wario Bike": ItemData(BASE_ID + 328),
}


# Powerup unlocks
POWERUP_ITEMS = {
    "Powerup: Red Shell": ItemData(BASE_ID + 400),
    "Powerup: Triple Bananas": ItemData(BASE_ID + 401),
    "Powerup: Triple Green Shells": ItemData(BASE_ID + 402),
    "Powerup: Triple Red Shells": ItemData(BASE_ID + 403),
    "Powerup: Bob-omb": ItemData(BASE_ID + 404),
    "Powerup: Blue Shell": ItemData(BASE_ID + 405),
    "Powerup: Fake Item Box": ItemData(BASE_ID + 406),
    "Powerup: Star": ItemData(BASE_ID + 407),
    "Powerup: Golden Mushroom": ItemData(BASE_ID + 408),
    "Powerup: Mega Mushroom": ItemData(BASE_ID + 409),
    "Powerup: Blooper": ItemData(BASE_ID + 410),
    "Powerup: POW Block": ItemData(BASE_ID + 411),
    "Powerup: Lightning": ItemData(BASE_ID + 412),
    "Powerup: Triple Mushrooms": ItemData(BASE_ID + 413),
    "Powerup: Bullet Bill": ItemData(BASE_ID + 414),
    "Powerup: Mushroom": ItemData(BASE_ID + 415),
    "Powerup: Green Shell": ItemData(BASE_ID + 416),
    "Powerup: Banana": ItemData(BASE_ID + 417),
}


# Trap items
TRAP_ITEMS = {
    "Brake Trap": ItemData(BASE_ID + 500, "trap"),
    "Gas Trap": ItemData(BASE_ID + 501, "trap"),
    "Boost Trap": ItemData(BASE_ID + 502, "trap"),
    "Cloud Trap": ItemData(BASE_ID + 503, "trap"),
    "POW Trap": ItemData(BASE_ID + 504, "trap"),
    "Lightning Trap": ItemData(BASE_ID + 505, "trap"),
}


# Filler items
FILLER_ITEMS = {
    "Filler: Random Item": ItemData(BASE_ID + 600, "filler"),
    "Filler: Mushroom": ItemData(BASE_ID + 601, "filler"),
    "Filler: Triple Mushroom": ItemData(BASE_ID + 602, "filler"),
    "Filler: Golden Mushroom": ItemData(BASE_ID + 603, "filler"),
    "Filler: Star": ItemData(BASE_ID + 604, "filler"),
    "Filler: Bullet Bill": ItemData(BASE_ID + 605, "filler"),
    "Filler: Mega Mushroom": ItemData(BASE_ID + 606, "filler"),
    "Filler: Blue Shell": ItemData(BASE_ID + 607, "filler"),
    "Filler: Red Shell": ItemData(BASE_ID + 608, "filler"),
    "Filler: Triple Red Shell": ItemData(BASE_ID + 609, "filler"),
    "Filler: Bob-omb": ItemData(BASE_ID + 610, "filler"),
    "Filler: Lightning": ItemData(BASE_ID + 611, "filler"),
    "Filler: Blooper": ItemData(BASE_ID + 612, "filler"),
    "Filler: POW Block": ItemData(BASE_ID + 613, "filler"),
}


# Special items
SPECIAL_ITEMS = {
    "Victory Trophy": ItemData(BASE_ID + 700, "progression"),
    "Victory": ItemData(None, "progression"),
}


# All cups (used by __init__.py for starting cup selection)
ALL_CUPS = [
    "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
    "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup",
]


# Weight class per character, keyed by the name used in item names
# (e.g. "Character: Mario" -> "Mario"). Covers both save-bit and
# default characters.
CHARACTER_WEIGHT_CLASS: Dict[str, str] = {
    "Mario": "Medium", "Baby Peach": "Small", "Waluigi": "Large", "Bowser": "Large",
    "Baby Daisy": "Small", "Dry Bones": "Small", "Baby Mario": "Small", "Luigi": "Medium",
    "Toad": "Small", "Donkey Kong": "Large", "Yoshi": "Medium", "Wario": "Large",
    "Baby Luigi": "Small", "Toadette": "Small", "Koopa Troopa": "Small", "Daisy": "Medium",
    "Peach": "Medium", "Birdo": "Medium", "Diddy Kong": "Medium", "King Boo": "Large",
    "Bowser Jr.": "Medium", "Dry Bowser": "Large", "Funky Kong": "Large", "Rosalina": "Large",
}

# Weight class per vehicle, keyed by the name used in item names
# (e.g. "Kart: Standard Kart S" -> "Standard Kart S"). Covers both
# save-bit and default vehicles, karts and bikes both.
VEHICLE_WEIGHT_CLASS: Dict[str, str] = {
    "Standard Kart S": "Small", "Standard Kart M": "Medium", "Standard Kart L": "Large",
    "Baby Booster": "Small", "Nostalgia 1": "Medium", "Offroader": "Large",
    "Concerto": "Small", "Wild Wing": "Medium", "Flame Flyer": "Large",
    "Cheep Charger": "Small", "Turbo Blooper": "Medium", "Piranha Prowler": "Large",
    "Rally Romper": "Small", "Royal Racer": "Medium", "Aero Glider": "Large",
    "Blue Falcon": "Small", "B. Dasher Mk 2": "Medium", "Dragonetti": "Large",
    "Standard Bike S": "Small", "Standard Bike M": "Medium", "Standard Bike L": "Large",
    "Bullet Bike": "Small", "Mach Bike": "Medium", "Bowser Bike": "Large",
    "Nanobike": "Small", "Bon Bon": "Medium", "Wario Bike": "Large",
    "Quacker": "Small", "Rapide": "Medium", "Twinkle Star": "Large",
    "Magicruiser": "Small", "Nitrocycle": "Medium", "Torpedo": "Large",
    "Bubble Bike": "Small", "Dolphin Dasher": "Medium", "Phantom": "Large",
}

# All character/kart/bike names, regardless of tier. Used for picking
# starting characters/vehicles, which can come from either tier.
ALL_CHARACTERS = list(CHARACTER_WEIGHT_CLASS.keys())
ALL_KARTS = [
    "Standard Kart S", "Standard Kart M", "Standard Kart L",
    "Baby Booster", "Nostalgia 1", "Offroader",
    "Concerto", "Wild Wing", "Flame Flyer",
    "Cheep Charger", "Turbo Blooper", "Piranha Prowler",
    "Rally Romper", "Royal Racer", "Aero Glider",
    "Blue Falcon", "B. Dasher Mk 2", "Dragonetti",
]
ALL_BIKES = [
    "Standard Bike S", "Standard Bike M", "Standard Bike L",
    "Bullet Bike", "Mach Bike", "Bowser Bike",
    "Nanobike", "Bon Bon", "Wario Bike",
    "Quacker", "Rapide", "Twinkle Star",
    "Magicruiser", "Nitrocycle", "Torpedo",
    "Bubble Bike", "Dolphin Dasher", "Phantom",
]


# Combine all items
item_table: Dict[str, ItemData] = {
    **CUP_CC_ITEMS,
    **MODE_ITEMS,
    **CHARACTER_ITEMS,
    **DEFAULT_CHARACTER_ITEMS,
    **KART_ITEMS,
    **DEFAULT_KART_ITEMS,
    **BIKE_ITEMS,
    **DEFAULT_BIKE_ITEMS,
    **POWERUP_ITEMS,
    **TRAP_ITEMS,
    **FILLER_ITEMS,
    **SPECIAL_ITEMS,
}


def get_item_group(item_name: str) -> str:
    """Get the group an item belongs to."""
    if item_name in CUP_CC_ITEMS:
        return "Cup Unlocks"
    elif item_name in MODE_ITEMS:
        return "Mode Unlocks"
    elif item_name in CHARACTER_ITEMS or item_name in DEFAULT_CHARACTER_ITEMS:
        return "Characters"
    elif item_name in KART_ITEMS or item_name in DEFAULT_KART_ITEMS:
        return "Karts"
    elif item_name in BIKE_ITEMS or item_name in DEFAULT_BIKE_ITEMS:
        return "Bikes"
    elif item_name in POWERUP_ITEMS:
        return "Powerups"
    elif item_name in TRAP_ITEMS:
        return "Traps"
    elif item_name in FILLER_ITEMS:
        return "Filler"
    return "Unknown"