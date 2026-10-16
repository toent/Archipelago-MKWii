baseAddressCombos = {
    # Name: (PAL, NTSC)
    "SYSTEM_MANAGER_PTR": (0x809BD748, 0x00000000),
    "RACE_CONFIG_PTR": (0x809BD728, 0x00000000),
    "RACE_MGR_PTR_ADDR": (0x809BD730, 0x00000000),
    "TRACK_ID_ADDR": (0x809C26B3, 0x00000000),
    "PLAYER_HOLDER_PTR_ADDR": (0x809C18F8, 0x00000000),
    "ITEM_HOLDER_STATIC_ADDR": (0x809C3618, 0x00000000),
    "UNLOCK_PATCH_PRIMARY_ADDR": (0x80854FA4, 0x00000000),
    "UNLOCK_PATCH_FALLBACK_ADDR": (0x805EB920, 0x00000000),
}

pointerCombos = {
    # Pointer name: ({base address name: ([offsets PAL], [offsets NTSC])}, field size in bytes)
    # Walk: read the pointer at the current address, add the offset, repeat. The last offset is the field.

    # Save system. Address holding the rksys buffer pointer.
    "RAW_SAVE_OFFSET": ({"SYSTEM_MANAGER_PTR": ([0x14], [])}, 4),

    # First byte of the runtime unlock flags for license 1 (8 bytes, stride 0x93F0 per license).
    "RUNTIME_UNLOCK_BASE": ({"SYSTEM_MANAGER_PTR": ([0x9034], [])}, 8),

    # RaceConfig
    "RACECONFIG_CUP": ({"RACE_CONFIG_PTR": ([0x177B], [])}, 1),
    "RACECONFIG_COURSE": ({"RACE_CONFIG_PTR": ([0x175B], [])}, 1),
    "RACECONFIG_CC": ({"RACE_CONFIG_PTR": ([0x175F], [])}, 1),
    "RACECONFIG_MIRROR": ({"RACE_CONFIG_PTR": ([0x1783], [])}, 1),
    "MENU_VEHICLE": ({"RACE_CONFIG_PTR": ([0xC20], [])}, 4),
    "MENU_CHARACTER": ({"RACE_CONFIG_PTR": ([0xC24], [])}, 4),

    # Race manager
    "RACE_STAGE": ({"RACE_MGR_PTR_ADDR": ([0x28], [])}, 4),
    "P1_PLAYER_PTR": ({"RACE_MGR_PTR_ADDR": ([0xAC], [])}, 4),
    "P1_PLACEMENT": ({"RACE_MGR_PTR_ADDR": ([0xAC, 0x20], [])}, 1),
    "P1_LAP": ({"RACE_MGR_PTR_ADDR": ([0xAC, 0x25], [])}, 1),

    # DeathLink (player 0)
    "PRE_RESPAWN_PATH": ({"PLAYER_HOLDER_PTR_ADDR": ([0x20, 0x0, 0x0, 0x30, 0x48], [])}, 2),
    "PLAYER_Y_PATH": ({"PLAYER_HOLDER_PTR_ADDR": ([0x20, 0x0, 0x0, 0x8, 0x90, 0x4, 0x6C], [])}, 4),

    # Item holder (player 0). 0x14 is the address holding the item holder pointer.
    "ITEM_HOLDER_PTR": ({"ITEM_HOLDER_STATIC_ADDR": ([0x14], [])}, 4),
    "ITEM_ID": ({"ITEM_HOLDER_STATIC_ADDR": ([0x14, 0x8C], [])}, 4),
    "ITEM_COUNT": ({"ITEM_HOLDER_STATIC_ADDR": ([0x14, 0x90], [])}, 4),
    "ITEM_GM_ACTIVATION_FLAG": ({"ITEM_HOLDER_STATIC_ADDR": ([0x14, 0xA4], [])}, 4),
    "ITEM_ROULETTE_DISPLAY": ({"ITEM_HOLDER_STATIC_ADDR": ([0x14, 0x6C], [])}, 4),
}

layoutConstants = {
    # Name: (PAL, NTSC)
    "RUNTIME_LICENSE_STRIDE": (0x93F0, 0x0),
    "SAVE_LICENSE_STRIDE": (0x8CC0, 0x0),
    "SAVE_UNLOCK_START": (0x0038, 0x0),
    "UNLOCK_BYTE_COUNT": (8, 0x0),
}

class DMEAddressIndex:
    def __init__(self, region="pal"):
        region = region.lower()
        if region not in ("pal", "ntsc"):
            raise ValueError(f"Unknown region: {region}")
        idx = 0 if region == "pal" else 1

        self.region = region
        self.baseAddresses = {name: pair[idx] for name, pair in baseAddressCombos.items()}
        self.constants = {name: pair[idx] for name, pair in layoutConstants.items()}

        self.pointers = {
            name: ({base: offsets[idx] for base, offsets in bases.items()}, size)
            for name, (bases, size) in pointerCombos.items()
        }