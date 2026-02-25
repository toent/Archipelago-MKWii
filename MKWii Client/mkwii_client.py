"""
Mario Kart Wii Archipelago Client

Connects to an Archipelago server and synchronizes game state with Dolphin
Emulator via direct memory access. Unlock flags are written to both the
runtime structure (instant effect) and the rksys buffer (persistence).

Vanilla unlock blocking strategy:
  - When the game sets an unauthorized unlock bit (e.g. completing Star Cup
    50cc triggers King Boo in vanilla), we immediately clear that bit then
    load the clean savestate to wipe the GP data causing re-derivation.
  - After any savestate load, a grace period suppresses blocking to let
    memory stabilize before scanning again.
  - The initial connection always loads the clean savestate for a fresh start.

Expected directory layout:
    Archipelago/
        CommonClient.py, NetUtils.py, ...
        MKWii Client/
            mkwii_client.py     (this file)
            dolphin_memory.py
            dolphin_manager.py
            tracker.py
            Saves/
"""
from __future__ import annotations
import sys
import traceback

def _crash_handler(exc_type, exc_value, exc_tb):
    with open("crash.log", "w") as f:
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    traceback.print_exception(exc_type, exc_value, exc_tb)

sys.excepthook = _crash_handler

import asyncio
import logging
import os
import time
import atexit
from pathlib import Path
from typing import Dict, Optional, Set, Tuple
from gecko_manager import disable_gecko_codes

# Resolve imports from parent Archipelago directory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from CommonClient import (
    ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop,
)
from NetUtils import ClientStatus

from dolphin_memory import (
    CHARACTER_IDS, VEHICLE_IDS, CUP_UNLOCK_IDS, MODE_IDS, ALL_UNLOCK_IDS,
    CUP_TROPHY_IDS, DolphinMemoryManager, get_vehicle_alternates,
)
from dolphin_manager import DolphinManager
from tracker import launch_tracker

# Console logger for verbose output that should not appear in the AP GUI
console_logger = logging.getLogger("MKWii.Console")
console_logger.propagate = False
if not console_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    console_logger.addHandler(_handler)
console_logger.setLevel(logging.DEBUG)

# Tier ordering (index = strength, higher is better)
TIER_HIERARCHY = ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star", "3_star"]
CC_NAMES = ["50cc", "100cc", "150cc", "Mirror"]
CUPS = [
    "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
    "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup",
]

# Mapping from tier strings (various casings) to canonical form
TIER_NORMALIZE: Dict[str, str] = {}
for _t in TIER_HIERARCHY:
    _readable = _t.replace("_", " ")
    TIER_NORMALIZE[_readable] = _t
    TIER_NORMALIZE[_readable.title()] = _t
    TIER_NORMALIZE[_readable.lower()] = _t

# Seconds to wait after sending F-key before re-hooking to Dolphin.
# Dolphin needs time to decompress and apply the savestate; 8s handles slow machines
# and mid-gameplay loads where the save system takes longer to reinitialize.
POST_LOAD_SETTLE_SECS = 8.0

# Seconds to suppress all blocking after a savestate load to let memory stabilize.
POST_LOAD_GRACE_SECS = 8.0

# -- Commands --

