"""
Item Slot Manager for Mario Kart Wii AP Client

Handles real-time item injection into P1's item slot during races:
  - Reads P1 race state (lap, placement, track, CC) from Dolphin memory
  - Replaces game-given items with AP-unlocked pool items (GP placement odds)
  - Prioritises queued targeted powerups, then fillers, then pool replacements
  - Traps with in-game equivalents overwrite the slot immediately, no conditions
  - Brake/Gas/Boost traps are held in queue for future memory-effect implementation
  - Filler/targeted queues persist across sessions via /itemqueues/<room_id>.itemqueue
  - Sends individual race location checks (track + CC + 1st Place) when lap=4, place=1

Memory addresses and pointer chains live in dme_addresses.py, access goes through dme_helpers.py.

Priority order each poll tick:
  1. Pending immediate trap  -> overwrite, no remorse, regardless of slot state
  2. Targeted powerup        -> inject on slot-empty, no was_filler_trap_given check
  3. Filler item             -> inject on slot-empty, only if not was_filler_trap_given
  4. Pool replacement        -> replace game-given item when slot transitions empty>full
                               and was_filler_trap_given is False
"""
from __future__ import annotations
import typing

import json
import logging
from collections import deque
from pathlib import Path
from random import choices, choice
from typing import Callable, Deque, Dict, List, Optional, Set, Tuple

from dme_helpers import U8, U32, base_address, is_valid_ptr, read_named, read_u8, write_named
from reporting import ReportHandler

logger = logging.getLogger("MKWii.ItemSlot")

# In game item IDs
ITEM_ID: Dict[str, int] = {
    "Green Shell":        0x00,
    "Red Shell":          0x01,
    "Banana":             0x02,
    "Fake Item Box":      0x03,
    "Mushroom":           0x04,
    "Triple Mushrooms":   0x05,
    "Bob-omb":            0x06,
    "Blue Shell":         0x07,
    "Lightning":          0x08,
    "Star":               0x09,
    "Golden Mushroom":    0x0A,
    "Mega Mushroom":      0x0B,
    "Blooper":            0x0C,
    "POW Block":          0x0D,
    "Thunder Cloud":      0x0E,
    "Bullet Bill":        0x0F,
    "Triple Green Shells":0x10,
    "Triple Red Shells":  0x11,
    "Triple Bananas":     0x12,
}
EMPTY_ID = 0x14

# Items that require count > 1
_ITEM_COUNT_MAP: Dict[int, int] = {
    0x05: 3,  # Triple Mushrooms
    0x10: 3,  # Triple Green Shells
    0x11: 3,  # Triple Red Shells
    0x12: 3,  # Triple Bananas
}

# Track ID - location-table track name
TRACK_ID_TO_NAME: Dict[int, str] = {
    0x08: "Luigi Circuit",
    0x01: "Moo Moo Meadows",
    0x02: "Mushroom Gorge",
    0x04: "Toad's Factory",
    0x00: "Mario Circuit",
    0x05: "Coconut Mall",
    0x06: "DK Summit",
    0x07: "Wario's Gold Mine",
    0x09: "Daisy Circuit",
    0x0F: "Koopa Cape",
    0x0B: "Maple Treeway",
    0x03: "Grumble Volcano",
    0x0E: "Dry Dry Ruins",
    0x0A: "Moonview Highway",
    0x0C: "Bowser's Castle",
    0x0D: "Rainbow Road",

    0x10: "GCN Peach Beach",
    0x14: "DS Yoshi Falls",
    0x19: "SNES Ghost Valley 2",
    0x1A: "N64 Mario Raceway",
    0x1B: "N64 Sherbet Land",
    0x1F: "GBA Shy Guy Beach",
    0x17: "DS Delfino Square",
    0x12: "GCN Waluigi Stadium",
    0x15: "DS Desert Hills",
    0x1E: "GBA Bowser's Castle 3",
    0x1D: "N64 DK's Jungle Parkway",
    0x11: "GCN Mario Circuit",
    0x18: "SNES Mario Circuit 3",
    0x16: "DS Peach Gardens",
    0x13: "GCN DK Mountain",
    0x1C: "N64 Bowser's Castle",
}

# CC byte value > location-table CC string
CC_BYTE_TO_NAME: Dict[int, str] = {
    0: "50cc",
    1: "100cc",
    2: "150cc",
}

