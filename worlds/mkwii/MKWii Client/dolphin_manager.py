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
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
import Utils

from reporting import ReportHandler

logger = logging.getLogger("MKWii.Dolphin")

GAME_ID_PAL = "RMCP01"
GAME_ID_NTSC = "RMCE01"
game_id = GAME_ID_PAL  # Default to PAL, can be changed by set_region() in dme_helpers.py
CONFIG_FILENAME = "mkwii_ap_config.json"
BUNDLED_EMPTY_SAVE = "Saves/Empty Save/rksys.dat"


class DolphinManager:
    """Manages Dolphin process lifecycle, configuration, and savestate operations."""
    
    def __init__(self) -> None:

        if getattr(sys, 'frozen', False):
        # Running as PyInstaller exe - use the folder containing the exe
            self._script_dir = os.path.dirname(sys.executable)
        else:
        # Running as normal Python script
            self._script_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.reporter = ReportHandler(mgr=self, logger=logger)
        self.config_path = os.path.join(self._script_dir, CONFIG_FILENAME)
        self.config = self._load_config()
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
            self.reporter.report(type="WARNING", msg=f"Could not save config: {e}")

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
            path = Utils.open_filename(
                title="Select Mario Kart Wii save file (rksys.dat)",
                filetypes=[
                    ("MKWii save file", "rksys.dat"),
                    ("All files", "*.*"),
                ],
            )
            return path or ""
        except Exception as e:
            self.reporter.report(type="ERROR", msg=f"File dialog failed: {e}")
            path = input("Enter path to rksys.dat: ").strip().strip('"')
            return path or ""

    # Window focus (pywinauto)

    def _find_game_window(self) -> bool:
        try:
            from pywinauto import Application, findwindows

            handles = findwindows.find_windows(title_re=rf"(?i)Dolphin.*{game_id}", visible_only=True)
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
                sys.exit(0)
                return False
        return True

    # find existing save, then replace with empty save
    def replace_save_with_empty(self) -> bool:
        save_path = self.get_save_path()
        if not save_path:
            self.reporter.report(type="ERROR", msg="No save file selected")
            return False

        empty_save = os.path.join(self._script_dir, BUNDLED_EMPTY_SAVE)
        if not os.path.isfile(empty_save):
            self.reporter.report(type="ERROR", msg=f"Bundled empty save not found: {empty_save}")
            return False

        backup_path = save_path + ".backup"
        try:
            shutil.copy2(save_path, backup_path)
            self.reporter.report(type="INFO", msg=f"Backed up existing save to: {backup_path}")
        except Exception as e:
            self.reporter.report(type="WARNING", msg=f"Failed to backup existing save: {e}")

        try:
            shutil.copy2(empty_save, save_path)
            self.reporter.report(type="INFO", msg="Replaced existing save with empty save")
            return True
        except Exception as e:
            self.reporter.report(type="ERROR", msg=f"Failed to replace save with empty: {e}")
            return False

    def show_tracker_auto_launch_selection(self) -> bool:
        """Ask user if the AP tracker should auto-launch when connected. Returns True if yes."""
        print("\n  AP Tracker Auto-Launch")
        print("  " + "-" * 40)
        print("  Would you like the AP tracker window to automatically open when")
        print("  you connect to the Archipelago server?")
        print("  This can be changed later in the config file (tracker_auto_launch).")

        response = input("\n  Enable tracker auto-launch? (y/n): ").strip().lower()
        enable = response == "y"
        self.config["tracker_auto_launch"] = enable
        self._save_config()
        return enable

    # Setup wizard
    def run_setup(self) -> dict:
        """Interactive first-run setup. Returns {"ready": bool}."""
        result = {"ready": False}

        print("\n" + "=" * 60)
        print("  Mario Kart Wii - Archipelago Setup")
        print("=" * 60 + "\n")

        result["ready"] = True
        print("\n  Setup complete!\n")
        return result