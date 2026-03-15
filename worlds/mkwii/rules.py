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

    # Mirror mode requires receiving at least one unlockable Mirror cup item. Even the 4 starting cups are inaccessible in Mirror until then.
    MIRROR_UNLOCK_ITEMS = {
        "Star Cup Mirror", "Special Cup Mirror",
        "Leaf Cup Mirror", "Lightning Cup Mirror",
    }

    # Non-starting cups require their specific cup+CC unlock item
    for cup in CUPS:
        for cc in enabled_ccs:
            entrance_name = f"To {cup} {cc}"
            for entrance in menu.exits:
                if entrance.name != entrance_name:
                    continue

                is_starting = cup in starting_cups

                if cc == "Mirror" and not is_starting:
                    # Locked Mirror cup: needs both mirror mode and its cup unlock
                    cup_item = f"{cup} {cc}"
                    entrance.access_rule = lambda state, ci=cup_item: (
                        state.has_any(MIRROR_UNLOCK_ITEMS, player)
                        and state.has(ci, player)
                    )
                elif cc == "Mirror" and is_starting:
                    # Starting cup in Mirror: only needs mirror mode unlocked
                    entrance.access_rule = lambda state: state.has_any(MIRROR_UNLOCK_ITEMS, player)
                elif not is_starting:
                    # Non-mirror locked cup: needs its cup+CC unlock item
                    cup_item = f"{cup} {cc}"
                    entrance.access_rule = lambda state, ci=cup_item: state.has(ci, player)
                # else: starting cup in non-Mirror CC, no rule needed

    # Victory: player must reach enough goal-tier locations
    goal_cc = CC_INDEX[world.options.goal_cc.value]
    goal_difficulty = DIFFICULTY_INDEX[world.options.goal_difficulty.value]
    cups_required = world.options.cups_required_for_goal.value

    goal_cups = []
    for cup in CUPS:
        if "star" in goal_difficulty:
            loc_name = f"{cup} {goal_cc} - {goal_difficulty.replace('_', ' ').title()}"
        else:
            loc_name = f"{cup} {goal_cc} - {goal_difficulty.replace('_', ' ')}"
        try:
            multiworld.get_location(loc_name, player)
            goal_cups.append(cup)
        except KeyError:
            pass

    def victory_rule(state: CollectionState) -> bool:
        count = 0
        for cup in goal_cups:
            if cup in starting_cups:
                if goal_cc == "Mirror":
                    # Mirror starting cups still need mirror mode unlocked
                    if state.has_any(MIRROR_UNLOCK_ITEMS, player):
                        count += 1
                else:
                    count += 1
            elif state.has(f"{cup} {goal_cc}", player):
                count += 1
        return count >= cups_required

    for entrance in menu.exits:
        if entrance.name == "To Victory":
            entrance.access_rule = victory_rule

    multiworld.completion_condition[player] = lambda state: state.has("Victory", player)
