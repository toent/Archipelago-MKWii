"""
Gecko code manager for Mario Kart Wii AP Client.

Ensures required Gecko codes are defined and enabled in Dolphin's
per-game INI before launch. Non-destructive: only adds what is missing,
never removes or rewrites existing content.
"""
import logging
import os

logger = logging.getLogger("MKWii.Gecko")

GAME_ID = "RMCP01"

GECKO_CODES: dict[str, list[str]] = {
    "Prevent Unlock Screen [vabold]": [
        "06854FA4 00000008",
        "3860FFFF 4E800020",
    ]
}


def _base_name(name: str) -> str:
    """Strip author tag from a Gecko code name for matching.
    e.g. 'Prevent Unlock Screen [vabold]' -> 'Prevent Unlock Screen'
    """
    return name.split("[")[0].strip()


def _parse_ini_sections(raw_lines: list[str]) -> list[tuple[str, list[str]]]:
    """Parse raw INI lines into a list of (section_header, body_lines) tuples.
    Lines before any section header are grouped under '__preamble__'.
    """
    sections: list[tuple[str, list[str]]] = []
    current_section: str | None = None
    current_body: list[str] = []

    for line in raw_lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_section is not None:
                sections.append((current_section, current_body))
            current_section = stripped
            current_body = []
        else:
            if current_section is None:
                sections.append(("__preamble__", [line]))
            else:
                current_body.append(line)

    if current_section is not None:
        sections.append((current_section, current_body))

    return sections


def _write_ini_sections(path: str, sections: list[tuple[str, list[str]]]) -> None:
    """Write sections back to the INI file."""
    with open(path, "w") as f:
        for section_name, body in sections:
            if section_name == "__preamble__":
                f.writelines(body)
            else:
                f.write(f"{section_name}\n")
                f.writelines(body)

def _append_to_body(body: list[str], *lines: str) -> None:
    """Append lines to a section body, ensuring no extra blank lines before them."""
    while body and body[-1].strip() == "":
        body.pop()
    for line in lines:
        body.append(line if line.endswith("\n") else f"{line}\n")

def inject_gecko_codes(dolphin_user_dir: str, codes: dict[str, list[str]] = None) -> None:
    """Ensure Gecko codes are defined and enabled in the game's INI.

    Args:
        dolphin_user_dir: Path to the Dolphin user directory
                          (the folder containing GameSettings/, Config/, etc.)
        codes: Dict of {code_name: [line1, line2, ...]} to inject.
               Defaults to GECKO_CODES if not provided.
    """
    if codes is None:
        codes = GECKO_CODES

    if not dolphin_user_dir:
        logger.warning("Dolphin user dir not provided, skipping Gecko injection")
        return

    settings_dir = os.path.join(dolphin_user_dir, "GameSettings")
    os.makedirs(settings_dir, exist_ok=True)
    ini_path = os.path.join(settings_dir, f"{GAME_ID}.ini")

    # Read existing file
    raw_lines: list[str] = []
    if os.path.exists(ini_path):
        with open(ini_path, "r") as f:
            raw_lines = f.readlines()

    sections = _parse_ini_sections(raw_lines)

    # Locate [Gecko] and [Gecko_Enabled]
    gecko_idx = next((i for i, (s, _) in enumerate(sections) if s == "[Gecko]"), None)
    enabled_idx = next((i for i, (s, _) in enumerate(sections) if s == "[Gecko_Enabled]"), None)

    gecko_body: list[str] = sections[gecko_idx][1] if gecko_idx is not None else []
    enabled_body: list[str] = sections[enabled_idx][1] if enabled_idx is not None else []

    # Collect already-present names
    existing_definitions: set[str] = {
        _base_name(l.strip()[1:])
        for l in gecko_body if l.strip().startswith("$")
    }
    existing_enabled: set[str] = {
        _base_name(l.strip()[1:])
        for l in enabled_body if l.strip().startswith("$")
    }

    # Add only what's missing
    codes_added = codes_enabled = 0
    for name, code_lines in codes.items():
        base = _base_name(name)

        if base not in existing_definitions:
            _append_to_body(gecko_body, f"${name}", *code_lines)
            codes_added += 1
            logger.info(f"Gecko: added definition for '{name}'")

        if base not in existing_enabled:
            _append_to_body(enabled_body, f"${_base_name(name)}")
            codes_enabled += 1
            logger.info(f"Gecko: enabled '{_base_name(name)}'")

    if codes_added == 0 and codes_enabled == 0:
        logger.info("Gecko codes already present and enabled, INI unchanged")
        return

    # Write back
    if gecko_idx is not None:
        sections[gecko_idx] = ("[Gecko]", gecko_body)
    else:
        sections.append(("[Gecko]", gecko_body))

    if enabled_idx is not None:
        sections[enabled_idx] = ("[Gecko_Enabled]", enabled_body)
    else:
        sections.append(("[Gecko_Enabled]", enabled_body))

    _write_ini_sections(ini_path, sections)
    logger.info(f"Gecko INI updated (+{codes_added} defined, +{codes_enabled} enabled): {ini_path}")

def disable_gecko_codes(dolphin_user_dir: str, codes: dict[str, list[str]] = None) -> None:
    """Remove Gecko codes from [Gecko_Enabled]"""
    if codes is None:
        codes = GECKO_CODES

    if not dolphin_user_dir:
        logger.warning("Dolphin user dir not provided, skipping Gecko disable")
        return

    ini_path = os.path.join(dolphin_user_dir, "GameSettings", f"{GAME_ID}.ini")
    if not os.path.exists(ini_path):
        return

    with open(ini_path, "r") as f:
        raw_lines = f.readlines()

    sections = _parse_ini_sections(raw_lines)

    enabled_idx = next((i for i, (s, _) in enumerate(sections) if s == "[Gecko_Enabled]"), None)
    if enabled_idx is None:
        logger.info("No [Gecko_Enabled] section found, nothing to disable")
        return

    enabled_body = sections[enabled_idx][1]
    bases_to_disable = {_base_name(name) for name in codes}

    original_len = len(enabled_body)
    enabled_body = [
        line for line in enabled_body
        if not (line.strip().startswith("$") and _base_name(line.strip()[1:]) in bases_to_disable)
    ]

    removed = original_len - len(enabled_body)
    if removed == 0:
        logger.info("Gecko codes were already disabled, INI unchanged")
        return

    sections[enabled_idx] = ("[Gecko_Enabled]", enabled_body)
    _write_ini_sections(ini_path, sections)
    logger.info(f"Gecko codes disabled (-{removed} from [Gecko_Enabled]): {ini_path}")