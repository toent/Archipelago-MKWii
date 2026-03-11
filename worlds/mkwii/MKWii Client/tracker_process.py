"""
tracker_process.py — standalone tracker subprocess.

Usage:
    python tracker_process.py <server_address> <slot_name> [password]

Connects directly to the Archipelago server using websockets, polls for
checked locations and received items, and displays them in a Kivy window.
"""
from __future__ import annotations

import json
import os
import sys
import asyncio
import threading
from pathlib import Path

AP_SERVER  = sys.argv[1] if len(sys.argv) > 1 else ""
AP_SLOT    = sys.argv[2] if len(sys.argv) > 2 else ""
AP_PASS    = sys.argv[3] if len(sys.argv) > 3 else ""

# If credentials were not supplied via args, the Kivy UI will show a login
# screen and populate these globals before starting the AP thread.
_STANDALONE_MODE = AP_SERVER == "" or AP_SLOT == ""

if getattr(sys, "frozen", False):
    _HERE = Path(sys.executable).parent
else:
    _HERE = Path(__file__).parent

# Write all uncaught exceptions to a log file beside this script,
# because subprocess stdout/stderr may not be visible to the user.
_LOG = _HERE / "tracker_crash.log"

def _excepthook(exc_type, exc_value, exc_tb):
    import traceback
    with open(_LOG, "w", encoding="utf-8") as _f:
        traceback.print_exception(exc_type, exc_value, exc_tb, file=_f)
    # Also try original stderr in case a console is attached
    traceback.print_exception(exc_type, exc_value, exc_tb)

sys.excepthook = _excepthook

# Make the parent Archipelago dir importable (for worlds.mkwii.*)
sys.path.insert(0, str(_HERE.parent))


def _ap_version() -> dict:
    """Return the Archipelago version dict, falling back to the client's own version."""
    try:
        from Utils import version_tuple  # Archipelago Utils
        major, minor, build = version_tuple
        return {"major": major, "minor": minor, "build": build, "class": "Version"}
    except Exception:
        pass
    # Fallback: parse from CommonClient if available
    try:
        import CommonClient
        v = CommonClient.ClientStatus  # noqa — just testing import
        from Utils import __version__
        parts = [int(x) for x in __version__.split(".")[:3]]
        return {"major": parts[0], "minor": parts[1], "build": parts[2], "class": "Version"}
    except Exception:
        return {"major": 0, "minor": 6, "build": 7, "class": "Version"}

IMG_DIR   = _HERE / "img"
IMG_MKWII = IMG_DIR / "mkwiiLicenseImage.png"
IMG_AP    = IMG_DIR / "AP_Asset_Pack" / "color-icon.png"

BG_OUTER      = (0.039, 0.059, 0.180, 1)
BG_CARD       = (0.067, 0.102, 0.290, 1)
BG_HEADER_ROW = (0.051, 0.082, 0.251, 1)
BG_ROW_ODD    = (0.075, 0.118, 0.329, 1)
BG_ROW_EVEN   = (0.059, 0.094, 0.282, 1)
BG_CELL_EMPTY = (0.035, 0.051, 0.165, 1)
BORDER_LIGHT  = (0.227, 0.310, 0.627, 1)
BORDER_GLOW   = (0.353, 0.498, 0.831, 1)
TEXT_WHITE    = (1, 1, 1, 1)
TEXT_YELLOW   = (1, 0.878, 0.251, 1)
TEXT_DIM      = (0.416, 0.498, 0.753, 1)
TEXT_ORANGE   = (1, 0.549, 0, 1)


def _hex4(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, 1)


TIER_BG = {
    "none":      BG_CELL_EMPTY,
    "3rd_place": _hex4("#cd7f32"),
    "2nd_place": _hex4("#c0c0c0"),
    "1st_place": _hex4("#deb900"),
    "1_star":    _hex4("#deb900"),
    "2_star":    _hex4("#deb900"),
    "3_star":    _hex4("#deb900"),
}
TIER_FG = {
    "none":      TEXT_DIM,
    "3rd_place": _hex4("#221100"),
    "2nd_place": _hex4("#4B4B4B"),
    "1st_place": _hex4("#645000"),
    "1_star":    _hex4("#645000"),
    "2_star":    _hex4("#645000"),
    "3_star":    _hex4("#645000"),
}
TIER_SYMBOLS = {
    "none":      "",
    "3rd_place": "🏆",
    "2nd_place": "🏆",
    "1st_place": "🏆",
    "1_star":    "⭐",
    "2_star":    "⭐⭐",
    "3_star":    "⭐⭐⭐",
}

# Cup icon spritesheet — sliced with Pillow at startup into temp PNG files,
# then loaded as normal KvImage source paths.
_CUP_SPRITESHEET = _HERE / "img" / "cup_icons.png"
_CUP_GRID_POS = {
    "Mushroom Cup":  (0, 0),
    "Flower Cup":    (1, 0),
    "Star Cup":      (2, 0),
    "Special Cup":   (3, 0),
    "Banana Cup":    (0, 1),
    "Shell Cup":     (1, 1),
    "Leaf Cup":      (2, 1),
    "Lightning Cup": (3, 1),
}
CUPS = list(_CUP_GRID_POS.keys())
# Maps cup name -> temp file path string; populated by _slice_cup_icons()
CUP_ICON_PATHS: dict[str, str] = {}


def _remove_bg_floodfill(cell_arr, threshold: int = 15):
    """Remove background by flood-filling connected near-black regions from all edges.
    Preserves dark pixels that are interior to the icon (outlines, shadows)."""
    from scipy.ndimage import label as _label
    import numpy as _np
    brightness = cell_arr[:, :, :3].astype(int).sum(axis=2)
    bg_candidate = brightness < threshold
    labeled, _ = _label(bg_candidate)
    border_labels: set = set()
    for edge in (labeled[0, :], labeled[-1, :], labeled[:, 0], labeled[:, -1]):
        border_labels.update(edge.flat)
    border_labels.discard(0)
    result = cell_arr.copy()
    result[_np.isin(labeled, list(border_labels)), 3] = 0
    return result


