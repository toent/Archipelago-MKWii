"""
Location tracker window for Mario Kart Wii AP Client.

Styled to replicate the in-game license/profile screen aesthetic.
Displays a grid of cup/CC completions with live updates.
Runs in a separate thread to avoid blocking the async event loop.
"""
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, font as tkfont
from typing import TYPE_CHECKING, Dict, Optional, Tuple

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

if TYPE_CHECKING:
    from mkwii_client import MKWiiContext

# Asset paths
if getattr(sys, 'frozen', False):
    _HERE = Path(sys.executable).parent
else:
    _HERE = Path(__file__).parent

IMG_DIR   = _HERE / "img"
IMG_MKWII = IMG_DIR / "mkwiiLicenseImage.png"
IMG_AP    = IMG_DIR / "AP_Asset_Pack" / "color-icon.png"


# Palette
BG_OUTER        = "#0a0f2e"
BG_CARD         = "#111a4a"
BG_HEADER_ROW   = "#0d1540"
BG_ROW_ODD      = "#131e54"
BG_ROW_EVEN     = "#0f1844"
BG_CELL_EMPTY   = "#090d2a"
BORDER_LIGHT    = "#3a4fa0"
BORDER_GLOW     = "#5a7fd4"
TEXT_WHITE      = "#ffffff"
TEXT_YELLOW     = "#ffe040"
TEXT_DIM        = "#6a7fc0"
TEXT_ORANGE     = "#ff8c00"

# Tier styling
TIER_COLORS: Dict[str, str] = {
    "none":       TEXT_DIM,
    "3rd_place":  "#221100",
    "2nd_place":  "#4B4B4B",
    "1st_place":  "#645000",
    "1_star":     "#645000",
    "2_star":     "#645000",
    "3_star":     "#645000",
}

TIER_BG: Dict[str, str] = {
    "none":       BG_CELL_EMPTY,
    "3rd_place":  "#cd7f32",
    "2nd_place":  "#c0c0c0",
    "1st_place":  "#deb900",
    "1_star":     "#deb900",
    "2_star":     "#deb900",
    "3_star":     "#deb900",
}

TIER_SYMBOLS: Dict[str, str] = {
    "none":       "",
    "3rd_place":  "🏆",
    "2nd_place":  "🏆",
    "1st_place":  "🏆",
    "1_star":     "★",
    "2_star":     "★★",
    "3_star":     "★★★",
}

# Cup display names with emoji shorthand
CUP_ICONS: Dict[str, str] = {
    "Mushroom Cup": "🍄",
    "Flower Cup":   "🌻",
    "Star Cup":     "⭐",
    "Special Cup":  "👑",
    "Shell Cup":    "🐢",
    "Banana Cup":   "🍌",
    "Leaf Cup":     "🍂",
    "Lightning Cup":"⚡",
}

