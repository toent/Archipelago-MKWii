"""
tracker.py — launches tracker_process.py as a standalone subprocess.

Passes AP credentials (server address, slot name, password) as command-line
arguments so the tracker process connects to the AP server independently.
No shared state file; the tracker manages its own AP connection.
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mkwii_client import MKWiiContext

if getattr(sys, "frozen", False):
    _HERE = Path(sys.executable).parent
else:
    _HERE = Path(__file__).parent

_PROCESS_SCRIPT = _HERE / "tracker_process.py"

_tracker_proc: Optional[subprocess.Popen] = None


def launch_tracker(ctx: "MKWiiContext") -> None:
    """Launch (or reuse) the tracker subprocess, passing AP credentials as args.

    Respects the tracker_auto_launch setting in mkwii_ap_config.json.
    If the setting is False the tracker is not opened automatically;
    the user can still launch tracker_process.py manually at any time.
    """
    global _tracker_proc

    # Check config — default to True so existing installs keep working
    mgr = getattr(ctx, "dolphin_mgr", None)
    if mgr is not None:
        if not mgr.config.get("tracker_auto_launch", True):
            return

    # If already running, do nothing
    if _tracker_proc is not None and _tracker_proc.poll() is None:
        return

    if not _PROCESS_SCRIPT.exists():
        print(f"[Tracker] ERROR: tracker_process.py not found at {_PROCESS_SCRIPT}")
        return

    server   = ctx.server_address or ""
    slot     = ctx.username        or ""
    password = ctx.password        or ""

    try:
        _tracker_proc = subprocess.Popen(
            [
                sys.executable,
                str(_PROCESS_SCRIPT),
                server,
                slot,
                password,
            ],
            creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32" else 0,
        )
        print(f"[Tracker] Launched tracker process (pid {_tracker_proc.pid})")
    except Exception as e:
        print(f"[Tracker] Failed to launch tracker process: {e}")