def _slice_cup_icons() -> None:
    """Slice cup_icons.png into per-cup temp PNGs, tight-cropped and centred."""
    if not _CUP_SPRITESHEET.exists():
        return
    try:
        from PIL import Image as PilImage
        import tempfile, numpy as np
        sheet   = PilImage.open(str(_CUP_SPRITESHEET)).convert("RGBA")
        W, H    = sheet.size
        cw, ch  = W / 4, H / 2
        arr     = np.array(sheet)
        tmp_dir = Path(tempfile.mkdtemp(prefix="mkwii_cups_"))

        crops = {}
        for cup, (col, row) in _CUP_GRID_POS.items():
            l = int(col * cw);       u = int(row * ch)
            r = int((col + 1) * cw); d = int((row + 1) * ch)
            cell = _remove_bg_floodfill(arr[u:d, l:r].copy())
            mask = cell[:, :, 3] > 0
            if not mask.any():
                crops[cup] = cell
                continue
            rmin, rmax = np.where(np.any(mask, axis=1))[0][[0, -1]]
            cmin, cmax = np.where(np.any(mask, axis=0))[0][[0, -1]]
            crops[cup] = cell[rmin:rmax+1, cmin:cmax+1]

        canvas_w = max(c.shape[1] for c in crops.values())
        canvas_h = max(c.shape[0] for c in crops.values())

        for cup, crop in crops.items():
            canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
            ch_off = (canvas_h - crop.shape[0]) // 2
            cw_off = (canvas_w - crop.shape[1]) // 2
            canvas[ch_off:ch_off+crop.shape[0], cw_off:cw_off+crop.shape[1]] = crop
            fname = cup.lower().replace(" ", "_") + ".png"
            out   = tmp_dir / fname
            PilImage.fromarray(canvas, "RGBA").save(str(out))
            CUP_ICON_PATHS[cup] = str(out)
    except Exception as e:
        print(f"[Tracker] Cup icon slice failed: {e}")


_slice_cup_icons()

CCS  = ["50cc", "100cc", "150cc", "Mirror"]
CELL_SIZE = 68

TRACKS = {
    "Mushroom Cup":  ["Luigi Circuit", "Moo Moo Meadows", "Mushroom Gorge", "Toad's Factory"],
    "Flower Cup":    ["Mario Circuit", "Coconut Mall", "DK Summit", "Wario's Gold Mine"],
    "Star Cup":      ["Daisy Circuit", "Koopa Cape", "Maple Treeway", "Grumble Volcano"],
    "Special Cup":   ["Dry Dry Ruins", "Moonview Highway", "Bowser's Castle", "Rainbow Road"],
    "Shell Cup":     ["GCN Peach Beach", "DS Yoshi Falls", "SNES Ghost Valley 2", "N64 Mario Raceway"],
    "Banana Cup":    ["N64 Sherbet Land", "GBA Shy Guy Beach", "DS Delfino Square", "GCN Waluigi Stadium"],
    "Leaf Cup":      ["DS Desert Hills", "GBA Bowser's Castle 3", "N64 DK's Jungle Parkway", "GCN Mario Circuit"],
    "Lightning Cup": ["SNES Mario Circuit 3", "DS Peach Gardens", "GCN DK Mountain", "N64 Bowser's Castle"],
}

POWERUP_ITEMS = [
    "Powerup: Red Shell",
    "Powerup: Triple Bananas",
    "Powerup: Triple Green Shells",
    "Powerup: Triple Red Shells",
    "Powerup: Bob-omb",
    "Powerup: Blue Shell",
    "Powerup: Fake Item Box",
    "Powerup: Star",
    "Powerup: Golden Mushroom",
    "Powerup: Mega Mushroom",
    "Powerup: Blooper",
    "Powerup: POW Block",
    "Powerup: Lightning",
    "Powerup: Triple Mushrooms",
    "Powerup: Bullet Bill",
    "Powerup: Mushroom",
    "Powerup: Green Shell",
    "Powerup: Banana",
]

# Item icon spritesheet — 11 cols x 2 rows, black background
_ITEM_SPRITESHEET = _HERE / "img" / "item_icons.png"
_ITEM_GRID_COLS = 9
_ITEM_GRID_POS = {
    "Powerup: Blooper":              (0, 0),
    "Powerup: Mega Mushroom":        (1, 0),
    "Powerup: POW Block":            (2, 0),
    "Powerup: Triple Bananas":       (3, 0),
    "Powerup: Banana":               (4, 0),
    "Powerup: Bob-omb":              (5, 0),
    "Powerup: Fake Item Box":        (6, 0),
    "Powerup: Golden Mushroom":      (7, 0),
    "Powerup: Lightning":            (8, 0),
    "Powerup: Star":                 (0, 1),
    "Powerup: Green Shell":          (1, 1),
    "Powerup: Triple Green Shells":  (2, 1),
    "Powerup: Red Shell":            (3, 1),
    "Powerup: Triple Red Shells":    (4, 1),
    "Powerup: Blue Shell":           (5, 1),
    "Powerup: Bullet Bill":          (6, 1),
    "Powerup: Mushroom":             (7, 1),
    "Powerup: Triple Mushrooms":     (8, 1),
}
# Maps item name -> temp PNG path; populated by _slice_item_icons()
ITEM_ICON_PATHS: dict[str, str] = {}


def _slice_item_icons() -> None:
    """Slice item_icons.png into per-item temp PNGs using Pillow.
    Each icon is cropped tight to its content bbox, then pasted centred onto
    a uniform canvas so all icons appear the same size in the UI.
    """
    if not _ITEM_SPRITESHEET.exists():
        return
    try:
        from PIL import Image as PilImage
        import tempfile, numpy as np
        sheet   = PilImage.open(str(_ITEM_SPRITESHEET)).convert("RGBA")
        W, H    = sheet.size
        cw, ch  = W / _ITEM_GRID_COLS, H / 2
        arr     = np.array(sheet)
        tmp_dir = Path(tempfile.mkdtemp(prefix="mkwii_items_"))

        # First pass: collect all tight-crop sizes to find the common canvas size
        crops = {}
        for item, (col, row) in _ITEM_GRID_POS.items():
            l = int(col * cw);       u = int(row * ch)
            r = int((col + 1) * cw); d = int((row + 1) * ch)
            cell = _remove_bg_floodfill(arr[u:d, l:r].copy())
            mask = cell[:, :, 3] > 0
            if not mask.any():
                crops[item] = cell
                continue
            rmin, rmax = np.where(np.any(mask, axis=1))[0][[0, -1]]
            cmin, cmax = np.where(np.any(mask, axis=0))[0][[0, -1]]
            crops[item] = cell[rmin:rmax+1, cmin:cmax+1]

        # Canvas = largest content dimensions across all icons
        canvas_w = max(c.shape[1] for c in crops.values())
        canvas_h = max(c.shape[0] for c in crops.values())

        # Second pass: paste each tight crop centred on the canvas
        for item, crop in crops.items():
            canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
            ch_off = (canvas_h - crop.shape[0]) // 2
            cw_off = (canvas_w - crop.shape[1]) // 2
            canvas[ch_off:ch_off+crop.shape[0], cw_off:cw_off+crop.shape[1]] = crop
            fname = item.lower().replace("powerup: ", "").replace(" ", "_").replace("-", "") + ".png"
            out = tmp_dir / fname
            PilImage.fromarray(canvas, "RGBA").save(str(out))
            ITEM_ICON_PATHS[item] = str(out)
    except Exception as e:
        print(f"[Tracker] Item icon slice failed: {e}")


