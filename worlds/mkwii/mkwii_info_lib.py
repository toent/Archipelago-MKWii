from typing import Dict

CCS  = ["50cc", "100cc", "150cc", "Mirror"]

CC_BYTE_TO_NAME: Dict[int, str] = {
    0: "50cc",
    1: "100cc",
    2: "150cc",
}

CUPS = [
    "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
    "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup",
]

TRACKS = {
    "Mushroom Cup": ["Luigi Circuit", "Moo Moo Meadows", "Mushroom Gorge", "Toad's Factory"],
    "Flower Cup": ["Mario Circuit", "Coconut Mall", "DK Summit", "Wario's Gold Mine"],
    "Star Cup": ["Daisy Circuit", "Koopa Cape", "Maple Treeway", "Grumble Volcano"],
    "Special Cup": ["Dry Dry Ruins", "Moonview Highway", "Bowser's Castle", "Rainbow Road"],
    "Shell Cup": ["GCN Peach Beach", "DS Yoshi Falls", "SNES Ghost Valley 2", "N64 Mario Raceway"],
    "Banana Cup": ["N64 Sherbet Land", "GBA Shy Guy Beach", "DS Delfino Square", "GCN Waluigi Stadium"],
    "Leaf Cup": ["DS Desert Hills", "GBA Bowser's Castle 3", "N64 DK's Jungle Parkway", "GCN Mario Circuit"],
    "Lightning Cup": ["SNES Mario Circuit 3", "DS Peach Gardens", "GCN DK Mountain", "N64 Bowser's Castle"],
}

_TRACK_TO_CUP: dict[str, str] = {
    track: cup for cup, tracks in TRACKS.items() for track in tracks
}

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
    "Mushroom (Unlock)":          "Mushroom",
    "Green Shell (Unlock)":       "Green Shell",
    "Banana (Unlock)":            "Banana",
    # Filler items with explicit item targets
    "Mushroom (Filler)":             "Mushroom",
    "Triple Mushroom (Filler)":      "Triple Mushrooms",
    "Golden Mushroom (Filler)":      "Golden Mushroom",
    "Star (Filler)":                 "Star",
    "Bullet Bill (Filler)":          "Bullet Bill",
    "Mega Mushroom (Filler)":        "Mega Mushroom",
    "Blue Shell (Filler)":           "Blue Shell",
    "Red Shell (Filler)":            "Red Shell",
    "Triple Red Shell (Filler)":     "Triple Red Shells",
    "Bob-omb (Filler)":              "Bob-omb",
    "Lightning (Filler)":            "Lightning",
    "Blooper (Filler)":              "Blooper",
    "POW Block (Filler)":            "POW Block",
}

EMPTY_ITEM_ID = 0x14

WEIGHT_CLASSES = ["Small", "Medium", "Large"]

CHARACTER_WEIGHT_CLASS: dict[str, str] = {
    "Mario": "Medium", "Baby Peach": "Small", "Waluigi": "Large", "Bowser": "Large",
    "Baby Daisy": "Small", "Dry Bones": "Small", "Baby Mario": "Small", "Luigi": "Medium",
    "Toad": "Small", "Donkey Kong": "Large", "Yoshi": "Medium", "Wario": "Large",
    "Baby Luigi": "Small", "Toadette": "Small", "Koopa Troopa": "Small", "Daisy": "Medium",
    "Peach": "Medium", "Birdo": "Medium", "Diddy Kong": "Medium", "King Boo": "Large",
    "Bowser Jr.": "Medium", "Dry Bowser": "Large", "Funky Kong": "Large", "Rosalina": "Large",
}

ALL_CHARACTERS = list(CHARACTER_WEIGHT_CLASS.keys()) + ["Mii Outfit A", "Mii Outfit B"]

CHARACTER_ID_TO_NAME: Dict[int, str] = {
    0x00: "Mario", 0x01: "Baby Peach", 0x02: "Waluigi", 0x03: "Bowser",
    0x04: "Baby Daisy", 0x05: "Dry Bones", 0x06: "Baby Mario", 0x07: "Luigi",
    0x08: "Toad", 0x09: "Donkey Kong", 0x0A: "Yoshi", 0x0B: "Wario",
    0x0C: "Baby Luigi", 0x0D: "Toadette", 0x0E: "Koopa Troopa", 0x0F: "Daisy",
    0x10: "Peach", 0x11: "Birdo", 0x12: "Diddy Kong", 0x13: "King Boo",
    0x14: "Bowser Jr.", 0x15: "Dry Bowser", 0x16: "Funky Kong", 0x17: "Rosalina",
}
CHARACTER_NAME_TO_ID: Dict[str, int] = {v: k for k, v in CHARACTER_ID_TO_NAME.items()}

VEHICLE_WEIGHT_CLASS: dict[str, str] = {
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

_ALL_VEHICLES = ALL_KARTS + ALL_BIKES

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