# GP item probability table
GP_PROBS: Dict[str, List[int]] = {
    "Green Shell":        [50, 35, 20, 10,  5,  0,  0,  0,  0,  0,  0,  0],
    "Red Shell":          [15, 50, 40, 30, 20, 15, 10,  5,  0,  0,  0,  0],
    "Banana":             [75, 35, 20, 10,  5,  0,  0,  0,  0,  0,  0,  0],
    "Fake Item Box":      [35, 20, 10,  5,  5,  0,  0,  0,  0,  0,  0,  0],
    "Mushroom":           [ 0, 20, 35, 40, 30, 25, 15,  5,  0,  0,  0,  0],
    "Triple Mushrooms":   [ 0,  0, 10, 20, 35, 50, 55, 65, 70, 50, 40, 25],
    "Bob-omb":            [ 0,  5, 15, 15, 10, 10,  0,  0,  0,  0,  0,  0],
    "Blue Shell":         [ 0,  0,  0,  5, 10, 15, 10,  5,  0,  0,  0,  0],
    "Lightning":          [ 0,  0,  0,  0,  0,  0,  0,  0,  5, 15, 25, 45],
    "Star":               [ 0,  0,  0,  0,  0,  0, 15, 25, 40, 45, 40, 30],
    "Golden Mushroom":    [ 0,  0,  0,  0,  0, 10, 30, 45, 55, 60, 55, 50],
    "Mega Mushroom":      [ 0,  0,  0,  5, 10, 20, 15, 10,  0,  0,  0,  0],
    "Blooper":            [ 0,  0,  0,  5, 10, 15, 15, 10,  5,  0,  0,  0],
    "POW Block":          [ 0,  0,  0,  0, 10, 10, 15, 10,  5,  0,  0,  0],
    "Thunder Cloud":      [ 0,  0, 10, 15, 15, 10,  5,  0,  0,  0,  0,  0],
    "Bullet Bill":        [ 0,  0,  0,  0,  0,  0,  0, 10, 20, 30, 40, 50],
    "Triple Green Shells":[ 0, 10, 25, 20, 10,  0,  0,  0,  0,  0,  0,  0],
    "Triple Red Shells":  [ 0,  0,  0, 15, 25, 20, 15, 10,  0,  0,  0,  0],
    "Triple Bananas":     [25, 25, 15,  5,  0,  0,  0,  0,  0,  0,  0,  0],
}

# AP item name in-game item name
AP_TO_GAME: Dict[str, str] = {
    # Powerup unlocks
    "Powerup: Red Shell":           "Red Shell",
    "Powerup: Triple Bananas":      "Triple Bananas",
    "Powerup: Triple Green Shells": "Triple Green Shells",
    "Powerup: Triple Red Shells":   "Triple Red Shells",
    "Powerup: Bob-omb":             "Bob-omb",
    "Powerup: Blue Shell":          "Blue Shell",
    "Powerup: Fake Item Box":       "Fake Item Box",
    "Powerup: Star":                "Star",
    "Powerup: Golden Mushroom":     "Golden Mushroom",
    "Powerup: Mega Mushroom":       "Mega Mushroom",
    "Powerup: Blooper":             "Blooper",
    "Powerup: POW Block":           "POW Block",
    "Powerup: Lightning":           "Lightning",
    "Powerup: Triple Mushrooms":    "Triple Mushrooms",
    "Powerup: Bullet Bill":         "Bullet Bill",
    "Powerup: Mushroom":          "Mushroom",
    "Powerup: Green Shell":       "Green Shell",
    "Powerup: Banana":            "Banana",
    # Filler items with explicit item targets
    "Filler: Mushroom":             "Mushroom",
    "Filler: Triple Mushroom":      "Triple Mushrooms",
    "Filler: Golden Mushroom":      "Golden Mushroom",
    "Filler: Star":                 "Star",
    "Filler: Bullet Bill":          "Bullet Bill",
    "Filler: Mega Mushroom":        "Mega Mushroom",
    "Filler: Blue Shell":           "Blue Shell",
    "Filler: Red Shell":            "Red Shell",
    "Filler: Triple Red Shell":     "Triple Red Shells",
    "Filler: Bob-omb":              "Bob-omb",
    "Filler: Lightning":            "Lightning",
    "Filler: Blooper":              "Blooper",
    "Filler: POW Block":            "POW Block",
}

# Traps that have a direct in-game item equivalent (overwrites item slot immediately)
TRAP_TO_GAME: Dict[str, str] = {
    "Cloud Trap":     "Thunder Cloud",
}

# Traps held for future memory-effect implementation (no current in-game action)
FUTURE_EFFECT_TRAPS: Set[str] = {"Brake Trap", "Gas Trap", "Boost Trap","POW Trap","Lightning Trap"}

# Internal sentinel for "Filler: Random Item"
_RANDOM_TOKEN = "__random__"


# Race state reader