_slice_item_icons()

TIER_HIERARCHY = ["3rd_place", "2nd_place", "1st_place", "1_star", "2_star", "3_star"]

TIER_NORMALIZE: dict[str, str] = {}
for _t in TIER_HIERARCHY:
    _readable = _t.replace("_", " ")
    TIER_NORMALIZE[_readable]        = _t
    TIER_NORMALIZE[_readable.title()] = _t
    TIER_NORMALIZE[_readable.lower()] = _t

# ---------------------------------------------------------------------------
# Shared state — written by the asyncio AP thread, read by Kivy tick
# ---------------------------------------------------------------------------

_state_lock = threading.Lock()
_state = {
    "connected":              False,
    "completed_locations":    {},    # "Cup||cc" -> tier str
    "track_locations":        {},    # "Track||cc" -> True/False
    "unlocked_items":         [],    # list of "Powerup: X" strings
    "include_race_checks":    True,  # whether Tracks tab is enabled
    "enable_item_randomization": True,  # whether Items tab is enabled
}


def _update_state(**kwargs) -> None:
    with _state_lock:
        _state.update(kwargs)


def _read_state() -> dict:
    with _state_lock:
        return {
            "connected":               _state["connected"],
            "completed_locations":     dict(_state["completed_locations"]),
            "track_locations":         dict(_state["track_locations"]),
            "unlocked_items":          list(_state["unlocked_items"]),
            "include_race_checks":     _state["include_race_checks"],
            "enable_item_randomization": _state["enable_item_randomization"],
        }


# ---------------------------------------------------------------------------
# AP websocket client (runs in a background thread)
# ---------------------------------------------------------------------------

def _ensure_ws_scheme(addr: str) -> str:
    if addr.startswith("ws://") or addr.startswith("wss://"):
        return addr
    return f"wss://{addr}"


def _update_completion(completed: dict, cup: str, cc: str, tier: str) -> None:
    key = f"{cup}||{cc}"
    current = completed.get(key, "none")
    ci = TIER_HIERARCHY.index(current) if current in TIER_HIERARCHY else -1
    ni = TIER_HIERARCHY.index(tier)    if tier    in TIER_HIERARCHY else -1
    if ni > ci:
        completed[key] = tier


def _parse_cup_location(name: str, completed: dict) -> None:
    """Parse a cup GP location name like 'Mushroom Cup 50cc - 2nd place'."""
    if " - " not in name:
        return
    cup_cc, tier_str = name.rsplit(" - ", 1)
    parts = cup_cc.rsplit(" ", 1)
    if len(parts) != 2:
        return
    cup, cc = parts
    if cup not in CUPS or cc not in CCS:
        return
    tier = TIER_NORMALIZE.get(tier_str)
    if tier:
        _update_completion(completed, cup, cc, tier)


def _parse_track_location(name: str, track_locs: dict) -> None:
    """Parse a track race location like 'Luigi Circuit 100cc - 1st Place'."""
    if " - 1st Place" not in name:
        return
    prefix = name.replace(" - 1st Place", "")
    parts  = prefix.rsplit(" ", 1)
    if len(parts) != 2:
        return
    track, cc = parts
    if cc not in CCS:
        return
    # Verify it's a real track
    for tracks in TRACKS.values():
        if track in tracks:
            track_locs[f"{track}||{cc}"] = True
            return


