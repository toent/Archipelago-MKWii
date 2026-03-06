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
            item_slot_manager.py
            tracker.py
            Saves/
"""
from __future__ import annotations
import sys
from time import time
import traceback
from dolphin_manager import DolphinManager

def _crash_handler(exc_type, exc_value, exc_tb):
    with open("crash.log", "w") as f:
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    traceback.print_exception(exc_type, exc_value, exc_tb)

from reporting import report_handler as _report_handler

sys.excepthook = _crash_handler

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

# Resolve imports from parent Archipelago directory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))

from CommonClient import (
    ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop,
)
from NetUtils import ClientStatus

from dolphin_memory import (
    CHARACTER_IDS, VEHICLE_IDS, CUP_UNLOCK_IDS, MODE_IDS, ALL_UNLOCK_IDS,
    CUP_TROPHY_IDS, DolphinMemoryManager, get_vehicle_alternates,
)
from item_slot_manager import ItemSlotManager, AP_TO_GAME
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
            if ctx._item_slot_mgr:
                mgr = ctx._item_slot_mgr
                self.output(
                    f"  Item pool: {len(mgr.unlocked_items)} items unlocked  "
                    f"Targeted queue: {len(mgr._targeted_queue)}  "
                    f"Filler queue: {len(mgr._filler_queue)}"
                )
        else:
            self.output("Not connected to Dolphin")

    def _cmd_check(self) -> None:
        """Manually trigger a location check cycle."""
        asyncio.create_task(self.ctx.check_locations())  # type: ignore[union-attr]

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
        self.goal_reached: bool = False
        self._memory_poll_task: Optional[asyncio.Task] = None
        self._initial_state_loaded: bool = False

        # Vanilla blocking state
        self._recently_blocked: Set[str] = set()
        # True while a load is in progress - poll loop must not interfere
        self._loading_state: bool = False

        # Item slot manager (created once room_id / seed is known)
        self._item_slot_mgr: Optional[ItemSlotManager] = None

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        
        if cmd == "RoomInfo":
            self.seed = args.get("seed_name", "unknown")

        elif cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            console_logger.info(f"Slot data keys: {list(self.slot_data.keys())}")

            self._build_location_lookup()
            self._populate_tracker_from_checked()

            if not self.seed:
                self.seed = f"team{args.get('team', 0)}_slot{args.get('slot', 0)}"

            # Build item slot manager once seed/room_id is confirmed
            random_mode = self.slot_data.get("random_item_mode", "placement")
            base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
            queue_dir = base_dir / "itemqueues"
            self._item_slot_mgr = ItemSlotManager(
                room_id                   = self.seed,
                queue_dir                 = queue_dir,
                random_item_mode          = random_mode,
                starting_items            = self.slot_data.get("starting_items"),
                enable_item_randomization = self.slot_data.get("enable_item_randomization", True),
            )
            # Re-sync unlocked powerup pool from already-received items
            self._resync_item_slot_pool()
            asyncio.create_task(self._item_slot_mgr.run_inject_loop())
            console_logger.info(
                f"[ItemSlot] Manager ready — pool: {len(self._item_slot_mgr.unlocked_items)} items, "
                f"mode: {random_mode}"
            )
            _report_handler(
                f"INFO: [ItemSlot] Manager ready — pool: {len(self._item_slot_mgr.unlocked_items)} items, "
                f"mode: {random_mode}", self.dolphin_mgr
            )

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
            self._process_item(name, item.player, item.location)

    def _process_item(self, item_name: str, sender_player: int = 0, location_id: int = 0) -> None:
        """Route a received item to the appropriate unlock set / item slot queue."""
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
                self.unlocked_modes.add("Mirror mode")
                if self.dolphin and self.dolphin.is_connected:
                    self.dolphin.unlock_mirror_mode()

        elif "Karts/Bikes" in item_name:
            self.unlocked_modes.add(item_name)
            self._apply_unlock(item_name, "mode")

        elif (
            item_name.startswith("Powerup:")
            or item_name.startswith("Filler:")
            or item_name.endswith("Trap")
        ):
            if item_name.startswith("Powerup:") and self._item_slot_mgr:
                game_name = AP_TO_GAME.get(item_name)
                if game_name:
                    self._item_slot_mgr.unlock_item_in_pool(game_name)
                    console_logger.info(f"[ItemSlot] Pool unlock: {item_name} -> {game_name}")
                    _report_handler(
                        f"INFO: [ItemSlot] Pool unlock: {item_name} -> {game_name}",
                        self.dolphin_mgr
                    )

            if self._item_slot_mgr:
                self._item_slot_mgr.receive_item(item_name, sender_player, location_id)
            else:
                console_logger.debug(
                    f"[ItemSlot] Manager not ready yet, item may be dropped: {item_name}"
                )

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

    def _resync_item_slot_pool(self) -> None:
        """
        Re-unlock all Powerup: items previously received so the item slot
        manager's pool reflects the full progression state. Called once after
        the ItemSlotManager is created (on Connected).
        """
        if not self._item_slot_mgr:
            return
        try:
            from worlds.mkwii.items import item_table
            id_to_name = {data.code: name for name, data in item_table.items()}
            count = 0
            for loc_id in self.checked_locations:
                name = id_to_name.get(loc_id)
                if name and name.startswith("Powerup:"):
                    game_name = AP_TO_GAME.get(name)
                    if game_name:
                        self._item_slot_mgr.unlock_item_in_pool(game_name)
                        count += 1
            if count:
                console_logger.info(f"[ItemSlot] Re-synced {count} powerups into pool")
                _report_handler(
                    f"INFO: [ItemSlot] Re-synced {count} powerups into pool",
                    self.dolphin_mgr
                )
        except Exception as e:
            console_logger.warning(f"[ItemSlot] Pool re-sync error: {e}")

    # Dolphin connection

    async def _try_hook_dolphin(self) -> bool:
        logger.warning("Starting Dolphin hook process...")
        _report_handler("WARNING: Starting Dolphin hook process...", self.dolphin_mgr)

        if self.dolphin is None:
            self.dolphin = DolphinMemoryManager(license_num=1, logger=console_logger)

        logger.info("Attempting to hook to Dolphin...")
        _report_handler("INFO: Attempting to hook to Dolphin...", self.dolphin_mgr)
        if not await self.dolphin.async_hook():
            logger.debug("Not hooked to Dolphin yet")
            _report_handler("DEBUG: Not hooked to Dolphin yet", self.dolphin_mgr)
            return False

        logger.info("Connected to Dolphin")
        _report_handler("INFO: Connected to Dolphin", self.dolphin_mgr)

        logger.info("Applying AP unlocks to current Dolphin session...")
        _report_handler("INFO: Applying AP unlocks to current Dolphin session...", self.dolphin_mgr)
        self._apply_all_received_items()
        return True

    async def _force_rehook(self) -> None:
        """Force a fresh hook to Dolphin, bypassing initial savestate logic."""
        if self.dolphin is None:
            self.dolphin = DolphinMemoryManager(license_num=1, logger=console_logger)

        self._loading_state = True
        if not self.dolphin._hooked:
            asyncio.sleep(1)
            self.dolphin_mgr.focus_game_window()
        try:
            for attempt in range(30):
                if self._try_hook_dolphin():
                    logger.info("Hooked to Dolphin via /hook")
                    _report_handler("INFO: Hooked to Dolphin via /hook", self.dolphin_mgr)
                    self._apply_all_received_items()
                    return

                if attempt in (5, 15, 25):
                    console_logger.info(f"Waiting for Dolphin... (attempt {attempt + 1}/30)")
                    _report_handler(f"INFO: Waiting for Dolphin... (attempt {attempt + 1}/30)", self.dolphin_mgr)

                await asyncio.sleep(1.0)

            logger.warning("/hook failed after 30 attempts - poll loop will retry")
            _report_handler("WARNING: /hook failed after 30 attempts - poll loop will retry", self.dolphin_mgr)

        finally:
            self._loading_state = False

    # Polling loop

    async def _poll_dolphin(self) -> None:
        """Main loop: connect to Dolphin, check locations, enforce AP state, inject items."""
        console_logger.info("Starting Dolphin memory poll...")
        _report_handler("INFO: Starting Dolphin memory poll...", self.dolphin_mgr)
        if self.dolphin is None:
            self.dolphin = DolphinMemoryManager(license_num=1, logger=console_logger)

        console_logger.info("Starting Dolphin memory polling loop...")
        _report_handler("INFO: Starting Dolphin memory polling loop...", self.dolphin_mgr)
        while True:
            try:
                if not self.dolphin._hooked:
                    asyncio.sleep(1)
                    console_logger.info("Focusing Dolphin window for hook...")
                    _report_handler("INFO: Focusing Dolphin window for hook...", self.dolphin_mgr)
                    self.dolphin_mgr.focus_game_window()
                await asyncio.sleep(0.5)

                if self._loading_state:
                    continue

                if not self.dolphin or not self.dolphin.is_connected:
                    console_logger.info("Trying to hook Dolphin...")
                    _report_handler("INFO: Trying to hook Dolphin...", self.dolphin_mgr)
                    if not await self._try_hook_dolphin():
                        await asyncio.sleep(2)
                        continue

                # Verify memory is still readable
                try:
                    self.dolphin.read_all_unlock_bytes()
                except Exception:
                    console_logger.warning("Lost Dolphin connection, retrying...")
                    _report_handler("WARNING: Lost Dolphin connection, retrying...", self.dolphin_mgr)
                    self.dolphin.unhook()
                    continue

                await self.dolphin.async_patch_vanilla_unlock_block()
                await self._block_vanilla_unlocks()
                await self.check_locations()

                # Item slot injection + race check
                if self._item_slot_mgr:
                    include_race = self.slot_data.get("include_race_checks", False)
                    race_callback = (
                        lambda t, c: asyncio.create_task(self._on_race_first_place(t, c))
                        if include_race else None
                    )
                    if self._item_slot_mgr:
                        self._item_slot_mgr.poll(on_race_check=race_callback)

            except asyncio.CancelledError:
                break
            except Exception as e:
                console_logger.error(f"Poll error: {e}")
                _report_handler(f"ERROR: Poll error: {e}", self.dolphin_mgr)
                await asyncio.sleep(2)

    # Vanilla unlock blocking

    async def _block_vanilla_unlocks(self) -> None:
        """Detect and revert any unlocks not granted by AP."""
        if not self.dolphin or not self.dolphin.is_connected:
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
                for name in blocked:
                    if name in ALL_UNLOCK_IDS:
                        self.dolphin.lock_item(name)

            for name in blocked:
                logger.warning(f"Blocked vanilla unlock: {name}")
                _report_handler(f"WARNING: Blocked vanilla unlock: {name}", self.dolphin_mgr)

        except Exception as e:
            console_logger.error(f"Error in vanilla unlock blocking: {e}")
            _report_handler(f"ERROR: Error in vanilla unlock blocking: {e}", self.dolphin_mgr)

    # Location checking

    def _build_location_lookup(self) -> None:
        from worlds.mkwii.locations import location_table
        self.location_name_to_id = {name: data.code for name, data in location_table.items()}
        console_logger.info(f"Location lookup: {len(self.location_name_to_id)} entries")
        _report_handler(f"INFO: Location lookup: {len(self.location_name_to_id)} entries", self.dolphin_mgr)

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
        _report_handler(
            f"INFO: Loaded {len(self.completed_locations)} completions from "
            f"{len(self.checked_locations)} checked locations", self.dolphin_mgr
        )
        launch_tracker(self)

    async def check_locations(self) -> None:
        """Read GP results from memory and send new location checks to the server."""
        if not self.slot_data or not self.dolphin or not self.dolphin.is_connected:
            return

        enabled_ccs   = self.slot_data.get("enabled_ccs", ["50cc", "100cc", "150cc"])
        enabled_tiers = self.slot_data.get(
            "enabled_cup_check_tiers",
            ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star"]
        )

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
                    if tier.__contains__("star"):
                        # Captitalize the word star.
                        loc_name = f"{cup_name} {cc} - {tier.replace('_', ' ').title()}"
                    else:
                        # Dont cause weird capitalization of 1st/2nd/3rd.
                        loc_name = f"{cup_name} {cc} - {tier.replace('_', ' ')}"
                        
                    loc_id   = self.location_name_to_id.get(loc_name)
                    if not loc_id:
                        continue

                    if loc_id in self.checked_locations or loc_id in self._pending_location_ids:
                        continue

                    new_locations.append(loc_id)
                    self._pending_location_ids.add(loc_id)
                    console_logger.info(f"New check: {loc_name}")
                    _report_handler(f"INFO: New check: {loc_name}", self.dolphin_mgr)
                    self._update_completion(cup_name, cc, tier)

        if new_locations:
            await self.send_msgs([{"cmd": "LocationChecks", "locations": new_locations}])
            console_logger.info(f"Sent {len(new_locations)} location checks")
            _report_handler(f"INFO: Sent {len(new_locations)} location checks", self.dolphin_mgr)

        self._pending_location_ids -= self.checked_locations

        await self._check_goal()

    async def _on_race_first_place(self, track_name: str, cc_name: str) -> None:
        """
        Callback from ItemSlotManager when P1 finishes 1st on a specific track.
        Builds the location name, validates it exists, and sends the check once.
        """
        loc_name = f"{track_name} {cc_name} - 1st Place"
        loc_id   = self.location_name_to_id.get(loc_name)

        if not loc_id:
            console_logger.warning(f"[ItemSlot] No location ID for race check: {loc_name!r}")
            _report_handler(
                f"WARNING: [ItemSlot] No location ID for race check: {loc_name!r}",
                self.dolphin_mgr
            )
            return

        if loc_id in self.checked_locations or loc_id in self._pending_location_ids:
            return

        self._pending_location_ids.add(loc_id)
        await self.send_msgs([{"cmd": "LocationChecks", "locations": [loc_id]}])
        console_logger.info(f"[ItemSlot] Race check sent: {loc_name}")
        _report_handler(f"INFO: [ItemSlot] Race check sent: {loc_name}", self.dolphin_mgr)

    def _is_real_result(self, cup_id: int, cc: str, trophy: str, rank: str) -> bool:
        """Filter out fake trophies left over from a previous savestate."""
        key = (cup_id, cc)
        if key not in self.fake_trophies:
            return True

        fake_trophy, fake_rank = self.fake_trophies[key]
        if trophy == fake_trophy and rank == fake_rank:
            return False

        trophy_val = {"none": 0, "bronze": 1, "silver": 2, "gold": 3}
        rank_val   = {"D": 0, "C": 1, "B": 2, "A": 3, "1_star": 4, "2_star": 5, "3_star": 6}
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
            star_tiers = {
                "1_star": ["1_star"],
                "2_star": ["1_star", "2_star"],
                "3_star": ["1_star", "2_star", "3_star"],
            }
            tiers.extend(star_tiers.get(rank, []))
        return tiers

    def _update_completion(self, cup: str, cc: str, tier: str) -> None:
        key     = (cup, cc)
        current = self.completed_locations.get(key, "none")
        current_idx = TIER_HIERARCHY.index(current) if current in TIER_HIERARCHY else -1
        new_idx     = TIER_HIERARCHY.index(tier)     if tier     in TIER_HIERARCHY else -1
        if new_idx > current_idx:
            self.completed_locations[key] = tier

    async def _check_goal(self) -> None:
        if self.goal_reached or not self.slot_data:
            return

        required   = self.slot_data.get("cups_required_for_goal", 6)
        goal_cc    = CC_NAMES[self.slot_data.get("goal_cc", 2)]
        goal_tier  = TIER_HIERARCHY[min(self.slot_data.get("goal_difficulty", 3), len(TIER_HIERARCHY) - 1)]
        goal_idx   = TIER_HIERARCHY.index(goal_tier)

        count = 0
        for cup in CUPS:
            achieved = self.completed_locations.get((cup, goal_cc), "none")
            if achieved in TIER_HIERARCHY:
                achieved_idx = TIER_HIERARCHY.index(achieved)

                if achieved_idx >= goal_idx:
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


# Entry point

async def main() -> None:
    print("\n" + "=" * 60)
    print("  Mario Kart Wii AP Client")
    print("=" * 60 + "\n")

    mgr = DolphinManager()

    if "dolphin_auto_launch" not in mgr.config:
        mgr.show_dolphin_auto_launch_selection()

    iso_path = None
    if mgr.config.get("dolphin_auto_launch", True):
        iso_path = mgr.config.get("iso_path")
        if not iso_path or not os.path.exists(iso_path):
            setup = mgr.run_setup()
            if not setup["ready"]:
                return
            iso_path = setup["iso_path"]
        else:
            print(f"  ISO: {os.path.basename(iso_path)}")

    if not mgr.show_backup_reminder():
        return

    if mgr.config.get("dolphin_auto_launch", True) and not mgr.is_dolphin_running() and iso_path:
        mgr.launch_dolphin(iso_path)
        mgr.focus_game_window()

    mgr.show_main_menu_reminder()

    parser = get_base_parser()
    args   = parser.parse_args()
    if not args.connect:
        args.connect = input("Enter server address (e.g. archipelago.gg:12345): ").strip()

    ctx = MKWiiContext(args.connect, args.password)
    ctx.dolphin_mgr  = mgr
    ctx.server_task  = asyncio.create_task(server_loop(ctx), name="ServerLoop")

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