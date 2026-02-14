"""
ESP32-C3 ROM symbol definitions.

Symbols extracted from the official ESP32-C3 ROM ELF published by Espressif:
  https://github.com/espressif/esp-rom-elfs
  Copyright (c) 2015-2022 Espressif Systems (Shanghai) Co. Ltd.
  Licensed under the Apache License, Version 2.0

Additional jump-table symbols from ESP-IDF linker scripts:
  https://github.com/espressif/esp-idf (components/esp_rom/esp32c3/ld/)

Both sources are pre-processed into esp32c3_rom_symbols.json.
"""
import json
import os

from binaryninja import Symbol
from binaryninja.enums import SectionSemantics, SegmentFlag, SymbolType


def _load_rom_symbols():
    """Load ROM symbols from the pre-processed JSON file."""
    json_path = os.path.join(os.path.dirname(__file__), 'esp32c3_rom_symbols.json')
    if not os.path.exists(json_path):
        return {}, {}
    with open(json_path, 'r') as f:
        data = json.load(f)
    functions = {int(addr, 16): name for addr, name in data.get('functions', {}).items()}
    data_syms = {int(addr, 16): name for addr, name in data.get('data', {}).items()}
    return functions, data_syms


# Load once at import time
rom_functions, rom_data_symbols = _load_rom_symbols()


# ROM code region
ROM_CODE_START = 0x40000000
ROM_CODE_END = 0x40060000

# ROM data region (data bus view)
ROM_DATA_START = 0x3FF00000
ROM_DATA_END = 0x3FF20000


def setup_esp32c3_rom(bv):
    """Define ROM segments and symbols in the BinaryView."""
    if not rom_functions and not rom_data_symbols:
        return

    # Add ROM code segment (no backing data — these are external/imported)
    bv.add_auto_segment(ROM_CODE_START, ROM_CODE_END - ROM_CODE_START, 0, 0,
                        SegmentFlag.SegmentContainsCode |
                        SegmentFlag.SegmentReadable |
                        SegmentFlag.SegmentExecutable)
    bv.add_auto_section("esp32c3_ROM", ROM_CODE_START,
                        ROM_CODE_END - ROM_CODE_START,
                        SectionSemantics.ExternalSectionSemantics)

    # Define function symbols
    for addr, name in rom_functions.items():
        if ROM_CODE_START <= addr < ROM_CODE_END:
            bv.define_auto_symbol(Symbol(
                SymbolType.ImportedFunctionSymbol, addr, name))

    # Define data symbols
    for addr, name in rom_data_symbols.items():
        bv.define_auto_symbol(Symbol(
            SymbolType.ImportedDataSymbol, addr, name))