class MKWiiCommandProcessor(ClientCommandProcessor):

    def _cmd_status(self) -> None:
        """Show MKWii client and Dolphin connection status."""
        ctx: MKWiiContext = self.ctx  # type: ignore[assignment]
        if ctx.dolphin and ctx.dolphin.is_connected:
            self.output(f"Connected to Dolphin (runtime @ 0x{ctx.dolphin._runtime_base:08X})")
            self.output(f"  Cups: {len(ctx.unlocked_cups)}  "
                        f"Characters: {len(ctx.unlocked_characters)}  "
                        f"Karts: {len(ctx.unlocked_karts)}  "
                        f"Bikes: {len(ctx.unlocked_bikes)}")
            self.output(f"  Checked locations: {len(ctx.checked_locations)}")
        else:
            self.output("Not connected to Dolphin")

    def _cmd_check(self) -> None:
        """Manually trigger a location check cycle."""
        asyncio.create_task(self.ctx.check_locations())  # type: ignore[union-attr]

    # def _cmd_loadstate(self) -> None:
    #     """Load the clean savestate and re-apply AP unlocks."""
    #     ctx: MKWiiContext = self.ctx  # type: ignore[assignment]
    #     if not ctx.dolphin_mgr or not ctx.dolphin_mgr.has_bundled_savestate:
    #         self.output("No savestate available")
    #         return
    #     asyncio.create_task(ctx._do_savestate_load("manual /loadstate"))

    # def _cmd_restart(self) -> None:
    #     """Restart the connection between the client and Dolphin by loading the clean savestate and rehooking."""
    #     ctx: MKWiiContext = self.ctx  # type: ignore[assignment]
    #     if not ctx.dolphin_mgr or not ctx.dolphin_mgr.has_bundled_savestate:
    #         self.output("No savestate available")
    #         return
    #     asyncio.create_task(ctx._do_savestate_load("manual /restart"))

    def _cmd_hook(self) -> None:
        """Force restart the Dolphin hook process (unhook + fresh re-hook)."""
        ctx: MKWiiContext = self.ctx  # type: ignore[assignment]
        if ctx.dolphin:
            ctx.dolphin.unhook()
            self.output("Unhooked from Dolphin, re-hooking...")
        else:
            self.output("Hooking to Dolphin...")
        asyncio.create_task(ctx._force_rehook())


# Context

