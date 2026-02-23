# [Archipelago](https://archipelago.gg) ![Discord Shield](https://discordapp.com/api/guilds/731205301247803413/widget.png?style=shield) | [Install](https://github.com/ArchipelagoMW/Archipelago/releases)

Archipelago provides a generic framework for developing multiworld capability for game randomizers. In all cases,
presently, Archipelago is also the randomizer itself.

## MKWii
### Things you will need:
* An __unmodified PAL__ Mario Kart Wii ROM
* [Python 3.13.12](https://www.python.org/downloads/release/python-31312/) (Other Python versions might work, but do so at your own risk)
* [Dolphin 2512](https://dolphin-emu.org/download/release/2512/) (Dolphin 5 or higher is the minimum)
* [Latest MKWii Client and APWorld Release](https://github.com/toent/Archipelago-MKWii/releases/latest)

### Getting Set up:
1. Install the requirements marked above according to their installers.
2. Make sure that in Dolphin `Settings > Advanced > Enable Memory Size Override` is unchecked/disabled.
3. If you have an existing Mario Kart Wii Savefile or Savestates that you care about, __make sure to back them up__.
4. Run `/MKWii Client/MKWii_Client.bat` (or `/MKWii Client/mkwii_client.py` in a CLI, if you're on linux)
5. Install required packages (the client will do this automatically after prompting you).
6. The client will ask for your ROM and your Dolphin make sure to assign them correctly.
7. Follow other instructions posed by the client and connect to the archipelago.
8. The client includes a text client and tracker window, they will open automatically.

### Good to know:
* The client might not connect to dolphin properly sometimes eventhough some text says it is, use `/status` in the text client to check for connection or check the tracker window.
* When generating with the `mkwii.apworld` make sure to keep `include_race_checks` and `enable_mid_race_memory_features` set to __False__ in your YAML, the options are just there for future development, but have no place yet in the client and __will not be unlockable__.
* Do __NOT__ use the speedup feature included in Dolphin as it has been known to skip over checks.
* In the current version trap or filler items do not do anything yet. There is plans for them for later.

## Arcipelago History

Archipelago is built upon a strong legacy of brilliant hobbyists. We want to honor that legacy by showing it here.
The repositories which Archipelago is built upon, inspired by, or otherwise owes its gratitude to are:

* [bonta0's MultiWorld](https://github.com/Bonta0/ALttPEntranceRandomizer/tree/multiworld_31)
* [AmazingAmpharos' Entrance Randomizer](https://github.com/AmazingAmpharos/ALttPEntranceRandomizer)
* [VT Web Randomizer](https://github.com/sporchia/alttp_vt_randomizer)
* [Dessyreqt's alttprandomizer](https://github.com/Dessyreqt/alttprandomizer)
* [Zarby89's](https://github.com/Ijwu/Enemizer/commits?author=Zarby89)
  and [sosuke3's](https://github.com/Ijwu/Enemizer/commits?author=sosuke3) contributions to Enemizer, which make up the
  vast majority of Enemizer contributions.

We recognize that there is a strong community of incredibly smart people that have come before us and helped pave the
path. Just because one person's name may be in a repository title does not mean that only one person made that project
happen. We can't hope to perfectly cover every single contribution that lead up to Archipelago, but we hope to honor
them fairly.

## Related Repositories

This project makes use of multiple other projects. We wouldn't be here without these other repositories and the
contributions of their developers, past and present.

* [z3randomizer](https://github.com/ArchipelagoMW/z3randomizer)
* [Enemizer](https://github.com/Ijwu/Enemizer)
* [Ocarina of Time Randomizer](https://github.com/TestRunnerSRL/OoT-Randomizer)

