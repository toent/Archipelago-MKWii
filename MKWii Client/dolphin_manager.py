"""
Dolphin Emulator lifecycle manager for Mario Kart Wii AP Client.

Handles ISO selection, Dolphin process launch, savestate operations,
and save backup reminders. Savestate loading works by copying a bundled
clean state file into Dolphin's slot directory, then sending an F-key
via pywinauto to trigger the load.
"""
import json
import configparser
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Optional
from pynput.keyboard import Key, Controller, KeyCode
from gecko_manager import inject_gecko_codes

logger = logging.getLogger("MKWii.Dolphin")

GAME_ID = "RMCP01"
CONFIG_FILENAME = "mkwii_ap_config.json"
# BUNDLED_SAVESTATE = "Saves/Savestate/MKWii_AP_Savestate.sav"
BUNDLED_EMPTY_SAVE = "Saves/Empty Save/rksys.dat"
# SAVESTATE_SLOT = 1

KEY_MAP = {
    "shift": Key.shift,
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "return": Key.enter,
    "escape": Key.esc,
    "tab": Key.tab,
    "f1": Key.f1,  "f2": Key.f2,  "f3": Key.f3,  "f4": Key.f4,
    "f5": Key.f5,  "f6": Key.f6,  "f7": Key.f7,  "f8": Key.f8,
    "f9": Key.f9,  "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
    "subtract": KeyCode.from_vk(0x6D),
    "add": KeyCode.from_vk(0x6B),
    "numpad1": KeyCode.from_vk(0x61), "numpad2": KeyCode.from_vk(0x62),
    "numpad3": KeyCode.from_vk(0x63), "numpad4": KeyCode.from_vk(0x64),
}

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
        self.keyboard = Controller()
        self.hotkeys_path = os.path.join(self.get_dolphin_user_dir(), "Config", "Hotkeys.ini")

    # Dolphin hotkey binding handling
    def parse_binding(self, raw: str) -> list:
        """Parse a Dolphin binding string into a list of pynput keys."""
        raw = raw.strip().replace("`", "")
        
        if raw.startswith("@(") and raw.endswith(")"):
            parts = raw[2:-1].split("+")
        else:
            parts = [raw]
        
        keys = []
        for part in parts:
            part = part.strip().lower()
            if part in KEY_MAP:
                keys.append(KEY_MAP[part])
            elif len(part) == 1:
                keys.append(KeyCode.from_char(part))
            else:
                raise ValueError(f"Unknown key: '{part}'")
        
        return keys

    def get_slot1_bindings(self) -> tuple[list, list]:
        """Read Hotkeys.ini and return (load_keys, save_keys) for slot 1."""
        config = configparser.ConfigParser()
        config.read(self.hotkeys_path)

        section = config["Hotkeys"]
        
        load_raw = section.get("load state/load state slot 1")
        save_raw = section.get("save state/save state slot 1")

        if not load_raw:
            raise ValueError("Load State Slot 1 binding not found in Hotkeys.ini")
        if not save_raw:
            raise ValueError("Save State Slot 1 binding not found in Hotkeys.ini")

        return self.parse_binding(load_raw), self.parse_binding(save_raw)

    def press_combo(self, keys: list, delay: float = 0.05):
        """Press a key combination, holding modifiers while pressing the final key."""
        modifiers = keys[:-1]
        final = keys[-1]

        for mod in modifiers:
            self.keyboard.press(mod)
            time.sleep(delay)

        self.keyboard.press(final)
        time.sleep(delay)
        self.keyboard.release(final)

        for mod in reversed(modifiers):
            self.keyboard.release(mod)
            time.sleep(delay)

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

    # def get_savestate_slot_path(self, slot: int = SAVESTATE_SLOT) -> Optional[str]:
    #     user_dir = self.get_dolphin_user_dir()
    #     if not user_dir:
    #         return ""
    #     return os.path.join(user_dir, "StateSaves", f"{GAME_ID}.s{slot:02d}")

    # def get_bundled_savestate_path(self) -> str:
    #     return os.path.join(self._script_dir, BUNDLED_SAVESTATE)

    # @property
    # def has_bundled_savestate(self) -> bool:
    #     return os.path.isfile(self.get_bundled_savestate_path())

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

    # Savestate operations

    # def load_state(self, slot: int = SAVESTATE_SLOT) -> bool:
    #     """Copy the bundled savestate into Dolphin's slot and trigger load via F-key."""
    #     bundled = self.get_bundled_savestate_path()
    #     ss_path = self.get_savestate_slot_path(slot)

    #     if not os.path.isfile(bundled):
    #         logger.error(f"Bundled savestate not found: {bundled}")
    #         return False
    #     if not ss_path:
    #         logger.error("Could not determine savestate slot path")
    #         return False

    #     os.makedirs(os.path.dirname(ss_path), exist_ok=True)

    #     try:
    #         shutil.copy2(bundled, ss_path)
    #     except Exception as e:
    #         logger.error(f"Failed to copy savestate: {e}")
    #         return False

    #     if not self.focus_game_window():
    #         logger.warning("Could not focus Dolphin window, sending F-key anyway")

    #     try:
    #         load_keys, _ = self.get_slot1_bindings()
    #         self.press_combo(load_keys)
    #     except Exception as e:
    #         logger.error(f"Failed to send slot 1 key combo: {self.get_slot1_bindings()[0]} - {e}")
    #         return False

    #     time.sleep(0.5)
    #     logger.info(f"Loaded savestate (slot {slot})")
    #     return True

    # Backup reminder

    def show_backup_reminder(self) -> bool:
        """Prompt user about save data backup. Returns False if user cancels."""
        if not self.config.get("remind_backup", True):
            inject_gecko_codes(self.get_dolphin_user_dir())
            self.replace_save_with_empty()
            return True

        print("\n  SAVE DATA WARNING")
        print("  " + "-" * 40)
        print("  Loading the AP will overwrite your save with an empty one.")
        print("  Additionally the included savestate will cause MKWii")
        print("  to auto-save over your existing save & savestate data.")
        user_dir = self.get_dolphin_user_dir()
        if user_dir:
            print(f"\n  Save location: {user_dir}")
            print("    Wii/title/00010004/524d4350/data/rksys.dat")

        response = input("\n  Have you backed up your save? (y/n): ").strip().lower()
        if response != "y":
            if input("  Continue anyway? (y/n): ").strip().lower() != "y":
                return False

        remind = input("  Show this reminder next time? (y/n): ").strip().lower()
        self.config["remind_backup"] = remind == "y"
        self._save_config()
        inject_gecko_codes(self.get_dolphin_user_dir())
        self.replace_save_with_empty()
        return True
    
    def show_main_menu_reminder(self) -> bool:
        """Prompt user to return to main menu. Returns False if user cancels."""
        print("  Please navigate to the MKWii main menu before starting AP.")
        print("  (the screen where you can select Single Player, Multiplayer, etc.)")
        print("  This ensures the save data is properly loaded and prevents")
        print("  potential issues with item tracking and progression.")

        response = input("\n  Are you at the main menu? (y/n): ").strip().lower()
        if response != "y":
            if input("  Continue anyway? (y/n): ").strip().lower() != "y":
                return False
        return True
    
    # find existing save, then replace with empty save
    def replace_save_with_empty(self) -> bool:
        user_dir = self.get_dolphin_user_dir()
        if not user_dir:
            logger.error("Could not determine Dolphin user directory for save replacement")
            return False

        save_path = os.path.join(user_dir, "wii", "title", "00010004", "524d4350", "data", "rksys.dat")
        empty_save = os.path.join(self._script_dir, BUNDLED_EMPTY_SAVE)

        if not os.path.isfile(empty_save):
            logger.error(f"Bundled empty save not found: {empty_save}")
            return False

        if os.path.isfile(save_path):
            backup_path = save_path + ".backup"
            try:
                shutil.copy2(save_path, backup_path)
                logger.info(f"Backed up existing save to: {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to backup existing save: {e}")

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

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

        iso_path = self.get_iso_path()
        if not iso_path:
            print("  No ISO selected.")
            return result
        result["iso_path"] = iso_path
        print(f"  ISO: {os.path.basename(iso_path)}")

        # if self.has_bundled_savestate:
        #     size = os.path.getsize(self.get_bundled_savestate_path())
        #     print(f"  Savestate: {BUNDLED_SAVESTATE} ({size / 1024 / 1024:.1f} MB)")
        # else:
        #     print(f"  Savestate not found: {BUNDLED_SAVESTATE}")
        #     print(f"    Expected at: {self.get_bundled_savestate_path()}")
        #     return result

        if not self.show_backup_reminder():
            return result

        result["ready"] = True
        print("\n  Setup complete!\n")
        return result
