"""
ESP32-C3 firmware loader test suite.

Uses Binary Ninja's headless Python API for validation.
Run with: pytest tests/test_esp32c3.py -v
"""
import os
import sys
import struct
import pytest

# Ensure the plugin is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TEST_FIRMWARE = '/tmp/temp.bin'


# ===========================================================================
# Unit tests: firmware parser
# ===========================================================================

class TestFirmwareParser:
    """Unit tests for the ESP32-C3 firmware parser."""

    def test_parse_from_bytes(self):
        from firmware_parser import ESP32C3Image
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESP32C3Image.from_bytes(data)
        assert img is not None, "Failed to parse firmware"

    def test_header_fields(self):
        from firmware_parser import ESP32C3Image
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESP32C3Image.from_bytes(data)
        assert img.magic == 0xE9
        assert img.chip_id == 0x0005
        assert img.segment_count == 6
        assert img.entry_point == 0x4038208a
        assert img.append_digest == 1

    def test_segment_count(self):
        from firmware_parser import ESP32C3Image
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESP32C3Image.from_bytes(data)
        assert len(img.segments) == 6

    def test_segment_addresses_in_valid_regions(self):
        from firmware_parser import ESP32C3Image, classify_address
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESP32C3Image.from_bytes(data)
        for seg in img.segments:
            region = classify_address(seg.load_address)
            assert region != 'UNKNOWN', \
                f"Segment at 0x{seg.load_address:08x} in unknown region"

    def test_segment_regions(self):
        """Verify each segment maps to the expected memory region."""
        from firmware_parser import ESP32C3Image
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESP32C3Image.from_bytes(data)
        expected_regions = ['DROM', 'DRAM', 'IRAM', 'IROM', 'IRAM', 'RTC']
        actual_regions = [seg.region for seg in img.segments]
        assert actual_regions == expected_regions

    def test_image_size_matches_file(self):
        from firmware_parser import ESP32C3Image
        with open(TEST_FIRMWARE, 'rb') as f:
            data = f.read()
        img = ESP32C3Image.from_bytes(data)
        assert img.image_size == len(data), \
            f"Image size 0x{img.image_size:x} != file size 0x{len(data):x}"

    def test_rejects_non_esp32c3(self):
        """Verify parser rejects images with wrong chip_id."""
        from firmware_parser import ESP32C3Image
        with open(TEST_FIRMWARE, 'rb') as f:
            data = bytearray(f.read())
        # Change chip_id to ESP32 (0x0000)
        struct.pack_into('<H', data, 0x0C, 0x0000)
        img = ESP32C3Image.from_bytes(bytes(data))
        assert img is None

    def test_rejects_bad_magic(self):
        from firmware_parser import ESP32C3Image
        data = b'\x00' * 1024
        img = ESP32C3Image.from_bytes(data)
        assert img is None


# ===========================================================================
# Integration tests: BinaryView loading (requires binaryninja)
# ===========================================================================

@pytest.fixture(scope='module')
def bv():
    """Load firmware via the ESP32C3Firmware BinaryView."""
    import binaryninja
    # Plugin is auto-loaded by BN if symlinked into the plugins directory.
    # If not, register it manually.
    try:
        bvt = binaryninja.BinaryViewType['ESP32C3Firmware']
    except KeyError:
        from binaryview import ESP32C3Firmware
        ESP32C3Firmware.register()
        bvt = binaryninja.BinaryViewType['ESP32C3Firmware']

    view = bvt.open(TEST_FIRMWARE)
    assert view is not None, "Failed to open firmware as ESP32C3Firmware"
    yield view


@pytest.fixture(scope='module')
def analyzed_bv(bv):
    """BinaryView with analysis completed."""
    bv.update_analysis_and_wait()
    yield bv


class TestBinaryViewLoading:
    """Integration tests for the ESP32C3Firmware BinaryView."""

    def test_architecture_is_riscv(self, bv):
        assert bv.arch.name == 'rv32gc'

    def test_entry_point(self, bv):
        assert bv.entry_point == 0x4038208a

    def test_segment_count(self, bv):
        # 6 firmware segments + 1 ROM segment = 7 minimum
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
        assert sym.address == 0x40047ef2

    def test_software_reset(self, bv):
        sym = bv.get_symbol_by_raw_name('software_reset')
        assert sym is not None, "software_reset not found"
        assert sym.address == 0x40048392

    def test_uart_tx_one_char(self, bv):
        sym = bv.get_symbol_by_raw_name('uart_tx_one_char')
        assert sym is not None
        assert sym.address == 0x4004bb50

    def test_c_library_symbols(self, bv):
        """Verify C library ROM symbols from ELF are present."""
        for name in ['bzero', '__udivdi3', 'memcpy', 'memset', 'strlen']:
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
