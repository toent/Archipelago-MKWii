"""
Mario Kart Wii (PAL/RMCP01) - Dolphin Memory Interface

Provides direct memory access to MKWii via dolphin-memory-engine for reading
and writing unlock flags, GP results, and mode settings in real time.

Memory layout (PAL):
    System manager pointer: 0x809BD748
    Runtime unlock flags:   manager + 0x9034 (per-license, stride 0x93F0)
    rksys.dat RAM buffer:   *(manager + 0x14) (RKSD header at offset 0)

Unlock flags are dual-written to both the runtime structure (instant in-game
effect) and the rksys buffer (persists when the game auto-saves).

RaceConfig cup locking (PAL):
    RaceConfig pointer:     0x809BD728 (points to MEM2)
    Selected cup:           RaceConfig + 0x177B (u8, cup ID 0-7)
    Selected course:        RaceConfig + 0x175B (u8, track ID)
    CC setting:             RaceConfig + 0x175F (u8, 0=50cc 1=100cc 2=150cc)
    Mirror flag:            RaceConfig + 0x1783 (u8, 1=mirror)

Base cups (Mushroom, Flower, Shell, Banana) have no save-file unlock bits.
They are blocked at runtime by overwriting the RaceConfig cup/course fields
to redirect the player to an unlocked cup.

All bit offsets verified against 25 progressive PAL save snapshots.
RaceConfig offsets verified via memory snapshot diffing.
"""
import logging
import struct
from typing import Dict, Optional, Set, Tuple

import dolphin_memory_engine as dme
import asyncio
from dolphin_manager import DolphinManager
from reporting import report_handler as _report_handler

logger = logging.getLogger("MKWii.Memory")

# PAL memory addresses

SYSTEM_MANAGER_PTR = 0x809BD748
RAW_SAVE_OFFSET = 0x14
RUNTIME_UNLOCK_OFFSET = 0x9034
RUNTIME_LICENSE_STRIDE = 0x93F0
SAVE_LICENSE_STRIDE = 0x8CC0

# Unlock bytes span 0x0038..0x003F in the per-license save block
SAVE_UNLOCK_START = 0x0038
UNLOCK_BYTE_COUNT = 8

# Per-license base offsets within the RKSD buffer (for GP result reads)
SAVE_LICENSE_OFFSETS = [0x0008, 0x8CC8, 0x11988, 0x1A648]

# GP data layout within a license block
GP_CUP_DATA_BASE = 0x1C0
GP_CUP_SIZE = 0x60
GP_CC_OFFSETS: Dict[str, int] = {
    "50cc":   0x000,
    "100cc":  0x300,
    "150cc":  0x600,
    "Mirror": 0x900,
}

# RaceConfig addresses (for cup locking)
RACE_CONFIG_PTR     = 0x809BD728
RACECONFIG_CUP_OFFSET    = 0x177B  # u8: selected cup ID (0-7)
RACECONFIG_COURSE_OFFSET = 0x175B  # u8: selected track ID
RACECONFIG_CC_OFFSET     = 0x175F  # u8: 0=50cc, 1=100cc, 2=150cc
RACECONFIG_MIRROR_OFFSET = 0x1783  # u8: 1=mirror

# Cup ID to name mapping
CUP_ID_TO_NAME: Dict[int, str] = {
    0: "Mushroom Cup", 1: "Flower Cup", 2: "Star Cup", 3: "Special Cup",
    4: "Shell Cup", 5: "Banana Cup", 6: "Leaf Cup", 7: "Lightning Cup",
}

CUP_NAME_TO_ID: Dict[str, int] = {v: k for k, v in CUP_ID_TO_NAME.items()}

# First track ID for each cup (used when redirecting to an unlocked cup)
CUP_FIRST_TRACK: Dict[int, int] = {
    0: 0x08,  # Mushroom -> Luigi Circuit
    1: 0x00,  # Flower -> Mario Circuit
    2: 0x09,  # Star -> Daisy Circuit
    3: 0x0E,  # Special -> Dry Dry Ruins
    4: 0x10,  # Shell -> GCN Peach Beach
    5: 0x1B,  # Banana -> N64 Sherbet Land
    6: 0x15,  # Leaf -> DS Desert Hills
    7: 0x18,  # Lightning -> SNES Mario Circuit 3
}

