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

Memory addresses are PAL (RMCP01) verified against testge.py.

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
import struct
from collections import deque
from pathlib import Path
from random import choices, choice
from typing import Callable, Deque, Dict, List, Optional, Set, Tuple

import dolphin_memory_engine as dme

logger = logging.getLogger("MKWii.ItemSlot")

# Pointer to the race manager base; player array is at base + 0xAC
_RACE_MGR_PTR_ADDR  = 0x809BD730
_PLAYER_ARRAY_OFFSET = 0xAC

# Static pointer chain for item holders
_ITEM_HOLDER_STATIC     = 0x809C3618
_ITEM_HOLDER_PTR_OFFSET = 0x14

# Current track ID (1 byte, direct address)
_TRACK_ID_ADDR = 0x809C26B3

# CC/mirror bytes sit behind a pointer
_CC_PTR_BASE    = 0x809BD728
_CC_OFFSET      = 0x175F
_MIRROR_OFFSET  = 0x1783

# Per-player offsets (relative to player pointer)
_PLACEMENT_OFFSET = 0x20
_LAP_OFFSET       = 0x25

# Item holder offsets (relative to item-holder pointer for a player)
_ITEM_ID_OFFSET    = 0x8C
_ITEM_COUNT_OFFSET = 0x90

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
    0x1E: "GBA Bowser Castle 3",
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

# Items always unlocked from a fresh save (start pool)
DEFAULT_UNLOCKED_ITEMS: Set[str] = {"Banana", "Green Shell", "Fake Item Box", "Mushroom"}

# Internal sentinel for "Filler: Random Item"
_RANDOM_TOKEN = "__random__"


# Helper methods

def _read_u8(addr: int) -> int:
    return struct.unpack(">B", dme.read_bytes(addr, 1))[0]

def _read_u32(addr: int) -> int:
    return struct.unpack(">I", dme.read_bytes(addr, 4))[0]

def _write_u32(addr: int, value: int) -> None:
    dme.write_bytes(addr, struct.pack(">I", value))

def _is_valid_mem1(addr: int) -> bool:
    return 0x80000000 <= addr <= 0x817FFFFF


# Race state reader

class RaceStateReader:
    def read_player_ptr(self, player_idx: int = 0) -> int:
        try:
            race_mgr   = _read_u32(_RACE_MGR_PTR_ADDR)
            array_base = race_mgr + _PLAYER_ARRAY_OFFSET
            ptr        = _read_u32(array_base + player_idx * 4)
            return ptr if _is_valid_mem1(ptr) else 0
        except Exception:
            return 0

    def read_p1_lap(self) -> int:
        ptr = self.read_player_ptr(0)
        if not ptr:
            return 0
        try:
            return _read_u8(ptr + _LAP_OFFSET)
        except Exception:
            return 0

    def read_p1_placement(self) -> int:
        ptr = self.read_player_ptr(0)
        if not ptr:
            return 0
        try:
            return _read_u8(ptr + _PLACEMENT_OFFSET)
        except Exception:
            return 0

    def read_p1_item_holder_ptr(self) -> int:
        try:
            item_holder = _read_u32(_ITEM_HOLDER_STATIC)
            ptr = _read_u32(item_holder + _ITEM_HOLDER_PTR_OFFSET)
            return ptr if _is_valid_mem1(ptr) else 0
        except Exception:
            return 0

    def read_track_id(self) -> int:
        try:
            return _read_u8(_TRACK_ID_ADDR)
        except Exception:
            return 0xFF

    def read_cc_name(self) -> Optional[str]:
        try:
            base   = _read_u32(_CC_PTR_BASE)
            mirror = _read_u8(base + _MIRROR_OFFSET)
            if mirror == 1:
                return "Mirror"
            cc_byte = _read_u8(base + _CC_OFFSET)
            return CC_BYTE_TO_NAME.get(cc_byte)
        except Exception:
            return None


# Item Slot Manager