class RaceStateReader:
    def read_p1_lap(self) -> int:
        return read_named("P1_LAP", U8) or 0

    def read_p1_placement(self) -> int:
        return read_named("P1_PLACEMENT", U8) or 0

    def item_holder_ready(self) -> bool:
        # True once P1's item holder pointer points at valid memory
        ptr = read_named("ITEM_HOLDER_PTR", U32)
        return ptr is not None and is_valid_ptr(ptr)

    def read_track_id(self) -> int:
        try:
            return read_u8(base_address("TRACK_ID_ADDR"))
        except Exception:
            return 0xFF
        
    def read_p1_roulette_active(self) -> bool:
        roulette_display = read_named("ITEM_ROULETTE_DISPLAY", U32)
        actual_item      = read_named("ITEM_ID", U32)
        if roulette_display is None or actual_item is None:
            return False
        return roulette_display != EMPTY_ID and actual_item == EMPTY_ID

    def read_cc_name(self) -> Optional[str]:
        mirror = read_named("RACECONFIG_MIRROR", U8)
        if mirror is None:
            return None
        if mirror == 1:
            return "Mirror"
        return CC_BYTE_TO_NAME.get(read_named("RACECONFIG_CC", U8))


# Item Slot Manager

class ItemSlotManager:

    def __init__(
        self,
        room_id: str,
        queue_dir: Path,
        random_item_mode: str = "placement",  # "placement" | "uniform"
        starting_items: Optional[List[str]] = None,
        enable_item_randomization: bool = True,
        logger=None,
        mgr=None,
    ) -> None:
        self.room_id                   = room_id
        self.queue_path                = queue_dir / f"{room_id}.itemqueue"
        self.random_item_mode          = random_item_mode
        self.enable_item_randomization = enable_item_randomization
        self.logger                    = logger if logger is not None else logging.getLogger("MKWii.ItemSlot")
        self.mgr                       = mgr
        self.reporter                  = ReportHandler(mgr=self.mgr, logger=self.logger)

        # Use slot_data starting_items if provided, else set Empty array
        initial = set(starting_items) if starting_items else set([])
        self.unlocked_items: Set[str] = initial

        self.item_slot_was_empty: bool  = True
        self._roulette_start_placement: int = 0
        self._prev_roulette_active: bool    = False
        self.was_filler_trap_given: bool = False

        self._targeted_queue: Deque[str] = deque()
        self._filler_queue: Deque[str]   = deque()
        self._future_traps_queue: Deque[str] = deque()
        
        self._pending_trap: Optional[str] = None
        # Active race inject state, updated by poll(), consumed by run_inject_loop()
        self._inject_active:    bool = False
        self._inject_placement: int = 0
        # Set of (sender_player, location_id) tuples already queued.
        # Persisted so reconnects don't re-queue items from previous sessions.
        self._seen_item_ids: Set[Tuple[int, int]] = set()

        self._prev_lap: int              = 0
        self._check_sent_this_race: bool = False

        self._race_reader = RaceStateReader()

        self._load_queue()

    # Queue persistence

    def _load_queue(self) -> None:
        if not self.queue_path.exists():
            return
        try:
            data = json.loads(self.queue_path.read_text(encoding="utf-8"))
            self._targeted_queue     = deque(data.get("targeted",     []))
            self._filler_queue       = deque(data.get("filler",       []))
            self._future_traps_queue = deque(data.get("future_traps", []))
            # Stored as [[player, location], ...], convert back to set of tuples
            self._seen_item_ids      = {tuple(pair) for pair in data.get("seen_item_ids", [])}
            self.reporter.report(
                type="INFO",
                msg=f"[ItemSlot] Loaded queue from {self.queue_path.name}: "
                    f"{len(self._targeted_queue)} targeted, "
                    f"{len(self._filler_queue)} filler, "
                    f"{len(self._future_traps_queue)} future traps, "
                    f"{len(self._seen_item_ids)} seen"
            )
        except Exception as e:
            self.reporter.report(type="WARNING", msg=f"[ItemSlot] Failed to load queue: {e}")

    def _save_queue(self) -> None:
        try:
            self.queue_path.parent.mkdir(parents=True, exist_ok=True)
            self.queue_path.write_text(
                json.dumps({
                    "targeted":      list(self._targeted_queue),
                    "filler":       list(self._filler_queue),
                    "future_traps": list(self._future_traps_queue),
                    # Sets aren't JSON-serialisable; store as list of [player, location] pairs
                    "seen_item_ids": [list(pair) for pair in self._seen_item_ids],
                }, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            self.reporter.report(type="WARNING", msg=f"[ItemSlot] Failed to save queue: {e}")

    # Public API: item receiving

    def receive_item(self, ap_item_name: str, sender_player: int, location_id: int) -> None:
        item_uid = (sender_player, location_id)
        if item_uid in self._seen_item_ids:
            return

        if ap_item_name in TRAP_TO_GAME:
            self._pending_trap = TRAP_TO_GAME[ap_item_name]
            self.reporter.report(
                type="INFO",
                msg=f"[ItemSlot] Trap pending overwrite: {ap_item_name} -> {self._pending_trap}"
            )

        elif ap_item_name in FUTURE_EFFECT_TRAPS:
            self._future_traps_queue.append(ap_item_name)
            self.reporter.report(
                type="INFO",
                msg=f"[ItemSlot] Future trap queued (no current effect): {ap_item_name}"
            )

        elif ap_item_name == "Filler: Random Item":
            self._filler_queue.append(_RANDOM_TOKEN)
            self.reporter.report(
                type="INFO",
                msg="[ItemSlot] Filler: Random Item queued (resolves at give-time)"
            )

        else:
            game_name = AP_TO_GAME.get(ap_item_name)
            if game_name:
                if ap_item_name.startswith("Powerup:"):
                    self._targeted_queue.append(game_name)
                    self.reporter.report(
                        type="INFO",
                        msg=f"[ItemSlot] Targeted powerup queued: {ap_item_name} -> {game_name}"
                    )
                else:
                    self._filler_queue.append(game_name)
                    self.reporter.report(
                        type="INFO",
                        msg=f"[ItemSlot] Filler queued: {ap_item_name} -> {game_name}"
                    )
            else:
                self.reporter.report(type="DEBUG", msg=f"[ItemSlot] No item-slot action for: {ap_item_name}")

        self._seen_item_ids.add(item_uid)
        self._save_queue()

    def unlock_item_in_pool(self, game_item_name: str) -> None:
        if game_item_name in ITEM_ID:
            self.unlocked_items.add(game_item_name)
            self.reporter.report(type="DEBUG", msg=f"[ItemSlot] Unlocked pool item: {game_item_name}")

    # Pool helpers

    def _build_pool(self, placement: int) -> Tuple[List[str], List[int]]:
        clamped = max(1, min(12, placement))

        def _try(p: int):
            idx = p - 1
            items, weights = [], []
            for item_name, prob_row in GP_PROBS.items():
                w = prob_row[idx]
                if w > 0 and item_name in self.unlocked_items:
                    items.append(item_name)
                    weights.append(w)
            return items, weights

        # First search upward (better placements: clamped -> 1)
        for p in range(clamped, 0, -1):
            items, weights = _try(p)
            if items:
                if p != clamped:
                    self.reporter.report(
                        type="DEBUG",
                        msg=f"[ItemSlot] Placement {clamped} pool empty, fell back up to {p}"
                    )
                return items, weights

        # Then search downward (worse placements: clamped+1 -> 12)
        for p in range(clamped + 1, 13):
            items, weights = _try(p)
            if items:
                self.reporter.report(
                    type="DEBUG",
                    msg=f"[ItemSlot] Placement {clamped} pool empty, fell back down to {p}"
                )
                return items, weights

        # No unlocked items found anywhere, signal empty slot
        if self.unlocked_items:
            fallback = list(self.unlocked_items)
            self.reporter.report(
                type="WARNING",
                msg="[ItemSlot] All placement pools empty, using equal-weight fallback"
            )
            return fallback, [1] * len(fallback)
        self.reporter.report(type="WARNING", msg="[ItemSlot] No unlocked items at all, slot will be cleared")
        return [], []

    def _pick_pool_item(self, placement: int) -> Optional[str]:
        if self.random_item_mode == "random":
            if not self.unlocked_items or len(self.unlocked_items) <= 0:
                return None
            return choice(list(self.unlocked_items))
        items, weights = self._build_pool(placement)
        if not items or len(items) <= 0:
            return None
        return choices(items, weights=weights)[0]

    def _resolve_filler_token(self, token: str, placement: int) -> Optional[str]:
        if token == _RANDOM_TOKEN:
            return self._pick_pool_item(placement)
        return token

    # Memory read/write

    def _read_slot(self) -> Optional[Tuple[int, int]]:
        # None if P1's item holder cannot be resolved right now
        item_id = read_named("ITEM_ID", U32)
        count   = read_named("ITEM_COUNT", U32)
        if item_id is None or count is None:
            return None
        return item_id, count

    def _write_slot(self, game_item_name: str) -> bool:
        item_id = ITEM_ID.get(game_item_name)
        if item_id is None:
            self.reporter.report(type="WARNING", msg=f"[ItemSlot] Unknown item for write: {game_item_name}")
            return False
        count = _ITEM_COUNT_MAP.get(item_id, 1)
        if not (write_named("ITEM_ID", U32, item_id) and write_named("ITEM_COUNT", U32, count)):
            self.reporter.report(type="WARNING", msg=f"[ItemSlot] Could not write slot: {game_item_name}")
            return False
        if item_id == ITEM_ID["Golden Mushroom"]:
            write_named("ITEM_GM_ACTIVATION_FLAG", U32, 0x01000000)
        self.reporter.report(
            type="INFO",
            msg=f"[ItemSlot] Wrote: {game_item_name} (id=0x{item_id:02X} count={count})"
        )
        return True

    def _clear_slot(self) -> None:
        write_named("ITEM_ID", U32, EMPTY_ID)
        write_named("ITEM_COUNT", U32, 0)
    
    # Race lifecycle

    def _on_new_race(self) -> None:
        self._roulette_start_placement  = 0
        self._prev_roulette_active      = False
        self.item_slot_was_empty        = True
        self.was_filler_trap_given      = False
        self._check_sent_this_race      = False
        self._pending_trap              = None
        self.reporter.report(type="DEBUG", msg="[ItemSlot] New race: per-race state reset")

    # Main poll

    def poll(
        self,
        on_race_check: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        lap       = self._race_reader.read_p1_lap()
        placement = self._race_reader.read_p1_placement()
        holder_ok = self._race_reader.item_holder_ready()

        if self._prev_lap == 0 and lap >= 1:
            self._on_new_race()
        self._prev_lap = lap

        if (
            on_race_check
            and lap == 4
            and placement == 1
            and not self._check_sent_this_race
        ):
            track_id  = self._race_reader.read_track_id()
            cc_name   = self._race_reader.read_cc_name()
            track_name = TRACK_ID_TO_NAME.get(track_id)
            if track_name and cc_name:
                on_race_check(track_name, cc_name)
            self._check_sent_this_race = True

        # Store active state for the fast inject loop
        if lap < 1 or lap >= 4 or not holder_ok or not self.enable_item_randomization:
            self._inject_active    = False
            self._inject_placement = 0
        else:
            self._inject_active    = True
            self._inject_placement = placement

    async def run_inject_loop(self) -> None:
        """
        Fast inject loop - runs at 0.016s (every frame).
        Started as an asyncio task by the client after the manager is created.
        Only does item injection; lap/check logic stays in poll().
        """
        import asyncio
        while True:
            try:
                if self._inject_active:
                    self._inject(self._inject_placement)
            except Exception as e:
                self.reporter.report(type="WARNING", msg=f"[ItemSlot] Inject loop error: {e}")
            await asyncio.sleep(0.016)

    def _inject(self, placement: int) -> None:
        slot = self._read_slot()
        if slot is None:
            return
        item_id, count = slot

        roulette_active = self._race_reader.read_p1_roulette_active()
        if roulette_active:
            if not self._prev_roulette_active:
                self._roulette_start_placement = placement
            self._prev_roulette_active = True
            return
        self._prev_roulette_active = False

        is_empty = (item_id == EMPTY_ID or count == 0)
        prev_was_empty = self.item_slot_was_empty

        if is_empty and not prev_was_empty:
            self.was_filler_trap_given = False

        if self._pending_trap is not None:
            trap_item = self._pending_trap
            self._pending_trap = None
            if self._write_slot(trap_item):
                self.was_filler_trap_given = True
                self.item_slot_was_empty   = False
            return

        if is_empty and self._targeted_queue:
            game_item = self._targeted_queue.popleft()
            self._save_queue()
            if self._write_slot(game_item):
                self.item_slot_was_empty = False
            return

        if is_empty and self._filler_queue and not self.was_filler_trap_given:
            token = self._filler_queue.popleft()
            self._save_queue()
            game_item = self._resolve_filler_token(token, placement)
            if game_item is None:
                self._clear_slot()
                self.reporter.report(type="INFO", msg="[ItemSlot] No unlocked items, cleared slot")
            elif self._write_slot(game_item):
                self.was_filler_trap_given = True
                self.item_slot_was_empty   = False
            return

        self.item_slot_was_empty = is_empty

        if prev_was_empty and not is_empty and not self.was_filler_trap_given:
            game_item = self._pick_pool_item(self._roulette_start_placement)
            if game_item is None:
                self._clear_slot()
                self.reporter.report(type="INFO", msg="[ItemSlot] No unlocked items, cleared slot")
            else:
                self._write_slot(game_item)