async def _ap_client_loop() -> None:
    try:
        import websockets
    except ImportError:
        print("[Tracker] websockets library not found — pip install websockets")
        return

    # Try wss:// first (archipelago.gg and most hosted servers require it),
    # fall back to ws:// for local/LAN servers.
    if AP_SERVER.startswith("ws://") or AP_SERVER.startswith("wss://"):
        uri_candidates = [AP_SERVER]
    else:
        uri_candidates = [f"wss://{AP_SERVER}", f"ws://{AP_SERVER}"]

    # Build location lookup from worlds package
    location_name_to_id: dict[str, int] = {}
    id_to_name:          dict[int, str]  = {}
    item_id_to_name:     dict[int, str]  = {}

    try:
        from worlds.mkwii.locations import location_table
        from worlds.mkwii.items     import item_table
        location_name_to_id = {n: d.code for n, d in location_table.items()}
        id_to_name          = {d.code: n for n, d in location_table.items()}
        item_id_to_name     = {d.code: n for n, d in item_table.items()}
    except Exception as e:
        print(f"[Tracker] Could not load worlds tables: {e}")

    while True:
        try:
            uri = None
            for candidate in uri_candidates:
                try:
                    print(f"[Tracker] Trying {candidate} as '{AP_SLOT}'...")
                    async with websockets.connect(candidate, ping_interval=30, open_timeout=8) as _test:
                        pass
                    uri = candidate
                    break
                except Exception as probe_err:
                    print(f"[Tracker] {candidate} failed: {probe_err}")
            if uri is None:
                print("[Tracker] All URI candidates failed, retrying in 5s...")
                await asyncio.sleep(5)
                continue
            # Cache the working scheme so reconnects skip the probe
            uri_candidates = [uri]
            print(f"[Tracker] Connecting to {uri} as '{AP_SLOT}'...")
            async with websockets.connect(uri, ping_interval=30) as ws:

                # ── handshake ──────────────────────────────────────────────

                # 1. Receive RoomInfo
                raw = await ws.recv()
                msgs = json.loads(raw)
                room_info = next((m for m in msgs if m["cmd"] == "RoomInfo"), None)
                if not room_info:
                    print("[Tracker] Did not receive RoomInfo")
                    await asyncio.sleep(5)
                    continue

                # 2. GetDataPackage
                await ws.send(json.dumps([{"cmd": "GetDataPackage", "games": ["Mario Kart Wii"]}]))
                raw = await ws.recv()
                msgs = json.loads(raw)
                dp = next((m for m in msgs if m["cmd"] == "DataPackage"), None)
                if dp:
                    try:
                        game_data = dp["data"]["games"].get("Mario Kart Wii", {})
                        loc_map   = game_data.get("location_name_to_id", {})
                        item_map  = game_data.get("item_name_to_id", {})
                        if loc_map:
                            location_name_to_id = {n: int(i) for n, i in loc_map.items()}
                            id_to_name          = {int(i): n for n, i in loc_map.items()}
                        if item_map:
                            item_id_to_name = {int(i): n for n, i in item_map.items()}
                    except Exception as e:
                        print(f"[Tracker] DataPackage parse error: {e}")

                # 3. Connect
                connect_msg = {
                    "cmd":          "Connect",
                    "game":         "Mario Kart Wii",
                    "name":         AP_SLOT,
                    "password":     AP_PASS,
                    "version":      _ap_version(),
                    "items_handling": 0b111,
                    "tags":         ["Tracker"],
                    "uuid":         "mkwii-tracker",
                    "slot_data":    True,
                }
                await ws.send(json.dumps([connect_msg]))

                raw = await ws.recv()
                msgs = json.loads(raw)

                connected_msg = next((m for m in msgs if m["cmd"] == "Connected"), None)
                if not connected_msg:
                    err = next((m for m in msgs if m["cmd"] == "ConnectionRefused"), None)
                    reason = err.get("errors", ["unknown"]) if err else ["no Connected received"]
                    print(f"[Tracker] Connection refused: {reason}")
                    _update_state(connected=False)
                    await asyncio.sleep(10)
                    continue

                # ── slot_data feature flags ────────────────────────────────
                slot_data          = connected_msg.get("slot_data", {})
                include_race       = bool(slot_data.get("include_race_checks", True))
                enable_items       = bool(slot_data.get("enable_item_randomization", True))
                # starting_items is a list of raw item name strings, e.g. ["Fake Item Box"]
                # Map them to "Powerup: X" form so they show as unlocked from the start.
                _GAME_TO_AP = {v: k for k, v in {
                    "Powerup: Red Shell":           "Red Shell",
                    "Powerup: Triple Bananas":      "Triple Bananas",
                    "Powerup: Triple Green Shells": "Triple Green Shells",
                    "Powerup: Triple Red Shells":   "Triple Red Shells",
                    "Powerup: Bob-omb":             "Bob-omb",
                    "Powerup: Blue Shell":          "Spiny Shell",
                    "Powerup: Fake Item Box":       "Fake Item Box",
                    "Powerup: Star":                "Star",
                    "Powerup: Golden Mushroom":     "Golden Mushroom",
                    "Powerup: Mega Mushroom":       "Mega Mushroom",
                    "Powerup: Blooper":             "Blooper",
                    "Powerup: POW Block":           "POW Block",
                    "Powerup: Lightning":           "Lightning",
                    "Powerup: Triple Mushrooms":    "Triple Mushrooms",
                    "Powerup: Bullet Bill":         "Bullet Bill",
                    "Powerup: Mushroom":            "Mushroom",
                    "Powerup: Green Shell":         "Green Shell",
                    "Powerup: Banana":              "Banana",
                }.items()}
                starting_items_raw = slot_data.get("starting_items") or []
                starting_unlocked: list[str] = []
                for raw_name in starting_items_raw:
                    ap_name = _GAME_TO_AP.get(raw_name)
                    if ap_name and ap_name not in starting_unlocked:
                        starting_unlocked.append(ap_name)

                # ── initial state from checked_locations ───────────────────
                checked_ids: list[int] = connected_msg.get("checked_locations", [])
                completed: dict[str, str] = {}
                track_locs: dict[str, bool] = {}
                # Seed with starting items so they show unlocked immediately
                unlocked_items: list[str] = list(starting_unlocked)

                for loc_id in checked_ids:
                    name = id_to_name.get(loc_id)
                    if not name:
                        continue
                    _parse_cup_location(name, completed)
                    _parse_track_location(name, track_locs)

                # ReceivedItems may follow immediately in the same batch
                for m in msgs:
                    if m["cmd"] == "ReceivedItems":
                        for net_item in m.get("items", []):
                            iname = item_id_to_name.get(net_item.get("item", -1))
                            if iname and iname.startswith("Powerup:") and iname not in unlocked_items:
                                unlocked_items.append(iname)

                _update_state(
                    connected=True,
                    completed_locations=completed,
                    track_locations=track_locs,
                    unlocked_items=unlocked_items,
                    include_race_checks=include_race,
                    enable_item_randomization=enable_items,
                )
                print(f"[Tracker] Connected — {len(checked_ids)} checked locations, "
                      f"race={include_race}, items={enable_items}, "
                      f"starting_unlocked={starting_unlocked}")

                # ── main receive loop ──────────────────────────────────────
                async for raw in ws:
                    msgs = json.loads(raw)
                    changed = False

                    for m in msgs:
                        cmd = m.get("cmd")

                        if cmd == "LocationInfo":
                            pass  # not needed by tracker

                        elif cmd == "ReceivedItems":
                            for net_item in m.get("items", []):
                                iname = item_id_to_name.get(net_item.get("item", -1))
                                if iname and iname.startswith("Powerup:") and iname not in unlocked_items:
                                    unlocked_items.append(iname)
                                    changed = True

                        elif cmd == "RoomUpdate":
                            new_checked = m.get("checked_locations", [])
                            for loc_id in new_checked:
                                name = id_to_name.get(loc_id)
                                if not name:
                                    continue
                                _parse_cup_location(name, completed)
                                _parse_track_location(name, track_locs)
                                changed = True

                        elif cmd == "PrintJSON":
                            pass  # ignore chat/print messages

                    if changed:
                        _update_state(
                            completed_locations=completed,
                            track_locations=track_locs,
                            unlocked_items=unlocked_items,
                        )

        except Exception as e:
            print(f"[Tracker] AP connection error: {e}")
            _update_state(connected=False)
            await asyncio.sleep(5)


async def _ap_thread_main() -> None:
    # In standalone mode, spin until the UI login form populates the globals
    global AP_SERVER, AP_SLOT
    while not AP_SERVER or not AP_SLOT:
        await asyncio.sleep(0.2)
    await _ap_client_loop()


def _run_ap_thread() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_ap_thread_main())


# ---------------------------------------------------------------------------
# Kivy UI  (identical visual structure to the original)
# ---------------------------------------------------------------------------

os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")

from kivy.config import Config

_GRID_W = (len(CUPS) + 1) * CELL_SIZE + len(CUPS) * 2 + 2 * 6
_GRID_H = (len(CCS)  + 1) * CELL_SIZE + len(CCS)  * 2 + 2 * 6
_W = _GRID_W + 2 * 6
_H = _GRID_H + 84 + 6 + 30 + 4 + 2 * 6
Config.set("graphics", "width",      str(_W))
Config.set("graphics", "height",     str(_H))
Config.set("graphics", "resizable",  "0")
Config.set("graphics", "borderless", "0")
Config.set("kivy",     "window_icon", "")

from kivy.app              import App
from kivy.clock            import Clock
from kivy.core.text        import LabelBase
from kivy.graphics         import Color, Rectangle, Line
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout    import BoxLayout
from kivy.uix.floatlayout  import FloatLayout
from kivy.uix.gridlayout   import GridLayout
from kivy.uix.label        import Label
from kivy.uix.image        import Image as KvImage
from kivy.uix.scrollview   import ScrollView
import kivy.resources

