from typing import Dict, List, Set

# AP item name suffixes
UNLOCK_SUFFIX = " (Unlock)"
FILLER_SUFFIX = " (Filler)"


def is_unlock(item_name: str) -> bool:
    # Checks if the item is a powerup unlock item
    return item_name.endswith(UNLOCK_SUFFIX)

def is_filler(item_name: str) -> bool:
    # Checks if the item is a filler item
    return item_name.endswith(FILLER_SUFFIX)

def strip_suffix(item_name: str) -> str:
    # Remove a trailing (Unlock) or (Filler), if there is one
    if item_name.endswith(UNLOCK_SUFFIX):
        return item_name[:-len(UNLOCK_SUFFIX)]
    if item_name.endswith(FILLER_SUFFIX):
        return item_name[:-len(FILLER_SUFFIX)]
    return item_name


# CCs and cups
CCS = ["50cc", "100cc", "150cc", "Mirror"]

# CC byte in RaceConfig to CC string (Mirror is a separate byte)
CC_BYTE_TO_NAME: Dict[int, str] = {
    0: "50cc",
    1: "100cc",
    2: "150cc",
}

# All cups in the game
CUPS = [
    "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
    "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup",
]

# Cup ID in memory to bare PAL name, and the reverse mapping
CUP_ID_TO_NAME: Dict[int, str] = {
    0: "Mushroom Cup", 1: "Flower Cup", 2: "Star Cup", 3: "Special Cup",
    4: "Shell Cup", 5: "Banana Cup", 6: "Leaf Cup", 7: "Lightning Cup",
}
CUP_NAME_TO_ID: Dict[str, int] = {v: k for k, v in CUP_ID_TO_NAME.items()}

# Cups unlocked by default, without save file flags
BASE_CUP_NAMES = {"Mushroom Cup", "Flower Cup", "Shell Cup", "Banana Cup"}

# Every cup and their tracks
TRACKS: Dict[str, List[str]] = {
    "Mushroom Cup": ["Luigi Circuit", "Moo Moo Meadows", "Mushroom Gorge", "Toad's Factory"],
    "Flower Cup": ["Mario Circuit", "Coconut Mall", "DK Summit", "Wario's Gold Mine"],
    "Star Cup": ["Daisy Circuit", "Koopa Cape", "Maple Treeway", "Grumble Volcano"],
    "Special Cup": ["Dry Dry Ruins", "Moonview Highway", "Bowser's Castle", "Rainbow Road"],
    "Shell Cup": ["GCN Peach Beach", "DS Yoshi Falls", "SNES Ghost Valley 2", "N64 Mario Raceway"],
    "Banana Cup": ["N64 Sherbet Land", "GBA Shy Guy Beach", "DS Delfino Square", "GCN Waluigi Stadium"],
    "Leaf Cup": ["DS Desert Hills", "GBA Bowser's Castle 3", "N64 DK's Jungle Parkway", "GCN Mario Circuit"],
    "Lightning Cup": ["SNES Mario Circuit 3", "DS Peach Gardens", "GCN DK Mountain", "N64 Bowser's Castle"],
}

# Track name to the cup it is in
TRACK_NAME_TO_CUP: Dict[str, str] = {}
for _cup, _tracks in TRACKS.items():
    for _track in _tracks:
        TRACK_NAME_TO_CUP[_track] = _cup

