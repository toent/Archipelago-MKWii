"""
Location tracker window for Mario Kart Wii AP Client.

Styled to replicate the in-game license/profile screen aesthetic.
Displays a grid of cup/CC completions with live updates.
Runs in a separate thread to avoid blocking the async event loop.

Ported from tkinter to Kivy to match the rest of the AP client UI stack.
Visual output is intentionally identical to the original tkinter version.
"""
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from mkwii_client import MKWiiContext

# Asset paths
if getattr(sys, "frozen", False):
    _HERE = Path(sys.executable).parent
else:
    _HERE = Path(__file__).parent

IMG_DIR   = _HERE / "img"
IMG_MKWII = IMG_DIR / "mkwiiLicenseImage.png"
IMG_AP    = IMG_DIR / "AP_Asset_Pack" / "color-icon.png"

# Palette
BG_OUTER        = (0.039, 0.059, 0.180, 1)   # #0a0f2e
BG_CARD         = (0.067, 0.102, 0.290, 1)   # #111a4a
BG_HEADER_ROW   = (0.051, 0.082, 0.251, 1)   # #0d1540
BG_ROW_ODD      = (0.075, 0.118, 0.329, 1)   # #131e54
BG_ROW_EVEN     = (0.059, 0.094, 0.282, 1)   # #0f1844
BG_CELL_EMPTY   = (0.035, 0.051, 0.165, 1)   # #090d2a
BORDER_LIGHT    = (0.227, 0.310, 0.627, 1)   # #3a4fa0
BORDER_GLOW     = (0.353, 0.498, 0.831, 1)   # #5a7fd4
TEXT_WHITE      = (1, 1, 1, 1)
TEXT_YELLOW     = (1, 0.878, 0.251, 1)        # #ffe040
TEXT_DIM        = (0.416, 0.498, 0.753, 1)   # #6a7fc0
TEXT_ORANGE     = (1, 0.549, 0, 1)            # #ff8c00

def _hex4(h: str) -> Tuple[float, float, float, float]:
    h = h.lstrip("#")
    r, g, b = int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255
    return (r, g, b, 1)

# Tier colours
TIER_BG: Dict[str, Tuple] = {
    "none":      BG_CELL_EMPTY,
    "3rd_place": _hex4("#cd7f32"),
    "2nd_place": _hex4("#c0c0c0"),
    "1st_place": _hex4("#deb900"),
    "1_star":    _hex4("#deb900"),
    "2_star":    _hex4("#deb900"),
    "3_star":    _hex4("#deb900"),
}

TIER_FG: Dict[str, Tuple] = {
    "none":      TEXT_DIM,
    "3rd_place": _hex4("#221100"),
    "2nd_place": _hex4("#4B4B4B"),
    "1st_place": _hex4("#645000"),
    "1_star":    _hex4("#645000"),
    "2_star":    _hex4("#645000"),
    "3_star":    _hex4("#645000"),
}

TIER_SYMBOLS: Dict[str, str] = {
    "none":      "",
    "3rd_place": "🏆",
    "2nd_place": "🏆",
    "1st_place": "🏆",
    "1_star":    "★",
    "2_star":    "★★",
    "3_star":    "★★★",
}

CUP_ICONS: Dict[str, str] = {
    "Mushroom Cup":  "🍄",
    "Flower Cup":    "🌻",
    "Star Cup":      "⭐",
    "Special Cup":   "👑",
    "Shell Cup":     "🐢",
    "Banana Cup":    "🍌",
    "Leaf Cup":      "🍂",
    "Lightning Cup": "⚡",
}

CUPS = list(CUP_ICONS.keys())
CCS  = ["50cc", "100cc", "150cc", "Mirror"]

CELL_SIZE = 68   # px

# Kivy imports  (deferred so the module can be imported without a display)
def _import_kivy():
    """Import Kivy lazily to avoid polluting the import namespace."""
    import kivy
    kivy.require("2.0.0")

    from kivy.app             import App
    from kivy.clock           import Clock
    from kivy.core.image      import Image as CoreImage
    from kivy.graphics        import Color, Rectangle, Line
    from kivy.uix.boxlayout   import BoxLayout
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.gridlayout  import GridLayout
    from kivy.uix.image       import Image as KvImage
    from kivy.uix.label       import Label
    from kivy.uix.widget      import Widget
    from kivy.config          import Config

    return (App, Clock, CoreImage, Color, Rectangle, Line,
            BoxLayout, FloatLayout, GridLayout, KvImage, Label, Widget, Config)