# Track ID to cup ID mapping (for race-level fallback detection)
TRACK_TO_CUP: Dict[int, int] = {
    # Mushroom Cup (0)
    0x08: 0, 0x01: 0, 0x02: 0, 0x04: 0,
    # Flower Cup (1)
    0x00: 1, 0x05: 1, 0x06: 1, 0x07: 1,
    # Star Cup (2)
    0x09: 2, 0x0F: 2, 0x0B: 2, 0x03: 2,
    # Special Cup (3)
    0x0E: 3, 0x0A: 3, 0x0C: 3, 0x0D: 3,
    # Shell Cup (4)
    0x10: 4, 0x14: 4, 0x19: 4, 0x1A: 4,
    # Banana Cup (5)
    0x1B: 5, 0x1F: 5, 0x17: 5, 0x12: 5,
    # Leaf Cup (6)
    0x15: 6, 0x1E: 6, 0x1D: 6, 0x11: 6,
    # Lightning Cup (7)
    0x18: 7, 0x16: 7, 0x13: 7, 0x1C: 7,
}

# Unlock bit tables
# Each entry: (absolute_offset_from_license_start, bit_index)
CHARACTER_IDS: Dict[str, Optional[Tuple[int, int]]] = {
    "Baby Daisy":   (0x003B, 2),
    "Baby Luigi":   (0x003B, 3),
    "Dry Bones":    (0x003B, 0),
    "Bowser Jr.":   (0x003B, 5),
    "Toadette":     (0x003B, 1),
    "King Boo":     (0x003A, 1),
    "Dry Bowser":   (0x003A, 0),
    "Funky Kong":   (0x003A, 2),
    "Rosalina":     (0x003A, 3),
    "Diddy Kong":   (0x003B, 4),
    "Daisy":        (0x003B, 6),
    "Birdo":        (0x003B, 7),
    "Mii Outfit A": (0x003A, 4),
    "Mii Outfit B": (0x003A, 5),
}

VEHICLE_IDS: Dict[str, Optional[Tuple[int, int]]] = {
    # Unlockable karts (PAL primary name first, US alias follows)
    "Turbo Blooper":   (0x003F, 5),
    "Cheep Charger":   (0x003F, 2),
    "Royal Racer":     (0x003F, 6),
    "Blue Falcon":     (0x003F, 4),
    "Rally Romper":    (0x003F, 3),
    "B. Dasher Mk 2":  (0x003F, 7),
    "B Dasher Mk 2":   (0x003F, 7),
    "Dragonetti":      (0x003E, 2),
    "Aero Glider":     (0x003E, 1),
    "Piranha Prowler": (0x003E, 0),
    # Unlockable bikes
    "Magicruiser":     (0x003E, 4),
    "Twinkle Star":    (0x003D, 1),
    "Rapide":          (0x003E, 6),
    "Nitrocycle":      (0x003E, 7),
    "Quacker":         (0x003E, 3),
    "Dolphin Dasher":  (0x003D, 0),
    "Bubble Bike":     (0x003E, 5),
    "Phantom":         (0x003D, 3),
    "Torpedo":         (0x003D, 2),
}

CUP_UNLOCK_IDS: Dict[str, Tuple[int, int]] = {
    # Save-file unlock bits (Star, Special, Leaf, Lightning only)
    # Base cups (Mushroom, Flower, Shell, Banana) have NO save bits
    # and are blocked via RaceConfig redirect instead.
    # 50cc
    "Star Cup 50cc":       (0x003A, 6),
    "Special Cup 50cc":    (0x0039, 2),
    "Leaf Cup 50cc":       (0x0039, 6),
    "Lightning Cup 50cc":  (0x0038, 2),
    # 100cc
    "Star Cup 100cc":      (0x003A, 7),
    "Special Cup 100cc":   (0x0039, 3),
    "Leaf Cup 100cc":      (0x0039, 7),
    "Lightning Cup 100cc": (0x0038, 3),
    # 150cc
    "Star Cup 150cc":      (0x0039, 0),
    "Special Cup 150cc":   (0x0039, 4),
    "Leaf Cup 150cc":      (0x0038, 0),
    "Lightning Cup 150cc": (0x0038, 4),
    # Mirror
    "Star Cup Mirror":     (0x0039, 1),
    "Special Cup Mirror":  (0x0039, 5),
    "Leaf Cup Mirror":     (0x0038, 1),
    "Lightning Cup Mirror": (0x0038, 5),
}

