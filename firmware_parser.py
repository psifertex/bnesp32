"""
ESP32-C3 firmware image parser.

Parses the ESP-IDF extended header format used by ESP32-series chips.
The ESP32-C3 uses a 24-byte header (8 common + 16 extended) followed by
segments, a checksum byte, and an optional SHA256 hash.
"""
import struct


# ESP32-C3 memory regions
MEMORY_REGIONS = {
    'DROM':  (0x3C000000, 0x3C800000),  # Flash-mapped read-only data
    'DRAM':  (0x3FC80000, 0x3FCE0000),  # Internal data RAM
    'ROM':   (0x40000000, 0x40060000),  # Internal mask ROM
    'IRAM':  (0x4037C000, 0x403E0000),  # Internal instruction RAM
    'IROM':  (0x42000000, 0x42800000),  # Flash-mapped code
    'RTC':   (0x50000000, 0x50002000),  # RTC FAST memory
}


def classify_address(addr):
    """Classify a memory address into its ESP32-C3 memory region."""
    for name, (start, end) in MEMORY_REGIONS.items():
        if start <= addr < end:
            return name
    return 'UNKNOWN'


def is_code_region(region):
    """Return True if the region contains executable code."""
    return region in ('IRAM', 'IROM', 'ROM')


def is_writable_region(region):
    """Return True if the region is writable."""
    return region in ('DRAM', 'RTC')


class ESP32C3Segment:
    """A single loadable segment from an ESP32-C3 firmware image."""

    HEADER_FMT = '<II'
    HEADER_SIZE = struct.calcsize(HEADER_FMT)  # 8 bytes

    def __init__(self, load_address, size, file_offset):
        self.load_address = load_address
        self.size = size
        self.file_offset = file_offset  # offset of segment DATA in file

    @property
    def region(self):
        return classify_address(self.load_address)

    @property
    def is_code(self):
        return is_code_region(self.region)

    @property
    def is_writable(self):
        return is_writable_region(self.region)

    def __repr__(self):
        return (f"ESP32C3Segment(addr=0x{self.load_address:08x}, "
                f"size=0x{self.size:x}, offset=0x{self.file_offset:x}, "
                f"region={self.region})")


class ESP32C3Image:
    """Parsed ESP32-C3 firmware image."""

    COMMON_HEADER_FMT = '<BBBBI'
    COMMON_HEADER_SIZE = struct.calcsize(COMMON_HEADER_FMT)  # 8 bytes
    EXTENDED_HEADER_SIZE = 16  # bytes 0x08-0x17
    TOTAL_HEADER_SIZE = COMMON_HEADER_SIZE + EXTENDED_HEADER_SIZE  # 24

    ESP_IMAGE_MAGIC = 0xE9
    ESP32C3_CHIP_ID = 0x0005

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

    @property
    def segments(self):
        return list(self._segments)

    @classmethod
    def from_binary_view(cls, bv):
        """Parse an ESP32-C3 image from a Binary Ninja BinaryView."""
        header_data = bv.read(0, cls.TOTAL_HEADER_SIZE)
        if len(header_data) < cls.TOTAL_HEADER_SIZE:
            return None
        return cls._parse(header_data, lambda off, sz: bv.read(off, sz), bv.length)

    @classmethod
    def from_bytes(cls, data):
        """Parse an ESP32-C3 image from raw bytes."""
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

        if img.chip_id != cls.ESP32C3_CHIP_ID:
            return None

        # Parse segments
        offset = cls.TOTAL_HEADER_SIZE
        for _ in range(img.segment_count):
            seg_header = read_fn(offset, ESP32C3Segment.HEADER_SIZE)
            if len(seg_header) < ESP32C3Segment.HEADER_SIZE:
                return None
            load_addr, size = struct.unpack(ESP32C3Segment.HEADER_FMT, seg_header)
            data_offset = offset + ESP32C3Segment.HEADER_SIZE
            img._segments.append(ESP32C3Segment(load_addr, size, data_offset))
            offset = data_offset + size

        # Checksum is at next 16-byte aligned position
        align = (16 - 1) - (offset % 16)
        checksum_offset = offset + align
        img.image_size = checksum_offset + 1

        if img.append_digest:
            img.image_size += 32  # SHA256

        return img


def parse_esp32c3(bv):
    """Parse an ESP32-C3 firmware image from a BinaryView. Returns ESP32C3Image or None."""
    return ESP32C3Image.from_binary_view(bv)
