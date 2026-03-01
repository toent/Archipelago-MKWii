"""
Region definitions for Mario Kart Wii Archipelago World
"""
import typing

from BaseClasses import Region, Entrance

if typing.TYPE_CHECKING:
    from . import MKWiiWorld

from .locations import MKWiiLocation, location_table, CUPS, TRACKS

_CC_INDEX = ["50cc", "100cc", "150cc", "Mirror"]
_DIFFICULTY_INDEX = ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star", "3_star"]


def create_regions(world: "MKWiiWorld") -> None:
    """Create the region graph: Menu -> Cup/CC regions -> Victory."""
    multiworld = world.multiworld
    player = world.player

    enabled_ccs = world.options.enabled_ccs.value
    enabled_tiers = world.options.enabled_cup_check_tiers.value
    include_races = world.options.include_race_checks.value

    goal_cc_str = _CC_INDEX[world.options.goal_cc.value]
    goal_difficulty_str = _DIFFICULTY_INDEX[world.options.goal_difficulty.value]

    menu = Region("Menu", player, multiworld)
    multiworld.regions.append(menu)

    for cup in CUPS:
        for cc in enabled_ccs:
            region_name = f"{cup} {cc}"
            region = Region(region_name, player, multiworld)

            # Cup completion checks.
            # Always include the goal difficulty tier for the goal CC so the
            # victory condition can be satisfied even when that tier was not
            # listed in enabled_cup_check_tiers.
            difficulties_to_create = set(enabled_tiers)
            if cc == goal_cc_str:
                difficulties_to_create.add(goal_difficulty_str)

            for difficulty in difficulties_to_create:
                loc_name = f"{cup} {cc} - {difficulty.replace('_', ' ').title()}"
                if loc_name in location_table:
                    loc = MKWiiLocation(player, loc_name, location_table[loc_name].code, region)
                    region.locations.append(loc)

            # Individual race checks
            if include_races:
                for track in TRACKS.get(cup, []):
                    loc_name = f"{track} {cc} - 1st Place"
                    if loc_name in location_table:
                        loc = MKWiiLocation(player, loc_name, location_table[loc_name].code, region)
                        region.locations.append(loc)

            multiworld.regions.append(region)

            entrance = Entrance(player, f"To {region_name}", menu)
            menu.exits.append(entrance)
            entrance.connect(region)

    # Victory region with locked event item
    victory_region = Region("Victory", player, multiworld)
    multiworld.regions.append(victory_region)

    victory_entrance = Entrance(player, "To Victory", menu)
    menu.exits.append(victory_entrance)
    victory_entrance.connect(victory_region)

    victory_loc = MKWiiLocation(player, "Victory", None, victory_region)
    victory_loc.place_locked_item(world.create_item("Victory"))
    victory_region.locations.append(victory_loc)
