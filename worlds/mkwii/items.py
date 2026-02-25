"""
Items for Mario Kart Wii Archipelago World (PAL Version)

Only items with verified save file unlock bits are included.
Items without save bits are always available and listed as starting items in world.py.
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
CUP_CC_ITEMS = {
    # 50cc cups (except starting cups: Mushroom, Flower, Shell, Banana)
    "Star Cup 50cc": ItemData(BASE_ID + 0),
    "Special Cup 50cc": ItemData(BASE_ID + 1),
    "Leaf Cup 50cc": ItemData(BASE_ID + 3),
    "Lightning Cup 50cc": ItemData(BASE_ID + 2),
    
    # 100cc cups (except starting cups: Mushroom, Flower, Shell, Banana)
    "Star Cup 100cc": ItemData(BASE_ID + 12),
    "Special Cup 100cc": ItemData(BASE_ID + 13),
    "Leaf Cup 100cc": ItemData(BASE_ID + 16),
    "Lightning Cup 100cc": ItemData(BASE_ID + 17),
    
    # 150cc cups (except starting cups: Mushroom, Flower, Shell, Banana)
    "Star Cup 150cc": ItemData(BASE_ID + 22),
    "Special Cup 150cc": ItemData(BASE_ID + 23),
    "Leaf Cup 150cc": ItemData(BASE_ID + 26),
    "Lightning Cup 150cc": ItemData(BASE_ID + 27),
    
    # Mirror cups (except starting cups: Mushroom, Flower, Shell, Banana)
    "Star Cup Mirror": ItemData(BASE_ID + 32),
    "Special Cup Mirror": ItemData(BASE_ID + 33),
    "Leaf Cup Mirror": ItemData(BASE_ID + 36),
    "Lightning Cup Mirror": ItemData(BASE_ID + 37),
}


# Mode unlock items — verified save file bits at 0x0038
MODE_ITEMS = {
    "50cc Karts/Bikes": ItemData(BASE_ID + 40),     # 0x0038 bit 6 (0x40)
    "100cc Karts/Bikes": ItemData(BASE_ID + 41),     # 0x0038 bit 7 (0x80)
}


# Character unlocks — all characters with verified save file bits (PAL)
# Starting characters (no save bit): Mario, Luigi, Peach, Yoshi, Toad,
#   Koopa Troopa, Bowser, Donkey Kong, Wario, Waluigi, Baby Mario, Baby Peach
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


# Kart unlocks — only karts with verified save file bits (PAL names)
# Starting karts (no save bit): Standard Kart S/M/L, Baby Booster,
#   Nostalgia 1, Concerto, Mini Beast, Offroader, Flame Flyer
KART_ITEMS = {
    "Kart: Turbo Blooper": ItemData(BASE_ID + 200),      # US: Super Blooper
    "Kart: Cheep Charger": ItemData(BASE_ID + 201),
    "Kart: Royal Racer": ItemData(BASE_ID + 202),         # US: Daytripper
    "Kart: Blue Falcon": ItemData(BASE_ID + 203),
    "Kart: Rally Romper": ItemData(BASE_ID + 204),         # US: Tiny Titan
    "Kart: B. Dasher Mk 2": ItemData(BASE_ID + 205),      # US: Sprinter
    "Kart: Dragonetti": ItemData(BASE_ID + 206),           # US: Honeycoupe
    "Kart: Aero Glider": ItemData(BASE_ID + 207),          # US: Jetsetter
    "Kart: Piranha Prowler": ItemData(BASE_ID + 208),
}


# Bike unlocks — only bikes with verified save file bits (PAL names)
# Starting bikes (no save bit): Standard Bike S/M/L, Bullet Bike,
#   Nanobike, Bon Bon, Mach Bike, Bowser Bike
BIKE_ITEMS = {
    "Bike: Magicruiser": ItemData(BASE_ID + 300),          # US: Magikruiser
    "Bike: Twinkle Star": ItemData(BASE_ID + 301),         # US: Shooting Star
    "Bike: Rapide": ItemData(BASE_ID + 302),               # US: Zip Zip
    "Bike: Nitrocycle": ItemData(BASE_ID + 303),           # US: Sneakster
    "Bike: Quacker": ItemData(BASE_ID + 304),
    "Bike: Dolphin Dasher": ItemData(BASE_ID + 305),
    "Bike: Bubble Bike": ItemData(BASE_ID + 306),          # US: Jet Bubble
    "Bike: Phantom": ItemData(BASE_ID + 307),
    "Bike: Torpedo": ItemData(BASE_ID + 308),              # US: Spear
}


# Powerup unlocks (items that can appear in item boxes)
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


# Filler items (one-time use items)
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
    "Victory": ItemData(None, "progression"),
}


# Combine all items
item_table: Dict[str, ItemData] = {
    **CUP_CC_ITEMS,
    **MODE_ITEMS,
    **CHARACTER_ITEMS,
    **KART_ITEMS,
    **BIKE_ITEMS,
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
    elif item_name in CHARACTER_ITEMS:
        return "Characters"
    elif item_name in KART_ITEMS:
        return "Karts"
    elif item_name in BIKE_ITEMS:
        return "Bikes"
    elif item_name in POWERUP_ITEMS:
        return "Powerups"
    elif item_name in TRAP_ITEMS:
        return "Traps"
    elif item_name in FILLER_ITEMS:
        return "Filler"
    return "Unknown"
