"""
ESP32 chip variant definitions.

Data-driven chip definition table covering all ESP32 variants.
Memory regions sourced from ESP-IDF soc.h (SOC_*_LOW/HIGH defines).
"""
from dataclasses import dataclass, field


@dataclass
class ChipDef:
    name: str
    arch: str  # Binary Ninja architecture name
    chip_id: int
    memory_regions: dict  # {name: (start, end)}
    rom_code_range: tuple  # (start, end)
    rom_data_range: tuple | None  # (start, end) or None if same as rom_code
    rom_symbols_file: str  # filename in rom/ directory

    def classify_address(self, addr):
        """Classify a memory address into its memory region name."""
        for name, (start, end) in self.memory_regions.items():
            if start <= addr < end:
                return name
        return 'UNKNOWN'


def is_code_region(region):
    """Return True if the region contains executable code."""
    return region in ('IRAM', 'IROM', 'ROM', 'RTC_IRAM')


def is_writable_region(region):
    """Return True if the region is writable."""
    return region in ('DRAM', 'RTC', 'RTC_DRAM')


# All supported ESP32 chip variants.
# Memory regions from ESP-IDF components/soc/<chip>/include/soc/soc.h
CHIPS = {
    # ---- Xtensa chips ----

    0x0000: ChipDef(
        name="ESP32",
        arch="xtensa",
        chip_id=0x0000,
        memory_regions={
            'DROM':     (0x3F400000, 0x3F800000),  # Flash-mapped read-only data (4 MB)
            'RTC_DRAM': (0x3FF80000, 0x3FF82000),  # RTC fast memory, data bus (8 KB)
            'DRAM':     (0x3FFAE000, 0x40000000),  # Internal data RAM (328 KB)
            'ROM':      (0x40000000, 0x40070000),  # Internal mask ROM (448 KB)
            'IRAM':     (0x40080000, 0x400A0000),  # Internal instruction RAM (168 KB)
            'RTC_IRAM': (0x400C0000, 0x400C2000),  # RTC fast memory, instruction bus (8 KB)
            'IROM':     (0x400D0000, 0x40400000),  # Flash-mapped code (~3 MB)
            'RTC':      (0x50000000, 0x50002000),  # RTC slow memory (8 KB)
        },
        rom_code_range=(0x40000000, 0x40070000),
        rom_data_range=None,  # ROM data symbols in DRAM space, no dedicated region
        rom_symbols_file="esp32_rom_symbols.json",
    ),

    0x0002: ChipDef(
        name="ESP32-S2",
        arch="xtensa",
        chip_id=0x0002,
        memory_regions={
            'DROM':     (0x3F000000, 0x3FF80000),  # Flash-mapped read-only data (~16 MB)
            'RTC_DRAM': (0x3FF9E000, 0x3FFA0000),  # RTC fast memory, data bus (8 KB)
            'DRAM':     (0x3FFB0000, 0x40000000),  # Internal data RAM (320 KB)
            'ROM':      (0x40000000, 0x40020000),  # Internal mask ROM (128 KB)
            'IRAM':     (0x40020000, 0x40070000),  # Internal instruction RAM (320 KB)
            'RTC_IRAM': (0x40070000, 0x40072000),  # RTC fast memory, instruction bus (8 KB)
            'IROM':     (0x40080000, 0x40800000),  # Flash-mapped code (~8 MB)
            'RTC':      (0x50000000, 0x50002000),  # RTC slow memory (8 KB)
        },
        rom_code_range=(0x40000000, 0x40020000),
        rom_data_range=None,  # ROM data symbols in DRAM space, no dedicated region
        rom_symbols_file="esp32s2_rom_symbols.json",
    ),

    0x0009: ChipDef(
        name="ESP32-S3",
        arch="xtensa",
        chip_id=0x0009,
        memory_regions={
            'DROM': (0x3C000000, 0x3E000000),   # Flash-mapped read-only data (32 MB)
            'DRAM': (0x3FC88000, 0x3FD00000),    # Internal data RAM (480 KB)
            'ROM':  (0x40000000, 0x40060000),    # Internal mask ROM (384 KB)
            'IRAM': (0x40370000, 0x403E0000),    # Internal instruction RAM (448 KB)
            'IROM': (0x42000000, 0x44000000),    # Flash-mapped code (32 MB)
            'RTC':  (0x50000000, 0x50002000),    # RTC slow memory (8 KB)
            'RTC_DRAM': (0x600FE000, 0x60100000),  # RTC fast memory (8 KB)
        },
        rom_code_range=(0x40000000, 0x40060000),
        rom_data_range=None,  # ROM data symbols at 0x3FF1xxxx but not formally defined
        rom_symbols_file="esp32s3_rom_symbols.json",
    ),

    # ---- RISC-V chips (split-bus) ----

    0x0005: ChipDef(
        name="ESP32-C3",
        arch="rv32gc",
        chip_id=0x0005,
        memory_regions={
            'DROM': (0x3C000000, 0x3C800000),  # Flash-mapped read-only data (8 MB)
            'DRAM': (0x3FC80000, 0x3FCE0000),   # Internal data RAM (384 KB)
            'ROM':  (0x40000000, 0x40060000),   # Internal mask ROM (384 KB)
            'IRAM': (0x4037C000, 0x403E0000),   # Internal instruction RAM (400 KB)
            'IROM': (0x42000000, 0x42800000),   # Flash-mapped code (8 MB)
            'RTC':  (0x50000000, 0x50002000),   # RTC slow memory (8 KB)
        },
        rom_code_range=(0x40000000, 0x40060000),
        rom_data_range=(0x3FF00000, 0x3FF20000),  # DROM_MASK
        rom_symbols_file="esp32c3_rom_symbols.json",
    ),

    0x000C: ChipDef(
        name="ESP32-C2",
        arch="rv32gc",
        chip_id=0x000C,
        memory_regions={
            'DROM': (0x3C000000, 0x3C400000),  # Flash-mapped read-only data (4 MB)
            'DRAM': (0x3FCA0000, 0x3FCE0000),   # Internal data RAM (256 KB)
            'ROM':  (0x40000000, 0x40090000),   # Internal mask ROM (576 KB)
            'IRAM': (0x4037C000, 0x403C0000),   # Internal instruction RAM (272 KB)
            'IROM': (0x42000000, 0x42400000),   # Flash-mapped code (4 MB)
            # No RTC/LP memory on ESP32-C2
        },
        rom_code_range=(0x40000000, 0x40090000),
        rom_data_range=(0x3FF00000, 0x3FF50000),  # DROM_MASK
        rom_symbols_file="esp32c2_rom_symbols.json",
    ),

    # ---- RISC-V chips (unified-bus: IRAM=DRAM, IROM=DROM) ----

    0x000D: ChipDef(
        name="ESP32-C6",
        arch="rv32gc",
        chip_id=0x000D,
        memory_regions={
            'DROM': (0x42000000, 0x43000000),  # Flash-mapped (16 MB, unified with IROM)
            'DRAM': (0x40800000, 0x40880000),   # Internal RAM (512 KB, unified with IRAM)
            'ROM':  (0x40000000, 0x40050000),   # Internal mask ROM (320 KB)
            'IRAM': (0x40800000, 0x40880000),   # Same as DRAM (unified bus)
            'IROM': (0x42000000, 0x43000000),   # Same as DROM (unified bus)
            'RTC':  (0x50000000, 0x50004000),   # LP memory (16 KB)
        },
        rom_code_range=(0x40000000, 0x40050000),
        rom_data_range=(0x40000000, 0x40050000),  # Unified: same as ROM code
        rom_symbols_file="esp32c6_rom_symbols.json",
    ),

    0x0010: ChipDef(
        name="ESP32-H2",
        arch="rv32gc",
        chip_id=0x0010,
        memory_regions={
            'DROM': (0x42000000, 0x43000000),  # Flash-mapped (16 MB, unified with IROM)
            'DRAM': (0x40800000, 0x40850000),   # Internal RAM (320 KB, unified with IRAM)
            'ROM':  (0x40000000, 0x40020000),   # Internal mask ROM (128 KB)
            'IRAM': (0x40800000, 0x40850000),   # Same as DRAM (unified bus)
            'IROM': (0x42000000, 0x43000000),   # Same as DROM (unified bus)
            'RTC':  (0x50000000, 0x50001000),   # LP memory (4 KB)
        },
        rom_code_range=(0x40000000, 0x40020000),
        rom_data_range=(0x40000000, 0x40020000),  # Unified: same as ROM code
        rom_symbols_file="esp32h2_rom_symbols.json",
    ),

    0x0012: ChipDef(
        name="ESP32-P4",
        arch="rv32gc",
        chip_id=0x0012,
        memory_regions={
            'DROM': (0x40000000, 0x44000000),  # Flash-mapped (64 MB, unified with IROM)
            'DRAM': (0x4FF00000, 0x4FFC0000),   # Internal HP RAM (768 KB, unified with IRAM)
            'ROM':  (0x4FC00000, 0x4FC20000),   # Internal mask ROM (128 KB)
            'IRAM': (0x4FF00000, 0x4FFC0000),   # Same as DRAM (unified bus)
            'IROM': (0x40000000, 0x44000000),   # Same as DROM (unified bus)
            'RTC':  (0x50108000, 0x50110000),   # LP RAM (32 KB)
        },
        rom_code_range=(0x4FC00000, 0x4FC20000),
        rom_data_range=(0x4FC00000, 0x4FC20000),  # Unified: same as ROM code
        rom_symbols_file="esp32p4_rom_symbols.json",
    ),

    0x0017: ChipDef(
        name="ESP32-C5",
        arch="rv32gc",
        chip_id=0x0017,
        memory_regions={
            'DROM': (0x42000000, 0x44000000),  # Flash-mapped (32 MB, unified with IROM)
            'DRAM': (0x40800000, 0x40860000),   # Internal RAM (384 KB, unified with IRAM)
            'ROM':  (0x40000000, 0x40050000),   # Internal mask ROM (320 KB)
            'IRAM': (0x40800000, 0x40860000),   # Same as DRAM (unified bus)
            'IROM': (0x42000000, 0x44000000),   # Same as DROM (unified bus)
            'RTC':  (0x50000000, 0x50004000),   # LP memory (16 KB)
        },
        rom_code_range=(0x40000000, 0x40050000),
        rom_data_range=(0x40000000, 0x40050000),  # Unified: same as ROM code
        rom_symbols_file="esp32c5_rom_symbols.json",
    ),
}
