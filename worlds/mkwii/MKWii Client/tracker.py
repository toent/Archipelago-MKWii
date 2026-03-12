"""
tracker.py — launches tracker_process.py as a standalone subprocess.

Passes AP credentials (server address, slot name, password) as command-line
arguments so the tracker process connects to the AP server independently.
No shared state file; the tracker manages its own AP connection.
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mkwii_client import MKWiiContext

_frozen = getattr(sys, "frozen", False)

if _frozen:
    _HERE = Path(sys.executable).parent
    # When compiled, the tracker runs as its own exe next to the client exe
    _TRACKER_EXE    = _HERE / "mkwii tracker.exe"
    _PROCESS_SCRIPT = None
else:
    _HERE           = Path(__file__).parent
    _TRACKER_EXE    = None
    _PROCESS_SCRIPT = _HERE / "tracker_process.py"

_tracker_proc: Optional[subprocess.Popen] = None


def launch_tracker(ctx: "MKWiiContext") -> None:
    """Launch (or reuse) the tracker subprocess, passing AP credentials as args.

    Respects the tracker_auto_launch setting in mkwii_ap_config.json.
    If the setting is False the tracker is not opened automatically;
    the user can still launch tracker_process.py / mkwii tracker.exe manually.
    """
    global _tracker_proc

    mgr = getattr(ctx, "dolphin_mgr", None)
    if mgr is not None:
        if not mgr.config.get("tracker_auto_launch", True):
            return

    if _tracker_proc is not None and _tracker_proc.poll() is None:
        return

    server   = ctx.server_address or ""
    slot     = ctx.username        or ""
    password = ctx.password        or ""

    if _frozen:
        if not _TRACKER_EXE.exists():
            print(f"[Tracker] ERROR: mkwii tracker.exe not found at {_TRACKER_EXE}")
            return
        cmd = [str(_TRACKER_EXE), server, slot, password]
    else:
        if not _PROCESS_SCRIPT.exists():
            print(f"[Tracker] ERROR: tracker_process.py not found at {_PROCESS_SCRIPT}")
            return
        cmd = [sys.executable, str(_PROCESS_SCRIPT), server, slot, password]

    try:
        _tracker_proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32" else 0,
        )
        print(f"[Tracker] Launched tracker process (pid {_tracker_proc.pid})")
    except Exception as e:
        print(f"[Tracker] Failed to launch tracker process: {e}")