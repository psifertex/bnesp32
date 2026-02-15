# ESP32 Firmware Loader for Binary Ninja

A Binary Ninja plugin that loads ESP32-series firmware images built with ESP-IDF or PlatformIO. Auto-detects the chip variant from the firmware header and configures the correct architecture, memory map, and ROM symbols.

## Supported Chips

| Chip | Chip ID | Architecture | ROM Symbols | Notes |
|------|---------|-------------|-------------|-------|
| ESP32 | 0x0000 | Xtensa LX6 | 2,713 | Requires [xtensa architecture plugin](https://github.com/zackorndorff/binja-xtensa) |
| ESP32-S2 | 0x0002 | Xtensa LX7 | 1,107 | Requires xtensa architecture plugin |
| ESP32-S3 | 0x0009 | Xtensa LX7 | 3,545 | Requires xtensa architecture plugin |
| ESP32-C2 | 0x000C | RISC-V | 4,690 | Built-in `rv32gc` architecture |
| ESP32-C3 | 0x0005 | RISC-V | 3,055 | Built-in `rv32gc` architecture |
| ESP32-C5 | 0x0017 | RISC-V | 2,255 | Built-in `rv32gc` architecture |
| ESP32-C6 | 0x000D | RISC-V | 2,132 | Built-in `rv32gc` architecture |
| ESP32-H2 | 0x0010 | RISC-V | 1,221 | Built-in `rv32gc` architecture |
| ESP32-P4 | 0x0012 | RISC-V | 1,459 | Built-in `rv32gc` architecture |

RISC-V variants work out of the box with Binary Ninja's built-in `rv32gc` architecture. Xtensa variants (ESP32, ESP32-S2, ESP32-S3) require a third-party architecture plugin — the loader will detect the firmware and warn if the architecture is not available.

## Features

- Parses the ESP-IDF extended header format (magic `0xE9`) for all ESP32 chip variants
- Auto-detects the chip from the `chip_id` field in the extended header
- Creates segments at correct memory addresses per chip (IRAM, IROM, DRAM, DROM, RTC)
- Loads ROM function and data symbols extracted from official Espressif ROM ELFs and ESP-IDF linker scripts
- Identifies the entry point and kicks off auto-analysis

## Installation

Symlink this directory into your Binary Ninja plugins folder:

```bash
# macOS
ln -s /path/to/this/repo "$HOME/Library/Application Support/Binary Ninja/plugins/esp32-loader"

# Linux
ln -s /path/to/this/repo "$HOME/.binaryninja/plugins/esp32-loader"
```

## Usage

Open an ESP32 `.bin` firmware file in Binary Ninja. The loader will automatically detect it via the magic byte and chip ID, and offer to load it as "ESP32 Firmware."

A load setting is available to enable/disable ROM symbol loading.

## Testing

```bash
./run_tests.sh        # run all tests
./run_tests.sh -v     # verbose output
./run_tests.sh -k "TestChipsTable"  # run specific tests
```

Requires `pytest` and a Binary Ninja license (headless API). The test script uses Binary Ninja's `lastrun` file to locate the installation automatically.

Test firmware for all 9 chip variants is expected in `tests/firmware/` (not committed to the repo).

## Regenerating ROM Symbols

ROM symbols in `rom/` are pre-generated and committed. To regenerate them:

```bash
pip install pyelftools
python scripts/extract_rom_symbols.py
```

This downloads ROM ELFs from [espressif/esp-rom-elfs](https://github.com/espressif/esp-rom-elfs) and linker scripts from [espressif/esp-idf](https://github.com/espressif/esp-idf), then merges them into per-chip JSON files.

## Credits

ROM symbols were extracted from two sources:

- **ROM ELFs**: Official ROM ELFs from [espressif/esp-rom-elfs](https://github.com/espressif/esp-rom-elfs) (Apache 2.0, Copyright 2015-2022 Espressif Systems).
- **Linker scripts**: ESP-IDF ROM linker scripts from [espressif/esp-idf](https://github.com/espressif/esp-idf) (`components/esp_rom/<chip>/ld/`).

The [ghidra-esp32-flash-loader](https://github.com/dynacylabs/ghidra-esp32-flash-loader) project (dynacylabs) was a reference for the firmware format and ROM ELF approach.

## License

MIT
