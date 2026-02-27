"""
Dolphin Emulator lifecycle manager for Mario Kart Wii AP Client.

Handles ISO selection, Dolphin process launch, savestate operations,
and save backup reminders. Savestate loading works by copying a bundled
clean state file into Dolphin's slot directory, then sending an F-key
via pywinauto to trigger the load.
"""
import json
import logging
import os
import shutil
import subprocess
import sys
from typing import Optional

logger = logging.getLogger("MKWii.Dolphin")

GAME_ID = "RMCP01"
CONFIG_FILENAME = "mkwii_ap_config.json"
# BUNDLED_SAVESTATE = "Saves/Savestate/MKWii_AP_Savestate.sav"
BUNDLED_EMPTY_SAVE = "Saves/Empty Save/rksys.dat"
# SAVESTATE_SLOT = 1


class DolphinManager:
    """Manages Dolphin process lifecycle, configuration, and savestate operations."""
    
    def __init__(self) -> None:

        if getattr(sys, 'frozen', False):
        # Running as PyInstaller exe - use the folder containing the exe
            self._script_dir = os.path.dirname(sys.executable)
        else:
        # Running as normal Python script
            self._script_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.config_path = os.path.join(self._script_dir, CONFIG_FILENAME)
        self.config = self._load_config()
        self._dolphin_process: Optional[subprocess.Popen] = None
        self._dolphin_user_dir: Optional[str] = None
        self._game_app = None
        self._game_window = None

    # Config file handling
    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self) -> None:
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save config: {e}")

    # Path discovery

    def get_dolphin_user_dir(self) -> str:
        if self._dolphin_user_dir:
            return self._dolphin_user_dir

        docs = os.path.join(os.path.expanduser("~"), "Documents", "Dolphin Emulator")
        if os.path.isdir(docs):
            self._dolphin_user_dir = docs
            return docs

        roaming = os.path.join(os.environ.get("APPDATA", ""), "Dolphin Emulator")
        if os.path.isdir(roaming):
            self._dolphin_user_dir = roaming
            return roaming

        custom = self.config.get("dolphin_user_dir")
        if custom and os.path.isdir(custom):
            self._dolphin_user_dir = custom
            return custom
        return ""

    # Save file picker
    def get_save_path(self) -> Optional[str]:
        saved = self.config.get("save_path")
        if saved and os.path.isfile(saved):
            return saved

        path = self._pick_save_dialog()
        if path and os.path.isfile(path):
            self.config["save_path"] = path
            self._save_config()
            return path
        return ""

    def _pick_save_dialog(self) -> Optional[str]:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Select Mario Kart Wii save file (rksys.dat)",
                filetypes=[
                    ("MKWii save file", "rksys.dat"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()
            return path or ""
        except Exception as e:
            logger.error(f"File dialog failed: {e}")
            path = input("Enter path to rksys.dat: ").strip().strip('"')
            return path or ""

    # ISO picker
    def get_iso_path(self) -> Optional[str]:
        saved = self.config.get("iso_path")
        if saved and os.path.isfile(saved):
            return saved

        path = self._pick_iso_dialog()
        if path and os.path.isfile(path):
            self.config["iso_path"] = path
            self._save_config()
            return path
        return ""

    def _pick_iso_dialog(self) -> Optional[str]:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Select Mario Kart Wii PAL ISO",
                filetypes=[
                    ("Wii disc images", "*.iso *.wbfs *.gcz *.rvz *.wia *.ciso"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()
            return path or ""
        except Exception as e:
            logger.error(f"File dialog failed: {e}")
            path = input("Enter path to MKWii PAL ISO: ").strip().strip('"')
            return path or ""

    # Dolphin launch
    def find_dolphin_exe(self) -> Optional[str]:
        saved = self.config.get("dolphin_exe")
        if saved and os.path.isfile(saved):
            return saved

        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Dolphin", "Dolphin.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Dolphin", "Dolphin.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Dolphin", "Dolphin.exe"),
            os.path.join(os.path.expanduser("~"), "Desktop", "Dolphin-x64", "Dolphin.exe"),
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                self.config["dolphin_exe"] = candidate
                self._save_config()
                return candidate

        try:
            result = subprocess.run(["where", "Dolphin.exe"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                path = result.stdout.strip().split("\n")[0]
                if os.path.isfile(path):
                    self.config["dolphin_exe"] = path
                    self._save_config()
                    return path
        except Exception:
            pass
        return None

    def pick_dolphin_exe(self) -> Optional[str]:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Select Dolphin.exe",
                filetypes=[("Dolphin Emulator", "Dolphin.exe"), ("All executables", "*.exe")],
            )
            root.destroy()
            if path and os.path.isfile(path):
                self.config["dolphin_exe"] = path
                self._save_config()
                return path
        except Exception as e:
            logger.error(f"File dialog failed: {e}")
            path = input("Enter path to Dolphin.exe: ").strip().strip('"')
            if path and os.path.isfile(path):
                self.config["dolphin_exe"] = path
                self._save_config()
                return path
        return None

    def launch_dolphin(self, iso_path: str) -> bool:
        dolphin_exe = self.find_dolphin_exe()
        if not dolphin_exe:
            logger.info("Dolphin.exe not found, please select it...")
            dolphin_exe = self.pick_dolphin_exe()
        if not dolphin_exe:
            logger.error("Could not find Dolphin.exe")
            return False

        try:
            self._dolphin_process = subprocess.Popen(
                [dolphin_exe, "-e", iso_path, "-b"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            logger.info(f"Launched Dolphin (PID {self._dolphin_process.pid})")
            return True
        except Exception as e:
            logger.error(f"Failed to launch Dolphin: {e}")
            return False

    def is_dolphin_running(self) -> bool:
        return self._dolphin_process is not None and self._dolphin_process.poll() is None

    # Window focus (pywinauto)

    def _find_game_window(self) -> bool:
        try:
            from pywinauto import Application, findwindows

            handles = findwindows.find_windows(title_re=r"(?i)Dolphin.*RMCP01", visible_only=True)
            if not handles:
                return False
            self._game_app = Application(backend="uia").connect(handle=handles[0])
            self._game_window = self._game_app.window(handle=handles[0])
            return True
        except Exception:
            self._game_app = None
            self._game_window = None
            return False

    def focus_game_window(self) -> bool:
        if not self._game_window:
            if not self._find_game_window():
                return False
        try:
            self._game_window.set_focus()
            return True
        except Exception:
            self._game_window = None
            if self._find_game_window():
                try:
                    self._game_window.set_focus()
                    return True
                except Exception:
                    pass
            return False

    # Backup reminder

    def show_backup_reminder(self) -> bool:
        """Prompt user about save data backup. Returns False if user cancels."""
        if not self.config.get("remind_backup", True):
            self.replace_save_with_empty()
            return True

        print("\n  SAVE DATA WARNING")
        print("  " + "-" * 40)
        print("  Loading the AP will overwrite your save with an empty one.")
        print("  Additionally the included save will cause MKWii")
        print("  to auto-save over your existing save data.")
        save_path = self.config.get("save_path")
        if save_path:
            print(f"\n  Save location: {save_path}")

        response = input("\n  Have you backed up your save? (y/n): ").strip().lower()
        if response != "y":
            if input("  Continue anyway? (y/n): ").strip().lower() != "y":
                return False

        remind = input("  Show this reminder next time? (y/n): ").strip().lower()
        self.config["remind_backup"] = remind == "y"
        self._save_config()
        self.replace_save_with_empty()
        return True
    
    def show_main_menu_reminder(self) -> bool:
        """Prompt user to return to main menu. Returns False if user cancels."""
        print("  Please navigate to the MKWii license select screen before starting AP.")
        print("  (the screen where you can select any of the 4 licenses.)")
        print("  This ensures the save data is properly loaded and prevents")
        print("  potential issues with item tracking and progression.")
        print("  NOTE: The AP currently only works with the top left license slot.")

        response = input("\n  Are you at the license select screen? (y/n): ").strip().lower()
        if response != "y":
            if input("  Continue anyway? (y/n): ").strip().lower() != "y":
                return False
        return True

    def show_dolphin_auto_launch_selection(self) -> bool:
        """Ask user if they want Dolphin to auto-launch with the ISO. Returns True if yes."""
        print("\n  Dolphin Auto-Launch")
        print("  " + "-" * 40)
        print("  Would you like the AP client to automatically launch Dolphin with the selected ISO when you start the client?")
        print("  This can be changed later in the config file.")

        response = input("\n  Enable Dolphin auto-launch? (y/n): ").strip().lower()
        enable = response == "y"
        self.config["dolphin_auto_launch"] = enable
        self._save_config()
        return enable
    
    # find existing save, then replace with empty save
    def replace_save_with_empty(self) -> bool:
        save_path = self.get_save_path()
        if not save_path:
            logger.error("No save file selected")
            return False

        empty_save = os.path.join(self._script_dir, BUNDLED_EMPTY_SAVE)
        if not os.path.isfile(empty_save):
            logger.error(f"Bundled empty save not found: {empty_save}")
            return False

        backup_path = save_path + ".backup"
        try:
            shutil.copy2(save_path, backup_path)
            logger.info(f"Backed up existing save to: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to backup existing save: {e}")

        try:
            shutil.copy2(empty_save, save_path)
            logger.info("Replaced existing save with empty save")
            return True
        except Exception as e:
            logger.error(f"Failed to replace save with empty: {e}")
            return False

    # Setup wizard
    def run_setup(self) -> dict:
        """Interactive first-run setup. Returns {"iso_path": str, "ready": bool}."""
        result = {"iso_path": None, "ready": False}

        print("\n" + "=" * 60)
        print("  Mario Kart Wii - Archipelago Setup")
        print("=" * 60 + "\n")

        if self.config.get("dolphin_auto_launch", True):
            iso_path = self.get_iso_path()
            if not iso_path:
                print("  No ISO selected.")
                return result
            result["iso_path"] = iso_path
            print(f"  ISO: {os.path.basename(iso_path)}")

        result["ready"] = True
        print("\n  Setup complete!\n")
        return result