"""
Locations for Mario Kart Wii Archipelago World
"""
import typing

from BaseClasses import Location


class MKWiiLocation(Location):
    game: str = "Mario Kart Wii"


class LocationData(typing.NamedTuple):
    code: int
    cup: str
    cc: str
    difficulty: typing.Optional[str] = None
    track: typing.Optional[str] = None


BASE_LOCATION_ID = 0x4D4B1000

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
    "Leaf Cup": ["DS Desert Hills", "GCN Bowser's Castle", "N64 DK's Jungle Parkway", "GC Mario Circuit"],
    "Lightning Cup": ["SNES Mario Circuit 3", "DS Peach Gardens", "GCN DK Mountain", "N64 Bowser's Castle"],
}

CCS = ["50cc", "100cc", "150cc", "Mirror"]
DIFFICULTY_TIERS = ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star", "3_star"]


def _build_location_table() -> typing.Dict[str, LocationData]:
    """Build the complete location table at module load time."""
    table: typing.Dict[str, LocationData] = {}
    loc_id = BASE_LOCATION_ID

    for cup in CUPS:
        for cc in CCS:
            for difficulty in DIFFICULTY_TIERS:
                name = f"{cup} {cc} - {difficulty.replace('_', ' ').title()}"
                table[name] = LocationData(code=loc_id, cup=cup, cc=cc, difficulty=difficulty)
                loc_id += 1

    for cup in CUPS:
        for track in TRACKS[cup]:
            for cc in CCS:
                name = f"{track} {cc} - 1st Place"
                table[name] = LocationData(code=loc_id, cup=cup, cc=cc, track=track)
                loc_id += 1

    return table


location_table: typing.Dict[str, LocationData] = _build_location_table()