# Base cup item names (no save bits, blocked via RaceConfig)
BASE_CUP_NAMES = {"Mushroom Cup", "Flower Cup", "Shell Cup", "Banana Cup"}

MODE_IDS: Dict[str, Tuple[int, int]] = {
    "50cc Karts/Bikes":  (0x0038, 6),
    "100cc Karts/Bikes": (0x0038, 7),
    "Mirror mode":       (0x003D, 4),
}

# Combined lookup for all items that have save bits
ALL_UNLOCK_IDS: Dict[str, Optional[Tuple[int, int]]] = {}
ALL_UNLOCK_IDS.update(CHARACTER_IDS)
ALL_UNLOCK_IDS.update({k: v for k, v in VEHICLE_IDS.items() if v is not None})
ALL_UNLOCK_IDS.update(CUP_UNLOCK_IDS)
ALL_UNLOCK_IDS.update(MODE_IDS)

# Cup/GP tables
CUP_TROPHY_IDS: Dict[str, int] = {
    "Mushroom Cup": 0, "Flower Cup": 1, "Star Cup": 2, "Special Cup": 3,
    "Shell Cup": 4, "Banana Cup": 5, "Leaf Cup": 6, "Lightning Cup": 7,
}

# PAL <-> US name aliases for vehicles
_VEHICLE_ALIASES: Set[frozenset] = {
    frozenset({"Turbo Blooper", "Super Blooper"}),
    frozenset({"Royal Racer", "Daytripper"}),
    frozenset({"Rally Romper", "Tiny Titan"}),
    frozenset({"Magicruiser", "Magikruiser"}),
    frozenset({"B. Dasher Mk 2", "B Dasher Mk 2", "Sprinter"}),
    frozenset({"Dragonetti", "Honeycoupe"}),
    frozenset({"Aero Glider", "Jetsetter"}),
    frozenset({"Twinkle Star", "Shooting Star"}),
    frozenset({"Rapide", "Zip Zip"}),
    frozenset({"Nitrocycle", "Sneakster"}),
    frozenset({"Bubble Bike", "Jet Bubble"}),
    frozenset({"Torpedo", "Spear"}),
    frozenset({"Baby Booster", "Booster Seat"}),
    frozenset({"Nostalgia 1", "Classic Dragster"}),
    frozenset({"Concerto", "Wild Wing"}),
    frozenset({"Bowser Bike", "Flame Runner"}),
    frozenset({"Nanobike", "Bit Bike"}),
    frozenset({"Bon Bon", "Sugarscoot"}),
}


def get_vehicle_alternates(vehicle_name: str) -> Set[str]:
    """Return all regional name variants for a vehicle."""
    for group in _VEHICLE_ALIASES:
        if vehicle_name in group:
            return set(group)
    return {vehicle_name}


