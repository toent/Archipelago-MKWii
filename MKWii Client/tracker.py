"""
Location tracker window for Mario Kart Wii AP Client.

Displays a grid of cup/CC completions with live updates from Dolphin memory.
Runs in a separate thread to avoid blocking the async event loop.
"""
import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from mkwii_client import MKWiiContext

TIER_COLORS: Dict[str, str] = {
    "none": "gray",
    "3rd_place": "#CD7F32",
    "2nd_place": "#C0C0C0",
    "1st_place": "#FFD700",
    "1_star": "#00FF00",
    "2_star": "#00FFFF",
    "3_star": "#FF00FF",
}

TIER_SYMBOLS: Dict[str, str] = {
    "none": "-",
    "3rd_place": "🥉 3rd",
    "2nd_place": "🥈 2nd",
    "1st_place": "🥇 1st",
    "1_star": "⭐ 1-Star",
    "2_star": "⭐⭐ 2-Star",
    "3_star": "⭐⭐⭐ 3-Star",
}

CUPS = [
    "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
    "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup",
]

CCS = ["50cc", "100cc", "150cc", "Mirror"]


class LocationTrackerWindow:
    """Tkinter window showing cup completion progress."""

    def __init__(self, ctx: "MKWiiContext") -> None:
        self.ctx = ctx
        self.root: Optional[tk.Tk] = None
        self.labels: Dict[Tuple[str, str], tk.Label] = {}
        self.status_label: Optional[tk.Label] = None
        self.running: bool = False

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        thread = threading.Thread(target=self._run_window, daemon=True)
        thread.start()

    def _run_window(self) -> None:
        self.root = tk.Tk()
        self.root.title("MKWii AP Tracker")
        self.root.geometry("820x550")

        title = tk.Label(self.root, text="Mario Kart Wii - AP Location Tracker",
                         font=("Arial", 16, "bold"))
        title.pack(pady=5)

        self.status_label = tk.Label(self.root, text="Waiting for Dolphin...",
                                     font=("Arial", 10), fg="orange")
        self.status_label.pack(pady=2)

        canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Header row
        tk.Label(frame, text="Cup", font=("Arial", 10, "bold"),
                 width=15, anchor="w").grid(row=0, column=0, padx=5, pady=5)
        for col, cc in enumerate(CCS):
            tk.Label(frame, text=cc, font=("Arial", 10, "bold"),
                     width=12).grid(row=0, column=col + 1, padx=5, pady=5)

        # Cup rows
        for row, cup in enumerate(CUPS):
            tk.Label(frame, text=cup, font=("Arial", 9),
                     width=15, anchor="w").grid(row=row + 1, column=0, padx=5, pady=2)
            for col, cc in enumerate(CCS):
                label = tk.Label(frame, text="-", font=("Arial", 9), width=12, fg="gray")
                label.grid(row=row + 1, column=col + 1, padx=5, pady=2)
                self.labels[(cup, cc)] = label

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._schedule_update()

        try:
            self.root.mainloop()
        except Exception:
            pass
        finally:
            self.running = False

    def _schedule_update(self) -> None:
        if not self.root or not self.running:
            return

        try:
            connected = self.ctx.dolphin and self.ctx.dolphin.is_connected
            self.status_label.config(
                text="Connected to Dolphin" if connected else "Waiting for Dolphin...",
                fg="green" if connected else "orange",
            )

            for (cup, cc), label in self.labels.items():
                tier = self.ctx.completed_locations.get((cup, cc), "none")
                label.config(
                    text=TIER_SYMBOLS.get(tier, "-"),
                    fg=TIER_COLORS.get(tier, "gray"),
                )

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
