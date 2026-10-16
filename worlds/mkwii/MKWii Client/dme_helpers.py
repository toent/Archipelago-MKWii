import struct
from typing import Optional

import dolphin_memory_engine as dme

from dme_addresses import DMEAddressIndex

# Struct formats, big endian because the Wii is big endian
U8 = ">B"
U16 = ">H"
S16 = ">h"
U32 = ">I"
F32 = ">f"

# Valid pointer ranges: MEM1 and MEM2
MEM1 = (0x80000000, 0x817FFFFF)
MEM2 = (0x90000000, 0x93FFFFFF)

_index = DMEAddressIndex("pal")


def set_region(region: str) -> None:
    """Switch every lookup to "pal" or "ntsc"."""
    global _index
    _index = DMEAddressIndex(region)


# Raw reads and writes

def read(addr: int, fmt: str):
    """Read one value of the given struct format at addr."""
    return struct.unpack(fmt, dme.read_bytes(addr, struct.calcsize(fmt)))[0]


def write(addr: int, fmt: str, value) -> None:
    """Write one value of the given struct format at addr."""
    dme.write_bytes(addr, struct.pack(fmt, value))


def read_u8(addr: int) -> int:
    return read(addr, U8)


def read_s16(addr: int) -> int:
    return read(addr, S16)


def read_u32(addr: int) -> int:
    return read(addr, U32)


def read_f32(addr: int) -> float:
    return read(addr, F32)


def write_u8(addr: int, value: int) -> None:
    write(addr, U8, value)


def write_s16(addr: int, value: int) -> None:
    write(addr, S16, value)


def write_u32(addr: int, value: int) -> None:
    write(addr, U32, value)


def write_f32(addr: int, value: float) -> None:
    write(addr, F32, value)


# Pointers

def is_valid_ptr(addr: int) -> bool:
    # True if addr lies inside MEM1 or MEM2.
    return MEM1[0] <= addr <= MEM1[1] or MEM2[0] <= addr <= MEM2[1]


def walk_pointers(base: int, offsets) -> Optional[int]:
    # Follow a pointer chain and return the address of the final field.
    # At each step: read the pointer stored at the current address, check it is valid, add the offset. Returns None if a pointer is invalid or unreadable,
    
    addr = base
    try:
        for offset in offsets:
            ptr = read_u32(addr)
            if not is_valid_ptr(ptr):
                return None
            addr = ptr + offset
    except Exception:
        return None
    return addr


# Lookups by name (names come from dme_addresses.py)

def base_address(name: str) -> int:
    """Look up a base address, e.g. base_address("TRACK_ID_ADDR")."""
    return _index.baseAddresses[name]


def constant(name: str) -> int:
    """Look up a layout constant, e.g. constant("UNLOCK_BYTE_COUNT")."""
    return _index.constants[name]


def resolve(name: str) -> Optional[int]:
    """Walk a named pointer chain and return the final field address.

    Returns None if the chain is invalid right now. Raises if the chain has
    no offsets for the current region, so a missing NTSC entry is not
    silently treated as a direct read of the base address.
    """
    bases, _size = _index.pointers[name]
    base_name, offsets = next(iter(bases.items()))
    if not offsets:
        raise ValueError(f"No offsets for {name} in region {_index.region}")
    return walk_pointers(base_address(base_name), offsets)


def read_named(name: str, fmt: str):
    """Resolve a named chain and read the field. Returns None on failure."""
    addr = resolve(name)
    if addr is None:
        return None
    try:
        return read(addr, fmt)
    except Exception:
        return None


def write_named(name: str, fmt: str, value) -> bool:
    """Resolve a named chain and write the field. Returns True on success."""
    addr = resolve(name)
    if addr is None:
        return False
    try:
        write(addr, fmt, value)
        return True
    except Exception:
        return False