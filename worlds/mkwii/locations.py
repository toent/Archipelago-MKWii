"""
Locations for Mario Kart Wii Archipelago World
"""
import typing

from BaseClasses import Location

from .mkwii_info_lib import CUPS, TRACKS, CCS


class MKWiiLocation(Location):
    game: str = "Mario Kart Wii"


class LocationData(typing.NamedTuple):
    code: int
    cup: str
    cc: str
    difficulty: typing.Optional[str] = None
    track: typing.Optional[str] = None


BASE_LOCATION_ID = 0x4D4B1000

DIFFICULTY_TIERS = ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star", "3_star"]


def _build_location_table() -> typing.Dict[str, LocationData]:
    """Build the complete location table at module load time."""
    table: typing.Dict[str, LocationData] = {}
    loc_id = BASE_LOCATION_ID

    for cup in CUPS:
        for cc in CCS:
            for difficulty in DIFFICULTY_TIERS:
                if difficulty.__contains__("star"):
                    # Captitalize the word star.
                    name = f"{cup} {cc} - {difficulty.replace('_', ' ').title()}"
                else:
                    # Dont cause weird capitalization of 1st/2nd/3rd.
                    name = f"{cup} {cc} - {difficulty.replace('_', ' ')}"
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