# Helper: coloured bordered box
def _make_bordered_box(parent_canvas, x, y, w, h, bg, border):
    """Draw a filled rectangle with a 1-px border onto parent_canvas."""
    from kivy.graphics import Color, Rectangle, Line
    with parent_canvas:
        Color(*bg)
        Rectangle(pos=(x, y), size=(w, h))
        Color(*border)
        Line(rectangle=(x, y, w, h), width=1)


# LicenseCell widget
class LicenseCellWidget:
    """
    A single 68×68 cell in the cup grid.
    Wraps a Kivy FloatLayout so we can layer a background + a centred label.
    """

    def __init__(self, Grid, row_hint, col_hint):
        from kivy.uix.floatlayout import FloatLayout
        from kivy.uix.label       import Label
        from kivy.graphics        import Color, Rectangle, Line

        self._Color     = Color
        self._Rectangle = Rectangle
        self._Line      = Line

        self.widget = FloatLayout(size_hint=(None, None),
                                  size=(CELL_SIZE, CELL_SIZE))

        # Background canvas instruction references so we can update them
        with self.widget.canvas.before:
            self._bg_color  = Color(*BG_CELL_EMPTY)
            self._bg_rect   = Rectangle(size=(CELL_SIZE, CELL_SIZE))
            self._bdr_color = Color(*BORDER_LIGHT)
            self._bdr_line  = Line(rectangle=(0, 0, CELL_SIZE, CELL_SIZE), width=1)

        self._label = Label(
            text="",
            color=list(TEXT_DIM),
            font_size="11sp",
            halign="center",
            valign="middle",
            size_hint=(1, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self.widget.add_widget(self._label)

        # Keep canvas in sync with widget position
        self.widget.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, instance, _value):
        x, y = instance.pos
        w, h = instance.size
        self._bg_rect.pos  = (x, y)
        self._bg_rect.size = (w, h)
        self._bdr_line.rectangle = (x, y, w, h)

    def set_tier(self, tier: str) -> None:
        bg  = TIER_BG.get(tier, BG_CELL_EMPTY)
        fg  = TIER_FG.get(tier, TEXT_DIM)
        sym = TIER_SYMBOLS.get(tier, "")

        self._bg_color.rgba  = list(bg)
        self._bdr_color.rgba = list(BORDER_GLOW if tier != "none" else BORDER_LIGHT)
        self._label.text     = sym
        self._label.color    = list(fg)


# Main tracker App
class _TrackerApp:
    """Encapsulates the Kivy App subclass so it can hold a ctx reference."""

    def __init__(self, ctx: "MKWiiContext"):
        self.ctx   = ctx
        self.cells: Dict[Tuple[str, str], "LicenseCellWidget"] = {}
        self._status_dot:  Optional[object] = None
        self._status_text: Optional[object] = None
        self._app:         Optional[object] = None

    def run(self) -> None:
        """Build and run the Kivy App (blocking — call from a thread)."""
        (App, Clock, CoreImage, Color, Rectangle, Line,
         BoxLayout, FloatLayout, GridLayout, KvImage, Label, Widget, Config) = _import_kivy()

        Config.set("graphics", "width",      str(CELL_SIZE * (len(CUPS) + 1) + 40))
        Config.set("graphics", "height",     str(CELL_SIZE * (len(CCS)  + 1) + 140))
        Config.set("graphics", "resizable",  "0")
        Config.set("graphics", "borderless", "0")
        Config.set("kivy",     "window_icon", "")

        ctx = self.ctx

        # build the UI
        outer = BoxLayout(orientation="vertical",
                          padding=12, spacing=8)
        outer.canvas.before.add(Color(*BG_OUTER))
        _bg = Rectangle(size=outer.size, pos=outer.pos)
        outer.canvas.before.add(_bg)
        outer.bind(size=lambda i,v: setattr(_bg, "size", v),
                   pos =lambda i,v: setattr(_bg, "pos",  v))

        # TOP BAR
        top_bar = BoxLayout(orientation="horizontal",
                            size_hint_y=None, height=84,
                            padding=6, spacing=8)
        _paint_bg(top_bar, BG_CARD, BORDER_GLOW)

        # MKWii banner image (or fallback label)
        if IMG_MKWII.exists():
            try:
                banner = KvImage(source=str(IMG_MKWII),
                                 size_hint=(None, None), size=(72, 72),
                                 allow_stretch=True, keep_ratio=True)
            except Exception:
                banner = _make_label("MKWii", BG_CARD, TEXT_YELLOW, bold=True,
                                     size_hint=(None, 1), width=72)
        else:
            banner = _make_label("MKWii", BG_CARD, TEXT_YELLOW, bold=True,
                                 size_hint=(None, 1), width=72)
        top_bar.add_widget(banner)

        # Title + status
        info_col = BoxLayout(orientation="vertical", spacing=4)
        _paint_bg(info_col, BG_CARD)

        title_lbl = Label(
            text="Mario Kart Wii  •  AP Tracker",
            color=list(TEXT_YELLOW),
            font_size="13sp",
            bold=True,
            halign="left",
            valign="bottom",
            size_hint_y=0.55,
        )
        title_lbl.bind(size=title_lbl.setter("text_size"))
        info_col.add_widget(title_lbl)

        status_row = BoxLayout(orientation="horizontal", spacing=3,
                               size_hint_y=0.45)
        _paint_bg(status_row, BG_CARD)

        self._status_dot = Label(
            text="●", color=list(TEXT_ORANGE),
            font_size="10sp",
            size_hint=(None, 1), width=14,
        )
        self._status_text = Label(
            text="Waiting for Dolphin…",
            color=list(TEXT_DIM),
            font_size="9sp",
            halign="left", valign="middle",
        )
        self._status_text.bind(size=self._status_text.setter("text_size"))
        status_row.add_widget(self._status_dot)
        status_row.add_widget(self._status_text)
        info_col.add_widget(status_row)
        top_bar.add_widget(info_col)

        # AP logo (or fallback)
        if IMG_AP.exists():
            try:
                ap_img = KvImage(source=str(IMG_AP),
                                 size_hint=(None, None), size=(56, 56),
                                 allow_stretch=True, keep_ratio=True)
                top_bar.add_widget(ap_img)
            except Exception:
                top_bar.add_widget(_ap_fallback(Label))
        else:
            top_bar.add_widget(_ap_fallback(Label))

        outer.add_widget(top_bar)

        # GRID
        grid_outer = BoxLayout(orientation="vertical", padding=6, spacing=0)
        _paint_bg(grid_outer, BG_CARD, BORDER_GLOW)

        cols = len(CUPS) + 1
        grid = GridLayout(cols=cols,
                          spacing=2, padding=0,
                          size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        # Corner cell
        corner = _header_cell("Tracker", BG_OUTER, TEXT_DIM, font_size="9sp")
        grid.add_widget(corner)

        # Cup column headers
        for cup in CUPS:
            icon  = CUP_ICONS[cup]
            short = cup.replace(" Cup", "")
            hdr   = FloatLayout(size_hint=(None, None), size=(CELL_SIZE, CELL_SIZE))
            _paint_bg(hdr, BG_HEADER_ROW, BORDER_LIGHT)
            hdr.add_widget(Label(text=icon, font_size="18sp",
                                 color=list(TEXT_WHITE),
                                 pos_hint={"center_x": 0.5, "center_y": 0.65},
                                 size_hint=(1, None), height=CELL_SIZE))
            hdr.add_widget(Label(text=short, font_size="7sp",
                                 color=list(TEXT_DIM),
                                 pos_hint={"center_x": 0.5, "center_y": 0.18},
                                 size_hint=(1, None), height=CELL_SIZE))
            grid.add_widget(hdr)

        # CC rows + data cells
        for row_idx, cc in enumerate(CCS):
            bg_row = BG_ROW_ODD if row_idx % 2 == 0 else BG_ROW_EVEN

            cc_cell = _header_cell(cc, bg_row, TEXT_WHITE,
                                   font_size="9sp", bold=True)
            grid.add_widget(cc_cell)

            for cup in CUPS:
                cell = LicenseCellWidget(grid, row_idx, CUPS.index(cup))
                self.cells[(cup, cc)] = cell
                grid.add_widget(cell.widget)

        grid_outer.add_widget(grid)
        outer.add_widget(grid_outer)

        # Kivy App subclass
        tracker_self = self

        class TrackerApp(App):
            def build(self_app):
                self_app.title = "MKWii AP Tracker"
                return outer

            def on_start(self_app):
                Clock.schedule_interval(tracker_self._tick, 0.5)

        self._app = TrackerApp()
        self._app.run()

    def _tick(self, dt) -> None:
        """Called by Kivy Clock every 0.5 s — update connection status & cells."""
        try:
            connected = (getattr(self.ctx, "dolphin", None) and
                         self.ctx.dolphin.is_connected)

            if self._status_dot and self._status_text:
                if connected:
                    self._status_dot.color  = [0, 0.878, 0.376, 1]   # #00e060
                    self._status_text.text  = "Connected to Dolphin"
                    self._status_text.color = [0.502, 1, 0.690, 1]   # #80ffb0
                else:
                    self._status_dot.color  = list(TEXT_ORANGE)
                    self._status_text.text  = "Waiting for Dolphin…"
                    self._status_text.color = list(TEXT_DIM)

            completed = getattr(self.ctx, "completed_locations", {})
            for (cup, cc), cell in self.cells.items():
                tier = completed.get((cup, cc), "none")
                cell.set_tier(tier)
        except Exception:
            pass


# Small helpers
def _paint_bg(widget, bg, border=None):
    """Attach a background (and optional border) to any widget's canvas.before."""
    from kivy.graphics import Color, Rectangle, Line
    with widget.canvas.before:
        Color(*bg)
        rect = Rectangle(size=widget.size, pos=widget.pos)
        widget.bind(size=lambda i,v: setattr(rect,"size",v),
                    pos =lambda i,v: setattr(rect,"pos", v))
        if border:
            Color(*border)
            line = Line(rectangle=(widget.x, widget.y,
                                   widget.width, widget.height), width=1)
            widget.bind(
                size=lambda i,v,l=line,w=widget: setattr(
                    l, "rectangle", (w.x, w.y, v[0], v[1])),
                pos =lambda i,v,l=line,w=widget: setattr(
                    l, "rectangle", (v[0], v[1], w.width, w.height)),
            )


def _make_label(text, bg, fg, bold=False, **kwargs):
    from kivy.uix.label import Label
    lbl = Label(text=text, color=list(fg), bold=bold,
                halign="center", valign="middle", **kwargs)
    _paint_bg(lbl, bg)
    return lbl


def _header_cell(text, bg, fg, font_size="9sp", bold=False):
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.label       import Label
    cell = FloatLayout(size_hint=(None, None), size=(CELL_SIZE, CELL_SIZE))
    _paint_bg(cell, bg, BORDER_LIGHT)
    lbl = Label(text=text, color=list(fg),
                font_size=font_size, bold=bold,
                halign="center", valign="middle",
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                size_hint=(1, 1))
    lbl.bind(size=lbl.setter("text_size"))
    cell.add_widget(lbl)
    return cell


def _ap_fallback(Label):
    from kivy.uix.floatlayout import FloatLayout
    box = FloatLayout(size_hint=(None, None), size=(54, 34))
    _paint_bg(box, (0.118, 0.227, 0.541, 1), BORDER_GLOW)   # #1e3a8a
    box.add_widget(Label(text="AP", color=list(TEXT_YELLOW),
                         font_size="13sp", bold=True,
                         pos_hint={"center_x": 0.5, "center_y": 0.5},
                         size_hint=(1, 1)))
    return box


# Public API
class LocationTrackerWindow:
    """Drop-in replacement for the original tkinter LocationTrackerWindow."""

    def __init__(self, ctx: "MKWiiContext") -> None:
        self.ctx     = ctx
        self.running = False
        self._app    = _TrackerApp(ctx)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self) -> None:
        try:
            self._app.run()
        except Exception:
            pass
        finally:
            self.running = False


_tracker_instance: Optional[LocationTrackerWindow] = None


def launch_tracker(ctx: "MKWiiContext") -> None:
    """Launch (or reuse) the location tracker window."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = LocationTrackerWindow(ctx)
    _tracker_instance.start()