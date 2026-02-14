"""
ESP32-C3 Firmware BinaryView for Binary Ninja.

Loads ESP32-C3 firmware images (magic 0xE9, chip_id 0x0005) using
Binary Ninja's built-in rv32gc architecture.
"""
import json
import struct

from binaryninja import Architecture, BinaryView, Settings, Symbol
from binaryninja.enums import SectionSemantics, SegmentFlag, SymbolType

from .firmware_parser import parse_esp32c3, classify_address, is_code_region
from .known_symbols import setup_esp32c3_rom


class ESP32C3Firmware(BinaryView):
    name = "ESP32C3Firmware"
    long_name = "ESP32-C3 Firmware"

    def __init__(self, data):
        BinaryView.__init__(self, file_metadata=data.file, parent_view=data)
        self.raw = data

    @classmethod
    def is_valid_for_data(cls, data):
        """Check if this is an ESP32-C3 firmware image."""
        header = data.read(0, 24)
        if len(header) < 24:
            return False
        if header[0] != 0xE9:
            return False
        chip_id = struct.unpack_from('<H', header, 0x0C)[0]
        return chip_id == 0x0005

    @classmethod
    def get_load_settings_for_data(cls, data):
        image = parse_esp32c3(data)
        if image is None:
            return None

        load_settings = Settings("esp32c3_bv_settings")
        assert load_settings.register_group("loader", "Loader")

        setting = json.dumps({
            "title": "Load ROM Symbols",
            "type": "boolean",
            "description": "Load ESP32-C3 ROM function symbols",
            "default": True
        })
        assert load_settings.register_setting(
            "loader.esp32c3.loadRomSymbols", setting)

        return load_settings

    def perform_is_executable(self):
        return True

    def perform_get_entry_point(self):
        return self.entry_addr

    def perform_get_address_size(self):
        return 4

    def init(self):
        image = parse_esp32c3(self.parent_view)
        if image is None:
            return False

        self.platform = Architecture['rv32gc'].standalone_platform
        self.arch = Architecture['rv32gc']
        self.entry_addr = image.entry_point

        # Load ROM symbols setting
        load_rom = True
        try:
            load_settings = self.get_load_settings(self.name)
            load_rom = load_settings.get_bool(
                "loader.esp32c3.loadRomSymbols", self)
        except:
            pass

        # Add segments
        for seg in image.segments:
            region = classify_address(seg.load_address)

            if is_code_region(region):
                flags = (SegmentFlag.SegmentContainsCode |
                         SegmentFlag.SegmentContainsData |
                         SegmentFlag.SegmentReadable |
                         SegmentFlag.SegmentExecutable)
            elif region == 'DROM':
                flags = (SegmentFlag.SegmentContainsData |
                         SegmentFlag.SegmentReadable |
                         SegmentFlag.SegmentDenyWrite)
            else:
                # DRAM, RTC, unknown
                flags = (SegmentFlag.SegmentContainsData |
                         SegmentFlag.SegmentReadable |
                         SegmentFlag.SegmentWritable)

            self.add_auto_segment(
                seg.load_address, seg.size,
                seg.file_offset, seg.size,
                flags)

            # Add sections with appropriate semantics
            if is_code_region(region):
                section_name = f"{region.lower()}_{seg.load_address:08x}"
                self.add_auto_section(
                    section_name, seg.load_address, seg.size,
                    SectionSemantics.ReadOnlyCodeSectionSemantics)
            elif region == 'DROM':
                section_name = f"drom_{seg.load_address:08x}"
                self.add_auto_section(
                    section_name, seg.load_address, seg.size,
                    SectionSemantics.ReadOnlyDataSectionSemantics)
            else:
                section_name = f"{region.lower()}_{seg.load_address:08x}"
                self.add_auto_section(
                    section_name, seg.load_address, seg.size,
                    SectionSemantics.ReadWriteDataSectionSemantics)

        # Create entry point function and symbol
        self.add_entry_point(self.entry_addr)
        self.define_auto_symbol(Symbol(
            SymbolType.FunctionSymbol, self.entry_addr, "entry"))

        # Load ROM symbols
        if load_rom:
            setup_esp32c3_rom(self)

        return True