class MKWiiContext(CommonContext):
    """Client context managing Dolphin memory sync and AP server communication."""

    command_processor = MKWiiCommandProcessor
    game = "Mario Kart Wii"
    items_handling = 0b111

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)

        self.dolphin: Optional[DolphinMemoryManager] = None
        self.dolphin_mgr: Optional[DolphinManager] = None

        # AP-granted state
        self.unlocked_cups: Set[str] = set()
        self.unlocked_characters: Set[str] = set()
        self.unlocked_karts: Set[str] = set()
        self.unlocked_bikes: Set[str] = set()
        self.unlocked_modes: Set[str] = set()

        # Location tracking
        self.completed_locations: Dict[Tuple[str, str], str] = {}
        self.location_name_to_id: Dict[str, int] = {}
        self.fake_trophies: Dict[Tuple[int, str], Tuple[str, str]] = {}
        # Locations sent but not yet confirmed - prevents duplicate sends
        self._pending_location_ids: Set[int] = set()

        # Internal state
        self.slot_data: dict = {}
        self.seed: Optional[str] = None
        self.backup_dir: Optional[Path] = None
        self.goal_reached: bool = False
        self._memory_poll_task: Optional[asyncio.Task] = None
        self._initial_state_loaded: bool = False

        # Vanilla blocking state
        self._recently_blocked: Set[str] = set()
        # Grace period after savestate load - suppress all blocking to let memory stabilize
        self._grace_until: float = 0.0
        # True while a savestate load is in progress - poll loop must not interfere
        self._loading_state: bool = False
        # Set when a savestate loaded but rehook failed - poll loop should
        # apply grace period when it eventually reconnects
        self._needs_post_load_grace: bool = False

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "RoomInfo":
            self.seed = args.get("seed_name", "unknown")
            self.backup_dir = (
                Path.home() / "Documents" / "Dolphin Emulator" / "MKWii_AP_Backups" / self.seed
            )
            self.backup_dir.mkdir(parents=True, exist_ok=True)

        elif cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            console_logger.info(f"Slot data keys: {list(self.slot_data.keys())}")

            if not self.seed:
                self.seed = f"team{args.get('team', 0)}_slot{args.get('slot', 0)}"
                self.backup_dir = (
                    Path.home() / "Documents" / "Dolphin Emulator" / "MKWii_AP_Backups" / self.seed
                )
                self.backup_dir.mkdir(parents=True, exist_ok=True)

            self._build_location_lookup()
            self._populate_tracker_from_checked()
            if not self._memory_poll_task:
                self._memory_poll_task = asyncio.create_task(self._poll_dolphin())


        elif cmd == "ReceivedItems":
            self._handle_received_items(args)

    # Item reception

    def _handle_received_items(self, args: dict) -> None:
        from worlds.mkwii.items import item_table

        start_index = args["index"]
        id_to_name = {data.code: name for name, data in item_table.items()}

        for i, item in enumerate(args["items"]):
            name = id_to_name.get(item.item, f"Unknown({item.item})")
            console_logger.info(f"Received #{start_index + i}: {name}")
            self._process_item(name)

    def _process_item(self, item_name: str) -> None:
        """Route a received item to the appropriate unlock set and apply it."""
        if "Character:" in item_name:
            char = item_name.replace("Character: ", "")
            self.unlocked_characters.add(char)
            self._apply_unlock(char, "character")

        elif "Kart:" in item_name or "Bike:" in item_name:
            vehicle = item_name.replace("Kart: ", "").replace("Bike: ", "")
            all_names = get_vehicle_alternates(vehicle)
            if "Kart:" in item_name:
                self.unlocked_karts.update(all_names)
            else:
                self.unlocked_bikes.update(all_names)
            self._apply_unlock(vehicle, "vehicle")

        elif "Cup" in item_name and ("cc" in item_name.lower() or "mirror" in item_name.lower()):
            self.unlocked_cups.add(item_name)
            self._apply_unlock(item_name, "cup")
            if "mirror" in item_name.lower():
                # Mirror cups require mirror mode to be accessible
                self.unlocked_modes.add("Mirror mode")
                if self.dolphin and self.dolphin.is_connected:
                    self.dolphin.unlock_mirror_mode()

        elif "Karts/Bikes" in item_name:
            self.unlocked_modes.add(item_name)
            self._apply_unlock(item_name, "mode")

        elif "Filler:" in item_name or "Trap" in item_name:
            console_logger.debug(f"Non-unlock item: {item_name}")

    def _apply_unlock(self, name: str, category: str) -> None:
        """Write a single unlock to Dolphin memory if connected."""
        if not self.dolphin or not self.dolphin.is_connected:
            return
        changed = self.dolphin.unlock_item(name)
        if changed:
            logger.info(f"Unlocked {category}: {name}")

    def _apply_all_received_items(self) -> None:
        """Re-apply every AP-granted unlock. Called after savestate load or reconnect."""
        if not self.dolphin or not self.dolphin.is_connected:
            return

        count = 0
        for char in self.unlocked_characters:
            if char in CHARACTER_IDS:
                self.dolphin.unlock_item(char)
                count += 1

        for vehicle in self.unlocked_karts | self.unlocked_bikes:
            if vehicle in VEHICLE_IDS and VEHICLE_IDS[vehicle] is not None:
                self.dolphin.unlock_item(vehicle)
                count += 1

        for cup in self.unlocked_cups:
            if cup in CUP_UNLOCK_IDS:
                self.dolphin.unlock_item(cup)
                count += 1
            if "mirror" in cup.lower():
                self.dolphin.unlock_mirror_mode()

        for mode in self.unlocked_modes:
            if mode in MODE_IDS:
                self.dolphin.unlock_item(mode)
                count += 1

        if count:
            logger.info(f"Re-applied {count} AP unlocks")

    # Dolphin connection

    async def _try_hook_dolphin(self) -> bool:
        if self.dolphin is None:
            self.dolphin = DolphinMemoryManager(license_num=1)

        if not self.dolphin.hook():
            logger.debug("Not hooked to Dolphin yet")
            return False

        logger.info("Connected to Dolphin")

        # On first connection, load clean savestate for a fresh AP start
        # if not self._initial_state_loaded and self.dolphin_mgr:
        #     self._initial_state_loaded = True

        #     if self.dolphin_mgr.has_bundled_savestate:
        #         await self._do_savestate_load("initial clean start")
        #         # _do_savestate_load handles its own re-hook + re-apply.
        #         # If re-hook failed, we must not claim success - the poll
        #         # loop will retry on the next cycle.
        #         if not self.dolphin or not self.dolphin.is_connected:
        #             return False
        #         return True
        #     else:
        #         logger.error("Bundled savestate missing - place MKWii_AP_Savestate.sav next to the client")
        self._apply_all_received_items()

        # If recovering from a failed loadstate rehook, set grace period
        if self._needs_post_load_grace:
            self._needs_post_load_grace = False
            self._grace_until = time.monotonic() + POST_LOAD_GRACE_SECS
            console_logger.info("Recovered from savestate load - grace period active")

        return True

    # async def _do_savestate_load(self, reason: str) -> bool:
    #     """Load the clean savestate, re-hook, and re-apply AP items.

    #     Used for the initial clean start and as the last-resort escalation
    #     when bit-level locking can't keep up with the game re-deriving bits.
    #     """
    #     if not self.dolphin_mgr or not self.dolphin_mgr.has_bundled_savestate:
    #         return False

    #     # Prevent the poll loop from interfering during the load
    #     self._loading_state = True
    #     self._recently_blocked.clear()

    #     try:
    #         console_logger.info(f"Loading savestate ({reason})...")

    #         # Mark internal pointers as stale but keep DME connected -
    #         # Dolphin is the same process, we just need to re-resolve pointers.
    #         if self.dolphin:
    #             self.dolphin._hooked = False
    #             self.dolphin._manager_ptr = None
    #             self.dolphin._runtime_base = None
    #             self.dolphin._save_buffer_base = None

    #         self.dolphin_mgr.load_state()

    #         # Dolphin needs time to decompress and apply the savestate.
    #         # During active gameplay this takes longer than at boot.
    #         await asyncio.sleep(POST_LOAD_SETTLE_SECS)

    #         # Re-resolve pointers (lightweight - no DME unhook/rehook).
    #         # The save system needs time to reinitialize after a state load.
    #         for attempt in range(40):
    #             if self.dolphin and self.dolphin.resolve_pointers():
    #                 break
    #             if attempt in (5, 15, 25, 35):
    #                 console_logger.info(f"Waiting for save system... (attempt {attempt + 1}/40)")
    #             await asyncio.sleep(1.0)
    #         else:
    #             # resolve_pointers failed - try a full DME rehook as last resort
    #             console_logger.info("Pointer resolution failed, trying full DME rehook...")
    #             if self.dolphin:
    #                 self.dolphin.unhook()
    #             for attempt in range(10):
    #                 if self.dolphin and self.dolphin.hook():
    #                     break
    #                 await asyncio.sleep(1.0)

    #         if not self.dolphin or not self.dolphin.is_connected:
    #             # Don't panic - the poll loop will keep retrying hook()
    #             # and will re-apply items once connected.
    #             self._needs_post_load_grace = True
    #             console_logger.warning(
    #                 "Savestate loaded but hook timed out - poll loop will retry automatically. "
    #                 "You can also try /hook"
    #             )
    #             return False

    #         self._apply_all_received_items()
    #         # Set grace period AFTER rehook so it doesn't expire during the loop
    #         self._grace_until = time.monotonic() + POST_LOAD_GRACE_SECS
    #         console_logger.info("Savestate loaded, AP unlocks re-applied")
    #         return True
    #     except Exception as e:
    #         console_logger.error(f"Error during savestate load: {e}")
    #     finally:
    #         # Always release the lock so the poll loop can resume
    #         self._loading_state = False

    async def _force_rehook(self) -> None:
        """Force a fresh hook to Dolphin, bypassing initial savestate logic."""
        if self.dolphin is None:
            self.dolphin = DolphinMemoryManager(license_num=1)

        # Prevent poll loop from interfering
        self._loading_state = True
        if not self.dolphin._hooked:
            asyncio.sleep(1)
            self.dolphin_mgr.focus_game_window()
        try:
            for attempt in range(30):
                if self.dolphin.hook():
                    logger.info("Hooked to Dolphin via /hook")
                    self._apply_all_received_items()

                    if self._needs_post_load_grace:
                        self._needs_post_load_grace = False
                        self._grace_until = time.monotonic() + POST_LOAD_GRACE_SECS
                        console_logger.info("Grace period active after savestate recovery")

                    return

                if attempt in (5, 15, 25):
                    console_logger.info(f"Waiting for Dolphin... (attempt {attempt + 1}/30)")

                await asyncio.sleep(1.0)

            logger.warning("/hook failed after 30 attempts - poll loop will retry")

        finally:
            # Always release so poll loop can resume
            self._loading_state = False

    # Polling loop: continuously monitor Dolphin memory for changes and enforce AP state 

    async def _poll_dolphin(self) -> None:
        """Main loop: connect to Dolphin, check locations, enforce AP state."""
        console_logger.info("Starting Dolphin memory poll...")
        if self.dolphin is None:
            self.dolphin = DolphinMemoryManager(license_num=1)

        while True:
            try:
                if not self.dolphin._hooked:
                    asyncio.sleep(1)
                    self.dolphin_mgr.focus_game_window()
                await asyncio.sleep(0.5)

                # Don't touch Dolphin while a savestate load is in progress
                if self._loading_state:
                    continue

                if not self.dolphin or not self.dolphin.is_connected:
                    if not await self._try_hook_dolphin():
                        await asyncio.sleep(2)
                        continue

                # Verify memory is still readable
                try:
                    self.dolphin.read_all_unlock_bytes()
                except Exception:
                    console_logger.warning("Lost Dolphin connection, retrying...")
                    self.dolphin.unhook()
                    continue

                await self.check_locations()
                await self._block_vanilla_unlocks()
                # await self._check_goal()

            except asyncio.CancelledError:
                break
            except Exception as e:
                console_logger.error(f"Poll error: {e}")
                await asyncio.sleep(2)

    # -- Vanilla unlock blocking --

    async def _block_vanilla_unlocks(self) -> None:
        """Detect and revert any unlocks not granted by AP.

        Strategy:
          1. Scan for unauthorized unlock bits
          2. Bit-lock them immediately (prevents flicker)
          3. Load savestate to wipe the GP data causing re-derivation
          4. Re-apply AP unlocks

        The game always re-derives unlock bits from GP completion data,
        so bit-locking alone is a losing battle - the savestate load is
        what actually fixes it.
        """
        if not self.dolphin or not self.dolphin.is_connected:
            return

        # Grace period after savestate load - don't touch anything
        if time.monotonic() < self._grace_until:
            return

        try:
            blocked: list[str] = []

            for name, data in CHARACTER_IDS.items():
                if data and self.dolphin.is_item_unlocked(name) and name not in self.unlocked_characters:
                    blocked.append(name)

            for name, data in VEHICLE_IDS.items():
                if data and self.dolphin.is_item_unlocked(name):
                    if name not in self.unlocked_karts and name not in self.unlocked_bikes:
                        blocked.append(name)

            for name in CUP_UNLOCK_IDS:
                if self.dolphin.is_item_unlocked(name) and name not in self.unlocked_cups:
                    blocked.append(name)

            for name in MODE_IDS:
                if self.dolphin.is_item_unlocked(name) and name not in self.unlocked_modes:
                    blocked.append(name)

            if not blocked:
                return

            if self.dolphin.is_connected:
                # Bit-lock any unauthorized bits
                for name in blocked:
                    if name in ALL_UNLOCK_IDS:
                        #await asyncio.sleep(5) # CHANGE AFTER GECKO CODE FOR BLOCKING UNLOCK SCREEN: Wait a moment to let any new bits stabilize before locking
                        self.dolphin.lock_item(name)

            for name in blocked:
                logger.warning(f"Blocked vanilla unlock: {name}")

            # Load savestate to wipe the GP data causing re-derivation
            # """Load the clean savestate and re-apply AP unlocks."""
            if not self.dolphin_mgr or not self.dolphin_mgr.has_bundled_savestate:
                self.output("No savestate available")
                return
            # await self._do_savestate_load("vanilla unlock blocked")

        except Exception as e:
            console_logger.error(f"Error in vanilla unlock blocking: {e}")

    # Location checking

    def _build_location_lookup(self) -> None:
        from worlds.mkwii.locations import location_table
        self.location_name_to_id = {name: data.code for name, data in location_table.items()}
        console_logger.info(f"Location lookup: {len(self.location_name_to_id)} entries")

    def _populate_tracker_from_checked(self) -> None:
        """Reconstruct completion state from previously checked location IDs."""
        id_to_name = {v: k for k, v in self.location_name_to_id.items()}

        for loc_id in self.checked_locations:
            name = id_to_name.get(loc_id)
            if not name or " - " not in name:
                continue
            cup_cc, tier_str = name.rsplit(" - ", 1)
            parts = cup_cc.rsplit(" ", 1)
            if len(parts) != 2:
                continue
            cup, cc = parts
            tier = TIER_NORMALIZE.get(tier_str)
            if tier:
                self._update_completion(cup, cc, tier)

        console_logger.info(
            f"Loaded {len(self.completed_locations)} completions from "
            f"{len(self.checked_locations)} checked locations"
        )
        launch_tracker(self)

    async def check_locations(self) -> None:
        """Read GP results from memory and send new location checks to the server."""
        if not self.slot_data or not self.dolphin or not self.dolphin.is_connected:
            return

        enabled_ccs = self.slot_data.get("enabled_ccs", ["50cc", "100cc", "150cc"])
        enabled_tiers = self.slot_data.get("enabled_cup_check_tiers",
                                           ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star"])

        new_locations: list[int] = []

        for cup_name, cup_id in CUP_TROPHY_IDS.items():
            for cc in enabled_ccs:
                trophy, rank = self.dolphin.get_gp_result(cup_id, cc)

                if not self._is_real_result(cup_id, cc, trophy, rank):
                    continue

                tiers = self._tiers_from_result(trophy, rank)

                for tier in tiers:
                    if tier not in enabled_tiers:
                        continue
                    loc_name = f"{cup_name} {cc} - {tier.replace('_', ' ').title()}"
                    loc_id = self.location_name_to_id.get(loc_name)
                    if not loc_id:
                        continue

                    # Skip if already confirmed OR already sent and awaiting confirm
                    if loc_id in self.checked_locations or loc_id in self._pending_location_ids:
                        continue

                    new_locations.append(loc_id)
                    self._pending_location_ids.add(loc_id)
                    console_logger.info(f"New check: {loc_name}")
                    self._update_completion(cup_name, cc, tier)

        if new_locations:
            await self.send_msgs([{"cmd": "LocationChecks", "locations": new_locations}])
            console_logger.info(f"Sent {len(new_locations)} location checks")

        # Clean up pending set: anything the server has confirmed can be removed
        self._pending_location_ids -= self.checked_locations

        await self._check_goal()

    def _is_real_result(self, cup_id: int, cc: str, trophy: str, rank: str) -> bool:
        """Filter out fake trophies left over from a previous savestate."""
        key = (cup_id, cc)
        if key not in self.fake_trophies:
            return True

        fake_trophy, fake_rank = self.fake_trophies[key]
        if trophy == fake_trophy and rank == fake_rank:
            return False

        trophy_val = {"none": 0, "bronze": 1, "silver": 2, "gold": 3}
        rank_val = {"D": 0, "C": 1, "B": 2, "A": 3, "1_star": 4, "2_star": 5, "3_star": 6}
        if (trophy_val.get(trophy, 0) > trophy_val.get(fake_trophy, 0) or
                (trophy == fake_trophy and rank_val.get(rank, 0) > rank_val.get(fake_rank, 0))):
            del self.fake_trophies[key]
            return True
        return False

    @staticmethod
    def _tiers_from_result(trophy: str, rank: str) -> list[str]:
        """Convert a GP trophy/rank pair into the list of achieved tier strings."""
        tiers: list[str] = []
        if trophy == "none":
            return tiers
        tiers.append("3rd_place")
        if trophy in ("silver", "gold"):
            tiers.append("2nd_place")
        if trophy == "gold":
            tiers.append("1st_place")
            star_tiers = {"1_star": ["1_star"], "2_star": ["1_star", "2_star"],
                          "3_star": ["1_star", "2_star", "3_star"]}
            tiers.extend(star_tiers.get(rank, []))
        return tiers

    def _update_completion(self, cup: str, cc: str, tier: str) -> None:
        key = (cup, cc)
        current = self.completed_locations.get(key, "none")
        current_idx = TIER_HIERARCHY.index(current) if current in TIER_HIERARCHY else -1
        new_idx = TIER_HIERARCHY.index(tier) if tier in TIER_HIERARCHY else -1
        if new_idx > current_idx:
            self.completed_locations[key] = tier

    async def _check_goal(self) -> None:
        if self.goal_reached or not self.slot_data:
            return

        required = self.slot_data.get("cups_required_for_goal", 6)
        goal_cc = CC_NAMES[self.slot_data.get("goal_cc", 2)]
        goal_tier = TIER_HIERARCHY[min(self.slot_data.get("goal_difficulty", 3), len(TIER_HIERARCHY) - 1)]
        goal_idx = TIER_HIERARCHY.index(goal_tier)

        count = 0
        for cup in CUPS:
            achieved = self.completed_locations.get((cup, goal_cc), "none")
            if achieved in TIER_HIERARCHY:
                achieved_idx = TIER_HIERARCHY.index(achieved)

                if achieved_idx >= goal_idx:
                    # Verify all lower tiers are also completed
                    valid_progression = True
                    for lower_idx in range(achieved_idx):
                        lower_tier = TIER_HIERARCHY[lower_idx]
                        if self.completed_locations.get((cup, goal_cc)) != lower_tier and \
                        TIER_HIERARCHY.index(
                            self.completed_locations.get((cup, goal_cc), "none")
                        ) < lower_idx:
                            valid_progression = False
                            break

                    if valid_progression:
                        count += 1
                    

        if count >= required:
            self.goal_reached = True
            logger.info(f"GOAL COMPLETE: {count}/{required} cups at "
                        f"{goal_tier.replace('_', ' ')}+ on {goal_cc}")
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])


