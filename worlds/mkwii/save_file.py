"""
Mario Kart Wii Save File Handler (rksys.dat)

Handles reading and writing the MK Wii save file structure.
File size: 0x8000 (32KB)
"""

import struct
from typing import Dict, Set, Tuple
from pathlib import Path


class MKWiiSaveFile:
    """Handler for rksys.dat save file."""
    
    SAVE_SIZE = 0x8000
    MAGIC = b"RKSD"
    LICENSE_SIZE = 0x1C00
    LICENSE_OFFSETS = [0x0008, 0x1C08, 0x3808, 0x5408]
    
    # Offsets within a license block
    OFFSET_CHARACTER_UNLOCKS = 0x0020
    OFFSET_VEHICLE_UNLOCKS = 0x0024
    OFFSET_CUP_UNLOCKS = 0x0028
    OFFSET_MODE_UNLOCKS = 0x002C
    OFFSET_GP_50CC = 0x0030
    OFFSET_GP_100CC = 0x0070
    OFFSET_GP_150CC = 0x00B0
    OFFSET_GP_MIRROR = 0x00F0
    
    # Trophy and rank mappings
    TROPHY_VALUES = {"none": 0, "bronze": 1, "silver": 2, "gold": 3}
    RANK_VALUES = {
        "D": 0, "C": 1, "B": 2, "A": 3,
        "1_star": 4, "2_star": 5, "3_star": 6
    }
    
    # Reverse mappings
    VALUE_TO_RANK = {v: k for k, v in RANK_VALUES.items()}
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.data = bytearray()
        
    def read(self) -> bool:
        """Read save file from disk."""
        try:
            with open(self.filepath, 'rb') as f:
                self.data = bytearray(f.read())
            
            if len(self.data) != self.SAVE_SIZE:
                return False
            
            if self.data[0:4] != self.MAGIC:
                return False
            
            return True
        except Exception as e:
            print(f"Error reading save file: {e}")
            return False
    
    def write(self) -> bool:
        """Write save file to disk with updated checksum."""
        try:
            # Calculate and update checksum
            self._update_checksum()
            
            with open(self.filepath, 'wb') as f:
                f.write(self.data)
            
            return True
        except Exception as e:
            print(f"Error writing save file: {e}")
            return False
    
    def _update_checksum(self):
        """Calculate CRC32 checksum and write it at 0x7FF8."""
        import zlib
        # Checksum is over first 0x7FF8 bytes
        checksum_data = self.data[0:0x7FF8]
        crc = zlib.crc32(checksum_data) & 0xFFFFFFFF
        struct.pack_into('>I', self.data, 0x7FF8, crc)
    
    def get_license_offset(self, license_id: int = 0) -> int:
        """Get offset for a license (0-3)."""
        if 0 <= license_id < 4:
            return self.LICENSE_OFFSETS[license_id]
        return self.LICENSE_OFFSETS[0]
    
    # === Character Unlocks ===
    
    def get_unlocked_characters(self, license_id: int = 0) -> Set[int]:
        """Get set of unlocked character IDs."""
        offset = self.get_license_offset(license_id) + self.OFFSET_CHARACTER_UNLOCKS
        bitfield = struct.unpack_from('>I', self.data, offset)[0]
        
        unlocked = set()
        for bit in range(32):
            if bitfield & (1 << bit):
                unlocked.add(bit)
        return unlocked
    
    def unlock_character(self, character_id: int, license_id: int = 0):
        """Unlock a character by ID."""
        offset = self.get_license_offset(license_id) + self.OFFSET_CHARACTER_UNLOCKS
        bitfield = struct.unpack_from('>I', self.data, offset)[0]
        bitfield |= (1 << character_id)
        struct.pack_into('>I', self.data, offset, bitfield)
    
    # === Vehicle Unlocks ===
    
    def get_unlocked_vehicles(self, license_id: int = 0) -> Set[int]:
        """Get set of unlocked vehicle IDs."""
        offset = self.get_license_offset(license_id) + self.OFFSET_VEHICLE_UNLOCKS
        bitfield = struct.unpack_from('>I', self.data, offset)[0]
        
        unlocked = set()
        for bit in range(32):
            if bitfield & (1 << bit):
                unlocked.add(bit)
        return unlocked
    
    def unlock_vehicle(self, vehicle_id: int, license_id: int = 0):
        """Unlock a vehicle by ID."""
        offset = self.get_license_offset(license_id) + self.OFFSET_VEHICLE_UNLOCKS
        bitfield = struct.unpack_from('>I', self.data, offset)[0]
        bitfield |= (1 << vehicle_id)
        struct.pack_into('>I', self.data, offset, bitfield)
    
    # === Cup Unlocks ===
    
    def get_cup_unlocks(self, license_id: int = 0) -> int:
        """Get cup unlock bitfield."""
        offset = self.get_license_offset(license_id) + self.OFFSET_CUP_UNLOCKS
        return struct.unpack_from('>I', self.data, offset)[0]
    
    def set_cup_unlocks(self, bitfield: int, license_id: int = 0):
        """Set cup unlock bitfield."""
        offset = self.get_license_offset(license_id) + self.OFFSET_CUP_UNLOCKS
        struct.pack_into('>I', self.data, offset, bitfield)
    
    def is_cup_unlocked(self, cup_name: str, license_id: int = 0) -> bool:
        """Check if a specific cup is unlocked (at base 50cc level)."""
        # Cup unlock bits:
        # Bit 0: Flower Cup
        # Bit 1: Star Cup
        # Bit 2: Special Cup
        # Bit 3: Shell Cup
        # Bit 4: Banana Cup
        # Bit 5: Leaf Cup
        # Bit 6: Lightning Cup
        # Bit 7: Mirror Mode
        
        # Mushroom Cup is always unlocked (no bit)
        if cup_name == "Mushroom Cup":
            return True
        
        cup_bits = {
            "Flower Cup": 0,
            "Star Cup": 1,
            "Special Cup": 2,
            "Shell Cup": 3,
            "Banana Cup": 4,
            "Leaf Cup": 5,
            "Lightning Cup": 6,
        }
        
        if cup_name not in cup_bits:
            return False
        
        bitfield = self.get_cup_unlocks(license_id)
        return bool(bitfield & (1 << cup_bits[cup_name]))
    
    def unlock_cup(self, cup_name: str, license_id: int = 0):
        """Unlock a specific cup (at base 50cc level)."""
        cup_bits = {
            "Flower Cup": 0,
            "Star Cup": 1,
            "Special Cup": 2,
            "Shell Cup": 3,
            "Banana Cup": 4,
            "Leaf Cup": 5,
            "Lightning Cup": 6,
        }
        
        if cup_name == "Mushroom Cup":
            return  # Always unlocked
        
        if cup_name in cup_bits:
            offset = self.get_license_offset(license_id) + self.OFFSET_CUP_UNLOCKS
            bitfield = struct.unpack_from('>I', self.data, offset)[0]
            bitfield |= (1 << cup_bits[cup_name])
            struct.pack_into('>I', self.data, offset, bitfield)
    
    def is_mirror_mode_unlocked(self, license_id: int = 0) -> bool:
        """Check if Mirror Mode is unlocked."""
        bitfield = self.get_cup_unlocks(license_id)
        return bool(bitfield & (1 << 7))
    
    def unlock_mirror_mode(self, license_id: int = 0):
        """Unlock Mirror Mode."""
        offset = self.get_license_offset(license_id) + self.OFFSET_CUP_UNLOCKS
        bitfield = struct.unpack_from('>I', self.data, offset)[0]
        bitfield |= (1 << 7)
        struct.pack_into('>I', self.data, offset, bitfield)
    
    # === Grand Prix Results ===
    
    def get_gp_result(self, cup_id: int, cc: str, license_id: int = 0) -> Tuple[str, str]:
        """
        Get Grand Prix result for a cup.
        
        Args:
            cup_id: 0-7 (Mushroom, Flower, Star, Special, Shell, Banana, Leaf, Lightning)
            cc: "50cc", "100cc", "150cc", "Mirror"
            license_id: 0-3
        
        Returns:
            (trophy, rank) tuple, e.g. ("gold", "2_star")
        """
        # Determine base offset for CC
        cc_offsets = {
            "50cc": self.OFFSET_GP_50CC,
            "100cc": self.OFFSET_GP_100CC,
            "150cc": self.OFFSET_GP_150CC,
            "Mirror": self.OFFSET_GP_MIRROR
        }
        
        base_offset = self.get_license_offset(license_id) + cc_offsets[cc]
        
        # Each cup entry is 2 bytes: [trophy byte][rank byte]
        # Cup order: Mushroom, Flower, Star, Special, Shell, Banana, Leaf, Lightning
        cup_offset = base_offset + (cup_id * 2)
        
        trophy_byte = self.data[cup_offset]
        rank_byte = self.data[cup_offset + 1]
        
        # Convert to strings
        trophy = {v: k for k, v in self.TROPHY_VALUES.items()}.get(trophy_byte, "none")
        rank = self.VALUE_TO_RANK.get(rank_byte, "D")
        
        return (trophy, rank)
    
    def set_gp_result(self, cup_id: int, cc: str, trophy: str, rank: str, license_id: int = 0):
        """Set Grand Prix result for a cup."""
        cc_offsets = {
            "50cc": self.OFFSET_GP_50CC,
            "100cc": self.OFFSET_GP_100CC,
            "150cc": self.OFFSET_GP_150CC,
            "Mirror": self.OFFSET_GP_MIRROR
        }
        
        base_offset = self.get_license_offset(license_id) + cc_offsets[cc]
        cup_offset = base_offset + (cup_id * 2)
        
        trophy_byte = self.TROPHY_VALUES.get(trophy, 0)
        rank_byte = self.RANK_VALUES.get(rank, 0)
        
        self.data[cup_offset] = trophy_byte
        self.data[cup_offset + 1] = rank_byte
    
    def unlock_cup_at_cc(self, cup_name: str, cc: str, license_id: int = 0):
        """
        Unlock a cup at a specific CC by writing minimum completion data.
        
        This works by giving the PREVIOUS cup a bronze trophy, which unlocks the next cup.
        For the first cup in a CC, just make sure it has some trophy data.
        """
        cup_order = [
            "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
            "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup"
        ]
        
        if cup_name not in cup_order:
            return
        
        cup_idx = cup_order.index(cup_name)
        
        # Mushroom Cup is always available (it's first)
        if cup_idx == 0:
            return
        
        # To unlock this cup, give the previous cup a bronze trophy
        prev_cup_idx = cup_idx - 1
        current_trophy, current_rank = self.get_gp_result(prev_cup_idx, cc, license_id)
        
        # Only set if not already completed
        if current_trophy == "none":
            self.set_gp_result(prev_cup_idx, cc, "bronze", "D", license_id)
    
    def unlock_all_cups_at_cc(self, cc: str, license_id: int = 0):
        """Unlock all cups at a specific CC by giving each previous cup bronze."""
        cup_order = [
            "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
            "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup"
        ]
        
        # Give each cup (except last) bronze to unlock the next
        for i in range(7):
            current_trophy, _ = self.get_gp_result(i, cc, license_id)
            if current_trophy == "none":
                self.set_gp_result(i, cc, "bronze", "D", license_id)
    
    def is_cup_accessible_at_cc(self, cup_name: str, cc: str, license_id: int = 0) -> bool:
        """
        Check if a cup is accessible at a specific CC.
        
        Determined by whether the previous cup has a trophy.
        """
        cup_order = [
            "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
            "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup"
        ]
        
        if cup_name not in cup_order:
            return False
        
        cup_idx = cup_order.index(cup_name)
        
        # Mushroom Cup is always accessible
        if cup_idx == 0:
            return True
        
        # Check if previous cup has a trophy
        prev_cup_idx = cup_idx - 1
        prev_trophy, _ = self.get_gp_result(prev_cup_idx, cc, license_id)
        
        return prev_trophy != "none"
    
    def unlock_mirror_mode_requirement(self, license_id: int = 0):
        """
        Unlock Mirror Mode by satisfying requirements.
        
        Requires all 150cc cups to have at least 1-star rank.
        This writes minimal completion data and sets the Mirror flag.
        """
        # Give all 150cc cups gold + 1-star to unlock Mirror
        for cup_id in range(8):
            current_trophy, current_rank = self.get_gp_result(cup_id, "150cc", license_id)
            # Only set if not already better
            if self.TROPHY_VALUES.get(current_trophy, 0) < 3 or \
               self.RANK_VALUES.get(current_rank, 0) < 4:
                self.set_gp_result(cup_id, "150cc", "gold", "1_star", license_id)
        
        # Set Mirror Mode flag
        self.unlock_mirror_mode(license_id)
    
    def get_all_gp_results(self, license_id: int = 0) -> Dict[Tuple[int, str], Tuple[str, str]]:
        """Get all GP results. Returns dict of {(cup_id, cc): (trophy, rank)}."""
        results = {}
        
        for cup_id in range(8):
            for cc in ["50cc", "100cc", "150cc", "Mirror"]:
                trophy, rank = self.get_gp_result(cup_id, cc, license_id)
                results[(cup_id, cc)] = (trophy, rank)
        
        return results


