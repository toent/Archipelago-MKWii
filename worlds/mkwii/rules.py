"""
Access rules for Mario Kart Wii Archipelago World

All cups require their specific cup+CC unlock item to access.
Two starting cups (randomly chosen during generation) are pre-granted
and have no access rule for their assigned CC.
"""
import typing

from BaseClasses import CollectionState

if typing.TYPE_CHECKING:
    from . import MKWiiWorld

from .locations import CUPS


CC_INDEX = ["50cc", "100cc", "150cc", "Mirror"]
DIFFICULTY_INDEX = ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star", "3_star"]


def set_rules(world: "MKWiiWorld") -> None:
    """Set access rules for cup regions and the victory condition."""
    multiworld = world.multiworld
    player = world.player

    enabled_ccs = world.options.enabled_ccs.value
    starting_cups = world.starting_cups  # dict: {"cup_name": "cc"}

    menu = multiworld.get_region("Menu", player)

    # All Mirror cup items (receiving any one of these unlocks mirror mode)
    ALL_MIRROR_CUPS = {f"{cup} Mirror" for cup in CUPS}

    for cup in CUPS:
        for cc in enabled_ccs:
            entrance_name = f"To {cup} {cc}"
            for entrance in menu.exits:
                if entrance.name != entrance_name:
                    continue

                # Check if this exact cup+CC is a starting pair
                is_starting = (starting_cups.get(cup) == cc)

                if is_starting:
                    # Starting cup at its starting CC: no rule needed
                    pass
                elif cc == "Mirror":
                    # Mirror cup: needs mirror mode (any mirror cup item) AND this specific cup
                    cup_item = f"{cup} {cc}"
                    entrance.access_rule = lambda state, ci=cup_item: (
                        state.has_any(ALL_MIRROR_CUPS, player)
                        and state.has(ci, player)
                    )
                else:
                    # Non-mirror locked cup: needs its cup+CC unlock item
                    cup_item = f"{cup} {cc}"
                    entrance.access_rule = lambda state, ci=cup_item: state.has(ci, player)

    # Victory condition: collect enough Victory Trophies
    # Victory Trophies are pre-placed at the goal tier + goal CC locations
    # for all 8 cups. The player needs cups_required_for_goal of them.
    cups_required = world.options.cups_required_for_goal.value

    def victory_rule(state: CollectionState) -> bool:
        return state.has("Victory Trophy", player, cups_required)

    for entrance in menu.exits:
        if entrance.name == "To Victory":
            entrance.access_rule = victory_rule

    multiworld.completion_condition[player] = lambda state: state.has("Victory", player)
