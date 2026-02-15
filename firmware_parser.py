"""
ESP32 firmware image parser.

Parses the ESP-IDF extended header format used by all ESP32-series chips.
The header is 24 bytes (8 common + 16 extended) followed by segments,
a checksum byte, and an optional SHA256 hash.
"""
import struct

try:
    from .chips import CHIPS, is_code_region, is_writable_region
except ImportError:
    from chips import CHIPS, is_code_region, is_writable_region


class ESPSegment:
    """A single loadable segment from an ESP32 firmware image."""

    HEADER_FMT = '<II'
    HEADER_SIZE = struct.calcsize(HEADER_FMT)  # 8 bytes

    def __init__(self, load_address, size, file_offset, region):
        self.load_address = load_address
        self.size = size
        self.file_offset = file_offset  # offset of segment DATA in file
        self.region = region
        self.is_code = is_code_region(region)
        self.is_writable = is_writable_region(region)

    def __repr__(self):
        return (f"ESPSegment(addr=0x{self.load_address:08x}, "
                f"size=0x{self.size:x}, offset=0x{self.file_offset:x}, "
                f"region={self.region})")


class ESPImage:
    """Parsed ESP32 firmware image (any chip variant)."""

    COMMON_HEADER_FMT = '<BBBBI'
    COMMON_HEADER_SIZE = struct.calcsize(COMMON_HEADER_FMT)  # 8 bytes
    EXTENDED_HEADER_SIZE = 16  # bytes 0x08-0x17
    TOTAL_HEADER_SIZE = COMMON_HEADER_SIZE + EXTENDED_HEADER_SIZE  # 24

    ESP_IMAGE_MAGIC = 0xE9

    def __init__(self):
        # Common header
        self.magic = 0
        self.segment_count = 0
        self.flash_mode = 0
        self.flash_size_freq = 0
        self.entry_point = 0
        # Extended header
        self.wp_pin = 0
        self.chip_id = 0
        self.min_rev = 0
        self.min_rev_full = 0
        self.max_rev_full = 0
        self.append_digest = 0
        # Parsed data
        self._segments = []
        self.image_size = 0
        self.chip_def = None

    @property
    def segments(self):
        return list(self._segments)

    @classmethod
    def from_binary_view(cls, bv):
        """Parse an ESP32 image from a Binary Ninja BinaryView."""
        header_data = bv.read(0, cls.TOTAL_HEADER_SIZE)
        if len(header_data) < cls.TOTAL_HEADER_SIZE:
            return None
        return cls._parse(header_data, lambda off, sz: bv.read(off, sz), bv.length)

    @classmethod
    def from_bytes(cls, data):
        """Parse an ESP32 image from raw bytes."""
        if len(data) < cls.TOTAL_HEADER_SIZE:
            return None
        return cls._parse(data[:cls.TOTAL_HEADER_SIZE],
                          lambda off, sz: data[off:off + sz], len(data))

    @classmethod
    def _parse(cls, header_data, read_fn, total_size):
        img = cls()

        # Common header (8 bytes)
        (img.magic, img.segment_count, img.flash_mode,
         img.flash_size_freq, img.entry_point) = struct.unpack_from(
            cls.COMMON_HEADER_FMT, header_data, 0)

        if img.magic != cls.ESP_IMAGE_MAGIC:
            return None

        # Extended header (16 bytes at offset 0x08)
        img.wp_pin = header_data[0x08]
        img.chip_id = struct.unpack_from('<H', header_data, 0x0C)[0]
        img.min_rev = header_data[0x0E]
        img.min_rev_full = struct.unpack_from('<H', header_data, 0x0F)[0]
        img.max_rev_full = struct.unpack_from('<H', header_data, 0x11)[0]
        img.append_digest = header_data[0x17]

        # Look up chip definition
        chip_def = CHIPS.get(img.chip_id)
        if chip_def is None:
            return None
        img.chip_def = chip_def

        # Parse segments
        offset = cls.TOTAL_HEADER_SIZE
        for _ in range(img.segment_count):
            seg_header = read_fn(offset, ESPSegment.HEADER_SIZE)
            if len(seg_header) < ESPSegment.HEADER_SIZE:
                return None
            load_addr, size = struct.unpack(ESPSegment.HEADER_FMT, seg_header)
            data_offset = offset + ESPSegment.HEADER_SIZE
            region = chip_def.classify_address(load_addr)
            img._segments.append(ESPSegment(load_addr, size, data_offset, region))
            offset = data_offset + size

        # Checksum is at next 16-byte aligned position
        align = (16 - 1) - (offset % 16)
        checksum_offset = offset + align
        img.image_size = checksum_offset + 1

        if img.append_digest:
            img.image_size += 32  # SHA256

        return img


def parse_esp32(bv):
    """Parse an ESP32 firmware image from a BinaryView. Returns ESPImage or None."""
    return ESPImage.from_binary_view(bv)