_EMOJI_FONT = "Roboto"
_emoji_candidates = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "seguiemj.ttf"),
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
    "/usr/share/fonts/noto/NotoEmoji-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/twemoji/TwitterColorEmoji-SVGinOT.ttf",
    "/usr/share/fonts/truetype/emojione/emojione-android.ttf",
]
for _candidate in _emoji_candidates:
    if os.path.isfile(_candidate):
        try:
            LabelBase.register(name="KivyEmoji", fn_regular=_candidate)
            _EMOJI_FONT = "KivyEmoji"
        except Exception:
            pass
        break

if _EMOJI_FONT == "Roboto":
    for _kc in ("fonts/NotoEmoji-Regular.ttf", "fonts/DroidSansFallback.ttf"):
        _found = kivy.resources.resource_find(_kc)
        if _found:
            try:
                LabelBase.register(name="KivyEmoji", fn_regular=_found)
                _EMOJI_FONT = "KivyEmoji"
            except Exception:
                pass
            break


def _paint_bg(widget, bg, border=None):
    with widget.canvas.before:
        _c = Color(*bg)
        _r = Rectangle(size=widget.size, pos=widget.pos)
        widget.bind(size=lambda i, v: setattr(_r, "size", v),
                    pos =lambda i, v: setattr(_r, "pos",  v))
        if border:
            Color(*border)
            _bl = Line(rectangle=(widget.x, widget.y, widget.width, widget.height), width=1)
            def _upd(inst, _v, l=_bl, w=widget):
                l.rectangle = (w.x, w.y, w.width, w.height)
            widget.bind(size=_upd, pos=_upd)


def _label(text, fg, font_size="10pt", bold=False, emoji=False, **kw):
    kw.setdefault("halign", "center")
    kw.setdefault("valign", "middle")
    if emoji:
        kw["font_name"] = _EMOJI_FONT
    l = Label(text=text, color=list(fg), font_size=font_size, bold=bold, **kw)
    l.bind(size=l.setter("text_size"))
    return l


def _header_cell(text, bg, fg, font_size="10pt", bold=False):
    cell = FloatLayout(size_hint=(None, None), size=(CELL_SIZE, CELL_SIZE))
    _paint_bg(cell, bg, BORDER_LIGHT)
    cell.add_widget(_label(text, fg, font_size=font_size, bold=bold,
                           pos_hint={"center_x": 0.5, "center_y": 0.5},
                           size_hint=(1, 1)))
    return cell


def _centered_image(path, w, h):
    anchor = AnchorLayout(anchor_x="center", anchor_y="center",
                          size_hint=(None, 1), width=w + 4)
    anchor.add_widget(KvImage(source=str(path),
                              size_hint=(None, None), size=(w, h),
                              allow_stretch=True, keep_ratio=True,
                              mipmap=True))
    return anchor


class LicenseCell:
    def __init__(self):
        self.widget = FloatLayout(size_hint=(None, None), size=(CELL_SIZE, CELL_SIZE))
        with self.widget.canvas.before:
            self._bg_c = Color(*BG_CELL_EMPTY)
            self._bg_r = Rectangle(size=(CELL_SIZE, CELL_SIZE))
            self._bd_c = Color(*BORDER_LIGHT)
            self._bd_l = Line(rectangle=(0, 0, CELL_SIZE, CELL_SIZE), width=1)
        self.widget.bind(pos=self._sync, size=self._sync)
        self._lbl = Label(text="", color=list(TEXT_DIM), font_size="11pt",
                          font_name=_EMOJI_FONT,
                          halign="center", valign="middle",
                          pos_hint={"center_x": 0.5, "center_y": 0.5},
                          size_hint=(1, 1))
        self._lbl.bind(size=self._lbl.setter("text_size"))
        self.widget.add_widget(self._lbl)

    def _sync(self, inst, _v):
        x, y = inst.pos
        w, h = inst.size
        self._bg_r.pos  = (x, y)
        self._bg_r.size = (w, h)
        self._bd_l.rectangle = (x, y, w, h)

    def set_tier(self, tier):
        self._bg_c.rgba = list(TIER_BG.get(tier, BG_CELL_EMPTY))
        self._bd_c.rgba = list(BORDER_GLOW if tier != "none" else BORDER_LIGHT)
        self._lbl.text  = TIER_SYMBOLS.get(tier, "")
        self._lbl.color = list(TIER_FG.get(tier, TEXT_DIM))


class TrackCell:
    def __init__(self, cc: str):
        self._cc = cc
        self.widget = FloatLayout(size_hint=(None, None), size=(CELL_SIZE, CELL_SIZE))
        with self.widget.canvas.before:
            self._bg_c = Color(*BG_CELL_EMPTY)
            self._bg_r = Rectangle(size=(CELL_SIZE, CELL_SIZE))
            self._bd_c = Color(*BORDER_LIGHT)
            self._bd_l = Line(rectangle=(0, 0, CELL_SIZE, CELL_SIZE), width=1)
        self.widget.bind(pos=self._sync, size=self._sync)
        self._lbl = Label(text="", color=list(TEXT_DIM), font_size="11pt",
                          bold=True, halign="center", valign="middle",
                          pos_hint={"center_x": 0.5, "center_y": 0.5},
                          size_hint=(1, 1))
        self._lbl.bind(size=self._lbl.setter("text_size"))
        self.widget.add_widget(self._lbl)

    def _sync(self, inst, _v):
        x, y = inst.pos
        w, h = inst.size
        self._bg_r.pos  = (x, y)
        self._bg_r.size = (w, h)
        self._bd_l.rectangle = (x, y, w, h)

    def set_done(self, done: bool):
        if done:
            self._bg_c.rgba = list(_hex4("#deb900"))
            self._bd_c.rgba = list(BORDER_GLOW)
            self._lbl.text  = self._cc
            self._lbl.color = list(_hex4("#645000"))
        else:
            self._bg_c.rgba = list(BG_CELL_EMPTY)
            self._bd_c.rgba = list(BORDER_LIGHT)
            self._lbl.text  = ""
            self._lbl.color = list(TEXT_DIM)


