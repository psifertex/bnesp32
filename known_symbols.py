"""
ESP32 ROM symbol definitions.

Loads ROM symbols from per-chip JSON files in the rom/ directory.
Symbols are extracted from the official ROM ELFs published by Espressif:
  https://github.com/espressif/esp-rom-elfs
  Copyright (c) 2015-2022 Espressif Systems (Shanghai) Co. Ltd.
  Licensed under the Apache License, Version 2.0

Additional jump-table symbols from ESP-IDF linker scripts:
  https://github.com/espressif/esp-idf (components/esp_rom/<chip>/ld/)
"""
import json
import os

try:
    from binaryninja import Symbol
    from binaryninja.enums import SectionSemantics, SegmentFlag, SymbolType
except ImportError:
    pass


def _load_rom_symbols(chip_def):
    """Load ROM symbols from the per-chip JSON file."""
    json_path = os.path.join(os.path.dirname(__file__), 'rom', chip_def.rom_symbols_file)
    if not os.path.exists(json_path):
        return {}, {}
    with open(json_path, 'r') as f:
        data = json.load(f)
    functions = {int(addr, 16): name for addr, name in data.get('functions', {}).items()}
    data_syms = {int(addr, 16): name for addr, name in data.get('data', {}).items()}
    return functions, data_syms


def setup_rom_symbols(bv, chip_def):
    """Define ROM segments and symbols in the BinaryView."""
    rom_functions, rom_data_symbols = _load_rom_symbols(chip_def)
    if not rom_functions and not rom_data_symbols:
        return

    rom_code_start, rom_code_end = chip_def.rom_code_range

    # Add ROM code segment (no backing data — these are external/imported)
    bv.add_auto_segment(rom_code_start, rom_code_end - rom_code_start, 0, 0,
                        SegmentFlag.SegmentContainsCode |
                        SegmentFlag.SegmentReadable |
                        SegmentFlag.SegmentExecutable)
    bv.add_auto_section(f"{chip_def.name.lower().replace('-', '')}_ROM",
                        rom_code_start, rom_code_end - rom_code_start,
                        SectionSemantics.ExternalSectionSemantics)

    # Add ROM data segment if it's a separate region from ROM code
    if chip_def.rom_data_range and chip_def.rom_data_range != chip_def.rom_code_range:
        rom_data_start, rom_data_end = chip_def.rom_data_range
        bv.add_auto_segment(rom_data_start, rom_data_end - rom_data_start, 0, 0,
                            SegmentFlag.SegmentContainsData |
                            SegmentFlag.SegmentReadable)
        bv.add_auto_section(f"{chip_def.name.lower().replace('-', '')}_ROM_data",
                            rom_data_start, rom_data_end - rom_data_start,
                            SectionSemantics.ExternalSectionSemantics)

    # Define function symbols
    for addr, name in rom_functions.items():
        if rom_code_start <= addr < rom_code_end:
            bv.define_auto_symbol(Symbol(
                SymbolType.ImportedFunctionSymbol, addr, name))

    # Define data symbols
    for addr, name in rom_data_symbols.items():
        bv.define_auto_symbol(Symbol(
            SymbolType.ImportedDataSymbol, addr, name))
