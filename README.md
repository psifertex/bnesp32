# ESP32-C3 Firmware Loader for Binary Ninja

A Binary Ninja plugin that loads ESP32-C3 (RISC-V) firmware images built with ESP-IDF or PlatformIO.

## Features

- Parses the ESP-IDF extended header format (magic `0xE9`, chip ID `0x0005`)
- Creates segments at correct ESP32-C3 memory addresses (IRAM, IROM, DRAM, DROM, RTC)
- Uses Binary Ninja's built-in `rv32gc` architecture — no custom architecture needed
- Loads 2,600+ ROM function and data symbols (C library, BLE/WiFi, crypto, boot ROM, compiler builtins)
- Identifies the entry point and kicks off auto-analysis

## Installation

Symlink this directory into your Binary Ninja plugins folder:

```bash
ln -s /path/to/this/repo "$HOME/Library/Application Support/Binary Ninja/plugins/esp32-c3"
```

## Usage

Open an ESP32-C3 `.bin` firmware file in Binary Ninja. The loader will automatically detect it via the magic byte and chip ID, and offer to load it as "ESP32-C3 Firmware."

## Testing

```bash
./tests/run_tests.sh
```

Requires `pytest` and a Binary Ninja license (headless API).

## Credits

ROM symbols were extracted from two sources:

- **ROM ELF**: Official ESP32-C3 ROM ELF from [espressif/esp-rom-elfs](https://github.com/espressif/esp-rom-elfs) (Apache 2.0, Copyright 2015-2022 Espressif Systems). Provides 1,968 function symbols with actual implementation addresses.
- **Jump table entries**: ESP-IDF linker scripts from [espressif/esp-idf](https://github.com/espressif/esp-idf) (`components/esp_rom/esp32c3/ld/`). Provides 658 additional stable API entry points.

The [ghidra-esp32-flash-loader](https://github.com/tslater2006/esp32_flash_loader) project (by tslater2006, with forks by Ebiroll, dynacylabs, and saibotk) was the reference for discovering the ROM ELF approach.

## License

MIT
