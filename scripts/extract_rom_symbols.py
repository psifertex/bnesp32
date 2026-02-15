#!/usr/bin/env python3
"""
Extract ROM symbols for all ESP32 chip variants from ELF files and linker scripts.

Produces JSON files in rom/<chip>_rom_symbols.json with the format:
{
    "functions": {"0x40047ef2": "ets_printf", ...},
    "data": {"0x3ff1ffe0": "some_data_sym", ...}
}

Sources:
1. ROM ELF files from https://github.com/espressif/esp-rom-elfs
2. ROM linker scripts (.rom.ld) from ESP-IDF
"""

import json
import os
import re
import sys
import tarfile
import urllib.request
from collections import OrderedDict
from pathlib import Path

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

# ── Configuration ──────────────────────────────────────────────────────────────

CHIPS = [
    "esp32", "esp32s2", "esp32s3",
    "esp32c2", "esp32c3", "esp32c5", "esp32c6",
    "esp32h2", "esp32p4",
]

# ROM code address ranges (addresses in this range are functions, others are data)
ROM_CODE_RANGES = {
    "esp32":   (0x40000000, 0x40070000),
    "esp32s2": (0x40000000, 0x40020000),
    "esp32s3": (0x40000000, 0x40060000),
    "esp32c2": (0x40000000, 0x40090000),
    "esp32c3": (0x40000000, 0x40060000),
    "esp32c5": (0x40000000, 0x40050000),
    "esp32c6": (0x40000000, 0x40050000),
    "esp32h2": (0x40000000, 0x40020000),
    "esp32p4": (0x4FC00000, 0x4FC20000),
}

ELF_ARCHIVE_URL = "https://github.com/espressif/esp-rom-elfs/releases/download/20241011/esp-rom-elfs-20241011.tar.gz"
ELF_ARCHIVE_PATH = Path("/tmp/esp-rom-elfs-20241011.tar.gz")
ELF_EXTRACT_DIR = Path("/tmp/esp-rom-elfs")

ROM_LD_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/espressif/esp-idf/master/"
    "components/esp_rom/{chip}/ld/{chip}.rom.ld"
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "rom"


# ── ELF Symbol Extraction ─────────────────────────────────────────────────────

def download_elf_archive():
    """Download the ROM ELF archive if not already present."""
    if ELF_ARCHIVE_PATH.exists():
        print(f"  ELF archive already downloaded: {ELF_ARCHIVE_PATH}")
        return

    print(f"  Downloading ELF archive from {ELF_ARCHIVE_URL}...")
    urllib.request.urlretrieve(ELF_ARCHIVE_URL, str(ELF_ARCHIVE_PATH))
    print(f"  Downloaded: {ELF_ARCHIVE_PATH.stat().st_size} bytes")


def extract_elf_archive():
    """Extract the ROM ELF archive if not already extracted."""
    if ELF_EXTRACT_DIR.exists() and any(ELF_EXTRACT_DIR.glob("*.elf")):
        print(f"  ELF archive already extracted: {ELF_EXTRACT_DIR}")
        return

    print(f"  Extracting ELF archive to {ELF_EXTRACT_DIR}...")
    ELF_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(ELF_ARCHIVE_PATH), "r:gz") as tar:
        tar.extractall(str(ELF_EXTRACT_DIR), filter="data")
    print(f"  Extracted {len(list(ELF_EXTRACT_DIR.glob('*.elf')))} ELF files")


def find_best_elf(chip: str) -> Path:
    """Find the highest-revision ELF file for a chip."""
    pattern = f"{chip}_rev*_rom.elf"
    elfs = sorted(ELF_EXTRACT_DIR.glob(pattern))
    if not elfs:
        raise FileNotFoundError(f"No ELF files found for {chip} (pattern: {pattern})")

    # Parse revision numbers and pick the highest
    def rev_key(path: Path) -> int:
        m = re.search(r"_rev(\d+)_rom\.elf$", path.name)
        return int(m.group(1)) if m else 0

    best = max(elfs, key=rev_key)
    return best


