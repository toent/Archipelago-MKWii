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
    "Baby Daisy": ItemData(BASE_ID + 100),
    "Baby Luigi": ItemData(BASE_ID + 101),
    "Dry Bones": ItemData(BASE_ID + 102),
    "Bowser Jr.": ItemData(BASE_ID + 103),
    "Toadette": ItemData(BASE_ID + 104),
    "King Boo": ItemData(BASE_ID + 105),
    "Dry Bowser": ItemData(BASE_ID + 106),
    "Funky Kong": ItemData(BASE_ID + 107),
    "Rosalina": ItemData(BASE_ID + 108),
    "Diddy Kong": ItemData(BASE_ID + 109),
    "Daisy": ItemData(BASE_ID + 110),
    "Birdo": ItemData(BASE_ID + 111),
    "Mii Outfit A": ItemData(BASE_ID + 112),
    "Mii Outfit B": ItemData(BASE_ID + 113),
}


# Default character unlocks (no save bits, blocked via RaceConfig redirect).
# Only added to the pool when lock_default_characters is on.
DEFAULT_CHARACTER_ITEMS = {
    "Mario": ItemData(BASE_ID + 120),
    "Luigi": ItemData(BASE_ID + 121),
    "Peach": ItemData(BASE_ID + 122),
    "Yoshi": ItemData(BASE_ID + 123),
    "Toad": ItemData(BASE_ID + 124),
    "Koopa Troopa": ItemData(BASE_ID + 125),
    "Bowser": ItemData(BASE_ID + 126),
    "Donkey Kong": ItemData(BASE_ID + 127),
    "Wario": ItemData(BASE_ID + 128),
    "Waluigi": ItemData(BASE_ID + 129),
    "Baby Mario": ItemData(BASE_ID + 130),
    "Baby Peach": ItemData(BASE_ID + 131),
}


# Kart unlocks (save-file bits)
KART_ITEMS = {
    "Turbo Blooper": ItemData(BASE_ID + 200),
    "Cheep Charger": ItemData(BASE_ID + 201),
    "Royal Racer": ItemData(BASE_ID + 202),
    "Blue Falcon": ItemData(BASE_ID + 203),
    "Rally Romper": ItemData(BASE_ID + 204),
    "B. Dasher Mk 2": ItemData(BASE_ID + 205),
    "Dragonetti": ItemData(BASE_ID + 206),
    "Aero Glider": ItemData(BASE_ID + 207),
    "Piranha Prowler": ItemData(BASE_ID + 208),
}


# Default kart unlocks (no save bits). Only added when lock_default_vehicles is on.
DEFAULT_KART_ITEMS = {
    "Standard Kart S": ItemData(BASE_ID + 220),
    "Standard Kart M": ItemData(BASE_ID + 221),
    "Standard Kart L": ItemData(BASE_ID + 222),
    "Baby Booster": ItemData(BASE_ID + 223),
    "Nostalgia 1": ItemData(BASE_ID + 224),
    "Concerto": ItemData(BASE_ID + 225),
    "Wild Wing": ItemData(BASE_ID + 226),
    "Offroader": ItemData(BASE_ID + 227),
    "Flame Flyer": ItemData(BASE_ID + 228),
}


# Bike unlocks (save-file bits)
BIKE_ITEMS = {
    "Magicruiser": ItemData(BASE_ID + 300),
    "Twinkle Star": ItemData(BASE_ID + 301),
    "Rapide": ItemData(BASE_ID + 302),
    "Nitrocycle": ItemData(BASE_ID + 303),
    "Quacker": ItemData(BASE_ID + 304),
    "Dolphin Dasher": ItemData(BASE_ID + 305),
    "Bubble Bike": ItemData(BASE_ID + 306),
    "Phantom": ItemData(BASE_ID + 307),
    "Torpedo": ItemData(BASE_ID + 308),
}


# Default bike unlocks (no save bits). Only added when lock_default_vehicles is on.
DEFAULT_BIKE_ITEMS = {
    "Standard Bike S": ItemData(BASE_ID + 320),
    "Standard Bike M": ItemData(BASE_ID + 321),
    "Standard Bike L": ItemData(BASE_ID + 322),
    "Bullet Bike": ItemData(BASE_ID + 323),
    "Nanobike": ItemData(BASE_ID + 324),
    "Bon Bon": ItemData(BASE_ID + 325),
    "Mach Bike": ItemData(BASE_ID + 326),
    "Bowser Bike": ItemData(BASE_ID + 327),
    "Wario Bike": ItemData(BASE_ID + 328),
}


# Powerup unlocks
POWERUP_ITEMS = {
    "Red Shell (Unlock)": ItemData(BASE_ID + 400),
    "Triple Bananas (Unlock)": ItemData(BASE_ID + 401),
    "Triple Green Shells (Unlock)": ItemData(BASE_ID + 402),
    "Triple Red Shells (Unlock)": ItemData(BASE_ID + 403),
    "Bob-omb (Unlock)": ItemData(BASE_ID + 404),
    "Blue Shell (Unlock)": ItemData(BASE_ID + 405),
    "Fake Item Box (Unlock)": ItemData(BASE_ID + 406),
    "Star (Unlock)": ItemData(BASE_ID + 407),
    "Golden Mushroom (Unlock)": ItemData(BASE_ID + 408),
    "Mega Mushroom (Unlock)": ItemData(BASE_ID + 409),
    "Blooper (Unlock)": ItemData(BASE_ID + 410),
    "POW Block (Unlock)": ItemData(BASE_ID + 411),
    "Lightning (Unlock)": ItemData(BASE_ID + 412),
    "Triple Mushrooms (Unlock)": ItemData(BASE_ID + 413),
    "Bullet Bill (Unlock)": ItemData(BASE_ID + 414),
    "Mushroom (Unlock)": ItemData(BASE_ID + 415),
    "Green Shell (Unlock)": ItemData(BASE_ID + 416),
    "Banana (Unlock)": ItemData(BASE_ID + 417),
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
    "Random Item (Filler)": ItemData(BASE_ID + 600, "filler"),
    "Mushroom (Filler)": ItemData(BASE_ID + 601, "filler"),
    "Triple Mushroom (Filler)": ItemData(BASE_ID + 602, "filler"),
    "Golden Mushroom (Filler)": ItemData(BASE_ID + 603, "filler"),
    "Star (Filler)": ItemData(BASE_ID + 604, "filler"),
    "Bullet Bill (Filler)": ItemData(BASE_ID + 605, "filler"),
    "Mega Mushroom (Filler)": ItemData(BASE_ID + 606, "filler"),
    "Blue Shell (Filler)": ItemData(BASE_ID + 607, "filler"),
    "Red Shell (Filler)": ItemData(BASE_ID + 608, "filler"),
    "Triple Red Shell (Filler)": ItemData(BASE_ID + 609, "filler"),
    "Bob-omb (Filler)": ItemData(BASE_ID + 610, "filler"),
    "Lightning (Filler)": ItemData(BASE_ID + 611, "filler"),
    "Blooper (Filler)": ItemData(BASE_ID + 612, "filler"),
    "POW Block (Filler)": ItemData(BASE_ID + 613, "filler"),
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