# Character ID mapping (bit positions in character unlock bitmap)
CHARACTER_IDS = {
    "Baby Daisy": 0,
    "Baby Luigi": 1,
    "Dry Bones": 2,
    "Bowser Jr.": 3,
    "Toadette": 4,
    "King Boo": 5,
    "Dry Bowser": 6,
    "Funky Kong": 7,
    "Rosalina": 8,
    "Diddy Kong": 9,
    "Daisy": 10,
    "Birdo": 11,
    "Mii Outfit A": 12,
    "Mii Outfit B": 13,
    # Bits 14-31 unused
}

# Vehicle ID mapping (bit positions in vehicle unlock bitmap, PAL names)
VEHICLE_IDS = {
    "Standard Kart M": 0,
    "Nostalgia 1": 1,          # US: Classic Dragster
    "Concerto": 2,             # US: Wild Wing
    "Turbo Blooper": 3,        # US: Super Blooper
    "Piranha Prowler": 4,
    "Rally Romper": 5,         # US: Tiny Titan
    "Royal Racer": 6,          # US: Daytripper
    "Aero Glider": 7,          # US: Jetsetter
    "Blue Falcon": 8,
    "B. Dasher Mk 2": 9,      # US: Sprinter
    "Dragonetti": 10,          # US: Honeycoupe
    "Flame Flyer": 11,
    "Mini Beast": 12,
    "Cheep Charger": 13,
    "Baby Booster": 14,        # US: Booster Seat
    "Standard Bike S": 15,
    "Bullet Bike": 16,
    "Nanobike": 17,            # US: Bit Bike
    "Quacker": 18,
    "Magicruiser": 19,         # US: Magikruiser
    "Nitrocycle": 20,          # US: Sneakster
    "Standard Bike M": 21,
    "Mach Bike": 22,
    "Bon Bon": 23,             # US: Sugarscoot
    "Rapide": 24,              # US: Zip Zip
    "Twinkle Star": 25,        # US: Shooting Star
    "Standard Bike L": 26,
    "Bowser Bike": 27,         # US: Flame Runner
    "Torpedo": 28,             # US: Wario Bike / Spear
    "Phantom": 29,
    # Bits 30-31 unused
}

# Cup ID mapping
CUP_IDS = {
    "Mushroom Cup": 0,
    "Flower Cup": 1,
    "Star Cup": 2,
    "Special Cup": 3,
    "Shell Cup": 4,
    "Banana Cup": 5,
    "Leaf Cup": 6,
    "Lightning Cup": 7,
}

# CC ID mapping
CC_IDS = {
    "50cc": 0,
    "100cc": 1,
    "150cc": 2,
    "Mirror": 3,
}
