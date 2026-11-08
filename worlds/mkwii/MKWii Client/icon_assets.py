"""
Icon files for the menu lock (MKWii PAL, RMCP01).

The menu lock swaps the icon textures of locked characters and cups for the
game's own "?" texture. That needs the original bytes of every icon and the
bytes of the "?" textures. They are Nintendo data, so none of it ships with
the client. Instead:

    icon_manifest.json   ships with the client, hashes only (SHA-256 of each
                         texture and a CRC32 of a short slice used to find it)
    bins/                local to the player, filled by IconCapture from the
                         player's own running game, never committed

The first time a player opens the character select and the cup select, the
textures are in memory. IconCapture finds them by their hashes and saves them
to bins/. From then on they are just files. The one exception is the 128x128
"?" for the cups: the game has none, so it is made from the 64x64 one (Lanczos). make_icon_manifest.py creates the
manifest from a bins/ folder (run it once, as the maintainer).
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from reporting import ReportHandler

# Character icons are 64x64 RGB5A3 (2 bytes per pixel), cup icons are 128x128.
CHARACTER_ICON_SIZE = 64 * 64 * 2
CUP_ICON_SIZE = 128 * 128 * 2

# The "?" textures are saved under these names, the originals as <name>.bin (see _file_stem)
QMARK_64_FILE = "qmark64.bin"
QMARK_128_FILE = "qmark128.bin"
MANIFEST_FILE = "icon_manifest.json"

# Textures sit at 32 byte aligned addresses and the probe slice is 32 bytes at a multiple of 32, so the capture only has to look at aligned windows.
PROBE_LENGTH = 32

# The capture scan costs about 0.4 s of CPU, so while icons are still missing it runs at most every CAPTURE_SECS. After CAPTURE_FAST_RUNS runs in a row that found nothing (the menus are not open) it slows down to CAPTURE_SLOW_SECS.
CAPTURE_SECS = 2.0
CAPTURE_FAST_RUNS = 30
CAPTURE_SLOW_SECS = 8.0


@dataclass
class Icon:
    original: bytes
    qmark: bytes
    # A short, distinctive slice of the original used to find it quickly.
    probe_offset: int
    probe: bytes
    # Write the original back when the item unlocks. Character icons skip this because the game reloads them when the selection opens.
    restore: bool = True


def default_icon_names() -> Tuple[List[str], List[str]]:
    """Names of the default characters and cups, the ones that get locked."""
    from worlds.mkwii.mkwii_info_lib import BASE_CUP_NAMES
    from worlds.mkwii.items import DEFAULT_CHARACTER_ITEMS

    characters = [n for n in DEFAULT_CHARACTER_ITEMS]
    return characters, sorted(BASE_CUP_NAMES)


# Textures that are not in the game and are made locally instead (see make_qmark128), so they are never in the manifest and never captured
DERIVED_NAMES = {"qmark128"}


def icon_specs(characters: List[str], cups: List[str]) -> List[Tuple[str, int]]:
    """Every texture of the game the menu lock needs as (name, size in bytes)."""
    return (
        [(name, CHARACTER_ICON_SIZE) for name in characters]
        + [(name, CUP_ICON_SIZE) for name in cups]
        + [("qmark64", CHARACTER_ICON_SIZE)]
    )


# Local files

def _file_stem(name: str) -> str:
    # "Baby Peach" -> "baby_peach", "Mushroom Cup" -> "mushroom_cup"
    return name.lower().replace(".", "").replace(" ", "_")


# Other file names accepted for an icon, compared without case, spaces, dots, dashes and underscores. Other prefixes and suffixes are ignored too, so "chara_baby_peach_icon.bin" also works.
ICON_FILE_ALIASES = {
    "Donkey Kong": ("dk",),
    "Koopa Troopa": ("koopa",),
    "Baby Mario": ("bmario",),
    "Baby Peach": ("bpeach",),
}
ICON_FILE_PREFIXES = ("character", "chara", "char", "icon")
ICON_FILE_SUFFIXES = ("icon",)


def _squash(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def find_icon_file(asset_dir: Path, name: str, taken: Set[Path]) -> Optional[Path]:
    exact = asset_dir / f"{_file_stem(name)}.bin"
    if exact.exists():
        return exact

    wanted = {_squash(name), *(_squash(alias) for alias in ICON_FILE_ALIASES.get(name, ()))}
    for path in sorted(asset_dir.glob("*.bin")):
        stem = _squash(path.stem)
        for prefix in ("",) + ICON_FILE_PREFIXES:
            if not stem.startswith(prefix):
                continue
            core = stem[len(prefix):]
            for suffix in ("",) + ICON_FILE_SUFFIXES:
                if core.endswith(suffix) and core[:len(core) - len(suffix)] in wanted and path not in taken:
                    return path
    return None


def pick_probe(data: bytes, length: int = PROBE_LENGTH) -> Tuple[int, bytes]:
    # A slice with many different bytes, so it rarely matches by accident.
    # A slice of zeros would match half of memory.
    for offset in range(0, len(data) - length, length):
        chunk = data[offset:offset + length]
        if len(set(chunk)) >= 8:
            return offset, chunk
    return 0, data[:length]


def load_icons(
    asset_dir: Path,
    names: List[str],
    size: int,
    qmark_file: str,
    restore: bool,
    reporter: ReportHandler,
    quiet_missing: bool = False,
) -> Dict[str, Icon]:
    """Load the local original icons of the given names and the "?" texture.

    Missing files are reported as warnings, unless quiet_missing is set
    (they are about to be captured from the game).
    """
    qmark_path = asset_dir / qmark_file
    if not qmark_path.exists():
        if not quiet_missing:
            reporter.report(type="WARNING", msg=f"[MenuLock] {qmark_path} missing, skipping {size} byte icons")
        return {}
    qmark = qmark_path.read_bytes()
    if len(qmark) != size:
        reporter.report(type="WARNING", msg=f"[MenuLock] {qmark_file} is {len(qmark)} bytes, expected {size}")
        return {}

    icons: Dict[str, Icon] = {}
    missing: List[str] = []
    taken: Set[Path] = {qmark_path}
    for name in names:
        path = find_icon_file(asset_dir, name, taken)
        if path is None:
            missing.append(name)
            continue
        taken.add(path)
        original = path.read_bytes()
        if len(original) != size:
            reporter.report(type="WARNING", msg=f"[MenuLock] {path.name} is {len(original)} bytes, expected {size}")
            continue
        icons[name] = Icon(original, qmark, *pick_probe(original), restore=restore)

    if missing and not quiet_missing:
        reporter.report(
            type="WARNING", msg=f"[MenuLock] No original icon file in {asset_dir} for: {', '.join(missing)}"
        )
        # Show what is there so a naming mismatch is easy to spot
        unused = sorted(p.name for p in asset_dir.glob("*.bin") if p not in taken and p.stat().st_size == size)
        shown = ", ".join(unused[:30]) if unused else f"none, no unused {size} byte .bin files in that folder"
        reporter.report(type="WARNING", msg=f"[MenuLock] Unused .bin files: {shown}")
    return icons


# The 128x128 "?" for the cup icons. The game has no such texture, so it is made from the 64x64 one with a Lanczos resize.

Pixel = Tuple[int, int, int, int]


def _decode_rgb5a3(data: bytes, width: int, height: int) -> List[Pixel]:
    # Tiles of 4x4 pixels, 16 bit big endian. Top bit set: opaque RGB555. Otherwise 3 bit alpha and RGB444.
    pixels: List[Pixel] = [(0, 0, 0, 0)] * (width * height)
    tiles_per_row = width // 4
    for tile in range(tiles_per_row * (height // 4)):
        tx, ty = (tile % tiles_per_row) * 4, (tile // tiles_per_row) * 4
        for i in range(16):
            value = int.from_bytes(data[tile * 32 + i * 2:tile * 32 + i * 2 + 2], "big")
            if value & 0x8000:
                r, g, b = (value >> 10) & 0x1F, (value >> 5) & 0x1F, value & 0x1F
                pixel = ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), 255)
            else:
                a = (value >> 12) & 0x7
                pixel = (((value >> 8) & 0xF) * 17, ((value >> 4) & 0xF) * 17, (value & 0xF) * 17,
                         (a << 5) | (a << 2) | (a >> 1))
            pixels[(ty + i // 4) * width + tx + i % 4] = pixel
    return pixels


def _encode_rgb5a3(pixels: List[Pixel], width: int, height: int) -> bytes:
    out = bytearray()
    for ty in range(0, height, 4):
        for tx in range(0, width, 4):
            for y in range(ty, ty + 4):
                for x in range(tx, tx + 4):
                    r, g, b, a = pixels[y * width + x]
                    if a == 255:
                        value = 0x8000 | (r >> 3) << 10 | (g >> 3) << 5 | (b >> 3)
                    else:
                        value = (a >> 5) << 12 | (r >> 4) << 8 | (g >> 4) << 4 | (b >> 4)
                    out += value.to_bytes(2, "big")
    return bytes(out)


# Lanczos resize, a pure Python copy of what Pillow's Image.resize(..., LANCZOS) does for RGBA images, step for step (premultiplied alpha, 22 bit fixed point weights, a horizontal then a vertical pass). That makes the result identical to a qmark128.bin that was made with Pillow, and the client needs no Pillow.
LANCZOS_SUPPORT = 3.0
WEIGHT_BITS = 22


def _lanczos(x: float) -> float:
    if x <= -LANCZOS_SUPPORT or x >= LANCZOS_SUPPORT:
        return 0.0
    if x == 0.0:
        return 1.0
    a = math.pi * x
    b = a / LANCZOS_SUPPORT
    return (math.sin(a) / a) * (math.sin(b) / b)


def _resize_weights(in_size: int, out_size: int) -> List[Tuple[int, List[int]]]:
    """For every output position: the first input position and the fixed point weights."""
    scale = in_size / out_size
    stretch = max(scale, 1.0)
    support = LANCZOS_SUPPORT * stretch
    rows = []
    for out_pos in range(out_size):
        center = (out_pos + 0.5) * scale
        first = max(int(center - support + 0.5), 0)
        last = min(int(center + support + 0.5), in_size)
        weights = [_lanczos((first + i - center + 0.5) / stretch) for i in range(last - first)]
        total = 0.0
        for weight in weights:
            total += weight
        if total != 0.0:
            weights = [weight / total for weight in weights]
        scaled = [weight * (1 << WEIGHT_BITS) for weight in weights]
        rows.append((first, [int(v + 0.5) if v >= 0 else int(v - 0.5) for v in scaled]))
    return rows


def _clip8(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else value


def _convolve(line: List[Tuple[int, ...]], weights: List[Tuple[int, List[int]]]) -> List[Tuple[int, ...]]:
    out = []
    for first, taps in weights:
        out.append(tuple(
            _clip8(((1 << (WEIGHT_BITS - 1)) + sum(line[first + i][c] * w for i, w in enumerate(taps))) >> WEIGHT_BITS)
            for c in range(4)
        ))
    return out


def make_qmark128(qmark64: bytes) -> bytes:
    """Make the 128x128 "?" from the 64x64 one with a Lanczos resize."""
    src_size, dst_size = 64, 128
    pixels = _decode_rgb5a3(qmark64, src_size, src_size)

    # Premultiply the colours with alpha, so transparent pixels do not bleed into the edge
    def premultiply(c: int, a: int) -> int:
        t = c * a + 128
        return ((t >> 8) + t) >> 8

    premultiplied = [(premultiply(r, a), premultiply(g, a), premultiply(b, a), a) for r, g, b, a in pixels]
    weights = _resize_weights(src_size, dst_size)

    # Horizontal pass over every row, then vertical pass over every column
    wide = [
        pixel for y in range(src_size)
        for pixel in _convolve(premultiplied[y * src_size:(y + 1) * src_size], weights)
    ]
    columns = [_convolve([wide[y * dst_size + x] for y in range(src_size)], weights) for x in range(dst_size)]
    resized = [columns[x][y] for y in range(dst_size) for x in range(dst_size)]

    result: List[Pixel] = []
    for r, g, b, a in resized:
        if a in (0, 255):
            result.append((r, g, b, a))
        else:
            result.append((_clip8(255 * r // a), _clip8(255 * g // a), _clip8(255 * b // a), a))
    return _encode_rgb5a3(result, dst_size, dst_size)


def ensure_qmark128(asset_dir: Path, reporter: ReportHandler) -> None:
    """Make qmark128.bin from qmark64.bin when it does not exist. An existing
    file is never replaced."""
    target = asset_dir / QMARK_128_FILE
    source = asset_dir / QMARK_64_FILE
    if target.exists() or not source.exists():
        return
    data = source.read_bytes()
    if len(data) != CHARACTER_ICON_SIZE:
        return
    try:
        target.write_bytes(make_qmark128(data))
    except OSError as e:
        reporter.report(type="WARNING", msg=f"[MenuLock] Cannot save {QMARK_128_FILE}: {e}")
        return
    reporter.report(type="INFO", msg=f"[MenuLock] Made {QMARK_128_FILE} from {QMARK_64_FILE}")


# Manifest

@dataclass
class ManifestEntry:
    name: str
    size: int
    # SHA-256 of the whole texture, the proof that a capture is the real one
    sha256: str
    # CRC32 of the 32 byte probe slice at probe_offset, only used to find candidates quickly
    probe_offset: int
    probe_crc32: int


def entry_from_bytes(name: str, data: bytes) -> ManifestEntry:
    offset, probe = pick_probe(data)
    return ManifestEntry(name, len(data), hashlib.sha256(data).hexdigest(), offset, zlib.crc32(probe))


def save_manifest(path: Path, entries: List[ManifestEntry]) -> None:
    document = {
        "game": "RMCP01",
        "icons": [
            {
                "name": e.name,
                "size": e.size,
                "sha256": e.sha256,
                "probe_offset": e.probe_offset,
                "probe_crc32": e.probe_crc32,
            }
            for e in entries
        ],
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def load_manifest(path: Path, reporter: ReportHandler) -> List[ManifestEntry]:
    """Read the manifest. A missing or broken one is not fatal, the icon files
    then have to be put into bins/ by hand."""
    if not path.exists():
        reporter.report(type="WARNING", msg=f"[MenuLock] {path.name} not found, icons cannot be captured from the game")
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        return [ManifestEntry(**item) for item in document["icons"]]
    except (OSError, ValueError, KeyError, TypeError) as e:
        reporter.report(type="WARNING", msg=f"[MenuLock] Could not read {path.name}: {e}")
        return []


# Capture

class IconCapture:
    """Saves the icons that are still missing in bins/ from a MEM2 snapshot.

    A texture is only saved when its whole SHA-256 matches the manifest, so a
    capture is always the real icon and never a half loaded or replaced one.
    Existing files are never overwritten.
    """

    def __init__(self, asset_dir: Path, entries: List[ManifestEntry], base: int, reporter: ReportHandler) -> None:
        self._asset_dir = asset_dir
        self._base = base
        self._reporter = reporter
        entries = [e for e in entries if e.name not in DERIVED_NAMES]
        self._total = len(entries)
        self._pending = [e for e in entries if find_icon_file(asset_dir, e.name, set()) is None]
        self._last_run = float("-inf")
        self._empty_runs = 0
        self._write_failed = False

    def pending(self) -> bool:
        return bool(self._pending) and not self._write_failed

    def pending_names(self) -> List[str]:
        return [e.name for e in self._pending]

    def due(self) -> bool:
        interval = CAPTURE_SECS if self._empty_runs < CAPTURE_FAST_RUNS else CAPTURE_SLOW_SECS
        return self.pending() and time.monotonic() - self._last_run >= interval

    def run(self, snapshot: bytes) -> List[str]:
        """Look for the missing icons in the snapshot, save what is found and
        return their names. Runs in the scan thread."""
        self._last_run = time.monotonic()
        by_probe: Dict[int, List[ManifestEntry]] = {}
        for entry in self._pending:
            by_probe.setdefault(entry.probe_crc32, []).append(entry)

        found: Dict[str, bytes] = {}
        view = memoryview(snapshot)
        crc32 = zlib.crc32
        for pos in range(0, len(snapshot) - PROBE_LENGTH + 1, PROBE_LENGTH):
            candidates = by_probe.get(crc32(view[pos:pos + PROBE_LENGTH]))
            if candidates is None:
                continue
            for entry in candidates:
                start = pos - entry.probe_offset
                texture = view[start:start + entry.size]
                if (
                    entry.name not in found
                    and start >= 0
                    and len(texture) == entry.size
                    and hashlib.sha256(texture).hexdigest() == entry.sha256
                ):
                    found[entry.name] = bytes(texture)
            if len(found) == len(self._pending):
                break

        saved = self._save(found)
        self._empty_runs = 0 if saved else self._empty_runs + 1
        return saved

    def _save(self, found: Dict[str, bytes]) -> List[str]:
        saved: List[str] = []
        for entry in list(self._pending):
            data = found.get(entry.name)
            if data is None:
                continue
            path = self._asset_dir / f"{_file_stem(entry.name)}.bin"
            try:
                self._asset_dir.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    temp = path.with_suffix(".tmp")
                    temp.write_bytes(data)
                    temp.replace(path)
            except OSError as e:
                self._write_failed = True
                self._reporter.report(type="WARNING", msg=f"[MenuLock] Cannot save icons to {self._asset_dir}: {e}")
                return saved
            self._pending.remove(entry)
            saved.append(entry.name)
            self._reporter.report(type="INFO", msg=f"[MenuLock] Captured {entry.name} icon from the game ({path.name})")

        if saved:
            done = self._total - len(self._pending)
            self._reporter.report(type="INFO", msg=f"[MenuLock] {done}/{self._total} icon files captured")
        return saved