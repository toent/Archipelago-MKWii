"""
Archipelago World definition for Mario Kart Wii (PAL)
"""
import typing
from random import choices

from BaseClasses import ItemClassification, Tutorial
from worlds.AutoWorld import WebWorld, World

from .items import (
    MKWiiItem, ItemData, item_table,
    CUP_CC_ITEMS, MODE_ITEMS, CHARACTER_ITEMS, KART_ITEMS, BIKE_ITEMS,
    POWERUP_ITEMS, TRAP_ITEMS, FILLER_ITEMS,
)
from .locations import location_table
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

    # Event items (code=None) must be excluded from ID maps.
    item_name_to_id = {name: data.code for name, data in item_table.items() if data.code is not None}
    location_name_to_id = {name: data.code for name, data in location_table.items() if data.code is not None}

    # Characters available from a fresh save (no unlock bit in rksys.dat).
    STARTING_CHARACTERS: typing.ClassVar[typing.List[str]] = [
        "Mario", "Luigi", "Peach", "Yoshi", "Toad", "Koopa Troopa",
        "Bowser", "Donkey Kong", "Wario", "Waluigi", "Baby Mario", "Baby Peach",
    ]

    # Cups that are always accessible regardless of CC (no unlock bit).
    STARTING_CUPS: typing.ClassVar[typing.List[str]] = [
        "Mushroom Cup", "Flower Cup", "Shell Cup", "Banana Cup",
    ]

    # Vehicles without save file bits — always available from a fresh save.
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
    STARTING_POWERUPS: typing.ClassVar[typing.List[str]] = [
        "Banana", "Green Shell", "Mushroom",
    ]

    def create_regions(self) -> None:
        create_regions(self)

    def create_items(self) -> None:
        item_pool: typing.List[MKWiiItem] = []

        # Cup unlocks (only non-starting cups have save bits)
        all_cups = [
            "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
            "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup",
        ]
        for cup in all_cups:
            if cup in self.STARTING_CUPS:
                continue
            for cc in self.options.enabled_ccs.value:
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

        # Powerups and traps require mid-race memory features
        if self.options.enable_mid_race_memory_features.value:
            for name in POWERUP_ITEMS:
                item_pool.append(self.create_item(name))

            total_locations = len(self.multiworld.get_unfilled_locations(self.player))
            needed_items = total_locations - len(item_pool)

            # Split filler/trap slots based on trap percentage
            trap_pct = self.options.trap_percentage.value / 100.0
            num_traps = int(needed_items * trap_pct)

            # Build weighted trap pool
            trap_weights = self._get_trap_weights()
            if trap_weights and num_traps > 0:
                trap_names = list(trap_weights.keys())
                weights = list(trap_weights.values())
                for _ in range(num_traps):
                    trap = choices(trap_names, weights=weights)[0]
                    item_pool.append(self.create_item(trap))

            for _ in range(needed_items - num_traps):
                item_pool.append(self.create_filler())
        else:
            # Fill remaining slots with inert filler
            total_locations = len(self.multiworld.get_unfilled_locations(self.player))
            needed_items = total_locations - len(item_pool)
            for _ in range(needed_items):
                item_pool.append(self.create_item("Filler: Random Item"))

        self.multiworld.itempool += item_pool

    def create_item(self, name: str) -> MKWiiItem:
        data = item_table[name]

        if name in TRAP_ITEMS:
            classification = ItemClassification.trap
        elif name in FILLER_ITEMS:
            classification = ItemClassification.filler
        elif name == "Victory":
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
            "cups_required_for_goal": self.options.cups_required_for_goal.value,
            "goal_difficulty": self.options.goal_difficulty.value,
            "goal_cc": self.options.goal_cc.value,
            "starting_characters": self.STARTING_CHARACTERS,
            "starting_cups": self.STARTING_CUPS,
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
