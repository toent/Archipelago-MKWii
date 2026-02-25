"""
Access rules for Mario Kart Wii Archipelago World
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
    starting_cups = world.STARTING_CUPS

    menu = multiworld.get_region("Menu", player)

    # Non-starting cups require their unlock item to access
    for cup in CUPS:
        if cup in starting_cups:
            continue
        for cc in enabled_ccs:
            item_name = f"{cup} {cc}"
            for entrance in menu.exits:
                if entrance.name == f"To {cup} {cc}":
                    entrance.access_rule = lambda state, item=item_name: state.has(item, player)

    # Victory: player must be able to reach enough goal-tier locations
    goal_cc = CC_INDEX[world.options.goal_cc.value]
    goal_difficulty = DIFFICULTY_INDEX[world.options.goal_difficulty.value]
    cups_required = world.options.cups_required_for_goal.value

    # Build a set of goal cups that actually exist in this player's world
    # (i.e. the goal CC and goal difficulty tier were enabled for this player)
    goal_cups = []
    for cup in CUPS:
        loc_name = f"{cup} {goal_cc} - {goal_difficulty.replace('_', ' ').title()}"
        try:
            multiworld.get_location(loc_name, player)
            goal_cups.append(cup)
        except KeyError:
            pass

    def victory_rule(state: CollectionState) -> bool:
        count = 0
        for cup in goal_cups:
            if cup in starting_cups:
                # Starting cups are always accessible — no unlock item needed
                count += 1
            elif state.has(f"{cup} {goal_cc}", player):
                # Locked cups require their specific CC unlock item
                count += 1
        return count >= cups_required

    for entrance in menu.exits:
        if entrance.name == "To Victory":
            entrance.access_rule = victory_rule

    multiworld.completion_condition[player] = lambda state: state.has("Victory", player)
