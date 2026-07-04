---
name: fnv-bsa
description: Read, extract, list, and create Fallout New Vegas BSA archives using BSArch.
paths: "**/*.bsa"
---

# BSA Archive Operations (FNV)

> **Preferred:** `bash tools/automod-cli.sh bsa <list|unpack|pack|extract-file> ... --json` (wraps BSArch, auto-detected) — see `docs/automod-cli.md`. Raw BSArch usage below for reference.
> **With the MO2 MCP running** (`mcp__mo2__*` present): prefer `mo2_list_bsa` / `mo2_extract_bsa` / `mo2_extract_bsa_file` / `mo2_validate_bsa` — they take a **VFS path** and resolve it for you, and extracts land in the output mod.

FNV uses **BSA only** (older archive version — **no BA2**). Use **BSArch** (public CLI, ships with xEdit) for archive work.

## Commands (BSArch)
```bash
# List contents:
BSArch.exe list "Archive.bsa"

# Extract everything to a folder:
BSArch.exe unpack "Archive.bsa" "<output_dir>"

# Create a new BSA from a folder (pick the FNV/FO3 format):
BSArch.exe pack "<source_dir>" "NewArchive.bsa" -fo3 -z
```
(Run `BSArch.exe` with no args for the exact flag list of your version; `-fo3` selects the Fallout 3/NV archive format, `-z` enables compression.)

## Key rules
- **Loose files always override BSA contents** — before assuming BSA content loads, check for a loose file of the same path in `Data/` (or a higher-priority MO2 mod).
- A BSA is loaded if a plugin of the **same base name** is active (e.g. `MyMod.bsa` ↔ `MyMod.esp`) or if listed in the INI archives.
- **MO2:** extract/repack into a **mod folder**; new loose files go in `mods/<YourMod>/…` or `overwrite/`, enabled in MO2 — not the real `Data/`.

## Common tasks
- **Inspect a vanilla asset**: `list` to find the path, `unpack` (or extract a single file) to read it.
- **Repack a mod's loose files** into a BSA to reduce loose-file count and loading stutter.
- **Audit**: list a BSA to see what paths it provides (useful for conflict reasoning).

> See `KNOWLEDGEBASE.md → BSA Archives`. Vanilla audio is in `Fallout - Voices1.bsa` / `Fallout - Sound.bsa`; meshes in `Fallout - Meshes.bsa`.
