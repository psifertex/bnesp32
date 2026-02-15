"""
ESP32 Firmware BinaryView for Binary Ninja.

Loads ESP32-series firmware images (magic 0xE9) for all supported chip
variants. The chip is auto-detected from the extended header chip_id field.
"""
import json
import struct

from binaryninja import Architecture, BinaryView, Settings, Symbol, log_warn
from binaryninja.enums import SectionSemantics, SegmentFlag, SymbolType

try:
    from .chips import CHIPS, is_code_region
    from .firmware_parser import parse_esp32
    from .known_symbols import setup_rom_symbols
except ImportError:
    from chips import CHIPS, is_code_region
    from firmware_parser import parse_esp32
    from known_symbols import setup_rom_symbols


class ESPFirmware(BinaryView):
    name = "ESPFirmware"
    long_name = "ESP32 Firmware"

    def __init__(self, data):
        BinaryView.__init__(self, file_metadata=data.file, parent_view=data)
        self.raw = data

    @classmethod
    def is_valid_for_data(cls, data):
        """Check if this is a supported ESP32-series firmware image."""
        header = data.read(0, 24)
        if len(header) < 24:
            return False
        if header[0] != 0xE9:
            return False
        chip_id = struct.unpack_from('<H', header, 0x0C)[0]
        return chip_id in CHIPS

    @classmethod
    def get_load_settings_for_data(cls, data):
        image = parse_esp32(data)
        if image is None:
            return None

        chip_def = image.chip_def
        setting_id = f"loader.esp32.loadRomSymbols"

        load_settings = Settings("esp32_bv_settings")
        assert load_settings.register_group("loader", "Loader")

        setting = json.dumps({
            "title": f"Load {chip_def.name} ROM Symbols",
            "type": "boolean",
            "description": f"Load {chip_def.name} ROM function symbols",
            "default": True
        })
        assert load_settings.register_setting(setting_id, setting)

        return load_settings

    def perform_is_executable(self):
        return True

    def perform_get_entry_point(self):
        return self.entry_addr

    def perform_get_address_size(self):
        return 4

    def init(self):
        image = parse_esp32(self.parent_view)
        if image is None:
            return False

        chip_def = image.chip_def

        # Check architecture availability
        try:
            arch = Architecture[chip_def.arch]
        except KeyError:
            log_warn(f"ESP32 Loader: Architecture '{chip_def.arch}' not available. "
                     f"Install a {chip_def.arch} architecture plugin to analyze "
                     f"{chip_def.name} firmware.")
            return False

        self.platform = arch.standalone_platform
        self.arch = arch
        self.entry_addr = image.entry_point

        # Load ROM symbols setting
        load_rom = True
        try:
            load_settings = self.get_load_settings(self.name)
            load_rom = load_settings.get_bool(
                "loader.esp32.loadRomSymbols", self)
        except:
            pass

        # Add segments
        for seg in image.segments:
            if seg.is_code:
                flags = (SegmentFlag.SegmentContainsCode |
                         SegmentFlag.SegmentContainsData |
                         SegmentFlag.SegmentReadable |
                         SegmentFlag.SegmentExecutable)
            elif seg.region == 'DROM':
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
            if seg.is_code:
                section_name = f"{seg.region.lower()}_{seg.load_address:08x}"
                self.add_auto_section(
                    section_name, seg.load_address, seg.size,
                    SectionSemantics.ReadOnlyCodeSectionSemantics)
            elif seg.region == 'DROM':
                section_name = f"drom_{seg.load_address:08x}"
                self.add_auto_section(
                    section_name, seg.load_address, seg.size,
                    SectionSemantics.ReadOnlyDataSectionSemantics)
            else:
                section_name = f"{seg.region.lower()}_{seg.load_address:08x}"
                self.add_auto_section(
                    section_name, seg.load_address, seg.size,
                    SectionSemantics.ReadWriteDataSectionSemantics)

        # Create entry point function and symbol
        self.add_entry_point(self.entry_addr)
        self.define_auto_symbol(Symbol(
            SymbolType.FunctionSymbol, self.entry_addr, "entry"))

        # Load ROM symbols
        if load_rom:
            setup_rom_symbols(self, chip_def)

        return True