# Every track ID in memory to its bare PAL name
TRACK_ID_TO_NAME: Dict[int, str] = {
    0x08: "Luigi Circuit",
    0x01: "Moo Moo Meadows",
    0x02: "Mushroom Gorge",
    0x04: "Toad's Factory",
    0x00: "Mario Circuit",
    0x05: "Coconut Mall",
    0x06: "DK Summit",
    0x07: "Wario's Gold Mine",
    0x09: "Daisy Circuit",
    0x0F: "Koopa Cape",
    0x0B: "Maple Treeway",
    0x03: "Grumble Volcano",
    0x0E: "Dry Dry Ruins",
    0x0A: "Moonview Highway",
    0x0C: "Bowser's Castle",
    0x0D: "Rainbow Road",

    0x10: "GCN Peach Beach",
    0x14: "DS Yoshi Falls",
    0x19: "SNES Ghost Valley 2",
    0x1A: "N64 Mario Raceway",
    0x1B: "N64 Sherbet Land",
    0x1F: "GBA Shy Guy Beach",
    0x17: "DS Delfino Square",
    0x12: "GCN Waluigi Stadium",
    0x15: "DS Desert Hills",
    0x1E: "GBA Bowser's Castle 3",
    0x1D: "N64 DK's Jungle Parkway",
    0x11: "GCN Mario Circuit",
    0x18: "SNES Mario Circuit 3",
    0x16: "DS Peach Gardens",
    0x13: "GCN DK Mountain",
    0x1C: "N64 Bowser's Castle",
}


# Game items and their IDs in memory
ITEM_ID: Dict[str, int] = {
    "Green Shell":        0x00,
    "Red Shell":          0x01,
    "Banana":             0x02,
    "Fake Item Box":      0x03,
    "Mushroom":           0x04,
    "Triple Mushrooms":   0x05,
    "Bob-omb":            0x06,
    "Blue Shell":         0x07,
    "Lightning":          0x08,
    "Star":               0x09,
    "Golden Mushroom":    0x0A,
    "Mega Mushroom":      0x0B,
    "Blooper":            0x0C,
    "POW Block":          0x0D,
    "Thunder Cloud":      0x0E,
    "Bullet Bill":        0x0F,
    "Triple Green Shells":0x10,
    "Triple Red Shells":  0x11,
    "Triple Bananas":     0x12,
}

# The ID of the "empty" item, indicating the item slot is empty
EMPTY_ITEM_ID = 0x14

# AP item name to the game item it gives or unlocks
AP_TO_ITEM: Dict[str, str] = {
    # Powerup unlocks
    "Red Shell (Unlock)":           "Red Shell",
    "Triple Bananas (Unlock)":      "Triple Bananas",
    "Triple Green Shells (Unlock)": "Triple Green Shells",
    "Triple Red Shells (Unlock)":   "Triple Red Shells",
    "Bob-omb (Unlock)":             "Bob-omb",
    "Blue Shell (Unlock)":          "Blue Shell",
    "Fake Item Box (Unlock)":       "Fake Item Box",
    "Star (Unlock)":                "Star",
    "Golden Mushroom (Unlock)":     "Golden Mushroom",
    "Mega Mushroom (Unlock)":       "Mega Mushroom",
    "Blooper (Unlock)":             "Blooper",
    "POW Block (Unlock)":           "POW Block",
    "Lightning (Unlock)":           "Lightning",
    "Triple Mushrooms (Unlock)":    "Triple Mushrooms",
    "Bullet Bill (Unlock)":         "Bullet Bill",
    "Mushroom (Unlock)":            "Mushroom",
    "Green Shell (Unlock)":         "Green Shell",
    "Banana (Unlock)":              "Banana",

    # Filler items with explicit item targets
    "Mushroom (Filler)":            "Mushroom",
    "Triple Mushroom (Filler)":     "Triple Mushrooms",
    "Golden Mushroom (Filler)":     "Golden Mushroom",
    "Star (Filler)":                "Star",
    "Bullet Bill (Filler)":         "Bullet Bill",
    "Mega Mushroom (Filler)":       "Mega Mushroom",
    "Blue Shell (Filler)":          "Blue Shell",
    "Red Shell (Filler)":           "Red Shell",
    "Triple Red Shell (Filler)":    "Triple Red Shells",
    "Bob-omb (Filler)":             "Bob-omb",
    "Lightning (Filler)":           "Lightning",
    "Blooper (Filler)":             "Blooper",
    "POW Block (Filler)":           "POW Block",
}