# Dolphin Memory Manager
class DolphinMemoryManager:
    """Reads and writes MKWii game state via Dolphin's memory interface."""

    def __init__(self, license_num: int = 1, logger=None) -> None:
        self.license_idx = license_num - 1
        self._manager_ptr: Optional[int] = None
        self._runtime_base: Optional[int] = None
        self._save_buffer_base: Optional[int] = None
        self._hooked: bool = False
        self._suppress_warnings: Dict[str, bool] = {}
        self.mgr: DolphinManager = DolphinManager()
        self.logger = logger if logger is not None else logging.getLogger("MKWii.Memory")
        self.unlockblock_patch_applied_once = False

    @property
    def is_connected(self) -> bool:
        if not self._hooked:
            return False

        try:
            if not dme.is_hooked():
                self._hooked = False
                return False

            # Validate runtime pointer still readable
            if not self._runtime_base:
                self._hooked = False
                return False

            dme.read_bytes(self._runtime_base, 1)
            return True

        except Exception:
            # Pointer chain invalid -> force full re-hook
            self._hooked = False
            self._manager_ptr = None
            self._runtime_base = None
            self._save_buffer_base = None
            return False

    async def async_hook(self) -> bool:
        """Hook to Dolphin and resolve the MKWii pointer chain.

        Returns True if fully connected with valid save system pointers.
        Silently returns False during normal boot (memory not yet mapped).
        """
        self.logger.info("Attempting to hook to Dolphin and resolve MKWii pointers...")
        _report_handler("INFO: Attempting to hook to Dolphin and resolve MKWii pointers...", self.mgr)
        try:
            # Only hook if not already hooked
            if not dme.is_hooked():
                dme.hook()

            if not dme.is_hooked():
                self.logger.warning("DME failed to hook!")
                _report_handler("WARNING: DME failed to hook!", self.mgr)
                return False

            self.logger.info("DME hooked successfully, resolving pointers...")
            _report_handler("INFO: DME hooked successfully, resolving pointers...", self.mgr)
            return await self.async_resolve_pointers()
        except Exception as e:
            self.logger.error(f"Hook failed unexpectedly: {e}")
            _report_handler(f"ERROR: Hook failed unexpectedly: {e}", self.mgr)
            try:
                dme.un_hook()
            except Exception:
                pass
            self._hooked = False
            return False

    async def async_resolve_pointers(self) -> bool:
        """Internal: walk the pointer chain and validate the save system."""
        # Verify PAL game ID - may throw if emulated memory isn't mapped yet
        try:
            game_id = dme.read_bytes(0x80000000, 6).decode("ascii", errors="replace")
        except Exception as e:
            self.logger.warning(f"Waiting for Dolphin to load game: {e}")
            _report_handler(f"WARNING: Waiting for Dolphin to load game: {e}", self.mgr)    
            return False

        if game_id != "RMCP01":
            self.logger.warning(f"Wrong game ID: {game_id} (expected RMCP01)")
            _report_handler(f"WARNING: Wrong game ID: {game_id} (expected RMCP01)", self.mgr)
            return False

        # Resolve system manager pointer
        try:
            raw = dme.read_bytes(SYSTEM_MANAGER_PTR, 4)
        except Exception as e:
            self.logger.warning(f"Game still initializing: {e}")
            _report_handler(f"WARNING: Game still initializing: {e}", self.mgr)
            return False

        mgr_ptr = struct.unpack(">I", raw)[0]
        await asyncio.sleep(0.1)
        if mgr_ptr < 0x80000000:
            self.logger.warning("Waiting for game to load past title screen...")
            _report_handler("WARNING: Waiting for game to load past title screen...", self.mgr)
            return False

        await asyncio.sleep(0.1)
 
        # Resolve save buffer pointer and verify RKSD magic
        try:
            save_ptr_raw = dme.read_bytes(mgr_ptr + RAW_SAVE_OFFSET, 4)
        except Exception as e:
            self.logger.warning(f"Save system loading: {e}")
            _report_handler(f"WARNING: Save system loading: {e}", self.mgr)
            return False

        save_ptr = struct.unpack(">I", save_ptr_raw)[0]
        await asyncio.sleep(0.1)
        
        if save_ptr < 0x80000000:
            self.logger.warning(f"Save system loading: {save_ptr}")
            _report_handler(f"WARNING: Save system loading: {save_ptr}", self.mgr)
            return False

        await asyncio.sleep(0.1)

        try:
            magic = dme.read_bytes(save_ptr, 4)
        except Exception as e:
            self.logger.warning(f"Save buffer not ready: {e}")
            _report_handler(f"WARNING: Save buffer not ready: {e}", self.mgr)
            return False
        
        await asyncio.sleep(0.1)

        if magic != b"RKSD":
            self.logger.warning(f"Save buffer initializing (magic: {magic.hex()})...")
            _report_handler(f"WARNING: Save buffer initializing (magic: {magic.hex()})...", self.mgr)
            return False

        # All pointers valid
        self._manager_ptr = mgr_ptr
        self._save_buffer_base = save_ptr
        self._runtime_base = (
            mgr_ptr + RUNTIME_UNLOCK_OFFSET + self.license_idx * RUNTIME_LICENSE_STRIDE
        )
        self._hooked = True
        self._suppress_warnings.clear()

        self.logger.info(
            f"Hooked: manager=0x{mgr_ptr:08X} "
            f"runtime=0x{self._runtime_base:08X} "
            f"rksys=0x{save_ptr:08X}"
        )
        _report_handler(
            f"Hooked: manager=0x{mgr_ptr:08X} "
            f"runtime=0x{self._runtime_base:08X} "
            f"rksys=0x{save_ptr:08X}", self.mgr
        )
        return True

    def unhook(self) -> None:
        try:
            dme.un_hook()
        except Exception:
            pass
        self._hooked = False
        self._manager_ptr = None
        self._runtime_base = None
        self._save_buffer_base = None

    # Unlock read/write

    def _runtime_addr(self, abs_offset: int) -> int:
        """Convert an absolute save offset (0x0038-0x003F) to a runtime address."""
        return self._runtime_base + (abs_offset - SAVE_UNLOCK_START)

    def _save_addr(self, abs_offset: int) -> int:
        """Convert an absolute save offset to the rksys buffer address."""
        return self._save_buffer_base + abs_offset + self.license_idx * SAVE_LICENSE_STRIDE

    def read_unlock_byte(self, abs_offset: int) -> int:
        return struct.unpack("B", dme.read_bytes(self._runtime_addr(abs_offset), 1))[0]

    def read_all_unlock_bytes(self) -> bytes:
        return dme.read_bytes(self._runtime_base, UNLOCK_BYTE_COUNT)

    def is_item_unlocked(self, item_name: str) -> bool:
        lookup = ALL_UNLOCK_IDS.get(item_name)
        if lookup is None:
            return True  # Starting items are always available
        abs_offset, bit = lookup
        return bool(self.read_unlock_byte(abs_offset) & (1 << bit))

    def write_unlock_bit(self, abs_offset: int, bit: int, value: bool = True) -> Tuple[int, int]:
        """Set or clear an unlock bit in both runtime and save buffer.

        Returns (old_byte, new_byte) from the runtime write.
        """
        rt_addr = self._runtime_addr(abs_offset)
        old = struct.unpack("B", dme.read_bytes(rt_addr, 1))[0]
        new = old | (1 << bit) if value else old & ~(1 << bit)
        dme.write_bytes(rt_addr, struct.pack("B", new))

        # Mirror to save buffer (non-critical)
        try:
            sv_addr = self._save_addr(abs_offset)
            sv_old = struct.unpack("B", dme.read_bytes(sv_addr, 1))[0]
            sv_new = sv_old | (1 << bit) if value else sv_old & ~(1 << bit)
            dme.write_bytes(sv_addr, struct.pack("B", sv_new))
        except Exception:
            pass

        return old, new

    def unlock_item(self, item_name: str) -> bool:
        """Unlock an item by name. Returns True if the bit actually changed."""
        lookup = ALL_UNLOCK_IDS.get(item_name)
        if lookup is None:
            return False
        old, new = self.write_unlock_bit(*lookup, value=True)
        return old != new

    def lock_item(self, item_name: str) -> bool:
        """Lock an item by name. Returns True if the bit actually changed."""
        lookup = ALL_UNLOCK_IDS.get(item_name)
        if lookup is None:
            return False
        old, new = self.write_unlock_bit(*lookup, value=False)
        return old != new

    def unlock_mirror_mode(self) -> None:
        self.write_unlock_bit(0x003D, 4, value=True)

    def lock_all_unlocks(self) -> None:
        """Zero all unlock bytes (fresh AP state)."""
        for i in range(UNLOCK_BYTE_COUNT):
            offset = SAVE_UNLOCK_START + i
            dme.write_bytes(self._runtime_addr(offset), struct.pack("B", 0))
            try:
                dme.write_bytes(self._save_addr(offset), struct.pack("B", 0))
            except Exception:
                pass

    # GP result reading
    def _gp_cup_addr(self, cup_id: int, cc: str) -> Optional[int]:
        cc_offset = GP_CC_OFFSETS.get(cc)
        if cc_offset is None:
            return None
        license_base = SAVE_LICENSE_OFFSETS[self.license_idx]
        offset = license_base + GP_CUP_DATA_BASE + cc_offset + cup_id * GP_CUP_SIZE
        return self._save_buffer_base + offset

    def get_gp_result(self, cup_id: int, cc: str) -> Tuple[str, str]:
        """Read a Grand Prix result from the rksys buffer.

        Returns (trophy, rank) where trophy is one of "gold"/"silver"/"bronze"/"none"
        and rank is one of "3_star"/"2_star"/"1_star"/"A"-"F"/"D".
        """
        addr = self._gp_cup_addr(cup_id, cc)
        if addr is None:
            return ("none", "D")

        try:
            completion = struct.unpack("B", dme.read_bytes(addr + 0x52, 1))[0]
            if not (completion & 0x80):
                return ("none", "D")

            trophy_byte = struct.unpack("B", dme.read_bytes(addr + 0x4F, 1))[0]
            trophy = {0: "gold", 1: "silver", 2: "bronze", 3: "none"}.get(
                (trophy_byte >> 6) & 0x03, "none"
            )

            rank_byte = struct.unpack("B", dme.read_bytes(addr + 0x51, 1))[0]
            rank = {
                0: "3_star", 1: "2_star", 2: "1_star",
                3: "A", 4: "B", 5: "C", 6: "D", 7: "E", 8: "F",
            }.get(rank_byte & 0x0F, "D")

            return (trophy, rank)
        except Exception as e:
            self.logger.error(f"Error reading GP result for cup {cup_id} {cc}: {e}")
            _report_handler(f"ERROR: Error reading GP result for cup {cup_id} {cc}: {e}", self.mgr)
            return ("none", "D")

    # RaceConfig cup reading/writing (for base cup locking)

    def _read_rc_base(self) -> int:
        """Read the RaceConfig base pointer. Returns 0 on failure."""
        try:
            return struct.unpack(">I", dme.read_bytes(RACE_CONFIG_PTR, 4))[0]
        except Exception:
            return 0

    def read_selected_cup(self) -> int:
        """Read the currently selected cup ID from RaceConfig. Returns -1 on failure."""
        try:
            base = self._read_rc_base()
            if base == 0:
                return -1
            return struct.unpack(">B", dme.read_bytes(base + RACECONFIG_CUP_OFFSET, 1))[0]
        except Exception:
            return -1

    def read_selected_cc(self) -> Optional[str]:
        """Read the current CC from RaceConfig."""
        try:
            base = self._read_rc_base()
            if base == 0:
                return None
            mirror = struct.unpack(">B", dme.read_bytes(base + RACECONFIG_MIRROR_OFFSET, 1))[0]
            if mirror == 1:
                return "Mirror"
            cc_byte = struct.unpack(">B", dme.read_bytes(base + RACECONFIG_CC_OFFSET, 1))[0]
            return {0: "50cc", 1: "100cc", 2: "150cc"}.get(cc_byte)
        except Exception:
            return None

    def redirect_cup(self, target_cup_id: int) -> bool:
        """Overwrite the selected cup and course in RaceConfig to redirect
        the player to a different cup. Used to block locked base cups.

        Returns True if the write succeeded.
        """
        try:
            base = self._read_rc_base()
            if base == 0:
                return False
            target_track = CUP_FIRST_TRACK.get(target_cup_id)
            if target_track is None:
                return False
            dme.write_bytes(base + RACECONFIG_CUP_OFFSET, struct.pack(">B", target_cup_id))
            dme.write_bytes(base + RACECONFIG_COURSE_OFFSET, struct.pack(">B", target_track))
            return True
        except Exception:
            return False

    # Race-level detection and lap freeze (fallback for cup locking)

    _RACE_MGR_PTR_ADDR   = 0x809BD730
    _PLAYER_ARRAY_OFFSET = 0xAC
    _TRACK_ID_ADDR       = 0x809C26B3
    _LAP_OFFSET          = 0x25

    def is_in_race(self) -> Tuple[bool, int]:
        """Check if we're currently in a race.
        Returns (in_race, race_mgr_ptr).
        """
        try:
            race_mgr = struct.unpack(">I", dme.read_bytes(self._RACE_MGR_PTR_ADDR, 4))[0]
            if 0x80000000 <= race_mgr <= 0x817FFFFF:
                return True, race_mgr
            return False, 0
        except Exception:
            return False, 0

    def read_race_track_id(self) -> int:
        """Read the current track ID during a race. Returns -1 on failure."""
        try:
            return struct.unpack(">B", dme.read_bytes(self._TRACK_ID_ADDR, 1))[0]
        except Exception:
            return -1

    def freeze_p1_lap(self, race_mgr: int) -> bool:
        """Zero P1's lap counter to prevent race completion.
        Returns True if the write succeeded.
        """
        try:
            player_array = race_mgr + self._PLAYER_ARRAY_OFFSET
            player_ptr = struct.unpack(">I", dme.read_bytes(player_array, 4))[0]
            if 0x80000000 <= player_ptr <= 0x817FFFFF:
                dme.write_bytes(player_ptr + self._LAP_OFFSET, struct.pack(">B", 0))
                return True
            return False
        except Exception:
            return False

    # Vanilla unlock block patch

    # Primary:   write li r3, -1 + blr (0x3860FFFF 4E800020) to 0x80854FA4
    # Fallback:  write li r3, -1       (0x3860FFFF)           to 0x805EB920
    _PATCH_PRIMARY_ADDR   = 0x80854FA4
    _PATCH_PRIMARY_BYTES  = bytes.fromhex("3860FFFF4E800020")
    _PATCH_FALLBACK_ADDR  = 0x805EB920
    _PATCH_FALLBACK_BYTES = bytes.fromhex("3860FFFF")

    async def async_patch_vanilla_unlock_block(self):
        """Write the unlock-prevention patch directly into emulated RAM.

        Tries the 8-byte primary patch first (0x80854FA4), then the 4-byte
        fallback (0x805EB920).  Returns True if at least one patch was applied
        successfully, False if both writes fail.
        """
        if not self._hooked:
            self.logger.warning("patch_vanilla_unlock_block: not hooked, skipping")
            _report_handler("WARNING: patch_vanilla_unlock_block: not hooked, skipping", self.mgr)
            return

        # Primary patch
        try:
            dme.write_bytes(self._PATCH_PRIMARY_ADDR, self._PATCH_PRIMARY_BYTES)
            if(not self.unlockblock_patch_applied_once):
                self.logger.info(
                    f"Unlock-block patch applied at 0x{self._PATCH_PRIMARY_ADDR:08X} "
                    f"({self._PATCH_PRIMARY_BYTES.hex().upper()})"
                )
                _report_handler(
                    f"INFO: Unlock-block patch applied at 0x{self._PATCH_PRIMARY_ADDR:08X} "
                    f"({self._PATCH_PRIMARY_BYTES.hex().upper()})", self.mgr
                )
                self.unlockblock_patch_applied_once = True
            return
        except Exception as e:
            self.logger.warning(
                f"Primary patch failed at 0x{self._PATCH_PRIMARY_ADDR:08X}: {e} "
                f", trying fallback..."
            )
            _report_handler(
                f"WARNING: Primary patch failed at 0x{self._PATCH_PRIMARY_ADDR:08X}: {e} "
                f", trying fallback...", self.mgr
            )

        # Fallback patch
        try:
            dme.write_bytes(self._PATCH_FALLBACK_ADDR, self._PATCH_FALLBACK_BYTES)
            if(not self.unlockblock_patch_applied_once):
                self.logger.info(
                    f"Unlock-block fallback patch applied at 0x{self._PATCH_FALLBACK_ADDR:08X} "
                    f"({self._PATCH_FALLBACK_BYTES.hex().upper()})"
                )
                _report_handler(
                    f"INFO:Unlock-block fallback patch applied at 0x{self._PATCH_FALLBACK_ADDR:08X} "
                    f"({self._PATCH_FALLBACK_BYTES.hex().upper()})", self.mgr
                )
                self.unlockblock_patch_applied_once = True
            return
        except Exception as e:
            self.logger.error(
                f"Fallback patch also failed at 0x{self._PATCH_FALLBACK_ADDR:08X}: {e}"
            )
            _report_handler(
                f"ERROR: Fallback patch also failed at 0x{self._PATCH_FALLBACK_ADDR:08X}: {e}", self.mgr
            )
            return

    # Helpers

    def _warn_once(self, key: str, msg: str) -> None:
        if not self._suppress_warnings.get(key):
            self.logger.warning(msg)
            self._suppress_warnings[key] = True