class ItemCell:
    # Dimensions are set dynamically by _build_items_panel; defaults are fallbacks
    _ITEM_W = 103
    _ITEM_H = 80

    def __init__(self, name: str, w: int = 103, h: int = 80):
        self._name  = name
        self._short = name.replace("Powerup: ", "")
        self.widget = FloatLayout(size_hint=(None, None), size=(w, h))
        with self.widget.canvas.before:
            self._bg_c = Color(*BG_CELL_EMPTY)
            self._bg_r = Rectangle(size=(w, h))
            self._bd_c = Color(*BORDER_LIGHT)
            self._bd_l = Line(rectangle=(0, 0, w, h), width=1)
        self.widget.bind(pos=self._sync, size=self._sync)

        icon_size = int(min(w - 8, h - 24) * 0.75)  # 75% of cell, leave room for name
        if name in ITEM_ICON_PATHS:
            self._icon_img = KvImage(
                source=ITEM_ICON_PATHS[name],
                size_hint=(None, None), size=(icon_size, icon_size),
                allow_stretch=True, keep_ratio=True,
                pos_hint={"center_x": 0.5, "center_y": 0.62})
            self.widget.add_widget(self._icon_img)
        else:
            self._icon_img = None

        self._name_lbl = Label(text=self._short, font_size="10pt", bold=True,
                               color=list(TEXT_DIM),
                               halign="center", valign="middle",
                               pos_hint={"center_x": 0.5, "center_y": 0.12},
                               size_hint=(1, None), height=h)
        self._name_lbl.bind(size=self._name_lbl.setter("text_size"))
        self.widget.add_widget(self._name_lbl)

    def _sync(self, inst, _v):
        x, y = inst.pos
        w, h = inst.size
        self._bg_r.pos  = (x, y)
        self._bg_r.size = (w, h)
        self._bd_l.rectangle = (x, y, w, h)

    def set_unlocked(self, unlocked: bool):
        if unlocked:
            self._bg_c.rgba      = list(_hex4("#1a3a1a"))
            self._bd_c.rgba      = list(BORDER_GLOW)
            self._name_lbl.color = list((0.6, 1.0, 0.6, 1))
            if self._icon_img:
                self._icon_img.color = (1, 1, 1, 1)
        else:
            self._bg_c.rgba      = list(BG_CELL_EMPTY)
            self._bd_c.rgba      = list(BORDER_LIGHT)
            self._name_lbl.color = list(TEXT_DIM)
            if self._icon_img:
                self._icon_img.color = (0.35, 0.35, 0.35, 1)