def extract_elf_symbols(elf_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """
    Extract function and data symbols from a ROM ELF file.

    Returns (functions, data) where each is {hex_addr_str: name}.
    """
    functions = {}
    data = {}

    with open(elf_path, "rb") as f:
        elf = ELFFile(f)

        # Build set of BSS section indices (SHT_NOBITS or name contains 'bss')
        bss_indices = set()
        for i, section in enumerate(elf.iter_sections()):
            if section["sh_type"] == "SHT_NOBITS" or "bss" in section.name.lower():
                bss_indices.add(i)

        # Extract symbols
        for section in elf.iter_sections():
            if not isinstance(section, SymbolTableSection):
                continue

            for sym in section.iter_symbols():
                addr = sym.entry["st_value"]
                stype = sym.entry["st_info"]["type"]
                name = sym.name
                shndx = sym.entry["st_shndx"]

                # Skip: no address, no name, mapping symbols ($x, $d, etc.)
                if addr == 0 or not name or name.startswith("$"):
                    continue

                # Skip symbols in BSS sections
                if isinstance(shndx, int) and shndx in bss_indices:
                    continue

                addr_str = f"0x{addr:08x}"

                if stype == "STT_FUNC":
                    functions[addr_str] = name
                elif stype == "STT_OBJECT":
                    data[addr_str] = name

    return functions, data


# ── Linker Script Parsing ──────────────────────────────────────────────────────

def download_rom_ld(chip: str) -> str | None:
    """Download the .rom.ld file for a chip. Returns content or None on failure."""
    url = ROM_LD_URL_TEMPLATE.format(chip=chip)
    try:
        response = urllib.request.urlopen(url)
        content = response.read().decode("utf-8")
        return content
    except Exception as e:
        print(f"  Warning: Could not download {url}: {e}")
        return None


def parse_rom_ld(content: str, chip: str) -> tuple[dict[str, str], dict[str, str]]:
    """
    Parse a .rom.ld file and classify symbols as functions or data.

    Handles two patterns:
    - Bare assignment: symbol_name = 0xADDRESS;
    - PROVIDE statement: PROVIDE ( symbol_name = 0xADDRESS );

    Returns (functions, data) dicts.
    """
    functions = {}
    data = {}

    code_lo, code_hi = ROM_CODE_RANGES[chip]

    # Pattern for PROVIDE( symbol = 0xADDR );
    # Allow optional space variations
    provide_re = re.compile(
        r"PROVIDE\s*\(\s*(\w+)\s*=\s*(0x[0-9a-fA-F]+)\s*\)\s*;"
    )

    # Pattern for bare assignment: symbol = 0xADDR;
    # Must not be inside PROVIDE, so we match lines that don't start with PROVIDE
    bare_re = re.compile(
        r"^(\w+)\s*=\s*(0x[0-9a-fA-F]+)\s*;", re.MULTILINE
    )

    symbols = {}

    for m in provide_re.finditer(content):
        name, addr_s = m.group(1), m.group(2)
        addr = int(addr_s, 16)
        symbols[addr] = name

    for m in bare_re.finditer(content):
        name, addr_s = m.group(1), m.group(2)
        addr = int(addr_s, 16)
        symbols[addr] = name

    for addr, name in symbols.items():
        addr_str = f"0x{addr:08x}"
        if code_lo <= addr < code_hi:
            functions[addr_str] = name
        else:
            data[addr_str] = name

    return functions, data


# ── Merging ────────────────────────────────────────────────────────────────────

def merge_symbols(
    elf_funcs: dict[str, str], elf_data: dict[str, str],
    ld_funcs: dict[str, str], ld_data: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Merge ELF and .rom.ld symbols.

    - Start with ELF symbols
    - Add .rom.ld symbols not already present (by address)
    - If same address in both, prefer the .rom.ld name (official public name)
    """
    functions = dict(elf_funcs)
    data = dict(elf_data)

    # Overlay .rom.ld names (they take priority for same address)
    for addr, name in ld_funcs.items():
        functions[addr] = name

    for addr, name in ld_data.items():
        data[addr] = name

    return functions, data


def sort_by_address(d: dict[str, str]) -> dict[str, str]:
    """Sort a dict of {hex_addr: name} by numeric address value."""
    return dict(sorted(d.items(), key=lambda kv: int(kv[0], 16)))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== ESP32 ROM Symbol Extraction ===\n")

    # Step 1: Download and extract ELF archive
    print("Step 1: ROM ELF files")
    download_elf_archive()
    extract_elf_archive()
    print()

    summary = []

    for chip in CHIPS:
        print(f"--- {chip} ---")

        # Step 2: Extract ELF symbols
        try:
            elf_path = find_best_elf(chip)
            print(f"  ELF: {elf_path.name}")
            elf_funcs, elf_data = extract_elf_symbols(elf_path)
            print(f"  ELF symbols: {len(elf_funcs)} functions, {len(elf_data)} data")
        except FileNotFoundError as e:
            print(f"  {e}")
            elf_funcs, elf_data = {}, {}

        # Step 3: Download and parse .rom.ld
        print(f"  Downloading {chip}.rom.ld...")
        ld_content = download_rom_ld(chip)
        if ld_content:
            ld_funcs, ld_data = parse_rom_ld(ld_content, chip)
            print(f"  LD symbols: {len(ld_funcs)} functions, {len(ld_data)} data")
        else:
            ld_funcs, ld_data = {}, {}

        # Step 4: Merge
        functions, data_syms = merge_symbols(elf_funcs, elf_data, ld_funcs, ld_data)
        functions = sort_by_address(functions)
        data_syms = sort_by_address(data_syms)
        print(f"  Merged: {len(functions)} functions, {len(data_syms)} data")

        # Step 5: Write JSON
        output_path = OUTPUT_DIR / f"{chip}_rom_symbols.json"
        output = OrderedDict([
            ("functions", functions),
            ("data", data_syms),
        ])
        with open(output_path, "w") as f:
            json.dump(output, f, indent=1)
            f.write("\n")
        print(f"  Written: {output_path}")

        summary.append((chip, len(functions), len(data_syms)))
        print()

    # Summary table
    print("=" * 55)
    print(f"{'Chip':<12} {'Functions':>10} {'Data':>10} {'Total':>10}")
    print("-" * 55)
    for chip, nf, nd in summary:
        print(f"{chip:<12} {nf:>10} {nd:>10} {nf + nd:>10}")
    print("=" * 55)

    # Validation against existing esp32c3 file
    existing_path = PROJECT_DIR / "esp32c3_rom_symbols.json"
    new_path = OUTPUT_DIR / "esp32c3_rom_symbols.json"
    if existing_path.exists() and new_path.exists():
        print("\n--- Validation: esp32c3 ---")
        with open(existing_path) as f:
            old = json.load(f)
        with open(new_path) as f:
            new = json.load(f)
        old_f = len(old.get("functions", {}))
        old_d = len(old.get("data", {}))
        new_f = len(new.get("functions", {}))
        new_d = len(new.get("data", {}))
        print(f"  Existing: {old_f} functions, {old_d} data (total {old_f + old_d})")
        print(f"  New:      {new_f} functions, {new_d} data (total {new_f + new_d})")

        # Check overlap
        old_func_addrs = set(old["functions"].keys())
        new_func_addrs = set(new["functions"].keys())
        common = old_func_addrs & new_func_addrs
        only_old = old_func_addrs - new_func_addrs
        only_new = new_func_addrs - old_func_addrs
        print(f"  Function addresses: {len(common)} shared, "
              f"{len(only_old)} only in existing, {len(only_new)} only in new")

    print("\nDone.")


if __name__ == "__main__":
    main()
