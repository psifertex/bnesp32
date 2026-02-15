"""
ESP32 firmware loader test suite.

Uses Binary Ninja's headless Python API for validation.
Run with: ./run_tests.sh -v
"""
import os
import sys
import struct
import pytest

# Ensure the plugin is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

FIRMWARE_DIR = os.path.join(os.path.dirname(__file__), 'firmware')
TEST_FIRMWARE = os.path.join(FIRMWARE_DIR, 'esp32c3.bin')
# Fallback for backward compatibility
if not os.path.exists(TEST_FIRMWARE) and os.path.exists('/tmp/temp.bin'):
    TEST_FIRMWARE = '/tmp/temp.bin'


# ===========================================================================
# Unit tests: chips table
# ===========================================================================

class TestChipsTable:
    """Tests for the chip definition table."""

    def test_all_expected_chips_present(self):
        from chips import CHIPS
        expected_ids = {0x0000, 0x0002, 0x0005, 0x0009, 0x000C, 0x000D, 0x0010, 0x0012, 0x0017}
        assert set(CHIPS.keys()) == expected_ids

    def test_chip_names(self):
        from chips import CHIPS
        expected = {
            0x0000: "ESP32", 0x0002: "ESP32-S2", 0x0005: "ESP32-C3",
            0x0009: "ESP32-S3", 0x000C: "ESP32-C2", 0x000D: "ESP32-C6",
            0x0010: "ESP32-H2", 0x0012: "ESP32-P4", 0x0017: "ESP32-C5",
        }
        for chip_id, name in expected.items():
            assert CHIPS[chip_id].name == name

    def test_chip_architectures(self):
        from chips import CHIPS
        xtensa_ids = {0x0000, 0x0002, 0x0009}
        riscv_ids = {0x0005, 0x000C, 0x000D, 0x0010, 0x0012, 0x0017}
        for chip_id in xtensa_ids:
            assert CHIPS[chip_id].arch == "xtensa"
        for chip_id in riscv_ids:
            assert CHIPS[chip_id].arch == "rv32gc"

    def test_memory_regions_non_empty(self):
        from chips import CHIPS
        for chip_id, chip_def in CHIPS.items():
            assert len(chip_def.memory_regions) >= 4, \
                f"{chip_def.name} has too few memory regions"

    def test_required_regions_present(self):
        from chips import CHIPS
        # Every chip must have DROM, DRAM, ROM, IRAM, IROM
        required = {'DROM', 'DRAM', 'ROM', 'IRAM', 'IROM'}
        for chip_id, chip_def in CHIPS.items():
            missing = required - set(chip_def.memory_regions.keys())
            assert not missing, \
                f"{chip_def.name} missing regions: {missing}"

    def test_classify_address(self):
        from chips import CHIPS
        c3 = CHIPS[0x0005]
        assert c3.classify_address(0x3C100000) == 'DROM'
        assert c3.classify_address(0x3FC90000) == 'DRAM'
        assert c3.classify_address(0x40010000) == 'ROM'
        assert c3.classify_address(0x40380000) == 'IRAM'
        assert c3.classify_address(0x42100000) == 'IROM'
        assert c3.classify_address(0x50000100) == 'RTC'
        assert c3.classify_address(0x00000000) == 'UNKNOWN'

    def test_classify_address_esp32p4(self):
        """ESP32-P4 has a different address layout."""
        from chips import CHIPS
        p4 = CHIPS[0x0012]
        assert p4.classify_address(0x4FC10000) == 'ROM'
        assert p4.classify_address(0x4FF10000) == 'DRAM'
        assert p4.classify_address(0x42000000) == 'DROM'


# ===========================================================================
# Unit tests: firmware parser
# ===========================================================================