class TrackerApp(App):

    def build(self):
        self.title         = "MKWii AP Tracker"
        self.cells         = {}
        self.tcells        = {}
        self.icells        = {}
        self._active_tab   = "Cups"
        # All tabs start disabled; enabled once AP connection is established
        self._disabled_tabs: set[str] = {"Cups", "Tracks", "Items"}
        # Track previous connected state to detect connect/disconnect transitions
        self._was_connected: bool = False

        root = BoxLayout(orientation="vertical", padding=[6, 6, 6, 6], spacing=4)
        _paint_bg(root, BG_OUTER)

        # ── top bar ────────────────────────────────────────────────────────
        top_bar = BoxLayout(orientation="horizontal",
                            size_hint=(1, None), height=84,
                            padding=[6, 6, 6, 6], spacing=8)
        _paint_bg(top_bar, BG_CARD, BORDER_GLOW)

        if IMG_MKWII.exists():
            top_bar.add_widget(_centered_image(IMG_MKWII, 72, 72))
        else:
            top_bar.add_widget(_label("MKWii", TEXT_YELLOW, bold=True,
                                      size_hint=(None, 1), width=72))

        info_col = BoxLayout(orientation="vertical", spacing=2)
        _paint_bg(info_col, BG_CARD)
        info_col.add_widget(_label("Mario Kart Wii  •  AP Tracker", TEXT_YELLOW,
                                   font_size="13pt", bold=True,
                                   size_hint_y=0.55, halign="left"))

        status_row = BoxLayout(orientation="horizontal", spacing=3, size_hint_y=0.45)
        _paint_bg(status_row, BG_CARD)
        self._dot = Label(text="•", color=list(TEXT_ORANGE), font_size="14pt",
                          size_hint=(None, 1), width=18)
        self._txt = _label("Enter credentials to connect…" if _STANDALONE_MODE else f"Connecting to {AP_SERVER}…", TEXT_DIM,
                            font_size="9pt", halign="left", size_hint=(1, 1))
        status_row.add_widget(self._dot)
        status_row.add_widget(self._txt)
        info_col.add_widget(status_row)
        top_bar.add_widget(info_col)

        if IMG_AP.exists():
            top_bar.add_widget(_centered_image(IMG_AP, 56, 56))

        root.add_widget(top_bar)

        # ── tab bar ────────────────────────────────────────────────────────
        tab_bar = BoxLayout(orientation="horizontal",
                            size_hint=(1, None), height=30, spacing=4)
        _paint_bg(tab_bar, BG_OUTER)
        self._tab_buttons = {}
        for tab_name in ("Cups", "Tracks", "Items"):
            btn = self._make_tab_btn(tab_name, active=False, disabled=True)
            self._tab_buttons[tab_name] = btn
            tab_bar.add_widget(btn)
        tab_bar.add_widget(BoxLayout(size_hint_x=1))
        root.add_widget(tab_bar)

        # ── content ────────────────────────────────────────────────────────
        self._content = BoxLayout(orientation="vertical", size_hint=(1, 1))
        _paint_bg(self._content, BG_OUTER)
        root.add_widget(self._content)

        self._panels = {
            "Cups":   self._build_cups_panel(),
            "Tracks": self._build_tracks_panel(),
            "Items":  self._build_items_panel(),
        }

        if _STANDALONE_MODE:
            self._show_login_panel()
        else:
            self._show_tab("Cups")

        # Start AP background thread (will wait for creds if standalone)
        t = threading.Thread(target=_run_ap_thread, daemon=True)
        t.start()

        Clock.schedule_interval(self._tick, 0.5)
        return root

    # ── login panel (standalone mode) ─────────────────────────────────────

    def _show_login_panel(self):
        from kivy.uix.textinput import TextInput
        from kivy.uix.button   import Button

        self._content.clear_widgets()
        panel = BoxLayout(orientation="vertical", padding=20, spacing=12,
                          size_hint=(1, 1))
        _paint_bg(panel, BG_CARD, BORDER_GLOW)

        panel.add_widget(_label("Connect to Archipelago Server", TEXT_YELLOW,
                                font_size="12pt", bold=True,
                                size_hint=(1, None), height=36))

        def _inp(hint, text=""):
            ti = TextInput(hint_text=hint, text=text,
                           multiline=False,
                           size_hint=(1, None), height=38,
                           background_color=[0.05, 0.08, 0.22, 1],
                           foreground_color=[1, 1, 1, 1],
                           hint_text_color=[0.4, 0.5, 0.7, 1],
                           cursor_color=[1, 0.88, 0.25, 1],
                           font_size="11pt")
            return ti

        self._inp_server = _inp("Server  (e.g. archipelago.gg:12345)", AP_SERVER)
        self._inp_slot   = _inp("Slot name", AP_SLOT)
        self._inp_pass   = _inp("Password (leave blank if none)", AP_PASS)

        self._login_status = _label("", TEXT_DIM, font_size="9pt",
                                    size_hint=(1, None), height=24)

        btn = Button(text="Connect", size_hint=(1, None), height=42,
                     background_color=[0.35, 0.50, 0.83, 1],
                     color=[1, 1, 1, 1], bold=True, font_size="11pt")
        btn.bind(on_release=self._on_login_connect)

        for w in (self._inp_server, self._inp_slot, self._inp_pass,
                  self._login_status, btn):
            panel.add_widget(w)

        # spacer
        panel.add_widget(BoxLayout(size_hint_y=1))
        self._content.add_widget(panel)

    def _on_login_connect(self, _btn):
        global AP_SERVER, AP_SLOT, AP_PASS, _STANDALONE_MODE
        server = self._inp_server.text.strip()
        slot   = self._inp_slot.text.strip()
        passwd = self._inp_pass.text.strip()

        if not server or not slot:
            self._login_status.text  = "Server address and slot name are required."
            self._login_status.color = list(TEXT_ORANGE)
            return

        AP_SERVER        = server
        AP_SLOT          = slot
        AP_PASS          = passwd
        _STANDALONE_MODE = False

        self._login_status.text  = f"Connecting to {server} as '{slot}'…"
        self._login_status.color = list(TEXT_DIM)

        # Update status bar text
        self._txt.text  = f"Connecting to {server}…"
        self._txt.color = list(TEXT_DIM)

        # Stay on login panel — _tick will switch to Cups once connected

    # ── tab helpers ────────────────────────────────────────────────────────

    def _make_tab_btn(self, label: str, active: bool, disabled: bool = False):
        btn = FloatLayout(size_hint=(None, None), size=(90, 30))
        if disabled:
            bg     = (0.03, 0.04, 0.12, 1)
            border = (0.12, 0.16, 0.32, 1)
            fg     = (0.22, 0.26, 0.40, 1)
        else:
            bg     = BG_CARD if active else BG_OUTER
            border = BORDER_GLOW if active else BORDER_LIGHT
            fg     = TEXT_YELLOW if active else TEXT_DIM
        _paint_bg(btn, bg, border)
        # Strikethrough-style suffix to make disabled state obvious
        display = f"{label} ✕" if disabled else label
        btn.add_widget(_label(display, fg,
                              font_size="9pt", bold=(active and not disabled),
                              pos_hint={"center_x": 0.5, "center_y": 0.5},
                              size_hint=(1, 1)))
        btn.bind(on_touch_down=self._on_tab_touch)
        return btn

    def _on_tab_touch(self, btn_widget, touch):
        if btn_widget.collide_point(*touch.pos):
            for name, w in self._tab_buttons.items():
                if w is btn_widget:
                    if name in self._disabled_tabs:
                        return  # silently ignore clicks on disabled tabs
                    self._show_tab(name)
                    return

    def _show_tab(self, name: str):
        if name in self._disabled_tabs:
            return
        self._active_tab = name
        self._content.clear_widgets()
        self._content.add_widget(self._panels[name])
        for tname, btn in self._tab_buttons.items():
            if tname in self._disabled_tabs:
                continue  # leave disabled tabs with their greyed style
            active = (tname == name)
            btn.canvas.before.clear()
            _paint_bg(btn, BG_CARD if active else BG_OUTER,
                      BORDER_GLOW if active else BORDER_LIGHT)
            lbl = btn.children[0]
            lbl.color = list(TEXT_YELLOW if active else TEXT_DIM)
            lbl.bold  = active

    # ── Cups panel ─────────────────────────────────────────────────────────

    def _build_cups_panel(self):
        grid_wrap = BoxLayout(orientation="vertical", padding=[6, 6, 6, 6], spacing=0,
                              size_hint=(1, 1))
        _paint_bg(grid_wrap, BG_CARD, BORDER_GLOW)

        grid = GridLayout(cols=len(CUPS) + 1, spacing=2, padding=0,
                          size_hint=(None, None), width=_GRID_W)
        grid.bind(minimum_height=grid.setter("height"))

        grid.add_widget(_header_cell("Tracker", BG_OUTER, TEXT_DIM, font_size="9pt"))

        for cup in CUPS:
            short = cup.replace(" Cup", "")
            hdr = FloatLayout(size_hint=(None, None), size=(CELL_SIZE, CELL_SIZE))
            _paint_bg(hdr, BG_HEADER_ROW, BORDER_LIGHT)
            if cup in CUP_ICON_PATHS:
                hdr.add_widget(KvImage(source=CUP_ICON_PATHS[cup],
                                       size_hint=(None, None), size=(36, 36),
                                       allow_stretch=True, keep_ratio=True,
                                       pos_hint={"center_x": 0.5, "center_y": 0.65}))
            hdr.add_widget(_label(short, TEXT_DIM, font_size="7pt",
                                  pos_hint={"center_x": 0.5, "center_y": 0.18},
                                  size_hint=(1, None), height=CELL_SIZE))
            grid.add_widget(hdr)

        for row_idx, cc in enumerate(CCS):
            bg_row = BG_ROW_ODD if row_idx % 2 == 0 else BG_ROW_EVEN
            grid.add_widget(_header_cell(cc, bg_row, TEXT_WHITE,
                                         font_size="9pt", bold=True))
            for cup in CUPS:
                cell = LicenseCell()
                self.cells[(cup, cc)] = cell
                grid.add_widget(cell.widget)

        grid_wrap.add_widget(grid)
        return grid_wrap

    # ── Tracks panel ───────────────────────────────────────────────────────

    def _build_tracks_panel(self):
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                            bar_width=6, scroll_type=["bars", "content"])

        # cc cells are fixed; track name column fills the rest of the window
        _OUTER_PAD  = 6 * 2          # outer BoxLayout padding left+right
        _INNER_PAD  = 6 * 2          # outer padding inside card
        _CELL_COLS  = len(CCS) * CELL_SIZE + (len(CCS) - 1) * 2
        TRACK_NAME_W = _W - _OUTER_PAD - _INNER_PAD - _CELL_COLS - 12
        row_w = TRACK_NAME_W + _CELL_COLS

        outer = BoxLayout(orientation="vertical", padding=[6, 6, 6, 6], spacing=2,
                          size_hint=(None, None), width=row_w + 12)
        _paint_bg(outer, BG_CARD, BORDER_GLOW)
        outer.bind(minimum_height=outer.setter("height"))

        for cup in CUPS:
            short = cup.replace(" Cup", "")

            cup_hdr = BoxLayout(orientation="horizontal", spacing=6,
                                size_hint=(None, None),
                                width=row_w, height=36,
                                padding=[6, 2, 6, 2])
            _paint_bg(cup_hdr, BG_HEADER_ROW, BORDER_LIGHT)
            if cup in CUP_ICON_PATHS:
                cup_hdr.add_widget(KvImage(source=CUP_ICON_PATHS[cup],
                                           size_hint=(None, 1), width=30,
                                           allow_stretch=True, keep_ratio=True))
            cup_hdr.add_widget(_label(short + " Cup", TEXT_YELLOW,
                                      font_size="13pt", bold=True,
                                      halign="left", size_hint=(1, 1)))
            outer.add_widget(cup_hdr)

            for track in TRACKS[cup]:
                row = BoxLayout(orientation="horizontal", spacing=2,
                                size_hint=(None, None),
                                width=row_w, height=CELL_SIZE)

                name_cell = FloatLayout(size_hint=(None, None),
                                        size=(TRACK_NAME_W, CELL_SIZE))
                _paint_bg(name_cell, BG_ROW_ODD, BORDER_LIGHT)
                name_cell.add_widget(_label(track, TEXT_WHITE, font_size="11pt",
                                            bold=True,
                                            pos_hint={"center_x": 0.5, "center_y": 0.5},
                                            size_hint=(1, 1)))
                row.add_widget(name_cell)

                for cc in CCS:
                    cell = TrackCell(cc)
                    self.tcells[(track, cc)] = cell
                    row.add_widget(cell.widget)

                outer.add_widget(row)

        scroll.add_widget(outer)
        return scroll

    # ── Items panel ────────────────────────────────────────────────────────

    def _build_items_panel(self):
        # 6 cols × 3 rows fills the window without scrolling.
        # Cell sizes are fixed pixels so the grid is exactly as large as needed.
        COLS     = 6
        ROWS     = 3
        SPACING  = 4
        PAD      = 6

        # Width: fill _W minus outer root padding (6*2) minus card padding (6*2)
        avail_w = _W - 6 * 2 - PAD * 2 - SPACING * (COLS - 1)
        ITEM_W  = avail_w // COLS

        # Height: _H minus root padding (6*2) minus top-bar+spacing (84+6)
        #         minus tab-bar+spacing (30+4) minus card padding (6*2)
        #         minus cell spacing rows (SPACING*(ROWS-1))
        avail_h = (_H - 6 * 2 - (84 + 6) - (30 + 4) - PAD * 2
                   - SPACING * (ROWS - 1))
        ITEM_H  = avail_h // ROWS

        grid_w = ITEM_W * COLS + SPACING * (COLS - 1)
        grid_h = ITEM_H * ROWS + SPACING * (ROWS - 1)

        wrap = BoxLayout(orientation="vertical", padding=[PAD, PAD, PAD, PAD],
                         size_hint=(1, 1))
        _paint_bg(wrap, BG_CARD, BORDER_GLOW)

        grid = GridLayout(cols=COLS, spacing=SPACING, padding=0,
                          size_hint=(None, None),
                          size=(grid_w, grid_h))

        for item_name in POWERUP_ITEMS:
            cell = ItemCell(item_name, w=ITEM_W, h=ITEM_H)
            self.icells[item_name] = cell
            grid.add_widget(cell.widget)

        wrap.add_widget(grid)
        return wrap

    # ── tab enable/disable helper ──────────────────────────────────────────

    def _apply_tab_states(self, disabled: set) -> None:
        """Re-style all tab buttons to match the given disabled set."""
        if disabled == self._disabled_tabs:
            return
        self._disabled_tabs = disabled
        for tab_name, btn in self._tab_buttons.items():
            is_disabled = tab_name in self._disabled_tabs
            is_active   = (tab_name == self._active_tab) and not is_disabled
            btn.canvas.before.clear()
            if is_disabled:
                _paint_bg(btn, (0.03, 0.04, 0.12, 1), (0.12, 0.16, 0.32, 1))
                lbl = btn.children[0]
                lbl.text  = f"{tab_name} ✕"
                lbl.color = list((0.22, 0.26, 0.40, 1))
                lbl.bold  = False
            else:
                _paint_bg(btn, BG_CARD if is_active else BG_OUTER,
                          BORDER_GLOW if is_active else BORDER_LIGHT)
                lbl = btn.children[0]
                lbl.text  = tab_name
                lbl.color = list(TEXT_YELLOW if is_active else TEXT_DIM)
                lbl.bold  = is_active
        if self._active_tab in self._disabled_tabs:
            self._show_tab("Cups")

    # ── tick ───────────────────────────────────────────────────────────────

    def _tick(self, _dt):
        state = _read_state()

        connected = state["connected"]

        # ── connection state transitions ────────────────────────────────────
        if connected and not self._was_connected:
            # Just connected — unlock tabs per slot_data, switch to Cups
            self._was_connected = True
            new_disabled: set[str] = set()
            if not state["include_race_checks"]:
                new_disabled.add("Tracks")
            if not state["enable_item_randomization"]:
                new_disabled.add("Items")
            self._apply_tab_states(new_disabled)
            self._show_tab("Cups")

        elif not connected and self._was_connected:
            # Lost connection after being connected — lock all tabs, back to login
            self._was_connected = False
            self._apply_tab_states({"Cups", "Tracks", "Items"})
            self._show_login_panel()

        elif not connected and not self._was_connected and AP_SERVER:
            # Still trying to connect (credentials entered but not yet connected)
            # Keep login panel showing — nothing to switch
            pass

        # ── status bar ─────────────────────────────────────────────────────
        if connected:
            self._dot.color = [0, 0.878, 0.376, 1]
            self._txt.text  = f"Connected — {AP_SLOT} @ {AP_SERVER}"
            self._txt.color = [0.502, 1, 0.690, 1]
        else:
            self._dot.color = list(TEXT_ORANGE)
            self._txt.text  = (f"Connecting to {AP_SERVER}…" if AP_SERVER else "Enter credentials to connect…")
            self._txt.color = list(TEXT_DIM)

        completed   = state["completed_locations"]
        track_locs  = state["track_locations"]
        unlocked    = set(state["unlocked_items"])

        for (cup, cc), cell in self.cells.items():
            tier = completed.get(f"{cup}||{cc}", "none")
            cell.set_tier(tier)

        for (track, cc), cell in self.tcells.items():
            done = track_locs.get(f"{track}||{cc}", False)
            cell.set_done(done=done)

        for item_name, cell in self.icells.items():
            cell.set_unlocked(unlocked=(item_name in unlocked))


if __name__ == "__main__":
    try:
        TrackerApp().run()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        with open(_LOG, "w", encoding="utf-8") as f:
            f.write(tb)
        print(tb, file=sys.__stderr__)
        raise