CUPS = list(CUP_ICONS.keys())
CCS  = ["50cc", "100cc", "150cc", "Mirror"]


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _blend(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _load_image(path: Path, size: Tuple[int, int]) -> Optional["ImageTk.PhotoImage"]:
    """Load and resize an image for tkinter. Returns None if unavailable."""
    if not PIL_AVAILABLE or not path.exists():
        return None
    try:
        img = Image.open(path).convert("RGBA").resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


class LicenseCell(tk.Frame):
    """A single cell in the cup grid, styled like an MKW license trophy slot."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(
            parent,
            bg=BG_CELL_EMPTY,
            highlightbackground=BORDER_LIGHT,
            highlightthickness=1,
            width=68,
            height=68,
            **kwargs,
        )
        self.pack_propagate(False)
        self.label = tk.Label(
            self,
            text="",
            bg=BG_CELL_EMPTY,
            fg=TEXT_DIM,
            font=("Segoe UI Emoji", 11),
            anchor="center",
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")

    def set_tier(self, tier: str) -> None:
        bg   = TIER_BG.get(tier, BG_CELL_EMPTY)
        fg   = TIER_COLORS.get(tier, TEXT_DIM)
        sym  = TIER_SYMBOLS.get(tier, "–")
        self.config(bg=bg, highlightbackground=BORDER_GLOW if tier != "none" else BORDER_LIGHT)
        self.label.config(text=sym, bg=bg, fg=fg)


class LocationTrackerWindow:
    """Tkinter window styled like the Mario Kart Wii license screen."""

    def __init__(self, ctx: "MKWiiContext") -> None:
        self.ctx  = ctx
        self.root: Optional[tk.Tk] = None
        self.cells: Dict[Tuple[str, str], LicenseCell] = {}
        self.status_dot:  Optional[tk.Label] = None
        self.status_text: Optional[tk.Label] = None
        self.running: bool = False
        # Keep references so tkinter doesn't GC the images
        self._img_mkwii: Optional["ImageTk.PhotoImage"] = None
        self._img_ap:    Optional["ImageTk.PhotoImage"] = None

    # Public API
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        thread = threading.Thread(target=self._run_window, daemon=True)
        thread.start()

    # Window construction
    def _run_window(self) -> None:
        self.root = tk.Tk()
        self.root.title("MKWii AP Tracker")
        self.root.configure(bg=BG_OUTER)
        self.root.resizable(False, False)

        self._build_ui()
        self._schedule_update()

        try:
            self.root.mainloop()
        except Exception:
            pass
        finally:
            self.running = False

    def _build_ui(self) -> None:
        root = self.root

        # Pre-load images
        self._img_mkwii = _load_image(IMG_MKWII, (72, 72))
        self._img_ap    = _load_image(IMG_AP,    (56, 56))

        # Outer padding frame
        outer = tk.Frame(root, bg=BG_OUTER, padx=12, pady=10)
        outer.pack(fill="both", expand=True)

        # Top bar
        top_bar = tk.Frame(outer, bg=BG_CARD,
                           highlightbackground=BORDER_GLOW, highlightthickness=2)
        top_bar.pack(fill="x", pady=(0, 8))

        # MKWii banner image
        if self._img_mkwii:
            banner = tk.Label(top_bar, image=self._img_mkwii, bg=BG_CARD, borderwidth=0)
        else:
            # Fallback: plain dark box if image not found
            banner = tk.Label(top_bar, text="MKWii", bg="#1a2050",
                              fg=TEXT_YELLOW, font=("Trebuchet MS", 10, "bold"),
                              width=8, height=4)
        banner.pack(side="left", padx=(6, 8), pady=6)

        # Title + connection status
        info_frame = tk.Frame(top_bar, bg=BG_CARD)
        info_frame.pack(side="left", fill="both", expand=True, padx=0, pady=6)

        tk.Label(
            info_frame,
            text="Mario Kart Wii  •  AP Tracker",
            bg=BG_CARD, fg=TEXT_YELLOW,
            font=("Trebuchet MS", 13, "bold"),
            anchor="w",
        ).pack(anchor="w")

        status_row = tk.Frame(info_frame, bg=BG_CARD)
        status_row.pack(anchor="w", pady=(2, 0))

        self.status_dot = tk.Label(status_row, text="●", bg=BG_CARD, fg="#ff6600",
                                   font=("Arial", 10))
        self.status_dot.pack(side="left")

        self.status_text = tk.Label(status_row, text="Waiting for Dolphin…",
                                    bg=BG_CARD, fg=TEXT_DIM, font=("Trebuchet MS", 9))
        self.status_text.pack(side="left", padx=(3, 0))

        # Archipelago logo
        if self._img_ap:
            ap_widget = tk.Label(top_bar, image=self._img_ap, bg=BG_CARD, borderwidth=0)
            ap_widget.pack(side="right", padx=10, pady=6)
        else:
            # Fallback placeholder frame — shown until archipelago_logo.png is in Img/
            ap_fallback = tk.Frame(top_bar, bg="#1e3a8a", width=54, height=34,
                                   highlightbackground=BORDER_GLOW, highlightthickness=1)
            ap_fallback.pack(side="right", padx=10, pady=6)
            ap_fallback.pack_propagate(False)
            tk.Label(ap_fallback, text="AP", bg="#1e3a8a", fg=TEXT_YELLOW,
                     font=("Trebuchet MS", 13, "bold")).place(relx=0.5, rely=0.5, anchor="center")

        # License grid
        grid_outer = tk.Frame(outer, bg=BG_CARD,
                              highlightbackground=BORDER_GLOW, highlightthickness=2)
        grid_outer.pack(fill="both", expand=True)

        grid_frame = tk.Frame(grid_outer, bg=BG_CARD, padx=6, pady=6)
        grid_frame.pack(fill="both", expand=True)

        CELL_W   = 68
        CELL_H   = 68
        CC_COL_W = 68


        # Corner spacer
        corner = tk.Frame(grid_frame, bg=BG_OUTER, width=CC_COL_W, height=CELL_H,
                          highlightbackground=BORDER_LIGHT, highlightthickness=1)
        corner.grid(row=0, column=0, padx=1, pady=1, sticky="nsew")
        corner.pack_propagate(False)
        tk.Label(corner, text="Tracker", bg=BG_OUTER, fg=TEXT_DIM,
                 font=("Trebuchet MS", 9), anchor="center").place(relx=0.5, rely=0.5, anchor="center")

        # Cup column headers
        for col, cup in enumerate(CUPS):
            icon  = CUP_ICONS[cup]
            short = cup.replace(" Cup", "")
            hdr = tk.Frame(grid_frame, bg=BG_HEADER_ROW, width=CELL_W, height=CELL_H,
                           highlightbackground=BORDER_LIGHT, highlightthickness=1)
            hdr.grid(row=0, column=col + 1, padx=1, pady=1, sticky="nsew")
            hdr.pack_propagate(False)
            tk.Label(hdr, text=icon, bg=BG_HEADER_ROW, fg=TEXT_WHITE,
                     font=("Segoe UI Emoji", 18), anchor="center").place(relx=0.5, rely=0.35, anchor="center")
            tk.Label(hdr, text=short, bg=BG_HEADER_ROW, fg=TEXT_DIM,
                     font=("Trebuchet MS", 7), anchor="center").place(relx=0.5, rely=0.82, anchor="center")

        # CC rows
        for row, cc in enumerate(CCS):
            bg_row = BG_ROW_ODD if row % 2 == 0 else BG_ROW_EVEN

            cc_cell = tk.Frame(grid_frame, bg=bg_row, width=CC_COL_W, height=CELL_H,
                               highlightbackground=BORDER_LIGHT, highlightthickness=1)
            cc_cell.grid(row=row + 1, column=0, padx=1, pady=1, sticky="nsew")
            cc_cell.pack_propagate(False)
            tk.Label(cc_cell, text=cc, bg=bg_row, fg=TEXT_WHITE,
                     font=("Trebuchet MS", 9, "bold"), anchor="center"
                     ).place(relx=0.5, rely=0.5, anchor="center")

            for col, cup in enumerate(CUPS):
                cell = LicenseCell(grid_frame)
                cell.grid(row=row + 1, column=col + 1, padx=1, pady=1, sticky="nsew")
                self.cells[(cup, cc)] = cell

        # Resize to fit
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_reqwidth(), self.root.winfo_reqheight())

    # Live update loop
    def _schedule_update(self) -> None:
        if not self.root or not self.running:
            return
        try:
            connected = getattr(self.ctx, "dolphin", None) and self.ctx.dolphin.is_connected

            if self.status_dot and self.status_text:
                if connected:
                    self.status_dot.config(fg="#00e060")
                    self.status_text.config(text="Connected to Dolphin", fg="#80ffb0")
                else:
                    self.status_dot.config(fg=TEXT_ORANGE)
                    self.status_text.config(text="Waiting for Dolphin…", fg=TEXT_DIM)

            completed = getattr(self.ctx, "completed_locations", {})
            for (cup, cc), cell in self.cells.items():
                tier = completed.get((cup, cc), "none")
                cell.set_tier(tier)

            self.root.after(500, self._schedule_update)
        except Exception:
            pass


_tracker_instance: Optional[LocationTrackerWindow] = None


def launch_tracker(ctx: "MKWiiContext") -> None:
    """Launch (or reuse) the location tracker window."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = LocationTrackerWindow(ctx)
    _tracker_instance.start()