POWERUP_ITEMS: Dict[str, str] = {ap: item for ap, item in AP_TO_ITEM.items() if is_unlock(ap)}
FILLER_ITEMS: Dict[str, str] = {ap: item for ap, item in AP_TO_ITEM.items() if is_filler(ap)}


# The three weight classes, in order of increasing weight
WEIGHT_CLASSES = ["Small", "Medium", "Large"]

# All characters and their respective weight classes. The Miis are not included here
CHARACTER_WEIGHT_CLASS: Dict[str, str] = {
    "Mario": "Medium", "Baby Peach": "Small", "Waluigi": "Large", "Bowser": "Large",
    "Baby Daisy": "Small", "Dry Bones": "Small", "Baby Mario": "Small", "Luigi": "Medium",
    "Toad": "Small", "Donkey Kong": "Large", "Yoshi": "Medium", "Wario": "Large",
    "Baby Luigi": "Small", "Toadette": "Small", "Koopa Troopa": "Small", "Daisy": "Medium",
    "Peach": "Medium", "Birdo": "Medium", "Diddy Kong": "Medium", "King Boo": "Large",
    "Bowser Jr.": "Medium", "Dry Bowser": "Large", "Funky Kong": "Large", "Rosalina": "Large",
}

# The 24 characters that have a weight class. The Miis are not included here
RACE_CHARACTERS = list(CHARACTER_WEIGHT_CLASS.keys())

# Every character AP item, including the Miis
ALL_CHARACTERS = RACE_CHARACTERS + ["Mii Outfit A", "Mii Outfit B"]

# Every character ID in memory to its bare PAL name, and the reverse mapping
CHARACTER_ID_TO_NAME: Dict[int, str] = {
    0x00: "Mario", 0x01: "Baby Peach", 0x02: "Waluigi", 0x03: "Bowser",
    0x04: "Baby Daisy", 0x05: "Dry Bones", 0x06: "Baby Mario", 0x07: "Luigi",
    0x08: "Toad", 0x09: "Donkey Kong", 0x0A: "Yoshi", 0x0B: "Wario",
    0x0C: "Baby Luigi", 0x0D: "Toadette", 0x0E: "Koopa Troopa", 0x0F: "Daisy",
    0x10: "Peach", 0x11: "Birdo", 0x12: "Diddy Kong", 0x13: "King Boo",
    0x14: "Bowser Jr.", 0x15: "Dry Bowser", 0x16: "Funky Kong", 0x17: "Rosalina",
}
CHARACTER_NAME_TO_ID: Dict[str, int] = {v: k for k, v in CHARACTER_ID_TO_NAME.items()}


# Vehicles and their weight classes
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

# All kart names (PAL)
ALL_KARTS = [
    "Standard Kart S", "Standard Kart M", "Standard Kart L",
    "Baby Booster", "Nostalgia 1", "Offroader",
    "Concerto", "Wild Wing", "Flame Flyer",
    "Cheep Charger", "Turbo Blooper", "Piranha Prowler",
    "Rally Romper", "Royal Racer", "Aero Glider",
    "Blue Falcon", "B. Dasher Mk 2", "Dragonetti",
]

# All bike names (PAL)
ALL_BIKES = [
    "Standard Bike S", "Standard Bike M", "Standard Bike L",
    "Bullet Bike", "Mach Bike", "Bowser Bike",
    "Nanobike", "Bon Bon", "Wario Bike",
    "Quacker", "Rapide", "Twinkle Star",
    "Magicruiser", "Nitrocycle", "Torpedo",
    "Bubble Bike", "Dolphin Dasher", "Phantom",
]

