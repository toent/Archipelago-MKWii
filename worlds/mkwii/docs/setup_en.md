# Setup Guide (English)

## Things you will need:
* An **unmodified PAL** Mario Kart Wii ROM
* [Dolphin 2512+](https://dolphin-emu.org/download/release/2512/) (Dolphin 5 or higher is the minimum)
* [Latest MKWii Client and APWorld Release](https://github.com/toent/Archipelago-MKWii/releases/latest)
* LINUX ONLY [Python 3.13.12](https://www.python.org/downloads/release/python-31312/) and [Git](https://git-scm.com/install/) are needed

## Getting Set up:
1. Install the requirements marked above according to their installers.
2. Make sure that in Dolphin `Config > Advanced > Enable Memory Size Override` is **unchecked/disabled**.
3. If you have an existing Mario Kart Wii Savefile that you care about, **make sure to back it up**.
4. **Windows:** Download the latest client and run `mkwii_client.exe`.
5. **Linux:** Follow the instructions to [run Archipelago from source.](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/running%20from%20source.md)
6. **Linux:** Download the source code that goes along with the latest client and run `MKWii Client/mkwii_client.py`.
7. **Linux:** Install required packages (the client will do this automatically after prompting you).
8. The client will ask for your savefile, choose the one you get by going to `Dolphin > MKWii > Right Click > Open Wii Save Folder`, if there is no `rksys.dat` savefile, just start your game once, and make a license.
9. Make sure the client is at the license selection question before opening your emulation instance.
10. If you opt for **Auto tracker start**, the tracker will be opened once you connect to archipelago. You can still close it seperately and open it seperately as well.
11. If you opt for **Manual track start**, the tracker wont open and you need to run `mkwii tracker.exe` or `tracker_process.py` and connect to the archipelago.
12. Follow other instructions posed by the client and connect to the Archipelago.
13. The client includes a text client and tracker window, they will open automatically.

## Good to know (READ THIS):
* The client might not connect to dolphin properly sometimes eventhough some text says it is, use `/status` in the client to check for connection or check the tracker window. To fix this, just restart the client and try again or try `/hook` in the client.
* When generating with the `mkwii.apworld` make sure to keep `enable_traps` set to **False** in your YAML, the options are just there for future development, but have no place yet in the client and **will not be unlockable**.
* Do **NOT** use the speedup feature included in Dolphin as it has been known to skip over checks.
* If you get any directory errors regarding saves not loading, add `"dolphin_user_dir":"Y:/our/Filepath/Dolphin Emulator"` as the next entry in the `mkwii_ap_config.json`.
    * You can easily find your Dolphin Userdata by opening dolphin right-clicking a game and clicking `Open Wii Save Folder`, and then navigate back until you are in the `Dolphin Emulator` folder (this is the directory the client will need).
* Individual race checks **can** be completed through VS-Race as well.
* For **Linux** make sure to use the use the **flatpak** version of Dolphin, other versions will **not** work.