class TestFirmwareParser:
    """Unit tests for the ESP32 firmware parser."""

    def test_parse_from_bytes(self):
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        assert img is not None, "Failed to parse firmware"

    def test_header_fields(self):
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        assert img.magic == 0xE9
        assert img.chip_id == 0x0005
        assert img.segment_count == 6
        assert img.entry_point == 0x4038208a
        assert img.append_digest == 1

    def test_chip_def_attached(self):
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        assert img.chip_def is not None
        assert img.chip_def.name == "ESP32-C3"

    def test_segment_count(self):
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        assert len(img.segments) == 6

    def test_segment_addresses_in_valid_regions(self):
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        for seg in img.segments:
            assert seg.region != 'UNKNOWN', \
                f"Segment at 0x{seg.load_address:08x} in unknown region"

    def test_segment_regions(self):
        """Verify each segment maps to the expected memory region."""
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        expected_regions = ['DROM', 'DRAM', 'IRAM', 'IROM', 'IRAM', 'RTC']
        actual_regions = [seg.region for seg in img.segments]
        assert actual_regions == expected_regions

    def test_segment_is_code_flag(self):
        """Verify is_code is set at parse time."""
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        for seg in img.segments:
            if seg.region in ('IRAM', 'IROM', 'ROM'):
                assert seg.is_code, f"Segment {seg.region} should be code"
            else:
                assert not seg.is_code, f"Segment {seg.region} should not be code"

    def test_image_size_matches_file(self):
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        assert img.image_size == len(data), \
            f"Image size 0x{img.image_size:x} != file size 0x{len(data):x}"

    def test_rejects_unknown_chip_id(self):
        """Verify parser rejects images with unknown chip_id."""
        from firmware_parser import ESPImage
        with open(TEST_FIRMWARE, 'rb') as f:
            data = bytearray(f.read())
        # Set chip_id to 0xFFFF (unknown)
        struct.pack_into('<H', data, 0x0C, 0xFFFF)
        img = ESPImage.from_bytes(bytes(data))
        assert img is None

    def test_accepts_all_known_chip_ids(self):
        """Verify parser accepts all chips in the CHIPS table."""
        from firmware_parser import ESPImage
        from chips import CHIPS
        with open(TEST_FIRMWARE, 'rb') as f:
            data = bytearray(f.read())
        for chip_id in CHIPS:
            struct.pack_into('<H', data, 0x0C, chip_id)
            img = ESPImage.from_bytes(bytes(data))
            assert img is not None, f"Failed to parse with chip_id 0x{chip_id:04x}"
            assert img.chip_id == chip_id
            assert img.chip_def.chip_id == chip_id

    def test_rejects_bad_magic(self):
        from firmware_parser import ESPImage
        data = b'\x00' * 1024
        img = ESPImage.from_bytes(data)
        assert img is None


# ===========================================================================
# Unit tests: multi-chip firmware parsing
# ===========================================================================

