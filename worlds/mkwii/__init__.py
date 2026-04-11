"""
Archipelago World definition for Mario Kart Wii (PAL)

Starting cups: Two cups are randomly chosen during generation.
  - One is assigned to the lowest enabled CC (typically 50cc)
  - The other to the second lowest (typically 100cc)
  - This forces the player to use both karts and bikes early on
  - All other cup/CC combinations are locked and received as AP items
"""
import typing
from random import choices, sample

from BaseClasses import ItemClassification, Tutorial
from worlds.AutoWorld import WebWorld, World

from .items import (
    MKWiiItem, ItemData, item_table, ALL_CUPS,
    CUP_CC_ITEMS, MODE_ITEMS, CHARACTER_ITEMS, KART_ITEMS, BIKE_ITEMS,
    POWERUP_ITEMS, TRAP_ITEMS, FILLER_ITEMS, SPECIAL_ITEMS,
)
from .locations import location_table, CUPS, DIFFICULTY_TIERS
from .options import MKWiiOptions
from .regions import create_regions
from .rules import set_rules


class MKWiiWeb(WebWorld):
    theme = "ocean"

    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Mario Kart Wii with Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["toent"],
    )
    tutorials = [setup_en]


class MKWiiWorld(World):
    """
    Mario Kart Wii is a racing game for the Nintendo Wii. Race through cups across
    multiple engine classes, unlocking characters, vehicles, and new cups along the way.
    """

    game = "Mario Kart Wii"
    options_dataclass = MKWiiOptions
    options: MKWiiOptions
    topology_present = False
    web = MKWiiWeb()

    item_name_to_id = {name: data.code for name, data in item_table.items() if data.code is not None}
    location_name_to_id = {name: data.code for name, data in location_table.items() if data.code is not None}

    # Characters available from a fresh save (no unlock bit in rksys.dat).
    STARTING_CHARACTERS: typing.ClassVar[typing.List[str]] = [
        "Mario", "Luigi", "Peach", "Yoshi", "Toad", "Koopa Troopa",
        "Bowser", "Donkey Kong", "Wario", "Waluigi", "Baby Mario", "Baby Peach",
    ]

    # Vehicles without save file bits.
    STARTING_KARTS: typing.ClassVar[typing.List[str]] = [
        "Standard Kart S", "Standard Kart M", "Standard Kart L",
        "Baby Booster", "Nostalgia 1", "Concerto",
        "Mini Beast", "Offroader", "Flame Flyer",
    ]
    STARTING_BIKES: typing.ClassVar[typing.List[str]] = [
        "Standard Bike S", "Standard Bike M", "Standard Bike L",
        "Bullet Bike", "Nanobike", "Bon Bon",
        "Mach Bike", "Bowser Bike",
    ]

    # Per-instance starting cups, set during create_items
    starting_cups: typing.Dict[str, str]  # {"cup_name": "cc"}

    def create_regions(self) -> None:
        create_regions(self)

    def _pick_starting_cups(self) -> typing.Dict[str, str]:
        """Pick 2 random starting cups and assign them to the two lowest enabled CCs.

        Returns a dict mapping cup name to its starting CC, e.g.:
          {"Shell Cup": "50cc", "Star Cup": "100cc"}

        If only one CC is enabled, both cups get that CC.
        """
        cc_priority = ["50cc", "100cc", "150cc", "Mirror"]
        enabled = [cc for cc in cc_priority if cc in self.options.enabled_ccs.value]

        if not enabled:
            enabled = ["50cc"]

        # Pick the two lowest CCs (or the same CC twice if only one enabled)
        cc_1 = enabled[0]
        cc_2 = enabled[1] if len(enabled) >= 2 else enabled[0]

        # Pick 2 random cups from all 8
        picked = self.random.sample(ALL_CUPS, 2)

        return {picked[0]: cc_1, picked[1]: cc_2}

    def create_items(self) -> None:
        item_pool: typing.List[MKWiiItem] = []

        # Pick starting cups for this seed
        self.starting_cups = self._pick_starting_cups()

        # Pre-place Victory Trophies at goal tier + goal CC locations
        # for all 8 cups. These are placed directly on the locations
        # so they always end up in the player's own game.
        cc_index = ["50cc", "100cc", "150cc", "Mirror"]
        diff_index = ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star", "3_star"]
        goal_cc = cc_index[self.options.goal_cc.value]
        goal_diff = diff_index[self.options.goal_difficulty.value]

        for cup in ALL_CUPS:
            if "star" in goal_diff:
                loc_name = f"{cup} {goal_cc} - {goal_diff.replace('_', ' ').title()}"
            else:
                loc_name = f"{cup} {goal_cc} - {goal_diff.replace('_', ' ')}"
            try:
                loc = self.multiworld.get_location(loc_name, self.player)
                loc.place_locked_item(self.create_item("Victory Trophy"))
            except KeyError:
                pass

        # Cup unlocks: all cups for all enabled CCs, except the starting cup/CC pairs
        for cup in ALL_CUPS:
            for cc in self.options.enabled_ccs.value:
                # Skip if this exact cup+CC is a starting pair
                if self.starting_cups.get(cup) == cc:
                    continue
                item_name = f"{cup} {cc}"
                if item_name in item_table:
                    item_pool.append(self.create_item(item_name))

        # Mode unlocks
        for mode_name in MODE_ITEMS:
            item_pool.append(self.create_item(mode_name))

        # Characters (only those with save bits)
        for name in CHARACTER_ITEMS:
            char = name.split(": ", 1)[1]
            if char not in self.STARTING_CHARACTERS:
                item_pool.append(self.create_item(name))

        # Vehicles (only those with save bits)
        for name in KART_ITEMS:
            item_pool.append(self.create_item(name))
        for name in BIKE_ITEMS:
            item_pool.append(self.create_item(name))

        total_locations = len(self.multiworld.get_unfilled_locations(self.player))
        needed_items = total_locations - len(item_pool)

        if self.options.enable_item_randomization.value:
            starting = self.options.starting_items.value
            for name in POWERUP_ITEMS:
                game_name = name.replace("Powerup: ", "", 1)
                if game_name not in starting:
                    item_pool.append(self.create_item(name))
            needed_items = total_locations - len(item_pool)

            if self.options.enable_traps.value:
                trap_pct = self.options.trap_percentage.value / 100.0
                num_traps = int(needed_items * trap_pct)
                trap_weights = self._get_trap_weights()
                if trap_weights and num_traps > 0:
                    trap_names = list(trap_weights.keys())
                    weights = list(trap_weights.values())
                    for _ in range(num_traps):
                        trap = choices(trap_names, weights=weights)[0]
                        item_pool.append(self.create_item(trap))
                    needed_items -= num_traps

            for _ in range(needed_items):
                item_pool.append(self.create_filler())
        else:
            for _ in range(needed_items):
                item_pool.append(self.create_item("Filler: Random Item"))

        self.multiworld.itempool += item_pool

    def create_item(self, name: str) -> MKWiiItem:
        data = item_table[name]

        if name in TRAP_ITEMS:
            classification = ItemClassification.trap
        elif name in FILLER_ITEMS:
            classification = ItemClassification.filler
        elif name == "Victory" or name == "Victory Trophy":
            classification = ItemClassification.progression
        elif name in CHARACTER_ITEMS or name in KART_ITEMS or name in BIKE_ITEMS:
            classification = ItemClassification.useful
        elif name in MODE_ITEMS:
            classification = ItemClassification.useful
        elif name in POWERUP_ITEMS:
            classification = ItemClassification.useful
        else:
            # Cup unlocks gate access to locations
            classification = ItemClassification.progression

        return MKWiiItem(name, classification, data.code, self.player)

    def create_filler(self) -> MKWiiItem:
        filler_weights = self._get_filler_weights()
        if not filler_weights:
            return self.create_item("Filler: Random Item")
        names = list(filler_weights.keys())
        weights = list(filler_weights.values())
        return self.create_item(choices(names, weights=weights)[0])

    def set_rules(self) -> None:
        set_rules(self)

    def fill_slot_data(self) -> dict:
        return {
            "enabled_ccs": list(self.options.enabled_ccs.value),
            "enabled_cup_check_tiers": list(self.options.enabled_cup_check_tiers.value),
            "include_race_checks": self.options.include_race_checks.value,
            "enable_item_randomization": bool(self.options.enable_item_randomization.value),
            "enable_traps": bool(self.options.enable_traps.value),
            "starting_items": list(self.options.starting_items.value),
            "random_item_mode": (
                "uniform" if self.options.random_item_mode.value == 1 else "placement"
            ),
            "cups_required_for_goal": self.options.cups_required_for_goal.value,
            "goal_difficulty": self.options.goal_difficulty.value,
            "goal_cc": self.options.goal_cc.value,
            "starting_characters": self.STARTING_CHARACTERS,
            "starting_cups": self.starting_cups,
            "starting_karts": self.STARTING_KARTS,
            "starting_bikes": self.STARTING_BIKES,
        }

    def _get_trap_weights(self) -> typing.Dict[str, int]:
        mapping = {
            "Brake Trap": self.options.trap_weight_brake.value,
            "Gas Trap": self.options.trap_weight_gas.value,
            "Boost Trap": self.options.trap_weight_boost.value,
            "Cloud Trap": self.options.trap_weight_cloud.value,
            "POW Trap": self.options.trap_weight_pow.value,
            "Lightning Trap": self.options.trap_weight_lightning.value,
        }
        return {k: v for k, v in mapping.items() if v > 0}

    def _get_filler_weights(self) -> typing.Dict[str, int]:
        mapping = {
            "Filler: Random Item": self.options.filler_weight_random.value,
            "Filler: Mushroom": self.options.filler_weight_mushroom.value,
            "Filler: Triple Mushroom": self.options.filler_weight_triple_mushroom.value,
            "Filler: Golden Mushroom": self.options.filler_weight_golden_mushroom.value,
            "Filler: Star": self.options.filler_weight_star.value,
            "Filler: Bullet Bill": self.options.filler_weight_bullet_bill.value,
            "Filler: Mega Mushroom": self.options.filler_weight_mega_mushroom.value,
            "Filler: Blue Shell": self.options.filler_weight_blue_shell.value,
            "Filler: Red Shell": self.options.filler_weight_red_shell.value,
            "Filler: Triple Red Shell": self.options.filler_weight_triple_red_shell.value,
            "Filler: Bob-omb": self.options.filler_weight_bob_omb.value,
            "Filler: Lightning": self.options.filler_weight_lightning_item.value,
            "Filler: Blooper": self.options.filler_weight_blooper.value,
            "Filler: POW Block": self.options.filler_weight_pow_block.value,
        }
        return {k: v for k, v in mapping.items() if v > 0}