class ItemSlotManager:

    def __init__(
        self,
        room_id: str,
        queue_dir: Path,
        random_item_mode: str = "placement",  # "placement" | "uniform"
        starting_items: Optional[List[str]] = None,
        enable_item_randomization: bool = True,
    ) -> None:
        self.room_id                   = room_id
        self.queue_path                = queue_dir / f"{room_id}.itemqueue"
        self.random_item_mode          = random_item_mode
        self.enable_item_randomization = enable_item_randomization

        # Use slot_data starting_items if provided, else the hardcoded default
        initial = set(starting_items) if starting_items else set(DEFAULT_UNLOCKED_ITEMS)
        self.unlocked_items: Set[str] = initial

        self.item_slot_was_empty: bool  = True
        self.was_filler_trap_given: bool = False

        self._targeted_queue: Deque[str] = deque()
        self._filler_queue: Deque[str]   = deque()
        self._future_traps_queue: Deque[str] = deque()

        self._pending_trap: Optional[str] = None
        # Active race inject state — updated by poll(), consumed by run_inject_loop()
        self._inject_ih_ptr:    int = 0
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
            # Stored as [[player, location], ...] — convert back to set of tuples
            self._seen_item_ids      = {tuple(pair) for pair in data.get("seen_item_ids", [])}
            logger.info(
                f"[ItemSlot] Loaded queue from {self.queue_path.name}: "
                f"{len(self._targeted_queue)} targeted, "
                f"{len(self._filler_queue)} filler, "
                f"{len(self._future_traps_queue)} future traps, "
                f"{len(self._seen_item_ids)} seen"
            )
        except Exception as e:
            logger.warning(f"[ItemSlot] Failed to load queue: {e}")

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
            logger.warning(f"[ItemSlot] Failed to save queue: {e}")

    # Public API: item receiving

    def receive_item(self, ap_item_name: str, sender_player: int, location_id: int) -> None:
        item_uid = (sender_player, location_id)
        if item_uid in self._seen_item_ids:
            return

        if ap_item_name in TRAP_TO_GAME:
            self._pending_trap = TRAP_TO_GAME[ap_item_name]
            logger.info(f"[ItemSlot] Trap pending overwrite: {ap_item_name} -> {self._pending_trap}")

        elif ap_item_name in FUTURE_EFFECT_TRAPS:
            self._future_traps_queue.append(ap_item_name)
            logger.info(f"[ItemSlot] Future trap queued (no current effect): {ap_item_name}")

        elif ap_item_name == "Filler: Random Item":
            self._filler_queue.append(_RANDOM_TOKEN)
            logger.info("[ItemSlot] Filler: Random Item queued (resolves at give-time)")

        else:
            game_name = AP_TO_GAME.get(ap_item_name)
            if game_name:
                if ap_item_name.startswith("Powerup:"):
                    self._targeted_queue.append(game_name)
                    logger.info(f"[ItemSlot] Targeted powerup queued: {ap_item_name} -> {game_name}")
                else:
                    self._filler_queue.append(game_name)
                    logger.info(f"[ItemSlot] Filler queued: {ap_item_name} -> {game_name}")
            else:
                logger.debug(f"[ItemSlot] No item-slot action for: {ap_item_name}")

        self._seen_item_ids.add(item_uid)
        self._save_queue()

    def unlock_item_in_pool(self, game_item_name: str) -> None:
        if game_item_name in ITEM_ID:
            self.unlocked_items.add(game_item_name)
            logger.debug(f"[ItemSlot] Unlocked pool item: {game_item_name}")

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
                    logger.debug(
                        f"[ItemSlot] Placement {clamped} pool empty, fell back up to {p}"
                    )
                return items, weights

        # Then search downward (worse placements: clamped+1 -> 12)
        for p in range(clamped + 1, 13):
            items, weights = _try(p)
            if items:
                logger.debug(
                    f"[ItemSlot] Placement {clamped} pool empty, fell back down to {p}"
                )
                return items, weights

        # No unlocked items found anywhere — signal empty slot
        if self.unlocked_items:
            fallback = list(self.unlocked_items)
            logger.warning("[ItemSlot] All placement pools empty — using equal-weight fallback")
            return fallback, [1] * len(fallback)
        logger.warning("[ItemSlot] No unlocked items at all — slot will be cleared")
        return [], []

    def _pick_pool_item(self, placement: int) -> Optional[str]:
        if self.random_item_mode == "random":
            if not self.unlocked_items:
                return None
            return choice(list(self.unlocked_items))
        items, weights = self._build_pool(placement)
        if not items:
            return None
        return choices(items, weights=weights)[0]

    def _resolve_filler_token(self, token: str, placement: int) -> Optional[str]:
        if token == _RANDOM_TOKEN:
            return self._pick_pool_item(placement)
        return token

    # Memory read/write

    def _read_slot(self, ih_ptr: int) -> Tuple[int, int]:
        item_id = _read_u32(ih_ptr + _ITEM_ID_OFFSET)
        count   = _read_u32(ih_ptr + _ITEM_COUNT_OFFSET)
        return item_id, count

    def _write_slot(self, ih_ptr: int, game_item_name: str) -> bool:
        item_id = ITEM_ID.get(game_item_name)
        if item_id is None:
            logger.warning(f"[ItemSlot] Unknown item for write: {game_item_name}")
            return False
        count = _ITEM_COUNT_MAP.get(item_id, 1)
        _write_u32(ih_ptr + _ITEM_ID_OFFSET,    item_id)
        _write_u32(ih_ptr + _ITEM_COUNT_OFFSET, count)
        logger.info(f"[ItemSlot] Wrote: {game_item_name} (id=0x{item_id:02X} count={count})")
        return True

    # Race lifecycle

    def _on_new_race(self) -> None:
        self.item_slot_was_empty     = True
        self.was_filler_trap_given   = False
        self._check_sent_this_race   = False
        self._pending_trap           = None
        logger.debug("[ItemSlot] New race: per-race state reset")

    # Main poll

    def poll(
        self,
        on_race_check: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        lap       = self._race_reader.read_p1_lap()
        placement = self._race_reader.read_p1_placement()
        ih_ptr    = self._race_reader.read_p1_item_holder_ptr()

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
        if lap < 1 or lap >= 4 or ih_ptr == 0 or not self.enable_item_randomization:
            self._inject_ih_ptr    = 0
            self._inject_placement = 0
        else:
            self._inject_ih_ptr    = ih_ptr
            self._inject_placement = placement

    async def run_inject_loop(self) -> None:
        """
        Fast inject loop — runs at 0.125s (quarter of the main 0.5s poll).
        Started as an asyncio task by the client after the manager is created.
        Only does item injection; lap/check logic stays in poll().
        """
        import asyncio
        while True:
            try:
                if self._inject_ih_ptr != 0:
                    self._inject(self._inject_ih_ptr, self._inject_placement)
            except Exception as e:
                logger.warning(f"[ItemSlot] Inject loop error: {e}")
            await asyncio.sleep(0.125)

    def _inject(self, ih_ptr: int, placement: int) -> None:
        try:
            item_id, count = self._read_slot(ih_ptr)
        except Exception as e:
            logger.warning(f"[ItemSlot] Slot read error: {e}")
            return

        is_empty = (item_id == EMPTY_ID or count == 0)
        prev_was_empty = self.item_slot_was_empty

        if is_empty and not prev_was_empty:
            self.was_filler_trap_given = False

        if self._pending_trap is not None:
            trap_item = self._pending_trap
            self._pending_trap = None
            if self._write_slot(ih_ptr, trap_item):
                self.was_filler_trap_given = True
                self.item_slot_was_empty   = False
            return

        if is_empty and self._targeted_queue:
            game_item = self._targeted_queue.popleft()
            self._save_queue()
            if self._write_slot(ih_ptr, game_item):
                self.item_slot_was_empty = False
            return

        if is_empty and self._filler_queue and not self.was_filler_trap_given:
            token = self._filler_queue.popleft()
            self._save_queue()
            game_item = self._resolve_filler_token(token, placement)
            if game_item is None:
                _write_u32(ih_ptr + _ITEM_ID_OFFSET,    EMPTY_ID)
                _write_u32(ih_ptr + _ITEM_COUNT_OFFSET, 0)
                logger.info("[ItemSlot] No unlocked items - cleared slot")
            elif self._write_slot(ih_ptr, game_item):
                self.was_filler_trap_given = True
                self.item_slot_was_empty   = False
            return

        self.item_slot_was_empty = is_empty

        if prev_was_empty and not is_empty and not self.was_filler_trap_given:
            game_item = self._pick_pool_item(placement)
            if game_item is None:
                _write_u32(ih_ptr + _ITEM_ID_OFFSET,    EMPTY_ID)
                _write_u32(ih_ptr + _ITEM_COUNT_OFFSET, 0)
                logger.info("[ItemSlot] No unlocked items — cleared slot")
            else:
                self._write_slot(ih_ptr, game_item)