"""
Menu lock visuals for the Mario Kart Wii AP client.

Default characters, cups and vehicles have no unlock flag in the save, so the
client cannot lock them there. mkwii_client.py enforces the lock in gameplay
(combo fixes, cup redirects, lap freeze). This module only changes what the
menus show: a locked default item is drawn with the game's own "?" so the
player can see it is not unlocked yet. DME reads and writes only, no patching.

Vehicles (layout pane flags):
    Every vehicle button has six panes. Showing the hatena pane and hiding the
    other five gives a clean "?". The flag is the byte right before each pane
    name string in MEM2. The panes are found by scanning for the names.
    The scan finds two layouts at once: a small one for the kart only or bike
    only page (N sets) and a large one for the karts and bikes page (2N sets).
    N follows from how many vehicles the save has unlocked, so N = sets / 3.

Characters and cups (texture swap):
    The icon texture is found in MEM2 by its exact bytes and overwritten with
    the "?" texture. Cup icons are written back when the item unlocks. Character
    icons are not, the game reloads them whenever the selection opens, so they
    are checked often and get the "?" again after every reload.
    The original and "?" bytes are local files in bins/ that are captured from
    the player's own game, nothing of them ships with the client (see
    icon_assets.py).

All of it is research tested with PAL (RMCP01), see the vehicle lock notes.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from dme_helpers import MEM2, constant, read_bytes, read_region, read_u8, write_bytes, write_u8
from dolphin_memory import character_weight_class
from icon_assets import (
    CHARACTER_ICON_SIZE,
    CUP_ICON_SIZE,
    MANIFEST_FILE,
    QMARK_64_FILE,
    QMARK_128_FILE,
    Icon,
    IconCapture,
    default_icon_names,
    ensure_qmark128,
    load_icons,
    load_manifest,
)
from reporting import ReportHandler
from worlds.mkwii.mkwii_info_lib import VEHICLE_ID_TO_NAME

if TYPE_CHECKING:
    from dolphin_memory import DolphinMemoryManager

MEM2_BASE = MEM2[0]
MEM2_SIZE = MEM2[1] - MEM2[0] + 1

# Icons are checked often because the game rewrites a character icon every time its page opens, and the "?" has to go back on before the page is drawn. Vehicles are checked less often. Memory is only rescanned every RESCAN_SECS.
ICON_CYCLE_SECS = 0.05
VEHICLE_CYCLE_SECS = 0.25
SCAN_POLL_SECS = 0.1
RESCAN_SECS = 2.0

# Copies of one icon that are tracked at most, and how many checks in a row a copy may match nothing before it counts as reused memory
MAX_COPIES = 8
MISS_LIMIT = int(2.0 / ICON_CYCLE_SECS)

# Vehicle panes
# Order matters: the tuples below line up with this order.
PANE_NAMES = ("hatena", "chara", "chara_shadow", "chara_c_down", "chara_light_01", "chara_light_02")
PANE_SHOWN = (0, 1, 1, 1, 1, 1)
PANE_LOCKED = (1, 0, 0, 0, 0, 0)

# Largest distance between two neighbouring sets inside one layout cluster.
PANE_SET_GAP = 0x10000

# Vehicle ids: position i (0 to 2) of weight class w is 3 * i + w for karts, and BIKE_ID_BASE + 3 * i + w for bikes (see VEHICLE_ID_TO_NAME).
BIKE_ID_BASE = 0x12
WEIGHT_INDEX = {"Small": 0, "Medium": 1, "Large": 2}

@dataclass
class UnlockedItems:
    """What the AP client considers unlocked. The sets are shared with the
    client context, so changes show up on the next cycle without any copy."""
    characters: Set[str]
    karts: Set[str]
    bikes: Set[str]
    cups: Set[str]  # "{Cup Name} {cc}", e.g. "Mushroom Cup 50cc"


# Vehicle panes

@dataclass
class PaneSet:
    """The six panes of one vehicle button, as the address of each name string."""
    addrs: Dict[str, int]

    @property
    def key(self) -> int:
        return self.addrs["hatena"]

    def intact(self) -> bool:
        # Both copies of every name must still be there, otherwise the memory was freed or reused and must not be written to.
        twin = constant("PANE_TWIN_STRIDE")
        try:
            for name, addr in self.addrs.items():
                expected = name.encode() + b"\x00"
                if read_bytes(addr, len(expected)) != expected:
                    return False
                if read_bytes(addr + twin, len(expected)) != expected:
                    return False
        except RuntimeError:
            return False
        return True

    def read_state(self) -> Tuple[int, ...]:
        return tuple(read_u8(self.addrs[name] - 1) for name in PANE_NAMES)

    def write_state(self, state: Tuple[int, ...]) -> None:
        for name, flag in zip(PANE_NAMES, state):
            write_u8(self.addrs[name] - 1, flag)


def _cluster(addrs: List[int], gap: int) -> List[List[int]]:
    clusters: List[List[int]] = []
    current: List[int] = []
    for addr in addrs:
        if current and addr - current[-1] > gap:
            clusters.append(current)
            current = []
        current.append(addr)
    if current:
        clusters.append(current)
    return clusters


def find_pane_sets(snapshot: bytes) -> List[Optional[PaneSet]]:
    """Find the vehicle pane sets in a MEM2 snapshot, ordered by address.

    An entry is None when a set is incomplete, so set numbers never shift.
    """
    twin = constant("PANE_TWIN_STRIDE")

    # First copy of every name: flag byte is 0 or 1 and the twin copy follows.
    firsts: Dict[str, List[int]] = {}
    for name in PANE_NAMES:
        needle = name.encode() + b"\x00"
        found: Set[int] = set()
        i = snapshot.find(needle, 1)
        while i != -1:
            found.add(i)
            i = snapshot.find(needle, i + 1)
        firsts[name] = sorted(i for i in found if snapshot[i - 1] in (0, 1) and i + twin in found)

    # The biggest hatena cluster is the vehicle page layouts.
    clusters = _cluster(firsts["hatena"], PANE_SET_GAP)
    hatena = max(clusters, key=len, default=None)
    if not hatena:
        return []

    # Give every other pane to the nearest hatena of the cluster.
    others = PANE_NAMES[1:]
    found_for: List[Dict[str, List[int]]] = [{name: [] for name in others} for _ in hatena]
    for name in others:
        for addr in firsts[name]:
            if hatena[0] - PANE_SET_GAP <= addr <= hatena[-1] + PANE_SET_GAP:
                nearest = min(range(len(hatena)), key=lambda k: abs(hatena[k] - addr))
                found_for[nearest][name].append(addr)

    sets: List[Optional[PaneSet]] = []
    for h, found in zip(hatena, found_for):
        if all(len(addrs) == 1 for addrs in found.values()):
            addrs = {"hatena": MEM2_BASE + h}
            addrs.update({name: MEM2_BASE + found[name][0] for name in others})
            sets.append(PaneSet(addrs))
        else:
            sets.append(None)
    return sets


def wanted_pane_locks(
    small_size: int,
    cc: Optional[str],
    weight: int,
    is_locked: Callable[[int], bool],
) -> Dict[int, bool]:
    """Map pane set number (1 based) to "should show the ?" for the default
    vehicles of one weight class.

    Large layout (karts and bikes page): sets small_size + 1 onwards, in the
    order kart, bike, kart, bike, kart, bike. Always applied.
    Small layout (single type page): sets 1 to 3. 50cc only holds karts and
    100cc only holds bikes, so the cc decides which vehicle each set is. At
    150cc and Mirror the small layout is not used.
    """
    wanted: Dict[int, bool] = {}
    for i in range(3):
        kart_id = 3 * i + weight
        bike_id = BIKE_ID_BASE + 3 * i + weight
        wanted[small_size + 1 + 2 * i] = is_locked(kart_id)
        wanted[small_size + 2 + 2 * i] = is_locked(bike_id)
        if cc == "50cc":
            wanted[1 + i] = is_locked(kart_id)
        elif cc == "100cc":
            wanted[1 + i] = is_locked(bike_id)
    return wanted


class VehiclePaneLock:
    def __init__(self, reporter: ReportHandler) -> None:
        self._reporter = reporter
        # Sets this client locked, so a set the game shows as "?" on its own (a vehicle the save has locked) is never touched.
        self._written: Set[int] = set()

    def apply(self, sets: List[Optional[PaneSet]], wanted: Dict[int, bool]) -> bool:
        """Write the wanted state. Returns False when a cached set no longer
        matches memory, so the caller rescans."""
        for number, lock in wanted.items():
            pane_set = sets[number - 1] if number <= len(sets) else None
            if pane_set is None:
                continue
            if not pane_set.intact():
                return False

            state = pane_set.read_state()
            # Only a set in the plain shown state is locked. The layout that is not on screen sits in the "?" state already, so it is skipped.
            if lock and state == PANE_SHOWN:
                pane_set.write_state(PANE_LOCKED)
                self._written.add(pane_set.key)
                self._reporter.report(type="DEBUG", msg=f"[MenuLock] Vehicle set {number} locked")
            elif not lock and state == PANE_LOCKED and pane_set.key in self._written:
                pane_set.write_state(PANE_SHOWN)
                self._written.discard(pane_set.key)
                self._reporter.report(type="DEBUG", msg=f"[MenuLock] Vehicle set {number} restored")
        return True


# Character and cup icon textures

class IconTextures:
    """Swaps icon textures to the "?" and back, one write per change.

    The game keeps several copies of an icon in memory and only one of them is
    on screen, which one changes between menu loads. So every copy that newly
    appeared since the previous scan is tracked and all of them get the same
    treatment, the one on screen is always among them.

    Freed copies of a texture keep their bytes, so writing to any exact match
    could hit freed memory (that gave unknown pointer crashes in the research).
    To avoid it only copies that newly appeared since the previous scan are
    tracked, and a write only ever happens on an exact match of the original or
    the "?". The first scan after the client starts only records what is
    there, so the menu has to be entered (or re-entered) after that.

    The game can rewrite an icon in place when its page opens (characters do).
    The copy stays tracked through that and is written again as soon as its
    bytes match the original, which is why apply() is called very often.
    """

    def __init__(self, icons: Dict[str, Icon], reporter: ReportHandler, miss_limit: int = MISS_LIMIT) -> None:
        self._icons = icons
        self._reporter = reporter
        self._miss_limit = miss_limit
        self._prev_hits: Dict[str, Set[int]] = {}
        self._have_baseline = False
        # Tracked copies of each icon, oldest first
        self._live: Dict[str, List[int]] = {}
        # Checks in a row where a tracked copy matched neither the original nor the "?"
        self._misses: Dict[Tuple[str, int], int] = {}

    def find_hits(self, snapshot: bytes) -> Dict[str, Set[int]]:
        """Addresses of every exact copy of every original icon. Runs in the
        scan thread and only reads the snapshot."""
        hits: Dict[str, Set[int]] = {}
        for name, icon in self._icons.items():
            size = len(icon.original)
            found: Set[int] = set()
            i = snapshot.find(icon.probe)
            while i != -1:
                start = i - icon.probe_offset
                if start >= 0 and snapshot[start:start + size] == icon.original:
                    found.add(MEM2_BASE + start)
                i = snapshot.find(icon.probe, i + 1)
            hits[name] = found
        return hits

    def observe(self, hits: Dict[str, Set[int]]) -> None:
        """Start tracking the copies that appeared since the previous scan."""
        if self._have_baseline:
            for name, addrs in hits.items():
                copies = self._live.setdefault(name, [])
                for addr in sorted(addrs - self._prev_hits.get(name, set())):
                    if addr not in copies:
                        copies.append(addr)
                        self._reporter.report(type="DEBUG", msg=f"[MenuLock] Icon {name} live at 0x{addr:08X}")
                # Keep the newest copies if there are too many
                del copies[:-MAX_COPIES]
        self._prev_hits = hits
        self._have_baseline = True

    def add_icons(self, icons: Dict[str, Icon]) -> None:
        """Add icons that were captured after startup. Called from the event
        loop only, never while a scan reads the icons."""
        for name, icon in icons.items():
            if name not in self._icons:
                self._icons[name] = icon
                self._reporter.report(type="DEBUG", msg=f"[MenuLock] Icon {name} added")

    def reset(self) -> None:
        # Menu memory is gone, forget the tracked copies and previous scan
        self._live.clear()
        self._misses.clear()
        self._prev_hits = {}

    def apply(self, wanted: Dict[str, bool]) -> None:
        """Write the original or the "?" over each tracked copy.

        wanted maps icon name to "should show the ?". Names missing from it
        are left as they are. Memory that matches neither the original nor the
        "?" (not loaded yet, half rewritten, or reused) is never written, and
        a copy that stays that way for a while is dropped.
        """
        for name, copies in self._live.items():
            icon = self._icons[name]
            lock = wanted.get(name)
            for addr in list(copies):
                try:
                    current = read_bytes(addr, len(icon.original))
                except RuntimeError:
                    continue

                key = (name, addr)
                if current != icon.original and current != icon.qmark:
                    misses = self._misses.get(key, 0) + 1
                    if misses >= self._miss_limit:
                        copies.remove(addr)
                        self._misses.pop(key, None)
                        self._reporter.report(type="DEBUG", msg=f"[MenuLock] Icon {name} lost 0x{addr:08X}")
                    else:
                        self._misses[key] = misses
                    continue

                self._misses.pop(key, None)
                if current == icon.original and lock is True:
                    write_bytes(addr, icon.qmark)
                    self._reporter.report(type="DEBUG", msg=f"[MenuLock] Icon {name} locked at 0x{addr:08X}")
                elif current == icon.qmark and lock is False and icon.restore:
                    write_bytes(addr, icon.original)
                    self._reporter.report(type="DEBUG", msg=f"[MenuLock] Icon {name} restored at 0x{addr:08X}")


# Coordinator

def _default_manifest_path() -> Path:
    # A manifest next to the exe wins, so it can be replaced without a rebuild. Otherwise the one bundled with the code is used (--add-data).
    if getattr(sys, "frozen", False):
        beside_exe = Path(sys.executable).parent / MANIFEST_FILE
        if beside_exe.exists():
            return beside_exe
    return Path(__file__).with_name(MANIFEST_FILE)


class MenuLock:
    """Keeps the menus in line with what the AP client has unlocked."""

    def __init__(
        self,
        get_dolphin: Callable[[], Optional["DolphinMemoryManager"]],
        get_items: Callable[[], UnlockedItems],
        asset_dir: Path,
        reporter: ReportHandler,
        manifest_path: Optional[Path] = None,
    ) -> None:
        """get_dolphin returns the memory manager only while it is hooked and
        not in the middle of a savestate load, otherwise None. Icon files that
        are missing in asset_dir are captured from the game, see icon_assets."""
        self._get_dolphin = get_dolphin
        self._get_items = get_items
        self._asset_dir = asset_dir
        self._reporter = reporter

        self._default_characters, self._default_cups = default_icon_names()

        manifest = load_manifest(manifest_path or _default_manifest_path(), reporter)
        self._capture = IconCapture(asset_dir, manifest, MEM2_BASE, reporter)

        icons = self._load_icons(quiet_missing=self._capture.pending())
        self._textures = IconTextures(icons, reporter)
        self._vehicles = VehiclePaneLock(reporter)

        # State shared by the scan loop and the apply loop
        self._sets: List[Optional[PaneSet]] = []
        self._last_scan = 0.0
        self._rescan_requested = False
        self._in_race = False

        reporter.report(type="INFO", msg=f"[MenuLock] Ready, {len(icons)} icon textures available")
        if self._capture.pending():
            reporter.report(
                type="INFO",
                msg=f"[MenuLock] {len(self._capture.pending_names())} icon files are not in {asset_dir} yet. "
                "Open the character select and the cup select once, they are captured from the game.",
            )

    def _load_icons(self, quiet_missing: bool = True) -> Dict[str, Icon]:
        # The cup "?" is made from the character "?" once that has been captured.
        ensure_qmark128(self._asset_dir, self._reporter)
        # Characters are not restored when they unlock, the game reloads them when the selection opens.
        icons = load_icons(
            self._asset_dir, self._default_characters, CHARACTER_ICON_SIZE, QMARK_64_FILE, False, self._reporter,
            quiet_missing,
        )
        icons.update(load_icons(
            self._asset_dir, self._default_cups, CUP_ICON_SIZE, QMARK_128_FILE, True, self._reporter, quiet_missing,
        ))
        return icons

    def _scan(self) -> Tuple[List[Optional[PaneSet]], Dict[str, Set[int]], List[str]]:
        # One MEM2 snapshot serves all scans. Runs in a worker thread.
        snapshot = read_region(MEM2_BASE, MEM2_SIZE)
        captured = self._capture.run(snapshot) if self._capture.due() else []
        return find_pane_sets(snapshot), self._textures.find_hits(snapshot), captured

    def _apply_vehicle_locks(
        self, dolphin: "DolphinMemoryManager", sets: List[Optional[PaneSet]], cc: Optional[str]
    ) -> bool:
        # Nothing to do until a character is picked (the class picks the vehicles).
        character = dolphin.read_menu_character()
        if character is None or not sets or len(sets) % 3:
            return True
        weight = WEIGHT_INDEX.get(character_weight_class(character))
        if weight is None:
            return True

        items = self._get_items()

        def is_locked(vehicle_id: int) -> bool:
            name = VEHICLE_ID_TO_NAME[vehicle_id]
            return name not in items.karts and name not in items.bikes

        wanted = wanted_pane_locks(len(sets) // 3, cc, weight, is_locked)
        return self._vehicles.apply(sets, wanted)

    def _wanted_icons(self, cc: Optional[str]) -> Dict[str, bool]:
        items = self._get_items()
        wanted = {name: name not in items.characters for name in self._default_characters}
        # Cups are locked per cc, so they are undecided until a cc is known.
        if cc:
            for cup in self._default_cups:
                wanted[cup] = f"{cup} {cc}" not in items.cups
        return wanted

    async def run(self) -> None:
        # The scan takes a while, so it runs on its own and never holds up the apply loop.
        await asyncio.gather(self._scan_loop(), self._apply_loop())

    async def _scan_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(SCAN_POLL_SECS)
            if self._get_dolphin() is None or self._in_race:
                continue
            if not self._rescan_requested and loop.time() - self._last_scan < RESCAN_SECS:
                continue

            try:
                self._rescan_requested = False
                self._sets, hits, captured = await asyncio.to_thread(self._scan)
                self._textures.observe(hits)
                self._last_scan = loop.time()
                if captured:
                    # Newly saved icons are tracked from the next scan on, the copies in memory count as new then
                    self._textures.add_icons(self._load_icons())
                    self._rescan_requested = True
            except Exception as e:
                self._reporter.report(type="ERROR", msg=f"[MenuLock] Scan error: {e}")
                await asyncio.sleep(2)

    async def _apply_loop(self) -> None:
        loop = asyncio.get_running_loop()
        last_vehicle_apply = 0.0
        while True:
            await asyncio.sleep(ICON_CYCLE_SECS)
            dolphin = self._get_dolphin()
            if dolphin is None:
                continue

            try:
                self._in_race, _ = dolphin.is_in_race()
                if self._in_race:
                    # The menus are gone during a race, drop everything cached
                    self._sets = []
                    self._textures.reset()
                    self._last_scan = 0.0
                    continue

                cc = dolphin.read_selected_cc()
                if loop.time() - last_vehicle_apply >= VEHICLE_CYCLE_SECS:
                    last_vehicle_apply = loop.time()
                    if not self._apply_vehicle_locks(dolphin, self._sets, cc):
                        # A cached set moved, rescan as soon as possible
                        self._rescan_requested = True
                self._textures.apply(self._wanted_icons(cc))

            except Exception as e:
                self._reporter.report(type="ERROR", msg=f"[MenuLock] Error: {e}")
                await asyncio.sleep(2)