# Vehicle ID in memory to bare PAL name
VEHICLE_ID_TO_NAME: Dict[int, str] = {
    0x00: "Standard Kart S", 0x01: "Standard Kart M", 0x02: "Standard Kart L",
    0x03: "Baby Booster", 0x04: "Nostalgia 1", 0x05: "Offroader",
    0x06: "Concerto", 0x07: "Wild Wing", 0x08: "Flame Flyer",
    0x09: "Cheep Charger", 0x0A: "Turbo Blooper", 0x0B: "Piranha Prowler",
    0x0C: "Rally Romper", 0x0D: "Royal Racer", 0x0E: "Aero Glider",
    0x0F: "Blue Falcon", 0x10: "B. Dasher Mk 2", 0x11: "Dragonetti",
    0x12: "Standard Bike S", 0x13: "Standard Bike M", 0x14: "Standard Bike L",
    0x15: "Bullet Bike", 0x16: "Mach Bike", 0x17: "Bowser Bike",
    0x18: "Nanobike", 0x19: "Bon Bon", 0x1A: "Wario Bike",
    0x1B: "Quacker", 0x1C: "Rapide", 0x1D: "Twinkle Star",
    0x1E: "Magicruiser", 0x1F: "Nitrocycle", 0x20: "Torpedo",
    0x21: "Bubble Bike", 0x22: "Dolphin Dasher", 0x23: "Phantom",
}


# What kind of AP item a bare name is, for handling received items
KIND_OF_NAME: Dict[str, str] = {}
for _name in ALL_CHARACTERS:
    KIND_OF_NAME[_name] = "character"
for _name in ALL_KARTS:
    KIND_OF_NAME[_name] = "kart"
for _name in ALL_BIKES:
    KIND_OF_NAME[_name] = "bike"

# Characters and vehicles that make the game much easier.
META_ITEMS = ["Funky Kong", "Daisy", "Bowser Bike", "Mach Bike"]

# Vehicle names that differ between PAL and NTSC
PAL_TO_NTSC_VEHICLE: Dict[str, str] = {
    "Turbo Blooper": "Super Blooper",
    "Royal Racer": "Daytripper",
    "Rally Romper": "Tiny Titan",
    "Magicruiser": "Magikruiser",
    "B. Dasher Mk 2": "Sprinter",
    "Dragonetti": "Honeycoupe",
    "Aero Glider": "Jetsetter",
    "Twinkle Star": "Shooting Star",
    "Rapide": "Zip Zip",
    "Nitrocycle": "Sneakster",
    "Bubble Bike": "Jet Bubble",
    "Torpedo": "Spear",
    "Baby Booster": "Booster Seat",
    "Nostalgia 1": "Classic Dragster",
    "Concerto": "Mini Beast",
    "Bowser Bike": "Flame Runner",
    "Nanobike": "Bit Bike",
    "Bon Bon": "Sugarscoot",
}

# Extra spellings of a PAL name that should also be recognised
EXTRA_VEHICLE_SPELLINGS: Dict[str, str] = {
    "B Dasher Mk 2": "B. Dasher Mk 2",
}


def get_vehicle_alternates(vehicle_name: str) -> Set[str]:
    # All names a vehicle goes by: PAL name, NTSC name and extra spellings
    pal_name = to_pal_vehicle_name(vehicle_name)
    names = {pal_name}
    if pal_name in PAL_TO_NTSC_VEHICLE:
        names.add(PAL_TO_NTSC_VEHICLE[pal_name])
    for spelling, target in EXTRA_VEHICLE_SPELLINGS.items():
        if target == pal_name:
            names.add(spelling)
    return names


def to_pal_vehicle_name(vehicle_name: str) -> str:
    # Convert an NTSC name or extra spelling to the PAL name
    if vehicle_name in EXTRA_VEHICLE_SPELLINGS:
        return EXTRA_VEHICLE_SPELLINGS[vehicle_name]
    for pal_name, ntsc_name in PAL_TO_NTSC_VEHICLE.items():
        if vehicle_name == ntsc_name:
            return pal_name
    return vehicle_name


# Every name of a vehicle (PAL, NTSC, extra spellings) to its ID
VEHICLE_NAME_TO_ID: Dict[str, int] = {}
for _vehicle_id, _vehicle_name in VEHICLE_ID_TO_NAME.items():
    for _alt_name in get_vehicle_alternates(_vehicle_name):
        VEHICLE_NAME_TO_ID[_alt_name] = _vehicle_id