#Entry point

async def main() -> None:
    print("\n" + "=" * 60)
    print("  Mario Kart Wii AP Client")
    print("=" * 60 + "\n")

    mgr = DolphinManager()

    # Handle all exit paths: normal exit, Ctrl+C, and CMD window close button
    def _on_exit():
        disable_gecko_codes(mgr.get_dolphin_user_dir())

    atexit.register(_on_exit)  # normal exit / Ctrl+C

    try:
        import win32api
        def _console_handler(event):
            _on_exit()
            return False  # False = let Windows proceed with default handling
        win32api.SetConsoleCtrlHandler(_console_handler, True)
    except ImportError:
        logger.warning("win32api not available, CMD close button may not disable Gecko codes")

    iso_path = mgr.config.get("iso_path")
    if iso_path and os.path.exists(iso_path):
        print(f"  ISO: {os.path.basename(iso_path)}")
        if not mgr.show_backup_reminder():
            return
    else:
        setup = mgr.run_setup()
        if not setup["ready"]:
            return
        iso_path = setup["iso_path"]

    # if not mgr.has_bundled_savestate:
    #     print(f"  Savestate not found: {mgr.get_bundled_savestate_path()}")
    #     return

    if not mgr.is_dolphin_running() and iso_path:
        mgr.launch_dolphin(iso_path)
        mgr.focus_game_window()

    mgr.show_main_menu_reminder()

    parser = get_base_parser()
    args = parser.parse_args()
    if not args.connect:
        args.connect = input("Enter server address (e.g. archipelago.gg:12345): ").strip()

    ctx = MKWiiContext(args.connect, args.password)
    ctx.dolphin_mgr = mgr
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")

    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()

    print("\n  Commands: /status  /check  /loadstate  /hook  /reconnect")
    print("  Waiting for Dolphin...\n")

    try:
        await ctx.exit_event.wait()
    except KeyboardInterrupt:
        pass
    await ctx.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