class TestMultiChipParsing:
    """Test parsing firmware files for all available chip variants."""

    @pytest.fixture(params=[
        f for f in os.listdir(FIRMWARE_DIR)
        if f.endswith('.bin')
    ] if os.path.isdir(FIRMWARE_DIR) else [])
    def firmware_file(self, request):
        return os.path.join(FIRMWARE_DIR, request.param)

    def test_parse_firmware(self, firmware_file):
        from firmware_parser import ESPImage
        with open(firmware_file, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        assert img is not None, f"Failed to parse {os.path.basename(firmware_file)}"
        assert img.magic == 0xE9
        assert img.chip_def is not None
        assert len(img.segments) > 0

    def test_segments_in_valid_regions(self, firmware_file):
        from firmware_parser import ESPImage
        with open(firmware_file, 'rb') as f:
            data = f.read()
        img = ESPImage.from_bytes(data)
        assert img is not None
        for seg in img.segments:
            assert seg.region != 'UNKNOWN', \
                f"{img.chip_def.name}: segment at 0x{seg.load_address:08x} in unknown region"


# ===========================================================================
# Integration tests: BinaryView loading (requires binaryninja)
# ===========================================================================

@pytest.fixture(scope='module')
def bv():
    """Load firmware via the ESPFirmware BinaryView."""
    import binaryninja
    # Plugin is auto-loaded by BN if symlinked into the plugins directory.
    # If not, register it manually.
    try:
        bvt = binaryninja.BinaryViewType['ESPFirmware']
    except KeyError:
        from binaryview import ESPFirmware
        ESPFirmware.register()
        bvt = binaryninja.BinaryViewType['ESPFirmware']

    view = bvt.open(TEST_FIRMWARE)
    assert view is not None, "Failed to open firmware as ESPFirmware"
    yield view


@pytest.fixture(scope='module')
def analyzed_bv(bv):
    """BinaryView with analysis completed."""
    bv.update_analysis_and_wait()
    yield bv


class TestBinaryViewLoading:
    """Integration tests for the ESPFirmware BinaryView."""

    def test_architecture_is_riscv(self, bv):
        assert bv.arch.name == 'rv32gc'

    def test_entry_point(self, bv):
        assert bv.entry_point == 0x4038208a

    def test_segment_count(self, bv):
        # 6 firmware segments + 1 ROM segment + 1 ROM data segment = 8 minimum
        assert len(bv.segments) >= 7

    def test_firmware_segments_present(self, bv):
        """Verify all firmware segments were created at correct addresses."""
        expected = [
            (0x3c130020, 0x121bf0),  # DROM
            (0x3fc8e800, 0x3cf4),    # DRAM
            (0x40380000, 0xa704),    # IRAM
            (0x42000020, 0x120828),  # IROM
            (0x4038a704, 0x3f08),    # IRAM
            (0x50000000, 0x1c),      # RTC
        ]
        seg_starts = {seg.start: seg for seg in bv.segments}
        for addr, size in expected:
            assert addr in seg_starts, \
                f"Missing segment at 0x{addr:08x}"
            assert seg_starts[addr].data_length == size, \
                f"Segment at 0x{addr:08x}: expected size 0x{size:x}, " \
                f"got 0x{seg_starts[addr].data_length:x}"

    def test_code_segments_executable(self, bv):
        code_addrs = [0x40380000, 0x4038a704, 0x42000020]
        for addr in code_addrs:
            seg = bv.get_segment_at(addr)
            assert seg is not None, f"No segment at 0x{addr:08x}"
            assert seg.executable, \
                f"Segment at 0x{addr:08x} should be executable"

    def test_data_segments_not_executable(self, bv):
        data_addrs = [0x3c130020, 0x3fc8e800]
        for addr in data_addrs:
            seg = bv.get_segment_at(addr)
            assert seg is not None, f"No segment at 0x{addr:08x}"
            assert not seg.executable, \
                f"Segment at 0x{addr:08x} should not be executable"

    def test_rom_segment_present(self, bv):
        seg = bv.get_segment_at(0x40000000)
        assert seg is not None, "ROM segment not present"
        assert seg.executable, "ROM segment should be executable"


class TestROMSymbols:
    """Test ROM symbol loading."""

    def test_ets_printf(self, bv):
        sym = bv.get_symbol_by_raw_name('ets_printf')
        assert sym is not None, "ets_printf not found"
        assert 0x40000000 <= sym.address < 0x40060000

    def test_software_reset(self, bv):
        sym = bv.get_symbol_by_raw_name('software_reset')
        assert sym is not None, "software_reset not found"
        assert 0x40000000 <= sym.address < 0x40060000

    def test_uart_tx_one_char(self, bv):
        sym = bv.get_symbol_by_raw_name('uart_tx_one_char')
        assert sym is not None
        assert 0x40000000 <= sym.address < 0x40060000

    def test_c_library_symbols(self, bv):
        """Verify C library ROM symbols from ELF are present."""
        for name in ['memcpy', 'memset', 'strlen']:
            sym = bv.get_symbol_by_raw_name(name)
            assert sym is not None, f"{name} not found"
            assert 0x40000000 <= sym.address < 0x40060000

    def test_symbol_count(self, bv):
        """Verify ROM symbols were loaded (ELF + jump table)."""
        rom_syms = [s for s in bv.get_symbols()
                    if 0x40000000 <= s.address < 0x40060000]
        assert len(rom_syms) > 2000, \
            f"Only {len(rom_syms)} ROM symbols, expected 2000+"


class TestAnalysis:
    """Smoke tests for auto-analysis."""

    def test_analysis_completes(self, analyzed_bv):
        """Analysis runs without error."""
        pass  # if we got here, analysis completed

    def test_entry_function_created(self, analyzed_bv):
        func = analyzed_bv.get_function_at(analyzed_bv.entry_point)
        assert func is not None, "No function at entry point"

    def test_functions_discovered(self, analyzed_bv):
        assert len(analyzed_bv.functions) > 100, \
            f"Only {len(analyzed_bv.functions)} functions discovered"

    def test_disassembly_at_entry(self, analyzed_bv):
        """Verify entry point contains valid RISC-V instructions."""
        func = analyzed_bv.get_function_at(analyzed_bv.entry_point)
        assert func is not None
        # Should have at least a few basic blocks
        assert len(list(func.basic_blocks)) > 0
